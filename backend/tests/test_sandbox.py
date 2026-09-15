from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.learning_state import ConceptState
from app.services.sandbox_runner import (
    FakeSandboxRunner,
    RunResult,
    set_sandbox_runner,
    validate_argv,
)
from tests.conftest import make_course_path


@pytest.fixture
def fake_runner() -> FakeSandboxRunner:
    runner = FakeSandboxRunner(
        RunResult(exit_code=0, stdout="2 passed in 0.01s\n", stderr="")
    )
    set_sandbox_runner(runner)
    yield runner
    set_sandbox_runner(None)


@pytest.fixture
def workspace_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workspaces"
    monkeypatch.setattr(
        "app.core.config.settings.sandbox_workspaces_root", str(root)
    )
    monkeypatch.setattr("app.services.sandbox.settings.sandbox_workspaces_root", str(root))
    return root


def _enroll_project(client: TestClient, auth_headers: dict[str, str], db: Session) -> int:
    path = make_course_path(db, with_project=True)
    response = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": path["course_id"],
            "primary_option_id": path["primary_option_id"],
            "secondary_option_id": path["secondary_option_id"],
            "learning_mode": "project",
        },
    )
    assert response.status_code == 201, response.text
    user_project_id = response.json()["user_project"]["id"]
    return int(user_project_id)


def test_validate_argv_allowlist() -> None:
    assert validate_argv(["node", "server.js"]) == ["node", "server.js"]
    assert validate_argv(["node", "--test"]) == ["node", "--test"]
    assert validate_argv(["mkdir", "-p", "lib"]) == ["mkdir", "-p", "lib"]
    assert validate_argv(["npx", "--version"]) == ["npx", "--version"]
    with pytest.raises(ValueError, match="not allowed"):
        validate_argv(["bash", "-c", "ls"])
    with pytest.raises(ValueError, match="not allowed"):
        validate_argv(["curl", "https://example.com"])
    with pytest.raises(ValueError, match="empty"):
        validate_argv([])


def test_parse_command_line() -> None:
    from app.services.sandbox_runner import parse_command_line, validate_cwd

    assert parse_command_line("ls -la") == ["ls", "-la"]
    assert parse_command_line("node --test") == ["node", "--test"]
    with pytest.raises(ValueError, match="shell operators"):
        parse_command_line("ls | cat")
    assert validate_cwd(None) is None
    assert validate_cwd("app/api") == "app/api"
    with pytest.raises(ValueError, match="traversal"):
        validate_cwd("../etc")


