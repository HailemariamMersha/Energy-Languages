"""LocalExecutor: run commands in the current process / container."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Sequence

from .base import ExecResult


class LocalExecutor:
    """Execute commands on the local filesystem.

    Used either on the developer's workstation or inside the
    PerfArena container. Does not set up any sandboxing beyond
    whatever the ambient environment already provides.
    """

    def run(
        self,
        cmd: str | Sequence[str],
        cwd: str | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        if isinstance(cmd, str):
            args = shlex.split(cmd)
            use_shell = False
        else:
            args = list(cmd)
            use_shell = False

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                args,
                cwd=cwd,
                timeout=timeout,
                env=merged_env,
                shell=use_shell,
                capture_output=True,
                text=True,
            )
            return ExecResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_s=time.monotonic() - t0,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(
                returncode=124,
                stdout=exc.stdout.decode(errors="replace") if exc.stdout else "",
                stderr=(exc.stderr.decode(errors="replace") if exc.stderr else "")
                + f"\n[perfarena] LocalExecutor timeout after {timeout}s",
                duration_s=time.monotonic() - t0,
            )

    def put_file(self, local: str, remote: str) -> None:
        Path(remote).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, remote)

    def get_file(self, remote: str, local: str) -> None:
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(remote, local)

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def probe_arch(self) -> str:
        import platform

        machine = platform.machine().lower()
        # Common aliases.
        if machine in ("x86_64", "amd64"):
            machine = "x86_64"
        elif machine in ("arm64", "aarch64"):
            machine = "aarch64"
        system = platform.system().lower()  # "linux", "darwin", ...
        return f"{machine}-{system}-gnu"

    def close(self) -> None:
        # Nothing to release for the local executor.
        return None
