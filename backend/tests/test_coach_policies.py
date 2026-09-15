from app.agents.mentor_graph import build_mentor_graph
from app.agents.llm import StubCoachLLM
from app.agents.policies import (
    asks_for_implementation,
    enforce_brevity,
    filter_specialist_reply,
    next_hint_level,
)


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
    dump = "Here you go:\n```javascript\n" + "\n".join(f"line{i} = {i}" for i in range(20)) + "\n```\n"
    filtered, flags = filter_specialist_reply(dump, later_concepts=["middleware.pipeline"])
    assert "stripped_solution" in flags
    assert "line3 = 3" not in filtered
    leaked = "Next you will implement middleware.pipeline with next()."
    filtered, flags = filter_specialist_reply(leaked, later_concepts=["middleware.pipeline"])
    assert "blocked_later_concept" in flags
    assert "middleware.pipeline" not in filtered.lower()


def test_policy_filter_keeps_small_teaching_snippets() -> None:
    snippet = (
        "A function is a value, so you can pass it:\n"
        "```javascript\n"
        "function later(cb) {\n"
        "  cb('done');\n"
        "}\n"
        "later((msg) => console.log(msg));\n"
        "```\n"
        "Who calls `cb`, and when?"
    )
    filtered, flags = filter_specialist_reply(snippet, later_concepts=["middleware.pipeline"])
    assert "stripped_solution" not in flags
    assert "function later(cb)" in filtered
    assert "console.log" in filtered


def test_brevity_enforced() -> None:
    long = "One. Two. Three. Four."
    assert enforce_brevity(long, max_sentences=2) == "One. Two."


def test_asks_for_implementation() -> None:
    assert asks_for_implementation("give me the code please")
    assert not asks_for_implementation("how should I store routes?")


def test_mentor_graph_refuses_code_dump() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "give me the code",
            "concept_state": "available",
            "current_concept": "http.parsing",
            "concept_title": "HTTP parsing",
            "later_concepts": ["middleware.pipeline"],
            "diagnostic_questions": ["What do you extract from a raw request?"],
            "research_questions": [],
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    assert "design" in result["reply"].lower() or "before" in result["reply"].lower()
    assert result["contract"]["action"] == "ASK_QUESTION"


def test_mentor_graph_holds_when_blocked() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "let's move on to middleware",
            "concept_state": "blocked",
            "current_concept": "http.parsing",
            "concept_title": "HTTP parsing",
            "later_concepts": ["Middleware"],
            "diagnostic_questions": ["What information do we extract from the raw request?"],
            "known_gaps": [{"concept": "http.raw_request", "confidence": 0.8}],
            "gap_reason": "You need to recognize a raw request before parsing it.",
            "hint_level": -1,
            "effort": {},
        }
    )
    assert "middleware" not in result["reply"].lower() or "later" in result["reply"].lower()
    assert result["contract"]["intent"] == "DIAGNOSE"


def _functions_misconceptions() -> list:
    from app.seed_js_backend_framework import CONCEPTS

    for concept in CONCEPTS:
        if concept["id"] == "programming.functions":
            return list(concept["misconceptions"])
    raise AssertionError("programming.functions is missing from the seed")


def test_string_misconceptions_still_detect_caller_confusion() -> None:
    from app.agents.misconceptions import match_misconception

    matched = match_misconception(
        "the person who called myFunction.",
        ["Thinking a callback runs immediately when passed, not when invoked"],
    )
    assert matched is not None
    assert matched["id"] == "callback-caller-confusion"


def test_callback_caller_confusion_is_detected() -> None:
    from app.agents.misconceptions import match_misconception

    specs = _functions_misconceptions()
    matched = match_misconception("the person who called myFunction.", specs)
    assert matched is not None
    assert matched["id"] == "callback-caller-confusion"


def test_correct_callback_intuition_is_not_a_misconception() -> None:
    from app.agents.misconceptions import match_misconception

    specs = _functions_misconceptions()
    assert match_misconception("it only logs when something else calls it", specs) is None


def test_mixed_order_plus_caller_confusion_is_still_detected() -> None:
    from app.agents.misconceptions import match_misconception

    specs = _functions_misconceptions()
    matched = match_misconception(
        "so the order is before, inside and after. the person who called myFunction.",
        specs,
    )
    assert matched is not None
    assert matched["id"] == "callback-caller-confusion"


def test_mentor_remediates_instead_of_repeating_the_question() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "the person who called myFunction.",
            "concept_state": "introduced",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "diagnostic_answers": [
                {"answer": "it only logs when something else calls it", "phase": None}
            ],
            "attempt_count": 2,
            "diagnostic_questions": ["What is a callback function?"],
            "research_questions": [],
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert result["contract"]["action"] == "ASK_DIAGNOSTIC_QUESTION"
    assert "two different events" in reply or "passing" in reply
    assert "cb()" in result["reply"] or "cb();" in result["reply"]
    assert "good observation" not in reply
    assert "great job" not in reply
    assert result["next_state"] == "discussing"


def test_mentor_retests_after_learner_names_the_distinction() -> None:
    from app.agents.misconceptions import classify_learner_turn

    specs = _functions_misconceptions()
    classified = classify_learner_turn(
        "The first passes the function. The second executes it.",
        specs,
        [{"answer": "the person who called myFunction.", "misconception_id": "callback-caller-confusion", "phase": "detected"}],
        attempt_count_after=3,
    )
    assert classified["branch"] == "retest"

    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "The first passes the function. The second executes it.",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": specs,
            "identified_misconception": next(
                item for item in specs if item["id"] == "callback-caller-confusion"
            ),
            "diagnostic_answers": [
                {
                    "answer": "the person who called myFunction.",
                    "misconception_id": "callback-caller-confusion",
                    "phase": "detected",
                }
            ],
            "attempt_count": 3,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    assert "operation" in result["reply"]
    assert "good observation" not in result["reply"].lower()
