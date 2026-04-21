"""Measurement ingest and join.

Parses the JSONL traces produced by ``RAPL/perfarena_runner`` and
joins them with the generation ``meta.json`` sidecars to produce
one row per (model, language, problem, sample, iteration) that is
ready to feed the statistics layer and the leaderboard.

Output format: JSONL on disk, with an optional Parquet writer
behind a lazy import so the base dependency set stays small.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


# -- Parsing the RAPL runner output ----------------------------------------


@dataclass
class RawIteration:
    test: str
    language: str
    iteration: int
    phase: str
    wall_ms: float
    rapl_pkg_start_raw: int
    rapl_pkg_end_raw: int
    rapl_pkg_delta_raw: int
    samples: int
    exit_code: int
    source_file: str = ""

    @classmethod
    def from_jsonl_line(cls, line: str, source_file: str = "") -> "RawIteration":
        data = json.loads(line)
        return cls(
            test=data["test"],
            language=data["language"],
            iteration=int(data["iteration"]),
            phase=data["phase"],
            wall_ms=float(data["wall_ms"]),
            rapl_pkg_start_raw=int(data["rapl_pkg_start_raw"]),
            rapl_pkg_end_raw=int(data["rapl_pkg_end_raw"]),
            rapl_pkg_delta_raw=int(data["rapl_pkg_delta_raw"]),
            samples=int(data.get("samples", 0)),
            exit_code=int(data.get("exit_code", 0)),
            source_file=source_file,
        )


def read_rapl_jsonl(path: str | Path) -> list[RawIteration]:
    path = Path(path)
    rows: list[RawIteration] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(RawIteration.from_jsonl_line(line, source_file=str(path)))
    return rows


# -- Grouping: idle baseline + warm-up + measurement ------------------------


@dataclass
class IterationGroup:
    test: str
    language: str
    idle: RawIteration | None
    warmup: list[RawIteration] = field(default_factory=list)
    measurement: list[RawIteration] = field(default_factory=list)


def group_iterations(rows: list[RawIteration]) -> list[IterationGroup]:
    """Collapse a flat list of iteration rows into one group per (test, language) run.

    The RAPL runner writes one idle row, then K warm-up rows, then
    M measurement rows per invocation. A single ``<language>.jsonl``
    file accumulates many invocations across many benchmarks. This
    function splits them: every ``phase == "idle"`` row starts a
    new group.
    """
    groups: list[IterationGroup] = []
    current: IterationGroup | None = None
    for row in rows:
        if row.phase == "idle":
            if current is not None:
                groups.append(current)
            current = IterationGroup(
                test=row.test, language=row.language, idle=row
            )
        elif row.phase == "warmup":
            if current is None:
                current = IterationGroup(
                    test=row.test, language=row.language, idle=None
                )
            current.warmup.append(row)
        elif row.phase == "measure":
            if current is None:
                current = IterationGroup(
                    test=row.test, language=row.language, idle=None
                )
            current.measurement.append(row)
    if current is not None:
        groups.append(current)
    return groups


# -- Joining with the generation meta.json ---------------------------------


def _find_meta_for(
    generations_dir: Path,
    model_slug: str,
    language_folder: str,
    problem: str,
    sample_id: int,
    language_ext: str,
) -> Path | None:
    """Return the expected meta.json path for a (model, lang, problem, sample)."""
    candidate = (
        generations_dir
        / model_slug
        / language_folder
        / problem
        / f"sample_{sample_id:02d}{language_ext}.meta.json"
    )
    return candidate if candidate.exists() else None


def load_meta(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


@dataclass
class MeasurementRow:
    """One row in the measurement dataset."""

    # Identity keys.
    model_slug: str
    provider: str
    model: str
    language: str
    language_folder: str
    problem: str
    sample_id: int
    iteration: int
    phase: str  # "measure" (or "warmup" if you keep them)

    # Measurements.
    wall_ms: float
    rapl_pkg_delta_raw: int
    exit_code: int
    samples_during_run: int

    # Idle context.
    idle_wall_ms: float | None
    idle_rapl_pkg_delta_raw: int | None

    # Inherited provenance from meta.json.
    generation_meta_path: str
    generation_duration_s: float | None
    inference_metrics: dict[str, Any] = field(default_factory=dict)
    prompt_pair_sha256: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_slug": self.model_slug,
            "provider": self.provider,
            "model": self.model,
            "language": self.language,
            "language_folder": self.language_folder,
            "problem": self.problem,
            "sample_id": self.sample_id,
            "iteration": self.iteration,
            "phase": self.phase,
            "wall_ms": self.wall_ms,
            "rapl_pkg_delta_raw": self.rapl_pkg_delta_raw,
            "exit_code": self.exit_code,
            "samples_during_run": self.samples_during_run,
            "idle_wall_ms": self.idle_wall_ms,
            "idle_rapl_pkg_delta_raw": self.idle_rapl_pkg_delta_raw,
            "generation_meta_path": self.generation_meta_path,
            "generation_duration_s": self.generation_duration_s,
            "inference_metrics": self.inference_metrics,
            "prompt_pair_sha256": self.prompt_pair_sha256,
            "provenance": self.provenance,
        }


def join_group_with_meta(
    group: IterationGroup,
    meta: dict[str, Any],
    include_warmup: bool = False,
) -> Iterator[MeasurementRow]:
    """Produce one MeasurementRow per (measurement) iteration in the group."""
    iters: list[RawIteration]
    if include_warmup:
        iters = list(group.warmup) + list(group.measurement)
    else:
        iters = list(group.measurement)

    idle_wall_ms = group.idle.wall_ms if group.idle else None
    idle_rapl = group.idle.rapl_pkg_delta_raw if group.idle else None

    model_slug = f"{meta['provider']}__{meta['model']}".replace("/", "_")
    inference_metrics = (meta.get("inference") or {}).get("metrics", {})

    for it in iters:
        yield MeasurementRow(
            model_slug=model_slug,
            provider=meta["provider"],
            model=meta["model"],
            language=meta["language"],
            language_folder=meta["language_folder"],
            problem=meta["problem"],
            sample_id=int(meta["sample_id"]),
            iteration=it.iteration,
            phase=it.phase,
            wall_ms=it.wall_ms,
            rapl_pkg_delta_raw=it.rapl_pkg_delta_raw,
            exit_code=it.exit_code,
            samples_during_run=it.samples,
            idle_wall_ms=idle_wall_ms,
            idle_rapl_pkg_delta_raw=idle_rapl,
            generation_meta_path="",  # caller fills in
            generation_duration_s=(meta.get("response") or {}).get("duration_s"),
            inference_metrics=inference_metrics,
            prompt_pair_sha256=(meta.get("prompts") or {}).get("prompt_pair_sha256", ""),
            provenance=meta.get("provenance", {}),
        )


# -- Writers ---------------------------------------------------------------


def write_jsonl(rows: list[MeasurementRow], out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row.to_dict(), sort_keys=True))
            fh.write("\n")
    return out


def write_parquet(rows: list[MeasurementRow], out_path: str | Path) -> Path:
    """Write rows to Parquet using pyarrow if available."""
    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Parquet output requires `pip install pyarrow`."
        ) from exc

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist([row.to_dict() for row in rows])
    pq.write_table(table, str(out))
    return out
