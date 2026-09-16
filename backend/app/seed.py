"""Seed the catalog: JavaScript backend-framework graph plus the Python
fundamentals + CLI-notebook graph. Legacy stub courses (Task Tracker, Business,
etc.) are still removed; both real language tracks stay active.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.course import Course, CourseOption
from app.models.curriculum import Concept, ConceptDependency, MilestoneConcept
from app.models.enrollment import Enrollment
from app.models.project import Milestone, Project, ProjectCurriculumMode, ProjectDifficulty
from app.seed_js_backend_framework import (
    CONCEPTS as JS_CONCEPTS,
    DEPENDENCIES as JS_DEPENDENCIES,
    MILESTONES as JS_MILESTONES,
    PROJECT_SPEC as JS_PROJECT,
)
from app.seed_python_fundamentals import (
    CONCEPTS as PY_CONCEPTS,
    DEPENDENCIES as PY_DEPENDENCIES,
    MILESTONES as PY_MILESTONES,
    PROJECT_SPEC as PY_PROJECT,
)

_ALLOWED_COURSE_SLUGS = {"javascript", "python"}

_DEFINITION_LIST_KEYS = (
    "prerequisites",
    "skills",
    "constraints",
    "tests",
    "evaluation_criteria",
    "extension_challenges",
    "recommended_resources",
)

_ALL_CONCEPTS = list(JS_CONCEPTS) + list(PY_CONCEPTS)
_ALL_DEPENDENCIES = list(JS_DEPENDENCIES) + list(PY_DEPENDENCIES)


def _seed_language_course(
    db: Session,
    *,
    slug: str,
    name: str,
    description: str,
    primary_slug: str,
    primary_name: str,
    secondary_slug: str,
    secondary_name: str,
) -> tuple[Course, CourseOption, CourseOption]:
    course = db.query(Course).filter(Course.slug == slug).first()
    if course is None:
        try:
            with db.begin_nested():
                course = Course(
                    slug=slug,
                    name=name,
                    description=description,
                    primary_label="Language",
                    secondary_label="Track",
                )
                db.add(course)
                db.flush()
            print(f"Seeded course: {name}")
        except IntegrityError:
            course = db.query(Course).filter(Course.slug == slug).first()
    if course is None:
        raise RuntimeError(f"Could not seed course '{slug}'")
    course.name = name
    course.description = description
    course.primary_label = "Language"
    course.secondary_label = "Track"

    primary = (
        db.query(CourseOption)
        .filter(
            CourseOption.course_id == course.id,
            CourseOption.slug == primary_slug,
            CourseOption.parent_id.is_(None),
        )
        .first()
    )
    if primary is None:
        try:
            with db.begin_nested():
                primary = CourseOption(
                    course_id=course.id, name=primary_name, slug=primary_slug
                )
                db.add(primary)
                db.flush()
        except IntegrityError:
            primary = (
                db.query(CourseOption)
                .filter(
                    CourseOption.course_id == course.id,
                    CourseOption.slug == primary_slug,
                    CourseOption.parent_id.is_(None),
                )
                .first()
            )
    if primary is None:
        raise RuntimeError(f"Could not seed option '{primary_slug}' on {slug}")
    primary.name = primary_name

    secondary = (
        db.query(CourseOption)
        .filter(
            CourseOption.course_id == course.id,
            CourseOption.slug == secondary_slug,
            CourseOption.parent_id == primary.id,
        )
        .first()
    )
    if secondary is None:
        try:
            with db.begin_nested():
                secondary = CourseOption(
                    course_id=course.id,
                    name=secondary_name,
                    slug=secondary_slug,
                    parent_id=primary.id,
                )
                db.add(secondary)
                db.flush()
        except IntegrityError:
            secondary = (
                db.query(CourseOption)
                .filter(
                    CourseOption.course_id == course.id,
                    CourseOption.slug == secondary_slug,
                    CourseOption.parent_id == primary.id,
                )
                .first()
            )
    if secondary is None:
        raise RuntimeError(f"Could not seed option '{secondary_slug}' on {slug}")
    secondary.name = secondary_name

    return course, primary, secondary


def _sync_concepts(db: Session) -> None:
    existing = {c.id: c for c in db.query(Concept).all()}
    for spec in _ALL_CONCEPTS:
        concept = existing.get(spec["id"])
        fields = {
            "title": spec["title"],
            "category": spec["category"],
            "description": spec["description"],
            "learning_objectives": list(spec.get("learning_objectives") or []),
            "misconceptions": list(spec.get("misconceptions") or []),
            "diagnostic_questions": list(spec.get("diagnostic_questions") or []),
            "research_questions": list(spec.get("research_questions") or []),
            "resources": list(spec.get("resources") or []),
            "hints": list(spec.get("hints") or []),
            "mastery_requirements": dict(spec.get("mastery_requirements") or {}),
            "practice_tasks": list(spec.get("practice_tasks") or []),
            "mentor_scripts": dict(spec.get("mentor_scripts") or {}),
        }
        if concept is None:
            db.add(Concept(id=spec["id"], **fields))
        else:
            for key, value in fields.items():
                setattr(concept, key, value)
    db.flush()


def _sync_dependencies(db: Session) -> None:
    existing = {
        (d.concept_id, d.requires_concept_id): d for d in db.query(ConceptDependency).all()
    }
    for concept_id, requires_concept_id, reason in _ALL_DEPENDENCIES:
        key = (concept_id, requires_concept_id)
        dep = existing.get(key)
        if dep is None:
            db.add(
                ConceptDependency(
                    concept_id=concept_id,
                    requires_concept_id=requires_concept_id,
                    reason=reason,
                )
            )
        else:
            dep.reason = reason
    db.flush()


def _sync_milestones(db: Session, project: Project, milestones: list[dict[str, Any]]) -> None:
    existing = {
        m.order_index: m
        for m in db.query(Milestone).filter(
            Milestone.project_id == project.id, Milestone.user_project_id.is_(None)
        )
    }
    for index, spec in enumerate(milestones, start=1):
        concept_ids = list(spec.get("concepts") or [])
        current = existing.get(index)
        if current is None:
            current = Milestone(
                project_id=project.id,
                order_index=index,
                title=spec["title"],
                description=spec["description"],
                instructions=spec["instructions"],
                success_criteria=spec["success_criteria"],
                concepts=concept_ids,
                questions=[],
            )
            db.add(current)
            db.flush()
        else:
            current.title = spec["title"]
            current.description = spec["description"]
            current.instructions = spec["instructions"]
            current.success_criteria = spec["success_criteria"]
            current.concepts = concept_ids
            db.flush()

        existing_links = {
            mc.concept_id: mc
            for mc in db.query(MilestoneConcept).filter(MilestoneConcept.milestone_id == current.id)
        }
        for order, concept_id in enumerate(concept_ids):
            if concept_id in existing_links:
                existing_links[concept_id].order_index = order
            else:
                db.add(
                    MilestoneConcept(
                        milestone_id=current.id, concept_id=concept_id, order_index=order
                    )
                )
        for concept_id, link in existing_links.items():
            if concept_id not in concept_ids:
                db.delete(link)
    db.flush()


def _ensure_project(
    db: Session,
    *,
    spec: dict[str, Any],
    concepts: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    course_id: int,
    primary_option_id: int,
    secondary_option_id: int,
) -> Project:
    title = str(spec["title"])
    fields: dict[str, object] = {
        "description": str(spec["description"]),
        "objective": str(spec["objective"]),
        "difficulty": ProjectDifficulty(str(spec["difficulty"])),
        "expected_outcome": str(spec["expected_outcome"]),
        "curriculum_mode": ProjectCurriculumMode.deterministic,
        "runtime": dict(spec.get("runtime") or {}),
    }
    for key in _DEFINITION_LIST_KEYS:
        fields[key] = list(spec[key])  # type: ignore[arg-type]
    fields["concepts"] = [item["id"] for item in concepts]

    project = db.query(Project).filter(Project.title == title).first()
    if project is None:
        project = Project(
            title=title,
            course_id=course_id,
            primary_option_id=primary_option_id,
            secondary_option_id=secondary_option_id,
            is_active=True,
            **fields,
        )
        db.add(project)
        db.flush()
        print(f"Seeded project: {title}")
    else:
        project.course_id = course_id
        project.primary_option_id = primary_option_id
        project.secondary_option_id = secondary_option_id
        project.is_active = True
        for key, value in fields.items():
            setattr(project, key, value)
        print(f"Updated project definition: {title}")

    _sync_milestones(db, project, milestones)
    duplicates = (
        db.query(Project)
        .filter(
            Project.id != project.id,
            Project.is_active.is_(True),
            Project.course_id == course_id,
            Project.primary_option_id == primary_option_id,
            Project.secondary_option_id == secondary_option_id,
        )
        .all()
    )
    for other in duplicates:
        other.is_active = False
    return project


def _retire_legacy_catalog(db: Session) -> None:
    """Remove leftover stub courses/projects from earlier seeds."""
    stale = db.query(Course).filter(Course.slug.notin_(_ALLOWED_COURSE_SLUGS)).all()
    if not stale:
        return
    ids = [course.id for course in stale]
    db.query(Enrollment).filter(Enrollment.course_id.in_(ids)).delete(synchronize_session=False)
    db.query(Project).filter(Project.course_id.in_(ids)).delete(synchronize_session=False)
    db.query(Course).filter(Course.id.in_(ids)).delete(synchronize_session=False)
    print(f"Removed {len(ids)} legacy course(s).")


def seed(db: Session) -> None:
    _retire_legacy_catalog(db)
    js_course, js_primary, js_secondary = _seed_language_course(
        db,
        slug="javascript",
        name="JavaScript",
        description="Build real systems in JavaScript through deliberate, mentored practice.",
        primary_slug="javascript",
        primary_name="JavaScript",
        secondary_slug="node-core",
        secondary_name="Node.js core (no framework)",
    )
    py_course, py_primary, py_secondary = _seed_language_course(
        db,
        slug="python",
        name="Python",
        description="Learn Python through mentored practice, then build a small CLI.",
        primary_slug="python",
        primary_name="Python",
        secondary_slug="stdlib",
        secondary_name="Standard library (no web framework)",
    )
    _sync_concepts(db)
    _sync_dependencies(db)
    _ensure_project(
        db,
        spec=JS_PROJECT,
        concepts=list(JS_CONCEPTS),
        milestones=list(JS_MILESTONES),
        course_id=js_course.id,
        primary_option_id=js_primary.id,
        secondary_option_id=js_secondary.id,
    )
    _ensure_project(
        db,
        spec=PY_PROJECT,
        concepts=list(PY_CONCEPTS),
        milestones=list(PY_MILESTONES),
        course_id=py_course.id,
        primary_option_id=py_primary.id,
        secondary_option_id=py_secondary.id,
    )
    db.commit()
    print("Seed complete (JavaScript backend framework + Python fundamentals).")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
