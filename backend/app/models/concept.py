import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConceptSessionStatus(str, enum.Enum):
    pending_generation = "pending_generation"
    active = "active"
    completed = "completed"


class ConceptTurnRole(str, enum.Enum):
    learner = "learner"
    tutor = "tutor"


class ConceptQuestion(Base):
    """Catalog of hard concept questions. Used until AI generation is wired up."""

    __tablename__ = "concept_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    primary_option_id: Mapped[int] = mapped_column(
        ForeignKey("course_options.id", ondelete="RESTRICT"), nullable=False
    )
    secondary_option_id: Mapped[int] = mapped_column(
        ForeignKey("course_options.id", ondelete="RESTRICT"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    course = relationship("Course")
    primary_option = relationship("CourseOption", foreign_keys=[primary_option_id])
    secondary_option = relationship("CourseOption", foreign_keys=[secondary_option_id])


class ConceptSession(Base):
    __tablename__ = "concept_sessions"
    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_concept_session_enrollment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ConceptSessionStatus] = mapped_column(
        Enum(ConceptSessionStatus, name="concept_session_status", native_enum=False),
        default=ConceptSessionStatus.pending_generation,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    enrollment = relationship("Enrollment", back_populates="concept_session")
    turns = relationship(
        "ConceptTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConceptTurn.id",
    )


class ConceptTurn(Base):
    __tablename__ = "concept_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("concept_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ConceptTurnRole] = mapped_column(
        Enum(ConceptTurnRole, name="concept_turn_role", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session = relationship("ConceptSession", back_populates="turns")
