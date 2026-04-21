"""Harness: drive the CLBG Makefile contract over one or two executors.

The greensoftwarelab/Energy-Languages fork expresses each benchmark
as a per-language folder containing one sub-folder per CLBG problem,
each with a ``Makefile`` that implements the ``compile``, ``run``,
``measure``, ``mem``, and ``clean`` targets. The :class:`Harness`
class wraps that contract behind one or two :class:`Executor`
backends so the PerfArena pipeline can route the ``compile`` action
to the build container (for cross-compilation) and the
``run``/``measure``/``mem`` actions to a remote bare-metal host
(for measurement), with automatic SFTP-based staging of the built
artifacts in between.

Usage patterns
--------------

Single executor (backwards-compatible): compile and measure both
run on the same side, typical for smoke tests and CI.

    Harness(config, executor=LocalExecutor())

Two executors (the intended production layout for PerfArena): the
build container compiles, the bare-metal host measures.

    Harness(
        config,
        build_executor=LocalExecutor(),
        run_executor=SSHExecutor(host="perfarena-lab", user="perfarena"),
        run_repo_path="/opt/perfarena/Energy-Languages",
    )

When a build+run split is used, the harness will, after a
successful ``make compile`` on the build side, walk the cell
directory and stream every file to the run side via
:meth:`Executor.put_file` before any subsequent ``run``,
``measure`` or ``mem`` action. Files already present on the run
side are overwritten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

from .config import LanguageSpec, PerfArenaConfig, ProblemSpec
from .executors.base import ExecResult, Executor


@dataclass
class HarnessResult:
    language: str
    problem: str
    action: str
    cell_path: str
    result: ExecResult
    env: dict[str, str] = field(default_factory=dict)
    side: str = "build"  # "build" or "run"
    staged_files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.result.ok


VALID_ACTIONS = frozenset({"compile", "run", "measure", "mem", "clean", "validate"})

# Actions that live on the build side when build and run are split.
# Every other action routes to the run executor.
BUILD_SIDE_ACTIONS = frozenset({"compile", "validate"})


# Map a canonical GNU triple to the environment variables that the
# per-language build systems respect for cross-compilation. Languages
# not present in a given mapping produce arch-independent artifacts
# (Java bytecode, .NET IL, TypeScript-to-JS, interpreted sources) and
# need no per-arch variables.
_ARCH_BUILD_ENV: dict[str, dict[str, dict[str, str]]] = {
    "x86_64-linux-gnu": {
        "go": {"GOOS": "linux", "GOARCH": "amd64", "CGO_ENABLED": "0"},
        "rust": {"CARGO_BUILD_TARGET": "x86_64-unknown-linux-gnu"},
        "cpp": {"CC": "gcc", "CXX": "g++"},
    },
    "aarch64-linux-gnu": {
        "go": {"GOOS": "linux", "GOARCH": "arm64", "CGO_ENABLED": "0"},
        "rust": {"CARGO_BUILD_TARGET": "aarch64-unknown-linux-gnu"},
        "cpp": {
            "CC": "aarch64-linux-gnu-gcc",
            "CXX": "aarch64-linux-gnu-g++",
        },
    },
}


def build_env_for(language: str, target_arch: str) -> dict[str, str]:
    """Return the build-time env vars for (language, target_arch).

    Returns an empty dict when the language produces arch-independent
    artifacts, when the target is unknown, or when the language has
    no cross-compile entry for that target.
    """
    per_arch = _ARCH_BUILD_ENV.get(target_arch, {})
    return dict(per_arch.get(language, {}))


class Harness:
    """Drive compile/run/measure/mem/clean over the CLBG tree.

    Parameters
    ----------
    config:
        Loaded :class:`PerfArenaConfig`.
    executor:
        Single executor to use for every action. Backwards-compatible
        shortcut. Mutually exclusive with ``build_executor`` /
        ``run_executor``.
    build_executor:
        Executor to use for the ``compile`` action. Typically the
        :class:`LocalExecutor` running inside the PerfArena build
        container.
    run_executor:
        Executor to use for ``run``, ``measure``, and ``mem``.
        Typically an :class:`SSHExecutor` pointing at the bare-metal
        reference host.
    build_repo_path:
        Fork location on the build-executor filesystem.
    run_repo_path:
        Fork location on the run-executor filesystem.
    target_arch:
        ``"auto"`` (probe the run executor), or an explicit triple
        like ``"x86_64-linux-gnu"`` / ``"aarch64-linux-gnu"``.
    """

    def __init__(
        self,
        config: PerfArenaConfig,
        executor: Executor | None = None,
        *,
        build_executor: Executor | None = None,
        run_executor: Executor | None = None,
        remote_repo_path: str | None = None,
        build_repo_path: str | None = None,
        run_repo_path: str | None = None,
        target_arch: str = "auto",
    ) -> None:
        if executor is not None and (build_executor or run_executor):
            raise ValueError(
                "Pass either `executor` (single) or "
                "`build_executor` + `run_executor` (split), not both."
            )
        if executor is None and build_executor is None and run_executor is None:
            raise ValueError("Harness needs at least one executor.")

        self.config = config

        if executor is not None:
            self.build_executor: Executor = executor
            self.run_executor: Executor = executor
            self._split = False
            repo = remote_repo_path or str(config.repo_root)
            self.build_repo_path = repo
            self.run_repo_path = repo
        else:
            if build_executor is None or run_executor is None:
                raise ValueError(
                    "Split mode requires both `build_executor` and `run_executor`."
                )
            self.build_executor = build_executor
            self.run_executor = run_executor
            self._split = True
            self.build_repo_path = build_repo_path or str(config.repo_root)
            self.run_repo_path = run_repo_path or str(config.repo_root)

        self._target_arch = target_arch
        self._resolved_arch: str | None = None
        # Remember which cells have been staged during this Harness
        # instance so we don't re-ship the same directory twice.
        self._staged_cells: set[tuple[str, str]] = set()
        # Track the staged source filename per (language, problem) cell
        # so run_action can pass SOURCE= to make.
        self._staged_sources: dict[tuple[str, str], str] = {}

    # ---------------------------------------------------------------- target

    def resolve_target_arch(self) -> str:
        """Probe the run executor (the measurement host) for its arch."""
        if self._resolved_arch is not None:
            return self._resolved_arch
        if self._target_arch == "auto":
            self._resolved_arch = self.run_executor.probe_arch()
        else:
            self._resolved_arch = self._target_arch
        return self._resolved_arch

    # ------------------------------------------------------------------ paths

    def _cell_path_for(self, repo_path: str, language: str, problem: str) -> str:
        lang = self.config.get_language(language)
        return str(PurePosixPath(repo_path) / lang.folder / problem)

    def build_cell_path(self, language: str, problem: str) -> str:
        return self._cell_path_for(self.build_repo_path, language, problem)

    def run_cell_path(self, language: str, problem: str) -> str:
        return self._cell_path_for(self.run_repo_path, language, problem)

    def cell_path(self, language: str, problem: str) -> str:
        """Legacy single-side helper. Returns the run-side cell path."""
        return self.run_cell_path(language, problem)

    def ensure_source_staged(
        self,
        language: str,
        problem: str,
        local_source_path: str,
    ) -> str:
        """Copy a generated source file into the *build*-side cell directory.

        The destination filename follows the convention
        ``perfarena_generated<ext>``. Subsequent compile/validate/measure
        calls with ``use_staged=True`` override the Makefile's ``SOURCE``
        variable to point at this file instead of the human reference.
        """
        lang = self.config.get_language(language)
        cell = self.build_cell_path(language, problem)
        staged_name = f"perfarena_generated{lang.file_extension}"
        remote = str(PurePosixPath(cell) / staged_name)
        self.build_executor.put_file(local_source_path, remote)
        self._staged_sources[(language, problem)] = staged_name
        return remote

    # --------------------------------------------------------------- staging

    def _stage_build_artifacts_to_run(
        self,
        language: str,
        problem: str,
    ) -> list[str]:
        """Walk the build-side cell directory and ship every file to the run side.

        Used after a successful ``make compile`` in split mode, so
        that subsequent ``run``/``measure``/``mem`` calls on the run
        executor see the freshly-built artifacts. Only meaningful when
        the build executor is :class:`LocalExecutor`; otherwise we
        would need a build-side ``get_file`` first, which would
        defeat the point of the split. The method early-returns if
        called in non-split mode.
        """
        if not self._split:
            return []
        build_cell = Path(self.build_cell_path(language, problem))
        if not build_cell.exists():
            return []

        run_cell = self.run_cell_path(language, problem)
        self.run_executor.run(["mkdir", "-p", run_cell])

        shipped: list[str] = []
        for path in sorted(build_cell.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(build_cell)
            remote = str(PurePosixPath(run_cell) / str(rel).replace("\\", "/"))
            self.run_executor.put_file(str(path), remote)
            shipped.append(remote)
        self._staged_cells.add((language, problem))
        return shipped

    # ----------------------------------------------------------------- actions

    def run_action(
        self,
        language: str,
        problem: str,
        action: str,
        timeout: float = 600.0,
        env: dict[str, str] | None = None,
        stage_after_compile: bool = True,
        use_staged: bool = True,
    ) -> HarnessResult:
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"Unknown action {action!r}. Valid actions: {sorted(VALID_ACTIONS)}"
            )
        # Resolve language/problem so we raise on unknown keys.
        _lang: LanguageSpec = self.config.get_language(language)
        _prob: ProblemSpec = self.config.get_problem(problem)
        del _lang, _prob

        on_build_side = action in BUILD_SIDE_ACTIONS
        executor = self.build_executor if on_build_side else self.run_executor
        cell = (
            self.build_cell_path(language, problem)
            if on_build_side
            else self.run_cell_path(language, problem)
        )
        side = "build" if on_build_side else "run"

        merged_env = dict(env) if env else {}
        if action == "compile":
            arch = self.resolve_target_arch()
            merged_env.setdefault("PERFARENA_TARGET_ARCH", arch)
            for key, value in build_env_for(language, arch).items():
                merged_env.setdefault(key, value)

        # If LLM-generated code was staged for this cell, override the
        # Makefile's SOURCE variable so compile/validate/measure use the
        # generated file instead of the human reference.
        staged_name = self._staged_sources.get((language, problem))
        if use_staged and staged_name:
            make_args.append(f"SOURCE={staged_name}")

        res = executor.run(
            make_args,
            cwd=cell,
            timeout=timeout,
            env=merged_env or None,
        )

        staged: list[str] = []
        if (
            action == "compile"
            and res.ok
            and self._split
            and stage_after_compile
        ):
            staged = self._stage_build_artifacts_to_run(language, problem)

        return HarnessResult(
            language=language,
            problem=problem,
            action=action,
            cell_path=cell,
            result=res,
            env=merged_env,
            side=side,
            staged_files=staged,
        )

    def run_all(
        self,
        action: str,
        languages: Iterable[str] | None = None,
        problems: Iterable[str] | None = None,
        timeout: float = 600.0,
        env: dict[str, str] | None = None,
    ) -> list[HarnessResult]:
        langs = list(languages) if languages else list(self.config.languages)
        probs = list(problems) if problems else list(self.config.problems)
        results: list[HarnessResult] = []
        for lang in langs:
            for prob in probs:
                results.append(
                    self.run_action(lang, prob, action, timeout=timeout, env=env)
                )
        return results

    def compile_validate_then_measure(
        self,
        language: str,
        problem: str,
        timeout: float = 600.0,
    ) -> list[HarnessResult]:
        """Convenience: compile, validate correctness, then measure.

        The validate step runs the benchmark at a small N and
        compares stdout against the reference output. If validation
        fails, measurement is skipped and the returned list contains
        only the compile and validate results (so the caller can see
        which step failed and why).
        """
        compile_res = self.run_action(language, problem, "compile", timeout=timeout)
        if not compile_res.ok:
            return [compile_res]
        validate_res = self.run_action(language, problem, "validate", timeout=timeout)
        if not validate_res.ok:
            return [compile_res, validate_res]
        measure_res = self.run_action(language, problem, "measure", timeout=timeout)
        return [compile_res, validate_res, measure_res]
