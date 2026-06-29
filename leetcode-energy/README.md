# LeetCode Energy Pipeline

This tree stages solutions already judged by PerfArena and measures accepted
Python solutions against the unchanged curated LeetCodeDataset93 cases. It does
not submit to LeetCode and does not require LeetCode cookies or Docker.

The current measurement backend is direct Apple `powermetrics`. Historical
CLBG and `python_curated*` outputs still use CodeCarbon and are preserved, but
they are not produced by the casewise commands below.

## Data Flow

1. Fetch accepted solutions from `GET /api/datasets/solutions`.
2. Store each source under a model-specific path.
3. Sync the audited LeetCodeDataset93 workloads.
4. Validate each accepted solution against its complete workload.
5. Measure every unchanged case independently with direct `powermetrics`.
6. Summarize case medians, then problem medians.
7. Compare models only over their common completed case intersection.

Model-specific source files are stored at:

```text
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<slug>/solution.py
```

The optional `leetcode-energy/Python/<slug>/solution.py` file is only for human
inspection. It is not the measurement source of truth.

## Prerequisites

```bash
cd /Users/haile/Desktop/spring26/sanad_lab/perfArena/Energy-Languages
source .venv/bin/activate
export PERFARENA_LEETCODE_BASE_URL=https://perfarena.ngrok.app
```

The command requires macOS and scoped passwordless sudo for
`/usr/bin/powermetrics`. Verify the final configuration with:

```bash
sudo -n /usr/bin/powermetrics \
  --samplers cpu_power -i 100 -n 1 -o /dev/null
```

Grant only the exact `powermetrics` executable through `visudo`; do not grant
passwordless access to arbitrary commands. The CLI fails before measuring if
this check is unavailable.

Run the tests with:

```bash
python -m pytest perfarena/tests/test_leetcode_energy.py \
  perfarena/tests/test_casewise_energy.py
```

## Measure One Model

Use the model name shown by PerfArena:

```bash
perfarena leetcode-measure-model \
  --base-url "$PERFARENA_LEETCODE_BASE_URL" \
  --model gemma4:e4b \
  --language python \
  --accepted-only \
  --curated-dataset ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --warmup-seconds 60 \
  --measurements 10 \
  --batch-seconds 1 \
  --powermetrics-interval-ms 100 \
  --resume
```

The command imports accepted sources, synchronizes workloads, validates, then
measures. Python is the only measured language in this version.

Use `--resume` after interruption. Completed `(problem, case, iteration)` rows
are not repeated. Use `--rerun` only to delete and replace that model's
casewise JSONL.

For an already imported model or the original Gemma progress file:

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

The completed Gemma run on this Mac measured 44 problems, 4,167 curated cases,
and 41,670 measurement rows. The clean detached run started at about
2026-06-22 16:43 and finished at about 2026-06-23 10:03, so the full run took
about 17 hours 19 minutes. The process is wrapped in `caffeinate`, and a
checkpoint is flushed after every valid measurement row.

## Measurement Protocol

For each accepted problem, the runner starts one persistent Python worker.
Imports and worker startup occur before any measured case.

1. The worker validates the solution against every curated case.
2. It repeatedly sweeps all cases for 60 seconds.
3. Warmup drift compares the median sweep time in the final two 10-second
   windows. A difference above 5% is recorded as unstable; it does not silently
   discard the result.
4. Each case is calibrated once to find an invocation count lasting about one
   second. The input and expected output are not enlarged or modified.
5. Ten deterministic shuffled rounds run. Every case appears once per round.
6. One continuous `powermetrics` process samples CPU power and thermal state at
   100 ms for the problem.
7. A row is retained only when at least five complete nominal thermal samples
   fall inside its batch window. Invalid rows are retried.
8. Batch values are normalized by the fixed invocation count.

For a batch of 2,000 calls taking 1.2 seconds and using 6 J:

```text
wall_ms_per_call       = 1200 ms / 2000 = 0.6 ms
cpu_energy_j_per_call  = 6 J / 2000 = 0.003 J
```

The case result is the median of its ten normalized rows. The problem result is
the median of all completed case medians. This ordering is intentional: the
runner never takes a median over a whole problem sweep.

`powermetrics` reports estimated machine-wide CPU power. The benchmark does not
subtract an idle baseline. Results are suitable for controlled comparisons on
the same Mac, power configuration, and protocol, not cross-device ranking.

The runner starts `/usr/bin/powermetrics` once per problem with the
`cpu_power`, `gpu_power`, `ane_power`, and `thermal` samplers. The process runs
continuously while all cases for that problem are measured and writes a raw
NUL-delimited plist stream. For each measured batch, the runner keeps only
samples whose time windows are fully inside the batch start and end times. CPU
energy for that batch is the integral of sampled CPU power over those included
sample windows:

```text
sample_energy_j = sample_cpu_power_w * sample_elapsed_seconds
batch_cpu_energy_j = sum(sample_energy_j for included samples)
cpu_energy_j_per_call = batch_cpu_energy_j / batch_calls
```

Each retained row must have at least five included samples and nominal thermal
pressure. GPU and ANE energy are recorded as supporting fields, but the ranking
metric is CPU energy per call.

## Outputs

