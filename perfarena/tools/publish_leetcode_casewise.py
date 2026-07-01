"""Build and publish compact casewise measurement summaries to PerfArena."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _first_measurement_host(jsonl_path: Path) -> dict[str, Any]:
    with jsonl_path.open() as fh:
        for line in fh:
            row = json.loads(line)
            if row.get("host"):
                return row["host"]
    raise ValueError(f"no host metadata found in {jsonl_path}")


def scrub_machine_metadata(host: dict[str, Any]) -> dict[str, Any]:
    power_source_raw = str(host.get("power_source") or "")
    if "AC Power" in power_source_raw:
        power_source = "AC Power"
    elif "Battery Power" in power_source_raw:
        power_source = "Battery Power"
    else:
        power_source = "unknown"
    low_power_raw = host.get("low_power_mode")
    if isinstance(low_power_raw, list):
        low_power_mode = any(str(value).strip() == "1" for value in low_power_raw)
    else:
        low_power_mode = str(low_power_raw).strip().lower() in {"1", "true", "yes"}
    return {
        "machine_model": host.get("machine_model") or "unknown",
        "architecture": host.get("machine") or "unknown",
        "macos_version": host.get("macos_version") or "unknown",
        "python_version": host.get("python") or "unknown",
        "power_source": power_source,
        "low_power_mode": low_power_mode,
    }


def duration_from_summary(summary: dict[str, Any], summary_path: Path) -> float | None:
    value = summary.get("duration_seconds")
    if value is not None:
        return float(value)
    markdown = summary_path.with_suffix(".md")
    if not markdown.exists():
        return None
    text = markdown.read_text()
    match = re.search(r"about \*\*(?:(\d+) hours?)?(?:\s*(\d+) minutes?)?\*\*", text)
    if not match or not any(match.groups()):
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return float(hours * 3600 + minutes * 60)


def resolve_model_version(rows: Iterable[dict[str, Any]], explicit: str | None) -> str:
    versions = sorted({str(row.get("model_version")) for row in rows if row.get("model_version")})
    if explicit:
        if versions and explicit not in versions:
            raise ValueError(
                f"model version {explicit!r} is not present in dataset rows: {versions}"
            )
        return explicit
    if not versions:
        raise ValueError("dataset rows do not include model_version")
    if len(versions) != 1:
        raise ValueError(
            f"multiple model versions found {versions}; pass --model-version"
        )
    return versions[0]


def build_payload(
    root: Path,
    *,
    model_name: str,
    model_version: str,
    model_slug: str,
    language: str,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    summary_path = root / f"{language}_casewise_summary.json"
    jsonl_path = root / f"{language}_casewise.jsonl"
    missing = [path for path in (summary_path, jsonl_path) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "missing casewise publication inputs:\n"
            + "\n".join(f"  {path}" for path in missing)
        )
    summary = json.loads(summary_path.read_text())
    if summary.get("model_slug") != model_slug:
        raise ValueError(
            f"summary model_slug {summary.get('model_slug')!r} does not match {model_slug!r}"
        )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in summary.get("cases") or []:
        grouped[case["problem"]].append(case)
    problems: list[dict[str, Any]] = []
    for problem in summary.get("problems") or []:
        slug = problem["problem"]
        cases = grouped.get(slug, [])
        if len(cases) != int(problem["case_count"]):
            raise ValueError(f"{slug}: summary problem/case rows are incomplete")
        source_hashes = {case["source_hash"] for case in cases}
        if len(source_hashes) != 1:
            raise ValueError(f"{slug}: cases have multiple source hashes")
        problems.append(
            {
                "problem_slug": slug,
                "case_count": int(problem["case_count"]),
                "expected_case_count": int(problem["expected_case_count"]),
                "median_case_wall_ms": float(problem["median_case_wall_ms"]),
                "median_case_cpu_energy_j": float(
                    problem["median_case_cpu_energy_j"]
                ),
                "local_suite_wall_ms": math.fsum(
                    float(case["median_wall_ms_per_call"]) for case in cases
                ),
                "local_suite_cpu_energy_j": math.fsum(
                    float(case["median_cpu_energy_j_per_call"]) for case in cases
                ),
                "median_case_energy_cv": float(problem["median_case_energy_cv"]),
                "max_case_energy_cv": float(problem["max_case_energy_cv"]),
                "warmup_stable": bool(problem["warmup_stable"]),
                "workload_hash": problem["workload_hash"],
                "source_hash": source_hashes.pop(),
                "cases": [
                    {
                        key: case[key]
                        for key in (
                            "case_index",
                            "case_hash",
                            "batch_calls",
                            "measurement_rows",
                            "median_wall_ms_per_call",
                            "min_wall_ms_per_call",
                            "max_wall_ms_per_call",
                            "median_cpu_energy_j_per_call",
                            "min_cpu_energy_j_per_call",
                            "max_cpu_energy_j_per_call",
                            "energy_cv",
                            "median_cpu_power_w",
                            "median_powermetrics_samples",
                            "warmup_stable",
                            "workload_hash",
                            "source_hash",
                        )
                    }
                    for case in sorted(cases, key=lambda row: int(row["case_index"]))
                ],
            }
        )
    host = scrub_machine_metadata(_first_measurement_host(jsonl_path))
    duration = duration_seconds
    if duration is None:
        duration = duration_from_summary(summary, summary_path)
    return {
        "model_name": model_name,
        "model_version": model_version,
        "model_slug": model_slug,
        "language": language,
        "benchmark": summary.get("benchmark", "leetcode-energy-casewise"),
        "energy_source": summary.get("energy_source", "powermetrics-cpu"),
        "machine_metadata": host,
        "protocol": summary["measurement_protocol"],
        "duration_seconds": duration,
        "measured_problems": len(problems),
        "complete_cases": sum(len(problem["cases"]) for problem in problems),
        "measurement_rows": sum(
            int(case["measurement_rows"])
            for problem in problems
            for case in problem["cases"]
        ),
        "skipped_problems": int(summary.get("skipped_problems", 0)),
        "failed_problems": int(summary.get("failed_problems", 0)),
        "model_median_problem_energy_j": float(
            summary["model_median_problem_energy_j"]
        ),
        "problems": problems,
    }


def payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "payload_hash": _canonical_hash(payload),
        "model_name": payload["model_name"],
        "model_version": payload["model_version"],
        "language": payload["language"],
        "measured_problems": payload["measured_problems"],
        "complete_cases": payload["complete_cases"],
        "measurement_rows": payload["measurement_rows"],
        "duration_seconds": payload["duration_seconds"],
        "machine_metadata": payload["machine_metadata"],
    }
