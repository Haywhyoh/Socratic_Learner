"""Generate and normalize catalog knowledge graphs for the admin dashboard."""

from __future__ import annotations

import re
from typing import Any

from app.agents.llm import LLMConfigurationError, get_coach_llm
from app.services.curriculum_authoring import (
    GraphValidationError,
    normalize_dependency,
    validate_graph_payload,
)
from app.services.runtime import (
    language_display_name,
    language_extension,
    normalize_language,
    run_argv_for_file,
    runtime_for_language,
)

HINT_DEFAULTS = (
    "What is the smallest example of this idea?",
    "Try the smallest change that would prove you understand it.",
    "Name the mechanism in one sentence.",
    "Structure: write the smallest file that shows this.",
    "Run it and point at the output that proves it.",
)

DEFAULT_MASTERY = {"explanation": True, "implementation": True}

SLUG_RE = re.compile(r"[^a-z0-9]+")


class GraphAuthorError(RuntimeError):
    """Raised when the model cannot produce a usable graph draft."""


def slugify(value: str, *, fallback: str = "track") -> str:
    slug = SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return slug or fallback


def namespaced_id(raw: str, slug: str) -> str:
    token = str(raw or "").strip().lower().replace(" ", ".")
    token = token.strip(".")
    prefix = f"{slug}."
    if not token:
        return f"{prefix}concept"
    if token.startswith(prefix):
        return token
    if "." in token:
        token = token.split(".", 1)[1] or token
    return prefix + token


def pad_hints(hints: list[Any] | None) -> list[str]:
    texts = [str(item).strip() for item in list(hints or []) if str(item).strip()]
    for default in HINT_DEFAULTS:
        if len(texts) >= 5:
            break
        texts.append(default)
    return texts[:5]


def _default_practice_task(concept_id: str, language: str, title: str) -> dict[str, Any]:
    leaf = concept_id.rsplit(".", 1)[-1].replace("-", "_") or "practice"
    ext = language_extension(language)
    filename = f"practice/{leaf}.{ext}"
    return {
        "id": leaf,
        "filename": filename,
        "prompt": f"Write the smallest file that proves you understand: {title}.",
        "run": run_argv_for_file(runtime_for_language(language), filename),
        "expect": {"exit_code": 0, "stdout_contains": []},
        "rubric": "The file runs. Do not require extra features.",
    }


def _normalize_concept(spec: dict[str, Any], slug: str, language: str) -> dict[str, Any]:
    concept_id = namespaced_id(str(spec.get("id") or spec.get("title") or "concept"), slug)
    title = str(spec.get("title") or concept_id)
    tasks = list(spec.get("practice_tasks") or [])
    if not tasks:
        tasks = [_default_practice_task(concept_id, language, title)]
    mastery = dict(spec.get("mastery_requirements") or {})
    if not mastery:
        mastery = dict(DEFAULT_MASTERY)
    resources = []
    for item in list(spec.get("resources") or []):
        if isinstance(item, dict):
            resources.append(
                {
                    "title": str(item.get("title") or "Resource"),
                    "url": str(item.get("url") or ""),
                }
            )
        elif item:
            resources.append({"title": str(item), "url": ""})
    return {
        "id": concept_id,
        "title": title,
        "category": str(spec.get("category") or "foundation"),
        "description": str(spec.get("description") or ""),
        "learning_objectives": [str(item) for item in list(spec.get("learning_objectives") or [])],
        "misconceptions": list(spec.get("misconceptions") or []),
        "diagnostic_questions": [str(item) for item in list(spec.get("diagnostic_questions") or [])],
        "research_questions": [str(item) for item in list(spec.get("research_questions") or [])],
        "resources": resources,
        "hints": pad_hints(spec.get("hints")),
        "mastery_requirements": mastery,
        "practice_tasks": tasks,
        "mentor_scripts": dict(spec.get("mentor_scripts") or {}),
    }


def _language_name(language: str) -> str:
    return language_display_name(language)


