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
from app.models.project import Milestone, Project, ProjectCurriculumMode, ProjectDifficulty
from app.models.user import User
from app.seed import seed
from app.services.sandbox_runner import FakeSandboxRunner, RunResult, set_sandbox_runner

engine = create_engine(settings.test_database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def stub_coach_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.llm import StubCoachLLM

    monkeypatch.setattr("app.services.coach.get_coach_llm", StubCoachLLM)
    monkeypatch.setattr("app.services.curriculum.get_coach_llm", StubCoachLLM)
    monkeypatch.setattr("app.agents.llm.get_coach_llm", StubCoachLLM)


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
def workspace_tmp(tmp_path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "workspaces"
    monkeypatch.setattr("app.core.config.settings.sandbox_workspaces_root", str(root))
    monkeypatch.setattr("app.services.sandbox.settings.sandbox_workspaces_root", str(root))
    return root


@pytest.fixture
def fake_runner() -> Generator[FakeSandboxRunner, None, None]:
    runner = FakeSandboxRunner(
        RunResult(exit_code=0, stdout="2 passed in 0.01s\n", stderr="")
    )
    set_sandbox_runner(runner)
    yield runner
    set_sandbox_runner(None)


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
        slug="javascript",
        name="JavaScript",
        description="JS",
        primary_label="Language",
        secondary_label="Track",
    )
    db.add(course)
    db.flush()
    primary = CourseOption(course_id=course.id, name="JavaScript", slug="javascript")
    db.add(primary)
    db.flush()
    secondary = CourseOption(
        course_id=course.id,
        name="Node.js core (no framework)",
        slug="node-core",
        parent_id=primary.id,
    )
    db.add(secondary)
    db.flush()

    project_id = None
    if with_project:
        project = Project(
            title="Build a Simple Backend Framework in JavaScript",
            description="Build a framework",
            objective="Ship a small backend framework.",
            difficulty=ProjectDifficulty.intermediate,
            expected_outcome="A from-scratch Node.js framework.",
            prerequisites=["JavaScript"],
            skills=["routing"],
            concepts=[],
            constraints=["No Express"],
            tests=["GET route works"],
            evaluation_criteria=["Milestones complete"],
            extension_challenges=["Async middleware"],
            recommended_resources=[{"title": "Node http", "url": "https://nodejs.org/api/http.html"}],
            curriculum_mode=ProjectCurriculumMode.deterministic,
            course_id=course.id,
            primary_option_id=primary.id,
            secondary_option_id=secondary.id,
            is_active=True,
        )
        db.add(project)
        db.flush()
        for index, title in enumerate(["Scaffold", "CRUD", "Auth"], start=1):
            if title == "Scaffold":
                instructions = (
                    "What to do:\n"
                    "1. Create a clean project layout (app package, settings, entrypoint).\n"
                    "2. Add a GET /health endpoint that returns JSON like {\"status\": \"ok\"}.\n"
                    "3. Wire dependency management and a README with run steps.\n"
                    "4. Confirm uvicorn starts locally without import errors."
                )
            else:
                instructions = (
                    f"What to do:\n"
                    f"1. Implement the core of {title}.\n"
                    f"2. Add tests that prove {title} works.\n"
                )
            db.add(
                Milestone(
                    project_id=project.id,
                    title=title,
                    description=f"{title} description",
                    instructions=instructions,
                    order_index=index,
                    success_criteria=f"{title} done",
                    concepts=[title.lower()],
                    questions=[
                        f"What is the goal of {title}?",
                        f"How will you verify {title} works?",
                    ],
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
