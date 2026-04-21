"""PerfArena command-line interface.

Built with Typer. The single entry point is the ``perfarena``
console script installed by ``pyproject.toml``. Commands:

- ``list-problems``   -- show the CLBG problem set.
- ``list-languages``  -- show the target language slate.
- ``generate``        -- run the LLM generation pipeline for one cell.
- ``exec-check``      -- sanity-check an executor (local or SSH).
- ``harness-run``     -- drive ``make <action>`` over a cell via an executor.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .executors import LocalExecutor, SSHExecutor, from_config
from .executors.base import Executor
from .generation.pipeline import (
    GenerationRequest,
    generate_one,
    generate_one_via_agent,
)
from .harness import Harness
from . import static_analysis
from .measurement import (
    group_iterations,
    join_group_with_meta,
    load_meta,
    read_rapl_jsonl,
    write_jsonl,
)
from .tools import patch_makefiles as patcher

app = typer.Typer(
    help=(
        "PerfArena: measurement and LLM-code-generation pipeline "
        "built on a fork of greensoftwarelab/Energy-Languages."
    ),
    no_args_is_help=True,
)
console = Console()


# --- list-problems / list-languages ----------------------------------------


@app.command("list-problems")
def list_problems() -> None:
    """List the CLBG problems configured for PerfArena."""
    cfg = load_config()
    table = Table(title="PerfArena problem set")
    table.add_column("key", style="bold")
    table.add_column("default N")
    table.add_column("algorithm class")
    table.add_column("description (first line)")
    for p in cfg.problems.values():
        first_line = p.description.strip().splitlines()[0]
        if len(first_line) > 60:
            first_line = first_line[:57] + "..."
        table.add_row(p.key, p.default_argument, p.algorithm_class, first_line)
    console.print(table)


@app.command("list-languages")
def list_languages() -> None:
    """List the target programming languages."""
    cfg = load_config()
    table = Table(title="PerfArena target languages")
    table.add_column("key", style="bold")
    table.add_column("display name")
    table.add_column("folder")
    table.add_column("ext")
    table.add_column("paradigm")
    for lang in cfg.languages.values():
        table.add_row(
            lang.key,
            lang.display_name,
            lang.folder,
            lang.file_extension,
            lang.paradigm,
        )
    console.print(table)


# --- generate --------------------------------------------------------------


@app.command("generate")
def generate(
    provider: str = typer.Option(
        ..., help="LLM provider: openai | anthropic | google | ollama"
    ),
    model: str = typer.Option(..., help="Model name understood by the provider"),
    problem: str = typer.Option(..., help="CLBG problem key (see list-problems)"),
    language: str = typer.Option(..., help="Target language key (see list-languages)"),
    samples: int = typer.Option(1, help="Number of independent generations"),
    temperature: float = typer.Option(0.2, help="Sampling temperature"),
    max_tokens: int = typer.Option(4096, help="Max output tokens"),
    top_p: Optional[float] = typer.Option(None, help="Nucleus-sampling top-p"),
    top_k: Optional[int] = typer.Option(None, help="Top-k sampling"),
    seed: Optional[int] = typer.Option(
        None, help="Provider seed (where exposed)"
    ),
    system_template: str = typer.Option(
        "system.txt", help="System prompt template filename"
    ),
    user_template: str = typer.Option(
        "user.txt", help="User prompt template filename"
    ),
    via_agent: bool = typer.Option(
        False,
        "--via-agent",
        help=(
            "Run the generation through perfarena-agent (isolated subprocess) "
            "so that inference wall time, CPU time, peak RSS, and RAPL energy "
            "are captured per call and written into the meta.json sidecar."
        ),
    ),
    target_process: Optional[str] = typer.Option(
        None,
        help=(
            "Agent mode only: name of an external LLM daemon whose resource "
            "usage the agent should attribute to the call (e.g. 'ollama')."
        ),
    ),
    target_pid: Optional[int] = typer.Option(
        None,
        help="Agent mode only: explicit PID of an external LLM daemon.",
    ),
    agent_command: Optional[str] = typer.Option(
        None,
        help=(
            "Agent mode only: override the command used to launch the agent. "
            "Defaults to the installed perfarena-agent entry point, falling "
            "back to 'python -m perfarena.generation.agent'."
        ),
    ),
    timeout: float = typer.Option(
        600.0, help="Agent mode only: subprocess timeout in seconds."
    ),
) -> None:
    """Generate source code for a (problem, language) cell with the chosen LLM."""
    cfg = load_config()
    for i in range(samples):
        req = GenerationRequest(
            provider=provider,
            model=model,
            problem=problem,
            language=language,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            seed=seed,
            sample_id=i,
            system_template_name=system_template,
            user_template_name=user_template,
            target_pid=target_pid,
            target_process=target_process,
        )
        mode = "agent" if via_agent else "direct"
        console.print(
            f"[bold]generate[/bold] [{mode}] sample {i + 1}/{samples} "
            f"-> {provider}/{model} {problem}/{language}"
        )
        if via_agent:
            result = generate_one_via_agent(
                cfg,
                req,
                agent_command=agent_command,
                timeout=timeout,
            )
            metrics = result.metadata.get("inference", {}).get("metrics", {})
            console.print(
                f"  source: {result.source_path}\n"
                f"  raw:    {result.raw_path}\n"
                f"  meta:   {result.meta_path}\n"
                f"  wall:   {metrics.get('wall_time_s', 0.0):.2f}s  "
                f"cpu: {metrics.get('cpu_time_s', 0.0):.2f}s  "
                f"rss_peak: {metrics.get('peak_rss_kb', 0)}kB  "
                f"energy: {metrics.get('energy_uj', 'n/a')} uJ "
                f"({metrics.get('energy_source', 'none')})"
            )
        else:
            result = generate_one(cfg, req)
            console.print(
                f"  source: {result.source_path}\n"
                f"  raw:    {result.raw_path}\n"
                f"  meta:   {result.meta_path}\n"
                f"  time:   {result.duration_s:.2f}s"
            )


# --- exec-check ------------------------------------------------------------


def _build_executor(
    host: Optional[str],
    user: Optional[str],
    key_path: Optional[str],
    port: int,
) -> Executor:
    if host:
        if not user:
            raise typer.BadParameter("--user is required when --host is set")
        return from_config(
            {
                "type": "ssh",
                "host": host,
                "user": user,
                "key_path": key_path,
                "port": port,
            }
        )
    return LocalExecutor()


@app.command("exec-check")
def exec_check(
    host: Optional[str] = typer.Option(
        None, help="SSH host; if omitted, uses LocalExecutor"
    ),
    user: Optional[str] = typer.Option(None, help="SSH user"),
    key_path: Optional[str] = typer.Option(None, help="SSH private key path"),
    port: int = typer.Option(22, help="SSH port"),
) -> None:
    """Run a trivial command through the configured executor."""
    executor = _build_executor(host, user, key_path, port)
    try:
        res = executor.run(["sh", "-c", "uname -a && echo OK"])
        console.print(res.stdout.strip() or "(no stdout)")
        if res.stderr.strip():
            console.print(f"[yellow]stderr[/yellow]: {res.stderr.strip()}")
        color = "green" if res.ok else "red"
        console.print(
            f"[{color}]rc={res.returncode} duration={res.duration_s:.3f}s[/{color}]"
        )
    finally:
        executor.close()


# --- harness-run -----------------------------------------------------------


@app.command("harness-run")
def harness_run(
    action: str = typer.Argument(..., help="compile | run | measure | mem | clean"),
    language: str = typer.Option(..., help="Language key"),
    problem: str = typer.Option(..., help="CLBG problem key"),
    host: Optional[str] = typer.Option(None, help="SSH host; default = local"),
    user: Optional[str] = typer.Option(None, help="SSH user"),
    key_path: Optional[str] = typer.Option(None, help="SSH private key path"),
    port: int = typer.Option(22, help="SSH port"),
    remote_repo_path: Optional[str] = typer.Option(
        None,
        help=(
            "Path to the fork on the executor-side filesystem. "
            "Defaults to /workspace for local and to /opt/perfarena/Energy-Languages for SSH."
        ),
    ),
    target_arch: str = typer.Option(
        "auto",
        help=(
            "Target CPU arch for the compile step. "
            "'auto' probes the executor host via uname. "
            "Other accepted values: x86_64-linux-gnu, aarch64-linux-gnu."
        ),
    ),
    timeout: float = typer.Option(600.0, help="Per-action timeout in seconds"),
) -> None:
    """Drive ``make <action>`` for one (language, problem) cell via an executor."""
    cfg = load_config()
    executor = _build_executor(host, user, key_path, port)
    if remote_repo_path is None:
        remote_repo_path = (
            "/opt/perfarena/Energy-Languages" if host else str(cfg.repo_root)
        )
    harness = Harness(
        cfg,
        executor,
        remote_repo_path=remote_repo_path,
        target_arch=target_arch,
    )
    try:
        if action == "compile":
            resolved = harness.resolve_target_arch()
            console.print(f"[dim]target arch: {resolved}[/dim]")
        result = harness.run_action(
            language=language,
            problem=problem,
            action=action,
            timeout=timeout,
        )
        console.print(f"cell: {result.cell_path}")
        if result.result.stdout.strip():
            console.print(result.result.stdout)
        if result.result.stderr.strip():
            console.print(f"[yellow]stderr[/yellow]:\n{result.result.stderr}")
        color = "green" if result.ok else "red"
        console.print(
            f"[{color}]rc={result.result.returncode} "
            f"duration={result.result.duration_s:.2f}s[/{color}]"
        )
        if not result.ok:
            raise typer.Exit(code=1)
    finally:
        executor.close()


@app.command("patch-makefiles")
def patch_makefiles_cmd(
    repo: str = typer.Option(".", help="Path to the Energy-Languages fork root."),
    languages: str = typer.Option(
        "",
        help="Comma-separated language keys to patch. Defaults to all ten.",
    ),
    problems: str = typer.Option(
        "",
        help="Comma-separated CLBG problem keys to patch. Defaults to all ten.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would change without writing files."
    ),
) -> None:
    """Rewrite the fork's per-benchmark Makefiles to delegate to perfarena.mk."""
    argv: list[str] = ["--repo", repo]
    if languages:
        argv += ["--languages", languages]
    if problems:
        argv += ["--problems", problems]
    if dry_run:
        argv += ["--dry-run"]
    rc = patcher.main(argv)
    raise typer.Exit(code=rc)


