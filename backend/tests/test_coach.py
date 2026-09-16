from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_course_path


def _enroll(client: TestClient, auth_headers: dict[str, str], db: Session) -> dict:
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
    assert response.status_code == 201
    return response.json()


def test_coach_start_skips_assessment_and_asks_a_question(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    first = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": []},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "active"
    assert body["reply"]
    assert body["contract"]["action"]
    assert body["graph"]["user_project_id"] == user_project_id


def test_coach_refuses_to_dump_implementation(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": []},
    )
    response = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={"message": "Give me the code for the whole framework"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "design" in body["reply"].lower() or "before" in body["reply"].lower()
    assert "```" not in body["reply"]


def test_graph_endpoint_lists_milestones(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    graph = client.get(
        f"/api/v1/me/projects/{user_project_id}/graph",
        headers=auth_headers,
    )
    assert graph.status_code == 200
    body = graph.json()
    assert len(body["milestones"]) == 3


def test_coach_chat_is_saved_per_milestone_and_reopens_on_restart(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    ordered = sorted(
        enrolled["user_milestones"],
        key=lambda um: next(
            m["order_index"] for m in enrolled["milestones"] if m["id"] == um["milestone_id"]
        ),
    )
    first_um = ordered[0]["id"]
    start = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": []},
    )
    assert start.status_code == 200
    first_session = start.json()["session_id"]
    assert start.json()["user_milestone_id"] == first_um
    assert start.json()["turns"]

    again = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": []},
    )
    assert again.status_code == 200
    assert again.json()["session_id"] == first_session
    assert again.json()["resumed"] is True

    client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={"message": "I would start with the health endpoint."},
    )
    from tests.test_learning import _gate_milestone

    _gate_milestone(client, auth_headers, first_um, last=False, user_project_id=user_project_id)
    completed = client.post(
        f"/api/v1/me/milestones/{first_um}/complete",
        headers=auth_headers,
    )
    assert completed.status_code == 200

    history = client.get(
        f"/api/v1/me/milestones/{first_um}/coach",
        headers=auth_headers,
    )
    assert history.status_code == 200
    saved = history.json()
    assert saved["read_only"] is True
    assert saved["session"]["id"] == first_session
    assert saved["session"]["status"] == "completed"
    assert any("health endpoint" in turn["content"] for turn in saved["session"]["turns"])

    next_start = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": []},
    )
    assert next_start.status_code == 200
    assert next_start.json()["session_id"] != first_session
    assert next_start.json()["user_milestone_id"] == ordered[1]["id"]
    assert next_start.json()["resumed"] is False

    restarted = client.post(
        f"/api/v1/me/milestones/{first_um}/restart",
        headers=auth_headers,
    )
    assert restarted.status_code == 200
    redo = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": []},
    )
    assert redo.status_code == 200
    assert redo.json()["user_milestone_id"] == first_um
    assert redo.json()["session_id"] != first_session
    still_saved = client.get(
        f"/api/v1/me/milestones/{first_um}/coach?attempt=1",
        headers=auth_headers,
    )
    assert still_saved.status_code == 200
    assert still_saved.json()["session"]["id"] == first_session
    assert any("health endpoint" in turn["content"] for turn in still_saved.json()["session"]["turns"])
