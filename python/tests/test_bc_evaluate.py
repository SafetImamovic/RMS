"""The comparison artifacts, and the guards that stop them meaning the wrong thing.

Three failures this file exists to catch, all of which produce a confident number rather than
an error:

- a checkpoint scored against a split it was not trained on,
- two runs differing in more than the balancing policy, with the difference then attributed to
  balancing,
- a distribution reported pooled only, on a dataset where pooling is already known to hide the
  difference between the two tracks.

`summarise` is also cross-checked against `eda.stats` directly, which is how the "this module
computes no statistic of its own" rule in research R5 is verified rather than asserted.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip(
    "torch", reason="evaluation loads a checkpoint, so it needs torch; run this under .venv-bc"
)

from python.bc import config, evaluate, train  # noqa: E402
from python.bc.dataset import BalancingPolicy  # noqa: E402
from python.eda import config as eda_config  # noqa: E402
from python.eda import stats  # noqa: E402


@pytest.fixture
def predictions() -> evaluate.PredictionSet:
    """A small set spanning both tracks, with deliberately non-contiguous row indices."""
    order = [10, 11, 12, 13, 500, 501, 502, 503]
    return evaluate.PredictionSet(
        run_id="bc_test_v01",
        order=order,
        predicted=np.array([0.0, 0.1, 0.2, 0.15, -0.3, -0.25, -0.2, 0.05]),
        actual=np.array([0.0, 0.05, 0.25, 0.15, -0.35, -0.25, -0.15, 0.0]),
        track=np.array(["track1data"] * 4 + ["track2data"] * 4),
    )


def a_record(**overrides) -> train.RunRecord:
    fields = dict(
        run_id="bc_unbalanced_v01",
        policy=BalancingPolicy.NONE.value,
        seed=config.SEED,
        split_digest="a" * 64,
        device="cpu",
        hyperparameters={"learning_rate": config.LEARNING_RATE, "batch_size": 64},
        n_train_samples=77_871,
        n_val_samples=5_576,
        duration_s=100.0,
        epochs_completed=10,
        val_error=0.05,
        baseline_error=0.09,
        parameter_count=252_219,
    )
    fields.update(overrides)
    return train.RunRecord(**fields)


# -----------------------------------------------------------------------------------------
# The lattice. DESIGN section 7.
# -----------------------------------------------------------------------------------------


def test_the_lattice_is_exactly_the_41_levels_feature_002_measured():
    """Set equality, not a count. A grid with the right size and the wrong offset would pass
    a count check and would silently move every quantised prediction.
    """
    levels = evaluate.lattice_levels()
    expected = {round(-1.0 + i * config.STEERING_LATTICE_STEP, 4) for i in range(41)}

    assert len(levels) == 41
    assert set(np.round(levels, 4)) == expected


def test_quantising_maps_onto_the_lattice_and_nowhere_else():
    rng = np.random.default_rng(config.SEED)
    values = rng.uniform(-1.5, 1.5, size=5000)

    snapped = evaluate.quantise_to_lattice(values)

    assert set(np.round(snapped, 4)).issubset(set(np.round(evaluate.lattice_levels(), 4)))


def test_quantising_clips_rather_than_wrapping():
    snapped = evaluate.quantise_to_lattice([-4.0, 4.0])

    assert snapped[0] == pytest.approx(-1.0)
    assert snapped[1] == pytest.approx(1.0)


def test_quantising_does_not_produce_negative_zero():
    """They compare equal, but a histogram listing both -0.00 and 0.00 invites the wrong
    question about which bin the real zeros are in.
    """
    snapped = evaluate.quantise_to_lattice([-0.001, -0.02])

    assert not np.signbit(snapped).any()


# -----------------------------------------------------------------------------------------
# The divergence
# -----------------------------------------------------------------------------------------


def test_a_distribution_has_no_divergence_from_itself():
    rng = np.random.default_rng(config.SEED)
    values = rng.choice(evaluate.lattice_levels(), size=2000)

    assert evaluate.kl_divergence(values, values) == pytest.approx(0.0, abs=1e-9)


def test_a_shifted_distribution_is_further_away_than_an_unshifted_one():
    rng = np.random.default_rng(config.SEED)
    human = rng.choice(evaluate.lattice_levels(), size=2000)
    near = np.clip(human + 0.05, -1.0, 1.0)
    far = np.clip(human + 0.5, -1.0, 1.0)

    assert evaluate.kl_divergence(near, human) < evaluate.kl_divergence(far, human)


def test_the_divergence_stays_finite_when_the_model_uses_an_unseen_level():
    """The reason `KL_SMOOTHING` exists.

    Unsmoothed, one prediction on a level the human never used makes this infinite, which
    reports "completely different" on the strength of a single frame.
    """
    human = np.zeros(1000)
    predicted = np.concatenate([np.zeros(999), [1.0]])

    assert np.isfinite(evaluate.kl_divergence(predicted, human))


def test_the_lattice_distribution_sums_to_one():
    rng = np.random.default_rng(config.SEED)
    values = rng.uniform(-1.0, 1.0, size=3000)

    assert evaluate.lattice_distribution(values).sum() == pytest.approx(1.0)


# -----------------------------------------------------------------------------------------
# Reports. SC-004 and FR-016.
# -----------------------------------------------------------------------------------------


def test_relative_frequencies_sum_to_one(predictions):
    """SC-004."""
    for report in evaluate.report_run(predictions):
        assert report.histogram_relative.sum() == pytest.approx(1.0), report.name


def test_every_distribution_appears_in_all_three_scopes(predictions):
    """FR-016. Feature 002 already found a column that looked fine pooled and was constant
    within each track, and steering carries the same trap.
    """
    reports = evaluate.report_run(predictions)
    by_name: dict[str, set[str]] = {}
    for report in reports:
        by_name.setdefault(report.name, set()).add(report.scope)

    assert by_name, "no reports were produced"
    for name, scopes in by_name.items():
        assert scopes == {"pooled", *eda_config.SESSION_PATH_MARKERS}, name


def test_a_missing_track_is_refused_rather_than_reported_pooled(predictions):
    one_track = evaluate.PredictionSet(
        run_id=predictions.run_id,
        order=predictions.order[:4],
        predicted=predictions.predicted[:4],
        actual=predictions.actual[:4],
        track=np.array(["track1data"] * 4),
    )

    with pytest.raises(evaluate.EvaluationError, match="track2data"):
        evaluate.report_run(one_track)


def test_summarise_delegates_to_the_shared_statistics(predictions):
    """Research R5, verified rather than asserted.

    If this module computed its own mean, BC's figures and M1's could drift apart in definition
    while both looked correct, and the M5 comparison would be between two different questions.
    """
    values = predictions.predicted
    report = evaluate.summarise(values, "predicted_steering", "pooled")
    direct = stats.describe(values, variable="whatever")

    assert report.summary.mean == direct.mean
    assert report.summary.std == direct.std
    assert report.summary.variance == direct.variance
    assert report.summary.minimum == direct.minimum
    assert report.summary.maximum == direct.maximum
    assert report.summary.n == direct.n


def test_the_lattice_flag_is_never_left_implicit(predictions):
    reports = {(r.name, r.scope): r for r in evaluate.report_run(predictions)}

    assert reports[("predicted_steering", "pooled")].lattice_applied is False
    assert reports[("predicted_steering_lattice", "pooled")].lattice_applied is True
    assert reports[("human_steering", "pooled")].lattice_applied is False


def test_an_empty_distribution_is_refused():
    with pytest.raises(evaluate.EvaluationError, match="empty"):
        evaluate.summarise(np.array([]), "predicted_steering", "pooled")


# -----------------------------------------------------------------------------------------
# Residuals and smoothness
# -----------------------------------------------------------------------------------------


def test_residuals_are_derived_rather_than_stored(predictions):
    assert np.allclose(predictions.residual, predictions.predicted - predictions.actual)


def test_frame_to_frame_change_does_not_difference_across_a_block_boundary():
    """FR-015. The validation set is two held-out blocks per track, so its rows are not one
    continuous stretch. Differencing straight through invents a jump at every edge, and the
    smoothness figure would then describe the invented jumps.
    """
    order = [10, 11, 12, 500, 501]
    values = np.array([0.0, 0.1, 0.3, 1.0, 0.5])

    change = evaluate.absolute_frame_to_frame_change(values, order)

    # Within the runs: 0.1, 0.2 and 0.5. The 0.7 jump from 0.3 to 1.0 is not a real neighbour.
    assert np.allclose(change, [0.1, 0.2, 0.5])
    assert 0.7 not in change


def test_a_single_frame_run_contributes_no_change():
    change = evaluate.absolute_frame_to_frame_change(np.array([0.5]), [10])

    assert change.size == 0


# -----------------------------------------------------------------------------------------
# The comparison. FR-021.
# -----------------------------------------------------------------------------------------


def test_two_runs_differing_only_in_policy_compare():
    balanced = a_record(run_id="bc_balanced_v01",
                        policy=BalancingPolicy.DOWNSAMPLE_ZERO.value,
                        n_train_samples=66_783, val_error=0.04)
    unbalanced = a_record()

    comparison = evaluate.compare_runs(balanced, unbalanced, 0.10, 0.15)

    assert comparison.same_split is True
    assert set(comparison.differing_fields) == {"policy", "n_train_samples"}
    assert comparison.accuracy_delta == pytest.approx(0.04 - 0.05)
    assert comparison.distribution_delta == pytest.approx(0.10 - 0.15)


def test_two_runs_differing_in_learning_rate_are_refused_and_the_field_is_named():
    """The test that keeps the headline comparison honest.

    Two runs that also differ in learning rate still produce a difference, and that difference
    gets read as the cost of balancing by whoever sees the table.
    """
    balanced = a_record(run_id="bc_balanced_v01",
                        policy=BalancingPolicy.DOWNSAMPLE_ZERO.value,
                        n_train_samples=66_783,
                        hyperparameters={"learning_rate": 0.5, "batch_size": 64})
    unbalanced = a_record()

    with pytest.raises(evaluate.EvaluationError, match="hyperparameters.learning_rate"):
        evaluate.compare_runs(balanced, unbalanced, 0.1, 0.1)


def test_two_runs_on_different_splits_are_refused():
    balanced = a_record(run_id="bc_balanced_v01",
                        policy=BalancingPolicy.DOWNSAMPLE_ZERO.value,
                        n_train_samples=66_783, split_digest="b" * 64)
    unbalanced = a_record()

    with pytest.raises(evaluate.EvaluationError, match="different splits"):
        evaluate.compare_runs(balanced, unbalanced, 0.1, 0.1)


def test_two_runs_with_different_seeds_are_refused():
    balanced = a_record(run_id="bc_balanced_v01",
                        policy=BalancingPolicy.DOWNSAMPLE_ZERO.value,
                        n_train_samples=66_783, seed=config.SEED + 1)
    unbalanced = a_record()

    with pytest.raises(evaluate.EvaluationError, match="seed"):
        evaluate.compare_runs(balanced, unbalanced, 0.1, 0.1)


def test_a_differing_validation_count_is_refused(predictions):
    """FR-022: both runs are scored on the same unbalanced validation set. A different count
    means one of them was scored on a different yardstick.
    """
    balanced = a_record(run_id="bc_balanced_v01",
                        policy=BalancingPolicy.DOWNSAMPLE_ZERO.value,
                        n_train_samples=66_783, n_val_samples=5_000)
    unbalanced = a_record()

    with pytest.raises(evaluate.EvaluationError, match="n_val_samples"):
        evaluate.compare_runs(balanced, unbalanced, 0.1, 0.1)


def test_the_comparison_reports_both_deltas_without_a_verdict():
    """A run that wins one axis and loses the other is the expected outcome and is the finding.

    Asserted on the rendered text, because the temptation to collapse it lives in the writing
    rather than in the data structure.
    """
    balanced = a_record(run_id="bc_balanced_v01",
                        policy=BalancingPolicy.DOWNSAMPLE_ZERO.value,
                        n_train_samples=66_783, val_error=0.04)
    unbalanced = a_record()

    comparison = evaluate.compare_runs(balanced, unbalanced, 0.20, 0.15)
    rendered = evaluate.render_comparison(comparison, 0.20, 0.15)

    assert "Accuracy" in rendered
    assert "Distribution" in rendered
    assert "not combined into a verdict" in rendered
    # Balanced wins accuracy and loses distribution here, which must both be visible.
    assert f"{comparison.accuracy_delta:+.6f}" in rendered
    assert f"{comparison.distribution_delta:+.6f}" in rendered
