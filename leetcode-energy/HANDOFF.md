# LeetCode Energy Handoff

Last updated: 2026-06-23

This handoff covers the LeetCode energy work in `Energy-Languages`. The current
pipeline measures Python solutions already accepted by PerfArena against the
unchanged curated LeetCodeDataset93 workloads. It no longer submits to
LeetCode, no longer requires Docker for correctness checks, and no longer uses
synthetic stress cases.

## Current Status

The completed main result is the Gemma Python casewise run:

```text
model: ollama__gemma4_e4b
language: python
measured problems: 44
complete cases: 4167
measurement rows: 41670
skipped problems: 2
failed problems: 0
run duration: about 17 hours 19 minutes
```

The skipped accepted problems were missing from the curated LeetCodeDataset93
workloads:

```text
design-a-stack-with-increment-operation
random-pick-index
```

Keep these files as the main Gemma result:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise.jsonl
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_cases.csv
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_problems.csv
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_summary.json
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_summary.md
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/powermetrics/
```

The summary markdown has been expanded with methodology, CSV field definitions,
batch-measurement explanation, powermetrics integration, and the observed run
duration:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_summary.md
```

## Methodology In Short

For every accepted problem:

1. Start one persistent Python worker.
2. Load the accepted source and curated workload.
3. Validate the solution against every curated case.
4. Warm up by sweeping unchanged cases for 60 seconds.
5. Calibrate each unchanged case to find `batch_calls`, the repeat count that
   makes one measured batch last about one second.
6. Run ten measured batches per case.
7. Use direct Apple `powermetrics` at 100 ms to integrate CPU energy during each
   measured batch.
8. Normalize each row:

```text
wall_ms_per_call = batch_wall_ms / batch_calls
cpu_energy_j_per_call = batch_cpu_energy_j / batch_calls
```

9. Case score: median of ten normalized rows.
10. Problem score: median of that problem's case medians.
11. Model score: median of completed problem scores, or common-intersection
    medians when comparing multiple models.

A batch is repeated execution of the same unchanged case. It is not a larger
input. For example, if calibration picks `batch_calls = 2,000,000`, then ten
measured batches means 20,000,000 measured calls for that case, plus validation,
warmup, and calibration calls that are not used in the reported median.

## Important Difference From Stress Runs

The old stress workflow selected a few problems and enlarged or modified
workloads to make them heavier. That reduced measurement noise, but it changed
the benchmark cases.

The current casewise workflow does not alter inputs or expected outputs. It
repeats each curated case enough times to produce a measurable batch, then
divides by the repeat count. This is cleaner for model and language comparison
because the workload remains the same audited LeetCodeDataset93 workload.

Old smoke and synthetic stress result files were removed from the active result
directory. The preserved historical non-casewise outputs are still separate
from the current casewise outputs.

## Main Implementation Files

```text
perfarena/casewise_energy.py
perfarena/runners/leetcode_case_worker.py
perfarena/tools/summarize_leetcode_casewise.py
perfarena/cli.py
perfarena/tests/test_casewise_energy.py
perfarena/tests/test_leetcode_energy.py
leetcode-energy/README.md
leetcode-energy/DEMO.md
```

Key CLI commands:

```text
perfarena leetcode-measure-model
perfarena leetcode-case-measure
perfarena leetcode-compare-models
```

The implementation is Python-only for measurement right now. The curated
workloads are shared and stable, so future Java, C++, Rust, etc. runners should
measure against the same workload files:

```text
leetcode-energy/reference/workloads/<slug>.json
```

## Environment Requirements

Work from:

```bash
cd /Users/haile/Desktop/spring26/sanad_lab/perfArena/Energy-Languages
source .venv/bin/activate
export PERFARENA_LEETCODE_BASE_URL=https://perfarena.ngrok.app
```

The machine must be macOS with scoped passwordless sudo for
`/usr/bin/powermetrics`:

```bash
sudo -n /usr/bin/powermetrics \
  --samplers cpu_power -i 100 -n 1 -o /dev/null
```

This setup was configured locally with:

```sudoers
haile ALL=(root) NOPASSWD: /usr/bin/powermetrics
```

Only grant the exact powermetrics binary. Do not grant passwordless access to
arbitrary commands.

## Run A New Model

Use the model name from PerfArena, not the local slug:

