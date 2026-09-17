"""Author-time knowledge graph persistence.

Seed modules and the admin dashboard both write the same catalog shape:
Course + options + deterministic Project + Concept + ConceptDependency +
catalog Milestone / MilestoneConcept. Learner clones are not rewritten here.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.course import Course, CourseOption
from app.models.curriculum import Concept, ConceptDependency, MilestoneConcept
from app.models.enrollment import Enrollment
from app.models.project import Milestone, Project, ProjectCurriculumMode, ProjectDifficulty
from app.services.practice import normalize_practice_tasks
from app.services.runtime import runtime_for_language

DEFINITION_LIST_KEYS = (
    "prerequisites",
    "skills",
    "constraints",
    "tests",
    "evaluation_criteria",
    "extension_challenges",
    "recommended_resources",
)

# Old stub catalog rows from earlier seeds. Unknown slugs (admin-created tracks)
# must survive `python -m app.seed`.
LEGACY_COURSE_SLUGS = {
    "task-tracker",
    "business",
    "web-dev",
    "webdev",
    "data",
    "data-science",
    "fullstack",
}

CONCEPT_FIELD_KEYS = (
    "title",
    "category",
    "description",
    "learning_objectives",
    "misconceptions",
    "diagnostic_questions",
    "research_questions",
    "resources",
    "hints",
    "mastery_requirements",
    "practice_tasks",
    "mentor_scripts",
)


class GraphValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("; ".join(self.errors) or "Invalid knowledge graph")


def concept_fields_from_spec(spec: dict[str, Any], *, language: str | None = None) -> dict[str, Any]:
    return {
        "title": str(spec.get("title") or spec.get("id") or "Untitled"),
        "category": str(spec.get("category") or "foundation"),
        "description": str(spec.get("description") or ""),
        "learning_objectives": list(spec.get("learning_objectives") or []),
        "misconceptions": list(spec.get("misconceptions") or []),
        "diagnostic_questions": list(spec.get("diagnostic_questions") or []),
        "research_questions": list(spec.get("research_questions") or []),
        "resources": list(spec.get("resources") or []),
        "hints": list(spec.get("hints") or []),
        "mastery_requirements": dict(spec.get("mastery_requirements") or {}),
        "practice_tasks": normalize_practice_tasks(list(spec.get("practice_tasks") or []), language),
        "mentor_scripts": dict(spec.get("mentor_scripts") or {}),
    }


def concept_to_spec(concept: Concept, *, language: str | None = None) -> dict[str, Any]:
    return {
        "id": concept.id,
        "title": concept.title,
        "category": concept.category,
        "description": concept.description,
        "learning_objectives": list(concept.learning_objectives or []),
        "misconceptions": list(concept.misconceptions or []),
        "diagnostic_questions": list(concept.diagnostic_questions or []),
        "research_questions": list(concept.research_questions or []),
        "resources": list(concept.resources or []),
        "hints": list(concept.hints or []),
        "mastery_requirements": dict(concept.mastery_requirements or {}),
        "practice_tasks": normalize_practice_tasks(list(concept.practice_tasks or []), language),
        "mentor_scripts": dict(concept.mentor_scripts or {}),
    }


def normalize_dependency(item: Any) -> tuple[str, str, str]:
    if isinstance(item, dict):
        concept_id = str(item.get("concept_id") or item.get("id") or "").strip()
        requires = str(
            item.get("requires_concept_id") or item.get("requires") or ""
        ).strip()
        reason = str(item.get("reason") or "")
        return concept_id, requires, reason
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        reason = str(item[2]) if len(item) > 2 else ""
        return str(item[0]).strip(), str(item[1]).strip(), reason
    raise GraphValidationError(["Each dependency must be a triple or object"])


def graph_has_cycle(concept_ids: set[str], dependencies: list[tuple[str, str, str]]) -> bool:
    remaining = {cid: set() for cid in concept_ids}
    for concept_id, requires, _reason in dependencies:
        if concept_id in remaining and requires in remaining:
            remaining[concept_id].add(requires)
    ready = [cid for cid, deps in remaining.items() if not deps]
    seen: set[str] = set()
    while ready:
        node = ready.pop()
        seen.add(node)
        for cid, deps in remaining.items():
            if node in deps:
                deps.remove(node)
                if not deps and cid not in seen:
                    ready.append(cid)
    return seen != concept_ids


def validate_graph_payload(
    concepts: list[dict[str, Any]],
    dependencies: list[Any],
    milestones: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    errors: list[str] = []
    ids = [str(spec.get("id") or "").strip() for spec in concepts]
    if not concepts:
        errors.append("At least one concept is required")
    if any(not cid for cid in ids):
        errors.append("Every concept needs a non-empty id")
    if len(ids) != len(set(ids)):
        errors.append("Concept ids must be unique")
    id_set = {cid for cid in ids if cid}

    normalized: list[tuple[str, str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for item in dependencies:
        try:
            concept_id, requires, reason = normalize_dependency(item)
        except GraphValidationError as exc:
            errors.extend(exc.errors)
            continue
        if not concept_id or not requires:
            errors.append("Dependencies need concept_id and requires_concept_id")
            continue
        if concept_id == requires:
            errors.append(f"Concept {concept_id} cannot depend on itself")
            continue
        if concept_id not in id_set:
            errors.append(f"Dependency references unknown concept {concept_id}")
            continue
        if requires not in id_set:
            errors.append(f"Dependency references unknown prerequisite {requires}")
            continue
        key = (concept_id, requires)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        normalized.append((concept_id, requires, reason))

    if id_set and graph_has_cycle(id_set, normalized):
        errors.append("Concept dependencies contain a cycle")

    if not milestones:
        errors.append("At least one milestone is required")
    for spec in milestones:
        for concept_id in list(spec.get("concepts") or []):
            if str(concept_id) not in id_set:
                errors.append(f"Milestone references unknown concept {concept_id}")

    if errors:
        raise GraphValidationError(errors)
    return normalized


def retire_legacy_catalog(db: Session) -> None:
    """Remove leftover stub courses/projects from earlier seeds."""
    stale = db.query(Course).filter(Course.slug.in_(LEGACY_COURSE_SLUGS)).all()
    if not stale:
        return
    ids = [course.id for course in stale]
    db.query(Enrollment).filter(Enrollment.course_id.in_(ids)).delete(synchronize_session=False)
    db.query(Project).filter(Project.course_id.in_(ids)).delete(synchronize_session=False)
    db.query(Course).filter(Course.id.in_(ids)).delete(synchronize_session=False)
    print(f"Removed {len(ids)} legacy course(s).")


def ensure_course_path(
    db: Session,
    *,
    slug: str,
    name: str,
    description: str,
    primary_slug: str,
    primary_name: str,
    secondary_slug: str,
    secondary_name: str,
    primary_label: str = "Language",
    secondary_label: str = "Track",
) -> tuple[Course, CourseOption, CourseOption]:
    course = db.query(Course).filter(Course.slug == slug).first()
    if course is None:
        try:
            with db.begin_nested():
                course = Course(
                    slug=slug,
                    name=name,
                    description=description,
                    primary_label=primary_label,
                    secondary_label=secondary_label,
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
    course.primary_label = primary_label
    course.secondary_label = secondary_label

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


def upsert_concepts(
    db: Session, concepts: list[dict[str, Any]], *, language: str | None = None
) -> None:
    ids = [str(spec["id"]) for spec in concepts]
    existing = {
        c.id: c for c in db.query(Concept).filter(Concept.id.in_(ids)).all()
    } if ids else {}
    for spec in concepts:
        concept_id = str(spec["id"])
        fields = concept_fields_from_spec(spec, language=language)
        concept = existing.get(concept_id)
        if concept is None:
            db.add(Concept(id=concept_id, **fields))
        else:
            for key, value in fields.items():
                setattr(concept, key, value)
    db.flush()


def upsert_dependencies(
    db: Session,
    concept_ids: set[str],
    dependencies: list[tuple[str, str, str]],
) -> None:
    """Replace prerequisite edges whose both ends belong to this graph."""
    if not concept_ids:
        return
    existing_rows = (
        db.query(ConceptDependency)
        .filter(
            ConceptDependency.concept_id.in_(concept_ids),
            ConceptDependency.requires_concept_id.in_(concept_ids),
        )
        .all()
    )
    existing = {(d.concept_id, d.requires_concept_id): d for d in existing_rows}
    wanted = {(concept_id, requires): reason for concept_id, requires, reason in dependencies}
    for key, reason in wanted.items():
        dep = existing.get(key)
        if dep is None:
            db.add(
                ConceptDependency(
                    concept_id=key[0],
                    requires_concept_id=key[1],
                    reason=reason,
                )
            )
        else:
            dep.reason = reason
    for key, dep in existing.items():
        if key not in wanted:
            db.delete(dep)
    db.flush()


def catalog_milestones(db: Session, project_id: int) -> list[Milestone]:
    return (
        db.query(Milestone)
        .filter(Milestone.project_id == project_id, Milestone.user_project_id.is_(None))
        .order_by(Milestone.order_index)
        .all()
    )


def sync_milestones(db: Session, project: Project, milestones: list[dict[str, Any]]) -> None:
    existing = {m.order_index: m for m in catalog_milestones(db, project.id)}
    keep_indexes: set[int] = set()
    for index, spec in enumerate(milestones, start=1):
        keep_indexes.add(index)
        concept_ids = [str(cid) for cid in list(spec.get("concepts") or [])]
        current = existing.get(index)
        if current is None:
            current = Milestone(
                project_id=project.id,
                order_index=index,
                title=str(spec.get("title") or f"Milestone {index}"),
                description=str(spec.get("description") or ""),
                instructions=str(spec.get("instructions") or ""),
                success_criteria=str(spec.get("success_criteria") or ""),
                concepts=concept_ids,
                questions=list(spec.get("questions") or []),
            )
            db.add(current)
            db.flush()
        else:
            current.title = str(spec.get("title") or current.title)
            current.description = str(spec.get("description") or "")
            current.instructions = str(spec.get("instructions") or "")
            current.success_criteria = str(spec.get("success_criteria") or "")
            current.concepts = concept_ids
            current.questions = list(spec.get("questions") or [])
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

    extras = [row for index, row in existing.items() if index not in keep_indexes]
    for row in extras:
        db.query(MilestoneConcept).filter(MilestoneConcept.milestone_id == row.id).delete(
            synchronize_session=False
        )
        db.delete(row)
    db.flush()


def ensure_project(
    db: Session,
    *,
    spec: dict[str, Any],
    concepts: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    course_id: int,
    primary_option_id: int,
    secondary_option_id: int,
    project_id: int | None = None,
    match: Literal["title", "path", "id"] = "title",
) -> Project:
    title = str(spec["title"])
    fields: dict[str, object] = {
        "description": str(spec.get("description") or ""),
        "objective": str(spec.get("objective") or ""),
        "difficulty": ProjectDifficulty(str(spec.get("difficulty") or "beginner")),
        "expected_outcome": str(spec.get("expected_outcome") or ""),
        "curriculum_mode": ProjectCurriculumMode.deterministic,
        "runtime": dict(spec.get("runtime") or {}),
    }
    for key in DEFINITION_LIST_KEYS:
        fields[key] = list(spec.get(key) or [])
    fields["concepts"] = [item["id"] for item in concepts]

    project: Project | None = None
    if match == "id" or project_id is not None:
        if project_id is None:
            raise GraphValidationError(["project_id is required"])
        project = db.get(Project, project_id)
        if project is None:
            raise GraphValidationError([f"Project {project_id} not found"])
    elif match == "path":
        project = (
            db.query(Project)
            .filter(
                Project.course_id == course_id,
                Project.primary_option_id == primary_option_id,
                Project.secondary_option_id == secondary_option_id,
                Project.is_active.is_(True),
            )
            .first()
        )
    else:
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
        project.title = title
        project.course_id = course_id
        project.primary_option_id = primary_option_id
        project.secondary_option_id = secondary_option_id
        project.is_active = True
        for key, value in fields.items():
            setattr(project, key, value)
        print(f"Updated project definition: {title}")

    sync_milestones(db, project, milestones)
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


def _project_concept_ids(project: Project, db: Session) -> list[str]:
    ids = [str(cid) for cid in list(project.concepts or []) if str(cid)]
    if ids:
        return ids
    linked = (
        db.query(MilestoneConcept.concept_id)
        .join(Milestone, Milestone.id == MilestoneConcept.milestone_id)
        .filter(Milestone.project_id == project.id, Milestone.user_project_id.is_(None))
        .all()
    )
    return list(dict.fromkeys(str(row[0]) for row in linked))


def list_graphs(db: Session) -> list[dict[str, Any]]:
    projects = (
        db.query(Project)
        .filter(
            Project.is_active.is_(True),
            Project.curriculum_mode == ProjectCurriculumMode.deterministic,
        )
        .order_by(Project.id)
        .all()
    )
    summaries: list[dict[str, Any]] = []
    for project in projects:
        concept_ids = _project_concept_ids(project, db)
        edge_count = 0
        if concept_ids:
            edge_count = (
                db.query(ConceptDependency)
                .filter(
                    ConceptDependency.concept_id.in_(concept_ids),
                    ConceptDependency.requires_concept_id.in_(concept_ids),
                )
                .count()
            )
        milestone_count = (
            db.query(Milestone)
            .filter(Milestone.project_id == project.id, Milestone.user_project_id.is_(None))
            .count()
        )
        course = db.get(Course, project.course_id)
        summaries.append(
            {
                "project_id": project.id,
                "title": project.title,
                "description": project.description,
                "difficulty": project.difficulty.value
                if hasattr(project.difficulty, "value")
                else str(project.difficulty),
                "course_id": project.course_id,
                "course_slug": course.slug if course else "",
                "course_name": course.name if course else "",
                "language": str((project.runtime or {}).get("language") or ""),
                "concept_count": len(concept_ids),
                "edge_count": edge_count,
                "milestone_count": milestone_count,
            }
        )
    return summaries


def get_graph(db: Session, project_id: int) -> dict[str, Any]:
    project = db.get(Project, project_id)
    if project is None:
        raise GraphValidationError([f"Project {project_id} not found"])
    course = db.get(Course, project.course_id)
    primary = db.get(CourseOption, project.primary_option_id)
    secondary = db.get(CourseOption, project.secondary_option_id)
    concept_ids = _project_concept_ids(project, db)
    concepts = (
        db.query(Concept).filter(Concept.id.in_(concept_ids)).all() if concept_ids else []
    )
    concept_map = {row.id: row for row in concepts}
    language = str((project.runtime or {}).get("language") or "") or None
    ordered_concepts = [
        concept_to_spec(concept_map[cid], language=language)
        for cid in concept_ids
        if cid in concept_map
    ]
    deps: list[dict[str, str]] = []
    if concept_ids:
        rows = (
            db.query(ConceptDependency)
            .filter(
                ConceptDependency.concept_id.in_(concept_ids),
                ConceptDependency.requires_concept_id.in_(concept_ids),
            )
            .all()
        )
        deps = [
            {
                "concept_id": row.concept_id,
                "requires_concept_id": row.requires_concept_id,
                "reason": row.reason or "",
            }
            for row in rows
        ]
    milestones = [
        {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "instructions": row.instructions,
            "success_criteria": row.success_criteria,
            "order_index": row.order_index,
            "concepts": list(row.concepts or []),
            "questions": list(row.questions or []),
        }
        for row in catalog_milestones(db, project.id)
    ]
    difficulty = (
        project.difficulty.value if hasattr(project.difficulty, "value") else str(project.difficulty)
    )
    return {
        "project_id": project.id,
        "course": {
            "id": course.id if course else project.course_id,
            "slug": course.slug if course else "",
            "name": course.name if course else "",
            "description": course.description if course else "",
            "primary_label": course.primary_label if course else "Language",
            "secondary_label": course.secondary_label if course else "Track",
            "primary_slug": primary.slug if primary else "",
            "primary_name": primary.name if primary else "",
            "secondary_slug": secondary.slug if secondary else "",
            "secondary_name": secondary.name if secondary else "",
        },
        "project": {
            "title": project.title,
            "description": project.description,
            "objective": project.objective,
            "difficulty": difficulty,
            "expected_outcome": project.expected_outcome,
            "prerequisites": list(project.prerequisites or []),
            "skills": list(project.skills or []),
            "constraints": list(project.constraints or []),
            "tests": list(project.tests or []),
            "evaluation_criteria": list(project.evaluation_criteria or []),
            "extension_challenges": list(project.extension_challenges or []),
            "recommended_resources": list(project.recommended_resources or []),
            "runtime": dict(project.runtime or {}),
        },
        "concepts": ordered_concepts,
        "dependencies": deps,
        "milestones": milestones,
    }


def publish_graph(
    db: Session,
    payload: dict[str, Any],
    *,
    project_id: int | None = None,
) -> dict[str, Any]:
    course_spec = dict(payload.get("course") or {})
    project_spec = dict(payload.get("project") or {})
    concepts = [dict(item) for item in list(payload.get("concepts") or [])]
    milestones = [dict(item) for item in list(payload.get("milestones") or [])]
    normalized_deps = validate_graph_payload(
        concepts, list(payload.get("dependencies") or []), milestones
    )
    if not str(course_spec.get("slug") or "").strip():
        raise GraphValidationError(["Course slug is required"])
    if not str(project_spec.get("title") or "").strip():
        raise GraphValidationError(["Project title is required"])

    language = str((project_spec.get("runtime") or {}).get("language") or "")
    if not language:
        language = str(course_spec.get("primary_slug") or "javascript")
        project_spec["runtime"] = {
            **runtime_for_language(language),
            **dict(project_spec.get("runtime") or {}),
        }

    course, primary, secondary = ensure_course_path(
        db,
        slug=str(course_spec["slug"]).strip(),
        name=str(course_spec.get("name") or course_spec["slug"]).strip(),
        description=str(course_spec.get("description") or ""),
        primary_slug=str(course_spec.get("primary_slug") or language or "language").strip(),
        primary_name=str(course_spec.get("primary_name") or course_spec.get("primary_slug") or "Language"),
        secondary_slug=str(course_spec.get("secondary_slug") or "fundamentals").strip(),
        secondary_name=str(
            course_spec.get("secondary_name") or course_spec.get("secondary_slug") or "Fundamentals"
        ),
        primary_label=str(course_spec.get("primary_label") or "Language"),
        secondary_label=str(course_spec.get("secondary_label") or "Track"),
    )
    upsert_concepts(db, concepts, language=language or None)
    upsert_dependencies(db, {str(spec["id"]) for spec in concepts}, normalized_deps)
    match: Literal["title", "path", "id"] = "id" if project_id is not None else "path"
    project = ensure_project(
        db,
        spec=project_spec,
        concepts=concepts,
        milestones=milestones,
        course_id=course.id,
        primary_option_id=primary.id,
        secondary_option_id=secondary.id,
        project_id=project_id,
        match=match,
    )
    db.flush()
    return get_graph(db, project.id)
