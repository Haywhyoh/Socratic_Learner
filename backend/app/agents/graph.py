from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from app.agents.llm import CoachLLM, StubCoachLLM
from app.agents.policies import (
    MAX_QUESTION_ATTEMPTS,
    apply_assessment_answers,
    assessment_questions,
    build_roadmap,
    classify_intent,
    current_teach_concepts,
    enforce_brevity,
    fallback_card_reply,
    filter_specialist_reply,
    go_build_reply,
    later_milestone_concepts,
    next_hint_level,
    pose_question,
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


def question_node(state: CoachState) -> CoachState:
    questions = list(state.get("milestone_questions") or [])
    index = int(state.get("question_index") or 0)
    question = pose_question(questions, index)
    if question is None:
        reply = go_build_reply(
            constraints=list(state.get("constraints") or []),
            success_criteria=state.get("success_criteria") or "",
            instructions=state.get("milestone_instructions") or "",
            milestone_title=state.get("milestone_title") or "",
        )
        return {
            "reply": reply,
            "current_question": None,
            "questions_complete": True,
            "answer_status": "complete",
        }
    return {
        "reply": question,
        "current_question": question,
        "questions_complete": False,
        "answer_status": "awaiting",
    }


def route_node(state: CoachState) -> CoachState:
    return {"intent": classify_intent(state.get("learner_message") or "")}


def _pick_chat_branch(state: CoachState) -> str:
    intent = state.get("intent") or "answer"
    if intent == "hint":
        return "hint_gate"
    if intent in {"card", "checkpoint"}:
        return "card_reply"
    if intent == "guidance":
        return "guidance"
    return "evaluate"


def make_evaluate_node(llm: CoachLLM) -> Callable[[CoachState], CoachState]:
    def evaluate_node(state: CoachState) -> CoachState:
        questions = list(state.get("milestone_questions") or [])
        index = int(state.get("question_index") or 0)
        question = pose_question(questions, index)
        if question is None:
            # Past checkpoints: real mentor reply to their question (LLM when configured).
            reply = llm.mentor_reply(
                message=state.get("learner_message") or "",
                project_title=state.get("project_title") or "",
                milestone_title=state.get("milestone_title") or "",
                instructions=state.get("milestone_instructions") or "",
                constraints=list(state.get("constraints") or []),
                success_criteria=state.get("success_criteria") or "",
            )
            return {
                "reply": reply,
                "questions_complete": True,
                "answer_status": "guidance",
                "current_question": None,
            }
        result = llm.evaluate_answer(
            question=question,
            answer=state.get("learner_message") or "",
            milestone_title=state.get("milestone_title") or "",
        )
        if result.get("passed"):
            new_index = index + 1
            new_passed = int(state.get("questions_passed") or 0) + 1
            next_q = pose_question(questions, new_index)
            if next_q is None:
                reply = go_build_reply(
                    constraints=list(state.get("constraints") or []),
                    success_criteria=state.get("success_criteria") or "",
                    instructions=state.get("milestone_instructions") or "",
                    milestone_title=state.get("milestone_title") or "",
                )
                return {
                    "question_index": new_index,
                    "questions_passed": new_passed,
                    "question_attempts": 0,
                    "reply": reply,
                    "answer_status": "passed",
                    "push_back": None,
                    "questions_complete": True,
                    "current_question": None,
                    "eval_result": result,
                }
            return {
                "question_index": new_index,
                "questions_passed": new_passed,
                "question_attempts": 0,
                "reply": next_q,
                "answer_status": "passed",
                "push_back": None,
                "questions_complete": False,
                "current_question": next_q,
                "eval_result": result,
            }

        attempts = int(state.get("question_attempts") or 0) + 1
        if attempts >= MAX_QUESTION_ATTEMPTS:
            # Cap reached: don't rephrase the same question forever. Note the
            # gap and move the learner on so they can start building.
            new_index = index + 1
            next_q = pose_question(questions, new_index)
            gap_note = (
                f"Noted — moving on without a confirmed answer on '{question}'. "
                "We'll revisit this in the milestone review."
            )
            if next_q is None:
                build_reply = go_build_reply(
                    constraints=list(state.get("constraints") or []),
                    success_criteria=state.get("success_criteria") or "",
                    instructions=state.get("milestone_instructions") or "",
                    milestone_title=state.get("milestone_title") or "",
                )
                return {
                    "question_index": new_index,
                    "question_attempts": 0,
                    "gap_question": question,
                    "reply": enforce_brevity(
                        f"{gap_note} {build_reply}", max_sentences=4
                    ),
                    "answer_status": "advanced_with_gap",
                    "push_back": None,
                    "questions_complete": True,
                    "current_question": None,
                    "eval_result": result,
                }
            return {
                "question_index": new_index,
                "question_attempts": 0,
                "gap_question": question,
                "reply": enforce_brevity(f"{gap_note} Next: {next_q}", max_sentences=2),
                "answer_status": "advanced_with_gap",
                "push_back": None,
                "questions_complete": False,
                "current_question": next_q,
                "eval_result": result,
            }

        push = result.get("push_back") or "Not enough. Answer in one clear sentence."
        return {
            "question_attempts": attempts,
            "reply": enforce_brevity(str(push), max_sentences=1),
            "answer_status": "push_back",
            "push_back": push,
            "questions_complete": False,
            "current_question": question,
            "eval_result": result,
        }

    return evaluate_node


def make_guidance_node(llm: CoachLLM) -> Callable[[CoachState], CoachState]:
    def guidance_node(state: CoachState) -> CoachState:
        reply = llm.mentor_reply(
            message=state.get("learner_message") or "",
            project_title=state.get("project_title") or "",
            milestone_title=state.get("milestone_title") or "",
            instructions=state.get("milestone_instructions") or "",
            constraints=list(state.get("constraints") or []),
            success_criteria=state.get("success_criteria") or "",
        )
        question = state.get("current_question")
        if question:
            reply = f"{reply}\n\nStill answer the checkpoint first: {question}"
        return {"reply": reply, "answer_status": "guidance"}

    return guidance_node


def hint_gate_node(state: CoachState) -> CoachState:
    level, reason = next_hint_level(int(state.get("hint_level", -1)), state.get("effort") or {})
    return {"hint_level": level, "hint_blocked_reason": reason}


def _after_hint_gate(state: CoachState) -> str:
    if state.get("hint_blocked_reason") == "need_effort":
        return "policy"
    return "hint_coach"


def make_hint_node(llm: CoachLLM) -> Callable[[CoachState], CoachState]:
    def hint_node(state: CoachState) -> CoachState:
        reply = llm.hint_reply(
            int(state.get("hint_level", 0)),
            state.get("milestone_title") or "this milestone",
            state.get("current_concepts") or [],
            instructions=state.get("milestone_instructions") or "",
        )
        question = state.get("current_question")
        if question:
            reply = f"{reply} Still answer: {question}"
        return {"reply": reply, "answer_status": "hint"}

    return hint_node


def card_reply_node(state: CoachState) -> CoachState:
    return {
        "reply": fallback_card_reply(state.get("cards") or []),
        "answer_status": "card",
    }


def policy_node(state: CoachState) -> CoachState:
    reply = state.get("reply") or ""
    if state.get("hint_blocked_reason") == "need_effort":
        question = state.get("current_question") or "the current question"
        reply = (
            f"Show effort first — try a step in the editor/terminal, then ask again. "
            f"If a checkpoint is open, answer: {question}"
        )
    status = state.get("answer_status") or ""
    max_sentences = 8 if status in {"complete", "guidance", "hint", "passed", "advanced_with_gap"} else 2
    if status == "push_back":
        max_sentences = 1
    allow_commands = status in {"guidance", "hint", "complete", "passed"}
    filtered, flags = filter_specialist_reply(
        reply,
        later_concepts=state.get("later_concepts") or [],
        allow_code=False,
        allow_commands=allow_commands,
        max_sentences=max_sentences,
    )
    catalog = state.get("catalog_milestones") or []
    milestone_id = state.get("milestone_id")
    later = list(state.get("later_concepts") or [])
    if milestone_id is not None and not later:
        later = later_milestone_concepts(catalog, milestone_id)
        filtered, extra = filter_specialist_reply(
            filtered,
            later_concepts=later,
            allow_code=False,
            allow_commands=allow_commands,
            max_sentences=max_sentences,
        )
        flags.extend(extra)
    return {"reply": filtered, "policy_flags": flags}


def build_start_graph(llm: CoachLLM | None = None):
    llm = llm or StubCoachLLM()
    builder = StateGraph(CoachState)
    builder.add_node("assess", assess_node)
    builder.add_node("plan", plan_node)
    builder.add_node("cards", make_cards_node(llm))
    builder.add_node("question", question_node)
    builder.add_edge(START, "assess")
    builder.add_conditional_edges(
        "assess",
        _route_after_assess,
        {"plan": "plan", "end": END},
    )
    builder.add_edge("plan", "cards")
    builder.add_edge("cards", "question")
    builder.add_edge("question", END)
    return builder.compile()


def build_chat_graph(llm: CoachLLM | None = None):
    llm = llm or StubCoachLLM()
    builder = StateGraph(CoachState)
    builder.add_node("route", route_node)
    builder.add_node("evaluate", make_evaluate_node(llm))
    builder.add_node("guidance", make_guidance_node(llm))
    builder.add_node("hint_gate", hint_gate_node)
    builder.add_node("hint_coach", make_hint_node(llm))
    builder.add_node("card_reply", card_reply_node)
    builder.add_node("policy", policy_node)
    builder.add_edge(START, "route")
    builder.add_conditional_edges(
        "route",
        _pick_chat_branch,
        {
            "evaluate": "evaluate",
            "guidance": "guidance",
            "hint_gate": "hint_gate",
            "card_reply": "card_reply",
        },
    )
    builder.add_conditional_edges(
        "hint_gate",
        _after_hint_gate,
        {"policy": "policy", "hint_coach": "hint_coach"},
    )
    builder.add_edge("evaluate", "policy")
    builder.add_edge("guidance", "policy")
    builder.add_edge("hint_coach", "policy")
    builder.add_edge("card_reply", "policy")
    builder.add_edge("policy", END)
    return builder.compile()
