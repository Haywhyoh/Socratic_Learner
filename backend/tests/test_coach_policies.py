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


def test_execution_trace_is_callback_progress_not_a_full_exam() -> None:
    from app.agents.misconceptions import answer_resolves_misconception

    specs = _functions_misconceptions()
    callback = next(item for item in specs if item["id"] == "callback-caller-confusion")
    trace = (
        "the myFunction logs before, then calls cb the callback function. "
        "cb then logs inside then it logs after"
    )
    assert answer_resolves_misconception(trace, callback)

    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": trace,
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": specs,
            "learning_objectives": [
                "Explain what a callback is and why it lets code run 'later'",
                "Explain, in your own words, what a closure captures and why",
            ],
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
    reply = result["reply"].lower()
    assert "closure captures" not in reply
    assert "no explanation" not in reply
    assert "operation" in result["reply"] or "cb()" in result["reply"]


def test_mentor_explains_when_learner_asks() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "can you explain it",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": [
                "Explain what a callback is and why it lets code run 'later'",
                "Explain, in your own words, what a closure captures and why",
            ],
            "diagnostic_answers": [
                {
                    "answer": "the person who called myFunction.",
                    "misconception_id": "callback-caller-confusion",
                    "phase": "detected",
                }
            ],
            "attempt_count": 4,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "no explanation" not in reply
    assert "asked a question" not in reply
    assert "later" in reply
    assert "cb()" in result["reply"] or "cb();" in result["reply"]


def test_what_next_does_not_regrade_the_learner() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "so what next",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": [
                "Explain what a callback is and why it lets code run 'later'",
                "Explain, in your own words, what a closure captures and why",
            ],
            "next_concept_title": "Objects, properties, methods, references",
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "no explanation" not in reply
    assert "does not address" not in reply
    assert "closure" in reply or "next concept" in reply or "missing" in reply or "pass" in reply


def test_correct_closure_answer_is_not_callback_remediation() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "it print n = 2",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": [
                "Explain what a callback is and why it lets code run 'later'",
                "Explain, in your own words, what a closure captures and why",
            ],
            "last_tutor_message": (
                "The callback model is solid. Stay on this concept for one more piece: closures.\n"
                "If let n = 1 and an inner function reads n, then later n = 2, "
                "what does the inner function print when you call it?"
            ),
            "next_concept_title": "Objects, properties, methods, references",
            "attempt_count": 6,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "two different events" not in reply
    assert "later(()" not in result["reply"]
    assert "2" in result["reply"]
    assert "live" in reply or "link" in reply


def test_partial_pass_answer_asks_for_invoke_not_the_same_drill() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    drill = (
        "I think we've found the part that's unclear.\n\n"
        "Passing a function and calling a function are two different events.\n\n"
        "Two separate answers, please:\n"
        "1. Which line *passes* the function?\n"
        "2. Which exact line *invokes* it?"
    )
    result = graph.invoke(
        {
            "learner_message": "the line later(() => console.log('inside')) passes the function",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "misconceptions": _functions_misconceptions(),
            "last_tutor_message": drill,
            "diagnostic_answers": [
                {"answer": "it print n = 2", "misconception_id": "callback-runs-when-passed", "phase": "stuck"}
            ],
            "attempt_count": 7,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "invokes" in reply
    assert reply.count("two different events") == 0
    assert "yes" in reply


def test_naming_both_pass_and_invoke_does_not_repeat_the_drill() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": (
                "passing a function is this later(() => console.log('inside')); "
                "and calling the function is cb();"
            ),
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "misconceptions": _functions_misconceptions(),
            "last_tutor_message": (
                "Two separate answers, please:\n"
                "1. Which line *passes* the function?\n"
                "2. Which exact line *invokes* it?"
            ),
            "attempt_count": 8,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "two different events" not in reply
    assert "cb();" not in result["reply"] or "operation" in result["reply"]


def test_explain_during_pass_invoke_drill_teaches_instead_of_repeating() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "can you explain",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "misconceptions": _functions_misconceptions(),
            "last_tutor_message": (
                "Two separate answers, please:\n"
                "Which line passes the function?\n"
                "Which exact line invokes it?"
            ),
            "attempt_count": 8,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "the learner thinks" not in reply
    assert "later" in reply or "stores" in reply or "cb()" in result["reply"]


def _functions_objectives() -> list[str]:
    return [
        "Explain what a callback is and why it lets code run 'later'",
        "Explain, in your own words, what a closure captures and why",
    ]


def _proved_callback_control(*, closures: bool = False) -> dict:
    from app.agents.learning_control import (
        CLOSURE_UNDERSTANDING,
        INVOKE_UNDERSTANDING,
        PASS_UNDERSTANDING,
        empty_control,
    )

    control = empty_control("programming.functions")
    control["confirmed_understandings"] = [PASS_UNDERSTANDING, INVOKE_UNDERSTANDING]
    control["purposes_demonstrated"] = [
        "identify_pass",
        "identify_invoke",
        "identify_pass_invoke",
        "transfer_pass_invoke",
        "remove_cb",
        "trace_execution",
    ]
    control["subskills_verified"] = ["pass_vs_invoke"]
    if closures:
        control["confirmed_understandings"].append(CLOSURE_UNDERSTANDING)
        control["purposes_demonstrated"].append("closure_live_link")
        control["subskills_verified"].append("closures")
    return control


def test_what_next_names_missing_evidence_instead_of_regrading() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "so what next",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": _functions_objectives(),
            "next_concept_title": "Objects, properties, methods, references",
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "no explanation" not in reply
    assert "does not address" not in reply
    assert "missing" in reply or "pass" in reply or "closure" in reply or "next concept" in reply


def test_proved_callback_does_not_repeat_the_same_question() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": (
                "passing is later(() => console.log('inside')); invoking is cb();"
            ),
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": _functions_objectives(),
            "learning_control": _proved_callback_control(),
            "last_tutor_message": (
                "Two separate answers, please:\n"
                "1. Which line *passes* the function?\n"
                "2. Which exact line *invokes* it?"
            ),
            "next_concept_title": "Objects, properties, methods, references",
            "attempt_count": 9,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "two different events" not in reply
    assert "two separate answers" not in reply
    assert "closure" in reply
    assert "verified" in reply or "missing" in reply or "still" in reply


