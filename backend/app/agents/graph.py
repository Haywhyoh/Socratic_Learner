from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.agents.llm import CoachLLM, StubCoachLLM
from app.agents.policies import (
    apply_assessment_answers,
    assessment_questions,
    build_roadmap,
    classify_intent,
    current_teach_concepts,
    fallback_card_reply,
    filter_specialist_reply,
    later_milestone_concepts,
    next_hint_level,
)
from app.agents.state import CoachState


def assess_node(state: CoachState) -> CoachState:
    catalog = state.get("catalog_milestones") or []
    answers = state.get("assessment_answers") or {}
    existing = state.get("knowledge_profile") or {}
    if existing:
        return {"knowledge_profile": existing, "status": "active"}
    if not answers:
        return {
            "assessment_questions": assessment_questions(catalog),
            "status": "needs_assessment",
        }
    return {
        "knowledge_profile": apply_assessment_answers(catalog, answers),
        "status": "active",
        "assessment_questions": [],
    }


def _route_after_assess(state: CoachState) -> str:
    if state.get("status") == "needs_assessment":
        return "end"
    return "plan"


def plan_node(state: CoachState) -> CoachState:
    catalog = state.get("catalog_milestones") or []
    profile = state.get("knowledge_profile") or {}
    return {"roadmap": build_roadmap(catalog, profile)}


def make_cards_node(llm: CoachLLM) -> Callable[[CoachState], CoachState]:
    def cards_node(state: CoachState) -> CoachState:
        milestone_id = state.get("milestone_id")
        if milestone_id is None:
            return {"cards": []}
        names = current_teach_concepts(
            state.get("roadmap") or [],
            milestone_id,
            state.get("knowledge_profile") or {},
        )
        title = state.get("milestone_title") or "this milestone"
        resources = state.get("resources") or []
        cards = [llm.generate_card(name, title, resources) for name in names]
        return {"cards": cards, "current_concepts": names}

    return cards_node


def route_node(state: CoachState) -> CoachState:
    return {"intent": classify_intent(state.get("learner_message") or "")}


def _pick_chat_branch(state: CoachState) -> str:
    intent = state.get("intent") or "mentor"
    if intent == "hint":
        return "hint_gate"
    if intent in {"card", "checkpoint"}:
        return "card_reply"
    return "mentor"


def make_mentor_node(llm: CoachLLM) -> Callable[[CoachState], CoachState]:
    def mentor_node(state: CoachState) -> CoachState:
        reply = llm.mentor_reply(
            milestone_title=state.get("milestone_title") or "the current milestone",
            constraints=state.get("constraints") or [],
            success_criteria=state.get("success_criteria") or "",
            current_concepts=state.get("current_concepts") or [],
            learner_message=state.get("learner_message") or "",
        )
        return {"reply": reply}

    return mentor_node


def hint_gate_node(state: CoachState) -> CoachState:
    level, reason = next_hint_level(int(state.get("hint_level", -1)), state.get("effort") or {})
    return {"hint_level": level, "hint_blocked_reason": reason}


def _after_hint_gate(state: CoachState) -> str:
    if state.get("hint_blocked_reason") == "need_effort":
        return "mentor"
    return "hint_coach"


def make_hint_node(llm: CoachLLM) -> Callable[[CoachState], CoachState]:
    def hint_node(state: CoachState) -> CoachState:
        reply = llm.hint_reply(
            int(state.get("hint_level", 0)),
            state.get("milestone_title") or "this milestone",
            state.get("current_concepts") or [],
        )
        return {"reply": reply}

    return hint_node


def card_reply_node(state: CoachState) -> CoachState:
    return {"reply": fallback_card_reply(state.get("cards") or [])}


def policy_node(state: CoachState) -> CoachState:
    reply = state.get("reply") or ""
    if state.get("hint_blocked_reason") == "need_effort":
        reply = (
            "Show genuine effort first — describe what you tried, an approach, "
            "or a checkpoint answer. I will not make the hint more specific yet.\n\n"
            + reply
        )
    filtered, flags = filter_specialist_reply(
        reply,
        later_concepts=state.get("later_concepts") or [],
        allow_code=int(state.get("hint_level", -1)) >= 3
        and state.get("intent") == "hint"
        and not state.get("hint_blocked_reason"),
    )
    catalog = state.get("catalog_milestones") or []
    milestone_id = state.get("milestone_id")
    later = list(state.get("later_concepts") or [])
    if milestone_id is not None and not later:
        later = later_milestone_concepts(catalog, milestone_id)
        filtered, extra = filter_specialist_reply(
            filtered, later_concepts=later, allow_code=False
        )
        flags.extend(extra)
    return {"reply": filtered, "policy_flags": flags}


def build_start_graph(llm: CoachLLM | None = None):
    llm = llm or StubCoachLLM()
    builder = StateGraph(CoachState)
    builder.add_node("assess", assess_node)
    builder.add_node("plan", plan_node)
    builder.add_node("cards", make_cards_node(llm))
    builder.add_edge(START, "assess")
    builder.add_conditional_edges(
        "assess",
        _route_after_assess,
        {"plan": "plan", "end": END},
    )
    builder.add_edge("plan", "cards")
    builder.add_edge("cards", END)
    return builder.compile()


def build_chat_graph(llm: CoachLLM | None = None):
    llm = llm or StubCoachLLM()
    builder = StateGraph(CoachState)
    builder.add_node("route", route_node)
    builder.add_node("mentor", make_mentor_node(llm))
    builder.add_node("hint_gate", hint_gate_node)
    builder.add_node("hint_coach", make_hint_node(llm))
    builder.add_node("card_reply", card_reply_node)
    builder.add_node("policy", policy_node)
    builder.add_edge(START, "route")
    builder.add_conditional_edges(
        "route",
        _pick_chat_branch,
        {
            "mentor": "mentor",
            "hint_gate": "hint_gate",
            "card_reply": "card_reply",
        },
    )
    builder.add_conditional_edges(
        "hint_gate",
        _after_hint_gate,
        {"mentor": "mentor", "hint_coach": "hint_coach"},
    )
    builder.add_edge("mentor", "policy")
    builder.add_edge("hint_coach", "policy")
    builder.add_edge("card_reply", "policy")
    builder.add_edge("policy", END)
    return builder.compile()
