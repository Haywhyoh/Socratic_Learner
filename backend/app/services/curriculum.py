"""Per-learner curriculum materialization.

Graph-driven (``curriculum_mode=deterministic``) projects clone the seeded
catalog outline 1:1 and initialize ConceptState rows. The AI mentor never
invents or reorders that graph.

``ai_generated`` is the legacy per-learner LLM-tailored path, kept as a
fallback for any project that still opts into it.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

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


def _clone_concept_links(
    db: Session, catalog_milestone_id: int | None, learner_milestone: Milestone
) -> None:
    if catalog_milestone_id is None:
        for order, concept_id in enumerate(list(learner_milestone.concepts or [])):
            db.add(
                MilestoneConcept(
                    milestone_id=learner_milestone.id,
                    concept_id=str(concept_id),
                    order_index=order,
                )
            )
        return
    links = (
        db.query(MilestoneConcept)
        .filter(MilestoneConcept.milestone_id == catalog_milestone_id)
        .order_by(MilestoneConcept.order_index)
        .all()
    )
    for link in links:
        db.add(
            MilestoneConcept(
                milestone_id=learner_milestone.id,
                concept_id=link.concept_id,
                order_index=link.order_index,
            )
        )


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
