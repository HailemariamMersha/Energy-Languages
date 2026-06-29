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

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .executors import LocalExecutor, from_config
from .executors.base import Executor
from .generation.pipeline import (
    GenerationRequest,
    generate_one,
    generate_one_via_agent,
)
from .harness import Harness
from . import static_analysis
from . import leetcode_energy as leetcode
from . import casewise_energy
from .measurement import (
    group_iterations,
    join_group_with_meta,
    load_meta,
    read_rapl_jsonl,
    write_jsonl,
)
from .tools import patch_makefiles as patcher
from .tools import summarize_leetcode_casewise as casewise_summary
from .tools import visualize_leetcode_casewise as casewise_viz

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
    seed: Optional[int] = typer.Option(None, help="Provider seed (where exposed)"),
    system_template: str = typer.Option(
        "system.txt", help="System prompt template filename"
    ),
    user_template: str = typer.Option("user.txt", help="User prompt template filename"),
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


# --- LeetCode-Energy -------------------------------------------------------


@app.command("leetcode-scaffold")
def leetcode_scaffold_cmd(
    languages: str = typer.Option(
        "",
        help=(
            "Comma-separated Energy-Languages keys. Defaults to all 10: "
            "python,javascript,typescript,java,csharp,cpp,php,go,rust,ruby."
        ),
    ),
    problems: str = typer.Option(
        "",
        help="Comma-separated LeetCode title slugs. Defaults to all 99.",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        help="PerfArena LeetCode backend URL. Defaults to env or http://localhost:8000.",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help=(
            "Use the local sibling perfarena-leetcode/data/sampled_problems.json "
            "instead of fetching from the backend."
        ),
    ),
    overwrite_solution: bool = typer.Option(
        False,
        "--overwrite-solution",
        help="Overwrite existing solution.<ext> files with backend starter snippets.",
    ),
) -> None:
    """Create/update leetcode-energy/<Language>/<slug>/ cells."""
    cfg = load_config()
    langs = leetcode.parse_language_list(languages)
    client = None if local else leetcode.LeetCodeApiClient(base_url=base_url)
    catalog = leetcode.load_problem_catalog(cfg.repo_root, client, prefer_local=local)
    selected = leetcode.filter_problems(catalog, leetcode.parse_slug_list(problems))
    detailed = leetcode.hydrate_problem_details(
        cfg.repo_root,
        selected,
        client,
        prefer_local=local,
    )
    written = leetcode.scaffold(
        cfg.repo_root,
        langs,
        detailed,
        overwrite_solution=overwrite_solution,
    )
    console.print(
        f"scaffolded {len(detailed)} problem(s) x {len(langs)} language(s) "
        f"under {leetcode.leetcode_root(cfg.repo_root)}"
    )
    console.print(f"wrote/updated {len(written)} file(s)")


@app.command("leetcode-compile")
def leetcode_compile_cmd(
    language: str = typer.Option(..., help="Energy-Languages key, e.g. python or go."),
    source: Path = typer.Option(..., help="Path to solution source file."),
    result: Path = typer.Option(
        Path("compile.json"),
        help="Path to write compile result JSON.",
    ),
) -> None:
    """Run the language-dependent local LeetCode compile/syntax check."""
    lang = leetcode.get_language(language)
    compile_result = leetcode.compile_solution(lang, source)
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps(compile_result.to_dict(), indent=2, sort_keys=True))
    color = "green" if compile_result.ok else "red"
    console.print(
        f"[{color}]compile {lang.key}: rc={compile_result.returncode} "
        f"duration={compile_result.duration_s:.2f}s[/{color}]"
    )
    if compile_result.stderr.strip():
        console.print(f"[yellow]stderr[/yellow]:\n{compile_result.stderr}")
    if not compile_result.ok:
        raise typer.Exit(code=1)


