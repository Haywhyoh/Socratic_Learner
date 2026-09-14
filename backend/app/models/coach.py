import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConceptMastery(str, enum.Enum):
    unknown = "unknown"
    familiar = "familiar"
    can_explain = "can_explain"


class TeachingFlag(str, enum.Enum):
    teach = "teach"
    skip = "skip"


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


class LearnerKnowledge(Base):
    __tablename__ = "learner_knowledge"
    __table_args__ = (
        UniqueConstraint("user_project_id", "concept_name", name="uq_learner_knowledge_concept"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mastery: Mapped[ConceptMastery] = mapped_column(
        Enum(ConceptMastery, name="concept_mastery", native_enum=False),
        default=ConceptMastery.unknown,
        nullable=False,
    )
    attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    researched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_project = relationship("UserProject")


class LearnerState(Base):
    """Per-milestone learning control state — the core IP of the product."""

    __tablename__ = "learner_states"
    __table_args__ = (
        UniqueConstraint(
            "user_project_id",
            "milestone_id",
            name="uq_learner_state_milestone",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False
    )
    question_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    researched_concepts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    failed_at: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    can_explain: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    can_reproduce: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    help_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user_project = relationship("UserProject")
    milestone = relationship("Milestone")


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"
    __table_args__ = (
        UniqueConstraint(
            "user_project_id",
            "milestone_id",
            "concept_name",
            name="uq_roadmap_item",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False
    )
    concept_name: Mapped[str] = mapped_column(String(255), nullable=False)
    teaching: Mapped[TeachingFlag] = mapped_column(
        Enum(TeachingFlag, name="teaching_flag", native_enum=False),
        default=TeachingFlag.teach,
        nullable=False,
    )

    user_project = relationship("UserProject")
    milestone = relationship("Milestone")


class ConceptCard(Base):
    __tablename__ = "concept_cards"
    __table_args__ = (
        UniqueConstraint(
            "user_project_id",
            "milestone_id",
            "name",
            name="uq_concept_card",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    research_questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    resources: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    checkpoint: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_project = relationship("UserProject")
    milestone = relationship("Milestone")
    checkpoints = relationship(
        "CardCheckpoint",
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="CardCheckpoint.id",
    )


class CardCheckpoint(Base):
    __tablename__ = "card_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("concept_cards.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    card = relationship("ConceptCard", back_populates="checkpoints")


class MentorSession(Base):
    __tablename__ = "mentor_sessions"
    __table_args__ = (
        UniqueConstraint("user_project_id", name="uq_mentor_session_user_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[MentorSessionStatus] = mapped_column(
        Enum(MentorSessionStatus, name="mentor_session_status", native_enum=False),
        default=MentorSessionStatus.needs_assessment,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_project = relationship("UserProject")
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
