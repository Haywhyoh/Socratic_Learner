from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.agents.graph import build_chat_graph, build_start_graph
from app.agents.llm import get_coach_llm
from app.agents.policies import (
    MAX_REVIEW_ATTEMPTS,
    current_teach_concepts,
    message_looks_like_attempt,
)
from app.agents.state import CatalogMilestone, CoachState
from app.models.coach import (
    CardCheckpoint,
    ConceptCard,
    ConceptMastery,
    HintReveal,
    LearnerKnowledge,
    LearnerState,
    MentorSession,
    MentorSessionStatus,
    MentorTurn,
    MentorTurnRole,
    MilestoneReview,
    MilestoneReviewVerdict,
    RoadmapItem,
    TeachingFlag,
)
from app.models.project import (
    UserMilestone,
    UserMilestoneStatus,
    UserProject,
)
from app.models.user import User
from app.schemas.coach import AssessmentAnswer, RoadmapConceptRead, RoadmapMilestoneRead
from app.services import learning as learning_service


def _user_project(db: Session, user: User, user_project_id: int) -> UserProject:
    return learning_service.get_user_project(db, user, user_project_id)


def _catalog(user_project: UserProject) -> list[CatalogMilestone]:
    # This learner's own generated curriculum (each learner gets their own
    # milestone set), not the shared catalog template on Project.milestones.
    milestones = sorted(
        (um.milestone for um in user_project.user_milestones if um.milestone is not None),
        key=lambda m: m.order_index,
    )
    return [
        {
            "id": milestone.id,
            "title": milestone.title,
            "order_index": milestone.order_index,
            "concepts": list(milestone.concepts or []),
            "questions": list(milestone.questions or []),
            "success_criteria": milestone.success_criteria,
            "description": milestone.description,
        }
        for milestone in milestones
    ]


def current_user_milestone(user_project: UserProject) -> UserMilestone | None:
    pending = [
        um
        for um in user_project.user_milestones
        if um.status == UserMilestoneStatus.pending and um.milestone is not None
    ]
    pending.sort(key=lambda um: um.milestone.order_index)
    return pending[0] if pending else None


def _session(db: Session, user_project: UserProject) -> MentorSession:
    session = (
        db.query(MentorSession)
        .options(joinedload(MentorSession.turns))
        .filter(MentorSession.user_project_id == user_project.id)
        .first()
    )
    if session is None:
        session = MentorSession(
            user_project_id=user_project.id,
            status=MentorSessionStatus.needs_assessment,
        )
        db.add(session)
        db.flush()
    return session


def _knowledge_profile(db: Session, user_project_id: int) -> dict[str, str]:
    rows = (
        db.query(LearnerKnowledge)
        .filter(LearnerKnowledge.user_project_id == user_project_id)
        .all()
    )
    return {row.concept_name: row.mastery.value for row in rows}


def _persist_knowledge(db: Session, user_project_id: int, profile: dict[str, str]) -> None:
    existing = {
        row.concept_name: row
        for row in db.query(LearnerKnowledge)
        .filter(LearnerKnowledge.user_project_id == user_project_id)
        .all()
    }
    for name, mastery in profile.items():
        row = existing.get(name)
        value = ConceptMastery(mastery)
        if row is None:
            db.add(
                LearnerKnowledge(
                    user_project_id=user_project_id,
                    concept_name=name,
                    mastery=value,
                )
            )
        else:
            row.mastery = value


def _persist_roadmap(
    db: Session,
    user_project_id: int,
    roadmap: list[dict],
) -> None:
    db.query(RoadmapItem).filter(RoadmapItem.user_project_id == user_project_id).delete()
    for item in roadmap:
        for concept in item.get("concepts") or []:
            db.add(
                RoadmapItem(
                    user_project_id=user_project_id,
                    milestone_id=item["milestone_id"],
                    concept_name=concept["name"],
                    teaching=TeachingFlag(concept["teaching"]),
                )
            )


