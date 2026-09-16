"""State-aware mentor graph.

The curriculum engine decides *what* the learner works on. This graph decides
*how* the mentor responds inside that node: question, research, hint, review,
or diagnosis. It never invents the next milestone.
"""

from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.agents.llm import CoachLLM, StubCoachLLM
from app.agents.learning_control import (
    callback_distinction_proved,
    closure_proved,
    has_evidence_ledger,
    missing_required_evidence,
    representation_script,
    required_conversational_evidence_satisfied,
)
from app.agents.misconceptions import (
    classify_learner_turn,
    last_tutor_asks_closures,
    last_tutor_asks_pass_invoke,
    match_misconception,
    normalize_misconceptions,
    remediation_script,
    retest_script,
    teach_script,
    uncovered_objectives,
)
from app.agents.policies import (
    asks_for_implementation,
    asks_for_mentor_explanation,
    asks_what_next,
    classify_intent,
    enforce_brevity,
    explain_gap_reason,
    filter_specialist_reply,
    next_hint_level,
)
from app.agents.state import MentorContract, MentorState
from app.models.learning_state import ConceptStatus

_BLOCKED_STATES = {
    ConceptStatus.blocked.value,
    ConceptStatus.diagnosis.value,
    ConceptStatus.knowledge_gap.value,
    ConceptStatus.needs_review.value,
}


def empty_contract(**overrides: object) -> MentorContract:
    base: MentorContract = {
        "intent": "MENTOR",
        "action": "ASK_QUESTION",
        "message": "",
        "diagnostic_concept": None,
        "identified_gap": None,
        "hint_level": 0,
        "should_unlock": False,
        "next_state": ConceptStatus.introduced.value,
    }
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def _behaviors_for(status: str, *, needs_build: bool) -> list[str]:
    if status in _BLOCKED_STATES:
        return ["question", "diagnose", "hint"]
    if status in {ConceptStatus.available.value, ConceptStatus.introduced.value}:
        return ["question", "research"]
    if status == ConceptStatus.researching.value:
        return ["question", "research"]
    if status in {ConceptStatus.discussing.value, ConceptStatus.explained.value}:
        return ["question", "diagnose", "review"]
    if status in {ConceptStatus.attempted.value, ConceptStatus.testing.value}:
        return ["question", "diagnose", "hint", "review"]
    if status == ConceptStatus.verification.value:
        return ["question", "review"]
    if needs_build:
        return ["question", "hint", "review"]
    return ["question", "diagnose", "review"]


def route_node(state: MentorState) -> MentorState:
    message = state.get("learner_message") or ""
    intent = classify_intent(message)
    status = state.get("concept_state") or ConceptStatus.available.value
    if asks_for_implementation(message):
        intent = "code_ask"
    if status in _BLOCKED_STATES and intent not in {"hint", "code_ask"}:
        intent = "diagnose"
    return {"intent": intent}


def _classify_turn(state: MentorState) -> dict:
    branch = state.get("misconception_branch")
    if isinstance(branch, str) and branch:
        return {
            "branch": branch,
            "misconception": state.get("identified_misconception"),
        }
    classified = classify_learner_turn(
        state.get("learner_message") or "",
        state.get("misconceptions") or [],
        state.get("diagnostic_answers") or [],
        attempt_count_after=int(state.get("attempt_count") or 0),
        last_tutor_message=state.get("last_tutor_message") or "",
        control=state.get("learning_control") or {},
        objectives=list(state.get("learning_objectives") or []),
        concept_title=str(state.get("concept_title") or ""),
    )
    if not classified.get("misconception"):
        identified = state.get("identified_misconception")
        if isinstance(identified, dict) and identified.get("description"):
            classified["misconception"] = identified
    return classified


def _pick_branch(state: MentorState) -> str:
    status = state.get("concept_state") or ConceptStatus.available.value
    intent = state.get("intent") or "answer"
    message = state.get("learner_message") or ""
    if state.get("awaiting_reflection"):
        return "reflection"
    if state.get("project_complete"):
        return "milestone_gate"
    if intent == "hint":
        return "hint_gate"
    classified = _classify_turn(state)
    branch = classified.get("branch")
    if branch == "remediate":
        return "misconception_remediation"
    if branch == "retest":
        return "misconception_retest"
    if branch == "cleared":
        return "misconception_cleared"
    if branch == "proved_this":
        return "proved_this"
    if branch == "change_representation":
        return "change_representation"
    if branch == "application_check":
        return "application_check"
    if branch == "transfer_check":
        return "transfer_check"
    if branch == "await_invoke":
        return "await_invoke"
    if branch == "await_pass":
        return "await_pass"
    if branch == "closure_pass":
        return "closure_pass"
    if branch == "missing_evidence":
        return "missing_evidence"
    if asks_what_next(message):
        return "next_step"
    if asks_for_mentor_explanation(message):
        return "teach"
    if intent == "guidance":
        return "question"
    if intent == "code_ask":
        return "question"
    if status in _BLOCKED_STATES:
        return "gap_diagnosis"
    if status in {ConceptStatus.available.value, ConceptStatus.introduced.value}:
        return "question"
    if status == ConceptStatus.researching.value:
        return "research_prompt"
    if status in {ConceptStatus.discussing.value, ConceptStatus.explained.value, ConceptStatus.verification.value}:
        return "explanation_eval"
    if status in {ConceptStatus.attempted.value, ConceptStatus.testing.value}:
        tests = state.get("tests") or {}
        if (tests.get("failed") or 0) > 0 or "test" in message.lower():
            return "test_feedback"
        return "implementation_gate"
    return "question"


