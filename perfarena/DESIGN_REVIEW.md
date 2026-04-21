# PerfArena design review

A plain record of what is implemented today, what choices we made
on purpose, what gaps are still open, what is likely to bite us
when we actually run the experiment, and what threats the final
results will be subject to even after the gaps are closed.

This is not a rewrite of the proposal's Section 8. The proposal is
forward-looking. This document is a status report on the code
inside this fork and the decisions behind it.

---

## 1. Implementation status

### Build and orchestration
- Build container with ten language toolchains and aarch64 cross-compilers — **done**
- `pyproject.toml` with deps and the two console scripts — **done**
- `perfarena` CLI and `perfarena-agent` installable — **done**

### Config and data model
- `config.py` loader and dataclasses — **done**
- `configs/problems.yaml` (10 CLBG problems) — **done**
- `configs/languages.yaml` (10 target languages) — **done**

### Executor abstraction
- `Executor` protocol with `run`, `put_file`, `get_file`, `exists`, `probe_arch`, `close` — **done**
- `LocalExecutor` — **done**
- `SSHExecutor` with SFTP and arch probing — **done**
- `from_config` factory — **done**

### Harness
- `Harness.run_action` with target-arch env vars for compile — **done**
- `Harness.run_all` sweep — **done** (naive nested loop)
- `Harness.ensure_source_staged` helper — **done** (not yet called by the pipeline)
- Automatic split of `compile` (LocalExecutor) from `run` / `measure` (SSHExecutor) — **not done**
- Orchestrated compile → stage → measure → fetch flow — **not done**

### Generation pipeline
- LangChain chat-model factory for OpenAI / Anthropic / Google / Ollama — **done**
- `generate_one` (direct, no inference profiling) — **done**
- `generate_one_via_agent` (isolated subprocess, profiled) — **done**
- Prompt template loading from files with format-string rendering — **done**
- Code extraction from fenced blocks, per-language alias preference — **done**
- Raw response and `meta.json` sidecars — **done**
- Prompt intervention variants (efficiency-oriented, CoT, few-shot) — **not done**
- N=10 per cell orchestrated across full slate — **not done**

### Profiler and agent
- `Profiler` context manager (wall, CPU, peak RSS, RAPL delta, target PID) — **done**
- Standalone `perfarena-agent` reading JSON on stdin — **done**
- Target-PID CPU and RSS attribution via psutil — **done** (best-effort)
- Persistent-mode agent (long-lived, keeps weights loaded) — **not done**
- Remote agent over SSH (orchestrator on laptop, agent on LLM host) — **not done**

### Prompts
- `prompts/system.txt` and `prompts/user.txt` — **done**
- `prompts/language_hints/{python,javascript,typescript,java,csharp,cpp,php,go,rust,ruby}.txt` — **done**
- Alternate templates for prompt-intervention follow-up — **not done**

### CLI
- `list-problems`, `list-languages` — **done**
- `generate` (direct + `--via-agent` + target-process + target-pid) — **done**
- `exec-check` (local + SSH) — **done**
- `harness-run` (with `--target-arch`) — **done**
- Measurement ingest command — **not done**
- Leaderboard regeneration command — **not done**
- Full-campaign sweep runner — **not done**

### Existing fork's build plumbing (inherited from 2017)
- Per-benchmark `Makefile`s respecting `$(CC)` / `$(CXX)` / `$(CARGO_BUILD_TARGET)` / `$(GOOS)` / `$(GOARCH)` — **done** (101 Makefiles patched via `patch_makefiles.py`)
- Modernised toolchain paths in the Makefiles — **done**
- `RAPL/main.c` periodic sampling at ≥1 Hz — **not done** (still single end-point reads)
- `RAPL/main.c` idle-baseline calibration — **not done**
- JIT warm-up amortisation at the harness level — **not done**
- Active-core accounting via `perf stat` — **not done**

### Measurement and statistics
- CSV-to-Parquet ingest — **not done**
- Per-row provenance joiner — **not done**
- Harmonic-mean speedup aggregator — **not done**
- Kendall's tau, Mann-Whitney U, 95% CI computation — **not done**
- "Refuse to rank if CIs overlap" policy — **not done**
- Break-Even Point computation — **not done**
- Multiple-comparisons correction (Holm / Bonferroni) — **not done**
- Higher-N validation sub-study runner — **not done**

