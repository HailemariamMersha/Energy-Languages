"""Perturbed-CLBG generator: a contamination-probe sensitivity arm.

Most modern code LLMs have almost certainly trained on CLBG
solutions. The perturbed-CLBG probe asks a simple question: if we
rename the identifiers and rescale the input, do the models still
produce the same solutions they produced before? A model that is
essentially quoting a memorised solution will either fail on the
perturbed version or regress on efficiency; a model that understands
the problem should be robust.

This module provides two things:

1. :func:`perturb_prompt_context` — returns a perturbed copy of the
   problem description, renamed identifier hints, and a rescaled
   default argument, suitable for plugging into the existing user
   prompt template.
2. :func:`rescale_argument` — independent helper for rescaling the
   default N argument of a CLBG problem while keeping the iteration
   budget roughly constant.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Iterable

from .config import PerfArenaConfig, ProblemSpec


# ---------------------------------------------------------------- identifier perturbation


_IDENTIFIER_BANK = [
    "alpha", "beta", "gamma", "delta", "epsilon",
    "zeta", "eta", "theta", "iota", "kappa",
    "lambda_", "mu", "nu", "xi", "omicron",
    "pi_", "rho", "sigma", "tau", "upsilon",
    "phi_", "chi", "psi", "omega",
    "quark", "lepton", "boson", "fermion",
    "photon", "gluon",
]


def _deterministic_rng(seed_material: str) -> random.Random:
    digest = hashlib.sha256(seed_material.encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def renamed_identifier_hints(problem: ProblemSpec, seed_material: str = "") -> dict[str, str]:
    """Produce a deterministic renaming for the canonical identifiers
    mentioned in a CLBG problem's description.

    The intent is not to rewrite source code; it is to produce an
    alternative vocabulary that the user prompt can use so the LLM
    cannot lean on exact-string pattern matching against training
    data.
    """
    canonical_names = _canonical_names_for(problem)
    rng = _deterministic_rng(seed_material or problem.key)
    pool = list(_IDENTIFIER_BANK)
    rng.shuffle(pool)
    return {old: pool[i] for i, old in enumerate(canonical_names) if i < len(pool)}


def _canonical_names_for(problem: ProblemSpec) -> list[str]:
    """Return the small set of canonical identifiers we care about
    for a given CLBG problem.

    These are the identifiers that commonly appear in reference
    solutions and are therefore the ones a memoised LLM would
    gravitate to. The set is intentionally short; the goal is
    vocabulary perturbation, not a full AST rewrite.
    """
    per_problem: dict[str, list[str]] = {
        "binary-trees": ["tree", "depth", "check", "left", "right", "node"],
        "fannkuch-redux": ["perm", "flip", "checksum", "maxflips"],
        "fasta": ["alu", "iub", "homosapiens", "seed", "rand_next"],
        "k-nucleotide": ["freq", "kmer", "sequence", "count"],
        "mandelbrot": ["cx", "cy", "zr", "zi", "iter_limit"],
        "n-body": ["bodies", "dx", "dy", "dz", "mass", "velocity", "position"],
        "pidigits": ["digit", "spigot", "k", "n1", "n2"],
        "regex-redux": ["pattern", "replacement", "seq", "count"],
        "reverse-complement": ["seq", "complement", "reverse"],
        "spectral-norm": ["eigenvalue", "iter", "a", "v", "u"],
    }
    return per_problem.get(problem.key, [])


# ---------------------------------------------------------------- argument rescaling


def rescale_argument(problem: ProblemSpec, scale: float) -> str:
    """Multiply the problem's default argument by ``scale`` and return
    the result as a string, rounded to the nearest integer.

    A scale factor of 1.0 returns the original argument. Values
    above 1.0 make the benchmark longer; values below 1.0 make it
    shorter. This is the main input-size-tuning knob for making
    sure every iteration exceeds the RAPL noise floor (~1 s).
    """
    try:
        base = int(problem.default_argument)
    except ValueError:
        return problem.default_argument
    scaled = max(1, int(round(base * scale)))
    return str(scaled)


# ---------------------------------------------------------------- prompt context


@dataclass
class PerturbedContext:
    problem_key: str
    renamed_identifiers: dict[str, str]
    rescaled_argument: str
    seed_material: str
    extra_hint: str


def perturb_prompt_context(
    problem: ProblemSpec,
    scale: float = 1.0,
    seed_material: str = "",
) -> PerturbedContext:
    """Return the bundle of perturbations for a prompt override.

    The returned ``extra_hint`` is a short paragraph that can be
    inlined into the user prompt (replacing or augmenting the
    language hint) to make the LLM acknowledge the new vocabulary
    and argument.
    """
    renaming = renamed_identifier_hints(problem, seed_material)
    rescaled = rescale_argument(problem, scale)
    lines = [
        "Use the following identifier names wherever a reference solution "
        "to this problem conventionally uses the originals:",
    ]
    for old, new in renaming.items():
        lines.append(f"  - {old} -> {new}")
    lines.append(
        f"Interpret the default N argument as {rescaled} "
        f"(rescaled from {problem.default_argument})."
    )
    return PerturbedContext(
        problem_key=problem.key,
        renamed_identifiers=renaming,
        rescaled_argument=rescaled,
        seed_material=seed_material,
        extra_hint="\n".join(lines),
    )


def perturb_all(
    config: PerfArenaConfig,
    scale: float = 1.0,
    seed_material: str = "",
    problems: Iterable[str] | None = None,
) -> dict[str, PerturbedContext]:
    keys = list(problems) if problems else list(config.problems)
    return {
        k: perturb_prompt_context(
            config.get_problem(k), scale=scale, seed_material=seed_material
        )
        for k in keys
    }
