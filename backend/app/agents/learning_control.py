"""Teaching-strategy memory for the mentor.

Stored on ConceptState.evidence["learning_control"] (JSONB, no migration).
The graph uses this so it does not re-ask a purpose the learner already
proved, and so one verbal explanation is not treated as mastery.
"""

from __future__ import annotations

import re
from typing import Any

from app.agents.misconceptions import (
    answer_shows_live_closure,
    names_invoking,
    names_passing,
)

STRATEGIES = (
    "diagnostic",
    "diagnose_gap",
    "micro_explanation",
    "guided_example",
    "new_example",
    "verify",
    "change_representation",
    "explained",
    "application",
    "transfer",
    "verified",
)

REPRESENTATIONS = ("verbal", "trace", "diagram", "analogy", "application")

CALLBACK_PURPOSES = {
    "identify_pass",
    "identify_invoke",
    "identify_pass_invoke",
    "trace_execution",
    "transfer_pass_invoke",
    "remove_cb",
}

PASS_UNDERSTANDING = "learner understands later(...) passes the function"
INVOKE_UNDERSTANDING = "learner understands cb() invokes the callback"
CLOSURE_UNDERSTANDING = "learner understands a closure keeps a live link to outer variables"
REMOVE_UNDERSTANDING = "learner understands removing cb() prevents the callback from running"

_FRUSTRATION = (
    "same question",
    "already asked",
    "you just asked",
    "keep asking",
    "asked this",
    "this again",
    "again?",
    "stop asking",
    "i already said",
    "i already told",
    "we keep going over",
    "keep going over the same",
    "can we move on",
    "i already answered",
    "you're repeating",
    "you are repeating",
    "repeating yourself",
)

_CONTROL_KEYS = {
    "concept_id",
    "strategy",
    "representation",
    "concept_attempt_count",
    "diagnostic_attempt_count",
    "remediation_attempt_count",
    "repeated_question_count",
    "learner_frustration_signal",
    "attempts",
    "confirmed_understandings",
    "remaining_uncertainties",
    "active_misconceptions",
    "remediated_misconceptions",
    "questions_already_asked",
    "purposes_demonstrated",
    "purposes_asked",
    "subskills_verified",
    "evidence_types",
    "active_misconception_status",
}


def empty_control(concept_id: str = "") -> dict[str, Any]:
    return {
        "concept_id": concept_id,
        "strategy": "diagnostic",
        "representation": "verbal",
        "concept_attempt_count": 0,
        "diagnostic_attempt_count": 0,
        "remediation_attempt_count": 0,
        "repeated_question_count": 0,
        "learner_frustration_signal": False,
        "attempts": [],
        "confirmed_understandings": [],
        "remaining_uncertainties": [],
        "active_misconceptions": [],
        "remediated_misconceptions": [],
        "questions_already_asked": [],
        "purposes_demonstrated": [],
        "purposes_asked": [],
        "subskills_verified": [],
        "evidence_types": {
            "answer": False,
            "reasoning": False,
            "conceptual_model": False,
            "application": False,
            "transfer": False,
            "explanation": False,
            "retrieval": False,
        },
        "active_misconception_status": None,
    }


def normalize_control(raw: Any, *, concept_id: str = "") -> dict[str, Any]:
    base = empty_control(concept_id)
    if not isinstance(raw, dict):
        return base
    for key in _CONTROL_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(base[key], list) and isinstance(value, list):
            base[key] = value[-40:]
        elif isinstance(base[key], dict) and isinstance(value, dict):
            merged = dict(base[key])
            merged.update(value)
            base[key] = merged
        elif type(base[key]) is type(value) or key in {
            "strategy",
            "representation",
            "concept_id",
            "active_misconception_status",
        }:
            base[key] = value
    if concept_id:
        base["concept_id"] = concept_id
    if base["strategy"] not in STRATEGIES:
        base["strategy"] = "diagnostic"
    if base["representation"] not in REPRESENTATIONS:
        base["representation"] = "verbal"
    return base


def learner_frustrated(message: str) -> bool:
    text = message.lower()
    return any(phrase in text for phrase in _FRUSTRATION)


