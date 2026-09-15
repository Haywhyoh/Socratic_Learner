"""Mentor service: learning-state context in, structured contract out."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.agents.llm import get_coach_llm
from app.agents.mentor_graph import _behaviors_for, build_mentor_graph
from app.agents.misconceptions import classify_learner_turn, is_boot_message
from app.agents.policies import (
    MAX_REVIEW_ATTEMPTS,
    message_looks_like_attempt,
)
from app.models.coach import (
    HintReveal,
    MentorSession,
    MentorSessionStatus,
    MentorTurn,
    MentorTurnRole,
    MilestoneReview,
    MilestoneReviewVerdict,
)
from app.models.curriculum import Concept, ConceptDependency
from app.models.learning_state import (
    ConceptState,
    ConceptStatus,
    DefenseVerdict,
    ProjectDefense,
    Reflection,
    ResearchRecord,
    RetrievalCheck,
    RetrievalCheckStatus,
)
from app.models.project import UserMilestone, UserProject
from app.models.sandbox import SandboxWorkspace
from app.models.user import User
from app.services import curriculum_graph
from app.services import learning as learning_service


def _looks_like_concept_id(value: str) -> bool:
    cleaned = value.strip()
    return bool(cleaned) and " " not in cleaned and len(cleaned) <= 100


def _normalize_gap(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict) and value.get("concept"):
        concept = str(value["concept"]).strip()
        if not _looks_like_concept_id(concept):
            return None
        try:
            confidence = float(value.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        return {"concept": concept, "confidence": confidence}
    if isinstance(value, str) and _looks_like_concept_id(value):
        return {"concept": value.strip(), "confidence": 0.0}
    return None


def _user_project(db: Session, user: User, user_project_id: int) -> UserProject:
    return learning_service.get_user_project(db, user, user_project_id)


def current_user_milestone(user_project: UserProject) -> UserMilestone | None:
    return curriculum_graph.current_user_milestone(user_project)


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
            status=MentorSessionStatus.active,
        )
        db.add(session)
        db.flush()
    elif session.status == MentorSessionStatus.needs_assessment:
        session.status = MentorSessionStatus.active
    return session


def _append_turn(db: Session, session: MentorSession, role: MentorTurnRole, content: str) -> None:
    db.add(MentorTurn(session_id=session.id, role=role, content=content))


def _concept_payload(concept: Concept | None) -> dict[str, Any]:
    if concept is None:
        return {}
    return {
        "id": concept.id,
        "title": concept.title,
        "category": concept.category,
        "description": concept.description,
        "learning_objectives": list(concept.learning_objectives or []),
        "misconceptions": list(concept.misconceptions or []),
        "diagnostic_questions": list(concept.diagnostic_questions or []),
        "research_questions": list(concept.research_questions or []),
        "resources": list(concept.resources or []),
        "hints": list(concept.hints or []),
        "mastery_requirements": dict(concept.mastery_requirements or {}),
    }


def _state_payload(row: ConceptState | None, position: dict[str, Any]) -> dict[str, Any]:
    evidence = dict((row.evidence if row else None) or curriculum_graph.empty_evidence())
    return {
        "user_project_id": row.user_project_id if row else position.get("user_milestone_id"),
        "concept_id": row.concept_id if row else position.get("current_concept_id"),
        "status": row.status.value if row else position.get("concept_state"),
        "evidence": evidence,
        "attempt_count": row.attempt_count if row else 0,
        "hints_used": row.hints_used if row else 0,
        "hint_level": row.hint_level if row else -1,
        "last_explanation": row.last_explanation if row else "",
        "milestone_id": position.get("milestone_id"),
        "user_milestone_id": position.get("user_milestone_id"),
    }


def _prereq_states(db: Session, user_project: UserProject, concept_id: str | None) -> dict[str, str]:
    if not concept_id:
        return {}
    deps = (
        db.query(ConceptDependency)
        .filter(ConceptDependency.concept_id == concept_id)
        .all()
    )
    states = curriculum_graph.states_by_concept(db, user_project.id)
    return {
        dep.requires_concept_id: (
            states[dep.requires_concept_id].status.value
            if dep.requires_concept_id in states
            else ConceptStatus.locked.value
        )
        for dep in deps
    }


def _test_counts(db: Session, user_project_id: int) -> tuple[dict[str, int], str]:
    row = (
        db.query(SandboxWorkspace)
        .filter(SandboxWorkspace.user_project_id == user_project_id)
        .first()
    )
    summary = (row.last_test_summary if row else None) or {}
    counts = {
        "passed": int(summary.get("passed") or 0),
        "failed": int(summary.get("failed") or 0),
        "errors": int(summary.get("errors") or 0),
    }
    return counts, str(summary.get("summary") or "")


def _mentor_context(db: Session, user_project: UserProject) -> dict[str, Any]:
    position = curriculum_graph.resolve_current_position(db, user_project)
    concept_id = position.get("current_concept_id")
    concept = db.get(Concept, concept_id) if concept_id else None
    state_row = (
        curriculum_graph.get_or_create_state(db, user_project, str(concept_id))
        if concept_id
        else None
    )
    tests, tests_summary = _test_counts(db, user_project.id)
    gaps = [
        {"concept": g.suspected_concept_id, "confidence": g.confidence}
        for g in curriculum_graph.open_gaps(db, user_project.id)
        if not concept_id or g.blocked_concept_id == concept_id
    ]
    status = (state_row.status.value if state_row else None) or ConceptStatus.available.value
    um = current_user_milestone(user_project)
    awaiting_reflection = False
    if um and um.milestone and curriculum_graph.milestone_concepts_complete(
        db, user_project, um.milestone
    ):
        awaiting_reflection = not curriculum_graph.reflection_complete(db, um.id)
    gap_reason = ""
    if gaps:
        gap_reason = curriculum_graph.explain_gap_reason(
            db, str(concept_id or ""), str(gaps[0]["concept"])
        )
    later_titles = curriculum_graph.later_concept_titles(
        db, list(position.get("later_concepts") or [])
    )
    return {
        "position": position,
        "concept": concept,
        "state_row": state_row,
        "graph_state": {
            "project": "javascript-backend-framework",
            "project_title": user_project.project.title if user_project.project else "",
            "current_milestone": f"M{position.get('milestone_order') or 0:02d}",
            "current_milestone_title": position.get("milestone_title") or "",
            "current_concept": concept_id or "",
            "concept_title": concept.title if concept else "",
            "concept_description": concept.description if concept else "",
            "concept_state": status,
            "prerequisites": _prereq_states(db, user_project, str(concept_id) if concept_id else None),
            "known_gaps": gaps,
            "attempt_count": state_row.attempt_count if state_row else 0,
            "hints_used": state_row.hints_used if state_row else 0,
            "hint_level": state_row.hint_level if state_row else -1,
            "tests": tests,
            "tests_summary": tests_summary,
            "learner_last_explanation": state_row.last_explanation if state_row else "",
            "allowed_ai_behavior": _behaviors_for(
                status, needs_build=curriculum_graph.needs_build(concept) if concept else False
            ),
            "later_concepts": later_titles,
            "resources": list((concept.resources if concept else None) or []),
            "diagnostic_questions": list((concept.diagnostic_questions if concept else None) or []),
            "research_questions": list((concept.research_questions if concept else None) or []),
            "misconceptions": list((concept.misconceptions if concept else None) or []),
            "diagnostic_answers": list((state_row.diagnostic_answers if state_row else None) or []),
            "hints": list((concept.hints if concept else None) or []),
            "learning_objectives": list((concept.learning_objectives if concept else None) or []),
            "needs_build": curriculum_graph.needs_build(concept) if concept else False,
            "gap_reason": gap_reason,
            "awaiting_reflection": awaiting_reflection,
            "project_complete": bool(position.get("project_complete")),
        },
    }


def _apply_next_state(
    db: Session,
    user_project: UserProject,
    concept_id: str | None,
    next_state: str | None,
) -> None:
    if not concept_id or not next_state:
        return
    try:
        status = ConceptStatus(next_state)
    except ValueError:
        return
    row = curriculum_graph.get_or_create_state(db, user_project, concept_id)
    if row.status in {ConceptStatus.mastered, ConceptStatus.verified}:
        return
    if status == ConceptStatus.mastered:
        curriculum_graph.try_master(db, user_project, concept_id)
        return
    curriculum_graph.set_status(db, user_project, concept_id, status)


def _run_mentor(
    db: Session,
    user_project: UserProject,
    message: str,
    *,
    effort: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session = _session(db, user_project)
    ctx = _mentor_context(db, user_project)
    graph_state = dict(ctx["graph_state"])
    state_row = ctx["state_row"]
    concept = ctx["concept"]
    prior_answers = list((state_row.diagnostic_answers if state_row else None) or [])
    classified: dict[str, Any] = {
        "branch": None,
        "misconception": None,
        "phase": None,
    }
    if state_row and not is_boot_message(message):
        classified = classify_learner_turn(
            message,
            list((concept.misconceptions if concept else None) or []),
            prior_answers,
            attempt_count_after=int(state_row.attempt_count or 0) + 1,
        )
        misc = classified.get("misconception") or {}
        curriculum_graph.record_learner_answer(
            db,
            user_project,
            state_row.concept_id,
            message,
            misconception_id=misc.get("id") if isinstance(misc, dict) else None,
            phase=classified.get("phase"),
        )
        graph_state["attempt_count"] = int(state_row.attempt_count or 0)
        graph_state["learner_last_explanation"] = message
    graph_state["diagnostic_answers"] = prior_answers
    graph_state["misconception_branch"] = classified.get("branch")
    graph_state["identified_misconception"] = classified.get("misconception")
    graph_state["learner_message"] = message
    graph_state["effort"] = effort or {
        "learner_turns_since_hint": 1,
        "checkpoint_since_hint": False,
        "attempt_message": message_looks_like_attempt(message),
        "tested_attempt": False,
    }
    compiled = build_mentor_graph(get_coach_llm())
    result = compiled.invoke(graph_state)
    contract = dict(result.get("contract") or {})
    reply = str(result.get("reply") or contract.get("message") or "")
    next_state = str(result.get("next_state") or contract.get("next_state") or "")
    concept_id = ctx["graph_state"].get("current_concept") or None
    if next_state:
        _apply_next_state(db, user_project, str(concept_id) if concept_id else None, next_state)
    if result.get("identified_gap") and concept_id:
        suspects = curriculum_graph.suspect_gaps(db, user_project, str(concept_id))
        curriculum_graph.persist_suspected_gaps(db, user_project, str(concept_id), suspects)
    _append_turn(db, session, MentorTurnRole.tutor, reply)
    db.commit()
    db.refresh(session)
    position = curriculum_graph.resolve_current_position(db, user_project)
    state_row = (
        curriculum_graph.get_or_create_state(db, user_project, str(position["current_concept_id"]))
        if position.get("current_concept_id")
        else None
    )
    return {
        "intent": contract.get("intent") or result.get("intent") or "MENTOR",
        "action": contract.get("action") or "ASK_QUESTION",
        "reply": reply,
        "hint_level": result.get("hint_level", contract.get("hint_level")),
        "hint_blocked_reason": result.get("hint_blocked_reason"),
        "policy_flags": list(result.get("policy_flags") or []),
        "turns": session.turns,
        "current_question": reply if contract.get("action") in {
            "ASK_QUESTION", "ASK_RESEARCH", "ASK_DIAGNOSTIC_QUESTION",
            "ASK_REFLECTION", "ASK_DEFENSE",
        } else None,
        "answer_status": contract.get("action"),
        "push_back": None,
        "learner_state": _state_payload(state_row, position),
        "contract": {
            "intent": contract.get("intent") or "MENTOR",
            "action": contract.get("action") or "ASK_QUESTION",
            "message": reply,
            "diagnostic_concept": contract.get("diagnostic_concept"),
            "identified_gap": _normalize_gap(
                contract.get("identified_gap") or result.get("identified_gap")
            ),
            "hint_level": contract.get("hint_level") or 0,
            "should_unlock": bool(contract.get("should_unlock") or result.get("should_unlock")),
            "next_state": next_state,
        },
        "concept": _concept_payload(ctx["concept"]),
        "position": position,
    }


def start_coach(
    db: Session,
    user: User,
    user_project_id: int,
    answers: list | None = None,
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    session = _session(db, user_project)
    curriculum_graph.initialize_learning_state(db, user_project)
    ctx = _mentor_context(db, user_project)
    state_row = ctx["state_row"]
    if state_row and state_row.status == ConceptStatus.available:
        curriculum_graph.introduce_concept(db, user_project, state_row.concept_id)
    result = _run_mentor(db, user_project, "What should I think about first?")
    position = result["position"]
    return {
        "status": MentorSessionStatus.active,
        "user_project_id": user_project.id,
        "session_id": session.id,
        "milestone_id": position.get("milestone_id"),
        "assessment_questions": [],
        "roadmap": [],
        "cards": [],
        "reply": result["reply"],
        "current_question": result["current_question"],
        "answer_status": result["answer_status"],
        "resumed": len(session.turns) > 2,
        "learner_state": result["learner_state"],
        "contract": result["contract"],
        "concept": result["concept"],
        "position": position,
        "graph": curriculum_graph.graph_payload(db, user_project),
    }


def post_message(
    db: Session, user: User, user_project_id: int, message: str
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    session = _session(db, user_project)
    _append_turn(db, session, MentorTurnRole.learner, message)
    ctx = _mentor_context(db, user_project)
    state_row = ctx["state_row"]
    if state_row and state_row.status == ConceptStatus.researching:
        # A substantial message during research is treated as notes + discussion.
        if len(message.strip()) >= 40:
            curriculum_graph.mark_discussing(db, user_project, state_row.concept_id)
    result = _run_mentor(db, user_project, message)
    return result


def get_graph(db: Session, user: User, user_project_id: int) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    return curriculum_graph.graph_payload(db, user_project)


def get_learner_state(db: Session, user: User, user_project_id: int) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    position = curriculum_graph.resolve_current_position(db, user_project)
    concept_id = position.get("current_concept_id")
    row = (
        curriculum_graph.get_or_create_state(db, user_project, str(concept_id))
        if concept_id
        else None
    )
    return _state_payload(row, position)


def request_hint(db: Session, user: User, user_milestone_id: int) -> dict[str, Any]:
    um = (
        db.query(UserMilestone)
        .options(joinedload(UserMilestone.user_project).joinedload(UserProject.enrollment))
        .filter(UserMilestone.id == user_milestone_id)
        .first()
    )
    if um is None or um.user_project.enrollment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    user_project = um.user_project
    position = curriculum_graph.resolve_current_position(db, user_project)
    concept_id = position.get("current_concept_id")
    result = _run_mentor(
        db,
        user_project,
        "hint",
        effort={
            "learner_turns_since_hint": 1,
            "checkpoint_since_hint": False,
            "attempt_message": True,
            "tested_attempt": False,
        },
    )
    if concept_id and not result.get("hint_blocked_reason"):
        row = curriculum_graph.get_or_create_state(db, user_project, str(concept_id))
        row.hints_used = int(row.hints_used or 0) + 1
        row.hint_level = int(result.get("hint_level") or row.hint_level)
        db.add(
            HintReveal(
                user_milestone_id=um.id,
                level=int(result.get("hint_level") or 0),
                content=result.get("reply") or "",
            )
        )
        db.commit()
    return result


def submit_research(
    db: Session,
    user: User,
    user_project_id: int,
    concept_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    record = ResearchRecord(
        user_project_id=user_project.id,
        concept_id=concept_id,
        question=str(payload.get("question") or ""),
        sources=list(payload.get("sources") or []),
        learner_notes=str(payload.get("learner_notes") or ""),
        learner_summary=str(payload.get("learner_summary") or ""),
        remaining_questions=str(payload.get("remaining_questions") or ""),
    )
    db.add(record)
    curriculum_graph.mark_discussing(db, user_project, concept_id)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "concept_id": record.concept_id,
        "question": record.question,
        "sources": record.sources,
        "learner_notes": record.learner_notes,
        "learner_summary": record.learner_summary,
        "remaining_questions": record.remaining_questions,
    }


def submit_explanation(
    db: Session, user: User, user_project_id: int, concept_id: str, answer: str
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    concept = db.get(Concept, concept_id)
    if concept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found")
    llm = get_coach_llm()
    result = llm.evaluate_explanation(
        concept_title=concept.title,
        concept_description=concept.description,
        objectives=list(concept.learning_objectives or []),
        answer=answer,
    )
    if result.get("passed"):
        curriculum_graph.explanation_passed(db, user_project, concept_id, answer)
    else:
        curriculum_graph.explanation_failed(db, user_project, concept_id, answer)
        suspects = curriculum_graph.suspect_gaps(db, user_project, concept_id)
        curriculum_graph.persist_suspected_gaps(db, user_project, concept_id, suspects)
    db.commit()
    row = curriculum_graph.get_or_create_state(db, user_project, concept_id)
    return {
        "passed": bool(result.get("passed")),
        "feedback": result.get("feedback"),
        "status": row.status.value,
        "evidence": dict(row.evidence or {}),
    }


def skip_diagnostic(
    db: Session, user: User, user_project_id: int, concept_id: str, answers: list[str]
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    result = curriculum_graph.evaluate_skip_diagnostic(db, user_project, concept_id, answers)
    db.commit()
    return result


def submit_reflection(
    db: Session, user: User, user_milestone_id: int, answers: dict[str, Any]
) -> dict[str, Any]:
    um = (
        db.query(UserMilestone)
        .options(joinedload(UserMilestone.user_project).joinedload(UserProject.enrollment))
        .filter(UserMilestone.id == user_milestone_id)
        .first()
    )
    if um is None or um.user_project.enrollment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    row = (
        db.query(Reflection).filter(Reflection.user_milestone_id == um.id).first()
    )
    if row is None:
        row = Reflection(user_milestone_id=um.id, answers=answers)
        db.add(row)
    else:
        row.answers = answers
    db.commit()
    db.refresh(row)
    return {"id": row.id, "user_milestone_id": um.id, "answers": row.answers}


DEFENSE_QUESTIONS = [
    "Why did you structure your router this way?",
    "What is the complexity of route lookup?",
    "How does middleware execution work?",
    "What happens when middleware doesn't call next()?",
    "How would you support async middleware?",
    "How would you handle concurrent requests?",
    "How would you add authentication?",
    "How would you prevent malformed HTTP requests?",
    "How would you scale this framework?",
    "What parts would you rewrite?",
]


def start_defense(db: Session, user: User, user_project_id: int) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    position = curriculum_graph.resolve_current_position(db, user_project)
    current = current_user_milestone(user_project)
    if not position.get("project_complete") and current is not None and current.milestone:
        later = [
            um
            for um in user_project.user_milestones
            if um.milestone and um.milestone.order_index > current.milestone.order_index
        ]
        if later:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Finish earlier milestones before the final defense",
            )
    row = (
        db.query(ProjectDefense)
        .filter(ProjectDefense.user_project_id == user_project.id)
        .first()
    )
    if row is None:
        row = ProjectDefense(
            user_project_id=user_project.id,
            questions=list(DEFENSE_QUESTIONS),
            verdict=DefenseVerdict.pending,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return {
        "id": row.id,
        "user_project_id": user_project.id,
        "questions": row.questions,
        "answers": row.answers,
        "verdict": row.verdict.value,
        "summary": row.summary,
        "attempts": row.attempts,
    }


def answer_defense(
    db: Session, user: User, user_project_id: int, answers: list[str]
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    row = (
        db.query(ProjectDefense)
        .filter(ProjectDefense.user_project_id == user_project.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Start the defense first")
    llm = get_coach_llm()
    graded = []
    all_passed = True
    for question, answer in zip(row.questions or DEFENSE_QUESTIONS, answers):
        result = llm.evaluate_understanding(
            question=str(question),
            answer=answer,
            milestone_title="Final engineering review",
        )
        passed = bool(result.get("passed"))
        all_passed = all_passed and passed
        graded.append(
            {
                "question": question,
                "answer": answer,
                "passed": passed,
                "feedback": result.get("feedback"),
            }
        )
    row.answers = graded
    row.attempts = int(row.attempts or 0) + 1
    if all_passed:
        row.verdict = DefenseVerdict.passed
        row.summary = "Defense passed — you can explain what you built."
    else:
        row.verdict = DefenseVerdict.needs_work
        row.summary = "Some answers were too thin. Revisit those design questions."
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "user_project_id": user_project.id,
        "questions": row.questions,
        "answers": row.answers,
        "verdict": row.verdict.value,
        "summary": row.summary,
        "attempts": row.attempts,
    }


def list_retrieval_checks(db: Session, user: User, user_project_id: int) -> list[dict[str, Any]]:
    user_project = _user_project(db, user, user_project_id)
    rows = (
        db.query(RetrievalCheck)
        .filter(RetrievalCheck.user_project_id == user_project.id)
        .order_by(RetrievalCheck.scheduled_for)
        .all()
    )
    return [
        {
            "id": row.id,
            "concept_id": row.concept_id,
            "scheduled_for": row.scheduled_for.isoformat(),
            "prompt": row.prompt,
            "status": row.status.value,
            "learner_response": row.learner_response,
        }
        for row in rows
    ]


def answer_retrieval(
    db: Session, user: User, user_project_id: int, check_id: int, answer: str
) -> dict[str, Any]:
    user_project = _user_project(db, user, user_project_id)
    row = db.get(RetrievalCheck, check_id)
    if row is None or row.user_project_id != user_project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check not found")
    row.learner_response = answer
    row.status = RetrievalCheckStatus.completed
    row.completed_at = datetime.now(UTC)
    if len(answer.strip()) >= 40:
        curriculum_graph.record_evidence(db, user_project, row.concept_id, retrieval=True)
    db.commit()
    return {
        "id": row.id,
        "concept_id": row.concept_id,
        "status": row.status.value,
        "learner_response": row.learner_response,
    }


def record_sandbox_test_attempt(
    db: Session,
    user: User,
    user_project_id: int,
    *,
    outcome: str,
    summary: str,
    passed: bool,
) -> None:
    user_project = _user_project(db, user, user_project_id)
    curriculum_graph.record_test_result(
        db, user_project, passed=passed, summary=summary
    )
    db.commit()


def get_milestone_review(
    db: Session, user: User, user_milestone_id: int
) -> MilestoneReview:
    um = (
        db.query(UserMilestone)
        .options(joinedload(UserMilestone.user_project).joinedload(UserProject.enrollment))
        .filter(UserMilestone.id == user_milestone_id)
        .first()
    )
    if um is None or um.user_project.enrollment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    review = (
        db.query(MilestoneReview)
        .filter(MilestoneReview.user_milestone_id == um.id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No review yet")
    return review


def request_milestone_review(
    db: Session, user: User, user_milestone_id: int
) -> MilestoneReview:
    um = (
        db.query(UserMilestone)
        .options(
            joinedload(UserMilestone.milestone),
            joinedload(UserMilestone.user_project).joinedload(UserProject.enrollment),
            joinedload(UserMilestone.user_project).joinedload(UserProject.project),
        )
        .filter(UserMilestone.id == user_milestone_id)
        .first()
    )
    if um is None or um.user_project.enrollment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    workspace = (
        db.query(SandboxWorkspace)
        .filter(SandboxWorkspace.user_project_id == um.user_project_id)
        .first()
    )
    summary = (workspace.last_test_summary if workspace else None) or {}
    tests_passed = summary.get("outcome") == "passed"
    if not tests_passed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Get your tests green before requesting a review",
        )
    llm = get_coach_llm()
    from app.services.sandbox import collect_source_bundle

    bundle = collect_source_bundle(um.user_project_id)
    payload = llm.review_milestone(
        milestone_title=um.milestone.title if um.milestone else "",
        milestone_description=um.milestone.description if um.milestone else "",
        success_criteria=um.milestone.success_criteria if um.milestone else "",
        constraints=list((um.user_project.project.constraints if um.user_project.project else None) or []),
        code_bundle=bundle,
        tests_passed=tests_passed,
        test_summary=str(summary.get("summary") or ""),
    )
    review = (
        db.query(MilestoneReview)
        .filter(MilestoneReview.user_milestone_id == um.id)
        .first()
    )
    if review is None:
        review = MilestoneReview(user_milestone_id=um.id)
        db.add(review)
    review.attempts = int(review.attempts or 0) + 1
    review.dimensions = payload.get("dimensions") or {}
    review.summary = str(payload.get("summary") or "")
    review.understanding_questions = list(payload.get("understanding_questions") or [])
    review.understanding_answers = []
    if review.attempts > MAX_REVIEW_ATTEMPTS:
        review.verdict = MilestoneReviewVerdict.passed
        review.summary = (review.summary + " Remaining gaps noted — proceeding.").strip()
    elif review.understanding_questions:
        review.verdict = MilestoneReviewVerdict.awaiting_understanding
    else:
        review.verdict = MilestoneReviewVerdict.needs_work
    db.commit()
    db.refresh(review)
    return review


def submit_milestone_review_answers(
    db: Session, user: User, user_milestone_id: int, answers: list[str]
) -> MilestoneReview:
    review = get_milestone_review(db, user, user_milestone_id)
    llm = get_coach_llm()
    um = db.get(UserMilestone, user_milestone_id)
    title = um.milestone.title if um and um.milestone else ""
    graded = []
    all_passed = True
    for question, answer in zip(review.understanding_questions or [], answers):
        result = llm.evaluate_understanding(question=str(question), answer=answer, milestone_title=title)
        passed = bool(result.get("passed"))
        all_passed = all_passed and passed
        graded.append(
            {
                "question": question,
                "answer": answer,
                "passed": passed,
                "feedback": result.get("feedback"),
            }
        )
    review.understanding_answers = graded
    review.verdict = (
        MilestoneReviewVerdict.passed if all_passed else MilestoneReviewVerdict.needs_work
    )
    db.commit()
    db.refresh(review)
    return review
