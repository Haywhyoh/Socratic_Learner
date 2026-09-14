from __future__ import annotations

import json
import os
import re
from typing import Protocol

from app.agents.policies import (
    fallback_card,
    fallback_evaluate,
    fallback_hint,
)
from app.agents.state import CardDraft, EvalResult
from app.core.config import settings


class CoachLLM(Protocol):
    def generate_card(
        self,
        concept: str,
        milestone_title: str,
        resources: list[dict[str, str]],
    ) -> CardDraft: ...

    def evaluate_answer(
        self,
        *,
        question: str,
        answer: str,
        milestone_title: str,
    ) -> EvalResult: ...

    def hint_reply(self, level: int, milestone_title: str, concepts: list[str]) -> str: ...


class StubCoachLLM:
    """Deterministic specialist used in tests and when no model key is configured."""

    def generate_card(
        self,
        concept: str,
        milestone_title: str,
        resources: list[dict[str, str]],
    ) -> CardDraft:
        return fallback_card(concept, milestone_title, resources)

    def evaluate_answer(
        self,
        *,
        question: str,
        answer: str,
        milestone_title: str,
    ) -> EvalResult:
        result = fallback_evaluate(question, answer)
        return {"passed": bool(result["passed"]), "push_back": result.get("push_back")}  # type: ignore[return-value]

    def hint_reply(self, level: int, milestone_title: str, concepts: list[str]) -> str:
        return fallback_hint(level, milestone_title, concepts)


def get_coach_llm() -> CoachLLM:
    model_name = (settings.llm_model or "stub").strip()
    api_key = settings.resolved_llm_api_key().strip()
    if model_name.lower() in {"stub", "none", "fake"} or not api_key:
        return StubCoachLLM()
    try:
        from langchain.chat_models import init_chat_model

        if model_name.lower().startswith("anthropic:") or "claude" in model_name.lower():
            os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
        else:
            os.environ.setdefault("OPENAI_API_KEY", api_key)

        model = init_chat_model(model_name, api_key=api_key)
        return LangChainCoachLLM(model)
    except Exception:
        return StubCoachLLM()


class LangChainCoachLLM:
    def __init__(self, model: object) -> None:
        self._model = model

    def _invoke(self, prompt: str) -> str:
        result = getattr(self._model, "invoke")(prompt)
        content = getattr(result, "content", result)
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    text = getattr(item, "text", None)
                    parts.append(str(text if text is not None else item))
            return "".join(parts)
        return str(content)

    def generate_card(
        self,
        concept: str,
        milestone_title: str,
        resources: list[dict[str, str]],
    ) -> CardDraft:
        return fallback_card(concept, milestone_title, resources)

    def evaluate_answer(
        self,
        *,
        question: str,
        answer: str,
        milestone_title: str,
    ) -> EvalResult:
        prompt = (
            "You evaluate a learner's understanding. "
            "Return ONLY JSON: {\"passed\": true|false, \"push_back\": null|\"one sentence\"}. "
            "passed=true if they show understanding. "
            "If not, push_back is ONE short question. Never explain the answer. Never give code.\n"
            f"Milestone: {milestone_title}\n"
            f"Question: {question}\n"
            f"Answer: {answer}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            passed = bool(payload.get("passed"))
            push = payload.get("push_back")
            if push is not None:
                push = str(push).strip() or None
            if passed:
                return {"passed": True, "push_back": None}
            return {
                "passed": False,
                "push_back": push or "Not enough. Answer in one clear sentence.",
            }
        except Exception:
            result = fallback_evaluate(question, answer)
            return {
                "passed": bool(result["passed"]),
                "push_back": result.get("push_back"),  # type: ignore[return-value]
            }

    def hint_reply(self, level: int, milestone_title: str, concepts: list[str]) -> str:
        return fallback_hint(level, milestone_title, concepts)
