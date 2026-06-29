"""Persistent Python worker for isolated curated LeetCode case execution."""

from __future__ import annotations

import argparse
import ast
import json
import math
import statistics
import sys
import time
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
        compile(ast.Expression(body=call), "<leetcode-case>", "eval")
        for call in extractor.calls
    ]


class CaseWorker:
    def __init__(self, source: Path, workload: dict[str, Any]) -> None:
        self.workload = workload
        self.namespace: dict[str, Any] = {"__name__": "leetcode_case_workload"}
        combined = "\n".join([workload["prompt"], source.read_text(), workload["test"]])
        exec(compile(combined, str(source), "exec"), self.namespace)
        self.calls = candidate_calls(workload["test"])
        if len(self.calls) != len(workload["cases"]):
            raise ValueError(
                "curated workload call count mismatch: "
                f"{len(self.calls)} != {len(workload['cases'])}"
            )
        self.warmup_case_ns: list[list[int]] = [[] for _ in self.calls]

    def candidate(self) -> Any:
        return eval(self.workload["entry_point"], self.namespace)

    def validate(self) -> dict[str, Any]:
        self.namespace["check"](self.candidate())
        return {"ok": True, "cases": len(self.calls)}

    def _run_case(self, case_index: int, calls: int) -> dict[str, Any]:
        candidate = self.candidate()
        local_values = {"candidate": candidate}
        compiled_call = self.calls[case_index]
        started_ns = time.monotonic_ns()
        for _ in range(max(1, calls)):
            # Evaluating the AST reconstructs list/dict literals for each invocation.
            eval(compiled_call, self.namespace, local_values)
        ended_ns = time.monotonic_ns()
        return {
            "case_index": case_index,
            "batch_calls": max(1, calls),
            "started_ns": started_ns,
            "ended_ns": ended_ns,
            "wall_ns": ended_ns - started_ns,
        }

    def warmup(self, seconds: float) -> dict[str, Any]:
        minimum_ns = max(0, int(seconds * 1_000_000_000))
        started_ns = time.monotonic_ns()
        sweep_rows: list[dict[str, int]] = []
        while not sweep_rows or time.monotonic_ns() - started_ns < minimum_ns:
            sweep_start = time.monotonic_ns()
            for case_index in range(len(self.calls)):
                row = self._run_case(case_index, 1)
                self.warmup_case_ns[case_index].append(row["wall_ns"])
            sweep_end = time.monotonic_ns()
            sweep_rows.append(
                {
                    "started_ns": sweep_start,
                    "ended_ns": sweep_end,
                    "wall_ns": sweep_end - sweep_start,
                }
            )
        ended_ns = time.monotonic_ns()
        drift = _warmup_drift(sweep_rows, ended_ns)
        return {
            "ok": True,
            "started_ns": started_ns,
            "ended_ns": ended_ns,
            "wall_ns": ended_ns - started_ns,
            "sweeps": len(sweep_rows),
            **drift,
        }

    def calibrate(self, case_index: int, target_seconds: float) -> dict[str, Any]:
        target_ns = max(1, int(target_seconds * 1_000_000_000))
        timings = self.warmup_case_ns[case_index]
        estimate_ns = int(statistics.median(timings)) if timings else 1
        batch_calls = max(1, math.ceil(target_ns / max(1, estimate_ns)))
        pilot: dict[str, Any] | None = None
        for _ in range(5):
            pilot = self._run_case(case_index, batch_calls)
            wall_ns = pilot["wall_ns"]
            if wall_ns >= target_ns or batch_calls == 1:
                break
            batch_calls = max(
                batch_calls + 1,
                math.ceil(batch_calls * target_ns / max(1, wall_ns)),
            )
        assert pilot is not None
        if pilot["batch_calls"] != batch_calls:
            pilot = self._run_case(case_index, batch_calls)
        return {
            "ok": True,
            "case_index": case_index,
            "batch_calls": batch_calls,
            "pilot_wall_ns": pilot["wall_ns"],
            "target_ns": target_ns,
        }

    def command(self, request: dict[str, Any]) -> dict[str, Any]:
        action = request.get("action")
        if action == "validate":
            return self.validate()
        if action == "warmup":
            return self.warmup(float(request["seconds"]))
        if action == "calibrate":
            return self.calibrate(
                int(request["case_index"]),
                float(request["target_seconds"]),
            )
        if action == "measure":
            return {
                "ok": True,
                **self._run_case(
                    int(request["case_index"]),
                    int(request["batch_calls"]),
                ),
            }
        if action == "stop":
            return {"ok": True, "stop": True}
        raise ValueError(f"unknown worker action: {action!r}")


def _warmup_drift(sweeps: list[dict[str, int]], ended_ns: int) -> dict[str, Any]:
    windows: list[list[int]] = [[], []]
    boundaries = [ended_ns - 20_000_000_000, ended_ns - 10_000_000_000]
    for row in sweeps:
        if row["ended_ns"] >= boundaries[1]:
            windows[1].append(row["wall_ns"])
        elif row["ended_ns"] >= boundaries[0]:
            windows[0].append(row["wall_ns"])
    if not windows[0] or not windows[1]:
        return {
            "warmup_drift": None,
            "warmup_stable": False,
            "warmup_stability_reason": "insufficient completed sweeps in final windows",
        }
    earlier = statistics.median(windows[0])
    later = statistics.median(windows[1])
    drift = abs(later - earlier) / earlier if earlier else 0.0
    return {
        "warmup_drift": drift,
        "warmup_stable": drift <= 0.05,
        "warmup_stability_reason": "final 10-second median vs preceding 10-second median",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--workload", type=Path, required=True)
    args = parser.parse_args()
    workload = json.loads(args.workload.read_text())
    worker = CaseWorker(args.source, workload)
    print(json.dumps({"ready": True, "cases": len(worker.calls)}), flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = worker.command(json.loads(line))
        except Exception as exc:  # noqa: BLE001
            response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(response, sort_keys=True), flush=True)
        if response.get("stop"):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