def test_sandbox_init_and_files(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    user_project_id = _enroll_project(client, auth_headers, db)
    init = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox",
        headers=auth_headers,
    )
    assert init.status_code == 200
    body = init.json()
    assert body["user_project_id"] == user_project_id
    assert body["status"] == "ready"
    assert (workspace_tmp / str(user_project_id) / "README.md").exists()

    listed = client.get(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    paths = {entry["path"] for entry in listed.json()["files"]}
    assert "README.md" in paths
    assert "tests" not in paths


def test_sandbox_path_traversal_rejected(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    from fastapi import HTTPException

    from app.services.sandbox import resolve_safe_path, workspace_path_for

    user_project_id = _enroll_project(client, auth_headers, db)
    client.post(f"/api/v1/me/projects/{user_project_id}/sandbox", headers=auth_headers)
    root = workspace_path_for(user_project_id)
    with pytest.raises(HTTPException) as exc:
        resolve_safe_path(root, "../etc/passwd")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        resolve_safe_path(root, "subdir/../../outside.py")
    assert exc.value.status_code == 400

    # Absolute-looking paths still resolve under the workspace root
    ok = resolve_safe_path(root, "src/main.py")
    assert ok == (root / "src" / "main.py").resolve()


def test_sandbox_write_read_delete(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    user_project_id = _enroll_project(client, auth_headers, db)
    put = client.put(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files/hello.js",
        headers=auth_headers,
        json={"content": "console.log('hi')\n"},
    )
    assert put.status_code == 200
    assert put.json()["content"] == "console.log('hi')\n"

    get = client.get(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files/hello.js",
        headers=auth_headers,
    )
    assert get.status_code == 200
    assert get.json()["content"] == "console.log('hi')\n"

    delete = client.delete(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files/hello.js",
        headers=auth_headers,
    )
    assert delete.status_code == 204
    missing = client.get(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files/hello.js",
        headers=auth_headers,
    )
    assert missing.status_code == 404


def test_sandbox_run_rejects_disallowed(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    user_project_id = _enroll_project(client, auth_headers, db)
    response = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox/run",
        headers=auth_headers,
        json={"argv": ["curl", "https://example.com"]},
    )
    assert response.status_code == 400
    assert fake_runner.calls == []


def test_sandbox_run_accepts_command_string(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    user_project_id = _enroll_project(client, auth_headers, db)
    response = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox/run",
        headers=auth_headers,
        json={"command": "mkdir -p app"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["argv"] == ["mkdir", "-p", "app"]
    assert body["mutates_fs"] is True
    assert fake_runner.calls[-1][1] == ["mkdir", "-p", "app"]


def test_sandbox_run_and_test_wire_coach_attempts(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    user_project_id = _enroll_project(client, auth_headers, db)

    run = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox/run",
        headers=auth_headers,
        json={"argv": ["node", "-e", "console.log(1)"]},
    )
    assert run.status_code == 200
    assert run.json()["exit_code"] == 0
    assert fake_runner.calls[-1][1] == ["node", "-e", "console.log(1)"]

    fake_runner.result = RunResult(
        exit_code=1,
        stdout="# tests 1\n# pass 0\n# fail 1\n",
        stderr="",
    )
    test = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox/test",
        headers=auth_headers,
    )
    assert test.status_code == 200
    body = test.json()
    assert body["outcome"] == "failed"
    assert body["failed"] == 1
    assert fake_runner.calls[-1][1] == ["node", "--test"]

    state = (
        db.query(ConceptState)
        .filter(ConceptState.user_project_id == user_project_id)
        .first()
    )
    # Fixture projects have no concept graph rows; recording still should not 500.
    fake_runner.result = RunResult(
        exit_code=0, stdout="# tests 3\n# pass 3\n# fail 0\n", stderr=""
    )
    ok = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox/test",
        headers=auth_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["outcome"] == "passed"
    if state is not None:
        db.refresh(state)
        assert state.status.value in {"explained", "attempted", "testing", "blocked", "available", "introduced"}


def test_tested_attempt_counts_as_hint_effort() -> None:
    from app.agents.policies import has_genuine_effort, next_hint_level

    assert has_genuine_effort(
        {
            "learner_turns_since_hint": 0,
            "checkpoint_since_hint": False,
            "attempt_message": False,
            "tested_attempt": True,
        }
    )
    level, reason = next_hint_level(
        0,
        {
            "learner_turns_since_hint": 0,
            "checkpoint_since_hint": False,
            "attempt_message": False,
            "tested_attempt": True,
        },
    )
    assert reason is None
    assert level == 1


def test_docker_unavailable_returns_503(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Docker is down, run/test should be 503 with a clear detail — not 500."""
    from app.services.sandbox_runner import DockerSandboxRunner, set_sandbox_runner

    class BrokenDocker(DockerSandboxRunner):
        def _client(self):  # noqa: ANN202
            raise RuntimeError(
                "Cannot connect to Docker. Install/start Docker Desktop "
                "(or a Docker daemon), then build the sandbox image:\n"
                "  docker build -t socratic-sandbox-node:latest sandbox"
            )

    set_sandbox_runner(BrokenDocker())
    try:
        user_project_id = _enroll_project(client, auth_headers, db)
        response = client.post(
            f"/api/v1/me/projects/{user_project_id}/sandbox/run",
            headers=auth_headers,
            json={"argv": ["node", "-e", "console.log(1)"]},
        )
        assert response.status_code == 503
        assert "Docker" in response.json()["detail"]
    finally:
        set_sandbox_runner(None)


@pytest.mark.docker
def test_docker_sandbox_smoke(tmp_path: Path) -> None:
    """Optional: requires Docker + built socratic-sandbox-node:latest."""
    import os

    if os.environ.get("SOCRATIC_SANDBOX_DOCKER") != "1":
        pytest.skip("Set SOCRATIC_SANDBOX_DOCKER=1 to run Docker integration")

    from app.services.sandbox_runner import DockerSandboxRunner

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "hello.js").write_text("console.log('ok')\n", encoding="utf-8")
    runner = DockerSandboxRunner(timeout_sec=60)
    result = runner.run(workspace, ["node", "hello.js"])
    assert result.timed_out is False
    assert result.exit_code == 0
    assert "ok" in result.stdout


def test_parse_node_test_counts() -> None:
    from app.services.sandbox import _parse_node_test_counts

    passed, failed, errors = _parse_node_test_counts("# tests 3\n# pass 3\n# fail 0\n")
    assert (passed, failed, errors) == (3, 0, 0)
    passed, failed, errors = _parse_node_test_counts("# tests 1\n# pass 0\n# fail 1\n")
    assert (passed, failed) == (0, 1)

