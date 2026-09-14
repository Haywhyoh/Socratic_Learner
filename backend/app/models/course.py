from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_label: Mapped[str] = mapped_column(String(100), nullable=False)
    secondary_label: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    options = relationship("CourseOption", back_populates="course", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="course")
    enrollments = relationship("Enrollment", back_populates="course")


class CourseOption(Base):
    __tablename__ = "course_options"
    __table_args__ = (
        UniqueConstraint("course_id", "parent_id", "slug", name="uq_course_option_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_options.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    course = relationship("Course", back_populates="options")
    parent = relationship("CourseOption", remote_side=[id], back_populates="children")
    children = relationship("CourseOption", back_populates="parent", cascade="all, delete-orphan")
