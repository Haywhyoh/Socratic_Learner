from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphGenerateRequest(BaseModel):
    topic: str
    language: str = "python"
    slug: str
    audience: str = ""
    constraints: list[str] = Field(default_factory=list)
    capstone: str = ""
    difficulty: str = "beginner"
    course_name: str = ""
    track_kind: Literal["language", "project"] = "language"
    project_brief: str = ""
    include_concepts: list[str] = Field(default_factory=list)


class ConceptGenerateRequest(BaseModel):
    concept: dict[str, Any]
    language: str = "python"
    project_title: str = ""
    slug: str = "track"


class CoursePathSpec(BaseModel):
    id: int | None = None
    slug: str
    name: str
    description: str = ""
    primary_label: str = "Language"
    secondary_label: str = "Track"
    primary_slug: str
    primary_name: str
    secondary_slug: str
    secondary_name: str


class ProjectGraphSpec(BaseModel):
    title: str
    description: str = ""
    objective: str = ""
    difficulty: str = "beginner"
    expected_outcome: str = ""
    prerequisites: list[Any] = Field(default_factory=list)
    skills: list[Any] = Field(default_factory=list)
    constraints: list[Any] = Field(default_factory=list)
    tests: list[Any] = Field(default_factory=list)
    evaluation_criteria: list[Any] = Field(default_factory=list)
    extension_challenges: list[Any] = Field(default_factory=list)
    recommended_resources: list[Any] = Field(default_factory=list)
    runtime: dict[str, Any] = Field(default_factory=dict)


class ConceptGraphSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    category: str = "foundation"
    description: str = ""
    learning_objectives: list[Any] = Field(default_factory=list)
    misconceptions: list[Any] = Field(default_factory=list)
    diagnostic_questions: list[Any] = Field(default_factory=list)
    research_questions: list[Any] = Field(default_factory=list)
    resources: list[Any] = Field(default_factory=list)
    hints: list[Any] = Field(default_factory=list)
    mastery_requirements: dict[str, Any] = Field(default_factory=dict)
    practice_tasks: list[Any] = Field(default_factory=list)
    mentor_scripts: dict[str, Any] = Field(default_factory=dict)


class DependencyGraphSpec(BaseModel):
    concept_id: str
    requires_concept_id: str
    reason: str = ""


class MilestoneGraphSpec(BaseModel):
    id: int | None = None
    title: str
    description: str = ""
    instructions: str = ""
    success_criteria: str = ""
    order_index: int | None = None
    concepts: list[str] = Field(default_factory=list)
    questions: list[Any] = Field(default_factory=list)


class GraphPayload(BaseModel):
    course: CoursePathSpec
    project: ProjectGraphSpec
    concepts: list[ConceptGraphSpec]
    dependencies: list[DependencyGraphSpec] = Field(default_factory=list)
    milestones: list[MilestoneGraphSpec] = Field(default_factory=list)


class GraphGenerateJob(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    error: str | None = None
    graph: GraphPayload | None = None


class CatalogGraphRead(GraphPayload):
    project_id: int


class GraphSummary(BaseModel):
    project_id: int
    title: str
    description: str
    difficulty: str
    course_id: int
    course_slug: str
    course_name: str
    language: str
    concept_count: int
    edge_count: int
    milestone_count: int
