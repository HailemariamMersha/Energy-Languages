"""Runtime provenance capture for PerfArena.

Every generated sample and every measurement row should be able to
answer the question "which exact PerfArena image and which exact
PerfArena source tree produced this number". This module reads the
few pieces of that answer that live outside the package itself and
returns them as a dict ready for inclusion in the meta.json sidecar.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


def _env(name: str, default: str = "unknown") -> str:
    value = os.environ.get(name)
    return value if value else default


@lru_cache(maxsize=1)
def _git_sha_from_source() -> str | None:
    """Best-effort ``git rev-parse HEAD`` against the package source tree."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip()
    return None


@lru_cache(maxsize=1)
def _toolchain_file() -> dict[str, str]:
    """Parse ``/etc/perfarena-versions`` written by the Dockerfile."""
    path = Path("/etc/perfarena-versions")
    if not path.exists():
        return {}
    parsed: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            parsed[key.strip()] = value.strip()
        else:
            parsed.setdefault("raw", "")
            parsed["raw"] += line + "\n"
    return parsed


def capture() -> dict[str, Any]:
    """Return the runtime provenance block for inclusion in meta.json."""
    git_sha = _env("PERFARENA_GIT_SHA", "")
    if not git_sha or git_sha == "unknown":
        live = _git_sha_from_source()
        if live:
            git_sha = live
    return {
        "git_sha": git_sha or "unknown",
        "image_tag": _env("PERFARENA_IMAGE_TAG"),
        "image_build_date": _env("PERFARENA_BUILD_DATE"),
        "container_hostname": _env("HOSTNAME", ""),
        "toolchains": _toolchain_file(),
    }
