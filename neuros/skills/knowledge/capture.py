"""Knowledge capture skill — store text with tags, embed to Qdrant, log to Postgres."""

from __future__ import annotations

import logging

from neuros.memory.manager import manager as memory_manager
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.knowledge.capture")

PARA_PATHS = {
    "mistake": "03-Resources/mistakes",
    "decision": "03-Resources/decisions",
    "solution": "03-Resources/patterns",
    "correction": "03-Resources/patterns",
    "system": "03-Resources/systems",
    "project": "01-Projects",
}


@skill("capture", "Store knowledge: embed → Qdrant + log → Postgres")
class CaptureSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        text = params.get("text", "")
        tags = params.get("tags", [])
        source = params.get("source", "user")
        category = params.get("category", "general")
        title = params.get("title", text[:60].strip())

        if not text.strip():
            return SkillResult.fail("No text provided to capture")

        para_path = PARA_PATHS.get(category, "03-Resources")
        metadata = {
            "source": source,
            "tags": tags,
            "category": category,
            "para_path": para_path,
            "title": title,
        }

        try:
            memory_id = await memory_manager.store(text, metadata)
            logger.info("Captured knowledge: %s (id=%s)", text[:60], memory_id)
            return SkillResult.ok(
                {
                    "memory_id": memory_id,
                    "tags": tags,
                    "category": category,
                    "para_path": para_path,
                }
            )
        except Exception as exc:
            return SkillResult.fail(str(exc))