def _persist_cards(
    db: Session,
    user_project_id: int,
    milestone_id: int,
    cards: list[dict],
) -> list[ConceptCard]:
    stored: list[ConceptCard] = []
    existing = {
        card.name: card
        for card in db.query(ConceptCard)
        .filter(
            ConceptCard.user_project_id == user_project_id,
            ConceptCard.milestone_id == milestone_id,
        )
        .all()
    }
    for draft in cards:
        current = existing.get(draft["name"])
        payload = {
            "why_it_matters": draft["why_it_matters"],
            "research_questions": list(draft.get("research_questions") or []),
            "resources": list(draft.get("resources") or []),
            "checkpoint": draft["checkpoint"],
            "explanation": draft.get("explanation") or "",
        }
        if current is None:
            current = ConceptCard(
                user_project_id=user_project_id,
                milestone_id=milestone_id,
                name=draft["name"],
                **payload,
            )
            db.add(current)
            db.flush()
        else:
            for key, value in payload.items():
                setattr(current, key, value)
        stored.append(current)
    return stored


def _get_or_create_learner_state(
    db: Session, user_project_id: int, milestone_id: int
) -> LearnerState:
    row = (
        db.query(LearnerState)
        .filter(
            LearnerState.user_project_id == user_project_id,
            LearnerState.milestone_id == milestone_id,
        )
        .first()
    )
    if row is None:
        row = LearnerState(
            user_project_id=user_project_id,
            milestone_id=milestone_id,
            question_index=0,
            questions_passed=0,
            attempts=[],
            researched_concepts=[],
            failed_at=[],
            can_explain=[],
            can_reproduce=False,
            help_received=0,
        )
        db.add(row)
        db.flush()
    return row


def _roadmap_read(db: Session, user_project: UserProject) -> list[RoadmapMilestoneRead]:
    items = (
        db.query(RoadmapItem)
        .options(joinedload(RoadmapItem.milestone))
        .filter(RoadmapItem.user_project_id == user_project.id)
        .all()
    )
    profile = _knowledge_profile(db, user_project.id)
    grouped: dict[int, RoadmapMilestoneRead] = {}
    for item in items:
        milestone = item.milestone
        bucket = grouped.get(item.milestone_id)
        if bucket is None:
            bucket = RoadmapMilestoneRead(
                milestone_id=item.milestone_id,
                title=milestone.title if milestone else "",
                order_index=milestone.order_index if milestone else 0,
                concepts=[],
            )
            grouped[item.milestone_id] = bucket
        bucket.concepts.append(
            RoadmapConceptRead(
                name=item.concept_name,
                teaching=item.teaching,
                mastery=ConceptMastery(
                    profile.get(item.concept_name, ConceptMastery.unknown.value)
                ),
            )
        )
    return sorted(grouped.values(), key=lambda row: row.order_index)


def _cards_for_milestone(
    db: Session, user_project_id: int, milestone_id: int
) -> list[ConceptCard]:
    return (
        db.query(ConceptCard)
        .filter(
            ConceptCard.user_project_id == user_project_id,
            ConceptCard.milestone_id == milestone_id,
        )
        .order_by(ConceptCard.id)
        .all()
    )


def _max_hint_level(db: Session, user_milestone_id: int) -> int:
    levels = [
        row.level
        for row in db.query(HintReveal)
        .filter(HintReveal.user_milestone_id == user_milestone_id)
        .all()
    ]
    return max(levels) if levels else -1


def _has_recent_tested_attempt(learner_state: LearnerState | None) -> bool:
    if learner_state is None:
        return False
    for attempt in reversed(list(learner_state.attempts or [])):
        if isinstance(attempt, dict) and attempt.get("tested") is True:
            return True
    return False


