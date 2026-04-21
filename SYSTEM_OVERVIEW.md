# PerfArena: how it works

PerfArena measures how good different language models are at writing
fast, efficient code. It asks each model to solve the same set of
programming problems in multiple languages, then compiles, runs, and
measures the code each model produces. The result is a public
ranking that shows which models write the fastest code, which use the
least memory, and which consume the least energy, broken down by
language and problem.

This document explains how the system is built and how the pieces
fit together.

---

## The idea in one paragraph

Take ten well-known programming problems. Ask a dozen language
models to solve each one in ten different programming languages.
Check that the solutions are correct. Measure how fast they run,
how much memory they use, and how much energy they consume. Record
everything, including the exact prompts, the model versions, the
compiler versions, and the hardware, so anyone can reproduce the
results. Publish the rankings.

---

## The two machines

PerfArena is designed around two separate machines.

**Your laptop** (or any machine with internet access) runs the
PerfArena toolbox inside a portable container. This machine talks
to the language model, generates source code, and compiles it. It
never runs the benchmarks for real measurement.

**The measurement machine** is a dedicated computer set up
specifically for accurate timing and energy readings. It has a
tuned operating system, stable clock speeds, and hardware energy
counters. It receives the compiled programs from your laptop over
a network connection, runs them many times, and sends back the
measurements.

You can also run everything on a single machine for testing. The
numbers won't be as clean, but the workflow is the same.

---

## What's in the container

The container is a pre-built environment that has everything needed
to compile programs in all ten target languages: Python, JavaScript,
TypeScript, Java, C#, C++, PHP, Go, Rust, and Ruby. It also has
cross-compilers, so if the measurement machine uses a different
processor architecture (for example, your laptop is Apple Silicon
but the measurement machine is Intel), the container can still
produce binaries that run on the measurement machine.

The container also holds the PerfArena command-line tool and the
code generation pipeline.

---

## How code generation works

When you ask PerfArena to generate code, it does this:

1. **Loads a prompt template from a file.** There are two templates:
   a system prompt that tells the model to act as an expert
   programmer, and a user prompt that describes the specific problem
   to solve. Each language also has a short hints file with
   language-specific tips (for example, "use buffered output in
   Java" or "disable sync_with_stdio in C++").

2. **Sends the prompt to the language model.** PerfArena supports
   four kinds of model providers: OpenAI, Anthropic, Google, and
   Ollama (for locally-hosted models). It uses the same interface
   for all of them, so switching providers is a one-flag change.

3. **Extracts the source code from the response.** Language models
   usually wrap their code in a fenced block. PerfArena pulls out
   the code and discards the explanation text.

4. **Writes three files.** For every generated sample, three files
   appear on disk:
   - The source code itself.
   - The full, unedited model response (for debugging).
   - A metadata file that records everything about the generation:
     which model, which version, what temperature, what prompts
     were used (identified by their fingerprints), how long the
     generation took, and how much energy the generation consumed.

### Measuring the generation itself

When you run with the `--via-agent` flag, the generation happens
inside a separate process called the "agent." The agent wraps the
model call in a profiler that records:

- How long the call took (wall-clock time).
- How much processor time the call used.
- How much memory the process consumed.
- How much energy was used during the call.

The energy reading comes from hardware counters on Linux or from
a software estimator called CodeCarbon on macOS. On Apple Silicon
Macs without administrator access, CodeCarbon falls back to a
power-consumption estimate based on the processor model. The
metadata file records which method was used, so you always know
how the number was produced.

The agent runs as a separate process on purpose: it keeps the
orchestrator's own resource usage out of the measurement. For
locally-hosted models where the model runs as a background service
(like Ollama), the agent can also track that service's processor
usage by looking up its process identifier.

---

## How measurement works

Measurement is the part where PerfArena finds out how fast and how
efficient the generated code actually is. It happens in three
steps: compile, validate, then measure.

### Step 1: Compile

The container compiles the generated source code into a runnable
program. For languages like C++, Rust, and Go, this produces a
native binary. For languages like Python, Ruby, and PHP, this is
just a file copy (the interpreter on the measurement machine runs
the source directly). For Java and C#, this produces
platform-independent bytecode.

If the measurement machine has a different processor than the
container, the container uses a cross-compiler to produce a binary
that matches the measurement machine's processor.

### Step 2: Validate

Before spending time on measurement, PerfArena checks that the
generated code actually produces the right answer. It runs the
program with a small input and compares the output, byte for byte,
against a known-correct reference. If the output doesn't match,
the sample is marked as incorrect and skipped. Only correct
programs get measured.

Three of the ten problems read their input from a pipe rather than
from a command-line argument. PerfArena handles this automatically:
the input files are pre-generated and the build system pipes them
in, so every problem is triggered the same way from the
measurement tool's perspective.

### Step 3: Measure

The measurement tool runs the program many times and records how
long each run takes and how much energy it uses.

On Linux, energy is measured by reading hardware counters built
into the processor (called "Running Average Power Limit" counters).
These give a direct reading of how many joules the processor
package consumed during each run. The measurement tool reads these
counters at high frequency (about 10 times per second) while the
program runs, so the reading covers the entire execution.

On macOS, where those hardware counters are not available,
PerfArena uses CodeCarbon, a software-based energy estimator. On
Apple Silicon with administrator access, CodeCarbon reads real
power data from the operating system. Without administrator access,
it estimates power from the processor's rated power consumption.
Either way, the energy numbers are comparable across models on the
same machine.

Each measurement campaign starts with a short idle period (a few
seconds of doing nothing) to establish a baseline for the machine's
idle power draw. Then it runs a set of warm-up iterations that are
recorded but not used for ranking, to let the runtime (especially
for languages with just-in-time compilation, like Java and
JavaScript) reach a stable state. Finally, it runs the measurement
iterations and records every one.

The output is a structured log file with one row per iteration,
containing the wall-clock time, the energy reading, the energy
source (hardware counter or software estimate), and the program's
exit code.

---

## How the correctness oracle works

Each of the ten benchmark problems has a known-correct reference
output stored in the repository. The reference was generated by
running the original human-written solutions (which have been
verified against the official benchmark specifications) at a small
input size.

When the `validate` step runs, it executes the generated program at
that same small input size and compares the output to the reference.
If they match exactly, the program passes. If they don't, it fails.
One benchmark (the Mandelbrot set renderer) produces binary image
data instead of text, so PerfArena uses a byte-level comparison
instead of a text diff for that one.

This is the gate between "code that compiles and runs" and "code
that's actually correct." Without it, the ranking would include
programs that exit instantly (because they crash or produce no
output), which would look artificially fast.

---

## How the pieces connect

Here is the flow for one sample:

```
You
 |
 |  perfarena generate --via-agent --provider ollama --model gemma4:e4b
 |                     --problem binary-trees --language python
 v
Container (your laptop)
 |
 |  1. Load prompt templates from files.
 |  2. Spawn the profiling agent.
 |     Agent calls the language model.
 |     Agent records inference time, memory, energy.
 |     Agent returns the response + metrics.
 |  3. Extract source code from the response.
 |  4. Write: source file, raw response, metadata file.
 |
 |  perfarena harness-run compile --language python --problem binary-trees
 |
 |  5. Compile the source for the measurement machine's processor.
 |
 |  perfarena harness-run validate --language python --problem binary-trees
 |
 |  6. Run at a small input size.
 |  7. Compare output to reference. PASS or FAIL.
 |
 |  (if PASS) ship the compiled program to the measurement machine
 |
 v
Measurement machine (dedicated hardware)
 |
 |  8. Idle baseline (a few seconds of silence).
 |  9. Warm-up iterations (recorded, not ranked).
 | 10. Measurement iterations (recorded, ranked).
 |     Each iteration: start energy counter, run program, stop energy counter.
 | 11. Write a structured log with one row per iteration.
 |
 |  ship the log back to the container
 |
 v
Container
 |
 | 12. Join the measurement log with the generation metadata.
 | 13. Compute statistics: median time, confidence interval, energy per run.
 | 14. Decide whether this sample can be ranked (skip it if the
 |     confidence interval is too wide to distinguish it from others).
 |
 v
Leaderboard row
```

---

## What gets recorded

Every number on the leaderboard can be traced back through a chain
of files:

- **The leaderboard row** points to a measurement log.
- **The measurement log** contains per-iteration timing and energy
  data, plus a reference to the generation metadata file.
- **The generation metadata file** contains the model name and
  version, the exact prompt text (identified by fingerprint), the
  sampling parameters (temperature, randomness settings), the
  inference time and energy, and the machine fingerprint (operating
  system, processor, available energy measurement method).
- **The raw response file** contains the full text the model
  returned, before any code extraction.
- **The source file** is the exact code that was compiled and
  measured.

This chain exists so that if someone questions a number on the
leaderboard, they can walk backwards through the files and see
exactly what produced it.

---

## Energy measurement: two methods

PerfArena uses two methods to measure energy, depending on what
hardware is available.

### Hardware counters (Linux, Intel and AMD processors)

Modern Intel and AMD processors have built-in counters that track
how much energy the processor package consumes. PerfArena reads
these counters directly through the operating system. This is the
most accurate method, and it's what PerfArena uses for publishable
results.

The measurement tool reads the counter before and after each
benchmark run. It also reads the counter at regular intervals
during the run (about 10 times per second) to keep the reading
path active. The energy for one run is the difference between the
start and end readings, measured in microjoules.

### Software estimation (macOS, and Linux without hardware counters)

On macOS (including Apple Silicon), the hardware counters are not
directly accessible. PerfArena uses CodeCarbon, an open-source
library that estimates energy consumption. On Apple Silicon with
administrator access, CodeCarbon reads real power data from the
operating system's power-management interface. Without administrator
access, it estimates power based on the processor model's rated
power consumption.

CodeCarbon reports energy in kilowatt-hours. PerfArena converts
this to microjoules (the same unit the hardware counters use) so
the downstream analysis code works identically regardless of which
method was used.

The metadata always records which method produced the energy
number (`"energy_source": "rapl"` for hardware counters,
`"energy_source": "codecarbon"` for the software estimator,
`"energy_source": "none"` if neither was available). Numbers from
different methods are never mixed in the same ranking.

---

## The ten problems

PerfArena uses ten benchmark problems from the Computer Language
Benchmarks Game, a long-running collection of small programs
designed to compare programming language performance. Each problem
tests a different kind of computation:

| Problem | What it does |
|---------|-------------|
| binary-trees | Allocates and frees millions of small objects. Tests memory management. |
| fannkuch-redux | Flips and permutes arrays. Tests raw computation speed. |
| fasta | Generates random DNA sequences. Tests streaming output. |
| k-nucleotide | Counts substrings in a DNA sequence. Tests hash-table performance. |
| mandelbrot | Renders a fractal image. Tests floating-point arithmetic. |
| n-body | Simulates gravitational physics. Tests numerical integration. |
| pidigits | Computes digits of pi. Tests big-number arithmetic. |
| regex-redux | Applies regular expressions to DNA data. Tests regex-engine speed. |
| reverse-complement | Reverses and transforms DNA sequences. Tests string processing. |
| spectral-norm | Estimates a matrix property. Tests dense linear algebra. |

These problems are small (typically under 200 lines of code),
well-specified (the expected output for any input is known exactly),
and diverse enough to exercise different parts of a language's
runtime. They have been used in language-comparison research for
over a decade, which means the results can be compared to prior
work.

---

## The ten languages

PerfArena targets the ten most widely used programming languages
according to the GitHub usage rankings:

| Language | How it runs | Compiled or interpreted |
|----------|-------------|------------------------|
| Python | Interpreter | Interpreted |
| JavaScript | Just-in-time compiled (V8 engine) | Interpreted + compiled at runtime |
| TypeScript | Transpiled to JavaScript, then run by V8 | Transpiled |
| Java | Compiled to bytecode, then just-in-time compiled | Bytecode + compiled at runtime |
| C# | Compiled to intermediate code, then just-in-time compiled | Bytecode + compiled at runtime |
| C++ | Compiled to native binary | Compiled ahead of time |
| PHP | Interpreter | Interpreted |
| Go | Compiled to native binary | Compiled ahead of time |
| Rust | Compiled to native binary | Compiled ahead of time |
| Ruby | Interpreter | Interpreted |

The set deliberately spans the spectrum from fully interpreted
languages (Python, Ruby, PHP) through runtime-compiled languages
(Java, C#, JavaScript) to ahead-of-time compiled languages (C++,
Rust, Go). This makes cross-language comparisons more interesting:
a model that writes fast C++ may or may not write fast Python,
and PerfArena measures both.

---

## Static analysis

In addition to runtime measurement, PerfArena can scan generated
code for common performance problems using language-specific
analysis tools. For Python it uses pylint, for C++ it uses
cppcheck, for Rust it uses the compiler's built-in lint warnings,
for Go it uses go vet, and for JavaScript and TypeScript it uses
the respective type-checkers and linters.

The output is a count of issues found, divided by the number of
lines of code, producing a "issues per thousand lines" metric. This
metric is reported alongside the runtime measurements but is not
mixed into the main ranking. It gives a different angle on code
quality: a program can be fast but full of bad practices, or slow
but cleanly written.

---

## The contamination probe

The benchmark problems are old and well-known, which means they are
almost certainly in the training data of every major language model.
A model might produce a fast solution not because it "understands"
performance, but because it memorized a fast human-written solution
from its training data.

PerfArena includes a contamination probe that tests this. It takes
the standard problem description and changes two things: it renames
the conventional variable names to unusual ones (for example,
"tree" becomes "gamma" and "depth" becomes "delta"), and it rescales
the input size. A model that is reciting a memorized solution will
either ignore the renamed variables (producing code that uses the
original names despite being told otherwise) or fail on the
rescaled input. A model that genuinely understands the problem will
adapt.

The renaming is deterministic (the same seed produces the same
names) so results are reproducible, but the seed is chosen per
campaign and not published in advance.

---

## The classification test

PerfArena also tests whether a model can *recognize* efficient code,
not just generate it. It shows the model two implementations of the
same problem in the same language (one fast, one slow, in a
randomized order) and asks it to pick the faster one. The answer is
scored against the actual measurement data.

This matters because generating efficient code and understanding
efficiency are different skills. A model might produce fast code
by pattern-matching against training data without understanding why
it's fast, in which case it would fail the classification test.

---

## What PerfArena does not do

- It does not rank languages against each other. The question is
  "which model writes the fastest Python," not "is Python faster
  than Rust." The language is held constant in every comparison.
- It does not publish absolute energy numbers as ground truth.
  The numbers are meaningful for comparing models on the same
  machine, not for predicting energy consumption on a different
  machine.
- It does not continuously update. Each measurement campaign is a
  snapshot: a fixed set of models, a fixed set of languages, a
  fixed set of problems, measured on a fixed machine. Re-running
  with new models is a new campaign.

---

## File layout

```
Energy-Languages/
    Dockerfile                 the container definition
    perfarena.mk               shared build rules for all benchmarks
    reference/
        inputs/                pre-generated input files for pipe-based problems
        outputs/               known-correct reference outputs for validation
    RAPL/
        perfarena_runner.c     Linux energy measurement tool (hardware counters)
    Python/                    one folder per language
        binary-trees/
            Makefile           build rules for this specific benchmark
            binarytrees.py     the source code to run
        ...
    perfarena/                 the Python package
        cli.py                 command-line interface
        config.py              problem and language definitions
        harness.py             drives compile / validate / measure
        measurement.py         reads measurement logs and joins with metadata
        stats.py               statistics (medians, confidence intervals, rankings)
        classification.py      the "pick the faster one" test
        perturb.py             the contamination probe
        static_analysis.py     code-quality scanning
        generation/
            pipeline.py        prompt rendering, model calling, code extraction
            agent.py           isolated profiling subprocess
            profiler.py        energy and resource measurement wrapper
            llm.py             model provider abstraction
        runners/
            codecarbon_runner.py   macOS energy measurement tool (software estimate)
        executors/
            local.py           run commands on this machine
            ssh.py             run commands on a remote machine
        prompts/
            system.txt         the "you are an expert programmer" prompt
            user.txt           the problem description template
            language_hints/    per-language tips for the model
        configs/
            problems.yaml      the ten benchmark problems
            languages.yaml     the ten target languages
    perfarena_out/             created at runtime, not checked in
        generations/           one folder per model, language, problem, sample
        measurements/          joined measurement + generation data
```

---

## How the system answers each research question

The proposal defines seven research questions. Here is which part
of PerfArena produces the data to answer each one.

### Question 1: Do different models produce code with systematically different runtime, memory, and energy profiles?

**What you run.** Generate N samples per model for every (language,
problem) cell. Validate each sample. Measure the ones that pass.
Ingest the measurement logs.

**Which components are involved.**
- `perfarena generate` (with `--via-agent` for inference profiling)
  produces the source code and records inference cost.
- `make validate` gates correctness.
- `make measure` (via the hardware-counter runner on Linux or the
  CodeCarbon runner on macOS) produces per-iteration timing and
  energy logs.
- `perfarena ingest-measurements` joins each log with its
  generation metadata.
- `stats.median_and_ci` computes the median runtime/energy per
  cell with a confidence interval.
- `stats.mann_whitney_u` tests whether the distributions of two
  models are statistically distinguishable within a cell.
- `stats.refuse_to_rank` drops cells whose confidence intervals
  overlap.

**What the answer looks like.** A table where each row is a model
and each column is a (language, problem) cell, with the median
wall time or energy per execution and its confidence interval.
Cells where the confidence intervals of two models don't overlap
represent a real difference.

---

### Question 2: Is a model's ranking stable across languages?

**What you run.** The same campaign as Question 1, but the analysis
looks across languages for a fixed problem (or across problems for
a fixed language).

**Which components are involved.**
- All the same generation and measurement steps as Question 1.
- `stats.kendall_tau_b` computes the rank correlation between a
  model's rankings in two different languages. A correlation near
  1.0 means the model that writes the fastest Python also writes
  the fastest Rust. A correlation near 0 means the rankings are
  unrelated.

**What the answer looks like.** A matrix of rank-correlation
coefficients, one per pair of languages, for each problem. If the
correlations are high, "best model" is stable across languages. If
they're low, different models excel in different languages.

---

### Question 3: How does model-generated code compare to the 2017 human reference solutions?

**What you run.** Measure both the model-generated samples (from
the core campaign) and the human-written reference solutions that
ship with the fork (the original programs from 2017). Compare
them on the same hardware.

**Which components are involved.**
- `make compile` and `make measure` on the human reference (the
  default `SOURCE` in each Makefile) produces the human baseline.
- The same steps on the model-generated code (with
  `SOURCE=perfarena_generated.<ext>`) produce the model data.
- Direct comparison of the median wall time and energy per cell.

**What the answer looks like.** A ratio per cell: model median
divided by human median. A ratio below 1.0 means the model's code
is faster than the human reference. A ratio above 1.0 means it's
slower. Broken down by language to see where models are catching
up and where they're still behind.

---

### Question 4: When inference energy is included, how many runs does it take to break even?

**What you run.** The same campaign as Question 1, with
`--via-agent` so that every generation records the energy the
model consumed while producing the code. Then combine the
inference energy (from the metadata file) with the per-execution
energy (from the measurement log).

**Which components are involved.**
- The profiling agent (`perfarena-agent`) measures inference
  energy via CodeCarbon or hardware counters.
- The metadata file stores that number in
  `inference.metrics.energy_uj`.
- The measurement log stores per-execution energy in
  `rapl_pkg_delta_raw`.
- `stats.break_even_point` computes how many times the generated
  code must run before the energy savings (compared to a baseline)
  recover the one-time inference cost.

**What the answer looks like.** A number per (model, language,
problem) cell: "this model's code breaks even after X executions."
Small numbers mean the model is worth using even for code that
runs a few times. Large numbers mean the model is only worthwhile
for hot-path code that runs thousands of times.

---

### Question 5: Can a model that generates inefficient code still recognize which of two implementations is faster?

**What you run.** After the core campaign has produced measurement
data, run the classification test.

**Which components are involved.**
- `classification.build_pairs_from_measurements` picks the fastest
  and slowest sample for each cell from the measurement data.
- `classification.classify_pair` shows each pair to a model (in
  randomized order) and asks it to pick the faster one.
- The answer is scored against the measurement-derived ground truth.

**What the answer looks like.** An accuracy percentage per model:
"model X correctly identified the faster implementation Y% of the
time." A model that generates slow code but scores high on
classification understands efficiency in principle but can't
produce it. A model that generates fast code but scores low on
classification is pattern-matching without understanding.

---

### Question 6: Do prompt and decoding interventions improve the efficiency of generated code?

**What you run.** Generate additional samples using modified prompt
templates: an efficiency-focused system prompt, few-shot examples
of efficient code, explicit algorithmic hints, or different
sampling temperatures. Compare the resulting measurements against
the baseline campaign.

**Which components are involved.**
- Custom prompt template files under `perfarena/prompts/`. The
  `--system-template` and `--user-template` flags on
  `perfarena generate` point at the modified templates.
- The contamination probe (`perturb.perturb_prompt_context`)
  can generate a perturbed version of the user prompt that
  renames identifiers, testing whether the improvement comes
  from understanding or from memorization.
- All the same measurement, ingest, and statistics steps.

**What the answer looks like.** A comparison of median runtime
and energy between the baseline prompt and each intervention, per
(model, language, problem) cell. An intervention that consistently
improves efficiency across models and problems is a real finding.
One that only helps certain models or certain problems is a
prompt-sensitivity result.

---

### Question 7: Is there a tradeoff between correctness and efficiency?

**What you run.** The core campaign. The validation step already
records which samples pass and which fail. The measurement step
only runs on correct samples. So the data for this question falls
out of the existing pipeline.

**Which components are involved.**
- The pass rate per (model, language, problem) cell comes from
  counting how many of the N generated samples passed the
  `make validate` step.
- The efficiency (median wall time, energy) comes from the
  measurement data on the passing samples.
- Plotting pass rate against efficiency for each model shows
  whether models that produce faster code tend to produce fewer
  correct programs.

**What the answer looks like.** A scatter plot per language: the
x-axis is the pass rate (fraction of correct samples), the y-axis
is the median wall time or energy of the correct samples. Models
in the lower-right corner (high correctness, low runtime) are the
best. Models in the upper-left corner (low correctness, high
runtime) are the worst. A downward-sloping trend would mean that
the models producing the fastest code also produce the most
correct code (no tradeoff). An upward-sloping trend would mean
there is a tradeoff.
