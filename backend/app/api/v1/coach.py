from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.coach import (
    CoachMessageRequest,
    CoachMessageResponse,
    CoachStartRequest,
    CoachStartResponse,
    DefenseAnswerRequest,
    ExplainRequest,
    ExplanationResultRead,
    GraphRead,
    LearnerStateRead,
    MilestoneCoachRead,
    MentorSessionRead,
    MentorSessionSummary,
    MilestoneReviewRead,
    ProjectDefenseRead,
    ReflectionRead,
    ReflectionRequest,
    ResearchRecordRead,
    ResearchRequest,
    RetrievalAnswerRequest,
    RetrievalCheckRead,
    ReviewAnswerRequest,
    SkipDiagnosticRequest,
    SkipResultRead,
)
from app.services import coach as coach_service

router = APIRouter(tags=["coach"])


@router.post(
    "/me/projects/{user_project_id}/coach/start",
    response_model=CoachStartResponse,
)
def start_coach(
    user_project_id: int,
    payload: CoachStartRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachStartResponse:
    _ = payload or CoachStartRequest()
    result = coach_service.start_coach(db, current_user, user_project_id)
    return CoachStartResponse.model_validate(result)


@router.post(
    "/me/projects/{user_project_id}/coach/message",
    response_model=CoachMessageResponse,
)
def coach_message(
    user_project_id: int,
    payload: CoachMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachMessageResponse:
    result = coach_service.post_message(
        db, current_user, user_project_id, payload.message
    )
    return CoachMessageResponse.model_validate(result)


@router.get(
    "/me/projects/{user_project_id}/coach/sessions",
    response_model=list[MentorSessionSummary],
)
def list_coach_sessions(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MentorSessionSummary]:
    return [
        MentorSessionSummary.model_validate(row)
        for row in coach_service.list_mentor_sessions(db, current_user, user_project_id)
    ]


@router.get(
    "/me/coach/sessions/{session_id}",
    response_model=MentorSessionRead,
)
def get_coach_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MentorSessionRead:
    return MentorSessionRead.model_validate(
        coach_service.get_mentor_session(db, current_user, session_id)
    )


@router.get(
    "/me/milestones/{user_milestone_id}/coach",
    response_model=MilestoneCoachRead,
)
def get_milestone_coach(
    user_milestone_id: int,
    attempt: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MilestoneCoachRead:
    return MilestoneCoachRead.model_validate(
        coach_service.get_milestone_coach(
            db, current_user, user_milestone_id, attempt=attempt
        )
    )


@router.get(
    "/me/projects/{user_project_id}/graph",
    response_model=GraphRead,
)
def get_graph(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GraphRead:
    return GraphRead.model_validate(
        coach_service.get_graph(db, current_user, user_project_id)
    )


@router.get(
    "/me/projects/{user_project_id}/state",
    response_model=LearnerStateRead,
)
def get_learner_state(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearnerStateRead:
    return LearnerStateRead.model_validate(
        coach_service.get_learner_state(db, current_user, user_project_id)
    )


@router.post(
    "/me/milestones/{user_milestone_id}/hints",
    response_model=CoachMessageResponse,
)
def request_hint(
    user_milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachMessageResponse:
    result = coach_service.request_hint(db, current_user, user_milestone_id)
    return CoachMessageResponse.model_validate(result)


@router.post(
    "/me/projects/{user_project_id}/concepts/{concept_id}/research",
    response_model=ResearchRecordRead,
)
def submit_research(
    user_project_id: int,
    concept_id: str,
    payload: ResearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearchRecordRead:
    return ResearchRecordRead.model_validate(
        coach_service.submit_research(
            db, current_user, user_project_id, concept_id, payload.model_dump()
        )
    )


@router.post(
    "/me/projects/{user_project_id}/concepts/{concept_id}/explain",
    response_model=ExplanationResultRead,
)
def submit_explanation(
    user_project_id: int,
    concept_id: str,
    payload: ExplainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExplanationResultRead:
    return ExplanationResultRead.model_validate(
        coach_service.submit_explanation(
            db, current_user, user_project_id, concept_id, payload.answer
        )
    )


@router.post(
    "/me/projects/{user_project_id}/concepts/{concept_id}/skip-diagnostic",
    response_model=SkipResultRead,
)
def skip_diagnostic(
    user_project_id: int,
    concept_id: str,
    payload: SkipDiagnosticRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SkipResultRead:
    return SkipResultRead.model_validate(
        coach_service.skip_diagnostic(
            db, current_user, user_project_id, concept_id, payload.answers
        )
    )


@router.post(
    "/me/milestones/{user_milestone_id}/reflection",
    response_model=ReflectionRead,
)
def submit_reflection(
    user_milestone_id: int,
    payload: ReflectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReflectionRead:
    return ReflectionRead.model_validate(
        coach_service.submit_reflection(
            db, current_user, user_milestone_id, payload.answers
        )
    )


@router.post(
    "/me/projects/{user_project_id}/defense/start",
    response_model=ProjectDefenseRead,
)
def start_defense(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDefenseRead:
    return ProjectDefenseRead.model_validate(
        coach_service.start_defense(db, current_user, user_project_id)
    )


@router.post(
    "/me/projects/{user_project_id}/defense/answer",
    response_model=ProjectDefenseRead,
)
def answer_defense(
    user_project_id: int,
    payload: DefenseAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectDefenseRead:
    return ProjectDefenseRead.model_validate(
        coach_service.answer_defense(
            db, current_user, user_project_id, payload.answers
        )
    )


@router.get(
    "/me/projects/{user_project_id}/retrieval-checks",
    response_model=list[RetrievalCheckRead],
)
def list_retrieval_checks(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RetrievalCheckRead]:
    return [
        RetrievalCheckRead.model_validate(row)
        for row in coach_service.list_retrieval_checks(db, current_user, user_project_id)
    ]


@router.post(
    "/me/projects/{user_project_id}/retrieval-checks/{check_id}/answer",
    response_model=RetrievalCheckRead,
)
def answer_retrieval(
    user_project_id: int,
    check_id: int,
    payload: RetrievalAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetrievalCheckRead:
    return RetrievalCheckRead.model_validate(
        coach_service.answer_retrieval(
            db, current_user, user_project_id, check_id, payload.answer
        )
    )


@router.get(
    "/me/milestones/{user_milestone_id}/review",
    response_model=MilestoneReviewRead,
)
def get_milestone_review(
    user_milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MilestoneReviewRead:
    return MilestoneReviewRead.model_validate(
        coach_service.get_milestone_review(db, current_user, user_milestone_id)
    )


@router.post(
    "/me/milestones/{user_milestone_id}/review",
    response_model=MilestoneReviewRead,
)
def request_milestone_review(
    user_milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MilestoneReviewRead:
    return MilestoneReviewRead.model_validate(
        coach_service.request_milestone_review(db, current_user, user_milestone_id)
    )


@router.post(
    "/me/milestones/{user_milestone_id}/review/answer",
    response_model=MilestoneReviewRead,
)
def answer_milestone_review(
    user_milestone_id: int,
    payload: ReviewAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MilestoneReviewRead:
    return MilestoneReviewRead.model_validate(
        coach_service.submit_milestone_review_answers(
            db, current_user, user_milestone_id, payload.answers
        )
    )
