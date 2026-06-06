"""RunTestsSkill — pytest runner with parsed pass/fail counts."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path

from neuros.config import settings
from neuros.skills.base import BaseSkill, SkillResult, skill
from neuros.skills.code import _safety
from neuros.skills.code._safety import resolve_safe

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
    async def _run_pytest(
        self,
        test_path: str | list[str],
        verbose: bool,
        *,
        allow_fallback: bool = True,
    ) -> SkillResult:
        project_root = Path(settings.project_root)

        if isinstance(test_path, list):
            paths_to_run: list[str] = []
            missing: list[str] = []
            for p in test_path:
                full = project_root / p
                if full.exists():
                    paths_to_run.append(p)
                else:
                    missing.append(p)

            if missing:
                logger.warning("Test files not found: %s", missing)
            if not paths_to_run:
                logger.warning("No proposed test files found — running full test suite")
                paths_to_run = ["tests/"]
            test_args = paths_to_run
        else:
            target = project_root / test_path
            if not target.exists():
                logger.warning("Test file not found: %s", test_path)
                if allow_fallback and test_path != "tests/":
                    logger.warning("Test file not found: %s — running full suite", test_path)
                    return await self._run_pytest("tests/", verbose, allow_fallback=False)
                logger.warning("No proposed test files found — running full test suite")
                test_path = "tests/"
            test_args = [test_path]

        cmd = ["pytest", *test_args, "-x", "--tb=short"]
        if verbose:
            cmd.append("-v")

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(_safety.project_root()),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode("utf-8", errors="replace")
            returncode = proc.returncode
        except TimeoutError:
            return SkillResult.fail("pytest timed out after 120s")
        except FileNotFoundError:
            return SkillResult.fail("pytest not installed")

        duration_ms = int((time.monotonic() - start) * 1000)
        passed, failed, errors = parse_pytest_output(output)

        if (
            allow_fallback
            and "tests/" not in test_args
            and ("no tests ran" in output.lower() or "collected 0 items" in output.lower())
        ):
            logger.warning("No tests collected from specified paths — running full suite")
            return await self._run_pytest("tests/", verbose, allow_fallback=False)

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

    async def run(self, **params) -> SkillResult:
        test_path = params.get("test_path") or "tests/"
        verbose = bool(params.get("verbose", False))

        try:
            if isinstance(test_path, str):
                resolve_safe(test_path)
            else:
                for p in test_path:
                    resolve_safe(p)
        except ValueError as e:
            return SkillResult.fail(str(e))

        return await self._run_pytest(test_path, verbose)