@app.command("leetcode-import-solutions")
def leetcode_import_solutions_cmd(
    base_url: Optional[str] = typer.Option(
        None,
        help=(
            "PerfArena dataset API base URL. Defaults to "
            "PERFARENA_LEETCODE_BASE_URL, ARENA_BASE_URL, or localhost."
        ),
    ),
    languages: str = typer.Option(
        "python",
        help=("Comma-separated Energy-Languages keys to import. Defaults to python."),
    ),
    model: Optional[str] = typer.Option(
        None,
        help="Optional dataset model_name filter, e.g. gemma4:e4b.",
    ),
    model_version: Optional[str] = typer.Option(
        None,
        help="Optional local model_version filter.",
    ),
    problems: str = typer.Option(
        "",
        help="Comma-separated LeetCode title slugs. Defaults to all returned rows.",
    ),
    progress: Path = typer.Option(
        Path("perfarena_out/leetcode_dataset_import_progress.json"),
        help="Progress JSON path used later by workload-build and measure.",
    ),
    accepted_only: bool = typer.Option(True, "--accepted-only/--all-results"),
    overwrite: bool = typer.Option(
        True,
        "--overwrite/--no-overwrite",
        help="Overwrite local solution files with the exact dataset code.",
    ),
    hydrate_problem: bool = typer.Option(
        True,
        "--hydrate-problem/--no-hydrate-problem",
        help="Fetch /api/problems/{slug} metadata when staging each cell.",
    ),
) -> None:
    """Import already-judged source code from the PerfArena dataset API."""
    cfg = load_config()
    langs = leetcode.parse_language_list(languages)
    progress_data = leetcode.import_dataset_solutions(
        repo_root=cfg.repo_root,
        base_url=base_url,
        languages=langs,
        model=model,
        model_version=model_version,
        problem_slugs=leetcode.parse_slug_list(problems),
        progress_path=progress,
        accepted_only=accepted_only,
        overwrite_source=overwrite,
        hydrate_problem=hydrate_problem,
    )
    stats = progress_data.get("dataset_import_stats", {})
    console.print(
        "leetcode-import-solutions: "
        f"seen={stats.get('seen', 0)} "
        f"imported={stats.get('imported', 0)} "
        f"skipped={stats.get('skipped', 0)} -> {progress}"
    )
    by_model = stats.get("by_model_slug") or {}
    for model_slug, count in sorted(by_model.items()):
        console.print(f"  model_slug {model_slug}: {count}")
    by_language = stats.get("by_language") or {}
    for language, count in sorted(by_language.items()):
        console.print(f"  language {language}: {count}")


