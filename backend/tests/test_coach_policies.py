from app.agents.graph import build_chat_graph, build_start_graph
from app.agents.llm import StubCoachLLM
from app.agents.policies import (
    build_roadmap,
    current_teach_concepts,
    enforce_brevity,
    filter_specialist_reply,
    next_hint_level,
)
from app.agents.state import CardDraft, CatalogMilestone


CATALOG: list[CatalogMilestone] = [
    {
        "id": 1,
        "title": "Scaffold",
        "order_index": 1,
        "concepts": ["layout", "health"],
        "questions": [
            "What does a health endpoint return?",
            "Where should config live?",
        ],
        "success_criteria": "health works",
        "description": "scaffold",
    },
    {
        "id": 2,
        "title": "CRUD",
        "order_index": 2,
        "concepts": ["persistence"],
        "questions": ["Why use a database?"],
        "success_criteria": "crud works",
        "description": "crud",
    },
    {
        "id": 3,
        "title": "Auth",
        "order_index": 3,
        "concepts": ["ownership isolation"],
        "questions": ["Who owns a task?"],
        "success_criteria": "auth works",
        "description": "auth",
    },
]


def test_planner_cannot_invent_milestones() -> None:
    profile = {"layout": "unknown", "health": "unknown", "persistence": "unknown"}
    roadmap = build_roadmap(CATALOG, profile)
    assert [row["milestone_id"] for row in roadmap] == [1, 2, 3]
    assert {c["name"] for row in roadmap for c in row["concepts"]} <= {
        "layout",
        "health",
        "persistence",
        "ownership isolation",
    }


def test_cards_only_for_current_unknown_concepts() -> None:
    profile = {"layout": "can_explain", "health": "unknown", "persistence": "unknown"}
    roadmap = build_roadmap(CATALOG, profile)
    names = current_teach_concepts(roadmap, milestone_id=1, knowledge_profile=profile)
    assert names == ["health"]
    assert "persistence" not in names
    assert "layout" not in names


def test_hint_levels_cannot_skip_without_effort() -> None:
    level, reason = next_hint_level(-1, {})
    assert level == 0
    assert reason is None
    level, reason = next_hint_level(0, {"learner_turns_since_hint": 0, "attempt_message": False})
    assert level == 0
    assert reason == "need_effort"
    level, reason = next_hint_level(
        0,
        {"learner_turns_since_hint": 1, "attempt_message": False, "checkpoint_since_hint": False},
    )
    assert level == 1
    assert reason is None
    level, reason = next_hint_level(3, {"attempt_message": True})
    assert level == 4


def test_policy_filter_strips_full_solutions_and_later_concepts() -> None:
    dump = "Here you go:\n```python\n" + "\n".join(f"line{i} = {i}" for i in range(10)) + "\n```\n"
    filtered, flags = filter_specialist_reply(dump, later_concepts=["ownership isolation"])
    assert "stripped_solution" in flags
    assert "line3 = 3" not in filtered
    leaked = "Next you will implement ownership isolation with JWT."
    filtered, flags = filter_specialist_reply(leaked, later_concepts=["ownership isolation"])
    assert "blocked_later_concept" in flags
    assert "ownership isolation" not in filtered.lower()


def test_policy_keeps_beginner_instructions_when_trimming_dump() -> None:
    reply = (
        "First create the package.\n"
        "mkdir -p scaffold\n"
        "touch scaffold/main.py\n"
        "Then add /health yourself.\n"
        "```python\n"
        + "\n".join(
            [
                "from fastapi import FastAPI, Depends, HTTPException",
                "from sqlalchemy import create_engine",
                "app = FastAPI()",
                "@app.get('/items')",
                "def list_items():",
                "    return []",
                "@app.post('/items')",
                "def create_item():",
                "    return {}",
                "@app.delete('/items/{id}')",
                "def delete_item():",
                "    return {}",
                "class Item:",
                "    pass",
                "engine = create_engine('sqlite://')",
                "def get_db():",
                "    pass",
            ]
        )
        + "\n```\n"
        "After that run uvicorn."
    )
    filtered, flags = filter_specialist_reply(
        reply,
        later_concepts=[],
        allow_commands=True,
        max_sentences=12,
    )
    assert "stripped_solution" in flags
    assert "mkdir -p scaffold" in filtered
    assert "First create the package" in filtered
    assert "No full app dumps" not in filtered
    assert "create_engine" not in filtered
    assert "fastapi.tiangolo.com" in filtered.lower() or "yourself" in filtered.lower()


def test_enforce_single_build_step_cuts_later_sections() -> None:
    from app.agents.build_coach import enforce_single_build_step

    dumped = (
        "Step 1 of 4: create folders\n"
        "mkdir -p app\n"
        "## Step 2: Add dependencies\n"
        "paste a whole pyproject\n"
        "## Step 3: health\n"
        "more stuff\n"
    )
    clipped = enforce_single_build_step(dumped)
    assert "mkdir -p app" in clipped
    assert "Step 2" not in clipped
    assert "done" in clipped.lower()


