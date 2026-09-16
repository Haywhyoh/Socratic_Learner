"""add project runtime and concept practice tasks

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-09-16 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    project_cols = _column_names("projects")
    concept_cols = _column_names("concepts")
    if "runtime" not in project_cols:
        op.add_column(
            "projects",
            sa.Column(
                "runtime",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if "practice_tasks" not in concept_cols:
        op.add_column(
            "concepts",
            sa.Column(
                "practice_tasks",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
    if "mentor_scripts" not in concept_cols:
        op.add_column(
            "concepts",
            sa.Column(
                "mentor_scripts",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    op.alter_column("projects", "runtime", server_default=None)
    op.alter_column("concepts", "practice_tasks", server_default=None)
    op.alter_column("concepts", "mentor_scripts", server_default=None)


def downgrade() -> None:
    concept_cols = _column_names("concepts")
    project_cols = _column_names("projects")
    if "mentor_scripts" in concept_cols:
        op.drop_column("concepts", "mentor_scripts")
    if "practice_tasks" in concept_cols:
        op.drop_column("concepts", "practice_tasks")
    if "runtime" in project_cols:
        op.drop_column("projects", "runtime")
