from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_course_path

REFLECTION = {
    "what": "I built the smallest possible version of this milestone.",
    "why": "It was the simplest design that still satisfied the success criteria.",
    "alternatives": "I considered a more nested layout but rejected it.",
    "difficult": "Naming the modules without copying a framework.",
    "scale": "A linear scan would get slow with thousands of routes.",
    "change": "I would extract a matcher function.",
}


def _gate_milestone(client: TestClient, auth_headers: dict[str, str], user_milestone_id: int, *, last: bool, user_project_id: int) -> None:
    reflected = client.post(
        f"/api/v1/me/milestones/{user_milestone_id}/reflection",
        headers=auth_headers,
        json={"answers": REFLECTION},
    )
    assert reflected.status_code == 200
    if last:
        start = client.post(
            f"/api/v1/me/projects/{user_project_id}/defense/start",
            headers=auth_headers,
        )
        assert start.status_code == 200
        questions = start.json()["questions"]
        answers = [
            "I structured it this way because each concern has a single owner in the code."
        ] * len(questions)
        defended = client.post(
            f"/api/v1/me/projects/{user_project_id}/defense/answer",
            headers=auth_headers,
            json={"answers": answers},
        )
        assert defended.status_code == 200
        assert defended.json()["verdict"] == "passed"


def test_list_courses_and_nested_options(client: TestClient, seeded_db: Session) -> None:
    courses = client.get("/api/v1/courses")
    assert courses.status_code == 200
    body = courses.json()
    assert {c["slug"] for c in body} == {"javascript"}

    js = body[0]
    primary = client.get(f"/api/v1/courses/{js['id']}/options")
    assert primary.status_code == 200
    names = {o["name"] for o in primary.json()}
    assert "JavaScript" in names

    lang = next(o for o in primary.json() if o["slug"] == "javascript")
    secondary = client.get(f"/api/v1/courses/{js['id']}/options/{lang['id']}/options")
    assert secondary.status_code == 200
    assert {o["slug"] for o in secondary.json()} >= {"node-core"}


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

    for index, um in enumerate(ordered):
        _gate_milestone(
            client,
            auth_headers,
            um["id"],
            last=index == len(ordered) - 1,
            user_project_id=enrolled.json()["user_project"]["id"],
        )
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
    user_project_id = enrolled.json()["user_project"]["id"]
    for index, um in enumerate(ordered):
        _gate_milestone(
            client,
            auth_headers,
            um["id"],
            last=index == len(ordered) - 1,
            user_project_id=user_project_id,
        )
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

    _gate_milestone(
        client,
        auth_headers,
        ordered[1]["id"],
        last=False,
        user_project_id=enrolled.json()["user_project"]["id"],
    )
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


def test_enroll_concept_mode_assigns_pending_without_catalog(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
) -> None:
    courses = client.get("/api/v1/courses").json()
    js = next(c for c in courses if c["slug"] == "javascript")
    primary = client.get(f"/api/v1/courses/{js['id']}/options").json()
    lang = next(o for o in primary if o["slug"] == "javascript")
    secondary = client.get(f"/api/v1/courses/{js['id']}/options/{lang['id']}/options").json()
    node = next(o for o in secondary if o["slug"] == "node-core")

    response = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": js["id"],
            "primary_option_id": lang["id"],
            "secondary_option_id": node["id"],
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
    assert body["status"] == "pending_generation"
    assert body["question_text"] is None


def test_seeded_js_framework_project_exists(client: TestClient, seeded_db: Session) -> None:
    courses = client.get("/api/v1/courses").json()
    js = next(c for c in courses if c["slug"] == "javascript")
    primary = client.get(f"/api/v1/courses/{js['id']}/options").json()
    lang = next(o for o in primary if o["slug"] == "javascript")
    secondary = client.get(f"/api/v1/courses/{js['id']}/options/{lang['id']}/options").json()
    node = next(o for o in secondary if o["slug"] == "node-core")

    projects = client.get(
        "/api/v1/projects",
        params={
            "course_id": js["id"],
            "primary_option_id": lang["id"],
            "secondary_option_id": node["id"],
        },
    ).json()
    assert {p["title"] for p in projects} >= {
        "Build a Simple Backend Framework in JavaScript",
    }
    project = projects[0]
    detail = client.get(f"/api/v1/projects/{project['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["difficulty"] == "intermediate"
    assert body["objective"]
    assert len(body["milestones"]) == 12
    assert body["milestones"][0]["instructions"]
    assert "What to do" in body["milestones"][0]["instructions"]
