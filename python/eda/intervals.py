"""Confidence intervals for a proportion, and why the obvious one is wrong here.

**Every completion rate this project reports is near 1.0 on a few dozen runs**, which is the one
regime where the textbook normal approximation fails loudly enough to mislead. At `p = 1` its
half-width is `z * sqrt(p(1-p)/n)`, which is exactly zero, so it reports `[1.00, 1.00]`: certainty,
from ten runs. M3 was closed on 30 of 30 and this module exists so that figure is never quoted as
though the next track were guaranteed.

The **Wilson score interval** is the standard remedy. It inverts the score test rather than the
Wald test, which keeps it bounded away from a point at the extremes and inside `[0, 1]` everywhere.
On 10 of 10 it gives roughly `[0.72, 1.00]`, which is the honest statement that ten perfect runs are
consistent with a policy that fails one track in four.

Kept separate from `authenticity.py` because an interval is not a hypothesis test. That module's
results carry `reject_null` and a p-value, and neither means anything here: an interval answers
"what rates are consistent with this sample", not "is the null rejected".
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Two-sided 95 per cent. The z rather than a t, because this is a proportion and not a mean.
Z_95: float = 1.959963984540054


@dataclass(frozen=True)
class ProportionInterval:
    """A rate with the interval it is only meaningful inside."""

    scope: str
    successes: int
    trials: int
    point: float
    low: float
    high: float
    confidence: float

    @property
    def width(self) -> float:
        return self.high - self.low

    def overlaps(self, other: "ProportionInterval") -> bool:
        """Whether two intervals share any value.

        **The comparison that matters, and the one a bare percentage invites a reader to skip.**
        Two rates that differ by ten points on thirty runs each are not two different rates if
        their intervals overlap; they are one rate measured twice. Overlap is a conservative test
        of difference, so a non-overlap is evidence and an overlap is the absence of it, never
        proof that the two are equal.
        """
        return self.low <= other.high and other.low <= self.high

    def __str__(self) -> str:
        return (f"{self.successes}/{self.trials} = {100 * self.point:.1f}% "
                f"[{100 * self.low:.1f}, {100 * self.high:.1f}]")


def wilson(successes: int, trials: int, z: float = Z_95, scope: str = "") -> ProportionInterval:
    """The Wilson score interval for a binomial proportion.

    `trials == 0` returns the whole unit interval rather than raising: no data is not an error, and
    a caller reporting a set with nothing in it should print `[0, 1]` rather than crash or, worse,
    print a rate.
    """
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError(f"{successes} successes of {trials} trials is not a proportion")

    if trials == 0:
        return ProportionInterval(scope, 0, 0, float("nan"), 0.0, 1.0, _confidence(z))

    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator

    return ProportionInterval(
        scope=scope,
        successes=successes,
        trials=trials,
        point=p,
        low=max(0.0, centre - half),
        high=min(1.0, centre + half),
        confidence=_confidence(z),
    )


def wald(successes: int, trials: int, z: float = Z_95, scope: str = "") -> ProportionInterval:
    """The normal approximation, provided **only so the difference can be shown**.

    Nothing in this project should report this interval. It is here because research R6 quotes what
    it does at `p = 1`, and a claim about a method is worth more when the method is present and
    tested than when it is described.
    """
    if trials == 0:
        return ProportionInterval(scope, 0, 0, float("nan"), 0.0, 1.0, _confidence(z))

    p = successes / trials
    half = z * math.sqrt(p * (1 - p) / trials)
    return ProportionInterval(
        scope=scope,
        successes=successes,
        trials=trials,
        point=p,
        low=max(0.0, p - half),
        high=min(1.0, p + half),
        confidence=_confidence(z),
    )


def _confidence(z: float) -> float:
    """Round-trip the z back to a confidence level so the reported number is not a second literal
    that can drift away from the z it came from."""
    from scipy import stats

    return float(2 * stats.norm.cdf(z) - 1)
