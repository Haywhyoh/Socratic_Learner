"""Match learner answers to seeded concept misconceptions.

The curriculum graph owns the known wrong models. The mentor should not
improvise a new Socratic question when a known misconception is firing —
it should name the distinction and run the seeded remediation.
"""

from __future__ import annotations

import re
from typing import Any

_WS = re.compile(r"[^a-z0-9\s]+")

_BOOT_MESSAGES = {
    "what should i think about first?",
    "what should i think about first",
}

_PASS_TOKENS = ("pass", "passes", "passed", "passing", "gives", "supplies", "argument")
_PASS_RE = re.compile(r"\b(pass(?:es|ed|ing)?|gives|supplies|argument)\b")
_INVOKE_TOKENS = (
    "invoke",
    "invokes",
    "invoking",
    "execute",
    "executes",
    "executing",
    "calling",
    "calls",
    "cb()",
    "calls cb",
    "call cb",
    "calls the callback",
    "operation()",
    "calls operation",
    "runs it",
    "run it",
)
_INVOKE_RE = re.compile(
    r"\b(invoke[sd]?|invoking|execut(?:e|es|ing)|calls|calling|runs it|run it)\b"
)
_CALLER_CONFUSION = (
    "person who called",
    "who called myfunction",
    "the caller of myfunction",
    "the one that called",
)

CALLBACK_CALLER_CONFUSION: dict[str, Any] = {
    "id": "callback-caller-confusion",
    "description": (
        "The learner confuses passing a callback with invoking it: they think "
        "the caller of the outer function is what executes the callback."
    ),
    "signals": [
        "the person who called",
        "who called myfunction",
        "the caller of myfunction",
        "the one that called myfunction",
        "the person who called myfunction",
        "because we have the callback function line called next",
        "the caller executes the callback",
        "the callback runs because it appears as an argument",
    ],
    "diagnostic_questions": [
        "Which line passes the function?",
        "Which line invokes the function?",
        "What happens if cb() is removed?",
    ],
    "remediation": {
        "type": "trace_execution",
        "script": (
            "I think we've found the part that's unclear.\n\n"
            "You're distinguishing when `myFunction` is called, but we're asking "
            "when the *callback itself* is called. Those are two different events.\n\n"
            "```javascript\n"
            "function myFunction(cb) {\n"
            "  console.log('before');\n"
            "  cb();\n"
            "  console.log('after');\n"
            "}\n"
            "myFunction(() => console.log('inside'));\n"
            "```\n\n"
            "Two separate answers, please — don't merge them:\n"
            "1. What does `myFunction(() => console.log('inside'))` do?\n"
            "2. What does the `cb();` line do?\n\n"
            "If the execution order (before → inside → after) was already clear, "
            "keep that. The remaining error is *who invokes* the callback."
        ),
        "retest_script": (
            "Exactly. Passing and invoking are different events.\n\n"
            "Now prove you can see that without the parameter being named `cb`:\n\n"
            "```javascript\n"
            "function run(operation) {\n"
            "  console.log('start');\n"
            "  operation();\n"
            "  console.log('end');\n"
            "}\n"
            "run(() => console.log('work'));\n"
            "```\n\n"
            "Two separate answers:\n"
            "1. Which line passes the function?\n"
            "2. Which line invokes it?"
        ),
        "teach_script": (
            "You traced the order correctly: before → inside → after.\n\n"
            "That order is the mechanism. Passing and invoking are different events.\n\n"
            "`myFunction(() => console.log('inside'))` only gives `myFunction` a function. "
            "Nothing inside that arrow function runs yet.\n\n"
            "`cb()` is the later. That is the line that prints `inside`.\n\n"
            "A callback can run 'later' because the function is stored until some other "
            "line invokes it. Closures are a different idea — we will do those next.\n\n"
            "One check: if you deleted the `cb();` line, would `inside` still print?"
        ),
    },
}


def is_boot_message(message: str) -> bool:
    return message.strip().lower().rstrip("?.!") in _BOOT_MESSAGES


def _norm(text: str) -> str:
    return " ".join(_WS.sub(" ", text.lower()).split())


