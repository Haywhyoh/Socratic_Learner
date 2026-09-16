"""Language-agnostic project runtime defaults (sandbox image, run, tests)."""

from __future__ import annotations

from typing import Any

from app.models.project import Project

JS_RUNTIME: dict[str, Any] = {
    "language": "javascript",
    "sandbox_image": "socratic-sandbox-node:latest",
    "run": ["node", "{file}"],
    "test_command": ["node", "--test"],
    "entry_globs": ["*.js", "*.mjs"],
}

PYTHON_RUNTIME: dict[str, Any] = {
    "language": "python",
    "sandbox_image": "socratic-sandbox-python:latest",
    "run": ["python", "{file}"],
    "test_command": ["pytest", "-q"],
    "entry_globs": ["*.py"],
}


def project_runtime(project: Project | None) -> dict[str, Any]:
    raw = dict(getattr(project, "runtime", None) or {})
    language = str(raw.get("language") or "").strip().lower()
    if language in {"python", "py"}:
        base = dict(PYTHON_RUNTIME)
    else:
        base = dict(JS_RUNTIME)
    for key, value in raw.items():
        if value not in (None, "", [], {}):
            base[key] = value
    return base


def runtime_language(project: Project | None) -> str:
    return str(project_runtime(project).get("language") or "javascript")


def run_argv_for_file(runtime: dict[str, Any], filename: str) -> list[str]:
    template = list(runtime.get("run") or ["node", "{file}"])
    return [str(part).replace("{file}", filename) for part in template]


def test_command(runtime: dict[str, Any]) -> list[str]:
    command = list(runtime.get("test_command") or [])
    return [str(part) for part in command] if command else ["node", "--test"]


def sandbox_image(runtime: dict[str, Any]) -> str:
    return str(runtime.get("sandbox_image") or JS_RUNTIME["sandbox_image"])


def entry_globs(runtime: dict[str, Any]) -> list[str]:
    globs = list(runtime.get("entry_globs") or [])
    return [str(item) for item in globs] if globs else list(JS_RUNTIME["entry_globs"])