def _effort(
    db: Session,
    session: MentorSession,
    user_milestone: UserMilestone | None,
    message: str,
) -> dict[str, object]:
    last_hint_at = None
    if user_milestone is not None:
        last = (
            db.query(HintReveal)
            .filter(HintReveal.user_milestone_id == user_milestone.id)
            .order_by(HintReveal.created_at.desc(), HintReveal.id.desc())
            .first()
        )
        if last is not None:
            last_hint_at = last.created_at
    turns_since = 0
    for turn in session.turns:
        if last_hint_at is not None and turn.created_at <= last_hint_at:
            continue
        if turn.role == MentorTurnRole.learner:
            turns_since += 1
    checkpoint_since = False
    learner_state = None
    if user_milestone is not None:
        cards = _cards_for_milestone(db, session.user_project_id, user_milestone.milestone_id)
        card_ids = [card.id for card in cards]
        if card_ids:
            query = db.query(CardCheckpoint).filter(CardCheckpoint.card_id.in_(card_ids))
            if last_hint_at is not None:
                query = query.filter(CardCheckpoint.created_at > last_hint_at)
            checkpoint_since = query.first() is not None
        learner_state = (
            db.query(LearnerState)
            .filter(
                LearnerState.user_project_id == session.user_project_id,
                LearnerState.milestone_id == user_milestone.milestone_id,
            )
            .first()
        )
    return {
        "learner_turns_since_hint": turns_since,
        "checkpoint_since_hint": checkpoint_since,
        "attempt_message": message_looks_like_attempt(message),
        "tested_attempt": _has_recent_tested_attempt(learner_state),
    }


def _base_state(user_project: UserProject, user_milestone: UserMilestone | None) -> CoachState:
    catalog = _catalog(user_project)
    milestone = user_milestone.milestone if user_milestone else None
    resources = [
        {"title": str(item.get("title", "")), "url": str(item.get("url", ""))}
        for item in (user_project.project.recommended_resources or [])
        if isinstance(item, dict)
    ]
    return {
        "user_project_id": user_project.id,
        "milestone_id": milestone.id if milestone else None,
        "project_title": user_project.project.title,
        "milestone_title": milestone.title if milestone else "",
        "constraints": list(user_project.project.constraints or []),
        "success_criteria": milestone.success_criteria if milestone else "",
        "milestone_questions": list(milestone.questions or []) if milestone else [],
        "catalog_milestones": catalog,
        "resources": resources,
    }


def _learner_state_payload(row: LearnerState, questions: list[str]) -> dict:
    index = row.question_index
    current = questions[index] if 0 <= index < len(questions) else None
    return {
        "user_project_id": row.user_project_id,
        "milestone_id": row.milestone_id,
        "question_index": row.question_index,
        "questions_passed": row.questions_passed,
        "question_attempts": row.question_attempts,
        "questions_total": len(questions),
        "current_question": current,
        "attempts": list(row.attempts or []),
        "researched_concepts": list(row.researched_concepts or []),
        "failed_at": list(row.failed_at or []),
        "can_explain": list(row.can_explain or []),
        "can_reproduce": row.can_reproduce,
        "help_received": row.help_received,
        "questions_complete": index >= len(questions),
    }


