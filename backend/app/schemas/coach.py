from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.coach import ConceptMastery, MentorSessionStatus, MentorTurnRole, TeachingFlag


class AssessmentAnswer(BaseModel):
    concept: str
    mastery: ConceptMastery


class CoachStartRequest(BaseModel):
    answers: list[AssessmentAnswer] = Field(default_factory=list)


class CoachMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class CheckpointRequest(BaseModel):
    answer: str = Field(min_length=1)


class AssessmentQuestion(BaseModel):
    concept: str
    prompt: str


class ResourceRead(BaseModel):
    title: str
    url: str = ""


class ConceptCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_project_id: int
    milestone_id: int
    name: str
    why_it_matters: str
    research_questions: list[str] = []
    resources: list[ResourceRead] = []
    checkpoint: str
    explanation: str


class RoadmapConceptRead(BaseModel):
    name: str
    teaching: TeachingFlag
    mastery: ConceptMastery


class RoadmapMilestoneRead(BaseModel):
    milestone_id: int
    title: str
    order_index: int
    concepts: list[RoadmapConceptRead] = []


class MentorTurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MentorTurnRole
    content: str
    created_at: datetime


class HintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_milestone_id: int
    level: int
    content: str
    created_at: datetime


class CheckpointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    answer: str
    passed: bool
    created_at: datetime


class CoachStartResponse(BaseModel):
    status: MentorSessionStatus
    user_project_id: int
    session_id: int
    milestone_id: int | None = None
    assessment_questions: list[AssessmentQuestion] = []
    roadmap: list[RoadmapMilestoneRead] = []
    cards: list[ConceptCardRead] = []
    reply: str | None = None


class CoachMessageResponse(BaseModel):
    intent: str
    reply: str
    hint_level: int | None = None
    hint_blocked_reason: str | None = None
    policy_flags: list[str] = []
    cards: list[ConceptCardRead] = []
    turns: list[MentorTurnRead] = []
