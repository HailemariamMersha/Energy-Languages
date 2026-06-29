"""Static HTML/SVG visualizations for LeetCode casewise energy results."""

from __future__ import annotations

import csv
import html
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BoxStats:
    minimum: float
    q1: float
    median: float
    q3: float
    maximum: float


def quartiles(values: list[float]) -> BoxStats:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot compute quartiles for an empty list")
    n = len(ordered)
    median = statistics.median(ordered)
    if n == 1:
        return BoxStats(ordered[0], ordered[0], ordered[0], ordered[0], ordered[0])
    midpoint = n // 2
    lower = ordered[:midpoint]
    upper = ordered[midpoint:] if n % 2 == 0 else ordered[midpoint + 1 :]
    return BoxStats(
        minimum=ordered[0],
        q1=statistics.median(lower),
        median=median,
        q3=statistics.median(upper),
        maximum=ordered[-1],
    )


def log_position(value: float, minimum: float, maximum: float, start: float, end: float) -> float:
    if value <= 0 or minimum <= 0 or maximum <= 0:
        raise ValueError("log-scaled values must be positive")
    if maximum == minimum:
        return (start + end) / 2
    lo = math.log10(minimum)
    hi = math.log10(maximum)
    ratio = (math.log10(value) - lo) / (hi - lo)
    return start + ratio * (end - start)


def measurement_root(repo_root: Path, model_slug: str) -> Path:
    return repo_root / "perfarena_out" / "leetcode_measurements" / model_slug


def report_path(repo_root: Path, model_slug: str, language: str) -> Path:
    return measurement_root(repo_root, model_slug) / f"{language}_casewise_report.html"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _int(row: dict[str, str], key: str) -> int:
    return int(float(row[key]))


def _fmt_energy(value: float) -> str:
    if value >= 1e-3:
        return f"{value:.4g} J"
    return f"{value:.3e} J"


def _fmt_ms(value: float) -> str:
    if value >= 1:
        return f"{value:.3f} ms"
    return f"{value:.3e} ms"


def _slug_label(slug: str, limit: int = 30) -> str:
    label = slug.replace("-", " ")
    return label if len(label) <= limit else label[: limit - 1] + "…"


def _duration_from_summary_markdown(path: Path) -> str:
    md = path.with_suffix(".md")
    if not md.exists():
        return "not recorded"
    text = md.read_text()
    match = re.search(r"about \*\*([^*]+)\*\*", text)
    return match.group(1) if match else "not recorded"


def load_data(root: Path, language: str) -> dict[str, Any]:
    cases_path = root / f"{language}_casewise_cases.csv"
    problems_path = root / f"{language}_casewise_problems.csv"
    summary_path = root / f"{language}_casewise_summary.json"
    missing = [path for path in [cases_path, problems_path, summary_path] if not path.exists()]
    if missing:
        joined = "\n".join(f"  {path}" for path in missing)
        raise FileNotFoundError(f"missing required casewise files:\n{joined}")

    cases = _read_csv(cases_path)
    problems = _read_csv(problems_path)
    summary = json.loads(summary_path.read_text())
    return {
        "cases": cases,
        "problems": problems,
        "summary": summary,
        "duration": _duration_from_summary_markdown(summary_path),
        "root": root,
    }


def _axis_ticks(minimum: float, maximum: float) -> list[float]:
    start = math.floor(math.log10(minimum))
    stop = math.ceil(math.log10(maximum))
    return [10**power for power in range(start, stop + 1)]


