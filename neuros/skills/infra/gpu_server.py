"""GPU server skill — llama.cpp health, loaded models, GPU utilization."""

from __future__ import annotations

import logging

import httpx

from neuros.config import settings
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.infra.gpu")


@skill("gpu_server", "Check llama.cpp health, loaded models, GPU utilization")
class GPUServerSkill(BaseSkill):
    """Query the lts1 GPU inference server."""

    async def run(self, **params) -> SkillResult:
        action = params.get("action", "health")

        try:
            if action == "health":
                return await self._health()
            elif action == "models":
                return await self._models()
            elif action == "gpu":
                return await self._gpu_utilization()
            else:
                return SkillResult.fail(f"Unknown action: {action}")
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _health(self) -> SkillResult:
        """Ping the llama.cpp router health endpoint."""
        url = f"{settings.lts1_base_url}/health"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        return SkillResult.ok({
            "status": "ok" if resp.status_code == 200 else "error",
            "body": resp.text,
        })

    async def _models(self) -> SkillResult:
        """List loaded models on the router."""
        url = f"{settings.lts1_base_url}/v1/models"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        data = resp.json()
        model_names = [m.get("id", m.get("name", "?")) for m in data.get("data", [])]
        return SkillResult.ok({"models": model_names})

    async def _gpu_utilization(self) -> SkillResult:
        """Query GPU utilization via nvidia-smi over SSH."""
        # This would use the SSH skill internally; stub for now.
        return SkillResult.ok({"message": "GPU query not yet implemented"})