def start_coach(
    db: Session,
    user: User,
    user_project_id: int,
    answers: list[AssessmentAnswer] | None = None,
) -> dict:
    user_project = _user_project(db, user, user_project_id)
    session = _session(db, user_project)
    current = current_user_milestone(user_project)
    profile = _knowledge_profile(db, user_project.id)
    if session.status == MentorSessionStatus.active and not answers:
        learner_state = None
        questions: list[str] = []
        reply = None
        if current is not None:
            questions = list(current.milestone.questions or [])
            learner_state = _get_or_create_learner_state(
                db, user_project.id, current.milestone_id
            )
            if learner_state.question_index < len(questions):
                reply = questions[learner_state.question_index]
            else:
                constraints = list(user_project.project.constraints or [])
                constraint = constraints[0] if constraints else "follow constraints"
                reply = (
                    f"Go build. Constraint: {constraint}; "
                    f"success: {current.milestone.success_criteria}."
                )
        db.commit()
        return {
            "status": session.status,
            "user_project_id": user_project.id,
            "session_id": session.id,
            "milestone_id": current.milestone_id if current else None,
            "assessment_questions": [],
            "roadmap": _roadmap_read(db, user_project),
            "cards": [],
            "reply": reply,
            "current_question": reply if current and learner_state and learner_state.question_index < len(questions) else None,
            "answer_status": None,
            "resumed": True,
            "learner_state": (
                _learner_state_payload(learner_state, questions) if learner_state else None
            ),
        }
    answer_map = {item.concept: item.mastery.value for item in answers or []}
    state: CoachState = _base_state(user_project, current)
    state["mode"] = "start"
    state["knowledge_profile"] = profile
    state["assessment_answers"] = answer_map
    if current is not None:
        learner_state = _get_or_create_learner_state(
            db, user_project.id, current.milestone_id
        )
        state["question_index"] = learner_state.question_index
        state["questions_passed"] = learner_state.questions_passed
    graph = build_start_graph(get_coach_llm())
    result = graph.invoke(state)
    status_value = result.get("status") or MentorSessionStatus.needs_assessment.value
    if status_value == MentorSessionStatus.needs_assessment.value:
        session.status = MentorSessionStatus.needs_assessment
        db.commit()
        db.refresh(session)
        return {
            "status": session.status,
            "user_project_id": user_project.id,
            "session_id": session.id,
            "milestone_id": current.milestone_id if current else None,
            "assessment_questions": result.get("assessment_questions") or [],
            "roadmap": [],
            "cards": [],
            "reply": None,
            "current_question": None,
            "answer_status": None,
            "learner_state": None,
        }

    profile = result.get("knowledge_profile") or profile
    _persist_knowledge(db, user_project.id, profile)
    _persist_roadmap(db, user_project.id, result.get("roadmap") or [])
    if current is not None:
        _persist_cards(
            db, user_project.id, current.milestone_id, result.get("cards") or []
        )
        learner_state = _get_or_create_learner_state(
            db, user_project.id, current.milestone_id
        )
    else:
        learner_state = None
    session.status = MentorSessionStatus.active
    reply = result.get("reply") or ""
    db.add(
        MentorTurn(
            session_id=session.id,
            role=MentorTurnRole.system,
            content=reply,
        )
    )
    db.commit()
    db.refresh(session)
    questions = list(current.milestone.questions or []) if current else []
    return {
        "status": session.status,
        "user_project_id": user_project.id,
        "session_id": session.id,
        "milestone_id": current.milestone_id if current else None,
        "assessment_questions": [],
        "roadmap": _roadmap_read(db, user_project),
        "cards": [],
        "reply": reply,
        "current_question": result.get("current_question"),
        "answer_status": result.get("answer_status"),
        "learner_state": (
            _learner_state_payload(learner_state, questions) if learner_state else None
        ),
    }


def get_roadmap(db: Session, user: User, user_project_id: int) -> list[RoadmapMilestoneRead]:
    user_project = _user_project(db, user, user_project_id)
    return _roadmap_read(db, user_project)


def get_learner_state(db: Session, user: User, user_project_id: int) -> dict:
    user_project = _user_project(db, user, user_project_id)
    current = current_user_milestone(user_project)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending milestone",
        )
    row = _get_or_create_learner_state(db, user_project.id, current.milestone_id)
    db.commit()
    return _learner_state_payload(row, list(current.milestone.questions or []))


def record_sandbox_test_attempt(
    db: Session,
    user: User,
    user_project_id: int,
    *,
    outcome: str,
    summary: str,
    passed: bool,
) -> None:
    """Persist a real sandbox test run onto the current milestone learner state."""
    user_project = _user_project(db, user, user_project_id)
    current = current_user_milestone(user_project)
    if current is None:
        return
    row = _get_or_create_learner_state(db, user_project.id, current.milestone_id)
    now = datetime.now(UTC).isoformat()
    attempts = list(row.attempts or [])
    attempts.append(
        {
            "summary": summary[:200],
            "tested": True,
            "outcome": outcome,
            "at": now,
            "source": "sandbox_test",
        }
    )
    row.attempts = attempts[-20:]
    if passed:
        row.can_reproduce = True
    else:
        failed = list(row.failed_at or [])
        failed.append({"description": summary[:200], "at": now, "source": "sandbox_test"})
        row.failed_at = failed[-20:]
    db.add(row)
    db.commit()


