from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from perfarena import cli as cli_module
from perfarena.cli import app
from perfarena import leetcode_energy as leetcode
from perfarena.runners.codecarbon_runner import _kwh_to_uj


runner = CliRunner()


def _problem(slug: str = "two-sum") -> dict:
    return {
        "id": 1,
        "title_slug": slug,
        "title": "Two Sum",
        "level": "Easy",
        "tags": ["Array", "Hash Table"],
        "content": "Given an array of integers...",
        "hints": None,
        "code_snippets": {
            "python3": "class Solution:\n    def twoSum(self, nums, target):\n        pass",
            "golang": "func twoSum(nums []int, target int) []int {\n    return nil\n}",
        },
    }


def _dataset_row(
    *,
    model_name: str = "gemma4:e4b",
    provider: str = "ollama",
    trace_hash: str | None = None,
    code: str | None = None,
    slug: str = "two-sum",
    status: str = "Accepted",
) -> dict:
    return {
        "submission_id": 42,
        "language": "python3",
        "problem_slug": slug,
        "problem_title": "Two Sum",
        "problem_level": "Easy",
        "problem_tags": ["Array"],
        "model_name": model_name,
        "model_version": provider,
        "status_msg": status,
        "runtime_ms": 12,
        "memory_mb": 17.5,
        "total_correct": 63,
        "total_testcases": 63,
        "trace_hash": trace_hash or f"{provider}-{model_name}",
        "trace": {"provider": provider, "raw_response": "raw"},
        "code": code
        or (
            "class Solution:\n"
            "    def twoSum(self, nums, target):\n"
            "        return [0, 1]\n"
        ),
    }


def test_language_registry_maps_energy_keys_to_leetcode_slugs() -> None:
    py = leetcode.get_language("python")
    go = leetcode.get_language("go")

    assert py.api_language == "python3"
    assert py.folder == "Python"
    assert py.extension == ".py"
    assert go.api_language == "golang"
    assert go.folder == "Go"
    assert go.extension == ".go"
    assert leetcode.get_language("python3") is py
    assert leetcode.get_language("golang") is go


def test_scaffold_creates_problem_cells(tmp_path: Path) -> None:
    languages = [leetcode.get_language("python"), leetcode.get_language("go")]
    problems = [_problem("two-sum"), _problem("add-digits")]

    leetcode.scaffold(tmp_path, languages, problems)

    for lang in languages:
        for problem in problems:
            cdir = tmp_path / "leetcode-energy" / lang.folder / problem["title_slug"]
            assert (cdir / "problem.json").exists()
            assert (cdir / f"solution{lang.extension}").exists()
            makefile = (cdir / "Makefile").read_text()
            assert "leetcode-compile" in makefile
            assert "leetcode-check" not in makefile
            assert "leetcode-workload-run" in makefile


def test_submission_payload_uses_leetcode_language_slug() -> None:
    lang = leetcode.get_language("python")
    attempt = leetcode.build_attempt_payload(
        problem_slug="two-sum",
        code="class Solution:\n    def twoSum(self, nums, target):\n        return []\n",
        language=lang,
    )
    payload = leetcode.build_submission_payload(
        language=lang,
        provider="ollama",
        model="qwen",
        model_version="ollama",
        model_params={"temperature": 0.2},
        prompt_template="Solve this problem in Python.",
        attempts=[attempt],
    )

    assert payload["language"] == "python3"
    assert payload["attempts"][0]["title_slug"] == "two-sum"
    assert payload["attempts"][0]["trace"]["provider"] == "manual"
    assert payload["model_params"]["provider"] == "ollama"


def test_dataset_import_stages_exact_code_and_progress(tmp_path: Path) -> None:
    row = _dataset_row(trace_hash="abc123")
    progress = tmp_path / "progress.json"

    imported = leetcode.import_dataset_solution_rows(
        repo_root=tmp_path,
        rows=[row],
        base_url="https://perfarena.example",
        languages=[leetcode.get_language("python")],
        progress_path=progress,
        hydrate_problem=False,
    )

    source = (
        tmp_path
        / "perfarena_out"
        / "leetcode_dataset_solutions"
        / "ollama__gemma4_e4b"
        / "Python"
        / "two-sum"
        / "solution.py"
    )
    staged = tmp_path / "leetcode-energy" / "Python" / "two-sum" / "solution.py"
    result_path = (
        tmp_path
        / "leetcode-energy"
        / "Python"
        / "two-sum"
        / "result_ollama__gemma4_e4b.json"
    )
    rec = imported["records"]["ollama__gemma4_e4b|python|two-sum"]
    result = json.loads(result_path.read_text())

    assert source.read_text() == row["code"]
    assert staged.read_text() == row["code"]
    assert rec["accepted"] is True
    assert rec["result_path"] == str(result_path)
    assert rec["source"] == str(source)
    assert result["imported"] is True
    assert result["attempt"]["accepted"] is True
    assert result["source"] == str(source)


