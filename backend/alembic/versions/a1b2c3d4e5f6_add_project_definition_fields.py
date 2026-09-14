"""add project definition fields

Revision ID: a1b2c3d4e5f6
Revises: 2661eccabbb7
Create Date: 2026-09-14 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "2661eccabbb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_empty_list = sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "projects",
        sa.Column(
            "difficulty",
            sa.Enum(
                "beginner",
                "intermediate",
                "advanced",
                name="project_difficulty",
                native_enum=False,
            ),
            nullable=False,
            server_default="beginner",
        ),
    )
    op.add_column(
        "projects",
        sa.Column("expected_outcome", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "projects",
        sa.Column(
            "prerequisites",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "skills",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "concepts",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "constraints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "tests",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "evaluation_criteria",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "extension_challenges",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "recommended_resources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=_empty_list,
        ),
    )

    op.alter_column("projects", "objective", server_default=None)
    op.alter_column("projects", "difficulty", server_default=None)
    op.alter_column("projects", "expected_outcome", server_default=None)
    op.alter_column("projects", "prerequisites", server_default=None)
    op.alter_column("projects", "skills", server_default=None)
    op.alter_column("projects", "concepts", server_default=None)
    op.alter_column("projects", "constraints", server_default=None)
    op.alter_column("projects", "tests", server_default=None)
    op.alter_column("projects", "evaluation_criteria", server_default=None)
    op.alter_column("projects", "extension_challenges", server_default=None)
    op.alter_column("projects", "recommended_resources", server_default=None)

    op.drop_column("projects", "brief")


def downgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("projects", "brief", server_default=None)

    op.drop_column("projects", "recommended_resources")
    op.drop_column("projects", "extension_challenges")
    op.drop_column("projects", "evaluation_criteria")
    op.drop_column("projects", "tests")
    op.drop_column("projects", "constraints")
    op.drop_column("projects", "concepts")
    op.drop_column("projects", "skills")
    op.drop_column("projects", "prerequisites")
    op.drop_column("projects", "expected_outcome")
    op.drop_column("projects", "difficulty")
    op.drop_column("projects", "objective")
