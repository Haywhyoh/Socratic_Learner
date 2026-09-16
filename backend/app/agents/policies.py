"""Deterministic coaching policy: planner mapping, hint gating, output filter."""

from __future__ import annotations

import re
from typing import Any

from app.agents.build_coach import replacement_for_stripped_dump
from app.agents.state import EffortSignals

HINT_LEVELS = {
    0: "question",
    1: "direction",
    2: "concept",
    3: "structure",
    4: "targeted",
}

MAX_HINT_LEVEL = 4
MAX_QUESTION_ATTEMPTS = 3
"""How many times a pre-code question can be pushed back before the coach
notes the gap and moves the learner on, rather than rephrasing forever."""

MAX_REVIEW_ATTEMPTS = 3
"""How many post-milestone review cycles before the coach notes remaining
gaps and lets the learner proceed, rather than blocking indefinitely."""
SOLUTION_FENCE_LINES = 8
_MINI_EXAMPLE_LINES = 14
_FENCE_RE = re.compile(r"```[\w+-]*\n(.*?)```", re.DOTALL)
_ATTEMPT_MARKERS = (
    "i tried",
    "i attempted",
    "my approach",
    "i implemented",
    "i tested",
    "it failed",
    "the error",
)


def explain_gap_reason(reason: str, *, concept_id: str, requires_id: str) -> str:
    """Render why the learner is being sent backward (spec §26 / §28)."""
    if reason:
        return (
            f"Before we move forward, '{requires_id}' is still unclear — {reason} "
            f"We'll stay with that instead of jumping to '{concept_id}'."
        )
    return (
        f"Before we move forward, your work on '{concept_id}' suggests "
        f"'{requires_id}' is still shaky. Let's investigate that."
    )


def asks_for_implementation(message: str) -> bool:
    lower = message.lower()
    return any(
        phrase in lower
        for phrase in (
            "give me the code",
            "write the code",
            "paste the code",
            "give me the implementation",
            "just give me the",
            "generate the code",
            "write it for me",
        )
    )


def asks_for_practice_eval(message: str) -> bool:
    lower = (message or "").strip().lower()
    return any(
        phrase in lower
        for phrase in (
            "check my work",
            "check this",
            "evaluate my",
            "grade my",
            "i'm done",
            "i am done",
            "done with the file",
            "please check",
            "run my file",
        )
    ) or lower in {"done", "check", "evaluate"}


def has_genuine_effort(effort: EffortSignals) -> bool:
    return bool(
        effort.get("learner_turns_since_hint", 0) >= 1
        or effort.get("checkpoint_since_hint")
        or effort.get("attempt_message")
        or effort.get("tested_attempt")
    )


def message_looks_like_attempt(message: str) -> bool:
    text = message.strip()
    if len(text) >= 120:
        return True
    lower = text.lower()
    return any(marker in lower for marker in _ATTEMPT_MARKERS)


def next_hint_level(current_level: int, effort: EffortSignals) -> tuple[int, str | None]:
    """Return (level_to_emit, blocked_reason). current_level is max already revealed, or -1."""
    if current_level < 0:
        return 0, None
    if current_level >= MAX_HINT_LEVEL:
        return MAX_HINT_LEVEL, "already_max"
    if not has_genuine_effort(effort):
        return current_level, "need_effort"
    return current_level + 1, None


def asks_what_next(message: str) -> bool:
    collapsed = " ".join(message.lower().split())
    return any(
        phrase in collapsed
        for phrase in (
            "what next",
            "what's next",
            "whats next",
            "what now",
            "where to next",
            "next step",
            "what do i do now",
            "what should i do next",
            "can we move on",
            "i already answered",
            "we keep going over",
            "keep going over the same",
            "you're repeating",
            "you are repeating",
            "repeating yourself",
        )
    )


def asks_for_mentor_explanation(message: str) -> bool:
    if asks_what_next(message):
        return False
    collapsed = " ".join(message.lower().split())
    return any(
        phrase in collapsed
        for phrase in (
            "can you explain",
            "could you explain",
            "please explain",
            "explain it",
            "explain this",
            "explain how",
            "explain why",
            "i don't get it",
            "i dont get it",
            "what does that mean",
            "i don't understand",
            "i dont understand",
        )
    )