def test_dataset_import_keeps_models_in_distinct_source_files(tmp_path: Path) -> None:
    base = {
        "submission_id": 42,
        "language": "python3",
        "problem_slug": "two-sum",
        "problem_title": "Two Sum",
        "problem_level": "Easy",
        "problem_tags": ["Array"],
        "model_version": "ollama",
        "status_msg": "Accepted",
        "trace": {"provider": "ollama"},
    }
    rows = [
        {
            **base,
            "model_name": "gemma4:e4b",
            "trace_hash": "gemma",
            "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n",
        },
        {
            **base,
            "model_name": "qwen3:8b",
            "trace_hash": "qwen",
            "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [1, 0]\n",
        },
    ]
    progress = tmp_path / "progress.json"

    imported = leetcode.import_dataset_solution_rows(
        repo_root=tmp_path,
        rows=rows,
        base_url="https://perfarena.example",
        languages=[leetcode.get_language("python")],
        progress_path=progress,
        hydrate_problem=False,
        stage_solution=False,
    )

    gemma = (
        tmp_path
        / "perfarena_out"
        / "leetcode_dataset_solutions"
        / "ollama__gemma4_e4b"
        / "Python"
        / "two-sum"
        / "solution.py"
    )
    qwen = (
        tmp_path
        / "perfarena_out"
        / "leetcode_dataset_solutions"
        / "ollama__qwen3_8b"
        / "Python"
        / "two-sum"
        / "solution.py"
    )

    assert gemma.exists()
    assert qwen.exists()
    assert gemma.read_text() != qwen.read_text()
    assert (
        tmp_path / "leetcode-energy" / "Python" / "two-sum" / "solution.py"
    ).read_text() == ""
    assert imported["records"]["ollama__gemma4_e4b|python|two-sum"]["source"] == str(
        gemma
    )
    assert imported["records"]["ollama__qwen3_8b|python|two-sum"]["source"] == str(qwen)


def test_select_single_model_slug_requires_disambiguation() -> None:
    rows = [
        _dataset_row(model_name="same", provider="ollama"),
        _dataset_row(model_name="same", provider="openai"),
    ]

    try:
        leetcode.select_single_model_slug(rows)
    except ValueError as exc:
        assert "multiple model slugs" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected multiple-slug failure")

    slug, selected = leetcode.select_single_model_slug(
        rows,
        requested_model_slug="ollama__same",
    )

    assert slug == "ollama__same"
    assert len(selected) == 1


def test_accepted_result_selection_prefers_progress_source(tmp_path: Path) -> None:
    lang = leetcode.get_language("python")
    result_dir = tmp_path / "leetcode-energy" / "Python" / "two-sum"
    result_dir.mkdir(parents=True)
    stale_source = result_dir / "solution.py"
    stale_source.write_text("class Solution: pass\n")
    model_source = (
        tmp_path
        / "perfarena_out"
        / "leetcode_dataset_solutions"
        / "ollama__gemma4_e4b"
        / "Python"
        / "two-sum"
        / "solution.py"
    )
    model_source.parent.mkdir(parents=True)
    model_source.write_text("class Solution:\n    pass\n")
    result_path = result_dir / "result_ollama__gemma4_e4b.json"
    result_path.write_text(
        json.dumps(
            {
                "problem": "two-sum",
                "language": "python",
                "source": str(stale_source),
                "attempt": {"accepted": True},
            }
        )
    )
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "records": {
                    "ollama__gemma4_e4b|python|two-sum": {
                        "accepted": True,
                        "result_path": str(result_path),
                        "source": str(model_source),
                    }
                }
            }
        )
    )

    rows = leetcode.accepted_results_from_progress(
        tmp_path,
        progress,
        lang,
        model_slug="ollama__gemma4_e4b",
    )

    assert rows[0].source_path == model_source


def test_leetcode_measure_model_rejects_non_python() -> None:
    result = runner.invoke(
        app,
        ["leetcode-measure-model", "--model", "gemma4:e4b", "--language", "java"],
    )

    assert result.exit_code == 2
    assert "supports python only" in result.output