def _invoke_contract(llm: CoachLLM, state: MentorState, action_hint: str) -> MentorContract:
    context = {
        "project": state.get("project") or "",
        "current_milestone": state.get("current_milestone") or "",
        "current_milestone_title": state.get("current_milestone_title") or "",
        "current_concept": state.get("current_concept") or "",
        "concept_title": state.get("concept_title") or "",
        "concept_description": state.get("concept_description") or "",
        "concept_state": state.get("concept_state") or "",
        "prerequisites": state.get("prerequisites") or {},
        "known_gaps": state.get("known_gaps") or [],
        "attempt_count": state.get("attempt_count") or 0,
        "hints_used": state.get("hints_used") or 0,
        "tests": state.get("tests") or {},
        "learner_last_explanation": state.get("learner_last_explanation") or "",
        "allowed_ai_behavior": state.get("allowed_ai_behavior") or [],
        "diagnostic_questions": state.get("diagnostic_questions") or [],
        "research_questions": state.get("research_questions") or [],
        "misconceptions": state.get("misconceptions") or [],
        "identified_misconception": state.get("identified_misconception")
        or _classify_turn(state).get("misconception"),
        "learning_control": state.get("learning_control") or {},
        "do_not_ask_purposes": list(
            (state.get("learning_control") or {}).get("purposes_demonstrated") or []
        ),
        "subskills_verified": list(
            (state.get("learning_control") or {}).get("subskills_verified") or []
        ),
        "missing_required_evidence": missing_required_evidence(
            state.get("learning_control") or {},
            list(state.get("learning_objectives") or []),
            concept_id=str(state.get("current_concept") or ""),
            concept_title=str(state.get("concept_title") or ""),
        ),
        "evidence_ledger_active": has_evidence_ledger(
            list(state.get("learning_objectives") or []),
            concept_id=str(state.get("current_concept") or ""),
            concept_title=str(state.get("concept_title") or ""),
        ),
        "recent_learner_answers": [
            item.get("answer") if isinstance(item, dict) else str(item)
            for item in (state.get("diagnostic_answers") or [])[-4:]
        ],
        "hints": state.get("hints") or [],
        "learning_objectives": state.get("learning_objectives") or [],
        "needs_build": bool(state.get("needs_build")),
        "gap_reason": state.get("gap_reason") or "",
        "tests_summary": state.get("tests_summary") or "",
    }
    return llm.mentor_contract(context=context, message=state.get("learner_message") or "", action_hint=action_hint)


def make_question_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def question_node(state: MentorState) -> MentorState:
        skipped = _advance_or_missing_if_ready(state)
        if skipped is not None:
            return skipped
        status = state.get("concept_state") or ConceptStatus.available.value
        if asks_for_implementation(state.get("learner_message") or ""):
            contract = empty_contract(
                intent="MENTOR",
                action="ASK_QUESTION",
                message=(
                    "Before I give you implementation help, show me how you would design it. "
                    "What information does this piece need to store or produce?"
                ),
                next_state=status if status != ConceptStatus.available.value else ConceptStatus.introduced.value,
            )
        else:
            contract = _invoke_contract(llm, state, "ASK_QUESTION")
            if status == ConceptStatus.available.value:
                next_state = ConceptStatus.introduced.value
            else:
                next_state = status
            contract["next_state"] = next_state
            if str(contract.get("action") or "") == "REVIEW" and not _ledger_satisfied(state):
                contract["action"] = "ASK_QUESTION"
                contract["should_unlock"] = False
        return {
            "reply": str(contract.get("message") or ""),
            "contract": contract,
            "next_state": str(contract.get("next_state") or ConceptStatus.introduced.value),
        }

    return question_node


