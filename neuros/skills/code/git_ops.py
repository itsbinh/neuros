"""Git skills: status, diff, commit, push. Never commits to or force-pushes main."""

from __future__ import annotations

import asyncio
import logging
import re

from neuros.skills.base import BaseSkill, SkillResult, skill
from neuros.skills.code._safety import project_root, resolve_safe

logger = logging.getLogger("neuros.skills.code.git_ops")


async def _git(*args: str, timeout: float = 30.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(project_root()),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", "git command timed out"
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


async def _current_branch() -> str:
    rc, out, _ = await _git("rev-parse", "--abbrev-ref", "HEAD")
    return out.strip() if rc == 0 else ""


@skill("git_status", "Get current git status of NeurOS repository")
class GitStatusSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        branch = await _current_branch()
        rc, status_out, err = await _git("status", "--short")
        if rc != 0:
            return SkillResult.fail(err.strip() or "git status failed")
        changed = [ln.strip() for ln in status_out.splitlines() if ln.strip()]

        rc2, log_out, _ = await _git("log", "--oneline", "-5")
        commits = [ln for ln in log_out.splitlines() if ln.strip()] if rc2 == 0 else []

        return SkillResult.ok(
            {"branch": branch, "changed_files": changed, "recent_commits": commits},
            skill_name=self.name,
        )


@skill("git_diff", "Show git diff for a specific file or all changes")
class GitDiffSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        path = params.get("path")
        staged = bool(params.get("staged", False))

        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            try:
                resolve_safe(path)
            except ValueError as e:
                return SkillResult.fail(str(e))
            args.append(path)

        rc, out, err = await _git(*args)
        if rc != 0:
            return SkillResult.fail(err.strip() or "git diff failed")

        files_changed = len(re.findall(r"^diff --git ", out, re.MULTILINE))
        insertions = len(re.findall(r"^\+(?!\+)", out, re.MULTILINE))
        deletions = len(re.findall(r"^-(?!-)", out, re.MULTILINE))

        return SkillResult.ok(
            {
                "diff": out[:20000],
                "files_changed": files_changed,
                "insertions": insertions,
                "deletions": deletions,
            },
            skill_name=self.name,
        )


@skill("git_commit", "Commit approved NeurOS changes to git")
class GitCommitSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        message = (params.get("message") or "").strip()
        paths = params.get("paths") or []
        confirmed = params.get("confirmed", False)

        if confirmed is not True:
            return SkillResult.fail("confirmed=True required to commit")
        if len(message) < 10:
            return SkillResult.fail("commit message must be at least 10 chars")

        if paths:
            for p in paths:
                try:
                    resolve_safe(p)
                except ValueError as e:
                    return SkillResult.fail(str(e))
            add_args = ["add", *paths]
        else:
            add_args = ["add", "-A"]

        rc, _, err = await _git(*add_args)
        if rc != 0:
            return SkillResult.fail(f"git add failed: {err.strip()}")

        rc, out, err = await _git("commit", "-m", message)
        if rc != 0:
            return SkillResult.fail(f"git commit failed: {(err or out).strip()}")

        rc, hash_out, _ = await _git("rev-parse", "--short", "HEAD")
        commit_hash = hash_out.strip() if rc == 0 else ""

        try:
            import neuros.memory.manager as mm

            if mm.manager is not None:
                await mm.manager.store(
                    f"Git commit: {message}",
                    {"source": "git", "hash": commit_hash},
                )
        except Exception as e:
            logger.debug("git_commit: memory store skipped: %s", e)

        return SkillResult.ok(
            {
                "committed": True,
                "message": message,
                "hash": commit_hash,
                "files": list(paths),
            },
            skill_name=self.name,
        )


@skill("git_push", "Push current branch to remote (never pushes to main)")
class GitPushSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        confirmed = params.get("confirmed", False)
        if confirmed is not True:
            return SkillResult.fail("confirmed=True required to push")

        branch = await _current_branch()
        if branch in {"main", "master"}:
            return SkillResult.fail(f"refusing to push protected branch: {branch}")
        if not branch:
            return SkillResult.fail("could not determine current branch")

        rc, out, err = await _git("push", "-u", "origin", branch, timeout=60.0)
        if rc != 0:
            return SkillResult.fail(f"git push failed: {(err or out).strip()}")

        return SkillResult.ok(
            {"pushed": True, "branch": branch, "remote": "origin"}, skill_name=self.name
        )
