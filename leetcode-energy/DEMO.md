# LeetCode-Energy Demo: Dataset To Energy

This walkthrough uses the PerfArena dataset API as the correctness source. It
does not submit to LeetCode and does not require LeetCode browser headers.

The flow is:

1. Import already-judged accepted solutions from `/api/datasets/solutions`.
2. Store the exact dataset code under a model-scoped local path.
3. Sync shared local validation workloads.
4. Validate and measure energy for accepted Python solutions.

## 1. Start In Energy-Languages

```bash
cd /Users/haile/Desktop/spring26/sanad_lab/perfArena/Energy-Languages
source .venv/bin/activate
```

Use the hosted PerfArena dataset API:

```bash
export PERFARENA_LEETCODE_BASE_URL=https://perfarena.ngrok.app
```

## 2. Recommended: Measure A Model By Name

Use the model name shown by PerfArena. The command fetches accepted Python rows
for that model, imports them into model-scoped source files, syncs the curated
dataset workloads, validates each accepted solution, and measures energy:

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

The command writes:

```text
perfarena_out/leetcode_imports/<model_slug>/python_progress.json
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<slug>/solution.py
perfarena_out/leetcode_measurements/<model_slug>/python_curated.jsonl
perfarena_out/leetcode_measurements/<model_slug>/python_curated_summary.{json,csv,md}
```

If `python_curated.jsonl` already exists for that model, the command prints the
existing paths and exits without remeasuring. Use `--rerun` only when you
intentionally want to replace an existing run.

## 3. Manual Import Accepted Python Solutions

```bash
perfarena leetcode-import-solutions \
  --base-url "$PERFARENA_LEETCODE_BASE_URL" \
  --languages python \
  --model gemma4:e4b \
  --accepted-only \
  --progress perfarena_out/leetcode_dataset_import_progress.json \
  --overwrite
```

What this does:

- Streams NDJSON rows from `/api/datasets/solutions`.
- Filters to Python accepted rows for the requested model.
- Writes `problem.json`, `solution.py`, and a local `Makefile`.
- Writes `result_<model_slug>.json` with the accepted status and dataset
  provenance.
- Writes `perfarena_out/leetcode_dataset_import_progress.json`.

Check which model slug was imported:

```bash
python3 - <<'PY'
import json
from pathlib import Path

progress = json.loads(Path("perfarena_out/leetcode_dataset_import_progress.json").read_text())
print(progress["dataset_import_stats"]["by_model_slug"])
PY
```

Use that slug in the next commands. For Ollama `gemma4:e4b`, it is usually:

```text
ollama__gemma4_e4b
```

The one-command workflow stores measured source in
`perfarena_out/leetcode_dataset_solutions/<model_slug>/...` instead of relying
on the shared `leetcode-energy/Python/<slug>/solution.py` staging file.

## 4. Compile One Imported Cell

```bash
cd leetcode-energy/Python/check-if-two-string-arrays-are-equivalent
make compile
cd ../../..
```

For Python, `compile` runs:

```bash
python3 -m py_compile solution.py
```

## 5. Build Shared Validation Workloads

```bash
perfarena leetcode-workload-build \
  --progress perfarena_out/leetcode_dataset_import_progress.json \
  --language python \
  --model-slug ollama__gemma4_e4b \
  --accepted-only \
  --overwrite
```

This writes:

```text
leetcode-energy/reference/workloads/<slug>.json
leetcode-energy/reference/outputs/<slug>.json
```

## 6. How The Validation Cases Are Produced

The workload now comes from the curated LeetCodeDataset93 export, not the old
local type-template generator. The source dataset contains generated cases from
LeetCodeDataset v0.3.1. Our curation pass removes malformed and
constraint-violating cases, corrects one independently verified expected
output, and adds semantic validators where multiple outputs are valid.

Sync the 93 audited workloads:

```bash
perfarena leetcode-curated-sync \
  --dataset ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --prune
```

This produces 9,152 fixed cases. There is no random generation during
validation or measurement.

Interpretation:

- The dataset API accepted status remains the correctness oracle.
- The local cases are the reproducible energy workload, not a replacement for
  LeetCode hidden tests.
- Tree and linked-list cases are supported by the curated Python harness.
- Two accepted problems are absent from the 93-problem dataset and are skipped:
  `design-a-stack-with-increment-operation` and `random-pick-index`.

## 7. Manual Measure Energy

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

Per-problem summaries:

```text
leetcode-energy/Python/<slug>/energy_curated_ollama__gemma4_e4b.json
```

Aggregate rows:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_curated.jsonl
```

Rows keep the CLBG-compatible measurement fields:

```json
{
  "test": "split-array-largest-sum",
  "language": "Python",
  "iteration": 13,
  "phase": "measure",
  "wall_ms": 785.902,
  "rapl_pkg_delta_raw": 19000,
  "energy_source": "codecarbon",
  "exit_code": 0
}
```

Rows also include LeetCode metadata:

```json
{
  "benchmark": "leetcode-energy-curated",
  "model_slug": "ollama__gemma4_e4b",
  "leetcode_language": "python3",
  "accepted": true,
  "workload_hash": "...",
  "source": "perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<slug>/solution.py",
  "result_path": "leetcode-energy/Python/<slug>/result_ollama__gemma4_e4b.json"
}
```

## 8. Inspect Results

Count aggregate rows:

```bash
wc -l perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_curated.jsonl
```

Summarize measured versus skipped accepted solutions:

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("leetcode-energy/Python")
files = list(root.glob("*/energy_curated_ollama__gemma4_e4b.json"))
measured = []
skipped = {}

for path in files:
    data = json.loads(path.read_text())
    if data.get("measured"):
        measured.append(path)
    else:
        reason = data.get("skipped_reason", "unknown")
        skipped[reason] = skipped.get(reason, 0) + 1

print("accepted summaries:", len(files))
print("measured:", len(measured))
print("skipped:", sum(skipped.values()))
for reason, count in sorted(skipped.items()):
    print(count, reason)
PY
```

## 9. Future Cross-Language Runs

The workload and expected-output JSON files belong to the problem, not to a
language. When Java, C++, Rust, Go, and other adapters are added, they should
read the same files under `leetcode-energy/reference/` so energy comparisons
use identical inputs.
