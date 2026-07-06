from __future__ import annotations

import json
from pathlib import Path

import pytest

from perfarena.tools import publish_leetcode_casewise as publisher


def _fixture(root: Path) -> None:
    case = {
        "problem": "two-sum",
        "case_index": 0,
        "case_hash": "a" * 64,
        "measurement_rows": 10,
        "batch_calls": 100,
        "median_wall_ms_per_call": 0.1,
        "min_wall_ms_per_call": 0.09,
        "max_wall_ms_per_call": 0.11,
        "median_cpu_energy_j_per_call": 0.001,
        "min_cpu_energy_j_per_call": 0.0009,
        "max_cpu_energy_j_per_call": 0.0011,
        "energy_cv": 0.03,
        "median_cpu_power_w": 5.0,
        "median_powermetrics_samples": 8,
        "warmup_stable": True,
        "workload_hash": "b" * 64,
        "source_hash": "c" * 64,
    }
    summary = {
        "benchmark": "leetcode-energy-casewise",
        "model_slug": "ollama__test",
        "energy_source": "powermetrics-cpu",
        "measurement_protocol": {
            "measurement_iterations_per_case": 10,
            "warmup_seconds": 60,
        },
        "skipped_problems": 2,
        "failed_problems": 0,
        "model_median_problem_energy_j": 0.001,
        "problems": [
            {
                "problem": "two-sum",
                "case_count": 1,
                "expected_case_count": 1,
                "median_case_wall_ms": 0.1,
                "median_case_cpu_energy_j": 0.001,
                "median_case_energy_cv": 0.03,
                "max_case_energy_cv": 0.03,
                "warmup_stable": True,
                "workload_hash": "b" * 64,
            }
        ],
        "cases": [case],
    }
    (root / "python_casewise_summary.json").write_text(json.dumps(summary))
    (root / "python_casewise_summary.md").write_text(
        "The run took about **17 hours 19 minutes** for all problems."
    )
    measurement = {
        "source": "/private/source.py",
        "raw_powermetrics_path": "/private/raw.plist",
        "host": {
            "machine_model": "Mac15,6",
            "machine": "arm64",
            "macos_version": "26.5",
            "python": "3.14.3",
            "power_source": "Now drawing from 'AC Power' battery 39%",
            "low_power_mode": ["0", "0"],
            "power_settings": "private machine settings",
        },
    }
    (root / "python_casewise.jsonl").write_text(json.dumps(measurement) + "\n")


def test_build_payload_contains_compact_server_contract(tmp_path: Path) -> None:
    _fixture(tmp_path)

    payload = publisher.build_payload(
        tmp_path,
        model_name="test-model",
        model_version="v1",
        model_slug="ollama__test",
        language="python",
    )

    assert payload["measured_problems"] == 1
    assert payload["complete_cases"] == 1
    assert payload["measurement_rows"] == 10
    assert payload["harness_slug"] == "local-powermetrics"
    assert payload["duration_seconds"] == 62_340
    assert payload["problems"][0]["local_suite_wall_ms"] == pytest.approx(0.1)
    assert payload["problems"][0]["local_suite_cpu_energy_j"] == pytest.approx(0.001)
    assert payload["machine_metadata"] == {
        "machine_model": "Mac15,6",
        "architecture": "arm64",
        "macos_version": "26.5",
        "python_version": "3.14.3",
        "power_source": "AC Power",
        "low_power_mode": False,
    }


def test_payload_excludes_raw_telemetry_code_and_paths(tmp_path: Path) -> None:
    _fixture(tmp_path)
    payload = publisher.build_payload(
        tmp_path,
        model_name="test-model",
        model_version="v1",
        model_slug="ollama__test",
        language="python",
    )
    serialized = json.dumps(payload)

    for forbidden in (
        "raw_powermetrics_path",
        "private machine settings",
        "/private/source.py",
        "/private/raw.plist",
        '"code"',
    ):
        assert forbidden not in serialized


def test_resolve_model_version_requires_disambiguation() -> None:
    rows = [{"model_version": "v1"}, {"model_version": "v2"}]

    with pytest.raises(ValueError, match="multiple model versions"):
        publisher.resolve_model_version(rows, None)
    assert publisher.resolve_model_version(rows, "v2") == "v2"


def test_payload_summary_is_small_and_stable(tmp_path: Path) -> None:
    _fixture(tmp_path)
    payload = publisher.build_payload(
        tmp_path,
        model_name="test-model",
        model_version="v1",
        model_slug="ollama__test",
        language="python",
    )

    summary = publisher.payload_summary(payload)

    assert len(summary["payload_hash"]) == 64
    assert "problems" not in summary
    assert summary["complete_cases"] == 1
    assert summary["harness_slug"] == "local-powermetrics"
