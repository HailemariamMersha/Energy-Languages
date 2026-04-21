"""Profiler for LLM inference calls.

A small context manager that records wall time, CPU time, peak RSS,
and package energy around a block of Python code. Used by the
PerfArena generation agent to measure the cost of a single LLM call.

Energy backends (tried in order):

1. **RAPL** via ``/sys/class/powercap`` on Linux x86. Direct
   hardware counter, most accurate.
2. **CodeCarbon** on any platform where it is installed. On macOS
   with Apple Silicon this uses ``powermetrics`` (needs sudo for
   real data, falls back to TDP estimation otherwise). On Linux it
   reads RAPL internally. On Intel Macs it uses Intel Power Gadget.
3. **None.** If neither is available, energy fields are ``null``
   and ``energy_source`` is ``"none"``.

Install CodeCarbon for macOS support:

    pip install 'perfarena[codecarbon]'
"""
from __future__ import annotations

import os
import platform
import resource
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import psutil  # type: ignore

    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover
    _HAS_PSUTIL = False

try:
    from codecarbon import EmissionsTracker as _CCTracker  # type: ignore

    _HAS_CODECARBON = True
except ImportError:  # pragma: no cover
    _HAS_CODECARBON = False


# Linux Intel RAPL package energy counter. Unavailable on macOS, on
# ARM Linux without intel_rapl_common, and inside unprivileged
# containers that don't mount /sys/class/powercap.
RAPL_ENERGY_UJ_PATH = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
RAPL_MAX_UJ_PATH = "/sys/class/powercap/intel-rapl/intel-rapl:0/max_energy_range_uj"


def _read_int_file(path: str) -> Optional[int]:
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def rapl_available() -> bool:
    return _read_int_file(RAPL_ENERGY_UJ_PATH) is not None


def codecarbon_available() -> bool:
    return _HAS_CODECARBON


def _best_energy_backend() -> str:
    """Pick the best available energy backend for this platform."""
    if rapl_available():
        return "rapl"
    if _HAS_CODECARBON:
        return "codecarbon"
    return "none"


def host_fingerprint() -> dict[str, Any]:
    """Return a minimal machine fingerprint for provenance."""
    info: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": os.uname().sysname if hasattr(os, "uname") else "",
        "release": os.uname().release if hasattr(os, "uname") else "",
        "machine": os.uname().machine if hasattr(os, "uname") else "",
        "cpu_count": os.cpu_count(),
        "rapl_available": rapl_available(),
        "codecarbon_available": codecarbon_available(),
        "energy_backend": _best_energy_backend(),
    }
    if _HAS_PSUTIL:
        try:
            info["total_memory_bytes"] = psutil.virtual_memory().total
        except Exception:  # pragma: no cover
            pass
    return info


@dataclass
class ProfileMetrics:
    wall_time_s: float = 0.0
    cpu_time_s: float = 0.0
    peak_rss_kb: int = 0
    rss_delta_kb: int = 0
    energy_uj: Optional[int] = None
    energy_source: str = "none"
    target_pid: Optional[int] = None
    target_cpu_delta_s: Optional[float] = None
    target_rss_kb_end: Optional[int] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_time_s": self.wall_time_s,
            "cpu_time_s": self.cpu_time_s,
            "peak_rss_kb": self.peak_rss_kb,
            "rss_delta_kb": self.rss_delta_kb,
            "energy_uj": self.energy_uj,
            "energy_source": self.energy_source,
            "target_pid": self.target_pid,
            "target_cpu_delta_s": self.target_cpu_delta_s,
            "target_rss_kb_end": self.target_rss_kb_end,
            "notes": list(self.notes),
        }


