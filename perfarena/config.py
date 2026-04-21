"""Config loader for PerfArena (problems, languages, paths)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProblemSpec:
    """A CLBG problem in the PerfArena set."""

    key: str
    name: str
    description: str
    input_spec: str
    output_spec: str
    default_argument: str
    invocation_hint: str
    algorithm_class: str = ""
    needs_stdin: bool = False
    stdin_input_file: str = ""
    validation_n: str = ""
    reference_output: str = ""
    binary_output: bool = False


@dataclass
class LanguageSpec:
    """A target programming language.

    The ``folder`` field matches the directory name inside the
    greensoftwarelab/Energy-Languages fork, so the harness can drop
    generated source files into the existing CLBG tree.
    """

    key: str
    display_name: str
    folder: str
    file_extension: str
    paradigm: str = ""


@dataclass
class PerfArenaConfig:
    """Top-level config bundle."""

    repo_root: Path
    prompts_dir: Path
    configs_dir: Path
    generations_dir: Path
    problems: dict[str, ProblemSpec] = field(default_factory=dict)
    languages: dict[str, LanguageSpec] = field(default_factory=dict)

    def get_problem(self, key: str) -> ProblemSpec:
        if key not in self.problems:
            raise KeyError(
                f"Unknown problem: {key!r}. Known problems: {sorted(self.problems)}"
            )
        return self.problems[key]

    def get_language(self, key: str) -> LanguageSpec:
        if key not in self.languages:
            raise KeyError(
                f"Unknown language: {key!r}. Known languages: {sorted(self.languages)}"
            )
        return self.languages[key]


def load_config(repo_root: str | Path | None = None) -> PerfArenaConfig:
    """Load PerfArena config from the package's bundled YAML files.

    ``repo_root`` should point at the root of the Energy-Languages
    fork (the directory that contains ``Python/``, ``C++/``, etc.).
    If omitted it defaults to the parent of the installed
    ``perfarena`` package, which corresponds to the bind-mounted
    ``/workspace`` directory inside the PerfArena container.
    """
    pkg_root = Path(__file__).resolve().parent
    prompts_dir = pkg_root / "prompts"
    configs_dir = pkg_root / "configs"

    if repo_root is None:
        # When perfarena is installed and run from inside the
        # container with the fork bind-mounted at /workspace, this
        # is the right default.
        ws = Path("/workspace")
        repo_root = ws if ws.exists() else pkg_root.parent
    repo_root = Path(repo_root).resolve()

    generations_dir = repo_root / "perfarena_out" / "generations"

    with (configs_dir / "problems.yaml").open() as fh:
        problems_raw: dict[str, Any] = yaml.safe_load(fh)
    with (configs_dir / "languages.yaml").open() as fh:
        languages_raw: dict[str, Any] = yaml.safe_load(fh)

    problems = {
        entry["key"]: ProblemSpec(**entry) for entry in problems_raw["problems"]
    }
    languages = {
        entry["key"]: LanguageSpec(**entry) for entry in languages_raw["languages"]
    }

    return PerfArenaConfig(
        repo_root=repo_root,
        prompts_dir=prompts_dir,
        configs_dir=configs_dir,
        generations_dir=generations_dir,
        problems=problems,
        languages=languages,
    )
