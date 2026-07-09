# Local Energy Publishing Handoff

This document explains which files hold the local LeetCode energy measurements
and how the `Energy-Languages` publisher sends them to the PerfArena website.
For the broader local measurement workflow and `perfarena_out` structure, see
[Local Measurement Architecture](LOCAL_MEASUREMENT_ARCHITECTURE.md).

## Repository Roles

```text
Energy-Languages
  Owns measurement inputs, measured solution files, local result files, and the
  publisher CLI.

perfarena-leetcode
  Owns the website/backend API, validates uploaded summaries, stores them in
  SQLite, and renders the Local Energy UI.
```

The two repositories communicate over HTTP. `Energy-Languages` does not write
directly to the website database.

## Measurement File Layout

The completed local measurements are stored under:

```text
perfarena_out/leetcode_measurements/<model_slug>/
```

Current measured model folders:

```text
perfarena_out/leetcode_measurements/ollama__gemma4_e4b/
perfarena_out/leetcode_measurements/ollama__qwen2.5_7b/
perfarena_out/leetcode_measurements/ollama__qwen3_4b/
```

Each folder contains the same core files:

```text
python_casewise.jsonl
python_casewise_cases.csv
python_casewise_problems.csv
python_casewise_summary.json
python_casewise_summary.md
```

Publishing requires:

```text
python_casewise_summary.json
python_casewise.jsonl
```

Recommended to share for review/debugging:

```text
python_casewise_cases.csv
python_casewise_problems.csv
python_casewise_summary.md
```

The publisher does not upload raw `powermetrics` plist files, raw local paths,
or measured source code.

## Source And Workload Layout

Measured accepted source files are stored separately from the published
measurement summaries:

```text
perfarena_out/leetcode_dataset_solutions/<model_slug>/Python/<problem_slug>/solution.py
```

The curated workload dataset lives outside this repo:

```text
../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl
```

These files are needed to re-measure. They are not needed to publish an already
completed casewise result.

## Publisher Code Path

Run the publisher through the CLI:

```bash
perfarena leetcode-publish-casewise \
  --base-url https://perfarena.ngrok.app \
  --model <perfarena-model-name> \
  --model-slug <local-model-slug> \
  --language python
```

Important implementation files:

```text
perfarena/cli.py
perfarena/tools/publish_leetcode_casewise.py
perfarena/leetcode_energy.py
```

Flow:

```text
1. perfarena/cli.py handles `leetcode-publish-casewise`.
2. It finds the model folder under perfarena_out/leetcode_measurements/<model_slug>/.
3. publish_leetcode_casewise.py reads python_casewise_summary.json.
4. publish_leetcode_casewise.py reads python_casewise.jsonl only to extract host metadata.
5. It builds one compact JSON payload with run, problem, and case summaries.
6. leetcode_energy.py POSTs the payload to the PerfArena website API.
```

## Destination API

The publisher sends the payload to:

```http
POST /api/admin/measurements/local/runs
Authorization: Bearer <ARENA_API_KEY>
```

For local preview:

```text
http://localhost:8013/api/admin/measurements/local/runs
```

For live:

```text
https://perfarena.ngrok.app/api/admin/measurements/local/runs
```

The live site stores accepted uploads in its Docker SQLite database:

```text
/data/arena.db
```

Tables:

```text
localmeasurementrun
localproblemmeasurement
localcasemeasurement
```

## Payload Contents

The uploaded payload includes:

```text
model_name
model_version
model_slug
language
harness_slug = local-powermetrics
benchmark = leetcode-energy-casewise
energy_source = powermetrics-cpu
machine_metadata
measurement protocol
duration_seconds
problem summaries
case summaries
workload hashes
source hashes
```

The uploaded payload excludes:

```text
source code
raw powermetrics files
raw local file paths
full raw batch JSONL
LeetCode cookies or session data
```

The website recomputes problem/model aggregates from the uploaded case rows and
rejects payloads whose counts, medians, hashes, or measurement iterations do
not match.

## Dry Run

Always dry-run before uploading:

```bash
export ARENA_API_KEY=<admin-api-key>

perfarena leetcode-publish-casewise \
  --base-url https://perfarena.ngrok.app \
  --model gemma4:e4b \
  --model-slug ollama__gemma4_e4b \
  --language python \
  --dry-run
```

The dry run prints the canonical payload hash, counts, duration, and machine
metadata without sending anything.

## Publish Current Runs

```bash
export ARENA_API_KEY=<admin-api-key>

perfarena leetcode-publish-casewise \
  --base-url https://perfarena.ngrok.app \
  --model gemma4:e4b \
  --model-slug ollama__gemma4_e4b \
  --language python

perfarena leetcode-publish-casewise \
  --base-url https://perfarena.ngrok.app \
  --model qwen2.5:7b \
  --model-slug ollama__qwen2.5_7b \
  --language python

perfarena leetcode-publish-casewise \
  --base-url https://perfarena.ngrok.app \
  --model qwen3:4b \
  --model-slug ollama__qwen3_4b \
  --language python
```

Expected uploaded counts:

```text
gemma4:e4b   -> 44 problems, 4,167 cases
qwen2.5:7b   -> 41 problems, 4,166 cases
qwen3:4b     -> 26 problems, 2,494 cases
```

After all three are published, the website Local Energy comparison should show:

```text
11 common problems
1,098 common cases
```

## What To Send To Another Machine

If another person will publish from their machine, send:

```text
1. This Energy-Languages branch.
2. The three perfarena_out/leetcode_measurements/<model_slug>/ folders.
```

They do not need the curated dataset or measured solution files unless they
want to re-run measurement instead of publishing existing results.
