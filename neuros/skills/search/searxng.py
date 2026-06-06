"""SearXNG search skill — web queries via local SearXNG instance."""

from __future__ import annotations

import logging

import httpx

from neuros.config import settings
from neuros.models import SearchResult
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.search.searxng")


@skill("search", "Web search via local SearXNG")
class SearXNGSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        query = params.get("query", "")
        n = params.get("n", 5)

        if not query.strip():
            return SkillResult.fail("No search query provided")

        try:
            results = await self._search(query, n=n)
            return SkillResult.ok(
                {
                    "results": [r.model_dump() for r in results],
                    "count": len(results),
                }
            )
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _search(self, query: str, n: int = 5) -> list[SearchResult]:
        """Query SearXNG and return structured results."""
        url = f"{settings.searxng_url}/search"
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", [])[:n]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "") or item.get("description", ""),
                    source=item.get("engine", "unknown"),
                )
            )
        return results
