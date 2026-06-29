"""Per-test-case LeetCode energy measurement using macOS powermetrics."""

from __future__ import annotations

import hashlib
import gzip
import json
import os
import platform
import plistlib
import random
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


BENCHMARK = "leetcode-energy-casewise"


def measurement_path(repo_root: Path, model_slug: str, language: str) -> Path:
    return (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / f"{language}_casewise.jsonl"
    )


def summary_prefix(repo_root: Path, model_slug: str, language: str) -> Path:
    return (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / f"{language}_casewise_summary"
    )


def raw_metrics_dir(repo_root: Path, model_slug: str) -> Path:
    return (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / "powermetrics"
    )


def archive_raw_plist(source: Path, destination: Path) -> None:
    """Compress completed raw samples outside the measured execution window."""
    if not source.exists() or source.stat().st_size == 0:
        source.unlink(missing_ok=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        source.open("rb") as input_fh,
        gzip.open(destination, "ab", compresslevel=6) as output_fh,
    ):
        shutil.copyfileobj(input_fh, output_fh)
    source.unlink()


def case_hash(case: dict[str, Any]) -> str:
    raw = json.dumps(case, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class PowerSample:
    ended_ns: int
    elapsed_ns: int
    cpu_w: float
    gpu_w: float | None = None
    ane_w: float | None = None
    thermal: str | None = None

    @property
    def started_ns(self) -> int:
        return self.ended_ns - self.elapsed_ns


class Sampler(Protocol):
    interval_ms: int

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def wait_for_window(self, ended_ns: int, timeout: float = 2.0) -> None: ...
    def samples_for_window(
        self, started_ns: int, ended_ns: int
    ) -> list[PowerSample]: ...
    def latest_thermal(self) -> str | None: ...


class PowermetricsSampler:
    """Continuously parse NUL-delimited powermetrics plists."""

    def __init__(self, raw_path: Path, interval_ms: int = 100) -> None:
        self.raw_path = raw_path
        self.interval_ms = interval_ms
        self.samples: list[PowerSample] = []
        self._condition = threading.Condition()
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._reader_error: str | None = None
        self._thermal: str | None = None

    @staticmethod
    def preflight() -> None:
        if platform.system() != "Darwin":
            raise RuntimeError("direct powermetrics measurement requires macOS")
        if not Path("/usr/bin/powermetrics").exists():
            raise RuntimeError("/usr/bin/powermetrics is unavailable")
        check = subprocess.run(
            [
                "sudo",
                "-n",
                "/usr/bin/powermetrics",
                "--samplers",
                "cpu_power",
                "-i",
                "100",
                "-n",
                "1",
                "-o",
                "/dev/null",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if check.returncode:
            raise RuntimeError(
                "powermetrics requires scoped passwordless sudo. Add permission for "
                "/usr/bin/powermetrics, then verify with `sudo -n powermetrics`. "
                f"Details: {check.stderr.strip()}"
            )

    def start(self) -> None:
        self.raw_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "sudo",
            "-n",
            "/usr/bin/powermetrics",
            "--samplers",
            "cpu_power,gpu_power,ane_power,thermal",
            "--sample-rate",
            str(self.interval_ms),
            "--sample-count",
            "-1",
            "--format",
            "plist",
            "--buffer-size",
            "0",
        ]
        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 5
        with self._condition:
            while not self.samples and self._reader_error is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
        if self._reader_error:
            raise RuntimeError(self._reader_error)
        if not self.samples:
            self.stop()
            raise RuntimeError(
                "powermetrics produced no CPU power sample within 5 seconds"
            )

    def _read(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            buffer = b""
            with self.raw_path.open("ab") as raw:
                while chunk := self._proc.stdout.read(65536):
                    raw.write(chunk)
                    raw.flush()
                    buffer += chunk
                    while b"\0" in buffer:
                        payload, buffer = buffer.split(b"\0", 1)
                        if payload.strip():
                            self._append_sample(
                                parse_powermetrics_plist(
                                    payload, ended_ns=time.monotonic_ns()
                                )
                            )
        except Exception as exc:  # noqa: BLE001
            with self._condition:
                self._reader_error = f"powermetrics reader failed: {exc}"
                self._condition.notify_all()

    def _append_sample(self, sample: PowerSample) -> None:
        with self._condition:
            self.samples.append(sample)
            self._thermal = sample.thermal
            self._condition.notify_all()

    def wait_for_window(self, ended_ns: int, timeout: float = 2.0) -> None:
        target = ended_ns + self.interval_ms * 1_000_000
        deadline = time.monotonic() + timeout
        with self._condition:
            while (
                not self.samples or self.samples[-1].ended_ns < target
            ) and self._reader_error is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
        if self._reader_error:
            raise RuntimeError(self._reader_error)

    def samples_for_window(self, started_ns: int, ended_ns: int) -> list[PowerSample]:
        with self._condition:
            return [
                sample
                for sample in self.samples
                if sample.started_ns >= started_ns and sample.ended_ns <= ended_ns
            ]

    def latest_thermal(self) -> str | None:
        with self._condition:
            return self._thermal

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc.wait(timeout=3)
        if self._thread is not None:
            self._thread.join(timeout=3)


def parse_powermetrics_plist(
    payload: bytes,
    *,
    ended_ns: int | None = None,
) -> PowerSample:
    """Parse one machine-readable powermetrics sample."""
    document = plistlib.loads(payload)

    def find(key: str) -> Any:
        pending: list[Any] = [document]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                if key in value:
                    return value[key]
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
        return None

    cpu_mw = find("cpu_power")
    if cpu_mw is None:
        raise ValueError("powermetrics plist does not contain cpu_power")
    elapsed_ns = int(find("elapsed_ns") or 0)
    if elapsed_ns <= 0:
        raise ValueError("powermetrics plist does not contain a valid elapsed_ns")
    thermal = find("thermal_pressure")
    if isinstance(thermal, dict):
        thermal = thermal.get("level") or thermal.get("pressure_level")
    return PowerSample(
        ended_ns=ended_ns or time.monotonic_ns(),
        elapsed_ns=elapsed_ns,
        cpu_w=float(cpu_mw) / 1000,
        gpu_w=(
            float(value) / 1000 if (value := find("gpu_power")) is not None else None
        ),
        ane_w=(
            float(value) / 1000 if (value := find("ane_power")) is not None else None
        ),
        thermal=str(thermal) if thermal is not None else None,
    )


class WorkerClient:
    def __init__(self, repo_root: Path, source: Path, workload: Path) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = (
            str(repo_root)
            if not env.get("PYTHONPATH")
            else f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
        )
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "perfarena.runners.leetcode_case_worker",
                "--source",
                str(source),
                "--workload",
                str(workload),
            ],
            cwd=repo_root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready = self._read()
        if not ready.get("ready"):
            raise RuntimeError(f"case worker did not become ready: {ready}")

    def _read(self) -> dict[str, Any]:
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"case worker exited unexpectedly: {stderr}")
        return json.loads(line)

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        response = self._read()
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "case worker failed"))
        return response

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.request({"action": "stop"})
            except Exception:  # noqa: BLE001
                self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)


