from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.course import Course
from app.seed import seed
from app.services.curriculum_authoring import GraphValidationError, publish_graph, validate_graph_payload


def test_generate_preserves_go_language(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/graphs/generate",
        json={"topic": "Go CLI notes", "language": "go", "slug": "go-cli"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project"]["runtime"]["language"] == "go"
    assert body["course"]["primary_name"] == "Go"
    filenames = [
        str(task.get("filename") or "")
        for concept in body["concepts"]
        for task in concept.get("practice_tasks") or []
    ]
    assert any(name.endswith(".go") for name in filenames)


def test_admin_lists_extended_languages(client: TestClient) -> None:
    response = client.get("/api/v1/admin/languages")
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert slugs >= {"python", "javascript", "typescript", "go", "csharp", "c"}


def test_generate_returns_namespaced_acyclic_draft(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/graphs/generate",
        json={
            "topic": "Go CLI notes",
            "language": "python",
            "slug": "go-cli",
            "audience": "beginners",
            "capstone": "a tiny notebook",
            "difficulty": "beginner",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [c["id"] for c in body["concepts"]]
    assert ids == ["go-cli.start", "go-cli.core", "go-cli.capstone"]
    assert body["course"]["slug"] == "go-cli"
    deps = [
        (d["concept_id"], d["requires_concept_id"], d["reason"])
        for d in body["dependencies"]
    ]
    validate_graph_payload(body["concepts"], deps, body["milestones"])


def test_publish_list_get_and_enroll(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    generated = client.post(
        "/api/v1/admin/graphs/generate",
        json={"topic": "Rust basics", "language": "python", "slug": "rust-basics"},
    )
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    created = client.post("/api/v1/admin/graphs", json=payload)
    assert created.status_code == 201, created.text
    graph = created.json()
    project_id = graph["project_id"]
    assert graph["course"]["slug"] == "rust-basics"
    assert len(graph["concepts"]) == 3
    assert len(graph["dependencies"]) == 2

    listed = client.get("/api/v1/admin/graphs")
    assert listed.status_code == 200
    assert any(item["project_id"] == project_id for item in listed.json())

    fetched = client.get(f"/api/v1/admin/graphs/{project_id}")
    assert fetched.status_code == 200
    assert {c["id"] for c in fetched.json()["concepts"]} == {
        "rust-basics.start",
        "rust-basics.core",
        "rust-basics.capstone",
    }

    courses = client.get("/api/v1/courses").json()
    course = next(c for c in courses if c["slug"] == "rust-basics")
    primary = client.get(f"/api/v1/courses/{course['id']}/options").json()[0]
    secondary = client.get(
        f"/api/v1/courses/{course['id']}/options/{primary['id']}/options"
    ).json()[0]
    enrolled = client.post(
        "/api/v1/enrollments",
        headers=auth_headers,
        json={
            "course_id": course["id"],
            "primary_option_id": primary["id"],
            "secondary_option_id": secondary["id"],
            "learning_mode": "project",
        },
    )
    assert enrolled.status_code == 201, enrolled.text
    detail = enrolled.json()
    assert len(detail["user_milestones"]) == 3
    learner_graph = client.get(
        f"/api/v1/me/projects/{detail['user_project']['id']}/graph",
        headers=auth_headers,
    )
    assert learner_graph.status_code == 200
    assert learner_graph.json()["milestones"]


def test_cycle_is_rejected(client: TestClient) -> None:
    generated = client.post(
        "/api/v1/admin/graphs/generate",
        json={"topic": "Cycle", "language": "javascript", "slug": "cycle-track"},
    )
    payload = generated.json()
    ids = [c["id"] for c in payload["concepts"]]
    payload["dependencies"] = [
        {
            "concept_id": ids[0],
            "requires_concept_id": ids[1],
            "reason": "loop",
        },
        {
            "concept_id": ids[1],
            "requires_concept_id": ids[0],
            "reason": "loop",
        },
    ]
    response = client.post("/api/v1/admin/graphs", json=payload)
    assert response.status_code == 400
    assert "cycle" in str(response.json()["detail"]).lower()


def test_unknown_prerequisite_is_rejected(client: TestClient) -> None:
    generated = client.post(
        "/api/v1/admin/graphs/generate",
        json={"topic": "Missing edge", "language": "python", "slug": "missing-edge"},
    )
    payload = generated.json()
    payload["dependencies"].append(
        {
            "concept_id": payload["concepts"][0]["id"],
            "requires_concept_id": "missing-edge.does-not-exist",
            "reason": "ghost",
        }
    )
    response = client.post("/api/v1/admin/graphs", json=payload)
    assert response.status_code == 400
    assert "unknown" in str(response.json()["detail"]).lower()


def test_seed_does_not_delete_admin_course(db: Session) -> None:
    payload = {
        "course": {
            "slug": "admin-keep",
            "name": "Admin Keep",
            "description": "Should survive seed",
            "primary_slug": "python",
            "primary_name": "Python",
            "secondary_slug": "fundamentals",
            "secondary_name": "Fundamentals",
        },
        "project": {
            "title": "Keep Me",
            "description": "Admin graph",
            "objective": "Stay",
            "difficulty": "beginner",
            "expected_outcome": "Still here",
            "runtime": {"language": "python"},
        },
        "concepts": [
            {
                "id": "admin-keep.start",
                "title": "Start",
                "category": "foundation",
                "description": "First node",
                "hints": ["a", "b", "c", "d", "e"],
                "mastery_requirements": {"explanation": True},
            },
            {
                "id": "admin-keep.core",
                "title": "Core",
                "category": "core",
                "description": "Second node",
                "hints": ["a", "b", "c", "d", "e"],
                "mastery_requirements": {"explanation": True},
            },
        ],
        "dependencies": [
            {
                "concept_id": "admin-keep.core",
                "requires_concept_id": "admin-keep.start",
                "reason": "order",
            }
        ],
        "milestones": [
            {
                "title": "Only",
                "description": "Both",
                "instructions": "Do it",
                "success_criteria": "Done",
                "concepts": ["admin-keep.start", "admin-keep.core"],
            }
        ],
    }
    publish_graph(db, payload)
    db.commit()
    seed(db)
    kept = db.query(Course).filter(Course.slug == "admin-keep").first()
    assert kept is not None
    python = db.query(Course).filter(Course.slug == "python").first()
    assert python is not None


def test_update_graph_changes_title(client: TestClient) -> None:
    generated = client.post(
        "/api/v1/admin/graphs/generate",
        json={"topic": "Update me", "language": "python", "slug": "update-me"},
    )
    created = client.post("/api/v1/admin/graphs", json=generated.json())
    payload = created.json()
    payload["project"]["title"] = "Updated title"
    payload["concepts"][0]["title"] = "Renamed start"
    response = client.put(f"/api/v1/admin/graphs/{payload['project_id']}", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project"]["title"] == "Updated title"
    assert body["concepts"][0]["title"] == "Renamed start"


def test_generate_concept_keeps_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/graphs/concepts/generate",
        json={
            "slug": "go-cli",
            "language": "python",
            "project_title": "Learn Go CLI",
            "concept": {
                "id": "go-cli.core",
                "title": "Core idea",
                "category": "core",
                "description": "",
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == "go-cli.core"
    assert body["title"] == "Core idea"
    assert len(body["hints"]) == 5


def test_validate_rejects_self_edge() -> None:
    try:
        validate_graph_payload(
            [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}],
            [("a", "a", "loop")],
            [{"title": "M", "concepts": ["a"]}],
        )
    except GraphValidationError as exc:
        assert any("itself" in err for err in exc.errors)
    else:
        raise AssertionError("expected GraphValidationError")
