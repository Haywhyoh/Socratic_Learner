"""add project brief and milestone instructions

Revision ID: 2661eccabbb7
Revises: 891e2de86750
Create Date: 2026-09-14 20:41:04.449144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2661eccabbb7"
down_revision: Union[str, None] = "891e2de86750"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "projects",
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("milestones", "instructions", server_default=None)
    op.alter_column("projects", "brief", server_default=None)


def downgrade() -> None:
    op.drop_column("projects", "brief")
    op.drop_column("milestones", "instructions")