def _host_metadata() -> dict[str, Any]:
    def output(command: list[str]) -> str:
        try:
            return subprocess.run(
                command, text=True, capture_output=True, check=False, timeout=5
            ).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""

    power_settings = output(["pmset", "-g", "custom"])
    low_power_values = [
        line.split()[-1]
        for line in power_settings.splitlines()
        if "lowpowermode" in line.lower() and line.split()
    ]
    return {
        "machine": platform.machine(),
        "machine_model": output(["sysctl", "-n", "hw.model"]),
        "os": platform.platform(),
        "macos_version": platform.mac_ver()[0],
        "python": platform.python_version(),
        "power_source": output(["pmset", "-g", "batt"]),
        "low_power_mode": low_power_values or None,
        "power_settings": power_settings,
    }


def _completed_rows(path: Path) -> dict[tuple[str, str, int], dict[str, Any]]:
    completed: dict[tuple[str, str, int], dict[str, Any]] = {}
    if not path.exists():
        return completed
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("phase") != "measure":
            continue
        completed[
            (row["problem"], row["case_hash"], int(row["measurement_iteration"]))
        ] = row
    return completed


def _problem_statuses(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    return {
        (row["problem"], row["status"])
        for line in path.read_text().splitlines()
        if line.strip()
        for row in [json.loads(line)]
        if row.get("phase") == "status"
    }


def _append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _thermal_nominal(value: str | None) -> bool:
    return value is None or "nominal" in value.lower()


def _wait_for_thermal(sampler: Sampler, timeout: float = 600.0) -> None:
    deadline = time.monotonic() + timeout
    while not _thermal_nominal(sampler.latest_thermal()):
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "thermal pressure did not return to nominal within 10 minutes"
            )
        time.sleep(30)


