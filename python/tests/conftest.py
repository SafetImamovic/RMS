"""Shared pytest fixtures: a tiny synthetic dataset that mimics the real format.

We build a 5-row headerless CSV (7 columns, Windows-style image paths) plus a fake IMG/
folder with matching files, then point config.TRACK_PATHS at it via monkeypatch. This lets
us exercise the loader/fingerprint code without the real ~200k-image dataset.
"""

from __future__ import annotations

import pandas as pd
import pytest

from python.eda import config as eda_config
from python.eda.config import TrackPaths

# Known values chosen so each numeric column has an unambiguous identity:
#   steering: has negatives (left turns)        throttle: [0,1] with positives
#   brake:    all zero (no braking in this clip) speed:    large magnitude
_STEERING = [-0.5, 0.0, 0.3, 0.0, -0.2]
_THROTTLE = [0.5, 0.0, 0.8, 0.2, 0.0]
_BRAKE = [0.0, 0.0, 0.0, 0.0, 0.0]
_SPEED = [10.0, 15.0, 0.0, 22.0, 5.0]


@pytest.fixture
def synthetic_track(tmp_path, monkeypatch):
    """Create a 5-row track with all images present, registered as track 'testtrack'."""
    img_dir = tmp_path / "IMG"
    img_dir.mkdir()

    records = []
    for i in range(5):
        ts = f"2020_01_01_00_00_0{i}_000"
        names = {cam: f"{cam}_{ts}.jpg" for cam in ("center", "left", "right")}
        for fname in names.values():
            (img_dir / fname).write_bytes(b"x")  # content irrelevant; only existence matters
        records.append(
            [
                f"Desktop\\clip\\IMG\\{names['center']}",
                f"Desktop\\clip\\IMG\\{names['left']}",
                f"Desktop\\clip\\IMG\\{names['right']}",
                _STEERING[i],
                _THROTTLE[i],
                _BRAKE[i],
                _SPEED[i],
            ]
        )

    csv_path = tmp_path / "driving_log.csv"
    pd.DataFrame(records).to_csv(csv_path, header=False, index=False)

    # Register the synthetic track so load_track("testtrack") works.
    patched = dict(eda_config.TRACK_PATHS)
    patched["testtrack"] = TrackPaths(csv_path=csv_path, img_dir=img_dir)
    monkeypatch.setattr(eda_config, "TRACK_PATHS", patched)

    return {
        "name": "testtrack",
        "csv_path": csv_path,
        "img_dir": img_dir,
        "n_rows": 5,
        "n_images": 15,  # 5 rows x 3 cameras, all present
    }
