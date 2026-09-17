"""Deterministic curriculum engine.

The knowledge graph (Concept / ConceptDependency / MilestoneConcept) is the
single source of truth for *what* is learned and in what order. This module
computes *where the learner is* and *what they may do next*. The AI mentor
never invents or reorders this — it only narrates inside the current node.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.models.curriculum import Concept, ConceptDependency, MilestoneConcept
from app.models.learning_state import (
    ConceptState,
    ConceptStatus,
    GapStatus,
    KnowledgeGap,
    Reflection,
    RetrievalCheck,
    RetrievalCheckStatus,
)
from app.models.project import (
    Milestone,
    UserMilestone,
    UserMilestoneStatus,
    UserProject,
)

SATISFIED_STATUSES = frozenset({ConceptStatus.mastered, ConceptStatus.verified})
TERMINAL_STATUSES = SATISFIED_STATUSES
IN_PROGRESS_STATUSES = frozenset(
    {
        ConceptStatus.available,
        ConceptStatus.introduced,
        ConceptStatus.researching,
        ConceptStatus.discussing,
        ConceptStatus.attempted,
        ConceptStatus.testing,
        ConceptStatus.explained,
        ConceptStatus.verification,
        ConceptStatus.blocked,
        ConceptStatus.diagnosis,
        ConceptStatus.knowledge_gap,
        ConceptStatus.needs_review,
    }
)

EMPTY_EVIDENCE: dict[str, bool] = {
    "research": False,
    "implementation": False,
    "testing": False,
    "explanation": False,
    "retrieval": False,
}

RETRIEVAL_OFFSETS_DAYS = (1, 7, 30)


def empty_evidence() -> dict[str, bool]:
    return dict(EMPTY_EVIDENCE)


def _status(value: ConceptStatus | str) -> ConceptStatus:
    if isinstance(value, ConceptStatus):
        return value
    return ConceptStatus(value)


def prereq_satisfied(status: ConceptStatus | str) -> bool:
    return _status(status) in SATISFIED_STATUSES


def needs_build(concept: Concept) -> bool:
    req = concept.mastery_requirements or {}
    if req.get("implementation") or req.get("testing"):
        return True
    from app.services.practice import practice_tasks_for

    return bool(practice_tasks_for(concept))


def _norm_question(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def required_questions(concept: Concept | None) -> list[str]:
    if concept is None:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(concept.diagnostic_questions or []) + list(concept.research_questions or []):
        text = str(raw or "").strip()
        key = _norm_question(text)
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _answered_question_keys(row: ConceptState | None, evidence: dict[str, Any] | None = None) -> set[str]:
    keys: set[str] = set()
    blob = dict(evidence if evidence is not None else ((row.evidence if row else None) or {}))
    for item in list(blob.get("answered_questions") or []):
        key = _norm_question(str(item))
        if key:
            keys.add(key)
    if row is None:
        return keys
    for item in list(row.diagnostic_answers or []):
        if not isinstance(item, dict):
            continue
        answer = str(item.get("answer") or "").strip()
        if len(answer) < 25:
            continue
        question = str(item.get("question") or "").strip()
        if question:
            keys.add(_norm_question(question))
    return keys


def questions_work_complete(
    concept: Concept | None,
    row: ConceptState | None,
    evidence: dict[str, Any] | None = None,
) -> bool:
    required = required_questions(concept)
    if not required:
        return True
    if row is not None and bool(getattr(row, "verified_via_skip", False)):
        return True
    answered = _answered_question_keys(row, evidence)
    return all(_norm_question(question) in answered for question in required)


def practice_work_complete(
    concept: Concept | None,
    evidence: dict[str, Any] | None = None,
    *,
    language: str | None = None,
    extra_done: set[str] | None = None,
) -> bool:
    from app.services.practice import practice_tasks_for

    tasks = practice_tasks_for(concept, language=language)
    if not tasks:
        return True
    done = {str(item) for item in list((evidence or {}).get("practice_task_ids") or [])}
    if extra_done:
        done |= {str(item) for item in extra_done if str(item)}
    return all(str(task.get("id") or "") in done for task in tasks)


def concept_work_complete(
    concept: Concept | None,
    row: ConceptState | None,
    evidence: dict[str, Any] | None = None,
    *,
    language: str | None = None,
) -> bool:
    blob = dict(evidence if evidence is not None else ((row.evidence if row else None) or {}))
    return questions_work_complete(concept, row, blob) and practice_work_complete(
        concept, blob, language=language
    )


def mark_required_questions_answered(
    row: ConceptState, concept: Concept | None, *, answer: str = ""
) -> None:
    questions = required_questions(concept)
    if not questions:
        return
    evidence = dict(row.evidence or empty_evidence())
    recorded = [str(item) for item in list(evidence.get("answered_questions") or [])]
    known = {_norm_question(item) for item in recorded}
    for question in questions:
        if _norm_question(question) in known:
            continue
        recorded.append(question)
        known.add(_norm_question(question))
    evidence["answered_questions"] = recorded
    row.evidence = evidence
    flag_modified(row, "evidence")
    if answer.strip():
        answers = list(row.diagnostic_answers or [])
        have = {
            _norm_question(str(item.get("question") or ""))
            for item in answers
            if isinstance(item, dict)
        }
        for question in questions:
            if _norm_question(question) in have:
                continue
            answers.append({"question": question, "answer": answer.strip()[:2000]})
        row.diagnostic_answers = answers[-40:]
        flag_modified(row, "diagnostic_answers")


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------


def catalog_milestones(db: Session, project_id: int) -> list[Milestone]:
    return (
        db.query(Milestone)
        .filter(Milestone.project_id == project_id, Milestone.user_project_id.is_(None))
        .order_by(Milestone.order_index)
        .all()
    )


def learner_milestones(user_project: UserProject) -> list[Milestone]:
    return sorted(
        (um.milestone for um in user_project.user_milestones if um.milestone is not None),
        key=lambda m: m.order_index,
    )


def _existing_concept_ids(db: Session, candidate_ids: list[str]) -> list[str]:
    if not candidate_ids:
        return []
    known = {
        row[0]
        for row in db.query(Concept.id).filter(Concept.id.in_(candidate_ids)).all()
    }
    return [cid for cid in candidate_ids if cid in known]


def concept_ids_for_milestone(db: Session, milestone_id: int) -> list[str]:
    rows = (
        db.query(MilestoneConcept)
        .filter(MilestoneConcept.milestone_id == milestone_id)
        .order_by(MilestoneConcept.order_index, MilestoneConcept.id)
        .all()
    )
    if rows:
        return [row.concept_id for row in rows]
    milestone = db.get(Milestone, milestone_id)
    return _existing_concept_ids(db, list((milestone.concepts if milestone else []) or []))


def all_project_concept_ids(db: Session, project_id: int) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for milestone in catalog_milestones(db, project_id):
        for concept_id in concept_ids_for_milestone(db, milestone.id):
            if concept_id not in seen:
                seen.add(concept_id)
                ordered.append(concept_id)
    return ordered


def dependencies_for(db: Session, concept_ids: list[str] | None = None) -> list[ConceptDependency]:
    query = db.query(ConceptDependency)
    if concept_ids is not None:
        query = query.filter(ConceptDependency.concept_id.in_(concept_ids or ["__none__"]))
    return query.all()


def requires_map(db: Session) -> dict[str, list[ConceptDependency]]:
    mapping: dict[str, list[ConceptDependency]] = {}
    for dep in db.query(ConceptDependency).all():
        mapping.setdefault(dep.concept_id, []).append(dep)
    return mapping


def states_by_concept(db: Session, user_project_id: int) -> dict[str, ConceptState]:
    rows = (
        db.query(ConceptState)
        .filter(ConceptState.user_project_id == user_project_id)
        .all()
    )
    return {row.concept_id: row for row in rows}


# ---------------------------------------------------------------------------
# Initialization / unlocking
# ---------------------------------------------------------------------------


def initialize_learning_state(db: Session, user_project: UserProject) -> list[ConceptState]:
    """Create ConceptState rows for every concept in the project's graph.

    Concepts with no unmet prerequisites start AVAILABLE; everything else is
    LOCKED. Must run in the same transaction as enrollment; caller commits.
    """
    concept_ids = all_project_concept_ids(db, user_project.project_id)
    existing = states_by_concept(db, user_project.id)
    created: list[ConceptState] = []
    for concept_id in concept_ids:
        if concept_id in existing:
            created.append(existing[concept_id])
            continue
        row = ConceptState(
            user_project_id=user_project.id,
            concept_id=concept_id,
            status=ConceptStatus.locked,
            evidence=empty_evidence(),
        )
        db.add(row)
        created.append(row)
    db.flush()
    apply_unlocks(db, user_project)
    return created


def _prereqs_met(
    concept_id: str,
    states: dict[str, ConceptState],
    deps: dict[str, list[ConceptDependency]],
) -> bool:
    for dep in deps.get(concept_id, []):
        prereq = states.get(dep.requires_concept_id)
        if prereq is None or not prereq_satisfied(prereq.status):
            return False
    return True


def apply_unlocks(db: Session, user_project: UserProject) -> list[str]:
    """Unlock LOCKED concepts whose prerequisites are now satisfied.

    Does not skip past the current milestone's incomplete concepts — it only
    changes LOCKED → AVAILABLE. The mentor still cannot jump milestones.
    """
    states = states_by_concept(db, user_project.id)
    deps = requires_map(db)
    unlocked: list[str] = []
    changed = True
    while changed:
        changed = False
        for concept_id, row in states.items():
            if row.status != ConceptStatus.locked:
                continue
            if _prereqs_met(concept_id, states, deps):
                row.status = ConceptStatus.available
                unlocked.append(concept_id)
                changed = True
    db.flush()
    return unlocked


# ---------------------------------------------------------------------------
# Current position
# ---------------------------------------------------------------------------


class Position(dict):
    """Plain dict so it serializes cleanly through FastAPI/Pydantic."""


def current_user_milestone(user_project: UserProject) -> UserMilestone | None:
    pending = [
        um
        for um in user_project.user_milestones
        if um.status == UserMilestoneStatus.pending and um.milestone is not None
    ]
    pending.sort(key=lambda um: um.milestone.order_index)
    return pending[0] if pending else None


def resolve_current_position(db: Session, user_project: UserProject) -> dict[str, Any]:
    """Return the current milestone, current concept, and allow/block lists.

    Purely computed from ConceptState + ConceptDependency. Never asks an LLM.
    """
    states = states_by_concept(db, user_project.id)
    um = current_user_milestone(user_project)
    current_milestone = um.milestone if um else None
    current_concept_id: str | None = None
    current_status: str | None = None

    if current_milestone is not None:
        for concept_id in concept_ids_for_milestone(db, current_milestone.id):
            row = states.get(concept_id)
            if row is None or row.status in TERMINAL_STATUSES:
                continue
            current_concept_id = concept_id
            current_status = row.status.value
            break

    allowed: list[str] = []
    blocked: list[str] = []
    for concept_id, row in states.items():
        if row.status == ConceptStatus.locked:
            blocked.append(concept_id)
        elif row.status not in TERMINAL_STATUSES:
            allowed.append(concept_id)

    later: list[str] = []
    if current_milestone is not None:
        for other in learner_milestones(user_project):
            if other.order_index <= current_milestone.order_index:
                continue
            later.extend(concept_ids_for_milestone(db, other.id))

    return {
        "user_milestone_id": um.id if um else None,
        "milestone_id": current_milestone.id if current_milestone else None,
        "milestone_title": current_milestone.title if current_milestone else None,
        "milestone_order": current_milestone.order_index if current_milestone else None,
        "milestone_instructions": current_milestone.instructions if current_milestone else "",
        "milestone_success": current_milestone.success_criteria if current_milestone else "",
        "current_concept_id": current_concept_id,
        "concept_state": current_status,
        "allowed_concepts": allowed,
        "blocked_concepts": blocked,
        "later_concepts": later,
        "project_complete": um is None,
    }


def later_concept_titles(db: Session, later_ids: list[str]) -> list[str]:
    if not later_ids:
        return []
    rows = db.query(Concept).filter(Concept.id.in_(later_ids)).all()
    return [row.title for row in rows] + later_ids


def next_unlocked_concept_title(
    db: Session, user_project: UserProject, current_concept_id: str | None
) -> str:
    um = current_user_milestone(user_project)
    if um is None or um.milestone is None:
        return ""
    ids = concept_ids_for_milestone(db, um.milestone.id)
    states = states_by_concept(db, user_project.id)
    seen_current = not current_concept_id
    for concept_id in ids:
        if not seen_current:
            if concept_id == current_concept_id:
                seen_current = True
            continue
        row = states.get(concept_id)
        if row is None or row.status not in SATISFIED_STATUSES:
            concept = db.get(Concept, concept_id)
            return (concept.title if concept else concept_id) or concept_id
    return ""


# ---------------------------------------------------------------------------
# Evidence + transitions
# ---------------------------------------------------------------------------


def get_or_create_state(
    db: Session, user_project: UserProject, concept_id: str
) -> ConceptState:
    row = (
        db.query(ConceptState)
        .filter(
            ConceptState.user_project_id == user_project.id,
            ConceptState.concept_id == concept_id,
        )
        .first()
    )
    if row is None:
        row = ConceptState(
            user_project_id=user_project.id,
            concept_id=concept_id,
            status=ConceptStatus.locked,
            evidence=empty_evidence(),
        )
        db.add(row)
        db.flush()
    return row


def record_evidence(
    db: Session,
    user_project: UserProject,
    concept_id: str,
    **flags: bool,
) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    evidence = dict(row.evidence or empty_evidence())
    for key, value in flags.items():
        if key in EMPTY_EVIDENCE:
            evidence[key] = bool(value)
    row.evidence = evidence
    flag_modified(row, "evidence")
    db.flush()
    return row


def record_practice_pass(
    db: Session,
    user_project: UserProject,
    concept_id: str,
    task_id: str,
) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    evidence = dict(row.evidence or empty_evidence())
    ids = [str(item) for item in list(evidence.get("practice_task_ids") or [])]
    if task_id and task_id not in ids:
        ids.append(str(task_id))
    evidence["practice_task_ids"] = ids
    row.evidence = evidence
    flag_modified(row, "evidence")
    db.flush()
    concept = db.get(Concept, concept_id)
    if practice_work_complete(concept, evidence):
        row = record_evidence(db, user_project, concept_id, implementation=True)
    return row


def _requirements_met(
    concept: Concept,
    evidence: dict[str, Any],
    row: ConceptState | None = None,
) -> bool:
    req = concept.mastery_requirements or {}
    for key, needed in req.items():
        if needed and not evidence.get(key):
            return False
    if not practice_work_complete(concept, evidence):
        return False
    if not questions_work_complete(concept, row, evidence):
        return False
    return True


def try_master(db: Session, user_project: UserProject, concept_id: str) -> ConceptState:
    """Promote to MASTERED only when required evidence is present."""
    row = get_or_create_state(db, user_project, concept_id)
    concept = db.get(Concept, concept_id)
    if concept is None:
        return row
    if _requirements_met(concept, row.evidence or {}, row):
        row.status = ConceptStatus.mastered
        schedule_retrieval_checks(db, user_project, concept)
        apply_unlocks(db, user_project)
    else:
        row.status = ConceptStatus.verification
    db.flush()
    return row


def set_status(
    db: Session,
    user_project: UserProject,
    concept_id: str,
    status: ConceptStatus,
) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    row.status = status
    row.updated_at = datetime.now(UTC)
    db.flush()
    if status == ConceptStatus.mastered:
        concept = db.get(Concept, concept_id)
        if concept is not None:
            schedule_retrieval_checks(db, user_project, concept)
        apply_unlocks(db, user_project)
    return row


def introduce_concept(db: Session, user_project: UserProject, concept_id: str) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    if row.status in {ConceptStatus.locked}:
        return row
    if row.status == ConceptStatus.available:
        row.status = ConceptStatus.introduced
        db.flush()
    return row


def mark_researching(db: Session, user_project: UserProject, concept_id: str) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    if row.status in {
        ConceptStatus.available,
        ConceptStatus.introduced,
        ConceptStatus.researching,
        ConceptStatus.needs_review,
    }:
        row.status = ConceptStatus.researching
        db.flush()
    return row


def mark_discussing(db: Session, user_project: UserProject, concept_id: str) -> ConceptState:
    row = record_evidence(db, user_project, concept_id, research=True)
    if row.status in {
        ConceptStatus.available,
        ConceptStatus.introduced,
        ConceptStatus.researching,
        ConceptStatus.needs_review,
    }:
        row.status = ConceptStatus.discussing
        db.flush()
    return row


def get_learning_control(row: ConceptState) -> dict[str, Any]:
    from app.agents.learning_control import bound_control

    evidence = dict(row.evidence or empty_evidence())
    return bound_control(evidence.get("learning_control"), concept_id=row.concept_id)


def save_learning_control(row: ConceptState, control: dict[str, Any]) -> None:
    evidence = dict(row.evidence or empty_evidence())
    evidence["learning_control"] = control
    row.evidence = evidence
    flag_modified(row, "evidence")


def record_learner_answer(
    db: Session,
    user_project: UserProject,
    concept_id: str,
    message: str,
    *,
    misconception_id: str | None = None,
    phase: str | None = None,
    question: str | None = None,
) -> ConceptState:
    """Count a chat answer and keep a short history for misconception routing."""
    row = get_or_create_state(db, user_project, concept_id)
    row.attempt_count = int(row.attempt_count or 0) + 1
    row.last_explanation = message.strip()[:4000]
    concept = db.get(Concept, concept_id)
    blob = str(question or "").strip()
    matched = ""
    if concept is not None:
        for item in required_questions(concept):
            if item and item in blob:
                matched = item
                break
    answers = list(row.diagnostic_answers or [])
    answers.append(
        {
            "answer": message.strip()[:2000],
            "question": matched,
            "misconception_id": misconception_id,
            "phase": phase,
        }
    )
    row.diagnostic_answers = answers[-20:]
    flag_modified(row, "diagnostic_answers")
    if matched and len(message.strip()) >= 25:
        evidence = dict(row.evidence or empty_evidence())
        recorded = [str(item) for item in list(evidence.get("answered_questions") or [])]
        if _norm_question(matched) not in {_norm_question(item) for item in recorded}:
            recorded.append(matched)
            evidence["answered_questions"] = recorded
            row.evidence = evidence
            flag_modified(row, "evidence")
    db.flush()
    return row


def mark_attempted(db: Session, user_project: UserProject, concept_id: str) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    row.status = ConceptStatus.attempted
    row.attempt_count = int(row.attempt_count or 0) + 1
    record_evidence(db, user_project, concept_id, implementation=True)
    db.flush()
    return row


def record_test_result(
    db: Session,
    user_project: UserProject,
    *,
    passed: bool,
    summary: str = "",
) -> ConceptState | None:
    """Attach a sandbox test result to the current concept."""
    position = resolve_current_position(db, user_project)
    concept_id = position.get("current_concept_id")
    if not concept_id:
        return None
    row = get_or_create_state(db, user_project, str(concept_id))
    row.attempt_count = int(row.attempt_count or 0) + 1
    if passed:
        record_evidence(db, user_project, str(concept_id), testing=True, implementation=True)
        if row.status in {
            ConceptStatus.attempted,
            ConceptStatus.testing,
            ConceptStatus.discussing,
            ConceptStatus.blocked,
        }:
            row.status = ConceptStatus.explained
    else:
        row.status = ConceptStatus.blocked
        evidence = dict(row.evidence or empty_evidence())
        evidence["testing"] = False
        row.evidence = evidence
    db.flush()
    return row


def explanation_passed(
    db: Session, user_project: UserProject, concept_id: str, text: str
) -> ConceptState:
    row = record_evidence(db, user_project, concept_id, explanation=True)
    row.last_explanation = text
    concept = db.get(Concept, concept_id)
    if concept is not None and needs_build(concept) and not (row.evidence or {}).get("implementation"):
        row.status = ConceptStatus.attempted
        db.flush()
        return row
    return try_master(db, user_project, concept_id)


def explanation_failed(
    db: Session, user_project: UserProject, concept_id: str, text: str
) -> ConceptState:
    row = get_or_create_state(db, user_project, concept_id)
    row.last_explanation = text
    row.status = ConceptStatus.knowledge_gap
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Skip diagnostic (spec §29)
# ---------------------------------------------------------------------------


def evaluate_skip_diagnostic(
    db: Session,
    user_project: UserProject,
    concept_id: str,
    answers: list[str],
) -> dict[str, Any]:
    """Short assessment to skip a concept. Pass → VERIFIED (not MASTERED)."""
    concept = db.get(Concept, concept_id)
    row = get_or_create_state(db, user_project, concept_id)
    questions = list((concept.diagnostic_questions if concept else []) or [])
    if not questions:
        questions = ["Explain this concept in your own words."]
    paired = list(zip(questions, answers + [""] * len(questions)))
    passed_all = True
    for question, answer in paired[: len(questions)]:
        cleaned = (answer or "").strip()
        if len(cleaned) < 25 or cleaned.lower() in {"idk", "dunno", "pass", "yes", "no"}:
            passed_all = False
            break
        if cleaned.rstrip("?").lower() == question.rstrip("?").lower():
            passed_all = False
            break
    row.diagnostic_answers = [
        {"question": q, "answer": a, "passed": passed_all} for q, a in paired[: len(questions)]
    ]
    if passed_all:
        mark_required_questions_answered(row, concept, answer=(answers[0] if answers else ""))
        if concept is not None:
            record_evidence(db, user_project, concept_id, explanation=True)
        if practice_work_complete(concept, dict(row.evidence or {})):
            row.status = ConceptStatus.verified
            row.verified_via_skip = True
            apply_unlocks(db, user_project)
        else:
            row.status = ConceptStatus.attempted
            row.verified_via_skip = False
    else:
        row.status = ConceptStatus.needs_review
    db.flush()
    return {
        "passed": passed_all,
        "status": row.status.value,
        "concept_id": concept_id,
    }


# ---------------------------------------------------------------------------
# Knowledge gaps (rule-based heuristic, spec §10)
# ---------------------------------------------------------------------------


def suspect_gaps(
    db: Session, user_project: UserProject, concept_id: str
) -> list[dict[str, Any]]:
    """Rank likely missing prerequisites by graph proximity + weak evidence.

    ``confidence`` is a heuristic in [0, 1], not a trained model score.
    """
    states = states_by_concept(db, user_project.id)
    deps = requires_map(db)
    scores: dict[str, float] = {}

    def walk(node_id: str, depth: int) -> None:
        for dep in deps.get(node_id, []):
            prereq_id = dep.requires_concept_id
            row = states.get(prereq_id)
            base = 0.9 / (depth + 1)
            if row is None:
                scores[prereq_id] = max(scores.get(prereq_id, 0.0), base)
                continue
            penalty = 0.0
            if not prereq_satisfied(row.status):
                penalty += 0.55
            if row.status == ConceptStatus.locked:
                penalty += 0.2
            evidence = row.evidence or {}
            missing = sum(1 for v in evidence.values() if not v)
            penalty += 0.05 * missing
            if row.status in {
                ConceptStatus.blocked,
                ConceptStatus.knowledge_gap,
                ConceptStatus.needs_review,
            }:
                penalty += 0.15
            scores[prereq_id] = max(scores.get(prereq_id, 0.0), min(1.0, base * (0.4 + penalty)))
            if depth < 2:
                walk(prereq_id, depth + 1)

    walk(concept_id, 0)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        {"concept": cid, "confidence": round(conf, 2)}
        for cid, conf in ranked
        if conf >= 0.2
    ]


def persist_suspected_gaps(
    db: Session,
    user_project: UserProject,
    blocked_concept_id: str,
    suspects: list[dict[str, Any]],
) -> list[KnowledgeGap]:
    existing = {
        (g.blocked_concept_id, g.suspected_concept_id): g
        for g in db.query(KnowledgeGap)
        .filter(
            KnowledgeGap.user_project_id == user_project.id,
            KnowledgeGap.blocked_concept_id == blocked_concept_id,
            KnowledgeGap.status == GapStatus.open,
        )
        .all()
    }
    stored: list[KnowledgeGap] = []
    for item in suspects:
        key = (blocked_concept_id, item["concept"])
        row = existing.get(key)
        if row is None:
            row = KnowledgeGap(
                user_project_id=user_project.id,
                blocked_concept_id=blocked_concept_id,
                suspected_concept_id=item["concept"],
                confidence=float(item["confidence"]),
            )
            db.add(row)
        else:
            row.confidence = float(item["confidence"])
        stored.append(row)
    db.flush()
    return stored


def open_gaps(db: Session, user_project_id: int) -> list[KnowledgeGap]:
    return (
        db.query(KnowledgeGap)
        .filter(
            KnowledgeGap.user_project_id == user_project_id,
            KnowledgeGap.status == GapStatus.open,
        )
        .order_by(KnowledgeGap.confidence.desc())
        .all()
    )


def explain_gap_reason(db: Session, concept_id: str, requires_concept_id: str) -> str:
    dep = (
        db.query(ConceptDependency)
        .filter(
            ConceptDependency.concept_id == concept_id,
            ConceptDependency.requires_concept_id == requires_concept_id,
        )
        .first()
    )
    if dep and dep.reason:
        return dep.reason
    return f"'{requires_concept_id}' is a prerequisite of '{concept_id}'."


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def schedule_retrieval_checks(
    db: Session, user_project: UserProject, concept: Concept
) -> list[RetrievalCheck]:
    existing = {
        row.scheduled_for
        for row in db.query(RetrievalCheck)
        .filter(
            RetrievalCheck.user_project_id == user_project.id,
            RetrievalCheck.concept_id == concept.id,
        )
        .all()
    }
    today = date.today()
    prompts = {
        1: f"Explain how '{concept.title}' works, from memory.",
        7: f"Without looking at your code, design '{concept.title}' again in your own words.",
        30: f"From memory: what problem does '{concept.title}' solve, and what would break without it?",
    }
    created: list[RetrievalCheck] = []
    for days in RETRIEVAL_OFFSETS_DAYS:
        when = today + timedelta(days=days)
        if when in existing:
            continue
        row = RetrievalCheck(
            user_project_id=user_project.id,
            concept_id=concept.id,
            scheduled_for=when,
            prompt=prompts[days],
            original_response_ref="",
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def due_retrieval_checks(db: Session, user_project_id: int) -> list[RetrievalCheck]:
    today = date.today()
    return (
        db.query(RetrievalCheck)
        .filter(
            RetrievalCheck.user_project_id == user_project_id,
            RetrievalCheck.status == RetrievalCheckStatus.pending,
            RetrievalCheck.scheduled_for <= today,
        )
        .order_by(RetrievalCheck.scheduled_for)
        .all()
    )


# ---------------------------------------------------------------------------
# Milestone completion gates
# ---------------------------------------------------------------------------


def milestone_concepts_complete(
    db: Session, user_project: UserProject, milestone: Milestone
) -> bool:
    ids = concept_ids_for_milestone(db, milestone.id)
    if not ids:
        return True
    states = states_by_concept(db, user_project.id)
    return all(
        concept_ready_for_milestone(db.get(Concept, cid), states.get(cid)) for cid in ids
    )


def concept_ready_for_milestone(concept: Concept | None, row: ConceptState | None) -> bool:
    if concept is None or row is None:
        return False
    if not prereq_satisfied(row.status):
        return False
    return concept_work_complete(concept, row)


def reflection_complete(db: Session, user_milestone_id: int) -> bool:
    row = (
        db.query(Reflection)
        .filter(Reflection.user_milestone_id == user_milestone_id)
        .first()
    )
    if row is None:
        return False
    answers = row.answers or {}
    required = ("what", "why", "alternatives", "difficult", "scale", "change")
    return all(str(answers.get(key) or "").strip() for key in required)


def can_complete_milestone(
    db: Session, user_project: UserProject, user_milestone: UserMilestone
) -> tuple[bool, str]:
    milestone = user_milestone.milestone
    if milestone is None:
        return False, "Milestone not found"
    if not milestone_concepts_complete(db, user_project, milestone):
        return False, "Every concept in this milestone needs all questions answered and all practice tasks done"
    if not reflection_complete(db, user_milestone.id):
        return False, "Submit a milestone reflection before completing"
    # Final milestone also needs the project defense.
    remaining = [
        um
        for um in user_project.user_milestones
        if um.status == UserMilestoneStatus.pending and um.id != user_milestone.id
    ]
    if not remaining:
        from app.models.learning_state import DefenseVerdict, ProjectDefense

        defense = (
            db.query(ProjectDefense)
            .filter(ProjectDefense.user_project_id == user_project.id)
            .first()
        )
        if defense is None or defense.verdict != DefenseVerdict.passed:
            return False, "Pass the final engineering defense before completing the last milestone"
    return True, ""


def graph_payload(db: Session, user_project: UserProject) -> dict[str, Any]:
    position = resolve_current_position(db, user_project)
    states = states_by_concept(db, user_project.id)
    milestones_out: list[dict[str, Any]] = []
    for um in sorted(
        user_project.user_milestones,
        key=lambda row: row.milestone.order_index if row.milestone else 0,
    ):
        milestone = um.milestone
        if milestone is None:
            continue
        concepts_out = []
        for concept_id in concept_ids_for_milestone(db, milestone.id):
            concept = db.get(Concept, concept_id)
            state = states.get(concept_id)
            concepts_out.append(
                {
                    "id": concept_id,
                    "title": concept.title if concept else concept_id,
                    "category": concept.category if concept else "",
                    "status": state.status.value if state else ConceptStatus.locked.value,
                    "evidence": dict(state.evidence or empty_evidence()) if state else empty_evidence(),
                }
            )
        milestones_out.append(
            {
                "user_milestone_id": um.id,
                "milestone_id": milestone.id,
                "title": milestone.title,
                "order_index": milestone.order_index,
                "status": um.status.value,
                "description": milestone.description,
                "success_criteria": milestone.success_criteria,
                "concepts": concepts_out,
            }
        )
    gaps = [
        {
            "id": g.id,
            "concept": g.blocked_concept_id,
            "status": "blocked",
            "suspected_gaps": [
                {"concept": g.suspected_concept_id, "confidence": g.confidence}
            ],
        }
        for g in open_gaps(db, user_project.id)
    ]
    retrieval = [
        {
            "id": row.id,
            "concept_id": row.concept_id,
            "scheduled_for": row.scheduled_for.isoformat(),
            "prompt": row.prompt,
            "status": row.status.value,
        }
        for row in due_retrieval_checks(db, user_project.id)
    ]
    return {
        "user_project_id": user_project.id,
        "project_id": user_project.project_id,
        "current_milestone_id": position.get("milestone_id"),
        "current_user_milestone_id": position.get("user_milestone_id"),
        "current_concept_id": position.get("current_concept_id"),
        "concept_state": position.get("concept_state"),
        "project_complete": position.get("project_complete"),
        "milestones": milestones_out,
        "known_gaps": gaps,
        "due_retrieval_checks": retrieval,
    }


def reset_from_milestone(
    db: Session, user_project: UserProject, restart_from_order: int
) -> None:
    """Reset concept states for this milestone and later ones."""
    later_ids: set[str] = set()
    for um in user_project.user_milestones:
        if um.milestone and um.milestone.order_index >= restart_from_order:
            later_ids.update(concept_ids_for_milestone(db, um.milestone.id))
    for row in (
        db.query(ConceptState)
        .filter(
            ConceptState.user_project_id == user_project.id,
            ConceptState.concept_id.in_(later_ids or ["__none__"]),
        )
        .all()
    ):
        row.status = ConceptStatus.locked
        row.evidence = empty_evidence()
        row.attempt_count = 0
        row.hints_used = 0
        row.hint_level = -1
        row.last_explanation = ""
        row.verified_via_skip = False
        row.diagnostic_answers = []
    db.query(KnowledgeGap).filter(
        KnowledgeGap.user_project_id == user_project.id,
        KnowledgeGap.blocked_concept_id.in_(later_ids or ["__none__"]),
    ).delete(synchronize_session=False)
    apply_unlocks(db, user_project)