def integrate_window(
    samples: list[PowerSample],
    started_ns: int,
    ended_ns: int,
) -> dict[str, Any]:
    if not samples:
        raise ValueError("no complete powermetrics samples in measurement window")
    sampled_ns = sum(sample.elapsed_ns for sample in samples)
    weighted_cpu = (
        sum(sample.cpu_w * sample.elapsed_ns for sample in samples) / sampled_ns
    )

    def weighted(part: str) -> float | None:
        available = [sample for sample in samples if getattr(sample, part) is not None]
        if not available:
            return None
        duration = sum(sample.elapsed_ns for sample in available)
        return (
            sum(
                float(getattr(sample, part)) * sample.elapsed_ns for sample in available
            )
            / duration
        )

    gpu_w = weighted("gpu_w")
    ane_w = weighted("ane_w")
    cpu_energy_j = sum(
        sample.cpu_w * sample.elapsed_ns / 1_000_000_000 for sample in samples
    )

    def sampled_energy(part: str) -> float | None:
        available = [sample for sample in samples if getattr(sample, part) is not None]
        if not available:
            return None
        return sum(
            float(getattr(sample, part)) * sample.elapsed_ns / 1_000_000_000
            for sample in available
        )

    return {
        "powermetrics_samples": len(samples),
        "sampled_ms": sampled_ns / 1_000_000,
        "sample_coverage": sampled_ns / (ended_ns - started_ns),
        "mean_cpu_w": weighted_cpu,
        "mean_gpu_w": gpu_w,
        "mean_ane_w": ane_w,
        "cpu_energy_j": cpu_energy_j,
        "gpu_energy_j": sampled_energy("gpu_w"),
        "ane_energy_j": sampled_energy("ane_w"),
        "thermal_states": sorted(
            {sample.thermal for sample in samples if sample.thermal}
        ),
    }