def list_cards(
    db: Session, user: User, user_milestone_id: int
) -> list[ConceptCard]:
    user_milestone = _owned_user_milestone(db, user, user_milestone_id)
    return _cards_for_milestone(
        db, user_milestone.user_project_id, user_milestone.milestone_id
    )


def _owned_user_milestone(db: Session, user: User, user_milestone_id: int) -> UserMilestone:
    user_milestone = (
        db.query(UserMilestone)
        .options(
            joinedload(UserMilestone.milestone),
            joinedload(UserMilestone.user_project).joinedload(UserProject.enrollment),
            joinedload(UserMilestone.user_project).joinedload(UserProject.project),
        )
        .filter(UserMilestone.id == user_milestone_id)
        .first()
    )
    if (
        user_milestone is None
        or user_milestone.user_project.enrollment.user_id != user.id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    return user_milestone


def post_message(
    db: Session,
    user: User,
    user_project_id: int,
    message: str,
) -> dict:
    user_project = _user_project(db, user, user_project_id)
    session = _session(db, user_project)
    if session.status != MentorSessionStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete the knowledge assessment first (POST .../coach/start with answers)",
        )
    current = current_user_milestone(user_project)
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No pending milestone to coach against",
        )
    learner_state = _get_or_create_learner_state(
        db, user_project.id, current.milestone_id
    )
    profile = _knowledge_profile(db, user_project.id)
    roadmap_state = [
        {
            "milestone_id": item.milestone_id,
            "title": item.title,
            "order_index": item.order_index,
            "concepts": [concept.model_dump() for concept in item.concepts],
        }
        for item in _roadmap_read(db, user_project)
    ]
    cards = _cards_for_milestone(db, user_project.id, current.milestone_id)
    card_drafts = [
        {
            "name": card.name,
            "why_it_matters": card.why_it_matters,
            "research_questions": list(card.research_questions or []),
            "resources": list(card.resources or []),
            "checkpoint": card.checkpoint,
            "explanation": card.explanation,
        }
        for card in cards
    ]
    questions = list(current.milestone.questions or [])
    state: CoachState = _base_state(user_project, current)
    state.update(
        {
            "mode": "chat",
            "knowledge_profile": profile,
            "roadmap": roadmap_state,
            "cards": card_drafts,
            "current_concepts": current_teach_concepts(
                roadmap_state, current.milestone_id, profile
            ),
            "hint_level": _max_hint_level(db, current.id),
            "effort": _effort(db, session, current, message),
            "learner_message": message,
            "question_index": learner_state.question_index,
            "questions_passed": learner_state.questions_passed,
            "question_attempts": learner_state.question_attempts,
            "current_question": (
                questions[learner_state.question_index]
                if 0 <= learner_state.question_index < len(questions)
                else None
            ),
        }
    )
    result = build_chat_graph(get_coach_llm()).invoke(state)
    db.add(
        MentorTurn(session_id=session.id, role=MentorTurnRole.learner, content=message)
    )
    reply = result.get("reply") or ""
    db.add(MentorTurn(session_id=session.id, role=MentorTurnRole.tutor, content=reply))

    # Persist learner state updates
    now = datetime.now(UTC).isoformat()
    attempts = list(learner_state.attempts or [])
    attempts.append(
        {
            "summary": message[:200],
            "tested": False,
            "outcome": result.get("answer_status"),
            "at": now,
        }
    )
    learner_state.attempts = attempts[-20:]
    if result.get("answer_status") == "passed":
        learner_state.question_index = int(result.get("question_index", learner_state.question_index))
        learner_state.questions_passed = int(
            result.get("questions_passed", learner_state.questions_passed)
        )
        learner_state.question_attempts = 0
    elif result.get("answer_status") == "advanced_with_gap":
        learner_state.question_index = int(result.get("question_index", learner_state.question_index))
        learner_state.question_attempts = 0
        failed = list(learner_state.failed_at or [])
        failed.append(
            {
                "description": f"Advanced without a confirmed answer: {result.get('gap_question', '')}"[:200],
                "at": now,
                "capped": True,
            }
        )
        learner_state.failed_at = failed[-20:]
    elif result.get("answer_status") == "push_back":
        learner_state.question_attempts = int(
            result.get("question_attempts", learner_state.question_attempts + 1)
        )
        failed = list(learner_state.failed_at or [])
        failed.append({"description": message[:200], "at": now})
        learner_state.failed_at = failed[-20:]

    hint_level = None
    blocked = result.get("hint_blocked_reason")
    if result.get("intent") == "hint":
        learner_state.help_received = int(learner_state.help_received or 0) + 1
        if not blocked:
            hint_level = int(result.get("hint_level", 0))
            db.add(
                HintReveal(
                    user_milestone_id=current.id,
                    level=hint_level,
                    content=reply,
                )
            )

    db.commit()
    db.refresh(learner_state)
    session = (
        db.query(MentorSession)
        .options(joinedload(MentorSession.turns))
        .filter(MentorSession.id == session.id)
        .one()
    )
    return {
        "intent": result.get("intent") or "answer",
        "reply": reply,
        "hint_level": hint_level if result.get("intent") == "hint" else None,
        "hint_blocked_reason": blocked,
        "policy_flags": result.get("policy_flags") or [],
        "cards": [],
        "turns": session.turns[-4:],
        "current_question": result.get("current_question"),
        "answer_status": result.get("answer_status"),
        "push_back": result.get("push_back"),
        "learner_state": _learner_state_payload(learner_state, questions),
    }


