from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.project import Milestone
from app.services.sandbox_runner import FakeSandboxRunner
from tests.conftest import make_course_path


REFLECTION = {
    "what": "I built the smallest possible version of this milestone.",
    "why": "It was the simplest design that still satisfied the success criteria.",
    "alternatives": "I considered a more nested layout but rejected it.",
    "difficult": "Naming the modules without copying a framework.",
    "scale": "A linear scan would get slow with thousands of routes.",
    "change": "I would extract a matcher function.",
}


def _enroll_project(client: TestClient, auth_headers: dict[str, str], db: Session) -> dict:
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
    return response.json()


def _first_user_milestone_id(enrolled: dict) -> int:
    ordered = sorted(
        enrolled["user_milestones"],
        key=lambda um: next(
            m["order_index"] for m in enrolled["milestones"] if m["id"] == um["milestone_id"]
        ),
    )
    return int(ordered[0]["id"])


def test_curriculum_is_generated_per_user_project(
    client: TestClient, auth_headers: dict[str, str], db: Session
) -> None:
    """Milestones are cloned onto the learner's own UserProject."""
    enrolled = _enroll_project(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    milestone_ids = [um["milestone_id"] for um in enrolled["user_milestones"]]
    rows = db.query(Milestone).filter(Milestone.id.in_(milestone_ids)).all()
    assert len(rows) == 3
    for row in rows:
        assert row.user_project_id == user_project_id
        assert row.generated is False


def test_review_requires_passing_tests_first(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    enrolled = _enroll_project(client, auth_headers, db)
    user_milestone_id = _first_user_milestone_id(enrolled)

    blocked = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/review",
        headers=auth_headers,
    )
    assert blocked.status_code == 409
    assert "tests" in blocked.json()["detail"].lower()


def test_review_available_after_green_tests(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    enrolled = _enroll_project(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    user_milestone_id = _first_user_milestone_id(enrolled)

    client.post(f"/api/v1/me/projects/{user_project_id}/sandbox", headers=auth_headers)
    client.put(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files/server.js",
        headers=auth_headers,
        json={"content": "const http = require('http');\n"},
    )
    still_blocked = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/review", headers=auth_headers
    )
    assert still_blocked.status_code == 409

    test_run = client.post(
        f"/api/v1/me/projects/{user_project_id}/sandbox/test", headers=auth_headers
    )
    assert test_run.status_code == 200
    assert test_run.json()["outcome"] == "passed"

    review = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/review", headers=auth_headers
    )
    assert review.status_code == 200
    body = review.json()
    assert body["verdict"] == "awaiting_understanding"
    assert body["understanding_questions"]

    still_pending = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/complete", headers=auth_headers
    )
    assert still_pending.status_code == 409

    reflected = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/reflection",
        headers=auth_headers,
        json={"answers": REFLECTION},
    )
    assert reflected.status_code == 200
    completed = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/complete", headers=auth_headers
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_review_understanding_answers_can_fail_and_retry(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    workspace_tmp: Path,
    fake_runner: FakeSandboxRunner,
) -> None:
    enrolled = _enroll_project(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    user_milestone_id = _first_user_milestone_id(enrolled)

    client.post(f"/api/v1/me/projects/{user_project_id}/sandbox", headers=auth_headers)
    client.put(
        f"/api/v1/me/projects/{user_project_id}/sandbox/files/server.js",
        headers=auth_headers,
        json={"content": "const http = require('http');\n"},
    )
    client.post(f"/api/v1/me/projects/{user_project_id}/sandbox/test", headers=auth_headers)
    review = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/review", headers=auth_headers
    ).json()
    assert review["verdict"] == "awaiting_understanding"

    weak = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/review/answer",
        headers=auth_headers,
        json={"answers": ["idk" for _ in review["understanding_questions"]]},
    )
    assert weak.status_code == 200
    body = weak.json()
    assert body["verdict"] == "needs_work"
    assert body["understanding_answers"][-1]["passed"] is False
