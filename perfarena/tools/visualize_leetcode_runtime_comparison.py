"""Compare local casewise energy with PerfArena LeetCode runtime metadata."""

from __future__ import annotations

import csv
import html
import json
import math
import statistics
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .visualize_leetcode_casewise import log_position


RuntimeFetcher = Callable[[], Iterable[dict[str, Any]]]


def snapshot_path(root: Path, language: str) -> Path:
    return root / f"{language}_leetcode_runtime_snapshot.json"


def report_path(root: Path, language: str) -> Path:
    return root / f"{language}_casewise_leetcode_comparison.html"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def load_local_problems(root: Path, language: str) -> list[dict[str, str]]:
    problems_path = root / f"{language}_casewise_problems.csv"
    summary_path = root / f"{language}_casewise_summary.json"
    missing = [path for path in (problems_path, summary_path) if not path.exists()]
    if missing:
        joined = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(f"missing required casewise files:\n{joined}")
    problems = _read_csv(problems_path)
    if not problems:
        raise ValueError("casewise problem CSV contains no rows")
    return problems


def _runtime_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "problem_slug": row.get("problem_slug"),
        "problem_title": row.get("problem_title") or row.get("problem_slug"),
        "problem_level": row.get("problem_level"),
        "runtime_ms": row.get("runtime_ms"),
        "runtime_percentile": row.get("runtime_percentile"),
        "total_correct": row.get("total_correct"),
        "total_testcases": row.get("total_testcases"),
        "submission_id": row.get("submission_id"),
        "submitted_at": row.get("submitted_at"),
    }