def request_hint(db: Session, user: User, user_milestone_id: int) -> dict:
    user_milestone = _owned_user_milestone(db, user, user_milestone_id)
    return post_message(
        db,
        user,
        user_milestone.user_project_id,
        "I am stuck — please give me a hint.",
    )


def submit_checkpoint(
    db: Session, user: User, card_id: int, answer: str
) -> CardCheckpoint:
    card = db.get(ConceptCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    user_project = learning_service.get_user_project(db, user, card.user_project_id)
    passed = len(answer.strip()) >= 40 and "idk" not in answer.lower()
    row = CardCheckpoint(card_id=card.id, answer=answer, passed=passed)
    db.add(row)
    knowledge = (
        db.query(LearnerKnowledge)
        .filter(
            LearnerKnowledge.user_project_id == user_project.id,
            LearnerKnowledge.concept_name == card.name,
        )
        .first()
    )
    if knowledge is None:
        knowledge = LearnerKnowledge(
            user_project_id=user_project.id,
            concept_name=card.name,
            mastery=ConceptMastery.familiar if passed else ConceptMastery.unknown,
            researched=True,
        )
        db.add(knowledge)
    else:
        knowledge.researched = True
        if passed and knowledge.mastery == ConceptMastery.unknown:
            knowledge.mastery = ConceptMastery.familiar
    learner_state = _get_or_create_learner_state(
        db, user_project.id, card.milestone_id
    )
    researched = list(learner_state.researched_concepts or [])
    if card.name not in researched:
        researched.append(card.name)
        learner_state.researched_concepts = researched
    if passed:
        explained = list(learner_state.can_explain or [])
        if card.name not in explained:
            explained.append(card.name)
            learner_state.can_explain = explained
    db.commit()
    db.refresh(row)
    return row


def ensure_cards_for_current_milestone(db: Session, user: User, user_project_id: int) -> None:
    user_project = _user_project(db, user, user_project_id)
    session = (
        db.query(MentorSession)
        .filter(MentorSession.user_project_id == user_project.id)
        .first()
    )
    if session is None or session.status != MentorSessionStatus.active:
        return
    current = current_user_milestone(user_project)
    if current is None:
        return
    _get_or_create_learner_state(db, user_project.id, current.milestone_id)
    existing = _cards_for_milestone(db, user_project.id, current.milestone_id)
    if existing:
        db.commit()
        return
    profile = _knowledge_profile(db, user_project.id)
    state: CoachState = _base_state(user_project, current)
    state["knowledge_profile"] = profile
    state["assessment_answers"] = profile
    result = build_start_graph(get_coach_llm()).invoke(state)
    _persist_roadmap(db, user_project.id, result.get("roadmap") or [])
    _persist_cards(db, user_project.id, current.milestone_id, result.get("cards") or [])
    db.commit()