@app.command("leetcode-generate")
def leetcode_generate_cmd(
    provider: str = typer.Option(
        ..., help="LLM provider: openai | anthropic | google | ollama"
    ),
    model: str = typer.Option(..., help="Model name understood by the provider"),
    problem: str = typer.Option(..., help="LeetCode title slug"),
    language: str = typer.Option(..., help="Energy-Languages key"),
    samples: int = typer.Option(1, help="Number of independent generations"),
    temperature: float = typer.Option(0.2, help="Sampling temperature"),
    max_tokens: int = typer.Option(4096, help="Max output tokens"),
    top_p: Optional[float] = typer.Option(None, help="Nucleus-sampling top-p"),
    top_k: Optional[int] = typer.Option(None, help="Top-k sampling"),
    seed: Optional[int] = typer.Option(None, help="Provider seed where supported"),
    base_url: Optional[str] = typer.Option(
        None,
        help="PerfArena LeetCode backend URL. Defaults to env or http://localhost:8000.",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Use local sampled problem metadata instead of backend detail.",
    ),
    stage: bool = typer.Option(
        True,
        "--stage/--no-stage",
        help="Copy each generated sample into leetcode-energy/<Language>/<slug>/solution.<ext>.",
    ),
    empty_code_retries: int = typer.Option(
        2,
        help="Retry LLM generation this many times when extracted source is empty.",
    ),
) -> None:
    """Generate LeetCode-shaped source for one problem/language cell."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    client = None if local else leetcode.LeetCodeApiClient(base_url=base_url)
    catalog = leetcode.load_problem_catalog(cfg.repo_root, client, prefer_local=local)
    selected = leetcode.filter_problems(catalog, [problem])
    detailed = leetcode.hydrate_problem_details(
        cfg.repo_root,
        selected,
        client,
        prefer_local=local,
    )
    leetcode.scaffold(cfg.repo_root, [lang], detailed, overwrite_solution=False)
    for i in range(samples):
        console.print(
            f"[bold]leetcode-generate[/bold] sample {i + 1}/{samples} "
            f"-> {provider}/{model} {problem}/{lang.key}"
        )
        result = leetcode.generate_solution(
            cfg.repo_root,
            detailed[0],
            lang,
            provider=provider,
            model=model,
            sample_id=i,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            seed=seed,
            stage=stage,
            empty_code_retries=empty_code_retries,
        )
        console.print(
            f"  source: {result.source_path}\n"
            f"  raw:    {result.raw_path}\n"
            f"  meta:   {result.meta_path}"
        )


@app.command("leetcode-check")
def leetcode_check_cmd(
    language: str = typer.Option(..., help="Energy-Languages key"),
    problem: str = typer.Option(..., help="LeetCode title slug"),
    source: Path = typer.Option(..., help="Path to solution source file"),
    result: Path = typer.Option(
        Path("result.json"),
        help="Path to write LeetCode check result JSON.",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        help="PerfArena LeetCode backend URL. Defaults to env or http://localhost:8000.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        help="API key. Defaults to ARENA_API_KEY or PERFARENA_API_KEY.",
    ),
    submission_id: Optional[int] = typer.Option(
        None,
        help="Append to an existing submission id instead of creating one.",
    ),
    provider: str = typer.Option("manual", help="Provider name for new submissions."),
    model: str = typer.Option("manual", help="Model name for new submissions."),
    model_version: str = typer.Option(
        "manual", help="Model version for new submissions."
    ),
    generation_meta: Optional[Path] = typer.Option(
        None,
        help="Optional generation meta.json to include in attempt trace.",
    ),
    poll_timeout: int = typer.Option(900, help="Seconds to wait for backend judging."),
) -> None:
    """Compile locally, submit to the PerfArena LeetCode backend, and poll result."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    client = leetcode.LeetCodeApiClient(base_url=base_url, api_key=api_key)
    check = leetcode.check_solution(
        repo_root=cfg.repo_root,
        language=lang,
        problem_slug=problem,
        source=source,
        client=client,
        provider=provider,
        model=model,
        model_version=model_version,
        model_params={},
        submission_id=submission_id,
        generation_meta_path=generation_meta,
        result_path=result,
        poll_timeout_s=poll_timeout,
    )
    if not check.get("submitted"):
        console.print(f"[red]not submitted[/red]: {check.get('error')}")
        raise typer.Exit(code=1)
    attempt = check.get("attempt", {})
    status = attempt.get("status")
    accepted = attempt.get("accepted")
    color = "green" if accepted else "red"
    console.print(
        f"[{color}]submission={check.get('submission_id')} "
        f"status={status} accepted={accepted}[/{color}]"
    )
    console.print(f"wrote {result}")
    if not accepted:
        raise typer.Exit(code=1)


@app.command("leetcode-run")
def leetcode_run_cmd(
    provider: str = typer.Option(
        ..., help="LLM provider: openai | anthropic | google | ollama"
    ),
    model: str = typer.Option(..., help="Model name understood by the provider"),
    model_version: str = typer.Option(
        "ollama", help="Version label stored in backend submission"
    ),
    languages: str = typer.Option(
        "", help="Comma-separated Energy-Languages keys. Defaults to all 10."
    ),
    problems: str = typer.Option(
        "", help="Comma-separated LeetCode title slugs. Defaults to all 99."
    ),
    temperature: float = typer.Option(0.2, help="Sampling temperature"),
    max_tokens: int = typer.Option(4096, help="Max output tokens"),
    base_url: Optional[str] = typer.Option(
        None,
        help="PerfArena LeetCode backend URL. Defaults to env or http://localhost:8000.",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        help="API key. Defaults to ARENA_API_KEY or PERFARENA_API_KEY.",
    ),
    progress: Path = typer.Option(
        Path("perfarena_out/leetcode_run_progress.json"),
        help="Resumable progress JSON path.",
    ),
    retry_failed: bool = typer.Option(False, "--retry-failed"),
    poll_timeout: int = typer.Option(900, help="Seconds to wait per judged attempt."),
    empty_code_retries: int = typer.Option(
        2,
        help="Retry LLM generation this many times when extracted source is empty.",
    ),
) -> None:
    """Run generate -> compile -> backend correctness check over selected cells."""
    cfg = load_config()
    langs = leetcode.parse_language_list(languages)
    client = leetcode.LeetCodeApiClient(base_url=base_url, api_key=api_key)
    catalog = leetcode.load_problem_catalog(cfg.repo_root, client)
    selected = leetcode.filter_problems(catalog, leetcode.parse_slug_list(problems))
    detailed = leetcode.hydrate_problem_details(cfg.repo_root, selected, client)
    leetcode.scaffold(cfg.repo_root, langs, detailed, overwrite_solution=False)
    result = leetcode.run_pipeline(
        repo_root=cfg.repo_root,
        languages=langs,
        problems=detailed,
        client=client,
        provider=provider,
        model=model,
        model_version=model_version,
        temperature=temperature,
        max_tokens=max_tokens,
        progress_path=progress,
        retry_failed=retry_failed,
        poll_timeout_s=poll_timeout,
        empty_code_retries=empty_code_retries,
    )
    records = result.get("records", {})
    complete = sum(1 for row in records.values() if row.get("status") == "complete")
    failed = sum(1 for row in records.values() if row.get("status") == "failed")
    console.print(
        f"leetcode-run progress: {complete} complete, {failed} failed -> {progress}"
    )


