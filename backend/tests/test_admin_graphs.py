from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
import threading
import time

from app.agents.graph_author import normalize_graph_draft
from app.agents.llm import knowledge_graph_author_prompt
from app.models.course import Course
from app.models.curriculum import Concept
from app.models.project import UserMilestone, UserMilestoneStatus
from app.seed import seed
from app.services.curriculum_authoring import GraphValidationError, publish_graph, validate_graph_payload
from app.services.practice import normalize_practice_task


def generated_graph(client: TestClient, payload: dict) -> dict:
    started = client.post("/api/v1/admin/graphs/generate", json=payload)
    assert started.status_code == 202, started.text
    job_id = started.json()["job_id"]
    from app.services import graph_jobs

    job = None
    for _ in range(50):
        fetched = client.get(f"/api/v1/admin/graphs/generate/jobs/{job_id}")
        assert fetched.status_code == 200, fetched.text
        job = fetched.json()
        if job["status"] in {"done", "error"}:
            break
        time.sleep(0.02)
    if job is None or job["status"] != "done":
        graph_jobs.run_job(job_id)
        job = client.get(f"/api/v1/admin/graphs/generate/jobs/{job_id}").json()
    assert job["status"] == "done", job
    assert job.get("graph")
    return job["graph"]


def test_normalize_maps_title_description_practice_tasks() -> None:
    task = normalize_practice_task(
        {
            "id": "callback-basic",
            "title": "Write a function that takes a callback and invokes it",
            "description": "Write a function `process` that takes a callback `cb` as a parameter.",
            "acceptance_criteria": [
                "Function accepts a callback parameter",
                "Callback is invoked (not just passed)",
            ],
        },
        "javascript",
    )
    assert task["filename"] == "practice/callback-basic.js"
    assert "process" in task["prompt"]
    assert "callback" in task["rubric"].lower()
    assert task["run"] == ["node", "practice/callback-basic.js"]

    draft = normalize_graph_draft(
        {
            "course": {"name": "Simple backend"},
            "project": {"title": "Simple backend framework"},
            "concepts": [
                {
                    "id": "javascript.functions",
                    "title": "Functions, parameters, callbacks, closures",
                    "practice_tasks": [
                        {
                            "id": "callback-basic",
                            "title": "Write a function that takes a callback and invokes it",
                            "description": "Write a function `process` that takes a callback `cb`.",
                            "acceptance_criteria": ["Function accepts a callback parameter"],
                        }
                    ],
                }
            ],
            "dependencies": [],
            "milestones": [],
        },
        slug="js-backend",
        language="javascript",
        topic="Simple backend framework",
    )
    saved = draft["concepts"][0]["practice_tasks"][0]
    assert saved["filename"] == "practice/callback-basic.js"
    assert saved["prompt"]
    assert saved["rubric"]


def test_generate_concept_fills_filename_and_prompt(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/graphs/concepts/generate",
        json={
            "slug": "js-backend",
            "language": "javascript",
            "project_title": "Simple backend framework",
            "concept": {
                "id": "js-backend.functions",
                "title": "Functions, parameters, callbacks, closures",
                "practice_tasks": [
                    {
                        "id": "callback-basic",
                        "title": "Write a function that takes a callback and invokes it",
                        "description": "Write a function `process` that takes a callback `cb`.",
                        "acceptance_criteria": ["Callback is invoked"],
                    }
                ],
            },
        },
    )
    assert response.status_code == 200, response.text
    task = response.json()["practice_tasks"][0]
    assert task["filename"] == "practice/callback-basic.js"
    assert "process" in task["prompt"]
    assert "invoked" in task["rubric"].lower()