def make_research_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def research_prompt(state: MentorState) -> MentorState:
        contract = _invoke_contract(llm, state, "RESEARCH")
        questions = state.get("research_questions") or []
        if not contract.get("message"):
            listed = "\n".join(f"{i}. {q}" for i, q in enumerate(questions[:3], start=1))
            contract["message"] = (
                "Research this before I explain it. Do not copy an explanation — "
                "write down what you understand.\n\n"
                f"{listed or 'What is this concept, in your own words?'}"
            )
        contract["action"] = "ASK_RESEARCH"
        contract["next_state"] = ConceptStatus.researching.value
        return {
            "reply": str(contract["message"]),
            "contract": contract,
            "next_state": ConceptStatus.researching.value,
        }

    return research_prompt


def _recent_misconception(state: MentorState) -> dict | None:
    last_tutor = state.get("last_tutor_message") or ""
    specs = normalize_misconceptions(state.get("misconceptions") or [])
    by_id = {item["id"]: item for item in specs}
    if last_tutor_asks_closures(last_tutor) and by_id.get("closure-copies-values"):
        return by_id["closure-copies-values"]
    if last_tutor_asks_pass_invoke(last_tutor):
        return by_id.get("callback-caller-confusion") or by_id.get("callback-runs-when-passed")
    identified = state.get("identified_misconception")
    if isinstance(identified, dict) and identified.get("description"):
        return identified
    for item in reversed(list(state.get("diagnostic_answers") or [])):
        if not isinstance(item, dict):
            continue
        if item.get("phase") == "stuck":
            continue
        if item.get("misconception_id") in by_id:
            return by_id[str(item["misconception_id"])]
    return by_id.get("callback-caller-confusion") or (specs[0] if specs else None)


def _misconception_from_state(state: MentorState) -> dict | None:
    identified = state.get("identified_misconception")
    if isinstance(identified, dict) and identified.get("description"):
        return identified
    matched = match_misconception(
        state.get("learner_message") or "",
        state.get("misconceptions") or [],
    )
    if matched:
        return matched
    return _recent_misconception(state)


def make_teach_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def teach(state: MentorState) -> MentorState:
        misc = _recent_misconception(state)
        if misc:
            message = teach_script(misc)
        else:
            contract = _invoke_contract(llm, state, "TEACH")
            message = str(contract.get("message") or "").strip() or (
                "Here is the mechanism in the smallest form.\n"
                "A callback is stored when it is passed and runs only when some other "
                "line invokes it.\n\n"
                "Which exact line in the current example actually runs it?"
            )
        contract = empty_contract(
            intent="MENTOR",
            action="ASK_QUESTION",
            message=message,
            next_state=ConceptStatus.discussing.value,
        )
        return {
            "reply": message,
            "contract": contract,
            "next_state": ConceptStatus.discussing.value,
        }

    return teach


def _control_missing(state: MentorState) -> list[dict[str, str]] | None:
    return missing_required_evidence(
        state.get("learning_control") or {},
        list(state.get("learning_objectives") or []),
        concept_id=str(state.get("current_concept") or ""),
        concept_title=str(state.get("concept_title") or ""),
    )


def _ledger_satisfied(state: MentorState) -> bool:
    return required_conversational_evidence_satisfied(
        state.get("learning_control") or {},
        list(state.get("learning_objectives") or []),
        concept_id=str(state.get("current_concept") or ""),
        concept_title=str(state.get("concept_title") or ""),
    )


def _advance_or_missing_if_ready(state: MentorState) -> MentorState | None:
    if _ledger_satisfied(state):
        return proved_this_node(state)
    missing = _control_missing(state)
    if missing and callback_distinction_proved(state.get("learning_control") or {}):
        return missing_evidence_node(state)
    return None


def _advance_payload(state: MentorState) -> MentorState:
    title = state.get("concept_title") or "this concept"
    nxt = (state.get("next_concept_title") or "").strip()
    follow = f" The curriculum graph's next concept is {nxt}." if nxt else ""
    if state.get("needs_build"):
        message = (
            f"Required evidence for '{title}' is collected. I'm marking that verified.\n"
            "Now use it: build the smallest version that stores a function and runs it later."
        )
        next_state = ConceptStatus.attempted.value
        action = "ASK_IMPLEMENTATION"
        unlock = False
    else:
        message = (
            f"Required evidence for '{title}' is collected. I'm marking this concept "
            f"verified.{follow}"
        )
        next_state = ConceptStatus.verification.value
        action = "REVIEW"
        unlock = True
    contract = empty_contract(
        intent="MENTOR",
        action=action,
        message=message,
        should_unlock=unlock,
        next_state=next_state,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": next_state,
        "should_unlock": unlock,
    }


