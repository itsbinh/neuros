"""NAS skill — Synology HTTP API for file browsing, reading, writing."""

from __future__ import annotations

import logging

import httpx

from neuros.config import settings
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.infra.nas")


@skill("nas", "Browse, read, and write files on Synology NAS")
class NASSkill(BaseSkill):
    """Interact with Synology DSM File Station API."""

    async def run(self, **params) -> SkillResult:
        action = params.get("action", "browse")

        try:
            if action == "browse":
                return await self._browse(params)
            elif action == "read":
                return await self._read(params)
            elif action == "write":
                return await self._write(params)
            else:
                return SkillResult.fail(f"Unknown action: {action}")
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _browse(self, params: dict) -> SkillResult:
        path = params.get("path", "/")
        # Synology File Station API stub
        logger.info("NAS browse: %s", path)
        return SkillResult.ok({"message": "Synology API not yet configured", "path": path})

    async def _read(self, params: dict) -> SkillResult:
        path = params.get("path", "")
        logger.info("NAS read: %s", path)
        return SkillResult.ok({"message": "Synology API not yet configured", "path": path})

    async def _write(self, params: dict) -> SkillResult:
        path = params.get("path", "")
        content = params.get("content", "")
        logger.info("NAS write: %s (%d bytes)", path, len(content))
        return SkillResult.ok({"message": "Synology API not yet configured", "path": path})
