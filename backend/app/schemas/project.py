from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.project import UserMilestoneStatus, UserProjectStatus


class MilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    order_index: int
    success_criteria: str


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    course_id: int
    primary_option_id: int
    secondary_option_id: int
    is_active: bool


class ProjectDetail(ProjectRead):
    milestones: list[MilestoneRead] = []


class UserMilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_project_id: int
    milestone_id: int
    status: UserMilestoneStatus
    completed_at: datetime | None
    milestone: MilestoneRead | None = None


class UserProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enrollment_id: int
    project_id: int
    status: UserProjectStatus
    created_at: datetime
    project: ProjectRead | None = None
    user_milestones: list[UserMilestoneRead] = []