def purpose_of_message(message: str) -> str:
    text = (message or "").lower()
    if "operation" in text and ("which line" in text or "two separate" in text):
        return "transfer_pass_invoke"
    if "deleted" in text or "removed" in text or "remove `cb" in text:
        return "remove_cb"
    if "let n" in text or "inner function" in text or "closure" in text:
        return "closure_live_link"
    if "two separate answers" in text or (
        "which line" in text and ("pass" in text or "invoke" in text)
    ):
        return "identify_pass_invoke"
    if "before" in text and "after" in text and ("trace" in text or "order" in text or "cb()" in text):
        return "trace_execution"
    if "how would" in text or "router" in text and "later" in text:
        return "application"
    if "queue.push" in text or "new names" in text:
        return "transfer_pass_invoke"
    if "diagram" in text or "state:" in text:
        return "diagram"
    if "envelope" in text or "mail slot" in text or "whiteboard" in text:
        return "analogy"
    return "diagnostic"


def _append_unique(bucket: list[str], item: str) -> None:
    if item and item not in bucket:
        bucket.append(item)


def understandings_from_answer(message: str, last_tutor: str) -> list[str]:
    found: list[str] = []
    if names_passing(message):
        found.append(PASS_UNDERSTANDING)
    if names_invoking(message):
        found.append(INVOKE_UNDERSTANDING)
    if answer_shows_live_closure(message):
        found.append(CLOSURE_UNDERSTANDING)
    tutor = last_tutor.lower()
    if ("deleted" in tutor or "removed" in tutor) and re.search(
        r"\b(no|not|never|wouldn|wont|won't)\b", message.lower()
    ):
        found.append(REMOVE_UNDERSTANDING)
    return found


def purposes_from_answer(message: str, last_tutor: str) -> list[str]:
    purpose = purpose_of_message(last_tutor)
    shown: list[str] = []
    if purpose == "identify_pass_invoke":
        if names_passing(message):
            shown.append("identify_pass")
        if names_invoking(message):
            shown.append("identify_invoke")
        if names_passing(message) and names_invoking(message):
            shown.append("identify_pass_invoke")
    elif purpose == "transfer_pass_invoke":
        if names_passing(message) and names_invoking(message):
            shown.append("transfer_pass_invoke")
            shown.append("identify_pass")
            shown.append("identify_invoke")
    elif purpose == "closure_live_link" and answer_shows_live_closure(message):
        shown.append("closure_live_link")
    elif purpose == "remove_cb" and re.search(r"\b(no|not|never|wouldn)\b", message.lower()):
        shown.append("remove_cb")
    elif purpose == "trace_execution" and names_invoking(message):
        shown.append("trace_execution")
    elif purpose and purpose not in {"diagnostic"}:
        if names_passing(message) and names_invoking(message):
            shown.append(purpose)
    return shown


def callback_distinction_proved(control: dict[str, Any]) -> bool:
    confirmed = set(control.get("confirmed_understandings") or [])
    purposes = set(control.get("purposes_demonstrated") or [])
    has_both = PASS_UNDERSTANDING in confirmed and INVOKE_UNDERSTANDING in confirmed
    if not has_both and {"identify_pass", "identify_invoke"} <= purposes:
        has_both = True
    if not has_both:
        return False
    purposes = set(control.get("purposes_demonstrated") or [])
    if purposes & {"transfer_pass_invoke", "trace_execution", "remove_cb"}:
        return True
    if str(control.get("strategy") or "") in {"new_example", "verify", "verified"}:
        correct = [
            item
            for item in control.get("attempts") or []
            if item.get("result") == "correct"
            and item.get("purpose") in CALLBACK_PURPOSES | {"identify_pass", "identify_invoke"}
        ]
        return len(correct) >= 2
    return False


def closure_proved(control: dict[str, Any]) -> bool:
    confirmed = set(control.get("confirmed_understandings") or [])
    purposes = set(control.get("purposes_demonstrated") or [])
    return CLOSURE_UNDERSTANDING in confirmed or "closure_live_link" in purposes


def _concept_cares_about_functions(
    objectives: list[str] | None,
    *,
    concept_id: str = "",
    concept_title: str = "",
) -> bool:
    blob = " ".join([concept_id, concept_title, *(objectives or [])]).lower()
    return any(
        token in blob
        for token in ("callback", "closure", "later", "programming.functions", "first-class")
    )


