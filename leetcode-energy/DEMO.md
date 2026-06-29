# Demo: PerfArena Solution To Casewise Energy

## 1. Activate The Environment

```bash
cd /Users/haile/Desktop/spring26/sanad_lab/perfArena/Energy-Languages
source .venv/bin/activate
export PERFARENA_LEETCODE_BASE_URL=https://perfarena.ngrok.app
```

The dataset endpoint supplies solutions that PerfArena has already judged.
This workflow does not contact LeetCode and does not require Docker.

## 2. Verify Powermetrics Access

```bash
sudo -n /usr/bin/powermetrics \
  --samplers cpu_power -i 100 -n 1 -o /dev/null
```

This must succeed without prompting. The benchmark starts one continuous
privileged sampler per problem and records its raw NUL-delimited plist output.

## 3. Run A Model End To End

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

The command:

1. Fetches accepted Python rows for `qwen2.5:7b`.
2. Writes immutable model-scoped source files.
3. Syncs all 93 curated workloads.
4. Validates each selected solution against its complete workload.
5. Warms one persistent worker for 60 seconds per problem.
6. Calibrates each unchanged case to an approximately one-second batch.
7. Measures each case once in each of ten shuffled rounds.
8. Flushes every row so `--resume` can continue after interruption.
9. Generates case, problem, and methodology summaries.

No random cases are generated. The input and expected output for every case are
copied unchanged from the audited LeetCodeDataset93 record. Repetition only
extends the observation window.

## 4. Inspect The Result

Replace `<model_slug>` with the slug printed by the command:

```bash
cat perfarena_out/leetcode_measurements/<model_slug>/python_casewise_summary.md
```

The detailed files are:

```text
python_casewise.jsonl           one auditable row per measured batch
python_casewise_cases.csv       median and CV from ten rows per case
python_casewise_problems.csv    median of case medians per problem
python_casewise_summary.json    complete structured summary
python_casewise_summary.md      generated methodology and example
powermetrics/<slug>.plist.gz    raw NUL-delimited sampler output
```

One JSONL row stores both total and normalized values:

```json
{
  "problem": "two-sum",
  "case_index": 0,
  "measurement_iteration": 1,
  "batch_calls": 2000,
  "batch_wall_ms": 1200.0,
  "wall_ms_per_call": 0.6,
  "cpu_energy_j": 6.0,
  "cpu_energy_j_per_call": 0.003,
  "powermetrics_samples": 10
}
```

## 5. Resume Or Restart

Rerun the same command with `--resume` to keep completed rows. Use `--rerun`
only when intentionally replacing the complete casewise run for that model.

## 6. Compare Models Fairly

```bash
perfarena leetcode-compare-models \
  --models ollama__gemma4_e4b,ollama__qwen2_5_7b,provider__third_model \
  --language python
```

The command discards any case not completed by every requested model, computes
each problem from matched case medians, and ranks models by the median matched
problem CPU energy. This prevents a model with a smaller or easier accepted set
from receiving an unfair score.
