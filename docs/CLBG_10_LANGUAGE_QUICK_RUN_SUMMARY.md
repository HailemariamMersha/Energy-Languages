# CLBG 10-Language Final Repair Summary

Date: 2026-07-21 (Asia/Dubai)

## Outcome

All ten configured languages now compile, validate, and complete one
validation-size energy-plus-memory measurement for all ten CLBG problems.

| Language | Compile + validation | Energy rows | Nonzero peak RSS rows |
|---|---:|---:|---:|
| Python | 10/10 | 10/10 | 10/10 |
| JavaScript | 10/10 | 10/10 | 10/10 |
| TypeScript | 10/10 | 10/10 | 10/10 |
| Java | 10/10 | 10/10 | 10/10 |
| C# | 10/10 | 10/10 | 10/10 |
| C++ | 10/10 | 10/10 | 10/10 |
| PHP | 10/10 | 10/10 | 10/10 |
| Go | 10/10 | 10/10 | 10/10 |
| Rust | 10/10 | 10/10 | 10/10 |
| Ruby | 10/10 | 10/10 | 10/10 |
| **Total** | **100/100** | **100/100** | **100/100** |

## Measurement protocol

For every cell the final smoke runner performed:

```text
make clean compile validate
make measure ARG=<validation-size> \
  PERFARENA_WARMUP=0 PERFARENA_MEASURE=1 PERFARENA_IDLE_S=0
```

Each successful JSONL row contains wall time, the CodeCarbon energy estimate,
energy-source metadata, and process-tree `peak_rss_kb`. This verifies execution
and reporting only; the default repeated campaign remains 10 warm-ups and 20
measurements.

## Installed and verified toolchains

| Toolchain | Version |
|---|---|
| Python | 3.14.6 |
| Node.js | 26.5.0 |
| TypeScript | 5.9.3 |
| Java compiler | 17.0.18 |
| .NET SDK | 10.0.302 |
| Apple clang | 17.0.0 |
| PHP | 8.5.7 |
| Go | 1.26.4 darwin/arm64 |
| Rust / Cargo | 1.97.1 |
| Ruby | 2.6.10 |

Homebrew installation upgraded shared dependencies and temporarily broke the
old Node binary's `llhttp` link. Node was reinstalled and every JavaScript and
TypeScript cell was revalidated afterward.

## Main decisions and changes

- Retargeted C# projects from retired `netcoreapp1.1` to `net10.0`.
- Added a shared locked Cargo package for all Rust binaries.
- Replaced missing GMP/PCRE paths with managed or standard alternatives in C#,
  C++, Go, and Rust.
- Replaced x86/APR/OpenMP-specific C++ variants with current portable C++17
  sources on Apple Silicon.
- Corrected modern Node, TypeScript, PHP, and Ruby compatibility defects.
- Corrected all 100 Makefile default arguments from the YAML configuration.
- Made validation temporary output cell-local and therefore concurrency-safe.
- Kept per-language deterministic Mandelbrot PBMs because floating-point
  operation order changes a few boundary pixels across implementations.
- Sampled RSS every 1 ms and used `exec` for the benchmark child so short native
  validation runs still receive meaningful nonzero memory observations.

The per-cell symptom, cause, repair, and validation outcome are recorded in
`docs/CLBG_10_LANGUAGE_REPAIR_LOG.md`.

## Generated reports

Open `perfarena_out/clbg_quick/index.html`. It links to ten self-contained HTML
reports, each showing 10/10 success with wall time, energy, and peak RSS. The
adjacent JSON files retain metrics and command logs for every problem.

## Interpretation limits

- These are single smoke samples, not ranking-quality measurements.
- CodeCarbon values on this Mac are estimates and parallel smoke collection can
  include system activity. Use the normal isolated repeated campaign for
  comparisons.
- Mandelbrot oracles are language-specific only for floating boundary pixels;
  dimensions, PBM layout, coordinate grid, and iteration contract remain CLBG
  compatible.
