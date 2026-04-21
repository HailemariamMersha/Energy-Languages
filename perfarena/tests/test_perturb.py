"""Tests for the perturbed-CLBG generator."""
from __future__ import annotations

from perfarena.config import load_config
from perfarena.perturb import (
    perturb_prompt_context,
    renamed_identifier_hints,
    rescale_argument,
)


def test_rescale_argument_is_proportional():
    cfg = load_config()
    problem = cfg.get_problem("binary-trees")
    assert rescale_argument(problem, 1.0) == problem.default_argument
    doubled = rescale_argument(problem, 2.0)
    assert int(doubled) == 2 * int(problem.default_argument)


def test_renamed_identifiers_are_deterministic():
    cfg = load_config()
    problem = cfg.get_problem("binary-trees")
    a = renamed_identifier_hints(problem, "seed-1")
    b = renamed_identifier_hints(problem, "seed-1")
    c = renamed_identifier_hints(problem, "seed-2")
    assert a == b
    assert a != c


def test_perturb_prompt_context_mentions_rescale_and_renaming():
    cfg = load_config()
    problem = cfg.get_problem("binary-trees")
    ctx = perturb_prompt_context(problem, scale=1.5, seed_material="seed")
    assert ctx.rescaled_argument != problem.default_argument
    assert "tree" in ctx.extra_hint
    assert "->" in ctx.extra_hint
