"""Skill registry — auto-discovers and registers skills as LangGraph tools."""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any

from neuros.skills.base import BaseSkill, SkillResult

logger = logging.getLogger("neuros.skills.registry")

# All registered skill instances
_skills: dict[str, BaseSkill] = {}


def _discover_skills(package_name: str = "neuros.skills") -> list[type[BaseSkill]]:
    """Walk the skills package tree and find all BaseSkill subclasses."""
    discovered: list[type[BaseSkill]] = []
    package = importlib.import_module(package_name)
    importer = pkgutil.walk_packages(
        package.__path__,
        prefix=f"{package.__name__}.",
        onerror=lambda x: None,
    )
    for _, modname, _ in importer:
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            logger.warning("Failed to import %s: %s", modname, e)
            continue

        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                inspect.isclass(attr)
                and issubclass(attr, BaseSkill)
                and attr is not BaseSkill
                and not inspect.isabstract(attr)
            ):
                discovered.append(attr)
    return discovered


def register(skill_instance: BaseSkill) -> None:
    """Register a skill instance by name."""
    _skills[skill_instance.name] = skill_instance
    logger.info("Registered skill: %s — %s", skill_instance.name, skill_instance.description)


def get_skill(name: str) -> BaseSkill | None:
    """Get a registered skill by name."""
    return _skills.get(name)


def list_skills() -> dict[str, str]:
    """Return {name: description} of all registered skills."""
    return {name: s.description for name, s in _skills.items()}


async def dispatch(skill_name: str, **params: Any) -> SkillResult:
    """Dispatch a skill by name with parameters."""
    skill = _skills.get(skill_name)
    if skill is None:
        return SkillResult.fail(f"Unknown skill: {skill_name}")
    try:
        return await skill.run(**params)
    except Exception as exc:
        logger.exception("Skill %s failed: %s", skill_name, exc)
        return SkillResult.fail(str(exc))


def auto_register() -> None:
    """Auto-discover and register all skills. Call once at startup."""
    for cls in _discover_skills():
        instance = cls()
        register(instance)
    logger.info("Auto-registered %d skills", len(_skills))


class SkillRegistry:
    """OO wrapper around the module-level registry used by main.py."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = _skills

    @classmethod
    def auto_discover(cls) -> "SkillRegistry":
        auto_register()
        return cls()

    def all_skills(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    async def dispatch(self, skill_name: str, **params: Any) -> SkillResult:
        return await dispatch(skill_name, **params)
