"""Paced build coaching: one milestone task at a time."""

from __future__ import annotations

import re

from app.agents.policies import parse_instruction_tasks

_ADVANCE_MARKERS = (
    "done",
    "finished",
    "completed",
    "next step",
    "what's next",
    "whats next",
    "ready for next",
    "i did that",
    "i did it",
    "i created",
    "i ran",
    "it worked",
    "worked",
    "success",
    "ok next",
    "move on",
    "continue",
)

_STUCK_MARKERS = (
    "stuck",
    "error",
    "failed",
    "doesn't work",
    "does not work",
    "help",
    "how do i",
    "how to",
    "what command",
    "not sure",
    "confused",
)


def build_steps_for_milestone(instructions: str) -> list[str]:
    steps = parse_instruction_tasks(instructions)
    if steps:
        return steps
    return [
        "Create the project package folders and empty modules in the terminal",
        "Add a minimal /health endpoint and prove the app imports",
        "Document how to run the app (README / dependency file)",
    ]


def detect_build_step_advance(message: str) -> bool:
    lower = message.lower().strip()
    if any(m in lower for m in _ADVANCE_MARKERS):
        return True
    # Short confirmations after prior guidance
    if lower in {"next", "ok", "okay", "yes", "yep", "done.", "done!"}:
        return True
    return False


def detect_build_step_stuck(message: str) -> bool:
    lower = message.lower()
    return any(m in lower for m in _STUCK_MARKERS)


def enforce_single_build_step(text: str) -> str:
    """Keep only the first instructional step if the model dumped several."""
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    cut_points: list[int] = []
    for pattern in (
        r"\n#{1,3}\s*Step\s*2\b",
        r"\n\*\*Step\s*2\b",
        r"\nStep\s*2\s*[:.)]",
        r"\n#{1,3}\s*2[\.)]\s",
        r"\n##\s*Step\s*3\b",
        r"\n\*\*What's next\?\*\*",
        r"\nWhat's next\?",
        r"\n---\n",
    ):
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            cut_points.append(match.start())
    if cut_points:
        cleaned = cleaned[: min(cut_points)].rstrip()
        if "when that works" not in cleaned.lower() and "reply" not in cleaned.lower():
            cleaned += (
                "\n\nWhen that works, reply with **done** (or paste the terminal output) "
                "and I'll give the next step only."
            )
    return cleaned


def format_step_header(*, step_index: int, total: int, task: str) -> str:
    return f"Step {step_index + 1} of {total}: {task}"


def resource_hint(resources: list[dict[str, str]], *, topic: str) -> str:
    """Point learners at project resources instead of dumping file contents."""
    links = []
    for item in resources[:3]:
        title = str(item.get("title") or "Resource").strip()
        url = str(item.get("url") or "").strip()
        if url:
            links.append(f"- {title}: {url}")
        elif title:
            links.append(f"- {title}")
    joined = "\n".join(links) if links else "- FastAPI docs: https://fastapi.tiangolo.com/"
    return (
        f"For {topic}, don't paste a whole file from me — create a minimal version yourself.\n"
        f"Look here first:\n{joined}\n"
        "Include only what you need for this step (name, python version, fastapi, uvicorn). "
        "When the file exists, say **done**."
    )


def replacement_for_stripped_dump(
    body: str,
    *,
    resources: list[dict[str, str]] | None = None,
) -> str:
    lower = body.lower()
    resources = resources or []
    if "pyproject" in lower or "[project]" in lower or "dependencies" in lower:
        return resource_hint(resources, topic="pyproject.toml / dependencies")
    if "requirements.txt" in lower or "fastapi==" in lower:
        return resource_hint(resources, topic="dependency pinning")
    if "readme" in lower and ("## setup" in lower or "pip install" in lower):
        return (
            "Write a short README yourself: project name, how to install, "
            "and the exact uvicorn command. Keep it to a few lines — then say **done**."
        )
    if "fastapi" in lower or "def " in lower or "@app." in lower:
        return (
            "I won't paste a full app. Add only the smallest `/health` handler in your entrypoint, "
            "then run uvicorn and tell me what you see."
        )
    return (
        "I removed a large paste. Do the smallest version of that file yourself, "
        "using the project brief resources if needed — then reply **done**."
    )
