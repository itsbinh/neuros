"""Apple Reminders skill — create, list, complete reminders via AppleScript."""

from __future__ import annotations

import asyncio
import logging

from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.macos.reminders")


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


@skill("reminders", "Create, list, and complete Apple Reminders")
class RemindersSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        action = params.get("action", "list")

        try:
            if action == "create":
                return await self._create(params)
            elif action == "list":
                return await self._list(params)
            elif action == "complete":
                return await self._complete(params)
            else:
                return SkillResult.fail(f"Unknown action: {action}")
        except Exception as exc:
            return SkillResult.fail(str(exc))

    async def _create(self, params: dict) -> SkillResult:
        name = params.get("name", "")
        list_name = params.get("list", "Reminders")
        notes = params.get("notes", "")
        script = f'''
            tell application "Reminders"
                tell reminder list "{list_name}"
                    make new reminder with properties {{name:"{name}", body:"{notes}"}}
                end tell
            end tell
        '''
        await _run_applescript(script)
        return SkillResult.ok({"created": name, "list": list_name})

    async def _list(self, params: dict) -> SkillResult:
        list_name = params.get("list", "Reminders")
        script = f'''
            tell application "Reminders"
                set output to ""
                tell reminder list "{list_name}"
                    set uncompleted to (every reminder whose completed is false)
                    repeat with r in uncompleted
                        set output to output & name of r & "\\n"
                    end repeat
                end tell
                return output
            end tell
        '''
        result = await _run_applescript(script)
        reminders = [r for r in result.split("\n") if r.strip()]
        return SkillResult.ok({"reminders": reminders, "list": list_name})

    async def _complete(self, params: dict) -> SkillResult:
        name = params.get("name", "")
        script = f'''
            tell application "Reminders"
                set found to false
                set target to missing value
                tell reminder list "Reminders"
                    repeat with r in (every reminder whose completed is false)
                        if name of r is "{name}" then
                            set target to r
                            set found to true
                            exit repeat
                        end if
                    end repeat
                    if found then
                        set completed of target to true
                    end if
                end tell
                return found
            end tell
        '''
        result = await _run_applescript(script)
        return SkillResult.ok({"completed": name, "found": result == "true"})
