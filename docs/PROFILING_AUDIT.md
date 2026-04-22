# PerfArena profiling and benchmarking audit

An extensive review of every part of the PerfArena pipeline that
touches measurement, profiling, energy accounting, statistical
analysis, or experimental methodology. The goal is to find the
things that would make the results wrong, misleading, or
unreproducible before a real measurement campaign starts.

Findings are grouped by area and tagged with severity. "Critical"
means the numbers would be wrong in a way that changes rankings.
"High" means a systematic bias or a silent failure. "Medium" means
a known-imprecise approximation that should be documented. "Low"
means a code-quality or hygiene issue.

---

## 1. Energy measurement (RAPL)

### 1.1 RAPL counter wrap-around can lose energy on long runs
**Severity: critical.** `profiler.py:148-150`

The Python profiler handles a single counter wrap-around:

```python
delta = rapl_end - self._rapl_start
if delta < 0 and self._rapl_max is not None:
    delta += self._rapl_max
```

If the workload runs long enough for the counter to wrap more than
once (the max range for Intel package counters is typically around
250-260 J on recent CPUs; a 100-second inference call on a 150 W
TDP package can hit 15 kJ, wrapping roughly 60 times), this
formula gives a wrong answer. It only adds `max` once.

The C runner (`perfarena_runner.c:79-80`) has the same problem
in `write_row`, though since it samples at 10 Hz, each
per-sample delta is small enough that a single-wrap correction is
safe. The danger is in the *per-iteration* delta (rapl_start to
rapl_end across the entire child execution), which for slow
benchmarks can span multiple wraps.

**Fix:** In the Python profiler, use the periodic sampling
approach from the C runner and integrate the deltas, or at
minimum use `(rapl_end - rapl_start) % rapl_max` instead of a
conditional add. In the C runner, compute per-iteration energy as
the sum of the per-sample deltas rather than the single-read
start-to-end difference. This is architecturally correct because
the sampling loop already reads RAPL at 10 Hz and never wraps in a
100 ms interval.

### 1.2 RAPL read is taken at the wrong time in the C runner
**Severity: high.** `perfarena_runner.c:190-194`

The measurement loop reads RAPL *before* fork, then again *after*
the child exits:

```c
long long rapl_start = read_pkg_energy_raw(0);  // line 192
pid_t child = fork();                            // line 101 (inside run_child_with_sampling)
```

But `fork()` itself consumes CPU (copying page tables, allocating
the child struct) and therefore consumes energy. On a loaded
system with a large resident set, fork overhead is 5-50 ms. This
energy gets attributed to the benchmark, not to the infrastructure.

The fix is a synchronized start: parent reads RAPL, then signals
the already-forked child (which is blocked on a pipe read or
similar) to exec. The child doesn't start real work until after
the parent's RAPL start read is complete.

### 1.3 Package energy includes uncore and DRAM
**Severity: high.** `perfarena_runner.c:58`, `rapl.h`

The code reads only `MSR_PKG_ENERGY_STATUS`. Package energy
includes core (PP0), graphics (PP1, if present), and uncore
(memory controllers, LLC, interconnect). It does not include
DRAM energy separately.

For a benchmark whose hot loop is `memcpy` versus one whose hot
loop is `fma`, the package counter captures very different cost
breakdowns even if their CPU time is identical. This is exactly
the regime van Kempen et al. describe as the 2-8% memory-activity
contribution.

The fix is to read PP0 (`MSR_PP0_ENERGY_STATUS`), PP1
(`MSR_PP1_ENERGY_STATUS` where available), and DRAM
(`MSR_DRAM_ENERGY_STATUS`) separately and record all four
counters in the JSONL row. The code in `rapl.c` already reads
all four in `rapl_before`/`rapl_after`; the new runner just
doesn't call those functions and only reads PKG.

### 1.4 The idle baseline is captured but never subtracted
**Severity: critical.** `measurement.py:210`, `perfarena_runner.c:176-186`

The RAPL runner records an idle-phase row (5 seconds of sleep)
at the start of each measurement invocation. The ingest code in
`measurement.py` stores it as `idle_rapl_pkg_delta_raw` on each
`MeasurementRow`. But no code anywhere subtracts it. The stats
layer (`stats.py`) operates on `rapl_pkg_delta_raw` directly.