def test_frustration_after_proved_callbacks_asks_only_missing_evidence() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "we keep going over the same thing, I already answered this",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": _functions_objectives(),
            "learning_control": _proved_callback_control(),
            "next_concept_title": "Objects, properties, methods, references",
            "attempt_count": 10,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "two different events" not in reply
    assert "later(()" not in result["reply"]
    assert "closure" in reply
    assert "missing" in reply or "verified" in reply or "still" in reply


def test_frustration_after_all_evidence_advances_the_graph() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "can we move on, you're repeating yourself",
            "concept_state": "discussing",
            "current_concept": "programming.functions",
            "concept_title": "Functions, parameters, callbacks, closures",
            "misconceptions": _functions_misconceptions(),
            "learning_objectives": _functions_objectives(),
            "learning_control": _proved_callback_control(closures=True),
            "next_concept_title": "Objects, properties, methods, references",
            "attempt_count": 12,
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "two different events" not in reply
    assert "collected" in reply or "verified" in reply or "next concept" in reply
    assert "objects" in reply
    assert result["contract"]["action"] == "REVIEW"


def test_misconception_status_is_suspected_on_caller_confusion() -> None:
    from app.agents.learning_control import apply_learner_turn, empty_control
    from app.agents.misconceptions import classify_learner_turn

    classified = classify_learner_turn(
        "The person who called myFunction is responsible for invoking cb.",
        _functions_misconceptions(),
        [],
        attempt_count_after=1,
        last_tutor_message="Who invokes the callback?",
        control=empty_control("programming.functions"),
        objectives=_functions_objectives(),
        concept_title="Functions, parameters, callbacks, closures",
    )
    assert classified["branch"] == "remediate"
    control = apply_learner_turn(
        empty_control("programming.functions"),
        message="The person who called myFunction is responsible for invoking cb.",
        last_tutor="Who invokes the callback?",
        classified=classified,
    )
    assert control["active_misconception_status"] == "suspected"
    assert "callback-caller-confusion" in control["active_misconceptions"]


def test_finding_user_id_two_does_not_verify_arrays() -> None:
    graph = build_mentor_graph(StubCoachLLM())
    result = graph.invoke(
        {
            "learner_message": "i would itereate through each list and filter where the id == 2",
            "concept_state": "introduced",
            "current_concept": "programming.arrays",
            "concept_title": "Arrays, iteration, searching, collections",
            "concept_description": "Arrays as ordered collections; finding an element that matches a condition.",
            "learning_objectives": [
                "Explain how to find the first element in an array matching a condition",
                "Explain why an array of objects is a reasonable way to store a 'table' of records",
            ],
            "diagnostic_questions": [
                "How would you find the first item in a list that matches some condition?",
                "What does an array method return when nothing matches?",
            ],
            "misconceptions": [],
            "last_tutor_message": (
                "Imagine you have an array of user objects. You need to find the user "
                "with id: 2. Walk me through how you would write that—what would your "
                "first instinct be?"
            ),
            "next_concept_title": "Networking",
            "hints": [],
            "allowed_ai_behavior": ["question"],
            "hint_level": -1,
            "effort": {},
        }
    )
    reply = result["reply"].lower()
    assert "required evidence" not in reply
    assert "marking this concept verified" not in reply
    assert result["contract"]["action"] != "REVIEW"
    assert result.get("next_state") != "verification"


def test_number_two_is_not_closure_proof_off_a_find_question() -> None:
    from app.agents.learning_control import (
        CLOSURE_UNDERSTANDING,
        apply_learner_turn,
        empty_control,
        teaching_branch,
    )
    from app.agents.misconceptions import classify_learner_turn

    message = "i would itereate through each list and filter where the id == 2"
    last_tutor = (
        "You need to find the user with id: 2. Walk me through how you would write that."
    )
    classified = classify_learner_turn(
        message,
        [],
        [],
        attempt_count_after=1,
        last_tutor_message=last_tutor,
        control=empty_control("programming.arrays"),
        objectives=[
            "Explain how to find the first element in an array matching a condition",
        ],
        concept_title="Arrays, iteration, searching, collections",
    )
    assert classified["branch"] != "proved_this"
    control = apply_learner_turn(
        empty_control("programming.arrays"),
        message=message,
        last_tutor=last_tutor,
        classified=classified,
    )
    assert CLOSURE_UNDERSTANDING not in control["confirmed_understandings"]
    assert teaching_branch(
        classified,
        control,
        message=message,
        last_tutor=last_tutor,
        objectives=[
            "Explain how to find the first element in an array matching a condition",
        ],
        concept_title="Arrays, iteration, searching, collections",
    ) != "proved_this"
