"""ApplyChangeSkill — apply an approved proposal with backup + test gate."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from neuros.skills.base import BaseSkill, SkillResult, skill
from neuros.skills.code._safety import check_extension, resolve_safe
from neuros.skills.code.tester import RunTestsSkill

logger = logging.getLogger("neuros.skills.code.applier")


@skill("apply_change", "Apply an approved code change to the NeurOS codebase")
class ApplyChangeSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        proposal_id = params.get("proposal_id")
        confirmed = params.get("confirmed", False)

        if not proposal_id:
            return SkillResult.fail("proposal_id is required")
        if confirmed is not True:
            return SkillResult.fail("confirmed=True required to apply")

        import neuros.memory.manager as mm

        if mm.manager is None:
            return SkillResult.fail("memory manager not initialized")
        postgres = mm.manager._postgres

        proposal = await postgres.get_proposal(proposal_id)
        if proposal is None:
            return SkillResult.fail(f"Proposal not found: {proposal_id}")
        if proposal.status != "approved":
            return SkillResult.fail(
                f"Proposal status is {proposal.status}, must be 'approved'"
            )

        try:
            target = resolve_safe(proposal.path)
            check_extension(target)
        except ValueError as e:
            await postgres.update_proposal_status(proposal_id, "failed", test_result=str(e))
            return SkillResult.fail(str(e))

        if not target.is_file():
            await postgres.update_proposal_status(proposal_id, "failed", test_result="file gone")
            return SkillResult.fail(f"File no longer exists: {proposal.path}")

        original_content = target.read_text(encoding="utf-8")
        if proposal.original not in original_content:
            err = "original text no longer matches — file may have changed"
            await postgres.update_proposal_status(proposal_id, "failed", test_result=err)
            return SkillResult.fail(err)

        backup_path = Path(f"{target}.neuros_backup_{int(time.time())}")
        backup_path.write_text(original_content, encoding="utf-8")

        new_content = original_content.replace(proposal.original, proposal.replacement, 1)
        try:
            target.write_text(new_content, encoding="utf-8")
        except Exception as e:
            backup_path.unlink(missing_ok=True)
            await postgres.update_proposal_status(proposal_id, "failed", test_result=str(e))
            return SkillResult.fail(f"Write failed: {e}")

        test_paths = proposal.tests_affected or ["tests/"]
        tester = RunTestsSkill()
        tests_passed = True
        test_output_parts: list[str] = []
        for tp in test_paths:
            tr = await tester.run(test_path=tp)
            if not tr.success:
                tests_passed = False
                test_output_parts.append(f"[{tp}] {tr.error}")
                break
            data = tr.data or {}
            test_output_parts.append(
                f"[{tp}] passed={data.get('passed', 0)} failed={data.get('failed', 0)}"
            )
            if not data.get("success"):
                tests_passed = False
                test_output_parts.append(data.get("output", ""))
                break

        test_output = "\n".join(test_output_parts)

        if tests_passed:
            backup_path.unlink(missing_ok=True)
            await postgres.update_proposal_status(
                proposal_id, "applied", test_result=test_output
            )
            return SkillResult.ok(
                {
                    "proposal_id": proposal_id,
                    "applied": True,
                    "tests_passed": True,
                    "test_output": test_output,
                    "backed_up": None,
                },
                skill_name=self.name,
            )

        # Restore
        target.write_text(original_content, encoding="utf-8")
        backup_path.unlink(missing_ok=True)
        await postgres.update_proposal_status(proposal_id, "failed", test_result=test_output)
        return SkillResult.ok(
            {
                "proposal_id": proposal_id,
                "applied": False,
                "tests_passed": False,
                "test_output": test_output,
                "backed_up": None,
            },
            skill_name=self.name,
        )
