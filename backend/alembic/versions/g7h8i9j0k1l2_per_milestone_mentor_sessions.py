"""scope mentor sessions to a milestone and keep attempts

Revision ID: g7h8i9j0k1l2
Revises: 4227e015bd46
Create Date: 2026-09-16 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "4227e015bd46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mentor_sessions",
        sa.Column("user_milestone_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "mentor_sessions",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "mentor_sessions",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_mentor_sessions_user_milestone_id",
        "mentor_sessions",
        "user_milestones",
        ["user_milestone_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        sa.text(
            """
            UPDATE mentor_sessions AS ms
            SET user_milestone_id = (
                SELECT um.id
                FROM user_milestones AS um
                WHERE um.user_project_id = ms.user_project_id
                ORDER BY CASE WHEN um.status = 'pending' THEN 0 ELSE 1 END, um.id
                LIMIT 1
            )
            """
        )
    )
    op.drop_constraint("uq_mentor_session_user_project", "mentor_sessions", type_="unique")
    op.create_unique_constraint(
        "uq_mentor_session_milestone_attempt",
        "mentor_sessions",
        ["user_milestone_id", "attempt"],
    )
    op.alter_column("mentor_sessions", "attempt", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "uq_mentor_session_milestone_attempt", "mentor_sessions", type_="unique"
    )
    op.drop_constraint(
        "fk_mentor_sessions_user_milestone_id", "mentor_sessions", type_="foreignkey"
    )
    op.drop_column("mentor_sessions", "closed_at")
    op.drop_column("mentor_sessions", "attempt")
    op.drop_column("mentor_sessions", "user_milestone_id")
    op.create_unique_constraint(
        "uq_mentor_session_user_project", "mentor_sessions", ["user_project_id"]
    )
