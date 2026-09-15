from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.coach import MilestoneReview
from app.models.concept import ConceptQuestion, ConceptSession, ConceptSessionStatus
from app.models.course import Course, CourseOption
from app.models.enrollment import Enrollment, LearningMode
from app.models.project import (
    Project,
    UserMilestone,
    UserMilestoneStatus,
    UserProject,
    UserProjectStatus,
)
from app.models.user import User
from app.schemas.enrollment import EnrollmentCreate
from app.models.project import ProjectCurriculumMode
from app.services import curriculum as curriculum_service
from app.services import curriculum_graph


def list_courses(db: Session) -> list[Course]:
    return db.query(Course).order_by(Course.id).all()


def get_course(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def list_primary_options(db: Session, course_id: int) -> list[CourseOption]:
    return (
        db.query(CourseOption)
        .filter(CourseOption.course_id == course_id, CourseOption.parent_id.is_(None))
        .order_by(CourseOption.id)
        .all()
    )


def list_secondary_options(
    db: Session, course_id: int, parent_option_id: int
) -> list[CourseOption]:
    parent = db.get(CourseOption, parent_option_id)
    if parent is None or parent.course_id != course_id or parent.parent_id is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary option not found")
    return (
        db.query(CourseOption)
        .filter(
            CourseOption.course_id == course_id,
            CourseOption.parent_id == parent_option_id,
        )
        .order_by(CourseOption.id)
        .all()
    )


def list_projects(
    db: Session,
    *,
    course_id: int | None = None,
    primary_option_id: int | None = None,
    secondary_option_id: int | None = None,
    active_only: bool = True,
) -> list[Project]:
    query = db.query(Project)
    if active_only:
        query = query.filter(Project.is_active.is_(True))
    if course_id is not None:
        query = query.filter(Project.course_id == course_id)
    if primary_option_id is not None:
        query = query.filter(Project.primary_option_id == primary_option_id)
    if secondary_option_id is not None:
        query = query.filter(Project.secondary_option_id == secondary_option_id)
    return query.order_by(Project.id).all()


def get_project_with_milestones(db: Session, project_id: int) -> Project | None:
    return (
        db.query(Project)
        .options(joinedload(Project.milestones))
        .filter(Project.id == project_id)
        .first()
    )


def _validate_enrollment_options(
    db: Session, payload: EnrollmentCreate
) -> tuple[Course, CourseOption, CourseOption]:
    course = get_course(db, payload.course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    primary = db.get(CourseOption, payload.primary_option_id)
    if (
        primary is None
        or primary.course_id != payload.course_id
        or primary.parent_id is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid primary option for course",
        )

    secondary = db.get(CourseOption, payload.secondary_option_id)
    if (
        secondary is None
        or secondary.course_id != payload.course_id
        or secondary.parent_id != primary.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid secondary option for primary option",
        )
    return course, primary, secondary


def create_enrollment(db: Session, user: User, payload: EnrollmentCreate) -> Enrollment:
    _validate_enrollment_options(db, payload)

    existing = (
        db.query(Enrollment)
        .filter(
            Enrollment.user_id == user.id,
            Enrollment.course_id == payload.course_id,
            Enrollment.primary_option_id == payload.primary_option_id,
            Enrollment.secondary_option_id == payload.secondary_option_id,
            Enrollment.learning_mode == payload.learning_mode,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enrollment already exists for this learning path",
        )

    enrollment = Enrollment(
        user_id=user.id,
        course_id=payload.course_id,
        primary_option_id=payload.primary_option_id,
        secondary_option_id=payload.secondary_option_id,
        learning_mode=payload.learning_mode,
    )
    db.add(enrollment)
    db.flush()

    if payload.learning_mode == LearningMode.project:
        project = (
            db.query(Project)
            .filter(
                Project.course_id == payload.course_id,
                Project.primary_option_id == payload.primary_option_id,
                Project.secondary_option_id == payload.secondary_option_id,
                Project.is_active.is_(True),
            )
            .order_by(Project.id)
            .first()
        )
        if project is None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No active project matches this course path",
            )
        enrollment.assigned_project_id = project.id
        user_project = UserProject(
            enrollment_id=enrollment.id,
            project_id=project.id,
            status=UserProjectStatus.assigned,
        )
        db.add(user_project)
        db.flush()
        curriculum_service.generate_milestones_for_user_project(db, user_project, project)
    else:
        question = (
            db.query(ConceptQuestion)
            .filter(
                ConceptQuestion.course_id == payload.course_id,
                ConceptQuestion.primary_option_id == payload.primary_option_id,
                ConceptQuestion.secondary_option_id == payload.secondary_option_id,
                ConceptQuestion.is_active.is_(True),
            )
            .order_by(ConceptQuestion.id)
            .first()
        )
        if question is not None:
            db.add(
                ConceptSession(
                    enrollment_id=enrollment.id,
                    question_text=question.question_text,
                    status=ConceptSessionStatus.active,
                )
            )
        else:
            db.add(
                ConceptSession(
                    enrollment_id=enrollment.id,
                    question_text=None,
                    status=ConceptSessionStatus.pending_generation,
                )
            )

    db.commit()
    return get_enrollment(db, user, enrollment.id)


def get_enrollment(db: Session, user: User, enrollment_id: int) -> Enrollment:
    enrollment = (
        db.query(Enrollment)
        .options(
            joinedload(Enrollment.course),
            joinedload(Enrollment.primary_option),
            joinedload(Enrollment.secondary_option),
            joinedload(Enrollment.assigned_project).joinedload(Project.milestones),
            joinedload(Enrollment.user_project).joinedload(UserProject.project),
            joinedload(Enrollment.user_project)
            .joinedload(UserProject.user_milestones)
            .joinedload(UserMilestone.milestone),
            joinedload(Enrollment.concept_session),
        )
        .filter(Enrollment.id == enrollment_id, Enrollment.user_id == user.id)
        .first()
    )
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    return enrollment


def list_enrollments(db: Session, user: User) -> list[Enrollment]:
    return (
        db.query(Enrollment)
        .options(
            joinedload(Enrollment.course),
            joinedload(Enrollment.primary_option),
            joinedload(Enrollment.secondary_option),
            joinedload(Enrollment.user_project),
            joinedload(Enrollment.concept_session),
        )
        .filter(Enrollment.user_id == user.id)
        .order_by(Enrollment.id)
        .all()
    )


def get_user_project(db: Session, user: User, user_project_id: int) -> UserProject:
    user_project = (
        db.query(UserProject)
        .options(
            joinedload(UserProject.project).joinedload(Project.milestones),
            joinedload(UserProject.user_milestones).joinedload(UserMilestone.milestone),
            joinedload(UserProject.enrollment),
        )
        .filter(UserProject.id == user_project_id)
        .first()
    )
    if user_project is None or user_project.enrollment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User project not found")
    return user_project


def complete_user_milestone(
    db: Session, user: User, user_milestone_id: int
) -> UserMilestone:
    user_milestone = (
        db.query(UserMilestone)
        .options(
            joinedload(UserMilestone.milestone),
            joinedload(UserMilestone.user_project)
            .joinedload(UserProject.user_milestones)
            .joinedload(UserMilestone.milestone),
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
    if user_milestone.status == UserMilestoneStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Milestone already completed"
        )

    pending = sorted(
        (
            um
            for um in user_milestone.user_project.user_milestones
            if um.status == UserMilestoneStatus.pending
        ),
        key=lambda um: um.milestone.order_index,
    )
    if not pending or pending[0].id != user_milestone.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Milestones must be completed in order",
        )

    project = user_milestone.user_project.project
    mode = project.curriculum_mode if project is not None else None
    if mode == ProjectCurriculumMode.deterministic or (
        isinstance(mode, str) and mode == ProjectCurriculumMode.deterministic.value
    ):
        allowed, reason = curriculum_graph.can_complete_milestone(
            db, user_milestone.user_project, user_milestone
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=reason)
    else:
        from app.models.coach import MilestoneReviewVerdict

        review = (
            db.query(MilestoneReview)
            .filter(MilestoneReview.user_milestone_id == user_milestone.id)
            .first()
        )
        if review is None or review.verdict != MilestoneReviewVerdict.passed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The AI milestone review must pass before you can complete this "
                    "milestone — get your tests green, then run: socratic review"
                ),
            )

    user_milestone.status = UserMilestoneStatus.completed
    user_milestone.completed_at = datetime.now(UTC)

    user_project = user_milestone.user_project
    if user_project.status == UserProjectStatus.assigned:
        user_project.status = UserProjectStatus.in_progress

    remaining = [
        um
        for um in user_project.user_milestones
        if um.status == UserMilestoneStatus.pending and um.id != user_milestone.id
    ]
    if not remaining:
        user_project.status = UserProjectStatus.completed

    db.commit()
    db.refresh(user_milestone)
    return user_milestone


