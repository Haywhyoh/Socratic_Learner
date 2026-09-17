"""Background knowledge-graph generation so reverse proxies do not 504."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.graph_author import GraphAuthorError, generate_graph_draft
from app.agents.llm import LLMConfigurationError
from app.core.config import settings
from app.services.curriculum_authoring import GraphValidationError

TERMINAL = frozenset({"done", "error"})


def jobs_dir() -> Path:
    root = Path(settings.sandbox_workspaces_root).resolve().parent / "graph_jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(job_id: str) -> Path:
    token = "".join(ch for ch in job_id if ch.isalnum())
    if not token:
        raise FileNotFoundError(job_id)
    return jobs_dir() / f"{token}.json"


def _read(job_id: str) -> dict[str, Any]:
    path = _path(job_id)
    if not path.is_file():
        raise FileNotFoundError(job_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _write(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _path(job_id)
    path.write_text(json.dumps(payload, default=str), encoding="utf-8")
    return payload


def create_job(request: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    return _write(
        job_id,
        {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
            "error": None,
            "graph": None,
            "request": request,
        },
    )


def start_job(job_id: str) -> None:
    thread = threading.Thread(
        target=run_job,
        args=(job_id,),
        name=f"graph-generate-{job_id[:8]}",
        daemon=True,
    )
    thread.start()


def get_job(job_id: str) -> dict[str, Any]:
    row = _read(job_id)
    return {
        "job_id": row.get("job_id") or job_id,
        "status": str(row.get("status") or "queued"),
        "error": row.get("error"),
        "graph": row.get("graph"),
    }


def run_job(job_id: str) -> None:
    try:
        row = _read(job_id)
    except FileNotFoundError:
        return
    if str(row.get("status") or "") in TERMINAL:
        return
    row["status"] = "running"
    _write(job_id, row)
    request = dict(row.get("request") or {})
    try:
        graph = generate_graph_draft(
            topic=str(request.get("topic") or ""),
            language=str(request.get("language") or "python"),
            slug=str(request.get("slug") or "track"),
            audience=str(request.get("audience") or ""),
            constraints=list(request.get("constraints") or []),
            capstone=str(request.get("capstone") or ""),
            difficulty=str(request.get("difficulty") or "beginner"),
            course_name=str(request.get("course_name") or ""),
            track_kind=str(request.get("track_kind") or "language"),
            project_brief=str(request.get("project_brief") or ""),
            include_concepts=list(request.get("include_concepts") or []),
        )
        row["status"] = "done"
        row["graph"] = graph
        row["error"] = None
    except LLMConfigurationError as exc:
        row["status"] = "error"
        row["error"] = str(exc)
    except GraphValidationError as exc:
        row["status"] = "error"
        row["error"] = "; ".join(exc.errors) or str(exc)
    except GraphAuthorError as exc:
        row["status"] = "error"
        row["error"] = str(exc)
    except Exception as exc:
        row["status"] = "error"
        row["error"] = f"Failed to generate knowledge graph: {exc}"
    row["finished_at"] = datetime.now(UTC).isoformat()
    _write(job_id, row)