def normalize_runtime_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one deterministic accepted runtime row per problem slug."""
    by_slug: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = _runtime_projection(raw)
        slug = row["problem_slug"]
        runtime = row["runtime_ms"]
        if not slug or runtime is None or not math.isfinite(float(runtime)):
            continue
        if float(runtime) <= 0:
            continue
        current = by_slug.get(str(slug))
        candidate_key = (str(row.get("submitted_at") or ""), int(row.get("submission_id") or 0))
        current_key = (
            str(current.get("submitted_at") or ""),
            int(current.get("submission_id") or 0),
        ) if current else ("", 0)
        if current is None or candidate_key > current_key:
            by_slug[str(slug)] = row
    return [by_slug[slug] for slug in sorted(by_slug)]


def load_or_fetch_snapshot(
    path: Path,
    *,
    base_url: str,
    model: str,
    language: str,
    fetcher: RuntimeFetcher,
    refresh: bool = False,
) -> dict[str, Any]:
    if path.exists() and not refresh:
        data = json.loads(path.read_text())
        if not isinstance(data.get("rows"), list):
            raise ValueError(f"invalid runtime snapshot: {path}")
        return data

    rows = normalize_runtime_rows(fetcher())
    if not rows:
        raise ValueError(f"no accepted runtime rows found for model {model!r}")
    data = {
        "schema_version": 1,
        "source": f"{base_url.rstrip('/')}/api/datasets/solutions",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "language": language,
        "rows": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data


def average_ranks(values: list[float]) -> list[float]:
    """Return ascending ranks, assigning tied values their average rank."""
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        stop = index + 1
        while stop < len(indexed) and indexed[stop][1] == indexed[index][1]:
            stop += 1
        rank = ((index + 1) + stop) / 2
        for original_index, _ in indexed[index:stop]:
            ranks[original_index] = rank
        index = stop
    return ranks


def spearman(values_a: list[float], values_b: list[float]) -> float | None:
    if len(values_a) != len(values_b):
        raise ValueError("Spearman inputs must have the same length")
    if len(values_a) < 2:
        return None
    ranks_a = average_ranks(values_a)
    ranks_b = average_ranks(values_b)
    mean_a = statistics.mean(ranks_a)
    mean_b = statistics.mean(ranks_b)
    numerator = sum((a - mean_a) * (b - mean_b) for a, b in zip(ranks_a, ranks_b))
    denominator = math.sqrt(
        sum((a - mean_a) ** 2 for a in ranks_a)
        * sum((b - mean_b) ** 2 for b in ranks_b)
    )
    return numerator / denominator if denominator else None


def join_problem_rows(
    local_rows: list[dict[str, str]], runtime_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    local = {row["problem"]: row for row in local_rows}
    remote = {str(row["problem_slug"]): row for row in runtime_rows}
    shared = sorted(set(local) & set(remote))
    if not shared:
        raise ValueError("local energy and LeetCode runtime data have no overlapping problems")

    rows: list[dict[str, Any]] = []
    for slug in shared:
        left, right = local[slug], remote[slug]
        rows.append(
            {
                "problem": slug,
                "title": right.get("problem_title") or slug,
                "difficulty": right.get("problem_level") or "Unknown",
                "leetcode_runtime_ms": float(right["runtime_ms"]),
                "runtime_percentile": right.get("runtime_percentile"),
                "total_testcases": right.get("total_testcases"),
                "case_count": int(float(left["case_count"])),
                "local_wall_ms_per_call": float(left["median_case_wall_ms"]),
                "local_energy_j_per_call": float(left["median_case_cpu_energy_j"]),
            }
        )

    runtime_ranks = average_ranks([row["leetcode_runtime_ms"] for row in rows])
    energy_ranks = average_ranks([row["local_energy_j_per_call"] for row in rows])
    wall_ranks = average_ranks([row["local_wall_ms_per_call"] for row in rows])
    for row, runtime_rank, energy_rank, wall_rank in zip(
        rows, runtime_ranks, energy_ranks, wall_ranks
    ):
        row["leetcode_runtime_rank"] = runtime_rank
        row["local_energy_rank"] = energy_rank
        row["local_wall_rank"] = wall_rank
        row["energy_rank_difference"] = energy_rank - runtime_rank

    return {
        "rows": rows,
        "local_count": len(local),
        "runtime_count": len(remote),
        "overlap_count": len(rows),
        "local_only": sorted(set(local) - set(remote)),
        "runtime_only": sorted(set(remote) - set(local)),
        "runtime_wall_spearman": spearman(
            [row["leetcode_runtime_ms"] for row in rows],
            [row["local_wall_ms_per_call"] for row in rows],
        ),
        "runtime_energy_spearman": spearman(
            [row["leetcode_runtime_ms"] for row in rows],
            [row["local_energy_j_per_call"] for row in rows],
        ),
    }


def _ticks(minimum: float, maximum: float) -> list[float]:
    return [
        10**power
        for power in range(math.floor(math.log10(minimum)), math.ceil(math.log10(maximum)) + 1)
    ]


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def _scatter(rows: list[dict[str, Any]], y_key: str, y_label: str, color: str) -> str:
    xs = [row["leetcode_runtime_ms"] for row in rows]
    ys = [row[y_key] for row in rows]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    width, height = 920, 560
    left, right, top, bottom = 92, 28, 28, 72
    plot_w, plot_h = width - left - right, height - top - bottom

    def x(value: float) -> float:
        return log_position(value, xmin, xmax, left, left + plot_w)

    def y(value: float) -> float:
        return log_position(value, ymin, ymax, top + plot_h, top)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode runtime versus {html.escape(y_label)}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f2937"/>',
    ]
    for tick in _ticks(xmin, xmax):
        tx = x(tick)
        parts.append(f'<line x1="{tx:.2f}" y1="{top}" x2="{tx:.2f}" y2="{top + plot_h}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{tx:.2f}" y="{top + plot_h + 21}" text-anchor="middle" font-size="11">{_fmt(tick)} ms</text>')
    for tick in _ticks(ymin, ymax):
        ty = y(tick)
        parts.append(f'<line x1="{left}" y1="{ty:.2f}" x2="{left + plot_w}" y2="{ty:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 8}" y="{ty + 4:.2f}" text-anchor="end" font-size="11">{_fmt(tick)}</text>')
    for row in rows:
        label = html.escape(
            f'{row["problem"]}: LeetCode {row["leetcode_runtime_ms"]:.4g} ms; local {_fmt(row[y_key])}'
        )
        parts.append(
            f'<circle cx="{x(row["leetcode_runtime_ms"]):.2f}" cy="{y(row[y_key]):.2f}" '
            f'r="5" fill="{color}" opacity="0.75"><title>{label}</title></circle>'
        )
    parts.append(f'<text x="{left + plot_w / 2:.2f}" y="{height - 18}" text-anchor="middle" font-size="12">LeetCode runtime (ms, log scale)</text>')
    parts.append(f'<text x="20" y="{top + plot_h / 2:.2f}" transform="rotate(-90 20 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12">{html.escape(y_label)} (log scale)</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _rank_chart(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: abs(row["energy_rank_difference"]), reverse=True)
    width = 1050
    left, right, top, row_h = 350, 50, 52, 27
    height = top + len(ordered) * row_h + 50
    plot_w = width - left - right
    count = len(rows)

    def x(rank: float) -> float:
        return left + ((rank - 1) / max(1, count - 1)) * plot_w

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="LeetCode runtime and local energy rank comparison">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        '<circle cx="360" cy="21" r="5" fill="#2563eb"/><text x="372" y="25" font-size="11">LeetCode runtime rank</text>',
        '<circle cx="560" cy="21" r="5" fill="#dc2626"/><text x="572" y="25" font-size="11">Local energy rank</text>',
    ]
    for rank in (1, max(1, round(count / 2)), count):
        tx = x(rank)
        parts.append(f'<line x1="{tx:.2f}" y1="{top - 8}" x2="{tx:.2f}" y2="{height - 30}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{tx:.2f}" y="{top - 14}" text-anchor="middle" font-size="10">rank {rank}</text>')
    for index, row in enumerate(ordered):
        y = top + index * row_h
        runtime_x = x(row["leetcode_runtime_rank"])
        energy_x = x(row["local_energy_rank"])
        parts.append(f'<text x="{left - 10}" y="{y + 5}" text-anchor="end" font-size="10">{html.escape(row["problem"])}</text>')
        parts.append(f'<line x1="{runtime_x:.2f}" y1="{y}" x2="{energy_x:.2f}" y2="{y}" stroke="#94a3b8" stroke-width="2"/>')
        parts.append(f'<circle cx="{runtime_x:.2f}" cy="{y}" r="5" fill="#2563eb"><title>LeetCode rank {row["leetcode_runtime_rank"]:.1f}</title></circle>')
        parts.append(f'<circle cx="{energy_x:.2f}" cy="{y}" r="5" fill="#dc2626"><title>Local energy rank {row["local_energy_rank"]:.1f}</title></circle>')
    parts.append("</svg>")
    return "\n".join(parts)


def _slug_list(values: list[str]) -> str:
    if not values:
        return "<p>None.</p>"
    return '<div class="slug-list">' + "".join(
        f"<code>{html.escape(value)}</code>" for value in values
    ) + "</div>"


def _correlation(value: float | None) -> str:
    return "not defined" if value is None else f"{value:.3f}"


def _table(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: row["leetcode_runtime_ms"], reverse=True)
    body: list[str] = []
    for row in ordered:
        percentile = row["runtime_percentile"]
        tests = row["total_testcases"]
        body.append(
            "<tr>"
            f'<td><code>{html.escape(row["problem"])}</code></td>'
            f'<td>{html.escape(str(row["difficulty"]))}</td>'
            f'<td class="num">{row["leetcode_runtime_ms"]:.4g}</td>'
            f'<td class="num">{"-" if percentile is None else f"{float(percentile):.2f}%"}</td>'
            f'<td class="num">{"-" if tests is None else int(tests)}</td>'
            f'<td class="num">{row["case_count"]}</td>'
            f'<td class="num">{row["local_wall_ms_per_call"]:.6g}</td>'
            f'<td class="num">{row["local_energy_j_per_call"]:.6g}</td>'
            f'<td class="num">{row["leetcode_runtime_rank"]:.1f}</td>'
            f'<td class="num">{row["local_energy_rank"]:.1f}</td>'
            f'<td class="num">{row["energy_rank_difference"]:+.1f}</td>'
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Problem</th><th>Difficulty</th><th>LC runtime ms</th>"
        "<th>LC runtime %ile</th><th>LC testcases</th><th>Local cases</th>"
        "<th>Local wall ms/call</th><th>Local CPU J/call</th>"
        "<th>LC rank</th><th>Energy rank</th><th>Rank difference</th>"
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def render_report(data: dict[str, Any], snapshot: dict[str, Any]) -> str:
    rows = data["rows"]
    model = str(snapshot.get("model") or "unknown")
    fetched_at = str(snapshot.get("fetched_at") or "unknown")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(model)} Energy vs LeetCode Runtime</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #172033; background: #f6f8fb; }}
body {{ margin: 0; }} main {{ max-width: 1220px; margin: 0 auto; padding: 34px 24px 70px; }}
h1 {{ margin-bottom: 5px; }} h2 {{ margin-top: 34px; }} .muted {{ color: #5f6b7a; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 12px; margin: 22px 0; }}
.card, .panel, .note {{ background: white; border: 1px solid #dfe5ec; border-radius: 8px; padding: 16px; }}
.card .label {{ color: #64748b; font-size: 12px; text-transform: uppercase; }} .card .value {{ font-size: 25px; font-weight: 700; margin-top: 4px; }}
.panel {{ margin: 12px 0 26px; overflow-x: auto; }} .note {{ border-color: #f59e0b; background: #fffbeb; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
.slug-list {{ display: flex; flex-wrap: wrap; gap: 7px; }} code {{ background: #eef2ff; padding: 2px 5px; border-radius: 4px; }}
.table-wrap {{ overflow-x: auto; }} table {{ width: 100%; border-collapse: collapse; background: white; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px 9px; text-align: left; white-space: nowrap; }} th {{ position: sticky; top: 0; background: #f8fafc; }} .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
svg text {{ fill: #111827; }}
</style>
</head>
<body><main>
<h1>{html.escape(model)}: Local Energy vs LeetCode Runtime</h1>
<p class="muted">Exploratory problem-level comparison. PerfArena runtime snapshot fetched {html.escape(fetched_at)}.</p>
<section class="cards">
<div class="card"><div class="label">Local measured</div><div class="value">{data["local_count"]}</div></div>
<div class="card"><div class="label">PerfArena accepted</div><div class="value">{data["runtime_count"]}</div></div>
<div class="card"><div class="label">Overlapping slugs</div><div class="value">{data["overlap_count"]}</div></div>
<div class="card"><div class="label">Runtime vs local wall rho</div><div class="value">{_correlation(data["runtime_wall_spearman"])}</div></div>
<div class="card"><div class="label">Runtime vs local energy rho</div><div class="value">{_correlation(data["runtime_energy_spearman"])}</div></div>
</section>

<section class="note"><strong>Important limitation:</strong> rows are paired by problem slug and model name, not by source hash. The currently hosted accepted Gemma code revisions do not exactly match the source revisions used in the completed energy run. LeetCode also uses hidden workloads and different machines, harnesses, and testcase sizes. Treat correlation and rank agreement as context only; absolute times and Joules are not directly equivalent, and LeetCode runtime is not divided by testcase count.</section>

<h2>LeetCode Runtime vs Local Wall Time</h2>
<p class="muted">Each point is one overlapping problem. Both axes are logarithmic. Local wall time is the median of that problem's case-level median time per call.</p>
<div class="panel">{_scatter(rows, "local_wall_ms_per_call", "Local median wall time per call (ms)", "#2563eb")}</div>

<h2>LeetCode Runtime vs Local CPU Energy</h2>
<p class="muted">Local energy is the median of the problem's case-level median CPU energy per call. Hover over a point to see its problem and values.</p>
<div class="panel">{_scatter(rows, "local_energy_j_per_call", "Local median CPU energy per call (J)", "#0f766e")}</div>

<h2>Runtime Rank vs Energy Rank</h2>
<p class="muted">Rank 1 is the lowest value. Problems are ordered by the absolute difference between their LeetCode-runtime rank and local-energy rank.</p>
<div class="panel">{_rank_chart(rows)}</div>

<h2>Matched Problem Data</h2>
<p class="muted">The testcase count is shown as metadata only. It is not used to normalize LeetCode runtime.</p>
<div class="panel">{_table(rows)}</div>

<h2>Coverage</h2>
<div class="grid">
<section class="panel"><h3>Measured locally, absent from hosted Gemma accepted rows ({len(data["local_only"])})</h3>{_slug_list(data["local_only"])}</section>
<section class="panel"><h3>Hosted Gemma accepted rows, not measured locally ({len(data["runtime_only"])})</h3>{_slug_list(data["runtime_only"])}</section>
</div>

<h2>How To Interpret The Correlations</h2>
<div class="panel"><p>Spearman's rho compares ordering rather than units. A value near +1 means problems that rank slower on LeetCode also tend to rank slower or more energy-intensive locally. A value near 0 indicates little rank agreement. It does not establish that the two systems measured the same workload or code revision.</p></div>
</main></body></html>
"""


def write_report(
    root: Path,
    language: str,
    snapshot: dict[str, Any],
    output: Path | None = None,
) -> Path:
    local_rows = load_local_problems(root, language)
    comparison = join_problem_rows(local_rows, snapshot["rows"])
    out = output or report_path(root, language)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(comparison, snapshot))
    return out
