"""Rewrite the fork's per-benchmark Makefiles to use perfarena.mk.

The original greensoftwarelab/Energy-Languages Makefiles hardcode
2017-era compiler paths (``/usr/local/src/Python-3.6.1/bin/python3.6``,
``/usr/local/src/jdk1.8.0_121/bin/javac``, etc.). This tool walks
the fork, inspects each benchmark cell Makefile, and rewrites it
so that it delegates to the common ``perfarena.mk`` include. Each
rewrite uses a per-language template that understands how that
language's build step works and how it should express itself in
terms of the cross-compile environment variables that the PerfArena
harness exports.

Design notes
------------

- **Idempotent.** Re-running the tool on an already-patched Makefile
  is a no-op.
- **Reversible.** Before overwriting any Makefile the tool writes a
  ``Makefile.orig`` sidecar. Restore via ``mv Makefile.orig Makefile``
  or ``git checkout``.
- **Scope-limited.** Only the ten PerfArena target languages are
  touched. Everything else in the fork is left alone.
- **Per-language inference.** For each language we look at the
  source files present in the cell and the text of the existing
  Makefile to pick the source filename, the output binary name,
  and the default N argument. When inference fails the Makefile is
  skipped and the reason is printed.

Run it:

    perfarena patch-makefiles
    perfarena patch-makefiles --repo /workspace --dry-run
    perfarena patch-makefiles --languages python,cpp,rust,go
    perfarena patch-makefiles --languages python --problems binary-trees
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml


# ---------------------------------------------------------------- types


@dataclass
class PatchResult:
    cell: Path
    status: str  # "patched", "skipped", "already-patched", "no-source"
    reason: str = ""


# ---------------------------------------------------------------- problem metadata


def _load_problem_meta() -> dict[str, dict[str, Any]]:
    """Load per-problem metadata from problems.yaml."""
    cfg_path = Path(__file__).resolve().parent.parent / "configs" / "problems.yaml"
    raw = yaml.safe_load(cfg_path.read_text())
    return {p["key"]: p for p in raw["problems"]}


_PROBLEM_META: dict[str, dict[str, Any]] | None = None


def _get_problem_meta() -> dict[str, dict[str, Any]]:
    global _PROBLEM_META
    if _PROBLEM_META is None:
        _PROBLEM_META = _load_problem_meta()
    return _PROBLEM_META


def _validation_block(problem_key: str) -> str:
    """Return the Makefile lines for VALIDATION_N, REFERENCE_OUTPUT,
    STDIN_FILE, and BINARY_OUTPUT for a given problem."""
    meta = _get_problem_meta().get(problem_key, {})
    lines: list[str] = []
    vn = meta.get("validation_n", "")
    if vn:
        lines.append(f"VALIDATION_N       = {vn}")
    ref = meta.get("reference_output", "")
    if ref:
        lines.append(f"REFERENCE_OUTPUT   = ../../{ref}")
    if meta.get("needs_stdin"):
        stdin_file = meta.get("stdin_input_file", "")
        if stdin_file:
            lines.append(f"STDIN_FILE         = ../../{stdin_file}")
    if meta.get("binary_output"):
        lines.append("BINARY_OUTPUT      = 1")
    return "\n".join(lines)


# ---------------------------------------------------------------- helpers


_NUMERIC_ARG_RE = re.compile(r"\b(\d{2,})\b")


def _infer_arg(makefile_text: str, default: str) -> str:
    """Pick the N argument from the measure/run lines of an existing Makefile."""
    for line in makefile_text.splitlines():
        if "make " in line:
            continue
        m = _NUMERIC_ARG_RE.findall(line)
        if m:
            # Prefer the largest number, which is almost always the
            # CLBG default argument. Skip version numbers by ignoring
            # anything less than 10.
            best = max((int(x) for x in m if int(x) >= 10), default=None)
            if best is not None:
                return str(best)
    return default


def _already_patched(text: str) -> bool:
    return "include ../../perfarena.mk" in text


def _first_file_matching(cell: Path, patterns: list[str]) -> str | None:
    for pattern in patterns:
        matches = sorted(cell.glob(pattern))
        if matches:
            return matches[0].name
    return None


def _finalize(body: str, cell_name: str) -> str:
    """Append validation metadata and the include line."""
    vblock = _validation_block(cell_name)
    parts = [body.rstrip()]
    if vblock:
        parts.append("")
        parts.append(vblock)
    parts.append("")
    parts.append("include ../../perfarena.mk\n")
    return "\n".join(parts)


# ---------------------------------------------------------------- language rewriters


def _rewrite_python(cell: Path, original: str) -> str | None:
    source = _first_file_matching(
        cell,
        ["*.python3", "*.py"],
    )
    if source is None:
        return None
    stem = source.split(".")[0]
    output = f"{stem}.py"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG        = Python\n"
        f"TEST        = {cell.name}\n"
        f"SOURCE      = {source}\n"
        f"OUTPUT      = {output}\n"
        f"ARG         = {arg}\n"
        f"RUN_CMD     = python3 -OO $(OUTPUT) $(ARG)\n"
        f"COMPILE_CMD = cp $(SOURCE) $(OUTPUT)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_cpp(cell: Path, original: str) -> str | None:
    source = _first_file_matching(
        cell,
        ["*.gpp-*.c++", "*.cpp", "*.cc", "*.c++"],
    )
    if source is None:
        return None
    output = f"{cell.name}.gpp_run"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG    = C++\n"
        f"TEST    = {cell.name}\n"
        f"SOURCE  = {source}\n"
        f"OUTPUT  = {output}\n"
        f"ARG     = {arg}\n"
        f"RUN_CMD = ./$(OUTPUT) $(ARG)\n"
        f"\n"
        f"CXXFLAGS ?= -O3 -fomit-frame-pointer -std=c++14 -fopenmp\n"
        f"\n"
        f"COMPILE_CMD = $(CXX) $(CXXFLAGS) $(SOURCE) -o $(OUTPUT)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_rust(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.rs"])
    if source is None:
        return None
    output = f"{cell.name}.rust_run"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG    = Rust\n"
        f"TEST    = {cell.name}\n"
        f"SOURCE  = {source}\n"
        f"OUTPUT  = {output}\n"
        f"ARG     = {arg}\n"
        f"RUN_CMD = ./$(OUTPUT) $(ARG)\n"
        f"\n"
        f"RUSTC       ?= rustc\n"
        f"RUSTC_FLAGS ?= -C opt-level=3 -C lto\n"
        f"\n"
        f"ifneq ($(CARGO_BUILD_TARGET),)\n"
        f"  RUSTC_TARGET_FLAG = --target $(CARGO_BUILD_TARGET)\n"
        f"else\n"
        f"  RUSTC_TARGET_FLAG =\n"
        f"endif\n"
        f"\n"
        f"COMPILE_CMD = $(RUSTC) $(RUSTC_FLAGS) $(RUSTC_TARGET_FLAG) $(SOURCE) -o $(OUTPUT)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_go(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.go"])
    if source is None:
        return None
    output = f"{cell.name}.go_run"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG    = Go\n"
        f"TEST    = {cell.name}\n"
        f"SOURCE  = {source}\n"
        f"OUTPUT  = {output}\n"
        f"ARG     = {arg}\n"
        f"RUN_CMD = ./$(OUTPUT) $(ARG)\n"
        f"\n"
        f"COMPILE_CMD = go build -o $(OUTPUT) $(SOURCE)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_java(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.java-*.java", "*.java"])
    if source is None:
        return None
    # Assume the benchmark uses a class named after the file stem.
    class_name = source.split(".")[0]
    arg = _infer_arg(original, "21")
    body = (
        f"LANG    = Java\n"
        f"TEST    = {cell.name}\n"
        f"SOURCE  = {source}\n"
        f"OUTPUT  = {class_name}.class\n"
        f"ARG     = {arg}\n"
        f"RUN_CMD = java {class_name} $(ARG)\n"
        f"\n"
        f"JAVAC ?= javac\n"
        f"\n"
        f"COMPILE_CMD = cp $(SOURCE) {class_name}.java && $(JAVAC) -d . {class_name}.java\n"
    )
    return _finalize(body, cell.name)


def _rewrite_javascript(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.node", "*.js"])
    if source is None:
        return None
    output = f"{cell.name}.js"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG        = JavaScript\n"
        f"TEST        = {cell.name}\n"
        f"SOURCE      = {source}\n"
        f"OUTPUT      = {output}\n"
        f"ARG         = {arg}\n"
        f"RUN_CMD     = node --use_strict $(OUTPUT) $(ARG)\n"
        f"COMPILE_CMD = cp $(SOURCE) $(OUTPUT)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_typescript(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.typescript-*.ts", "*.ts"])
    if source is None:
        return None
    js_output = f"{cell.name}.js"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG        = TypeScript\n"
        f"TEST        = {cell.name}\n"
        f"SOURCE      = {source}\n"
        f"OUTPUT      = {js_output}\n"
        f"ARG         = {arg}\n"
        f"RUN_CMD     = node $(OUTPUT) $(ARG)\n"
        f"\n"
        f"TSC ?= tsc\n"
        f"\n"
        f"COMPILE_CMD = $(TSC) --target es2020 --outFile $(OUTPUT) $(SOURCE)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_csharp(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.cs"])
    if source is None:
        return None
    output = f"bin/Release/{cell.name}"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG    = CSharp\n"
        f"TEST    = {cell.name}\n"
        f"SOURCE  = {source}\n"
        f"OUTPUT  = {output}\n"
        f"ARG     = {arg}\n"
        f"RUN_CMD = dotnet run --configuration Release -- $(ARG)\n"
        f"\n"
        f"COMPILE_CMD = dotnet build --configuration Release --nologo\n"
    )
    return _finalize(body, cell.name)


def _rewrite_php(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.php-*.php", "*.php"])
    if source is None:
        return None
    output = f"{cell.name}.php"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG        = PHP\n"
        f"TEST        = {cell.name}\n"
        f"SOURCE      = {source}\n"
        f"OUTPUT      = {output}\n"
        f"ARG         = {arg}\n"
        f"RUN_CMD     = php -n -d memory_limit=2G $(OUTPUT) $(ARG)\n"
        f"COMPILE_CMD = cp $(SOURCE) $(OUTPUT)\n"
    )
    return _finalize(body, cell.name)


def _rewrite_ruby(cell: Path, original: str) -> str | None:
    source = _first_file_matching(cell, ["*.jruby", "*.yarv", "*.rb"])
    if source is None:
        return None
    output = f"{cell.name}.rb"
    arg = _infer_arg(original, "21")
    body = (
        f"LANG        = Ruby\n"
        f"TEST        = {cell.name}\n"
        f"SOURCE      = {source}\n"
        f"OUTPUT      = {output}\n"
        f"ARG         = {arg}\n"
        f"RUN_CMD     = ruby $(OUTPUT) $(ARG)\n"
        f"COMPILE_CMD = cp $(SOURCE) $(OUTPUT)\n"
    )
    return _finalize(body, cell.name)


# Mapping: canonical language folder name -> rewriter.
LANGUAGE_REWRITERS: dict[str, Callable[[Path, str], str | None]] = {
    "Python": _rewrite_python,
    "C++": _rewrite_cpp,
    "Rust": _rewrite_rust,
    "Go": _rewrite_go,
    "Java": _rewrite_java,
    "JavaScript": _rewrite_javascript,
    "TypeScript": _rewrite_typescript,
    "CSharp": _rewrite_csharp,
    "PHP": _rewrite_php,
    "Ruby": _rewrite_ruby,
}


# Map CLI --languages keys back to the canonical folder names.
_KEY_TO_FOLDER = {
    "python": "Python",
    "cpp": "C++",
    "rust": "Rust",
    "go": "Go",
    "java": "Java",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "csharp": "CSharp",
    "php": "PHP",
    "ruby": "Ruby",
}


# ---------------------------------------------------------------- entry point


def patch_one(cell: Path, rewriter: Callable[[Path, str], str | None], *, dry_run: bool) -> PatchResult:
    mf = cell / "Makefile"
    if not mf.exists():
        return PatchResult(cell=cell, status="skipped", reason="no Makefile")
    original = mf.read_text()
    if _already_patched(original):
        return PatchResult(cell=cell, status="already-patched")
    new_text = rewriter(cell, original)
    if new_text is None:
        return PatchResult(cell=cell, status="no-source", reason="source file not found")
    if dry_run:
        return PatchResult(cell=cell, status="patched", reason="(dry-run)")
    backup = cell / "Makefile.orig"
    if not backup.exists():
        backup.write_text(original)
    mf.write_text(new_text)
    return PatchResult(cell=cell, status="patched")


def walk_and_patch(
    repo_root: Path,
    language_folders: list[str],
    problem_keys: list[str] | None,
    dry_run: bool,
) -> list[PatchResult]:
    results: list[PatchResult] = []
    for folder in language_folders:
        lang_dir = repo_root / folder
        if not lang_dir.is_dir():
            continue
        rewriter = LANGUAGE_REWRITERS.get(folder)
        if rewriter is None:
            continue
        for cell in sorted(p for p in lang_dir.iterdir() if p.is_dir()):
            if problem_keys and cell.name not in problem_keys:
                continue
            results.append(patch_one(cell, rewriter, dry_run=dry_run))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="perfarena-patch-makefiles")
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the Energy-Languages fork root. Defaults to cwd.",
    )
    parser.add_argument(
        "--languages",
        default="",
        help=(
            "Comma-separated language keys to patch. "
            "Defaults to the full PerfArena slate."
        ),
    )
    parser.add_argument(
        "--problems",
        default="",
        help="Comma-separated CLBG problem keys to patch. Defaults to all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; just report what would change.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).resolve()

    if args.languages:
        keys = [k.strip() for k in args.languages.split(",") if k.strip()]
        folders = [_KEY_TO_FOLDER[k] for k in keys if k in _KEY_TO_FOLDER]
    else:
        folders = list(_KEY_TO_FOLDER.values())

    problem_keys = (
        [p.strip() for p in args.problems.split(",") if p.strip()]
        if args.problems
        else None
    )

    results = walk_and_patch(repo_root, folders, problem_keys, args.dry_run)
    for r in results:
        note = f" ({r.reason})" if r.reason else ""
        print(f"{r.status:16s} {r.cell}{note}")

    summary: dict[str, int] = {}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    print()
    print("summary:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