def missing_evidence_node(state: MentorState) -> MentorState:
    title = state.get("concept_title") or "this concept"
    missing = _control_missing(state)
    if missing is None:
        questions = list(state.get("diagnostic_questions") or [])
        ask = questions[0] if questions else "What can you still prove about this, in your own words?"
        message = f"We're still on '{title}'. Next: {ask}"
        contract = empty_contract(
            intent="MENTOR",
            action="ASK_QUESTION",
            message=message,
            next_state=ConceptStatus.discussing.value,
        )
        return {
            "reply": message,
            "contract": contract,
            "next_state": ConceptStatus.discussing.value,
        }
    if not missing:
        if _ledger_satisfied(state):
            return _advance_payload(state)
        questions = list(state.get("diagnostic_questions") or [])
        ask = questions[0] if questions else "What can you still prove about this, in your own words?"
        message = f"We're still on '{title}'. Still missing evidence. Next: {ask}"
        contract = empty_contract(
            intent="MENTOR",
            action="ASK_QUESTION",
            message=message,
            next_state=ConceptStatus.discussing.value,
        )
        return {
            "reply": message,
            "contract": contract,
            "next_state": ConceptStatus.discussing.value,
        }
    first = missing[0]
    if first["skill"] == "closures":
        message = (
            f"Not another callback question — that distinction is verified on '{title}'.\n\n"
            f"Still missing: {first['why']}\n\n"
            "If `let n = 1` and an inner function reads `n`, then later `n = 2`, "
            "what does the inner function print when you call it?"
        )
    else:
        message = (
            f"We're not repeating for its own sake. Still missing on '{title}': "
            f"{first['why']}\n\n"
            "Two separate answers, please:\n"
            "1. Which line *passes* the function?\n"
            "2. Which exact line *invokes* it?"
        )
    contract = empty_contract(
        intent="MENTOR",
        action="ASK_QUESTION",
        message=message,
        next_state=ConceptStatus.discussing.value,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": ConceptStatus.discussing.value,
    }


def next_step_node(state: MentorState) -> MentorState:
    skipped = _advance_or_missing_if_ready(state)
    if skipped is not None:
        return skipped
    missing = _control_missing(state)
    if missing:
        return missing_evidence_node(state)
    title = state.get("concept_title") or "this concept"
    nxt = (state.get("next_concept_title") or "").strip()
    status = state.get("concept_state") or ""
    if status in {
        ConceptStatus.explained.value,
        ConceptStatus.verification.value,
        ConceptStatus.mastered.value,
        ConceptStatus.verified.value,
    } and nxt:
        message = (
            f"Next concept: {nxt}. Don't skip ahead — what do you already understand about it?"
        )
        next_state = status
    else:
        questions = list(state.get("diagnostic_questions") or [])
        ask = questions[0] if questions else "What can you still prove about this, in your own words?"
        message = f"We're still on '{title}'. Next: {ask}"
        next_state = status or ConceptStatus.discussing.value
    contract = empty_contract(
        intent="MENTOR",
        action="ASK_QUESTION",
        message=message,
        next_state=next_state,
    )
    return {"reply": message, "contract": contract, "next_state": next_state}


def await_invoke_node(state: MentorState) -> MentorState:
    message = (
        "Yes. That line *passes* the function. It does not run it.\n\n"
        "Second answer, separately: which exact line *invokes* it?"
    )
    contract = empty_contract(
        intent="DIAGNOSE",
        action="ASK_DIAGNOSTIC_QUESTION",
        message=message,
        next_state=ConceptStatus.discussing.value,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": ConceptStatus.discussing.value,
    }


def await_pass_node(state: MentorState) -> MentorState:
    message = (
        "Yes. That line *invokes* it.\n\n"
        "Second answer, separately: which exact line *passes* the function in?"
    )
    contract = empty_contract(
        intent="DIAGNOSE",
        action="ASK_DIAGNOSTIC_QUESTION",
        message=message,
        next_state=ConceptStatus.discussing.value,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": ConceptStatus.discussing.value,
    }


def closure_pass_node(state: MentorState) -> MentorState:
    prefix = (
        "Right. It prints 2. The inner function does not copy `n` — it keeps a live link to it.\n\n"
    )
    if _ledger_satisfied(state):
        result = _advance_payload(state)
    elif _control_missing(state):
        result = missing_evidence_node(state)
    else:
        result = application_check_node(state)
    result["reply"] = prefix + str(result.get("reply") or "")
    contract = dict(result.get("contract") or {})
    contract["message"] = result["reply"]
    result["contract"] = contract  # type: ignore[typeddict-item]
    return result


def proved_this_node(state: MentorState) -> MentorState:
    missing = _control_missing(state)
    if missing:
        return missing_evidence_node(state)
    if _ledger_satisfied(state):
        return _advance_payload(state)
    title = state.get("concept_title") or "this concept"
    questions = list(state.get("diagnostic_questions") or [])
    ask = questions[0] if questions else "Show me that on a different example — one instinct is not enough."
    message = f"We're still on '{title}'. {ask}"
    contract = empty_contract(
        intent="MENTOR",
        action="ASK_QUESTION",
        message=message,
        next_state=ConceptStatus.discussing.value,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": ConceptStatus.discussing.value,
    }


