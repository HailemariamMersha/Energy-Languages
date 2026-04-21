"""Pairwise classification subtask.

The proposal's multi-oracle evaluation (Section 4 item 7) asks
whether a model that *generates* efficient code also *recognises*
efficient code when shown two implementations. This module builds
classification pairs from the measurement dataset, runs an LLM on
each pair, and scores its answers against the measurement-derived
ground truth.

The pipeline is deliberately simple:

1. Collect all (language, problem) cells where we have at least
   two samples whose execution measurements differ by a clear
   margin.
2. Pick one "fast" sample and one "slow" sample per cell.
3. Ask a chosen LLM which implementation is faster, with the two
   implementations presented in a randomised A/B order.
4. Record the model's answer, the correct answer, and a
   provenance sidecar alongside it.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from langchain_core.messages import HumanMessage, SystemMessage

from .config import PerfArenaConfig
from .generation.llm import build_chat_model
from .provenance import capture as capture_provenance


# ---------------------------------------------------------------- pair construction


@dataclass
class ClassificationPair:
    language: str
    problem: str
    fast_sample_path: Path
    slow_sample_path: Path
    fast_median_wall_ms: float
    slow_median_wall_ms: float
    speedup_ratio: float  # slow / fast, always >= 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "problem": self.problem,
            "fast_sample_path": str(self.fast_sample_path),
            "slow_sample_path": str(self.slow_sample_path),
            "fast_median_wall_ms": self.fast_median_wall_ms,
            "slow_median_wall_ms": self.slow_median_wall_ms,
            "speedup_ratio": self.speedup_ratio,
        }


def build_pairs_from_measurements(
    measurements: list[dict[str, Any]],
    generations_dir: Path,
    min_ratio: float = 1.25,
) -> list[ClassificationPair]:
    """Build classification pairs from a list of measurement rows.

    Expects the JSONL rows produced by ``perfarena.measurement``,
    each of which has ``language``, ``problem``, ``sample_id``,
    ``wall_ms``, and ``generation_meta_path`` fields. For every
    (language, problem) cell we compute the median wall time per
    sample, pick the fastest and slowest, and emit a pair if their
    ratio exceeds ``min_ratio``.
    """
    from statistics import median

    by_cell: dict[tuple[str, str], dict[int, list[float]]] = {}
    meta_for_sample: dict[tuple[str, str, int], str] = {}
    for row in measurements:
        key = (row["language"], row["problem"])
        sample = int(row["sample_id"])
        by_cell.setdefault(key, {}).setdefault(sample, []).append(float(row["wall_ms"]))
        if row.get("generation_meta_path"):
            meta_for_sample[(row["language"], row["problem"], sample)] = row[
                "generation_meta_path"
            ]

    pairs: list[ClassificationPair] = []
    for (language, problem), per_sample in by_cell.items():
        medians = {s: median(w) for s, w in per_sample.items() if w}
        if len(medians) < 2:
            continue
        fast_sample = min(medians, key=lambda s: medians[s])
        slow_sample = max(medians, key=lambda s: medians[s])
        if fast_sample == slow_sample:
            continue
        fast_median = medians[fast_sample]
        slow_median = medians[slow_sample]
        if fast_median <= 0:
            continue
        ratio = slow_median / fast_median
        if ratio < min_ratio:
            continue

        fast_meta = meta_for_sample.get((language, problem, fast_sample))
        slow_meta = meta_for_sample.get((language, problem, slow_sample))
        if not fast_meta or not slow_meta:
            continue
        fast_path = Path(_source_path_from_meta(fast_meta))
        slow_path = Path(_source_path_from_meta(slow_meta))
        if not fast_path.exists() or not slow_path.exists():
            continue

        pairs.append(
            ClassificationPair(
                language=language,
                problem=problem,
                fast_sample_path=fast_path,
                slow_sample_path=slow_path,
                fast_median_wall_ms=fast_median,
                slow_median_wall_ms=slow_median,
                speedup_ratio=ratio,
            )
        )
    return pairs


def _source_path_from_meta(meta_path: str) -> str:
    with open(meta_path) as fh:
        meta = json.load(fh)
    return meta["paths"]["source"]


# ---------------------------------------------------------------- scoring one pair


CLASSIFICATION_SYSTEM = (
    "You are a performance-aware programmer. You will be shown two "
    "implementations of the same problem in the same language. Your "
    "job is to decide which one will run faster on a typical CPU. "
    "Reply with a single token: A or B. Do not explain your "
    "reasoning."
)


CLASSIFICATION_USER_TEMPLATE = """\
Problem: {problem}
Language: {language}

Implementation A:
```{lang_tag}
{code_a}
```

Implementation B:
```{lang_tag}
{code_b}
```

Which implementation runs faster? Reply with A or B only.
"""


_ANSWER_RE = re.compile(r"\b([AB])\b", re.IGNORECASE)


def _parse_answer(raw: str) -> str | None:
    m = _ANSWER_RE.search(raw.strip())
    if m is None:
        return None
    return m.group(1).upper()


@dataclass
class ClassificationResult:
    pair: ClassificationPair
    provider: str
    model: str
    correct_answer: str  # "A" or "B"
    model_answer: str | None
    model_raw: str
    correct: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair.to_dict(),
            "provider": self.provider,
            "model": self.model,
            "correct_answer": self.correct_answer,
            "model_answer": self.model_answer,
            "model_raw": self.model_raw,
            "correct": self.correct,
            "metadata": self.metadata,
        }


def classify_pair(
    pair: ClassificationPair,
    provider: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 64,
    seed: int | None = None,
) -> ClassificationResult:
    """Ask the chosen LLM which of two implementations is faster.

    The two implementations are presented in a randomised A/B order
    that is itself seeded deterministically from the pair's source
    paths so a re-run produces the same ordering.
    """
    order_seed = int.from_bytes(
        hashlib.sha256(
            (str(pair.fast_sample_path) + str(pair.slow_sample_path)).encode()
        ).digest()[:8],
        "big",
    )
    rng = random.Random(order_seed)
    swap = rng.random() < 0.5
    if swap:
        code_a = pair.slow_sample_path.read_text()
        code_b = pair.fast_sample_path.read_text()
        correct = "B"
    else:
        code_a = pair.fast_sample_path.read_text()
        code_b = pair.slow_sample_path.read_text()
        correct = "A"

    user_text = CLASSIFICATION_USER_TEMPLATE.format(
        problem=pair.problem,
        language=pair.language,
        lang_tag=pair.language,
        code_a=code_a,
        code_b=code_b,
    )

    chat = build_chat_model(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        seed=seed,
    )
    response = chat.invoke(
        [SystemMessage(content=CLASSIFICATION_SYSTEM), HumanMessage(content=user_text)]
    )
    raw = response.content if isinstance(response.content, str) else "".join(
        part if isinstance(part, str) else part.get("text", "") for part in response.content
    )
    parsed = _parse_answer(raw)

    return ClassificationResult(
        pair=pair,
        provider=provider,
        model=model,
        correct_answer=correct,
        model_answer=parsed,
        model_raw=raw,
        correct=parsed == correct,
        metadata={
            "order_swap": swap,
            "provenance": capture_provenance(),
        },
    )


def classify_pairs(
    pairs: Iterable[ClassificationPair],
    provider: str,
    model: str,
    **kwargs: Any,
) -> list[ClassificationResult]:
    return [classify_pair(p, provider, model, **kwargs) for p in pairs]
