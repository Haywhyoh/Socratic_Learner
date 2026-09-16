import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MentorTurnRole(str, enum.Enum):
    learner = "learner"
    tutor = "tutor"
    system = "system"


class MentorSessionStatus(str, enum.Enum):
    needs_assessment = "needs_assessment"
    active = "active"
    completed = "completed"


class MilestoneReviewVerdict(str, enum.Enum):
    needs_work = "needs_work"
    awaiting_understanding = "awaiting_understanding"
    passed = "passed"


class MentorSession(Base):
    __tablename__ = "mentor_sessions"
    __table_args__ = (
        UniqueConstraint(
            "user_milestone_id",
            "attempt",
            name="uq_mentor_session_milestone_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    user_milestone_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_milestones.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[MentorSessionStatus] = mapped_column(
        Enum(MentorSessionStatus, name="mentor_session_status", native_enum=False),
        default=MentorSessionStatus.needs_assessment,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user_project = relationship("UserProject")
    user_milestone = relationship("UserMilestone")
    turns = relationship(
        "MentorTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="MentorTurn.id",
    )


class MentorTurn(Base):
    __tablename__ = "mentor_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("mentor_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MentorTurnRole] = mapped_column(
        Enum(MentorTurnRole, name="mentor_turn_role", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session = relationship("MentorSession", back_populates="turns")


class MilestoneReview(Base):
    """Post-milestone AI review gate — the record of whether the coach has

    signed off on a learner's implementation (correctness, architecture,
    readability, complexity, reliability, testing) and on their understanding
    of what they built. ``complete_user_milestone`` requires ``verdict ==
    passed`` here before a milestone can be marked complete.
    """

    __tablename__ = "milestone_reviews"
    __table_args__ = (
        UniqueConstraint("user_milestone_id", name="uq_milestone_review_user_milestone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_milestone_id: Mapped[int] = mapped_column(
        ForeignKey("user_milestones.id", ondelete="CASCADE"), nullable=False
    )
    verdict: Mapped[MilestoneReviewVerdict] = mapped_column(
        Enum(MilestoneReviewVerdict, name="milestone_review_verdict", native_enum=False),
        default=MilestoneReviewVerdict.needs_work,
        nullable=False,
    )
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    understanding_questions: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    understanding_answers: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user_milestone = relationship("UserMilestone")


class HintReveal(Base):
    __tablename__ = "hint_reveals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_milestone_id: Mapped[int] = mapped_column(
        ForeignKey("user_milestones.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_milestone = relationship("UserMilestone")