Every energy number in the leaderboard therefore includes the
idle power draw of the measurement host for the duration of the
benchmark iteration. On a 50 W idle machine running a 2-second
benchmark, that is 100 J of idle energy added to every single
row. This is larger than the signal we are trying to measure for
many CLBG problems.

The fix is straightforward: in `measurement.py`, compute
`net_energy_raw = row.rapl_pkg_delta_raw - (idle_delta_per_ms * row.wall_ms)`
and store it as a new field. The per-ms idle rate comes from
`idle.rapl_pkg_delta_raw / idle.wall_ms`.

### 1.5 No idle-period validation
**Severity: medium.** `perfarena_runner.c:176-186`

The idle baseline uses `sleep(idle_s)` and assumes the machine is
actually idle during that time. If a background process is doing
work (cron, systemd timers, other SSH sessions), the baseline is
inflated. There is no check that the idle reading is plausible.

The fix: sample idle energy at 1 Hz for N seconds, take the
minimum 1-second window as the "true idle rate", and discard the
rest. If the variance across windows exceeds a threshold, warn
and abort.

### 1.6 The 10 Hz sampling loop introduces timing jitter
**Severity: medium.** `perfarena_runner.c:115-116`

The sampling loop calls `usleep(100000)` between RAPL reads, but
`usleep` on Linux can sleep longer than requested (due to timer
coalescing, scheduler preemption, and timer slack). The actual
sampling rate is <=10 Hz, not ==10 Hz. The `samples` field in the
output counts iterations, not elapsed seconds, so the reader
cannot reconstruct the true sampling rate.

The fix: record a timestamp with each sample (not just at
iteration start/end), or compute the actual interval per sample
from `wall_ms / samples`.

---

## 2. Inference profiling (agent, profiler)

### 2.1 Agent subprocess startup overhead is in the measurement
**Severity: high.** `pipeline.py:568-575`

`generate_one_via_agent` spawns `perfarena-agent` as a subprocess
for every generation. The subprocess startup (Python interpreter
init, LangChain import, provider library init) takes 1-5 seconds
on a cold start. This time is included in the
`orchestrator_duration_s` but not in the agent's `wall_time_s`
(which only covers the profiled block). So the two numbers
disagree.

The real problem is that the *first* invocation of `chat.invoke`
inside the agent may trigger lazy initialization (HTTP session
setup, model loading in some providers, TLS handshake). This
latency is inside the profiler's context and inflates
`wall_time_s` for sample 0 relative to samples 1-9.

The fix: the agent should do a throwaway warm-up call before
entering the profiled block, or the pipeline should spawn the
agent once in persistent mode and stream requests.

### 2.2 `peak_rss_kb` on macOS is in bytes, not kilobytes
**Severity: high.** `profiler.py:139, 143`

`resource.getrusage(RUSAGE_SELF).ru_maxrss` returns kilobytes on
Linux but bytes on macOS (Darwin). The profiler stores the value
directly in `peak_rss_kb`, which means on macOS the number is
1024x too large. The demo run we just did reported
`peak_rss_kb: 79134720`, which is about 75 GB. The actual peak
RSS was about 75 MB.

```python
rss_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
self.metrics.peak_rss_kb = int(rss_peak)
```

The fix: detect the platform and divide by 1024 on macOS:

```python
import platform
divisor = 1024 if platform.system() == "Darwin" else 1
self.metrics.peak_rss_kb = int(rss_peak) // divisor
```

### 2.3 The profiler measures the agent process, not the LLM process
**Severity: medium.** `profiler.py:115-134`

For Ollama, the agent process makes an HTTP call to the daemon.
The agent's own CPU time is ~0.1 s (HTTP client overhead); the
real work is in the daemon process. The profiler tries to capture
the daemon's CPU delta via `target_pid`, but:

- It only gets CPU time and ending RSS, not energy. RAPL is
  package-wide so it captures the daemon's energy, but we cannot
  separate it from other processes on the same package.
- If the daemon PID is wrong (e.g. `find_process_by_name`
  returns the wrong `ollama` process), the target-PID metrics
  are misleading.
- If the daemon is in a container, the agent running outside that
  container cannot see the daemon's PID.

