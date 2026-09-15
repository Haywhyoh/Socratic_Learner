from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.coach import MentorSessionStatus, MentorTurnRole, MilestoneReviewVerdict
from app.models.learning_state import ConceptStatus, DefenseVerdict, RetrievalCheckStatus


class CoachStartRequest(BaseModel):
    answers: list[dict[str, Any]] = Field(default_factory=list)


class CoachMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class ResearchRequest(BaseModel):
    question: str = ""
    sources: list[Any] = Field(default_factory=list)
    learner_notes: str = ""
    learner_summary: str = ""
    remaining_questions: str = ""


class ExplainRequest(BaseModel):
    answer: str = Field(min_length=1)


class SkipDiagnosticRequest(BaseModel):
    answers: list[str] = Field(min_length=1)


class ReflectionRequest(BaseModel):
    answers: dict[str, str]


class ReviewAnswerRequest(BaseModel):
    answers: list[str] = Field(min_length=1)


class DefenseAnswerRequest(BaseModel):
    answers: list[str] = Field(min_length=1)


class RetrievalAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


class ResourceRead(BaseModel):
    title: str
    url: str = ""


class MentorTurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MentorTurnRole
    content: str
    created_at: datetime


class IdentifiedGapRead(BaseModel):
    concept: str
    confidence: float = 0.0


class MentorContractRead(BaseModel):
    intent: str = "MENTOR"
    action: str = "ASK_QUESTION"
    message: str = ""
    diagnostic_concept: str | None = None
    identified_gap: IdentifiedGapRead | None = None
    hint_level: int = 0
    should_unlock: bool = False
    next_state: str = ""


class ConceptRead(BaseModel):
    id: str = ""
    title: str = ""
    category: str = ""
    description: str = ""
    learning_objectives: list[str] = []
    misconceptions: list[str] = []
    diagnostic_questions: list[str] = []
    research_questions: list[str] = []
    resources: list[ResourceRead] = []
    hints: list[str] = []
    mastery_requirements: dict[str, Any] = {}


class LearnerStateRead(BaseModel):
    user_project_id: int | None = None
    concept_id: str | None = None
    status: ConceptStatus | str | None = None
    evidence: dict[str, Any] = {}
    attempt_count: int = 0
    hints_used: int = 0
    hint_level: int = -1
    last_explanation: str = ""
    milestone_id: int | None = None
    user_milestone_id: int | None = None


class GraphConceptRead(BaseModel):
    id: str
    title: str
    category: str = ""
    status: str
    evidence: dict[str, Any] = {}


class GraphMilestoneRead(BaseModel):
    user_milestone_id: int
    milestone_id: int
    title: str
    order_index: int
    status: str
    description: str = ""
    success_criteria: str = ""
    concepts: list[GraphConceptRead] = []


class KnowledgeGapRead(BaseModel):
    id: int | None = None
    concept: str
    status: str = "blocked"
    suspected_gaps: list[IdentifiedGapRead] = []


class RetrievalCheckRead(BaseModel):
    id: int
    concept_id: str
    scheduled_for: str
    prompt: str = ""
    status: RetrievalCheckStatus | str = RetrievalCheckStatus.pending
    learner_response: str = ""


class GraphRead(BaseModel):
    user_project_id: int
    project_id: int
    current_milestone_id: int | None = None
    current_user_milestone_id: int | None = None
    current_concept_id: str | None = None
    concept_state: str | None = None
    project_complete: bool = False
    milestones: list[GraphMilestoneRead] = []
    known_gaps: list[KnowledgeGapRead] = []
    due_retrieval_checks: list[RetrievalCheckRead] = []


class CoachMessageResponse(BaseModel):
    intent: str
    action: str = "ASK_QUESTION"
    reply: str
    hint_level: int | None = None
    hint_blocked_reason: str | None = None
    policy_flags: list[str] = []
    cards: list[dict[str, Any]] = []
    turns: list[MentorTurnRead] = []
    current_question: str | None = None
    answer_status: str | None = None
    push_back: str | None = None
    learner_state: LearnerStateRead | None = None
    contract: MentorContractRead | None = None
    concept: ConceptRead | None = None
    position: dict[str, Any] = {}


class CoachStartResponse(BaseModel):
    status: MentorSessionStatus | str
    user_project_id: int
    session_id: int
    milestone_id: int | None = None
    assessment_questions: list[dict[str, Any]] = []
    roadmap: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    reply: str | None = None
    current_question: str | None = None
    answer_status: str | None = None
    resumed: bool = False
    learner_state: LearnerStateRead | None = None
    contract: MentorContractRead | None = None
    concept: ConceptRead | None = None
    position: dict[str, Any] = {}
    graph: GraphRead | None = None


class ReviewDimensionRead(BaseModel):
    rating: str
    notes: str = ""


class UnderstandingAnswerRead(BaseModel):
    question: str
    answer: str
    passed: bool
    feedback: str | None = None


class MilestoneReviewRead(BaseModel):
    id: int
    user_milestone_id: int
    verdict: MilestoneReviewVerdict
    dimensions: dict[str, ReviewDimensionRead] = {}
    summary: str = ""
    understanding_questions: list[str] = []
    understanding_answers: list[UnderstandingAnswerRead] = []
    attempts: int = 0
    created_at: datetime
    updated_at: datetime


class ResearchRecordRead(BaseModel):
    id: int
    concept_id: str
    question: str = ""
    sources: list[Any] = []
    learner_notes: str = ""
    learner_summary: str = ""
    remaining_questions: str = ""


class ReflectionRead(BaseModel):
    id: int
    user_milestone_id: int
    answers: dict[str, Any] = {}


class ExplanationResultRead(BaseModel):
    passed: bool
    feedback: Any = None
    status: str
    evidence: dict[str, Any] = {}


class SkipResultRead(BaseModel):
    passed: bool
    status: str
    concept_id: str


class ProjectDefenseRead(BaseModel):
    id: int
    user_project_id: int
    questions: list[Any] = []
    answers: list[Any] = []
    verdict: DefenseVerdict | str
    summary: str = ""
    attempts: int = 0
