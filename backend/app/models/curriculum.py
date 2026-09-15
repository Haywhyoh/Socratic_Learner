"""Curriculum graph: concepts, their prerequisite edges, and milestone linkage.

This is the deterministic knowledge graph for graph-driven projects — the AI
mentor never invents or reorders this data; it only narrates/questions/hints
within whatever the graph currently allows (see services/curriculum_graph.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Concept(Base):
    """A single node in the curriculum knowledge graph.

    ``id`` is a stable, human-readable slug (e.g. ``"http.parsing"``) used
    everywhere else in the system (ConceptDependency, ConceptState,
    KnowledgeGap, mentor context) instead of a surrogate integer key, because
    the graph is meant to be read/edited as data later (admin editor, deferred
    for now).
    """

    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    learning_objectives: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    misconceptions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    diagnostic_questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    research_questions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    resources: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    hints: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    """Ordered hint ladder, index 0..4 matching HINT_LEVELS in agents/policies.py
    (0=question, 1=direction, 2=concept, 3=structure, 4=targeted)."""
    mastery_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    """Which evidence types this concept needs before MASTERED, e.g.
    {"research": true, "implementation": true, "testing": true, "explanation": true}."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dependencies = relationship(
        "ConceptDependency",
        foreign_keys="ConceptDependency.concept_id",
        back_populates="concept",
        cascade="all, delete-orphan",
    )


class ConceptDependency(Base):
    """A prerequisite edge: ``concept_id`` requires ``requires_concept_id``.

    ``reason`` is shown back to the learner when the mentor sends them
    backward to a prerequisite instead of a bare "go review X".
    """

    __tablename__ = "concept_dependencies"
    __table_args__ = (
        UniqueConstraint("concept_id", "requires_concept_id", name="uq_concept_dependency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    requires_concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    concept = relationship(
        "Concept", foreign_keys=[concept_id], back_populates="dependencies"
    )
    requires = relationship("Concept", foreign_keys=[requires_concept_id])


class MilestoneConcept(Base):
    """Join table: which concepts belong to a milestone, and in what order."""

    __tablename__ = "milestone_concepts"
    __table_args__ = (
        UniqueConstraint("milestone_id", "concept_id", name="uq_milestone_concept"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    milestone = relationship("Milestone")
    concept = relationship("Concept")
