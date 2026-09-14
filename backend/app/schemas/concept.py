from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.concept import ConceptSessionStatus, ConceptTurnRole


class ConceptTurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: ConceptTurnRole
    content: str
    created_at: datetime


class ConceptSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enrollment_id: int
    question_text: str | None
    status: ConceptSessionStatus
    created_at: datetime
    turns: list[ConceptTurnRead] = []
