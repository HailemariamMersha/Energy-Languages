# PerfArena local demo

A walkthrough of the full PerfArena pipeline running on a single
macOS laptop, using `gemma4:e4b` served by Ollama at
`llms.sanadlab.ngrok.app`. No Docker needed. No remote
measurement host. Everything runs locally.

This demo is illustrative. It shows the generation, compilation,
execution, static analysis, and statistics steps in one place so
you can see the end-to-end flow. Publishable measurements would
use the bare-metal reference host with RAPL, which is not
available on macOS.

---

## 0. Setup

```bash
cd /Users/rar9993/repos/research/perfarena/Energy-Languages

# Create and activate a virtualenv if you haven't already.
python3 -m venv .venv
source .venv/bin/activate

# Install the package and its dependencies.
pip install -e '.[dev]'

# Point the Ollama client at the remote endpoint.
export OLLAMA_HOST=https://llms.sanadlab.ngrok.app
```

Verify the CLI works:

```bash
perfarena --help
```

---

## 1. See what's configured

```bash
perfarena list-problems
perfarena list-languages
```

You should see tables with the 10 CLBG problems and the 10 target
languages.

---

## 2. Make sure the Makefiles are patched

If you haven't already:

```bash
perfarena patch-makefiles --repo .
```

This rewrites every benchmark Makefile for the 10 target languages
so they delegate to `perfarena.mk` and use `$(CC)` / `$(CXX)` /
`python3` instead of hardcoded 2017 paths.

---

## 3. Generate code with inference profiling

Generate 3 samples of the `binary-trees` benchmark in Python,
using `gemma4:e4b` through the profiling agent. The agent measures
wall time, CPU time, and peak RSS of each LLM call.

```bash
perfarena generate \
    --provider ollama \
    --model gemma4:e4b \
    --problem binary-trees \
    --language python \
    --samples 3 \
    --temperature 0.2 \
    --via-agent
```

Output goes to
`perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/`.

Check that the files are there:

```bash
ls -la perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/
```

You should see three groups of files:

```
sample_00.py              <- extracted source code
sample_00.py.raw.md       <- full LLM response
sample_00.py.meta.json    <- provenance + inference metrics
sample_01.py
sample_01.py.raw.md
sample_01.py.meta.json
sample_02.py
sample_02.py.raw.md
sample_02.py.meta.json
```

Inspect one of the meta files:

```bash
python3 -m json.tool perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/sample_00.py.meta.json
```

You should see the `inference.metrics` block with `wall_time_s`,
`cpu_time_s`, `peak_rss_kb`, and `energy_source` (which will be
`"none"` on macOS since RAPL is not available).

---

## 4. Look at the generated code

```bash
cat perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/sample_00.py
```

This is the source file PerfArena extracted from `gemma4:e4b`'s
response. It should be a standalone Python program that implements
the binary-trees benchmark.

---

## 5. Compile and run a generated sample locally

Copy the generated source into the benchmark cell and compile:

```bash
cp perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/sample_00.py \
    Python/binary-trees/binarytrees.py

cd Python/binary-trees
make compile
```

Run it:

```bash
make run
```

You should see the binary-trees output (stretch tree, long-lived
tree, and intermediate-depth tree checksums). If the LLM generated
correct code, the output will match the CLBG reference. If it
didn't, you'll see errors or wrong output, which is data too.

Go back to the repo root:

```bash
cd ../..
```

---

## 6. Run the same generation for more languages

Generate for all ten languages. This calls the remote Ollama
endpoint once per sample per language, so it takes a few minutes:

```bash
for lang in python javascript typescript java csharp cpp php go rust ruby; do
    echo "--- $lang ---"
    perfarena generate \
        --provider ollama \
        --model gemma4:e4b \
        --problem binary-trees \
        --language "$lang" \
        --samples 3 \
        --temperature 0.2 \
        --via-agent
done
```

Watch the inference metrics after each sample. You'll see how long
`gemma4:e4b` takes to generate code for each language and how much
memory the process uses.

---

## 7. Run static analysis on a generated sample

```bash
# Python (uses pylint if installed)
perfarena static-analyze \
    --language python \
    --source perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/sample_00.py
```

If pylint is installed, you'll get a JSON report with issue count,
lines of code, and issues per kLoC. If it isn't installed, the
output says `"available": false`.

Install pylint and try again:

```bash
pip install pylint
perfarena static-analyze \
    --language python \
    --source perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/sample_00.py
```

---

## 8. Generate for a second problem and compare inference costs

```bash
perfarena generate \
    --provider ollama \
    --model gemma4:e4b \
    --problem n-body \
    --language python \
    --samples 3 \
    --temperature 0.2 \
    --via-agent
```

