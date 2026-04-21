"""Isolated profiling agent for LLM generation.

The agent is a standalone subprocess that wraps a single LLM call
in a :class:`Profiler`. The orchestrator (the perfarena CLI) spawns
it, feeds it a request on stdin, waits for it to finish, and reads
the response from stdout. The response includes the generated text,
the request parameters, and the collected performance metrics.

Why a separate process: running the LLM call in its own process
keeps the measurement clean. The orchestrator's own CPU, memory,
and energy usage do not contaminate the numbers we record for the
inference step. For local LLMs whose inference happens in an
external daemon (Ollama), the agent can also be pointed at that
daemon's PID so it records the daemon's per-call CPU delta
alongside the package-level RAPL energy delta.

Request schema (JSON on stdin):

    {
      "provider":          "openai" | "anthropic" | "google" | "ollama",
      "model":             "<provider-specific model name>",
      "system_prompt":     "...",
      "user_prompt":       "...",
      "temperature":       0.2,
      "max_tokens":        4096,
      "top_p":             null | number,
      "top_k":             null | integer,
      "seed":              null | integer,
      "target_pid":        null | integer,      # measure this PID too
      "target_process":    null | "ollama"      # or auto-locate by name
    }

Response schema (JSON on stdout):

    {
      "ok":            true | false,
      "error":         null | "message",
      "raw_output":    "<full LLM response>",
      "request_echo":  { ... input, for provenance },
      "metrics":       { ... ProfileMetrics.to_dict() },
      "host":          { ... host_fingerprint() },
      "started_at":    "ISO-8601 UTC",
      "finished_at":   "ISO-8601 UTC",
      "agent_version": "x.y.z"
    }

Invocation:

    perfarena-agent < request.json > response.json
    perfarena-agent --request-file req.json --response-file resp.json
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

from .. import __version__
from .llm import build_chat_model
from .profiler import Profiler, find_process_by_name, host_fingerprint

from langchain_core.messages import HumanMessage, SystemMessage


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response_content_to_text(response: Any) -> str:
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


def run_one(request: dict[str, Any]) -> dict[str, Any]:
    """Execute a single generation request and return a response dict."""
    started_at = _utc_now_iso()

    provider = request["provider"]
    model = request["model"]
    system_prompt = request.get("system_prompt", "")
    user_prompt = request["user_prompt"]

    # Resolve a target PID for external-daemon profiling.
    target_pid: int | None = request.get("target_pid")
    target_process: str | None = request.get("target_process")
    if target_pid is None and target_process:
        target_pid = find_process_by_name(target_process)

    chat = build_chat_model(
        provider=provider,
        model=model,
        temperature=request.get("temperature", 0.2),
        max_tokens=request.get("max_tokens", 4096),
        top_p=request.get("top_p"),
        top_k=request.get("top_k"),
        seed=request.get("seed"),
    )

    messages: list[Any] = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=user_prompt))

    raw_output = ""
    error: str | None = None
    try:
        with Profiler(target_pid=target_pid) as prof:
            response = chat.invoke(messages)
            raw_output = _response_content_to_text(response)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        # Re-enter the profiler block so we still record partial metrics.
        traceback.print_exc(file=sys.stderr)

    finished_at = _utc_now_iso()

    return {
        "ok": error is None,
        "error": error,
        "raw_output": raw_output,
        "request_echo": {
            "provider": provider,
            "model": model,
            "temperature": request.get("temperature", 0.2),
            "max_tokens": request.get("max_tokens", 4096),
            "top_p": request.get("top_p"),
            "top_k": request.get("top_k"),
            "seed": request.get("seed"),
            "target_pid": target_pid,
            "target_process": target_process,
        },
        "metrics": prof.metrics.to_dict() if "prof" in locals() else {},
        "host": host_fingerprint(),
        "started_at": started_at,
        "finished_at": finished_at,
        "agent_version": __version__,
    }


def _run_persistent(argv_rest: list[str]) -> int:
    """Long-lived agent mode.

    Reads one JSON request per line on stdin. Writes one JSON
    response per line on stdout. Exits on EOF or on a blank line.
    Intended for in-process local LLMs (`transformers`,
    `llama-cpp-python`) where spawning a fresh Python process per
    call would reload the model weights. For those providers the
    orchestrator launches the agent once and streams requests into
    it for the duration of a campaign.
    """
    del argv_rest  # no extra flags today
    for line in sys.stdin:
        line = line.strip()
        if not line:
            break
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            sys.stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"invalid JSON on stdin: {exc}",
                    }
                )
                + "\n"
            )
            sys.stdout.flush()
            continue
        response = run_one(request)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="perfarena-agent",
        description="Isolated profiling agent for PerfArena LLM calls.",
    )
    parser.add_argument(
        "--request-file",
        help="Path to a JSON request file. If omitted, the request is read from stdin.",
    )
    parser.add_argument(
        "--response-file",
        help="Path to write the JSON response. If omitted, the response is written to stdout.",
    )
    parser.add_argument(
        "--persistent",
        action="store_true",
        help=(
            "Long-lived mode: read one JSON request per line on stdin "
            "and write one JSON response per line on stdout, until EOF "
            "or a blank line. Use this for in-process local LLMs where "
            "model weights should stay loaded across calls."
        ),
    )
    args = parser.parse_args(argv)

    if args.persistent:
        return _run_persistent([])

    if args.request_file:
        with open(args.request_file) as fh:
            request = json.load(fh)
    else:
        request = json.load(sys.stdin)

    response = run_one(request)
    payload = json.dumps(response, indent=2, sort_keys=True)

    if args.response_file:
        with open(args.response_file, "w") as fh:
            fh.write(payload)
    else:
        sys.stdout.write(payload)
        sys.stdout.write("\n")

    return 0 if response["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
