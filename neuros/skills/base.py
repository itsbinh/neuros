"""Skill base class and decorators."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("neuros.skills")


class SkillResult(BaseModel):
    """Standardized result from any skill execution."""

    success: bool
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any = None) -> SkillResult:
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> SkillResult:
        return cls(success=False, error=error)


class BaseSkill(ABC):
    """Base class for all NeurOS skills. Skills are stateless."""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def run(self, **params: Any) -> SkillResult:
        """Execute the skill with given parameters."""
        ...


def skill(name: str, description: str = ""):
    """Decorator to register a class as a NeurOS skill.

    Usage:
        @skill("reminders", "Manage Apple Reminders")
        class RemindersSkill(BaseSkill):
            ...
    """
    def wrapper(cls: type) -> type:
        cls.name = name
        cls.description = description or cls.__doc__ or ""
        return cls
    return wrapper