Compare wall times between the two problems:

```bash
python3 -c "
import json, glob

for problem in ['binary-trees', 'n-body']:
    metas = sorted(glob.glob(f'perfarena_out/generations/ollama__gemma4_e4b/Python/{problem}/*.meta.json'))
    times = []
    for m in metas:
        d = json.load(open(m))
        t = d.get('inference', {}).get('metrics', {}).get('wall_time_s', 0)
        times.append(t)
    avg = sum(times) / len(times) if times else 0
    print(f'{problem:25s}  samples={len(times)}  avg_wall_s={avg:.2f}')
"
```

---

## 9. Quick statistics on the generated code

Even without RAPL measurements, you can use the stats layer to
play with mock data or to summarize inference times:

```bash
python3 << 'EOF'
import json, glob
from perfarena.stats import median_and_ci, harmonic_mean, break_even_point

# Collect inference wall times from the meta.json files.
metas = sorted(glob.glob(
    "perfarena_out/generations/ollama__gemma4_e4b/Python/binary-trees/*.meta.json"
))
times = []
for path in metas:
    d = json.load(open(path))
    t = d.get("inference", {}).get("metrics", {}).get("wall_time_s")
    if t:
        times.append(t)

if times:
    ci = median_and_ci(times, confidence=0.95, seed=42)
    print(f"Inference wall time for binary-trees / Python / gemma4:e4b")
    print(f"  samples:  {ci.n}")
    print(f"  median:   {ci.point:.2f} s")
    print(f"  95% CI:   [{ci.lower:.2f}, {ci.upper:.2f}] s")
else:
    print("No inference times found (did you run with --via-agent?)")

# Mock BEP calculation: if the generated code runs 10% faster
# than a human baseline, and generation cost 50 J of inference
# energy, how many runs to break even?
bep = break_even_point(
    execution_energy_baseline_j=10.0,
    execution_energy_optimized_j=9.0,
    generation_energy_j=50.0,
)
print(f"\nMock BEP (10% savings, 50J generation cost): {bep:.0f} executions")
EOF
```

---

## 10. Run the perturbed-CLBG probe

Check how `gemma4:e4b` responds when identifiers are renamed and
the input is rescaled:

```bash
python3 << 'EOF'
from perfarena.config import load_config
from perfarena.perturb import perturb_prompt_context

cfg = load_config()
problem = cfg.get_problem("binary-trees")

ctx = perturb_prompt_context(problem, scale=1.5, seed_material="demo-1")
print("Perturbed context for binary-trees:")
print(f"  Rescaled argument: {problem.default_argument} -> {ctx.rescaled_argument}")
print(f"  Renamed identifiers:")
for old, new in ctx.renamed_identifiers.items():
    print(f"    {old} -> {new}")
print()
print("Extra hint to inject into the user prompt:")
print(ctx.extra_hint)
EOF
```

To actually generate with the perturbation, you would write a
modified user template that appends `ctx.extra_hint` to the
language hint block, save it as a file, and pass
`--user-template my_perturbed_user.txt` to `perfarena generate`.

---

## 11. Run the test suite

```bash
pytest perfarena/tests/ -q
```

All 33 tests should pass. They don't call any LLM or remote host;
they test config loading, code extraction, the profiler, the stats
layer, and the measurement ingest logic.

---

## 12. What you just did

You ran the following end-to-end on your local machine:

1. Generated LLM code for CLBG benchmarks using a remote Ollama
   instance serving `gemma4:e4b`.
2. Profiled each generation call (wall time, CPU, memory).
3. Extracted the source code from the LLM response.
4. Wrote three files per sample (source, raw response, provenance
   sidecar).
5. Compiled and ran a generated Python sample locally.
6. Ran static analysis on it.
7. Summarized inference times with bootstrap confidence intervals.
8. Showed how the perturbed-CLBG probe works.
9. Verified the test suite passes.

What's missing from a publishable measurement campaign: a
bare-metal Linux host with `perf`, RAPL counters, and the RAPL
runner (`RAPL/perfarena_runner`). That host would receive the
compiled artifacts over SSH and produce the per-iteration JSONL
traces that the `ingest-measurements` command joins with the
generation metadata to produce leaderboard rows.

---

## Environment summary for this demo

| Setting | Value |
|---------|-------|
| Machine | local macOS laptop |
| Python | system python3 in a virtualenv |
| Ollama endpoint | `https://llms.sanadlab.ngrok.app` |
| Model | `gemma4:e4b` (8B, Q4_K_M) |
| Provider | `ollama` |
| Docker | not used |
| RAPL | not available (macOS) |
| Measurement host | not used (local execution only) |
