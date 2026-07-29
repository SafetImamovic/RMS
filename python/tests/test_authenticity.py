"""Tests for the hypothesis tests and verdicts (feature 002, US2 + US3).

These run on samples crafted so the answer is known by construction - if a test cannot get
the right answer on data we built ourselves, its verdict on the real dataset is worthless.

Both directions again: each test must reject when the null is false, and must NOT reject
when the null is true.
"""

from __future__ import annotations

import numpy as np
import pytest

from python.eda import config
from python.eda.authenticity import (
    Verdict,
    chi2_homogeneity,
    chi2_symmetry,
    chi2_uniform_gof,
    pool_symmetric,
)

# The real steering lattice: 0.05 spacing from -1.0 to +1.0, 41 support points.
SUPPORT = np.round(np.arange(-1.0, 1.0 + 1e-9, 0.05), 10)


def _triangular(peak: float = 400.0, floor: float = 20.0) -> np.ndarray:
    """A symmetric, centre-heavy count vector - the shape real steering roughly has."""
    k = len(SUPPORT)
    centre = (k - 1) / 2
    weights = 1.0 - np.abs(np.arange(k) - centre) / centre
    return np.round(floor + (peak - floor) * weights)


# =======================================================================================
# T014 - pooling
# =======================================================================================
def test_pooling_leaves_a_healthy_table_alone():
    observed = np.full(len(SUPPORT), 100.0)
    expected = np.full(len(SUPPORT), 100.0)

    obs_p, exp_p, n_pooled = pool_symmetric(observed, expected, config.CHI2_MIN_EXPECTED_PER_BIN)

    assert n_pooled == 0
    assert len(obs_p) == len(SUPPORT)


def test_pooling_merges_sparse_tails_and_reports_how_many():
    observed = _triangular()
    expected = observed.copy()
    # Starve the outermost four levels on each side.
    expected[:4] = 1.0
    expected[-4:] = 1.0
    observed[:4] = 1.0
    observed[-4:] = 1.0

    obs_p, exp_p, n_pooled = pool_symmetric(observed, expected, config.CHI2_MIN_EXPECTED_PER_BIN)

    assert n_pooled > 0
    assert len(obs_p) == len(SUPPORT) - n_pooled
    assert (exp_p >= config.CHI2_MIN_EXPECTED_PER_BIN).all()
    # Nothing may be lost or invented by pooling.
    assert obs_p.sum() == pytest.approx(observed.sum())
    assert exp_p.sum() == pytest.approx(expected.sum())


def test_pooling_cannot_induce_asymmetry_in_a_symmetric_input():
    """The reason pooling is symmetric at all (research A5).

    If pooling merged the tails at different depths, the symmetry test would be measuring
    its own preprocessing rather than the data.
    """
    observed = _triangular()
    observed[:5] = 1.0
    observed[-5:] = 1.0
    expected = observed.copy()

    obs_p, exp_p, _ = pool_symmetric(observed, expected, config.CHI2_MIN_EXPECTED_PER_BIN)

    assert np.allclose(obs_p, obs_p[::-1])
    assert np.allclose(exp_p, exp_p[::-1])


# =======================================================================================
# T013 - the three chi-square tests, on data whose answer we know
# =======================================================================================
def test_uniform_sample_does_not_reject_uniformity():
    """T1's null is TRUE here, so it must survive.

    This is the direction that matters for tampering: if someone had generated the steering
    column with a random number generator, this is what it would look like - and the test
    would fail to reject, which is the alarm.
    """
    counts = np.full(len(SUPPORT), 200.0)
    res = chi2_uniform_gof(counts, SUPPORT)

    assert res.reject_null is False
    assert res.null_hypothesis
    assert res.interpretation
    # The interpretation must name the tampering mechanism this test guards against, not
    # merely report a decision. (Report prose is Bosnian, as in M1.)
    assert "generator" in res.interpretation.lower()


def test_structured_sample_rejects_uniformity():
    res = chi2_uniform_gof(_triangular(), SUPPORT)

    assert res.reject_null is True
    assert res.statistic > res.critical_value


