"""CodeCarbon-based measurement runner for macOS (and other non-RAPL platforms).

A Python-based replacement for ``RAPL/perfarena_runner`` that uses
CodeCarbon for energy estimation instead of direct MSR reads. On
Apple Silicon, CodeCarbon calls ``powermetrics`` under the hood
(requires sudo for real power data; falls back to TDP estimation
without it). On Intel Macs it uses Intel Power Gadget.

The output is the same JSONL schema that ``perfarena_runner.c``
produces, so ``measurement.py`` can ingest it without changes.

Usage:

    python -m perfarena.runners.codecarbon_runner \\
        "python3 binarytrees.py 21" Python binary-trees \\
        [warmup=10] [measure=20] [idle_s=5]

Or via the installed entry point:

    perfarena-cc-runner "python3 binarytrees.py 21" Python binary-trees
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from codecarbon import EmissionsTracker
except ImportError:
    EmissionsTracker = None  # type: ignore[assignment,misc]

DEFAULT_WARMUP = 10
DEFAULT_MEASURE = 20
DEFAULT_IDLE_S = 5


def _kwh_to_uj(kwh: float) -> int:
    """Convert kilowatt-hours to microjoules."""
    return int(kwh * 3_600_000_000_000)


def _write_row(
    out: Any,
    test: str,
    language: str,
    iteration: int,
    phase: str,
    wall_ms: float,
    energy_uj: int,
    energy_source: str,
    samples: int,
    exit_code: int,
    extra: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {
        "schema_version": 1,
        "test": test,
        "language": language,
        "iteration": iteration,
        "phase": phase,
        "wall_ms": round(wall_ms, 3),
        "rapl_pkg_start_raw": 0,
        "rapl_pkg_end_raw": 0,
        "rapl_pkg_delta_raw": energy_uj,
        "energy_source": energy_source,
        "samples": samples,
        "exit_code": exit_code,
    }
    if extra:
        row["extra"] = extra
    out.write(json.dumps(row) + "\n")
    out.flush()


def _run_child(command: str, timeout: float = 600.0) -> tuple[int, float]:
    """Run a shell command and return (exit_code, wall_ms)."""
    t0 = time.monotonic()
    proc = subprocess.run(
        ["sh", "-c", command],
        capture_output=True,
        timeout=timeout,
    )
    wall = (time.monotonic() - t0) * 1000.0
    return proc.returncode, wall


def _measure_with_codecarbon(
    command: str,
    timeout: float = 600.0,
) -> tuple[int, float, int, str, dict[str, Any]]:
    """Run a command under CodeCarbon tracking.

    Returns (exit_code, wall_ms, energy_uj, energy_source, extra).
    """
    extra: dict[str, Any] = {}
    if EmissionsTracker is None:
        # No CodeCarbon installed; fall back to wall-time only.
        exit_code, wall_ms = _run_child(command, timeout)
        return exit_code, wall_ms, 0, "none", {"note": "codecarbon not installed"}

    tracker = EmissionsTracker(
        project_name="perfarena-measure",
        log_level="error",
        save_to_file=False,
        save_to_api=False,
        save_to_logger=False,
    )

    tracker.start()
    exit_code, wall_ms = _run_child(command, timeout)
    try:
        tracker.stop()
    except Exception as exc:  # noqa: BLE001
        return exit_code, wall_ms, 0, "codecarbon-error", {"error": str(exc)}

    data = tracker.final_emissions_data
    if data is None or data.energy_consumed is None:
        return exit_code, wall_ms, 0, "codecarbon-no-data", {}

    energy_uj = _kwh_to_uj(data.energy_consumed)
    extra = {
        "cpu_energy_kwh": data.cpu_energy,
        "gpu_energy_kwh": data.gpu_energy,
        "ram_energy_kwh": data.ram_energy,
        "total_energy_kwh": data.energy_consumed,
        "emissions_kg_co2": data.emissions,
        "duration_s": data.duration,
    }
    return exit_code, wall_ms, energy_uj, "codecarbon", extra


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 3:
        print(
            f"usage: {sys.argv[0]} \"<command>\" <language> <test> "
            f"[warmup={DEFAULT_WARMUP}] [measure={DEFAULT_MEASURE}] "
            f"[idle_s={DEFAULT_IDLE_S}]",
            file=sys.stderr,
        )
        return 2

    command = args[0]
    language = args[1]
    test = args[2]
    warmup = int(args[3]) if len(args) > 3 else DEFAULT_WARMUP
    measure = int(args[4]) if len(args) > 4 else DEFAULT_MEASURE
    idle_s = int(args[5]) if len(args) > 5 else DEFAULT_IDLE_S

    out_path = Path(f"../{language}.jsonl")
    out = out_path.open("a")

    # --- Idle baseline ---
    print(f"[codecarbon-runner] idle baseline ({idle_s}s)...", file=sys.stderr)
    idle_tracker = None
    if EmissionsTracker is not None:
        try:
            idle_tracker = EmissionsTracker(
                project_name="perfarena-idle",
                log_level="error",
                save_to_file=False,
                save_to_api=False,
                save_to_logger=False,
            )
            idle_tracker.start()
        except Exception:  # noqa: BLE001
            idle_tracker = None

    t0 = time.monotonic()
    time.sleep(idle_s)
    idle_wall = (time.monotonic() - t0) * 1000.0

    idle_energy_uj = 0
    idle_source = "none"
    if idle_tracker is not None:
        try:
            idle_tracker.stop()
            d = idle_tracker.final_emissions_data
            if d is not None and d.energy_consumed is not None:
                idle_energy_uj = _kwh_to_uj(d.energy_consumed)
                idle_source = "codecarbon"
        except Exception:  # noqa: BLE001
            pass

    _write_row(
        out, test, language, 0, "idle",
        idle_wall, idle_energy_uj, idle_source, 0, 0,
    )

    # --- Warm-up + measurement ---
    total = warmup + measure
    for i in range(total):
        phase = "warmup" if i < warmup else "measure"
        print(
            f"[codecarbon-runner] {phase} {i + 1}/{total}...",
            file=sys.stderr,
        )
        exit_code, wall_ms, energy_uj, source, extra = _measure_with_codecarbon(command)
        _write_row(
            out, test, language, i + 1, phase,
            wall_ms, energy_uj, source, 0, exit_code, extra,
        )

    out.close()
    print(f"[codecarbon-runner] done. wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