### Static analysis / classification / perturbation
- PAP density per language (PMD, SpotBugs, ESLint, clippy, staticcheck, Pylint perf plugins) — **not done**
- "Pick the faster of two implementations" classification subtask — **not done**
- Perturbed-CLBG sensitivity arm (renamed identifiers, rescaled inputs) — **not done**

### Environment and reproducibility controls
- Git SHA and container image digest captured in every `meta.json` — **not done** (toolchain versions are captured at image build time only)
- Automated frequency pinning / governor check on the measurement host — **not done**
- Thermal sensor logging and cooldown gates — **not done**
- Container-tax calibration step (three configurations: bare metal, default Podman, Podman + cgroup limits) — **not done**
- Schema version migration story — **not done** (`schema_version: 1` is emitted, nothing consumes it)

### Leaderboard and deliverables
- Parquet schema and writer — **not done**
- Hugging Face Space front-end — **not done**
- Per-language, per-problem, per-algorithmic-class, per-lifecycle, overall views — **not done**
- ACM Artifact Evaluation reproducibility package — **not done**

### Tests
- Unit tests, smoke tests, end-to-end tests — **not done**

---

## 2. Deliberate design trade-offs

Each trade-off: what we chose, what we rejected, why, what it costs.

### 2.1 Container builds, remote measures
**Chosen.** The build container holds every compiler and transpiler, including aarch64 cross toolchains. The measurement host only holds pinned runtimes, `perf`, and RAPL. Binaries are cross-compiled inside the container and shipped to the remote via SFTP.

**Rejected.** A single SSH-driven flow where the measurement host also owns all the compilers.

**Why.** Keeps the lab host minimal and pinned. Toolchain version changes land in the Docker image, not on the lab box, which makes the lab state auditable.

**Cost.** One extra SFTP hop per build. We must handle cross-compilation correctly for every native-compiled language.

### 2.2 One-shot agent subprocess
**Chosen.** `perfarena-agent` is a fresh process per generation.

**Rejected.** A long-running HTTP or gRPC agent that keeps model weights loaded across calls.

**Why.** Simplest possible measurement. No server lifecycle, no state leak. For Ollama (the likely first local-LLM provider), the daemon already keeps models warm, so one-shot is fine in practice.

**Cost.** For in-process LLMs (`transformers`, `llama-cpp-python`), every call pays the full model-load cost. Any measurement campaign that uses those providers is blocked until persistent-mode lands.

### 2.3 Cross-compile in container
**Chosen.** C++, Rust, and Go get their target-specific toolchains inside the container. `GOARCH`, `CARGO_BUILD_TARGET`, and `CC`/`CXX` are set per (language, target arch).

**Rejected.** Native compile on the remote using the remote's installed compiler.

**Why.** One pinned image is easier to audit than a drifting lab install.

**Cost.** The aarch64 cross toolchain targets glibc Linux. Remote hosts using musl (Alpine) or a different libc would need a second cross toolchain we haven't installed.

### 2.4 Fork the existing harness instead of rewriting
**Chosen.** Fork `greensoftwarelab/Energy-Languages`, preserve the `Makefile`-per-benchmark contract, keep the `RAPL/main.c` C tool, keep the folder layout.

**Rejected.** Write a new harness from scratch with a unified Python build driver.

**Why.** Direct comparability with the 2017 baseline and with van Kempen et al.'s 2025 run, and faster bootstrapping. The replication-on-modern-infrastructure follow-up depends on it.

**Cost.** We inherit around 300 hand-written Makefiles. Before anything works end to end, they need to be patched to respect modern toolchain variables and modern compiler paths.