def change_representation_node(state: MentorState) -> MentorState:
    control = state.get("learning_control") or {}
    representation = str(control.get("representation") or "verbal")
    from app.agents.learning_control import next_representation

    nxt = next_representation(representation) or representation
    misc = _misconception_from_state(state)
    misc_id = misc.get("id") if isinstance(misc, dict) else None
    if last_tutor_asks_closures(state.get("last_tutor_message") or ""):
        misc_id = "closure-copies-values"
    message = (
        "Same concept, different representation — not another copy of the last question.\n\n"
        + representation_script(misc_id, nxt)
    )
    contract = empty_contract(
        intent="DIAGNOSE",
        action="ASK_DIAGNOSTIC_QUESTION",
        message=message,
        next_state=ConceptStatus.discussing.value,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": ConceptStatus.discussing.value,
        "learning_control": {**dict(control), "representation": nxt, "strategy": "change_representation"},
    }


def application_check_node(state: MentorState) -> MentorState:
    message = (
        "That explanation is enough to treat this as explained — not yet verified.\n\n"
        "Use it: a router stores a function when you register a path and runs it later "
        "when a request matches. Which moment is passing, and which is invoking?"
    )
    contract = empty_contract(
        intent="MENTOR",
        action="ASK_QUESTION",
        message=message,
        next_state=ConceptStatus.explained.value,
    )
    return {"reply": message, "contract": contract, "next_state": ConceptStatus.explained.value}


def transfer_check_node(state: MentorState) -> MentorState:
    message = (
        "Same distinction, new names — don't reuse the previous wording.\n\n"
        "```javascript\n"
        "queue.push(job);\n"
        "job();\n"
        "```\n\n"
        "Which line passes the function, and which line invokes it?"
    )
    contract = empty_contract(
        intent="DIAGNOSE",
        action="ASK_DIAGNOSTIC_QUESTION",
        message=message,
        next_state=ConceptStatus.explained.value,
    )
    return {"reply": message, "contract": contract, "next_state": ConceptStatus.explained.value}


def make_remediation_node() -> Callable[[MentorState], MentorState]:
    def misconception_remediation(state: MentorState) -> MentorState:
        misc = _misconception_from_state(state)
        message = (
            remediation_script(misc)
            if misc
            else (
                "I think we've found the part that's unclear. Let's isolate it.\n"
                "Which exact line of code does the action you just described?"
            )
        )
        contract = empty_contract(
            intent="DIAGNOSE",
            action="ASK_DIAGNOSTIC_QUESTION",
            message=message,
            next_state=ConceptStatus.discussing.value,
        )
        return {
            "reply": message,
            "contract": contract,
            "next_state": ConceptStatus.discussing.value,
        }

    return misconception_remediation


def make_retest_node() -> Callable[[MentorState], MentorState]:
    def misconception_retest(state: MentorState) -> MentorState:
        misc = _misconception_from_state(state)
        message = (
            retest_script(misc)
            if misc
            else (
                "Exactly. Now test the same distinction in a new example.\n"
                "Which line passes the function, and which line invokes it?"
            )
        )
        contract = empty_contract(
            intent="DIAGNOSE",
            action="ASK_DIAGNOSTIC_QUESTION",
            message=message,
            next_state=ConceptStatus.discussing.value,
        )
        return {
            "reply": message,
            "contract": contract,
            "next_state": ConceptStatus.discussing.value,
        }

    return misconception_retest


def misconception_cleared_node(state: MentorState) -> MentorState:
    leftover = uncovered_objectives(
        list(state.get("learning_objectives") or []),
        str(state.get("learner_message") or ""),
    )
    skipped = _advance_or_missing_if_ready(state)
    if skipped is not None:
        prefix = (
            "That's the callback distinction: passing stores the function, `cb()` runs it later.\n\n"
        )
        skipped["reply"] = prefix + str(skipped.get("reply") or "")
        contract = dict(skipped.get("contract") or {})
        contract["message"] = skipped["reply"]
        skipped["contract"] = contract  # type: ignore[typeddict-item]
        return skipped
    if leftover:
        message = (
            "That's the callback distinction: passing stores the function, `cb()` runs it later.\n\n"
            "Closures are a different idea. If `let n = 1` and an inner function reads `n`, "
            "then later `n = 2`, what does the inner function print when you call it?"
        )
    else:
        message = (
            "That's the distinction. We can use it now — I won't re-ask the same question."
        )
    contract = empty_contract(
        intent="MENTOR",
        action="ASK_QUESTION",
        message=message,
        next_state=ConceptStatus.discussing.value,
    )
    return {
        "reply": message,
        "contract": contract,
        "next_state": ConceptStatus.discussing.value,
    }


