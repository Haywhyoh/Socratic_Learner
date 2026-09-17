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
        current_question: str = "",
    ) -> dict[str, Any]: ...

    def evaluate_practice(
        self,
        *,
        concept_title: str,
        filename: str,
        prompt: str,
        rubric: str,
        source: str,
        run_result: dict[str, Any],
        expect_check: dict[str, Any],
        language: str = "",
    ) -> dict[str, Any]: ...

    def generate_knowledge_graph(
        self,
        *,
        topic: str,
        language: str,
        slug: str,
        audience: str = "",
        constraints: list[str] | None = None,
        capstone: str = "",
        difficulty: str = "beginner",
        course_name: str = "",
    ) -> dict[str, Any]: ...

    def generate_concept_content(
        self,
        *,
        concept: dict[str, Any],
        language: str,
        project_title: str,
    ) -> dict[str, Any]: ...


def stub_knowledge_graph(
    *,
    topic: str,
    language: str,
    slug: str,
    audience: str = "",
    constraints: list[str] | None = None,
    capstone: str = "",
    difficulty: str = "beginner",
    course_name: str = "",
) -> dict[str, Any]:
    """Tiny deterministic graph used in tests and when LLM_MODEL=stub."""
    from app.services.runtime import (
        language_display_name,
        language_extension,
        normalize_language,
        run_argv_for_file,
        runtime_for_language,
    )

    ns = re.sub(r"[^a-z0-9]+", "-", (slug or "track").strip().lower()).strip("-") or "track"
    language = normalize_language(language)
    ext = language_extension(language)
    name = course_name or topic or ns
    start_id = f"{ns}.start"
    core_id = f"{ns}.core"
    cap_id = f"{ns}.capstone"
    lang_name = language_display_name(language)

    def _concept(concept_id: str, title: str, category: str, description: str, filename: str) -> dict[str, Any]:
        path = f"practice/{filename}"
        return {
            "id": concept_id,
            "title": title,
            "category": category,
            "description": description,
            "learning_objectives": [
                f"Explain {title.lower()} in your own words",
                f"Write a small {language} file that uses {title.lower()}",
            ],
            "misconceptions": [
                {
                    "id": f"{concept_id}-mixup",
                    "description": f"The learner mixes up {title.lower()} with a nearby idea.",
                    "signals": ["confused", "mixed up"],
                    "diagnostic_questions": [f"What is {title.lower()} for?"],
                    "remediation": {
                        "type": "targeted_question",
                        "script": f"Separate {title.lower()} from lookalikes, then try a tiny example.",
                    },
                }
            ],
            "diagnostic_questions": [f"What does {title.lower()} let you do?"],
            "research_questions": [f"Where is {title.lower()} used in {language}?"],
            "resources": [],
            "hints": [
                f"What is the smallest example of {title.lower()}?",
                "Write the smallest file that proves the idea.",
                "Name the mechanism in one sentence.",
                f"Structure: a file named `practice/{filename}` with one clear example.",
                "Run it and point at the output that proves it.",
            ],
            "mastery_requirements": {"explanation": True, "implementation": True},
            "practice_tasks": [
                {
                    "id": filename.replace(f".{ext}", ""),
                    "filename": f"practice/{filename}",
                    "prompt": f"Write a tiny example of {title.lower()} for: {topic or name}.",
                    "run": run_argv_for_file(runtime_for_language(language), path),
                    "expect": {"exit_code": 0, "stdout_contains": []},
                    "rubric": "The file runs. Do not require extra features.",
                }
            ],
            "mentor_scripts": {},
        }

    return {
        "course": {
            "slug": ns,
            "name": name,
            "description": topic or f"Learn {name}.",
            "primary_label": "Language",
            "secondary_label": "Track",
            "primary_slug": language,
            "primary_name": lang_name,
            "secondary_slug": "fundamentals",
            "secondary_name": topic or "Fundamentals",
        },
        "project": {
            "title": f"Learn {name}",
            "description": topic or f"A short {language} track generated for testing.",
            "objective": f"Learn {name} through three concepts, then a tiny capstone.",
            "difficulty": difficulty or "beginner",
            "expected_outcome": capstone or f"A small {language} program you can defend.",
            "prerequisites": [audience] if audience else ["Comfort with a terminal"],
            "skills": ["Reading errors", "Running a file"],
            "constraints": list(constraints or []),
            "tests": ["Each practice file runs"],
            "evaluation_criteria": ["Explanation and implementation evidence on every concept"],
            "extension_challenges": [],
            "recommended_resources": [],
            "runtime": {"language": language},
        },
        "concepts": [
            _concept(start_id, "First programs", "foundation", f"Run a {language} file for {name}.", f"hello.{ext}"),
            _concept(core_id, "Core idea", "core", f"The central idea of {name}.", f"core.{ext}"),
            _concept(cap_id, "Capstone", "capstone", capstone or f"A tiny {name} program.", f"capstone.{ext}"),
        ],
        "dependencies": [
            {
                "concept_id": core_id,
                "requires_concept_id": start_id,
                "reason": "You need a running file before the core idea.",
            },
            {
                "concept_id": cap_id,
                "requires_concept_id": core_id,
                "reason": "The capstone applies the core idea.",
            },
        ],
        "milestones": [
            {
                "title": "Start",
                "description": "Get a file running.",
                "instructions": "Write and run the first practice file.",
                "success_criteria": "The hello file runs.",
                "concepts": [start_id],
                "questions": [],
            },
            {
                "title": "Core",
                "description": "Learn the central idea.",
                "instructions": "Explain the core idea, then implement the practice file.",
                "success_criteria": "Core practice file runs.",
                "concepts": [core_id],
                "questions": [],
            },
            {
                "title": "Capstone",
                "description": "Ship a tiny program.",
                "instructions": "Combine the earlier ideas into one small program.",
                "success_criteria": "The capstone file runs.",
                "concepts": [cap_id],
                "questions": [],
            },
        ],
    }


