"""Skill base class and decorators."""

from __future__ import annotations

import logging
import time as _time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger("neuros.skills")


class SkillResult(BaseModel):
    """Standardized result from any skill execution."""

    success: bool
    data: Any = None
    error: str | None = None
    skill_name: str | None = None

    @classmethod
    def ok(cls, data: Any = None, skill_name: str | None = None) -> SkillResult:
        return cls(success=True, data=data, skill_name=skill_name)

    @classmethod
    def fail(cls, error: str, skill_name: str | None = None) -> SkillResult:
        return cls(success=False, error=error, skill_name=skill_name)

    @property
    def output(self) -> Any:
        """Backward-compatible alias for older callers/tests."""
        return self.data

    @output.setter
    def output(self, value: Any) -> None:
        self.data = value


class BaseSkill(ABC):
    """Base class for all NeurOS skills. Skills are stateless."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def run(self, **params: Any) -> SkillResult:
        """Execute the skill with given parameters."""
        ...


class Skill(BaseSkill):
    """Alternate base for skills that implement execute() instead of run()."""

    async def run(self, **params: Any) -> SkillResult:
        return await self.execute(**params)

    @abstractmethod
    async def execute(self, **params: Any) -> SkillResult: ...


async def run_skill(skill: BaseSkill, **params: Any) -> SkillResult:
    """Run a skill and record telemetry."""
    from neuros import telemetry as _telemetry

    t0 = _time.monotonic()
    result = await skill.run(**params)
    duration_ms = int((_time.monotonic() - t0) * 1000)
    _telemetry.record(skill.name, result.success, duration_ms, result.error)
    return result


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
