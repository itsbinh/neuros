"""Knowledge recall skill — semantic search via Qdrant."""

from __future__ import annotations

import logging

from neuros.memory.manager import manager as memory_manager
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.knowledge.recall")


@skill("recall", "Semantic search over stored knowledge")
class RecallSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        query = params.get("query", "")
        k = params.get("k", 5)

        if not query.strip():
            return SkillResult.fail("No query provided")

        try:
            memories = await memory_manager.recall(query, k=k)
            results = [
                {
                    "text": m.text,
                    "source": m.source,
                    "tags": m.tags,
                    "score": m.score,
                }
                for m in memories
            ]
            return SkillResult.ok({"results": results, "count": len(results)})
        except Exception as exc:
            return SkillResult.fail(str(exc))
