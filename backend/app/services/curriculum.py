"""Per-learner curriculum materialization.

Graph-driven (``curriculum_mode=deterministic``) projects clone the seeded
catalog outline 1:1 and initialize ConceptState rows. The AI mentor never
invents or reorders that graph.

``ai_generated`` is the legacy per-learner LLM-tailored path, kept as a
fallback for any project that still opts into it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.agents.llm import get_coach_llm
from app.models.course import CourseOption
from app.models.curriculum import MilestoneConcept
from app.models.project import (
    Milestone,
    Project,
    ProjectCurriculumMode,
    UserMilestone,
    UserMilestoneStatus,
    UserProject,
)
from app.services import curriculum_graph
from app.services.curriculum_authoring import GraphValidationError


def _catalog_outline(db: Session, project_id: int) -> list[dict[str, object]]:
    rows = curriculum_graph.catalog_milestones(db, project_id)
    return [
        {
            "title": row.title,
            "description": row.description,
            "instructions": row.instructions,
            "success_criteria": row.success_criteria,
            "concepts": list(row.concepts or []),
            "questions": list(row.questions or []),
            "catalog_milestone_id": row.id,
        }
        for row in rows
    ]


def _replace_concept_links(db: Session, milestone: Milestone, concept_ids: list[str]) -> None:
    existing = {
        row.concept_id: row
        for row in db.query(MilestoneConcept).filter(MilestoneConcept.milestone_id == milestone.id)
    }
    for order, concept_id in enumerate(concept_ids):
        current = existing.get(concept_id)
        if current is None:
            db.add(
                MilestoneConcept(
                    milestone_id=milestone.id,
                    concept_id=concept_id,
                    order_index=order,
                )
            )
        else:
            current.order_index = order
    keep = set(concept_ids)
    for concept_id, row in existing.items():
        if concept_id not in keep:
            db.delete(row)
    milestone.concepts = list(concept_ids)


def _clone_concept_links(
    db: Session, catalog_milestone_id: int | None, learner_milestone: Milestone
) -> None:
    if catalog_milestone_id is None:
        _replace_concept_links(
            db, learner_milestone, [str(cid) for cid in list(learner_milestone.concepts or [])]
        )
        return
    links = (
        db.query(MilestoneConcept)
        .filter(MilestoneConcept.milestone_id == catalog_milestone_id)
        .order_by(MilestoneConcept.order_index)
        .all()
    )
    _replace_concept_links(db, learner_milestone, [link.concept_id for link in links])


def generate_milestones_for_user_project(
    db: Session,
    user_project: UserProject,
    project: Project,
) -> list[Milestone]:
    """Materialize this learner's milestone sequence and progress rows.

    Must run inside the same transaction as the enrollment; caller commits.
    """
    catalog = _catalog_outline(db, project.id)
    mode = project.curriculum_mode
    if isinstance(mode, str):
        mode = ProjectCurriculumMode(mode)

    if mode == ProjectCurriculumMode.deterministic:
        specs = catalog
    else:
        language = db.get(CourseOption, project.primary_option_id)
        framework = db.get(CourseOption, project.secondary_option_id)
        llm = get_coach_llm()
        specs = llm.generate_curriculum(
            project_title=project.title,
            project_objective=project.objective,
            language=language.name if language else "",
            framework=framework.name if framework else "",
            skills=list(project.skills or []),
            concepts=list(project.concepts or []),
            constraints=list(project.constraints or []),
            tests=list(project.tests or []),
            catalog=catalog,
        )
        if not specs:
            specs = catalog

    milestones: list[Milestone] = []
    for index, spec in enumerate(specs, start=1):
        milestone = Milestone(
            project_id=project.id,
            user_project_id=user_project.id,
            generated=mode != ProjectCurriculumMode.deterministic,
            order_index=index,
            title=str(spec.get("title", f"Milestone {index}")),
            description=str(spec.get("description", "")),
            instructions=str(spec.get("instructions", "")),
            success_criteria=str(spec.get("success_criteria", "")),
            concepts=list(spec.get("concepts") or []),
            questions=list(spec.get("questions") or []),
        )
        db.add(milestone)
        milestones.append(milestone)
    db.flush()

    for spec, milestone in zip(specs, milestones):
        catalog_id = spec.get("catalog_milestone_id")
        _clone_concept_links(
            db,
            int(catalog_id) if catalog_id is not None else None,
            milestone,
        )

    for milestone in milestones:
        db.add(
            UserMilestone(
                user_project_id=user_project.id,
                milestone_id=milestone.id,
                status=UserMilestoneStatus.pending,
            )
        )
    db.flush()
    curriculum_graph.initialize_learning_state(db, user_project)
    return milestones


def _copy_catalog_milestone(learner: Milestone, catalog: Milestone, concept_ids: list[str]) -> None:
    learner.title = catalog.title
    learner.description = catalog.description
    learner.instructions = catalog.instructions
    learner.success_criteria = catalog.success_criteria
    learner.questions = list(catalog.questions or [])
    learner.concepts = list(concept_ids)


def _freeze_order(user_project: UserProject) -> int | None:
    """Highest order_index that must not change.

    Completed milestones stay frozen. The current pending milestone has been
    started, so it stays frozen too. ``None`` means the course is complete.
    """
    current = curriculum_graph.current_user_milestone(user_project)
    if current is None or current.milestone is None:
        return None
    completed = [
        um.milestone.order_index
        for um in user_project.user_milestones
        if um.status == UserMilestoneStatus.completed and um.milestone is not None
    ]
    return max([current.milestone.order_index, *completed])


def _apply_catalog_to_user_project(
    db: Session, user_project: UserProject, catalog: list[Milestone]
) -> dict[str, object]:
    freeze_at = _freeze_order(user_project)
    if freeze_at is None:
        return {
            "enrollment_id": user_project.enrollment_id,
            "user_project_id": user_project.id,
            "status": "skipped",
            "reason": "course_complete",
            "freeze_order": None,
            "milestones_updated": 0,
            "milestones_added": 0,
            "milestones_removed": 0,
        }

    learner_by_order = {
        milestone.order_index: milestone
        for milestone in curriculum_graph.learner_milestones(user_project)
    }
    catalog_orders = {row.order_index for row in catalog}
    updated = 0
    added = 0

    for row in catalog:
        if row.order_index <= freeze_at:
            continue
        concept_ids = curriculum_graph.concept_ids_for_milestone(db, row.id)
        learner = learner_by_order.get(row.order_index)
        if learner is None:
            learner = Milestone(
                project_id=user_project.project_id,
                user_project_id=user_project.id,
                generated=False,
                order_index=row.order_index,
                title=row.title,
                description=row.description,
                instructions=row.instructions,
                success_criteria=row.success_criteria,
                questions=list(row.questions or []),
                concepts=list(concept_ids),
            )
            db.add(learner)
            db.flush()
            _replace_concept_links(db, learner, concept_ids)
            user_milestone = UserMilestone(
                user_project_id=user_project.id,
                milestone_id=learner.id,
                status=UserMilestoneStatus.pending,
            )
            db.add(user_milestone)
            user_project.user_milestones.append(user_milestone)
            learner_by_order[row.order_index] = learner
            added += 1
        else:
            _copy_catalog_milestone(learner, row, concept_ids)
            _replace_concept_links(db, learner, concept_ids)
            updated += 1

    removed = 0
    extras = [
        milestone
        for order, milestone in learner_by_order.items()
        if order > freeze_at and order not in catalog_orders
    ]
    for milestone in extras:
        db.query(MilestoneConcept).filter(MilestoneConcept.milestone_id == milestone.id).delete(
            synchronize_session=False
        )
        db.query(UserMilestone).filter(UserMilestone.milestone_id == milestone.id).delete(
            synchronize_session=False
        )
        db.delete(milestone)
        removed += 1

    db.flush()
    db.expire(user_project, ["user_milestones"])
    curriculum_graph.ensure_learner_concept_states(db, user_project)
    return {
        "enrollment_id": user_project.enrollment_id,
        "user_project_id": user_project.id,
        "status": "applied",
        "reason": None,
        "freeze_order": freeze_at,
        "milestones_updated": updated,
        "milestones_added": added,
        "milestones_removed": removed,
    }


def apply_catalog_to_enrollments(db: Session, project_id: int) -> dict[str, object]:
    """Push new catalog work onto enrollments that have not started it.

    Completed and in-progress milestones are left alone. Finished courses are
    skipped so a new trailing milestone cannot reopen them.
    """
    project = db.get(Project, project_id)
    if project is None:
        raise GraphValidationError([f"Project {project_id} not found"])
    catalog = curriculum_graph.catalog_milestones(db, project_id)
    user_projects = (
        db.query(UserProject)
        .options(selectinload(UserProject.user_milestones).selectinload(UserMilestone.milestone))
        .filter(UserProject.project_id == project_id)
        .all()
    )
    results = [_apply_catalog_to_user_project(db, row, catalog) for row in user_projects]
    return {
        "project_id": project_id,
        "applied": sum(1 for row in results if row["status"] == "applied"),
        "skipped": sum(1 for row in results if row["status"] == "skipped"),
        "results": results,
    }
