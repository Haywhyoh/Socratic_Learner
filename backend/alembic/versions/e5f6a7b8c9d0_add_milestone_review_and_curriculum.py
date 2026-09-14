"""add per-learner curriculum generation and milestone review gate

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-15 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_empty_list = sa.text("'[]'::jsonb")
_empty_dict = sa.text("'{}'::jsonb")


def upgrade() -> None:
    # --- Milestones become learner-scoped so curriculum can be AI-generated ---
    op.add_column(
        "milestones",
        sa.Column(
            "user_project_id",
            sa.Integer(),
            sa.ForeignKey("user_projects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "milestones",
        sa.Column("generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("milestones", "generated", server_default=None)

    op.drop_constraint("uq_milestone_order", "milestones", type_="unique")
    op.create_index(
        "uq_milestone_order_catalog",
        "milestones",
        ["project_id", "order_index"],
        unique=True,
        postgresql_where=sa.text("user_project_id IS NULL"),
    )
    op.create_index(
        "uq_milestone_order_generated",
        "milestones",
        ["user_project_id", "order_index"],
        unique=True,
        postgresql_where=sa.text("user_project_id IS NOT NULL"),
    )

    # --- Cap retries on pre-code questions ---
    op.add_column(
        "learner_states",
        sa.Column("question_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("learner_states", "question_attempts", server_default=None)

    # --- Post-milestone AI review gate ---
    op.create_table(
        "milestone_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_milestone_id",
            sa.Integer(),
            sa.ForeignKey("user_milestones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "verdict",
            sa.String(length=32),
            nullable=False,
            server_default="needs_work",
        ),
        sa.Column("dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=_empty_dict),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "understanding_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
        sa.Column(
            "understanding_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_milestone_id", name="uq_milestone_review_user_milestone"),
    )
    op.alter_column("milestone_reviews", "verdict", server_default=None)
    op.alter_column("milestone_reviews", "dimensions", server_default=None)
    op.alter_column("milestone_reviews", "summary", server_default=None)
    op.alter_column("milestone_reviews", "understanding_questions", server_default=None)
    op.alter_column("milestone_reviews", "understanding_answers", server_default=None)
    op.alter_column("milestone_reviews", "attempts", server_default=None)


def downgrade() -> None:
    op.drop_table("milestone_reviews")
    op.drop_column("learner_states", "question_attempts")
    op.drop_index("uq_milestone_order_generated", table_name="milestones")
    op.drop_index("uq_milestone_order_catalog", table_name="milestones")
    op.create_unique_constraint(
        "uq_milestone_order", "milestones", ["project_id", "order_index"]
    )
    op.drop_column("milestones", "generated")
    op.drop_column("milestones", "user_project_id")
