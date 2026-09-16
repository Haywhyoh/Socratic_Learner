import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserProjectStatus(str, enum.Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"


class UserMilestoneStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"


class ProjectDifficulty(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class ProjectCurriculumMode(str, enum.Enum):
    """Who controls milestone/concept sequencing for this project.

    ``deterministic`` — the seeded Concept/ConceptDependency/MilestoneConcept
    graph is the single source of truth; the AI mentor never invents or
    reorders milestones (see services/curriculum_graph.py). ``ai_generated``
    is the legacy per-learner LLM-tailored curriculum path.
    """

    deterministic = "deterministic"
    ai_generated = "ai_generated"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[ProjectDifficulty] = mapped_column(
        Enum(ProjectDifficulty, name="project_difficulty", native_enum=False),
        default=ProjectDifficulty.beginner,
        nullable=False,
    )
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prerequisites: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    skills: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    concepts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    constraints: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    tests: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    evaluation_criteria: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    extension_challenges: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    recommended_resources: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    curriculum_mode: Mapped[ProjectCurriculumMode] = mapped_column(
        Enum(ProjectCurriculumMode, name="project_curriculum_mode", native_enum=False),
        default=ProjectCurriculumMode.ai_generated,
        nullable=False,
    )
    runtime: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    """Sandbox/language metadata: language, sandbox_image, run, test_command, entry_globs."""
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    primary_option_id: Mapped[int] = mapped_column(
        ForeignKey("course_options.id", ondelete="RESTRICT"), nullable=False
    )
    secondary_option_id: Mapped[int] = mapped_column(
        ForeignKey("course_options.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    course = relationship("Course", back_populates="projects")
    primary_option = relationship("CourseOption", foreign_keys=[primary_option_id])
    secondary_option = relationship("CourseOption", foreign_keys=[secondary_option_id])
    milestones = relationship(
        "Milestone",
        primaryjoin=(
            "and_(Milestone.project_id == Project.id, "
            "Milestone.user_project_id.is_(None))"
        ),
        viewonly=True,
        order_by="Milestone.order_index",
    )


class Milestone(Base):
    """A milestone step.

    Rows with ``user_project_id IS NULL`` are the shared *catalog* outline for a
    project (seeded content, used as a reference template and shown before
    enrollment). Rows with ``user_project_id`` set are the learner-specific
    curriculum generated (by AI, or cloned from the catalog as a deterministic
    fallback) the moment a learner is assigned that project — this is what the
    coach actually teaches from.
    """

    __tablename__ = "milestones"
    __table_args__ = (
        Index(
            "uq_milestone_order_catalog",
            "project_id",
            "order_index",
            unique=True,
            postgresql_where=text("user_project_id IS NULL"),
        ),
        Index(
            "uq_milestone_order_generated",
            "user_project_id",
            "order_index",
            unique=True,
            postgresql_where=text("user_project_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=True
    )
    generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    success_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    concepts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    project = relationship("Project", foreign_keys=[project_id])
    user_project = relationship("UserProject", foreign_keys=[user_project_id])


class UserProject(Base):
    __tablename__ = "user_projects"
    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_user_project_enrollment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[UserProjectStatus] = mapped_column(
        Enum(UserProjectStatus, name="user_project_status", native_enum=False),
        default=UserProjectStatus.assigned,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    enrollment = relationship("Enrollment", back_populates="user_project")
    project = relationship("Project")
    user_milestones = relationship(
        "UserMilestone",
        back_populates="user_project",
        cascade="all, delete-orphan",
        order_by="UserMilestone.id",
    )


class UserMilestone(Base):
    __tablename__ = "user_milestones"
    __table_args__ = (
        UniqueConstraint("user_project_id", "milestone_id", name="uq_user_milestone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[UserMilestoneStatus] = mapped_column(
        Enum(UserMilestoneStatus, name="user_milestone_status", native_enum=False),
        default=UserMilestoneStatus.pending,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_project = relationship("UserProject", back_populates="user_milestones")
    milestone = relationship("Milestone")