def classify_intent(message: str) -> str:
    lower = message.lower().strip()
    if asks_for_implementation(message):
        return "code_ask"
    if asks_what_next(message) or asks_for_mentor_explanation(message):
        return "guidance"
    if any(word in lower for word in ("hint", "stuck", "clue", "give me a hint")):
        return "hint"
    if any(word in lower for word in ("i researched", "my notes", "i looked up", "research")):
        return "research"
    if "skip" in lower and any(w in lower for w in ("this", "tcp", "concept", "can i")):
        return "skip"
    guidance_markers = (
        "how do i",
        "how do you",
        "how to",
        "how can i",
        "how should i",
        "what should i",
        "where should",
        "where do i",
        "help me",
        "get started",
        "getting started",
        "create a clean",
        "project layout",
        "what next",
        "what's next",
        "walk me through",
        "guide me",
        "can you explain",
        "explain it",
        "explain this",
        "explain how",
        "so what next",
        "start with",
    )
    if any(marker in lower for marker in guidance_markers) or (
        lower.endswith("?") and any(
            lower.startswith(w) for w in ("how", "what", "where", "which", "why")
        )
    ):
        return "guidance"
    return "answer"


def parse_instruction_tasks(instructions: str) -> list[str]:
    """Pull numbered/bulleted steps out of milestone instructions."""
    tasks: list[str] = []
    for line in (instructions or "").splitlines():
        match = re.match(r"^\s*(?:\d+[.)]\s+|[-*]\s+)(.+)$", line)
        if match:
            text = match.group(1).strip()
            if text:
                tasks.append(text)
    return tasks


def fallback_card(
    concept: str,
    milestone_title: str,
    resources: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "name": concept,
        "why_it_matters": (
            f"{concept} is what makes '{milestone_title}' a real engineering problem, "
            "not just busywork."
        ),
        "research_questions": [
            f"What problem does {concept} solve in this milestone?",
            f"What goes wrong if you skip {concept}?",
            "Where would you look it up in official docs first?",
        ],
        "resources": resources[:3],
        "checkpoint": (
            f"In your own words, what is {concept} and how will you use it in "
            f"'{milestone_title}'?"
        ),
        "explanation": (
            f"Read just enough about {concept} to explain it back. Do not wait for a lecture."
        ),
    }


def pose_question(questions: list[str], question_index: int) -> str | None:
    if question_index < 0 or question_index >= len(questions):
        return None
    return questions[question_index]


def go_build_reply(
    *,
    constraints: list[str],
    success_criteria: str,
    instructions: str = "",
    milestone_title: str = "",
) -> str:
    """Kick the learner into the build phase with a concrete first task — no code dump."""
    constraint = constraints[0] if constraints else "follow the project constraints"
    success = success_criteria or "meet the milestone success criteria"
    tasks = parse_instruction_tasks(instructions)
    title = milestone_title or "this milestone"
    if tasks:
        first = tasks[0]
        return (
            f"Go build. First task: {first} "
            f"Constraint: {constraint}. Success: {success}. "
            "Ask a specific question about the next command or file you need — "
            "I will not paste the full app."
        )
    return (
        f"Go build on '{title}'. Constraint: {constraint}; success: {success}. "
        "Ask what to run or create next if you are unsure."
    )


