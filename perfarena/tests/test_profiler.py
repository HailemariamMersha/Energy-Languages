"""Tests for the Profiler context manager."""
from __future__ import annotations

import time

from perfarena.generation.profiler import Profiler, host_fingerprint


def test_profiler_captures_wall_time():
    with Profiler() as p:
        time.sleep(0.05)
    assert p.metrics.wall_time_s >= 0.04
    # CPU time for a sleep is near zero, so just sanity-check the
    # dict serialization includes the right fields.
    payload = p.metrics.to_dict()
    assert set(payload.keys()) >= {
        "wall_time_s",
        "cpu_time_s",
        "peak_rss_kb",
        "rss_delta_kb",
        "energy_uj",
        "energy_source",
    }


def test_profiler_falls_back_when_rapl_unreadable(monkeypatch):
    from perfarena.generation import profiler as prof_mod

    monkeypatch.setattr(prof_mod, "_read_int_file", lambda path: None)
    with Profiler() as p:
        time.sleep(0.01)
    # When RAPL is unavailable, the profiler should fall back to
    # CodeCarbon (if installed) or to "none".
    assert p.metrics.energy_source in ("none", "codecarbon", "codecarbon-no-data")
    if p.metrics.energy_source == "none":
        assert p.metrics.energy_uj is None


def test_profiler_forced_none_backend():
    """Force the 'none' backend and verify no energy is recorded."""
    with Profiler(energy_backend="none") as p:
        time.sleep(0.01)
    assert p.metrics.energy_source == "none"
    assert p.metrics.energy_uj is None


def test_host_fingerprint_has_required_keys():
    info = host_fingerprint()
    for key in ("hostname", "platform", "release", "machine", "cpu_count"):
        assert key in info