def missing_required_evidence(
    control: dict[str, Any],
    objectives: list[str] | None,
    *,
    concept_id: str = "",
    concept_title: str = "",
) -> list[dict[str, str]]:
    """Return only the evidence this concept still needs. Empty → advance."""
    control = normalize_control(control)
    objectives = list(objectives or [])
    concept_id = concept_id or str(control.get("concept_id") or "")
    missing: list[dict[str, str]] = []
    if _concept_cares_about_functions(
        objectives, concept_id=concept_id, concept_title=concept_title
    ) and not callback_distinction_proved(control):
        missing.append(
            {
                "skill": "pass_vs_invoke",
                "why": (
                    "Need evidence you can separate passing a function from invoking it."
                ),
            }
        )
    if any("closure" in item.lower() for item in objectives) and not closure_proved(control):
        missing.append(
            {
                "skill": "closures",
                "why": (
                    "This concept still lists closures as a required learning objective. "
                    "The knowledge graph has not moved on yet."
                ),
            }
        )
    return missing


def required_conversational_evidence_satisfied(
    control: dict[str, Any],
    objectives: list[str] | None,
    *,
    concept_id: str = "",
    concept_title: str = "",
) -> bool:
    if not _concept_cares_about_functions(
        objectives, concept_id=concept_id, concept_title=concept_title
    ):
        return False
    return not missing_required_evidence(
        control,
        objectives,
        concept_id=concept_id,
        concept_title=concept_title,
    )


def apply_learner_turn(
    control: dict[str, Any],
    *,
    message: str,
    last_tutor: str,
    classified: dict[str, Any],
) -> dict[str, Any]:
    control = normalize_control(control, concept_id=str(control.get("concept_id") or ""))
    control["concept_attempt_count"] = int(control.get("concept_attempt_count") or 0) + 1
    branch = classified.get("branch")
    if control["strategy"] == "diagnostic":
        control["diagnostic_attempt_count"] = int(control["diagnostic_attempt_count"] or 0) + 1
    if branch in {"remediate", "retest"} or control["strategy"] in {
        "diagnose_gap",
        "micro_explanation",
        "guided_example",
        "new_example",
        "change_representation",
    }:
        control["remediation_attempt_count"] = int(control["remediation_attempt_count"] or 0) + 1

    if learner_frustrated(message):
        control["learner_frustration_signal"] = True

    purpose = purpose_of_message(last_tutor)
    success = branch in {
        "retest",
        "cleared",
        "proved_this",
        "closure_pass",
        "await_invoke",
        "await_pass",
    } or (
        names_passing(message) and names_invoking(message)
    ) or answer_shows_live_closure(message)
    if branch == "remediate":
        success = False
    control["attempts"] = (list(control.get("attempts") or []) + [
        {
            "question_type": purpose or "diagnostic",
            "purpose": purpose or "diagnostic",
            "result": "correct" if success and branch != "remediate" else "incorrect",
            "branch": branch,
        }
    ])[-40:]

    for item in understandings_from_answer(message, last_tutor):
        _append_unique(control["confirmed_understandings"], item)
    for item in purposes_from_answer(message, last_tutor):
        _append_unique(control["purposes_demonstrated"], item)

    misc = classified.get("misconception") or {}
    misc_id = misc.get("id") if isinstance(misc, dict) else None
    if branch == "remediate" and misc_id:
        _append_unique(control["active_misconceptions"], str(misc_id))
        if control["diagnostic_attempt_count"] >= 2:
            control["strategy"] = "diagnose_gap"
    if branch in {"cleared", "proved_this", "closure_pass"} and misc_id:
        _append_unique(control["remediated_misconceptions"], str(misc_id))
        control["active_misconceptions"] = [
            item for item in control["active_misconceptions"] if item != misc_id
        ]

    if PASS_UNDERSTANDING in control["confirmed_understandings"]:
        control["remaining_uncertainties"] = [
            item for item in control["remaining_uncertainties"] if "pass" not in item
        ]
    if INVOKE_UNDERSTANDING in control["confirmed_understandings"]:
        control["remaining_uncertainties"] = [
            item for item in control["remaining_uncertainties"] if "invoke" not in item
        ]
    if not callback_distinction_proved(control) and "caller" not in " ".join(
        control["remaining_uncertainties"]
    ):
        if misc_id in {"callback-caller-confusion", "callback-runs-when-passed"}:
            _append_unique(
                control["remaining_uncertainties"],
                "learner may confuse caller with invoker",
            )

    types = dict(control.get("evidence_types") or empty_control()["evidence_types"])
    if names_passing(message) or names_invoking(message) or answer_shows_live_closure(message):
        types["answer"] = True
    if names_passing(message) and names_invoking(message):
        types["conceptual_model"] = True
        types["reasoning"] = True
    if "transfer_pass_invoke" in (control.get("purposes_demonstrated") or []):
        types["transfer"] = True
    if "trace_execution" in (control.get("purposes_demonstrated") or []):
        types["application"] = True
    if closure_proved(control) or callback_distinction_proved(control):
        types["explanation"] = True
    control["evidence_types"] = types

    if callback_distinction_proved(control):
        _append_unique(control["subskills_verified"], "pass_vs_invoke")
    if closure_proved(control):
        _append_unique(control["subskills_verified"], "closures")

    if branch == "remediate" and misc_id:
        control["active_misconception_status"] = "suspected"
    elif branch in {"cleared", "proved_this", "closure_pass"}:
        if misc_id:
            control["active_misconception_status"] = "remediated"
    return control


