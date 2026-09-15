"""Seed the catalog: one course/path, one deterministic project — the

JavaScript Backend Framework curriculum graph. All prior stub projects
(Task Tracker, Notes API, Library Catalog, Learning Dashboard, Content
Calendar) and the Business course have been removed: this is the first real
structured learning experience for the platform.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.course import Course, CourseOption
from app.models.curriculum import Concept, ConceptDependency, MilestoneConcept
from app.models.project import Milestone, Project, ProjectCurriculumMode, ProjectDifficulty
from app.seed_js_backend_framework import CONCEPTS, DEPENDENCIES, MILESTONES, PROJECT_SPEC

_DEFINITION_LIST_KEYS = (
    "prerequisites",
    "skills",
    "constraints",
    "tests",
    "evaluation_criteria",
    "extension_challenges",
    "recommended_resources",
)


def _seed_course(db: Session) -> tuple[Course, CourseOption, CourseOption]:
    course = db.query(Course).filter(Course.slug == "javascript").first()
    if course is None:
        course = Course(
            slug="javascript",
            name="JavaScript",
            description="Build real systems in JavaScript through deliberate, mentored practice.",
            primary_label="Language",
            secondary_label="Track",
        )
        db.add(course)
        db.flush()
        print("Seeded course: JavaScript")

    primary = (
        db.query(CourseOption)
        .filter(
            CourseOption.course_id == course.id,
            CourseOption.slug == "javascript",
            CourseOption.parent_id.is_(None),
        )
        .first()
    )
    if primary is None:
        primary = CourseOption(course_id=course.id, name="JavaScript", slug="javascript")
        db.add(primary)
        db.flush()

    secondary = (
        db.query(CourseOption)
        .filter(
            CourseOption.course_id == course.id,
            CourseOption.slug == "node-core",
            CourseOption.parent_id == primary.id,
        )
        .first()
    )
    if secondary is None:
        secondary = CourseOption(
            course_id=course.id,
            name="Node.js core (no framework)",
            slug="node-core",
            parent_id=primary.id,
        )
        db.add(secondary)
        db.flush()

    return course, primary, secondary


def _sync_concepts(db: Session) -> None:
    existing = {c.id: c for c in db.query(Concept).all()}
    for spec in CONCEPTS:
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
    for concept_id, requires_concept_id, reason in DEPENDENCIES:
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


def _sync_milestones(db: Session, project: Project) -> None:
    existing = {
        m.order_index: m
        for m in db.query(Milestone).filter(
            Milestone.project_id == project.id, Milestone.user_project_id.is_(None)
        )
    }
    for index, spec in enumerate(MILESTONES, start=1):
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
    db: Session, *, course_id: int, primary_option_id: int, secondary_option_id: int
) -> Project:
    title = str(PROJECT_SPEC["title"])
    fields: dict[str, object] = {
        "description": str(PROJECT_SPEC["description"]),
        "objective": str(PROJECT_SPEC["objective"]),
        "difficulty": ProjectDifficulty(str(PROJECT_SPEC["difficulty"])),
        "expected_outcome": str(PROJECT_SPEC["expected_outcome"]),
        "curriculum_mode": ProjectCurriculumMode.deterministic,
    }
    for key in _DEFINITION_LIST_KEYS:
        fields[key] = list(PROJECT_SPEC[key])  # type: ignore[arg-type]
    fields["concepts"] = [spec["id"] for spec in CONCEPTS]

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

    _sync_milestones(db, project)
    return project


def seed(db: Session) -> None:
    course, primary, secondary = _seed_course(db)
    _sync_concepts(db)
    _sync_dependencies(db)
    _ensure_project(
        db,
        course_id=course.id,
        primary_option_id=primary.id,
        secondary_option_id=secondary.id,
    )
    db.commit()
    print("Seed complete (JavaScript Backend Framework curriculum graph).")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