def test_build_step_advances_on_done() -> None:
    from app.agents.build_coach import detect_build_step_advance

    assert detect_build_step_advance("done")
    assert detect_build_step_advance("I created the folders, what's next?")
    assert not detect_build_step_advance("how do i create the folders?")
    assert not detect_build_step_advance("I finished the checkpoints. What is the first build step?")


def test_brevity_enforced() -> None:
    long = "One. Two. Three. Four."
    assert enforce_brevity(long, max_sentences=2) == "One. Two."


def test_start_graph_poses_first_question() -> None:
    graph = build_start_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "catalog_milestones": CATALOG,
            "milestone_id": 1,
            "milestone_title": "Scaffold",
            "milestone_questions": CATALOG[0]["questions"],
            "question_index": 0,
            "constraints": ["No frontend"],
            "success_criteria": "health works",
            "assessment_answers": {"layout": "can_explain", "health": "unknown"},
            "resources": [{"title": "Docs", "url": "https://example.com"}],
        }
    )
    assert result["status"] == "active"
    assert [row["milestone_id"] for row in result["roadmap"]] == [1, 2, 3]
    names = [card["name"] for card in result["cards"]]
    assert names == ["health"]
    card: CardDraft = result["cards"][0]
    assert card["why_it_matters"]
    assert result["reply"] == "What does a health endpoint return?"
    assert result["current_question"] == result["reply"]


def test_evaluate_pass_then_push_back_then_go_build() -> None:
    graph = build_chat_graph(StubCoachLLM())
    questions = CATALOG[0]["questions"]
    first = graph.invoke(
        {
            "learner_message": "A health endpoint should return a JSON status like ok.",
            "milestone_title": "Scaffold",
            "constraints": ["No frontend"],
            "success_criteria": "GET /health returns 200",
            "milestone_questions": questions,
            "question_index": 0,
            "questions_passed": 0,
            "current_concepts": ["health"],
            "hint_level": -1,
            "effort": {},
            "cards": [],
        }
    )
    assert first["answer_status"] == "passed"
    assert first["question_index"] == 1
    assert first["reply"] == questions[1]

    push = graph.invoke(
        {
            "learner_message": "no",
            "milestone_title": "Scaffold",
            "constraints": ["No frontend"],
            "success_criteria": "GET /health returns 200",
            "milestone_questions": questions,
            "question_index": 1,
            "questions_passed": 1,
            "current_concepts": ["health"],
            "hint_level": -1,
            "effort": {},
            "cards": [],
        }
    )
    assert push["answer_status"] == "push_back"
    assert push["question_index"] is None or push.get("question_index") == 1 or "question_index" not in push
    assert len(push["reply"].split(".")) <= 2

    done = graph.invoke(
        {
            "learner_message": "Config belongs in settings so secrets are not hard-coded.",
            "milestone_title": "Scaffold",
            "constraints": ["No frontend"],
            "success_criteria": "GET /health returns 200",
            "milestone_questions": questions,
            "question_index": 1,
            "questions_passed": 1,
            "current_concepts": ["health"],
            "hint_level": -1,
            "effort": {},
            "cards": [],
        }
    )
    assert done["answer_status"] == "passed"
    assert done["questions_complete"] is True
    assert "Step 1" in done["reply"] or "step 1" in done["reply"].lower()
    assert "Step 2" not in done["reply"]


def test_guidance_intent_for_layout_question() -> None:
    from app.agents.policies import classify_intent, guidance_reply, parse_instruction_tasks

    assert classify_intent("how do i create a clean layout for this project") == "guidance"
    assert classify_intent("I am stuck — please give me a hint") == "hint"
    instructions = (
        "What to do:\n"
        "1. Create a clean project layout (app package, settings, entrypoint).\n"
        "2. Add a GET /health endpoint.\n"
    )
    assert len(parse_instruction_tasks(instructions)) == 2
    reply = guidance_reply(
        message="what command do i need to scaffold the fastapi project named scaffold",
        milestone_title="Scaffold the API",
        instructions=instructions,
        constraints=["No frontend UI"],
        success_criteria="GET /health returns 200",
    )
    assert "mkdir" in reply.lower()
    assert "scaffold" in reply.lower()
    assert "first thing" in reply.lower() or "mkdir -p" in reply.lower()
    assert "clean layout usually means" not in reply.lower()
    assert "No full app dumps" not in reply

    graph = build_chat_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "what command creates the fastapi package scaffold",
            "project_title": "Task Tracker API",
            "milestone_title": "Scaffold the API",
            "milestone_instructions": instructions,
            "constraints": ["No frontend UI"],
            "success_criteria": "GET /health returns 200",
            "milestone_questions": [],
            "question_index": 0,
            "questions_passed": 0,
            "current_concepts": ["layout"],
            "hint_level": -1,
            "effort": {},
            "cards": [],
        }
    )
    assert result["answer_status"] == "guidance"
    assert "mkdir" in result["reply"].lower()
    assert "```python" not in result["reply"]
