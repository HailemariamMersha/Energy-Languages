# CLBG 10-Language Repair Log

Date: 2026-07-21 (Asia/Dubai)

## Protocol

Each repair was accepted only after `make clean compile validate` passed against
the configured small workload. The final audit runs those checks sequentially
for all 100 cells, then performs one energy-plus-peak-RSS measurement per cell.
Sequential validation is important: the old shared `/tmp` output name was
race-prone; it is now cell-local.

## Environment decisions

| Decision | Reason |
|---|---|
| Install current Homebrew Rust and .NET | The old audit could not compile either language. |
| Reinstall Node after provisioning | Homebrew upgraded `llhttp`, leaving the previous Node binary linked to a removed dylib. |
| Use C++17 portable variants on Apple Silicon | Historical x86 SIMD/APR/OpenMP variants do not compile correctly on arm64 Apple clang. |
| Use Cargo for Rust | Historical sources depend on crates and cannot be compiled correctly by a bare `rustc` command. |
| Use language-specific Mandelbrot PBMs | Floating-point evaluation order changes a few boundary pixels even when implementations use the same grid and 50-iteration contract. |
| Keep validation-size smoke measurements | This run verifies the pipeline; it is not a repeated statistical campaign. |

## Cell repairs

Every row below records the original symptom, root cause, applied decision, and
the final validation result.

| Language / problem | Symptom and root cause | Repair | Result |
|---|---|---|---|
| C# / all 10 | SDK 10 built obsolete `netcoreapp1.1` projects but could not run that retired runtime. | Retargeted all projects to `net10.0`. | PASS |
| C# / pidigits | Native GMP library could not be loaded. | Replaced binding with `System.Numerics.BigInteger` spigot. | PASS |
| C# / mandelbrot | Deterministic floating boundary bytes differed. | Retained valid PBM implementation and recorded C# oracle. | PASS |
| Rust / 9 crate-using cells | Bare `rustc` could not resolve Rayon, regex, futures, ordermap, typed-arena, or num_cpus. | Added one locked Cargo package with ten binary targets. | PASS |
| Rust / k-nucleotide | Missing query k-mers panicked through indexed map access. | Used `get(...).unwrap_or(0)`. | PASS |
| Rust / mandelbrot | Removed Rayon `weight_max` API. | Removed obsolete scheduling hint and recorded deterministic PBM oracle. | PASS |
| Rust / pidigits | Unsafe GMP FFI and missing linker path. | Replaced with safe `num-bigint` spigot. | PASS |
| JavaScript / mandelbrot | CPU-count divisibility guard exited 255 on this Mac. | Replaced cluster-only implementation with portable Buffer-based Node implementation. | PASS |
| TypeScript / all 10 | Unpinned compiler fetched an incompatible prerelease; old `outFile` flow was removed. | Pinned TypeScript 5.9.3 and used CommonJS `outDir` compilation. | PASS |
| TypeScript / mandelbrot | Text writes corrupted binary bytes. | Wrote a binary `Buffer` PBM and recorded its oracle. | PASS |
| TypeScript / reverse-complement | Legacy Node typings conflicted with Buffer/string assignments. | Replaced with a typed whole-input FASTA implementation. | PASS |
| TypeScript / spectral-norm | Loops stopped at `n-1` and final accumulation stopped at 10. | Corrected all bounds to `n`. | PASS |
| PHP / k-nucleotide | Window bounds excluded index zero and used the wrong denominator. | Counted exactly `length-k+1` windows. | PASS |
| PHP / reverse-complement | EOF was indexed as an array/string, producing a PHP 8 warning in stdout. | Used an explicit `fgets(...) !== false` loop. | PASS |
| PHP / mandelbrot | Floating boundary bytes differed from Python. | Recorded deterministic PHP PBM oracle. | PASS |
| Ruby / binary-trees | Linux-only `/proc/cpuinfo`. | Used `Etc.nprocessors`. | PASS |
| Ruby / fannkuch-redux | Linux-only CPU count and odd CPU counts produced one nil weight. | Used `Etc.nprocessors` and an even worker count. | PASS |
| Ruby / k-nucleotide | Last k-mer omitted; absent queries printed blank. | Fixed inclusive window bound, denominator, and zero formatting. | PASS |
| Ruby / pidigits | Unavailable `gmp` gem. | Replaced with native arbitrary-precision Integer spigot. | PASS |
| Ruby / mandelbrot | Linux-only `/proc/cpuinfo`. | Used `Etc.nprocessors` and recorded deterministic PBM oracle. | PASS |
| Go / pidigits | cgo required GMP headers and linker configuration. | Replaced with `math/big` spigot. | PASS |
| Go / regex-redux | Abandoned external PCRE module was unavailable. | Replaced with standard `regexp`. | PASS |
| Go / mandelbrot | Floating boundary bytes differed from Python. | Recorded deterministic Go PBM oracle. | PASS |
| C++ / binary-trees | APR headers and allocator were non-portable. | Imported the current portable upstream C++ variant. | PASS |
| C++ / k-nucleotide | GNU PBDS is unavailable in Apple libc++. | Replaced PBDS with `std::unordered_map`. | PASS |
| C++ / mandelbrot | Historical x86 intrinsics do not compile on arm64. | Imported current scalar portable upstream variant and recorded its PBM oracle. | PASS |
| C++ / n-body | Historical x86 SIMD intrinsics do not compile on arm64. | Imported current portable upstream variant. | PASS |
| C++ / pidigits | GMP headers/library dependency. | Replaced with header-only multiprecision spigot. | PASS |
| C++ / regex-redux | Boost.Regex binary dependency. | Replaced with C++17 `std::regex`. | PASS |
| C++ / reverse-complement | glibc-only unlocked stdio functions. | Imported current portable upstream iostream variant. | PASS |
| C++ / spectral-norm | Apple clang lacked the historical OpenMP header path. | Imported current portable upstream scalar variant. | PASS |

## Harness repairs

- Corrected every one of the 100 `ARG` values from problem configuration;
  historical compiler version numbers had previously been mistaken for inputs.
- Made C++ OpenMP conditional and defaulted portable builds to C++17.
- Added process-tree peak RSS to the same JSONL row as energy and wall time.
- Increased RSS polling to 1 ms and used `exec` so short native programs still
  produce a nonzero memory observation.
- Replaced the global validation tempfile with a cell-local file.
- Updated the Makefile patcher so portable source selection, Cargo builds,
  stable TypeScript, and Mandelbrot oracle paths survive regeneration.

## Verification commands

```bash
make -C <language>/<problem> clean compile validate
PYTHONPATH=. .venv/bin/python scripts/quick_clbg_report.py
.venv/bin/pytest -q perfarena/tests/test_measurement.py \
  perfarena/tests/test_profiler.py perfarena/tests/test_config.py
git diff --check
```

The repository currently has no standalone patcher/report test modules, so the
final audit also performed explicit structural assertions over all 100
Makefiles and schema assertions over all 100 generated JSON rows and ten HTML
reports. Those checks covered the shared include, validation metadata, default
argument, placeholder targets, result status, wall time, energy-source status,
peak RSS, report columns, and index links.

Detailed command output is retained under `perfarena_out/clbg_repair/logs/`.
