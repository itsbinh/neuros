"""Tests for macOS skills."""

from __future__ import annotations

import pytest

from neuros.skills.base import SkillResult


def test_skill_result_ok() -> None:
    result = SkillResult.ok(data={"key": "value"})
    assert result.success is True
    assert result.data == {"key": "value"}
    assert result.error is None


def test_skill_result_fail() -> None:
    result = SkillResult.fail("something broke")
    assert result.success is False
    assert result.error == "something broke"


@pytest.mark.asyncio
async def test_reminders_skill_unknown_action() -> None:
    """Reminders skill rejects unknown actions."""
    from neuros.skills.macos.reminders import RemindersSkill

    skill = RemindersSkill()
    # We can't run AppleScript in CI, so test the action dispatch logic
    result = await skill.run(action="invalid")
    assert not result.success
    assert "Unknown action" in (result.error or "")


@pytest.mark.asyncio
async def test_system_skill_unknown_action() -> None:
    """System skill rejects unknown actions."""
    from neuros.skills.macos.system import SystemSkill

    skill = SystemSkill()
    result = await skill.run(action="nonexistent")
    assert not result.success


@pytest.mark.asyncio
async def test_calendar_skill_unknown_action() -> None:
    """Calendar skill rejects unknown actions."""
    from neuros.skills.macos.calendar import CalendarSkill

    skill = CalendarSkill()
    result = await skill.run(action="invalid")
    assert not result.success
    assert "Unknown action" in (result.error or "")