def guidance_reply(
    *,
    message: str,
    milestone_title: str,
    instructions: str = "",
    constraints: list[str] | None = None,
    success_criteria: str = "",
    project_title: str = "",
) -> str:
    """Stub mentor help when no LLM is configured. Prefer commands over slogans."""
    lower = message.lower()
    tasks = parse_instruction_tasks(instructions)
    title = milestone_title or "this milestone"
    success = success_criteria or "meet the milestone success criteria"
    pkg = "app"
    named = re.search(
        r"(?:named|called|package|project)\s+[\"']?([a-zA-Z_][\w]*)[\"']?",
        message,
        re.IGNORECASE,
    )
    if named:
        pkg = named.group(1).lower()
    elif re.search(r"\bscaffold\b", lower):
        pkg = "scaffold"

    beginner_first = any(
        phrase in lower
        for phrase in (
            "first thing",
            "first step",
            "where do i start",
            "what do i do",
            "don't know",
            "dont know",
            "beginner",
            "getting started",
            "get started",
            "clean project",
            "create a project",
            "create the api",
            "scaffold",
            "how do i",
            "how to",
            "next command",
            "which command",
            "what command",
            "command",
            "mkdir",
            "touch",
            "terminal",
            "create",
        )
    )
    if beginner_first:
        return (
            f"First thing: create the package folders in the terminal (nothing fancy yet).\n"
            f"mkdir -p {pkg}\n"
            f"touch {pkg}/__init__.py {pkg}/main.py {pkg}/config.py\n"
            f"Then open {pkg}/main.py in the editor and add a FastAPI app with GET /health "
            f"returning {{\"status\": \"ok\"}}. "
            f"After that, smoke-test with: uvicorn {pkg}.main:app --host 127.0.0.1 --port 8000 "
            f"(it will time out here — that still means it started). "
            f"Milestone '{title}' success: {success}."
        )
    if tasks:
        return (
            f"You're on '{title}'. Next concrete step: {tasks[0]}\n"
            f"If you need the first commands: mkdir -p {pkg} && "
            f"touch {pkg}/__init__.py {pkg}/main.py {pkg}/config.py\n"
            "Tell me the exact error if a command fails."
        )
    return (
        f"Start in the terminal with mkdir/touch for package `{pkg}`, "
        f"then edit main.py for /health. Success for '{title}': {success}."
    )


def fallback_evaluate(question: str, answer: str) -> dict[str, object]:
    """Stub evaluator: short answers fail; substantive answers pass."""
    cleaned = answer.strip()
    if len(cleaned) < 20 or cleaned.lower() in {"idk", "dunno", "pass", "yes", "no"}:
        return {
            "passed": False,
            "push_back": "Not enough. Answer the question in one clear sentence.",
        }
    # Reject obvious non-answers that just repeat the question
    if cleaned.rstrip("?").lower() == question.rstrip("?").lower():
        return {
            "passed": False,
            "push_back": "That restates the question. What is your answer?",
        }
    return {"passed": True, "push_back": None}


def fallback_hint(level: int, milestone_title: str, concepts: list[str], instructions: str = "") -> str:
    concept = concepts[0] if concepts else "the core idea"
    tasks = parse_instruction_tasks(instructions)
    first_task = tasks[0] if tasks else None
    templates = {
        0: (
            f"Which numbered task in '{milestone_title}' are you on"
            + (f" — starting from '{first_task}'?" if first_task else "?")
        ),
        1: (
            f"Direction: finish task 1 first"
            + (f" ({first_task})" if first_task else "")
            + f" before jumping ahead in '{milestone_title}'."
        ),
        2: f"Concept: this milestone hinges on {concept}. Research that, then return with your plan.",
        3: (
            "Structure (no full app dump): package folder → config module → main entrypoint "
            "with FastAPI app → GET /health → prove with uvicorn."
        ),
        4: (
            f"Targeted: implement only the missing piece for {concept} / "
            f"the current task, then re-check the success criteria for '{milestone_title}'."
        ),
    }
    return templates.get(level, templates[0])


def fallback_card_reply(cards: list[dict]) -> str:
    if not cards:
        return "No cards yet. Ask about the command or file you're stuck on."
    card = cards[0]
    return f"{card['name']}: {card['why_it_matters']} Checkpoint: {card['checkpoint']}"


def enforce_brevity(text: str, *, max_sentences: int = 2) -> str:
    """Keep coach replies abrupt: at most max_sentences.

    Multi-line instructional replies (commands / tiny examples) are kept intact.
    """
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if "\n" in cleaned:
        return cleaned
    collapsed = " ".join(cleaned.split())
    parts = re.split(r"(?<=[.!?])\s+", collapsed)
    return " ".join(parts[:max_sentences]).strip()


def _looks_like_full_app(body: str) -> bool:
    """True for a pasted solution / whole server — not a tiny teaching snippet."""
    line_count = body.count("\n") + 1
    route_count = len(
        re.findall(r"\b(?:app|router)\.(get|post|put|patch|delete|use)\b", body, re.I)
    )
    has_models = bool(re.search(r"\b(class \w+\(.*Base|SQLAlchemy|create_engine)\b", body))
    has_crud = bool(
        re.search(r"\b(Session|Depends|HTTPException|oauth2|JWT|password)\b", body, re.I)
    )
    js_server = bool(re.search(r"\bcreateServer\b", body) and re.search(r"\b\.listen\b", body))
    if line_count > _MINI_EXAMPLE_LINES and (route_count >= 2 or has_models or has_crud or js_server):
        return True
    if line_count >= SOLUTION_FENCE_LINES * 2:
        return True
    if route_count >= 3:
        return True
    if js_server and route_count >= 1 and line_count > 10:
        return True
    return False


