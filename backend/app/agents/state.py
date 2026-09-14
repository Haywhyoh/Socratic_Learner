from typing import NotRequired, TypedDict


class CatalogMilestone(TypedDict):
    id: int
    title: str
    order_index: int
    concepts: list[str]
    questions: list[str]
    success_criteria: str
    description: str


class RoadmapConcept(TypedDict):
    name: str
    teaching: str
    mastery: str


class RoadmapMilestone(TypedDict):
    milestone_id: int
    title: str
    order_index: int
    concepts: list[RoadmapConcept]


class CardDraft(TypedDict):
    name: str
    why_it_matters: str
    research_questions: list[str]
    resources: list[dict[str, str]]
    checkpoint: str
    explanation: str


class EffortSignals(TypedDict):
    learner_turns_since_hint: int
    checkpoint_since_hint: bool
    attempt_message: bool
    tested_attempt: bool


class EvalResult(TypedDict):
    passed: bool
    push_back: str | None


class CoachState(TypedDict, total=False):
    mode: str
    user_project_id: int
    milestone_id: int | None
    project_title: str
    milestone_title: str
    constraints: list[str]
    success_criteria: str
    milestone_questions: list[str]
    question_index: int
    questions_passed: int
    current_question: str | None
    catalog_milestones: list[CatalogMilestone]
    knowledge_profile: dict[str, str]
    assessment_answers: dict[str, str]
    assessment_questions: list[dict[str, str]]
    roadmap: list[RoadmapMilestone]
    cards: list[CardDraft]
    resources: list[dict[str, str]]
    current_concepts: list[str]
    later_concepts: list[str]
    hint_level: int
    effort: EffortSignals
    learner_message: str
    intent: str
    reply: str
    status: str
    answer_status: str | None
    push_back: str | None
    questions_complete: bool
    hint_blocked_reason: NotRequired[str | None]
    policy_flags: list[str]
    eval_result: EvalResult
