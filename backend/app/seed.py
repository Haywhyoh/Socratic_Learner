"""Seed catalog courses, options, projects, milestones, and concept questions."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.concept import ConceptQuestion
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


def _get_option(db: Session, course_id: int, slug: str, parent_id: int | None = None) -> CourseOption:
    query = db.query(CourseOption).filter(
        CourseOption.course_id == course_id,
        CourseOption.slug == slug,
    )
    if parent_id is None:
        query = query.filter(CourseOption.parent_id.is_(None))
    else:
        query = query.filter(CourseOption.parent_id == parent_id)
    option = query.first()
    if option is None:
        raise RuntimeError(f"Missing course option slug={slug!r} parent_id={parent_id}")
    return option


def _ensure_project(
    db: Session,
    *,
    title: str,
    description: str,
    course_id: int,
    primary_option_id: int,
    secondary_option_id: int,
    milestones: list[tuple[str, str, str]],
) -> Project:
    project = db.query(Project).filter(Project.title == title).first()
    if project is None:
        project = Project(
            title=title,
            description=description,
            course_id=course_id,
            primary_option_id=primary_option_id,
            secondary_option_id=secondary_option_id,
            is_active=True,
        )
        db.add(project)
        db.flush()
        db.add_all(_milestones(project.id, milestones))
        print(f"Seeded project: {title}")
    return project


def _ensure_question(
    db: Session,
    *,
    course_id: int,
    primary_option_id: int,
    secondary_option_id: int,
    question_text: str,
) -> None:
    exists = (
        db.query(ConceptQuestion)
        .filter(
            ConceptQuestion.course_id == course_id,
            ConceptQuestion.primary_option_id == primary_option_id,
            ConceptQuestion.secondary_option_id == secondary_option_id,
            ConceptQuestion.question_text == question_text,
        )
        .first()
    )
    if exists is None:
        db.add(
            ConceptQuestion(
                course_id=course_id,
                primary_option_id=primary_option_id,
                secondary_option_id=secondary_option_id,
                question_text=question_text,
                is_active=True,
            )
        )


def _seed_base_catalog(db: Session) -> tuple[Course, Course]:
    se = db.query(Course).filter(Course.slug == "software-engineering").first()
    business = db.query(Course).filter(Course.slug == "business").first()
    if se is not None and business is not None:
        return se, business

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

    db.add_all(
        [
            _option(se.id, "FastAPI", "fastapi", parent_id=python.id),
            _option(se.id, "Django", "django", parent_id=python.id),
            _option(se.id, "React", "react", parent_id=javascript.id),
            _option(business.id, "Content Strategy", "content-strategy", parent_id=marketing.id),
            _option(business.id, "Accounting", "accounting", parent_id=finance.id),
        ]
    )
    db.flush()
    print("Seeded base courses and options.")
    return se, business


def seed(db: Session) -> None:
    se, business = _seed_base_catalog(db)

    python = _get_option(db, se.id, "python")
    javascript = _get_option(db, se.id, "javascript")
    marketing = _get_option(db, business.id, "marketing")
    fastapi_opt = _get_option(db, se.id, "fastapi", parent_id=python.id)
    django_opt = _get_option(db, se.id, "django", parent_id=python.id)
    react_opt = _get_option(db, se.id, "react", parent_id=javascript.id)
    content_opt = _get_option(db, business.id, "content-strategy", parent_id=marketing.id)

    # Python / FastAPI projects
    _ensure_project(
        db,
        title="Task Tracker API",
        description="Build a FastAPI service for creating, listing, and completing tasks.",
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=fastapi_opt.id,
        milestones=[
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
    _ensure_project(
        db,
        title="Notes API with Tags",
        description="Build a FastAPI notes service with tagging, search, and pagination.",
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=fastapi_opt.id,
        milestones=[
            (
                "Note model and create endpoint",
                "Persist notes with title and body; expose POST /notes.",
                "Creating a note returns 201 with an id.",
            ),
            (
                "Tags and filtering",
                "Attach tags to notes and filter list results by tag.",
                "GET /notes?tag=python returns only matching notes.",
            ),
            (
                "Search and pagination",
                "Add text search plus limit/offset pagination.",
                "Search and page params change the result set correctly.",
            ),
        ],
    )

    # Python / Django project
    _ensure_project(
        db,
        title="Library Catalog",
        description="Build a Django app to catalog books, authors, and borrow status.",
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=django_opt.id,
        milestones=[
            (
                "Models and admin",
                "Create Book and Author models and register them in Django admin.",
                "Books and authors can be created in the admin UI.",
            ),
            (
                "Catalog list views",
                "Expose list and detail pages for books.",
                "Catalog pages render without template errors.",
            ),
            (
                "Borrow workflow",
                "Track whether a book is available or borrowed.",
                "Borrowing a book flips availability and shows on the detail page.",
            ),
        ],
    )

    # Existing non-Python projects
    _ensure_project(
        db,
        title="Learning Dashboard",
        description="Build a React dashboard that visualizes a learner's progress.",
        course_id=se.id,
        primary_option_id=javascript.id,
        secondary_option_id=react_opt.id,
        milestones=[
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
    _ensure_project(
        db,
        title="Content Calendar Sprint",
        description="Design a 4-week content calendar and measurement plan for a product launch.",
        course_id=business.id,
        primary_option_id=marketing.id,
        secondary_option_id=content_opt.id,
        milestones=[
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

    # Python concept questions (stand-in for AI generation)
    python_fastapi_questions = [
        (
            "Why might you prefer dependency injection over importing a database session "
            "directly inside a FastAPI route, and what breaks if you don't?"
        ),
        (
            "Explain the difference between validating request bodies with Pydantic models "
            "versus validating query parameters. When would each approach hide bugs?"
        ),
        (
            "A FastAPI endpoint returns a list of ORM objects. What serialization pitfalls "
            "appear with relationships and lazy loading, and how would you design around them?"
        ),
    ]
    python_django_questions = [
        (
            "When would you choose a Django class-based view over a function-based view "
            "for a catalog page, and what complexity does that choice push onto beginners?"
        ),
        (
            "Explain why Django's ORM `select_related` vs `prefetch_related` matters for a "
            "book list that also shows authors. What N+1 failure looks like in practice?"
        ),
        (
            "A model field uses blank=True but not null=True. What does that mean for forms, "
            "the database, and API clients that send missing values?"
        ),
    ]

    for text in python_fastapi_questions:
        _ensure_question(
            db,
            course_id=se.id,
            primary_option_id=python.id,
            secondary_option_id=fastapi_opt.id,
            question_text=text,
        )
    for text in python_django_questions:
        _ensure_question(
            db,
            course_id=se.id,
            primary_option_id=python.id,
            secondary_option_id=django_opt.id,
            question_text=text,
        )

    _backfill_empty_concept_sessions(db)

    db.commit()
    print("Seed complete (projects + concept questions ensured).")


def _backfill_empty_concept_sessions(db: Session) -> None:
    """Fill concept sessions created before the question catalog existed."""
    from app.models.concept import ConceptSession, ConceptSessionStatus
    from app.models.enrollment import Enrollment, LearningMode

    empty_sessions = (
        db.query(ConceptSession)
        .join(Enrollment, ConceptSession.enrollment_id == Enrollment.id)
        .filter(
            ConceptSession.question_text.is_(None),
            Enrollment.learning_mode == LearningMode.concept,
        )
        .all()
    )
    filled = 0
    for session in empty_sessions:
        enrollment = db.get(Enrollment, session.enrollment_id)
        if enrollment is None:
            continue
        question = (
            db.query(ConceptQuestion)
            .filter(
                ConceptQuestion.course_id == enrollment.course_id,
                ConceptQuestion.primary_option_id == enrollment.primary_option_id,
                ConceptQuestion.secondary_option_id == enrollment.secondary_option_id,
                ConceptQuestion.is_active.is_(True),
            )
            .order_by(ConceptQuestion.id)
            .first()
        )
        if question is None:
            continue
        session.question_text = question.question_text
        session.status = ConceptSessionStatus.active
        filled += 1
    if filled:
        print(f"Backfilled {filled} empty concept session(s) with seeded questions.")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
