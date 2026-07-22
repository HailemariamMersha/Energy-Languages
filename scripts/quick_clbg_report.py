#!/usr/bin/env python3
"""Compile, validate, and sample each configured CLBG cell; write per-language HTML."""
from __future__ import annotations

import argparse
import html
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


def run(cmd: list[str], cwd: Path, timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"


def version(command: str, args: list[str]) -> str:
    path = shutil.which(command)
    if not path:
        return "not installed"
    code, output = run([path, *args], Path.cwd(), 20)
    return (output.strip().splitlines() or [f"exit {code}"])[0]


def render(language: str, rows: list[dict], versions: dict[str, str], generated: str) -> str:
    passed = sum(r["status"] == "PASS" for r in rows)
    cells = []
    for r in rows:
        cls = "ok" if r["status"] == "PASS" else "bad"
        energy = f'{r["energy_uj"] / 1_000_000:.6f}' if r.get("energy_uj") is not None else "—"
        memory = f'{r["peak_rss_kb"] / 1024:.2f}' if r.get("peak_rss_kb") is not None else "—"
        wall = f'{r["wall_ms"]:.2f}' if r.get("wall_ms") is not None else "—"
        energy_source = html.escape(r.get("energy_source_status", "unavailable"))
        cells.append(f"<tr><td>{html.escape(r['problem'])}</td><td class='{cls}'>{r['status']}</td>"
                     f"<td>{wall}</td><td>{memory}</td><td>{energy}</td><td>{energy_source}</td>"
                     f"<td><details><summary>log</summary><pre>{html.escape(r['log'])}</pre></details></td></tr>")
    vers = "".join(f"<li><code>{html.escape(k)}</code>: {html.escape(v)}</li>" for k, v in versions.items())
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<title>{html.escape(language)} CLBG quick check</title><style>
body{{font:15px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#18212b}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd5df;padding:.5rem;text-align:left}}
th{{background:#edf2f7}}.ok{{color:#087830;font-weight:700}}.bad{{color:#b42318;font-weight:700}}
pre{{white-space:pre-wrap;max-width:650px}}code{{background:#eef2f6;padding:.1rem .25rem}}</style></head><body>
<h1>{html.escape(language)} CLBG quick check</h1><p><strong>{passed}/{len(rows)} passed</strong>. Generated {generated} on {html.escape(platform.platform())}.</p>
<p>Each passing cell was compiled, checked against its small reference output, then sampled once. Energy is reported by the configured platform backend and peak RSS covers the benchmark process tree.</p>
<h2>Toolchain</h2><ul>{vers}</ul><table><thead><tr><th>Problem</th><th>Result</th><th>Wall (ms)</th><th>Peak RSS (MiB)</th><th>Energy (J)</th><th>Energy source</th><th>Details</th></tr></thead>
<tbody>{''.join(cells)}</tbody></table></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--languages", default="")
    args = ap.parse_args()
    root = args.repo.resolve()
    out = (args.out or root / "perfarena_out" / "clbg_quick").resolve()
    out.mkdir(parents=True, exist_ok=True)
    languages = yaml.safe_load((root / "perfarena/configs/languages.yaml").read_text())["languages"]
    problems = yaml.safe_load((root / "perfarena/configs/problems.yaml").read_text())["problems"]
    wanted = {x.strip().lower() for x in args.languages.split(",") if x.strip()}
    generated = datetime.now(timezone.utc).isoformat()
    tool_commands = {"Python": ("python3", ["--version"]), "JavaScript": ("node", ["--version"]),
        "TypeScript": ("npx", ["--version"]), "Java": ("javac", ["-version"]),
        "CSharp": ("dotnet", ["--version"]), "C++": ("c++", ["--version"]),
        "PHP": ("php", ["--version"]), "Go": ("go", ["version"]),
        "Rust": ("rustc", ["--version"]), "Ruby": ("ruby", ["--version"])}
    index = []
    for lang in languages:
        if wanted and lang["key"] not in wanted and lang["folder"].lower() not in wanted:
            continue
        folder = lang["folder"]
        trace = root / folder / f"{folder}.jsonl"
        rows = []
        for problem in problems:
            cell = root / folder / problem["key"]
            before = trace.stat().st_size if trace.exists() else 0
            code, log = run(["make", "clean", "compile", "validate", "PYTHON=../../.venv/bin/python"], cell)
            row = {"problem": problem["key"], "status": "FAIL", "log": log,
                   "wall_ms": None, "peak_rss_kb": None, "energy_uj": None,
                   "energy_source_status": "unavailable"}
            if code == 0:
                env_args = ["make", "measure", f"ARG={problem['validation_n']}", "PERFARENA_WARMUP=0",
                            "PERFARENA_MEASURE=1", "PERFARENA_IDLE_S=0",
                            f"PERFARENA_RUNNER={root / '.venv/bin/python'} -m perfarena.runners.codecarbon_runner"]
                code, mlog = run(env_args, cell, 240)
                row["log"] += "\n" + mlog
                if trace.exists():
                    with trace.open() as fh:
                        fh.seek(before)
                        measured = [json.loads(x) for x in fh if x.strip() and json.loads(x).get("phase") == "measure"]
                    if measured:
                        m = measured[-1]
                        row.update(wall_ms=m.get("wall_ms"), peak_rss_kb=m.get("peak_rss_kb"),
                                   energy_uj=m.get("rapl_pkg_delta_raw"),
                                   energy_source_status=m.get("energy_source", "unavailable"))
                row["status"] = "PASS" if code == 0 and row["wall_ms"] is not None else "FAIL"
            rows.append(row)
        command, v_args = tool_commands[folder]
        versions = {command: version(command, v_args), "make": version("make", ["--version"])}
        report = out / f"{lang['key']}_clbg_quick_report.html"
        report.write_text(render(lang["display_name"], rows, versions, generated))
        (out / f"{lang['key']}_clbg_quick_results.json").write_text(json.dumps(rows, indent=2) + "\n")
        passed = sum(r["status"] == "PASS" for r in rows)
        index.append((lang["display_name"], passed, report.name))
        print(f"{folder}: {passed}/{len(rows)} -> {report}", flush=True)
    # Include reports from earlier partial reruns as well as this invocation.
    known = {path for _, _, path in index}
    for result in sorted(out.glob("*_clbg_quick_results.json")):
        report_name = result.name.replace("_results.json", "_report.html")
        if report_name in known:
            continue
        data = json.loads(result.read_text())
        index.append((result.stem.removesuffix("_clbg_quick_results").title(),
                      sum(r["status"] == "PASS" for r in data), report_name))
    links = "".join(f"<li><a href='{html.escape(path)}'>{html.escape(name)}</a>: {n}/10</li>" for name, n, path in index)
    (out / "index.html").write_text(f"<!doctype html><meta charset='utf-8'><title>CLBG quick checks</title><h1>CLBG quick checks</h1><ul>{links}</ul>")
    return 0 if all(n == 10 for _, n, _ in index) else 1


if __name__ == "__main__":
    raise SystemExit(main())