def record_tutor_question(control: dict[str, Any], reply: str) -> dict[str, Any]:
    control = normalize_control(control, concept_id=str(control.get("concept_id") or ""))
    purpose = purpose_of_message(reply)
    fingerprint = " ".join(reply.split())[:180]
    asked = list(control.get("questions_already_asked") or [])
    if fingerprint and fingerprint not in asked:
        asked.append(fingerprint)
        control["questions_already_asked"] = asked[-30:]
    purposes_asked = list(control.get("purposes_asked") or [])
    if purpose:
        if purpose in purposes_asked:
            control["repeated_question_count"] = int(control["repeated_question_count"] or 0) + 1
        _append_unique(purposes_asked, purpose)
        control["purposes_asked"] = purposes_asked
    return control


def next_representation(current: str) -> str | None:
    try:
        index = REPRESENTATIONS.index(current if current in REPRESENTATIONS else "verbal")
    except ValueError:
        index = 0
    if index + 1 >= len(REPRESENTATIONS):
        return None
    return REPRESENTATIONS[index + 1]


def representation_script(misconception_id: str | None, representation: str) -> str:
    if misconception_id == "closure-copies-values" or representation == "closure":
        return _CLOSURE_REPS.get(representation) or _CLOSURE_REPS["verbal"]
    return _CALLBACK_REPS.get(representation) or _CALLBACK_REPS["verbal"]


_CALLBACK_REPS = {
    "verbal": (
        "Passing a function only stores it. Calling it is what runs it.\n\n"
        "`later(() => console.log('inside'))` gives `later` a function. "
        "`cb()` is the later — that line prints `inside`.\n\n"
        "If you deleted `cb();`, would `inside` still print?"
    ),
    "trace": (
        "Don't explain callbacks. Trace this exact order:\n\n"
        "```javascript\n"
        "function outer(cb) {\n"
        "  console.log('A');\n"
        "  cb();\n"
        "  console.log('B');\n"
        "}\n"
        "outer(() => console.log('callback'));\n"
        "```\n\n"
        "1. What value is passed into `cb`?\n"
        "2. Which line inside `outer` runs first?\n"
        "3. Which exact line causes `callback` to print?\n"
        "4. Which line runs after that?"
    ),
    "diagram": (
        "Here is the state, not another quiz in the same words:\n\n"
        "```\n"
        "call outer(fn)     →  cb is bound to fn     (nothing in fn has run)\n"
        "console.log('A')   →  prints A\n"
        "cb()               →  fn runs now           (this is the invoke)\n"
        "console.log('B')   →  prints B\n"
        "```\n\n"
        "Which row is passing, and which row is invoking?"
    ),
    "analogy": (
        "Passing a callback is handing someone a sealed envelope. "
        "Invoking it is opening the envelope.\n"
        "The person you handed it to opens it — not the person who originally "
        "gave it to them.\n\n"
        "In `outer(() => console.log('callback'));` who hands over the envelope, "
        "and which line opens it?"
    ),
    "application": (
        "Use it. A router stores a function when you register a path, and runs "
        "that function later when a request matches.\n\n"
        "Which of those two moments is passing, and which is invoking?"
    ),
}

_CLOSURE_REPS = {
    "verbal": (
        "A closure does not copy `n`. It keeps a live link to it.\n"
        "If `let n = 1` and later `n = 2`, what does the inner function print?"
    ),
    "trace": (
        "Trace this:\n\n"
        "```javascript\n"
        "function make() {\n"
        "  let n = 1;\n"
        "  return () => n;\n"
        "}\n"
        "const read = make();\n"
        "n is not in scope here, but the inner function still sees the same n.\n"
        "```\n\n"
        "If something inside `make` later set `n = 2` before you call `read`, "
        "what does `read()` return?"
    ),
    "diagram": (
        "```\n"
        "make() scope:  n ──► 1  then  n ──► 2\n"
        "inner ()      points at that same n, not a photocopy\n"
        "```\n"
        "So `read()` sees which value?"
    ),
    "analogy": (
        "A closure is a window looking at a whiteboard, not a photo of the whiteboard.\n"
        "If someone erases 1 and writes 2, what do you see through the window?"
    ),
    "application": (
        "A `createId` function returns `() => ++n` where `n` starts at 0. "
        "Why do repeated calls give 1, then 2, then 3?"
    ),
}


