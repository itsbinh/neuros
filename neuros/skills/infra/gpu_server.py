"""GPU server skill — llama.cpp health, loaded models, GPU utilization."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from neuros.config import settings
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.infra.gpu")

_executor = ThreadPoolExecutor(max_workers=4)

_HOST_URLS = {
    "lts1": settings.lts1_base_url,
}


def _ssh_run(host: str, cmd: str) -> str:
    """Run a command over SSH and return stdout. Requires paramiko."""
    import os

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    known_hosts = os.path.expanduser("~/.ssh/known_hosts")
    if os.path.exists(known_hosts):
        client.load_host_keys(known_hosts)
    try:
        client.connect(
            host,
            username=settings.ssh_user_lts1,
            key_filename=os.path.expanduser(settings.ssh_key_path),
            timeout=15,
        )
        _, stdout, _ = client.exec_command(cmd)
        return stdout.read().decode()
    finally:
        client.close()


@skill("gpu_server", "Check llama.cpp health, loaded models, GPU utilization, disk, containers")
class GPUServerSkill(BaseSkill):
    """Query the lts1/lts2 GPU inference servers."""

    async def run(self, **params) -> SkillResult:
        action = params.get("action", "health")
        host = params.get("host", "lts1")

        try:
            if action == "health":
                return await self._health()
            elif action == "models":
                return await self._models()
            elif action == "gpu":
                return await self._gpu_utilization()
            elif action == "disk":
                return await self._disk(host)
            elif action == "containers":
                return await self._containers(host)
            else:
                return SkillResult.fail(f"Unknown action: {action}")
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _health(self) -> SkillResult:
        """Ping the llama.cpp router health endpoint."""
        url = f"{settings.lts1_base_url}/health"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
        return SkillResult.ok(
            {
                "status": "ok" if resp.status_code == 200 else "error",
                "body": resp.text,
            }
        )

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

    async def _disk(self, host: str) -> SkillResult:
        """SSH to host and return disk usage for / and /mnt/main_pool."""
        loop = asyncio.get_event_loop()
        cmd = "df -h / /mnt/main_pool 2>/dev/null || df -h /"
        output = await loop.run_in_executor(_executor, _ssh_run, host, cmd)
        mounts: dict[str, dict] = {}
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 6:
                mount = parts[5]
                mounts[mount] = {
                    "size": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "use_pct": parts[4],
                }
        return SkillResult.ok({"host": host, "mounts": mounts})

    async def _containers(self, host: str) -> SkillResult:
        """SSH to host and list running Docker containers."""
        loop = asyncio.get_event_loop()
        cmd = "docker ps --format '{{.Names}}\t{{.Status}}\t{{.Image}}'"
        output = await loop.run_in_executor(_executor, _ssh_run, host, cmd)
        containers = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                name, status, image = parts[0], parts[1], parts[2]
                containers.append(
                    {
                        "name": name,
                        "status": status,
                        "image": image,
                        "restarting": "Restarting" in status,
                    }
                )
        return SkillResult.ok({"host": host, "containers": containers})
