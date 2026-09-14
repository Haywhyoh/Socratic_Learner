"""Seed catalog courses, options, projects, and milestones."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.course import Course, CourseOption
from app.models.project import Milestone, Project


def _option(
    course_id: int,
    name: str,
    slug: str,
    parent_id: int | None = None,
) -> CourseOption:
    return CourseOption(course_id=course_id, name=name, slug=slug, parent_id=parent_id)


def _milestones(project_id: int, items: list[tuple[str, str, str]]) -> list[Milestone]:
    return [
        Milestone(
            project_id=project_id,
            order_index=index,
            title=title,
            description=description,
            success_criteria=criteria,
        )
        for index, (title, description, criteria) in enumerate(items, start=1)
    ]


def seed(db: Session) -> None:
    if db.query(Course).first() is not None:
        print("Catalog already seeded; skipping.")
        return

    se = Course(
        slug="software-engineering",
        name="Software Engineering",
        description="Build software through languages, frameworks, and deliberate practice.",
        primary_label="Language",
        secondary_label="Framework",
    )
    business = Course(
        slug="business",
        name="Business",
        description="Learn business domains through applied projects and hard questions.",
        primary_label="Domain",
        secondary_label="Focus",
    )
    db.add_all([se, business])
    db.flush()

    python = _option(se.id, "Python", "python")
    javascript = _option(se.id, "JavaScript", "javascript")
    marketing = _option(business.id, "Marketing", "marketing")
    finance = _option(business.id, "Finance", "finance")
    db.add_all([python, javascript, marketing, finance])
    db.flush()

    fastapi_opt = _option(se.id, "FastAPI", "fastapi", parent_id=python.id)
    django_opt = _option(se.id, "Django", "django", parent_id=python.id)
    react_opt = _option(se.id, "React", "react", parent_id=javascript.id)
    content_opt = _option(business.id, "Content Strategy", "content-strategy", parent_id=marketing.id)
    accounting_opt = _option(business.id, "Accounting", "accounting", parent_id=finance.id)
    db.add_all([fastapi_opt, django_opt, react_opt, content_opt, accounting_opt])
    db.flush()

    task_api = Project(
        title="Task Tracker API",
        description="Build a FastAPI service for creating, listing, and completing tasks.",
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=fastapi_opt.id,
        is_active=True,
    )
    react_dashboard = Project(
        title="Learning Dashboard",
        description="Build a React dashboard that visualizes a learner's progress.",
        course_id=se.id,
        primary_option_id=javascript.id,
        secondary_option_id=react_opt.id,
        is_active=True,
    )
    content_calendar = Project(
        title="Content Calendar Sprint",
        description="Design a 4-week content calendar and measurement plan for a product launch.",
        course_id=business.id,
        primary_option_id=marketing.id,
        secondary_option_id=content_opt.id,
        is_active=True,
    )
    db.add_all([task_api, react_dashboard, content_calendar])
    db.flush()

    db.add_all(
        _milestones(
            task_api.id,
            [
                (
                    "Scaffold the API",
                    "Create the FastAPI app, health endpoint, and project layout.",
                    "GET /health returns 200 and the app starts cleanly.",
                ),
                (
                    "CRUD for tasks",
                    "Implement create, list, and complete task endpoints with persistence.",
                    "Tasks can be created, listed, and marked complete via the API.",
                ),
                (
                    "Auth-aware ownership",
                    "Restrict task access to the authenticated owner.",
                    "Users cannot read or mutate another user's tasks.",
                ),
            ],
        )
    )
    db.add_all(
        _milestones(
            react_dashboard.id,
            [
                (
                    "App shell",
                    "Create the React app shell with routing and a basic layout.",
                    "Two routes render without console errors.",
                ),
                (
                    "Progress widgets",
                    "Render milestone progress cards from mock API data.",
                    "At least three progress widgets display correctly.",
                ),
                (
                    "Interactive filters",
                    "Add filters for course and learning mode.",
                    "Filtering updates the visible widgets without a full page reload.",
                ),
            ],
        )
    )
    db.add_all(
        _milestones(
            content_calendar.id,
            [
                (
                    "Audience brief",
                    "Write a one-page audience and positioning brief.",
                    "Brief names audience, pain, promise, and proof.",
                ),
                (
                    "Four-week calendar",
                    "Produce a 4-week calendar with channels and CTAs.",
                    "Calendar includes at least 12 dated content items.",
                ),
                (
                    "Measurement plan",
                    "Define KPIs and a weekly review ritual.",
                    "Plan lists leading and lagging indicators with owners.",
                ),
            ],
        )
    )

    db.commit()
    print("Seeded courses, options, projects, and milestones.")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