@app.command("static-analyze")
def static_analyze_cmd(
    language: str = typer.Option(..., help="Language key (python, cpp, rust, go, ...)"),
    source: Path = typer.Option(..., help="Path to the source file."),
) -> None:
    """Run the default static analyzer for a language on one source file."""
    result = static_analysis.analyze(language, source)
    import json as _json

    console.print(_json.dumps(result.to_dict(), indent=2))
    if not result.available:
        raise typer.Exit(code=1)


@app.command("ingest-measurements")
def ingest_measurements_cmd(
    jsonl: Path = typer.Option(
        ..., help="Path to a <language>.jsonl file written by perfarena_runner."
    ),
    output: Path = typer.Option(
        ...,
        help="Destination path for the ingested measurement rows (JSONL).",
    ),
    generations_root: Path = typer.Option(
        ...,
        help="Directory holding the generation meta.json sidecars to join with.",
    ),
    model_slug: str = typer.Option(
        ..., help="Provider__model slug matching the generation output tree."
    ),
    language: str = typer.Option(..., help="Language key."),
    problem: str = typer.Option(..., help="Problem key."),
    sample_id: int = typer.Option(0, help="Sample id of the generation to join with."),
) -> None:
    """Join a RAPL trace with its generation meta.json and write measurement rows."""
    cfg = load_config()
    lang = cfg.get_language(language)
    meta_path = (
        generations_root
        / model_slug
        / lang.folder
        / problem
        / f"sample_{sample_id:02d}{lang.file_extension}.meta.json"
    )
    if not meta_path.exists():
        console.print(f"[red]meta.json not found: {meta_path}[/red]")
        raise typer.Exit(code=1)
    meta = load_meta(meta_path)

    iterations = read_rapl_jsonl(jsonl)
    groups = [
        g for g in group_iterations(iterations)
        if g.language == lang.folder and g.test == problem
    ]
    if not groups:
        console.print(f"[yellow]no matching iterations in {jsonl}[/yellow]")
        raise typer.Exit(code=1)

    rows = []
    for group in groups:
        for row in join_group_with_meta(group, meta):
            row.generation_meta_path = str(meta_path)
            rows.append(row)

    write_jsonl(rows, output)
    console.print(f"wrote {len(rows)} rows -> {output}")


if __name__ == "__main__":
    app()