This is documented in the design review but the per-row metadata
does not flag which of these cases occurred. A consumer looking at
`target_cpu_delta_s: 4.5` has no way to know whether that number
is reliable.

The fix: add a `target_pid_verified` boolean to the metrics that
is `true` only if the profiler confirmed the PID by checking the
process name and cmdline against expectations.

---

## 3. Statistical calculations

### 3.1 Bootstrap CI quantile indexing is truncated, not interpolated
**Severity: medium.** `stats.py:98-99`

The percentile bootstrap uses `int(alpha * n_resamples)` which
truncates. For 2000 resamples and 95% confidence, the lower
index is `int(0.025 * 2000) = 50` (correct by convention) and
the upper index is `int(0.975 * 2000) = 1950` (also correct).
But for non-standard confidence levels or non-standard resample
counts, truncation can skip a percentile bin. Standard practice
is linear interpolation between adjacent bins.

Not a bug at the default settings, but becomes one if someone
passes `n_resamples=100`.

### 3.2 Mann-Whitney U tie detection uses exact float comparison
**Severity: medium.** `stats.py:172`

```python
while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
```

If the input values were integer RAPL deltas that got cast to
float via `float(row["rapl_pkg_delta_raw"])`, exact comparison is
fine. But if they were computed (e.g. divided by wall time to get
"joules per second"), floating-point rounding means semantically
equal values won't compare equal. Tie correction will be wrong.

The fix: use `abs(a - b) < epsilon` with a small epsilon, or
operate on the raw integer values and convert afterward.

### 3.3 Kendall tau-b returns 0.0 for degenerate input instead of NaN
**Severity: low.** `stats.py:244`

When all values in one sequence are identical, the denominator is
zero and the function returns 0.0. This is arguably wrong:
Kendall's tau is undefined when one of the sequences is constant.
A consumer might interpret 0.0 as "no correlation" when the
answer is "correlation is undefined."

### 3.4 Harmonic mean is correct but rarely the right statistic
**Severity: medium (methodological).**

The proposal calls for harmonic-mean speedup aggregation (from the
GSO paper). Harmonic mean is the right aggregate for *rates* (e.g.
instructions per second) but PerfArena reports *times* (wall_ms)
and *energies* (rapl_delta). For times, arithmetic mean or median
is standard. Harmonic mean of times gives extra weight to the
fastest cells, which is the opposite of what most benchmarks want.

If the intent is to compute speedup ratios (model_time /
baseline_time) and then harmonic-mean those ratios, the harmonic
mean is correct. But the code doesn't compute ratios; it operates
on raw values. The consumer has to convert first, and nothing in
the codebase enforces that convention.

The fix: either (a) add a `speedup_ratio` helper that produces the
ratio, then harmonic-mean it, or (b) document clearly that
harmonic mean should only be applied to speedup ratios, not to
raw times.

---

## 4. Code correctness

### 4.1 Code extraction regex fails on nested or escaped fences
**Severity: high.** `pipeline.py:44`

```python
_FENCE_ANY = re.compile(r"```[a-zA-Z0-9_+\-]*\n(.*?)```", re.DOTALL)
```

This is a non-greedy match for the *first* closing ` ``` `. If
the LLM produces a response like:

    ```python
    s = "use ```javascript console.log()```"
    ```

the regex stops at the inner ` ``` `, extracting only
`s = "use `. The rest of the code is lost. The program won't
parse, and the harness will try to compile garbage.

The failure is silent: the extracted code is written to disk and
no validation step checks that it parses. The meta.json records
`extracted_code_chars` which would be smaller than expected, but
nothing raises.

The fix: use a parser that counts backtick sequences (a ` ``` `
that opens a block is three-or-more backticks at the start of a
line; the closing ` ``` ` must have the same number of backticks
at the start of a line). Or, at minimum, try to compile or parse
the extracted code and fall back to the next candidate block if
it fails.

### 4.2 `ru_maxrss` unit varies by OS
**Severity: high.** `profiler.py:139`

Already described in 2.2. On macOS, `ru_maxrss` is in bytes; on
Linux, it's in kilobytes. The field is named `peak_rss_kb` which
is only correct on Linux. On the macOS demo run this produced a
75 GB number.

