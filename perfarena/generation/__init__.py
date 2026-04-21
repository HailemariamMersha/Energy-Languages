"""LLM generation pipeline for PerfArena.

The generation layer produces the source files the harness
measures. It uses LangChain chat-model abstractions for provider
portability (OpenAI, Anthropic, Google, Ollama, ...) and loads
prompt templates from files under ``perfarena/prompts``. Every
generation emits three artefacts alongside the source file:

- the extracted source file (e.g. ``sample_00.py``),
- a ``.raw.md`` sidecar with the unprocessed LLM response,
- a ``.meta.json`` sidecar with full per-row provenance metadata
  as described in Section 4, item 11 of the proposal.
"""
from __future__ import annotations

from .llm import build_chat_model
from .pipeline import (
    GenerationRequest,
    GenerationResult,
    extract_code,
    generate_one,
    generate_one_via_agent,
    generate_one_via_remote_agent,
)
from .profiler import ProfileMetrics, Profiler, host_fingerprint, rapl_available

__all__ = [
    "GenerationRequest",
    "GenerationResult",
    "ProfileMetrics",
    "Profiler",
    "build_chat_model",
    "extract_code",
    "generate_one",
    "generate_one_via_agent",
    "generate_one_via_remote_agent",
    "host_fingerprint",
    "rapl_available",
]
