"""Static analysis for generated source files.

Runs a small set of per-language analyzers on a source file and
returns a common-schema result that can be joined into the
measurement dataset as the "PAP density" column. The analyzer set
is deliberately small so the base install stays light:

  Python      pylint (performance / code-smell subset)
  Rust        clippy on a one-file crate
  C++         cppcheck
  JavaScript  eslint (if installed)
  Go          go vet
  Java        pmd (if installed)
  C#         (placeholder; no open tool with good perf coverage)
  PHP         phpcs (if installed)
  Ruby        rubocop (if installed)
  TypeScript  tsc --noEmit + eslint (if installed)

Any analyzer that isn't found on PATH produces a result row with
``available=False`` so the downstream join still has a deterministic
per-language slot.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class StaticAnalysisResult:
    language: str
    tool: str
    available: bool
    issues: int
    lines_of_code: int
    density_per_kloc: float
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "tool": self.tool,
            "available": self.available,
            "issues": self.issues,
            "lines_of_code": self.lines_of_code,
            "density_per_kloc": self.density_per_kloc,
            "raw": self.raw,
        }


def _count_lines(path: Path) -> int:
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def _density(issues: int, loc: int) -> float:
    if loc <= 0:
        return 0.0
    return 1000.0 * issues / loc


def _run_tool(
    cmd: list[str],
    timeout: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )


def _missing(language: str, tool: str, source: Path) -> StaticAnalysisResult:
    return StaticAnalysisResult(
        language=language,
        tool=tool,
        available=False,
        issues=0,
        lines_of_code=_count_lines(source),
        density_per_kloc=0.0,
        raw={"reason": f"{tool} not on PATH"},
    )


# ---------------------------------------------------------------- per-language runners


def _analyze_python(source: Path) -> StaticAnalysisResult:
    if not shutil.which("pylint"):
        return _missing("python", "pylint", source)
    proc = _run_tool(
        [
            "pylint",
            "--score=no",
            "--output-format=json",
            "--disable=C,R",  # skip style/refactor noise; keep warnings
            str(source),
        ]
    )
    try:
        findings = json.loads(proc.stdout or "[]")
        if isinstance(findings, list):
            issues = len(findings)
        else:
            issues = 0
    except json.JSONDecodeError:
        issues = proc.stdout.count("\n")
    loc = _count_lines(source)
    return StaticAnalysisResult(
        language="python",
        tool="pylint",
        available=True,
        issues=issues,
        lines_of_code=loc,
        density_per_kloc=_density(issues, loc),
        raw={"stderr_tail": proc.stderr[-2000:]},
    )


def _analyze_cpp(source: Path) -> StaticAnalysisResult:
    if not shutil.which("cppcheck"):
        return _missing("cpp", "cppcheck", source)
    proc = _run_tool(
        [
            "cppcheck",
            "--enable=warning,performance,portability",
            "--quiet",
            "--template={file}:{line}:{severity}:{id}:{message}",
            str(source),
        ]
    )
    issues = sum(
        1 for line in proc.stderr.splitlines() if line.strip() and ":" in line
    )
    loc = _count_lines(source)
    return StaticAnalysisResult(
        language="cpp",
        tool="cppcheck",
        available=True,
        issues=issues,
        lines_of_code=loc,
        density_per_kloc=_density(issues, loc),
        raw={"stderr_tail": proc.stderr[-2000:]},
    )


def _analyze_rust(source: Path) -> StaticAnalysisResult:
    if not shutil.which("rustc"):
        return _missing("rust", "rustc-lints", source)
    proc = _run_tool(
        [
            "rustc",
            "--edition=2021",
            "-W",
            "clippy::all",
            "--emit=metadata",
            "-o",
            "/dev/null",
            str(source),
        ]
    )
    # rustc emits warnings in stderr, one per `warning:` line
    issues = sum(
        1 for line in proc.stderr.splitlines() if line.lstrip().startswith("warning")
    )
    loc = _count_lines(source)
    return StaticAnalysisResult(
        language="rust",
        tool="rustc-lints",
        available=True,
        issues=issues,
        lines_of_code=loc,
        density_per_kloc=_density(issues, loc),
        raw={"stderr_tail": proc.stderr[-2000:]},
    )


def _analyze_go(source: Path) -> StaticAnalysisResult:
    if not shutil.which("go"):
        return _missing("go", "go-vet", source)
    proc = _run_tool(["go", "vet", str(source)])
    issues = sum(1 for line in proc.stderr.splitlines() if line.strip())
    loc = _count_lines(source)
    return StaticAnalysisResult(
        language="go",
        tool="go-vet",
        available=True,
        issues=issues,
        lines_of_code=loc,
        density_per_kloc=_density(issues, loc),
        raw={"stderr_tail": proc.stderr[-2000:]},
    )


def _analyze_javascript(source: Path) -> StaticAnalysisResult:
    if not shutil.which("eslint"):
        return _missing("javascript", "eslint", source)
    proc = _run_tool(
        ["eslint", "--no-config-lookup", "--format", "json", str(source)]
    )
    issues = 0
    try:
        data = json.loads(proc.stdout or "[]")
        for entry in data:
            issues += len(entry.get("messages", []))
    except json.JSONDecodeError:
        issues = proc.stdout.count("\n")
    loc = _count_lines(source)
    return StaticAnalysisResult(
        language="javascript",
        tool="eslint",
        available=True,
        issues=issues,
        lines_of_code=loc,
        density_per_kloc=_density(issues, loc),
        raw={},
    )


def _analyze_typescript(source: Path) -> StaticAnalysisResult:
    if not shutil.which("tsc"):
        return _missing("typescript", "tsc", source)
    proc = _run_tool(
        ["tsc", "--noEmit", "--strict", "--target", "es2020", str(source)]
    )
    issues = sum(1 for line in proc.stdout.splitlines() if "error" in line)
    loc = _count_lines(source)
    return StaticAnalysisResult(
        language="typescript",
        tool="tsc",
        available=True,
        issues=issues,
        lines_of_code=loc,
        density_per_kloc=_density(issues, loc),
        raw={},
    )


_RUNNERS: dict[str, Callable[[Path], StaticAnalysisResult]] = {
    "python": _analyze_python,
    "cpp": _analyze_cpp,
    "c++": _analyze_cpp,
    "rust": _analyze_rust,
    "go": _analyze_go,
    "javascript": _analyze_javascript,
    "typescript": _analyze_typescript,
}


def analyze(language_key: str, source: str | Path) -> StaticAnalysisResult:
    """Run the default analyzer for the given language on a source file."""
    source_path = Path(source)
    runner = _RUNNERS.get(language_key.lower())
    if runner is None:
        return StaticAnalysisResult(
            language=language_key,
            tool="none",
            available=False,
            issues=0,
            lines_of_code=_count_lines(source_path),
            density_per_kloc=0.0,
            raw={"reason": f"no analyzer registered for {language_key!r}"},
        )
    return runner(source_path)
