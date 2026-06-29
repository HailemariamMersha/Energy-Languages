from __future__ import annotations

import gzip
import json
import plistlib
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from perfarena import casewise_energy
from perfarena.leetcode_energy import get_language
from perfarena.runners.leetcode_case_worker import CaseWorker
from perfarena.tools import summarize_leetcode_casewise as summary_tool


def _workload() -> dict:
    cases = [
        {"input": "nums = [1, 2, 3]", "output": "2"},
        {"input": "nums = [4, 5]", "output": "1"},
    ]
    return {
        "problem": "mutating-case",
        "workload_hash": "workload-hash",
        "prompt": "from typing import *\nevents = []\n",
        "entry_point": "Solution().solve",
        "cases": cases,
        "test": (
            "def check(candidate):\n"
            "    assert candidate(nums=[1, 2, 3]) == 2\n"
            "    assert candidate(nums=[4, 5]) == 1\n"
        ),
    }


def _source(path: Path) -> Path:
    path.write_text(
        "class Solution:\n"
        "    def solve(self, nums):\n"
        "        events.append(len(nums))\n"
        "        nums.pop()\n"
        "        return len(nums)\n"
    )
    return path


def test_worker_reconstructs_mutable_input_for_every_call(tmp_path: Path) -> None:
    workload = _workload()
    original = json.dumps(workload["cases"], sort_keys=True).encode()
    worker = CaseWorker(_source(tmp_path / "solution.py"), workload)

    row = worker._run_case(0, 3)

    assert row["batch_calls"] == 3
    assert worker.namespace["events"] == [3, 3, 3]
    assert json.dumps(workload["cases"], sort_keys=True).encode() == original


def test_worker_warms_before_calibration_and_fixes_batch_count(tmp_path: Path) -> None:
    worker = CaseWorker(_source(tmp_path / "solution.py"), _workload())

    warmup = worker.warmup(0)
    calibration = worker.calibrate(0, 0.001)
    first = worker._run_case(0, calibration["batch_calls"])
    second = worker._run_case(0, calibration["batch_calls"])

    assert warmup["sweeps"] >= 1
    assert calibration["batch_calls"] >= 1
    assert calibration["pilot_wall_ns"] >= calibration["target_ns"]
    assert first["batch_calls"] == second["batch_calls"]


def test_parse_powermetrics_plist_fixture() -> None:
    payload = plistlib.dumps(
        {
            "elapsed_ns": 100_000_000,
            "processor": {
                "cpu_power": 2500,
                "gpu_power": 500,
                "ane_power": 100,
            },
            "thermal_pressure": "Nominal",
        }
    )

    sample = casewise_energy.parse_powermetrics_plist(payload, ended_ns=1_000_000_000)

    assert sample.started_ns == 900_000_000
    assert sample.cpu_w == 2.5
    assert sample.gpu_w == 0.5
    assert sample.ane_w == 0.1
    assert sample.thermal == "Nominal"


def test_integrate_window_uses_complete_sample_windows() -> None:
    samples = [
        casewise_energy.PowerSample(
            ended_ns=200_000_000,
            elapsed_ns=100_000_000,
            cpu_w=2.0,
            thermal="Nominal",
        ),
        casewise_energy.PowerSample(
            ended_ns=300_000_000,
            elapsed_ns=100_000_000,
            cpu_w=4.0,
            thermal="Nominal",
        ),
    ]

    result = casewise_energy.integrate_window(samples, 100_000_000, 300_000_000)

    assert result["cpu_energy_j"] == pytest.approx(0.6)
    assert result["mean_cpu_w"] == pytest.approx(3.0)
    assert result["sample_coverage"] == pytest.approx(1.0)


def test_raw_plist_archiving_appends_compressed_members(tmp_path: Path) -> None:
    source = tmp_path / "samples.plist"
    destination = tmp_path / "samples.plist.gz"
    source.write_bytes(b"first\0")
    casewise_energy.archive_raw_plist(source, destination)
    source.write_bytes(b"second\0")
    casewise_energy.archive_raw_plist(source, destination)

    with gzip.open(destination, "rb") as fh:
        assert fh.read() == b"first\0second\0"
    assert not source.exists()


