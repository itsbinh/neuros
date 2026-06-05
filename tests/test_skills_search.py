"""Tests for search skills."""

from __future__ import annotations

import pytest

from neuros.skills.base import SkillResult


@pytest.mark.asyncio
async def test_searxng_skill_missing_query() -> None:
    """SearXNG skill requires a query."""
    from neuros.skills.search.searxng import SearXNGSkill

    skill = SearXNGSkill()
    result = await skill.run()
    assert not result.success
    assert "No search query" in (result.error or "")


@pytest.mark.asyncio
async def test_searxng_skill_empty_query() -> None:
    """SearXNG skill rejects empty query."""
    from neuros.skills.search.searxng import SearXNGSkill

    skill = SearXNGSkill()
    result = await skill.run(query="   ")
    assert not result.success
