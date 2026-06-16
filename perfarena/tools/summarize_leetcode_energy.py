"""Summarize a curated LeetCode energy JSONL trace."""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _median(values: list[float]) -> float:
    return round(statistics.median(values), 6)


def summarize(input_path: Path, summaries_root: Path) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in input_path.read_text().splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["test"]].append(row)

    problems: list[dict[str, Any]] = []
    for slug, problem_rows in sorted(grouped.items()):
        phases = Counter(row["phase"] for row in problem_rows)
        measured = [row for row in problem_rows if row["phase"] == "measure"]
        energies = [float(row["rapl_pkg_delta_raw"]) for row in measured]
        walls = [float(row["wall_ms"]) for row in measured]
        median_energy = statistics.median(energies)
        problems.append(
            {
                "problem": slug,
                "workload_cases": measured[0]["workload_cases"],
                "case_repeat": measured[0]["case_repeat"],
                "idle_rows": phases["idle"],
                "warmup_rows": phases["warmup"],
                "measurement_rows": phases["measure"],
                "median_wall_ms": _median(walls),
                "min_wall_ms": round(min(walls), 6),
                "max_wall_ms": round(max(walls), 6),
                "median_energy_uj": round(median_energy),
                "median_energy_j": round(median_energy / 1_000_000, 6),
                "energy_cv": round(
                    statistics.stdev(energies) / statistics.mean(energies), 6
                )
                if len(energies) > 1 and statistics.mean(energies)
                else 0.0,
                "workload_hash": measured[0]["workload_hash"],
                "energy_source": measured[0]["energy_source"],
            }
        )

    model_slug = rows[0]["model_slug"] if rows else None
    skipped: list[dict[str, str]] = []
    for path in summaries_root.glob("*/energy_curated_*.json"):
        data = json.loads(path.read_text())
        if data.get("model_slug") == model_slug and not data.get("measured"):
            skipped.append(
                {
                    "problem": data["problem"],
                    "reason": data.get("skipped_reason", "unknown"),
                }
            )

    phase_counts = Counter(row["phase"] for row in rows)
    return {
        "schema_version": 1,
        "benchmark": "leetcode-energy-curated",
        "input": str(input_path),
        "model_slug": model_slug,
        "language": rows[0]["language"] if rows else None,
        "energy_source": sorted({row["energy_source"] for row in rows}),
        "measured_problems": len(problems),
        "skipped_accepted_problems": sorted(skipped, key=lambda row: row["problem"]),
        "total_workload_cases": sum(row["workload_cases"] for row in problems),
        "rows": len(rows),
        "phase_counts": dict(sorted(phase_counts.items())),
        "nonzero_exit_rows": sum(bool(row.get("exit_code")) for row in rows),
        "complete_problem_rows": sum(
            row["idle_rows"] == 1
            and row["warmup_rows"] == 3
            and row["measurement_rows"] == 10
            for row in problems
        ),
        "measurement_protocol": {
            "idle_seconds": 2,
            "warmup_iterations": 3,
            "measurement_iterations": 10,
            "case_repeat": 1,
        },
        "interpretation": {
            "energy_values": "raw CodeCarbon estimates in microjoules",
            "idle_adjustment": "not reported because estimated subtraction was negative",
            "short_workloads": "tracker and process startup overhead dominates many rows",
            "recommended_final_platform": "Linux host with direct RAPL access",
        },
        "problems": problems,
    }


def write_outputs(summary: dict[str, Any], output_prefix: Path) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    output_prefix.with_suffix(".json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    fields = [
        "problem",
        "workload_cases",
        "case_repeat",
        "measurement_rows",
        "median_wall_ms",
        "min_wall_ms",
        "max_wall_ms",
        "median_energy_uj",
        "median_energy_j",
        "energy_cv",
        "energy_source",
        "workload_hash",
    ]
    with output_prefix.with_suffix(".csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary["problems"])

    top_energy = sorted(
        summary["problems"], key=lambda row: row["median_energy_j"], reverse=True
    )[:10]
    lines = [
        "# Python Curated LeetCode Energy Results",
        "",
        "## Run Summary",
        "",
        f"- Measured accepted problems: **{summary['measured_problems']}**",
        f"- Skipped accepted problems: **{len(summary['skipped_accepted_problems'])}**",
        f"- Curated cases executed per full pass: **{summary['total_workload_cases']}**",
        f"- Measurement rows: **{summary['phase_counts'].get('measure', 0)}**",
        f"- Nonzero child exits: **{summary['nonzero_exit_rows']}**",
        "- Protocol: 2 s idle, 3 warmups, 10 measurements, one workload pass per child.",
        "- Backend: CodeCarbon on macOS; values are raw estimates.",
        "",
        "## Highest Raw Median Energy",
        "",
        "| Problem | Cases | Median wall (ms) | Median energy (J) | CV |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in top_energy:
        lines.append(
            f"| `{row['problem']}` | {row['workload_cases']} | "
            f"{row['median_wall_ms']:.3f} | {row['median_energy_j']:.3f} | "
            f"{row['energy_cv']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Skipped Accepted Problems",
            "",
        ]
    )
    for row in summary["skipped_accepted_problems"]:
        lines.append(f"- `{row['problem']}`: {row['reason']}.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The raw energy values include CodeCarbon tracker and Python process startup",
            "overhead. Most workloads complete in about 0.1 seconds, while CodeCarbon's",
            "tracking interval is substantially longer. Idle subtraction was rejected",
            "because it produced negative values on this machine. These results verify the",
            "pipeline and provide raw local estimates, but direct Linux RAPL measurements",
            "with longer repeated workloads are required for final cross-language claims.",
            "",
        ]
    )
    output_prefix.with_suffix(".md").write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--summaries-root", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    summary = summarize(args.input, args.summaries_root)
    write_outputs(summary, args.output_prefix)
    print(
        f"summarized {summary['measured_problems']} problems and "
        f"{summary['phase_counts'].get('measure', 0)} measurement rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
