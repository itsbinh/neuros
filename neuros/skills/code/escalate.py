"""Escalate a task to Claude Code CLI for complex reasoning."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from neuros.skills.base import BaseSkill, SkillResult, skill


@skill("escalate", "Delegate a complex task to Claude Code CLI for deep reasoning")
class EscalateSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        task = params.get("task", "")
        context = params.get("context", "")
        timeout = params.get("timeout", 120)

        if not task:
            return SkillResult.fail("'task' param required")

        prompt = f"""Task: {task}

Context:
{context}

Provide a thorough analysis and solution. Be specific and actionable."""

        artifact_dir = Path.home() / ".neuros" / "escalations"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_id = str(uuid.uuid4())[:8]
        artifact_path = artifact_dir / f"{artifact_id}.md"
        artifact_path.write_text(
            f"# Escalation {artifact_id}\n\nTask: {task}\n\nContext:\n{context}\n"
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            result_text = stdout.decode().strip()
            if proc.returncode != 0:
                return SkillResult.fail(f"Claude CLI error: {stderr.decode().strip()}")

            artifact_path.write_text(artifact_path.read_text() + f"\n\n## Result\n\n{result_text}")
            return SkillResult.ok({"result": result_text, "artifact": str(artifact_path)})
        except TimeoutError:
            return SkillResult.fail(f"Escalation timed out after {timeout}s")
        except FileNotFoundError:
            return SkillResult.fail("Claude CLI not found — install claude-code")
