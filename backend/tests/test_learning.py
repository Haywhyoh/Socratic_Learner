from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_course_path


def test_list_courses_and_nested_options(client: TestClient, seeded_db: Session) -> None:
    courses = client.get("/api/v1/courses")
    assert courses.status_code == 200
    body = courses.json()
    assert {c["slug"] for c in body} >= {"software-engineering", "business"}

    se = next(c for c in body if c["slug"] == "software-engineering")
    primary = client.get(f"/api/v1/courses/{se['id']}/options")
    assert primary.status_code == 200
    names = {o["name"] for o in primary.json()}
    assert "Python" in names
    assert "JavaScript" in names

    python = next(o for o in primary.json() if o["slug"] == "python")
    secondary = client.get(f"/api/v1/courses/{se['id']}/options/{python['id']}/options")
    assert secondary.status_code == 200
    assert {o["slug"] for o in secondary.json()} >= {"fastapi", "django"}


def test_enroll_project_mode_assigns_project_and_milestones(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    path = make_course_path(db, with_project=True)
    response = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={**{k: path[k] for k in ("course_id", "primary_option_id", "secondary_option_id")}, "learning_mode": "project"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["assigned_project_id"] == path["project_id"]
    assert data["user_project"] is not None
    assert len(data["user_milestones"]) == 3
    assert all(um["status"] == "pending" for um in data["user_milestones"])


def test_enroll_project_mode_without_matching_project_returns_409(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    path = make_course_path(db, with_project=False)
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
    assert response.status_code == 409


def test_complete_milestones_in_order(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    path = make_course_path(db, with_project=True)
    enrolled = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": path["course_id"],
            "primary_option_id": path["primary_option_id"],
            "secondary_option_id": path["secondary_option_id"],
            "learning_mode": "project",
        },
    )
    assert enrolled.status_code == 201
    user_milestones = enrolled.json()["user_milestones"]
    ordered = sorted(
        user_milestones,
        key=lambda um: next(
            m["order_index"] for m in enrolled.json()["milestones"] if m["id"] == um["milestone_id"]
        ),
    )

    # Out of order should fail
    second = ordered[1]
    bad = client.post(
        f"/api/v1/me/milestones/{second['id']}/complete",
        headers=auth_headers,
    )
    assert bad.status_code == 409

    for um in ordered:
        ok = client.post(
            f"/api/v1/me/milestones/{um['id']}/complete",
            headers=auth_headers,
        )
        assert ok.status_code == 200
        assert ok.json()["status"] == "completed"

    user_project_id = enrolled.json()["user_project"]["id"]
    progress = client.get(f"/api/v1/me/projects/{user_project_id}", headers=auth_headers)
    assert progress.status_code == 200
    assert progress.json()["status"] == "completed"


def test_enroll_concept_mode_creates_pending_session(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    path = make_course_path(db, with_project=False)
    response = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": path["course_id"],
            "primary_option_id": path["primary_option_id"],
            "secondary_option_id": path["secondary_option_id"],
            "learning_mode": "concept",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["concept_session_id"] is not None

    session = client.get(
        f"/api/v1/concept-sessions/{data['concept_session_id']}",
        headers=auth_headers,
    )
    assert session.status_code == 200
    body = session.json()
    assert body["question_text"] is None
    assert body["status"] == "pending_generation"
    assert body["turns"] == []
