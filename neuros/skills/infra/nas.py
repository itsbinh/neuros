"""NAS skill — Synology HTTP API for file browsing, reading, writing."""

from __future__ import annotations

import logging

import httpx

from neuros.config import settings
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.infra.nas")

_NAS_BASE = None


def _base_url() -> str:
    global _NAS_BASE
    if _NAS_BASE is None:
        _NAS_BASE = settings.nas_base_url or f"http://{settings.nas_host}:5000"
    return _NAS_BASE


async def _auth(client: httpx.AsyncClient) -> str:
    """Authenticate with Synology DSM and return session ID (SID)."""
    resp = await client.get(
        f"{_base_url()}/webapi/entry.cgi",
        params={
            "api": "SYNO.API.Auth",
            "version": "7",
            "method": "login",
            "account": settings.nas_user,
            "passwd": settings.nas_password,
            "session": "NeurOS",
            "format": "sid",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"NAS auth failed: {data.get('error')}")
    return data["data"]["sid"]


@skill("nas", "Browse, read, and write files on Synology NAS")
class NASSkill(BaseSkill):
    """Interact with Synology DSM File Station API."""

    async def run(self, **params) -> SkillResult:
        if not settings.nas_password:
            return SkillResult.fail("NAS_PASSWORD not configured")

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
        async with httpx.AsyncClient() as client:
            sid = await _auth(client)
            resp = await client.get(
                f"{_base_url()}/webapi/entry.cgi",
                params={
                    "api": "SYNO.FileStation.List",
                    "version": "2",
                    "method": "list",
                    "folder_path": path,
                    "_sid": sid,
                },
                timeout=15.0,
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return SkillResult.fail(f"NAS browse failed: {data.get('error')}")
        files = [f["name"] for f in data["data"].get("files", [])]
        return SkillResult.ok({"path": path, "files": files})

    async def _read(self, params: dict) -> SkillResult:
        path = params.get("path", "")
        if not path:
            return SkillResult.fail("'path' required")
        async with httpx.AsyncClient() as client:
            sid = await _auth(client)
            resp = await client.get(
                f"{_base_url()}/webapi/entry.cgi",
                params={
                    "api": "SYNO.FileStation.Download",
                    "version": "2",
                    "method": "download",
                    "path": path,
                    "mode": "open",
                    "_sid": sid,
                },
                timeout=30.0,
            )
        resp.raise_for_status()
        return SkillResult.ok({"path": path, "content": resp.text})

    async def _write(self, params: dict) -> SkillResult:
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return SkillResult.fail("'path' required")
        import io

        folder = path.rsplit("/", 1)[0] or "/"
        filename = path.rsplit("/", 1)[-1]
        async with httpx.AsyncClient() as client:
            sid = await _auth(client)
            resp = await client.post(
                f"{_base_url()}/webapi/entry.cgi",
                params={
                    "api": "SYNO.FileStation.Upload",
                    "version": "3",
                    "method": "upload",
                    "path": folder,
                    "create_parents": "true",
                    "overwrite": "true",
                    "_sid": sid,
                },
                files={"file": (filename, io.BytesIO(content.encode()), "text/plain")},
                timeout=30.0,
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return SkillResult.fail(f"NAS write failed: {data.get('error')}")
        return SkillResult.ok({"path": path, "bytes_written": len(content)})