```text
perfarena_out/leetcode_imports/<model_slug>/python_progress.json
perfarena_out/leetcode_measurements/<model_slug>/python_casewise.jsonl
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_cases.csv
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_problems.csv
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_summary.json
perfarena_out/leetcode_measurements/<model_slug>/python_casewise_summary.md
perfarena_out/leetcode_measurements/<model_slug>/powermetrics/<slug>.plist.gz
```

Raw plist streams are compressed only after each problem's sampler stops, so
compression work is outside all measured windows. Every JSONL row retains batch
totals and normalized per-call values, stable
`case_index` and `case_hash`, solution/workload hashes, calibration count,
sample count, thermal state, raw sample path, warmup drift, and host metadata.

The shared workload source of truth remains:

```text
leetcode-energy/reference/workloads/<slug>.json
```

No synthetic stress files are generated.

### Current Gemma Result

The completed result to keep is:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise.jsonl
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_cases.csv
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_problems.csv
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_summary.json
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/python_casewise_summary.md
```

Run result:

```text
model: ollama__gemma4_e4b
language: python
measured problems: 44
complete cases: 4167
measurement rows: 41670
skipped problems: 2
failed problems: 0
model median problem CPU energy: 0.000007982333896755394 J per call
```

The skipped problems were accepted by LeetCode but are not in the curated
LeetCodeDataset93 workload set:

```text
design-a-stack-with-increment-operation
random-pick-index
```

Smoke-test outputs and the old synthetic stress result files were removed so
the directory presents only the current casewise benchmark result and preserved
historical non-casewise outputs.

### CSV Field Reference

`python_casewise_cases.csv` has one row per completed `(problem, case_hash)`.
Each row is calculated from exactly ten retained measurement rows for that same
case.

| Column | Meaning and calculation |
|---|---|
| `problem` | LeetCode title slug. |
| `case_index` | Stable index of the case inside the curated workload JSON. |
| `case_hash` | Content hash of that case input and expected output. This is used for cross-model matching. |
| `measurement_rows` | Number of retained measurement batches for the case. It should be `10` for complete cases. |
| `batch_calls` | Fixed number of repeated invocations selected during calibration to make this case take about one second per measured batch. |
| `median_wall_ms_per_call` | Median of the ten `batch_wall_ms / batch_calls` values. |
| `min_wall_ms_per_call` | Minimum of the ten normalized wall-time values. |
| `max_wall_ms_per_call` | Maximum of the ten normalized wall-time values. |
| `median_cpu_energy_j_per_call` | Median of the ten `batch_cpu_energy_j / batch_calls` values. This is the case energy score. |
| `min_cpu_energy_j_per_call` | Minimum of the ten normalized CPU-energy values. |
| `max_cpu_energy_j_per_call` | Maximum of the ten normalized CPU-energy values. |
| `energy_cv` | Coefficient of variation for the ten normalized CPU-energy values: sample standard deviation divided by mean. Lower means less spread across the ten repeats. |
| `median_cpu_power_w` | Median CPU power for the ten batches. Each batch power is `batch_cpu_energy_j / sampled_seconds`. |
| `median_powermetrics_samples` | Median number of included `powermetrics` samples across the ten batches. |
| `warmup_stable` | `True` when the final two 10-second warmup windows differ by no more than 5%. |
| `workload_hash` | Hash of the curated workload file used for this problem. |
| `source_hash` | Hash of the measured accepted Python source file. |

`python_casewise_problems.csv` has one row per completed problem. It is derived
from the rows in `python_casewise_cases.csv`.

| Column | Meaning and calculation |
|---|---|
| `problem` | LeetCode title slug. |
| `case_count` | Number of completed case rows included for this problem. |
| `expected_case_count` | Number of cases in the curated workload for this problem. `case_count` must match this for a complete problem. |
| `median_case_wall_ms` | Median of `median_wall_ms_per_call` across the problem's completed cases. |
| `median_case_cpu_energy_j` | Median of `median_cpu_energy_j_per_call` across the problem's completed cases. This is the problem energy score. |
| `median_case_energy_cv` | Median of `energy_cv` across the problem's cases. |
| `max_case_energy_cv` | Largest case-level energy CV in the problem. Useful for finding noisy cases. |
| `warmup_stable` | `True` only if the problem warmup was stable. |
| `workload_hash` | Hash of the curated workload file used for this problem. |

## Compare Models

After measuring at least two models:

```bash
perfarena leetcode-compare-models \
  --models ollama__gemma4_e4b,ollama__qwen2_5_7b \
  --language python
```

The comparison first intersects completed `(problem, case_hash)` pairs across
all requested models. It then recomputes problem medians and the model median
using only that matched set. Outputs are written under:

```text
perfarena_out/leetcode_measurements/comparisons/
```

## Methodology References

- [CodeCarbon methodology](https://mlco2.github.io/codecarbon/methodology)
- [Apple powermetrics reference](https://ss64.com/mac/powermetrics.html)
- [Virtual Machine Warmup Blows Hot and Cold](https://arxiv.org/abs/1602.00602)
- [Ranking programming languages by energy efficiency](https://doi.org/10.1016/j.scico.2021.102609)

See [DEMO.md](DEMO.md) for the complete operational walkthrough.
