from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.course import CourseOptionRead, CourseRead
from app.services import learning as learning_service

router = APIRouter(tags=["catalog"])


@router.get("/courses", response_model=list[CourseRead])
def list_courses(db: Session = Depends(get_db)) -> list[CourseRead]:
    return learning_service.list_courses(db)


@router.get("/courses/{course_id}/options", response_model=list[CourseOptionRead])
def list_primary_options(course_id: int, db: Session = Depends(get_db)) -> list[CourseOptionRead]:
    course = learning_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return learning_service.list_primary_options(db, course_id)


@router.get(
    "/courses/{course_id}/options/{option_id}/options",
    response_model=list[CourseOptionRead],
)
def list_secondary_options(
    course_id: int,
    option_id: int,
    db: Session = Depends(get_db),
) -> list[CourseOptionRead]:
    course = learning_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return learning_service.list_secondary_options(db, course_id, option_id)
