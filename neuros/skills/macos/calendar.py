"""Apple Calendar skill — create events and query day/week via AppleScript."""

from __future__ import annotations

import asyncio
import logging

from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.macos.calendar")


async def _run_applescript(script: str) -> str:
    """Execute an AppleScript and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error("AppleScript error: %s", stderr.decode())
        raise RuntimeError(stderr.decode().strip())
    return stdout.decode().strip()


@skill("calendar", "Create events and query Apple Calendar")
class CalendarSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        action = params.get("action", "query")

        try:
            if action == "create":
                return await self._create(params)
            elif action in ("day", "week"):
                return await self._query(params)
            else:
                return SkillResult.fail(f"Unknown action: {action}")
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _create(self, params: dict) -> SkillResult:
        summary = params.get("summary", "")
        start = params.get("start", "")  # e.g. "tomorrow at 9am"
        duration = params.get("duration", 60)  # minutes
        calendar = params.get("calendar", "Home")

        script = f'''
            tell application "Calendar"
                tell calendar "{calendar}"
                    make new event with properties \
                        {{summary:"{summary}", start date:{start}, duration:{duration * 60}}}
                end tell
            end tell
        '''
        await _run_applescript(script)
        return SkillResult.ok({"created": summary, "start": start})

    async def _query(self, params: dict) -> SkillResult:
        scope = params.get("action", "day")  # "day" or "week"
        script = f'''
            tell application "Calendar"
                set output to ""
                repeat with cal in calendars
                    set events_list to (every event of cal whose start date > (current date))
                    repeat with e in events_list
                        set output to output & summary of e & "\\n"
                    end repeat
                end repeat
                return output
            end tell
        '''
        result = await _run_applescript(script)
        events = [e for e in result.split("\n") if e.strip()]
        return SkillResult.ok({"events": events, "scope": scope})
