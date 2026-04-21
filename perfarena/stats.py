"""Statistics layer for PerfArena.

Small, dependency-free statistical helpers. No scipy or pandas on
the base install. When we need heavier machinery later we can pull
it in behind an optional dep, but the numbers below are the ones
explicitly named in the proposal and need to be available to every
PerfArena user.

Provided:

- :func:`harmonic_mean`
- :func:`bootstrap_ci` (percentile bootstrap)
- :func:`median_and_ci` (wraps bootstrap_ci around statistics.median)
- :func:`cis_overlap`
- :func:`refuse_to_rank` (the overlapping-CI no-rank rule)
- :func:`mann_whitney_u` (two-sided, normal approximation)
- :func:`kendall_tau_b` (handles ties)
- :func:`holm_bonferroni`

None of these are intended to replace a real statistics package
for publication-grade work. They exist so the leaderboard
pipeline can run on a stock Python install and so the tests in
this repo can be self-contained.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


# -- Aggregators -----------------------------------------------------------


def harmonic_mean(values: Sequence[float]) -> float:
    """Harmonic mean, safe for lists with zeros or negatives.

    Raises ValueError if the list is empty. Non-positive values
    yield NaN (you cannot harmonic-mean a speedup ratio of 0 or
    below).
    """
    if not values:
        raise ValueError("harmonic_mean: empty sequence")
    inv_sum = 0.0
    for v in values:
        if v <= 0 or math.isnan(v) or math.isinf(v):
            return float("nan")
        inv_sum += 1.0 / v
    return len(values) / inv_sum


# -- Bootstrap CI ----------------------------------------------------------


@dataclass
class CI:
    point: float
    lower: float
    upper: float
    method: str = "bootstrap-percentile"
    n: int = 0
    confidence: float = 0.95

    def width(self) -> float:
        return self.upper - self.lower

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = statistics.median,
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int | None = None,
) -> CI:
    """Percentile bootstrap CI for an arbitrary statistic.

    Defaults: median, 95%, 2000 resamples. Use the ``seed`` argument
    for reproducible CI widths across reruns.
    """
    if len(values) == 0:
        raise ValueError("bootstrap_ci: empty sequence")
    if confidence <= 0.0 or confidence >= 1.0:
        raise ValueError("confidence must be in (0, 1)")

    rng = random.Random(seed)
    n = len(values)
    resamples: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        resamples.append(statistic(sample))
    resamples.sort()
    alpha = (1.0 - confidence) / 2.0
    lower = resamples[int(alpha * n_resamples)]
    upper = resamples[min(int((1.0 - alpha) * n_resamples), n_resamples - 1)]
    point = statistic(values)
    return CI(point=point, lower=lower, upper=upper, n=n, confidence=confidence)


def median_and_ci(
    values: Sequence[float],
    confidence: float = 0.95,
    n_resamples: int = 2000,
    seed: int | None = None,
) -> CI:
    return bootstrap_ci(
        values,
        statistic=statistics.median,
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
    )


# -- Overlap and the refuse-to-rank rule -----------------------------------


def cis_overlap(a: CI, b: CI) -> bool:
    return not (a.upper < b.lower or b.upper < a.lower)


def refuse_to_rank(cells: dict[str, CI]) -> tuple[list[str], list[tuple[str, str]]]:
    """Apply the refuse-to-rank-if-CIs-overlap policy.

    Returns a tuple ``(ordered, overlaps)``:

    - ``ordered``: the subset of cell keys that can be placed on a
      linear ranking using the rule that one cell is strictly better
      than another only when their CIs do not overlap. Ordering is
      by point estimate ascending. If any pair in the transitive
      closure overlaps, that cell is excluded.
    - ``overlaps``: the pairs of cell keys whose CIs overlap and
      therefore cannot be ordered against each other.
    """
    keys = sorted(cells, key=lambda k: cells[k].point)
    overlaps: list[tuple[str, str]] = []
    for i, a_key in enumerate(keys):
        for b_key in keys[i + 1 :]:
            if cis_overlap(cells[a_key], cells[b_key]):
                overlaps.append((a_key, b_key))
    overlapped = {k for pair in overlaps for k in pair}
    ordered = [k for k in keys if k not in overlapped]
    return ordered, overlaps


# -- Mann-Whitney U (two-sided, normal approximation) ----------------------


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Return (U, p) for a two-sided Mann-Whitney U test.

    Uses the normal approximation with a tie correction, which is
    adequate for the sample sizes PerfArena operates on (N=10 to
    N=30 per cell). Not exact; not suitable for very small N.
    """
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("mann_whitney_u: empty sequence")

    combined = [(v, 0) for v in a] + [(v, 1) for v in b]
    combined.sort(key=lambda t: t[0])

    # Compute ranks with average-rank tie handling.
    ranks = [0.0] * len(combined)
    i = 0
    tie_correction = 0.0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-indexed average rank
        for k in range(i, j + 1):
            ranks[k] = avg
        t = j - i + 1
        if t > 1:
            tie_correction += t * t * t - t
        i = j + 1

    r1 = sum(r for r, (_, grp) in zip(ranks, combined) if grp == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    mean_u = n1 * n2 / 2.0
    n = n1 + n2
    if n <= 1:
        return u, 1.0
    tie_adj = tie_correction / (n * (n - 1))
    var_u = (n1 * n2 / 12.0) * ((n + 1) - tie_adj)
    if var_u <= 0:
        return u, 1.0
    z = (u - mean_u) / math.sqrt(var_u)
    # Two-sided p from the standard normal.
    p = 2.0 * (1.0 - _phi(abs(z)))
    return u, max(0.0, min(1.0, p))


def _phi(x: float) -> float:
    """Standard normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# -- Kendall's tau-b -------------------------------------------------------


def kendall_tau_b(a: Sequence[float], b: Sequence[float]) -> float:
    """Kendall's tau-b rank correlation.

    Handles ties in either sequence. Returns 0.0 on degenerate input.
    """
    if len(a) != len(b):
        raise ValueError("kendall_tau_b: length mismatch")
    n = len(a)
    if n < 2:
        return 0.0

    concordant = 0
    discordant = 0
    ties_a = 0
    ties_b = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = a[i] - a[j]
            db = b[i] - b[j]
            if da == 0 and db == 0:
                continue
            if da == 0:
                ties_a += 1
                continue
            if db == 0:
                ties_b += 1
                continue
            if (da > 0 and db > 0) or (da < 0 and db < 0):
                concordant += 1
            else:
                discordant += 1

    n0 = n * (n - 1) / 2
    denom = math.sqrt((n0 - ties_a) * (n0 - ties_b))
    if denom == 0:
        return 0.0
    return (concordant - discordant) / denom


# -- Holm correction -------------------------------------------------------


def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Return Holm-Bonferroni-adjusted p-values in input order.

    For m tests, sort p-values ascending, multiply the i-th smallest
    by (m - i), then enforce monotonicity and cap at 1.0. Adjusted
    values are returned in the original input order.
    """
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda t: t[1])
    adjusted = [0.0] * m
    previous = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        factor = m - rank
        val = min(1.0, p * factor)
        val = max(val, previous)  # enforce monotonicity
        adjusted[orig_idx] = val
        previous = val
    return adjusted


# -- BEP -------------------------------------------------------------------


def break_even_point(
    execution_energy_baseline_j: float,
    execution_energy_optimized_j: float,
    generation_energy_j: float,
) -> float:
    """Return the number of executions after which the optimized code
    recovers the energy spent generating it.

    BEP = generation_energy / (baseline - optimized). Returns
    ``math.inf`` if the optimized code is not actually faster on
    average (a negative or zero denominator).
    """
    delta = execution_energy_baseline_j - execution_energy_optimized_j
    if delta <= 0:
        return math.inf
    return generation_energy_j / delta
