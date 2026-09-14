"""Per-learner curriculum generation.

A ``Project`` carries a shared catalog outline (seeded milestones with
``user_project_id IS NULL``) plus reference metadata (objective, skills,
concepts, constraints, tests). The moment a learner is assigned that project,
we generate their own milestone sequence — by default this asks the
configured LLM to tailor a curriculum to the project and language/framework;
without a configured model it deterministically clones the catalog outline so
behavior stays predictable in tests and offline setups.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.llm import get_coach_llm
from app.models.course import CourseOption
from app.models.project import Milestone, Project, UserMilestone, UserMilestoneStatus, UserProject


def _catalog_outline(db: Session, project_id: int) -> list[dict[str, object]]:
    rows = (
        db.query(Milestone)
        .filter(Milestone.project_id == project_id, Milestone.user_project_id.is_(None))
        .order_by(Milestone.order_index)
        .all()
    )
    return [
        {
            "title": row.title,
            "description": row.description,
            "instructions": row.instructions,
            "success_criteria": row.success_criteria,
            "concepts": list(row.concepts or []),
            "questions": list(row.questions or []),
        }
        for row in rows
    ]


def generate_milestones_for_user_project(
    db: Session,
    user_project: UserProject,
    project: Project,
) -> list[Milestone]:
    """Generate (or clone) this learner's milestone sequence and create the

    matching ``UserMilestone`` progress rows. Must run inside the same
    transaction as the enrollment; caller commits.
    """
    language = db.get(CourseOption, project.primary_option_id)
    framework = db.get(CourseOption, project.secondary_option_id)
    catalog = _catalog_outline(db, project.id)

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
            generated=True,
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

    for milestone in milestones:
        db.add(
            UserMilestone(
                user_project_id=user_project.id,
                milestone_id=milestone.id,
                status=UserMilestoneStatus.pending,
            )
        )
    return milestones
