"""Tests for the measurement ingest module."""
from __future__ import annotations

import json
from pathlib import Path

from perfarena.measurement import (
    RawIteration,
    group_iterations,
    read_rapl_jsonl,
    write_jsonl,
    join_group_with_meta,
    MeasurementRow,
)


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_read_and_group_iterations(tmp_path):
    rows = [
        {
            "test": "binary-trees",
            "language": "Python",
            "iteration": 0,
            "phase": "idle",
            "wall_ms": 5000.0,
            "rapl_pkg_start_raw": 100,
            "rapl_pkg_end_raw": 200,
            "rapl_pkg_delta_raw": 100,
            "samples": 0,
            "exit_code": 0,
        },
        {
            "test": "binary-trees",
            "language": "Python",
            "iteration": 1,
            "phase": "warmup",
            "wall_ms": 1100.0,
            "rapl_pkg_start_raw": 200,
            "rapl_pkg_end_raw": 400,
            "rapl_pkg_delta_raw": 200,
            "samples": 10,
            "exit_code": 0,
        },
        {
            "test": "binary-trees",
            "language": "Python",
            "iteration": 2,
            "phase": "measure",
            "wall_ms": 1050.0,
            "rapl_pkg_start_raw": 400,
            "rapl_pkg_end_raw": 590,
            "rapl_pkg_delta_raw": 190,
            "samples": 10,
            "exit_code": 0,
        },
    ]
    p = tmp_path / "Python.jsonl"
    _write(p, rows)

    parsed = read_rapl_jsonl(p)
    assert len(parsed) == 3
    groups = group_iterations(parsed)
    assert len(groups) == 1
    g = groups[0]
    assert g.idle is not None and g.idle.phase == "idle"
    assert len(g.warmup) == 1
    assert len(g.measurement) == 1


def test_join_group_with_meta_produces_measurement_rows():
    it = RawIteration(
        test="binary-trees",
        language="Python",
        iteration=2,
        phase="measure",
        wall_ms=1050.0,
        rapl_pkg_start_raw=400,
        rapl_pkg_end_raw=590,
        rapl_pkg_delta_raw=190,
        samples=10,
        exit_code=0,
    )
    from perfarena.measurement import IterationGroup

    group = IterationGroup(
        test="binary-trees",
        language="Python",
        idle=None,
        warmup=[],
        measurement=[it],
    )
    meta = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "language": "python",
        "language_folder": "Python",
        "problem": "binary-trees",
        "sample_id": 3,
        "response": {"duration_s": 2.0},
        "prompts": {"prompt_pair_sha256": "deadbeef"},
        "provenance": {"git_sha": "abc"},
        "inference": {"metrics": {"wall_time_s": 1.5}},
    }
    rows = list(join_group_with_meta(group, meta))
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, MeasurementRow)
    assert row.model == "gpt-4o-mini"
    assert row.sample_id == 3
    assert row.rapl_pkg_delta_raw == 190
    assert row.inference_metrics == {"wall_time_s": 1.5}
    assert row.provenance["git_sha"] == "abc"


def test_write_jsonl_roundtrip(tmp_path):
    it = RawIteration(
        test="mandelbrot",
        language="C++",
        iteration=1,
        phase="measure",
        wall_ms=800.0,
        rapl_pkg_start_raw=0,
        rapl_pkg_end_raw=1000,
        rapl_pkg_delta_raw=1000,
        samples=10,
        exit_code=0,
    )
    from perfarena.measurement import IterationGroup

    group = IterationGroup(
        test="mandelbrot",
        language="C++",
        idle=None,
        warmup=[],
        measurement=[it],
    )
    meta = {
        "provider": "anthropic",
        "model": "claude",
        "language": "cpp",
        "language_folder": "C++",
        "problem": "mandelbrot",
        "sample_id": 0,
        "response": {"duration_s": 0.9},
        "prompts": {"prompt_pair_sha256": ""},
        "provenance": {},
    }
    rows = list(join_group_with_meta(group, meta))
    out = write_jsonl(rows, tmp_path / "measurements.jsonl")
    assert out.exists()
    loaded = [json.loads(line) for line in out.read_text().splitlines() if line.strip()]
    assert len(loaded) == 1
    assert loaded[0]["model"] == "claude"
