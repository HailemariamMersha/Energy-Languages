"""LeetCode pipeline support for the Energy-Languages fork.

The primary energy workflow imports already-judged solutions from the
PerfArena dataset API, stages them in ``leetcode-energy/``, then validates and
measures accepted code locally. Legacy generation/submission helpers remain in
this module for creating new dataset rows, but the energy path does not talk to
LeetCode directly.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import ast
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from langchain_core.messages import HumanMessage, SystemMessage

from .generation.llm import build_chat_model
from .generation.pipeline import extract_code
from .provenance import capture as capture_provenance


# ---------------------------------------------------------------------------
# Language registry


@dataclass(frozen=True)
class LeetCodeLanguage:
    key: str
    api_language: str
    folder: str
    display_name: str
    extension: str
    fence_aliases: tuple[str, ...]


LEETCODE_LANGUAGES: dict[str, LeetCodeLanguage] = {
    "python": LeetCodeLanguage(
        key="python",
        api_language="python3",
        folder="Python",
        display_name="Python 3",
        extension=".py",
        fence_aliases=("python", "py", "python3"),
    ),
    "javascript": LeetCodeLanguage(
        key="javascript",
        api_language="javascript",
        folder="JavaScript",
        display_name="JavaScript",
        extension=".js",
        fence_aliases=("javascript", "js"),
    ),
    "typescript": LeetCodeLanguage(
        key="typescript",
        api_language="typescript",
        folder="TypeScript",
        display_name="TypeScript",
        extension=".ts",
        fence_aliases=("typescript", "ts"),
    ),
    "java": LeetCodeLanguage(
        key="java",
        api_language="java",
        folder="Java",
        display_name="Java",
        extension=".java",
        fence_aliases=("java",),
    ),
    "csharp": LeetCodeLanguage(
        key="csharp",
        api_language="csharp",
        folder="CSharp",
        display_name="C#",
        extension=".cs",
        fence_aliases=("csharp", "cs", "c#"),
    ),
    "cpp": LeetCodeLanguage(
        key="cpp",
        api_language="cpp",
        folder="C++",
        display_name="C++",
        extension=".cpp",
        fence_aliases=("cpp", "c++", "cxx"),
    ),
    "php": LeetCodeLanguage(
        key="php",
        api_language="php",
        folder="PHP",
        display_name="PHP",
        extension=".php",
        fence_aliases=("php",),
    ),
    "go": LeetCodeLanguage(
        key="go",
        api_language="golang",
        folder="Go",
        display_name="Go",
        extension=".go",
        fence_aliases=("go", "golang"),
    ),
    "rust": LeetCodeLanguage(
        key="rust",
        api_language="rust",
        folder="Rust",
        display_name="Rust",
        extension=".rs",
        fence_aliases=("rust", "rs"),
    ),
    "ruby": LeetCodeLanguage(
        key="ruby",
        api_language="ruby",
        folder="Ruby",
        display_name="Ruby",
        extension=".rb",
        fence_aliases=("ruby", "rb"),
    ),
}


def get_language(key: str) -> LeetCodeLanguage:
    key = key.strip().lower()
    if key == "python3":
        key = "python"
    if key == "golang":
        key = "go"
    if key not in LEETCODE_LANGUAGES:
        raise KeyError(
            f"Unknown LeetCode-Energy language {key!r}. "
            f"Known: {sorted(LEETCODE_LANGUAGES)}"
        )
    return LEETCODE_LANGUAGES[key]


def get_language_by_api_slug(api_language: str) -> LeetCodeLanguage:
    api_language = api_language.strip().lower()
    for language in LEETCODE_LANGUAGES.values():
        if language.api_language == api_language:
            return language
    return get_language(api_language)


def parse_language_list(value: str | None) -> list[LeetCodeLanguage]:
    if not value:
        return list(LEETCODE_LANGUAGES.values())
    return [get_language(part) for part in value.split(",") if part.strip()]


def parse_slug_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


# ---------------------------------------------------------------------------
# Paths and local problem loading


def leetcode_root(repo_root: Path) -> Path:
    return repo_root / "leetcode-energy"


def leetcode_reference_root(repo_root: Path) -> Path:
    return leetcode_root(repo_root) / "reference"


def workload_path(repo_root: Path, slug: str) -> Path:
    return leetcode_reference_root(repo_root) / "workloads" / f"{slug}.json"


def expected_output_path(repo_root: Path, slug: str) -> Path:
    return leetcode_reference_root(repo_root) / "outputs" / f"{slug}.json"


def default_curated_dataset_path(repo_root: Path) -> Path:
    return (
        repo_root.parent
        / "LeetCodeDataset93"
        / "curated"
        / "leetcode_energy_93_curated.jsonl"
    )


def cell_dir(repo_root: Path, language: LeetCodeLanguage, slug: str) -> Path:
    return leetcode_root(repo_root) / language.folder / slug


def solution_path(repo_root: Path, language: LeetCodeLanguage, slug: str) -> Path:
    return cell_dir(repo_root, language, slug) / f"solution{language.extension}"


def generations_root(repo_root: Path) -> Path:
    return repo_root / "perfarena_out" / "leetcode_generations"


def dataset_solutions_root(repo_root: Path) -> Path:
    return repo_root / "perfarena_out" / "leetcode_dataset_solutions"


def dataset_solution_path(
    repo_root: Path,
    model_slug: str,
    language: LeetCodeLanguage,
    slug: str,
) -> Path:
    return (
        dataset_solutions_root(repo_root)
        / model_slug
        / language.folder
        / slug
        / f"solution{language.extension}"
    )


def model_import_progress_path(
    repo_root: Path,
    model_slug: str,
    language: LeetCodeLanguage,
) -> Path:
    return (
        repo_root
        / "perfarena_out"
        / "leetcode_imports"
        / model_slug
        / f"{language.key}_progress.json"
    )


def model_measurement_path(
    repo_root: Path,
    model_slug: str,
    language: LeetCodeLanguage,
) -> Path:
    return (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / f"{language.key}_curated.jsonl"
    )


def model_summary_prefix(
    repo_root: Path,
    model_slug: str,
    language: LeetCodeLanguage,
) -> Path:
    return (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / f"{language.key}_curated_summary"
    )


def _sibling_sampled_problems(repo_root: Path) -> Path:
    return repo_root.parent / "perfarena-leetcode" / "data" / "sampled_problems.json"


def load_local_sampled_problems(repo_root: Path) -> list[dict[str, Any]]:
    path = _sibling_sampled_problems(repo_root)
    if not path.exists():
        raise FileNotFoundError(
            "Cannot find local sampled LeetCode problems. Expected "
            f"{path}; start the backend or place perfarena-leetcode next to "
            "Energy-Languages."
        )
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}")
    out: list[dict[str, Any]] = []
    for item in data:
        tags = item.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        out.append(
            {
                "id": item.get("id") or item.get("external_id"),
                "title_slug": item["title_slug"],
                "title": item["title"],
                "level": item["level"],
                "tags": tags,
                "content": item.get("content", ""),
                "hints": item.get("hints"),
                "code_snippets": item.get("code_snippets", {}),
            }
        )
    return out


def filter_problems(
    problems: Iterable[dict[str, Any]],
    slugs: list[str] | None,
) -> list[dict[str, Any]]:
    rows = list(problems)
    if not slugs:
        return rows
    wanted = set(slugs)
    found = {p["title_slug"] for p in rows}
    missing = sorted(wanted - found)
    if missing:
        raise ValueError(f"Unknown LeetCode problem slug(s): {missing}")
    return [p for p in rows if p["title_slug"] in wanted]


# ---------------------------------------------------------------------------
# HTTP client


def default_base_url() -> str:
    return (
        os.environ.get("PERFARENA_LEETCODE_BASE_URL")
        or os.environ.get("ARENA_BASE_URL")
        or "http://localhost:8000"
    ).rstrip("/")


def default_api_key() -> str | None:
    return os.environ.get("ARENA_API_KEY") or os.environ.get("PERFARENA_API_KEY")


class LeetCodeApiError(RuntimeError):
    pass


class LeetCodeApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = (base_url or default_base_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else default_api_key()
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
        )
        req.add_header("Content-Type", "application/json")
        if auth:
            if not self.api_key:
                raise LeetCodeApiError(
                    "Missing API key. Set ARENA_API_KEY or PERFARENA_API_KEY."
                )
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise LeetCodeApiError(
                f"HTTP {exc.code} {method} {path}: {detail}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise LeetCodeApiError(
                f"Cannot reach LeetCode backend at {self.base_url}: {exc}"
            ) from exc
        if not raw:
            return {}
        return json.loads(raw)

    def list_problems(self) -> list[dict[str, Any]]:
        return self.request("GET", "/api/problems")

    def get_problem(self, slug: str) -> dict[str, Any]:
        return self.request("GET", f"/api/problems/{slug}")

    def create_submission(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/api/submissions", body=payload, auth=True)

    def append_attempts(
        self,
        submission_id: int,
        attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/api/submissions/{submission_id}/attempts",
            body={"attempts": attempts},
            auth=True,
        )

    def submission_attempts(self, submission_id: int) -> list[dict[str, Any]]:
        return self.request("GET", f"/api/submissions/{submission_id}/attempts")

    def submission_progress(self, submission_id: int) -> dict[str, Any]:
        return self.request("GET", f"/api/submissions/{submission_id}/progress")


def load_problem_catalog(
    repo_root: Path,
    client: LeetCodeApiClient | None,
    *,
    prefer_local: bool = False,
) -> list[dict[str, Any]]:
    if prefer_local:
        return load_local_sampled_problems(repo_root)
    if client is not None:
        try:
            return client.list_problems()
        except LeetCodeApiError:
            pass
    return load_local_sampled_problems(repo_root)


def hydrate_problem_details(
    repo_root: Path,
    problems: list[dict[str, Any]],
    client: LeetCodeApiClient | None,
    *,
    prefer_local: bool = False,
) -> list[dict[str, Any]]:
    try:
        local_by_slug = {
            p["title_slug"]: p for p in load_local_sampled_problems(repo_root)
        }
    except FileNotFoundError:
        local_by_slug = {}
    out: list[dict[str, Any]] = []
    for problem in problems:
        slug = problem["title_slug"]
        detail: dict[str, Any] | None = None
        if not prefer_local and client is not None:
            try:
                detail = client.get_problem(slug)
            except LeetCodeApiError:
                detail = None
        if detail is None:
            detail = dict(local_by_slug.get(slug, problem))
        tags = detail.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        detail["tags"] = tags
        out.append(detail)
    return out


# ---------------------------------------------------------------------------
# Scaffolding


MAKEFILE_TEMPLATE = """\
LANGUAGE = {language_key}
LEETCODE_LANGUAGE = {api_language}
SLUG = {slug}
SOURCE = solution{extension}
MODEL_SLUG ?= manual__manual
WORKLOAD = ../../reference/workloads/$(SLUG).json
REFERENCE_OUTPUT = ../../reference/outputs/$(SLUG).json

