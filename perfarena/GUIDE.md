# PerfArena step-by-step guide

This guide walks you through every operation PerfArena supports,
from first install to a full measurement campaign. Each section is
self-contained. Skip to whatever you need.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Build the container](#2-build-the-container)
3. [Install without Docker (development mode)](#3-install-without-docker)
4. [Configuration files](#4-configuration-files)
5. [See what's configured](#5-see-whats-configured)
6. [Generate code with an LLM (direct mode)](#6-generate-code-direct-mode)
7. [Generate code with inference profiling (agent mode)](#7-generate-code-agent-mode)
8. [Generate code on a remote LLM host (remote agent)](#8-generate-code-remote-agent)
9. [Use persistent agent mode for local models](#9-persistent-agent-mode)
10. [Patch the fork's Makefiles](#10-patch-the-makefiles)
11. [Check that an executor works](#11-check-an-executor)
12. [Compile a benchmark for a target architecture](#12-compile-for-a-target-architecture)
13. [Run a benchmark on the measurement host](#13-run-a-benchmark)
14. [Measure a benchmark (RAPL runner)](#14-measure-a-benchmark)
15. [Ingest measurement traces](#15-ingest-measurement-traces)
16. [Run static analysis on generated code](#16-run-static-analysis)
17. [Run the classification subtask](#17-classification-subtask)
18. [Run the perturbed-CLBG sensitivity probe](#18-perturbed-clbg)
19. [Compute statistics and rankings](#19-compute-statistics)
20. [Run the test suite](#20-run-the-tests)
21. [Full campaign walkthrough](#21-full-campaign)
22. [Customizing prompts](#22-customizing-prompts)
23. [Adding a new language](#23-adding-a-language)
24. [Adding a new LLM provider](#24-adding-a-provider)
25. [Environment variables reference](#25-environment-variables)
26. [File layout reference](#26-file-layout)

---

## 1. Prerequisites

You need one or two machines.

**Machine A: your laptop or CI server.** Runs the PerfArena build
container, which holds the CLI, the compilers, the LLM generation
pipeline, and the cross-compile toolchains. Any OS that runs
Docker will work.

**Machine B (optional): the measurement host.** A dedicated Linux
box with Intel or AMD CPU, `perf` access, RAPL counters readable,
and the runtimes for the ten target languages installed natively.
If you skip this, everything still works in-container using the
`LocalExecutor`; you just won't get hardware-backed energy
numbers.

Other requirements:

- Docker (or Podman) on machine A.
- SSH key access from A to B (if using B).
- An LLM provider you can reach: Ollama running locally, or API
  keys for OpenAI / Anthropic / Google.

---

## 2. Build the container

```bash
cd Energy-Languages

docker build \
    --build-arg PERFARENA_GIT_SHA=$(git rev-parse HEAD) \
    --build-arg PERFARENA_IMAGE_TAG=perfarena:latest \
    --build-arg PERFARENA_BUILD_DATE=$(date -Iseconds) \
    -t perfarena:latest .
```

This builds an image with all ten language toolchains (gcc, g++,
aarch64 cross-compilers, JDK 21, .NET SDK 8, Node + TypeScript,
PHP, Ruby, Go, Rust with aarch64 and x86_64 targets), the
`perfarena` CLI, and the `perfarena-agent` entry point.

Test it:

```bash
docker run --rm perfarena:latest --help
```

---

## 3. Install without Docker

If you want to run the CLI directly on your laptop (without Docker),
install the package in a virtualenv:

```bash
cd Energy-Languages
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

The `perfarena` and `perfarena-agent` commands are now on your
PATH. The container is still recommended for reproducibility, but
this is fine for development and testing.

---

## 4. Configuration files

PerfArena reads two YAML files that live inside the package:

- `perfarena/configs/problems.yaml` lists the 10 CLBG problems
  with their descriptions, input/output specs, default arguments,
  invocation hints, and algorithm-class tags.
- `perfarena/configs/languages.yaml` lists the 10 target languages
  with their folder names (matching the fork's directory tree),
  file extensions, and paradigm labels.

You normally don't need to edit these. If you add a language or a
problem, start here.

Prompt templates live under `perfarena/prompts/`:

- `system.txt` sets the LLM's role.
- `user.txt` describes the problem to the LLM.
- `language_hints/<language>.txt` gives per-language guidance
  (toolchain version, idiomatic tips, common performance traps).

See [Section 22](#22-customizing-prompts) for how to override them
per run.

---

## 5. See what's configured

```bash
# Inside the container:
docker run --rm perfarena:latest list-problems
docker run --rm perfarena:latest list-languages

# Or without Docker:
perfarena list-problems
perfarena list-languages
```

Both commands print a table to the terminal.

---

## 6. Generate code (direct mode)

Direct mode calls the LLM from the current process. No inference
profiling. Good for API providers (OpenAI, Anthropic, Google) where
the inference happens in a remote datacenter and local profiling
would measure nothing useful.

```bash
docker run --rm \
    -v "$PWD":/workspace \
    -e OPENAI_API_KEY \
    perfarena:latest generate \
        --provider openai \
        --model gpt-4o-mini \
        --problem binary-trees \
        --language python \
        --samples 3 \
        --temperature 0.2
```

Each sample creates three files under
`perfarena_out/generations/<provider>__<model>/<language_folder>/<problem>/`:

| File | What it is |
|------|------------|
| `sample_00.py` | The extracted source code. |
| `sample_00.py.raw.md` | The full unprocessed LLM response. |
| `sample_00.py.meta.json` | Provenance sidecar: provider, model, sampling params, prompt hashes, response length, timing, git SHA, image tag. |

To generate for all ten languages at once, call `generate` in a
loop:

```bash
for lang in python javascript typescript java csharp cpp php go rust ruby; do
    docker run --rm -v "$PWD":/workspace -e OPENAI_API_KEY \
        perfarena:latest generate \
            --provider openai --model gpt-4o-mini \
            --problem binary-trees --language "$lang" \
            --samples 10
done
```

---

## 7. Generate code with inference profiling (agent mode)

Agent mode runs the LLM call inside an isolated subprocess
(`perfarena-agent`) that wraps the call in a profiler. The profiler
captures wall time, CPU time, peak RSS, and RAPL package energy (on
Linux with readable RAPL counters). Use this for local models where
you want to know the cost of the inference step itself.

```bash
docker run --rm \
    -v "$PWD":/workspace \
    --network host \
    perfarena:latest generate \
        --provider ollama \
        --model qwen2.5-coder:7b \
        --problem binary-trees \
        --language python \
        --samples 3 \
        --via-agent \
        --target-process ollama
```

`--via-agent` routes the generation through the agent subprocess.
`--target-process ollama` tells the agent to also find the running
Ollama daemon by name and record its CPU delta and ending RSS for
attribution.

The output is the same three files as direct mode, but the
`meta.json` sidecar now has an `inference` section:

```json
"inference": {
    "metrics": {
        "wall_time_s": 4.72,
        "cpu_time_s": 0.11,
        "peak_rss_kb": 48120,
        "energy_uj": 138450000,
        "energy_source": "rapl",
        "target_pid": 1234,
        "target_cpu_delta_s": 4.58,
        "target_rss_kb_end": 8432110
    },
    "host": { ... },
    "started_at": "...",
    "finished_at": "..."
}
```

If RAPL is not readable (macOS, unprivileged container),
`energy_uj` is `null` and `energy_source` is `"none"`. The other
metrics still work.

---

## 8. Generate code on a remote LLM host (remote agent)

When the LLM host is a different machine from the orchestrator
(the intended phase-1 layout), use the remote agent path. The
orchestrator ships a request JSON to the remote via SFTP, tells the
remote to run `perfarena-agent`, and fetches the response. The
remote host must have `perfarena-agent` on its PATH (install via
`pip install perfarena` on that machine).

This path is available programmatically:

```python
from perfarena.config import load_config
from perfarena.executors import SSHExecutor
from perfarena.generation.pipeline import GenerationRequest, generate_one_via_remote_agent

cfg = load_config()
ssh = SSHExecutor(host="llm-box", user="perfarena", key_path="/root/.ssh/id_rsa")

req = GenerationRequest(
    provider="ollama",
    model="qwen2.5-coder:7b",
    problem="binary-trees",
    language="python",
    target_process="ollama",
)
result = generate_one_via_remote_agent(cfg, req, executor=ssh)
print(result.source_path)
ssh.close()
```

The CLI does not yet expose `--remote-agent-host` as a flag
(follow-up patch). For now, use the Python API above or wrap it in
a short script.

---

## 9. Persistent agent mode

For in-process local LLMs (`transformers`, `llama-cpp-python`) where
you don't want to reload model weights on every generation, start the
agent in persistent mode:

```bash
perfarena-agent --persistent
```

The agent reads one JSON request per line on stdin and writes one
JSON response per line on stdout. It stays up until stdin closes or
it reads a blank line. Feed it from a script:

```bash
echo '{"provider":"ollama","model":"qwen2.5-coder:7b","user_prompt":"print(1)","temperature":0.2}' \
    | perfarena-agent --persistent
```

The pipeline does not yet auto-launch the persistent agent (it
uses the one-shot path by default). Wiring it into
`generate_one_via_agent` with a `--persistent` flag is a follow-up.

---

## 10. Patch the fork's Makefiles

The fork's original Makefiles hardcode 2017-era compiler paths
(`/usr/local/src/Python-3.6.1/bin/python3.6`, etc.). The patcher
rewrites them to delegate to `perfarena.mk`, a common include file
that uses `$(CC)`, `$(CXX)`, `$(CARGO_BUILD_TARGET)`, and
`$(GOARCH)` from the environment, so the harness can set them per
target architecture.

Dry run first:

```bash
perfarena patch-makefiles --repo . --dry-run
```

Then apply:

```bash
perfarena patch-makefiles --repo .
```

This rewrites every Makefile for the ten target languages and saves
the original as `Makefile.orig` in each cell. Each patched Makefile
now includes:

- `VALIDATION_N` and `REFERENCE_OUTPUT` for the correctness oracle.
- `STDIN_FILE` for the three stdin-input problems (k-nucleotide,
  regex-redux, reverse-complement), so their input is piped
  automatically.
- `BINARY_OUTPUT = 1` for mandelbrot (uses `cmp` instead of `diff`).

Undo with:

```bash
find . -name Makefile.orig -exec sh -c 'mv "$1" "${1%.orig}"' _ {} \;
```

You can scope it to a single language or a single problem:

```bash
perfarena patch-makefiles --repo . --languages python,cpp
perfarena patch-makefiles --repo . --problems binary-trees
```

---

## 11. Check that an executor works

Before running harness commands, confirm the executor can reach the
target.

```bash
# Local (in this container or on your laptop):
perfarena exec-check

# Remote (the measurement host):
perfarena exec-check \
    --host perfarena-lab \
    --user perfarena \
    --key-path ~/.ssh/perfarena
```

Both should print `uname -a` output and `OK`.

---

## 12. Compile for a target architecture

The build container cross-compiles for whatever CPU the measurement
host has. Pass `--target-arch auto` (the default) to let the
harness probe the remote via `uname -m`, or set it explicitly.

```bash
# Auto-probe and compile:
perfarena harness-run compile \
    --language cpp \
    --problem binary-trees \
    --host perfarena-lab \
    --user perfarena \
    --key-path ~/.ssh/perfarena

# Explicit target:
perfarena harness-run compile \
    --language rust \
    --problem n-body \
    --target-arch aarch64-linux-gnu
```

What happens: the harness resolves the target arch, sets
`CC`/`CXX`/`CARGO_BUILD_TARGET`/`GOOS`/`GOARCH` in the
environment, and runs `make compile` in the benchmark cell. For
languages that produce architecture-independent output (Java, C#,
TypeScript, Python, Ruby, PHP, JavaScript), no cross-compile
variables are set.

When using the split-executor mode (build on local, measure on
remote), the harness automatically stages the built artifacts to
the measurement host via SFTP after a successful compile.

---

## 13. Run a benchmark

```bash
# On the local executor (smoke test):
perfarena harness-run run \
    --language python \
    --problem binary-trees

# On the measurement host:
perfarena harness-run run \
    --language python \
    --problem binary-trees \
    --host perfarena-lab \
    --user perfarena \
    --key-path ~/.ssh/perfarena
```

This invokes `make run` in the cell, which runs the benchmark once
and prints stdout. Use it to verify the benchmark actually works
before committing to a measurement campaign.

---

## 14. Measure a benchmark (RAPL runner)

```bash
perfarena harness-run measure \
    --language python \
    --problem binary-trees \
    --host perfarena-lab \
    --user perfarena \
    --key-path ~/.ssh/perfarena
```

On the measurement host, `make measure` invokes the PerfArena RAPL
runner (`RAPL/perfarena_runner`). The runner:

1. Captures a 5-second idle baseline (RAPL start/end, wall time).
2. Runs 10 warm-up iterations (RAPL sampled at ~10 Hz during each,
   but results tagged `"phase": "warmup"`).
3. Runs 20 measurement iterations (same sampling, tagged
   `"phase": "measure"`).
4. Writes one JSONL row per iteration to `../<Language>.jsonl`.

You can tune the warm-up and measurement counts. Edit the cell's
Makefile and change:

```makefile
PERFARENA_WARMUP  = 10
PERFARENA_MEASURE = 20
PERFARENA_IDLE_S  = 5
```

Or override them on the command line:

```bash
make measure PERFARENA_WARMUP=5 PERFARENA_MEASURE=30 PERFARENA_IDLE_S=10
```

The original RAPL tool (`RAPL/main`) is still available for
2017-replication runs. The patched Makefiles use
`RAPL/perfarena_runner` by default.

Before measuring, build the runner on the measurement host:

```bash
cd RAPL && make all
```

RAPL requires MSR access. On the measurement host:

```bash
sudo modprobe msr
```

The Makefile does this automatically, but if `modprobe` fails
(container, VM, non-Intel CPU), the runner still writes JSONL rows
with `rapl_pkg_delta_raw: -1`.

---

## 15. Ingest measurement traces

After a measurement run, join the RAPL trace with the generation's
`meta.json` to produce a flat measurement dataset:

```bash
perfarena ingest-measurements \
    --jsonl Python/Python.jsonl \
    --output perfarena_out/measurements/python_binary-trees.jsonl \
    --generations-root perfarena_out/generations \
    --model-slug openai__gpt-4o-mini \
    --language python \
    --problem binary-trees \
    --sample-id 0
```

Each output row includes the measurement data (wall time, RAPL
delta, exit code, sample count), the idle baseline, and the
generation provenance (model, prompts, inference metrics, git SHA).

For Parquet output, use the Python API:

```python
from perfarena.measurement import read_rapl_jsonl, group_iterations, join_group_with_meta, load_meta, write_parquet

iters = read_rapl_jsonl("Python/Python.jsonl")
groups = group_iterations(iters)
meta = load_meta("perfarena_out/generations/.../sample_00.py.meta.json")
rows = [r for g in groups for r in join_group_with_meta(g, meta)]
write_parquet(rows, "perfarena_out/measurements.parquet")
```

Requires `pip install pyarrow`.

---

## 16. Run static analysis

Check a generated source file for performance anti-patterns:

```bash
perfarena static-analyze \
    --language python \
    --source perfarena_out/generations/openai__gpt-4o-mini/Python/binary-trees/sample_00.py
```

Output is JSON with fields `language`, `tool`, `available`,
`issues`, `lines_of_code`, `density_per_kloc`. The tool used
depends on the language:

| Language | Tool | Notes |
|----------|------|-------|
| Python | pylint | Warnings only (no style/refactor noise). |
| C++ | cppcheck | Warning, performance, portability checks. |
| Rust | rustc lints | Compiled with `-W clippy::all --emit=metadata`. |
| Go | go vet | Standard vet checks. |
| JavaScript | eslint | Requires eslint on PATH. |
| TypeScript | tsc --noEmit | Type-error check, strict mode. |
| Java, C#, PHP, Ruby | not wired | Returns `available: false`. |

If the tool is not installed on the machine, the result says
`available: false` and the rest of the row is zeroed.

---

## 17. Classification subtask

The classification subtask asks: can a model that *generates*
efficient code also *recognize* which of two implementations is
faster?

This requires measurement data first (Section 15). Then, in Python:

```python
from perfarena.classification import build_pairs_from_measurements, classify_pairs
import json

# Load the ingested measurement rows.
with open("perfarena_out/measurements/python_binary-trees.jsonl") as f:
    rows = [json.loads(line) for line in f if line.strip()]

# Build pairs: pick the fastest and slowest sample for each cell.
pairs = build_pairs_from_measurements(
    rows,
    generations_dir=Path("perfarena_out/generations"),
    min_ratio=1.25,  # only include pairs with >=25% speedup gap
)

# Ask a model to pick the faster one.
results = classify_pairs(
    pairs,
    provider="openai",
    model="gpt-4o-mini",
    temperature=0.0,
)

for r in results:
    print(r.correct, r.model_answer, r.correct_answer, r.pair.speedup_ratio)
```

Each pair is presented in a randomised A/B order so the model can't
rely on position. The order is seeded deterministically from the
source paths, so re-runs are reproducible.

---

## 18. Perturbed-CLBG sensitivity probe

This checks whether models are quoting memorised CLBG solutions or
actually understanding the problem. It renames the canonical
identifiers and rescales the default argument.

```python
from perfarena.config import load_config
from perfarena.perturb import perturb_prompt_context

cfg = load_config()
problem = cfg.get_problem("binary-trees")

ctx = perturb_prompt_context(problem, scale=1.5, seed_material="experiment-1")
print(ctx.extra_hint)
# Output: a paragraph asking the LLM to use renamed identifiers
# (e.g. "tree -> gamma", "depth -> delta") and a rescaled argument
# (21 -> 32).
```

To use it in a generation run, create a modified user prompt
template that appends `{language_hint}` with `ctx.extra_hint`, or
pass the hint text manually through `--user-template` pointing at
a new template file.

---

## 19. Compute statistics and rankings

The `stats` module provides everything the proposal commits to:

```python
from perfarena.stats import (
    harmonic_mean,
    median_and_ci,
    refuse_to_rank,
    mann_whitney_u,
    kendall_tau_b,
    holm_bonferroni,
    break_even_point,
)

# Per-cell summary: median wall time with a 95% CI.
values = [1050.0, 1100.0, 980.0, 1020.0, 1070.0]
ci = median_and_ci(values, confidence=0.95, seed=42)
print(f"median={ci.point:.1f}  95% CI=[{ci.lower:.1f}, {ci.upper:.1f}]")

# Aggregate across problems: harmonic mean of per-problem speedup ratios.
speedups = [1.2, 0.95, 1.5, 1.1, 1.3]
print(f"harmonic mean speedup: {harmonic_mean(speedups):.3f}")

# Refuse to rank cells whose CIs overlap.
cells = {
    "model_a": ci,
    "model_b": median_and_ci([900, 950, 880, 920, 910], seed=42),
}
ordered, overlaps = refuse_to_rank(cells)
print(f"rankable: {ordered}, overlapping: {overlaps}")

# Break-Even Point: how many times must the optimized code run
# before the LLM inference energy is recovered?
bep = break_even_point(
    execution_energy_baseline_j=10.0,
    execution_energy_optimized_j=8.0,
    generation_energy_j=100.0,
)
print(f"BEP: {bep:.0f} executions")
```

All functions are dependency-free (no scipy, no pandas, no numpy).
They use the standard library's `statistics`, `math`, and `random`
modules only.

---

## 20. Run the tests

```bash
# Inside the virtualenv (without Docker):
pip install -e '.[dev]'
pytest perfarena/tests/ -q

# Inside the container:
docker run --rm -v "$PWD":/workspace --entrypoint bash perfarena:latest \
    -c "pip install pytest && pytest perfarena/tests/ -q"
```

The test suite covers config loading, harness build-env logic,
code extraction from fenced blocks, the profiler context manager,
the statistics functions, the perturbation generator, and the
measurement ingest roundtrip. 33 tests, all dependency-free except
for the package itself.

---

## 21. Full campaign walkthrough

Here is the whole flow from zero to a set of measurement rows for
one model, one problem, one language. Replace the values to scale
up.

```bash
# 1. Build the container.
docker build \
    --build-arg PERFARENA_GIT_SHA=$(git rev-parse HEAD) \
    --build-arg PERFARENA_IMAGE_TAG=perfarena:$(date +%Y%m%d) \
    --build-arg PERFARENA_BUILD_DATE=$(date -Iseconds) \
    -t perfarena:latest .

# 2. Patch the Makefiles.
docker run --rm -v "$PWD":/workspace --entrypoint bash perfarena:latest \
    -c "perfarena patch-makefiles --repo /workspace"

# 3. Build the RAPL runner on the measurement host.
ssh perfarena@perfarena-lab "cd /opt/perfarena/Energy-Languages/RAPL && make all"

# 4. Generate 10 samples with inference profiling.
docker run --rm \
    -v "$PWD":/workspace \
    --network host \
    perfarena:latest generate \
        --provider ollama \
        --model qwen2.5-coder:7b \
        --problem binary-trees \
        --language python \
        --samples 10 \
        --via-agent \
        --target-process ollama

# 5. For each generated sample: stage, compile, validate, measure.
#    Only samples that pass the correctness oracle are measured.
#    (Manual loop; a campaign-runner CLI is a follow-up.)
for i in $(seq 0 9); do
    src="perfarena_out/generations/ollama__qwen2.5-coder_7b/Python/binary-trees/sample_$(printf '%02d' $i).py"
    staged="perfarena_generated.py"

    # Stage the generated source into the benchmark cell.
    cp "$src" "Python/binary-trees/$staged"

    # Compile using the staged file (SOURCE override).
    docker run --rm -v "$PWD":/workspace --entrypoint bash perfarena:latest \
        -c "cd /workspace/Python/binary-trees && make compile SOURCE=$staged"

    # Validate: run at a small N and diff against reference.
    docker run --rm -v "$PWD":/workspace --entrypoint bash perfarena:latest \
        -c "cd /workspace/Python/binary-trees && make validate SOURCE=$staged"
    if [ $? -ne 0 ]; then
        echo "SKIP sample $i: validation failed"
        continue
    fi

    # Ship the cell to the measurement host.
    rsync -az Python/binary-trees/ perfarena@perfarena-lab:/opt/perfarena/Energy-Languages/Python/binary-trees/

    # Run measurement on the bare-metal host (only reached if validated).
    ssh perfarena@perfarena-lab "cd /opt/perfarena/Energy-Languages/Python/binary-trees && sudo make measure SOURCE=$staged"

    # Fetch the trace.
    scp perfarena@perfarena-lab:/opt/perfarena/Energy-Languages/Python/Python.jsonl Python/Python.jsonl
done

# 6. Ingest the trace into the measurement dataset.
docker run --rm -v "$PWD":/workspace --entrypoint bash perfarena:latest \
    -c "perfarena ingest-measurements \
        --jsonl /workspace/Python/Python.jsonl \
        --output /workspace/perfarena_out/measurements/python_binary-trees.jsonl \
        --generations-root /workspace/perfarena_out/generations \
        --model-slug ollama__qwen2.5-coder_7b \
        --language python \
        --problem binary-trees \
        --sample-id 0"

# 7. Run static analysis on the generated samples.
for i in $(seq 0 9); do
    src="perfarena_out/generations/ollama__qwen2.5-coder_7b/Python/binary-trees/sample_$(printf '%02d' $i).py"
    docker run --rm -v "$PWD":/workspace --entrypoint bash perfarena:latest \
        -c "perfarena static-analyze --language python --source /workspace/$src"
done
```

---

## 22. Customizing prompts

Prompts live in `perfarena/prompts/`. To use different prompts for
a run, write your variant and point the CLI at it:

```bash
# Write a custom system prompt.
cat > my_prompts/system_efficiency.txt << 'EOF'
You are a performance engineer. Prioritize CPU cache locality,
minimal allocation, and vectorized operations over readability.
Write the most efficient {language_name} code possible.
Respond with a single fenced code block and nothing else.
EOF

# Use it.
perfarena generate \
    --provider ollama --model qwen2.5-coder:7b \
    --problem binary-trees --language python \
    --system-template system_efficiency.txt
```

The template file is looked up relative to `perfarena/prompts/`.
If you want to store custom templates elsewhere, either symlink
them into that directory or copy the whole `prompts/` tree and
point the `PerfArenaConfig.prompts_dir` at your copy.

Available placeholders in `user.txt`:

| Placeholder | Filled from |
|-------------|-------------|
| `{language_name}` | `languages.yaml` `display_name` |
| `{language_paradigm}` | `languages.yaml` `paradigm` |
| `{language_hint}` | `prompts/language_hints/<key>.txt` |
| `{problem_name}` | `problems.yaml` `name` |
| `{problem_description}` | `problems.yaml` `description` |
| `{input_spec}` | `problems.yaml` `input_spec` |
| `{output_spec}` | `problems.yaml` `output_spec` |
| `{default_argument}` | `problems.yaml` `default_argument` |
| `{invocation_hint}` | `problems.yaml` `invocation_hint` |
| `{algorithm_class}` | `problems.yaml` `algorithm_class` |

Available placeholders in `system.txt`:

| Placeholder | Filled from |
|-------------|-------------|
| `{language_name}` | `languages.yaml` `display_name` |
| `{language_paradigm}` | `languages.yaml` `paradigm` |

Literal curly braces in prompt text must be doubled: `{{` and `}}`.

---

## 23. Adding a new language

1. Add a new entry to `perfarena/configs/languages.yaml` with
   `key`, `display_name`, `folder`, `file_extension`, and
   `paradigm`.

2. Write a language hint file at
   `perfarena/prompts/language_hints/<key>.txt`.

3. Make sure the fork has a `<folder>/` directory with one
   subdirectory per CLBG problem, each containing a source file
   and a Makefile. The patcher can generate the Makefiles if you
   add a rewriter function for the new language in
   `perfarena/tools/patch_makefiles.py`.

4. If the language produces native binaries (like C++ / Rust / Go),
   add entries for both `x86_64-linux-gnu` and `aarch64-linux-gnu`
   in the `_ARCH_BUILD_ENV` dict in `perfarena/harness.py`.

5. Add a static-analysis runner function in
   `perfarena/static_analysis.py` and register it in the
   `_RUNNERS` dict.

6. Update the Dockerfile if the language's toolchain isn't already
   installed.

---

## 24. Adding a new LLM provider

1. Install the LangChain integration for the provider (e.g.
   `pip install langchain-fireworks`).

2. Add a branch in `perfarena/generation/llm.py`'s
   `build_chat_model` function that handles the new provider
   string.

3. Add the dependency to `pyproject.toml`.

4. If the provider runs locally and you want to measure its
   inference cost, make sure `perfarena-agent` is installed on the
   host where the model runs, and use `--via-agent` with
   `--target-process <daemon-name>`.

---

## 25. Environment variables reference

| Variable | Where set | What it does |
|----------|-----------|--------------|
| `OPENAI_API_KEY` | caller | Authenticates with OpenAI. |
| `ANTHROPIC_API_KEY` | caller | Authenticates with Anthropic. |
| `GOOGLE_API_KEY` | caller | Authenticates with Google. |
| `OLLAMA_HOST` | caller | URL of the Ollama daemon (default `http://localhost:11434`). |
| `PERFARENA_GIT_SHA` | Docker build-arg | Baked into the image, read at run time, written into every `meta.json`. |
| `PERFARENA_IMAGE_TAG` | Docker build-arg | Same as above. |
| `PERFARENA_BUILD_DATE` | Docker build-arg | Same as above. |
| `CC` | PerfArena harness | C compiler for native or cross builds. Set by `harness.run_action`. |
| `CXX` | PerfArena harness | C++ compiler. Same as `CC`. |
| `CARGO_BUILD_TARGET` | PerfArena harness | Rust cross-compile target triple. |
| `GOOS` / `GOARCH` | PerfArena harness | Go cross-compile OS and architecture. |
| `PERFARENA_TARGET_ARCH` | PerfArena harness | The resolved target arch triple, written into each compile action's env. |
| `PERFARENA_WARMUP` | Makefile override | Number of warm-up iterations (default 10). |
| `PERFARENA_MEASURE` | Makefile override | Number of measurement iterations (default 20). |
| `PERFARENA_IDLE_S` | Makefile override | Idle baseline duration in seconds (default 5). |

---

## 26. File layout reference

```
Energy-Languages/
    Dockerfile                    build container definition
    pyproject.toml                package metadata and deps
    perfarena.mk                  common Makefile include
    compile_all.py                original 2017 harness driver (preserved)
    gen-input.sh                  generates stdin inputs for 3 benchmarks
    RAPL/
        main.c                    original 2017 RAPL tool (preserved)
        perfarena_runner.c        new: periodic sampling, warm-up split, JSONL output
        rapl.c / rapl.h           shared RAPL MSR reading code
        Makefile                  builds both `main` and `perfarena_runner`
    Python/                       one of 28 language directories
        binary-trees/
            Makefile              patched: delegates to perfarena.mk
            Makefile.orig         backup of the 2017 original
            binarytrees.python3   CLBG reference source
            binarytrees.py        compiled artifact (copy of the above)
        ...
    C++/ Java/ Rust/ Go/ ...      same structure per language
    perfarena/                    the Python package
        __init__.py
        cli.py                    typer CLI entry point
        config.py                 YAML config loader
        harness.py                drives make compile/run/measure over executors
        measurement.py            JSONL/Parquet ingest and provenance join
        stats.py                  harmonic mean, CI, Mann-Whitney U, BEP, etc.
        provenance.py             captures git SHA, image tag, toolchain versions
        classification.py         pairwise "pick the faster one" subtask
        perturb.py                perturbed-CLBG sensitivity probe
        static_analysis.py        per-language PAP-density runners
        executors/
            base.py               Executor protocol, ExecResult
            local.py              LocalExecutor (in-container)
            ssh.py                SSHExecutor (forward to bare-metal host)
        generation/
            llm.py                LangChain chat-model factory
            pipeline.py           prompt -> LLM -> source + meta.json
            agent.py              isolated profiling subprocess
            profiler.py           wall/cpu/rss/RAPL context manager
        prompts/
            system.txt            default system prompt template
            user.txt              default user prompt template
            language_hints/       one file per target language
        configs/
            problems.yaml         10 CLBG problems
            languages.yaml        10 target languages
        tools/
            patch_makefiles.py    rewrites fork Makefiles to use perfarena.mk
        tests/
            test_config.py
            test_harness.py
            test_extract_code.py
            test_stats.py
            test_profiler.py
            test_perturb.py
            test_measurement.py
    perfarena_out/                created at run time, not checked in
        generations/
            <provider>__<model>/
                <Language>/
                    <problem>/
                        sample_00.<ext>
                        sample_00.<ext>.raw.md
                        sample_00.<ext>.meta.json
        measurements/
            <language>_<problem>.jsonl
```
