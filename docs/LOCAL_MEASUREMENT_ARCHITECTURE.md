# Local Measurement Architecture

This document summarizes how the local LeetCode execution-energy measurements
were produced in the `Energy-Languages` fork, what `perfarena_out` contains,
and how the results are published to the PerfArena website. It is intended for
someone who wants to move the measurement workflow onto a server and update the
website automatically.

## What `perfarena_out` Is

`perfarena_out/` is the local output workspace for generated code, imported
solutions, progress files, measurements, reports, and share artifacts. It is
ignored by Git because it can contain large generated files and raw telemetry.

Important subtrees:

```text
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<problem_slug>/solution.py
perfarena_out/leetcode_imports/<model_slug>/python_progress.json
perfarena_out/leetcode_measurements/<model_slug>/
perfarena_out/leetcode_measurements/comparisons/
```

The measured solution source of truth is:

```text
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<problem_slug>/solution.py
```

The measurement result source of truth is:

```text
perfarena_out/leetcode_measurements/<model_slug>/
```

Current measured model folders:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/
perfarena_out/leetcode_measurements/ollama__qwen2.5_7b/
perfarena_out/leetcode_measurements/ollama__qwen3_4b/
```

## Measurement Result Files

Each model folder contains the casewise result files:

```text
python_casewise.jsonl
python_casewise_cases.csv
python_casewise_problems.csv
python_casewise_summary.json
python_casewise_summary.md
python_casewise_report.html
python_casewise_run.log
powermetrics/<problem_slug>.plist.gz
```

Main meanings:

| File | Purpose |
|---|---|
| `python_casewise.jsonl` | One retained measured batch per row. Large audit file with batch totals, per-call normalized metrics, sample counts, host metadata, and hashes. |
| `python_casewise_cases.csv` | One row per completed `(problem, case_hash)`. Contains medians over the ten measured batches, CV, batch calls, and sample counts. |
| `python_casewise_problems.csv` | One row per completed problem. Contains problem-level medians over case medians. |
| `python_casewise_summary.json` | Machine-readable summary used by the publisher. Contains run, problem, and case summaries. |
| `python_casewise_summary.md` | Human-readable methodology and result summary. |
| `python_casewise_report.html` | Offline visual report for the model run. |
| `powermetrics/` | Raw compressed Apple `powermetrics` streams. Useful for audit, not uploaded to PerfArena. |

The share tarball keeps only publish/review files and excludes raw telemetry:

```text
python_casewise_summary.json
python_casewise.jsonl
python_casewise_cases.csv
python_casewise_problems.csv
python_casewise_summary.md
```

## Local Measurement Workflow

The current Python-only workflow is:

1. Fetch accepted Python solutions for a given model from the PerfArena dataset
   API.
2. Store each accepted source under the model-scoped
   `perfarena_out/leetcode_dataset_solutions/...` path.
3. Load the curated LeetCodeDataset93 workload from:

   ```text
   ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl
   ```

4. Validate the accepted solution against every curated case before measuring.
5. Start one persistent Python worker per problem so imports and process startup
   are outside measured case windows.
6. Warm the worker for 60 seconds by repeatedly sweeping all unchanged curated
   cases for that problem.
7. Calibrate each unchanged case to find `batch_calls`, the number of repeated
   calls that makes one measured batch last about one second.
8. Run ten deterministic shuffled measurement rounds. Every completed case is
   measured once per round, so each case should have ten retained rows.
9. Run `/usr/bin/powermetrics` continuously per problem at 100 ms sampling and
   integrate CPU power samples that fall fully inside each measured batch.
10. Normalize each measured batch:

    ```text
    wall_ms_per_call = batch_wall_ms / batch_calls
    cpu_energy_j_per_call = batch_cpu_energy_j / batch_calls
    ```

11. Compute medians in this order:

    ```text
    case score    = median of ten normalized batch rows
    problem score = median of that problem's case scores
    model score   = median of problem scores
    ```

The workload inputs are not enlarged or changed. Long-enough measurement
windows are produced by repeating the same curated case many times inside a
batch and dividing by the repeat count.

## Current Local Results

The completed Python runs are:

```text
gemma4:e4b   -> 44 problems, 4,167 cases, 41,670 measurement rows
qwen2.5:7b   -> 41 problems, 4,166 cases, 41,660 measurement rows
qwen3:4b     -> 26 problems, 2,494 cases, 24,940 measurement rows
```

The exact common comparison across all three models is:

```text
11 common problems
1,098 common cases
```

## Publisher Flow To PerfArena

Publishing is separate from measuring. The publisher turns local files into one
compact HTTP payload per model.

Command shape:

```bash
export ARENA_API_KEY=<admin-api-key>

perfarena leetcode-publish-casewise \
  --base-url https://perfarena.ngrok.app \
  --model gemma4:e4b \
  --model-slug ollama__gemma4_e4b \
  --language python
```

Publisher code path:

```text
perfarena/cli.py
perfarena/tools/publish_leetcode_casewise.py
perfarena/leetcode_energy.py
```

What the publisher reads:

```text
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_summary.json
perfarena_out/leetcode_measurements/<model_slug>/python_casewise.jsonl
```

What it sends:

```http
POST /api/admin/measurements/local/runs
Authorization: Bearer <ARENA_API_KEY>
```

The uploaded payload includes compact run, problem, and case summaries,
protocol settings, machine metadata, source hashes, workload hashes, and
medians. It excludes source code, local paths, raw powermetrics files, and
LeetCode credentials.

The `perfarena-leetcode` backend validates and stores the upload in SQLite:

```text
localmeasurementrun
localproblemmeasurement
localcasemeasurement
```

## What A Server Version Should Automate

A streamlined server runner should preserve the same separation of concerns:

```text
measurement worker
  fetch accepted solutions
  validate against curated workload
  measure execution energy/runtime
  write local artifacts
  publish compact summaries

PerfArena web backend
  receive already-computed summaries
  validate/recompute aggregates
  store immutable run/problem/case rows
  render Local Energy UI
```

Recommended server responsibilities:

- Run measurements outside the web process as a scheduled/background worker.
- Keep `perfarena_out` or an equivalent artifact directory on persistent
  storage for audit and resume.
- Publish only compact summaries through the existing admin API.
- Preserve the existing metric-source labels:

  ```text
  LeetCode judge
  Local benchmark · powermetrics
  Generation client
  ```

- Keep model comparisons restricted to compatible machine/protocol cohorts and
  exact common `(problem, case_hash)` intersections.

Backend-specific note: the current implementation measures on macOS using
Apple `powermetrics`. A Linux server would need an equivalent backend, such as
RAPL, and should record a different `energy_source`/protocol so results are
not mixed with the existing Apple powermetrics cohort.

## Files To Share With A Teammate

For someone who wants to publish existing measurements:

```text
1. This Energy-Languages branch.
2. perfarena_out/leetcode_measurements/ollama__gemma4_e4b/
3. perfarena_out/leetcode_measurements/ollama__qwen2.5_7b/
4. perfarena_out/leetcode_measurements/ollama__qwen3_4b/
```

The compact share tarball includes the required files without raw telemetry:

```text
local-energy-measurements-share.tar.gz
```

For someone who wants to re-measure, also provide the curated dataset:

```text
../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl
```
