import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SandboxWorkspaceStatus(str, enum.Enum):
    ready = "ready"
    error = "error"


class SandboxWorkspace(Base):
    __tablename__ = "sandbox_workspaces"
    __table_args__ = (
        UniqueConstraint("user_project_id", name="uq_sandbox_workspace_user_project"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_project_id: Mapped[int] = mapped_column(
        ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SandboxWorkspaceStatus] = mapped_column(
        Enum(SandboxWorkspaceStatus, name="sandbox_workspace_status", native_enum=False),
        default=SandboxWorkspaceStatus.ready,
        nullable=False,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_summary: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
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
