"""add milestone questions and learner state

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-14 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_empty_list = sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column(
            "questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.alter_column("milestones", "questions", server_default=None)

    op.add_column(
        "learner_knowledge",
        sa.Column("attempted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "learner_knowledge",
        sa.Column("researched", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "learner_knowledge",
        sa.Column("failed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("learner_knowledge", "attempted", server_default=None)
    op.alter_column("learner_knowledge", "researched", server_default=None)
    op.alter_column("learner_knowledge", "failed", server_default=None)

    op.create_table(
        "learner_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_project_id",
            sa.Integer(),
            sa.ForeignKey("user_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "milestone_id",
            sa.Integer(),
            sa.ForeignKey("milestones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("questions_passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "attempts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
        sa.Column(
            "researched_concepts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
        sa.Column(
            "failed_at",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
        sa.Column(
            "can_explain",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
        sa.Column("can_reproduce", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("help_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_project_id", "milestone_id", name="uq_learner_state_milestone"),
    )
    op.alter_column("learner_states", "question_index", server_default=None)
    op.alter_column("learner_states", "questions_passed", server_default=None)
    op.alter_column("learner_states", "attempts", server_default=None)
    op.alter_column("learner_states", "researched_concepts", server_default=None)
    op.alter_column("learner_states", "failed_at", server_default=None)
    op.alter_column("learner_states", "can_explain", server_default=None)
    op.alter_column("learner_states", "can_reproduce", server_default=None)
    op.alter_column("learner_states", "help_received", server_default=None)


def downgrade() -> None:
    op.drop_table("learner_states")
    op.drop_column("learner_knowledge", "failed")
    op.drop_column("learner_knowledge", "researched")
    op.drop_column("learner_knowledge", "attempted")
    op.drop_column("milestones", "questions")