def test_publish_persists_mapped_practice_tasks(db: Session) -> None:
    payload = {
        "course": {
            "slug": "js-mapped-tasks",
            "name": "Mapped tasks",
            "description": "LLM-shaped tasks",
            "primary_slug": "javascript",
            "primary_name": "JavaScript",
            "secondary_slug": "fundamentals",
            "secondary_name": "Fundamentals",
        },
        "project": {
            "title": "Mapped tasks",
            "description": "Admin graph",
            "objective": "Store files",
            "difficulty": "beginner",
            "expected_outcome": "Tasks have files",
            "runtime": {"language": "javascript"},
        },
        "concepts": [
            {
                "id": "js-mapped-tasks.functions",
                "title": "Functions",
                "category": "foundation",
                "description": "Callbacks",
                "hints": ["a", "b", "c", "d", "e"],
                "mastery_requirements": {"explanation": True, "implementation": True},
                "practice_tasks": [
                    {
                        "id": "callback-basic",
                        "title": "Write a function that takes a callback and invokes it",
                        "description": "Write a function `process` that takes a callback `cb`.",
                        "acceptance_criteria": ["Function accepts a callback parameter"],
                    }
                ],
            }
        ],
        "dependencies": [],
        "milestones": [
            {
                "title": "Only",
                "description": "One",
                "instructions": "Do it",
                "success_criteria": "Done",
                "concepts": ["js-mapped-tasks.functions"],
            }
        ],
    }
    graph = publish_graph(db, payload)
    db.commit()
    task = graph["concepts"][0]["practice_tasks"][0]
    assert task["filename"] == "practice/callback-basic.js"
    stored = db.get(Concept, "js-mapped-tasks.functions")
    assert stored is not None
    assert stored.practice_tasks[0]["filename"] == "practice/callback-basic.js"
    assert "process" in stored.practice_tasks[0]["prompt"]


def test_generate_preserves_go_language(client: TestClient) -> None:
    body = generated_graph(
        client, {"topic": "Go CLI notes", "language": "go", "slug": "go-cli"}
    )
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
    body = generated_graph(
        client,
        {
            "topic": "Go CLI notes",
            "language": "python",
            "slug": "go-cli",
            "audience": "beginners",
            "capstone": "a tiny notebook",
            "difficulty": "beginner",
        },
    )
    ids = [c["id"] for c in body["concepts"]]
    assert ids == ["go-cli.start", "go-cli.core", "go-cli.capstone"]
    assert body["course"]["slug"] == "go-cli"
    deps = [
        (d["concept_id"], d["requires_concept_id"], d["reason"])
        for d in body["dependencies"]
    ]
    validate_graph_payload(body["concepts"], deps, body["milestones"])


def test_generate_includes_requested_concepts(client: TestClient) -> None:
    body = generated_graph(
        client,
        {
            "topic": "Go CLI notes",
            "language": "go",
            "slug": "go-cli-includes",
            "track_kind": "language",
            "include_concepts": ["error wrapping", "flags"],
        },
    )
    titles = " ".join(c["title"].lower() for c in body["concepts"])
    assert "error wrapping" in titles
    assert "flags" in titles
    ids = [c["id"] for c in body["concepts"]]
    assert "go-cli-includes.start" in ids
    assert any("error" in cid for cid in ids)
    deps = [
        (d["concept_id"], d["requires_concept_id"], d["reason"])
        for d in body["dependencies"]
    ]
    validate_graph_payload(body["concepts"], deps, body["milestones"])


def test_generate_project_track_uses_brief(client: TestClient) -> None:
    body = generated_graph(
        client,
        {
            "topic": "Simple backend",
            "language": "javascript",
            "slug": "simple-backend-gen",
            "track_kind": "project",
            "project_brief": "tiny HTTP framework with routing and middleware",
        },
    )
    blob = json.dumps(body)
    assert "tiny HTTP framework" in blob
    assert body["course"]["secondary_slug"] == "project"


def test_normalize_injects_missing_include_concepts() -> None:
    draft = normalize_graph_draft(
        {
            "course": {"name": "HTTP"},
            "project": {"title": "Tiny server"},
            "concepts": [
                {
                    "id": "http.start",
                    "title": "Listen",
                    "description": "Accept connections.",
                }
            ],
            "dependencies": [],
            "milestones": [{"title": "Start", "concepts": ["http.start"]}],
        },
        slug="http-lab",
        language="javascript",
        track_kind="project",
        project_brief="tiny HTTP server",
        include_concepts=["middleware", "routing"],
    )
    titles = [c["title"].lower() for c in draft["concepts"]]
    assert "middleware" in titles
    assert "routing" in titles
    covered = {cid for row in draft["milestones"] for cid in row["concepts"]}
    assert {c["id"] for c in draft["concepts"]} <= covered


def test_project_prompt_covers_js_framework_shape() -> None:
    text = knowledge_graph_author_prompt(
        topic="Simple backend",
        language="javascript",
        slug="js-backend",
        track_kind="project",
        project_brief="tiny HTTP framework",
        include_concepts=["middleware", "routing"],
    )
    assert "PROJECT-BASED" in text
    assert "middleware" in text
    assert "12-22" in text


