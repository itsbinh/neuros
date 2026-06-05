"""LangGraph agent pipeline: intake → recall → think → act → store → respond."""

from __future__ import annotations

import logging
from typing import Any, Annotated, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from neuros.models import Memory, SearchResult, SkillResult, TaskType

logger = logging.getLogger("neuros.graph")


class AgentState(BaseModel):
    """Shared state flowing through the graph."""

    input_text: str = ""
    image_url: str | None = None
    session_id: str | None = None

    # recall outputs
    memories: list[Memory] = Field(default_factory=list)
    recent_context: list[str] = Field(default_factory=list)

    # think outputs
    task_type: TaskType = TaskType.REASONING
    model_name: str = ""
    llm_response: str = ""

    # act outputs
    actions_taken: list[SkillResult] = Field(default_factory=list)
    search_results: list[SearchResult] = Field(default_factory=list)

    # respond output
    final_response: str = ""

    # messages for langchain compatibility
    messages: Annotated[list, add_messages] = Field(default_factory=list)


# ── Node functions ───────────────────────────────────────────────

async def intake(state: AgentState) -> dict[str, Any]:
    """Parse input and classify task type."""
    logger.info("intake: %s", state.input_text[:80])
    has_image = bool(state.image_url)
    task_type = TaskType.VISION if has_image else TaskType.REASONING

    return {"task_type": task_type}


async def recall(state: AgentState) -> dict[str, Any]:
    """Retrieve relevant memories and recent context."""
    logger.info("recall: searching for '%s'", state.input_text[:60])
    # TODO: wire up memory_manager.recall() + redis get_recent()
    return {}


async def think(state: AgentState) -> dict[str, Any]:
    """Route to the correct model and generate response."""
    logger.info("think: task_type=%s", state.task_type)
    # TODO: wire up llm.selector + client.chat()
    return {"llm_response": ""}


async def act(state: AgentState) -> dict[str, Any]:
    """Execute skills based on LLM tool calls."""
    logger.info("act: processing tool calls")
    # TODO: wire up skill_registry dispatch
    return {}


async def store(state: AgentState) -> dict[str, Any]:
    """Persist interaction to memory layer."""
    logger.info("store: saving interaction")
    # TODO: wire up memory_manager.store() + log_interaction()
    return {}


async def respond(state: AgentState) -> dict[str, Any]:
    """Format final response for the user."""
    text = state.llm_response or "I'm not sure how to help with that."
    return {"final_response": text}


# ── Graph construction ───────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the agent pipeline."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("intake", intake)
    graph.add_node("recall", recall)
    graph.add_node("think", think)
    graph.add_node("act", act)
    graph.add_node("store", store)
    graph.add_node("respond", respond)

    # Define flow
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "recall")
    graph.add_edge("recall", "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", "store")
    graph.add_edge("store", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


# Compiled graph instance
graph = build_graph()
