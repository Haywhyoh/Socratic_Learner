from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.concept import ConceptSessionRead
from app.services import learning as learning_service

router = APIRouter(prefix="/concept-sessions", tags=["concept"])


@router.get("/{session_id}", response_model=ConceptSessionRead)
def get_concept_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConceptSessionRead:
    return learning_service.get_concept_session(db, current_user, session_id)