def stub_concept_content(
    concept: dict[str, Any],
    *,
    language: str,
    project_title: str,
) -> dict[str, Any]:
    title = str(concept.get("title") or concept.get("id") or "Concept")
    concept_id = str(concept.get("id") or "concept")
    from app.services.runtime import (
        language_extension,
        normalize_language,
        run_argv_for_file,
        runtime_for_language,
    )
    language = normalize_language(language)
    ext = language_extension(language)
    leaf = concept_id.rsplit(".", 1)[-1].replace("-", "_") or "practice"
    filename = f"practice/{leaf}.{ext}"
    return {
        **concept,
        "description": str(concept.get("description") or f"{title} for {project_title}."),
        "learning_objectives": list(concept.get("learning_objectives") or [f"Explain {title}", f"Use {title} in a small file"]),
        "diagnostic_questions": list(concept.get("diagnostic_questions") or [f"What is {title}?"]),
        "research_questions": list(concept.get("research_questions") or [f"Where is {title} used?"]),
        "hints": list(
            concept.get("hints")
            or [
                f"What is the smallest example of {title}?",
                "Write the smallest file that proves the idea.",
                "Name the mechanism in one sentence.",
                f"Structure: `practice/{leaf}.{ext}` with one clear example.",
                "Run it and point at the output that proves it.",
            ]
        ),
        "mastery_requirements": dict(concept.get("mastery_requirements") or {"explanation": True, "implementation": True}),
        "practice_tasks": list(
            concept.get("practice_tasks")
            or [
                {
                    "id": leaf,
                    "filename": filename,
                    "prompt": f"Write a tiny example of {title} for {project_title}.",
                    "run": run_argv_for_file(runtime_for_language(language), filename),
                    "expect": {"exit_code": 0, "stdout_contains": []},
                    "rubric": "The file runs.",
                }
            ]
        ),
    }


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
        current_question: str = "",
    ) -> dict[str, Any]:
        return fallback_explanation(answer)

    def evaluate_practice(
        self,
        *,
        concept_title: str,
        filename: str,
        prompt: str,
        rubric: str,
        source: str,
        run_result: dict[str, Any],
        expect_check: dict[str, Any],
        language: str = "",
    ) -> dict[str, Any]:
        ran = bool(source.strip())
        expect_ok = bool(expect_check.get("passed"))
        passed = ran and expect_ok
        if not source.strip():
            feedback = f"`{filename}` is empty. Write the snippet, then check again."
        elif not expect_ok:
            missing = expect_check.get("missing_stdout") or []
            feedback = (
                f"`{filename}` ran but did not match the expected output"
                + (f" (missing {missing})." if missing else ".")
            )
        else:
            feedback = f"`{filename}` ran and matches the practice check."
        return {"passed": passed, "feedback": feedback}

    def generate_knowledge_graph(
        self,
        *,
        topic: str,
        language: str,
        slug: str,
        audience: str = "",
        constraints: list[str] | None = None,
        capstone: str = "",
        difficulty: str = "beginner",
        course_name: str = "",
    ) -> dict[str, Any]:
        return stub_knowledge_graph(
            topic=topic,
            language=language,
            slug=slug,
            audience=audience,
            constraints=list(constraints or []),
            capstone=capstone,
            difficulty=difficulty,
            course_name=course_name,
        )

    def generate_concept_content(
        self,
        *,
        concept: dict[str, Any],
        language: str,
        project_title: str,
    ) -> dict[str, Any]:
        return stub_concept_content(concept, language=language, project_title=project_title)

    def bind_workspace_tools(self, tools: list[Any] | None) -> None:
        return None