def _box_plot(cases: list[dict[str, str]], problems: list[dict[str, str]]) -> str:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in cases:
        grouped[row["problem"]].append(_float(row, "median_cpu_energy_j_per_call"))
    ordered = sorted(
        [row["problem"] for row in problems],
        key=lambda slug: _float(
            next(problem for problem in problems if problem["problem"] == slug),
            "median_case_cpu_energy_j",
        ),
        reverse=True,
    )
    stats = {problem: quartiles(grouped[problem]) for problem in ordered}
    values = [value for vals in grouped.values() for value in vals]
    ymin, ymax = min(values), max(values)
    width = max(1180, 92 + len(ordered) * 28)
    height = 620
    left, right, top, bottom = 78, 24, 28, 190
    plot_w = width - left - right
    plot_h = height - top - bottom

    def y(value: float) -> float:
        return log_position(value, ymin, ymax, top + plot_h, top)

    step = plot_w / len(ordered)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Problem energy box plot">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#1f2937"/>',
    ]
    for tick in _axis_ticks(ymin, ymax):
        ty = y(tick)
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{ty:.2f}" y2="{ty:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 8}" y="{ty + 4:.2f}" text-anchor="end" font-size="11">{html.escape(_fmt_energy(tick))}</text>')
    for index, problem in enumerate(ordered):
        stat = stats[problem]
        x = left + step * index + step / 2
        box_w = max(7, min(18, step * 0.58))
        parts.extend(
            [
                f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{y(stat.minimum):.2f}" y2="{y(stat.maximum):.2f}" stroke="#64748b"/>',
                f'<line x1="{x - box_w / 2:.2f}" x2="{x + box_w / 2:.2f}" y1="{y(stat.minimum):.2f}" y2="{y(stat.minimum):.2f}" stroke="#64748b"/>',
                f'<line x1="{x - box_w / 2:.2f}" x2="{x + box_w / 2:.2f}" y1="{y(stat.maximum):.2f}" y2="{y(stat.maximum):.2f}" stroke="#64748b"/>',
                f'<rect x="{x - box_w / 2:.2f}" y="{y(stat.q3):.2f}" width="{box_w:.2f}" height="{max(1, y(stat.q1) - y(stat.q3)):.2f}" fill="#dbeafe" stroke="#2563eb"/>',
                f'<line x1="{x - box_w / 2:.2f}" x2="{x + box_w / 2:.2f}" y1="{y(stat.median):.2f}" y2="{y(stat.median):.2f}" stroke="#b91c1c" stroke-width="2"/>',
                f'<text transform="translate({x + 4:.2f},{top + plot_h + 10}) rotate(60)" font-size="10">{html.escape(_slug_label(problem, 28))}</text>',
            ]
        )
    parts.append(f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12">CPU energy per call (log scale)</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _runtime_box_plot(cases: list[dict[str, str]], problems: list[dict[str, str]]) -> str:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in cases:
        grouped[row["problem"]].append(_float(row, "median_wall_ms_per_call"))
    ordered = sorted(
        [row["problem"] for row in problems],
        key=lambda slug: _float(
            next(problem for problem in problems if problem["problem"] == slug),
            "median_case_wall_ms",
        ),
        reverse=True,
    )
    stats = {problem: quartiles(grouped[problem]) for problem in ordered}
    values = [value for vals in grouped.values() for value in vals]
    ymin, ymax = min(values), max(values)
    width = max(1180, 92 + len(ordered) * 28)
    height = 620
    left, right, top, bottom = 78, 24, 28, 190
    plot_w = width - left - right
    plot_h = height - top - bottom

    def y(value: float) -> float:
        return log_position(value, ymin, ymax, top + plot_h, top)

    step = plot_w / len(ordered)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Problem runtime box plot">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#1f2937"/>',
    ]
    for tick in _axis_ticks(ymin, ymax):
        ty = y(tick)
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{ty:.2f}" y2="{ty:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 8}" y="{ty + 4:.2f}" text-anchor="end" font-size="11">{html.escape(_fmt_ms(tick))}</text>')
    for index, problem in enumerate(ordered):
        stat = stats[problem]
        x = left + step * index + step / 2
        box_w = max(7, min(18, step * 0.58))
        parts.extend(
            [
                f'<line x1="{x:.2f}" x2="{x:.2f}" y1="{y(stat.minimum):.2f}" y2="{y(stat.maximum):.2f}" stroke="#64748b"/>',
                f'<line x1="{x - box_w / 2:.2f}" x2="{x + box_w / 2:.2f}" y1="{y(stat.minimum):.2f}" y2="{y(stat.minimum):.2f}" stroke="#64748b"/>',
                f'<line x1="{x - box_w / 2:.2f}" x2="{x + box_w / 2:.2f}" y1="{y(stat.maximum):.2f}" y2="{y(stat.maximum):.2f}" stroke="#64748b"/>',
                f'<rect x="{x - box_w / 2:.2f}" y="{y(stat.q3):.2f}" width="{box_w:.2f}" height="{max(1, y(stat.q1) - y(stat.q3)):.2f}" fill="#dcfce7" stroke="#16a34a"/>',
                f'<line x1="{x - box_w / 2:.2f}" x2="{x + box_w / 2:.2f}" y1="{y(stat.median):.2f}" y2="{y(stat.median):.2f}" stroke="#b91c1c" stroke-width="2"/>',
                f'<text transform="translate({x + 4:.2f},{top + plot_h + 10}) rotate(60)" font-size="10">{html.escape(_slug_label(problem, 28))}</text>',
            ]
        )
    parts.append(f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12">Wall time per call (log scale)</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _case_count_chart(problems: list[dict[str, str]]) -> str:
    ranked = sorted(problems, key=lambda row: _int(row, "case_count"), reverse=True)
    width = max(1180, 92 + len(ranked) * 28)
    height = 520
    left, right, top, bottom = 64, 24, 24, 180
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_count = max(_int(row, "case_count") for row in ranked)
    step = plot_w / len(ranked)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Test case count distribution by problem">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#1f2937"/>',
    ]
    for tick in [0, 50, 100, 150, 200]:
        if tick > max_count:
            continue
        y = top + plot_h - (tick / max_count * plot_h if max_count else 0)
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y:.2f}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11">{tick}</text>')
    for index, row in enumerate(ranked):
        count = _int(row, "case_count")
        x = left + step * index + step * 0.18
        h = count / max_count * plot_h if max_count else 0
        bar_w = max(5, step * 0.62)
        parts.append(f'<rect x="{x:.2f}" y="{top + plot_h - h:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="#0ea5e9" opacity="0.82"/>')
        parts.append(f'<text transform="translate({x + 4:.2f},{top + plot_h + 10}) rotate(60)" font-size="10">{html.escape(_slug_label(row["problem"], 28))}</text>')
    parts.append(f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12">Curated cases</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _batch_calls_chart(cases: list[dict[str, str]]) -> str:
    values = [_int(row, "batch_calls") for row in cases]
    lo_power = math.floor(math.log10(min(values)))
    hi_power = math.ceil(math.log10(max(values)))
    edges = [10**power for power in range(lo_power, hi_power + 1)]
    if edges[0] > min(values):
        edges.insert(0, min(values))
    if edges[-1] < max(values):
        edges.append(max(values))
    counts = [0 for _ in range(len(edges) - 1)]
    for value in values:
        for index in range(len(edges) - 1):
            if edges[index] <= value < edges[index + 1] or (index == len(edges) - 2 and value <= edges[index + 1]):
                counts[index] += 1
                break
    top = sorted(cases, key=lambda row: _int(row, "batch_calls"), reverse=True)[:12]
    width, height = 1180, 760
    left, base, bar_w, scale_h = 78, 300, 86, 225
    max_count = max(counts)
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Batch calls distribution">', f'<rect width="{width}" height="{height}" fill="white"/>']
    parts.append('<text x="78" y="34" font-size="14" font-weight="700">Batch call count histogram</text>')
    parts.append('<text x="78" y="54" font-size="11" fill="#475569">How many cases needed each order-of-magnitude repeat count to reach an approximately one-second batch.</text>')
    for index, count in enumerate(counts):
        h = count / max_count * scale_h if max_count else 0
        x = left + index * (bar_w + 24)
        label = f"{edges[index]:,.0f}-{edges[index + 1]:,.0f}"
        parts.append(f'<rect x="{x}" y="{base - h:.2f}" width="{bar_w}" height="{h:.2f}" fill="#14b8a6" opacity="0.82"/>')
        parts.append(f'<text transform="translate({x + bar_w / 2:.2f},{base + 18}) rotate(35)" text-anchor="start" font-size="10">{html.escape(label)}</text>')
        parts.append(f'<text x="{x + bar_w / 2}" y="{base - h - 5:.2f}" text-anchor="middle" font-size="10">{count}</text>')
    parts.append(f'<text x="22" y="{base - scale_h / 2:.2f}" transform="rotate(-90 22 {base - scale_h / 2:.2f})" text-anchor="middle" font-size="12">Cases</text>')

    right_x, top_y, row_h = 78, 465, 23
    parts.append(f'<text x="{right_x}" y="{top_y - 28}" font-size="14" font-weight="700">Largest calibrated batch counts</text>')
    parts.append(f'<text x="{right_x}" y="{top_y - 10}" font-size="11" fill="#475569">These are the fastest cases: they needed the most repeated calls to make a measurable batch.</text>')
    max_calls = _int(top[0], "batch_calls") if top else 1
    for index, row in enumerate(top):
        y = top_y + index * row_h
        calls = _int(row, "batch_calls")
        w = calls / max_calls * 520
        label = f'{_slug_label(row["problem"], 46)} case {row["case_index"]}'
        parts.append(f'<text x="{right_x}" y="{y + 14}" font-size="10">{html.escape(label)}</text>')
        parts.append(f'<rect x="{right_x + 330}" y="{y + 3}" width="{w:.2f}" height="15" fill="#0f766e" opacity="0.82"/>')
        parts.append(f'<text x="{right_x + 338 + w:.2f}" y="{y + 14}" font-size="10">{calls:,}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _problem_bar_chart(problems: list[dict[str, str]]) -> str:
    ranked = sorted(problems, key=lambda row: _float(row, "median_case_cpu_energy_j"), reverse=True)
    selected = ranked[:10] + list(reversed(ranked[-10:]))
    values = [_float(row, "median_case_cpu_energy_j") for row in selected]
    xmin, xmax = min(values), max(values)
    width, height = 980, 620
    left, right, top, row_h = 300, 80, 28, 26
    plot_w = width - left - right
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Top and bottom problem energy bar chart">', f'<rect width="{width}" height="{height}" fill="white"/>']
    for index, row in enumerate(selected):
        y = top + index * row_h
        value = _float(row, "median_case_cpu_energy_j")
        bar_w = max(2, log_position(value, xmin, xmax, 0, plot_w))
        color = "#ef4444" if index < 10 else "#10b981"
        parts.append(f'<text x="{left - 8}" y="{y + 15}" text-anchor="end" font-size="11">{html.escape(_slug_label(row["problem"], 38))}</text>')
        parts.append(f'<rect x="{left}" y="{y + 3}" width="{bar_w:.2f}" height="16" fill="{color}" opacity="0.82"/>')
        parts.append(f'<text x="{left + bar_w + 6:.2f}" y="{y + 15}" font-size="11">{html.escape(_fmt_energy(value))}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _scatter(cases: list[dict[str, str]]) -> str:
    xs = [_float(row, "median_wall_ms_per_call") for row in cases]
    ys = [_float(row, "median_cpu_energy_j_per_call") for row in cases]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    width, height = 900, 560
    left, right, top, bottom = 82, 28, 28, 70
    plot_w = width - left - right
    plot_h = height - top - bottom

    def x(value: float) -> float:
        return log_position(value, xmin, xmax, left, left + plot_w)

    def y(value: float) -> float:
        return log_position(value, ymin, ymax, top + plot_h, top)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Energy versus wall time scatter plot">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f2937"/>',
    ]
    for tick in _axis_ticks(xmin, xmax):
        tx = x(tick)
        parts.append(f'<line x1="{tx:.2f}" y1="{top}" x2="{tx:.2f}" y2="{top + plot_h}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{tx:.2f}" y="{top + plot_h + 20}" text-anchor="middle" font-size="11">{html.escape(_fmt_ms(tick))}</text>')
    for tick in _axis_ticks(ymin, ymax):
        ty = y(tick)
        parts.append(f'<line x1="{left}" y1="{ty:.2f}" x2="{left + plot_w}" y2="{ty:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 8}" y="{ty + 4:.2f}" text-anchor="end" font-size="11">{html.escape(_fmt_energy(tick))}</text>')
    for row in cases:
        parts.append(f'<circle cx="{x(_float(row, "median_wall_ms_per_call")):.2f}" cy="{y(_float(row, "median_cpu_energy_j_per_call")):.2f}" r="2.4" fill="#2563eb" opacity="0.38"/>')
    parts.append(f'<text x="{left + plot_w / 2:.2f}" y="{height - 18}" text-anchor="middle" font-size="12">Wall time per call (log scale)</text>')
    parts.append(f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12">CPU energy per call (log scale)</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _cv_chart(cases: list[dict[str, str]], problems: list[dict[str, str]]) -> str:
    values = [_float(row, "energy_cv") for row in cases]
    bins = [0, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, max(max(values), 0.3001)]
    counts = [0 for _ in range(len(bins) - 1)]
    for value in values:
        for index in range(len(bins) - 1):
            if bins[index] <= value < bins[index + 1] or (index == len(bins) - 2 and value <= bins[index + 1]):
                counts[index] += 1
                break
    top = sorted(problems, key=lambda row: _float(row, "max_case_energy_cv"), reverse=True)[:12]
    width, height = 1180, 760
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Case measurement noise chart">', f'<rect width="{width}" height="{height}" fill="white"/>']
    left, base, bar_w, scale_h = 78, 300, 96, 225
    max_count = max(counts)
    parts.append('<text x="78" y="34" font-size="14" font-weight="700">Case energy CV histogram</text>')
    parts.append('<text x="78" y="54" font-size="11" fill="#475569">Distribution of per-case measurement noise. CV is computed from the 10 batch energy-per-call values for each case.</text>')
    for index, count in enumerate(counts):
        h = count / max_count * scale_h if max_count else 0
        x = left + index * (bar_w + 18)
        parts.append(f'<rect x="{x}" y="{base - h:.2f}" width="{bar_w}" height="{h:.2f}" fill="#8b5cf6" opacity="0.78"/>')
        parts.append(f'<text transform="translate({x + bar_w / 2:.2f},{base + 18}) rotate(35)" text-anchor="start" font-size="10">{bins[index]:.3g}-{bins[index + 1]:.3g}</text>')
        parts.append(f'<text x="{x + bar_w / 2}" y="{base - h - 5:.2f}" text-anchor="middle" font-size="10">{count}</text>')
    parts.append(f'<text x="22" y="{base - scale_h / 2:.2f}" transform="rotate(-90 22 {base - scale_h / 2:.2f})" text-anchor="middle" font-size="12">Cases</text>')

    right_x, top_y, row_h = 78, 465, 23
    parts.append(f'<text x="{right_x}" y="{top_y - 28}" font-size="14" font-weight="700">Problems with the noisiest individual cases</text>')
    parts.append(f'<text x="{right_x}" y="{top_y - 10}" font-size="11" fill="#475569">Ranked by max case CV inside the problem. These are useful follow-up targets if a case looks unstable.</text>')
    max_cv = max(_float(row, "max_case_energy_cv") for row in top)
    for index, row in enumerate(top):
        y = top_y + index * row_h
        value = _float(row, "max_case_energy_cv")
        w = value / max_cv * 520 if max_cv else 0
        parts.append(f'<text x="{right_x}" y="{y + 14}" font-size="10">{html.escape(_slug_label(row["problem"], 46))}</text>')
        parts.append(f'<rect x="{right_x + 330}" y="{y + 3}" width="{w:.2f}" height="15" fill="#f59e0b" opacity="0.82"/>')
        parts.append(f'<text x="{right_x + 338 + w:.2f}" y="{y + 14}" font-size="10">{value:.3f}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _example_problem_rollup(cases: list[dict[str, str]], problems: list[dict[str, str]]) -> str:
    ranked = sorted(problems, key=lambda row: _float(row, "median_case_cpu_energy_j"))
    problem_row = ranked[len(ranked) // 2]
    problem = problem_row["problem"]
    problem_cases = sorted(
        [row for row in cases if row["problem"] == problem],
        key=lambda row: _float(row, "median_cpu_energy_j_per_call"),
    )
    energies = [_float(row, "median_cpu_energy_j_per_call") for row in problem_cases]
    ymin, ymax = min(energies), max(energies)
    xmin, xmax = 0, len(problem_cases) - 1
    width, height = 980, 500
    left, right, top, bottom = 82, 32, 34, 70
    plot_w = width - left - right
    plot_h = height - top - bottom

    def x(index: int) -> float:
        return left + (index - xmin) / max(1, xmax - xmin) * plot_w

    def y(value: float) -> float:
        return log_position(value, ymin, ymax, top + plot_h, top)

    median_energy = _float(problem_row, "median_case_cpu_energy_j")
    median_wall = _float(problem_row, "median_case_wall_ms")
    median_y = y(median_energy)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Example problem case rollup">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#1f2937"/>',
        f'<line x1="{left}" x2="{left + plot_w}" y1="{median_y:.2f}" y2="{median_y:.2f}" stroke="#b91c1c" stroke-width="2" stroke-dasharray="6 4"/>',
        f'<text x="{left + plot_w - 4}" y="{median_y - 7:.2f}" text-anchor="end" font-size="11">problem median {_fmt_energy(median_energy)}</text>',
    ]
    for tick in _axis_ticks(ymin, ymax):
        ty = y(tick)
        parts.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{ty:.2f}" y2="{ty:.2f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{left - 8}" y="{ty + 4:.2f}" text-anchor="end" font-size="11">{html.escape(_fmt_energy(tick))}</text>')
    for index, row in enumerate(problem_cases):
        radius = 2.2 + min(8.0, max(0.0, math.log10(max(1.0, _int(row, "batch_calls"))) - 2.0))
        parts.append(
            f'<circle cx="{x(index):.2f}" cy="{y(_float(row, "median_cpu_energy_j_per_call")):.2f}" '
            f'r="{radius:.2f}" fill="#2563eb" opacity="0.55"/>'
        )
    parts.append(f'<text x="{left + plot_w / 2:.2f}" y="{height - 18}" text-anchor="middle" font-size="12">Cases sorted by median CPU energy per call</text>')
    parts.append(f'<text x="18" y="{top + plot_h / 2:.2f}" transform="rotate(-90 18 {top + plot_h / 2:.2f})" text-anchor="middle" font-size="12">CPU energy per call (log scale)</text>')
    parts.append("</svg>")
    detail = (
        f"<p><strong>Example problem:</strong> <code>{html.escape(problem)}</code>. "
        f"It has {len(problem_cases)} cases. Each dot is one case median, already "
        f"computed from 10 measured batches for that case. The dashed red line is "
        f"the final problem number: median case CPU energy "
        f"<strong>{html.escape(_fmt_energy(median_energy))}</strong>. The same problem's "
        f"median runtime is <strong>{html.escape(_fmt_ms(median_wall))}</strong> per call. "
        "Dot size increases with calibrated batch calls.</p>"
    )
    return detail + "\n" + "\n".join(parts)


def _summary_cards(summary: dict[str, Any], duration: str) -> str:
    accepted_selected = (
        int(summary.get("measured_problems", 0))
        + int(summary.get("skipped_problems", 0))
        + int(summary.get("failed_problems", 0))
    )
    cards = [
        ("Model", summary.get("model_slug", "unknown")),
        ("Accepted selected", accepted_selected),
        ("Measured problems", summary.get("measured_problems", 0)),
        ("Complete cases", summary.get("complete_cases", 0)),
        ("Measurement rows", summary.get("measurement_rows", 0)),
        ("Skipped problems", summary.get("skipped_problems", 0)),
        ("Run duration", duration),
        ("Model median energy", _fmt_energy(float(summary.get("model_median_problem_energy_j") or 0))),
    ]
    return "\n".join(
        f'<div class="card"><div class="label">{html.escape(str(label))}</div><div class="value">{html.escape(str(value))}</div></div>'
        for label, value in cards
    )


def _measurement_walkthrough() -> str:
    return """
<div class="walkthrough">
  <div>
    <div class="step">1</div>
    <h3>Validate the accepted solution</h3>
    <p>The Python solution was already accepted by PerfArena/LeetCode. Before measuring energy, it is also run against every curated local case for that problem. If validation fails, the problem is skipped.</p>
  </div>
  <div>
    <div class="step">2</div>
    <h3>Start one worker and one sampler</h3>
    <p>One persistent Python worker loads the solution once, so import/startup is outside the measured case batches. One continuous <code>powermetrics</code> process starts for the problem before warmup and stops after the problem is done.</p>
  </div>
  <div>
    <div class="step">3</div>
    <h3>Warm up and calibrate every case</h3>
    <p>The worker sweeps all cases for 60 seconds. Then each case gets its own <code>batch_calls</code> count, chosen so repeating that unchanged case lasts about one second.</p>
  </div>
  <div>
    <div class="step">4</div>
    <h3>Measure ten batches per case</h3>
    <p>For each case, each measured batch repeats the same unchanged input <code>batch_calls</code> times. That batch produces one wall-time value and one CPU-energy value. Ten shuffled rounds produce ten batch rows for the case.</p>
  </div>
  <div>
    <div class="step">5</div>
    <h3>Integrate powermetrics samples</h3>
    <p>The sampler interval is 100 ms, but sample windows are not aligned to batch boundaries. Only complete sample windows fully inside the batch are integrated, so a roughly one-second batch often has about 8 usable samples rather than exactly 10.</p>
  </div>
  <div>
    <div class="step">6</div>
    <h3>Normalize and roll up medians</h3>
    <p>Each batch row is normalized by <code>batch_calls</code>. One case result is the median of its ten normalized rows. One problem result is the median of its case medians.</p>
  </div>
</div>
<pre>batch wall per call = batch_wall_ms / batch_calls
batch energy per call = batch_cpu_energy_j / batch_calls
case result = median(10 batch energy-per-call rows)
problem result = median(all case results for that problem)</pre>
"""


def render_report(data: dict[str, Any]) -> str:
    cases = data["cases"]
    problems = data["problems"]
    summary = data["summary"]
    duration = data["duration"]
    title = f"LeetCode Casewise Energy Report: {summary.get('model_slug', 'unknown')}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #111827; background: #f8fafc; }}
main {{ max-width: 1280px; margin: 0 auto; padding: 32px; }}
h1 {{ margin: 0 0 8px; font-size: 30px; }}
h2 {{ margin: 34px 0 12px; font-size: 22px; }}
p {{ line-height: 1.55; }}
.muted {{ color: #475569; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 22px 0; }}
.card {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; }}
.label {{ color: #64748b; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 20px; font-weight: 700; margin-top: 6px; }}
.panel {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin: 16px 0 28px; overflow-x: auto; }}
.note {{ background: #ecfeff; border: 1px solid #a5f3fc; border-radius: 8px; padding: 14px 16px; }}
.walkthrough {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }}
.walkthrough > div {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; }}
.walkthrough h3 {{ margin: 6px 0 8px; font-size: 16px; }}
.walkthrough p {{ margin: 0; color: #475569; }}
.step {{ width: 28px; height: 28px; border-radius: 50%; background: #2563eb; color: white; display: grid; place-items: center; font-weight: 700; }}
pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; }}
code {{ background: #eef2ff; padding: 1px 4px; border-radius: 4px; }}
svg text {{ fill: #111827; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Static offline report generated from existing casewise CSV and JSON outputs. Energy values are same-device Apple powermetrics CPU estimates and should not be used for cross-machine rankings.</p>
<section class="cards">{_summary_cards(summary, duration)}</section>

<section class="note">
<strong>How to read this report:</strong> one JSONL row is one measured batch for one case. One case CSV row is the median of 10 batch rows. One problem score is the median of all case medians for that problem.
Gemma had 46 accepted Python solutions selected for this run; 44 were measured and 2 were skipped because their curated workloads were not available.
</section>

<h2>Test Case Count Distribution</h2>
<p class="muted">Each bar is one measured problem. The height is the number of curated LeetCodeDataset93 cases used for that problem. This shows that the energy result is casewise: problems contribute different numbers of measured cases.</p>
<div class="panel">{_case_count_chart(problems)}</div>

<h2>Batch Calls Distribution</h2>
<p class="muted">Each case has its own calibrated batch count. Faster cases require more repeated calls to make one measured batch last about one second; slower cases require fewer calls.</p>
<div class="panel">{_batch_calls_chart(cases)}</div>

<h2>Case Runtime By Problem</h2>
<p class="muted">This box plot uses case median wall time per call. It answers the runtime version of the energy plot: how long each individual test case takes after normalizing the one-second batch by its calibrated call count.</p>
<div class="panel">{_runtime_box_plot(cases, problems)}</div>

<h2>Problem Energy Box Plot</h2>
<p class="muted">Each box summarizes case-level CPU energy per call for one problem. Problems are sorted by problem median energy. The y-axis is log-scaled because case energy spans orders of magnitude.</p>
<div class="panel">{_box_plot(cases, problems)}</div>

<h2>Example Problem Case Rollup</h2>
<p class="muted">This section shows the exact casewise aggregation idea for one representative problem: many case medians become one final problem median.</p>
<div class="panel">{_example_problem_rollup(cases, problems)}</div>

<h2>Highest And Lowest Median Problem Energy</h2>
<p class="muted">The red bars are the ten highest-energy problems by median case energy. The green bars are the ten lowest. Bar length uses a log scale.</p>
<div class="panel">{_problem_bar_chart(problems)}</div>

<h2>Energy vs Wall Time</h2>
<p class="muted">Each point is one completed case. Both axes are log-scaled. A tight upward trend means energy is largely tracking execution time for these Python solutions.</p>
<div class="panel">{_scatter(cases)}</div>

<h2>Case Measurement Noise</h2>
<p class="muted">CV is the coefficient of variation across the ten energy-per-call batch measurements for a case. Lower values mean the repeated batch measurements were more stable.</p>
<div class="panel">{_cv_chart(cases, problems)}</div>

<h2>Measurement Walkthrough</h2>
<p class="muted">This is the full path from an accepted solution to the numbers shown in the plots.</p>
{_measurement_walkthrough()}
</main>
</body>
</html>
"""


def write_report(root: Path, language: str, output: Path | None = None) -> Path:
    data = load_data(root, language)
    out = output or root / f"{language}_casewise_report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(data))
    return out
