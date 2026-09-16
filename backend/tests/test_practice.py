import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.llm import LLMConfigurationError, _dynamic_mentor_prompt, get_coach_llm
from app.models.learning_state import ConceptState
from app.services.sandbox_runner import FakeSandboxRunner, RunResult, set_sandbox_runner


def _enroll_python(client: TestClient, auth_headers: dict[str, str]) -> dict:
    courses = client.get("/api/v1/courses").json()
    py = next(c for c in courses if c["slug"] == "python")
    primary = client.get(f"/api/v1/courses/{py['id']}/options").json()
    lang = next(o for o in primary if o["slug"] == "python")
    secondary = client.get(f"/api/v1/courses/{py['id']}/options/{lang['id']}/options").json()
    stdlib = next(o for o in secondary if o["slug"] == "stdlib")
    response = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": py["id"],
            "primary_option_id": lang["id"],
            "secondary_option_id": stdlib["id"],
            "learning_mode": "project",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_python_mentor_prompt_is_not_js_framework() -> None:
    text = _dynamic_mentor_prompt(
        {
            "project_title": "Learn Python: Language and a CLI Notebook",
            "runtime": {"language": "python"},
            "practice_tasks": [
                {"id": "hello", "filename": "practice/hello.py", "prompt": "Print Hello"}
            ],
        },
        "hi",
        "IMPLEMENTATION",
    )
    assert "backend framework" not in text.lower()
    assert "python" in text.lower()
    assert "practice/hello.py" in text


def test_get_coach_llm_raises_without_key(monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "llm_model", "anthropic:claude-haiku-4-5")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    with pytest.raises(LLMConfigurationError):
        get_coach_llm()


def test_python_practice_eval_records_implementation(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
    db: Session,
    workspace_tmp,
) -> None:
    runner = FakeSandboxRunner(RunResult(exit_code=0, stdout="Hello, Python\n", stderr=""))
    set_sandbox_runner(runner)
    try:
        enrolled = _enroll_python(client, auth_headers)
        user_project_id = enrolled["user_project"]["id"]
        start = client.post(
            f"/api/v1/me/projects/{user_project_id}/coach/start",
            headers=auth_headers,
            json={"answers": []},
        )
        assert start.status_code == 200
        write = client.put(
            f"/api/v1/me/projects/{user_project_id}/sandbox/files/practice/hello.py",
            headers=auth_headers,
            json={"content": "print('Hello, Python')\n"},
        )
        assert write.status_code == 200, write.text
        checked = client.post(
            f"/api/v1/me/projects/{user_project_id}/coach/evaluate-practice",
            headers=auth_headers,
            json={"filename": "practice/hello.py"},
        )
        assert checked.status_code == 200, checked.text
        body = checked.json()
        db.expire_all()
        state = (
            db.query(ConceptState)
            .filter(
                ConceptState.user_project_id == user_project_id,
                ConceptState.concept_id == "python.scripts",
            )
            .first()
        )
        assert state is not None
        assert state.evidence.get("implementation") is True, body
        assert "hello" in (state.evidence.get("practice_task_ids") or []), body
        assert runner.calls[-1][1] == ["python", "practice/hello.py"]
    finally:
        set_sandbox_runner(None)


def test_python_sandbox_test_uses_pytest(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
    workspace_tmp,
) -> None:
    runner = FakeSandboxRunner(RunResult(exit_code=0, stdout="2 passed in 0.01s\n", stderr=""))
    set_sandbox_runner(runner)
    try:
        enrolled = _enroll_python(client, auth_headers)
        user_project_id = enrolled["user_project"]["id"]
        init = client.post(
            f"/api/v1/me/projects/{user_project_id}/sandbox",
            headers=auth_headers,
        )
        assert init.status_code == 200
        test = client.post(
            f"/api/v1/me/projects/{user_project_id}/sandbox/test",
            headers=auth_headers,
        )
        assert test.status_code == 200
        assert runner.calls[-1][1] == ["pytest", "-q"]
        assert test.json()["outcome"] == "passed"
    finally:
        set_sandbox_runner(None)
