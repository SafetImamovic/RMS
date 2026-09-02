"""The two-sample KS test M5 compares drivers with.

`DESIGN.md` 7.1 names it and nothing in the repository implemented it before this feature. These
tests pin the three properties M5 relies on: that it does not reject when it should not, that it
does when it should, and that it separates a significant difference from a large one. The third is
the one that matters, because M5 compares roughly 31,000 agent samples against 32,000 human ones
and at that size a p-value alone is close to a formality.
"""

from __future__ import annotations

import numpy as np
import pytest

from python.eda.authenticity import ks_two_sample


def test_identical_distributions_do_not_reject() -> None:
    rng = np.random.default_rng(7)
    a = rng.normal(0.0, 1.0, 5000)
    b = rng.normal(0.0, 1.0, 5000)

    result = ks_two_sample(a, b, label_a="a", label_b="b")

    assert not result.reject_null
    assert result.p_value > result.alpha
    assert not result.effect_is_material


def test_shifted_distributions_reject_and_are_material() -> None:
    rng = np.random.default_rng(7)
    a = rng.normal(0.0, 1.0, 5000)
    b = rng.normal(0.8, 1.0, 5000)

    result = ks_two_sample(a, b, label_a="a", label_b="b")

    assert result.reject_null
    assert result.p_value < result.alpha
    assert result.effect_is_material
    assert result.statistic > 0.25


def test_the_p_value_is_returned_not_only_the_decision() -> None:
    """SC-003 asks for the p-value to be reported, so it has to survive the return."""
    rng = np.random.default_rng(11)
    result = ks_two_sample(rng.normal(size=400), rng.normal(size=400))

    assert 0.0 <= result.p_value <= 1.0
    assert result.n_a == 400 and result.n_b == 400


def test_a_tiny_difference_on_a_huge_sample_rejects_without_being_material() -> None:
    """The whole reason effect size is reported beside the p-value (T026).

    A shift far too small to matter is still detected at M5's sample sizes. The test must say
    "significant but not material" rather than "different", because the second would be read as a
    finding about driving.
    """
    rng = np.random.default_rng(3)
    a = rng.normal(0.0, 1.0, 60000)
    b = rng.normal(0.03, 1.0, 60000)

    result = ks_two_sample(a, b, label_a="a", label_b="b")

    assert result.reject_null, "expected a rejection at this sample size"
    assert not result.effect_is_material, f"D={result.statistic} should be below the threshold"
    assert "NIJE materijalna" in result.interpretation


def test_effect_size_is_the_statistic_and_is_sample_size_independent() -> None:
    """The KS statistic is the largest gap between the two empirical CDFs, on 0 to 1.

    Pinned because the report prints `effect_size`, and if it ever diverged from `statistic` the
    two numbers would disagree on the page with no way to tell which was right.
    """
    rng = np.random.default_rng(5)
    small = ks_two_sample(rng.normal(size=2000), rng.normal(1.0, 1.0, 2000))
    large = ks_two_sample(rng.normal(size=40000), rng.normal(1.0, 1.0, 40000))

    assert small.effect_size == small.statistic
    assert large.effect_size == large.statistic
    # Same underlying difference, twenty times the data: the statistic is stable, the p-value is not.
    assert abs(small.statistic - large.statistic) < 0.05
    assert large.p_value < small.p_value


def test_empty_sample_raises_rather_than_returning_a_number() -> None:
    with pytest.raises(ValueError):
        ks_two_sample([], [1.0, 2.0])


def test_non_finite_values_are_dropped_before_the_test() -> None:
    rng = np.random.default_rng(13)
    clean = rng.normal(size=1000)
    dirty = np.concatenate([clean, [np.nan, np.inf, -np.inf]])

    result = ks_two_sample(dirty, clean)

    assert result.n_a == 1000, "the three non-finite values should not be counted"
    assert not result.reject_null
