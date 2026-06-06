"""macOS System skill — clipboard, app launch, notifications via AppleScript."""

from __future__ import annotations

import asyncio
import logging

from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.macos.system")


async def _run_applescript(script: str) -> str:
    """Execute an AppleScript and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "osascript",
        "-e",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error("AppleScript error: %s", stderr.decode())
        raise RuntimeError(stderr.decode().strip())
    return stdout.decode().strip()


@skill("system", "Clipboard R/W, app launch, system notifications")
class SystemSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        action = params.get("action", "")

        try:
            handlers = {
                "clipboard_read": self._clipboard_read,
                "clipboard_write": self._clipboard_write,
                "launch_app": self._launch_app,
                "notification": self._notification,
            }
            handler = handlers.get(action)
            if handler is None:
                return SkillResult.fail(f"Unknown action: {action}")
            return await handler(params)
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _clipboard_read(self, params: dict) -> SkillResult:
        script = "get the clipboard"
        text = await _run_applescript(script)
        return SkillResult.ok({"clipboard": text})

    async def _clipboard_write(self, params: dict) -> SkillResult:
        text = params.get("text", "")
        # Escape quotes for AppleScript
        safe = text.replace('"', '\\"')
        script = f'set the clipboard to "{safe}"'
        await _run_applescript(script)
        return SkillResult.ok({"written": len(text)})

    async def _launch_app(self, params: dict) -> SkillResult:
        app_name = params.get("app", "")
        script = f'tell application "{app_name}" to activate'
        await _run_applescript(script)
        return SkillResult.ok({"launched": app_name})

    async def _notification(self, params: dict) -> SkillResult:
        title = params.get("title", "NeurOS")
        message = params.get("message", "")
        safe_title = title.replace('"', '\\"')
        safe_msg = message.replace('"', '\\"')
        script = f'display notification "{safe_msg}" with title "{safe_title}"'
        await _run_applescript(script)
        return SkillResult.ok({"title": title})
