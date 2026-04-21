"""End-to-end generation pipeline: prompt -> LLM -> source file on disk."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import LanguageSpec, PerfArenaConfig, ProblemSpec
from ..provenance import capture as capture_provenance
from .llm import build_chat_model


# --- Prompt loading ---------------------------------------------------------


def load_prompt_template(config: PerfArenaConfig, name: str) -> str:
    """Load a prompt template file from ``perfarena/prompts``."""
    path = config.prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text()


def load_language_hint(config: PerfArenaConfig, language_key: str) -> str:
    """Load the per-language prompt hint, or return an empty string."""
    path = config.prompts_dir / "language_hints" / f"{language_key}.txt"
    if not path.exists():
        return ""
    return path.read_text()


# --- Code extraction --------------------------------------------------------


_FENCE_ANY = re.compile(r"```[a-zA-Z0-9_+\-]*\n(.*?)```", re.DOTALL)


def extract_code(raw: str, language_key: str) -> str:
    """Extract source code from a possibly-markdown LLM response.

    Preference order:

    1. A fenced block tagged with the language key (or a common
       alias: ``js`` for ``javascript``, ``ts`` for ``typescript``,
       ``cs`` for ``csharp``, ``cpp`` for ``cpp`` / ``c++``, etc.).
    2. The first fenced block of any kind.
    3. The raw text, stripped.

    This is intentionally simple. Cappendijk et al. (GREENS 2025)
    note that LLM-generated code often requires manual post-
    processing; downstream validation (compilation, unit tests)
    is the real safety net.
    """
    aliases = {
        "python": ["python", "py"],
        "javascript": ["javascript", "js"],
        "typescript": ["typescript", "ts"],
        "java": ["java"],
        "csharp": ["csharp", "cs", "c#"],
        "cpp": ["cpp", "c++", "cxx"],
        "php": ["php"],
        "go": ["go", "golang"],
        "rust": ["rust", "rs"],
        "ruby": ["ruby", "rb"],
    }
    tags = aliases.get(language_key, [language_key])
    for tag in tags:
        tagged = re.compile(
            rf"```{re.escape(tag)}\s*\n(.*?)```",
            re.DOTALL | re.IGNORECASE,
        )
        m = tagged.search(raw)
        if m:
            return m.group(1).strip() + "\n"

    m = _FENCE_ANY.search(raw)
    if m:
        return m.group(1).strip() + "\n"

    return raw.strip() + "\n"


# --- Request / result dataclasses ------------------------------------------


@dataclass
class GenerationRequest:
    provider: str
    model: str
    problem: str
    language: str
    temperature: float = 0.2
    max_tokens: int = 4096
    top_p: float | None = None
    top_k: int | None = None
    seed: int | None = None
    sample_id: int = 0
    system_template_name: str = "system.txt"
    user_template_name: str = "user.txt"
    # Agent-mode options (only used by ``generate_one_via_agent``).
    target_pid: int | None = None
    target_process: str | None = None


@dataclass
class GenerationResult:
    request: GenerationRequest
    raw_output: str
    extracted_code: str
    source_path: Path
    raw_path: Path
    meta_path: Path
    prompt_hash: str
    duration_s: float
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Prompt rendering ------------------------------------------------------


def _render_user_prompt(
    template: str,
    problem: ProblemSpec,
    language: LanguageSpec,
    language_hint: str,
) -> str:
    return template.format(
        language_name=language.display_name,
        language_paradigm=language.paradigm,
        language_hint=language_hint,
        problem_name=problem.name,
        problem_description=problem.description.strip(),
        input_spec=problem.input_spec.strip(),
        output_spec=problem.output_spec.strip(),
        default_argument=problem.default_argument,
        invocation_hint=problem.invocation_hint.strip(),
        algorithm_class=problem.algorithm_class,
    )


def _render_system_prompt(template: str, language: LanguageSpec) -> str:
    return template.format(
        language_name=language.display_name,
        language_paradigm=language.paradigm,
    )


def build_messages(
    config: PerfArenaConfig,
    problem: ProblemSpec,
    language: LanguageSpec,
    system_template_name: str = "system.txt",
    user_template_name: str = "user.txt",
) -> tuple[list[Any], str, str]:
    """Render the system and user messages and return them plus their texts."""
    system_template = load_prompt_template(config, system_template_name)
    user_template = load_prompt_template(config, user_template_name)
    language_hint = load_language_hint(config, language.key)

    system_text = _render_system_prompt(system_template, language)
    user_text = _render_user_prompt(user_template, problem, language, language_hint)

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=user_text),
    ]
    return messages, system_text, user_text


# --- Main entry point ------------------------------------------------------


def _slugify_model(provider: str, model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", f"{provider}__{model}")


def _response_to_text(response: Any) -> str:
    content = response.content
    if isinstance(content, str):
        return content
    # LangChain sometimes returns a list of content parts.
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and "text" in part:
            parts.append(part["text"])
    return "".join(parts)


def generate_one(
    config: PerfArenaConfig,
    request: GenerationRequest,
) -> GenerationResult:
    """Run a single (model, language, problem, sample_id) generation.

    Writes three files under
    ``<repo_root>/perfarena_out/generations/<model_slug>/<language_folder>/<problem>/``:

    - ``sample_<NN><ext>``            : extracted source code
    - ``sample_<NN><ext>.raw.md``     : raw LLM response
    - ``sample_<NN><ext>.meta.json``  : per-row provenance metadata
    """
    problem = config.get_problem(request.problem)
    language = config.get_language(request.language)

    messages, system_text, user_text = build_messages(
        config,
        problem,
        language,
        system_template_name=request.system_template_name,
        user_template_name=request.user_template_name,
    )

    chat = build_chat_model(
        provider=request.provider,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        top_k=request.top_k,
        seed=request.seed,
    )

    t0 = time.monotonic()
    response = chat.invoke(messages)
    duration = time.monotonic() - t0

    raw = _response_to_text(response)
    code = extract_code(raw, language.key)

    model_slug = _slugify_model(request.provider, request.model)
    out_dir = config.generations_dir / model_slug / language.folder / request.problem
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path = out_dir / f"sample_{request.sample_id:02d}{language.file_extension}"
    raw_path = source_path.with_suffix(source_path.suffix + ".raw.md")
    meta_path = source_path.with_suffix(source_path.suffix + ".meta.json")

    source_path.write_text(code)
    raw_path.write_text(raw)

    system_hash = hashlib.sha256(system_text.encode()).hexdigest()
    user_hash = hashlib.sha256(user_text.encode()).hexdigest()
    prompt_hash = hashlib.sha256(
        (system_text + "\n---\n" + user_text).encode()
    ).hexdigest()
    raw_sha = hashlib.sha256(raw.encode()).hexdigest()

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "perfarena_version": __import__("perfarena").__version__,
        "mode": "direct",
        "provider": request.provider,
        "model": request.model,
        "problem": request.problem,
        "language": request.language,
        "language_folder": language.folder,
        "sample_id": request.sample_id,
        "generation_parameters": {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "top_k": request.top_k,
            "seed": request.seed,
        },
        "prompts": {
            "system_template_name": request.system_template_name,
            "user_template_name": request.user_template_name,
            "system_prompt_sha256": system_hash,
            "user_prompt_sha256": user_hash,
            "prompt_pair_sha256": prompt_hash,
        },
        "response": {
            "raw_sha256": raw_sha,
            "raw_chars": len(raw),
            "extracted_code_chars": len(code),
            "duration_s": duration,
        },
        "provenance": capture_provenance(),
        "paths": {
            "source": str(source_path),
            "raw": str(raw_path),
        },
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))

    return GenerationResult(
        request=request,
        raw_output=raw,
        extracted_code=code,
        source_path=source_path,
        raw_path=raw_path,
        meta_path=meta_path,
        prompt_hash=prompt_hash,
        duration_s=duration,
        metadata=metadata,
    )


# --- Agent-mode generation -------------------------------------------------


def _resolve_agent_command(explicit: str | None = None) -> list[str]:
    """Decide how to invoke perfarena-agent.

    Preference order:

    1. ``explicit`` (caller-supplied path or full command string).
    2. The ``perfarena-agent`` console script, if pip installed it.
    3. ``python -m perfarena.generation.agent``, which always works
       when the package is importable.
    """
    if explicit:
        return explicit.split() if isinstance(explicit, str) else list(explicit)
    found = shutil.which("perfarena-agent")
    if found:
        return [found]
    return [sys.executable, "-m", "perfarena.generation.agent"]


def generate_one_via_remote_agent(
    config: PerfArenaConfig,
    request: GenerationRequest,
    executor: Any,
    remote_work_dir: str = "/tmp/perfarena",
    agent_command: str = "perfarena-agent",
    timeout: float = 600.0,
) -> GenerationResult:
    """Run ``perfarena-agent`` on a remote host via the given SSH executor.

    The orchestrator (this process) renders the prompts, writes a
    request JSON to a local temp file, ships it to the remote, tells
    the remote to run ``perfarena-agent --request-file ... --response-file ...``,
    then fetches the response JSON and extracts the code and metrics.
    The remote host must already have a matching ``perfarena-agent``
    on its PATH.

    This is the isolated-LLM-host mode: the orchestrator sits in the
    build container on a laptop or in CI, the agent runs on a
    dedicated LLM host where the model weights actually live, and the
    profiler numbers come from that host's RAPL counters and psutil
    view of its Ollama daemon.
    """
    import os
    import tempfile

    problem = config.get_problem(request.problem)
    language = config.get_language(request.language)

    _, system_text, user_text = build_messages(
        config,
        problem,
        language,
        system_template_name=request.system_template_name,
        user_template_name=request.user_template_name,
    )

    agent_request = {
        "provider": request.provider,
        "model": request.model,
        "system_prompt": system_text,
        "user_prompt": user_text,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "seed": request.seed,
        "target_pid": request.target_pid,
        "target_process": request.target_process,
    }

    # Give each request a stable, unique file name so concurrent
    # calls don't collide on the remote.
    stem = f"req_{os.getpid()}_{time.monotonic_ns()}"
    remote_req = f"{remote_work_dir}/{stem}.in.json"
    remote_resp = f"{remote_work_dir}/{stem}.out.json"

    executor.run(["mkdir", "-p", remote_work_dir])

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".in.json", delete=False
    ) as local_req_fh:
        json.dump(agent_request, local_req_fh)
        local_req_path = local_req_fh.name

    t0 = time.monotonic()
    try:
        executor.put_file(local_req_path, remote_req)

        res = executor.run(
            [
                agent_command,
                "--request-file",
                remote_req,
                "--response-file",
                remote_resp,
            ],
            timeout=timeout,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"remote perfarena-agent rc={res.returncode}: {res.stderr}"
            )

        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".out.json", delete=False
        ) as local_resp_fh:
            local_resp_path = local_resp_fh.name
        executor.get_file(remote_resp, local_resp_path)
        with open(local_resp_path) as fh:
            agent_response = json.load(fh)
    finally:
        try:
            Path(local_req_path).unlink()
        except OSError:
            pass
        # Best-effort remote cleanup.
        executor.run(
            ["rm", "-f", remote_req, remote_resp],
            timeout=30.0,
        )

    orchestrator_duration = time.monotonic() - t0

    if not agent_response.get("ok", False):
        raise RuntimeError(
            f"remote perfarena-agent reported failure: {agent_response.get('error')}"
        )

    raw = agent_response["raw_output"]
    code = extract_code(raw, language.key)

    model_slug = _slugify_model(request.provider, request.model)
    out_dir = config.generations_dir / model_slug / language.folder / request.problem
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path = out_dir / f"sample_{request.sample_id:02d}{language.file_extension}"
    raw_path = source_path.with_suffix(source_path.suffix + ".raw.md")
    meta_path = source_path.with_suffix(source_path.suffix + ".meta.json")

    source_path.write_text(code)
    raw_path.write_text(raw)

    system_hash = hashlib.sha256(system_text.encode()).hexdigest()
    user_hash = hashlib.sha256(user_text.encode()).hexdigest()
    prompt_hash = hashlib.sha256(
        (system_text + "\n---\n" + user_text).encode()
    ).hexdigest()
    raw_sha = hashlib.sha256(raw.encode()).hexdigest()

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "perfarena_version": __import__("perfarena").__version__,
        "mode": "remote-agent",
        "provider": request.provider,
        "model": request.model,
        "problem": request.problem,
        "language": request.language,
        "language_folder": language.folder,
        "sample_id": request.sample_id,
        "generation_parameters": {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "top_k": request.top_k,
            "seed": request.seed,
        },
        "prompts": {
            "system_template_name": request.system_template_name,
            "user_template_name": request.user_template_name,
            "system_prompt_sha256": system_hash,
            "user_prompt_sha256": user_hash,
            "prompt_pair_sha256": prompt_hash,
        },
        "response": {
            "raw_sha256": raw_sha,
            "raw_chars": len(raw),
            "extracted_code_chars": len(code),
            "orchestrator_duration_s": orchestrator_duration,
        },
        "inference": {
            "metrics": agent_response.get("metrics", {}),
            "host": agent_response.get("host", {}),
            "started_at": agent_response.get("started_at"),
            "finished_at": agent_response.get("finished_at"),
            "agent_version": agent_response.get("agent_version"),
            "target_pid": request.target_pid,
            "target_process": request.target_process,
            "executor": "ssh",
        },
        "provenance": capture_provenance(),
        "paths": {
            "source": str(source_path),
            "raw": str(raw_path),
        },
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))

    return GenerationResult(
        request=request,
        raw_output=raw,
        extracted_code=code,
        source_path=source_path,
        raw_path=raw_path,
        meta_path=meta_path,
        prompt_hash=prompt_hash,
        duration_s=orchestrator_duration,
        metadata=metadata,
    )


def generate_one_via_agent(
    config: PerfArenaConfig,
    request: GenerationRequest,
    agent_command: str | None = None,
    timeout: float = 600.0,
) -> GenerationResult:
    """Run a single generation through the isolated profiling agent.

    Spawns ``perfarena-agent`` as a subprocess, feeds it the rendered
    prompts and sampling parameters as JSON on stdin, and waits for
    the response on stdout. The returned :class:`GenerationResult`
    carries the extracted source file plus a ``meta.json`` sidecar
    whose ``inference`` section holds the metrics the agent recorded
    (wall time, CPU time, peak RSS, RAPL energy delta, optional
    target-PID CPU delta and RSS).

    Use this path whenever you want the numbers behind a generation.
    Use :func:`generate_one` when you only want the text and will
    ignore inference cost.
    """
    problem = config.get_problem(request.problem)
    language = config.get_language(request.language)

    messages, system_text, user_text = build_messages(
        config,
        problem,
        language,
        system_template_name=request.system_template_name,
        user_template_name=request.user_template_name,
    )
    del messages  # agent rebuilds messages from the two text prompts

    agent_request = {
        "provider": request.provider,
        "model": request.model,
        "system_prompt": system_text,
        "user_prompt": user_text,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "seed": request.seed,
        "target_pid": request.target_pid,
        "target_process": request.target_process,
    }

    cmd = _resolve_agent_command(agent_command)
    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        input=json.dumps(agent_request).encode(),
        capture_output=True,
        timeout=timeout,
    )
    orchestrator_duration = time.monotonic() - t0

    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError(
            "perfarena-agent failed "
            f"(rc={proc.returncode}): {proc.stderr.decode(errors='replace')}"
        )

    try:
        agent_response = json.loads(proc.stdout.decode(errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"perfarena-agent returned invalid JSON: {exc}. "
            f"stderr: {proc.stderr.decode(errors='replace')}"
        ) from exc

    if not agent_response.get("ok", False):
        raise RuntimeError(
            f"perfarena-agent reported failure: {agent_response.get('error')}"
        )

    raw = agent_response["raw_output"]
    code = extract_code(raw, language.key)

    model_slug = _slugify_model(request.provider, request.model)
    out_dir = config.generations_dir / model_slug / language.folder / request.problem
    out_dir.mkdir(parents=True, exist_ok=True)

    source_path = out_dir / f"sample_{request.sample_id:02d}{language.file_extension}"
    raw_path = source_path.with_suffix(source_path.suffix + ".raw.md")
    meta_path = source_path.with_suffix(source_path.suffix + ".meta.json")

    source_path.write_text(code)
    raw_path.write_text(raw)

    system_hash = hashlib.sha256(system_text.encode()).hexdigest()
    user_hash = hashlib.sha256(user_text.encode()).hexdigest()
    prompt_hash = hashlib.sha256(
        (system_text + "\n---\n" + user_text).encode()
    ).hexdigest()
    raw_sha = hashlib.sha256(raw.encode()).hexdigest()

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "perfarena_version": __import__("perfarena").__version__,
        "mode": "agent",
        "provider": request.provider,
        "model": request.model,
        "problem": request.problem,
        "language": request.language,
        "language_folder": language.folder,
        "sample_id": request.sample_id,
        "generation_parameters": {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "top_k": request.top_k,
            "seed": request.seed,
        },
        "prompts": {
            "system_template_name": request.system_template_name,
            "user_template_name": request.user_template_name,
            "system_prompt_sha256": system_hash,
            "user_prompt_sha256": user_hash,
            "prompt_pair_sha256": prompt_hash,
        },
        "response": {
            "raw_sha256": raw_sha,
            "raw_chars": len(raw),
            "extracted_code_chars": len(code),
            "orchestrator_duration_s": orchestrator_duration,
        },
        "inference": {
            "metrics": agent_response.get("metrics", {}),
            "host": agent_response.get("host", {}),
            "started_at": agent_response.get("started_at"),
            "finished_at": agent_response.get("finished_at"),
            "agent_version": agent_response.get("agent_version"),
            "target_pid": request.target_pid,
            "target_process": request.target_process,
        },
        "provenance": capture_provenance(),
        "paths": {
            "source": str(source_path),
            "raw": str(raw_path),
        },
    }
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))

    return GenerationResult(
        request=request,
        raw_output=raw,
        extracted_code=code,
        source_path=source_path,
        raw_path=raw_path,
        meta_path=meta_path,
        prompt_hash=prompt_hash,
        duration_s=orchestrator_duration,
        metadata=metadata,
    )