.PHONY: compile validate measure clean

compile:
\tperfarena leetcode-compile --language $(LANGUAGE) --source $(SOURCE) --result compile.json

validate:
\tperfarena leetcode-workload-run --language $(LANGUAGE) --problem $(SLUG) --source $(SOURCE) --workload $(WORKLOAD) --expected $(REFERENCE_OUTPUT)

measure: validate
\tperfarena leetcode-measure --language $(LANGUAGE) --problems $(SLUG) --model-slug $(MODEL_SLUG) --accepted-only

clean:
\trm -f compile.json result*.json energy_*.json
\trm -rf __pycache__ .pytest_cache
"""


def scaffold(
    repo_root: Path,
    languages: list[LeetCodeLanguage],
    problems: list[dict[str, Any]],
    *,
    overwrite_solution: bool = False,
) -> list[Path]:
    written: list[Path] = []
    for lang in languages:
        for problem in problems:
            slug = problem["title_slug"]
            cdir = cell_dir(repo_root, lang, slug)
            cdir.mkdir(parents=True, exist_ok=True)

            pmeta = {
                "title_slug": slug,
                "title": problem.get("title"),
                "level": problem.get("level"),
                "tags": problem.get("tags", []),
                "id": problem.get("id"),
                "content": problem.get("content", ""),
                "hints": problem.get("hints"),
                "code_snippets": problem.get("code_snippets", {}),
            }
            ppath = cdir / "problem.json"
            ppath.write_text(json.dumps(pmeta, indent=2, sort_keys=True))
            written.append(ppath)

            src = cdir / f"solution{lang.extension}"
            if overwrite_solution or not src.exists():
                snippet = (problem.get("code_snippets") or {}).get(
                    lang.api_language,
                    "",
                )
                src.write_text((snippet.rstrip() + "\n") if snippet else "")
                written.append(src)

            mf = cdir / "Makefile"
            mf.write_text(
                MAKEFILE_TEMPLATE.format(
                    language_key=lang.key,
                    api_language=lang.api_language,
                    slug=slug,
                    extension=lang.extension,
                )
            )
            written.append(mf)
    return written


# ---------------------------------------------------------------------------
# Dataset API imports


def iter_dataset_solutions(
    *,
    base_url: str | None = None,
    language: LeetCodeLanguage | None = None,
    model: str | None = None,
    only_accepted: bool = True,
    timeout: int = 300,
) -> Iterable[dict[str, Any]]:
    """Stream solution rows from the PerfArena dataset API.

    The endpoint returns newline-delimited JSON and includes the exact stored
    source code for each judged attempt.
    """

    query: dict[str, str] = {}
    if language is not None:
        query["language"] = language.api_language
    if model:
        query["model"] = model
    if only_accepted:
        query["only_accepted"] = "true"
    path = "/api/datasets/solutions"
    qs = urllib.parse.urlencode(query)
    url = f"{(base_url or default_base_url()).rstrip('/')}{path}"
    if qs:
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line:
                    yield json.loads(line)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise LeetCodeApiError(f"HTTP {exc.code} GET {path}: {detail}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise LeetCodeApiError(f"Cannot reach dataset API at {url}: {exc}") from exc


def _dataset_problem_from_row(row: dict[str, Any]) -> dict[str, Any]:
    tags = row.get("problem_tags") or []
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    slug = row.get("problem_slug") or row.get("title_slug")
    return {
        "id": row.get("problem_id"),
        "title_slug": slug,
        "title": row.get("problem_title") or slug,
        "level": row.get("problem_level"),
        "tags": tags,
        "content": row.get("content", ""),
        "hints": row.get("hints"),
        "code_snippets": row.get("code_snippets", {}),
    }


def _problem_detail_for_dataset_row(
    repo_root: Path,
    client: LeetCodeApiClient,
    row: dict[str, Any],
) -> dict[str, Any]:
    slug = row.get("problem_slug") or row.get("title_slug")
    if not slug:
        raise ValueError("dataset row is missing problem_slug")
    try:
        detail = hydrate_problem_details(
            repo_root,
            [_dataset_problem_from_row(row)],
            client,
            prefer_local=False,
        )[0]
        fallback = _dataset_problem_from_row(row)
        detail.setdefault("title_slug", slug)
        detail.setdefault("title", fallback.get("title"))
        detail.setdefault("level", fallback.get("level"))
        detail.setdefault("tags", fallback.get("tags", []))
        detail.setdefault("content", fallback.get("content", ""))
        detail.setdefault("hints", fallback.get("hints"))
        detail.setdefault("code_snippets", fallback.get("code_snippets", {}))
        return detail
    except Exception:  # noqa: BLE001
        return _dataset_problem_from_row(row)


def _dataset_trace(row: dict[str, Any]) -> dict[str, Any]:
    trace = row.get("trace")
    if isinstance(trace, dict):
        return trace
    return {}


def _dataset_provider(row: dict[str, Any]) -> str:
    trace = _dataset_trace(row)
    provider = trace.get("provider")
    if isinstance(provider, str) and provider.strip():
        return provider.strip()
    params = row.get("model_params")
    if isinstance(params, dict):
        provider = params.get("provider")
        if isinstance(provider, str) and provider.strip():
            return provider.strip()
    return "dataset"


def model_slug_from_dataset_row(row: dict[str, Any]) -> str:
    model = str(row.get("model_name") or row.get("model") or "unknown")
    return slugify_model(_dataset_provider(row), model)


def select_single_model_slug(
    rows: list[dict[str, Any]],
    *,
    requested_model_slug: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    if not rows:
        raise ValueError("no dataset rows available")
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_slug.setdefault(model_slug_from_dataset_row(row), []).append(row)
    if requested_model_slug:
        selected = by_slug.get(requested_model_slug, [])
        if not selected:
            raise ValueError(
                f"model_slug {requested_model_slug!r} did not match any returned row"
            )
        return requested_model_slug, selected
    if len(by_slug) != 1:
        raise ValueError(
            "multiple model slugs matched the requested model; pass --model-slug "
            f"to disambiguate: {', '.join(sorted(by_slug))}"
        )
    model_slug = next(iter(by_slug))
    return model_slug, by_slug[model_slug]


def _dataset_row_is_accepted(row: dict[str, Any]) -> bool:
    if row.get("accepted") is True:
        return True
    status = str(row.get("status_msg") or row.get("status") or "")
    return status.lower() == "accepted"


def _dataset_attempt_from_row(row: dict[str, Any]) -> dict[str, Any]:
    accepted = _dataset_row_is_accepted(row)
    status = row.get("status_msg") or row.get("status")
    return {
        "accepted": accepted,
        "status": status,
        "status_msg": status,
        "problem_slug": row.get("problem_slug") or row.get("title_slug"),
        "problem_title": row.get("problem_title"),
        "level": row.get("problem_level"),
        "language": row.get("language"),
        "model_name": row.get("model_name"),
        "model_version": row.get("model_version"),
        "runtime_ms": row.get("runtime_ms"),
        "memory_mb": row.get("memory_mb"),
        "total_correct": row.get("total_correct"),
        "total_testcases": row.get("total_testcases"),
        "trace_hash": row.get("trace_hash"),
        "trace": _dataset_trace(row),
        "runs": [
            {
                "status_msg": status,
                "accepted": accepted,
                "runtime_ms": row.get("runtime_ms"),
                "memory_mb": row.get("memory_mb"),
                "total_correct": row.get("total_correct"),
                "total_testcases": row.get("total_testcases"),
            }
        ],
    }


def imported_dataset_result(
    *,
    row: dict[str, Any],
    language: LeetCodeLanguage,
    source: Path,
    base_url: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "benchmark": "leetcode-energy",
        "problem": row.get("problem_slug") or row.get("title_slug"),
        "language": language.key,
        "leetcode_language": language.api_language,
        "source": str(source),
        "submitted": False,
        "imported": True,
        "imported_from": {
            "kind": "perfarena_dataset_api",
            "base_url": base_url.rstrip("/"),
            "endpoint": "/api/datasets/solutions",
            "submission_id": row.get("submission_id"),
            "trace_hash": row.get("trace_hash"),
        },
        "attempt": _dataset_attempt_from_row(row),
        "dataset": {
            "model_name": row.get("model_name"),
            "model_version": row.get("model_version"),
            "model_slug": model_slug_from_dataset_row(row),
            "problem_title": row.get("problem_title"),
            "problem_level": row.get("problem_level"),
            "problem_tags": row.get("problem_tags"),
        },
    }


def import_dataset_solution_rows(
    *,
    repo_root: Path,
    rows: Iterable[dict[str, Any]],
    base_url: str,
    languages: list[LeetCodeLanguage] | None = None,
    model_version: str | None = None,
    problem_slugs: list[str] | None = None,
    progress_path: Path,
    accepted_only: bool = True,
    overwrite_source: bool = True,
    hydrate_problem: bool = True,
    stage_solution: bool = True,
) -> dict[str, Any]:
    allowed_languages = {lang.api_language: lang for lang in languages or []}
    wanted_problems = set(problem_slugs or [])
    client = LeetCodeApiClient(base_url=base_url) if hydrate_problem else None
    progress = load_progress(progress_path)
    progress["schema_version"] = 1
    progress["benchmark"] = "leetcode-energy"
    progress["source"] = "perfarena_dataset_api"
    progress["base_url"] = base_url.rstrip("/")
    records = progress.setdefault("records", {})
    imports = progress.setdefault("dataset_imports", {})
    stats = {
        "seen": 0,
        "imported": 0,
        "skipped": 0,
        "by_model_slug": {},
        "by_language": {},
    }

    for row in rows:
        stats["seen"] += 1
        api_language = str(row.get("language") or "").strip().lower()
        if not api_language:
            stats["skipped"] += 1
            continue
        try:
            language = allowed_languages.get(api_language) or get_language_by_api_slug(
                api_language
            )
        except KeyError:
            stats["skipped"] += 1
            continue
        if allowed_languages and api_language not in allowed_languages:
            stats["skipped"] += 1
            continue
        if model_version and row.get("model_version") != model_version:
            stats["skipped"] += 1
            continue
        slug = row.get("problem_slug") or row.get("title_slug")
        if not slug:
            stats["skipped"] += 1
            continue
        if wanted_problems and slug not in wanted_problems:
            stats["skipped"] += 1
            continue
        if accepted_only and not _dataset_row_is_accepted(row):
            stats["skipped"] += 1
            continue
        code = row.get("code")
        if not isinstance(code, str) or not code.strip():
            stats["skipped"] += 1
            continue

        model_slug = model_slug_from_dataset_row(row)
        problem = (
            _problem_detail_for_dataset_row(repo_root, client, row)
            if client is not None
            else _dataset_problem_from_row(row)
        )
        scaffold(repo_root, [language], [problem], overwrite_solution=False)

        source = dataset_solution_path(repo_root, model_slug, language, slug)
        if source.exists() and not overwrite_source:
            records[f"skipped|{language.key}|{slug}|{stats['seen']}"] = {
                "status": "skipped",
                "reason": "solution exists and overwrite_source is false",
                "source": str(source),
            }
            stats["skipped"] += 1
            continue

        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(code.rstrip() + "\n")
        if stage_solution:
            staged = solution_path(repo_root, language, slug)
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(code.rstrip() + "\n")
        result_path = cell_dir(repo_root, language, slug) / f"result_{model_slug}.json"
        result = imported_dataset_result(
            row=row,
            language=language,
            source=source,
            base_url=base_url,
        )
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True))

        rec_key = f"{model_slug}|{language.key}|{slug}"
        records[rec_key] = {
            "status": "complete",
            "accepted": result["attempt"]["accepted"],
            "final_status": result["attempt"]["status"],
            "result_path": str(result_path),
            "source": str(source),
            "imported": True,
            "submission_id": row.get("submission_id"),
            "trace_hash": row.get("trace_hash"),
        }
        imports[rec_key] = {
            "model_name": row.get("model_name"),
            "model_version": row.get("model_version"),
            "leetcode_language": api_language,
            "problem": slug,
        }
        stats["imported"] += 1
        stats["by_model_slug"][model_slug] = stats["by_model_slug"].get(model_slug, 0) + 1
        stats["by_language"][language.key] = stats["by_language"].get(language.key, 0) + 1
        save_progress(progress_path, progress)

    progress["dataset_import_stats"] = stats
    save_progress(progress_path, progress)
    return progress


def import_dataset_solutions(
    *,
    repo_root: Path,
    base_url: str | None,
    languages: list[LeetCodeLanguage],
    model: str | None,
    model_version: str | None,
    problem_slugs: list[str] | None,
    progress_path: Path,
    accepted_only: bool = True,
    overwrite_source: bool = True,
    hydrate_problem: bool = True,
    stage_solution: bool = True,
) -> dict[str, Any]:
    resolved_base_url = (base_url or default_base_url()).rstrip("/")
    all_rows: list[dict[str, Any]] = []
    for language in languages:
        all_rows.extend(
            iter_dataset_solutions(
                base_url=resolved_base_url,
                language=language,
                model=model,
                only_accepted=accepted_only,
            )
        )
    return import_dataset_solution_rows(
        repo_root=repo_root,
        rows=all_rows,
        base_url=resolved_base_url,
        languages=languages,
        model_version=model_version,
        problem_slugs=problem_slugs,
        progress_path=progress_path,
        accepted_only=accepted_only,
        overwrite_source=overwrite_source,
        hydrate_problem=hydrate_problem,
        stage_solution=stage_solution,
    )


# ---------------------------------------------------------------------------
# Compile checks


@dataclass
class CompileResult:
    language: str
    source: str
    ok: bool
    returncode: int
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "source": self.source,
            "ok": self.ok,
            "returncode": self.returncode,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_s": self.duration_s,
            "skipped": self.skipped,
        }


def _missing_tool(lang: LeetCodeLanguage, source: Path, tool: str) -> CompileResult:
    return CompileResult(
        language=lang.key,
        source=str(source),
        ok=False,
        returncode=127,
        command=[tool],
        stderr=f"{tool} not found on PATH",
        skipped=True,
    )


def _run_compile(
    lang: LeetCodeLanguage,
    source: Path,
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 120.0,
) -> CompileResult:
    t0 = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return CompileResult(
        language=lang.key,
        source=str(source),
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        command=command,
        stdout=proc.stdout,
        stderr=proc.stderr,
        duration_s=time.monotonic() - t0,
    )


def compile_solution(language: LeetCodeLanguage, source: Path) -> CompileResult:
    source = source.resolve()
    if not source.exists():
        return CompileResult(
            language=language.key,
            source=str(source),
            ok=False,
            returncode=2,
            command=[],
            stderr=f"source not found: {source}",
        )

    if language.key == "python":
        if not shutil.which("python3"):
            return _missing_tool(language, source, "python3")
        return _run_compile(language, source, ["python3", "-m", "py_compile", str(source)])

    if language.key == "javascript":
        if not shutil.which("node"):
            return _missing_tool(language, source, "node")
        return _run_compile(language, source, ["node", "--check", str(source)])

    if language.key == "typescript":
        if not shutil.which("tsc"):
            return _missing_tool(language, source, "tsc")
        return _run_compile(
            language,
            source,
            ["tsc", "--noEmit", "--skipLibCheck", str(source)],
        )

    if language.key == "java":
        if not shutil.which("javac"):
            return _missing_tool(language, source, "javac")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Solution.java"
            path.write_text(source.read_text())
            return _run_compile(language, source, ["javac", str(path)])

    if language.key == "cpp":
        if not shutil.which("g++"):
            return _missing_tool(language, source, "g++")
        wrapped = (
            "#include <bits/stdc++.h>\nusing namespace std;\n"
            + source.read_text()
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "solution.cpp"
            path.write_text(wrapped)
            return _run_compile(
                language,
                source,
                ["g++", "-std=c++17", "-fsyntax-only", str(path)],
            )

    if language.key == "php":
        if not shutil.which("php"):
            return _missing_tool(language, source, "php")
        text = source.read_text()
        if text.lstrip().startswith("<?php"):
            return _run_compile(language, source, ["php", "-l", str(source)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "solution.php"
            path.write_text("<?php\n" + text)
            return _run_compile(language, source, ["php", "-l", str(path)])

    if language.key == "go":
        if not shutil.which("go"):
            return _missing_tool(language, source, "go")
        text = source.read_text()
        if not re.search(r"^\s*package\s+\w+", text, re.MULTILINE):
            text = "package main\n\n" + text
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "solution.go"
            path.write_text(text)
            return _run_compile(language, source, ["go", "test"], cwd=Path(tmp))

    if language.key == "rust":
        if not shutil.which("rustc"):
            return _missing_tool(language, source, "rustc")
        text = source.read_text()
        if "impl Solution" in text and "struct Solution" not in text:
            text = "pub struct Solution;\n" + text
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "solution.rs"
            path.write_text(text)
            return _run_compile(
                language,
                source,
                ["rustc", "--edition=2021", "--crate-type", "lib", str(path)],
            )

    if language.key == "ruby":
        if not shutil.which("ruby"):
            return _missing_tool(language, source, "ruby")
        return _run_compile(language, source, ["ruby", "-c", str(source)])

    if language.key == "csharp":
        if not shutil.which("dotnet"):
            return _missing_tool(language, source, "dotnet")
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            (tdir / "Solution.cs").write_text(source.read_text())
            (tdir / "Solution.csproj").write_text(
                "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
                "  <PropertyGroup>\n"
                "    <TargetFramework>net8.0</TargetFramework>\n"
                "    <OutputType>Library</OutputType>\n"
                "    <ImplicitUsings>enable</ImplicitUsings>\n"
                "    <Nullable>disable</Nullable>\n"
                "  </PropertyGroup>\n"
                "</Project>\n"
            )
            return _run_compile(
                language,
                source,
                ["dotnet", "build", "--nologo", "--verbosity", "quiet"],
                cwd=tdir,
                timeout=240.0,
            )

    raise ValueError(f"no compile checker for {language.key}")


# ---------------------------------------------------------------------------
# Generation and submission


def slugify_model(provider: str, model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", f"{provider}__{model}")


def _response_to_text(response: Any) -> str:
    content = response.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and "text" in part:
            parts.append(part["text"])
    return "".join(parts)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _prompt_text(problem: dict[str, Any], language: LeetCodeLanguage) -> tuple[str, str]:
    snippet = (problem.get("code_snippets") or {}).get(language.api_language, "")
    system = (
        f"You are a competitive-programming assistant. Solve the problem in "
        f"{language.display_name} using LeetCode's standard Solution shape. "
        "Return one fenced code block containing only the final solution."
    )
    hints = problem.get("hints")
    user = (
        f"Solve this LeetCode problem `{problem['title_slug']}`.\n\n"
        f"{problem.get('content', '')}\n\n"
    )
    if snippet:
        user += (
            "Starter code. Preserve the exact class name, method name, "
            "argument names, and return shape from this snippet; only fill in "
            "the method body.\n"
            f"```{language.fence_aliases[0]}\n{snippet}\n```\n\n"
        )
    if hints:
        user += f"Hints:\n{hints}\n\n"
    user += f"Write a correct and efficient {language.display_name} solution."
    return system, user


@dataclass
class LeetCodeGenerationResult:
    source_path: Path
    raw_path: Path
    meta_path: Path
    code: str
    raw: str
    metadata: dict[str, Any] = field(default_factory=dict)


class EmptyCodeGenerationError(RuntimeError):
    """Raised when every generation attempt extracts to empty source."""


def generate_solution(
    repo_root: Path,
    problem: dict[str, Any],
    language: LeetCodeLanguage,
    *,
    provider: str,
    model: str,
    sample_id: int = 0,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    top_p: float | None = None,
    top_k: int | None = None,
    seed: int | None = None,
    stage: bool = True,
    empty_code_retries: int = 2,
) -> LeetCodeGenerationResult:
    system_text, user_text = _prompt_text(problem, language)
    messages = [SystemMessage(content=system_text), HumanMessage(content=user_text)]
    chat = build_chat_model(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        top_k=top_k,
        seed=seed,
    )
    t0 = time.monotonic()
    attempts: list[dict[str, Any]] = []
    retry_hint = HumanMessage(
        content=(
            "The previous response did not contain any extractable source code. "
            "Return exactly one fenced code block containing the complete "
            "solution, and preserve the starter class and method signature."
        )
    )
    max_attempts = max(1, empty_code_retries + 1)
    raw = ""
    code = ""
    for attempt_index in range(max_attempts):
        attempt_messages = messages if attempt_index == 0 else [*messages, retry_hint]
        response = chat.invoke(attempt_messages)
        raw = _response_to_text(response)
        code = extract_code(raw, language.key)
        attempts.append(
            {
                "attempt_index": attempt_index,
                "raw_chars": len(raw),
                "extracted_code_chars": len(code),
                "empty_code": not bool(code.strip()),
            }
        )
        if code.strip():
            break
    duration_s = time.monotonic() - t0
    out_dir = (
        generations_root(repo_root)
        / slugify_model(provider, model)
        / language.folder
        / problem["title_slug"]
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    source = out_dir / f"sample_{sample_id:02d}{language.extension}"
    raw_path = source.with_suffix(source.suffix + ".raw.md")
    meta_path = source.with_suffix(source.suffix + ".meta.json")
    source.write_text(code)
    raw_path.write_text(raw)

    prompt_hash = hashlib.sha256(
        (system_text + "\n---\n" + user_text).encode()
    ).hexdigest()
    metadata = {
        "schema_version": 1,
        "benchmark": "leetcode-energy",
        "provider": provider,
        "model": model,
        "language": language.key,
        "leetcode_language": language.api_language,
        "language_folder": language.folder,
        "problem": problem["title_slug"],
        "sample_id": sample_id,
        "generation_parameters": {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "seed": seed,
        },
        "prompts": {
            "system_prompt_sha256": hashlib.sha256(system_text.encode()).hexdigest(),
            "user_prompt_sha256": hashlib.sha256(user_text.encode()).hexdigest(),
            "prompt_pair_sha256": prompt_hash,
            "system_prompt": system_text,
            "user_prompt": user_text,
        },
        "response": {
            "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "raw_chars": len(raw),
            "extracted_code_chars": len(code),
            "duration_s": duration_s,
            "attempts": attempts,
            "empty_code_retries": empty_code_retries,
        },
        "trace": {
            "prompt": user_text,
            "system_prompt": system_text,
            "raw_response": raw,
            "reasoning": None,
            "model": model,
            "provider": provider,
            "endpoint": os.environ.get("OLLAMA_HOST") if provider == "ollama" else None,
            "params": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "top_k": top_k,
                "seed": seed,
            },
            "created_at": _now(),
        },
        "provenance": capture_provenance(),
        "paths": {
            "source": str(source),
            "raw": str(raw_path),
        },
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))

    if not code.strip():
        raise EmptyCodeGenerationError(
            f"{problem['title_slug']}: empty code after {max_attempts} "
            f"generation attempt(s); wrote raw response to {raw_path}"
        )

    if stage:
        dest = solution_path(repo_root, language, problem["title_slug"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)

    return LeetCodeGenerationResult(
        source_path=source,
        raw_path=raw_path,
        meta_path=meta_path,
        code=code,
        raw=raw,
        metadata=metadata,
    )


def build_attempt_payload(
    *,
    problem_slug: str,
    code: str,
    language: LeetCodeLanguage,
    generation_meta: dict[str, Any] | None = None,
    compile_result: CompileResult | None = None,
    prefailed_reason: str | None = None,
) -> dict[str, Any]:
    trace = (generation_meta or {}).get("trace") or {
        "prompt": None,
        "system_prompt": None,
        "raw_response": code,
        "reasoning": None,
        "model": None,
        "provider": "manual",
        "endpoint": None,
        "params": {},
        "created_at": _now(),
    }
    if compile_result is not None:
        trace = dict(trace)
        trace["compile"] = compile_result.to_dict()

    summary = (
        "Generated solution submitted through Energy-Languages LeetCode "
        f"pipeline for {language.display_name}."
    )
    return {
        "title_slug": problem_slug,
        "code": code,
        "inference_trace": summary,
        "trace": trace,
        "wall_clock_ms": int(
            1000.0
            * float((generation_meta or {}).get("response", {}).get("duration_s", 0.0))
        )
        if generation_meta
        else None,
        "generation_energy_j": None,
        "prefailed_reason": prefailed_reason,
        "cost_usd": 0.0,
        "response_tokens": max(1, len(code) // 4) if code else 0,
    }


def build_submission_payload(
    *,
    language: LeetCodeLanguage,
    provider: str,
    model: str,
    model_version: str,
    model_params: dict[str, Any],
    prompt_template: str,
    attempts: list[dict[str, Any]],
    n_samples_per_problem: int = 1,
) -> dict[str, Any]:
    return {
        "model_name": model,
        "model_version": model_version,
        "language": language.api_language,
        "prompt_template": prompt_template,
        "model_params": {"provider": provider, **model_params},
        "n_samples_per_problem": n_samples_per_problem,
        "n_rounds": 1,
        "include_hints": False,
        "optimization_target": None,
        "attempts": attempts,
    }


def poll_attempt(
    client: LeetCodeApiClient,
    submission_id: int,
    problem_slug: str,
    *,
    timeout_s: int = 900,
    interval_s: int = 5,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        attempts = client.submission_attempts(submission_id)
        matching = [a for a in attempts if a.get("problem_slug") == problem_slug]
        if matching:
            latest = max(matching, key=lambda a: a.get("attempt_id", 0))
            if latest.get("n_runs", 0) > 0:
                return latest
        time.sleep(interval_s)
    raise TimeoutError(
        f"Timed out waiting for {problem_slug} in submission {submission_id}"
    )


def check_solution(
    *,
    repo_root: Path,
    language: LeetCodeLanguage,
    problem_slug: str,
    source: Path,
    client: LeetCodeApiClient,
    provider: str = "manual",
    model: str = "manual",
    model_version: str = "manual",
    model_params: dict[str, Any] | None = None,
    prompt_template: str = "Energy-Languages LeetCode pipeline submission.",
    submission_id: int | None = None,
    generation_meta_path: Path | None = None,
    result_path: Path | None = None,
    poll_timeout_s: int = 900,
) -> dict[str, Any]:
    compile_result = compile_solution(language, source)
    generation_meta: dict[str, Any] | None = None
    if generation_meta_path and generation_meta_path.exists():
        generation_meta = json.loads(generation_meta_path.read_text())

    if not compile_result.ok:
        result = {
            "schema_version": 1,
            "benchmark": "leetcode-energy",
            "problem": problem_slug,
            "language": language.key,
            "leetcode_language": language.api_language,
            "source": str(source),
            "submitted": False,
            "compile": compile_result.to_dict(),
            "error": "compile failed; not submitted to LeetCode backend",
        }
        if result_path:
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(result, indent=2, sort_keys=True))
        return result

    code = source.read_text()
    attempt = build_attempt_payload(
        problem_slug=problem_slug,
        code=code,
        language=language,
        generation_meta=generation_meta,
        compile_result=compile_result,
    )
    if submission_id is None:
        payload = build_submission_payload(
            language=language,
            provider=provider,
            model=model,
            model_version=model_version,
            model_params=model_params or {},
            prompt_template=prompt_template,
            attempts=[attempt],
        )
        created = client.create_submission(payload)
        submission_id = int(created["submission_id"])
    else:
        client.append_attempts(submission_id, [attempt])

    judged = poll_attempt(
        client,
        submission_id,
        problem_slug,
        timeout_s=poll_timeout_s,
    )
    result = {
        "schema_version": 1,
        "benchmark": "leetcode-energy",
        "problem": problem_slug,
        "language": language.key,
        "leetcode_language": language.api_language,
        "source": str(source),
        "submitted": True,
        "submission_id": submission_id,
        "compile": compile_result.to_dict(),
        "attempt": judged,
    }
    if result_path:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


# ---------------------------------------------------------------------------
# Shared LeetCode workloads and local measurement


UNSUPPORTED_WORKLOAD_TAGS = {
    "Tree",
    "Binary Tree",
    "Linked List",
    "Design",
    "Randomized",
}


@dataclass(frozen=True)
class AcceptedResult:
    model_slug: str
    language: LeetCodeLanguage
    problem_slug: str
    result_path: Path
    source_path: Path
    result: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def accepted_results_from_progress(
    repo_root: Path,
    progress_path: Path,
    language: LeetCodeLanguage,
    *,
    model_slug: str | None = None,
    accepted_only: bool = True,
    problem_slugs: list[str] | None = None,
) -> list[AcceptedResult]:
    progress = load_progress(progress_path)
    records = progress.get("records", {})
    wanted = set(problem_slugs or [])
    out: list[AcceptedResult] = []
    for key, record in records.items():
        parts = key.split("|", 2)
        if len(parts) != 3:
            continue
        rec_model, rec_language, rec_problem = parts
        if model_slug and rec_model != model_slug:
            continue
        if rec_language != language.key:
            continue
        if wanted and rec_problem not in wanted:
            continue
        result_raw = record.get("result_path")
        result_path = Path(result_raw) if result_raw else Path()
        if result_raw and not result_path.is_absolute():
            result_path = repo_root / result_path
        result = _read_json(result_path) if result_raw and result_path.exists() else {}
        accepted = (
            (result.get("attempt") or {}).get("accepted") is True
            or record.get("accepted") is True
        )
        if accepted_only and not accepted:
            continue
        default_source = (
            generations_root(repo_root)
            / rec_model
            / language.folder
            / rec_problem
            / f"sample_00{language.extension}"
        )
        source = Path(record.get("source") or result.get("source") or default_source)
        if not source.is_absolute():
            source = repo_root / source
        if not source.exists():
            continue
        if not result:
            result = {
                "problem": rec_problem,
                "language": language.key,
                "source": str(source),
                "attempt": {"accepted": accepted},
                "accepted_source": "progress",
            }
        out.append(
            AcceptedResult(
                model_slug=rec_model,
                language=language,
                problem_slug=rec_problem,
                result_path=result_path,
                source_path=source,
                result=result,
            )
        )
    return sorted(out, key=lambda row: row.problem_slug)


def read_curated_dataset(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            rows[row["task_id"]] = row
    return rows


def sync_curated_dataset_workloads(
    repo_root: Path,
    dataset_path: Path,
    *,
    prune: bool = True,
) -> list[dict[str, Any]]:
    """Write one self-contained shared workload per curated dataset problem."""
    ensure_reference_dirs(repo_root)
    rows = read_curated_dataset(dataset_path)
    source_sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    workloads_dir = leetcode_reference_root(repo_root) / "workloads"
    outputs_dir = leetcode_reference_root(repo_root) / "outputs"
    if prune:
        for path in workloads_dir.glob("*.json"):
            path.unlink()
        for path in outputs_dir.glob("*.json"):
            path.unlink()

    written: list[dict[str, Any]] = []
    for slug, row in sorted(rows.items()):
        workload = {
            "schema_version": 2,
            "benchmark": "leetcode-energy",
            "problem": slug,
            "language_independent_cases": True,
            "source_dataset": dataset_path.name,
            "source_dataset_sha256": source_sha256,
            "entry_point": row["entry_point"],
            "starter_code": row.get("starter_code", ""),
            "prompt": row["prompt"],
            "test": row["test"],
            "cases": row["input_output"],
        }
        workload["workload_hash"] = _json_hash(workload)
        path = workload_path(repo_root, slug)
        path.write_text(json.dumps(workload, indent=2, sort_keys=True))
        written.append(
            {
                "problem": slug,
                "cases": len(workload["cases"]),
                "workload_hash": workload["workload_hash"],
                "path": str(path),
            }
        )
    return written


def _reference_readme() -> str:
    return """# LeetCode-Energy Reference Workloads

