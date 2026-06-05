"""ProposeImprovementSkill — LLM-driven code-change proposal, persisted to Postgres."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from neuros.config import settings
from neuros.llm.client import chat
from neuros.llm.selector import select_model
from neuros.models import ProposedChange, TaskType
from neuros.skills.base import BaseSkill, SkillResult, skill
from neuros.skills.code.reader import ReadFileSkill

logger = logging.getLogger("neuros.skills.code.improver")

_SYSTEM_PROMPT = (
    "You are NeurOS's self-improvement engine.\n"
    "Analyze the provided source file and propose ONE specific, actionable improvement.\n\n"
    "Rules:\n"
    "- Propose only ONE change at a time\n"
    "- Change must be testable\n"
    "- Preserve all existing functionality\n"
    "- Output ONLY valid Python (or Lua for .lua files)\n"
    "- Be surgical — minimal diff, maximum impact"
)


def _parse_response(text: str) -> dict | None:
    """Parse the structured response into a dict, or None if malformed."""

    def grab(label: str) -> str | None:
        m = re.search(rf"^{label}:\s*(.+?)(?=\n[A-Z_]+:|\Z)", text, re.MULTILINE | re.DOTALL)
        return m.group(1).strip() if m else None

    summary = grab("SUMMARY")
    reason = grab("REASON")
    risk = grab("RISK")
    original = grab("ORIGINAL")
    replacement = grab("REPLACEMENT")
    tests = grab("TESTS_AFFECTED") or ""

    if not all([summary, reason, risk, original, replacement]):
        return None

    risk_norm = (risk or "medium").strip().lower().split()[0]
    if risk_norm not in {"low", "medium", "high"}:
        risk_norm = "medium"

    tests_list = [t.strip() for t in re.split(r"[,\n]", tests) if t.strip()]

    return {
        "summary": summary.strip(),
        "reason": reason.strip(),
        "risk": risk_norm,
        "original": original.strip("\n"),
        "replacement": replacement.strip("\n"),
        "tests_affected": tests_list,
    }


def _find_closest_test(proposed: str, real_files: list[str]) -> str | None:
    """Find closest real test file by substring match on stem."""
    proposed_stem = Path(proposed).stem.replace("test_", "")
    for real in real_files:
        real_stem = Path(real).stem.replace("test_", "")
        if proposed_stem in real_stem or real_stem in proposed_stem:
            return real
    return None


@skill("propose_improvement", "Analyze a NeurOS file and propose a specific improvement")
class ProposeImprovementSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        path = params.get("path")
        aspect = params.get("aspect", "general")
        instruction = params.get("instruction") or ""

        if not path:
            return SkillResult.fail("path is required")

        reader = ReadFileSkill()
        read_result = await reader.run(path=path)
        if not read_result.success:
            return read_result

        content = read_result.data["content"]
        project_root = Path(settings.project_root)
        tests_dir = project_root / "tests"
        test_files = sorted(
            [
                f.name
                for f in tests_dir.iterdir()
                if f.is_file() and f.name.startswith("test_") and f.suffix == ".py"
            ]
        ) if tests_dir.exists() else []

        user_prompt = (
            f"File: {path}\n"
            f"Aspect to improve: {aspect}\n"
            f"Specific instruction: {instruction or '(none)'}\n\n"
            f"Current content:\n{content[:18000]}\n\n"
            "IMPORTANT — test file constraint:\n"
            "The following test files actually exist in this project:\n"
            f"{chr(10).join(test_files)}\n\n"
            "TESTS_AFFECTED must ONLY reference files from the list above.\n"
            'If no existing test file covers the changed code, use "tests/test_dogfood.py".\n'
            "Never invent test file names.\n\n"
            "Respond in this EXACT format:\n\n"
            "SUMMARY: <one sentence what this change does>\n"
            "REASON: <one sentence why this improves NeurOS>\n"
            "RISK: low | medium | high\n\n"
            "ORIGINAL:\n<exact lines to replace — must match file exactly>\n\n"
            "REPLACEMENT:\n<new lines>\n\n"
            "TESTS_AFFECTED: <comma-separated test files to run>"
        )

        model_config = select_model(TaskType.REASONING)
        try:
            response = await chat(
                model=model_config.name,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                base_url=model_config.base_url,
                temperature=0.2,
            )
        except Exception as e:
            return SkillResult.fail(f"LLM call failed: {e}")

        if not isinstance(response, str):
            return SkillResult.fail("LLM returned non-text response")

        parsed = _parse_response(response)
        if parsed is None:
            return SkillResult.fail(
                f"Could not parse improvement response. Raw:\n{response[:500]}"
            )

        validated_tests: list[str] = []
        for test_name in parsed["tests_affected"]:
            test_path = project_root / test_name
            if test_path.exists():
                validated_tests.append(test_name)
                continue

            closest = _find_closest_test(test_name, test_files)
            if closest:
                validated_tests.append(f"tests/{closest}")

        if not validated_tests:
            validated_tests = ["tests/test_dogfood.py"]

        proposal = ProposedChange(
            id=str(uuid.uuid4()),
            path=path,
            summary=parsed["summary"],
            reason=parsed["reason"],
            risk=parsed["risk"],
            original=parsed["original"],
            replacement=parsed["replacement"],
            tests_affected=validated_tests,
            proposed_at=datetime.now(timezone.utc),
            status="pending",
        )

        try:
            import neuros.memory.manager as mm

            if mm.manager is not None:
                await mm.manager._postgres.save_proposal(proposal)
        except Exception as e:
            logger.warning("propose_improvement: db save failed: %s", e)

        return SkillResult.ok(proposal.model_dump(mode="json"), skill_name=self.name)
