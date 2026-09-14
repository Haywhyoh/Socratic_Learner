"""Seed catalog courses, options, projects, milestones, and concept questions."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.concept import ConceptQuestion
from app.models.course import Course, CourseOption
from app.models.project import Milestone, Project, ProjectDifficulty
from app.seed_content import (
    CONTENT_CALENDAR,
    LEARNING_DASHBOARD,
    LIBRARY_CATALOG,
    NOTES_API,
    TASK_TRACKER,
    MilestoneSpec,
    ProjectSpec,
)

_DEFINITION_LIST_KEYS = (
    "prerequisites",
    "skills",
    "concepts",
    "constraints",
    "tests",
    "evaluation_criteria",
    "extension_challenges",
    "recommended_resources",
)


def _definition_fields(spec: ProjectSpec) -> dict[str, object]:
    difficulty = ProjectDifficulty(str(spec["difficulty"]))
    fields: dict[str, object] = {
        "objective": str(spec["objective"]),
        "difficulty": difficulty,
        "expected_outcome": str(spec["expected_outcome"]),
    }
    for key in _DEFINITION_LIST_KEYS:
        fields[key] = list(spec[key])  # type: ignore[arg-type]
    return fields


def _option(
    course_id: int,
    name: str,
    slug: str,
    parent_id: int | None = None,
) -> CourseOption:
    return CourseOption(course_id=course_id, name=name, slug=slug, parent_id=parent_id)


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


def _sync_milestones(db: Session, project: Project, milestones: list[MilestoneSpec]) -> None:
    existing = {
        m.order_index: m
        for m in db.query(Milestone).filter(Milestone.project_id == project.id).all()
    }
    for index, (title, description, instructions, criteria, concepts) in enumerate(
        milestones, start=1
    ):
        current = existing.get(index)
        if current is None:
            db.add(
                Milestone(
                    project_id=project.id,
                    order_index=index,
                    title=title,
                    description=description,
                    instructions=instructions,
                    success_criteria=criteria,
                    concepts=list(concepts),
                )
            )
        else:
            current.title = title
            current.description = description
            current.instructions = instructions
            current.success_criteria = criteria
            current.concepts = list(concepts)


def _ensure_project(
    db: Session,
    *,
    spec: ProjectSpec,
    course_id: int,
    primary_option_id: int,
    secondary_option_id: int,
) -> Project:
    title = str(spec["title"])
    description = str(spec["description"])
    definition = _definition_fields(spec)
    milestones = list(spec["milestones"])  # type: ignore[arg-type]

    project = db.query(Project).filter(Project.title == title).first()
    if project is None:
        project = Project(
            title=title,
            description=description,
            course_id=course_id,
            primary_option_id=primary_option_id,
            secondary_option_id=secondary_option_id,
            is_active=True,
            **definition,
        )
        db.add(project)
        db.flush()
        print(f"Seeded project: {title}")
    else:
        project.description = description
        project.course_id = course_id
        project.primary_option_id = primary_option_id
        project.secondary_option_id = secondary_option_id
        project.is_active = True
        for key, value in definition.items():
            setattr(project, key, value)
        print(f"Updated project definition: {title}")

    _sync_milestones(db, project, milestones)
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

    _ensure_project(
        db,
        spec=TASK_TRACKER,
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=fastapi_opt.id,
    )
    _ensure_project(
        db,
        spec=NOTES_API,
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=fastapi_opt.id,
    )
    _ensure_project(
        db,
        spec=LIBRARY_CATALOG,
        course_id=se.id,
        primary_option_id=python.id,
        secondary_option_id=django_opt.id,
    )
    _ensure_project(
        db,
        spec=LEARNING_DASHBOARD,
        course_id=se.id,
        primary_option_id=javascript.id,
        secondary_option_id=react_opt.id,
    )
    _ensure_project(
        db,
        spec=CONTENT_CALENDAR,
        course_id=business.id,
        primary_option_id=marketing.id,
        secondary_option_id=content_opt.id,
    )

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
