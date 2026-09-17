from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.curriculum import Concept
from app.models.learning_state import ConceptStatus
from app.seed_js_backend_framework import CONCEPTS, DEPENDENCIES
from app.seed_python_fundamentals import (
    CONCEPTS as PY_CONCEPTS,
    DEPENDENCIES as PY_DEPENDENCIES,
)
from app.services import curriculum_graph
from tests.conftest import make_course_path


def test_seed_graph_has_no_missing_or_cyclic_edges() -> None:
    ids = {spec["id"] for spec in CONCEPTS}
    for concept_id, requires, _reason in DEPENDENCIES:
        assert concept_id in ids
        assert requires in ids
        assert concept_id != requires

    # No cycles: Kahn topological sort must consume every node.
    remaining = {cid: set() for cid in ids}
    for concept_id, requires, _reason in DEPENDENCIES:
        remaining[concept_id].add(requires)
    ready = [cid for cid, deps in remaining.items() if not deps]
    seen: set[str] = set()
    while ready:
        node = ready.pop()
        seen.add(node)
        for cid, deps in remaining.items():
            if node in deps:
                deps.remove(node)
                if not deps and cid not in seen:
                    ready.append(cid)
    assert seen == ids


def test_python_seed_graph_has_no_missing_or_cyclic_edges() -> None:
    ids = {spec["id"] for spec in PY_CONCEPTS}
    for concept_id, requires, _reason in PY_DEPENDENCIES:
        assert concept_id in ids
        assert requires in ids
        assert concept_id != requires
    remaining = {cid: set() for cid in ids}
    for concept_id, requires, _reason in PY_DEPENDENCIES:
        remaining[concept_id].add(requires)
    ready = [cid for cid, deps in remaining.items() if not deps]
    seen: set[str] = set()
    while ready:
        node = ready.pop()
        seen.add(node)
        for cid, deps in remaining.items():
            if node in deps:
                deps.remove(node)
                if not deps and cid not in seen:
                    ready.append(cid)
    assert seen == ids


def _enroll_seeded(client: TestClient, auth_headers: dict[str, str], seeded_db: Session) -> dict:
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
            "learning_mode": "project",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_deterministic_start_unlocks_only_root_concepts(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
    db: Session,
) -> None:
    enrolled = _enroll_seeded(client, auth_headers, seeded_db)
    user_project_id = enrolled["user_project"]["id"]
    from app.models.project import UserProject

    user_project = db.get(UserProject, user_project_id)
    assert user_project is not None
    position = curriculum_graph.resolve_current_position(db, user_project)
    assert position["current_concept_id"] == "programming.functions"
    states = curriculum_graph.states_by_concept(db, user_project.id)
    assert states["programming.functions"].status == ConceptStatus.available
    assert states["middleware.pipeline"].status == ConceptStatus.locked
    graph = client.get(
        f"/api/v1/me/projects/{user_project_id}/graph",
        headers=auth_headers,
    )
    assert graph.status_code == 200, graph.text
    body = graph.json()
    assert body["current_progress"]["total"] >= 1
    assert 0 <= body["current_progress"]["percent"] <= 100
    assert body["track_progress"]["total"] >= body["current_progress"]["total"]
    first = body["milestones"][0]["concepts"][0]
    assert "progress" in first
    assert "percent" in first["progress"]


def test_cannot_master_without_evidence(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
    db: Session,
) -> None:
    enrolled = _enroll_seeded(client, auth_headers, seeded_db)
    from app.models.project import UserProject

    user_project = db.get(UserProject, enrolled["user_project"]["id"])
    assert user_project is not None
    row = curriculum_graph.try_master(db, user_project, "programming.functions")
    assert row.status != ConceptStatus.mastered
    curriculum_graph.record_evidence(db, user_project, "programming.functions", explanation=True)
    concept = db.get(Concept, "programming.functions")
    row = curriculum_graph.get_or_create_state(db, user_project, "programming.functions")
    curriculum_graph.mark_required_questions_answered(
        row,
        concept,
        answer="A callback is a function passed as data so another function can invoke it later.",
    )
    row = curriculum_graph.try_master(db, user_project, "programming.functions")
    assert row.status == ConceptStatus.mastered
    assert "programming.objects" in curriculum_graph.apply_unlocks(db, user_project) or (
        curriculum_graph.states_by_concept(db, user_project.id)["programming.objects"].status
        == ConceptStatus.available
    )


def test_skip_diagnostic_verifies_not_masters(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
) -> None:
    enrolled = _enroll_seeded(client, auth_headers, seeded_db)
    user_project_id = enrolled["user_project"]["id"]
    response = client.post(
        f"/api/v1/me/projects/{user_project_id}/concepts/programming.functions/skip-diagnostic",
        headers=auth_headers,
        json={
            "answers": [
                "A callback is a function passed as a value and invoked later by the receiver.",
                "The inner function still sees the outer variable because a closure captures it.",
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["status"] == "verified"


def test_suspect_gaps_ranks_unmet_prerequisites(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
    db: Session,
) -> None:
    enrolled = _enroll_seeded(client, auth_headers, seeded_db)
    from app.models.project import UserProject

    user_project = db.get(UserProject, enrolled["user_project"]["id"])
    assert user_project is not None
    suspects = curriculum_graph.suspect_gaps(db, user_project, "http.parsing")
    ids = [item["concept"] for item in suspects]
    assert "http.raw_request" in ids
    assert suspects[0]["confidence"] >= suspects[-1]["confidence"]


def test_explanation_walks_a_concept_to_mastered(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_db: Session,
) -> None:
    enrolled = _enroll_seeded(client, auth_headers, seeded_db)
    user_project_id = enrolled["user_project"]["id"]
    response = client.post(
        f"/api/v1/me/projects/{user_project_id}/concepts/programming.functions/explain",
        headers=auth_headers,
        json={
            "answer": (
                "A callback is a function passed as data so another function can call it later. "
                "A closure captures variables from the enclosing scope so the inner function "
                "can still read them after the outer function has returned."
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["status"] == "mastered"
    assert body["evidence"]["explanation"] is True


def test_match_required_question_ignores_backticks() -> None:
    question = "What does the caller get if there is no `return`?"
    blob = (
        "We're still on 'Functions'. Next question:\n\n"
        "What does the caller get if there is no return?"
    )
    assert curriculum_graph.match_required_question([question], blob) == question
    assert (
        curriculum_graph.resolve_open_question(
            [question],
            last_tutor="The caller actually receives None, not nothing.",
            evidence={"open_question": question},
        )
        == question
    )


def test_concept_progress_counts_questions_and_practice() -> None:
    from types import SimpleNamespace

    concept = SimpleNamespace(
        diagnostic_questions=["Q1", "Q2"],
        research_questions=["R1"],
        practice_tasks=[{"id": "t1", "filename": "practice/t1.py", "prompt": "Write t1"}],
    )
    row = SimpleNamespace(
        evidence={"answered_questions": ["Q1"], "practice_task_ids": []},
        verified_via_skip=False,
        diagnostic_answers=[],
    )
    progress = curriculum_graph.concept_progress(concept, row, language="python")
    assert progress["questions_total"] == 3
    assert progress["questions_done"] == 1
    assert progress["practice_total"] == 1
    assert progress["practice_done"] == 0
    assert progress["done"] == 1
    assert progress["total"] == 4
    assert progress["percent"] == 25
