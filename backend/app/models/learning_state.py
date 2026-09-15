"""Per-learner state for the deterministic curriculum graph.

Three layers, per the product architecture:

    Curriculum (Concept/ConceptDependency/Milestone)  -- what should be learned
    Learning State (this module)                        -- what THIS learner understands
    AI Mentor (agents/mentor_graph.py)                   -- how to help them right now

Mastery is evidence-based (never "clicked Next") -- see ``ConceptState.evidence``
and ``Concept.mastery_requirements``.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
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


class ConceptStatus(str, enum.Enum):
    """Merges the concept-mastery ladder and the per-concept state machine
    into one enum. Forward path is linear; ``BLOCKED``/``DIAGNOSIS``/
    ``KNOWLEDGE_GAP``/``NEEDS_REVIEW`` are side-states reached from a failed
    TESTING or EXPLAINED step, and always loop back onto the forward path.
    """

    locked = "locked"
    available = "available"
    introduced = "introduced"
    researching = "researching"
    discussing = "discussing"
    attempted = "attempted"
    testing = "testing"
    blocked = "blocked"
    diagnosis = "diagnosis"
    knowledge_gap = "knowledge_gap"
    explained = "explained"
    needs_review = "needs_review"
    verification = "verification"
    verified = "verified"
    mastered = "mastered"


class GapStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class DefenseVerdict(str, enum.Enum):
    pending = "pending"
    needs_work = "needs_work"
    passed = "passed"


class RetrievalCheckStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"


class ConceptState(Base):
    """Evidence-tracked learning state for one (learner, concept) pair."""

    __tablename__ = "concept_states"
    __table_args__ = (
        UniqueConstraint("user_project_id", "concept_id", name="uq_concept_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ConceptStatus] = mapped_column(
        Enum(ConceptStatus, name="concept_status", native_enum=False),
        default=ConceptStatus.locked,
        nullable=False,
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    """{"research": bool, "implementation": bool, "testing": bool,
    "explanation": bool, "retrieval": bool}"""
    hint_level: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hints_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    diagnostic_answers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    last_explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verified_via_skip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user_project = relationship("UserProject")
    concept = relationship("Concept")


class KnowledgeGap(Base):
    """A suspected (not yet confirmed) prerequisite gap raised while a learner

    is blocked on ``blocked_concept_id``. ``confidence`` is a rule-based
    heuristic (graph proximity + prerequisite evidence weakness), not a
    trained model score.
    """

    __tablename__ = "knowledge_gaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    blocked_concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    suspected_concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[GapStatus] = mapped_column(
        Enum(GapStatus, name="knowledge_gap_status", native_enum=False),
        default=GapStatus.open,
        nullable=False,
    )
    diagnostic_transcript: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_project = relationship("UserProject")
    blocked_concept = relationship("Concept", foreign_keys=[blocked_concept_id])
    suspected_concept = relationship("Concept", foreign_keys=[suspected_concept_id])


class ResearchRecord(Base):
    """The learner's own research notes for a concept (spec: research-first)."""

    __tablename__ = "research_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sources: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    learner_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    learner_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remaining_questions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_project = relationship("UserProject")
    concept = relationship("Concept")


class Reflection(Base):
    """Milestone-completion reflection answers."""

    __tablename__ = "reflections"
    __table_args__ = (
        UniqueConstraint("user_milestone_id", name="uq_reflection_user_milestone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_milestone_id: Mapped[int] = mapped_column(
        ForeignKey("user_milestones.id", ondelete="CASCADE"), nullable=False
    )
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    """{"what": str, "why": str, "alternatives": str, "difficult": str,
    "scale": str, "change": str}"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_milestone = relationship("UserMilestone")


class ProjectDefense(Base):
    """Final technical-defense record for a completed project."""

    __tablename__ = "project_defenses"
    __table_args__ = (
        UniqueConstraint("user_project_id", name="uq_project_defense_user_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    answers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    verdict: Mapped[DefenseVerdict] = mapped_column(
        Enum(DefenseVerdict, name="project_defense_verdict", native_enum=False),
        default=DefenseVerdict.pending,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
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

    user_project = relationship("UserProject")


class RetrievalCheck(Base):
    """A scheduled spaced-retrieval prompt (1/7/30 days after mastery).

    Surfaced passively (no email/push infra exists yet) whenever the learner
    opens the workspace and a check's ``scheduled_for`` date has passed.
    """

    __tablename__ = "retrieval_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for: Mapped[date] = mapped_column(Date, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    original_response_ref: Mapped[str] = mapped_column(Text, nullable=False, default="")
    learner_response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[RetrievalCheckStatus] = mapped_column(
        Enum(RetrievalCheckStatus, name="retrieval_check_status", native_enum=False),
        default=RetrievalCheckStatus.pending,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_project = relationship("UserProject")
    concept = relationship("Concept")
