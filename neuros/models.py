"""Pydantic schemas for NeurOS data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    VISION = "vision"
    REASONING = "reasoning"
    FAST = "fast"


class QueryInput(BaseModel):
    text: str = Field(..., description="User query text")
    image_url: Optional[str] = None
    session_id: Optional[str] = None


class ActionInput(BaseModel):
    skill: str = Field(..., description="Skill name to invoke")
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None


class Memory(BaseModel):
    id: str
    text: str
    source: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    score: Optional[float] = None


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str


class SkillResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class NeurOSResponse(BaseModel):
    text: str
    memories: list[Memory] = Field(default_factory=list)
    search_results: list[SearchResult] = Field(default_factory=list)
    actions_taken: list[SkillResult] = Field(default_factory=list)
    model_used: Optional[str] = None
    session_id: Optional[str] = None
