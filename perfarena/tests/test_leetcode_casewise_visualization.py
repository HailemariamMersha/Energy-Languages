from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from perfarena.tools import visualize_leetcode_casewise as viz


def test_quartiles_known_values() -> None:
    stats = viz.quartiles([1, 2, 3, 4, 5])

    assert stats.minimum == 1
    assert stats.q1 == 1.5
    assert stats.median == 3
    assert stats.q3 == 4.5
    assert stats.maximum == 5


def test_log_position_requires_positive_values() -> None:
    assert viz.log_position(10, 1, 100, 0, 1) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="positive"):
        viz.log_position(0, 1, 100, 0, 1)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fixture(root: Path) -> None:
    _write_csv(
        root / "python_casewise_cases.csv",
        [
            {
                "problem": "alpha-problem",
                "case_index": 0,
                "case_hash": "a0",
                "measurement_rows": 10,
                "batch_calls": 100,
                "median_wall_ms_per_call": 0.1,
                "min_wall_ms_per_call": 0.09,
                "max_wall_ms_per_call": 0.11,
                "median_cpu_energy_j_per_call": 0.001,
                "min_cpu_energy_j_per_call": 0.0009,
                "max_cpu_energy_j_per_call": 0.0011,
                "energy_cv": 0.03,
                "median_cpu_power_w": 5,
                "median_powermetrics_samples": 8,
                "warmup_stable": True,
                "workload_hash": "w1",
                "source_hash": "s1",
            },
            {
                "problem": "alpha-problem",
                "case_index": 1,
                "case_hash": "a1",
                "measurement_rows": 10,
                "batch_calls": 50,
                "median_wall_ms_per_call": 1.0,
                "min_wall_ms_per_call": 0.9,
                "max_wall_ms_per_call": 1.1,
                "median_cpu_energy_j_per_call": 0.01,
                "min_cpu_energy_j_per_call": 0.009,
                "max_cpu_energy_j_per_call": 0.011,
                "energy_cv": 0.05,
                "median_cpu_power_w": 6,
                "median_powermetrics_samples": 8,
                "warmup_stable": True,
                "workload_hash": "w1",
                "source_hash": "s1",
            },
            {
                "problem": "beta-problem",
                "case_index": 0,
                "case_hash": "b0",
                "measurement_rows": 10,
                "batch_calls": 200,
                "median_wall_ms_per_call": 0.01,
                "min_wall_ms_per_call": 0.009,
                "max_wall_ms_per_call": 0.011,
                "median_cpu_energy_j_per_call": 0.0001,
                "min_cpu_energy_j_per_call": 0.00009,
                "max_cpu_energy_j_per_call": 0.00011,
                "energy_cv": 0.02,
                "median_cpu_power_w": 4,
                "median_powermetrics_samples": 8,
                "warmup_stable": True,
                "workload_hash": "w2",
                "source_hash": "s2",
            },
        ],
    )
    _write_csv(
        root / "python_casewise_problems.csv",
        [
            {
                "problem": "alpha-problem",
                "case_count": 2,
                "expected_case_count": 2,
                "median_case_wall_ms": 0.55,
                "median_case_cpu_energy_j": 0.0055,
                "median_case_energy_cv": 0.04,
                "max_case_energy_cv": 0.05,
                "warmup_stable": True,
                "workload_hash": "w1",
            },
            {
                "problem": "beta-problem",
                "case_count": 1,
                "expected_case_count": 1,
                "median_case_wall_ms": 0.01,
                "median_case_cpu_energy_j": 0.0001,
                "median_case_energy_cv": 0.02,
                "max_case_energy_cv": 0.02,
                "warmup_stable": True,
                "workload_hash": "w2",
            },
        ],
    )
    (root / "python_casewise_summary.json").write_text(
        json.dumps(
            {
                "model_slug": "test-model",
                "measured_problems": 2,
                "complete_cases": 3,
                "measurement_rows": 30,
                "skipped_problems": 0,
                "failed_problems": 0,
                "model_median_problem_energy_j": 0.0028,
            }
        )
    )
    (root / "python_casewise_summary.md").write_text(
        "The full experiment therefore took about **1 hour**.\n"
    )


def test_report_generation_from_tiny_fixture(tmp_path: Path) -> None:
    _fixture(tmp_path)

    output = viz.write_report(tmp_path, "python")
    html = output.read_text()

    assert "Problem Energy Box Plot" in html
    assert "Test Case Count Distribution" in html
    assert "Batch Calls Distribution" in html
    assert "Case Runtime By Problem" in html
    assert "Example Problem Case Rollup" in html
    assert "Energy vs Wall Time" in html
    assert "Case Measurement Noise" in html
    assert "Measurement Walkthrough" in html
    assert "Integrate powermetrics samples" in html
    assert "Accepted selected" in html
    assert "1 hour" in html


def test_missing_inputs_fail_clearly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing required casewise files"):
        viz.load_data(tmp_path, "python")
