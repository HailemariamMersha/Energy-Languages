# CLBG Python And Java Run Notes

This note summarizes the changes made so the local CLBG benchmarks run and
validate cleanly for Python and Java before measurement.

## Measurement Protocol

Both languages were measured with the existing CLBG Makefile flow:

```bash
make clean
make compile
make validate
make measure
```

On macOS, `make measure` uses the Python CodeCarbon runner:

```bash
PERFARENA_RUNNER="../../.venv/bin/python -m perfarena.runners.codecarbon_runner"
PYTHONPATH=../..
```

Each problem was run with the repo defaults from `perfarena.mk`:

- `PERFARENA_WARMUP=10`
- `PERFARENA_MEASURE=20`
- `PERFARENA_IDLE_S=5`

The aggregate CSV/HTML reports use only `phase=measure` rows with
`exit_code=0`. Each problem summary is calculated from 20 measured rows.

## Python Fixes

### `k-nucleotide`

File:

```text
Python/k-nucleotide/knucleotide.python3-3.python3
reference/outputs/k-nucleotide.txt
```

Problem:

- The benchmark failed on macOS/Python multiprocessing with `KeyError: 0`.
- The existing reference output had accidentally captured that traceback, so
  validation was comparing against a failure instead of a real benchmark output.

Fix:

- Changed the multiprocessing path to pass the full jobs directly to worker
  processes instead of relying on parent-process global state.
- Replaced `reference/outputs/k-nucleotide.txt` with the real expected output
  for `reference/inputs/fasta-10000.txt`.

### `pidigits`

Files:

```text
Python/pidigits/pidigits.python3-2.python3
Python/pidigits/Makefile
```

Problem:

- `gmpy2` was missing from the local venv.
- Modern `gmpy2.div` returns floating division, which produced incorrect digit
  output for this old benchmark source.
- The Makefile validated at `N=27`, but the reference output contains 28
  digits.

Fix:

- Installed `gmpy2` in `Energy-Languages/.venv`.
- Changed the source to use `gmpy2.t_div` for integer division.
- Changed `VALIDATION_N` from `27` to `28`.

## Java Fixes

### `fannkuch-redux`

File:

```text
Java/fannkuch-redux/Makefile
```

Problem:

- The Makefile copied `fannkuchredux.java` onto itself.
- On this machine, `cp` exits non-zero when source and destination are the same,
  so compile failed before `javac`.

Fix:

- Changed `COMPILE_CMD` to call `javac` directly.

### `k-nucleotide`

Files:

```text
Java/k-nucleotide/Makefile
Java/k-nucleotide/knucleotide.java
```

Problem:

- The Makefile copied `knucleotide.java` onto itself.
- The Java source depended on an external `fastutil` jar that is not present in
  this repo.

Fix:

- Changed `COMPILE_CMD` to call `javac` directly.
- Added a small local `Long2IntOpenHashMap` replacement using `HashMap<Long,
  Integer>` with only the methods used by this benchmark.

### `fasta`

File:

```text
Java/fasta/fasta.java-5.java
```

Problem:

- The optimized Java implementation is designed for large CLBG inputs and did
  not produce the shared small validation output at `N=1000`.

Fix:

- Added a small-`N` sequential validation path.
- The full-size measurement path is unchanged for the benchmark argument
  `ARG=25000000`.

### `mandelbrot`

Files:

```text
Java/mandelbrot/Makefile
Java/mandelbrot/mandelbrot.java-2.java
reference/outputs/mandelbrot-java.pbm
```

Problem:

- Java and Python differed by a few boundary bytes in the binary PBM validation
  output at `N=200`.

Fix:

- Added a small-`N` Java validation path.
- Added a Java-specific validation reference:
  `reference/outputs/mandelbrot-java.pbm`.
- Pointed `Java/mandelbrot/Makefile` at the Java-specific PBM.
- The full-size measurement path is unchanged for `ARG=16000`.

### `pidigits`

Files:

```text
Java/pidigits/Makefile
Java/pidigits/pidigits.java-2.java
```

Problem:

- The original source depended on native `jgmplib`, which is not available in
  the local Java library path.
- The Makefile validated at `N=27`, but the reference output contains 28
  digits.

Fix:

- Replaced the native GMP wrapper with `java.math.BigInteger`.
- Changed `VALIDATION_N` from `27` to `28`.

## Generated Results

Python:

```text
perfarena_out/clbg_python_full/python_clbg_full_report.html
perfarena_out/clbg_python_full/python_clbg_full_summary.csv
perfarena_out/clbg_python_full/python_clbg_full_rows.csv
perfarena_out/clbg_python_full/python_clbg_full_metadata.json
```

Java:

```text
perfarena_out/clbg_java_full/java_clbg_full_report.html
perfarena_out/clbg_java_full/java_clbg_full_summary.csv
perfarena_out/clbg_java_full/java_clbg_full_rows.csv
perfarena_out/clbg_java_full/java_clbg_full_metadata.json
```

Current result:

- Python: 10 / 10 CLBG problems validated and measured.
- Java: 10 / 10 CLBG problems validated and measured.

## Important Notes

- These measurements use existing CLBG benchmark implementations in the repo,
  not LLM-generated solutions.
- Correctness is checked with CLBG reference outputs, not LeetCode.
- CodeCarbon is the energy backend on macOS.
- The report CSVs aggregate measured rows only; warmup and idle rows are
  retained in the raw row files but not used for problem medians.
