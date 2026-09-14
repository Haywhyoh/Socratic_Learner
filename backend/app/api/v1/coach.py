from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.coach import (
    CheckpointRead,
    CheckpointRequest,
    CoachMessageRequest,
    CoachMessageResponse,
    CoachStartRequest,
    CoachStartResponse,
    ConceptCardRead,
    LearnerStateRead,
    MilestoneReviewRead,
    ReviewAnswerRequest,
    RoadmapMilestoneRead,
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
    body = payload or CoachStartRequest()
    result = coach_service.start_coach(
        db, current_user, user_project_id, answers=body.answers
    )
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
    "/me/projects/{user_project_id}/roadmap",
    response_model=list[RoadmapMilestoneRead],
)
def get_roadmap(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RoadmapMilestoneRead]:
    return coach_service.get_roadmap(db, current_user, user_project_id)


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


@router.get(
    "/me/milestones/{user_milestone_id}/cards",
    response_model=list[ConceptCardRead],
)
def list_cards(
    user_milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConceptCardRead]:
    return coach_service.list_cards(db, current_user, user_milestone_id)


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
    "/me/cards/{card_id}/checkpoint",
    response_model=CheckpointRead,
)
def submit_checkpoint(
    card_id: int,
    payload: CheckpointRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckpointRead:
    return coach_service.submit_checkpoint(
        db, current_user, card_id, payload.answer
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
