"""Tests for required steering and the match against the human reference.

Two of these are structural rather than numerical: the report must carry no p-value, and no
function in the module may return one. FR-019 makes that a contract, and a contract nobody
tests is a comment.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from python.track import config, generator, matching, vehicle

PROFILE = vehicle.build_profile()


@pytest.fixture(scope="module")
def reference() -> np.ndarray:
    return matching.reference_distribution("track1")


# -----------------------------------------------------------------------------------------
# The three measured scales (research C15)
# -----------------------------------------------------------------------------------------


def test_the_reference_scores_zero_against_itself(reference):
    assert matching._wasserstein1(reference, reference) == pytest.approx(0.0, abs=1e-12)


def test_the_two_halves_of_the_reference_score_the_recorded_self_consistency(reference):
    half = len(reference) // 2
    distance = matching._wasserstein1(reference[:half], reference[half:])

    assert distance == pytest.approx(config.W1_SELF_CONSISTENCY, abs=0.0005)
    assert distance < config.MATCH_DISTANCE_THRESHOLD


def test_the_two_recordings_score_the_recorded_human_to_human_distance(reference):
    other = matching.reference_distribution("track2")
    distance = matching._wasserstein1(reference, other)

    assert distance == pytest.approx(config.W1_HUMAN_TO_HUMAN, abs=0.0005)


def test_a_structureless_uniform_scores_the_recorded_ceiling(reference):
    """A distribution with no structure at all must land on the ceiling scale.

    The recorded value was corrected from 0.1047 to 0.1142 on 2026-07-31. Recomputing from
    the definition C15 states gives 0.1142 under both this module and
    scipy.stats.wasserstein_distance, while the same pair reproduces the other two scales
    exactly. The support was ruled out as the cause: uniform on [0, 1] gives 0.2127 and an
    unconditional reference gives 0.3359.
    """
    uniform = np.linspace(0.0, PROFILE.max_required_steer, 20000)
    distance = matching._wasserstein1(reference, uniform)

    assert distance == pytest.approx(config.W1_STRUCTURELESS, abs=0.0005)
    assert distance > config.MATCH_DISTANCE_THRESHOLD


def test_the_threshold_sits_strictly_between_the_floor_and_the_ceiling():
    """The property that makes the threshold discriminate rather than rubber-stamp."""
    assert config.W1_SELF_CONSISTENCY < config.MATCH_DISTANCE_THRESHOLD
    assert config.MATCH_DISTANCE_THRESHOLD < config.W1_STRUCTURELESS


def test_the_distance_is_symmetric(reference):
    other = matching.reference_distribution("track2")

    assert matching._wasserstein1(reference, other) == pytest.approx(
        matching._wasserstein1(other, reference), abs=1e-9)


def test_a_shifted_distribution_moves_by_exactly_the_shift():
    """W1 between a distribution and a translate of it is the size of the translation.

    An identity the definition guarantees, so it checks the implementation against
    mathematics rather than against another number this project produced.
    """
    values = np.random.default_rng(0).uniform(0, 1, 5000)

    for shift in (0.05, 0.2, 0.5):
        assert matching._wasserstein1(values, values + shift) == pytest.approx(
            shift, abs=1e-3)


# -----------------------------------------------------------------------------------------
# No p-value, by contract (FR-019)
# -----------------------------------------------------------------------------------------


def test_the_report_type_has_no_p_value_field():
    fields = set(matching.MatchReport.__dataclass_fields__)

    for banned in ("p_value", "pvalue", "p", "significance", "alpha"):
        assert banned not in fields


def test_no_function_in_the_module_returns_a_p_value():
    """A distance is not a test statistic. Feature 002 exists because that was confused once."""
    source = inspect.getsource(matching)

    for banned in ("p_value", "pvalue", "ttest", "ks_2samp", "chisquare", "scipy.stats"):
        assert banned not in source, f"matching.py references {banned}"


def test_the_note_states_both_known_limitations():
    demand = matching.required_steering(generator.generate(1), PROFILE)
    report = matching.match_distance(demand, profile=PROFILE)

    note = report.note.lower()
    assert "max_required_steer" in note
    assert "straight" in note
    assert "not a hypothesis test" in note
    assert "no p-value" in note


def test_the_report_carries_the_three_scales_so_a_distance_is_readable():
    demand = matching.required_steering(generator.generate(1), PROFILE)
    report = matching.match_distance(demand)

    assert report.scales["self_consistency"] == config.W1_SELF_CONSISTENCY
    assert report.scales["structureless"] == config.W1_STRUCTURELESS
    assert report.scales["human_to_human"] == config.W1_HUMAN_TO_HUMAN
    assert report.threshold == config.MATCH_DISTANCE_THRESHOLD
    assert report.accepted == (report.distance <= report.threshold)


def test_the_report_names_the_conditional_reference():
    """Which distribution was used is part of the result, not an implementation detail."""
    report = matching.match_distance(
        matching.required_steering(generator.generate(1), PROFILE))

    assert "track1" in report.reference
    assert "conditional" in report.reference


# -----------------------------------------------------------------------------------------
# Required steering
# -----------------------------------------------------------------------------------------


def test_required_steering_never_exceeds_what_the_profile_permits():
    """If it did, the radius check failed and the seed should already have been rejected."""
    for seed in range(1, 15):
        line = generator.generate(seed)
        demand = matching.required_steering(line, PROFILE)

        if line.min_radius_m >= PROFILE.r_floor_m:
            assert demand.max_required <= PROFILE.max_required_steer + 1e-9, f"seed {seed}"


def test_required_steering_is_unsigned():
    demand = matching.required_steering(generator.generate(4), PROFILE)

    assert np.all(demand.required_steer >= 0)


def test_required_steering_matches_the_scalar_function_it_vectorises():
    """The array form and vehicle.steering_for_radius must not drift apart."""
    line = generator.generate(3)
    demand = matching.required_steering(line, PROFILE)

    for i in (0, 500, 1200, 1999):
        expected = vehicle.steering_for_radius(float(line.radius[i]), PROFILE)
        assert demand.required_steer[i] == pytest.approx(expected, rel=1e-9)


def test_a_tighter_corner_demands_more_steering():
    line = generator.generate(5)
    demand = matching.required_steering(line, PROFILE)

    tightest = int(np.argmin(line.radius))
    assert demand.required_steer[tightest] == pytest.approx(demand.max_required)


def test_percentiles_cover_the_ones_m1_reports():
    demand = matching.required_steering(generator.generate(6), PROFILE)

    assert set(demand.percentiles) == set(matching.PERCENTILES)
    values = [demand.percentiles[p] for p in sorted(demand.percentiles)]
    assert values == sorted(values)


# -----------------------------------------------------------------------------------------
# Descriptives, required by Principle IX
# -----------------------------------------------------------------------------------------


def test_every_demand_carries_all_six_descriptive_figures():
    demand = matching.required_steering(generator.generate(7), PROFILE)
    d = demand.descriptives

    assert d.n == config.SAMPLES_PER_TRACK
    assert d.mean > 0
    assert d.variance > 0
    assert d.std == pytest.approx(np.sqrt(d.variance))
    assert d.min <= d.mean <= d.max
    assert d.max == pytest.approx(demand.max_required)


def test_the_histogram_is_relative_frequency_and_sums_to_one():
    """Counts would not be comparable between a 2000-sample track and a 2193-sample reference."""
    demand = matching.required_steering(generator.generate(7), PROFILE)
    d = demand.descriptives

    assert d.relative_frequency.sum() == pytest.approx(1.0)
    assert np.all(d.relative_frequency >= 0)
    assert np.all(d.relative_frequency <= 1)
    assert len(d.bin_edges) == len(d.relative_frequency) + 1


def test_describe_refuses_an_empty_distribution():
    with pytest.raises(ValueError):
        matching.describe([])


def test_describe_matches_numpy_on_a_known_array():
    values = np.array([1.0, 2.0, 3.0, 4.0])
    d = matching.describe(values)

    assert d.n == 4
    assert d.mean == pytest.approx(2.5)
    assert d.variance == pytest.approx(1.25)  # population, ddof=0
    assert d.min == 1.0 and d.max == 4.0


# -----------------------------------------------------------------------------------------
# Pooling (SC-010)
# -----------------------------------------------------------------------------------------


def test_a_pooled_report_records_how_many_seeds_went_into_it():
    """SC-010 may not be quoted from a report with fewer than 20 seeds pooled."""
    pooled = np.concatenate([
        matching.required_steering(generator.generate(s), PROFILE).required_steer
        for s in range(1, 21)])

    report = matching.match_distance(pooled, scope="train", n_seeds_pooled=20)

    assert report.n_seeds_pooled == 20
    assert report.scope == "train"
    assert report.n_track_samples == 20 * config.SAMPLES_PER_TRACK


def test_a_single_seed_report_says_so():
    report = matching.match_distance(
        matching.required_steering(generator.generate(9), PROFILE))

    assert report.n_seeds_pooled == 1
    assert "seed 9" in report.scope


# -----------------------------------------------------------------------------------------
# The bound SC-010 is judged on, after the 2026-07-31 revision
# -----------------------------------------------------------------------------------------


def test_a_pooled_batch_is_bounded_above_by_the_human_recording(reference):
    """SC-010 as revised: the track never demands more than a human was recorded supplying."""
    pooled = np.concatenate([
        matching.required_steering(generator.generate(s), PROFILE).required_steer
        for s in config.TRAIN_SEEDS])

    bound = matching.demand_bound(pooled, reference, scope="train",
                                  n_seeds_pooled=len(config.TRAIN_SEEDS))

    assert bound.within_bound is True
    assert bound.worst_percentile is None
    assert bound.exceedance_fraction == 0.0
    assert bound.max_required < bound.reference_max
    assert bound.n_seeds_pooled >= 20


def test_every_percentile_gap_is_negative_for_a_generated_batch(reference):
    """The gap must not merely be non-positive on average, but at every reported percentile."""
    pooled = np.concatenate([
        matching.required_steering(generator.generate(s), PROFILE).required_steer
        for s in config.TRAIN_SEEDS])

    bound = matching.demand_bound(pooled, reference)

    for p, gap in bound.percentile_gaps.items():
        assert gap <= 0.0, f"track demands {gap:+.3f} more than the human at P{p:g}"


def test_a_demand_above_the_human_maximum_fails_the_bound(reference):
    """The direction that must fail, or the check would approve anything."""
    too_much = np.full(1000, float(np.max(reference)) + 0.05)

    bound = matching.demand_bound(too_much, reference)

    assert bound.within_bound is False
    assert bound.exceedance_fraction == 1.0
    assert bound.worst_percentile is not None


def test_a_single_impossible_corner_fails_even_when_the_shape_is_fine(reference):
    """A distribution can sit under the human curve everywhere and still be unusable.

    One corner tighter than anything a human faced is exactly what an agent trained on that
    human's data would fail, so the bound cannot be a percentile check alone.
    """
    pooled = matching.required_steering(generator.generate(1), PROFILE).required_steer
    spiked = np.concatenate([pooled, [float(np.max(reference)) + 0.2]])

    assert matching.demand_bound(pooled, reference).within_bound is True
    assert matching.demand_bound(spiked, reference).within_bound is False


def test_the_bound_checks_only_the_upper_percentiles(reference):
    """A loop with no straights sits ABOVE a human at the bottom, by construction.

    Seed 1 demands about 0.28 at P5 against a human 0.05, because it is turning everywhere
    while the human's P5 is a small correction on a straight. Checking low percentiles would
    fail a track for a property research C9 already accepts, so the bound is an upper-tail
    statement only. Pinned here because widening it back would look like a harmless tidy-up.
    """
    assert min(matching.BOUND_PERCENTILES) >= 50.0

    single = matching.required_steering(generator.generate(1), PROFILE).required_steer
    assert np.percentile(single, 5) > np.percentile(reference, 5)

    assert matching.demand_bound(single, reference).within_bound is True


def test_the_bound_note_explains_why_it_is_not_a_distribution_match():
    bound = matching.demand_bound(
        matching.required_steering(generator.generate(1), PROFILE))

    note = bound.note.lower()
    assert "geometric minimum" in note
    assert "actually applied" in note
    assert "no p-value" in note


def test_the_bound_type_has_no_p_value_field():
    fields = set(matching.DemandBound.__dataclass_fields__)

    for banned in ("p_value", "pvalue", "significance", "alpha"):
        assert banned not in fields


def test_the_distance_is_still_reported_as_a_diagnostic(reference):
    """match_distance stays, and stays honest: it is no longer the SC-010 gate.

    Pinned at its measured value so a change in the generator shows up here rather than
    passing unnoticed.
    """
    pooled = np.concatenate([
        matching.required_steering(generator.generate(s), PROFILE).required_steer
        for s in config.TRAIN_SEEDS])

    report = matching.match_distance(pooled, reference, scope="train", n_seeds_pooled=40)

    assert report.distance == pytest.approx(0.0930, abs=0.001)
    assert report.accepted is False
    assert report.distance < config.W1_STRUCTURELESS


def test_the_reference_is_read_only(reference):
    """This module must never write to the dataset or to results."""
    source = inspect.getsource(matching)

    for banned in ("to_csv", "write_text", "open(", "savefig", "mkdir"):
        assert banned not in source, f"matching.py performs a write: {banned}"

    assert len(reference) == 2193
