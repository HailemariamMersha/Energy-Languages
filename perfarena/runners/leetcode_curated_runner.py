"""Lightweight executor for one curated LeetCode workload.

This module deliberately uses only the Python standard library so measured
iterations do not import the PerfArena CLI, LangChain, or provider SDKs.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


class CandidateCallExtractor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "candidate":
            self.calls.append(node)
            return
        self.generic_visit(node)


def candidate_calls(test_source: str) -> list[Any]:
    extractor = CandidateCallExtractor()
    extractor.visit(ast.parse(test_source))
    return [
        compile(ast.Expression(body=call), "<leetcode-curated-case>", "eval")
        for call in extractor.calls
    ]


def run(
    source: Path,
    workload: dict[str, Any],
    *,
    repeat: int,
    validate: bool,
) -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "leetcode_curated_workload"}
    combined = "\n".join(
        [workload["prompt"], source.read_text(), workload["test"]]
    )
    exec(compile(combined, str(source), "exec"), namespace)
    if validate:
        namespace["check"](eval(workload["entry_point"], namespace))

    calls = candidate_calls(workload["test"])
    if len(calls) != len(workload["cases"]):
        raise ValueError(
            f"curated workload call count mismatch: "
            f"{len(calls)} != {len(workload['cases'])}"
        )
    for _ in range(max(1, repeat)):
        candidate = eval(workload["entry_point"], namespace)
        local_values = {"candidate": candidate}
        for call in calls:
            eval(call, namespace, local_values)
    return {
        "ok": True,
        "problem": workload["problem"],
        "cases": len(calls),
        "repeat": max(1, repeat),
        "validated": validate,
        "workload_hash": workload["workload_hash"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--workload", required=True, type=Path)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    workload = json.loads(args.workload.read_text())
    if workload.get("problem") != args.problem:
        parser.error(
            f"workload problem {workload.get('problem')!r} "
            f"does not match {args.problem!r}"
        )
    result = run(
        args.source,
        workload,
        repeat=max(1, args.repeat),
        validate=args.validate,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