### 4.3 PurePosixPath used for local paths on all platforms
**Severity: medium.** `harness.py:194`

The harness builds paths with `PurePosixPath` even when the
build executor is `LocalExecutor` running on the same machine.
On macOS with forward-slash paths this works by accident. On
Windows it would not. More importantly, mixing `PurePosixPath`
with `Path` (which appears elsewhere in the pipeline code)
produces inconsistent path separators.

The fix: use `Path` for local-side paths (build executor),
`PurePosixPath` only for remote-side paths (SSH executor). The
harness already tracks `build_repo_path` and `run_repo_path`
separately; use the appropriate path type for each.

### 4.4 SSH command assembly exposes env values to shell interpretation
**Severity: medium.** `ssh.py:59-61`

```python
env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
full_cmd = f"{env_prefix} {full_cmd}"
```

`shlex.quote` handles most cases, but env variable *names* are
not quoted. If a key contains spaces or shell metacharacters
(unlikely but not validated), the resulting command is malformed.
Also, paramiko's `exec_command` supports an `environment`
parameter directly for some SSH servers, which would bypass shell
interpretation entirely.

### 4.5 The classification module mixes warm-up and measurement rows
**Severity: medium.** `classification.py:81-84`

`build_pairs_from_measurements` accepts a list of measurement
rows and collects all `wall_ms` values per sample without
filtering by `phase`. If the input includes warm-up rows (which
are slower due to JIT cold-start), the median wall time per
sample is biased upward and non-representative.

The fix: filter to `row["phase"] == "measure"` before passing
rows to `build_pairs_from_measurements`, or filter inside the
function itself.

---

## 5. Benchmarking methodology

### 5.1 Three stdin-input benchmarks will fail silently
**Severity: high.** Architecture.

`k-nucleotide`, `regex-redux`, and `reverse-complement` read
input from stdin. The patched Makefiles set `RUN_CMD` to
something like `python3 -OO $(OUTPUT) $(ARG)`. But these
benchmarks ignore the CLI argument and read from a piped file.

The original 2017 Makefiles had explicit redirection:
`... < knucleotide-input.txt`. The patcher's `_rewrite_python`
does not add this redirection because it infers the RUN_CMD from
the default argument, not from the invocation_hint.

The benchmarks will run but produce empty output (no stdin, so no
data to process). The harness will record a very short wall time
and an exit code of 0, and the leaderboard will show those three
cells as "blazing fast" when they're actually no-ops.

The fix: the patcher needs per-problem awareness for stdin
benchmarks. The `invocation_hint` field in `problems.yaml`
already documents the correct invocation (including stdin
redirection), but the patcher doesn't read it.

### 5.2 The perturbation scheme is deterministic and guessable
**Severity: medium.** `perturb.py:45-53`

The identifier renaming is seeded from the problem key by default:

```python
rng = _deterministic_rng(seed_material or problem.key)
```

This means that if someone runs the perturbation with the default
seed, every user sees the same "perturbed" names. If those
perturbed names ever appear in a training dataset (e.g. someone
publishes a PerfArena-perturbed version of CLBG), the probe
loses its purpose.

The fix: require a per-campaign random seed that is generated at
campaign start and not published until after all generations are
done. The current `seed_material` parameter supports this, but
the default should not be the problem key.

### 5.3 No correctness oracle is wired into the pipeline
**Severity: high.** Architecture.

The proposal says only samples that pass the CLBG correctness
oracle contribute to the energy/runtime statistics. But the
pipeline has no correctness check. It compiles, runs, and
measures every generated sample regardless of whether the output
is correct. The CLBG reference outputs exist in the fork (some
benchmarks produce deterministic output for a given N), but the
harness does not compare against them.

A leaderboard built from the current pipeline includes both
correct and incorrect samples in the same ranking, which
invalidates the numbers.

The fix: add a `validate` action to the harness that compares the
benchmark's stdout against a reference output file. Gate the
`measure` action behind a successful `validate`. Store the
pass/fail result in the measurement row.

### 5.4 Static analysis density conflates code and comments
**Severity: low.** `static_analysis.py:56-61`