@app.command("leetcode-workload-build")
def leetcode_workload_build_cmd(
    progress: Path = typer.Option(
        Path("perfarena_out/leetcode_python_real_with_snippets_progress.json"),
        help="LeetCode run progress JSON path.",
    ),
    language: str = typer.Option("python", help="Energy-Languages key."),
    model_slug: str = typer.Option(
        "ollama__gemma4_e4b",
        help="Model slug recorded in the progress keys.",
    ),
    problems: str = typer.Option(
        "",
        help="Comma-separated LeetCode title slugs. Defaults to all accepted records.",
    ),
    accepted_only: bool = typer.Option(True, "--accepted-only/--all-results"),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Build shared LeetCode reference workloads and expected outputs."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    if lang.key != "python":
        console.print(
            "[red]leetcode-workload-build currently supports python only[/red]"
        )
        raise typer.Exit(code=2)
    selected = leetcode.accepted_results_from_progress(
        cfg.repo_root,
        progress,
        lang,
        model_slug=model_slug,
        accepted_only=accepted_only,
        problem_slugs=leetcode.parse_slug_list(problems),
    )
    rows = leetcode.build_workloads(cfg.repo_root, selected, overwrite=overwrite)
    built = sum(1 for row in rows if row.get("status") == "built")
    exists = sum(1 for row in rows if row.get("status") == "exists")
    skipped = sum(1 for row in rows if row.get("status") == "skipped")
    console.print(
        f"leetcode-workload-build: selected={len(selected)} built={built} "
        f"exists={exists} skipped={skipped}"
    )
    for row in rows:
        if row.get("status") == "skipped":
            console.print(
                f"[yellow]skip[/yellow] {row.get('problem')}: {row.get('reason')}"
            )


@app.command("leetcode-workload-run")
def leetcode_workload_run_cmd(
    language: str = typer.Option(..., help="Energy-Languages key."),
    problem: str = typer.Option(..., help="LeetCode title slug."),
    source: Path = typer.Option(..., help="Path to solution source file."),
    workload: Path = typer.Option(..., help="Shared workload JSON path."),
    expected: Path = typer.Option(..., help="Shared expected-output JSON path."),
    repeat: int = typer.Option(1, help="Repeat the full workload this many times."),
) -> None:
    """Run one local LeetCode workload and validate against expected outputs."""
    lang = leetcode.get_language(language)
    result = leetcode.run_workload_once(
        language=lang,
        problem_slug=problem,
        source=source,
        workload_file=workload,
        expected_file=expected,
        repeat=repeat,
    )
    if not result.get("ok"):
        console.print(json.dumps(result, indent=2, sort_keys=True))
        raise typer.Exit(code=1)
    console.print(json.dumps(result, sort_keys=True))


@app.command("leetcode-curated-sync")
def leetcode_curated_sync_cmd(
    dataset: Optional[Path] = typer.Option(
        None,
        help="Curated LeetCodeDataset93 JSONL. Defaults to the sibling repository.",
    ),
    prune: bool = typer.Option(
        True,
        "--prune/--keep-existing",
        help="Remove old synthetic workload/output JSON before syncing.",
    ),
) -> None:
    """Sync the curated dataset into shared per-problem workload files."""
    cfg = load_config()
    dataset_path = dataset or leetcode.default_curated_dataset_path(cfg.repo_root)
    rows = leetcode.sync_curated_dataset_workloads(
        cfg.repo_root,
        dataset_path,
        prune=prune,
    )
    console.print(
        f"leetcode-curated-sync: problems={len(rows)} "
        f"cases={sum(row['cases'] for row in rows)} dataset={dataset_path}"
    )


@app.command("leetcode-curated-workload-run", hidden=True)
def leetcode_curated_workload_run_cmd(
    problem: str = typer.Option(...),
    source: Path = typer.Option(...),
    workload: Path = typer.Option(...),
    repeat: int = typer.Option(1, min=1),
    validate: bool = typer.Option(False, "--validate"),
) -> None:
    """Execute one curated Python workload; used by the energy runner."""
    data = json.loads(workload.read_text())
    if data.get("problem") != problem:
        raise typer.BadParameter(
            f"workload problem {data.get('problem')!r} does not match {problem!r}"
        )
    try:
        result = leetcode.run_curated_python_workload(
            source=source,
            workload=data,
            repeat=repeat,
            validate=validate,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]{type(exc).__name__}: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(json.dumps(result, sort_keys=True))


@app.command("leetcode-measure")
def leetcode_measure_cmd(
    progress: Path = typer.Option(
        Path("perfarena_out/leetcode_python_real_with_snippets_progress.json"),
        help="LeetCode run progress JSON path.",
    ),
    language: str = typer.Option("python", help="Energy-Languages key."),
    model_slug: str = typer.Option(
        "ollama__gemma4_e4b",
        help="Model slug recorded in the progress keys.",
    ),
    problems: str = typer.Option(
        "",
        help="Comma-separated LeetCode title slugs. Defaults to all accepted records.",
    ),
    accepted_only: bool = typer.Option(True, "--accepted-only/--all-results"),
    warmup: int = typer.Option(3, help="CodeCarbon/RAPL warmup iterations."),
    measure: int = typer.Option(10, help="CodeCarbon/RAPL measurement iterations."),
    idle_s: int = typer.Option(2, help="Idle baseline seconds."),
    case_repeat: int = typer.Option(
        1,
        help="Repeat the full workload inside each measured child process.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        help="Aggregate JSONL path. Defaults under perfarena_out/leetcode_measurements.",
    ),
    curated_dataset: Optional[Path] = typer.Option(
        None,
        "--curated-dataset",
        help=(
            "Use the curated LeetCodeDataset93 JSONL and sync its shared "
            "workloads before measuring."
        ),
    ),
    reset_output: bool = typer.Option(
        False,
        "--reset-output",
        help="Replace the aggregate output instead of appending to it.",
    ),
) -> None:
    """Measure accepted LeetCode solutions against shared local workloads."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    if lang.key != "python":
        console.print("[red]leetcode-measure currently supports python only[/red]")
        raise typer.Exit(code=2)
    selected = leetcode.accepted_results_from_progress(
        cfg.repo_root,
        progress,
        lang,
        model_slug=model_slug,
        accepted_only=accepted_only,
        problem_slugs=leetcode.parse_slug_list(problems),
    )
    if curated_dataset is not None:
        synced = leetcode.sync_curated_dataset_workloads(
            cfg.repo_root,
            curated_dataset,
            prune=True,
        )
        rows = leetcode.measure_curated_accepted_results(
            cfg.repo_root,
            selected,
            model_slug=model_slug,
            warmup=warmup,
            measure=measure,
            idle_s=idle_s,
            case_repeat=case_repeat,
            output=output,
            reset_output=reset_output,
        )
        console.print(
            f"curated workloads: problems={len(synced)} "
            f"cases={sum(row['cases'] for row in synced)}"
        )
    else:
        rows = leetcode.measure_accepted_results(
            cfg.repo_root,
            selected,
            model_slug=model_slug,
            warmup=warmup,
            measure=measure,
            idle_s=idle_s,
            case_repeat=case_repeat,
            output=output,
        )
    console.print(
        f"leetcode-measure: selected={len(selected)} measured_rows={len(rows)}"
    )


@app.command("leetcode-measure-model")
def leetcode_measure_model_cmd(
    base_url: Optional[str] = typer.Option(
        None,
        help=(
            "PerfArena dataset API base URL. Defaults to "
            "PERFARENA_LEETCODE_BASE_URL, ARENA_BASE_URL, or localhost."
        ),
    ),
    model: str = typer.Option(..., help="PerfArena dataset model_name."),
    language: str = typer.Option("python", help="Only python is supported in v1."),
    model_slug: Optional[str] = typer.Option(
        None,
        help="Optional explicit model slug if one model_name maps to multiple slugs.",
    ),
    accepted_only: bool = typer.Option(True, "--accepted-only/--all-results"),
    curated_dataset: Optional[Path] = typer.Option(
        None,
        "--curated-dataset",
        help="Curated LeetCodeDataset93 JSONL. Defaults to the sibling dataset.",
    ),
    warmup_seconds: float = typer.Option(
        60.0,
        min=0.0,
        help="Persistent full-workload warmup duration per problem.",
    ),
    measurements: int = typer.Option(
        10,
        min=1,
        help="Independent measured batches per curated test case.",
    ),
    batch_seconds: float = typer.Option(
        1.0,
        min=0.01,
        help="Calibration target for each unchanged case batch.",
    ),
    powermetrics_interval_ms: int = typer.Option(
        100,
        min=10,
        help="Direct powermetrics sampling interval in milliseconds.",
    ),
    rerun: bool = typer.Option(
        False,
        "--rerun",
        help="Replace an existing model measurement output.",
    ),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Resume case/iteration checkpoints from an existing JSONL file.",
    ),
    hydrate_problem: bool = typer.Option(
        True,
        "--hydrate-problem/--no-hydrate-problem",
        help="Fetch /api/problems/{slug} metadata when staging each cell.",
    ),
) -> None:
    """Import and measure one PerfArena model/language selection."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    if lang.key != "python":
        console.print(
            "[red]leetcode-measure-model currently supports python only[/red]"
        )
        raise typer.Exit(code=2)
    if not accepted_only:
        console.print(
            "[red]Casewise energy measurement requires --accepted-only.[/red]"
        )
        raise typer.Exit(code=2)
    resolved_base_url = (base_url or leetcode.default_base_url()).rstrip("/")
    rows = list(
        leetcode.iter_dataset_solutions(
            base_url=resolved_base_url,
            language=lang,
            model=model,
            only_accepted=accepted_only,
        )
    )
    if not rows:
        qualifier = "accepted " if accepted_only else ""
        console.print(
            f"[red]No {qualifier}{lang.key} dataset rows found for model "
            f"{model!r}.[/red]"
        )
        raise typer.Exit(code=1)
    try:
        resolved_model_slug, selected_rows = leetcode.select_single_model_slug(
            rows,
            requested_model_slug=model_slug,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    progress = leetcode.model_import_progress_path(
        cfg.repo_root,
        resolved_model_slug,
        lang,
    )
    output = casewise_energy.measurement_path(
        cfg.repo_root,
        resolved_model_slug,
        lang.key,
    )
    summary_prefix = casewise_energy.summary_prefix(
        cfg.repo_root, resolved_model_slug, lang.key
    )
    summary_json = summary_prefix.with_suffix(".json")
    if output.exists() and not rerun and not resume:
        console.print(
            f"[yellow]Existing casewise measurement found for {resolved_model_slug}; "
            "skipping. Use --resume or --rerun.[/yellow]"
        )
        console.print(f"aggregate: {output}")
        if summary_json.exists():
            console.print(f"summary:   {summary_prefix.with_suffix('.md')}")
        return

    progress_data = leetcode.import_dataset_solution_rows(
        repo_root=cfg.repo_root,
        rows=selected_rows,
        base_url=resolved_base_url,
        languages=[lang],
        progress_path=progress,
        accepted_only=accepted_only,
        overwrite_source=True,
        hydrate_problem=hydrate_problem,
        stage_solution=False,
    )
    stats = progress_data.get("dataset_import_stats", {})
    dataset_path = curated_dataset or leetcode.default_curated_dataset_path(
        cfg.repo_root
    )
    synced = leetcode.sync_curated_dataset_workloads(
        cfg.repo_root,
        dataset_path,
        prune=True,
    )
    selected = leetcode.accepted_results_from_progress(
        cfg.repo_root,
        progress,
        lang,
        model_slug=resolved_model_slug,
        accepted_only=accepted_only,
    )
    if not selected:
        console.print(
            f"[red]No accepted imported results selected for {resolved_model_slug}.[/red]"
        )
        raise typer.Exit(code=1)
    try:
        measured_rows = casewise_energy.measure_casewise_results(
            cfg.repo_root,
            selected,
            model_slug=resolved_model_slug,
            warmup_seconds=warmup_seconds,
            measurements=measurements,
            batch_seconds=batch_seconds,
            interval_ms=powermetrics_interval_ms,
            output=output,
            resume=resume and not rerun,
            reset_output=rerun,
        )
    except RuntimeError as exc:
        console.print(f"[red]Casewise measurement failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    summary = casewise_summary.summarize(output, expected_measurements=measurements)
    casewise_summary.write_outputs(summary, summary_prefix)
    console.print(
        "leetcode-measure-model: "
        f"model_slug={resolved_model_slug} "
        f"seen={stats.get('seen', 0)} "
        f"imported={stats.get('imported', 0)} "
        f"selected={len(selected)} "
        f"measured_rows={len(measured_rows)} "
        f"complete_cases={summary['complete_cases']} "
        f"skipped_problems={summary['skipped_problems']} "
        f"failed_problems={summary['failed_problems']} "
        f"incomplete_cases={len(summary['incomplete_cases'])}"
    )
    console.print(
        f"curated workloads: problems={len(synced)} "
        f"cases={sum(row['cases'] for row in synced)}"
    )
    console.print(f"progress:  {progress}")
    console.print(f"aggregate: {output}")
    console.print(f"summary:   {summary_prefix.with_suffix('.md')}")


@app.command("leetcode-case-measure")
def leetcode_case_measure_cmd(
    model_slug: str = typer.Option(..., help="Model slug to measure."),
    progress: Optional[Path] = typer.Option(
        None,
        help=(
            "Accepted progress JSON. Defaults to "
            "perfarena_out/leetcode_imports/<model_slug>/python_progress.json."
        ),
    ),
    language: str = typer.Option("python", help="Only python is supported in v1."),
    problems: str = typer.Option(
        "",
        help="Comma-separated curated slugs. Defaults to all accepted rows.",
    ),
    accepted_only: bool = typer.Option(True, "--accepted-only/--all-results"),
    warmup_seconds: float = typer.Option(
        60.0, min=0.0, help="Persistent full-workload warmup duration per problem."
    ),
    measurements: int = typer.Option(
        10, min=1, help="Independent measured batches per curated test case."
    ),
    batch_seconds: float = typer.Option(
        1.0, min=0.01, help="Calibration target for each unchanged case batch."
    ),
    powermetrics_interval_ms: int = typer.Option(
        100, min=10, help="Direct powermetrics sample interval in milliseconds."
    ),
    output: Optional[Path] = typer.Option(
        None,
        help="Casewise JSONL path. Defaults under perfarena_out/leetcode_measurements.",
    ),
    rerun: bool = typer.Option(
        False,
        "--rerun",
        help="Replace an existing casewise output.",
    ),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Resume completed case/iteration checkpoints.",
    ),
) -> None:
    """Measure unchanged curated Python cases with direct powermetrics."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    if lang.key != "python":
        console.print("[red]leetcode-case-measure currently supports python only[/red]")
        raise typer.Exit(code=2)
    if not accepted_only:
        console.print(
            "[red]Casewise energy measurement requires --accepted-only.[/red]"
        )
        raise typer.Exit(code=2)

    progress_path = progress or leetcode.model_import_progress_path(
        cfg.repo_root,
        model_slug,
        lang,
    )
    out_path = output or casewise_energy.measurement_path(
        cfg.repo_root, model_slug, lang.key
    )
    output_prefix = (
        out_path.with_name(f"{out_path.stem}_summary")
        if output is not None
        else casewise_energy.summary_prefix(cfg.repo_root, model_slug, lang.key)
    )
    selected = leetcode.accepted_results_from_progress(
        cfg.repo_root,
        progress_path,
        lang,
        model_slug=model_slug,
        accepted_only=accepted_only,
        problem_slugs=leetcode.parse_slug_list(problems),
    )
    if not selected:
        console.print(
            f"[red]No accepted curated candidates selected for {model_slug} "
            f"from {progress_path}.[/red]"
        )
        raise typer.Exit(code=1)
    try:
        measured_rows = casewise_energy.measure_casewise_results(
            cfg.repo_root,
            selected,
            model_slug=model_slug,
            warmup_seconds=warmup_seconds,
            measurements=measurements,
            batch_seconds=batch_seconds,
            interval_ms=powermetrics_interval_ms,
            output=out_path,
            resume=resume and not rerun,
            reset_output=rerun,
        )
    except RuntimeError as exc:
        console.print(f"[red]Casewise measurement failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    summary = casewise_summary.summarize(out_path, expected_measurements=measurements)
    casewise_summary.write_outputs(summary, output_prefix)
    console.print(
        "leetcode-case-measure: "
        f"model_slug={model_slug} "
        f"selected={len(selected)} "
        f"new_rows={len(measured_rows)} "
        f"complete_cases={summary['complete_cases']} "
        f"skipped_problems={summary['skipped_problems']} "
        f"failed_problems={summary['failed_problems']} "
        f"incomplete_cases={len(summary['incomplete_cases'])}"
    )
    console.print(f"aggregate: {out_path}")
    console.print(f"summary:   {output_prefix.with_suffix('.md')}")


@app.command("leetcode-compare-models")
def leetcode_compare_models_cmd(
    model_slugs: str = typer.Option(
        ...,
        "--models",
        help="Comma-separated model slugs with completed casewise summaries.",
    ),
    language: str = typer.Option("python", help="Only python is supported in v1."),
    output_prefix: Optional[Path] = typer.Option(
        None,
        help="Optional output prefix for the comparison JSON, CSV, and Markdown.",
    ),
) -> None:
    """Compare models over their common completed problem/case intersection."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    if lang.key != "python":
        console.print(
            "[red]leetcode-compare-models currently supports python only[/red]"
        )
        raise typer.Exit(code=2)
    requested = [value.strip() for value in model_slugs.split(",") if value.strip()]
    if len(requested) < 2:
        console.print("[red]Pass at least two model slugs with --models.[/red]")
        raise typer.Exit(code=2)

    summaries: list[dict[str, object]] = []
    missing: list[Path] = []
    for model_slug in requested:
        path = casewise_energy.summary_prefix(
            cfg.repo_root, model_slug, lang.key
        ).with_suffix(".json")
        if not path.exists():
            missing.append(path)
            continue
        summaries.append(json.loads(path.read_text()))
    if missing:
        console.print("[red]Missing casewise summaries:[/red]")
        for path in missing:
            console.print(f"  {path}")
        raise typer.Exit(code=1)

    try:
        comparison = casewise_summary.compare_models(summaries)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    prefix = output_prefix or casewise_summary.comparison_prefix(
        cfg.repo_root / "perfarena_out" / "leetcode_measurements",
        requested,
        lang.key,
    )
    casewise_summary.write_comparison(comparison, prefix)
    console.print(
        "leetcode-compare-models: "
        f"models={len(requested)} "
        f"common_problems={comparison['common_problems']} "
        f"common_cases={comparison['common_cases']}"
    )
    console.print(f"comparison: {prefix.with_suffix('.md')}")


@app.command("leetcode-visualize-casewise")
def leetcode_visualize_casewise_cmd(
    model_slug: str = typer.Option(..., help="Model slug with completed casewise CSVs."),
    language: str = typer.Option("python", help="Only python is supported in v1."),
    output: Optional[Path] = typer.Option(
        None,
        help="Optional HTML output path. Defaults under the model measurement folder.",
    ),
) -> None:
    """Generate a self-contained HTML/SVG report for casewise LeetCode results."""
    cfg = load_config()
    lang = leetcode.get_language(language)
    if lang.key != "python":
        console.print(
            "[red]leetcode-visualize-casewise currently supports python only[/red]"
        )
        raise typer.Exit(code=2)
    root = casewise_viz.measurement_root(cfg.repo_root, model_slug)
    try:
        report = casewise_viz.write_report(root, lang.key, output)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"casewise report: {report}")


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
        g
        for g in group_iterations(iterations)
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
