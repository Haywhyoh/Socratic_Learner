"""Sandbox-scoped tools the mentor LLM may call (never escapes the workspace)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from langchain_core.tools import StructuredTool


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, list):
            return "ERROR: " + "; ".join(str(item) for item in detail)
        return f"ERROR: {detail}"
    return f"ERROR: {exc}"


def make_sandbox_tools(
    *,
    list_files: Callable[[], str],
    read_file: Callable[[str], str],
    run_command: Callable[[str], str],
    delete_file: Callable[[str], str],
    rename_file: Callable[[str, str], str],
) -> list[Any]:
    return [
        StructuredTool.from_function(
            func=list_files,
            name="list_workspace_files",
            description="List files in the learner's sandbox workspace as a newline-separated list of paths.",
        ),
        StructuredTool.from_function(
            func=read_file,
            name="read_workspace_file",
            description="Read one UTF-8 text file from the learner workspace. Path is workspace-relative.",
        ),
        StructuredTool.from_function(
            func=run_command,
            name="run_workspace_command",
            description=(
                "Run one allowlisted command in the learner sandbox "
                "(python, pytest, node, ls, etc.). No pipes or network. "
                "Do not use this to delete or rename files — use delete_workspace_file "
                "or rename_workspace_file so paths stay inside the workspace."
            ),
        ),
        StructuredTool.from_function(
            func=delete_file,
            name="delete_workspace_file",
            description=(
                "Delete one workspace-relative file or empty folder. "
                "Paths cannot leave the learner sandbox."
            ),
        ),
        StructuredTool.from_function(
            func=rename_file,
            name="rename_workspace_file",
            description=(
                "Rename or move a workspace-relative file or folder. "
                "Both source and dest must stay inside the learner sandbox."
            ),
        ),
    ]


def bind_coach_sandbox_tools(db: Any, user: Any, user_project_id: int) -> list[Any]:
    from app.services import sandbox as sandbox_service

    def list_files() -> str:
        entries = sandbox_service.list_files(db, user, user_project_id)
        if not entries:
            return "(empty workspace)"
        lines: list[str] = []
        for entry in entries:
            suffix = "/" if entry.get("is_dir") else ""
            lines.append(f"{entry['path']}{suffix}")
        return "\n".join(lines)

    def read_file(path: str) -> str:
        try:
            payload = sandbox_service.read_file(db, user, user_project_id, path)
        except Exception as exc:
            return _error_text(exc)
        content = str(payload.get("content") or "")
        if len(content) > 8_000:
            return content[:8_000] + "\n...[truncated]"
        return content or "(empty file)"

    def run_command(command: str) -> str:
        try:
            result = sandbox_service.run_command(db, user, user_project_id, command=command)
        except Exception as exc:
            return _error_text(exc)
        parts = [
            f"exit_code={result.get('exit_code')}",
            f"timed_out={result.get('timed_out')}",
        ]
        stdout = str(result.get("stdout") or "").strip()
        stderr = str(result.get("stderr") or "").strip()
        if stdout:
            parts.append("stdout:\n" + stdout[-4_000:])
        if stderr:
            parts.append("stderr:\n" + stderr[-4_000:])
        return "\n".join(parts)

    def delete_file(path: str) -> str:
        try:
            sandbox_service.delete_file(db, user, user_project_id, path)
        except Exception as exc:
            return _error_text(exc)
        return f"Deleted {path}"

    def rename_file(source: str, dest: str) -> str:
        try:
            result = sandbox_service.rename_file(db, user, user_project_id, source, dest)
        except Exception as exc:
            return _error_text(exc)
        return f"Renamed {result['source']} -> {result['dest']}"

    return make_sandbox_tools(
        list_files=list_files,
        read_file=read_file,
        run_command=run_command,
        delete_file=delete_file,
        rename_file=rename_file,
    )


def workspace_root_path(user_project_id: int) -> Path:
    from app.services.sandbox import workspace_path_for

    return workspace_path_for(user_project_id)
