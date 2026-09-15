from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.learning_state import ConceptStatus
from app.seed_js_backend_framework import CONCEPTS, DEPENDENCIES
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
