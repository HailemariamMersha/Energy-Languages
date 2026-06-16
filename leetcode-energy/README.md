# LeetCode-Energy Pipeline

This folder stages already-judged LeetCode solutions from the PerfArena dataset
API, then measures accepted solutions locally against shared workloads.

Each problem cell has:

- `problem.json`: problem metadata and starter snippets when available.
- `solution.<ext>`: optional human-inspection source or starter scaffold.
- `Makefile`: local `compile`, `validate`, `measure`, and `clean` targets.

The correctness oracle is the dataset API row that already contains the backend
judge status. The energy phase does not submit to LeetCode and does not need
LeetCode cookies.

For model-selected measurement, imported source is stored under:

```text
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<slug>/solution.py
```

That model-scoped source path is what measurement uses. This prevents a later
model import from overwriting the code measured for an earlier model.

For a full walkthrough, see [DEMO.md](DEMO.md).

## 1. Enter The Repo

```bash
cd /Users/haile/Desktop/spring26/sanad_lab/perfArena/Energy-Languages
source .venv/bin/activate
```

## 2. Run Tests

```bash
python -m pytest perfarena/tests/test_leetcode_energy.py
```

## 3. Choose The Dataset API

Use the hosted dataset API:

```bash
export PERFARENA_LEETCODE_BASE_URL=https://perfarena.ngrok.app
```

Or use a local backend:

```bash
export PERFARENA_LEETCODE_BASE_URL=http://localhost:8000
```

No API key is required for the public dataset import endpoint.

## 4. One-Command Model Measurement

For a new Python model already submitted to PerfArena, pass the PerfArena
`model_name` and let the command import accepted rows, sync the curated
workloads, validate locally, measure energy, and write summaries:

```bash
perfarena leetcode-measure-model \
  --base-url "$PERFARENA_LEETCODE_BASE_URL" \
  --model gemma4:e4b \
  --language python \
  --accepted-only \
  --curated-dataset ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --warmup 3 \
  --measure 10 \
  --idle-s 2 \
  --case-repeat 1
```

Outputs are model-scoped:

```text
perfarena_out/leetcode_imports/<model_slug>/python_progress.json
perfarena_out/leetcode_measurements/<model_slug>/python_curated.jsonl
perfarena_out/leetcode_measurements/<model_slug>/python_curated_summary.{json,csv,md}
```

If the aggregate output already exists, the command skips measurement by
default. Use `--rerun` to replace it or `--append` to append rows. Existing
Gemma outputs under `perfarena_out/leetcode_measurements/ollama__gemma4_e4b/`
are therefore left untouched unless explicitly rerun.

Python is the only supported language for this command today. The shared
workloads are language-independent, but non-Python curated runners still need
to be added.

## 5. Manual Import Accepted Solutions

Import accepted Python solutions and stage the exact stored code into
`leetcode-energy/Python/<slug>/solution.py`:

```bash
perfarena leetcode-import-solutions \
  --base-url "$PERFARENA_LEETCODE_BASE_URL" \
  --languages python \
  --model gemma4:e4b \
  --accepted-only \
  --progress perfarena_out/leetcode_dataset_import_progress.json \
  --overwrite
```

The importer writes per-problem result files:

```text
leetcode-energy/Python/<slug>/result_<model_slug>.json
```

It also writes a progress file that the workload and measurement commands use:

```text
perfarena_out/leetcode_dataset_import_progress.json
```

The `model_slug` is derived from the dataset trace provider and model name. For
example, `provider=ollama` and `model_name=gemma4:e4b` becomes:

```text
ollama__gemma4_e4b
```

## 6. Sync Curated Shared Workloads

Sync the audited LeetCodeDataset93 cases into the CLBG-style shared reference
tree:

```bash
perfarena leetcode-curated-sync \
  --dataset ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --prune
```

This writes:

```text
leetcode-energy/reference/workloads/<slug>.json
```

There are 93 workload files containing 9,152 cases. The cases are
language-independent; the embedded Python harness supplies the current Python
semantic validator. Future Java, C++, Rust, Go, and other adapters must execute
the same cases and reproduce those semantic rules.

## 7. Manual Measure Energy

Run local energy measurement for accepted Python solutions:

```bash
perfarena leetcode-measure \
  --progress perfarena_out/leetcode_python_real_with_snippets_progress.json \
  --language python \
  --model-slug ollama__gemma4_e4b \
  --accepted-only \
  --warmup 3 \
  --measure 10 \
  --idle-s 2 \
  --case-repeat 1 \
  --curated-dataset \
    ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --output \
    perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_curated.jsonl \
  --reset-output
```

Per-problem summaries are written to:

```text
leetcode-energy/Python/<slug>/energy_curated_ollama__gemma4_e4b.json
```

The aggregate JSONL is written to:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_curated.jsonl
```

## 8. Measurement Behavior

Each accepted solution first runs the complete curated semantic harness. A
validation failure prevents energy measurement. Measured child processes then
execute only the solution calls extracted from that harness, excluding expected
output comparison and PerfArena CLI/provider imports.

On macOS, energy is reported by CodeCarbon. `rapl_pkg_delta_raw` stores
microjoules for schema compatibility; CodeCarbon data is an estimate unless a
supported hardware power interface is available. Idle, warmup, and measurement
rows are retained separately.

CodeCarbon JSONL produced before June 14, 2026 by this fork used an incorrect
kWh-to-microjoule factor and is lower by 1,000. Regenerate those files before
comparing them with curated results.

## 9. Regenerating Results

Generated files such as `result_<model_slug>.json`,
`energy_<model_slug>.json`, and aggregate JSONL files are intentionally not
kept in this clean scaffold. Recreate them with:

```bash
perfarena leetcode-import-solutions ...
perfarena leetcode-curated-sync ...
perfarena leetcode-measure --curated-dataset ...
```

Summarize a completed run:

```bash
.venv/bin/python -m perfarena.tools.summarize_leetcode_energy \
  perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_curated.jsonl \
  --summaries-root leetcode-energy/Python \
  --output-prefix \
    perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_curated_summary
```
