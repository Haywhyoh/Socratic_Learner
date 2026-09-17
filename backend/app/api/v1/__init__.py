from fastapi import APIRouter

from app.api.v1 import admin, auth, catalog, coach, concept, enrollments, projects, sandbox

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(enrollments.router)
api_router.include_router(projects.router)
api_router.include_router(concept.router)
api_router.include_router(coach.router)
api_router.include_router(sandbox.router)
api_router.include_router(admin.router)
