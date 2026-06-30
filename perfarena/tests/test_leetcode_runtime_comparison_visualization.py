from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from perfarena.tools import visualize_leetcode_runtime_comparison as viz


def _local_rows() -> list[dict[str, str]]:
    return [
        {
            "problem": "alpha-problem",
            "case_count": 2,
            "local_suite_wall_ms": 1.0,
            "local_suite_energy_j": 0.01,
        },
        {
            "problem": "beta-problem",
            "case_count": 1,
            "local_suite_wall_ms": 0.1,
            "local_suite_energy_j": 0.001,
        },
    ]


def _runtime_rows() -> list[dict[str, object]]:
    return [
        {
            "problem_slug": "alpha-problem",
            "problem_title": "Alpha Problem",
            "problem_level": "Easy",
            "runtime_ms": 100.0,
            "runtime_percentile": 80.0,
            "total_testcases": 30,
            "submission_id": 1,
            "submitted_at": "2026-01-01T00:00:00",
        },
        {
            "problem_slug": "beta-problem",
            "problem_title": "Beta Problem",
            "problem_level": "Hard",
            "runtime_ms": 10.0,
            "runtime_percentile": 90.0,
            "total_testcases": 40,
            "submission_id": 1,
            "submitted_at": "2026-01-01T00:00:00",
        },
        {
            "problem_slug": "remote-only",
            "problem_title": "Remote Only",
            "problem_level": "Medium",
            "runtime_ms": 20.0,
            "runtime_percentile": 70.0,
            "total_testcases": 20,
            "submission_id": 1,
            "submitted_at": "2026-01-01T00:00:00",
        },
    ]


def _write_local_fixture(root: Path) -> None:
    rows = [
        {
            "problem": "alpha-problem",
            "case_count": 2,
            "expected_case_count": 2,
            "median_case_wall_ms": 0.5,
            "median_case_cpu_energy_j": 0.005,
        },
        {
            "problem": "beta-problem",
            "case_count": 1,
            "expected_case_count": 1,
            "median_case_wall_ms": 0.1,
            "median_case_cpu_energy_j": 0.001,
        },
    ]
    with (root / "python_casewise_problems.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    case_rows = [
        {
            "problem": "alpha-problem",
            "median_wall_ms_per_call": 0.4,
            "median_cpu_energy_j_per_call": 0.004,
        },
        {
            "problem": "alpha-problem",
            "median_wall_ms_per_call": 0.6,
            "median_cpu_energy_j_per_call": 0.006,
        },
        {
            "problem": "beta-problem",
            "median_wall_ms_per_call": 0.1,
            "median_cpu_energy_j_per_call": 0.001,
        },
    ]
    with (root / "python_casewise_cases.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(case_rows[0]))
        writer.writeheader()
        writer.writerows(case_rows)
    (root / "python_casewise_summary.json").write_text(
        json.dumps({"model_slug": "test-model", "measured_problems": 2})
    )


def test_average_ranks_assigns_average_to_ties() -> None:
    assert viz.average_ranks([10.0, 10.0, 30.0, 20.0]) == [1.5, 1.5, 4.0, 3.0]


def test_spearman_known_monotonic_inputs() -> None:
    assert viz.spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert viz.spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    assert viz.spearman([1], [2]) is None


def test_join_problem_rows_reports_overlap_and_ranks() -> None:
    data = viz.join_problem_rows(_local_rows(), _runtime_rows())

    assert data["local_count"] == 2
    assert data["runtime_count"] == 3
    assert data["overlap_count"] == 2
    assert data["local_only"] == []
    assert data["runtime_only"] == ["remote-only"]
    assert data["runtime_energy_spearman"] == pytest.approx(1.0)
    assert {row["problem"] for row in data["rows"]} == {
        "alpha-problem",
        "beta-problem",
    }


def test_join_problem_rows_rejects_missing_overlap() -> None:
    with pytest.raises(ValueError, match="no overlapping problems"):
        viz.join_problem_rows(
            _local_rows(),
            [{"problem_slug": "other", "runtime_ms": 1.0}],
        )


def test_snapshot_cache_and_refresh(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"
    calls = 0

    def fetcher():
        nonlocal calls
        calls += 1
        return _runtime_rows()

    first = viz.load_or_fetch_snapshot(
        path,
        base_url="https://example.test",
        model="gemma",
        language="python3",
        fetcher=fetcher,
    )
    second = viz.load_or_fetch_snapshot(
        path,
        base_url="https://example.test",
        model="gemma",
        language="python3",
        fetcher=fetcher,
    )
    third = viz.load_or_fetch_snapshot(
        path,
        base_url="https://example.test",
        model="gemma",
        language="python3",
        fetcher=fetcher,
        refresh=True,
    )

    assert calls == 2
    assert len(first["rows"]) == 3
    assert second == first
    assert len(third["rows"]) == 3
    assert "code" not in third["rows"][0]


def test_normalize_runtime_rows_keeps_latest_duplicate() -> None:
    rows = _runtime_rows()
    rows.append(
        {
            **rows[0],
            "runtime_ms": 75.0,
            "submission_id": 2,
            "submitted_at": "2026-02-01T00:00:00",
            "code": "must not be cached",
        }
    )

    normalized = viz.normalize_runtime_rows(rows)
    alpha = next(row for row in normalized if row["problem_slug"] == "alpha-problem")

    assert alpha["runtime_ms"] == 75.0
    assert "code" not in alpha


def test_report_generation_from_fixture(tmp_path: Path) -> None:
    _write_local_fixture(tmp_path)
    snapshot = {
        "schema_version": 1,
        "model": "gemma4:e4b",
        "language": "python3",
        "fetched_at": "2026-06-30T00:00:00+00:00",
        "rows": _runtime_rows(),
    }

    output = viz.write_report(tmp_path, "python", snapshot)
    report = output.read_text()

    assert output.name == "python_casewise_leetcode_comparison.html"
    assert "Local Energy vs LeetCode Runtime" in report
    assert "LeetCode Runtime vs Local Wall Time" in report
    assert "LeetCode Runtime vs Local CPU Energy" in report
    assert "Runtime Rank vs Energy Rank" in report
    assert "Matched Problem Data" in report
    assert "not by source hash" in report
    assert "alpha-problem" in report


def test_local_suite_sums_each_case_median_once(tmp_path: Path) -> None:
    _write_local_fixture(tmp_path)

    suites = viz.load_local_problem_suites(tmp_path, "python")
    alpha = next(row for row in suites if row["problem"] == "alpha-problem")

    assert alpha["local_suite_wall_ms"] == pytest.approx(1.0)
    assert alpha["local_suite_energy_j"] == pytest.approx(0.01)


def test_load_local_problems_requires_summary_and_csv(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="missing required casewise files"):
        viz.load_local_problem_suites(tmp_path, "python")
