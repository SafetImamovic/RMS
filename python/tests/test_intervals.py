"""The Wilson interval, and the case the normal approximation gets wrong.

Research R6 worked three rows by hand before any result existed. These pin them, so a later
rewrite that quietly changed the method would be caught by the numbers the feature was planned on
rather than by a reader noticing the intervals looked different.
"""

from __future__ import annotations

import pytest

from python.eda.intervals import wald, wilson


def test_ten_perfect_runs_do_not_prove_certainty() -> None:
    """The whole reason this module exists. M3 was closed on runs like these."""
    interval = wilson(10, 10)

    assert interval.point == 1.0
    assert interval.high == pytest.approx(1.0, abs=1e-9)
    assert interval.low == pytest.approx(0.72, abs=0.01)


def test_the_normal_approximation_claims_certainty_on_the_same_data() -> None:
    """Not a hypothetical objection: it reports a zero-width interval at a point estimate of 1."""
    interval = wald(10, 10)

    assert interval.low == 1.0 and interval.high == 1.0
    assert interval.width == 0.0


def test_more_runs_narrow_the_interval_without_ever_closing_it() -> None:
    ten = wilson(10, 10)
    thirty_four = wilson(34, 34)

    assert thirty_four.low == pytest.approx(0.90, abs=0.01)
    assert thirty_four.low > ten.low, "34 perfect runs must say more than 10"
    assert thirty_four.width > 0.0


def test_three_failures_in_thirty_four_still_overlap_a_perfect_ten() -> None:
    """R6's third row, and the reason the comparison is made against intervals.

    A drop from 10 of 10 to 31 of 34 looks like a nine-point fall. It is not evidence of one.
    """
    perfect_ten = wilson(10, 10, scope="held out")
    imperfect = wilson(31, 34, scope="generalisation")

    assert imperfect.low == pytest.approx(0.77, abs=0.01)
    assert imperfect.high == pytest.approx(0.97, abs=0.01)
    assert imperfect.overlaps(perfect_ten)
    assert perfect_ten.overlaps(imperfect), "overlap must be symmetric"


def test_a_real_separation_is_reported_as_one() -> None:
    """The guard against the previous test's rule swallowing every difference."""
    good = wilson(34, 34)
    bad = wilson(12, 34)

    assert not good.overlaps(bad)


def test_the_interval_stays_inside_the_unit_interval_at_both_ends() -> None:
    for successes, trials in ((0, 5), (5, 5), (0, 1), (1, 1)):
        interval = wilson(successes, trials)
        assert 0.0 <= interval.low <= interval.high <= 1.0


def test_no_trials_returns_the_whole_range_rather_than_a_rate() -> None:
    """Printing a rate for an empty set is worse than printing nothing."""
    interval = wilson(0, 0)

    assert (interval.low, interval.high) == (0.0, 1.0)
    assert interval.point != interval.point, "the point estimate of nothing is nan"


def test_an_impossible_count_is_refused() -> None:
    with pytest.raises(ValueError):
        wilson(11, 10)
    with pytest.raises(ValueError):
        wilson(-1, 10)


def test_the_confidence_level_is_derived_from_the_z_it_was_computed_with() -> None:
    """Two literals that must agree are one literal too many."""
    assert wilson(5, 10).confidence == pytest.approx(0.95, abs=1e-6)
    assert wilson(5, 10, z=2.5758293035489004).confidence == pytest.approx(0.99, abs=1e-6)


def test_the_string_form_carries_the_interval_and_not_only_the_rate() -> None:
    assert str(wilson(34, 34)) == "34/34 = 100.0% [89.8, 100.0]"
