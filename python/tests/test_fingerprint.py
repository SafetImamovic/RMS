"""Tests for python/eda/fingerprint.py (US1).

We build a frame whose numeric columns have KNOWN identities and assert the rule-based
inference recovers them — including the case where columns are shuffled, proving the
inference relies on statistics, not on position/name.
"""

from __future__ import annotations

import pandas as pd

from python.eda import config
from python.eda.fingerprint import column_fingerprints
from python.eda.loader import TrackDataset


def _make_ds(steering, throttle, brake, speed) -> TrackDataset:
    # Image columns are placeholders; fingerprint only reads the numeric columns.
    n = len(steering)
    df = pd.DataFrame(
        {
            "center": ["c"] * n,
            "left": ["l"] * n,
            "right": ["r"] * n,
            "steering": steering,
            "throttle": throttle,
            "brake": brake,
            "speed": speed,
        }
    )
    return TrackDataset(name="t", csv_path=None, img_dir=None, df=df)


def test_fingerprint_infers_correct_identities():
    ds = _make_ds(
        steering=[-0.5, 0.0, 0.3, 0.0, -0.2],
        throttle=[0.5, 0.0, 0.8, 0.2, 0.0],
        brake=[0.0, 0.0, 0.0, 0.0, 0.0],
        speed=[10.0, 15.0, 0.0, 22.0, 5.0],
    )
    fps = {fp.assumed_name: fp for fp in column_fingerprints(ds)}
    assert fps["steering"].inferred_identity == "steering"
    assert fps["throttle"].inferred_identity == "throttle"
    assert fps["brake"].inferred_identity == "brake"
    assert fps["speed"].inferred_identity == "speed"
    assert all(fp.matches_assumption for fp in fps.values())


def test_fingerprint_only_steering_is_negative():
    ds = _make_ds(
        steering=[-0.9, 0.1, -0.4, 0.0, 0.2],
        throttle=[0.3, 0.4, 0.5, 0.6, 0.7],
        brake=[0.0, 0.0, 0.0, 0.0, 0.0],
        speed=[3.0, 4.0, 5.0, 6.0, 7.0],
    )
    steer_fp = next(fp for fp in column_fingerprints(ds) if fp.inferred_identity == "steering")
    assert steer_fp.pct_negative > 0
    assert steer_fp.minimum < 0
