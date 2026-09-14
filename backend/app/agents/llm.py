from __future__ import annotations

from typing import Protocol

from app.agents.policies import (
    fallback_card,
    fallback_hint,
    fallback_mentor_reply,
)
from app.agents.state import CardDraft
from app.core.config import settings


class CoachLLM(Protocol):
    def generate_card(
        self,
        concept: str,
        milestone_title: str,
        resources: list[dict[str, str]],
    ) -> CardDraft: ...

    def mentor_reply(
        self,
        *,
        milestone_title: str,
        constraints: list[str],
        success_criteria: str,
        current_concepts: list[str],
        learner_message: str,
    ) -> str: ...

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

    def mentor_reply(
        self,
        *,
        milestone_title: str,
        constraints: list[str],
        success_criteria: str,
        current_concepts: list[str],
        learner_message: str,
    ) -> str:
        return fallback_mentor_reply(
            milestone_title=milestone_title,
            constraints=constraints,
            success_criteria=success_criteria,
            current_concepts=current_concepts,
            learner_message=learner_message,
        )

    def hint_reply(self, level: int, milestone_title: str, concepts: list[str]) -> str:
        return fallback_hint(level, milestone_title, concepts)


def get_coach_llm() -> CoachLLM:
    if settings.llm_model.lower() in {"stub", "none", "fake"} or not settings.llm_api_key:
        return StubCoachLLM()
    try:
        from langchain.chat_models import init_chat_model

        model = init_chat_model(settings.llm_model)
        return LangChainCoachLLM(model)
    except Exception:
        return StubCoachLLM()


class LangChainCoachLLM:
    def __init__(self, model: object) -> None:
        self._model = model

    def _invoke(self, prompt: str) -> str:
        result = getattr(self._model, "invoke")(prompt)
        content = getattr(result, "content", result)
        return str(content)

    def generate_card(
        self,
        concept: str,
        milestone_title: str,
        resources: list[dict[str, str]],
    ) -> CardDraft:
        return fallback_card(concept, milestone_title, resources)

    def mentor_reply(
        self,
        *,
        milestone_title: str,
        constraints: list[str],
        success_criteria: str,
        current_concepts: list[str],
        learner_message: str,
    ) -> str:
        prompt = (
            "You are a senior engineer mentoring a junior. Ask what they think, "
            "expose missing assumptions, restate constraints, challenge architecture, "
            "then tell them to implement. Never paste a full solution or complete files.\n"
            f"Milestone: {milestone_title}\n"
            f"Constraints: {constraints}\n"
            f"Success: {success_criteria}\n"
            f"Concepts: {current_concepts}\n"
            f"Learner: {learner_message}\n"
        )
        try:
            return self._invoke(prompt)
        except Exception:
            return fallback_mentor_reply(
                milestone_title=milestone_title,
                constraints=constraints,
                success_criteria=success_criteria,
                current_concepts=current_concepts,
                learner_message=learner_message,
            )

    def hint_reply(self, level: int, milestone_title: str, concepts: list[str]) -> str:
        return fallback_hint(level, milestone_title, concepts)