def test_leetcode_measure_model_skips_existing_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    lang = leetcode.get_language("python")
    monkeypatch.setattr(
        cli_module,
        "load_config",
        lambda: SimpleNamespace(repo_root=tmp_path),
    )
    monkeypatch.setattr(
        leetcode,
        "iter_dataset_solutions",
        lambda **kwargs: iter([_dataset_row()]),
    )

    output = cli_module.casewise_energy.measurement_path(
        tmp_path,
        "ollama__gemma4_e4b",
        lang.key,
    )
    output.parent.mkdir(parents=True)
    output.write_text('{"model_slug":"ollama__gemma4_e4b"}\n')
    summary_prefix = cli_module.casewise_energy.summary_prefix(
        tmp_path,
        "ollama__gemma4_e4b",
        lang.key,
    )
    summary_prefix.with_suffix(".json").write_text("{}")
    summary_prefix.with_suffix(".md").write_text("# existing\n")

    def fail_import(**kwargs):  # pragma: no cover
        raise AssertionError("existing output should not be imported")

    monkeypatch.setattr(leetcode, "import_dataset_solution_rows", fail_import)

    result = runner.invoke(
        app,
        [
            "leetcode-measure-model",
            "--base-url",
            "https://perfarena.example",
            "--model",
            "gemma4:e4b",
            "--language",
            "python",
            "--no-resume",
        ],
    )

    assert result.exit_code == 0
    assert "Existing casewise measurement found for ollama__gemma4_e4b" in result.output
    assert output.read_text() == '{"model_slug":"ollama__gemma4_e4b"}\n'


class _FakeClient:
    def __init__(self) -> None:
        self.created = False

    def create_submission(self, payload: dict) -> dict:  # pragma: no cover
        self.created = True
        return {"submission_id": 1}

    def append_attempts(self, submission_id: int, attempts: list[dict]) -> dict:
        self.created = True
        return {"submission_id": submission_id}


def test_compile_failure_skips_backend_submission(tmp_path: Path) -> None:
    source = tmp_path / "bad.py"
    source.write_text("class Solution:\n    def broken(self):\n        return [\n")
    result_path = tmp_path / "result.json"
    client = _FakeClient()

    result = leetcode.check_solution(
        repo_root=tmp_path,
        language=leetcode.get_language("python"),
        problem_slug="two-sum",
        source=source,
        client=client,  # type: ignore[arg-type]
        result_path=result_path,
    )

    assert result["submitted"] is False
    assert result["compile"]["ok"] is False
    assert client.created is False
    assert result_path.exists()


class _FakeChat:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def invoke(self, messages: list[object]) -> SimpleNamespace:
        response = self.responses[self.calls]
        self.calls += 1
        return SimpleNamespace(content=response)


def test_generate_solution_retries_empty_extracted_code(
    tmp_path: Path,
    monkeypatch,
) -> None:
    chat = _FakeChat(
        [
            "```python\n```",
            "```python\nclass Solution:\n    def twoSum(self, nums, target):\n        return []\n```",
        ]
    )
    monkeypatch.setattr(leetcode, "build_chat_model", lambda **kwargs: chat)

    result = leetcode.generate_solution(
        tmp_path,
        _problem("two-sum"),
        leetcode.get_language("python"),
        provider="ollama",
        model="fake",
        empty_code_retries=2,
        stage=False,
    )

    assert chat.calls == 2
    assert "def twoSum" in result.code
    assert result.metadata["response"]["attempts"][0]["empty_code"] is True
    assert result.metadata["response"]["attempts"][1]["empty_code"] is False


def test_generate_solution_raises_after_empty_code_retries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    chat = _FakeChat(["```python\n```", ""])
    monkeypatch.setattr(leetcode, "build_chat_model", lambda **kwargs: chat)

    try:
        leetcode.generate_solution(
            tmp_path,
            _problem("two-sum"),
            leetcode.get_language("python"),
            provider="ollama",
            model="fake",
            empty_code_retries=1,
            stage=True,
        )
    except leetcode.EmptyCodeGenerationError as exc:
        assert "empty code after 2 generation attempt" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected EmptyCodeGenerationError")

    assert chat.calls == 2
    assert not (
        tmp_path / "leetcode-energy" / "Python" / "two-sum" / "solution.py"
    ).exists()


def _average_problem() -> dict:
    return {
        "id": 1491,
        "title_slug": "average-salary-excluding-the-minimum-and-maximum-salary",
        "title": "Average Salary Excluding the Minimum and Maximum Salary",
        "level": "Easy",
        "tags": ["Array", "Sorting"],
        "content": (
            "Given salaries.\n\n"
            "**Example 1:**\n\n"
            "**Input:** salary = \\[4000,3000,1000,2000\\]\n"
            "**Output:** 2500.00000\n"
            "**Explanation:** ok\n\n"
            "**Example 2:**\n\n"
            "**Input:** salary = \\[1000,2000,3000\\]\n"
            "**Output:** 2000.00000\n\n"
            "**Constraints:**\n"
            "* `3 <= salary.length <= 100`"
        ),
        "hints": None,
        "code_snippets": {
            "python3": "class Solution:\n    def average(self, salary: List[int]) -> float:\n        "
        },
    }