def _strip_solution_fences(
    text: str,
    *,
    allow_mini_examples: bool = True,
    resources: list[dict[str, str]] | None = None,
) -> tuple[str, bool]:
    """Remove oversized solution dumps, but keep surrounding instructions.

    Tiny fenced snippets (a handful of lines) are teaching examples and stay.
    """
    stripped = False

    def replacer(match: re.Match[str]) -> str:
        nonlocal stripped
        body = match.group(1)
        line_count = body.count("\n") + 1
        lang = (match.group(0).split("\n", 1)[0] or "").lower()
        is_shell = any(x in lang for x in ("bash", "sh", "shell", "zsh", "console")) or (
            line_count <= 8
            and all(
                (not ln.strip())
                or ln.strip().startswith(
                    ("mkdir", "touch", "python", "uvicorn", "pytest", "pip", "ls", "cd ",
                     "node", "npm", "npx", "#")
                )
                for ln in body.splitlines()
            )
        )
        if is_shell:
            return match.group(0)
        if allow_mini_examples and line_count <= _MINI_EXAMPLE_LINES and not _looks_like_full_app(body):
            if "[project]" in body.lower() or (
                "dependencies" in body.lower() and len(body) > 200
            ):
                stripped = True
                return "\n" + replacement_for_stripped_dump(body, resources=resources) + "\n"
            return match.group(0)
        if _looks_like_full_app(body) or line_count >= SOLUTION_FENCE_LINES or (
            "[project]" in body.lower() or (line_count >= 6 and "dependencies" in body.lower())
        ):
            stripped = True
            return "\n" + replacement_for_stripped_dump(body, resources=resources) + "\n"
        return match.group(0)

    return _FENCE_RE.sub(replacer, text), stripped


def filter_specialist_reply(
    reply: str,
    *,
    later_concepts: list[str],
    allow_code: bool = False,
    allow_commands: bool = False,
    allow_mini_examples: bool = True,
    max_sentences: int = 2,
    resources: list[dict[str, str]] | None = None,
) -> tuple[str, list[str]]:
    flags: list[str] = []
    text = enforce_brevity(reply, max_sentences=max_sentences)
    if not allow_code:
        # Commands (shell fences) always pass; teaching snippets pass when
        # allow_mini_examples is on. Full solutions still get stripped.
        text, stripped = _strip_solution_fences(
            text,
            allow_mini_examples=allow_mini_examples or allow_commands,
            resources=resources,
        )
        if stripped:
            flags.append("stripped_solution")
    for concept in later_concepts:
        if concept and concept.lower() in text.lower():
            flags.append("blocked_later_concept")
            pattern = re.compile(re.escape(concept), re.IGNORECASE)
            text = pattern.sub("[later]", text)
    return enforce_brevity(text, max_sentences=max_sentences), flags


def checkpoint_passes(answer: str) -> bool:
    cleaned = answer.strip()
    return len(cleaned) >= 40 and "idk" not in cleaned.lower()


REVIEW_DIMENSIONS = (
    "correctness",
    "architecture",
    "readability",
    "complexity",
    "reliability",
    "testing",
)


