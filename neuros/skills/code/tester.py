"""RunTestsSkill — pytest runner with parsed pass/fail counts."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from neuros.skills.base import BaseSkill, SkillResult, skill
from neuros.skills.code._safety import project_root, resolve_safe

logger = logging.getLogger("neuros.skills.code.tester")


def parse_pytest_output(output: str) -> tuple[int, int, int]:
    """Return (passed, failed, errors)."""
    passed = failed = errors = 0
    m = re.search(r"(\d+)\s+passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", output)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+)\s+error", output)
    if m:
        errors = int(m.group(1))
    return passed, failed, errors


@skill("run_tests", "Run NeurOS test suite or specific test files")
class RunTestsSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        test_path = params.get("test_path") or "tests/"
        verbose = bool(params.get("verbose", False))

        try:
            resolve_safe(test_path)
        except ValueError as e:
            return SkillResult.fail(str(e))

        cmd = ["pytest", test_path, "-x", "--tb=short"]
        if verbose:
            cmd.append("-v")

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_root()),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode("utf-8", errors="replace")
            returncode = proc.returncode
        except asyncio.TimeoutError:
            return SkillResult.fail("pytest timed out after 120s")
        except FileNotFoundError:
            return SkillResult.fail("pytest not installed")

        duration_ms = int((time.monotonic() - start) * 1000)
        passed, failed, errors = parse_pytest_output(output)
        success = returncode == 0 and failed == 0 and errors == 0

        try:
            import neuros.memory.manager as mm

            if mm.manager is not None:
                await mm.manager.store(
                    f"Test run: {passed} passed, {failed} failed",
                    {"source": "test_runner", "path": test_path},
                )
        except Exception as e:
            logger.debug("run_tests: memory store skipped: %s", e)

        return SkillResult.ok(
            {
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "output": output[-4000:],
                "success": success,
                "duration_ms": duration_ms,
            },
            skill_name=self.name,
        )