### 2.5 Ten CLBG problems, ten languages, both frozen
**Chosen.** The 10 CLBG problems used in the Pereira harness, and ten target languages (Python, JavaScript, TypeScript, Java, C#, C++, PHP, Go, Rust, Ruby).

**Rejected.** A sliding problem set, GSO-style commit mining, or a rolling language list.

**Why.** Direct comparability, stable definitions, fits on one reference host. All ten languages already exist in the fork with working CLBG implementations.

**Cost.** CLBG is numeric and micro-benchmarky, and the problems are almost certainly in every modern LLM's training data. External validity to production code is limited. Swift, Kotlin, Scala, Julia, and functional lineages are out of scope.

### 2.6 LangChain as the provider abstraction
**Chosen.** `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, `langchain-community` (Ollama).

**Rejected.** Per-provider direct SDKs.

**Why.** One `chat.invoke(messages)` interface across all providers. Easy to swap or add providers.

**Cost.** LangChain minor versions have historically broken message shapes and tool-call conventions. Our `>=0.3` pin is loose. Provider-specific parameters (Anthropic extended thinking, Ollama seed, Google safety settings) are not uniformly supported.

### 2.7 Prompt templates in plain text files
**Chosen.** `system.txt`, `user.txt`, and ten per-language hint files under `prompts/language_hints/`, rendered via Python `str.format`.

**Rejected.** Embedding prompts in Python source or in YAML.

**Why.** Prompts are what we iterate on most. File overrides are trivial (`--system-template`, `--user-template`), and the prompt-intervention follow-up is implementable with nothing more than new files.

**Cost.** Any literal `{` or `}` inside a prompt has to be doubled. This will trip up a future maintainer.

### 2.8 Preserve the Makefile-per-benchmark contract
**Chosen.** Keep `make compile`, `make run`, `make measure`, `make mem`, `make clean` as the per-benchmark interface.

**Rejected.** A unified Python build driver that knows about every language and problem.

**Why.** The existing Makefiles are the canonical 2017 entry points. Replacing them breaks replication.

**Cost.** Every compiler or flag change has to happen per Makefile. The target-arch env vars the harness exports only matter if each Makefile actually uses them, which the current ones do not.

### 2.9 Per-row provenance discipline
**Chosen.** Every generated sample produces three files (source, raw response, `meta.json`). Every measurement row will eventually carry experiment, generation, and measurement run IDs.

**Rejected.** A lighter metadata schema with just model name and language.

**Why.** Reproducibility is load-bearing in the proposal.

**Cost.** Three files per sample; disk usage is higher; schema drift is a real risk; ingestion has to join multiple sidecars.

### 2.10 RAPL primary, CodeCarbon secondary
**Chosen.** RAPL via `perf` on x86 is authoritative. CodeCarbon is a separately-reported column on ARM or Apple Silicon secondary profiles.

**Rejected.** CodeCarbon everywhere, or a unified software estimator.

**Why.** RAPL is hardware-backed. CodeCarbon has documented 20% deviation from RAPL.

**Cost.** Cross-backend comparability is a known threat. Never mix them in a single ranking.

### 2.11 N=10 generations per cell, K=30 execution iterations
**Chosen.** Ten independent generations at a fixed sampling temperature (plus one deterministic pass at T=0) and thirty in-process iterations per accepted sample (first ten as warm-up, ten through thirty as the measurement).

**Rejected.** Larger N/K (better variance estimates) or smaller (smaller budget).

**Why.** 10 × 30 × ~14 models × 10 languages × 10 problems ≈ 4.2M executions. Fits on one reference host over a reasonable campaign window.

**Cost.** N=10 is small relative to LLM generation stochasticity. A higher-N sub-study on a subset is the hedge and isn't coded.

### 2.12 Unit of analysis = LLM, not language
**Chosen.** Ask "within a fixed language and problem, which LLM produces the more efficient code".

**Rejected.** Ask "which language is greener" (the 2017 framing).

**Why.** Per-language differences across models cannot be attributed to the language because the language is held constant. The framing sidesteps the energy-vs-runtime debate entirely.

**Cost.** Users who want a single "best language" ranking have to compute it themselves from the per-language views.

---

## 3. Implementation gaps (the things actually missing)

These are the concrete deltas between "what the diagram shows" and "what the code does".

### 3.1 The Makefiles are still 2017-era
Every per-benchmark Makefile in the fork hardcodes absolute compiler paths and specific language versions (for example `Python/binary-trees/Makefile` uses `/usr/local/src/Python-3.6.1/bin/python3.6`). The target-arch env vars the harness exports do nothing until each Makefile is patched to respect `$(CC)`, `$(CXX)`, `$(CARGO_BUILD_TARGET)`, and `$(GOARCH)`. This is the single biggest blocker and everything else downstream is waiting on it.

### 3.2 `RAPL/main.c` samples once per run
Section 4 item 1 of the proposal commits to periodic sampling at ≥1 Hz. The C tool currently reads the counter at run start and run end. Single-point reads are exactly the pattern van Kempen et al. flagged. Until the C tool is patched, any number produced by `make measure` is not the number PerfArena intends to publish.

### 3.3 The harness does not split compile from measure
`harness.run_action` sends the `make` invocation through whichever executor was passed to the `Harness` constructor. To get the "container builds, remote measures" flow the diagram shows, the harness needs a second executor (or a policy) that routes `compile` to `LocalExecutor` and `run`/`measure`/`mem` to `SSHExecutor`, with `ensure_source_staged` + SFTP between them. The building blocks exist; the orchestration does not.

### 3.4 No CSV ingest
`RAPL/main.c` writes energy readings to per-language CSV files next to each benchmark. Nothing on the orchestrator reads those CSVs, joins them with the generation `meta.json`, or writes a Parquet row. The entire "leaderboard dataset" side of the project is empty.

### 3.5 No statistics layer
Harmonic-mean aggregation, 95% CI computation, the refuse-to-rank-if-CIs-overlap rule, Mann-Whitney U, Kendall's tau, Holm/Bonferroni correction, BEP computation, and the higher-N sub-study runner are all described in the proposal and missing from the code.

### 3.6 No static analysis
PAP density per language is part of the multi-oracle evaluation. No linter is wired and the result schema has no field for it. The classification subtask from NoFunEval and the perturbed-CLBG probe are also absent.

### 3.7 Environmental controls are manual
Frequency pinning, governor state, thermal logging, NUMA pinning, and cooldown gates are described as the responsibility of the bare-metal host. The harness does not check that the host is in the expected state before a measurement, and it does not log thermals per iteration.

### 3.8 Git SHAs and image digests are not captured at run time
`/etc/perfarena-versions` is written at image build time, which captures toolchain versions but not the PerfArena git SHA, the container image digest in use, or the harness's commit. The `meta.json` should record these per run.

### 3.9 No remote agent mode
Today the agent runs as a local subprocess. For the isolated-LLM-host layout the diagram shows, the orchestrator would invoke the agent through `SSHExecutor.run(["perfarena-agent"], input=...)`, ship request and response through SFTP, and collect the results. The executor has the primitives but the pipeline function doesn't use them yet.

### 3.10 No tests
Not a smoke test, not a unit test, not an end-to-end test. Every file in this package has had exactly one author look at it once.

---

## 4. Blindspots

Things we have not thought through enough yet, or that will likely cause trouble once real data starts flowing.

### 4.1 The Makefile patch is not mechanical
Every benchmark Makefile was written by a different contributor in 2017. Patching roughly three hundred of them is a per-file pattern match that cannot be done with a single `sed`: some set the compiler via a direct command, some use shell conditionals, some hardcode absolute paths, some embed shell loops. The budget for this patch is unknown and it's the gating task.

### 4.2 Package-level RAPL captures everything
RAPL is a package-wide counter. During any measurement run it accumulates the LLM daemon's work (if it's still running on the same box), the orchestrator, the OS, and every background process. Idle-baseline subtraction is essential and not yet implemented. The `target_pid` CPU-delta attribution we have is about CPU time, not energy.

### 4.3 Multi-threaded benchmarks vs single-threaded variants
Several CLBG problems (fannkuch-redux, mandelbrot, spectral-norm, k-nucleotide) have both single- and multi-threaded reference implementations. The proposal constrains cross-language comparisons to single-threaded variants, but the per-problem decision has not been frozen and the Makefiles have both.

### 4.4 The one-shot agent and in-process LLMs
Every time the agent starts, Python re-imports LangChain and the provider integration. For Ollama (HTTP to a daemon) this is cheap. For `transformers` or `llama-cpp-python` (in-process), the model reloads every call, which is a showstopper. Persistent-mode agent is not optional for those providers.

### 4.5 `--target-process ollama` is brittle
`find_process_by_name` returns the first PID whose `name` is `ollama`. If the daemon is `ollama-server`, or if the daemon runs in its own container with a separate process tree, the lookup returns `None` and the target-PID columns are empty. The profiler writes a note, but downstream analysis has to remember to check the `notes` field and many users will not.

### 4.6 Toolchain drift is not enforced at run time
The Docker image captures `/etc/perfarena-versions` at build time. Nothing in the per-row metadata asserts that the container was built from the expected image tag. A caller with a stale image can produce results that claim pinned toolchains without actually using them.

### 4.7 LangChain API churn
`langchain-core>=0.3` is a loose pin. Minor upgrades have historically changed message shapes, content-part encodings, and callback contracts. A silent upgrade mid-campaign can change generation behaviour without any code change on our side.

### 4.8 Closed-model versions rotate silently
OpenAI, Anthropic, and Google update weights without renaming the public model. Recording the name-plus-date is the best we can do from the client.

### 4.9 Cross-compile assumes glibc
`gcc-aarch64-linux-gnu` produces glibc-linked binaries. A musl-based measurement host (Alpine) cannot execute them. We've quietly assumed glibc Linux everywhere.

### 4.10 Prompts have a single cultural register
All prompts are English and follow a particular Western idiom. Different models have different prompt-format preferences (bare text vs Markdown, explicit role-play vs role-only, chain-of-thought triggers). Our current templates do not adapt per model.

### 4.11 N=10 may be too few for high-variance cells
Reasoning-heavy models at T=0.2 still produce noticeable inter-sample variance. The planned fix (higher-N sub-study) isn't coded. Until it is, we don't know if the core sweep's variance estimates are trustworthy on the worst-case cells.

### 4.12 RAPL permissions
`/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` has to be readable by the user running the agent. Recent kernels have tightened this. Unprivileged containers usually don't even mount the directory. The agent degrades gracefully (`energy_source: "none"`), but a user who doesn't notice will think they got an energy measurement when they didn't.

### 4.13 Benchmarks whose input comes from stdin
`k-nucleotide`, `regex-redux`, and `reverse-complement` read from stdin. The 2017 Makefiles wire stdin redirection internally. Any Makefile rewrite has to preserve that, and the harness code today does not know about it at all.

### 4.14 Single point of authorship
Every file in this package was written by one author in a small number of sessions. There are no tests. There has been no review. Any claim about correctness is on trust.

---

## 5. Threats to validity of the experimental results

Most of these will survive even after the implementation gaps are closed. Organised by the standard empirical-software-engineering framing.

### 5.1 Construct validity

- **Energy tracks runtime on most cells.** van Kempen et al. (2025) argue that once confounds are removed, energy is proportional to runtime. We report both anyway and flag divergent cells, but the "energy ranking" may reduce to a "runtime ranking" in practice.
- **PAP density is cold-code-agnostic.** Static analysers count anti-patterns wherever they appear, not just in hot paths. A PAP in an `if __name__ == "__main__":` block is harmless at runtime. PAP density is reported as an auxiliary column, not as a ranking signal.
- **BEP is deployment-context-dependent.** The Break-Even Point depends on the LLM-host's power profile, the cloud-API cost model if the model is API-based, and the measurement host's execution cost. Our BEP numbers are conditional on one (LLM host, measurement host) pair.
- **"Most efficient code" is a multi-objective decision.** Collapsing runtime + memory + energy + PAP density into a single score is impossible without weights we refuse to pick. PerfArena publishes views, not a score.

### 5.2 Internal validity

- **Single reference machine.** Every cross-model comparison is conditional on the specific CPU, memory topology, kernel, and microcode of the bare-metal host.
- **Toolchain drift mid-campaign.** A security update to GCC or the JVM mid-campaign invalidates within-study comparability. Toolchains are pinned in the Dockerfile but there is no campaign-freeze mechanism that refuses to build if the image digest changes.
- **Prompt format confounds model identity.** A single common prompt cannot be fair to every model. Prompt sensitivity is an object of study for a follow-up that isn't coded.
- **Closed-model silent updates.** We pin by date string, but nothing we do prevents the provider from silently rotating weights. Snapshotting raw generations is the only mitigation.
- **Generation variance vs execution variance.** Two sources of variance, reported separately. Without the higher-N sub-study, we do not know if N=10 is enough.

### 5.3 External validity

- **CLBG is small and numeric.** Generalisation to production code is unjustified.
- **CLBG contamination.** Every modern LLM has almost certainly trained on CLBG solutions. The perturbed-CLBG probe is a sensitivity arm, not a fix.
- **Ten languages is not all languages.** Swift, Kotlin, Scala, Julia, and functional lineages are out of scope.
- **Single hardware profile.** Results are conditional on x86_64 glibc Linux on the specific CPU we pin. Mobile, embedded, and ARM cloud are future work.
- **LLM slate is a snapshot.** Fixed at campaign start. Re-running on a refreshed slate is a follow-up paper, not an automatic update.

### 5.4 Conclusion validity

- **Measurement noise on sub-second cells.** CLBG problems with default inputs that run in under a second are dominated by RAPL noise. Input-size tuning per benchmark is not automated yet.
- **Overlapping confidence intervals.** The "refuse to rank if CIs overlap" rule isn't coded.
- **Multiple comparisons.** Ten languages × ten problems × ~14 models yields about 1,400 cells. Naive p-values lose meaning at that scale. Holm/Bonferroni correction and effect-size reporting are planned and not coded.
- **Calibration drift.** Ambient temperature, kernel updates, thermal soak cause day-to-day drift. Recalibration before each campaign is described but the thermal-logging and drift-gating code is missing.

### 5.5 Specific threats the current implementation introduces

- **No measurement has been run yet.** Every threat above is theoretical. Real ones will emerge from contact with the measurement host.
- **The harness split isn't wired.** Until `run_action` routes `compile` to `LocalExecutor` and the other actions to `SSHExecutor`, the "container builds, remote measures" separation is enforced by user discipline only. A user who forgets `--host` will silently measure inside the build container.
- **The Makefiles haven't been patched.** Every claim about cross-compilation and pinned toolchains is false end-to-end today because the fork's Makefiles still target 2017 paths. Until the patch lands, `harness-run compile` runs whatever the Makefile thinks the compiler is.
- **`RAPL/main.c` hasn't been updated.** Running `make measure` against the unpatched fork reads RAPL once per run, which is the noise-dominated pattern the proposal explicitly rejects.
- **Authorship concentration.** One author, no reviews, no tests. Any single mistake in any of these files is undetected.

---

## 6. Priority order for closing the gaps

Roughly the order that gets us to a first real measurement campaign.

1. **Patch the Makefiles.** Teach each per-benchmark Makefile to respect `$(CC)` / `$(CXX)` / `$(CARGO_BUILD_TARGET)` / `$(GOARCH)` and modern toolchain paths. Biggest single task.
2. **Split `run_action`.** Route `compile` to `LocalExecutor` and the other actions to `SSHExecutor`, with SFTP-based artifact staging between them.
3. **Update `RAPL/main.c`.** Periodic sampling at ≥1 Hz, idle-baseline subtraction, per-iteration trace output, warm-up vs steady-state split.
4. **Write CSV ingest and the provenance joiner.** Parquet output, schema versioning that actually migrates.
5. **Write the statistics layer.** Harmonic mean, 95% CIs, refuse-to-rank rule, Mann-Whitney U, Kendall's tau.
6. **Wire at least one static analyser per language** for PAP density.
7. **Run the container-tax calibration** on the reference host.
8. **Run the 2017-baseline replication.** Confirms the modernised harness reproduces the original numbers.
9. **Start the first real core-study campaign.**

Everything else (persistent agent, remote agent, classification subtask, perturbed-CLBG, higher-N sub-study, leaderboard front-end, Pareto-frontier analysis, prompt-intervention arm, ACM Artifact Evaluation packaging) can come after the first measurement lands.
