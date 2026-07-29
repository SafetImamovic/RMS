"""Tests for python/eda/loader.py (US1)."""

from __future__ import annotations

import pandas as pd
import pytest

from python.eda import config
from python.eda.loader import (
    check_integrity,
    load_track,
    resolve_image_paths,
)


def test_load_track_parses_seven_columns(synthetic_track):
    ds = load_track(synthetic_track["name"])
    assert list(ds.df.columns) == config.COLUMN_NAMES
    assert len(ds.df) == synthetic_track["n_rows"]
    # Numeric columns are real floats (scientific notation would also parse).
    assert ds.df["steering"].dtype.kind == "f"
    assert ds.df["speed"].dtype.kind == "f"


def test_load_track_rejects_wrong_column_count(tmp_path, monkeypatch):
    # Write a 4-column CSV and register it; loader must refuse it loudly.
    bad = tmp_path / "bad.csv"
    pd.DataFrame([[1, 2, 3, 4]]).to_csv(bad, header=False, index=False)
    patched = dict(config.TRACK_PATHS)
    patched["bad"] = config.TrackPaths(csv_path=bad, img_dir=tmp_path)
    monkeypatch.setattr(config, "TRACK_PATHS", patched)

    with pytest.raises(ValueError, match="columns"):
        load_track("bad")


def test_resolve_image_paths_strips_windows_prefix(synthetic_track):
    ds = load_track(synthetic_track["name"])
    resolve_image_paths(ds)
    # The re-rooted file name is just the basename, no 'Desktop\clip\IMG\'.
    first = ds.df["center_file"].iloc[0]
    assert first.startswith("center_")
    assert "\\" not in first and "/" not in first


def test_integrity_ok_when_all_images_present(synthetic_track):
    ds = load_track(synthetic_track["name"])
    report = check_integrity(ds)
    assert report.row_count == synthetic_track["n_rows"]
    assert report.image_count == synthetic_track["n_images"]
    assert report.expected_image_count == synthetic_track["n_rows"] * 3
    assert report.integrity_ok is True
    assert report.unresolved_rows == 0


def test_integrity_detects_missing_image(synthetic_track):
    ds = load_track(synthetic_track["name"])
    # Delete one image -> that row becomes unresolved and counts break.
    victim = next(synthetic_track["img_dir"].glob("center_*.jpg"))
    victim.unlink()

    report = check_integrity(ds)
    assert report.integrity_ok is False           # 14 != 15
    assert report.unresolved_rows == 1
    assert report.image_count == synthetic_track["n_images"] - 1
