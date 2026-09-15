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

_PASS_TOKENS = ("pass", "passes", "passed", "gives", "supplies", "argument")
_INVOKE_TOKENS = (
    "invoke",
    "invokes",
    "execute",
    "executes",
    "cb()",
    "calls cb",
    "calls the callback",
    "operation()",
    "calls operation",
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
    if "callback-caller-confusion" not in ids and ("callback" in blob or "invok" in blob):
        out.append(CALLBACK_CALLER_CONFUSION)
    return out


def answer_resolves_misconception(answer: str, misconception: dict[str, Any]) -> bool:
    """True when the learner now names both sides of the seeded distinction."""
    text = _norm(answer)
    if not text:
        return False
    if misconception.get("id") != "callback-caller-confusion":
        return False
    if any(phrase in text for phrase in _CALLER_CONFUSION):
        return False
    passes = any(token in text for token in _PASS_TOKENS)
    invokes = any(token in text for token in _INVOKE_TOKENS)
    return passes and invokes


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


def classify_learner_turn(
    message: str,
    raw_misconceptions: list[Any] | None,
    prior_answers: list[Any] | None,
    *,
    attempt_count_after: int,
) -> dict[str, Any]:
    """Decide whether to remediate, re-test, evaluate, or keep questioning."""
    if is_boot_message(message):
        return {"branch": None, "misconception": None, "phase": None}

    specs = normalize_misconceptions(raw_misconceptions)
    last = (list(prior_answers or []) or [{}])[-1] if prior_answers else {}
    if not isinstance(last, dict):
        last = {}

    resolved: dict[str, Any] | None = None
    for item in specs:
        if answer_resolves_misconception(message, item):
            resolved = item
            break

    if resolved:
        last_id = last.get("misconception_id")
        last_phase = last.get("phase")
        if last_id == resolved["id"] and last_phase in {"resolved", "retest"}:
            return {"branch": "cleared", "misconception": resolved, "phase": "cleared"}
        if last_id == resolved["id"]:
            return {"branch": "retest", "misconception": resolved, "phase": "resolved"}
        return {"branch": None, "misconception": resolved, "phase": "cleared"}

    matched = match_misconception(message, raw_misconceptions)
    if matched:
        return {"branch": "remediate", "misconception": matched, "phase": "detected"}

    if attempt_count_after >= 2:
        return {
            "branch": "evaluate",
            "misconception": specs[0] if specs else None,
            "phase": "stuck",
        }
    return {"branch": None, "misconception": None, "phase": None}
