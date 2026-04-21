"""SSHExecutor: forward commands to a remote bare-metal host."""
from __future__ import annotations

import shlex
import time
from pathlib import Path
from typing import Sequence

import paramiko

from .base import ExecResult


class SSHExecutor:
    """Run commands on a remote host over SSH.

    Intended for forwarding measurement workloads from the
    PerfArena container to the bare-metal reference host
    configured per Section 5.1 of the proposal. Authentication
    defaults to SSH-agent + system known_hosts; a ``key_path`` or
    ``password`` may be supplied explicitly for CI contexts.
    """

    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        key_path: str | None = None,
        password: str | None = None,
    ) -> None:
        self.host = host
        self.user = user
        self.port = port
        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        # WarningPolicy prints a warning but still connects; harder to
        # accidentally trust a new key in production than RejectPolicy,
        # softer than AutoAddPolicy for demos.
        self._client.set_missing_host_key_policy(paramiko.WarningPolicy())
        self._client.connect(
            hostname=host,
            port=port,
            username=user,
            key_filename=key_path,
            password=password,
            look_for_keys=key_path is None and password is None,
            allow_agent=password is None,
        )
        self._sftp = self._client.open_sftp()

    def run(
        self,
        cmd: str | Sequence[str],
        cwd: str | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        if not isinstance(cmd, str):
            cmd = " ".join(shlex.quote(c) for c in cmd)

        full_cmd = cmd
        if env:
            env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            full_cmd = f"{env_prefix} {full_cmd}"
        if cwd:
            full_cmd = f"cd {shlex.quote(cwd)} && {full_cmd}"

        t0 = time.monotonic()
        _, stdout, stderr = self._client.exec_command(full_cmd, timeout=timeout)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        rc = stdout.channel.recv_exit_status()
        return ExecResult(
            returncode=rc,
            stdout=out,
            stderr=err,
            duration_s=time.monotonic() - t0,
        )

    def put_file(self, local: str, remote: str) -> None:
        remote_dir = str(Path(remote).parent)
        self.run(["mkdir", "-p", remote_dir])
        self._sftp.put(local, remote)

    def get_file(self, remote: str, local: str) -> None:
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        self._sftp.get(remote, local)

    def exists(self, path: str) -> bool:
        try:
            self._sftp.stat(path)
            return True
        except FileNotFoundError:
            return False

    def probe_arch(self) -> str:
        res = self.run(["sh", "-c", "uname -m && uname -s"])
        if res.returncode != 0:
            raise RuntimeError(
                f"probe_arch: could not run uname on {self.host}: {res.stderr}"
            )
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            raise RuntimeError(
                f"probe_arch: unexpected uname output on {self.host}: {res.stdout!r}"
            )
        machine, system = lines[0].lower(), lines[1].lower()
        if machine in ("x86_64", "amd64"):
            machine = "x86_64"
        elif machine in ("arm64", "aarch64"):
            machine = "aarch64"
        return f"{machine}-{system}-gnu"

    def close(self) -> None:
        try:
            self._sftp.close()
        finally:
            self._client.close()