def normalize_graph_draft(
    payload: dict[str, Any],
    *,
    slug: str,
    language: str,
    topic: str = "",
    difficulty: str = "beginner",
    audience: str = "",
    constraints: list[str] | None = None,
    capstone: str = "",
) -> dict[str, Any]:
    slug = slugify(slug)
    language = normalize_language(language)
    course_in = dict(payload.get("course") or {})
    project_in = dict(payload.get("project") or {})
    raw_concepts = [dict(item) for item in list(payload.get("concepts") or [])]
    id_map: dict[str, str] = {}
    concepts: list[dict[str, Any]] = []
    used: set[str] = set()
    for spec in raw_concepts:
        original = str(spec.get("id") or spec.get("title") or "").strip()
        normalized = _normalize_concept(spec, slug, language)
        concept_id = normalized["id"]
        suffix = 2
        while concept_id in used:
            concept_id = f"{normalized['id']}-{suffix}"
            suffix += 1
        normalized["id"] = concept_id
        used.add(concept_id)
        if original:
            id_map[original] = concept_id
            id_map[original.lower()] = concept_id
        id_map[concept_id] = concept_id
        concepts.append(normalized)

    def remap(raw: str) -> str:
        key = str(raw or "").strip()
        if key in id_map:
            return id_map[key]
        namespaced = namespaced_id(key, slug)
        return id_map.get(namespaced, namespaced)

    raw_deps = list(payload.get("dependencies") or [])
    dependencies: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    id_set = {spec["id"] for spec in concepts}
    for item in raw_deps:
        try:
            concept_id, requires, reason = normalize_dependency(item)
        except GraphValidationError:
            continue
        concept_id = remap(concept_id)
        requires = remap(requires)
        if concept_id not in id_set or requires not in id_set or concept_id == requires:
            continue
        key = (concept_id, requires)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        dependencies.append(
            {
                "concept_id": concept_id,
                "requires_concept_id": requires,
                "reason": reason or f"{concept_id} builds on {requires}.",
            }
        )

    milestones: list[dict[str, Any]] = []
    for index, spec in enumerate(list(payload.get("milestones") or []), start=1):
        milestone = dict(spec)
        mapped = []
        for cid in list(milestone.get("concepts") or []):
            remapped = remap(str(cid))
            if remapped in id_set and remapped not in mapped:
                mapped.append(remapped)
        milestone["concepts"] = mapped
        milestone["title"] = str(milestone.get("title") or f"Milestone {index}")
        milestone["description"] = str(milestone.get("description") or "")
        milestone["instructions"] = str(milestone.get("instructions") or "")
        milestone["success_criteria"] = str(milestone.get("success_criteria") or "")
        milestone["questions"] = [str(q) for q in list(milestone.get("questions") or [])]
        milestones.append(milestone)

    if not milestones and concepts:
        milestones = [
            {
                "title": "Learn the track",
                "description": topic or "Work through the generated concepts.",
                "instructions": "Complete each concept in graph order.",
                "success_criteria": "Every concept has explanation and implementation evidence.",
                "concepts": [spec["id"] for spec in concepts],
                "questions": [],
            }
        ]

    validate_graph_payload(concepts, dependencies, milestones)

    lang_name = _language_name(language)
    course_name = str(course_in.get("name") or topic or slug).strip() or lang_name
    primary_slug = str(course_in.get("primary_slug") or language)
    secondary_slug = slugify(str(course_in.get("secondary_slug") or "fundamentals"), fallback="fundamentals")
    title = str(project_in.get("title") or f"Learn {course_name}").strip()
    runtime = {**runtime_for_language(language), **dict(project_in.get("runtime") or {})}
    runtime["language"] = language
    difficulty_value = str(project_in.get("difficulty") or difficulty or "beginner").lower()
    if difficulty_value not in {"beginner", "intermediate", "advanced"}:
        difficulty_value = "beginner"
    constraint_list = list(project_in.get("constraints") or constraints or [])
    if capstone and capstone not in constraint_list:
        constraint_list = list(constraint_list)

    return {
        "course": {
            "slug": slug,
            "name": course_name,
            "description": str(course_in.get("description") or topic or f"Learn {course_name}."),
            "primary_label": str(course_in.get("primary_label") or "Language"),
            "secondary_label": str(course_in.get("secondary_label") or "Track"),
            "primary_slug": primary_slug,
            "primary_name": str(course_in.get("primary_name") or lang_name),
            "secondary_slug": secondary_slug,
            "secondary_name": str(course_in.get("secondary_name") or topic or "Fundamentals"),
        },
        "project": {
            "title": title,
            "description": str(project_in.get("description") or topic or title),
            "objective": str(project_in.get("objective") or f"Learn {course_name} through a deterministic knowledge graph."),
            "difficulty": difficulty_value,
            "expected_outcome": str(project_in.get("expected_outcome") or capstone or f"A small {lang_name} project you can defend."),
            "prerequisites": list(project_in.get("prerequisites") or ([audience] if audience else [])),
            "skills": list(project_in.get("skills") or []),
            "constraints": constraint_list,
            "tests": list(project_in.get("tests") or []),
            "evaluation_criteria": list(project_in.get("evaluation_criteria") or []),
            "extension_challenges": list(project_in.get("extension_challenges") or []),
            "recommended_resources": list(project_in.get("recommended_resources") or []),
            "runtime": runtime,
        },
        "concepts": concepts,
        "dependencies": dependencies,
        "milestones": milestones,
    }


def generate_graph_draft(
    *,
    topic: str,
    language: str,
    slug: str,
    audience: str = "",
    constraints: list[str] | None = None,
    capstone: str = "",
    difficulty: str = "beginner",
    course_name: str = "",
) -> dict[str, Any]:
    llm = get_coach_llm()
    try:
        raw = llm.generate_knowledge_graph(
            topic=topic,
            language=language,
            slug=slugify(slug),
            audience=audience,
            constraints=list(constraints or []),
            capstone=capstone,
            difficulty=difficulty,
            course_name=course_name or topic,
        )
    except LLMConfigurationError:
        raise
    except Exception as exc:
        raise GraphAuthorError(f"Failed to generate knowledge graph: {exc}") from exc
    if not isinstance(raw, dict):
        raise GraphAuthorError("Model did not return a graph object")
    try:
        return normalize_graph_draft(
            raw,
            slug=slug,
            language=language,
            topic=topic,
            difficulty=difficulty,
            audience=audience,
            constraints=list(constraints or []),
            capstone=capstone,
        )
    except GraphValidationError:
        raise
    except Exception as exc:
        raise GraphAuthorError(f"Generated graph was not usable: {exc}") from exc


def generate_concept_draft(
    *,
    concept: dict[str, Any],
    language: str,
    project_title: str,
    slug: str,
) -> dict[str, Any]:
    llm = get_coach_llm()
    try:
        raw = llm.generate_concept_content(
            concept=concept,
            language=language,
            project_title=project_title,
        )
    except LLMConfigurationError:
        raise
    except Exception as exc:
        raise GraphAuthorError(f"Failed to generate concept: {exc}") from exc
    merged = {**concept, **(raw if isinstance(raw, dict) else {})}
    merged["id"] = concept.get("id") or merged.get("id")
    merged["title"] = concept.get("title") or merged.get("title")
    return _normalize_concept(merged, slugify(slug), language)
