from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enrollment import LearningMode
from app.schemas.course import CourseOptionRead, CourseRead
from app.schemas.project import MilestoneRead, ProjectRead, UserMilestoneRead, UserProjectRead


class EnrollmentCreate(BaseModel):
    course_id: int
    primary_option_id: int
    secondary_option_id: int
    learning_mode: LearningMode


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    course_id: int
    primary_option_id: int
    secondary_option_id: int
    learning_mode: LearningMode
    assigned_project_id: int | None
    created_at: datetime
    course: CourseRead | None = None
    primary_option: CourseOptionRead | None = None
    secondary_option: CourseOptionRead | None = None
    user_project: UserProjectRead | None = None
    concept_session_id: int | None = None


class EnrollmentDetail(EnrollmentRead):
    assigned_project: ProjectRead | None = None
    milestones: list[MilestoneRead] = []
    user_milestones: list[UserMilestoneRead] = []