def _write_average_solution(path: Path) -> None:
    path.write_text(
        "from typing import List\n\n"
        "class Solution:\n"
        "    def average(self, salary: List[int]) -> float:\n"
        "        return (sum(salary) - min(salary) - max(salary)) / (len(salary) - 2)\n"
    )


def test_reference_paths_use_shared_leetcode_layout(tmp_path: Path) -> None:
    slug = "two-sum"

    assert leetcode.workload_path(tmp_path, slug) == (
        tmp_path / "leetcode-energy" / "reference" / "workloads" / "two-sum.json"
    )
    assert leetcode.expected_output_path(tmp_path, slug) == (
        tmp_path / "leetcode-energy" / "reference" / "outputs" / "two-sum.json"
    )


def test_accepted_result_selection_reads_result_json(tmp_path: Path) -> None:
    lang = leetcode.get_language("python")
    result_dir = tmp_path / "leetcode-energy" / "Python" / "two-sum"
    result_dir.mkdir(parents=True)
    source = result_dir / "solution.py"
    source.write_text("class Solution: pass\n")
    accepted_result = result_dir / "result_ollama__gemma4_e4b.json"
    rejected_result = result_dir / "result_other.json"
    accepted_result.write_text(
        json.dumps(
            {
                "problem": "two-sum",
                "language": "python",
                "source": str(source),
                "attempt": {"accepted": True},
            }
        )
    )
    rejected_result.write_text(
        json.dumps(
            {
                "problem": "add-digits",
                "language": "python",
                "source": str(source),
                "attempt": {"accepted": False},
            }
        )
    )
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "records": {
                    "ollama__gemma4_e4b|python|two-sum": {
                        "result_path": str(accepted_result)
                    },
                    "ollama__gemma4_e4b|python|add-digits": {
                        "result_path": str(rejected_result)
                    },
                }
            }
        )
    )

    rows = leetcode.accepted_results_from_progress(
        tmp_path,
        progress,
        lang,
        model_slug="ollama__gemma4_e4b",
        accepted_only=True,
    )

    assert [row.problem_slug for row in rows] == ["two-sum"]


def test_accepted_result_selection_falls_back_to_progress_and_generation(
    tmp_path: Path,
) -> None:
    lang = leetcode.get_language("python")
    source = (
        tmp_path
        / "perfarena_out"
        / "leetcode_generations"
        / "ollama__gemma4_e4b"
        / "Python"
        / "two-sum"
        / "sample_00.py"
    )
    source.parent.mkdir(parents=True)
    source.write_text("class Solution: pass\n")
    missing_result = tmp_path / "missing-result.json"
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "records": {
                    "ollama__gemma4_e4b|python|two-sum": {
                        "accepted": True,
                        "result_path": str(missing_result),
                    }
                }
            }
        )
    )

    rows = leetcode.accepted_results_from_progress(
        tmp_path,
        progress,
        lang,
        model_slug="ollama__gemma4_e4b",
    )

    assert len(rows) == 1
    assert rows[0].source_path == source
    assert rows[0].result["accepted_source"] == "progress"


def test_build_workload_writes_deterministic_shared_files(tmp_path: Path) -> None:
    lang = leetcode.get_language("python")
    problem = _average_problem()
    leetcode.scaffold(tmp_path, [lang], [problem])
    source = leetcode.solution_path(tmp_path, lang, problem["title_slug"])
    _write_average_solution(source)
    result = leetcode.AcceptedResult(
        model_slug="ollama__gemma4_e4b",
        language=lang,
        problem_slug=problem["title_slug"],
        result_path=tmp_path / "result.json",
        source_path=source,
        result={"attempt": {"accepted": True}},
    )

    first = leetcode.build_workload_for_accepted_result(
        tmp_path,
        result,
        overwrite=True,
    )
    workload = json.loads(
        leetcode.workload_path(tmp_path, problem["title_slug"]).read_text()
    )
    expected = json.loads(
        leetcode.expected_output_path(tmp_path, problem["title_slug"]).read_text()
    )
    first_hash = workload["workload_hash"]
    second = leetcode.build_workload_for_accepted_result(
        tmp_path,
        result,
        overwrite=True,
    )
    workload_again = json.loads(
        leetcode.workload_path(tmp_path, problem["title_slug"]).read_text()
    )

    assert first["status"] == "built"
    assert second["status"] == "built"
    assert workload["language_independent"] is True
    assert workload["case_counts"]["examples"] == 2
    assert workload["case_counts"]["synthetic"] > 0
    assert expected["workload_hash"] == first_hash
    assert workload_again["workload_hash"] == first_hash