def _measurement_row(
    problem: str, hashed: str, case_index: int, iteration: int, energy: float
) -> dict:
    return {
        "phase": "measure",
        "problem": problem,
        "case_hash": hashed,
        "case_index": case_index,
        "measurement_iteration": iteration,
        "batch_calls": 10,
        "cpu_energy_j_per_call": energy,
        "wall_ms_per_call": energy * 2,
        "mean_cpu_w": 0.5,
        "powermetrics_samples": 8,
        "warmup_stable": True,
        "workload_hash": "w",
        "source_hash": "s",
        "model_slug": "model-a",
        "language": "python",
        "warmup_seconds": 60,
        "batch_target_s": 1,
        "powermetrics_interval_ms": 100,
    }


def test_summary_takes_case_medians_before_problem_median(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    rows = []
    for index, energy in enumerate([1.0, 7.0, 100.0]):
        rows.extend(
            _measurement_row("problem", f"case-{index}", index, iteration, energy)
            for iteration in range(1, 11)
        )
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    summary = summary_tool.summarize(path)

    assert summary["complete_cases"] == 3
    assert summary["problems"][0]["median_case_cpu_energy_j"] == 7.0
    assert summary["model_median_problem_energy_j"] == 7.0


def test_summary_requires_exactly_ten_unique_rows_per_case(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    rows = [
        _measurement_row("problem", "case", 0, iteration, 1.0)
        for iteration in range(1, 10)
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    summary = summary_tool.summarize(path)

    assert summary["complete_cases"] == 0
    assert summary["incomplete_cases"][0]["rows"] == 9


def test_model_comparison_uses_only_common_case_intersection() -> None:
    common_a = {
        "problem": "shared",
        "case_hash": "same",
        "median_cpu_energy_j_per_call": 2.0,
        "median_wall_ms_per_call": 4.0,
    }
    common_b = {**common_a, "median_cpu_energy_j_per_call": 3.0}
    model_a = {
        "model_slug": "a",
        "cases": [common_a, {**common_a, "problem": "only-a", "case_hash": "a"}],
    }
    model_b = {
        "model_slug": "b",
        "cases": [common_b, {**common_b, "problem": "only-b", "case_hash": "b"}],
    }

    comparison = summary_tool.compare_models([model_a, model_b])

    assert comparison["common_cases"] == 1
    assert comparison["common_problems"] == 1
    assert [row["model_slug"] for row in comparison["models"]] == ["a", "b"]


class _FakeSampler:
    interval_ms: int

    def __init__(self, raw_path: Path, interval_ms: int) -> None:
        self.raw_path = raw_path
        self.interval_ms = interval_ms

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def wait_for_window(self, ended_ns: int, timeout: float = 2.0) -> None:
        pass

    def samples_for_window(self, started_ns: int, ended_ns: int):
        elapsed = max(1, (ended_ns - started_ns) // 6)
        return [
            casewise_energy.PowerSample(
                ended_ns=started_ns + elapsed * (index + 1),
                elapsed_ns=elapsed,
                cpu_w=2.0,
                thermal="Nominal",
            )
            for index in range(6)
        ]

    def latest_thermal(self) -> str:
        return "Nominal"


class _RecordingWorker:
    events: list[dict] = []

    def __init__(self, repo_root: Path, source: Path, workload: Path) -> None:
        pass

    def request(self, payload: dict) -> dict:
        self.events.append(payload)
        if payload["action"] == "validate":
            return {"ok": True}
        if payload["action"] == "warmup":
            return {
                "ok": True,
                "wall_ns": int(payload["seconds"] * 1_000_000_000),
                "sweeps": 10,
                "warmup_drift": 0.01,
                "warmup_stable": True,
            }
        if payload["action"] == "calibrate":
            return {"batch_calls": 10, "pilot_wall_ns": 1_000_000_000}
        started = time.monotonic_ns()
        return {
            "batch_calls": payload["batch_calls"],
            "started_ns": started,
            "ended_ns": started + 1_000_000_000,
            "wall_ns": 1_000_000_000,
        }

    def close(self) -> None:
        pass


def test_engine_orders_sixty_second_warmup_before_calibration(
    tmp_path: Path, monkeypatch
) -> None:
    workload_path = (
        tmp_path / "leetcode-energy" / "reference" / "workloads" / "mutating-case.json"
    )
    workload_path.parent.mkdir(parents=True)
    workload_path.write_text(json.dumps(_workload()))
    source = _source(tmp_path / "solution.py")
    accepted = SimpleNamespace(
        problem_slug="mutating-case",
        source_path=source,
        result_path=tmp_path / "result.json",
        language=get_language("python"),
    )
    _RecordingWorker.events = []
    monkeypatch.setattr(casewise_energy, "WorkerClient", _RecordingWorker)
    monkeypatch.setattr(casewise_energy.platform, "system", lambda: "TestOS")

    casewise_energy.measure_casewise_results(
        tmp_path,
        [accepted],
        model_slug="model",
        warmup_seconds=60,
        measurements=1,
        output=tmp_path / "rows.jsonl",
        sampler_factory=_FakeSampler,
    )

    assert [row["action"] for row in _RecordingWorker.events[:4]] == [
        "validate",
        "warmup",
        "calibrate",
        "calibrate",
    ]
    assert _RecordingWorker.events[1]["seconds"] == 60


def test_casewise_smoke_checkpoints_and_resumes(tmp_path: Path, monkeypatch) -> None:
    workload = _workload()
    workload_path = (
        tmp_path / "leetcode-energy" / "reference" / "workloads" / "mutating-case.json"
    )
    workload_path.parent.mkdir(parents=True)
    workload_path.write_text(json.dumps(workload))
    source = _source(tmp_path / "solution.py")
    result_path = tmp_path / "result.json"
    result_path.write_text('{"accepted": true}')
    accepted = SimpleNamespace(
        problem_slug="mutating-case",
        source_path=source,
        result_path=result_path,
        language=get_language("python"),
    )
    output = tmp_path / "casewise.jsonl"
    monkeypatch.setattr(casewise_energy.platform, "system", lambda: "TestOS")

    first = casewise_energy.measure_casewise_results(
        tmp_path,
        [accepted],
        model_slug="model",
        warmup_seconds=0,
        measurements=2,
        batch_seconds=0.01,
        interval_ms=1,
        output=output,
        sampler_factory=_FakeSampler,
    )
    second = casewise_energy.measure_casewise_results(
        tmp_path,
        [accepted],
        model_slug="model",
        warmup_seconds=0,
        measurements=2,
        batch_seconds=0.01,
        interval_ms=1,
        output=output,
        sampler_factory=_FakeSampler,
    )

    assert len(first) == 4
    assert second == []
    assert len(output.read_text().splitlines()) == 4


def test_missing_curated_workload_writes_resumable_skip(tmp_path: Path) -> None:
    source = _source(tmp_path / "solution.py")
    accepted = SimpleNamespace(
        problem_slug="missing",
        source_path=source,
        result_path=tmp_path / "result.json",
        language=get_language("python"),
    )
    output = tmp_path / "casewise.jsonl"

    first = casewise_energy.measure_casewise_results(
        tmp_path,
        [accepted],
        model_slug="model",
        output=output,
        sampler_factory=_FakeSampler,
    )
    second = casewise_energy.measure_casewise_results(
        tmp_path,
        [accepted],
        model_slug="model",
        output=output,
        sampler_factory=_FakeSampler,
    )
    summary = summary_tool.summarize(output)

    assert first[0]["status"] == "skipped_missing_workload"
    assert second == []
    assert summary["skipped_problems"] == 1


def test_validation_failure_skips_measurement(tmp_path: Path) -> None:
    workload_path = (
        tmp_path / "leetcode-energy" / "reference" / "workloads" / "mutating-case.json"
    )
    workload_path.parent.mkdir(parents=True)
    workload_path.write_text(json.dumps(_workload()))
    source = tmp_path / "wrong.py"
    source.write_text(
        "class Solution:\n    def solve(self, nums):\n        return -1\n"
    )
    accepted = SimpleNamespace(
        problem_slug="mutating-case",
        source_path=source,
        result_path=tmp_path / "result.json",
        language=get_language("python"),
    )
    output = tmp_path / "casewise.jsonl"

    rows = casewise_energy.measure_casewise_results(
        tmp_path,
        [accepted],
        model_slug="model",
        output=output,
        sampler_factory=_FakeSampler,
    )

    assert rows[0]["status"] == "skipped_validation_failed"
    assert all(row["phase"] != "measure" for row in rows)