def fallback_curriculum(catalog: list[dict]) -> list[dict]:
    """Deterministic curriculum used in tests / when no model is configured.

    Clones the project's seeded catalog outline verbatim (so behavior matches
    today's static milestones). When a real LLM is configured this is only
    the safety-net fallback if generation fails — the LLM path in
    ``LangChainCoachLLM.generate_curriculum`` produces the actual AI-generated,
    learner-tailored curriculum.
    """
    if catalog:
        return [
            {
                "title": item["title"],
                "description": item["description"],
                "instructions": item.get("instructions", ""),
                "success_criteria": item["success_criteria"],
                "concepts": list(item.get("concepts") or []),
                "questions": list(item.get("questions") or []),
            }
            for item in catalog
        ]
    return [
        {
            "title": "Scaffold the project",
            "description": "Stand up a runnable skeleton so progress can be verified from step one.",
            "instructions": (
                "What to do:\n"
                "1. Create a clean project layout and entrypoint.\n"
                "2. Add a health/status check you can run immediately.\n"
                "3. Confirm the app starts cleanly."
            ),
            "success_criteria": "The app starts cleanly and a basic status check succeeds.",
            "concepts": ["Project layout", "Configuration"],
            "questions": [
                "What does 'runnable from step one' buy you as you keep building?",
            ],
        },
        {
            "title": "Core data and behavior",
            "description": "Implement the primary data model and the operations that make the project useful.",
            "instructions": (
                "What to do:\n"
                "1. Define the core data model.\n"
                "2. Implement create/read operations against it.\n"
                "3. Add at least one automated test."
            ),
            "success_criteria": "The core operation works end-to-end and is covered by a test.",
            "concepts": ["Data modeling", "Automated testing"],
            "questions": [
                "Why test this now instead of waiting until the project is 'done'?",
            ],
        },
        {
            "title": "Harden and finish",
            "description": "Close the gaps: validation, error handling, and the project's stated success criteria.",
            "instructions": (
                "What to do:\n"
                "1. Add input validation and sensible error responses.\n"
                "2. Verify the project's tests/evaluation criteria pass.\n"
                "3. Document how to run it."
            ),
            "success_criteria": "The project meets its stated tests and evaluation criteria.",
            "concepts": ["Error handling", "Reliability"],
            "questions": [
                "What's the difference between 'it works on my machine' and 'it's reliable'?",
            ],
        },
    ]


def fallback_review(
    *, code_bundle: str, tests_passed: bool, milestone_title: str
) -> dict[str, object]:
    """Deterministic reviewer used in tests / when no model is configured."""
    has_code = len(code_bundle.strip()) >= 40
    rating = "pass" if has_code and tests_passed else "concern" if has_code else "fail"
    dimensions = {
        dim: {
            "rating": rating,
            "notes": (
                f"{dim.capitalize()} looks reasonable for '{milestone_title}'."
                if rating == "pass"
                else f"Can't confirm {dim} yet for '{milestone_title}' — get tests green first."
            ),
        }
        for dim in REVIEW_DIMENSIONS
    }
    understanding_questions = [
        (
            f"In your own words, walk through how your implementation of "
            f"'{milestone_title}' works, and why you structured it that way."
        )
    ]
    return {
        "dimensions": dimensions,
        "summary": (
            "Tests are green — reviewing your implementation."
            if tests_passed
            else "Get your tests passing before requesting a review."
        ),
        "understanding_questions": understanding_questions if rating != "fail" else [],
    }


def fallback_understanding(question: str, answer: str) -> dict[str, object]:
    cleaned = answer.strip()
    if len(cleaned) < 25 or cleaned.lower() in {"idk", "dunno", "pass", "yes", "no"}:
        return {
            "passed": False,
            "feedback": "Too short — explain your actual implementation choice, not just the outcome.",
        }
    return {"passed": True, "feedback": None}


def fallback_explanation(answer: str) -> dict[str, Any]:
    cleaned = answer.strip()
    weak = len(cleaned) < 40 or cleaned.lower() in {"idk", "dunno", "pass", "yes", "no"}
    return {
        "passed": not weak,
        "accuracy": 0.0 if weak else 0.7,
        "completeness": 0.0 if weak else 0.7,
        "clarity": 0.0 if weak else 0.7,
        "causal": 0.0 if weak else 0.6,
        "feedback": (
            "Too thin — explain the cause, not just the name of the concept."
            if weak
            else "That's enough to work with."
        ),
    }


