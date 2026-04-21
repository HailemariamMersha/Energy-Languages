"""Executor protocol and result dataclass."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass
class ExecResult:
    """Outcome of a single command execution."""

    returncode: int
    stdout: str
    stderr: str
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Executor(Protocol):
    """Abstract execution backend.

    Implementations must be safe to reuse across many ``run`` calls.
    File-transfer methods are provided so the harness can stage
    generated source files onto a remote host before invoking the
    existing CLBG Makefiles.
    """

    def run(
        self,
        cmd: str | Sequence[str],
        cwd: str | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        ...

    def put_file(self, local: str, remote: str) -> None:
        ...

    def get_file(self, remote: str, local: str) -> None:
        ...

    def exists(self, path: str) -> bool:
        ...

    def probe_arch(self) -> str:
        """Return the CPU arch triple of the host this executor talks to.

        Values use the short GNU triple form, e.g. ``"x86_64-linux-gnu"``
        or ``"aarch64-linux-gnu"``. The build container uses this value
        to pick the right cross-compile toolchain when the harness is
        asked to build for ``target_arch="auto"``.
        """
        ...

    def close(self) -> None:
        ...
