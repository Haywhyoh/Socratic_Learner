"""Import all models so Alembic and metadata see them."""

from app.db.base import Base
from app.models.coach import (
    HintReveal,
    MentorSession,
    MentorTurn,
    MilestoneReview,
)
from app.models.concept import ConceptQuestion, ConceptSession, ConceptTurn
from app.models.course import Course, CourseOption
from app.models.curriculum import Concept, ConceptDependency, MilestoneConcept
from app.models.enrollment import Enrollment
from app.models.learning_state import (
    ConceptState,
    KnowledgeGap,
    ProjectDefense,
    Reflection,
    ResearchRecord,
    RetrievalCheck,
)
from app.models.project import Milestone, Project, UserMilestone, UserProject
from app.models.sandbox import SandboxWorkspace
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Course",
    "CourseOption",
    "ConceptQuestion",
    "ConceptSession",
    "ConceptTurn",
    "Enrollment",
    "Project",
    "Milestone",
    "UserProject",
    "UserMilestone",
    "SandboxWorkspace",
    "Concept",
    "ConceptDependency",
    "MilestoneConcept",
    "ConceptState",
    "KnowledgeGap",
    "ResearchRecord",
    "Reflection",
    "ProjectDefense",
    "RetrievalCheck",
    "MentorSession",
    "MentorTurn",
    "HintReveal",
    "MilestoneReview",
]
