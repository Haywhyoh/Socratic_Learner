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
