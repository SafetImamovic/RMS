"""The sensing block must say what config.py says, and the committed file must be current.

This test is the whole reason the sensing block exists (feature 005, FR-016).

`RAY_COUNT`, `RAY_FOV_DEG` and `RAY_LENGTH_M` used to live in `python/track/config.py` AND as
serialised fields on `CarAgent`, with nothing standing between the two copies. `CarAgent`'s own
comment said as much: changing a ray constant meant changing it in both places by hand, and
nothing would notice if only one of them moved. Feature 005 varies these values across a sweep,
which would have made that drift worse rather than better.

So the values moved into the exported profile and Unity reads them from there. That removes the
second copy, but it introduces a new way to be wrong: the committed file can go stale against the
constants it was generated from. These tests close that gap.

Contract: specs/005-heuristic-ray-driver/contracts/sensing-block.md
"""

from __future__ import annotations

import json

import pytest

from python.track import config
from python.track.vehicle import export_profile


def test_export_carries_the_sensing_block(tmp_path):
    """A freshly exported file mirrors the constants it was generated from."""
    written = export_profile(tmp_path / "vehicle_profile.json")
    sensing = json.loads(written.read_text(encoding="utf-8"))["sensing"]

    for field in ("ray_count", "ray_fov_deg", "ray_length_m"):
        assert field in sensing, f"{field} missing from the exported sensing block"

    assert sensing["ray_count"] == config.RAY_COUNT
    assert sensing["ray_fov_deg"] == pytest.approx(config.RAY_FOV_DEG)
    assert sensing["ray_length_m"] == pytest.approx(config.RAY_LENGTH_M)


def test_ray_spacing_is_not_exported(tmp_path):
    """Spacing is derived at both ends, so exporting it would create a third copy.

    A stored spacing can disagree with the count and the field of view it came from, which is
    exactly the failure this block was added to remove. Deriving it costs one division.
    """
    written = export_profile(tmp_path / "vehicle_profile.json")
    sensing = json.loads(written.read_text(encoding="utf-8"))["sensing"]

    assert "ray_spacing_deg" not in sensing
    assert "spacing" not in sensing


def test_schema_version_announces_the_new_block(tmp_path):
    """Unity refuses a version it does not understand rather than reading a moved block."""
    written = export_profile(tmp_path / "vehicle_profile.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 3, (
        "the sensing block was added at schema_version 3; a loader written against 2 must "
        "refuse this file rather than silently ignore the block it does not know about"
    )


def test_thirteen_rays_still_put_one_straight_ahead():
    """An odd count is the reason ray 06 looks down the nose, and T062 checked it there.

    An even count is a legal sweep configuration, not an error, so this asserts the CURRENT
    value rather than forbidding even counts outright. If the sweep adopts an even fan, this
    test changes in the same commit that adopts it, which is what FR-018 asks for.
    """
    assert config.RAY_COUNT % 2 == 1
    assert config.RAY_COUNT == 13


def test_committed_profile_carries_the_current_sensing_block():
    """The committed file is what Unity reads. If config moved and the file did not, say so.

    Regenerate with: python -m python.track.vehicle
    """
    committed = config.TRACKS_DIR / "vehicle_profile.json"
    if not committed.exists():
        pytest.skip("vehicle_profile.json not exported yet")

    payload = json.loads(committed.read_text(encoding="utf-8"))

    assert "sensing" in payload, (
        "the committed vehicle_profile.json predates the sensing block. Regenerate it with "
        "python -m python.track.vehicle, or CarAgent will refuse to start"
    )

    sensing = payload["sensing"]
    assert sensing["ray_count"] == config.RAY_COUNT
    assert sensing["ray_fov_deg"] == pytest.approx(config.RAY_FOV_DEG)
    assert sensing["ray_length_m"] == pytest.approx(config.RAY_LENGTH_M)


def test_committed_values_are_the_ones_feature_003_measured():
    """13 rays, 180 degrees, 20 m. T062 verified the observation vector against these.

    Moving where they are read from must not move what they are. If this fails alongside a
    deliberate sweep change, every sensing result in feature 003 needs re-measuring and any
    model trained against the old fan is invalid (FR-018).
    """
    committed = config.TRACKS_DIR / "vehicle_profile.json"
    if not committed.exists():
        pytest.skip("vehicle_profile.json not exported yet")

    sensing = json.loads(committed.read_text(encoding="utf-8"))["sensing"]
    assert sensing["ray_count"] == 13
    assert sensing["ray_fov_deg"] == pytest.approx(180.0)
    assert sensing["ray_length_m"] == pytest.approx(20.0)
