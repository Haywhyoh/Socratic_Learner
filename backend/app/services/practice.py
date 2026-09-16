"""Practice-file assignment, deterministic expect checks, and evaluation helpers."""

from __future__ import annotations

from typing import Any

from app.models.curriculum import Concept
from app.models.learning_state import ConceptState
from app.models.project import Project
from app.services.runtime import project_runtime, run_argv_for_file


def practice_tasks_for(concept: Concept | None) -> list[dict[str, Any]]:
    if concept is None:
        return []
    raw = list(getattr(concept, "practice_tasks", None) or [])
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "").strip().lstrip("/")
        if not filename:
            continue
        task_id = str(item.get("id") or filename)
        out.append(
            {
                "id": task_id,
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
) -> dict[str, Any] | None:
    tasks = practice_tasks_for(concept)
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