def make_explanation_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def explanation_eval(state: MentorState) -> MentorState:
        answer = state.get("learner_message") or ""
        if asks_what_next(answer):
            return next_step_node(state)
        if asks_for_mentor_explanation(answer):
            return make_teach_node(llm)(state)
        matched = match_misconception(answer, state.get("misconceptions") or [])
        if matched:
            message = remediation_script(matched)
            contract = empty_contract(
                intent="DIAGNOSE",
                action="ASK_DIAGNOSTIC_QUESTION",
                message=message,
                next_state=ConceptStatus.discussing.value,
            )
            return {
                "reply": message,
                "contract": contract,
                "next_state": ConceptStatus.discussing.value,
            }
        objectives = list(state.get("learning_objectives") or [])
        recent = _recent_misconception(state)
        if recent and recent.get("id") == "callback-caller-confusion":
            objectives = [item for item in objectives if "closure" not in item.lower()] or objectives[:1]
        result = llm.evaluate_explanation(
            concept_title=state.get("concept_title") or "",
            concept_description=state.get("concept_description") or "",
            objectives=objectives,
            answer=answer,
            current_question=str(state.get("last_tutor_message") or ""),
        )
        passed = bool(result.get("passed"))
        if passed:
            leftover = uncovered_objectives(
                list(state.get("learning_objectives") or []),
                answer,
            )
            if _ledger_satisfied(state):
                return proved_this_node(state)
            missing = _control_missing(state)
            if missing:
                return missing_evidence_node(state)
            if leftover and any("closure" in item.lower() for item in leftover) and not closure_proved(
                state.get("learning_control") or {}
            ):
                message = (
                    "The callback part is solid — passing stores the function, `cb()` runs it later.\n\n"
                    "Closures are a different idea. If `let n = 1` and an inner function reads `n`, "
                    "then later `n = 2`, what does the inner function print when you call it?"
                )
                contract = empty_contract(
                    intent="MENTOR",
                    action="ASK_QUESTION",
                    message=message,
                    next_state=ConceptStatus.discussing.value,
                )
                return {
                    "reply": message,
                    "contract": contract,
                    "next_state": ConceptStatus.discussing.value,
                }
            if has_evidence_ledger(
                list(state.get("learning_objectives") or []),
                concept_id=str(state.get("current_concept") or ""),
                concept_title=str(state.get("concept_title") or ""),
            ):
                return application_check_node(state)
            questions = list(state.get("diagnostic_questions") or [])
            ask = (
                questions[1]
                if len(questions) > 1
                else (questions[0] if questions else "Show me that on a different example.")
            )
            message = (
                f"{result.get('feedback') or 'That instinct is a start — not yet verified.'}\n\n"
                f"{ask}"
            )
            contract = empty_contract(
                intent="MENTOR",
                action="ASK_QUESTION",
                message=message,
                next_state=ConceptStatus.discussing.value,
            )
            return {
                "reply": message,
                "contract": contract,
                "next_state": ConceptStatus.discussing.value,
            }
        else:
            contract = empty_contract(
                intent="DIAGNOSE",
                action="ASK_QUESTION",
                message=str(
                    result.get("feedback")
                    or "Not yet — which part of this still feels fuzzy? Be specific."
                ),
                next_state=ConceptStatus.discussing.value,
            )
        return {
            "reply": str(contract["message"]),
            "contract": contract,
            "next_state": str(contract["next_state"]),
            "should_unlock": bool(contract.get("should_unlock")),
        }

    return explanation_eval


def make_implementation_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def implementation_gate(state: MentorState) -> MentorState:
        contract = _invoke_contract(llm, state, "IMPLEMENTATION")
        if not contract.get("message"):
            contract["message"] = (
                "Build it in the editor. I will not modify your files. "
                "When you have something running, tell me what you tried and what you observed."
            )
        contract["action"] = "ASK_IMPLEMENTATION"
        contract["next_state"] = ConceptStatus.attempted.value
        return {
            "reply": str(contract["message"]),
            "contract": contract,
            "next_state": ConceptStatus.attempted.value,
        }

    return implementation_gate


def make_test_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def test_feedback(state: MentorState) -> MentorState:
        tests = state.get("tests") or {}
        failed = int(tests.get("failed") or 0)
        summary = state.get("tests_summary") or ""
        if failed:
            contract = empty_contract(
                intent="MENTOR",
                action="ASK_QUESTION",
                message=(
                    "A test failed. Which part of your implementation is responsible "
                    "for the behavior that test is checking?"
                    + (f"\n\n{summary}" if summary else "")
                ),
                next_state=ConceptStatus.blocked.value,
            )
        else:
            contract = empty_contract(
                intent="MENTOR",
                action="REVIEW",
                message="Tests are green. In your own words, why did you design it this way?",
                next_state=ConceptStatus.explained.value,
            )
        extra = _invoke_contract(llm, state, "TEST_FEEDBACK")
        if extra.get("message") and not failed:
            contract["message"] = str(extra["message"])
        return {
            "reply": str(contract["message"]),
            "contract": contract,
            "next_state": str(contract["next_state"]),
        }

    return test_feedback


