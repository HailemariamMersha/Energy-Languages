"""LangChain chat-model factory.

Providers are loaded lazily so that adding a new provider does not
require pulling its client library at import time. Each provider's
LangChain integration reads credentials from the environment using
its standard variable (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``,
``GOOGLE_API_KEY``, ``OLLAMA_HOST``).
"""
from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel


def build_chat_model(
    provider: str,
    model: str,
    temperature: float = 0.2,
    max_tokens: int | None = 4096,
    top_p: float | None = None,
    top_k: int | None = None,
    seed: int | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Instantiate a LangChain chat model for the given provider.

    Supported providers: ``openai``, ``anthropic``, ``google``
    (alias ``gemini``), ``ollama``.

    Parameters not accepted by a particular provider are silently
    ignored so the same CLI surface can drive all of them.
    """
    provider = provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        extras: dict[str, Any] = {}
        if top_p is not None:
            extras["top_p"] = top_p
        if seed is not None:
            extras["seed"] = seed
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **extras,
            **kwargs,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        extras = {}
        if top_p is not None:
            extras["top_p"] = top_p
        if top_k is not None:
            extras["top_k"] = top_k
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **extras,
            **kwargs,
        )

    if provider in ("google", "gemini", "google-genai"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        extras = {}
        if top_p is not None:
            extras["top_p"] = top_p
        if top_k is not None:
            extras["top_k"] = top_k
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            **extras,
            **kwargs,
        )

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError:  # pragma: no cover - compatibility with older envs
            from langchain_community.chat_models import ChatOllama

        extras = {}
        if top_p is not None:
            extras["top_p"] = top_p
        if top_k is not None:
            extras["top_k"] = top_k
        if seed is not None:
            extras["seed"] = seed
        ollama_host = os.environ.get("OLLAMA_HOST")
        if ollama_host and "base_url" not in kwargs:
            extras["base_url"] = ollama_host
        return ChatOllama(
            model=model,
            temperature=temperature,
            num_predict=max_tokens,
            **extras,
            **kwargs,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}")
