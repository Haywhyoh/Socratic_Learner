"""Import all models so Alembic and metadata see them."""

from app.db.base import Base
from app.models.concept import ConceptQuestion, ConceptSession, ConceptTurn
from app.models.course import Course, CourseOption
from app.models.enrollment import Enrollment
from app.models.project import Milestone, Project, UserMilestone, UserProject
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Course",
    "CourseOption",
    "Enrollment",
    "Project",
    "Milestone",
    "UserProject",
    "UserMilestone",
    "ConceptQuestion",
    "ConceptSession",
    "ConceptTurn",
]
