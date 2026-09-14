"""Deterministic coaching policy: planner mapping, hint gating, output filter."""

from __future__ import annotations

import re
from typing import Any

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
        "some": ConceptMastery.familiar.value,
        "kinda": ConceptMastery.familiar.value,
        "no": ConceptMastery.unknown.value,
        "none": ConceptMastery.unknown.value,
    }
    mapped = aliases.get(raw, raw)
    try:
        return ConceptMastery(mapped).value
    except ValueError:
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
    return "mentor"


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


def fallback_mentor_reply(
    *,
    milestone_title: str,
    constraints: list[str],
    success_criteria: str,
    current_concepts: list[str],
    learner_message: str,
) -> str:
    constraint_line = "; ".join(constraints[:3]) if constraints else "the project constraints"
    concept_line = ", ".join(current_concepts[:3]) if current_concepts else "the current concepts"
    return (
        f"Before we talk implementation for '{milestone_title}', what do you think the "
        f"design should be? I want to hear your assumptions.\n\n"
        f"Constraints you cannot ignore: {constraint_line}.\n"
        f"Success looks like: {success_criteria}\n"
        f"Relevant concepts (research the cards, don't wait for me to lecture): {concept_line}.\n\n"
        f"You said: {learner_message[:280]}\n"
        "Challenge: name the tradeoff you are making, then go implement your approach. "
        "I will not write the solution for you."
    )


def fallback_hint(level: int, milestone_title: str, concepts: list[str]) -> str:
    concept = concepts[0] if concepts else "the core idea of this milestone"
    templates = {
        0: (
            f"Question only: which part of '{milestone_title}' is actually failing, "
            "and what did you expect to happen instead?"
        ),
        1: (
            f"Direction: look at the milestone success criteria and the first concept card "
            f"for '{concept}'. Start there, not in a tutorial dump."
        ),
        2: (
            f"Concept: this is about {concept}. Open that card, answer its research "
            "questions, then come back."
        ),
        3: (
            f"Structure sketch (not code): identify the boundary, the data you must persist, "
            f"and the check that proves '{milestone_title}' works. Fill those three boxes."
        ),
        4: (
            f"Targeted help: the stuck piece is usually the {concept} boundary — "
            "compare your actual result to the success criteria and change only that piece."
        ),
    }
    return templates.get(level, templates[0])


def fallback_card_reply(cards: list[CardDraft]) -> str:
    if not cards:
        return "No concept cards for this milestone — you already know these ideas. Implement it."
    lines = ["Research these cards. Explanations stay short on purpose:"]
    for card in cards:
        lines.append(f"- {card['name']}: {card['why_it_matters']}")
        lines.append(f"  Checkpoint: {card['checkpoint']}")
    lines.append("Come back when you can answer the checkpoint, not before.")
    return "\n".join(lines)


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
    text = reply
    if not allow_code:
        text, stripped = _strip_solution_fences(text)
        if stripped:
            flags.append("stripped_solution")
        if "```" in text and text.count("\n") > 20:
            flags.append("stripped_solution")
            text = (
                "I almost pasted a full solution there. Let's stay on design: "
                "what do you think the approach should be?"
            )
    remaining_later = []
    for concept in later_concepts:
        if concept and concept.lower() in text.lower():
            remaining_later.append(concept)
            pattern = re.compile(re.escape(concept), re.IGNORECASE)
            text = pattern.sub("[later-milestone concept withheld]", text)
    if remaining_later:
        flags.append("blocked_later_concept")
    return text, flags


def checkpoint_passes(answer: str) -> bool:
    cleaned = answer.strip()
    return len(cleaned) >= 40 and "idk" not in cleaned.lower()
