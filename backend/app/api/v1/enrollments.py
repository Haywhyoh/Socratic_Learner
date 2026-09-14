from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate, EnrollmentDetail, EnrollmentRead
from app.services import learning as learning_service

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


def _to_enrollment_read(enrollment: Enrollment) -> EnrollmentRead:
    return EnrollmentRead(
        id=enrollment.id,
        user_id=enrollment.user_id,
        course_id=enrollment.course_id,
        primary_option_id=enrollment.primary_option_id,
        secondary_option_id=enrollment.secondary_option_id,
        learning_mode=enrollment.learning_mode,
        assigned_project_id=enrollment.assigned_project_id,
        created_at=enrollment.created_at,
        course=enrollment.course,
        primary_option=enrollment.primary_option,
        secondary_option=enrollment.secondary_option,
        user_project=enrollment.user_project,
        concept_session_id=enrollment.concept_session.id if enrollment.concept_session else None,
    )


def _to_enrollment_detail(enrollment: Enrollment) -> EnrollmentDetail:
    base = _to_enrollment_read(enrollment)
    milestones = []
    user_milestones = []
    if enrollment.user_project is not None:
        user_milestones = enrollment.user_project.user_milestones
        # These are the learner's own generated milestones (not the shared
        # catalog outline) — each learner gets their own curriculum.
        milestones = sorted(
            (um.milestone for um in user_milestones if um.milestone is not None),
            key=lambda m: m.order_index,
        )
    return EnrollmentDetail(
        **base.model_dump(),
        assigned_project=enrollment.assigned_project,
        milestones=milestones,
        user_milestones=user_milestones,
    )


@router.post("", response_model=EnrollmentDetail, status_code=status.HTTP_201_CREATED)
def create_enrollment(
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnrollmentDetail:
    enrollment = learning_service.create_enrollment(db, current_user, payload)
    return _to_enrollment_detail(enrollment)


@router.get("", response_model=list[EnrollmentRead])
def list_enrollments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnrollmentRead]:
    return [_to_enrollment_read(e) for e in learning_service.list_enrollments(db, current_user)]


@router.get("/{enrollment_id}", response_model=EnrollmentDetail)
def get_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnrollmentDetail:
    enrollment = learning_service.get_enrollment(db, current_user, enrollment_id)
    return _to_enrollment_detail(enrollment)
