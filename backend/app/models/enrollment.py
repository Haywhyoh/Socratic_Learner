import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LearningMode(str, enum.Enum):
    project = "project"
    concept = "concept"


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
            "primary_option_id",
            "secondary_option_id",
            "learning_mode",
            name="uq_enrollment_path",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    primary_option_id: Mapped[int] = mapped_column(
        ForeignKey("course_options.id", ondelete="RESTRICT"), nullable=False
    )
    secondary_option_id: Mapped[int] = mapped_column(
        ForeignKey("course_options.id", ondelete="RESTRICT"), nullable=False
    )
    learning_mode: Mapped[LearningMode] = mapped_column(
        Enum(LearningMode, name="learning_mode", native_enum=False),
        nullable=False,
    )
    assigned_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    primary_option = relationship("CourseOption", foreign_keys=[primary_option_id])
    secondary_option = relationship("CourseOption", foreign_keys=[secondary_option_id])
    assigned_project = relationship("Project", foreign_keys=[assigned_project_id])
    user_project = relationship(
        "UserProject", back_populates="enrollment", uselist=False, cascade="all, delete-orphan"
    )
    concept_session = relationship(
        "ConceptSession", back_populates="enrollment", uselist=False, cascade="all, delete-orphan"
    )
