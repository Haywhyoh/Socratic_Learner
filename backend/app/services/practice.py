"""Practice-file assignment, deterministic expect checks, and evaluation helpers."""

from __future__ import annotations

import re
from typing import Any

from app.models.curriculum import Concept
from app.models.learning_state import ConceptState
from app.models.project import Project
from app.services.runtime import (
    language_extension,
    project_runtime,
    run_argv_for_file,
    runtime_for_language,
)

_LEAF_RE = re.compile(r"[^a-z0-9]+")


def practice_task_leaf(value: str) -> str:
    leaf = _LEAF_RE.sub("-", str(value or "").strip().lower()).strip("-")
    return leaf or "practice"


def _task_prompt(item: dict[str, Any]) -> str:
    prompt = str(item.get("prompt") or "").strip()
    if prompt:
        return prompt
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    if title and description and title not in description:
        return f"{title}\n\n{description}"
    return description or title


def _task_rubric(item: dict[str, Any]) -> str:
    rubric = str(item.get("rubric") or "").strip()
    if rubric:
        return rubric
    criteria = item.get("acceptance_criteria")
    if isinstance(criteria, list):
        return "\n".join(str(part).strip() for part in criteria if str(part).strip())
    return str(criteria or "").strip()


def _task_filename(item: dict[str, Any], leaf: str, language: str | None) -> str:
    ext = language_extension(language) if language else "txt"
    raw = str(item.get("filename") or "").strip().lstrip("/")
    if not raw:
        return f"practice/{leaf}.{ext}"
    stem = raw.rsplit("/", 1)[-1]
    if "." not in stem:
        raw = f"{raw}.{ext}"
    if "/" not in raw:
        raw = f"practice/{raw}"
    return raw


def _task_run(item: dict[str, Any], filename: str, language: str | None) -> list[str]:
    raw = item.get("run") or []
    if isinstance(raw, str):
        parts = [part for part in raw.split() if part]
    else:
        parts = [str(part) for part in raw if str(part)]
    if parts:
        return parts
    return run_argv_for_file(runtime_for_language(language), filename)


def normalize_practice_task(item: dict[str, Any], language: str | None = None) -> dict[str, Any]:
    """Map LLM title/description tasks onto the filename/prompt contract."""
    leaf = practice_task_leaf(str(item.get("id") or item.get("title") or item.get("filename") or "practice"))
    filename = _task_filename(item, leaf, language)
    task_id = str(item.get("id") or leaf).strip() or leaf
    raw_expect = item.get("expect") or {}
    expect = dict(raw_expect) if isinstance(raw_expect, dict) else {}
    if "exit_code" not in expect:
        expect["exit_code"] = 0
    if "stdout_contains" not in expect:
        expect["stdout_contains"] = list(expect.get("stdout_contains") or [])
    task: dict[str, Any] = {
        "id": task_id,
        "filename": filename,
        "prompt": _task_prompt(item),
        "run": _task_run(item, filename, language),
        "expect": expect,
        "rubric": _task_rubric(item),
    }
    title = str(item.get("title") or "").strip()
    if title:
        task["title"] = title
    return task


def normalize_practice_tasks(items: list[Any], language: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.append(normalize_practice_task(item, language))
    return out


def practice_tasks_for(concept: Concept | None, *, language: str | None = None) -> list[dict[str, Any]]:
    if concept is None:
        return []
    raw = normalize_practice_tasks(list(getattr(concept, "practice_tasks", None) or []), language)
    out: list[dict[str, Any]] = []
    for item in raw:
        filename = str(item.get("filename") or "").strip().lstrip("/")
        if not filename:
            continue
        out.append(
            {
                "id": str(item.get("id") or filename),
                "filename": filename,
                "prompt": str(item.get("prompt") or "").strip(),
                "run": list(item.get("run") or []),
                "expect": dict(item.get("expect") or {}),
                "rubric": str(item.get("rubric") or "").strip(),
            }
        )
    return out


def _completed_task_ids(state_row: ConceptState | None) -> set[str]:
    evidence = dict((state_row.evidence if state_row else None) or {})
    raw = evidence.get("practice_task_ids") or []
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return set()


def next_practice_task(
    concept: Concept | None,
    state_row: ConceptState | None = None,
    *,
    task_id: str | None = None,
    filename: str | None = None,
    language: str | None = None,
) -> dict[str, Any] | None:
    tasks = practice_tasks_for(concept, language=language)
    if not tasks:
        return None
    if task_id:
        for task in tasks:
            if task["id"] == task_id:
                return task
    if filename:
        cleaned = filename.strip().lstrip("/")
        for task in tasks:
            if task["filename"] == cleaned:
                return task
    done = _completed_task_ids(state_row)
    for task in tasks:
        if task["id"] not in done:
            return task
    return None


def run_argv_for_task(task: dict[str, Any], project: Project | None) -> list[str]:
    explicit = [str(part) for part in (task.get("run") or []) if str(part)]
    if explicit:
        return explicit
    runtime = project_runtime(project)
    return run_argv_for_file(runtime, str(task["filename"]))


def check_expect(expect: dict[str, Any], *, exit_code: int, stdout: str, stderr: str) -> dict[str, Any]:
    combined = f"{stdout}\n{stderr}"
    wanted_exit = expect.get("exit_code")
    exit_ok = True if wanted_exit is None else int(wanted_exit) == int(exit_code)
    missing: list[str] = []
    for needle in list(expect.get("stdout_contains") or []):
        text = str(needle)
        if text and text not in combined:
            missing.append(text)
    passed = exit_ok and not missing
    return {
        "passed": passed,
        "exit_ok": exit_ok,
        "missing_stdout": missing,
        "exit_code": exit_code,
    }


def assignment_message(task: dict[str, Any], concept_title: str) -> str:
    filename = task["filename"]
    prompt = task.get("prompt") or f"Write the smallest version of {concept_title} you can."
    return (
        f"Write this in `{filename}`:\n\n{prompt}\n\n"
        "I will not edit your files. When it runs, click **Check my work** "
        "or tell me you're done."
    )