`_count_lines` counts all non-empty lines, including comments and
docstrings. LLM-generated code tends to have verbose comments
(the demo sample from gemma4:e4b has multi-line docstrings on
every function). Human-written CLBG reference solutions have zero
comments. So PAP density (issues / kLoC) is systematically lower
for LLM-generated code than for human code on the same issue
count, because the denominator is inflated by comments.

---

## 6. Provenance and reproducibility

### 6.1 No idle baseline in meta.json
**Severity: high.** `pipeline.py:259-294`

The generation meta.json records the inference duration, the
prompt hashes, and the model parameters. But when the measurement
side records a RAPL trace, the idle baseline is in the JSONL file,
not in the meta.json. A downstream consumer looking only at
meta.json has no way to reconstruct the net (idle-subtracted)
energy.

The fix: after ingest, write a merged metadata file (or extend
the measurement JSONL row) that includes both the generation
provenance and the measurement context including the idle
baseline.

### 6.2 Schema version is static and there is no migration path
**Severity: medium.** `pipeline.py:260`

`"schema_version": 1` is written in every meta.json, but there is
no code that reads it. If the schema changes (e.g. a new field is
added, or the meaning of an existing field changes), old files
are silently misinterpreted.

The fix: add a schema registry (even if it's just a dict mapping
version -> expected fields) and a validation step at ingest.

### 6.3 Random seeds for LLM generation are optional
**Severity: medium.** `pipeline.py:274`

The `seed` field in `GenerationRequest` defaults to `None`. Many
Ollama and OpenAI models support a seed parameter for
reproducible outputs, but PerfArena doesn't require it. A
leaderboard entry generated without a seed is not reproducible.

The fix: at minimum, log a warning when `seed is None`. For the
core campaign, make seed mandatory and draw it from a
campaign-level master seed.

### 6.4 External tool versions are not recorded
**Severity: medium.** `static_analysis.py`

The static analysis module calls pylint, cppcheck, rustc, go vet,
eslint, and tsc, but does not record which version of each tool
was used. Two runs with different pylint versions can produce
different issue counts for the same source file.

The fix: capture `tool --version` output in the result dict.

---

## 7. Summary: what must be fixed before a real campaign

The table below lists the issues whose combined effect would make
a published leaderboard unreliable. Everything below "medium"
can wait.

| # | Issue | Severity | Effect on numbers |
|---|-------|----------|-------------------|
| 1.4 | Idle baseline captured but never subtracted | Critical | All energy numbers inflated by idle power, 10-50% depending on iteration length. |
| 1.1 | RAPL wrap-around handles only one wrap | Critical | Energy readings wrong for long runs (>~250 J per iteration). |
| 1.2 | RAPL start read includes fork() overhead | High | 5-50 ms systematic bias per iteration. |
| 1.3 | Only PKG counter read, not PP0/DRAM separately | High | Cannot separate core vs memory energy. |
| 2.2 | `ru_maxrss` bytes vs kB on macOS | High | RSS metric is 1024x wrong on macOS. |
| 2.1 | First agent call includes lazy-init overhead | High | Sample 0 biased by 2-10x. |
| 4.1 | Code extraction regex breaks on nested fences | High | Silently produces invalid source files. |
| 5.1 | stdin benchmarks produce empty output | High | 3 of 10 CLBG problems measure nothing. |
| 5.3 | No correctness oracle gates measurement | High | Incorrect code is measured and ranked. |
| 3.4 | Harmonic mean used on raw values, not ratios | Medium | Aggregate ranking is wrong unless consumer computes ratios first. |
| 5.2 | Perturbation seed defaults to problem key | Medium | Contamination probe may not probe contamination. |
| 1.5 | Idle baseline assumes the machine is idle | Medium | Baseline contaminated by background activity. |
| 3.2 | Float tie detection in Mann-Whitney U | Medium | P-values slightly wrong on aggregated data. |

The first five rows in this table (1.4, 1.1, 1.2, 1.3, 2.2) are
measurement-side issues that would make every number in the
leaderboard unreliable. They should be fixed before any data
collection. The next four (2.1, 4.1, 5.1, 5.3) are pipeline-side
issues that would produce wrong or missing data for specific
cells. The remaining rows are statistical or methodological issues
that affect interpretation but not raw data collection.
