"""SSH skill — async command execution on remote hosts via paramiko."""

from __future__ import annotations

import asyncio
import logging
import os

import paramiko

from neuros.config import settings
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.infra.ssh")


class SSHConnection:
    """Persistent SSH client wrapper."""

    def __init__(self, host: str) -> None:
        self.host = host
        self._client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        """Establish SSH connection using pre-shared keys."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key_path = os.path.expanduser(settings.ssh_key_path)
        self._client.connect(
            hostname=self.host,
            username="neuros",  # adjust as needed
            key_filename=key_path,
            timeout=10,
        )

    def execute(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """Run a command on the remote host. Returns (stdout, stderr, exit_code)."""
        if self._client is None:
            self.connect()
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        return stdout.read().decode(), stderr.read().decode(), stdout.channel.recv_exit_status()

    def close(self) -> None:
        if self._client:
            self._client.close()


@skill("ssh", "Execute commands on remote servers via SSH")
class SSHSkill(BaseSkill):
    """Run commands on lts1, lts2, or nas."""

    async def run(self, **params) -> SkillResult:
        host = params.get("host", "")
        command = params.get("command", "")

        if not host or not command:
            return SkillResult.fail("Both 'host' and 'command' are required")

        allowed_hosts = {settings.lts1_host, settings.lts2_host, settings.nas_host}
        if host not in allowed_hosts:
            return SkillResult.fail(f"Host '{host}' not configured. Allowed: {allowed_hosts}")

        try:
            conn = SSHConnection(host)
            # Run in thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            stdout, stderr, exit_code = await loop.run_in_executor(None, conn.execute, command)
            conn.close()

            if exit_code != 0:
                return SkillResult.fail(f"Exit code {exit_code}: {stderr.strip()}")
            return SkillResult.ok({"stdout": stdout.strip(), "host": host})
        except Exception as exc:
            return SkillResult.fail(str(exc))