def teaching_branch(
    classified: dict[str, Any],
    control: dict[str, Any],
    *,
    message: str,
    last_tutor: str,
    objectives: list[str] | None = None,
    concept_title: str = "",
) -> str | None:
    """Override graph routing from learning-control memory. None = keep classified branch."""
    control = normalize_control(control)
    for item in understandings_from_answer(message, last_tutor):
        _append_unique(control["confirmed_understandings"], item)
    for item in purposes_from_answer(message, last_tutor):
        _append_unique(control["purposes_demonstrated"], item)
    branch = classified.get("branch")
    missing = missing_required_evidence(
        control,
        objectives,
        concept_id=str(control.get("concept_id") or ""),
        concept_title=concept_title,
    )
    frustrated = control["learner_frustration_signal"] or learner_frustrated(message)

    if not missing and (
        callback_distinction_proved(control) or closure_proved(control)
    ) and branch in {
        "retest",
        "remediate",
        "await_invoke",
        "await_pass",
        "cleared",
        "change_representation",
        "application_check",
        None,
        "",
    }:
        return "proved_this"

    if callback_distinction_proved(control) and branch in {
        "retest",
        "remediate",
        "await_invoke",
        "await_pass",
        "cleared",
    }:
        return "proved_this" if not missing else "missing_evidence"

    if branch == "cleared" and callback_distinction_proved(control):
        return "proved_this" if not missing else "missing_evidence"

    if frustrated:
        if not missing and (
            callback_distinction_proved(control) or closure_proved(control)
        ):
            return "proved_this"
        if missing:
            return "missing_evidence"
        return None

    if control["strategy"] == "new_example" and branch not in {
        "cleared",
        "proved_this",
        "retest",
        "await_invoke",
        "await_pass",
        "closure_pass",
        "missing_evidence",
    }:
        if not (names_passing(message) and names_invoking(message)):
            return "change_representation"

    if int(control.get("repeated_question_count") or 0) >= 2 and branch in {
        "remediate",
        "retest",
        None,
        "",
    }:
        return "change_representation"

    if control["strategy"] == "explained" and branch not in {
        "proved_this",
        "closure_pass",
        "remediate",
    }:
        return "application_check"

    if control["strategy"] == "application" and not learner_frustrated(message):
        if names_passing(message) or names_invoking(message) or "later" in message.lower():
            return "transfer_check"
        return "application_check"

    if control["strategy"] == "transfer":
        if names_passing(message) and names_invoking(message):
            return "proved_this"
        return "change_representation"

    if control["strategy"] == "change_representation" and branch not in {
        "proved_this",
        "cleared",
        "closure_pass",
        "await_invoke",
        "await_pass",
    }:
        if names_passing(message) and names_invoking(message):
            return "proved_this"
        if answer_shows_live_closure(message):
            return "closure_pass"
        return "change_representation"

    return None


def apply_tutor_move(control: dict[str, Any], branch: str) -> dict[str, Any]:
    control = normalize_control(control, concept_id=str(control.get("concept_id") or ""))
    mapping = {
        "misconception_remediation": "guided_example",
        "misconception_retest": "new_example",
        "proved_this": "verified",
        "change_representation": "change_representation",
        "application_check": "application",
        "transfer_check": "transfer",
        "misconception_cleared": "explained",
        "teach": "micro_explanation",
        "closure_pass": "explained",
        "missing_evidence": "verify",
        "next_step": str(control.get("strategy") or "diagnostic"),
        "remediate": "guided_example",
        "retest": "new_example",
        "cleared": "explained",
    }
    if branch in mapping:
        control["strategy"] = mapping[branch]
    if branch == "proved_this":
        for item in list(control.get("active_misconceptions") or []):
            _append_unique(control["remediated_misconceptions"], item)
        control["active_misconceptions"] = []
        control["remaining_uncertainties"] = [
            item
            for item in control["remaining_uncertainties"]
            if "caller" not in item and "invoke" not in item
        ]
        if control["strategy"] != "verified":
            control["strategy"] = "explained"
    return control
