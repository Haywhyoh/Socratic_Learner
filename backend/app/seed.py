"""Seed the catalog: JavaScript backend-framework graph plus the Python
fundamentals + CLI-notebook graph. Legacy stub courses (Task Tracker, Business,
etc.) are still removed; both real language tracks stay active. Admin-created
courses with other slugs are left alone.
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.seed_js_backend_framework import (
    CONCEPTS as JS_CONCEPTS,
    DEPENDENCIES as JS_DEPENDENCIES,
    MILESTONES as JS_MILESTONES,
    PROJECT_SPEC as JS_PROJECT,
)
from app.seed_python_fundamentals import (
    CONCEPTS as PY_CONCEPTS,
    DEPENDENCIES as PY_DEPENDENCIES,
    MILESTONES as PY_MILESTONES,
    PROJECT_SPEC as PY_PROJECT,
)
from app.services import curriculum_authoring as authoring

_ALL_CONCEPTS = list(JS_CONCEPTS) + list(PY_CONCEPTS)
_ALL_DEPENDENCIES = list(JS_DEPENDENCIES) + list(PY_DEPENDENCIES)


def seed(db) -> None:
    authoring.retire_legacy_catalog(db)
    js_course, js_primary, js_secondary = authoring.ensure_course_path(
        db,
        slug="javascript",
        name="JavaScript",
        description="Build real systems in JavaScript through deliberate, mentored practice.",
        primary_slug="javascript",
        primary_name="JavaScript",
        secondary_slug="node-core",
        secondary_name="Node.js core (no framework)",
    )
    py_course, py_primary, py_secondary = authoring.ensure_course_path(
        db,
        slug="python",
        name="Python",
        description="Learn Python through mentored practice, then build a small CLI.",
        primary_slug="python",
        primary_name="Python",
        secondary_slug="stdlib",
        secondary_name="Standard library (no web framework)",
    )
    authoring.upsert_concepts(db, _ALL_CONCEPTS)
    # Seed upserts JS/PY edges without deleting admin-authored edges on other ids.
    js_ids = {str(spec["id"]) for spec in JS_CONCEPTS}
    py_ids = {str(spec["id"]) for spec in PY_CONCEPTS}
    authoring.upsert_dependencies(
        db,
        js_ids,
        [authoring.normalize_dependency(item) for item in JS_DEPENDENCIES],
    )
    authoring.upsert_dependencies(
        db,
        py_ids,
        [authoring.normalize_dependency(item) for item in PY_DEPENDENCIES],
    )
    authoring.ensure_project(
        db,
        spec=JS_PROJECT,
        concepts=list(JS_CONCEPTS),
        milestones=list(JS_MILESTONES),
        course_id=js_course.id,
        primary_option_id=js_primary.id,
        secondary_option_id=js_secondary.id,
        match="title",
    )
    authoring.ensure_project(
        db,
        spec=PY_PROJECT,
        concepts=list(PY_CONCEPTS),
        milestones=list(PY_MILESTONES),
        course_id=py_course.id,
        primary_option_id=py_primary.id,
        secondary_option_id=py_secondary.id,
        match="title",
    )
    db.commit()
    print("Seed complete (JavaScript backend framework + Python fundamentals).")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