```bash
perfarena leetcode-measure-model \
  --base-url "$PERFARENA_LEETCODE_BASE_URL" \
  --model qwen2.5:7b \
  --language python \
  --accepted-only \
  --curated-dataset ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --warmup-seconds 60 \
  --measurements 10 \
  --batch-seconds 1 \
  --powermetrics-interval-ms 100 \
  --resume
```

This command:

1. Fetches accepted Python solutions from PerfArena's dataset API.
2. Stores model-scoped source files under:

```text
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<slug>/solution.py
```

3. Builds/imports progress under:

```text
perfarena_out/leetcode_imports/<model_slug>/python_progress.json
```

4. Measures and summarizes under:

```text
perfarena_out/leetcode_measurements/<model_slug>/python_casewise.jsonl
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_cases.csv
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_problems.csv
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_summary.json
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_summary.md
perfarena_out/leetcode_measurements/<model_slug>/powermetrics/
```

Use `--resume` after interruption. Use `--rerun` only when intentionally
replacing that model's existing casewise JSONL.

## Rerun Or Resume Existing Gemma

The existing Gemma result should not be rerun unless intentionally replacing
it. To resume only if new rows are missing:

```bash
perfarena leetcode-case-measure \
  --model-slug ollama__gemma4_e4b \
  --progress perfarena_out/leetcode_python_real_with_snippets_progress.json \
  --language python \
  --warmup-seconds 60 \
  --measurements 10 \
  --batch-seconds 1 \
  --powermetrics-interval-ms 100 \
  --resume
```

Expected behavior now: it should find completed rows and avoid repeating them.

## Compare Models

After measuring multiple models:

```bash
perfarena leetcode-compare-models \
  --models ollama__gemma4_e4b,ollama__qwen2_5_7b,provider__third_model \
  --language python
```

The comparison uses only the common completed `(problem, case_hash)` intersection
across all selected models. This prevents a model with fewer accepted problems
or fewer completed cases from being compared on an easier set.

Outputs go under:

```text
perfarena_out/leetcode_measurements/comparisons/
```

## Tests

Run the focused tests:

```bash
python -m pytest perfarena/tests/test_casewise_energy.py \
  perfarena/tests/test_leetcode_energy.py
```

Most recent focused test run:

```text
python -m pytest perfarena/tests/test_casewise_energy.py
12 passed
```

Earlier full test status after the casewise implementation:

```text
67 passed, 2 warnings
```

The warnings were from legacy CodeCarbon profiler tests, not the new
powermetrics casewise path.

## Caveats

- Measurement is Python-only for now.
- Powermetrics values are estimated machine-wide CPU power. Use them for
  controlled same-device comparisons, not cross-device rankings.
- No idle baseline is subtracted.
- The summary generator does not infer wall-clock experiment duration from JSONL
  rows. The Gemma `17h 19m` duration came from observed run start/end times and
  is manually documented in the generated summary markdown.
- Regenerating `python_casewise_summary.md` with the current summarizer can
  overwrite the manual run-duration note. Re-add it or add explicit run metadata
  support before regenerating presentation artifacts.
- Keep the curated workload files as the source of truth. Do not regenerate
  larger synthetic cases for the main comparison.
- There are many unrelated dirty files in this working tree, including
  generated problem metadata and cache artifacts. Avoid cleaning or reverting
  unrelated files unless explicitly requested.

## Useful Status Checks

Check whether a long run is active:

```bash
screen -ls
ps -ax -o pid=,etime=,%cpu=,state=,command= \
  | rg 'leetcode-case-measure|leetcode_case_worker|powermetrics --samplers' \
  | rg -v 'rg '
```

Check progress for a casewise JSONL:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

path = Path("perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise.jsonl")
rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
measured = [row for row in rows if row.get("phase") == "measure"]
statuses = [row for row in rows if row.get("phase") == "status"]
counts = Counter(row["problem"] for row in measured)
print("measurement_rows", len(measured))
print("problems_started", len(counts))
print("status_rows", len(statuses))
if measured:
    row = measured[-1]
    print("last", row["problem"], row["case_index"], row["measurement_iteration"])
PY
```

## Next Good Steps

1. Measure `qwen2.5:7b` and any other PerfArena model using
   `leetcode-measure-model`.
2. Compare measured models with `leetcode-compare-models`.
3. Add explicit run start/end metadata to `python_casewise.jsonl` or summary
   JSON so run duration is generated automatically.
4. Add non-Python workers only after deciding how to reconstruct each curated
   case in that language without changing the workload.
