"""Tests for python/eda/stats.py (US2)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from python.eda.loader import TrackDataset
from python.eda.stats import (
    abs_delta_steering,
    describe,
    fit_steering,
    relative_frequency_histogram,
    track_delta_steering,
)


def _track(steering) -> TrackDataset:
    df = pd.DataFrame({"steering": steering})
    return TrackDataset(name="t", csv_path=None, img_dir=None, df=df)


def test_describe_matches_known_values():
    s = describe([0.0, 1.0, 2.0, 3.0, 4.0], "x")
    assert s.n == 5
    assert s.mean == pytest.approx(2.0)
    assert s.minimum == 0.0 and s.maximum == 4.0
    # sample variance (ddof=1) of 0..4 = 2.5
    assert s.variance == pytest.approx(2.5)
    assert s.percentiles[50] == pytest.approx(2.0)


def test_delta_steering_is_consecutive_difference():
    d = track_delta_steering(_track([0.0, 0.2, 0.1, 0.5]))
    assert d == pytest.approx([0.2, -0.1, 0.4])


def test_abs_delta_does_not_cross_track_junction():
    # Two tracks; a naive global diff would create one extra (bogus) value at the seam.
    t1 = _track([0.0, 0.1, 0.2])          # 2 deltas
    t2 = _track([0.9, 0.8])               # 1 delta
    combined = abs_delta_steering([t1, t2])
    assert combined.size == 2 + 1         # NOT (5 - 1) = 4
    # The bogus seam jump |0.9 - 0.2| = 0.7 must not appear.
    assert 0.7 not in combined


def test_fit_steering_returns_valid_result_on_known_normal():
    rng = np.random.default_rng(0)
    # Normal body + a chunk of exact zeros to exercise zero_mass handling.
    body = rng.normal(0, 0.1, size=5000)
    data = np.concatenate([body, np.zeros(2000)])
    res = fit_steering(data)
    assert res.dist_name in ("norm", "laplace", "uniform")
    assert res.dof >= 1
    assert isinstance(res.reject_null, bool)
    assert res.zero_mass == pytest.approx(2000 / 7000, abs=1e-6)
    assert set(res.aic_ranking) == {"norm", "laplace", "uniform"}


def test_relative_frequency_histogram_sums_to_one():
    rel, edges = relative_frequency_histogram([0, 1, 2, 3, 4, 5], bins=3)
    assert rel.sum() == pytest.approx(1.0)
    assert len(edges) == 4
