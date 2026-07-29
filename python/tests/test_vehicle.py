"""Tests for the M2 vehicle profile (feature 003, task T010).

Each check needs both directions of evidence, the same rule feature 002 established: a
function that rejects everything passes every "must reject" test and is useless. So every
family below asserts what must be refused AND what must go through untouched.

Contract: specs/003-unity-environment/contracts/track-generator-api.md
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from python.track import config
from python.track.vehicle import (
    VehicleProfile,
    build_profile,
    export_profile,
    normalise_speed,
    radius_for_steering,
    steering_for_radius,
    stopping_distance_m,
)


@pytest.fixture
def profile() -> VehicleProfile:
    return build_profile()


# =========================================================================================
# Derived values (research C1, C2)
# =========================================================================================


def test_derived_radii_match_research_c1(profile):
    """The three headline numbers the whole feature rests on."""
    assert profile.r_min_m == pytest.approx(5.361, abs=0.001)
    assert profile.r_floor_m == pytest.approx(6.970, abs=0.001)
    assert profile.max_required_steer == pytest.approx(0.789, abs=0.001)


def test_steering_reserve_is_the_margin_in_disguise(profile):
    """The margin's whole justification: 1.3 buys 21.1 percent of steering back.

    If this ever drifts, the margin has stopped meaning what research C2 says it means and
    the "corner leaves the driver nothing to correct with" argument no longer holds.
    """
    assert profile.steering_reserve == pytest.approx(0.211, abs=0.001)


@pytest.mark.parametrize(
    ("steer_norm", "expected_radius_m", "source"),
    [
        (0.25, 22.83, "track1 median of non-zero"),
        (0.40, 14.18, "track1 P75"),
        (0.50, 11.28, "track2 median"),
        (0.65, 8.58, "track1 P95"),
        (0.79, 6.96, "the limit a track may demand"),
        (0.90, 6.04, "track1 P99"),
        (1.00, 5.36, "full lock"),
    ],
)
def test_radius_table_from_research_c1(profile, steer_norm, expected_radius_m, source):
    """Reproduce the published radius table row by row.

    This table is quoted in research, in the plan and on the defense slide. If the code
    stops agreeing with it, one of the two is wrong and the test says which.
    """
    assert radius_for_steering(steer_norm, profile) == pytest.approx(
        expected_radius_m, abs=0.02
    ), f"row '{source}' no longer matches the documented table"


# =========================================================================================
# Wheelbase independence (research C2) - the reason the margin is an honest knob
# =========================================================================================


@pytest.mark.parametrize("wheelbase_m", [1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
def test_max_required_steer_is_independent_of_wheelbase(profile, wheelbase_m):
    """L cancels out. The margin ALONE controls what a track may demand.

    This is the property that makes RADIUS_MARGIN a meaningful thing to tune. If it failed,
    every change of wheelbase would silently move the steering ceiling too, and the two
    parameters could no longer be reasoned about separately.
    """
    swept = VehicleProfile(
        wheelbase_m=wheelbase_m,
        steer_max_deg=profile.steer_max_deg,
        steer_rate_norm_per_s=profile.steer_rate_norm_per_s,
        v_max_ms=profile.v_max_ms,
        accel_ms2=profile.accel_ms2,
        brake_ms2=profile.brake_ms2,
        radius_margin=profile.radius_margin,
    )
    assert swept.max_required_steer == pytest.approx(profile.max_required_steer, abs=1e-12)


def test_radii_do_scale_linearly_with_wheelbase(profile):
    """The other half of the same claim: the RADII move even though the steering does not.

    Without this, the test above would also pass on an implementation that ignored the
    wheelbase entirely.
    """
    doubled = VehicleProfile(
        wheelbase_m=2 * profile.wheelbase_m,
        steer_max_deg=profile.steer_max_deg,
        steer_rate_norm_per_s=profile.steer_rate_norm_per_s,
        v_max_ms=profile.v_max_ms,
        accel_ms2=profile.accel_ms2,
        brake_ms2=profile.brake_ms2,
        radius_margin=profile.radius_margin,
    )
    assert doubled.r_min_m == pytest.approx(2 * profile.r_min_m, rel=1e-12)
    assert doubled.r_floor_m == pytest.approx(2 * profile.r_floor_m, rel=1e-12)


def test_derived_values_cannot_be_set_independently(profile):
    """The profile is frozen and its radii are properties, so they cannot drift apart."""
    with pytest.raises((AttributeError, TypeError)):
        profile.wheelbase_m = 99.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        profile.r_min_m = 1.0  # type: ignore[misc]


# =========================================================================================
# Steering and radius are exact inverses
# =========================================================================================


@pytest.mark.parametrize("steer_norm", [0.05, 0.1, 0.25, 0.4, 0.5, 0.65, 0.789, 0.9, 1.0])
def test_steering_radius_round_trip(profile, steer_norm):
    radius = radius_for_steering(steer_norm, profile)
    assert steering_for_radius(radius, profile) == pytest.approx(steer_norm, abs=1e-12)


def test_straight_ahead_has_no_finite_radius(profile):
    """Zero steering is a straight line, so infinity, not a division by zero."""
    assert math.isinf(radius_for_steering(0.0, profile))
    assert steering_for_radius(math.inf, profile) == 0.0


def test_steering_is_unsigned_in_radius_terms(profile):
    """Left and right describe the same circle. The sign belongs to the track, not the car."""
    assert radius_for_steering(-0.5, profile) == pytest.approx(
        radius_for_steering(0.5, profile)
    )


def test_radius_below_the_minimum_is_refused(profile):
    """A corner tighter than r_min is unreachable, not merely demanding.

    Clipping it to full lock would let a physically impossible corner pass the radius check
    looking like a merely tight one, which is precisely the failure the check exists to
    catch.
    """
    with pytest.raises(ValueError, match="below the vehicle's minimum"):
        steering_for_radius(profile.r_min_m * 0.9, profile)


def test_radius_just_above_the_minimum_is_accepted(profile):
    """The other direction. A check that refuses everything proves nothing."""
    assert steering_for_radius(profile.r_min_m * 1.0001, profile) == pytest.approx(
        1.0, abs=1e-4
    )


def test_steering_beyond_full_lock_is_refused(profile):
    with pytest.raises(ValueError, match=r"within \[-1, 1\]"):
        radius_for_steering(1.5, profile)


def test_non_positive_radius_is_refused(profile):
    with pytest.raises(ValueError, match="must be positive"):
        steering_for_radius(0.0, profile)


# =========================================================================================
# Sensing range is DERIVED from stopping distance (FR-025, research C11)
# =========================================================================================


def test_stopping_distance_matches_research_c11(profile):
    """8.5 m at top speed under P95 braking. The figure RAY_LENGTH_M was chosen against."""
    assert stopping_distance_m(config.V_MAX_MS, config.BRAKE_MS2) == pytest.approx(
        8.5, abs=0.1
    )


def test_ray_length_exceeds_the_stopping_distance():
    """FR-025 requires the range be derived, so assert the derivation still holds.

    A sensor shorter than the stopping distance reports a barrier the car can no longer
    avoid. Without this assertion RAY_LENGTH_M is just a number with a comment next to it,
    and a later change to the braking figure would silently invalidate it.
    """
    stopping = stopping_distance_m(config.V_MAX_MS, config.BRAKE_MS2)
    assert config.RAY_LENGTH_M > 2 * stopping, (
        f"ray range {config.RAY_LENGTH_M} m must clear twice the {stopping:.1f} m "
        "stopping distance, per research C11"
    )


def test_stopping_distance_rejects_zero_deceleration():
    with pytest.raises(ValueError, match="must be positive"):
        stopping_distance_m(10.0, 0.0)


# =========================================================================================
# Speed normalisation (FR-004, research C3)
# =========================================================================================


def test_normalise_speed_divides_by_the_given_percentile():
    values = np.array([0.0, 8.7433, 17.4865])
    out = normalise_speed(values, config.DATASET_SPEED_P99)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(0.5, abs=1e-4)
    assert out[2] == pytest.approx(1.0, abs=1e-4)


def test_normalisation_is_unit_free():
    """The same drive expressed in two arbitrary units normalises to the same numbers.

    This is the entire argument for FR-004: because the dataset's speed column has no
    documented unit, only a unit-free comparison can be made at all.
    """
    raw = np.array([1.0, 5.0, 10.0, 17.0])
    rescaled = raw * 2.23694  # as if someone had "converted" it
    a = normalise_speed(raw, float(np.percentile(raw, 99)))
    b = normalise_speed(rescaled, float(np.percentile(rescaled, 99)))
    assert np.allclose(a, b)


def test_no_unit_conversion_function_exists():
    """There is deliberately no such function to call.

    Feature 002 established that the speed column carries no documented unit. The defence
    against a unit assumption creeping back in is that the API offers no way to express one.
    """
    import python.track.vehicle as vehicle_module

    names = [n.lower() for n in dir(vehicle_module)]
    forbidden = ("to_mph", "to_kmh", "to_ms", "convert_speed", "speed_in_")
    assert not [n for n in names if any(f in n for f in forbidden)]


def test_normalise_speed_rejects_a_useless_divisor():
    with pytest.raises(ValueError, match="must be positive"):
        normalise_speed([1.0, 2.0], 0.0)


# =========================================================================================
# The Unity handoff (T011)
# =========================================================================================


def test_export_profile_writes_every_derived_value(tmp_path, profile):
    """The C# side checks itself against this file, so the derived values must be in it."""
    written = export_profile(tmp_path / "vehicle_profile.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 2
    exported = payload["profile"]
    for field in (
        "wheelbase_m",
        "steer_max_deg",
        "steer_rate_norm_per_s",
        "v_max_ms",
        "accel_ms2",
        "brake_ms2",
        "radius_margin",
        "r_min_m",
        "r_floor_m",
        "max_required_steer",
        "steering_reserve",
    ):
        assert field in exported, f"{field} missing from the Unity handoff"

    assert exported["r_min_m"] == pytest.approx(profile.r_min_m)
    assert exported["max_required_steer"] == pytest.approx(profile.max_required_steer)


def test_export_carries_the_m1_envelope(tmp_path):
    """The HUD judges a live drive against these, so they must travel with the profile.

    Retyping them on the C# side would let the pass/fail thresholds drift away from M1
    with nothing to catch it, which would make a green HUD meaningless.
    """
    written = export_profile(tmp_path / "vehicle_profile.json")
    envelope = json.loads(written.read_text(encoding="utf-8"))["envelope"]

    for field in (
        "steer_abs_max",
        "dsteer_p95_track1",
        "dsteer_p95_track2",
        "dsteer_max",
        "speed_p99",
        "speed_max",
        "speed_max_over_p99",
        "compare_hz",
    ):
        assert field in envelope, f"{field} missing from the exported envelope"

    assert envelope["steer_abs_max"] == pytest.approx(1.0)
    assert envelope["dsteer_p95_track1"] == pytest.approx(0.30)
    assert envelope["dsteer_p95_track2"] == pytest.approx(0.70)
    assert envelope["compare_hz"] == pytest.approx(14.08)

    # Unit free by construction, and the only speed figure allowed into a comparison.
    assert envelope["speed_max_over_p99"] == pytest.approx(
        config.DATASET_SPEED_MAX / config.DATASET_SPEED_P99
    )
    assert envelope["speed_max_over_p99"] == pytest.approx(1.2552, abs=0.001)


def test_committed_profile_matches_the_current_config(profile):
    """The committed file is what Unity reads. If config moved and the file did not, say so.

    Regenerate with: python -m python.track.vehicle
    """
    committed = config.TRACKS_DIR / "vehicle_profile.json"
    if not committed.exists():
        pytest.skip("vehicle_profile.json not exported yet (task T011)")

    exported = json.loads(committed.read_text(encoding="utf-8"))["profile"]
    assert exported["wheelbase_m"] == pytest.approx(profile.wheelbase_m)
    assert exported["steer_max_deg"] == pytest.approx(profile.steer_max_deg)
    assert exported["radius_margin"] == pytest.approx(profile.radius_margin)
    assert exported["r_floor_m"] == pytest.approx(profile.r_floor_m)
    assert exported["max_required_steer"] == pytest.approx(profile.max_required_steer)
