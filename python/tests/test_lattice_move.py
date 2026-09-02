"""The lattice helpers moved from `python.bc.evaluate` to `python.eda.lattice` in feature 010.

**Why the move happened.** M5 compares four drivers on the human steering lattice, and its
comparison runs under `.venv`, which has no torch. `python.bc.evaluate` imports the model and the
trainer, so it cannot be imported there at all. The arithmetic itself never needed torch.

**What these tests are for.** A move is only safe if it is a move. They pin that the new module
agrees with feature 002's published measurement of the lattice, that the delegating names in
`python.bc.evaluate` still return the same values, and that the new module is importable without
torch, which was the entire point.
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from python.bc import config
from python.eda import lattice

HAS_TORCH = importlib.util.find_spec("torch") is not None


def test_the_module_imports_without_torch() -> None:
    """The reason the move happened. If this ever needs torch again, M5 cannot run."""
    import python.eda.lattice as module

    assert module is lattice


def test_the_lattice_matches_feature_002s_measurement() -> None:
    """41 support points, step 0.05, -1.0 to +1.0, as measured in `authenticity_stats.json`."""
    support = lattice.levels()

    assert support.size == 41
    assert support[0] == pytest.approx(-1.0)
    assert support[-1] == pytest.approx(1.0)
    steps = np.diff(support)
    assert np.allclose(steps, config.STEERING_LATTICE_STEP)


def test_quantise_snaps_to_the_nearest_level_and_clips() -> None:
    values = np.array([0.0, 0.024, 0.026, -0.049, 1.4, -1.4])
    snapped = lattice.quantise(values)

    assert snapped[0] == pytest.approx(0.0)
    assert snapped[1] == pytest.approx(0.0)
    assert snapped[2] == pytest.approx(0.05)
    assert snapped[3] == pytest.approx(-0.05)
    assert snapped[4] == pytest.approx(1.0), "must clip to the steering limits"
    assert snapped[5] == pytest.approx(-1.0)


def test_quantise_never_returns_negative_zero() -> None:
    """A histogram listing both -0.00 and 0.00 invites the reader to ask which holds the real zeros."""
    snapped = lattice.quantise(np.array([-0.0, -0.001, -0.01]))
    assert not np.signbit(snapped).any()


def test_distribution_sums_to_one_and_is_in_level_order() -> None:
    values = np.array([0.0, 0.0, 0.05, -0.05, 1.0])
    dist = lattice.distribution(values)

    assert dist.size == 41
    assert dist.sum() == pytest.approx(1.0)
    # index 20 is the zero level on a 41 point lattice from -1 to +1
    assert dist[20] == pytest.approx(2 / 5)
    assert dist[-1] == pytest.approx(1 / 5)


def test_kl_of_a_distribution_from_itself_is_zero() -> None:
    rng = np.random.default_rng(19)
    sample = rng.normal(0.0, 0.3, 4000)

    assert lattice.kl_divergence(sample, sample) == pytest.approx(0.0, abs=1e-12)


def test_kl_is_finite_when_a_level_is_unused_by_the_reference() -> None:
    """Track1 never produces 0.95, so an unsmoothed KL would be infinite. Not hypothetical."""
    reference = np.array([0.0] * 100)
    candidate = np.array([0.95] * 100)

    value = lattice.kl_divergence(candidate, reference)

    assert np.isfinite(value)
    assert value > 0.0


def test_smoothing_is_what_keeps_it_finite() -> None:
    reference = np.array([0.0] * 100)
    candidate = np.array([0.95] * 100)

    assert not np.isfinite(lattice.kl_divergence(candidate, reference, smoothing=0.0))


@pytest.mark.skipif(not HAS_TORCH, reason="python.bc.evaluate needs torch to import")
def test_the_old_names_still_return_the_same_values() -> None:
    """The move must be invisible to M4's callers. Run under `.venv-bc`, skipped under `.venv`."""
    from python.bc import evaluate

    rng = np.random.default_rng(23)
    sample = rng.normal(0.0, 0.4, 2000)
    human = rng.normal(0.0, 0.2, 2000)

    assert np.array_equal(evaluate.lattice_levels(), lattice.levels())
    assert np.array_equal(evaluate.quantise_to_lattice(sample), lattice.quantise(sample))
    assert np.array_equal(evaluate.lattice_distribution(sample), lattice.distribution(sample))
    assert evaluate.kl_divergence(sample, human) == pytest.approx(
        lattice.kl_divergence(sample, human)
    )
