"""add coach overlay tables and milestone concepts

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-14 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_empty_list = sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column(
            "concepts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.alter_column("milestones", "concepts", server_default=None)

    op.create_table(
        "learner_knowledge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_project_id", sa.Integer(), sa.ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_name", sa.String(255), nullable=False),
        sa.Column(
            "mastery",
            sa.Enum("unknown", "familiar", "can_explain", name="concept_mastery", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_project_id", "concept_name", name="uq_learner_knowledge_concept"),
    )
    op.create_table(
        "roadmap_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_project_id", sa.Integer(), sa.ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_id", sa.Integer(), sa.ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("concept_name", sa.String(255), nullable=False),
        sa.Column(
            "teaching",
            sa.Enum("teach", "skip", name="teaching_flag", native_enum=False),
            nullable=False,
        ),
        sa.UniqueConstraint("user_project_id", "milestone_id", "concept_name", name="uq_roadmap_item"),
    )
    op.create_table(
        "concept_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_project_id", sa.Integer(), sa.ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_id", sa.Integer(), sa.ForeignKey("milestones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("research_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checkpoint", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_project_id", "milestone_id", "name", name="uq_concept_card"),
    )
    op.create_table(
        "card_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("concept_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "mentor_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_project_id", sa.Integer(), sa.ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "needs_assessment",
                "active",
                "completed",
                name="mentor_session_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_project_id", name="uq_mentor_session_user_project"),
    )
    op.create_table(
        "mentor_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("mentor_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role",
            sa.Enum("learner", "tutor", "system", name="mentor_turn_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "hint_reveals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_milestone_id",
            sa.Integer(),
            sa.ForeignKey("user_milestones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("hint_reveals")
    op.drop_table("mentor_turns")
    op.drop_table("mentor_sessions")
    op.drop_table("card_checkpoints")
    op.drop_table("concept_cards")
    op.drop_table("roadmap_items")
    op.drop_table("learner_knowledge")
    op.drop_column("milestones", "concepts")