class Profiler:
    """Context manager that measures a block of Python code.

    Captures:
      * wall_time_s        ``time.monotonic`` delta
      * cpu_time_s         ``time.process_time`` delta for this process
      * peak_rss_kb        ``getrusage(RUSAGE_SELF).ru_maxrss`` at exit
                           (divided by 1024 on macOS where the unit is bytes)
      * rss_delta_kb       peak RSS gain since entry
      * energy_uj          energy delta via the best available backend:
                           RAPL on Linux, CodeCarbon on macOS, or None

    If ``target_pid`` is given (e.g. the PID of an Ollama daemon that
    does the real inference work), it also records the CPU delta and
    ending RSS of that process via psutil.

    Energy backend selection:

    1. RAPL (Linux x86 with readable ``/sys/class/powercap``).
    2. CodeCarbon (any platform; ``pip install 'perfarena[codecarbon]'``).
       On Apple Silicon this uses ``powermetrics`` (needs sudo for
       real power data; falls back to TDP estimation without it).
    3. None. ``energy_uj`` is ``null`` and ``energy_source`` is ``"none"``.

    Pass ``energy_backend="rapl"`` or ``energy_backend="codecarbon"``
    to force a specific backend. Default is ``"auto"`` which tries
    RAPL first, then CodeCarbon.
    """

    _RSS_DIVISOR = 1024 if platform.system() == "Darwin" else 1

    def __init__(
        self,
        target_pid: Optional[int] = None,
        energy_backend: str = "auto",
    ):
        self.target_pid = target_pid
        self.metrics = ProfileMetrics(target_pid=target_pid)
        self._requested_backend = energy_backend

    def _resolve_backend(self) -> str:
        req = self._requested_backend.lower()
        if req == "auto":
            return _best_energy_backend()
        return req

    def __enter__(self) -> "Profiler":
        self._wall_start = time.monotonic()
        self._cpu_start = time.process_time()
        self._rss_start = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        self._backend = self._resolve_backend()

        # --- RAPL setup ---
        self._rapl_start: Optional[int] = None
        self._rapl_max: Optional[int] = None
        if self._backend == "rapl":
            self._rapl_start = _read_int_file(RAPL_ENERGY_UJ_PATH)
            self._rapl_max = _read_int_file(RAPL_MAX_UJ_PATH)

        # --- CodeCarbon setup ---
        self._cc_tracker: Any = None
        if self._backend == "codecarbon" and _HAS_CODECARBON:
            try:
                self._cc_tracker = _CCTracker(
                    project_name="perfarena",
                    log_level="error",
                    save_to_file=False,
                    save_to_api=False,
                    save_to_logger=False,
                )
                self._cc_tracker.start()
            except Exception as exc:  # noqa: BLE001
                self.metrics.notes.append(
                    f"CodeCarbon start failed: {exc}"
                )
                self._cc_tracker = None

        # --- target PID setup ---
        self._proc = None
        if self.target_pid is not None and _HAS_PSUTIL:
            try:
                self._proc = psutil.Process(self.target_pid)
                cpu = self._proc.cpu_times()
                self._proc_cpu_start = cpu.user + cpu.system
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                self.metrics.notes.append(
                    f"target_pid {self.target_pid} unreachable: {exc}"
                )
                self._proc = None
        elif self.target_pid is not None and not _HAS_PSUTIL:
            self.metrics.notes.append(
                "target_pid requested but psutil not installed"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        wall = time.monotonic() - self._wall_start
        cpu = time.process_time() - self._cpu_start
        rss_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        self.metrics.wall_time_s = wall
        self.metrics.cpu_time_s = cpu
        self.metrics.peak_rss_kb = int(rss_peak) // self._RSS_DIVISOR
        self.metrics.rss_delta_kb = max(
            0, (int(rss_peak) - int(self._rss_start)) // self._RSS_DIVISOR
        )

        # --- RAPL energy ---
        if self._backend == "rapl" and self._rapl_start is not None:
            rapl_end = _read_int_file(RAPL_ENERGY_UJ_PATH)
            if rapl_end is not None:
                delta = rapl_end - self._rapl_start
                if delta < 0 and self._rapl_max is not None:
                    delta += self._rapl_max
                self.metrics.energy_uj = int(delta)
                self.metrics.energy_source = "rapl"
            else:
                self.metrics.energy_source = "none"
                self.metrics.notes.append("RAPL not readable at exit")

        # --- CodeCarbon energy ---
        elif self._backend == "codecarbon" and self._cc_tracker is not None:
            try:
                self._cc_tracker.stop()
                data = self._cc_tracker.final_emissions_data
                if data is not None and data.energy_consumed is not None:
                    kwh = data.energy_consumed
                    # Convert kWh to microjoules: 1 kWh = 3.6e9 uJ
                    uj = int(kwh * 3_600_000_000)
                    self.metrics.energy_uj = uj
                    self.metrics.energy_source = "codecarbon"
                    self.metrics.notes.append(
                        f"codecarbon: cpu_energy_kwh={data.cpu_energy}, "
                        f"gpu_energy_kwh={data.gpu_energy}, "
                        f"ram_energy_kwh={data.ram_energy}, "
                        f"duration_s={data.duration}"
                    )
                else:
                    self.metrics.energy_source = "codecarbon-no-data"
                    self.metrics.notes.append("CodeCarbon returned no data")
            except Exception as exc:  # noqa: BLE001
                self.metrics.energy_source = "codecarbon-error"
                self.metrics.notes.append(f"CodeCarbon stop failed: {exc}")

        else:
            self.metrics.energy_source = "none"
            if self._backend == "rapl":
                self.metrics.notes.append("RAPL not readable at start")
            elif self._backend == "codecarbon":
                self.metrics.notes.append(
                    "CodeCarbon requested but not installed; "
                    "pip install 'perfarena[codecarbon]'"
                )
                self.metrics.notes.append("RAPL not readable at start")

        if self._proc is not None:
            try:
                cpu_end = self._proc.cpu_times()
                self.metrics.target_cpu_delta_s = (
                    (cpu_end.user + cpu_end.system) - self._proc_cpu_start
                )
                self.metrics.target_rss_kb_end = (
                    self._proc.memory_info().rss // 1024
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                self.metrics.notes.append(
                    f"target_pid {self.target_pid} disappeared: {exc}"
                )


def find_process_by_name(name: str) -> Optional[int]:
    """Return the PID of the first process whose name matches ``name``.

    Used by the agent to locate an Ollama daemon (``ollama``) or any
    other external LLM process whose resource usage we want to
    attribute to a generation call.
    """
    if not _HAS_PSUTIL:
        return None
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            if proc.info["name"] == name:
                return int(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None
