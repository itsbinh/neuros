"""Knowledge capture skill — store text with tags, embed to Qdrant, log to Postgres."""

from __future__ import annotations

import logging

from neuros.memory.manager import manager as memory_manager
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.knowledge.capture")


@skill("capture", "Store knowledge: embed → Qdrant + log → Postgres")
class CaptureSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        text = params.get("text", "")
        tags = params.get("tags", [])
        source = params.get("source", "user")

        if not text.strip():
            return SkillResult.fail("No text provided to capture")

        try:
            memory_id = await memory_manager.store(
                text=text,
                source=source,
                tags=tags,
            )
            logger.info("Captured knowledge: %s (id=%s)", text[:60], memory_id)
            return SkillResult.ok({"memory_id": memory_id, "tags": tags})
        except Exception as exc:
            return SkillResult.fail(str(exc))
