"""Execution backends for the PerfArena harness.

Two backends are provided:

- :class:`LocalExecutor` runs commands in the current process or
  inside the PerfArena container. Portable but pays a small
  "container tax" and does not have privileged RAPL access.
  Intended for smoke tests, CI, and the portability column of the
  leaderboard.
- :class:`SSHExecutor` forwards commands to a remote bare-metal
  host over SSH. Intended for publishable measurements, where the
  container is the orchestrator and execution happens on metal.
"""
from __future__ import annotations

from .base import ExecResult, Executor
from .local import LocalExecutor
from .ssh import SSHExecutor

__all__ = [
    "Executor",
    "ExecResult",
    "LocalExecutor",
    "SSHExecutor",
    "from_config",
]


def from_config(config: dict) -> Executor:
    """Build an executor from a plain-dict config.

    Expected shapes:

        {"type": "local"}
        {"type": "ssh", "host": "lab1.example", "user": "perfarena",
         "key_path": "~/.ssh/perfarena", "port": 22}
    """
    kind = (config.get("type") or "local").lower()
    if kind == "local":
        return LocalExecutor()
    if kind == "ssh":
        return SSHExecutor(
            host=config["host"],
            user=config["user"],
            port=int(config.get("port", 22)),
            key_path=config.get("key_path"),
            password=config.get("password"),
        )
    raise ValueError(f"Unknown executor type: {kind!r}")