def test_publish_list_get_and_enroll(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    payload = generated_graph(
        client, {"topic": "Rust basics", "language": "python", "slug": "rust-basics"}
    )
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
    payload = generated_graph(
        client, {"topic": "Cycle", "language": "javascript", "slug": "cycle-track"}
    )
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
    payload = generated_graph(
        client, {"topic": "Missing edge", "language": "python", "slug": "missing-edge"}
    )
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
    created = client.post(
        "/api/v1/admin/graphs",
        json=generated_graph(
            client, {"topic": "Update me", "language": "python", "slug": "update-me"}
        ),
    )
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


def test_long_include_list_uses_compact_prompt() -> None:
    syllabus = [f"C# topic {index}" for index in range(12)]
    text = knowledge_graph_author_prompt(
        topic="c# from scratch",
        language="csharp",
        slug="csharp",
        track_kind="language",
        include_concepts=syllabus,
        capstone="Business Loan Banking System",
    )
    assert "compact concept" in text.lower()
    assert "C# topic 0" in text
    assert "8-16" not in text


def test_generate_job_returns_accepted_then_graph(
    client: TestClient, workspace_tmp
) -> None:
    started = client.post(
        "/api/v1/admin/graphs/generate/jobs",
        json={
            "topic": "c# from scratch",
            "language": "csharp",
            "slug": "csharp-beginner",
            "track_kind": "language",
            "include_concepts": ["C# Syntax", "C# Variables"],
        },
    )
    assert started.status_code == 202, started.text
    job_id = started.json()["job_id"]
    job = None
    for _ in range(50):
        fetched = client.get(f"/api/v1/admin/graphs/generate/jobs/{job_id}")
        assert fetched.status_code == 200, fetched.text
        job = fetched.json()
        if job["status"] in {"done", "error"}:
            break
        time.sleep(0.02)
    assert job is not None
    if job["status"] != "done":
        from app.services import graph_jobs

        graph_jobs.run_job(job_id)
        job = client.get(f"/api/v1/admin/graphs/generate/jobs/{job_id}").json()
    assert job["status"] == "done", job
    assert job["graph"]["project"]["runtime"]["language"] == "csharp"
    titles = " ".join(item["title"].lower() for item in job["graph"]["concepts"])
    assert "syntax" in titles
    assert "variables" in titles


def test_generate_returns_202_before_llm_finishes(
    client: TestClient, workspace_tmp, monkeypatch
) -> None:
    """nginx 504s if this POST waits on the model. It must return a job immediately."""
    release = threading.Event()

    def hang(**_kwargs):
        release.wait(timeout=5)
        raise RuntimeError("llm still running")

    monkeypatch.setattr("app.services.graph_jobs.generate_graph_draft", hang)
    started_at = time.perf_counter()
    response = client.post(
        "/api/v1/admin/graphs/generate",
        json={"topic": "c# from scratch", "language": "csharp", "slug": "csharp"},
    )
    elapsed = time.perf_counter() - started_at
    release.set()
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["job_id"]
    assert body["status"] in {"queued", "running"}
    assert body.get("graph") is None
    assert elapsed < 1.0, elapsed


def _concept_spec(concept_id: str, title: str) -> dict:
    return {
        "id": concept_id,
        "title": title,
        "category": "foundation",
        "description": title,
        "hints": ["a", "b", "c", "d", "e"],
        "mastery_requirements": {"explanation": True},
        "practice_tasks": [],
        "diagnostic_questions": [],
        "research_questions": [],
    }


def _milestone_spec(title: str, concepts: list[str]) -> dict:
    return {
        "title": title,
        "description": title,
        "instructions": title,
        "success_criteria": title,
        "concepts": concepts,
        "questions": [],
    }


def _track_payload(slug: str, concepts: list[dict], milestones: list[dict]) -> dict:
    return {
        "course": {
            "slug": slug,
            "name": slug,
            "description": "",
            "primary_label": "Language",
            "secondary_label": "Track",
            "primary_slug": "python",
            "primary_name": "Python",
            "secondary_slug": "fundamentals",
            "secondary_name": "Fundamentals",
        },
        "project": {
            "title": slug,
            "description": slug,
            "objective": slug,
            "difficulty": "beginner",
            "expected_outcome": slug,
            "runtime": {"language": "python"},
        },
        "concepts": concepts,
        "dependencies": [],
        "milestones": milestones,
    }


def _enroll_slug(client: TestClient, auth_headers: dict[str, str], slug: str) -> dict:
    courses = client.get("/api/v1/courses").json()
    course = next(item for item in courses if item["slug"] == slug)
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
    return enrolled.json()


def _milestone_concept_ids(graph: dict, order_index: int) -> list[str]:
    milestone = next(item for item in graph["milestones"] if item["order_index"] == order_index)
    return [item["id"] for item in milestone["concepts"]]


def test_apply_enrollments_adds_only_unstarted_work(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    slug = "apply-future-only"
    created = client.post(
        "/api/v1/admin/graphs",
        json=_track_payload(
            slug,
            [
                _concept_spec(f"{slug}.a", "A"),
                _concept_spec(f"{slug}.b", "B"),
            ],
            [
                _milestone_spec("First", [f"{slug}.a"]),
                _milestone_spec("Second", [f"{slug}.b"]),
            ],
        ),
    )
    assert created.status_code == 201, created.text
    graph = created.json()
    project_id = graph["project_id"]
    enrolled = _enroll_slug(client, auth_headers, slug)
    user_project_id = enrolled["user_project"]["id"]

    graph["concepts"].append(_concept_spec(f"{slug}.now", "Now"))
    graph["concepts"].append(_concept_spec(f"{slug}.later", "Later"))
    graph["concepts"].append(_concept_spec(f"{slug}.tail", "Tail"))
    graph["milestones"][0]["concepts"].append(f"{slug}.now")
    graph["milestones"][1]["concepts"].append(f"{slug}.later")
    graph["milestones"].append(_milestone_spec("Third", [f"{slug}.tail"]))
    updated = client.put(f"/api/v1/admin/graphs/{project_id}", json=graph)
    assert updated.status_code == 200, updated.text

    applied = client.post(f"/api/v1/admin/graphs/{project_id}/apply-enrollments")
    assert applied.status_code == 200, applied.text
    report = applied.json()
    assert report["applied"] == 1
    assert report["skipped"] == 0
    assert report["results"][0]["freeze_order"] == 1
    assert report["results"][0]["milestones_added"] == 1

    learner = client.get(
        f"/api/v1/me/projects/{user_project_id}/graph",
        headers=auth_headers,
    )
    assert learner.status_code == 200, learner.text
    body = learner.json()
    assert _milestone_concept_ids(body, 1) == [f"{slug}.a"]
    assert _milestone_concept_ids(body, 2) == [f"{slug}.b", f"{slug}.later"]
    assert _milestone_concept_ids(body, 3) == [f"{slug}.tail"]


def test_apply_enrollments_skips_finished_courses(
    client: TestClient, db: Session, auth_headers: dict[str, str]
) -> None:
    slug = "apply-finished"
    created = client.post(
        "/api/v1/admin/graphs",
        json=_track_payload(
            slug,
            [_concept_spec(f"{slug}.a", "A"), _concept_spec(f"{slug}.b", "B")],
            [
                _milestone_spec("First", [f"{slug}.a"]),
                _milestone_spec("Second", [f"{slug}.b"]),
            ],
        ),
    )
    assert created.status_code == 201, created.text
    graph = created.json()
    project_id = graph["project_id"]
    enrolled = _enroll_slug(client, auth_headers, slug)
    for item in enrolled["user_milestones"]:
        row = db.get(UserMilestone, item["id"])
        assert row is not None
        row.status = UserMilestoneStatus.completed
    db.commit()

    graph["concepts"].append(_concept_spec(f"{slug}.tail", "Tail"))
    graph["milestones"].append(_milestone_spec("Third", [f"{slug}.tail"]))
    updated = client.put(f"/api/v1/admin/graphs/{project_id}", json=graph)
    assert updated.status_code == 200, updated.text

    applied = client.post(f"/api/v1/admin/graphs/{project_id}/apply-enrollments")
    assert applied.status_code == 200, applied.text
    assert applied.json()["skipped"] == 1
    assert applied.json()["applied"] == 0

    learner = client.get(
        f"/api/v1/me/projects/{enrolled['user_project']['id']}/graph",
        headers=auth_headers,
    )
    assert learner.status_code == 200
    assert len(learner.json()["milestones"]) == 2


def test_apply_enrollments_unknown_project_is_404(client: TestClient) -> None:
    response = client.post("/api/v1/admin/graphs/999999/apply-enrollments")
    assert response.status_code == 404
