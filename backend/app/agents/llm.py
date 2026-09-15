from __future__ import annotations

import json
import os
import re
from typing import Protocol

from app.agents.build_coach import (
    build_steps_for_milestone,
    enforce_single_build_step,
    format_step_header,
    resource_hint,
)
from app.agents.policies import (
    REVIEW_DIMENSIONS,
    fallback_card,
    fallback_curriculum,
    fallback_evaluate,
    fallback_hint,
    fallback_review,
    fallback_understanding,
    guidance_reply,
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

    def hint_reply(
        self,
        level: int,
        milestone_title: str,
        concepts: list[str],
        *,
        instructions: str = "",
    ) -> str: ...

    def mentor_reply(
        self,
        *,
        message: str,
        project_title: str,
        milestone_title: str,
        instructions: str,
        constraints: list[str],
        success_criteria: str,
        build_step_index: int = 0,
        build_steps: list[str] | None = None,
        resources: list[dict[str, str]] | None = None,
    ) -> str: ...

    def generate_curriculum(
        self,
        *,
        project_title: str,
        project_objective: str,
        language: str,
        framework: str,
        skills: list[str],
        concepts: list[str],
        constraints: list[str],
        tests: list[str],
        catalog: list[dict[str, object]],
    ) -> list[dict[str, object]]: ...

    def review_milestone(
        self,
        *,
        milestone_title: str,
        milestone_description: str,
        success_criteria: str,
        constraints: list[str],
        code_bundle: str,
        tests_passed: bool,
        test_summary: str,
    ) -> dict[str, object]: ...

    def evaluate_understanding(
        self,
        *,
        question: str,
        answer: str,
        milestone_title: str,
    ) -> dict[str, object]: ...


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

    def hint_reply(
        self,
        level: int,
        milestone_title: str,
        concepts: list[str],
        *,
        instructions: str = "",
    ) -> str:
        return fallback_hint(level, milestone_title, concepts, instructions=instructions)

    def mentor_reply(
        self,
        *,
        message: str,
        project_title: str,
        milestone_title: str,
        instructions: str,
        constraints: list[str],
        success_criteria: str,
        build_step_index: int = 0,
        build_steps: list[str] | None = None,
        resources: list[dict[str, str]] | None = None,
    ) -> str:
        steps = build_steps or build_steps_for_milestone(instructions)
        idx = max(0, min(build_step_index, max(len(steps) - 1, 0)))
        current = steps[idx] if steps else "Create the smallest runnable scaffold"
        total = max(len(steps), 1)
        header = format_step_header(step_index=idx, total=total, task=current)
        # Dependency / README steps: point at resources instead of dumping files.
        lower_task = current.lower()
        if any(k in lower_task for k in ("pyproject", "dependenc", "requirement", "readme")):
            return (
                f"{header}\n"
                + resource_hint(resources or [], topic=current)
            )
        return guidance_reply(
            message=f"{message}\n(Focus only on: {current})",
            milestone_title=milestone_title,
            instructions=f"1. {current}",
            constraints=constraints,
            success_criteria=success_criteria,
            project_title=project_title,
        )

    def generate_curriculum(
        self,
        *,
        project_title: str,
        project_objective: str,
        language: str,
        framework: str,
        skills: list[str],
        concepts: list[str],
        constraints: list[str],
        tests: list[str],
        catalog: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        return fallback_curriculum(catalog)

    def review_milestone(
        self,
        *,
        milestone_title: str,
        milestone_description: str,
        success_criteria: str,
        constraints: list[str],
        code_bundle: str,
        tests_passed: bool,
        test_summary: str,
    ) -> dict[str, object]:
        return fallback_review(
            code_bundle=code_bundle,
            tests_passed=tests_passed,
            milestone_title=milestone_title,
        )

    def evaluate_understanding(
        self,
        *,
        question: str,
        answer: str,
        milestone_title: str,
    ) -> dict[str, object]:
        return fallback_understanding(question, answer)


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

    def hint_reply(
        self,
        level: int,
        milestone_title: str,
        concepts: list[str],
        *,
        instructions: str = "",
    ) -> str:
        return fallback_hint(level, milestone_title, concepts, instructions=instructions)

    def mentor_reply(
        self,
        *,
        message: str,
        project_title: str,
        milestone_title: str,
        instructions: str,
        constraints: list[str],
        success_criteria: str,
        build_step_index: int = 0,
        build_steps: list[str] | None = None,
        resources: list[dict[str, str]] | None = None,
    ) -> str:
        steps = build_steps or build_steps_for_milestone(instructions)
        idx = max(0, min(build_step_index, max(len(steps) - 1, 0)))
        current = steps[idx] if steps else "Create the smallest runnable scaffold"
        total = max(len(steps), 1)
        header = format_step_header(step_index=idx, total=total, task=current)
        resource_lines = []
        for item in (resources or [])[:3]:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if title and url:
                resource_lines.append(f"- {title}: {url}")
        resource_block = "\n".join(resource_lines) or "- FastAPI docs: https://fastapi.tiangolo.com/"
        prompt = (
            "You are a senior engineer mentoring a beginner ONE STEP AT A TIME.\n"
            "Hard rules:\n"
            f"- ONLY help with this current step ({idx + 1} of {total}): {current}\n"
            "- Do NOT mention later steps, databases, CRUD, auth, or 'what's next'.\n"
            "- Give clear beginner instructions for THIS step only.\n"
            "- You MAY give exact terminal commands (mkdir, touch, uvicorn).\n"
            "- For dependency files (pyproject/requirements) or README: do NOT paste a full file. "
            "Tell them what fields/sections to include and point them at the resources below.\n"
            "- You MAY show one tiny /health FastAPI example (under 12 lines) only if this step needs it.\n"
            "- Never paste a multi-file app or long solution.\n"
            "- End by asking them to reply **done** (or paste terminal output) before the next step.\n\n"
            f"Project: {project_title or 'learner project'}\n"
            f"Milestone: {milestone_title or 'current'}\n"
            f"Current step header: {header}\n"
            f"Constraints: {', '.join(constraints) or 'n/a'}\n"
            f"Overall success criteria (do not jump ahead): {success_criteria or 'n/a'}\n"
            f"Recommended resources:\n{resource_block}\n"
            f"Learner message: {message}\n"
        )
        try:
            raw = self._invoke(prompt).strip()
            if raw:
                return enforce_single_build_step(f"{header}\n\n{raw}")
        except Exception:
            pass
        return guidance_reply(
            message=f"{message}\n(Focus only on: {current})",
            milestone_title=milestone_title,
            instructions=f"1. {current}",
            constraints=constraints,
            success_criteria=success_criteria,
            project_title=project_title,
        )

    def generate_curriculum(
        self,
        *,
        project_title: str,
        project_objective: str,
        language: str,
        framework: str,
        skills: list[str],
        concepts: list[str],
        constraints: list[str],
        tests: list[str],
        catalog: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        catalog_outline = "\n".join(
            f"- {item['title']}: {item['success_criteria']}" for item in catalog
        ) or "(no reference outline — invent a sensible progression)"
        prompt = (
            "You design a project-based curriculum for a learner building a real "
            f"project in {language}/{framework}. Never include actual code — only "
            "descriptions of what to build and why. Each milestone must build "
            "directly on the code from the previous one (same codebase, growing).\n\n"
            f"Project: {project_title}\n"
            f"Objective: {project_objective}\n"
            f"Skills to exercise: {', '.join(skills) or 'n/a'}\n"
            f"Concepts to cover: {', '.join(concepts) or 'n/a'}\n"
            f"Constraints: {', '.join(constraints) or 'n/a'}\n"
            f"Must eventually satisfy these tests: {', '.join(tests) or 'n/a'}\n"
            f"Reference outline (you may follow or improve on this):\n{catalog_outline}\n\n"
            "Return ONLY a JSON array of 3-5 milestones, each an object with keys: "
            'title (string), description (1-2 sentences), instructions '
            '(numbered "what to do" steps, no code), success_criteria (one concrete, '
            "testable sentence), concepts (array of 3-6 short concept names), "
            "questions (array of 2-3 short conceptual questions to ask the learner "
            "BEFORE they start coding this milestone, about the milestone's ideas — "
            "not about code they haven't written yet)."
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            milestones: list[dict[str, object]] = []
            for item in payload:
                milestones.append(
                    {
                        "title": str(item["title"]).strip(),
                        "description": str(item.get("description", "")).strip(),
                        "instructions": str(item.get("instructions", "")).strip(),
                        "success_criteria": str(item.get("success_criteria", "")).strip(),
                        "concepts": [str(c) for c in (item.get("concepts") or [])],
                        "questions": [str(q) for q in (item.get("questions") or [])],
                    }
                )
            if milestones:
                return milestones
        except Exception:
            pass
        return fallback_curriculum(catalog)

    def review_milestone(
        self,
        *,
        milestone_title: str,
        milestone_description: str,
        success_criteria: str,
        constraints: list[str],
        code_bundle: str,
        tests_passed: bool,
        test_summary: str,
    ) -> dict[str, object]:
        dims = ", ".join(REVIEW_DIMENSIONS)
        prompt = (
            "You are a senior engineer reviewing a learner's code for a milestone. "
            "Never rewrite or paste corrected code — only critique and ask questions. "
            f"Rate each of these dimensions as pass, concern, or fail: {dims}.\n\n"
            f"Milestone: {milestone_title}\n{milestone_description}\n"
            f"Success criteria: {success_criteria}\n"
            f"Constraints: {', '.join(constraints) or 'n/a'}\n"
            f"Automated tests: {'PASSED' if tests_passed else 'NOT PASSING'} — {test_summary}\n\n"
            f"Learner's current codebase:\n{code_bundle or '(empty)'}\n\n"
            "Return ONLY JSON: {\"dimensions\": {\"<dimension>\": {\"rating\": "
            '"pass"|"concern"|"fail", "notes": "one short sentence"}, ...}, '
            '"summary": "one or two sentence overall verdict, no code", '
            '"understanding_questions": ["1-3 short questions about THEIR specific '
            'implementation choices, referencing what they actually built"]}. '
            "If correctness or testing is a fail, understanding_questions may be empty."
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            dimensions = {
                str(name): {
                    "rating": str(info.get("rating", "concern")),
                    "notes": str(info.get("notes", "")),
                }
                for name, info in (payload.get("dimensions") or {}).items()
            }
            if dimensions:
                return {
                    "dimensions": dimensions,
                    "summary": str(payload.get("summary", "")),
                    "understanding_questions": [
                        str(q) for q in (payload.get("understanding_questions") or [])
                    ],
                }
        except Exception:
            pass
        return fallback_review(
            code_bundle=code_bundle,
            tests_passed=tests_passed,
            milestone_title=milestone_title,
        )

    def evaluate_understanding(
        self,
        *,
        question: str,
        answer: str,
        milestone_title: str,
    ) -> dict[str, object]:
        prompt = (
            "You evaluate whether a learner genuinely understands the "
            "implementation they built (not a scripted quiz answer). "
            "Return ONLY JSON: {\"passed\": true|false, \"feedback\": null|\"one "
            "short sentence\"}. Never explain the answer for them, never give code.\n"
            f"Milestone: {milestone_title}\n"
            f"Question: {question}\n"
            f"Learner's answer: {answer}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            passed = bool(payload.get("passed"))
            feedback = payload.get("feedback")
            return {
                "passed": passed,
                "feedback": (str(feedback).strip() or None) if feedback else None,
            }
        except Exception:
            return fallback_understanding(question, answer)
