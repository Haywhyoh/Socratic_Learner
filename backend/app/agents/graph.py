"""LangGraph entrypoints.

The live mentor is ``build_mentor_graph`` in mentor_graph.py. These names stay
as thin aliases so older imports keep working.
"""

from app.agents.llm import CoachLLM
from app.agents.mentor_graph import build_mentor_graph


def build_start_graph(llm: CoachLLM | None = None):
    return build_mentor_graph(llm)


def build_chat_graph(llm: CoachLLM | None = None):
    return build_mentor_graph(llm)
