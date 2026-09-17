"""Public admin APIs for catalog knowledge graphs.

Auth/roles are deferred so the dashboard can be tested without a login.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.graph_author import GraphAuthorError, generate_concept_draft, generate_graph_draft
from app.agents.llm import LLMConfigurationError, get_coach_llm
from app.db.session import get_db
from app.schemas.admin import (
    CatalogGraphRead,
    ConceptGenerateRequest,
    ConceptGraphSpec,
    GraphGenerateJob,
    GraphGenerateRequest,
    GraphPayload,
    GraphSummary,
)
from app.services import graph_jobs
from app.services.curriculum_authoring import GraphValidationError, get_graph, list_graphs, publish_graph
from app.services.runtime import supported_languages

# TODO: gate these routes with an admin role once users have roles.
router = APIRouter(prefix="/admin", tags=["admin"])


def _http_from_validation(exc: GraphValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors)


@router.get("/languages")
def admin_list_languages() -> list[dict[str, str]]:
    return supported_languages()


@router.get("/graphs", response_model=list[GraphSummary])
def admin_list_graphs(db: Session = Depends(get_db)) -> list[GraphSummary]:
    return [GraphSummary.model_validate(item) for item in list_graphs(db)]


@router.get("/graphs/{project_id}", response_model=CatalogGraphRead)
def admin_get_graph(project_id: int, db: Session = Depends(get_db)) -> CatalogGraphRead:
    try:
        return CatalogGraphRead.model_validate(get_graph(db, project_id))
    except GraphValidationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.errors) from exc


@router.post("/graphs/generate", response_model=GraphPayload)
def admin_generate_graph(body: GraphGenerateRequest) -> GraphPayload:
    try:
        draft = generate_graph_draft(
            topic=body.topic,
            language=body.language,
            slug=body.slug,
            audience=body.audience,
            constraints=body.constraints,
            capstone=body.capstone,
            difficulty=body.difficulty,
            course_name=body.course_name,
            track_kind=body.track_kind,
            project_brief=body.project_brief,
            include_concepts=list(body.include_concepts or []),
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GraphValidationError as exc:
        raise _http_from_validation(exc) from exc
    except GraphAuthorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return GraphPayload.model_validate(draft)


@router.post(
    "/graphs/generate/jobs",
    response_model=GraphGenerateJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def admin_start_generate_graph(body: GraphGenerateRequest) -> GraphGenerateJob:
    try:
        get_coach_llm()
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    job = graph_jobs.create_job(body.model_dump())
    graph_jobs.start_job(job["job_id"])
    return GraphGenerateJob.model_validate(job)


@router.get("/graphs/generate/jobs/{job_id}", response_model=GraphGenerateJob)
def admin_get_generate_graph(job_id: str) -> GraphGenerateJob:
    try:
        job = graph_jobs.get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generate job not found") from exc
    return GraphGenerateJob.model_validate(job)


@router.post("/graphs/concepts/generate", response_model=ConceptGraphSpec)
def admin_generate_concept(body: ConceptGenerateRequest) -> ConceptGraphSpec:
    try:
        draft = generate_concept_draft(
            concept=body.concept,
            language=body.language,
            project_title=body.project_title,
            slug=body.slug,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except GraphAuthorError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ConceptGraphSpec.model_validate(draft)


@router.post("/graphs", response_model=CatalogGraphRead, status_code=status.HTTP_201_CREATED)
def admin_publish_graph(body: GraphPayload, db: Session = Depends(get_db)) -> CatalogGraphRead:
    try:
        graph = publish_graph(db, body.model_dump())
        db.commit()
    except GraphValidationError as exc:
        db.rollback()
        raise _http_from_validation(exc) from exc
    except Exception:
        db.rollback()
        raise
    return CatalogGraphRead.model_validate(graph)


@router.put("/graphs/{project_id}", response_model=CatalogGraphRead)
def admin_update_graph(
    project_id: int, body: GraphPayload, db: Session = Depends(get_db)
) -> CatalogGraphRead:
    try:
        graph = publish_graph(db, body.model_dump(), project_id=project_id)
        db.commit()
    except GraphValidationError as exc:
        db.rollback()
        detail = exc.errors
        code = (
            status.HTTP_404_NOT_FOUND
            if any("not found" in item.lower() for item in detail)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=detail) from exc
    except Exception:
        db.rollback()
        raise
    return CatalogGraphRead.model_validate(graph)