def test_reported_dof_is_the_post_pooling_value():
    """Never the naive k-1. Pooling removes categories, and the dof must follow.

    Homogeneity is the test that shows this: its expected counts follow the column totals,
    so starving the tails really does drop them below the validity threshold. (Under a
    uniform null every expected count is n/k, so a large sample never pools at all - which
    is itself worth knowing.)
    """
    counts_a = _triangular()
    counts_b = _triangular()
    for counts in (counts_a, counts_b):
        counts[:4] = 1.0
        counts[-4:] = 1.0

    res = chi2_homogeneity(counts_a, counts_b, SUPPORT)

    naive_dof = len(SUPPORT) - 1
    assert res.n_categories_pooled > 0
    assert res.dof == naive_dof - res.n_categories_pooled
    assert res.dof < naive_dof


def test_symmetric_sample_does_not_reject_symmetry():
    res = chi2_symmetry(_triangular(), SUPPORT)

    assert res.reject_null is False
    assert res.null_hypothesis


def test_strongly_skewed_sample_rejects_symmetry():
    counts = _triangular()
    negatives = SUPPORT < 0
    counts[negatives] = counts[negatives] * 5.0  # a left-biased loop, exaggerated

    res = chi2_symmetry(counts, SUPPORT)

    assert res.reject_null is True


def test_two_samples_from_one_distribution_do_not_reject_homogeneity():
    """T3's null is TRUE here.

    On the real data this is the direction that would be alarming: if the two 'tracks' were
    one recording copied and renamed to inflate the dataset, the test would fail to reject.
    """
    rng = np.random.default_rng(config.SEED)
    shape = _triangular()
    probabilities = shape / shape.sum()
    counts_a = rng.multinomial(20_000, probabilities).astype(float)
    counts_b = rng.multinomial(20_000, probabilities).astype(float)

    res = chi2_homogeneity(counts_a, counts_b, SUPPORT)

    assert res.reject_null is False
    assert "iskopiran" in res.interpretation.lower()
    assert "preimenovan" in res.interpretation.lower()


def test_two_different_distributions_reject_homogeneity():
    counts_a = _triangular()
    counts_b = _triangular()
    counts_b[SUPPORT < 0] *= 4.0

    res = chi2_homogeneity(counts_a, counts_b, SUPPORT)

    assert res.reject_null is True


def test_support_point_seen_on_only_one_track_is_retained():
    """A level observed on one track and not the other stays in the shared support, with
    an observed count of zero. Dropping it would quietly shrink the comparison."""
    counts_a = _triangular()
    counts_b = _triangular()
    counts_b[3] = 0.0

    res = chi2_homogeneity(counts_a, counts_b, SUPPORT)

    assert res.dof == len(SUPPORT) - 1 - res.n_categories_pooled


def test_every_result_states_its_null_and_its_meaning():
    """A bare statistic is a contract violation - no finding may be a naked number."""
    counts = _triangular()
    for res in (
        chi2_uniform_gof(counts, SUPPORT),
        chi2_symmetry(counts, SUPPORT),
        chi2_homogeneity(counts, counts, SUPPORT),
    ):
        assert res.null_hypothesis.strip()
        assert res.interpretation.strip()
        assert res.dof >= 1
        assert res.alpha == config.ALPHA
        assert 0.0 <= res.p_value <= 1.0


# =======================================================================================
# T022 - verdicts
# =======================================================================================
def test_explainable_verdict_without_a_mechanism_is_impossible():
    """An 'explainable' verdict with no named cause is just an assertion (FR-015)."""
    with pytest.raises(ValueError):
        Verdict(
            finding_id="f1",
            summary="track1 brake never leaves zero",
            classification="explainable",
            mechanism=None,
        )


def test_a_consequence_without_a_mitigation_is_impossible():
    """If a finding still bites a later milestone, saying so without saying what to do
    about it leaves the reader worse off than silence (FR-016)."""
    with pytest.raises(ValueError):
        Verdict(
            finding_id="f2",
            summary="track1 steers left 5.4x more often than right",
            classification="explainable",
            mechanism="closed loop driven anticlockwise",
            downstream_consequence="a BC model trained on track1 pulls left on straights",
            mitigation=None,
        )


def test_a_well_formed_verdict_is_accepted():
    verdict = Verdict(
        finding_id="f3",
        summary="track1 steers left more often than right",
        classification="explainable",
        mechanism="closed loop driven anticlockwise",
        downstream_consequence="a BC model trained on track1 pulls left on straights",
        mitigation="horizontal flip with sign-flipped steering",
    )

    assert verdict.classification == "explainable"


def test_unexplained_verdict_needs_no_mechanism():
    verdict = Verdict(
        finding_id="f4",
        summary="17 steering values sit off the lattice",
        classification="unexplained",
    )

    assert verdict.mechanism is None
