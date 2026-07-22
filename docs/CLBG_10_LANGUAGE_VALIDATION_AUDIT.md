# CLBG 10-Language Validation Audit

This audit checks the CLBG implementations for the ten target languages used by
the Energy-Languages work:

```text
Python, Go, JavaScript, TypeScript, Java, CSharp, C++, PHP, Rust, Ruby
```

The common CLBG problem set is:

```text
binary-trees
fannkuch-redux
fasta
k-nucleotide
mandelbrot
n-body
pidigits
regex-redux
reverse-complement
spectral-norm
```

## Upstream Reference

The current upstream source of truth checked for this audit is The Computer
Language Benchmarks Game:

```text
https://benchmarksgame-team.pages.debian.net/benchmarksgame/
https://salsa.debian.org/benchmarksgame-team/benchmarksgame
```

The upstream source bundle used for comparison was:

```text
public/download/benchmarksgame-sourcecode.zip
```

Generated comparison output:

```text
perfarena_out/clbg_validation_audit/upstream_source_match.csv
```

Important result:

- Upstream has candidate source files for 99 of the 100 target
  language/problem cells.
- TypeScript `pidigits` has no current upstream TypeScript candidate in the
  source bundle.
- None of the active local source files are byte-identical to the current
  upstream bundle. This repo contains local file names, Makefile wrappers,
  generated execution targets, validation-size changes, and macOS fixes, so a
  blind overwrite from upstream would not be safe.

## Local Toolchain Status

Validated on the current macOS development machine:

| Language | Toolchain status |
|---|---|
| Python | Available |
| Go | Available |
| JavaScript | Available through `node` |
| Java | Available through `javac` / `java` |
| C++ | Available, but Apple clang rejects the current `-fopenmp` flags |
| PHP | Available |
| Ruby | Available |
| TypeScript | Blocked: `tsc` not installed |
| CSharp | Blocked: `dotnet` not installed |
| Rust | Blocked: `rustc` / `cargo` not installed |

## Current Validation Result

The available-language validation audit was run with:

```bash
make clean
make validate
```

Generated outputs:

```text
perfarena_out/clbg_validation_audit/validation_audit_available_languages.jsonl
perfarena_out/clbg_validation_audit/validation_audit_summary.csv
perfarena_out/clbg_validation_audit/logs/
```

| Language | Result |
|---|---:|
| Python | 10 / 10 pass |
| Java | 10 / 10 pass |
| Go | 7 / 10 pass |
| JavaScript | 8 / 10 pass |
| PHP | 6 / 10 pass |
| Ruby | 5 / 10 pass |
| C++ | 0 / 10 pass locally because OpenMP compile flags fail |
| TypeScript | Not run; missing `tsc` |
| CSharp | Not run; missing `dotnet` |
| Rust | Not run; missing `rustc` / `cargo` |

## Fixes Already Applied

Python and Java are currently the only target languages validated end to end for
all ten CLBG problems.

The detailed fixes are documented in:

```text
docs/CLBG_PYTHON_JAVA_RUN_NOTES.md
```

Summary:

- Python `k-nucleotide`: fixed multiprocessing state handling and replaced a
  traceback reference output with the real expected output.
- Python `pidigits`: fixed `gmpy2` integer division and aligned validation with
  the 28-digit reference output.
- Java `fannkuch-redux` and `k-nucleotide`: removed self-copy compile failures.
- Java `k-nucleotide`: replaced a missing `fastutil` dependency with a small
  local map implementation.
- Java `fasta` and `mandelbrot`: added small-validation paths while preserving
  full-size benchmark paths.
- Java `pidigits`: replaced unavailable native GMP bindings with
  `java.math.BigInteger` and aligned validation with the 28-digit reference.

## Remaining Blockers

### Go

Passing:

```text
binary-trees, fannkuch-redux, fasta, k-nucleotide, n-body,
reverse-complement, spectral-norm
```

Failing:

