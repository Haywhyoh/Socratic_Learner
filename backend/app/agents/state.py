from typing import Any, NotRequired, TypedDict


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


class IdentifiedGap(TypedDict):
    concept: str
    confidence: float


class MentorContract(TypedDict, total=False):
    intent: str
    action: str
    message: str
    diagnostic_concept: str | None
    identified_gap: IdentifiedGap | None
    hint_level: int
    should_unlock: bool
    next_state: str


class MentorState(TypedDict, total=False):
    project: str
    project_title: str
    current_milestone: str
    current_milestone_title: str
    current_concept: str
    concept_title: str
    concept_description: str
    concept_state: str
    prerequisites: dict[str, str]
    known_gaps: list[dict]
    attempt_count: int
    hints_used: int
    tests: dict[str, int]
    learner_last_explanation: str
    allowed_ai_behavior: list[str]
    later_concepts: list[str]
    resources: list[dict[str, str]]
    diagnostic_questions: list[str]
    research_questions: list[str]
    misconceptions: list[Any]
    hints: list[str]
    learning_objectives: list[str]
    needs_build: bool
    gap_reason: str
    learner_message: str
    diagnostic_answers: NotRequired[list[Any]]
    misconception_branch: NotRequired[str | None]
    identified_misconception: NotRequired[dict[str, Any] | None]
    intent: str
    effort: EffortSignals
    hint_level: int
    hint_blocked_reason: NotRequired[str | None]
    reply: str
    contract: MentorContract
    policy_flags: list[str]
    next_state: str
    should_unlock: bool
    identified_gap: IdentifiedGap | None
    tests_summary: str
    awaiting_reflection: bool
    project_complete: bool


class CoachState(TypedDict, total=False):
    mode: str
    user_project_id: int
    milestone_id: int | None
    project_title: str
    milestone_title: str
    constraints: list[str]
    success_criteria: str
    milestone_instructions: str
    milestone_questions: list[str]
    question_index: int
    questions_passed: int
    question_attempts: int
    gap_question: str | None
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
    build_step_index: int
    build_steps: list[str]
    hint_blocked_reason: NotRequired[str | None]
    policy_flags: list[str]
    eval_result: EvalResult