This directory mirrors the CLBG `reference/` pattern.

- `workloads/<slug>.json` stores one self-contained curated workload, including
  cases, validation metadata, dataset provenance, and a content hash.

The files are synchronized from LeetCodeDataset93. Every language must execute
the same stored cases and reproduce the semantic validation rules. LeetCode
acceptance remains the correctness authority; these files define the local,
reproducible workload used for energy measurement.
"""


def ensure_reference_dirs(repo_root: Path) -> None:
    ref = leetcode_reference_root(repo_root)
    (ref / "workloads").mkdir(parents=True, exist_ok=True)
    (ref / "outputs").mkdir(parents=True, exist_ok=True)
    readme = ref / "README.md"
    if not readme.exists():
        readme.write_text(_reference_readme())


def _json_hash(data: Any) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _clean_statement_text(text: str) -> str:
    return (
        text.replace("\\[", "[")
        .replace("\\]", "]")
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escape = False
    for i, ch in enumerate(value):
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
        elif ch in "[({":
            depth += 1
        elif ch in "])}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(value[start:i].strip())
            start = i + 1
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _literal(value: str) -> Any:
    value = value.strip()
    value = re.sub(r"\btrue\b", "True", value, flags=re.IGNORECASE)
    value = re.sub(r"\bfalse\b", "False", value, flags=re.IGNORECASE)
    value = re.sub(r"\bnull\b", "None", value, flags=re.IGNORECASE)
    return ast.literal_eval(value)


def _parse_input_assignments(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for part in _split_top_level(raw):
        if "=" not in part:
            raise ValueError(f"input part is not an assignment: {part!r}")
        name, value = part.split("=", 1)
        out[name.strip()] = _literal(value)
    return out


def _parse_output_value(raw: str) -> Any:
    line = raw.strip().splitlines()[0].strip()
    return _literal(line)


def parse_visible_examples(problem: dict[str, Any]) -> list[dict[str, Any]]:
    content = _clean_statement_text(problem.get("content") or "")
    pattern = re.compile(
        r"\*\*Input:\*\*\s*(?P<input>.*?)\n\*\*Output:\*\*\s*(?P<output>.*?)(?=\n\*\*Explanation:|\n\n\*\*Example|\n\n\*\*Constraints:|\Z)",
        re.DOTALL,
    )
    cases: list[dict[str, Any]] = []
    for idx, match in enumerate(pattern.finditer(content), start=1):
        inputs = _parse_input_assignments(match.group("input").strip())
        expected = _parse_output_value(match.group("output").strip())
        cases.append(
            {
                "name": f"example_{idx}",
                "kind": "example",
                "input": inputs,
                "expected": expected,
                "expected_source": "statement",
            }
        )
    return cases


def _python_solution_signature(snippet: str) -> tuple[str, list[str], list[str]]:
    if "class Solution" not in snippet:
        raise ValueError("starter snippet is not a class Solution problem")
    match = re.search(r"^\s+def\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*(?:->.*?)?:", snippet, re.MULTILINE)
    if not match:
        raise ValueError("class Solution has no callable method")
    method_name = match.group(1)
    if method_name == "__init__":
        raise ValueError("class Solution constructor problems need an adapter")
    args: list[str] = []
    annotations: list[str] = []
    for raw_arg in _split_top_level(match.group(2)):
        raw_arg = raw_arg.strip()
        if not raw_arg or raw_arg == "self":
            continue
        raw_arg = raw_arg.split("=", 1)[0].strip()
        if ":" in raw_arg:
            name, annotation = raw_arg.split(":", 1)
            args.append(name.strip())
            annotations.append(annotation.strip())
        else:
            args.append(raw_arg)
            annotations.append("")
    return method_name, args, annotations


def _is_unsupported_python_problem(problem: dict[str, Any]) -> str | None:
    tags = set(problem.get("tags") or [])
    unsupported = sorted(tags & UNSUPPORTED_WORKLOAD_TAGS)
    if unsupported:
        return f"unsupported problem tag(s): {', '.join(unsupported)}"
    snippet = (problem.get("code_snippets") or {}).get("python3", "")
    if "TreeNode" in snippet or "ListNode" in snippet:
        return "TreeNode/ListNode adapter not implemented"
    if "class Solution" not in snippet:
        return "non-Solution class adapter not implemented"
    try:
        _python_solution_signature(snippet)
    except ValueError as exc:
        return str(exc)
    return None


def _letters(length: int, offset: int = 0, alphabet: str = "abcdefghijklmnopqrstuvwxyz") -> str:
    return "".join(alphabet[(i + offset) % len(alphabet)] for i in range(length))


def _synthetic_graph(size: int) -> list[list[int]]:
    return [[j for j in range(i + 1, min(size, i + 3))] for i in range(size)]


def _synthetic_points(size: int) -> list[list[int]]:
    return [[i, (i * i + 3 * i) % (size + 7)] for i in range(size)]


def _synthetic_matrix(rows: int, cols: int, binary: bool = False) -> list[list[int]]:
    return [[(r + c) % 2 if binary else (r * cols + c) % 17 for c in range(cols)] for r in range(rows)]


def _synthetic_value(
    name: str,
    annotation: str,
    size: int,
    index: int,
    problem: dict[str, Any],
) -> Any:
    lname = name.lower()
    content = (problem.get("content") or "").lower()
    if annotation in {"int", ""}:
        if lname in {"k", "key", "extracandies"}:
            return max(1, min(5, size // 3))
        if lname in {"target"}:
            return size + index
        if lname == "maxtime":
            return size * 4 + 10
        return max(1, size)
    if annotation == "str":
        if "binary" in content or lname in {"s"} and "alternating" in content:
            return "".join("01"[(i + index) % 2] for i in range(size))
        if "vowel" in content or "vowels" in content:
            return ("aeioubc" * ((size // 7) + 1))[:size]
        if "word" in lname:
            return _letters(max(1, min(size, 12)), index, "abcdefghij")
        return _letters(max(1, size), index)
    if annotation in {"List[int]", "list[int]"}:
        if "binary" in content or lname == "nums" and "0" in content and "1" in content:
            return [(i + index) % 2 for i in range(size)]
        if lname == "salary":
            return [1000 + 97 * i for i in range(3, size + 3)]
        if lname == "passingfees":
            return [1 + ((i * 3) % 20) for i in range(size)]
        return [((i * 7 + index) % 31) + 1 for i in range(size)]
    if annotation in {"List[str]", "list[str]"}:
        return [_letters(1 + (i % 4), i + index) for i in range(max(1, size // 2))]
    if annotation in {"List[List[int]]", "list[list[int]]"}:
        if lname == "graph":
            return _synthetic_graph(max(2, min(size, 20)))
        if lname in {"points", "coordinates"}:
            return _synthetic_points(max(2, size))
        if lname == "edges":
            n = max(3, min(size, 20))
            return [[i, i + 1, 2 + (i % 5)] for i in range(n - 1)]
        if lname in {"students", "mentors"}:
            return _synthetic_matrix(max(2, min(size, 8)), 5, binary=True)
        return _synthetic_matrix(max(2, min(size, 10)), 4)
    raise ValueError(f"unsupported annotation for synthetic input: {name}: {annotation}")


def generate_synthetic_cases(problem: dict[str, Any], arg_names: list[str], annotations: list[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for idx, size in enumerate([3, 8, 20, 50], start=1):
        values = {
            name: _synthetic_value(name, ann, size, idx, problem)
            for name, ann in zip(arg_names, annotations)
        }
        # Keep related arguments shape-compatible for common multi-input problems.
        if {"students", "mentors"} <= set(values):
            rows = max(2, min(size, 8))
            values["students"] = _synthetic_matrix(rows, 5, binary=True)
            values["mentors"] = _synthetic_matrix(rows, 5, binary=True)[::-1]
        if {"edges", "passingFees"} <= set(values):
            n = max(3, min(size, 20))
            values["edges"] = [[i, i + 1, 2 + (i % 5)] for i in range(n - 1)]
            values["passingFees"] = [1 + ((i * 3) % 20) for i in range(n)]
            if "maxTime" in values:
                values["maxTime"] = n * 8
        cases.append(
            {
                "name": f"synthetic_{idx}",
                "kind": "synthetic",
                "input": values,
            }
        )
    return cases


def _normalize_output(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_output(v) for v in value]
    if isinstance(value, list):
        return [_normalize_output(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _normalize_output(v) for k, v in value.items()}
    return value


def outputs_equal(actual: Any, expected: Any) -> bool:
    actual = _normalize_output(actual)
    expected = _normalize_output(expected)
    if isinstance(actual, float) or isinstance(expected, float):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-5, abs_tol=1e-5)
        except (TypeError, ValueError):
            return False
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            outputs_equal(a, e) for a, e in zip(actual, expected)
        )
    return actual == expected


class WorkloadTimeoutError(TimeoutError):
    pass


class _time_limit:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._previous: Any = None

    def _handle_timeout(self, signum: int, frame: Any) -> None:
        raise WorkloadTimeoutError(f"workload case exceeded {self.seconds:.1f}s")

    def __enter__(self) -> None:
        self._previous = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._previous)


def _load_python_solution(source: Path) -> Any:
    import typing

    namespace: dict[str, Any] = {
        "__name__": "leetcode_solution",
        "List": typing.List,
        "Optional": typing.Optional,
    }
    exec(compile(source.read_text(), str(source), "exec"), namespace)
    solution_cls = namespace.get("Solution")
    if solution_cls is None:
        raise ValueError(f"Solution class not found in {source}")
    return solution_cls


def run_python_cases(
    source: Path,
    method_name: str,
    arg_names: list[str],
    cases: list[dict[str, Any]],
    *,
    repeat: int = 1,
) -> list[dict[str, Any]]:
    solution_cls = _load_python_solution(source)
    outputs: list[dict[str, Any]] = []
    for _ in range(repeat):
        outputs = []
        for case in cases:
            args = [case["input"][name] for name in arg_names]
            actual = getattr(solution_cls(), method_name)(*args)
            outputs.append(
                {
                    "name": case["name"],
                    "output": _normalize_output(actual),
                }
            )
    return outputs


def validate_python_workload(
    source: Path,
    workload: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    method = workload["entrypoint"]["method"]
    args = workload["entrypoint"]["args"]
    cases = workload["cases"]
    expected_by_name = {row["name"]: row["output"] for row in expected["expected"]}
    actual_rows = run_python_cases(source, method, args, cases)
    failures: list[dict[str, Any]] = []
    for row in actual_rows:
        exp = expected_by_name[row["name"]]
        if not outputs_equal(row["output"], exp):
            failures.append(
                {
                    "name": row["name"],
                    "actual": row["output"],
                    "expected": exp,
                }
            )
    return {
        "ok": not failures,
        "cases": len(cases),
        "failures": failures,
    }


def build_workload_for_accepted_result(
    repo_root: Path,
    accepted: AcceptedResult,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    ensure_reference_dirs(repo_root)
    slug = accepted.problem_slug
    problem_path = cell_dir(repo_root, accepted.language, slug) / "problem.json"
    problem = _read_json(problem_path)
    wpath = workload_path(repo_root, slug)
    opath = expected_output_path(repo_root, slug)
    if wpath.exists() and opath.exists() and not overwrite:
        return {
            "problem": slug,
            "status": "exists",
            "workload_path": str(wpath),
            "expected_path": str(opath),
        }

    skipped_reason = _is_unsupported_python_problem(problem)
    if skipped_reason:
        workload = {
            "schema_version": 1,
            "problem": slug,
            "language_independent": True,
            "skipped": True,
            "skipped_reason": skipped_reason,
            "cases": [],
        }
        wpath.write_text(json.dumps(workload, indent=2, sort_keys=True))
        return {
            "problem": slug,
            "status": "skipped",
            "reason": skipped_reason,
            "workload_path": str(wpath),
        }

    snippet = (problem.get("code_snippets") or {}).get("python3", "")
    method, arg_names, annotations = _python_solution_signature(snippet)
    try:
        examples = parse_visible_examples(problem)
    except Exception as exc:  # noqa: BLE001
        examples = []
        skipped_reason = f"could not parse visible examples: {exc}"
    if not examples:
        workload = {
            "schema_version": 1,
            "problem": slug,
            "language_independent": True,
            "skipped": True,
            "skipped_reason": skipped_reason or "no visible examples parsed",
            "cases": [],
        }
        wpath.write_text(json.dumps(workload, indent=2, sort_keys=True))
        return {
            "problem": slug,
            "status": "skipped",
            "reason": workload["skipped_reason"],
            "workload_path": str(wpath),
        }

    example_cases = [
        {k: v for k, v in case.items() if k not in {"expected", "expected_source"}}
        for case in examples
    ]
    example_expected = [
        {
            "name": case["name"],
            "output": _normalize_output(case["expected"]),
            "source": "statement",
        }
        for case in examples
    ]
    workload = {
        "schema_version": 1,
        "problem": slug,
        "language_independent": True,
        "generator_version": "leetcode-energy-v1",
        "seed": hashlib.sha256(slug.encode()).hexdigest(),
        "entrypoint": {
            "class": "Solution",
            "method": method,
            "args": arg_names,
            "arg_annotations": annotations,
        },
        "cases": list(example_cases),
    }

    try:
        validation_expected = {"expected": example_expected}
        with _time_limit(5.0):
            validation = validate_python_workload(
                accepted.source_path,
                workload,
                validation_expected,
            )
    except Exception as exc:  # noqa: BLE001
        workload["skipped"] = True
        workload["skipped_reason"] = f"visible example validation crashed: {exc}"
        wpath.write_text(json.dumps(workload, indent=2, sort_keys=True))
        return {
            "problem": slug,
            "status": "skipped",
            "reason": workload["skipped_reason"],
            "workload_path": str(wpath),
        }
    if not validation["ok"]:
        workload["skipped"] = True
        workload["skipped_reason"] = "visible example validation failed"
        workload["validation_failures"] = validation["failures"]
        wpath.write_text(json.dumps(workload, indent=2, sort_keys=True))
        return {
            "problem": slug,
            "status": "skipped",
            "reason": workload["skipped_reason"],
            "workload_path": str(wpath),
        }

    synthetic_cases: list[dict[str, Any]] = []
    synthetic_expected: list[dict[str, Any]] = []
    for case in generate_synthetic_cases(problem, arg_names, annotations):
        trial = dict(workload)
        trial["cases"] = [case]
        try:
            with _time_limit(2.0):
                first = run_python_cases(accepted.source_path, method, arg_names, [case])[0]
            with _time_limit(2.0):
                second = run_python_cases(accepted.source_path, method, arg_names, [case])[0]
        except Exception:
            continue
        if outputs_equal(first["output"], second["output"]):
            synthetic_cases.append(case)
            synthetic_expected.append(
                {
                    "name": case["name"],
                    "output": first["output"],
                    "source": "accepted_python_solution",
                }
            )

    workload["cases"].extend(synthetic_cases)
    workload["case_counts"] = {
        "examples": len(example_cases),
        "synthetic": len(synthetic_cases),
        "total": len(workload["cases"]),
    }
    workload_hash = _json_hash(workload)
    workload["workload_hash"] = workload_hash
    expected = {
        "schema_version": 1,
        "problem": slug,
        "workload_hash": workload_hash,
        "expected": example_expected + synthetic_expected,
    }
    wpath.write_text(json.dumps(workload, indent=2, sort_keys=True))
    opath.write_text(json.dumps(expected, indent=2, sort_keys=True))
    return {
        "problem": slug,
        "status": "built",
        "workload_path": str(wpath),
        "expected_path": str(opath),
        "cases": len(workload["cases"]),
        "synthetic_cases": len(synthetic_cases),
    }


def build_workloads(
    repo_root: Path,
    accepted_results: list[AcceptedResult],
    *,
    overwrite: bool = False,
) -> list[dict[str, Any]]:
    return [
        build_workload_for_accepted_result(repo_root, result, overwrite=overwrite)
        for result in accepted_results
    ]


def run_workload_once(
    *,
    language: LeetCodeLanguage,
    problem_slug: str,
    source: Path,
    workload_file: Path,
    expected_file: Path,
    repeat: int = 1,
) -> dict[str, Any]:
    if language.key != "python":
        raise ValueError("leetcode-workload-run currently supports python only")
    workload = _read_json(workload_file)
    expected = _read_json(expected_file)
    if workload.get("skipped"):
        return {
            "ok": False,
            "problem": problem_slug,
            "skipped": True,
            "skipped_reason": workload.get("skipped_reason"),
        }
    if workload.get("workload_hash") != expected.get("workload_hash"):
        raise ValueError(
            f"workload/output hash mismatch for {problem_slug}: "
            f"{workload.get('workload_hash')} != {expected.get('workload_hash')}"
        )
    validation = validate_python_workload(source, workload, expected)
    if not validation["ok"]:
        return {
            "ok": False,
            "problem": problem_slug,
            "validation": validation,
        }
    run_python_cases(
        source,
        workload["entrypoint"]["method"],
        workload["entrypoint"]["args"],
        workload["cases"],
        repeat=max(1, repeat),
    )
    return {
        "ok": True,
        "problem": problem_slug,
        "workload_hash": workload.get("workload_hash"),
        "cases": len(workload["cases"]),
        "repeat": repeat,
    }


class _CandidateCallExtractor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "candidate":
            self.calls.append(node)
            return
        self.generic_visit(node)


def _curated_candidate_calls(test_source: str) -> list[Any]:
    tree = ast.parse(test_source)
    extractor = _CandidateCallExtractor()
    extractor.visit(tree)
    return [
        compile(ast.Expression(body=call), "<leetcode-curated-case>", "eval")
        for call in extractor.calls
    ]


def run_curated_python_workload(
    *,
    source: Path,
    workload: dict[str, Any],
    repeat: int = 1,
    validate: bool = False,
) -> dict[str, Any]:
    """Validate or execute a curated dataset workload in the current process."""
    namespace: dict[str, Any] = {"__name__": "leetcode_curated_workload"}
    combined = "\n".join(
        [workload["prompt"], source.read_text(), workload["test"]]
    )
    exec(compile(combined, str(source), "exec"), namespace)
    if validate:
        candidate = eval(workload["entry_point"], namespace)
        namespace["check"](candidate)

    calls = _curated_candidate_calls(workload["test"])
    expected_cases = len(workload["cases"])
    if len(calls) != expected_cases:
        raise ValueError(
            f"curated workload call count mismatch: {len(calls)} != {expected_cases}"
        )
    for _ in range(max(1, repeat)):
        candidate = eval(workload["entry_point"], namespace)
        locals_map = {"candidate": candidate}
        for call in calls:
            eval(call, namespace, locals_map)
    return {
        "ok": True,
        "problem": workload["problem"],
        "workload_hash": workload["workload_hash"],
        "cases": expected_cases,
        "repeat": max(1, repeat),
        "validated": validate,
    }


def measure_curated_accepted_results(
    repo_root: Path,
    accepted_results: list[AcceptedResult],
    *,
    model_slug: str,
    warmup: int = 3,
    measure: int = 10,
    idle_s: int = 2,
    case_repeat: int = 1,
    output: Path | None = None,
    reset_output: bool = False,
) -> list[dict[str, Any]]:
    """Measure accepted Python solutions against curated dataset workloads."""
    rows: list[dict[str, Any]] = []
    out_path = output or (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / "python_curated.jsonl"
    )
    if not out_path.is_absolute():
        out_path = repo_root / out_path
    if reset_output and out_path.exists():
        out_path.unlink()

    total = len(accepted_results)
    for index, accepted in enumerate(accepted_results, start=1):
        language = accepted.language
        slug = accepted.problem_slug
        print(f"[curated-measure] {index}/{total} {slug}", flush=True)
        wpath = workload_path(repo_root, slug)
        energy_path = (
            cell_dir(repo_root, language, slug)
            / f"energy_curated_{model_slug}.json"
        )
        if not wpath.exists():
            summary = {
                "schema_version": 2,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": "missing curated workload",
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue
        workload = _read_json(wpath)
        if workload.get("schema_version") != 2:
            summary = {
                "schema_version": 2,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": "workload is not a curated dataset workload",
                "workload_path": str(wpath),
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue

        env = dict(os.environ)
        env["PYTHONPATH"] = (
            str(repo_root)
            if not env.get("PYTHONPATH")
            else f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
        )
        command_parts = [
            sys.executable,
            "-m",
            "perfarena.runners.leetcode_curated_runner",
            "--problem",
            slug,
            "--source",
            str(accepted.source_path),
            "--workload",
            str(wpath),
        ]
        try:
            validation_proc = subprocess.run(
                [*command_parts, "--validate", "--repeat", "1"],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            validation = {
                "ok": validation_proc.returncode == 0,
                "returncode": validation_proc.returncode,
                "stdout": validation_proc.stdout,
                "stderr": validation_proc.stderr,
            }
        except Exception as exc:  # noqa: BLE001
            validation = {"ok": False, "error": str(exc)}
        if not validation["ok"]:
            summary = {
                "schema_version": 2,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": "curated validation failed before measurement",
                "validation": validation,
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue

        raw_jsonl = _runner_jsonl_path(repo_root, language)
        start_size = raw_jsonl.stat().st_size if raw_jsonl.exists() else 0
        command = " ".join(
            shlex.quote(part)
            for part in [*command_parts, "--repeat", str(case_repeat)]
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "perfarena.runners.codecarbon_runner",
                command,
                language.folder,
                slug,
                str(warmup),
                str(measure),
                str(idle_s),
            ],
            cwd=cell_dir(repo_root, language, slug),
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=900,
        )
        raw_rows = _new_jsonl_rows(raw_jsonl, start_size)
        enriched: list[dict[str, Any]] = []
        for row in raw_rows:
            enriched_row = dict(row)
            enriched_row.update(
                {
                    "benchmark": "leetcode-energy-curated",
                    "model_slug": model_slug,
                    "leetcode_language": language.api_language,
                    "accepted": True,
                    "workload_hash": workload["workload_hash"],
                    "workload_cases": len(workload["cases"]),
                    "case_repeat": max(1, case_repeat),
                    "source_dataset": workload["source_dataset"],
                    "source_dataset_sha256": workload["source_dataset_sha256"],
                    "workload_path": str(wpath),
                    "source": str(accepted.source_path),
                    "result_path": (
                        str(accepted.result_path)
                        if accepted.result_path.exists()
                        else None
                    ),
                    "accepted_source": accepted.result.get(
                        "accepted_source", "result_json"
                    ),
                }
            )
            enriched.append(enriched_row)
        _append_jsonl(out_path, enriched)
        rows.extend(enriched)
        measured_rows = [row for row in enriched if row.get("phase") == "measure"]
        summary = {
            "schema_version": 2,
            "problem": slug,
            "language": language.key,
            "model_slug": model_slug,
            "accepted": True,
            "validated": True,
            "measured": proc.returncode == 0 and bool(measured_rows),
            "runner_returncode": proc.returncode,
            "runner_stdout": proc.stdout,
            "runner_stderr": proc.stderr,
            "aggregate_jsonl": str(out_path),
            "rows": len(enriched),
            "measurement_rows": len(measured_rows),
            "workload_cases": len(workload["cases"]),
            "case_repeat": max(1, case_repeat),
            "workload_hash": workload["workload_hash"],
            "workload_path": str(wpath),
            "source": str(accepted.source_path),
            "accepted_source": accepted.result.get(
                "accepted_source", "result_json"
            ),
        }
        energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
        print(
            f"[curated-measure] completed {slug}: "
            f"measurement_rows={len(measured_rows)}",
            flush=True,
        )
    return rows


def _runner_jsonl_path(repo_root: Path, language: LeetCodeLanguage) -> Path:
    return leetcode_root(repo_root) / language.folder / f"{language.folder}.jsonl"


def _new_jsonl_rows(path: Path, start_size: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open() as fh:
        fh.seek(start_size)
        return [json.loads(line) for line in fh if line.strip()]


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")


def measure_accepted_results(
    repo_root: Path,
    accepted_results: list[AcceptedResult],
    *,
    model_slug: str,
    warmup: int = 3,
    measure: int = 10,
    idle_s: int = 2,
    case_repeat: int = 1,
    output: Path | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    out_path = output or (
        repo_root
        / "perfarena_out"
        / "leetcode_measurements"
        / model_slug
        / "python.jsonl"
    )
    for accepted in accepted_results:
        language = accepted.language
        slug = accepted.problem_slug
        wpath = workload_path(repo_root, slug)
        opath = expected_output_path(repo_root, slug)
        energy_path = cell_dir(repo_root, language, slug) / f"energy_{model_slug}.json"
        if not wpath.exists():
            summary = {
                "schema_version": 1,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": "missing workload",
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue
        workload = _read_json(wpath)
        if workload.get("skipped"):
            summary = {
                "schema_version": 1,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": workload.get("skipped_reason"),
                "workload_path": str(wpath),
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue
        if not opath.exists():
            summary = {
                "schema_version": 1,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": "missing expected output",
                "workload_path": str(wpath),
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue

        env = dict(os.environ)
        env["PYTHONPATH"] = (
            str(repo_root)
            if not env.get("PYTHONPATH")
            else f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
        )
        workload_command_parts = [
            sys.executable,
            "-m",
            "perfarena.cli",
            "leetcode-workload-run",
            "--language",
            language.key,
            "--problem",
            slug,
            "--source",
            str(accepted.source_path),
            "--workload",
            str(wpath),
            "--expected",
            str(opath),
        ]
        try:
            validation_proc = subprocess.run(
                [*workload_command_parts, "--repeat", "1"],
                cwd=repo_root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=20,
            )
            validation = {
                "ok": validation_proc.returncode == 0,
                "problem": slug,
                "returncode": validation_proc.returncode,
                "stdout": validation_proc.stdout,
                "stderr": validation_proc.stderr,
            }
        except Exception as exc:  # noqa: BLE001
            validation = {
                "ok": False,
                "problem": slug,
                "error": f"validation crashed or timed out: {exc}",
            }
        if not validation.get("ok"):
            summary = {
                "schema_version": 1,
                "problem": slug,
                "language": language.key,
                "model_slug": model_slug,
                "measured": False,
                "skipped_reason": "validation failed before measurement",
                "validation": validation,
            }
            energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
            continue

        raw_jsonl = _runner_jsonl_path(repo_root, language)
        start_size = raw_jsonl.stat().st_size if raw_jsonl.exists() else 0
        command = " ".join(
            shlex.quote(part)
            for part in [*workload_command_parts, "--repeat", str(case_repeat)]
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "perfarena.runners.codecarbon_runner",
                command,
                language.folder,
                slug,
                str(warmup),
                str(measure),
                str(idle_s),
            ],
            cwd=cell_dir(repo_root, language, slug),
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=900,
        )
        raw_rows = _new_jsonl_rows(raw_jsonl, start_size)
        enriched: list[dict[str, Any]] = []
        for row in raw_rows:
            enriched_row = dict(row)
            enriched_row.update(
                {
                    "benchmark": "leetcode-energy",
                    "model_slug": model_slug,
                    "leetcode_language": language.api_language,
                    "accepted": True,
                    "workload_hash": workload.get("workload_hash"),
                    "workload_path": str(wpath),
                    "expected_path": str(opath),
                    "source": str(accepted.source_path),
                    "result_path": str(accepted.result_path),
                }
            )
            enriched.append(enriched_row)
        _append_jsonl(out_path, enriched)
        rows.extend(enriched)
        summary = {
            "schema_version": 1,
            "problem": slug,
            "language": language.key,
            "model_slug": model_slug,
            "measured": proc.returncode == 0 and bool(enriched),
            "runner_returncode": proc.returncode,
            "runner_stdout": proc.stdout,
            "runner_stderr": proc.stderr,
            "raw_jsonl": str(raw_jsonl),
            "aggregate_jsonl": str(out_path),
            "rows": len(enriched),
            "workload_hash": workload.get("workload_hash"),
            "workload_path": str(wpath),
            "expected_path": str(opath),
        }
        energy_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return rows


# ---------------------------------------------------------------------------
# Orchestration


def load_progress(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_progress(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def run_pipeline(
    *,
    repo_root: Path,
    languages: list[LeetCodeLanguage],
    problems: list[dict[str, Any]],
    client: LeetCodeApiClient,
    provider: str,
    model: str,
    model_version: str,
    temperature: float,
    max_tokens: int,
    progress_path: Path,
    retry_failed: bool = False,
    poll_timeout_s: int = 900,
    empty_code_retries: int = 2,
) -> dict[str, Any]:
    progress = load_progress(progress_path)
    submissions = progress.setdefault("submissions", {})
    records = progress.setdefault("records", {})
    model_slug = slugify_model(provider, model)

    for lang in languages:
        sub_key = f"{model_slug}|{lang.key}"
        submission_id = submissions.get(sub_key)
        for problem in problems:
            slug = problem["title_slug"]
            rec_key = f"{sub_key}|{slug}"
            rec = records.get(rec_key)
            if rec and rec.get("status") == "complete":
                continue
            if rec and rec.get("status") == "failed" and not retry_failed:
                continue

            try:
                gen = generate_solution(
                    repo_root,
                    problem,
                    lang,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stage=True,
                    empty_code_retries=empty_code_retries,
                )
                result_path = (
                    cell_dir(repo_root, lang, slug)
                    / f"result_{model_slug}.json"
                )
                result = check_solution(
                    repo_root=repo_root,
                    language=lang,
                    problem_slug=slug,
                    source=solution_path(repo_root, lang, slug),
                    client=client,
                    provider=provider,
                    model=model,
                    model_version=model_version,
                    model_params={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    prompt_template=gen.metadata["prompts"]["user_prompt"],
                    submission_id=submission_id,
                    generation_meta_path=gen.meta_path,
                    result_path=result_path,
                    poll_timeout_s=poll_timeout_s,
                )
                submission_id = result.get("submission_id", submission_id)
                submissions[sub_key] = submission_id
                records[rec_key] = {
                    "status": "complete",
                    "submission_id": submission_id,
                    "accepted": result.get("attempt", {}).get("accepted"),
                    "final_status": result.get("attempt", {}).get("status"),
                    "result_path": str(result_path),
                }
            except Exception as exc:  # noqa: BLE001
                records[rec_key] = {
                    "status": "failed",
                    "error": str(exc),
                }
            save_progress(progress_path, progress)
    return progress
