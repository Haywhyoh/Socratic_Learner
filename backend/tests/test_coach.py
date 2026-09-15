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


def _activate(client: TestClient, auth_headers: dict[str, str], user_project_id: int) -> dict:
    start = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={
            "answers": [
                {"concept": "scaffold", "mastery": "unknown"},
                {"concept": "crud", "mastery": "unknown"},
                {"concept": "auth", "mastery": "unknown"},
            ]
        },
    )
    assert start.status_code == 200
    return start.json()


def _sentence_count(text: str) -> int:
    parts = [p for p in __import__("re").split(r"(?<=[.!?])\s+", text.strip()) if p]
    return len(parts)


def test_coach_start_poses_first_question(
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
    assert body["status"] == "needs_assessment"
    concepts = [q["concept"] for q in body["assessment_questions"]]
    assert "scaffold" in concepts
    answers = [{"concept": name, "mastery": "unknown"} for name in concepts]
    answers[0]["mastery"] = "can_explain"
    second = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/start",
        headers=auth_headers,
        json={"answers": answers},
    )
    assert second.status_code == 200
    ready = second.json()
    assert ready["status"] == "active"
    assert len(ready["roadmap"]) == 3
    assert ready["current_question"]
    assert "goal of Scaffold" in ready["reply"]
    assert ready["cards"] == []
    assert _sentence_count(ready["reply"]) <= 2

    skipped = ready["roadmap"][0]["concepts"][0]
    assert skipped["teaching"] == "skip"
    assert skipped["name"] == "scaffold"

    milestone_id = enrolled["user_milestones"][0]["id"]
    cards = client.get(
        f"/api/v1/me/milestones/{milestone_id}/cards",
        headers=auth_headers,
    )
    assert cards.status_code == 200
    assert skipped["name"] not in {c["name"] for c in cards.json()}


def test_question_flow_pass_push_back_and_go_build(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    ready = _activate(client, auth_headers, user_project_id)
    q1 = ready["current_question"]
    assert q1

    push = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={"message": "idk"},
    )
    assert push.status_code == 200
    body = push.json()
    assert body["answer_status"] == "push_back"
    assert body["push_back"]
    assert _sentence_count(body["reply"]) <= 2
    assert body["learner_state"]["question_index"] == 0
    assert body["learner_state"]["failed_at"]

    pass1 = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={
            "message": (
                "The goal is to stand up a runnable API skeleton with a health check "
                "so we can verify the service boots."
            )
        },
    )
    assert pass1.status_code == 200
    body = pass1.json()
    assert body["answer_status"] == "passed"
    assert body["learner_state"]["question_index"] == 1
    assert body["current_question"]
    assert body["current_question"] != q1

    pass2 = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={
            "message": (
                "I will verify by curling GET /health and confirming a 200 JSON status body."
            )
        },
    )
    assert pass2.status_code == 200
    body = pass2.json()
    assert body["answer_status"] == "passed"
    assert body["learner_state"]["questions_complete"] is True
    assert "Go build" in body["reply"]
    assert "first task" in body["reply"].lower()
    assert _sentence_count(body["reply"]) <= 6


def test_question_retry_cap_advances_with_noted_gap(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    """After MAX_QUESTION_ATTEMPTS failed answers, the coach stops rephrasing

    the same question and moves the learner on, noting the gap instead.
    """
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    ready = _activate(client, auth_headers, user_project_id)
    q1 = ready["current_question"]
    assert q1

    for _ in range(2):
        resp = client.post(
            f"/api/v1/me/projects/{user_project_id}/coach/message",
            headers=auth_headers,
            json={"message": "idk"},
        )
        assert resp.status_code == 200
        assert resp.json()["answer_status"] == "push_back"

    capped = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={"message": "idk"},
    )
    assert capped.status_code == 200
    body = capped.json()
    assert body["answer_status"] == "advanced_with_gap"
    assert body["learner_state"]["question_index"] == 1
    assert body["learner_state"]["question_attempts"] == 0
    assert body["current_question"] != q1


def test_learner_state_endpoint_and_hint_does_not_skip(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
) -> None:
    enrolled = _enroll(client, auth_headers, db)
    user_project_id = enrolled["user_project"]["id"]
    ready = _activate(client, auth_headers, user_project_id)
    assert ready["learner_state"]["question_index"] == 0

    state = client.get(
        f"/api/v1/me/projects/{user_project_id}/state",
        headers=auth_headers,
    )
    assert state.status_code == 200
    payload = state.json()
    assert payload["question_index"] == 0
    assert payload["questions_total"] == 2
    assert payload["current_question"]

    milestone_id = enrolled["user_milestones"][0]["id"]
    first_hint = client.post(
        f"/api/v1/me/milestones/{milestone_id}/hints",
        headers=auth_headers,
    )
    assert first_hint.status_code == 200
    assert first_hint.json()["hint_level"] == 0
    assert first_hint.json()["learner_state"]["question_index"] == 0
    assert _sentence_count(first_hint.json()["reply"]) <= 2

    second_hint = client.post(
        f"/api/v1/me/milestones/{milestone_id}/hints",
        headers=auth_headers,
    )
    assert second_hint.status_code == 200
    assert second_hint.json()["hint_blocked_reason"] == "need_effort"
    assert second_hint.json()["learner_state"]["question_index"] == 0

    effort = client.post(
        f"/api/v1/me/projects/{user_project_id}/coach/message",
        headers=auth_headers,
        json={
            "message": (
                "I tried scaffolding a FastAPI app, added GET /health, and it failed "
                "on import. My approach was a single main module. The error is ModuleNotFound."
            )
        },
    )
    assert effort.status_code == 200
    # Effort answer may pass the current question; that advances index by answering, not by hint.
    assert effort.json()["answer_status"] in {"passed", "push_back"}
    index_after = effort.json()["learner_state"]["question_index"]

    third_hint = client.post(
        f"/api/v1/me/milestones/{milestone_id}/hints",
        headers=auth_headers,
    )
    assert third_hint.status_code == 200
    assert third_hint.json()["hint_level"] == 1
    assert third_hint.json()["learner_state"]["question_index"] == index_after
