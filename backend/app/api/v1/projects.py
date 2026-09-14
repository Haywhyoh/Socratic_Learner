from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import MilestoneRead, ProjectDetail, ProjectRead, UserMilestoneRead, UserProjectRead
from app.services import learning as learning_service

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(
    course_id: int | None = None,
    primary_option_id: int | None = None,
    secondary_option_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[ProjectRead]:
    return learning_service.list_projects(
        db,
        course_id=course_id,
        primary_option_id=primary_option_id,
        secondary_option_id=secondary_option_id,
    )


@router.get("/projects/{project_id}/milestones", response_model=list[MilestoneRead])
def list_project_milestones(project_id: int, db: Session = Depends(get_db)) -> list[MilestoneRead]:
    project = learning_service.get_project_with_milestones(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project.milestones


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)) -> ProjectDetail:
    project = learning_service.get_project_with_milestones(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectDetail(
        id=project.id,
        title=project.title,
        description=project.description,
        course_id=project.course_id,
        primary_option_id=project.primary_option_id,
        secondary_option_id=project.secondary_option_id,
        is_active=project.is_active,
        milestones=project.milestones,
    )


@router.get("/me/projects/{user_project_id}", response_model=UserProjectRead)
def get_my_project(
    user_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProjectRead:
    return learning_service.get_user_project(db, current_user, user_project_id)


@router.post("/me/milestones/{user_milestone_id}/complete", response_model=UserMilestoneRead)
def complete_milestone(
    user_milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMilestoneRead:
    return learning_service.complete_user_milestone(db, current_user, user_milestone_id)


@router.post("/me/milestones/{user_milestone_id}/restart", response_model=UserProjectRead)
def restart_milestone(
    user_milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProjectRead:
    return learning_service.restart_user_milestone(db, current_user, user_milestone_id)