def hint_gate_node(state: MentorState) -> MentorState:
    level, reason = next_hint_level(
        int(state.get("hint_level", -1)), state.get("effort") or {}
    )
    return {"hint_level": level, "hint_blocked_reason": reason}


def _after_hint_gate(state: MentorState) -> str:
    if state.get("hint_blocked_reason") == "need_effort":
        return "policy"
    return "hint_ladder"


def make_hint_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def hint_ladder(state: MentorState) -> MentorState:
        level = int(state.get("hint_level") or 0)
        hints = list(state.get("hints") or [])
        seeded = hints[level] if 0 <= level < len(hints) else ""
        llm_hint = llm.hint_reply(
            level,
            state.get("current_milestone_title") or "this milestone",
            [state.get("concept_title") or state.get("current_concept") or ""],
            instructions=seeded,
        )
        last_tutor = state.get("last_tutor_message") or ""
        if last_tutor_asks_pass_invoke(last_tutor):
            message = (
                "Two different lines. One *gives* the function in. A different line *runs* it.\n"
                "If you already named `later(() => ...)`, the invoke line is `cb();` inside `later`."
            )
        elif last_tutor_asks_closures(last_tutor):
            message = (
                "The inner function does not snapshot `n`. It keeps a live link. "
                "If `n` later becomes 2, what does the inner function print?"
            )
        else:
            message = seeded or llm_hint
        contract = empty_contract(
            intent="MENTOR",
            action="HINT",
            message=message,
            hint_level=level,
            next_state=state.get("concept_state") or ConceptStatus.attempted.value,
        )
        return {"reply": message, "contract": contract, "hint_level": level}

    return hint_ladder


def make_gap_node(llm: CoachLLM) -> Callable[[MentorState], MentorState]:
    def gap_diagnosis(state: MentorState) -> MentorState:
        gaps = list(state.get("known_gaps") or [])
        top = gaps[0] if gaps else None
        identified = None
        if top:
            identified = {
                "concept": str(top.get("concept") or ""),
                "confidence": float(top.get("confidence") or 0),
            }
        reason = state.get("gap_reason") or ""
        if identified and reason:
            message = explain_gap_reason(
                reason,
                concept_id=state.get("current_concept") or "",
                requires_id=identified["concept"],
            )
        else:
            contract = _invoke_contract(llm, state, "DIAGNOSE")
            message = str(contract.get("message") or "")
        questions = state.get("diagnostic_questions") or []
        if questions and (not message or message == reason):
            message = questions[0]
        if not message:
            message = (
                "Before we solve that, what does this concept represent to you? "
                "I need to see which piece is actually missing."
            )
        contract = empty_contract(
            intent="DIAGNOSE",
            action="ASK_DIAGNOSTIC_QUESTION",
            message=message,
            diagnostic_concept=(identified or {}).get("concept") if identified else None,
            identified_gap=identified,
            next_state=ConceptStatus.diagnosis.value,
        )
        return {
            "reply": message,
            "contract": contract,
            "next_state": ConceptStatus.diagnosis.value,
            "identified_gap": identified,
        }

    return gap_diagnosis


def reflection_node(state: MentorState) -> MentorState:
    message = (
        "Before we close this milestone, reflect:\n"
        "What did you build? Why this design? What alternatives did you consider?\n"
        "What was difficult? What would break at larger scale? What would you change?"
    )
    contract = empty_contract(
        intent="MENTOR",
        action="ASK_REFLECTION",
        message=message,
        next_state=state.get("concept_state") or ConceptStatus.mastered.value,
    )
    return {"reply": message, "contract": contract}


def milestone_gate_node(state: MentorState) -> MentorState:
    status = state.get("concept_state") or ""
    if status in _BLOCKED_STATES or status == ConceptStatus.testing.value:
        message = (
            "Before we move forward, your work suggests you are still unclear on "
            f"'{state.get('concept_title') or 'the current concept'}'. Let's investigate that."
        )
        contract = empty_contract(
            intent="MENTOR",
            action="HOLD",
            message=message,
            should_unlock=False,
            next_state=status,
        )
        return {"reply": message, "contract": contract, "should_unlock": False}
    if state.get("project_complete"):
        message = (
            "The framework is built. This is a technical defense, not a congratulations. "
            "Why did you structure the router this way?"
        )
        contract = empty_contract(
            intent="MENTOR",
            action="ASK_DEFENSE",
            message=message,
            next_state=status,
        )
        return {"reply": message, "contract": contract}
    contract = empty_contract(
        intent="MENTOR",
        action="HOLD",
        message="Stay with the current concept until the evidence is there.",
        next_state=status,
    )
    return {"reply": str(contract["message"]), "contract": contract, "should_unlock": False}


