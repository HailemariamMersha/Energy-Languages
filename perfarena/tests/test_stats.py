"""Tests for the small statistics layer."""
from __future__ import annotations

import math
import statistics

from perfarena.stats import (
    CI,
    bootstrap_ci,
    break_even_point,
    cis_overlap,
    harmonic_mean,
    holm_bonferroni,
    kendall_tau_b,
    mann_whitney_u,
    refuse_to_rank,
)


def test_harmonic_mean_basic():
    assert abs(harmonic_mean([1.0, 2.0, 4.0]) - statistics.harmonic_mean([1, 2, 4])) < 1e-9


def test_harmonic_mean_nan_on_non_positive():
    assert math.isnan(harmonic_mean([1.0, 0.0, 2.0]))
    assert math.isnan(harmonic_mean([1.0, -1.0, 2.0]))


def test_bootstrap_ci_is_reproducible_with_seed():
    data = [float(x) for x in range(1, 21)]
    a = bootstrap_ci(data, seed=7, n_resamples=500)
    b = bootstrap_ci(data, seed=7, n_resamples=500)
    assert a.lower == b.lower
    assert a.upper == b.upper
    assert a.contains(a.point)


def test_cis_overlap_and_refuse_to_rank():
    cells = {
        "a": CI(point=1.0, lower=0.8, upper=1.2, n=10),
        "b": CI(point=2.0, lower=1.8, upper=2.2, n=10),  # separated from a
        "c": CI(point=2.1, lower=1.9, upper=2.3, n=10),  # overlaps b
    }
    assert not cis_overlap(cells["a"], cells["b"])
    assert cis_overlap(cells["b"], cells["c"])
    ordered, overlaps = refuse_to_rank(cells)
    assert ordered == ["a"]
    assert ("b", "c") in overlaps or ("c", "b") in overlaps


def test_mann_whitney_u_distinguishes_clearly_different_samples():
    u, p = mann_whitney_u([1, 2, 3, 4, 5], [10, 11, 12, 13, 14])
    assert p < 0.05


def test_mann_whitney_u_no_difference_has_high_p():
    a = [1, 2, 3, 4, 5]
    b = [1, 2, 3, 4, 5]
    _, p = mann_whitney_u(a, b)
    assert p > 0.5


def test_kendall_tau_b_perfect_agreement_is_one():
    assert abs(kendall_tau_b([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9


def test_kendall_tau_b_perfect_disagreement_is_minus_one():
    assert abs(kendall_tau_b([1, 2, 3, 4], [40, 30, 20, 10]) + 1.0) < 1e-9


def test_holm_bonferroni_order_and_cap():
    adj = holm_bonferroni([0.01, 0.02, 0.03, 0.5])
    assert all(0.0 <= v <= 1.0 for v in adj)
    # monotonic non-decreasing when sorted by original p
    indexed = sorted(zip([0.01, 0.02, 0.03, 0.5], adj), key=lambda t: t[0])
    for (p_prev, adj_prev), (p_next, adj_next) in zip(indexed, indexed[1:]):
        assert adj_next >= adj_prev


def test_break_even_point_infinite_when_no_improvement():
    assert math.isinf(break_even_point(1.0, 1.0, 100.0))
    assert math.isinf(break_even_point(1.0, 2.0, 100.0))


def test_break_even_point_basic():
    bep = break_even_point(10.0, 8.0, 100.0)
    assert abs(bep - 50.0) < 1e-9