| Problem | Cause |
|---|---|
| `mandelbrot` | Output differs from the shared PBM reference at validation size. |
| `pidigits` | Compile fails because `gmp.h` is not installed. |
| `regex-redux` | Compile fails because the `github.com/glenn-brown/golang-pkg-pcre/src/pkg/pcre` dependency is missing. |

### JavaScript

Passing:

```text
binary-trees, fannkuch-redux, fasta, k-nucleotide, n-body,
regex-redux, reverse-complement, spectral-norm
```

Failing:

| Problem | Cause |
|---|---|
| `mandelbrot` | Validation exits non-zero at the small PBM reference size. |
| `pidigits` | Makefile is an old stub and does not include the shared `perfarena.mk` targets. Upstream also has no current Node `pidigits` candidate in the source bundle. |

### PHP

Passing:

```text
binary-trees, fannkuch-redux, fasta, n-body, regex-redux, spectral-norm
```

Failing:

| Problem | Cause |
|---|---|
| `k-nucleotide` | Output differs from the corrected shared `k-nucleotide` reference. |
| `mandelbrot` | Output differs from the shared PBM reference at validation size. |
| `pidigits` | Makefile validates at `N=27`, while the shared reference contains 28 digits. |
| `reverse-complement` | Output differs from the shared reference input/output pair. |

### Ruby

Passing:

```text
fasta, n-body, regex-redux, reverse-complement, spectral-norm
```

Failing:

| Problem | Cause |
|---|---|
| `binary-trees` | Validation exits non-zero at the small reference size. |
| `fannkuch-redux` | Validation exits non-zero at the small reference size. |
| `k-nucleotide` | Output differs from the corrected shared `k-nucleotide` reference. |
| `mandelbrot` | Validation exits non-zero at the small PBM reference size. |
| `pidigits` | Makefile validates at `N=27`, while the shared reference contains 28 digits. |

### C++

All ten C++ targets fail locally before validation because the Makefiles compile
with:

```text
-fopenmp
```

The local `c++` is Apple clang, which rejects that flag. The implementation
files may still be valid CLBG sources, but they cannot be validated on this
machine until one of these is done:

- install a compiler/OpenMP setup that supports the existing flags, or
- add a macOS-specific compile path, or
- choose non-OpenMP upstream variants for the local macOS validation path.

### TypeScript, CSharp, Rust

These languages were not run because required toolchains are missing:

```text
TypeScript: tsc
CSharp: dotnet
Rust: rustc / cargo
```

The first step is toolchain installation, then the same `make clean &&
make validate` audit should be run.

## Recommended Path To "Latest Valid" For All Ten Languages

1. Keep the validated Python and Java fixes.
2. Install missing toolchains for TypeScript, CSharp, and Rust.
3. Fix low-risk validation mismatches first:
   - PHP `pidigits`: align `VALIDATION_N` with the 28-digit reference.
   - Ruby `pidigits`: align `VALIDATION_N` with the 28-digit reference.
   - JavaScript `pidigits`: either remove it from the ten-language CLBG scope or
     replace the stub with a deliberate local implementation, because current
     upstream does not provide a Node candidate.
4. Decide how to handle language-specific binary/text reference differences for
   `mandelbrot`, `k-nucleotide`, and `reverse-complement`.
5. Decide the C++ OpenMP strategy for macOS before measuring C++.
6. Only after local validation is green, selectively update implementation
   files from the current upstream source bundle. Do this per problem/language
   cell, not by bulk overwrite, because local Makefiles and validation fixes are
   part of the measurement harness.

## Current Bottom Line

The ten-language CLBG tree is not yet fully "latest valid".

Validated and measured now:

```text
Python: 10 / 10
Java:   10 / 10
```

Partially valid now:

```text
Go:         7 / 10
JavaScript: 8 / 10
PHP:        6 / 10
Ruby:       5 / 10
```

Blocked by local toolchain/compiler setup:

```text
C++:        OpenMP compile flags fail with Apple clang
TypeScript: tsc missing
CSharp:     dotnet missing
Rust:       rustc/cargo missing
```
