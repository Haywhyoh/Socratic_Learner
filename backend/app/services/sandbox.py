"""Learner code workspace + sandboxed execution (never on the API process)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.sandbox import SandboxWorkspace, SandboxWorkspaceStatus
from app.models.user import User
from app.services import coach as coach_service
from app.services import learning as learning_service
from app.services.runtime import project_runtime, sandbox_image, test_command
from app.services.sandbox_runner import (
    FS_MUTATING_BINARIES,
    get_sandbox_runner,
    resolve_run_argv,
    validate_cwd,
)

_PYTEST_COUNTS_RE = re.compile(
    r"(?P<failed>\d+)\s+failed"
    r"|(?P<passed>\d+)\s+passed"
    r"|(?P<errors>\d+)\s+error"
)
_NODE_TEST_RE = re.compile(
    r"^#\s+(?P<kind>tests|pass|fail|cancelled|skipped|todo)\s+(?P<count>\d+)\s*$",
    re.MULTILINE,
)


def _require_enabled() -> None:
    if not settings.sandbox_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sandbox is disabled",
        )


def workspace_root() -> Path:
    root = Path(settings.sandbox_workspaces_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_path_for(user_project_id: int) -> Path:
    return workspace_root() / str(user_project_id)


def resolve_safe_path(workspace: Path, relative: str) -> Path:
    """Resolve a relative path under workspace; reject traversal."""
    cleaned = relative.strip().lstrip("/")
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path",
        )
    if ".." in Path(cleaned).parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal is not allowed",
        )
    target = (workspace / cleaned).resolve()
    root = workspace.resolve()
    if not target.is_relative_to(root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path escapes workspace",
        )
    return target


def _scaffold(workspace: Path, project_title: str, *, test_argv: list[str] | None = None) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    readme = workspace / "README.md"
    command = " ".join(test_argv or ["node", "--test"])
    if not readme.exists():
        readme.write_text(
            f"# {project_title}\n\n"
            "Learner workspace. Write your code here — no starter files.\n"
            "When you have tests, run:\n\n"
            "```bash\n"
            f"{command}\n"
            "```\n"
            "or: `socratic sandbox test`\n",
            encoding="utf-8",
        )


def _runtime_for(db: Session, user: User, user_project_id: int) -> dict[str, Any]:
    user_project = learning_service.get_user_project(db, user, user_project_id)
    return project_runtime(user_project.project)


def ensure_workspace(db: Session, user: User, user_project_id: int) -> SandboxWorkspace:
    _require_enabled()
    user_project = learning_service.get_user_project(db, user, user_project_id)
    path = workspace_path_for(user_project.id)
    runtime = project_runtime(user_project.project)
    _scaffold(path, user_project.project.title, test_argv=test_command(runtime))

    row = (
        db.query(SandboxWorkspace)
        .filter(SandboxWorkspace.user_project_id == user_project.id)
        .first()
    )
    if row is None:
        row = SandboxWorkspace(
            user_project_id=user_project.id,
            status=SandboxWorkspaceStatus.ready,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
        except IntegrityError:
            db.rollback()
            row = (
                db.query(SandboxWorkspace)
                .filter(SandboxWorkspace.user_project_id == user_project.id)
                .first()
            )
            if row is None:
                raise
    return row


def list_files(db: Session, user: User, user_project_id: int) -> list[dict[str, Any]]:
    ensure_workspace(db, user, user_project_id)
    root = workspace_path_for(user_project_id).resolve()
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append({"path": rel, "is_dir": True, "size": None})
        else:
            entries.append({"path": rel, "is_dir": False, "size": path.stat().st_size})
    return entries


def read_file(db: Session, user: User, user_project_id: int, relative: str) -> dict[str, str]:
    ensure_workspace(db, user, user_project_id)
    root = workspace_path_for(user_project_id)
    target = resolve_safe_path(root, relative)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not UTF-8 text",
        ) from exc
    return {"path": relative.strip().lstrip("/"), "content": content}


def write_file(
    db: Session, user: User, user_project_id: int, relative: str, content: str
) -> dict[str, str]:
    ensure_workspace(db, user, user_project_id)
    root = workspace_path_for(user_project_id)
    target = resolve_safe_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": relative.strip().lstrip("/"), "content": content}


def delete_file(db: Session, user: User, user_project_id: int, relative: str) -> None:
    ensure_workspace(db, user, user_project_id)
    root = workspace_path_for(user_project_id)
    target = resolve_safe_path(root, relative)
    if not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if target.is_dir():
        try:
            next(target.iterdir())
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Directory is not empty",
            )
        except StopIteration:
            target.rmdir()
            return
    target.unlink()


def run_command(
    db: Session,
    user: User,
    user_project_id: int,
    *,
    argv: list[str] | None = None,
    command: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    _require_enabled()
    row = ensure_workspace(db, user, user_project_id)
    try:
        safe_argv = resolve_run_argv(argv=argv, command=command)
        safe_cwd = validate_cwd(cwd)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if safe_cwd is not None:
        cwd_path = workspace_path_for(user_project_id) / safe_cwd
        if not cwd_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"cwd does not exist: {safe_cwd}",
            )

    workspace = workspace_path_for(user_project_id)
    runtime = _runtime_for(db, user, user_project_id)
    try:
        result = get_sandbox_runner().run(
            workspace,
            safe_argv,
            cwd=safe_cwd,
            image=sandbox_image(runtime),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    row.last_run_at = datetime.now(UTC)
    db.add(row)
    db.commit()

    return {
        "exit_code": result.exit_code,
        "stdout": result.stdout[-50_000:],
        "stderr": result.stderr[-50_000:],
        "timed_out": result.timed_out,
        "argv": safe_argv,
        "cwd": safe_cwd,
        "mutates_fs": safe_argv[0] in FS_MUTATING_BINARIES,
    }


def _parse_pytest_counts(output: str) -> tuple[int, int, int]:
    passed = failed = errors = 0
    for match in _PYTEST_COUNTS_RE.finditer(output):
        if match.group("passed"):
            passed = int(match.group("passed"))
        if match.group("failed"):
            failed = int(match.group("failed"))
        if match.group("errors"):
            errors = int(match.group("errors"))
    return passed, failed, errors


def _parse_node_test_counts(output: str) -> tuple[int, int, int]:
    passed = failed = errors = 0
    for match in _NODE_TEST_RE.finditer(output):
        kind = match.group("kind")
        count = int(match.group("count"))
        if kind == "pass":
            passed = count
        elif kind == "fail":
            failed = count
        elif kind == "tests" and passed == 0 and failed == 0:
            # tests total only used as fallback
            pass
    if "ERR_TEST_FAILURE" in output or "uncaughtException" in output:
        errors = max(errors, 1 if failed == 0 and passed == 0 else 0)
    return passed, failed, errors


def _uses_node_tests(workspace: Path) -> bool:
    if (workspace / "package.json").exists():
        return True
    for path in workspace.rglob("*"):
        if path.is_file() and path.suffix in {".js", ".mjs", ".cjs"}:
            name = path.name.lower()
            if ".test." in name or ".spec." in name or path.parent.name == "test":
                return True
    return False


def _failure_summary(output: str, *, max_lines: int = 12) -> str:
    """Short failure signal for coach — what failed, not how to fix."""
    lines = [line for line in output.splitlines() if line.strip()]
    interesting = [
        line
        for line in lines
        if line.startswith("FAILED")
        or line.startswith("ERROR")
        or " short test summary " in line
        or line.startswith("E ")
        or "AssertionError" in line
    ]
    chosen = interesting[:max_lines] if interesting else lines[-max_lines:]
    return "\n".join(chosen)[:2000]


def run_tests(db: Session, user: User, user_project_id: int) -> dict[str, Any]:
    _require_enabled()
    row = ensure_workspace(db, user, user_project_id)
    runtime = _runtime_for(db, user, user_project_id)
    argv = test_command(runtime)
    workspace = workspace_path_for(user_project_id)

    try:
        result = get_sandbox_runner().run(
            workspace, argv, image=sandbox_image(runtime)
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    combined = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    language = str(runtime.get("language") or "")
    if language == "python":
        passed, failed, errors = _parse_pytest_counts(combined)
        if passed == 0 and failed == 0 and errors == 0:
            passed, failed, errors = _parse_node_test_counts(combined)
    else:
        passed, failed, errors = _parse_node_test_counts(combined)
        if passed == 0 and failed == 0 and errors == 0:
            passed, failed, errors = _parse_pytest_counts(combined)

    outcome = "passed" if result.exit_code == 0 and not result.timed_out else "failed"
    if result.timed_out:
        outcome = "failed"
    summary = _failure_summary(combined) if outcome == "failed" else "All tests passed."

    payload = {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "output": combined[-50_000:],
        "summary": summary,
        "outcome": outcome,
    }

    row.last_run_at = datetime.now(UTC)
    row.last_test_summary = {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "outcome": outcome,
        "summary": summary[:500],
    }
    db.add(row)
    db.commit()

    coach_service.record_sandbox_test_attempt(
        db,
        user,
        user_project_id,
        outcome=outcome,
        summary=summary[:200],
        passed=outcome == "passed",
    )
    return payload


_REVIEW_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules"}
_REVIEW_SKIP_FILES = {"README.md"}
_REVIEW_MAX_FILES = 25
_REVIEW_MAX_FILE_CHARS = 4_000
_REVIEW_MAX_TOTAL_CHARS = 30_000


def collect_source_bundle(user_project_id: int) -> str:
    """Read the learner's current workspace into a bounded text bundle for the

    milestone-review LLM prompt — this is how the coach 'sees' the actual code
    instead of only chat answers.
    """
    root = workspace_path_for(user_project_id)
    if not root.exists():
        return ""
    parts: list[str] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        if any(part in _REVIEW_SKIP_DIRS for part in rel.parts):
            continue
        if rel.name in _REVIEW_SKIP_FILES:
            continue
        if len(parts) >= _REVIEW_MAX_FILES or total >= _REVIEW_MAX_TOTAL_CHARS:
            break
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not content.strip():
            continue
        snippet = content[:_REVIEW_MAX_FILE_CHARS]
        block = f"--- {rel.as_posix()} ---\n{snippet}\n"
        total += len(block)
        parts.append(block)
    return "\n".join(parts)


def workspace_read_payload(row: SandboxWorkspace, user_project_id: int) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_project_id": row.user_project_id,
        "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        "last_run_at": row.last_run_at,
        "last_test_summary": row.last_test_summary,
        "workspace_path": str(workspace_path_for(user_project_id)),
    }
