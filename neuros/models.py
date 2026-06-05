"""Pydantic schemas for NeurOS data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class TaskType(str, Enum):
    VISION = "vision"
    REASONING = "reasoning"
    FAST = "fast"


class QueryInput(BaseModel):
    text: str = Field(..., description="User query text")
    image_url: str | None = None
    session_id: str | None = None


class ActionInput(BaseModel):
    skill: str = Field(..., description="Skill name to invoke")
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


class Memory(BaseModel):
    id: str
    text: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str | None = None
    score: float | None = None


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str


class SkillResult(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None


class NeurOSResponse(BaseModel):
    text: str
    memories: list[Memory] = Field(default_factory=list)
    search_results: list[SearchResult] = Field(default_factory=list)
    actions_taken: list[SkillResult] = Field(default_factory=list)
    model_used: str | None = None
    session_id: str | None = None


class MemoryResult(BaseModel):
    """Single result from semantic memory search."""

    id: str
    text: str
    score: float
    metadata: dict = Field(default_factory=dict)
    timestamp: str | None = None


class GraphMemoryResult(BaseModel):
    content: str
    score: float
    entity_names: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source: str = ""


class GraphEntity(BaseModel):
    uuid: str
    name: str
    entity_type: str
    summary: str | None = None
    created_at: datetime


class GraphRelation(BaseModel):
    subject: str
    predicate: str
    object: str
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    episode_id: str = ""


class TimelineEvent(BaseModel):
    timestamp: datetime
    fact: str
    source: str = ""
    still_valid: bool = True


class ProposedChange(BaseModel):
    """A proposed code change awaiting approval/apply."""

    id: str
    path: str
    summary: str
    reason: str
    risk: str  # "low" | "medium" | "high"
    original: str
    replacement: str
    tests_affected: list[str] = Field(default_factory=list)
    proposed_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"  # "pending" | "approved" | "rejected" | "applied" | "failed"
    applied_at: datetime | None = None
    test_result: str | None = None


class NeurOSState(TypedDict, total=False):
    """LangGraph state flowing through the agent pipeline."""

    input: str
    session_id: str
    context: list[str]
    response: str
    tool_calls: list[dict]
    skill_result: Any
    skill_results: list[Any]
    skill_used: str | None
    model_used: str
    latency_ms: int
    intent: str
    error: str | None
