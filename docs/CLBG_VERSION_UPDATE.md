# CLBG Version Update

This update modernizes the ten-language Computer Language Benchmarks Game
(CLBG) suite and brings all 100 configured language/problem cells to passing
compile, validation, and smoke-measurement status.

## Result

| Check | Result |
|---|---:|
| Languages | 10 |
| Problems per language | 10 |
| Compile and validation | 100/100 passed |
| Energy and memory smoke measurements | 100/100 passed |
| HTML language reports | 10/10 generated |
| Targeted Python tests | 10 passed |
| `git diff --check` | Passed |

Every smoke result contains a successful status, nonzero wall time, an energy
source status, and nonzero process-tree peak RSS. The campaign used zero
warm-ups, one measurement iteration, and zero idle delay; it verifies operation
but is not intended for performance ranking.

## Toolchain updates

- Installed and verified Rust 1.97.1 with Cargo 1.97.1.
- Installed and verified .NET SDK 10.0.302.
- Retargeted the old C# projects from `netcoreapp1.1` to `net10.0`.
- Pinned TypeScript to 5.9.3 and updated its Node/CommonJS build rules.
- Verified the suite with Node.js 26.5.0, Go 1.26.4, PHP 8.5.7, Apple clang
  17.0.0, Java 17.0.18, Python 3.14.6, and Ruby 2.6.10 on macOS arm64.
- Added a shared Cargo package and lockfile for the ten Rust binaries.

## Language repairs

### C++

- Replaced APR, GMP, Boost.Regex binary, OpenMP, and x86-specific assumptions
  with portable C++17 or header-only implementations.
- Added portable implementations for binary trees, Mandelbrot, n-body,
  reverse complement, and spectral norm.
- Reworked k-nucleotide around `std::unordered_map`, pidigits around
  header-only multiprecision, and regex-redux around `std::regex`.

### C#

- Updated all project targets for the current .NET SDK.
- Replaced the GMP-based pidigits implementation with `BigInteger`.
- Corrected Mandelbrot output and validation behavior.

### Go

- Replaced GMP pidigits logic with `math/big`.
- Replaced the external PCRE path with the standard `regexp` package.
- Corrected Mandelbrot PBM bytes.

### JavaScript and TypeScript

- Repaired Mandelbrot for small validation inputs and current Node behavior.
- Updated TypeScript compilation for 5.9.3.
- Reworked TypeScript reverse complement for safe typed whole-input handling.
- Corrected TypeScript spectral-norm loop bounds.

### PHP

- Corrected k-nucleotide window bounds and frequency denominators.
- Fixed reverse-complement end-of-file handling.
- Corrected validation metadata for binary Mandelbrot output.

### Ruby

- Replaced Linux-only processor detection with `Etc.nprocessors`.
- Fixed small-input worker assumptions, k-nucleotide formatting, pidigits, and
  Mandelbrot output for the installed Ruby runtime.

### Rust

- Moved all cells to current Cargo builds.
- Removed obsolete Mandelbrot APIs.
- Replaced the GMP pidigits dependency with `num-bigint`.
- Corrected missing k-nucleotide lookup output.

### Python and Java

- Corrected validation-size arguments and output differences discovered by the
  full cross-language audit.
- Updated Java implementations where current runtime behavior exposed parsing
  or output defects.

## Makefile and validation changes

- Corrected the default argument in every configured Makefile from the central
  problem configuration.
- Standardized all cells on the shared `perfarena.mk` compile, run, validate,
  measure, memory, and clean rules.
- Made validation output cell-local so concurrent validations cannot overwrite
  one another.
- Updated `patch_makefiles.py` so regenerated Makefiles retain the portable C++,
  Rust Cargo, current TypeScript, validation argument, and Mandelbrot reference
  decisions.
- Preserved a shared canonical output per problem. Mandelbrot has documented
  language-specific PBM references only where floating-point operation order
  changes boundary pixels while preserving the same CLBG contract.

## Energy and memory reporting

- Added process-tree `peak_rss_kb` to the same measurement row as wall time and
  energy.
- Changed the macOS runner to `exec` the benchmark and sample RSS every 1 ms so
  short native programs still produce a nonzero memory observation.
- Propagated `energy_source_status` into the generated machine-readable JSON.
- Added peak-RSS and energy-source columns to every HTML language report.

## Generated artifacts

- HTML index: `perfarena_out/clbg_quick/index.html`
- Per-language reports: `perfarena_out/clbg_quick/*_report.html`
- Machine-readable results: `perfarena_out/clbg_quick/*_results.json`
- Detailed repair record: `docs/CLBG_10_LANGUAGE_REPAIR_LOG.md`
- Full smoke summary: `docs/CLBG_10_LANGUAGE_QUICK_RUN_SUMMARY.md`

## Verification performed

Each repaired cell was checked with:

```sh
make clean compile validate
```

The final smoke campaign used:

```sh
make measure ARG=<validation-size> \
  PERFARENA_WARMUP=0 \
  PERFARENA_MEASURE=1 \
  PERFARENA_IDLE_S=0
```

The final audit also checked all 100 Makefiles for the shared include,
validation metadata, configured argument, and absence of placeholder targets.
Measurement ingestion, profiler behavior, configuration loading, all generated
JSON rows, report columns, index links, and whitespace integrity were checked.

## Limitations

- One measurement per cell is a smoke test, not a statistically meaningful
  benchmark campaign.
- CodeCarbon energy on macOS is an estimate and can include unrelated system
  activity, especially when smoke runs overlap.
- Use isolated repeated measurements for language performance comparisons.