def measure_casewise_results(
    repo_root: Path,
    accepted_results: list[Any],
    *,
    model_slug: str,
    warmup_seconds: float = 60,
    measurements: int = 10,
    batch_seconds: float = 1,
    interval_ms: int = 100,
    output: Path | None = None,
    resume: bool = True,
    reset_output: bool = False,
    sampler_factory: Any = PowermetricsSampler,
) -> list[dict[str, Any]]:
    if sampler_factory is PowermetricsSampler:
        PowermetricsSampler.preflight()
    out_path = output or measurement_path(repo_root, model_slug, "python")
    if reset_output and out_path.exists():
        out_path.unlink()
    if reset_output:
        shutil.rmtree(raw_metrics_dir(repo_root, model_slug), ignore_errors=True)
    completed = _completed_rows(out_path) if resume else {}
    statuses = _problem_statuses(out_path) if resume else set()
    new_rows: list[dict[str, Any]] = []
    host = _host_metadata()
    caffeinate = None
    if platform.system() == "Darwin" and shutil.which("caffeinate"):
        caffeinate = subprocess.Popen(["caffeinate", "-dimsu"])
    try:
        for accepted in accepted_results:
            slug = accepted.problem_slug
            workload_path = (
                repo_root
                / "leetcode-energy"
                / "reference"
                / "workloads"
                / f"{slug}.json"
            )
            if not workload_path.exists():
                status_key = (slug, "skipped_missing_workload")
                if status_key not in statuses:
                    row = {
                        "schema_version": 4,
                        "benchmark": BENCHMARK,
                        "phase": "status",
                        "status": status_key[1],
                        "problem": slug,
                        "model_slug": model_slug,
                        "language": accepted.language.key,
                        "source": str(accepted.source_path),
                        "reason": f"missing curated workload: {workload_path}",
                    }
                    _append_checkpoint(out_path, row)
                    new_rows.append(row)
                    statuses.add(status_key)
                continue
            workload = json.loads(workload_path.read_text())
            cases = workload.get("cases", [])
            hashes = [case_hash(case) for case in cases]
            if all(
                (slug, hashes[index], iteration) in completed
                for index in range(len(cases))
                for iteration in range(1, measurements + 1)
            ):
                continue
            raw_path = raw_metrics_dir(repo_root, model_slug) / f"{slug}.plist"
            archived_raw_path = raw_path.with_suffix(".plist.gz")
            archive_raw_plist(raw_path, archived_raw_path)
            sampler: Sampler = sampler_factory(raw_path, interval_ms)
            worker: WorkerClient | None = None
            try:
                try:
                    worker = WorkerClient(
                        repo_root, accepted.source_path, workload_path
                    )
                    worker.request({"action": "validate"})
                except RuntimeError as exc:
                    status_key = (slug, "skipped_validation_failed")
                    if status_key not in statuses:
                        row = {
                            "schema_version": 4,
                            "benchmark": BENCHMARK,
                            "phase": "status",
                            "status": status_key[1],
                            "problem": slug,
                            "model_slug": model_slug,
                            "language": accepted.language.key,
                            "source": str(accepted.source_path),
                            "workload_path": str(workload_path),
                            "workload_hash": workload["workload_hash"],
                            "workload_cases": len(cases),
                            "reason": str(exc),
                        }
                        _append_checkpoint(out_path, row)
                        new_rows.append(row)
                        statuses.add(status_key)
                    continue
                sampler.start()
                warmup = worker.request({"action": "warmup", "seconds": warmup_seconds})
                calibrations: dict[int, dict[str, Any]] = {}
                for case_index in range(len(cases)):
                    prior = [
                        row
                        for (problem, hashed, _), row in completed.items()
                        if problem == slug and hashed == hashes[case_index]
                    ]
                    if prior:
                        calibrations[case_index] = {
                            "batch_calls": int(prior[0]["batch_calls"]),
                            "pilot_wall_ns": prior[0].get("calibration_wall_ns"),
                        }
                    else:
                        calibrations[case_index] = worker.request(
                            {
                                "action": "calibrate",
                                "case_index": case_index,
                                "target_seconds": batch_seconds,
                            }
                        )
                for iteration in range(1, measurements + 1):
                    order = list(range(len(cases)))
                    seed = int(
                        hashlib.sha256(
                            f"{workload['workload_hash']}:{iteration}".encode()
                        ).hexdigest()[:16],
                        16,
                    )
                    random.Random(seed).shuffle(order)
                    for case_index in order:
                        hashed = hashes[case_index]
                        key = (slug, hashed, iteration)
                        if key in completed:
                            continue
                        _wait_for_thermal(sampler)
                        calibration = calibrations[case_index]
                        attempts = 0
                        while True:
                            attempts += 1
                            measured = worker.request(
                                {
                                    "action": "measure",
                                    "case_index": case_index,
                                    "batch_calls": calibration["batch_calls"],
                                }
                            )
                            sampler.wait_for_window(measured["ended_ns"])
                            samples = sampler.samples_for_window(
                                measured["started_ns"], measured["ended_ns"]
                            )
                            thermals = [
                                sample.thermal for sample in samples if sample.thermal
                            ]
                            if len(samples) >= 5 and all(
                                _thermal_nominal(value) for value in thermals
                            ):
                                break
                            if attempts >= 5:
                                raise RuntimeError(
                                    f"unable to collect five nominal samples for {slug} case {case_index}"
                                )
                            _wait_for_thermal(sampler)
                        energy = integrate_window(
                            samples, measured["started_ns"], measured["ended_ns"]
                        )
                        calls = int(measured["batch_calls"])
                        row = {
                            "schema_version": 4,
                            "benchmark": BENCHMARK,
                            "phase": "measure",
                            "problem": slug,
                            "case_index": case_index,
                            "case_hash": hashed,
                            "measurement_iteration": iteration,
                            "batch_calls": calls,
                            "batch_target_s": batch_seconds,
                            "batch_wall_ms": measured["wall_ns"] / 1_000_000,
                            "wall_ms_per_call": measured["wall_ns"] / 1_000_000 / calls,
                            "cpu_energy_j": energy["cpu_energy_j"],
                            "cpu_energy_j_per_call": energy["cpu_energy_j"] / calls,
                            "gpu_energy_j": energy["gpu_energy_j"],
                            "ane_energy_j": energy["ane_energy_j"],
                            "mean_cpu_w": energy["mean_cpu_w"],
                            "mean_gpu_w": energy["mean_gpu_w"],
                            "mean_ane_w": energy["mean_ane_w"],
                            "powermetrics_samples": energy["powermetrics_samples"],
                            "powermetrics_sampled_ms": energy["sampled_ms"],
                            "powermetrics_sample_coverage": energy["sample_coverage"],
                            "powermetrics_interval_ms": interval_ms,
                            "thermal_states": energy["thermal_states"],
                            "warmup_seconds": warmup_seconds,
                            "warmup_wall_ms": warmup["wall_ns"] / 1_000_000,
                            "warmup_sweeps": warmup["sweeps"],
                            "warmup_drift": warmup["warmup_drift"],
                            "warmup_stable": warmup["warmup_stable"],
                            "calibration_wall_ns": calibration.get("pilot_wall_ns"),
                            "model_slug": model_slug,
                            "language": accepted.language.key,
                            "leetcode_language": accepted.language.api_language,
                            "accepted": True,
                            "energy_source": "powermetrics-cpu",
                            "workload_hash": workload["workload_hash"],
                            "workload_cases": len(cases),
                            "workload_path": str(workload_path),
                            "source": str(accepted.source_path),
                            "source_hash": file_hash(accepted.source_path),
                            "result_path": str(accepted.result_path),
                            "raw_powermetrics_path": str(archived_raw_path),
                            "host": host,
                        }
                        _append_checkpoint(out_path, row)
                        completed[key] = row
                        new_rows.append(row)
            except RuntimeError as exc:
                status_key = (slug, "failed_measurement")
                if status_key not in statuses:
                    row = {
                        "schema_version": 4,
                        "benchmark": BENCHMARK,
                        "phase": "status",
                        "status": status_key[1],
                        "problem": slug,
                        "model_slug": model_slug,
                        "language": accepted.language.key,
                        "source": str(accepted.source_path),
                        "workload_path": str(workload_path),
                        "workload_hash": workload["workload_hash"],
                        "workload_cases": len(cases),
                        "reason": str(exc),
                        "resumable": True,
                    }
                    _append_checkpoint(out_path, row)
                    new_rows.append(row)
                    statuses.add(status_key)
            finally:
                sampler.stop()
                if worker is not None:
                    worker.close()
                archive_raw_plist(raw_path, archived_raw_path)
    finally:
        if caffeinate is not None:
            caffeinate.terminate()
            try:
                caffeinate.wait(timeout=3)
            except subprocess.TimeoutExpired:
                caffeinate.kill()
    return new_rows
