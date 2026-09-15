from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from app.agents.build_coach import (
    build_steps_for_milestone,
    enforce_single_build_step,
    format_resource_bullet,
    format_step_header,
    resource_hint,
)
from app.agents.policies import (
    REVIEW_DIMENSIONS,
    fallback_card,
    fallback_curriculum,
    fallback_evaluate,
    fallback_explanation,
    fallback_hint,
    fallback_mentor_contract,
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

    def mentor_contract(
        self,
        *,
        context: dict[str, Any],
        message: str,
        action_hint: str,
    ) -> dict[str, Any]: ...

    def evaluate_explanation(
        self,
        *,
        concept_title: str,
        concept_description: str,
        objectives: list[str],
        answer: str,
    ) -> dict[str, Any]: ...


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
        body = guidance_reply(
            message=f"{message}\n(Focus only on: {current})",
            milestone_title=milestone_title,
            instructions=f"1. {current}",
            constraints=constraints,
            success_criteria=success_criteria,
            project_title=project_title,
        )
        return f"{header}\n{body}\n\nWhen that works, reply **done** for the next step only."

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

    def mentor_contract(
        self,
        *,
        context: dict[str, Any],
        message: str,
        action_hint: str,
    ) -> dict[str, Any]:
        return fallback_mentor_contract(context, message, action_hint)

    def evaluate_explanation(
        self,
        *,
        concept_title: str,
        concept_description: str,
        objectives: list[str],
        answer: str,
    ) -> dict[str, Any]:
        return fallback_explanation(answer)


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
            if title or url:
                resource_lines.append(format_resource_bullet(title, url))
        resource_block = "\n".join(resource_lines) or format_resource_bullet(
            "FastAPI docs", "https://fastapi.tiangolo.com/"
        )
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
            "- Use simple Markdown: short paragraphs, bullet lists, `inline code` for paths/commands, "
            "fenced blocks only for tiny snippets (under 12 lines). No duplicate 'Step N' headings.\n"
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

    def mentor_contract(
        self,
        *,
        context: dict[str, Any],
        message: str,
        action_hint: str,
    ) -> dict[str, Any]:
        prompt = (
            "You are a senior engineer mentoring a learner who is building a backend "
            "framework from scratch. Never write the learner's implementation or skip "
            "ahead to later concepts. Return ONLY JSON with keys: intent, action, message, "
            "diagnostic_concept, identified_gap, hint_level, should_unlock, next_state.\n"
            "intent is MENTOR or DIAGNOSE. action is ASK_QUESTION, ASK_RESEARCH, HINT, "
            "REVIEW, ASK_DIAGNOSTIC_QUESTION, ASK_IMPLEMENTATION, ASK_REFLECTION, "
            "ASK_DEFENSE, or HOLD.\n"
            "message is what the learner sees. You may include a tiny fenced snippet "
            "(a few lines) to illustrate a concept. Never paste a full server, a complete "
            "file, or the code they are supposed to write.\n"
            "## IMPORTANT: DETECT AND NAME SPECIFIC MISCONCEPTIONS\n"
            "Do not continue asking variations of the same question when the learner "
            "repeatedly demonstrates the same misunderstanding. After 1–2 failed attempts, "
            "identify the specific misconception, name the distinction, use the smallest "
            "example, and ask the learner to identify the two separate actions. Then require "
            "a trace or a new example. Only return to the curriculum after they demonstrate "
            "understanding. Do not over-explain. Do not simply reveal the answer. Do not "
            "endlessly repeat the same question.\n"
            "Never praise an incorrect causal model. Never say Good / Great / Exactly / "
            "Good observation unless the causal claim is actually correct. If part of the "
            "answer is right and part is wrong, name both separately in one short reply and "
            "do not move on. If context.identified_misconception is set, follow it: name "
            "that distinction and run a targeted diagnostic — do not ask a semantically "
            "identical Socratic question.\n"
            f"Forced action family: {action_hint}\n"
            f"Context JSON: {json.dumps(context, default=str)}\n"
            f"Learner message: {message}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            gap = payload.get("identified_gap")
            if isinstance(gap, str):
                gap = {"concept": gap.strip(), "confidence": 0.0} if gap.strip() else None
            elif not isinstance(gap, dict):
                gap = None
            try:
                hint_level = int(payload.get("hint_level") or 0)
            except (TypeError, ValueError):
                hint_level = 0
            return {
                "intent": str(payload.get("intent") or "MENTOR"),
                "action": str(payload.get("action") or action_hint),
                "message": str(payload.get("message") or ""),
                "diagnostic_concept": payload.get("diagnostic_concept"),
                "identified_gap": gap,
                "hint_level": hint_level,
                "should_unlock": bool(payload.get("should_unlock")),
                "next_state": str(payload.get("next_state") or ""),
            }
        except Exception:
            return fallback_mentor_contract(context, message, action_hint)

    def evaluate_explanation(
        self,
        *,
        concept_title: str,
        concept_description: str,
        objectives: list[str],
        answer: str,
    ) -> dict[str, Any]:
        prompt = (
            "Evaluate a learner's explanation. Grade accuracy, completeness, clarity, "
            "and causal understanding — not keyword matching. Return ONLY JSON: "
            '{"passed": true|false, "accuracy": 0-1, "completeness": 0-1, '
            '"clarity": 0-1, "causal": 0-1, "feedback": "one short sentence"}. '
            "If any part of the causal model is wrong, passed=false. Do not praise the "
            "wrong part. If they mix a correct observation with an incorrect cause, say "
            "which part is right and which is wrong. Never give the full answer, never "
            "give a complete file.\n"
            f"Concept: {concept_title}\n{concept_description}\n"
            f"Objectives: {'; '.join(objectives)}\n"
            f"Answer: {answer}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            return {
                "passed": bool(payload.get("passed")),
                "accuracy": payload.get("accuracy"),
                "completeness": payload.get("completeness"),
                "clarity": payload.get("clarity"),
                "causal": payload.get("causal"),
                "feedback": payload.get("feedback"),
            }
        except Exception:
            return fallback_explanation(answer)
