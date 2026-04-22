# Energy Efficiency in Programming Languages
#### Checking Energy Consumption in Programming Languages Using the _Computer Language Benchmark Game_ as a case study.

### What is this?

This repo contains the source code of 10 distinct benchmarks, implemented in 28 different languages (exactly as taken from the [Computer Language Benchmark Game](https://benchmarksgame-team.pages.debian.net/benchmarksgame/)).

It also contains tools which provide support, for each benchmark of each language, to 4 operations: *(1)* **compilation**, *(2)* **execution**, *(3)* **energy measuring** and *(4)* **memory peak detection**.

### How is it structured and hows does it work?

This framework follows a specific folder structure, which guarantees the correct workflow when the goal is to perform and operation for all benchmarks at once.
Moreover, it must be defined, for each benchmark, how to perform the 4 operations considered.

Next, we explain the folder structure and how to specify, for each language benchmark, the execution of each operation.

#### The Structure
The main folder contains 32 elements: 
1. 28 sub-folders (one for each of the considered languages); each folder contains a sub-folder for each considered benchmark.
2. A `Python` script `compile_all.py`, capable of building, running and measuring the energy and memory usage of every benchmark in all considered languages.
3. A `RAPL` sub-folder, containing the code of the energy measurement framework.
4. A `Bash` script `gen-input.sh`, used to generate the input files for 3 benchmarks: `k-nucleotide`, `reverse-complement`, and `regex-redux`.

Basically, the directories tree will look something like this:

```Java
| ...
| <Language-1>
	| <benchmark-1>
		| <source>
		| Makefile
		| [input]
	| ...
	| <benchmark-i>
		| <source>
		| Makefile
		| [input]
| ...
| <Language-i>
	| <benchmark-1>
	| ...
	| <benchmark-i>
| RAPL
| compile_all.py
| gen-input.sh

```

Taking the `C` language as an example, this is how the folder for the `binary-trees` and `k-nucleotide` benchmarks would look like:

```Java
| ...
| C
	| binary-trees
		| binarytrees.gcc-3.c
		| Makefile
	| k-nucleotide
		| knucleotide.c
		| knucleotide-input25000000.txt
		| Makefile
	| ...
| ...

```

#### The Operations

Each benchmark sub-folder, included in a language folder, contains a `Makefile`.
This is the file where is stated how to perform the 4 supported operations: *(1)* **compilation**, *(2)* **execution**, *(3)* **energy measuring** and *(4)* **memory peak detection**.

Basically, each `Makefile` **must** contains 4 rules, one for each operations:

| Rule | Description |
| -------- | -------- |
| `compile` | This rule specifies how the benchmark should be compiled in the considered language; Interpreted languages don't need it, so it can be left blank in such cases. |
| `run` | This rule specifies how the benchmark should be executed; It is used to test whether the benchmark runs with no errors, and the output is the expected. |
| `measure` | This rule shows how to use the framework included in the `RAPL` folder to measure the energy of executing the task specified in the `run` rule. |
| `mem` | Similar to `measure`, this rule executes the task specified in the `run` rule but with support for memory peak detection. |

To better understand it, here's the `Makefile` for the `binary-trees` benchmark in the `C` language:

```Makefile
compile:
	/usr/bin/gcc -pipe -Wall -O3 -fomit-frame-pointer -march=native -fopenmp -D_FILE_OFFSET_BITS=64 -I/usr/include/apr-1.0 binarytrees.gcc-3.c -o binarytrees.gcc-3.gcc_run -lapr-1 -lgomp -lm
	
measure:
	sudo ../../RAPL/main "./binarytrees.gcc-3.gcc_run 21" C binary-trees

run:
	./binarytrees.gcc-3.gcc_run 21

mem:
	/usr/bin/time -v ./binarytrees.gcc-3.gcc_run 21

```

### Running an example.

*First things first:* We must give sudo access to the energy registers for RAPL to access
```
sudo modprobe msr
```
and then generate the input files, like this
```Makefile
./gen-input.sh
```
This will generate the necessary input files, and are valid for every language.

We included a main Python script, `compile_all.py`, that you can either call from the main folder or from inside a language folder, and it can be executed as follows:

```PowerShell
python compile_all.py [rule]
```

You can provide a rule from the available 4 referenced before, and the script will perform it using **every** `Makefile` found in the same folder level and bellow.

The default rule is `compile`, which means that if you run it with no arguments provided (`python compile_all.py`) the script will try to compile all benchmarks.

The results of the energy measurements will be stored in files with the name `<language>.csv`, where `<language>` is the name of the running language. 
You will find such file inside of corresponding language folder.

Each <language>.csv will contain a line with the following: 

```benchmark-name ; PKG (Joules) ; CPU (J) ; GPU (J) ; DRAM (J) ; Time (ms)```

Do note that the availability of GPU/DRAM measurements depend on your machine's architecture. These are requirements from RAPL itself.

### Add your own example!
#### Wanna know your own code's energy behavior? We can help you!
#### Follow this steps:

##### 1. Create a folder with the name of you benchmark, such as `test-benchmark`, inside the language you implemented it.

##### 2. Follow the instructions presented in the [Operations](#the-operations) section, and fill the `Makefile`.

##### 3. Use the `compile_all.py` script to compile, run, and/or measure what you want! Or run it yourself using the [`make`](https://linux.die.net/man/1/make) command.

### Further Reading
Wanna know more? Check [this website](https://sites.google.com/view/energy-efficiency-languages)!

There you can find the results of a successful experimental setup using the contents of this repo, and the used machine and compilers specifications.

You can also find there the paper which include such results and our discussion on them:

>**"_Energy Efficiency across Programming Languages: How does Energy, Time and Memory Relate?_"**, 
>Rui Pereira, Marco Couto, Francisco Ribeiro, Rui Rua, Jácome Cunha, João Paulo Fernandes, and João Saraiva. 
>In *Proceedings of the 10th International Conference on Software Language Engineering (SLE '17)*

#### IMPORTANT NOTE:
The `Makefiles` have specified, for some cases, the path for the language's compiler/runner. 
It is most likely that you will not have them in the same path of your machine.
If you would like to properly test every benchmark of every language, please make sure you have all compilers/runners installed, and adapt the `Makefiles` accordingly.

---

## PerfArena changelog

This fork extends the original Energy-Languages repository with
the PerfArena benchmarking infrastructure. Everything below was
added on top of the original codebase. The original files are
preserved; modified Makefiles have a `.orig` backup alongside them.

### New: build and packaging infrastructure

| File | What it does |
|------|-------------|
| `Dockerfile` | Build container with all 10 language toolchains, cross-compilers for aarch64, and the `perfarena` Python package. |
| `.dockerignore` | Keeps the container image clean. |
| `pyproject.toml` | Python package definition, dependencies (LangChain, paramiko, psutil, CodeCarbon), and three console-script entry points (`perfarena`, `perfarena-agent`, `perfarena-cc-runner`). |
| `perfarena.mk` | Common Makefile include that all per-benchmark Makefiles now delegate to. Implements `compile`, `run`, `measure`, `validate`, `mem`, `clean` targets, with automatic stdin piping, validation against reference outputs, and platform-aware runner selection (C RAPL runner on Linux, CodeCarbon runner on macOS). |

### New: the `perfarena` Python package

| Module | What it does |
|--------|-------------|
| `cli.py` | Command-line interface: `list-problems`, `list-languages`, `generate`, `exec-check`, `harness-run`, `patch-makefiles`, `static-analyze`, `ingest-measurements`. |
| `config.py` | Loads problem and language definitions from YAML. |
| `harness.py` | Drives `make compile / validate / measure` through one or two executors (local + remote split), with cross-compile env-var injection, automatic artifact staging via SFTP, and `SOURCE=` override for LLM-generated code. |
| `measurement.py` | Parses RAPL/CodeCarbon JSONL traces, joins them with generation metadata, writes measurement rows as JSONL or Parquet. |
| `stats.py` | Harmonic mean, bootstrap 95% CI, Mann-Whitney U, Kendall's tau-b, Holm-Bonferroni correction, refuse-to-rank policy, Break-Even Point formula. |
| `provenance.py` | Captures git SHA, container image tag, and toolchain versions at run time for per-row traceability. |
| `classification.py` | Pairwise "pick the faster implementation" test, scored against measurement ground truth. |
| `perturb.py` | Contamination probe: renames canonical identifiers and rescales inputs to test memorization vs understanding. |
| `static_analysis.py` | Runs per-language linters (pylint, cppcheck, rustc lints, go vet, eslint, tsc) and reports issue density per kLoC. |

| Module (generation) | What it does |
|---------------------|-------------|
| `generation/pipeline.py` | Loads prompt templates from files, calls the LLM via LangChain, extracts code from fenced blocks, writes three files per sample (source, raw response, provenance metadata sidecar). |
| `generation/agent.py` | Isolated subprocess that wraps a single LLM call in the profiler. One-shot and persistent (line-by-line) modes. |
| `generation/profiler.py` | Context manager that records wall time, CPU time, peak RSS, and energy (RAPL on Linux, CodeCarbon on macOS). Fixes the `ru_maxrss` bytes-vs-kilobytes discrepancy on macOS. |
| `generation/llm.py` | LangChain chat-model factory for OpenAI, Anthropic, Google, and Ollama, with `OLLAMA_HOST` env-var support. |

| Module (executors) | What it does |
|--------------------|-------------|
| `executors/local.py` | Runs commands via `subprocess` on the local machine or inside the container. |
| `executors/ssh.py` | Forwards commands to a remote bare-metal host over SSH (paramiko), with SFTP file staging and architecture probing via `uname`. |

| Module (runners) | What it does |
|------------------|-------------|
| `runners/codecarbon_runner.py` | Python-based measurement runner for macOS. Wraps each benchmark iteration in a CodeCarbon tracker, produces the same JSONL schema as the C RAPL runner. |

| Module (tools) | What it does |
|----------------|-------------|
| `tools/patch_makefiles.py` | Rewrites all per-benchmark Makefiles for the 10 target languages to delegate to `perfarena.mk`, with per-language compile commands, cross-compile variables, validation metadata, and stdin-input handling. Idempotent, reversible (writes `.orig` backups). |

### New: prompt templates

| File | What it does |
|------|-------------|
| `prompts/system.txt` | System prompt: "you are an expert programmer, single code block, no commentary." |
| `prompts/user.txt` | User prompt template with placeholders for problem description, input/output spec, invocation hint, algorithm class, and per-language guidance. |
| `prompts/language_hints/*.txt` | One file per target language (10 files) with idiomatic tips, runtime invocation conventions, and common performance traps. |

### New: configuration

| File | What it does |
|------|-------------|
| `configs/problems.yaml` | The 10 CLBG problems with descriptions, default arguments, invocation hints, algorithm-class tags, validation N, reference output paths, stdin-input flags, and binary-output flags. |
| `configs/languages.yaml` | The 10 target languages with folder names, file extensions, and paradigm labels. |

### New: reference data

| Directory | What it contains |
|-----------|-----------------|
| `reference/outputs/` | Known-correct reference outputs for all 10 problems at a small validation N, generated from the original human-written Python implementations. Used by the `make validate` correctness oracle. |
| `reference/inputs/` | Pre-generated stdin input file (`fasta-10000.txt`) used by the three stdin-input problems (k-nucleotide, regex-redux, reverse-complement). |

### New: measurement tool

| File | What it does |
|------|-------------|
| `RAPL/perfarena_runner.c` | Replacement for the original `RAPL/main.c` that adds: periodic RAPL sampling at ~10 Hz via a fork/exec/waitpid loop, idle-baseline capture, configurable warm-up/measurement iteration split, and JSONL output. The original `main.c` is preserved for 2017-replication runs. |

### New: campaign scripts

| File | What it does |
|------|-------------|
| `scripts/run_campaign.sh` | Full-sweep campaign runner: iterates over languages and problems, generates samples, validates each one, and reports pass/fail counts. |
| `scripts/analyze_campaign.py` | Reads all `meta.json` files from a generation run and prints a summary table of inference times, energy, and code sizes per cell. |

### New: documentation

| File | What it covers |
|------|---------------|
| `docs/SYSTEM_OVERVIEW.md` | Plain-language explanation of how the system works and how each research question maps to specific PerfArena features. |
| `docs/LOCAL_DEMO.md` | Step-by-step local demo on macOS using Ollama. |
| `docs/GUIDE.md` | 26-section step-by-step guide covering every operation. |
| `docs/PIPELINE.md` | Sequence diagram and artifact flow table for the full pipeline. |
| `docs/DESIGN_REVIEW.md` | Design trade-offs, implementation status, and known limitations. |
| `docs/PROFILING_AUDIT.md` | Detailed audit of measurement validity and statistical correctness. |

### New: tests

| Directory | What it covers |
|-----------|---------------|
| `perfarena/tests/` | 34 pytest tests covering config loading, code extraction, harness build-env logic, the profiler, the statistics layer, the perturbation generator, and the measurement ingest roundtrip. |

### Modified: existing files

| What changed | Details |
|-------------|---------|
| `RAPL/Makefile` | Added a `perfarena_runner` build target alongside the original `main` target. |
| 101 per-benchmark `Makefile`s | Rewritten by `patch_makefiles.py` to delegate to `perfarena.mk`. Each patched Makefile sets `LANG`, `TEST`, `SOURCE`, `OUTPUT`, `ARG`, `RUN_CMD`, `COMPILE_CMD`, plus validation metadata (`VALIDATION_N`, `REFERENCE_OUTPUT`, `STDIN_FILE`, `BINARY_OUTPUT` where applicable), and includes `../../perfarena.mk`. Originals are preserved as `Makefile.orig`. |

### Not changed

The original `compile_all.py`, `gen-input.sh`, `RAPL/main.c`,
`RAPL/rapl.c`, `RAPL/rapl.h`, all 28 language directories, and
all original benchmark source files are untouched. The `README.md`
(this file) retains the original documentation above; this
changelog is appended below it.

---

### Contacts and References

[Green Software Lab](http://greenlab.di.uminho.pt)

Main contributors: [@Marco Couto](http://github.com/MarcoCouto) and [@Rui Pereira](http://haslab.uminho.pt/ruipereira)


[The Computer Language Benchmark Game](https://benchmarksgame-team.pages.debian.net/benchmarksgame/)