class LLMConfigurationError(RuntimeError):
    """Raised when a real model is configured but cannot be initialized."""


def get_coach_llm() -> CoachLLM:
    model_name = (settings.llm_model or "stub").strip()
    if model_name.lower() in {"stub", "none", "fake"}:
        return StubCoachLLM()
    api_key = settings.resolved_llm_api_key().strip()
    if not api_key:
        raise LLMConfigurationError(
            f"LLM_MODEL={model_name} requires ANTHROPIC_API_KEY or LLM_API_KEY"
        )
    try:
        from langchain.chat_models import init_chat_model

        if model_name.lower().startswith("anthropic:") or "claude" in model_name.lower():
            os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
        else:
            os.environ.setdefault("OPENAI_API_KEY", api_key)

        model = init_chat_model(model_name, api_key=api_key)
        return LangChainCoachLLM(model)
    except LLMConfigurationError:
        raise
    except Exception as exc:
        raise LLMConfigurationError(f"Failed to initialize LLM {model_name}: {exc}") from exc


class LangChainCoachLLM:
    def __init__(self, model: object, tools: list[Any] | None = None) -> None:
        self._model = model
        self._tools = list(tools or [])

    def bind_workspace_tools(self, tools: list[Any] | None) -> None:
        self._tools = list(tools or [])

    def _normalize_content(self, content: object) -> str:
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

    def _invoke(self, prompt: str) -> str:
        result = getattr(self._model, "invoke")(prompt)
        return self._normalize_content(getattr(result, "content", result))

    def _invoke_with_tools(self, system: str, user: str, *, max_rounds: int = 4) -> str:
        if not self._tools:
            return self._invoke(f"{system}\n\n{user}")
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

        model = self._model.bind_tools(self._tools)  # type: ignore[attr-defined]
        messages: list[Any] = [SystemMessage(content=system), HumanMessage(content=user)]
        tool_map = {str(getattr(tool, "name", "")): tool for tool in self._tools}
        last = ""
        for _ in range(max_rounds):
            result = model.invoke(messages)
            last = self._normalize_content(getattr(result, "content", result))
            calls = getattr(result, "tool_calls", None) or []
            if not calls:
                return last
            messages.append(result)
            for call in calls:
                if isinstance(call, dict):
                    name = str(call.get("name") or "")
                    args = call.get("args") or {}
                    call_id = str(call.get("id") or "")
                else:
                    name = str(getattr(call, "name", "") or "")
                    args = getattr(call, "args", {}) or {}
                    call_id = str(getattr(call, "id", "") or "")
                tool = tool_map.get(name)
                try:
                    output = tool.invoke(args) if tool is not None else f"unknown tool {name}"
                except Exception as exc:
                    output = f"ERROR: {exc}"
                messages.append(ToolMessage(content=str(output), tool_call_id=call_id))
        return last

    def generate_card(
        self,
        concept: str,
        milestone_title: str,
        resources: list[dict[str, str]],
    ) -> CardDraft:
        prompt = (
            "Write a short concept card for a mentored learner. Return ONLY JSON with keys "
            "name, why_it_matters, research_questions (array of strings), resources "
            "(array of {title,url}), checkpoint, explanation. No code dumps, no full solutions.\n"
            f"Concept: {concept}\n"
            f"Milestone: {milestone_title}\n"
            f"Resources: {json.dumps(resources)}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            return {
                "name": str(payload.get("name") or concept),
                "why_it_matters": str(payload.get("why_it_matters") or ""),
                "research_questions": [str(q) for q in (payload.get("research_questions") or [])],
                "resources": list(payload.get("resources") or resources),
                "checkpoint": str(payload.get("checkpoint") or ""),
                "explanation": str(payload.get("explanation") or ""),
            }
        except Exception:
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
        prompt = (
            "Give one Socratic hint. Never paste a full solution or complete file. "
            "Hint levels: 0=question, 1=direction, 2=concept, 3=structure, 4=targeted. "
            f"Use level {level} only.\n"
            f"Milestone: {milestone_title}\n"
            f"Concepts: {', '.join(concepts) or 'n/a'}\n"
            f"Extra instructions: {instructions or 'n/a'}\n"
        )
        try:
            raw = self._invoke(prompt).strip()
            if raw:
                return raw
        except Exception:
            pass
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
        prompt = _dynamic_mentor_prompt(context, message, action_hint)
        try:
            raw = self._invoke_with_tools(
                prompt,
                "Return ONLY the JSON object. You may call workspace tools first if you need to read or run the learner's file.",
            )
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
            assigned = str(payload.get("assigned_file") or "").strip() or None
            task_id = str(payload.get("practice_task_id") or "").strip() or None
            if not assigned:
                task = _practice_task_from_context(context)
                if task:
                    assigned = str(task.get("filename") or "") or None
                    task_id = str(task.get("id") or "") or task_id
            return {
                "intent": str(payload.get("intent") or "MENTOR"),
                "action": str(payload.get("action") or action_hint),
                "message": str(payload.get("message") or ""),
                "diagnostic_concept": payload.get("diagnostic_concept"),
                "identified_gap": gap,
                "hint_level": hint_level,
                "should_unlock": bool(payload.get("should_unlock")),
                "next_state": str(payload.get("next_state") or ""),
                "assigned_file": assigned,
                "practice_task_id": task_id,
            }
        except Exception:
            return fallback_mentor_contract(context, message, action_hint)
        except Exception:
            return fallback_mentor_contract(context, message, action_hint)

    def evaluate_explanation(
        self,
        *,
        concept_title: str,
        concept_description: str,
        objectives: list[str],
        answer: str,
        current_question: str = "",
    ) -> dict[str, Any]:
        prompt = (
            "Evaluate a learner's explanation. Grade accuracy, completeness, clarity, "
            "and causal understanding — not keyword matching. Return ONLY JSON: "
            '{"passed": true|false, "accuracy": 0-1, "completeness": 0-1, '
            '"clarity": 0-1, "causal": 0-1, "feedback": "one short sentence"}. '
            "If the learner asked YOU a question, you are in the wrong mode — do not grade "
            "them for failing to explain. Never say 'no explanation was provided'. "
            "Grade whether they answered the current question, not every objective on the "
            "concept. Stay inside this concept — do not fail them for omitting a later idea. "
            "If they only traced execution after being asked to trace, that can "
            "be a pass for that diagnostic. If any part of the causal model they offered "
            "is wrong, passed=false. Do not praise the wrong part.\n"
            f"Concept: {concept_title}\n{concept_description}\n"
            f"Objectives: {'; '.join(objectives)}\n"
            f"Current question they were answering: {current_question or 'none'}\n"
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

    def evaluate_practice(
        self,
        *,
        concept_title: str,
        filename: str,
        prompt: str,
        rubric: str,
        source: str,
        run_result: dict[str, Any],
        expect_check: dict[str, Any],
        language: str = "",
    ) -> dict[str, Any]:
        system = (
            "You evaluate a learner's practice snippet. They were told to write a named file. "
            "Use the run result and rubric. Never paste a corrected full solution. "
            "Return ONLY JSON: {\"passed\": true|false, \"feedback\": \"2-4 short sentences\"}. "
            "If expect_check.passed is false, passed must be false unless the rubric is clearly "
            "satisfied and the expect check is overly strict. If the file is empty, fail."
        )
        user = (
            f"Language: {language or 'n/a'}\n"
            f"Concept: {concept_title}\n"
            f"File: {filename}\n"
            f"Task: {prompt}\n"
            f"Rubric: {rubric or 'Matches the task prompt.'}\n"
            f"Expect check: {json.dumps(expect_check, default=str)}\n"
            f"Run result: {json.dumps(run_result, default=str)}\n"
            f"Source:\n{source or '(empty)'}\n"
        )
        try:
            raw = self._invoke_with_tools(system, user)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            return {
                "passed": bool(payload.get("passed")),
                "feedback": str(payload.get("feedback") or "").strip()
                or "Check the file against the task and run it again.",
            }
        except Exception:
            ran = bool(source.strip())
            expect_ok = bool(expect_check.get("passed"))
            return {
                "passed": ran and expect_ok,
                "feedback": (
                    f"`{filename}` ran and matches the practice check."
                    if ran and expect_ok
                    else f"`{filename}` does not yet satisfy the practice check."
                ),
            }

    def generate_knowledge_graph(
        self,
        *,
        topic: str,
        language: str,
        slug: str,
        audience: str = "",
        constraints: list[str] | None = None,
        capstone: str = "",
        difficulty: str = "beginner",
        course_name: str = "",
    ) -> dict[str, Any]:
        prompt = (
            "You author deterministic curriculum knowledge graphs for Socratic Learner. "
            "The AI mentor never invents this graph; it only teaches inside it. "
            "Return ONLY JSON with keys: course, project, concepts, dependencies, milestones.\n"
            "course: {slug, name, description, primary_slug, primary_name, secondary_slug, secondary_name}.\n"
            "project: {title, description, objective, difficulty, expected_outcome, prerequisites, "
            "skills, constraints, tests, evaluation_criteria, extension_challenges, "
            "recommended_resources (array of {title,url})}.\n"
            "concepts: 6-10 objects with id, title, category, description, learning_objectives "
            "(2+ strings), misconceptions (objects with id, description, signals, "
            "diagnostic_questions, remediation.script), diagnostic_questions, research_questions, "
            "resources ({title,url}), hints (exactly 5 strings: question, direction, concept, "
            "structure, targeted), mastery_requirements (object of booleans), practice_tasks "
            "(objects with id, filename, prompt, run, expect, rubric). Never include full solutions.\n"
            "dependencies: array of {concept_id, requires_concept_id, reason}. No cycles. "
            "Every edge must reference concept ids in this graph.\n"
            "milestones: 4-8 objects with title, description, instructions (no code dumps), "
            "success_criteria, concepts (array of concept ids). Cover every concept at least once.\n"
            f"Namespace every concept id with `{slug}.` "
            "Quality bar: the Python fundamentals graph (scripts → types → functions → capstone CLI).\n"
            f"Topic: {topic}\n"
            f"Course name: {course_name or topic}\n"
            f"Language/runtime: {language}\n"
            f"Slug: {slug}\n"
            f"Audience: {audience or 'beginner'}\n"
            f"Difficulty: {difficulty}\n"
            f"Constraints: {json.dumps(list(constraints or []))}\n"
            f"Capstone idea: {capstone or 'a small stdlib/cli or node core program'}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            if isinstance(payload, dict) and payload.get("concepts"):
                return payload
        except Exception:
            pass
        return stub_knowledge_graph(
            topic=topic,
            language=language,
            slug=slug,
            audience=audience,
            constraints=list(constraints or []),
            capstone=capstone,
            difficulty=difficulty,
            course_name=course_name,
        )

    def generate_concept_content(
        self,
        *,
        concept: dict[str, Any],
        language: str,
        project_title: str,
    ) -> dict[str, Any]:
        prompt = (
            "Rewrite teaching content for one knowledge-graph concept. Return ONLY JSON with "
            "keys: description, learning_objectives, misconceptions, diagnostic_questions, "
            "research_questions, resources, hints (exactly 5), mastery_requirements, practice_tasks. "
            "Keep the same id and title. No full solutions.\n"
            f"Language: {language}\nProject: {project_title}\n"
            f"Concept JSON: {json.dumps(concept, default=str)}\n"
        )
        try:
            raw = self._invoke(prompt)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            payload = json.loads(match.group(0) if match else raw)
            if isinstance(payload, dict):
                return {**concept, **payload, "id": concept.get("id"), "title": concept.get("title")}
        except Exception:
            pass
        return stub_concept_content(concept, language=language, project_title=project_title)


def _practice_task_from_context(context: dict[str, Any]) -> dict[str, Any] | None:
    tasks = list(context.get("practice_tasks") or [])
    if not tasks:
        return None
    current_id = str(context.get("practice_task_id") or "")
    for item in tasks:
        if isinstance(item, dict) and (not current_id or str(item.get("id") or "") == current_id):
            return item
    first = tasks[0]
    return first if isinstance(first, dict) else None


def _dynamic_mentor_prompt(context: dict[str, Any], message: str, action_hint: str) -> str:
    runtime = dict(context.get("runtime") or {})
    language = str(runtime.get("language") or context.get("language") or "the project language")
    title = str(context.get("project_title") or context.get("project") or "this project")
    ledger = ""
    if context.get("evidence_ledger_active"):
        ledger = (
            "## EVIDENCE LEDGER (this concept only)\n"
            "Your job is evidence collection, not conversation length. Before asking, check "
            "do_not_ask_purposes, subskills_verified, missing_required_evidence, and "
            "learning_control. If a question produces no new evidence, do not ask it.\n"
            "Never set action REVIEW unless evidence_ledger_active is true AND "
            "missing_required_evidence is []. You do not choose the next concept.\n"
        )
    language_notes = ""
    if language.lower() in {"javascript", "js"}:
        language_notes = (
            "JavaScript objects: do NOT teach 'passed by reference' as the complete model. "
            "JS passes arguments by value. When the value is an object reference, the "
            "parameter gets a copy of that reference, so both variables can mutate the "
            "same object. Do not require memory addresses unless that is the concept.\n"
        )
    task = _practice_task_from_context(context)
    task_block = ""
    if task:
        task_block = (
            "When action is ASK_IMPLEMENTATION, name the exact filename and the task prompt. "
            f"Preferred file: `{task.get('filename')}`. Task: {task.get('prompt')}. "
            "Set assigned_file and practice_task_id in the JSON. Do not write the solution.\n"
        )
    return (
        f"You are a senior engineer mentoring a learner working on: {title} ({language}). "
        "Never write the learner's implementation or skip ahead to later concepts. "
        "Return ONLY JSON with keys: intent, action, message, diagnostic_concept, "
        "identified_gap, hint_level, should_unlock, next_state, assigned_file, practice_task_id.\n"
        "intent is MENTOR or DIAGNOSE. action is ASK_QUESTION, ASK_RESEARCH, HINT, "
        "REVIEW, ASK_DIAGNOSTIC_QUESTION, ASK_IMPLEMENTATION, ASK_REFLECTION, "
        "ASK_DEFENSE, PRACTICE_EVAL, or HOLD.\n"
        "message is what the learner sees. You may include a tiny fenced snippet "
        "(a few lines) to illustrate a concept. Never paste a complete file or the code "
        "they are supposed to write.\n"
        f"{ledger}"
        "One correct answer is not mastery. If the learner is wrong, name the known "
        "misconception when context.identified_misconception is set and remediate with "
        "one distinction, one tiny example, and one check question.\n"
        "Never praise an incorrect causal model. Never say Good / Great / Exactly unless "
        "the causal claim is actually correct.\n"
        "If they ask you to explain, explain the current mechanism in the smallest form, "
        "then ask one check question. If they ask what is next, tell them the next "
        "missing evidence or the graph's next concept.\n"
        f"{language_notes}"
        f"{task_block}"
        "You may call list_workspace_files, read_workspace_file, or run_workspace_command "
        "if you need to see or run their code before writing the JSON.\n"
        f"Forced action family: {action_hint}\n"
        f"Context JSON: {json.dumps(context, default=str)}\n"
        f"Learner message: {message}\n"
    )