def policy_node(state: MentorState) -> MentorState:
    reply = state.get("reply") or ""
    if state.get("hint_blocked_reason") == "need_effort":
        reply = (
            "Show effort first — try a step in the editor/terminal, then ask again. "
            "What did you attempt, and what happened?"
        )
    contract = dict(state.get("contract") or empty_contract())
    max_sentences = 8
    allow_commands = (state.get("intent") or "") in {"guidance", "hint"} or (
        state.get("concept_state") in {ConceptStatus.attempted.value, ConceptStatus.testing.value}
    )
    filtered, flags = filter_specialist_reply(
        reply,
        later_concepts=list(state.get("later_concepts") or []),
        allow_code=False,
        allow_commands=allow_commands,
        allow_mini_examples=True,
        max_sentences=max_sentences,
        resources=list(state.get("resources") or []),
    )
    if state.get("concept_state") in _BLOCKED_STATES:
        lowered = filtered.lower()
        if "let's move on" in lowered or "lets move on" in lowered or "next milestone" in lowered:
            filtered = (
                "Before we move forward, your explanation suggests you are still unclear "
                "about the current concept. Let's investigate that."
            )
            flags.append("blocked_advance")
    contract["message"] = filtered
    return {
        "reply": enforce_brevity(filtered, max_sentences=max_sentences),
        "policy_flags": flags,
        "contract": contract,  # type: ignore[typeddict-item]
    }


def build_mentor_graph(llm: CoachLLM | None = None):
    llm = llm or StubCoachLLM()
    builder = StateGraph(MentorState)
    builder.add_node("route", route_node)
    builder.add_node("question", make_question_node(llm))
    builder.add_node("research_prompt", make_research_node(llm))
    builder.add_node("misconception_remediation", make_remediation_node())
    builder.add_node("misconception_retest", make_retest_node())
    builder.add_node("misconception_cleared", misconception_cleared_node)
    builder.add_node("teach", make_teach_node(llm))
    builder.add_node("next_step", next_step_node)
    builder.add_node("await_invoke", await_invoke_node)
    builder.add_node("await_pass", await_pass_node)
    builder.add_node("closure_pass", closure_pass_node)
    builder.add_node("proved_this", proved_this_node)
    builder.add_node("missing_evidence", missing_evidence_node)
    builder.add_node("change_representation", change_representation_node)
    builder.add_node("application_check", application_check_node)
    builder.add_node("transfer_check", transfer_check_node)
    builder.add_node("explanation_eval", make_explanation_node(llm))
    builder.add_node("implementation_gate", make_implementation_node(llm))
    builder.add_node("test_feedback", make_test_node(llm))
    builder.add_node("hint_gate", hint_gate_node)
    builder.add_node("hint_ladder", make_hint_node(llm))
    builder.add_node("gap_diagnosis", make_gap_node(llm))
    builder.add_node("reflection", reflection_node)
    builder.add_node("milestone_gate", milestone_gate_node)
    builder.add_node("policy", policy_node)
    builder.add_edge(START, "route")
    builder.add_conditional_edges(
        "route",
        _pick_branch,
        {
            "question": "question",
            "research_prompt": "research_prompt",
            "misconception_remediation": "misconception_remediation",
            "misconception_retest": "misconception_retest",
            "misconception_cleared": "misconception_cleared",
            "teach": "teach",
            "next_step": "next_step",
            "await_invoke": "await_invoke",
            "await_pass": "await_pass",
            "closure_pass": "closure_pass",
            "proved_this": "proved_this",
            "missing_evidence": "missing_evidence",
            "change_representation": "change_representation",
            "application_check": "application_check",
            "transfer_check": "transfer_check",
            "explanation_eval": "explanation_eval",
            "implementation_gate": "implementation_gate",
            "test_feedback": "test_feedback",
            "hint_gate": "hint_gate",
            "gap_diagnosis": "gap_diagnosis",
            "reflection": "reflection",
            "milestone_gate": "milestone_gate",
        },
    )
    builder.add_conditional_edges(
        "hint_gate",
        _after_hint_gate,
        {"policy": "policy", "hint_ladder": "hint_ladder"},
    )
    for name in (
        "question",
        "research_prompt",
        "misconception_remediation",
        "misconception_retest",
        "misconception_cleared",
        "teach",
        "next_step",
        "await_invoke",
        "await_pass",
        "closure_pass",
        "proved_this",
        "change_representation",
        "application_check",
        "transfer_check",
        "explanation_eval",
        "implementation_gate",
        "test_feedback",
        "hint_ladder",
        "gap_diagnosis",
        "reflection",
        "milestone_gate",
    ):
        builder.add_edge(name, "policy")
    builder.add_edge("policy", END)
    return builder.compile()
