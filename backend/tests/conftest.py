from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.course import Course, CourseOption
from app.models.project import Milestone, Project, ProjectDifficulty
from app.models.user import User
from app.seed import seed

engine = create_engine(settings.test_database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables() -> Generator[None, None, None]:
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(db: Session) -> Session:
    seed(db)
    return db


@pytest.fixture
def user(db: Session) -> User:
    user = User(email="learner@example.com", hashed_password=hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": user.email, "password": "password123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_course_path(db: Session, *, with_project: bool = True) -> dict[str, int]:
    course = Course(
        slug="software-engineering",
        name="Software Engineering",
        description="SE",
        primary_label="Language",
        secondary_label="Framework",
    )
    db.add(course)
    db.flush()
    primary = CourseOption(course_id=course.id, name="Python", slug="python")
    db.add(primary)
    db.flush()
    secondary = CourseOption(
        course_id=course.id, name="FastAPI", slug="fastapi", parent_id=primary.id
    )
    db.add(secondary)
    db.flush()

    project_id = None
    if with_project:
        project = Project(
            title="Task Tracker API",
            description="Build an API",
            objective="Ship a small task-tracking backend.",
            difficulty=ProjectDifficulty.beginner,
            expected_outcome="Auth-aware task CRUD with tests.",
            prerequisites=["Python", "HTTP basics"],
            skills=["routing", "auth"],
            concepts=["ownership isolation"],
            constraints=["No frontend"],
            tests=["Happy-path create/list/complete"],
            evaluation_criteria=["Milestones complete"],
            extension_challenges=["Due dates"],
            recommended_resources=[{"title": "FastAPI docs", "url": "https://fastapi.tiangolo.com"}],
            course_id=course.id,
            primary_option_id=primary.id,
            secondary_option_id=secondary.id,
            is_active=True,
        )
        db.add(project)
        db.flush()
        for index, title in enumerate(["Scaffold", "CRUD", "Auth"], start=1):
            db.add(
                Milestone(
                    project_id=project.id,
                    title=title,
                    description=f"{title} description",
                    instructions=f"{title} instructions",
                    order_index=index,
                    success_criteria=f"{title} done",
                    concepts=[title.lower()],
                )
            )
        project_id = project.id
    db.commit()
    return {
        "course_id": course.id,
        "primary_option_id": primary.id,
        "secondary_option_id": secondary.id,
        "project_id": project_id or 0,
    }