def restart_user_milestone(db: Session, user: User, user_milestone_id: int) -> UserProject:
    """Reset a milestone and all later ones so the learner can redo from that point."""
    user_milestone = (
        db.query(UserMilestone)
        .options(
            joinedload(UserMilestone.milestone),
            joinedload(UserMilestone.user_project)
            .joinedload(UserProject.user_milestones)
            .joinedload(UserMilestone.milestone),
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

    restart_from = user_milestone.milestone.order_index
    user_project = user_milestone.user_project
    reset_ids = [
        um.id for um in user_project.user_milestones if um.milestone.order_index >= restart_from
    ]
    for um in user_project.user_milestones:
        if um.milestone.order_index >= restart_from:
            um.status = UserMilestoneStatus.pending
            um.completed_at = None
    if reset_ids:
        db.query(MilestoneReview).filter(
            MilestoneReview.user_milestone_id.in_(reset_ids)
        ).delete(synchronize_session=False)
        curriculum_graph.reset_from_milestone(db, user_project, restart_from)

    completed_count = sum(
        1 for um in user_project.user_milestones if um.status == UserMilestoneStatus.completed
    )
    if completed_count == 0:
        user_project.status = UserProjectStatus.assigned
    else:
        user_project.status = UserProjectStatus.in_progress

    db.commit()
    return get_user_project(db, user, user_project.id)


def get_concept_session(db: Session, user: User, session_id: int) -> ConceptSession:
    session = (
        db.query(ConceptSession)
        .options(
            joinedload(ConceptSession.turns),
            joinedload(ConceptSession.enrollment),
        )
        .filter(ConceptSession.id == session_id)
        .first()
    )
    if session is None or session.enrollment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concept session not found"
        )
    return session
