"""Tests for infrastructure skills."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_ssh_skill_missing_params() -> None:
    """SSH skill requires host and command."""
    from neuros.skills.infra.ssh import SSHSkill

    skill = SSHSkill()

    result = await skill.run()
    assert not result.success
    assert "required" in (result.error or "")


@pytest.mark.asyncio
async def test_ssh_skill_disallowed_host() -> None:
    """SSH skill rejects unconfigured hosts."""
    from neuros.skills.infra.ssh import SSHSkill

    skill = SSHSkill()
    result = await skill.run(host="evil.com", command="rm -rf /")
    assert not result.success
    assert "not configured" in (result.error or "")


@pytest.mark.asyncio
async def test_gpu_server_skill_unknown_action() -> None:
    """GPU server skill rejects unknown actions."""
    from neuros.skills.infra.gpu_server import GPUServerSkill

    skill = GPUServerSkill()
    result = await skill.run(action="invalid")
    assert not result.success


@pytest.mark.asyncio
async def test_nas_skill_unknown_action() -> None:
    """NAS skill rejects unknown actions."""
    from neuros.skills.infra.nas import NASSkill

    skill = NASSkill()
    result = await skill.run(action="invalid")
    assert not result.success


@pytest.mark.asyncio
async def test_nas_skill_requires_password() -> None:
    """NAS skill fails gracefully when NAS_PASSWORD is not configured."""
    from neuros.skills.infra.nas import NASSkill

    skill = NASSkill()
    result = await skill.run(action="browse", path="/home")
    # Without NAS_PASSWORD set, expect a clean failure not a crash
    assert result.success is False
    assert "NAS_PASSWORD" in (result.error or "")