def fallback_mentor_contract(
    context: dict[str, Any], message: str, action_hint: str
) -> dict[str, Any]:
    title = context.get("concept_title") or context.get("current_concept") or "this"
    questions = list(context.get("diagnostic_questions") or [])
    research = list(context.get("research_questions") or [])
    status = context.get("concept_state") or "available"
    if action_hint == "RESEARCH" or status == "researching":
        listed = "\n".join(f"{i}. {q}" for i, q in enumerate(research[:3], start=1))
        return {
            "intent": "MENTOR",
            "action": "ASK_RESEARCH",
            "message": (
                f"Research '{title}' before I explain it. Write your own understanding.\n"
                + (listed or f"What is {title}?")
            ),
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "researching",
        }
    if action_hint == "IMPLEMENTATION":
        tasks = list(context.get("practice_tasks") or [])
        task = tasks[0] if tasks and isinstance(tasks[0], dict) else None
        filename = str((task or {}).get("filename") or "").strip()
        prompt = str((task or {}).get("prompt") or "").strip()
        if filename:
            body = (
                f"Write this in `{filename}`:\n\n"
                f"{prompt or 'The smallest version of this concept you can.'}\n\n"
                "I will not edit your files. When it runs, click Check my work or tell me you're done."
            )
        else:
            body = (
                f"Build the smallest version of '{title}' you can. I will not edit your files. "
                "When something runs, tell me what you tried."
            )
        return {
            "intent": "MENTOR",
            "action": "ASK_IMPLEMENTATION",
            "message": body,
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "attempted",
            "assigned_file": filename or None,
            "practice_task_id": str((task or {}).get("id") or "") or None,
        }
    if action_hint == "PRACTICE_EVAL":
        return {
            "intent": "MENTOR",
            "action": "PRACTICE_EVAL",
            "message": (
                "I looked at the file you were assigned. Tell me what you changed if this still fails."
            ),
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "attempted",
            "assigned_file": context.get("assigned_file"),
            "practice_task_id": context.get("practice_task_id"),
        }
    if action_hint == "DIAGNOSE":
        q = questions[0] if questions else f"What does '{title}' represent to you?"
        return {
            "intent": "DIAGNOSE",
            "action": "ASK_DIAGNOSTIC_QUESTION",
            "message": q,
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "diagnosis",
        }
    if action_hint in {"REMEDIATE", "ASK_DIAGNOSTIC_QUESTION"}:
        misc = context.get("identified_misconception") or {}
        description = ""
        if isinstance(misc, dict):
            description = str(misc.get("description") or "")
            script = (misc.get("remediation") or {}).get("script") if isinstance(misc.get("remediation"), dict) else None
            if isinstance(script, str) and script.strip():
                message_out = script.strip()
            else:
                message_out = (
                    "I think we've found the part that's unclear.\n\n"
                    f"{description or 'You are mixing two different actions.'}\n"
                    "Which exact line of code does each action?"
                )
        else:
            message_out = (
                "I think we've found the part that's unclear. "
                "Which exact line of code does the action you just described?"
            )
        return {
            "intent": "DIAGNOSE",
            "action": "ASK_DIAGNOSTIC_QUESTION",
            "message": message_out,
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "discussing",
        }
    if action_hint == "RETEST":
        misc = context.get("identified_misconception") or {}
        script = None
        if isinstance(misc, dict) and isinstance(misc.get("remediation"), dict):
            script = misc["remediation"].get("retest_script")
        message_out = (
            script.strip()
            if isinstance(script, str) and script.strip()
            else (
                "Exactly. Now test the same distinction in a new example.\n"
                "Which line passes the function, and which line invokes it?"
            )
        )
        return {
            "intent": "DIAGNOSE",
            "action": "ASK_DIAGNOSTIC_QUESTION",
            "message": message_out,
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "discussing",
        }
    if action_hint == "TEACH":
        misc = context.get("identified_misconception") or {}
        script = None
        if isinstance(misc, dict) and isinstance(misc.get("remediation"), dict):
            script = misc["remediation"].get("teach_script") or misc["remediation"].get("script")
        message_out = (
            script.strip()
            if isinstance(script, str) and script.strip()
            else (
                "A callback is stored when it is passed and runs only when some other "
                "line invokes it. Which exact line in the current example actually runs it?"
            )
        )
        return {
            "intent": "MENTOR",
            "action": "ASK_QUESTION",
            "message": message_out,
            "diagnostic_concept": None,
            "identified_gap": None,
            "hint_level": 0,
            "should_unlock": False,
            "next_state": "discussing",
        }
    opener = questions[0] if questions else f"What do you already understand about {title}?"
    if (context.get("concept_state") or "") == "available":
        opener = (
            f"Before writing code: what is '{title}' for, in your own words? "
            "Do not search yet."
        )
    return {
        "intent": "MENTOR",
        "action": "ASK_QUESTION",
        "message": opener,
        "diagnostic_concept": None,
        "identified_gap": None,
        "hint_level": 0,
        "should_unlock": False,
        "next_state": "introduced",
    }
