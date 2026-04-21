# PerfArena

PerfArena is a small toolkit for ranking LLMs by how efficient the
code they generate actually is. It forks
[`greensoftwarelab/Energy-Languages`](https://github.com/greensoftwarelab/Energy-Languages),
reuses the 10 Computer Language Benchmarks Game (CLBG) problems and
the per-benchmark `Makefile` structure, and adds three things on
top: a portable build container, an LLM generation pipeline, and an
SSH-driven harness that hands built artifacts to a remote host for
measurement.

The full research proposal lives in `../proposal.md`.

## How the pieces fit

There are two machines involved.

**The build container.** You run this on your laptop or in CI. It
holds every compiler and transpiler PerfArena needs, including
cross-compilers for aarch64. Its only jobs are:

1. Generate source code by calling an LLM.
2. Build that source code for the target CPU architecture.
3. Ship the build output to the measurement host.
4. Ask the measurement host to run things and collect results.

The container never runs `perf`, never reads RAPL, and never runs a
`make measure` step locally. It has no privileged access. You can
throw it away and rebuild it.

**The measurement host.** This is the bare-metal reference machine
described in Section 5.1 of the proposal. It holds the tuned
operating system, `perf`, RAPL, and the pinned runtimes. It is
where every publishable number comes from. PerfArena talks to it
over SSH.

For quick smoke tests and CI you can point the CLI at the
container itself as the "remote host", and get a no-measurement
dry run. For real numbers, point it at the lab machine.

## Target CPU architecture

Because compilation happens in the container and execution happens
elsewhere, the container has to know which architecture to build
for. You have three options:

- `auto` (the default). The CLI asks the remote host over SSH,
  via `uname -m`, and picks the matching toolchain.
- `x86_64-linux-gnu`. Native build using `gcc`, `g++`, `rustc
  --target x86_64-unknown-linux-gnu`, and `GOARCH=amd64`.
- `aarch64-linux-gnu`. Cross-compile using
  `aarch64-linux-gnu-gcc`, `aarch64-linux-gnu-g++`, `rustc --target
  aarch64-unknown-linux-gnu`, and `GOARCH=arm64`.

The arch only matters for languages that produce native binaries
(C++, Rust, Go). Java, C#, TypeScript, Python, Ruby, PHP, and
JavaScript produce either bytecode, IL, or source text that any
runtime of the right version can execute.

## Files in this package

```
perfarena/
  cli.py              typer CLI, entry point 'perfarena'
  config.py           YAML loader for problems and languages
  harness.py          drives 'make <action>' for one cell via an executor
  executors/
    base.py           Executor protocol + ExecResult
    local.py          run commands in this container (or on the host)
    ssh.py            forward commands to a remote machine over SSH
  generation/
    llm.py            LangChain chat-model factory
    pipeline.py       prompt -> LLM -> source file + metadata sidecar
  prompts/
    system.txt        default system prompt
    user.txt          default user prompt (uses config placeholders)
    language_hints/   one file per target language
  configs/
    problems.yaml     the 10 CLBG problems
    languages.yaml    the 10 target languages
```

## Build the container

From the root of the fork (one directory above this one):

```
docker build -t perfarena:latest .
```

## Run the CLI

Mount the fork into `/workspace` and pass whatever API keys you
need through the environment:

```
docker run --rm -it \
    -v "$PWD":/workspace \
    -v ~/.ssh:/root/.ssh:ro \
    -e OPENAI_API_KEY \
    -e ANTHROPIC_API_KEY \
    -e GOOGLE_API_KEY \
    perfarena:latest --help
```

### List what's configured

```
docker run --rm perfarena:latest list-problems
docker run --rm perfarena:latest list-languages
```

### Generate source code with an LLM

```
docker run --rm \
    -v "$PWD":/workspace \
    -e OPENAI_API_KEY \
    perfarena:latest generate \
        --provider openai \
        --model gpt-4o-mini \
        --problem binary-trees \
        --language python \
        --samples 3
```

Each sample produces three files under
`perfarena_out/generations/<provider>__<model>/<language_folder>/<problem>/`:

- `sample_NN.<ext>` is the source file the harness will build.
- `sample_NN.<ext>.raw.md` is the unprocessed LLM response.
- `sample_NN.<ext>.meta.json` is the provenance sidecar (provider,
  model, sampling parameters, prompt hashes, response length,
  generation time).

### Profile the LLM itself while it generates

Pass `--via-agent` to route the generation through
`perfarena-agent`, a standalone subprocess that wraps the LLM call
in a profiler and writes wall time, CPU time, peak RSS, and RAPL
energy back into the meta.json sidecar. Use this whenever you want
to know how much the inference step itself cost, which is required
for the Break-Even Point analysis in the proposal.

```
perfarena generate \
    --provider ollama \
    --model qwen2.5-coder:7b \
    --problem binary-trees \
    --language python \
    --samples 3 \
    --via-agent \
    --target-process ollama
```

The `--target-process ollama` flag asks the agent to find the
running `ollama` daemon and record its per-call CPU delta and
ending RSS alongside the package-level RAPL reading, so you get
the daemon's share of the work even though the Python process
itself is just waiting on I/O. You can also pass `--target-pid N`
to point at a specific PID directly.

You can drive the agent outside the CLI for debugging:

```
echo '{"provider":"ollama","model":"qwen2.5-coder:7b",
       "user_prompt":"print hello","temperature":0.2,
       "target_process":"ollama"}' \
  | perfarena-agent
```

The agent reads a JSON request on stdin and writes a JSON response
on stdout with fields `ok`, `raw_output`, `metrics`, `host`,
`started_at`, `finished_at`, and `agent_version`. The `metrics`
field is `{wall_time_s, cpu_time_s, peak_rss_kb, rss_delta_kb,
energy_uj, energy_source, target_pid, target_cpu_delta_s,
target_rss_kb_end, notes}`.

The agent is a separate process on purpose. It keeps the
orchestrator's own CPU and memory use out of the measurement, and
it leaves room for a future remote mode where the same agent runs
on an isolated LLM host and the orchestrator reaches it via the
existing SSH executor.

### Check that an executor works

```
# LocalExecutor: runs inside this container.
docker run --rm perfarena:latest exec-check

# SSHExecutor: forward to the lab host.
docker run --rm -v ~/.ssh:/root/.ssh:ro perfarena:latest \
    exec-check --host perfarena-lab --user perfarena \
               --key-path /root/.ssh/perfarena
```

### Validate a generated sample against the reference output

Every benchmark has a reference output at a small validation N
stored under `reference/outputs/`. The `validate` Makefile target
runs the benchmark and diffs the result:

```
# Validate using LLM-generated code (SOURCE override):
cd Python/binary-trees
make compile SOURCE=perfarena_generated.py
make validate SOURCE=perfarena_generated.py
# prints "validate: PASS" or "validate: FAIL"
```

Stdin-input problems (k-nucleotide, regex-redux, reverse-complement)
pipe their input automatically from the file named in the
`STDIN_FILE` Makefile variable. No special handling needed.

The harness's `compile_validate_then_measure` method runs all three
steps and skips measurement if validation fails.

### Build a benchmark for the remote host

The container compiles; the remote runs. Target arch is probed
automatically unless you pass `--target-arch`.

```
# Auto-probe the remote, then compile in the container for that arch.
docker run --rm -v "$PWD":/workspace -v ~/.ssh:/root/.ssh:ro \
    perfarena:latest harness-run compile \
        --language rust --problem binary-trees \
        --host perfarena-lab --user perfarena \
        --key-path /root/.ssh/perfarena

# Force a specific target arch.
docker run --rm -v "$PWD":/workspace \
    perfarena:latest harness-run compile \
        --language cpp --problem n-body \
        --target-arch aarch64-linux-gnu

# Ask the remote host to measure the already-built artifact.
docker run --rm -v ~/.ssh:/root/.ssh:ro \
    perfarena:latest harness-run measure \
        --language rust --problem binary-trees \
        --host perfarena-lab --user perfarena \
        --key-path /root/.ssh/perfarena
```

Under the hood, `compile` sets build-time environment variables
that match the target arch:

| Target            | C++ (CC/CXX)                             | Rust (CARGO_BUILD_TARGET)        | Go (GOOS/GOARCH) |
|-------------------|------------------------------------------|----------------------------------|------------------|
| x86_64-linux-gnu  | `gcc` / `g++`                            | `x86_64-unknown-linux-gnu`       | `linux` / `amd64` |
| aarch64-linux-gnu | `aarch64-linux-gnu-gcc` / `...-g++`      | `aarch64-unknown-linux-gnu`      | `linux` / `arm64` |

For this to take effect you need Makefiles that respect `CC`,
`CXX`, and the environment variables above. The original fork's
Makefiles hardcode the compiler per benchmark; updating them to
use the environment is a mechanical follow-up patch.

## Prompts

Prompts are plain text files under `perfarena/prompts/`. `system.txt`
and `user.txt` are rendered with placeholders from the problem and
language configs. Each language has its own short hints file under
`prompts/language_hints/` that gets inlined into the user prompt.
You can override either template per run with `--system-template`
and `--user-template` on `perfarena generate`.

## Provenance

Every generated sample gets a `meta.json` sidecar that records the
provider, the dated model version, every sampling parameter
(temperature, top-p, top-k, seed, max tokens), SHA-256 hashes of
the rendered system and user prompts, response length, and
wall-clock generation time. When the harness runs a measurement
through the SSH executor, it adds the remote toolchain fingerprint
from `/etc/perfarena-versions` and the resolved target arch, so
every number on the final leaderboard can be traced back to the
exact generation and build that produced it.
