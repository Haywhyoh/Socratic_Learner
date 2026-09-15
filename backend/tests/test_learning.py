from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.coach import MilestoneReview, MilestoneReviewVerdict
from tests.conftest import make_course_path


def _approve_review(db: Session, user_milestone_id: int) -> None:
    """Test helper: milestone completion is gated on the AI review passing —

    the review pipeline itself (sandbox code + LLM) is covered in
    test_coach.py, so ordering/restart tests here just approve directly.
    """
    review = MilestoneReview(
        user_milestone_id=user_milestone_id,
        verdict=MilestoneReviewVerdict.passed,
    )
    db.add(review)
    db.commit()


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
        _approve_review(db, um["id"])
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


def test_restart_milestone_resets_from_that_point(
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
    ordered = sorted(
        enrolled.json()["user_milestones"],
        key=lambda um: next(
            m["order_index"] for m in enrolled.json()["milestones"] if m["id"] == um["milestone_id"]
        ),
    )
    for um in ordered:
        _approve_review(db, um["id"])
        assert (
            client.post(
                f"/api/v1/me/milestones/{um['id']}/complete",
                headers=auth_headers,
            ).status_code
            == 200
        )

    restarted = client.post(
        f"/api/v1/me/milestones/{ordered[1]['id']}/restart",
        headers=auth_headers,
    )
    assert restarted.status_code == 200
    body = restarted.json()
    assert body["status"] == "in_progress"

    by_id = {um["id"]: um for um in body["user_milestones"]}
    assert by_id[ordered[0]["id"]]["status"] == "completed"
    assert by_id[ordered[0]["id"]]["completed_at"] is not None
    assert by_id[ordered[1]["id"]]["status"] == "pending"
    assert by_id[ordered[1]["id"]]["completed_at"] is None
    assert by_id[ordered[2]["id"]]["status"] == "pending"
    assert by_id[ordered[2]["id"]]["completed_at"] is None

    # Can complete again from the restarted point
    _approve_review(db, ordered[1]["id"])
    assert (
        client.post(
            f"/api/v1/me/milestones/{ordered[1]['id']}/complete",
            headers=auth_headers,
        ).status_code
        == 200
    )


def test_enroll_concept_mode_without_question_is_pending(
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


def test_enroll_concept_mode_assigns_seeded_question(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
) -> None:
    courses = client.get("/api/v1/courses").json()
    se = next(c for c in courses if c["slug"] == "software-engineering")
    primary = client.get(f"/api/v1/courses/{se['id']}/options").json()
    python = next(o for o in primary if o["slug"] == "python")
    secondary = client.get(f"/api/v1/courses/{se['id']}/options/{python['id']}/options").json()
    fastapi = next(o for o in secondary if o["slug"] == "fastapi")

    response = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": se["id"],
            "primary_option_id": python["id"],
            "secondary_option_id": fastapi["id"],
            "learning_mode": "concept",
        },
    )
    assert response.status_code == 201
    session = client.get(
        f"/api/v1/concept-sessions/{response.json()['concept_session_id']}",
        headers=auth_headers,
    )
    assert session.status_code == 200
    body = session.json()
    assert body["status"] == "active"
    assert body["question_text"]
    assert "FastAPI" in body["question_text"] or "dependency" in body["question_text"].lower()


def test_seeded_python_projects_exist(client: TestClient, seeded_db: Session) -> None:
    courses = client.get("/api/v1/courses").json()
    se = next(c for c in courses if c["slug"] == "software-engineering")
    primary = client.get(f"/api/v1/courses/{se['id']}/options").json()
    python = next(o for o in primary if o["slug"] == "python")
    secondary = client.get(f"/api/v1/courses/{se['id']}/options/{python['id']}/options").json()
    fastapi = next(o for o in secondary if o["slug"] == "fastapi")
    django = next(o for o in secondary if o["slug"] == "django")

    fastapi_projects = client.get(
        "/api/v1/projects",
        params={
            "course_id": se["id"],
            "primary_option_id": python["id"],
            "secondary_option_id": fastapi["id"],
        },
    ).json()
    django_projects = client.get(
        "/api/v1/projects",
        params={
            "course_id": se["id"],
            "primary_option_id": python["id"],
            "secondary_option_id": django["id"],
        },
    ).json()

    assert {p["title"] for p in fastapi_projects} >= {
        "Task Tracker API",
        "Notes API with Tags",
    }
    assert {p["title"] for p in django_projects} >= {"Library Catalog"}

    task = next(p for p in fastapi_projects if p["title"] == "Task Tracker API")
    detail = client.get(f"/api/v1/projects/{task['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["difficulty"] == "beginner"
    assert body["objective"]
    assert "task-tracking" in body["objective"].lower() or "task" in body["objective"].lower()
    assert isinstance(body["skills"], list) and body["skills"]
    assert isinstance(body["tests"], list) and body["tests"]
    assert isinstance(body["recommended_resources"], list) and body["recommended_resources"]
    assert body["recommended_resources"][0]["title"]
    assert body["recommended_resources"][0]["url"]
    assert "brief" not in body
    assert len(body["milestones"]) == 3
    assert body["milestones"][0]["instructions"]
    assert "What to do" in body["milestones"][0]["instructions"]
