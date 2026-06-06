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


@pytest.mark.asyncio
async def test_query_search_prefix_uses_searxng(monkeypatch) -> None:
    """Overlay search: queries bypass the LLM and use SearXNG directly."""
    from neuros.main import query
    from neuros.models import QueryInput
    from neuros.skills.search.searxng import SearXNGSkill

    async def fake_run(self, **params):
        assert params["query"] == "hammerspoon webview"
        return SkillResult.ok(
            {
                "results": [
                    {
                        "title": "Hammerspoon",
                        "url": "https://www.hammerspoon.org/",
                        "snippet": "Automation for macOS.",
                        "source": "mock",
                    }
                ],
                "count": 1,
            }
        )

    monkeypatch.setattr(SearXNGSkill, "run", fake_run)

    result = await query(QueryInput(text="search: hammerspoon webview"))

    assert result.model_used == "searxng"
    assert "Hammerspoon" in result.text
    assert result.search_results[0].source == "mock"
