#!/usr/bin/env python3
"""Analyze the output of a PerfArena generation campaign.

Reads all meta.json files under perfarena_out/generations/ and
prints a summary table: per-cell pass/fail counts, inference
times, energy, and code sizes.

Usage:
    python scripts/analyze_campaign.py [--model-slug ollama__gemma4_e4b]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    model_slug = sys.argv[1] if len(sys.argv) > 1 else None
    gen_root = Path("perfarena_out/generations")

    if not gen_root.exists():
        print("No generations found. Run perfarena generate first.")
        return

    # Collect all meta.json files
    metas: list[dict] = []
    for meta_path in sorted(gen_root.rglob("*.meta.json")):
        try:
            d = json.loads(meta_path.read_text())
            if model_slug and model_slug not in str(meta_path):
                continue
            d["_path"] = str(meta_path)
            metas.append(d)
        except (json.JSONDecodeError, OSError):
            continue

    if not metas:
        print("No meta.json files found.")
        return

    # Group by (language, problem)
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for m in metas:
        cells[(m["language"], m["problem"])].append(m)

    # Print summary
    print(f"{'language':<14} {'problem':<22} {'n':>3} {'avg_wall_s':>10} "
          f"{'avg_energy_J':>12} {'avg_code_chars':>14} {'energy_src':<12}")
    print("-" * 90)

    total_samples = 0
    total_energy_j = 0.0
    for (lang, prob), samples in sorted(cells.items()):
        n = len(samples)
        total_samples += n

        walls = []
        energies = []
        code_sizes = []
        src = "?"

        for s in samples:
            inf = s.get("inference", {}).get("metrics", {})
            walls.append(inf.get("wall_time_s", 0))
            e = inf.get("energy_uj")
            if e is not None:
                energies.append(e / 1e6)
                total_energy_j += e / 1e6
            src = inf.get("energy_source", s.get("mode", "?"))
            code_sizes.append(s.get("response", {}).get("extracted_code_chars", 0))

        avg_wall = sum(walls) / len(walls) if walls else 0
        avg_energy = sum(energies) / len(energies) if energies else 0
        avg_code = sum(code_sizes) / len(code_sizes) if code_sizes else 0

        print(f"{lang:<14} {prob:<22} {n:>3} {avg_wall:>10.1f} "
              f"{avg_energy:>12.3f} {avg_code:>14.0f} {src:<12}")

    print("-" * 90)
    print(f"Total: {total_samples} samples across {len(cells)} cells, "
          f"total inference energy: {total_energy_j:.2f} J")

    # Check which cells are missing
    all_langs = {"python", "javascript", "typescript", "java", "csharp",
                 "cpp", "php", "go", "rust", "ruby"}
    all_probs = {"binary-trees", "fannkuch-redux", "fasta", "k-nucleotide",
                 "mandelbrot", "n-body", "pidigits", "regex-redux",
                 "reverse-complement", "spectral-norm"}

    present = set(cells.keys())
    expected = {(l, p) for l in all_langs for p in all_probs}
    missing = expected - present
    if missing and not model_slug:
        print(f"\nMissing cells: {len(missing)} (run with full 10x10 sweep to fill)")


if __name__ == "__main__":
    main()
