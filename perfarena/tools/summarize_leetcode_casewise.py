"""Summaries and fair model comparisons for casewise LeetCode energy rows."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _median(values: list[float]) -> float:
    return statistics.median(values)


def _cv(values: list[float]) -> float:
    mean = statistics.mean(values)
    return statistics.stdev(values) / mean if len(values) > 1 and mean else 0.0


def summarize(input_path: Path, expected_measurements: int = 10) -> dict[str, Any]:
    rows = (
        [
            json.loads(line)
            for line in input_path.read_text().splitlines()
            if line.strip()
        ]
        if input_path.exists()
        else []
    )
    measured = [row for row in rows if row.get("phase") == "measure"]
    statuses = [row for row in rows if row.get("phase") == "status"]
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in measured:
        grouped[(row["problem"], row["case_hash"])].append(row)

    cases: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for (problem, hashed), case_rows in sorted(grouped.items()):
        by_iteration = {int(row["measurement_iteration"]): row for row in case_rows}
        if len(by_iteration) != expected_measurements:
            incomplete.append(
                {
                    "problem": problem,
                    "case_hash": hashed,
                    "rows": len(by_iteration),
                    "expected_rows": expected_measurements,
                }
            )
            continue
        ordered = [by_iteration[index] for index in sorted(by_iteration)]
        energy = [float(row["cpu_energy_j_per_call"]) for row in ordered]
        wall = [float(row["wall_ms_per_call"]) for row in ordered]
        cases.append(
            {
                "problem": problem,
                "case_index": int(ordered[0]["case_index"]),
                "case_hash": hashed,
                "measurement_rows": len(ordered),
                "batch_calls": int(ordered[0]["batch_calls"]),
                "median_wall_ms_per_call": _median(wall),
                "min_wall_ms_per_call": min(wall),
                "max_wall_ms_per_call": max(wall),
                "median_cpu_energy_j_per_call": _median(energy),
                "min_cpu_energy_j_per_call": min(energy),
                "max_cpu_energy_j_per_call": max(energy),
                "energy_cv": _cv(energy),
                "median_cpu_power_w": _median(
                    [float(row["mean_cpu_w"]) for row in ordered]
                ),
                "median_powermetrics_samples": _median(
                    [float(row["powermetrics_samples"]) for row in ordered]
                ),
                "warmup_stable": all(bool(row["warmup_stable"]) for row in ordered),
                "workload_hash": ordered[0]["workload_hash"],
                "source_hash": ordered[0]["source_hash"],
            }
        )

    by_problem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_problem[case["problem"]].append(case)
    problems: list[dict[str, Any]] = []
    partial_problems: list[dict[str, Any]] = []
    for problem, problem_cases in sorted(by_problem.items()):
        problem_rows = [row for row in measured if row["problem"] == problem]
        expected_cases = max(
            [
                int(row.get("workload_cases", len(problem_cases)))
                for row in problem_rows
            ],
            default=len(problem_cases),
        )
        incomplete_case_rows = [row for row in incomplete if row["problem"] == problem]
        result = {
            "problem": problem,
            "case_count": len(problem_cases),
            "expected_case_count": expected_cases,
            "median_case_wall_ms": _median(
                [row["median_wall_ms_per_call"] for row in problem_cases]
            ),
            "median_case_cpu_energy_j": _median(
                [row["median_cpu_energy_j_per_call"] for row in problem_cases]
            ),
            "median_case_energy_cv": _median(
                [row["energy_cv"] for row in problem_cases]
            ),
            "max_case_energy_cv": max(row["energy_cv"] for row in problem_cases),
            "warmup_stable": all(row["warmup_stable"] for row in problem_cases),
            "workload_hash": problem_cases[0]["workload_hash"],
        }
        if len(problem_cases) == expected_cases and not incomplete_case_rows:
            problems.append(result)
        else:
            partial_problems.append(result)

    complete_problem_names = {row["problem"] for row in problems}
    unresolved_statuses = [
        row for row in statuses if row["problem"] not in complete_problem_names
    ]
    example_case: dict[str, Any] | None = None
    if cases:
        case = cases[0]
        ordered = sorted(
            grouped[(case["problem"], case["case_hash"])],
            key=lambda row: int(row["measurement_iteration"]),
        )
        example_case = {
            "case_row": case,
            "measurement_rows": [
                {
                    "measurement_iteration": int(row["measurement_iteration"]),
                    "batch_calls": int(row["batch_calls"]),
                    "batch_wall_ms": row.get("batch_wall_ms"),
                    "cpu_energy_j": row.get("cpu_energy_j"),
                    "wall_ms_per_call": row.get("wall_ms_per_call"),
                    "cpu_energy_j_per_call": row.get("cpu_energy_j_per_call"),
                    "mean_cpu_w": row.get("mean_cpu_w"),
                    "powermetrics_samples": row.get("powermetrics_samples"),
                    "powermetrics_sampled_ms": row.get("powermetrics_sampled_ms"),
                    "powermetrics_sample_coverage": row.get(
                        "powermetrics_sample_coverage"
                    ),
                }
                for row in ordered
            ],
        }

    return {
        "schema_version": 2,
        "benchmark": "leetcode-energy-casewise",
        "input": str(input_path),
        "model_slug": (
            measured[0]["model_slug"]
            if measured
            else statuses[0]["model_slug"]
            if statuses
            else None
        ),
        "language": (
            measured[0]["language"]
            if measured
            else statuses[0]["language"]
            if statuses
            else None
        ),
        "energy_source": "powermetrics-cpu",
        "measurement_protocol": {
            "warmup_seconds": measured[0]["warmup_seconds"] if measured else None,
            "measurement_iterations_per_case": expected_measurements,
            "batch_target_seconds": measured[0]["batch_target_s"] if measured else None,
            "powermetrics_interval_ms": measured[0]["powermetrics_interval_ms"]
            if measured
            else None,
            "case_statistic": "median of normalized per-call values across measurement iterations",
            "problem_statistic": "median of case medians",
        },
        "measurement_rows": len(measured),
        "status_rows": statuses,
        "unresolved_status_rows": unresolved_statuses,
        "skipped_problems": len(
            {
                row["problem"]
                for row in unresolved_statuses
                if row.get("status", "").startswith("skipped_")
            }
        ),
        "failed_problems": len(
            {
                row["problem"]
                for row in unresolved_statuses
                if row.get("status", "").startswith("failed_")
            }
        ),
        "complete_cases": len(cases),
        "incomplete_cases": incomplete,
        "measured_problems": len(problems),
        "partial_problems": partial_problems,
        "model_median_problem_energy_j": (
            _median([row["median_case_cpu_energy_j"] for row in problems])
            if problems
            else None
        ),
        "example_case": example_case,
        "cases": cases,
        "problems": problems,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(summary: dict[str, Any], prefix: Path) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    stem = prefix.name.removesuffix("_summary")
    _write_csv(prefix.parent / f"{stem}_cases.csv", summary["cases"])
    _write_csv(prefix.parent / f"{stem}_problems.csv", summary["problems"])
    protocol = summary["measurement_protocol"]

    def fmt(value: Any, precision: int = 6) -> str:
        if value is None:
            return "n/a"
        try:
            return f"{float(value):.{precision}g}"
        except (TypeError, ValueError):
            return str(value)

    lines = [
        "# Python Per-Test-Case LeetCode Energy Results",
        "",
        "## Run Summary",
        "",
        f"- Model: `{summary['model_slug']}`",
        f"- Complete cases: **{summary['complete_cases']}**",
        f"- Incomplete cases: **{len(summary['incomplete_cases'])}**",
        f"- Measured problems: **{summary['measured_problems']}**",
        f"- Measurement rows: **{summary['measurement_rows']}**",
        f"- Skipped problems: **{summary['skipped_problems']}**",
        f"- Failed/resumable problems: **{summary['failed_problems']}**",
        f"- Warmup: **{protocol['warmup_seconds']} seconds per problem**",
        f"- Measurements: **{protocol['measurement_iterations_per_case']} per case**",
        f"- Target batch duration: **{protocol['batch_target_seconds']} second(s)**",
        f"- Powermetrics interval: **{protocol['powermetrics_interval_ms']} ms**",
        "- Primary metric: direct `powermetrics` CPU energy on this Mac.",
        "",
        "## Problem Results",
        "",
        "Each problem value is the median of its completed case medians.",
        "",
        "| Problem | Cases | Median case wall (ms) | Median case CPU energy (J) | Median case CV | Warmup stable |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(
        summary["problems"],
        key=lambda value: value["median_case_cpu_energy_j"],
        reverse=True,
    ):
        lines.append(
            f"| `{row['problem']}` | {row['case_count']} | "
            f"{row['median_case_wall_ms']:.6f} | "
            f"{row['median_case_cpu_energy_j']:.9f} | "
            f"{row['median_case_energy_cv']:.4f} | "
            f"{'yes' if row['warmup_stable'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## How One Case Is Measured",
            "",
            "For each accepted problem, the runner follows this exact timeline:",
            "",
            "1. Load the accepted Python source and the curated workload JSON.",
            "2. Start one persistent Python worker for the problem. Import time and",
            "   worker startup are outside the measured case batches.",
            "3. Validate the solution against the complete curated workload. If",
            "   validation fails, the problem is skipped and no energy rows are",
            "   recorded.",
            "4. Start one privileged `/usr/bin/powermetrics` process for the problem.",
            "   This happens after validation and before warmup. The sampler remains",
            "   active through warmup, calibration, and all measured batches for that",
            "   problem, then stops after the problem finishes.",
            f"5. Warm the worker for {protocol['warmup_seconds']} seconds by repeatedly",
            "   sweeping all unchanged cases once each.",
            "6. Calibrate every case to choose `batch_calls`, the fixed number of",
            "   repeated invocations used for one measured batch.",
            f"7. Run {protocol['measurement_iterations_per_case']} deterministic shuffled",
            "   measurement rounds. In each round, every case appears once.",
            "8. For each case in each round, execute exactly one measured batch:",
            "   `batch_calls` repeated calls to the same unchanged case.",
            "9. After the batch ends, collect the powermetrics samples whose sample",
            "   windows fall fully inside that batch's start and end timestamps.",
            "10. If fewer than five complete nominal thermal samples are available,",
            "    retry that batch. Otherwise, integrate the samples and checkpoint one",
            "    JSONL measurement row.",
            "11. After all ten rows exist for a case, summarize that case by taking",
            "    medians across its ten normalized rows.",
            "",
            "A batch is not a larger test case. It is many repeated calls to the",
            "same unchanged curated case inside one measured window. Very fast cases",
            "can require millions of calls per batch. If calibration picks",
            "`batch_calls = 2,000,000`, then ten measured batches means",
            "20,000,000 measured calls for that one case, plus extra validation,",
            "warmup, and calibration calls that are not included in the reported",
            "median.",
            "",
            "`batch_calls` is determined separately for each case. The worker first",
            "uses warmup timings for one call of that case, takes their median as an",
            "initial per-call estimate, and computes:",
            "",
            "```text",
            "initial_batch_calls = ceil(target_batch_seconds / estimated_seconds_per_call)",
            "```",
            "",
            "It then runs a pilot batch. If the pilot is still shorter than the target",
            "duration, it scales `batch_calls` upward and retries, up to five pilot",
            "attempts. The final `batch_calls` value is then fixed for all ten",
            "measurement rows for that case.",
            "",
            "Example: if one case is calibrated to 2,000,000 calls and a measured",
            "batch takes 1.2 seconds and 6 joules, that row records:",
            "",
            "```text",
            "wall_ms_per_call      = 1200 ms / 2,000,000 = 0.0006 ms",
            "cpu_energy_per_call   = 6 J / 2,000,000 = 0.000003 J",
            "```",
            "",
            f"The reported case result is the median of {protocol['measurement_iterations_per_case']} normalized rows.",
            "The reported problem result is the median of its case medians.",
            "",
            "The median rollup is therefore:",
            "",
            "```text",
            "one JSONL row = one measured batch for one case in one round",
            "one case CSV row = median of the 10 JSONL rows for that case",
            "one problem CSV row = median of all case CSV medians for that problem",
            "one model score = median of completed problem medians",
            "```",
            "",
            "## Concrete Casewise CSV Example",
            "",
        ]
    )
    example = summary.get("example_case")
    if example:
        case = example["case_row"]
        lines.extend(
            [
                "This example is one actual row from `python_casewise_cases.csv`.",
                "",
                f"- `problem`: `{case['problem']}`",
                f"- `case_index`: `{case['case_index']}`",
                f"- `case_hash`: `{case['case_hash']}`",
                f"- `batch_calls`: `{case['batch_calls']}`",
                f"- `measurement_rows`: `{case['measurement_rows']}`",
                f"- `median_wall_ms_per_call`: `{fmt(case['median_wall_ms_per_call'], 12)}`",
                f"- `median_cpu_energy_j_per_call`: `{fmt(case['median_cpu_energy_j_per_call'], 12)}`",
                f"- `energy_cv`: `{fmt(case['energy_cv'], 8)}`",
                "",
                "`case_index` is the zero-based position of the case in the curated",
                "workload file for that problem. It is useful for locating the case by",
                "eye. `case_hash` is the content-derived identifier used for fair",
                "cross-model matching, because it follows the case content even if file",
                "ordering ever changes.",
                "",
                "The ten underlying measurement rows for this case were:",
                "",
                "| Iteration | Batch calls | Batch wall (ms) | Sampled ms | Coverage | Batch CPU energy (J) | Wall ms/call | CPU J/call | Samples |",
                "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in example["measurement_rows"]:
            lines.append(
                f"| {row['measurement_iteration']} | {row['batch_calls']} | "
                f"{fmt(row['batch_wall_ms'], 10)} | "
                f"{fmt(row['powermetrics_sampled_ms'], 8)} | "
                f"{fmt(row['powermetrics_sample_coverage'], 6)} | "
                f"{fmt(row['cpu_energy_j'], 10)} | "
                f"{fmt(row['wall_ms_per_call'], 10)} | "
                f"{fmt(row['cpu_energy_j_per_call'], 10)} | "
                f"{fmt(row['powermetrics_samples'], 4)} |"
            )
        lines.extend(
            [
                "",
                "The case CSV row is populated from those ten rows:",
                "",
                f"- `median_wall_ms_per_call` is the median of the ten `Wall ms/call` values: `{fmt(case['median_wall_ms_per_call'], 12)}`.",
                f"- `median_cpu_energy_j_per_call` is the median of the ten `CPU J/call` values: `{fmt(case['median_cpu_energy_j_per_call'], 12)}`.",
                "- `min_*` and `max_*` columns are the minimum and maximum of the same ten normalized values.",
                f"- `energy_cv` is the sample standard deviation divided by the mean across the ten `CPU J/call` values: `{fmt(case['energy_cv'], 8)}`.",
                f"- `median_powermetrics_samples` is the median sample count across the ten batches: `{fmt(case['median_powermetrics_samples'], 4)}`.",
                "",
                "Why does this example show 8 samples instead of about 10? The sampler",
                "interval is 100 ms, so a one-second batch might appear to allow about",
                "ten samples. However, powermetrics runs continuously and its sample",
                "windows are not synchronized to the exact batch boundaries. The runner",
                "only integrates sample windows that are fully inside the batch. The",
                "first and last sampler windows usually overlap the batch boundary and",
                "are excluded. In this example, each approximately 1.01 second batch",
                "contains about 870-876 ms of fully enclosed powermetrics sample windows,",
                "which gives 8 complete samples. This is why the table records `Samples",
                "= 8` and `Coverage` around 0.86.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "No completed case was available, so no concrete case example could be generated.",
                "",
            ]
        )
    lines.extend(
        [
            "## Powermetrics Method",
            "",
            "The runner starts one privileged `/usr/bin/powermetrics` process per",
            "problem using the `cpu_power`, `gpu_power`, `ane_power`, and `thermal`",
            f"samplers at {protocol['powermetrics_interval_ms']} ms. The sampler runs",
            "continuously while all cases for that problem are measured. Raw sampler",
            "output is stored as a NUL-delimited plist stream and compressed only",
            "after the problem finishes, so compression is outside the measured",
            "windows.",
            "",
            "For each measured batch, only samples whose windows fall fully inside",
            "the batch start and end timestamps are integrated. Samples overlapping",
            "the start or end boundary are discarded to avoid attributing energy from",
            "outside the case batch. CPU energy is calculated as:",
            "",
            "```text",
            "sample_energy_j = sample_cpu_power_w * sample_elapsed_seconds",
            "batch_cpu_energy_j = sum(sample_energy_j for included samples)",
            "cpu_energy_j_per_call = batch_cpu_energy_j / batch_calls",
            "```",
            "",
            "`powermetrics_samples` is the count of included complete sample windows.",
            "`powermetrics_sampled_ms` is the total duration of those included",
            "windows. `powermetrics_sample_coverage` is sampled duration divided by",
            "the measured batch wall time. A row is kept only when at least five valid",
            "samples are available and thermal pressure is nominal. GPU and ANE energy",
            "are retained as supporting metadata, but CPU energy per call is the",
            "primary metric.",
            "",
            "## CSV Outputs",
            "",
            "`python_casewise_cases.csv` has one row per completed problem case.",
            "Each row is calculated from the ten retained measurement batches for",
            "that exact `(problem, case_hash)` pair.",
            "",
            "| Column | How it is populated |",
            "|---|---|",
            "| `problem` | LeetCode title slug. |",
            "| `case_index` | Zero-based position of the case inside the curated workload file. It lets you locate the exact case in `leetcode-energy/reference/workloads/<slug>.json`. |",
            "| `case_hash` | Content hash of the case input and expected output, used for cross-model matching. |",
            "| `measurement_rows` | Number of retained measured batches for the case. Complete cases have 10. |",
            "| `batch_calls` | Fixed invocation count selected during calibration for this case. The same value is used for all ten measured batches for the case. |",
            "| `median_wall_ms_per_call` | Median of ten `batch_wall_ms / batch_calls` values. |",
            "| `min_wall_ms_per_call` | Minimum normalized wall-time value across the ten batches. |",
            "| `max_wall_ms_per_call` | Maximum normalized wall-time value across the ten batches. |",
            "| `median_cpu_energy_j_per_call` | Median of ten `batch_cpu_energy_j / batch_calls` values. This is the case energy score. |",
            "| `min_cpu_energy_j_per_call` | Minimum normalized CPU-energy value across the ten batches. |",
            "| `max_cpu_energy_j_per_call` | Maximum normalized CPU-energy value across the ten batches. |",
            "| `energy_cv` | Coefficient of variation of the ten normalized CPU-energy values: sample standard deviation divided by mean. |",
            "| `median_cpu_power_w` | Median of the ten batch mean CPU power values. |",
            "| `median_powermetrics_samples` | Median number of included powermetrics samples per batch. |",
            "| `warmup_stable` | True when the final two 10-second warmup windows differ by no more than 5%. |",
            "| `workload_hash` | Hash of the curated workload file. |",
            "| `source_hash` | Hash of the measured accepted Python source file. |",
            "",
            "`python_casewise_problems.csv` has one row per completed problem. It",
            "is calculated from the case CSV rows.",
            "",
            "| Column | How it is populated |",
            "|---|---|",
            "| `problem` | LeetCode title slug. |",
            "| `case_count` | Number of completed case rows included for the problem. |",
            "| `expected_case_count` | Number of cases in the curated workload. The problem is complete only when this matches `case_count`. |",
            "| `median_case_wall_ms` | Median of `median_wall_ms_per_call` across the problem's completed cases. |",
            "| `median_case_cpu_energy_j` | Median of `median_cpu_energy_j_per_call` across completed cases. This is the problem energy score. |",
            "| `median_case_energy_cv` | Median of case-level `energy_cv` values. |",
            "| `max_case_energy_cv` | Largest case-level `energy_cv`, useful for finding noisy cases. |",
            "| `warmup_stable` | True only if the problem warmup was stable. |",
            "| `workload_hash` | Hash of the curated workload file. |",
            "",
            "## Interpretation",
            "",
            "The curated inputs and expected outputs are unchanged. Repetition extends the",
            "measurement window without creating larger synthetic inputs. Values represent",
            "machine-wide CPU energy during the case batch and are appropriate for controlled",
            "same-device comparisons, not comparisons between different Macs.",
            "",
        ]
    )
    prefix.with_suffix(".md").write_text("\n".join(lines))


def compare_models(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if len(summaries) < 2:
        raise ValueError("at least two casewise model summaries are required")
    case_maps = {
        summary["model_slug"]: {
            (row["problem"], row["case_hash"]): row
            for row in summary["cases"]
            if "problems" not in summary
            or row["problem"] in {problem["problem"] for problem in summary["problems"]}
        }
        for summary in summaries
    }
    common = set.intersection(*(set(rows) for rows in case_maps.values()))
    if not common:
        raise ValueError("the selected models have no completed cases in common")
    common_problems = sorted({problem for problem, _ in common})
    models: list[dict[str, Any]] = []
    for model_slug, rows in sorted(case_maps.items()):
        problem_scores: list[dict[str, Any]] = []
        for problem in common_problems:
            matched = [rows[key] for key in common if key[0] == problem]
            problem_scores.append(
                {
                    "problem": problem,
                    "cases": len(matched),
                    "median_case_cpu_energy_j": _median(
                        [row["median_cpu_energy_j_per_call"] for row in matched]
                    ),
                    "median_case_wall_ms": _median(
                        [row["median_wall_ms_per_call"] for row in matched]
                    ),
                }
            )
        models.append(
            {
                "model_slug": model_slug,
                "common_problems": len(problem_scores),
                "common_cases": len(common),
                "median_problem_cpu_energy_j": _median(
                    [row["median_case_cpu_energy_j"] for row in problem_scores]
                ),
                "median_problem_wall_ms": _median(
                    [row["median_case_wall_ms"] for row in problem_scores]
                ),
                "problems": problem_scores,
            }
        )
    return {
        "schema_version": 1,
        "benchmark": "leetcode-energy-casewise-comparison",
        "common_intersection": True,
        "common_problems": len(common_problems),
        "common_cases": len(common),
        "models": sorted(models, key=lambda row: row["median_problem_cpu_energy_j"]),
    }


def comparison_prefix(root: Path, model_slugs: list[str], language: str) -> Path:
    digest = hashlib.sha256("\n".join(sorted(model_slugs)).encode()).hexdigest()[:12]
    return root / "comparisons" / f"{language}_{digest}"


def write_comparison(comparison: dict[str, Any], prefix: Path) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".json").write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n"
    )
    flat = [
        {key: value for key, value in row.items() if key != "problems"}
        for row in comparison["models"]
    ]
    _write_csv(prefix.with_suffix(".csv"), flat)
    lines = [
        "# LeetCode Casewise Model Comparison",
        "",
        f"Common intersection: **{comparison['common_problems']} problems, {comparison['common_cases']} cases**.",
        "",
        "| Rank | Model | Median problem CPU energy (J) | Median problem wall (ms) |",
        "|---:|---|---:|---:|",
    ]
    for index, row in enumerate(comparison["models"], start=1):
        lines.append(
            f"| {index} | `{row['model_slug']}` | "
            f"{row['median_problem_cpu_energy_j']:.9f} | "
            f"{row['median_problem_wall_ms']:.6f} |"
        )
    prefix.with_suffix(".md").write_text("\n".join(lines) + "\n")
