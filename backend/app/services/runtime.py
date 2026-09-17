"""Language runtimes for catalog graphs and sandboxes.

Python and JavaScript were the first seeded tracks, not a product limit.
Admin-authored graphs can target any language listed here; unknown names
are preserved instead of being rewritten to JavaScript.
"""

from __future__ import annotations

from typing import Any

from app.models.project import Project

LANGUAGE_ALIASES = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "c#": "csharp",
    "cs": "csharp",
    "c-sharp": "csharp",
    "c_sharp": "csharp",
}

LANGUAGE_RUNTIMES: dict[str, dict[str, Any]] = {
    "python": {
        "language": "python",
        "display_name": "Python",
        "sandbox_image": "socratic-sandbox-python:latest",
        "run": ["python", "{file}"],
        "test_command": ["pytest", "-q"],
        "entry_globs": ["*.py"],
        "extension": "py",
    },
    "javascript": {
        "language": "javascript",
        "display_name": "JavaScript",
        "sandbox_image": "socratic-sandbox-node:latest",
        "run": ["node", "{file}"],
        "test_command": ["node", "--test"],
        "entry_globs": ["*.js", "*.mjs"],
        "extension": "js",
    },
    "typescript": {
        "language": "typescript",
        "display_name": "TypeScript",
        "sandbox_image": "socratic-sandbox-node:latest",
        "run": ["npx", "tsx", "{file}"],
        "test_command": ["node", "--test"],
        "entry_globs": ["*.ts", "*.tsx"],
        "extension": "ts",
    },
    "go": {
        "language": "go",
        "display_name": "Go",
        "sandbox_image": "socratic-sandbox-go:latest",
        "run": ["go", "run", "{file}"],
        "test_command": ["go", "test", "./..."],
        "entry_globs": ["*.go"],
        "extension": "go",
    },
    "csharp": {
        "language": "csharp",
        "display_name": "C#",
        "sandbox_image": "socratic-sandbox-csharp:latest",
        "run": ["dotnet", "run", "{file}"],
        "test_command": ["dotnet", "test"],
        "entry_globs": ["*.cs"],
        "extension": "cs",
    },
    "c": {
        "language": "c",
        "display_name": "C",
        "sandbox_image": "socratic-sandbox-c:latest",
        "run": ["bash", "-lc", "cc {file} -o /tmp/socratic-a.out && /tmp/socratic-a.out"],
        "test_command": ["bash", "-lc", "cc *.c -o /tmp/socratic-a.out && /tmp/socratic-a.out"],
        "entry_globs": ["*.c", "*.h"],
        "extension": "c",
    },
}

PYTHON_RUNTIME: dict[str, Any] = {
    key: value for key, value in LANGUAGE_RUNTIMES["python"].items() if key != "display_name"
}
JS_RUNTIME: dict[str, Any] = {
    key: value for key, value in LANGUAGE_RUNTIMES["javascript"].items() if key != "display_name"
}


def normalize_language(language: str | None) -> str:
    raw = str(language or "").strip().lower()
    raw = LANGUAGE_ALIASES.get(raw, raw)
    return raw or "python"


def supported_languages() -> list[dict[str, str]]:
    return [
        {
            "slug": spec["language"],
            "name": str(spec["display_name"]),
            "extension": str(spec["extension"]),
        }
        for spec in LANGUAGE_RUNTIMES.values()
    ]


def language_display_name(language: str | None) -> str:
    key = normalize_language(language)
    spec = LANGUAGE_RUNTIMES.get(key)
    if spec:
        return str(spec["display_name"])
    return key.replace("_", " ").title() or "Python"


def language_extension(language: str | None) -> str:
    key = normalize_language(language)
    spec = LANGUAGE_RUNTIMES.get(key)
    if spec:
        return str(spec["extension"])
    return "txt"


def run_prefix(language: str | None) -> list[str]:
    runtime = runtime_for_language(language)
    template = list(runtime.get("run") or [])
    if template and template[-1] == "{file}":
        return template[:-1]
    if any("{file}" in str(part) for part in template):
        return template
    return template or ["python"]


def runtime_for_language(language: str | None) -> dict[str, Any]:
    key = normalize_language(language)
    spec = LANGUAGE_RUNTIMES.get(key)
    if spec is None:
        return {
            "language": key,
            "sandbox_image": f"socratic-sandbox-{key}:latest",
            "run": ["cat", "{file}"],
            "test_command": [],
            "entry_globs": ["*"],
            "extension": "txt",
        }
    return {k: v for k, v in spec.items() if k != "display_name"}


def project_runtime(project: Project | None) -> dict[str, Any]:
    raw = dict(getattr(project, "runtime", None) or {})
    language = normalize_language(str(raw.get("language") or ""))
    base = runtime_for_language(language)
    for key, value in raw.items():
        if value not in (None, "", [], {}):
            base[key] = value
    base["language"] = language
    return base


def runtime_language(project: Project | None) -> str:
    return str(project_runtime(project).get("language") or "python")


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