def test_unsupported_workload_shape_is_skipped(tmp_path: Path) -> None:
    lang = leetcode.get_language("python")
    problem = _problem("linked-list-components")
    problem["tags"] = ["Linked List"]
    problem["code_snippets"]["python3"] = (
        "# class ListNode:\n"
        "#     def __init__(self, val=0, next=None):\n"
        "#         self.val = val\n"
        "class Solution:\n"
        "    def numComponents(self, head: Optional[ListNode], nums: List[int]) -> int:\n"
        "        "
    )
    leetcode.scaffold(tmp_path, [lang], [problem])
    source = leetcode.solution_path(tmp_path, lang, problem["title_slug"])
    source.write_text("class Solution: pass\n")
    result = leetcode.AcceptedResult(
        model_slug="ollama__gemma4_e4b",
        language=lang,
        problem_slug=problem["title_slug"],
        result_path=tmp_path / "result.json",
        source_path=source,
        result={"attempt": {"accepted": True}},
    )

    row = leetcode.build_workload_for_accepted_result(tmp_path, result, overwrite=True)
    workload = json.loads(
        leetcode.workload_path(tmp_path, problem["title_slug"]).read_text()
    )

    assert row["status"] == "skipped"
    assert workload["skipped"] is True
    assert "Linked List" in workload["skipped_reason"]


def test_codecarbon_kwh_conversion_is_microjoules() -> None:
    assert _kwh_to_uj(1.0) == 3_600_000_000_000


def test_curated_sync_writes_shared_workload_and_prunes_old_files(
    tmp_path: Path,
) -> None:
    old_workload = tmp_path / "leetcode-energy" / "reference" / "workloads" / "old.json"
    old_output = tmp_path / "leetcode-energy" / "reference" / "outputs" / "old.json"
    old_workload.parent.mkdir(parents=True)
    old_output.parent.mkdir(parents=True)
    old_workload.write_text("{}")
    old_output.write_text("{}")
    dataset = tmp_path / "curated.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "task_id": "double-number",
                "entry_point": "Solution().double",
                "starter_code": "class Solution:\n    def double(self, value: int) -> int:\n        pass\n",
                "prompt": "",
                "test": "def check(candidate):\n    assert candidate(value=2) == 4\n",
                "input_output": [{"input": "value = 2", "output": "4"}],
            }
        )
        + "\n"
    )

    rows = leetcode.sync_curated_dataset_workloads(tmp_path, dataset, prune=True)
    workload = json.loads(leetcode.workload_path(tmp_path, "double-number").read_text())

    assert rows[0]["cases"] == 1
    assert workload["schema_version"] == 2
    assert workload["language_independent_cases"] is True
    assert len(workload["workload_hash"]) == 64
    assert not old_workload.exists()
    assert not old_output.exists()


def test_curated_runner_validates_then_executes_cases(tmp_path: Path) -> None:
    source = tmp_path / "solution.py"
    source.write_text(
        "class Solution:\n    def restore(self, pairs):\n        return [1, 2, 3]\n"
    )
    workload = {
        "problem": "restore",
        "workload_hash": "abc",
        "prompt": "from collections import Counter\n",
        "entry_point": "Solution().restore",
        "cases": [{"input": "pairs = [[1, 2], [2, 3]]", "output": "[3, 2, 1]"}],
        "test": (
            "def valid(actual):\n"
            "    return {frozenset((actual[i], actual[i + 1])) for i in range(2)} "
            "== {frozenset((1, 2)), frozenset((2, 3))}\n"
            "def check(candidate):\n"
            "    assert valid(candidate(pairs=[[1, 2], [2, 3]]))\n"
        ),
    }

    result = leetcode.run_curated_python_workload(
        source=source,
        workload=workload,
        repeat=2,
        validate=True,
    )

    assert result["ok"] is True
    assert result["cases"] == 1
    assert result["repeat"] == 2


def test_case_measure_rejects_non_python() -> None:
    result = runner.invoke(
        app,
        [
            "leetcode-case-measure",
            "--model-slug",
            "ollama__gemma4_e4b",
            "--language",
            "java",
        ],
    )

    assert result.exit_code == 2
    assert "supports python only" in result.output