def normalize_misconceptions(raw: list[Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw or []):
        if isinstance(item, str) and item.strip():
            out.append(
                {
                    "id": f"misc-{index}",
                    "description": item.strip(),
                    "signals": [item.strip()],
                    "diagnostic_questions": [],
                    "remediation": {"type": "targeted_question"},
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        signals = [str(s).strip() for s in (item.get("signals") or []) if str(s).strip()]
        remediation = item.get("remediation")
        out.append(
            {
                "id": str(item.get("id") or f"misc-{index}"),
                "description": description,
                "signals": signals or [description],
                "diagnostic_questions": [
                    str(q).strip()
                    for q in (item.get("diagnostic_questions") or [])
                    if str(q).strip()
                ],
                "remediation": remediation if isinstance(remediation, dict) else {"type": "targeted_question"},
            }
        )
    ids = {item["id"] for item in out}
    blob = " ".join(item["description"].lower() for item in out)
    if "callback-caller-confusion" not in ids and "callback" in blob:
        out.append(CALLBACK_CALLER_CONFUSION)
    return out


def names_passing(answer: str) -> bool:
    raw = answer.lower()
    text = _norm(answer)
    if "later(" in raw or "myfunction(" in raw or "run(" in raw:
        if _PASS_RE.search(text):
            return True
    return bool(_PASS_RE.search(text))


def names_invoking(answer: str) -> bool:
    raw = answer.lower()
    if "cb()" in raw or "operation()" in raw:
        return True
    text = _norm(answer)
    if _INVOKE_RE.search(text):
        return True
    return bool(re.search(r"\bcb\b", text)) and any(
        token in text for token in ("call", "calling", "invoke", "run", "line")
    )


def last_tutor_asks_closures(message: str) -> bool:
    text = message.lower()
    return any(
        phrase in text
        for phrase in ("closure", "let n", "inner function", "live link", "captures")
    )


def last_tutor_asks_pass_invoke(message: str) -> bool:
    text = message.lower()
    if "two separate answers" in text:
        return True
    return "which line" in text and bool(
        re.search(r"\b(pass(?:es|ed|ing)?|invoke[sd]?|invoking)\b", text)
    )


def answer_shows_live_closure(answer: str) -> bool:
    text = _norm(answer)
    if not text:
        return False
    if re.search(r"\b1\b", text) and not re.search(r"\b2\b", text):
        return False
    if "copy" in text and "2" not in text:
        return False
    return bool(re.search(r"\b2\b", text))


def answer_resolves_misconception(answer: str, misconception: dict[str, Any]) -> bool:
    """True when the learner now names both sides of the seeded distinction."""
    if not answer.strip():
        return False
    misc_id = misconception.get("id")
    if misc_id == "closure-copies-values":
        return answer_shows_live_closure(answer)
    if misc_id not in {"callback-caller-confusion", "callback-runs-when-passed"}:
        return False
    if any(phrase in _norm(answer) for phrase in _CALLER_CONFUSION):
        return False
    traced = all(word in _norm(answer) for word in ("before", "inside", "after")) and names_invoking(answer)
    named = names_passing(answer) and names_invoking(answer)
    return traced or named


def match_misconception(answer: str, raw_misconceptions: list[Any] | None) -> dict[str, Any] | None:
    if is_boot_message(answer):
        return None
    text = _norm(answer)
    if not text:
        return None
    best: dict[str, Any] | None = None
    best_hits = 0
    for item in normalize_misconceptions(raw_misconceptions):
        if answer_resolves_misconception(answer, item):
            continue
        hits = 0
        for signal in item["signals"]:
            needle = _norm(str(signal))
            if len(needle) >= 6 and needle in text:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best = item
    return best if best_hits else None


def remediation_script(misconception: dict[str, Any]) -> str:
    script = (misconception.get("remediation") or {}).get("script")
    if isinstance(script, str) and script.strip():
        return script.strip()
    questions = misconception.get("diagnostic_questions") or []
    asked = "\n".join(f"{i}. {q}" for i, q in enumerate(questions[:3], start=1))
    return (
        f"I think we've found the part that's unclear.\n\n"
        f"{misconception['description']}\n\n"
        "Let's isolate that — don't move on yet.\n"
        + (asked or "Say it again using the exact line of code that does each action.")
    )


def retest_script(misconception: dict[str, Any]) -> str:
    script = (misconception.get("remediation") or {}).get("retest_script")
    if isinstance(script, str) and script.strip():
        return script.strip()
    questions = misconception.get("diagnostic_questions") or []
    asked = "\n".join(questions[:2]) if questions else (
        "Which line passes the function, and which line invokes it?"
    )
    return (
        "Exactly. Passing and invoking are different events.\n\n"
        "Now test the same distinction in a new example — don't reuse the previous wording.\n\n"
        f"{asked}"
    )


def teach_script(misconception: dict[str, Any]) -> str:
    script = (misconception.get("remediation") or {}).get("teach_script")
    if isinstance(script, str) and script.strip():
        return script.strip()
    return (
        f"{misconception.get('description') or 'Here is the mechanism in the smallest form.'}\n\n"
        "Passing a function only stores it. `cb()` is the line that actually runs it.\n"
        "If you deleted `cb();`, the callback would never run."
    )


def uncovered_objectives(objectives: list[str], answer: str) -> list[str]:
    text = _norm(answer)
    leftover: list[str] = []
    for objective in objectives:
        lower = objective.lower()
        if "closure" in lower:
            if answer_shows_live_closure(answer) or "closure" in text or "capture" in text:
                continue
            leftover.append(objective)
    return leftover


def classify_learner_turn(
    message: str,
    raw_misconceptions: list[Any] | None,
    prior_answers: list[Any] | None,
    *,
    attempt_count_after: int,
    last_tutor_message: str = "",
    control: dict[str, Any] | None = None,
    objectives: list[str] | None = None,
    concept_title: str = "",
    concept_id: str = "",
) -> dict[str, Any]:
    """Decide whether to remediate, re-test, evaluate, or keep questioning."""
    from app.agents.learning_control import has_evidence_ledger, teaching_branch
    from app.agents.policies import asks_for_mentor_explanation, asks_what_next

    if is_boot_message(message) or (
        asks_for_mentor_explanation(message) and not asks_what_next(message)
    ):
        return {"branch": None, "misconception": None, "phase": None}

    live_id = concept_id or str((control or {}).get("concept_id") or "")
    ledger = has_evidence_ledger(
        objectives,
        concept_id=live_id,
        concept_title=concept_title,
    )
    specs = normalize_misconceptions(raw_misconceptions)
    by_id = {item["id"]: item for item in specs}
    last = (list(prior_answers or []) or [{}])[-1] if prior_answers else {}
    if not isinstance(last, dict):
        last = {}
    callback_misc = (
        by_id.get("callback-caller-confusion")
        or by_id.get("callback-runs-when-passed")
        or (specs[0] if ledger and specs else None)
    )
    closure_misc = by_id.get("closure-copies-values")

    result: dict[str, Any]
    if (
        ledger
        and last_tutor_asks_closures(last_tutor_message)
        and answer_shows_live_closure(message)
    ):
        result = {
            "branch": "closure_pass",
            "misconception": closure_misc,
            "phase": "cleared",
        }
    else:
        resolved: dict[str, Any] | None = None
        for item in specs:
            if answer_resolves_misconception(message, item):
                resolved = item
                break
        if resolved:
            last_phase = last.get("phase")
            if last_phase in {"resolved", "retest"} or "operation" in last_tutor_message.lower():
                result = {"branch": "cleared", "misconception": resolved, "phase": "cleared"}
            else:
                result = {"branch": "retest", "misconception": resolved, "phase": "resolved"}
        else:
            asked_pass_invoke = ledger and (
                last_tutor_asks_pass_invoke(last_tutor_message)
                or last.get("phase") in {
                    "detected",
                    "stuck",
                    "resolved",
                }
            )
            if asked_pass_invoke and names_passing(message) and not names_invoking(message):
                result = {
                    "branch": "await_invoke",
                    "misconception": callback_misc,
                    "phase": last.get("phase") or "detected",
                }
            elif asked_pass_invoke and names_invoking(message) and not names_passing(message):
                result = {
                    "branch": "await_pass",
                    "misconception": callback_misc,
                    "phase": last.get("phase") or "detected",
                }
            else:
                matched = match_misconception(message, raw_misconceptions)
                if matched and (
                    ledger
                    or str(matched.get("id") or "")
                    not in {"callback-caller-confusion", "callback-runs-when-passed", "closure-copies-values"}
                ):
                    result = {"branch": "remediate", "misconception": matched, "phase": "detected"}
                else:
                    result = {"branch": None, "misconception": None, "phase": None}

    override = teaching_branch(
        result,
        control or {},
        message=message,
        last_tutor=last_tutor_message,
        objectives=objectives,
        concept_title=concept_title,
        concept_id=live_id,
    )
    if override:
        result["branch"] = override
        if override == "proved_this" and callback_misc:
            result["misconception"] = result.get("misconception") or callback_misc
            result["phase"] = "cleared"
    return result
