"""Tests for the LangGraph agent pipeline."""

from __future__ import annotations

import pytest

from neuros.graph import AgentState, build_graph


def test_build_graph() -> None:
    """Graph compiles without error."""
    graph = build_graph()
    assert graph is not None


def test_agent_state_defaults() -> None:
    """AgentState has sensible defaults."""
    state = AgentState()
    assert state.input_text == ""
    assert state.memories == []
    assert state.actions_taken == []
    assert state.final_response == ""


@pytest.mark.asyncio
async def test_intake_node_text_only() -> None:
    """Intake classifies text-only input as REASONING."""
    from neuros.graph import intake

    state = AgentState(input_text="What is 2+2?")
    result = await intake(state)
    assert result["task_type"].value == "reasoning"


@pytest.mark.asyncio
async def test_intake_node_with_image() -> None:
    """Intake classifies image input as VISION."""
    from neuros.graph import intake

    state = AgentState(input_text="Describe this image", image_url="http://example.com/img.png")
    result = await intake(state)
    assert result["task_type"].value == "vision"


@pytest.mark.asyncio
async def test_respond_node() -> None:
    """Respond formats the LLM response."""
    from neuros.graph import respond

    state = AgentState(llm_response="The answer is 42.")
    result = await respond(state)
    assert result["final_response"] == "The answer is 42."


@pytest.mark.asyncio
async def test_respond_node_empty() -> None:
    """Respond provides fallback when no LLM response."""
    from neuros.graph import respond

    state = AgentState(llm_response="")
    result = await respond(state)
    assert "not sure" in result["final_response"].lower()
