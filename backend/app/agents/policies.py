"""Deterministic coaching policy: planner mapping, hint gating, output filter."""

from __future__ import annotations

import difflib
import re

from app.agents.state import (
    CardDraft,
    CatalogMilestone,
    EffortSignals,
    RoadmapMilestone,
)
from app.models.coach import ConceptMastery, TeachingFlag

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


def catalog_concepts(milestones: list[CatalogMilestone]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for milestone in milestones:
        for concept in milestone.get("concepts") or []:
            if concept not in seen:
                seen.add(concept)
                names.append(concept)
    return names


def assessment_questions(milestones: list[CatalogMilestone]) -> list[dict[str, str]]:
    return [
        {
            "concept": name,
            "prompt": (
                f"How well do you already understand '{name}'? "
                "Answer unknown, familiar, or can_explain."
            ),
        }
        for name in catalog_concepts(milestones)
    ]


def normalize_mastery(value: str | None) -> str:
    raw = (value or ConceptMastery.unknown.value).strip().lower().replace(" ", "_")
    aliases = {
        "know": ConceptMastery.can_explain.value,
        "yes": ConceptMastery.can_explain.value,
        "expert": ConceptMastery.can_explain.value,
        "explain": ConceptMastery.can_explain.value,
        "can": ConceptMastery.can_explain.value,
        "some": ConceptMastery.familiar.value,
        "kinda": ConceptMastery.familiar.value,
        "mid": ConceptMastery.familiar.value,
        "no": ConceptMastery.unknown.value,
        "none": ConceptMastery.unknown.value,
        "idk": ConceptMastery.unknown.value,
    }
    mapped = aliases.get(raw, raw)
    try:
        return ConceptMastery(mapped).value
    except ValueError:
        # Tolerate typos like "can_explaun"
        matches = difflib.get_close_matches(
            mapped,
            [m.value for m in ConceptMastery],
            n=1,
            cutoff=0.7,
        )
        if matches:
            return matches[0]
        return ConceptMastery.unknown.value


def apply_assessment_answers(
    milestones: list[CatalogMilestone],
    answers: dict[str, str] | None,
) -> dict[str, str]:
    profile = {name: ConceptMastery.unknown.value for name in catalog_concepts(milestones)}
    for name, value in (answers or {}).items():
        if name in profile:
            profile[name] = normalize_mastery(value)
    return profile


def build_roadmap(
    milestones: list[CatalogMilestone],
    knowledge_profile: dict[str, str],
) -> list[RoadmapMilestone]:
    """Map catalog concepts onto existing milestones. Never invent milestones."""
    ordered = sorted(milestones, key=lambda m: m["order_index"])
    roadmap: list[RoadmapMilestone] = []
    for milestone in ordered:
        items = []
        for name in milestone.get("concepts") or []:
            mastery = knowledge_profile.get(name, ConceptMastery.unknown.value)
            teaching = (
                TeachingFlag.skip.value
                if mastery == ConceptMastery.can_explain.value
                else TeachingFlag.teach.value
            )
            items.append({"name": name, "teaching": teaching, "mastery": mastery})
        roadmap.append(
            {
                "milestone_id": milestone["id"],
                "title": milestone["title"],
                "order_index": milestone["order_index"],
                "concepts": items,
            }
        )
    return roadmap


def current_teach_concepts(
    roadmap: list[RoadmapMilestone],
    milestone_id: int,
    knowledge_profile: dict[str, str],
) -> list[str]:
    for item in roadmap:
        if item["milestone_id"] != milestone_id:
            continue
        names = []
        for concept in item["concepts"]:
            mastery = knowledge_profile.get(
                concept["name"], concept.get("mastery", ConceptMastery.unknown.value)
            )
            if (
                concept["teaching"] == TeachingFlag.teach.value
                and mastery != ConceptMastery.can_explain.value
            ):
                names.append(concept["name"])
        return names
    return []


def later_milestone_concepts(
    catalog: list[CatalogMilestone],
    current_milestone_id: int,
) -> list[str]:
    current = next((m for m in catalog if m["id"] == current_milestone_id), None)
    if current is None:
        return []
    names: list[str] = []
    current_set = set(current.get("concepts") or [])
    for milestone in catalog:
        if milestone["order_index"] <= current["order_index"]:
            continue
        for concept in milestone.get("concepts") or []:
            if concept not in current_set:
                names.append(concept)
    return names


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


def classify_intent(message: str) -> str:
    lower = message.lower()
    if any(word in lower for word in ("hint", "stuck", "clue", "give me a hint")):
        return "hint"
    if any(word in lower for word in ("concept card", "research question", "show card")):
        return "card"
    if "checkpoint" in lower or "i researched" in lower:
        return "checkpoint"
    return "answer"


def fallback_card(
    concept: str,
    milestone_title: str,
    resources: list[dict[str, str]],
) -> CardDraft:
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


def go_build_reply(*, constraints: list[str], success_criteria: str) -> str:
    constraint = constraints[0] if constraints else "follow the project constraints"
    success = success_criteria or "meet the milestone success criteria"
    return f"Go build. Constraint: {constraint}; success: {success}."


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


def fallback_hint(level: int, milestone_title: str, concepts: list[str]) -> str:
    concept = concepts[0] if concepts else "the core idea"
    templates = {
        0: f"What part of '{milestone_title}' is failing?",
        1: f"Look at the success criteria for '{milestone_title}'.",
        2: f"This is about {concept}. Research that, then answer.",
        3: f"Sketch: boundary, data to persist, proof for '{milestone_title}'.",
        4: f"Fix only the {concept} boundary. Compare to success criteria.",
    }
    return templates.get(level, templates[0])


def fallback_card_reply(cards: list[CardDraft]) -> str:
    if not cards:
        return "No cards. Go build."
    card = cards[0]
    return f"{card['name']}: {card['why_it_matters']} Checkpoint: {card['checkpoint']}"


def enforce_brevity(text: str, *, max_sentences: int = 2) -> str:
    """Keep coach replies abrupt: at most max_sentences."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return cleaned
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return " ".join(parts[:max_sentences]).strip()


def _strip_solution_fences(text: str) -> tuple[str, bool]:
    stripped = False

    def replacer(match: re.Match[str]) -> str:
        nonlocal stripped
        body = match.group(1)
        if body.count("\n") + 1 >= SOLUTION_FENCE_LINES:
            stripped = True
            return (
                "[full solution removed — implement the approach yourself; "
                "ask a design question if you are stuck]"
            )
        return match.group(0)

    return _FENCE_RE.sub(replacer, text), stripped


def filter_specialist_reply(
    reply: str,
    *,
    later_concepts: list[str],
    allow_code: bool = False,
) -> tuple[str, list[str]]:
    flags: list[str] = []
    text = enforce_brevity(reply, max_sentences=2)
    if not allow_code:
        text, stripped = _strip_solution_fences(text)
        if stripped:
            flags.append("stripped_solution")
            text = "No full solutions. Answer the question."
        if "```" in text:
            flags.append("stripped_solution")
            text = "No code dumps. Answer the question."
    for concept in later_concepts:
        if concept and concept.lower() in text.lower():
            flags.append("blocked_later_concept")
            pattern = re.compile(re.escape(concept), re.IGNORECASE)
            text = pattern.sub("[later]", text)
    return enforce_brevity(text, max_sentences=2), flags


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
