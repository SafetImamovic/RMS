"""The vehicle profile and the geometry that follows from it.

One place holds every limit the car has. The three numbers that matter most - the minimum
turning radius, the floor a track's corners may not go below, and the steering a corner at
that floor demands - are computed from the wheelbase and the margin, never stored beside
them. A profile whose stored radius disagrees with its wheelbase is the single easiest way
for this feature to become quietly wrong, so the type makes that state unrepresentable.

The model is the low-speed bicycle model: both front wheels collapse to one in the middle,
both rear wheels likewise, and R = L / tan(delta). At speed a real car understeers and
achieves a LARGER radius than this, which is exactly why RADIUS_MARGIN exists rather than
designing to the geometric limit (research C1, and the understeer assumption in spec.md).

Contract: specs/003-unity-environment/contracts/track-generator-api.md
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import config


@dataclass(frozen=True)
class VehicleProfile:
    """Every limit the car has, each traceable to a measurement or a stated assumption.

    Frozen, matching TrackDataset in M1 and RecordingSession in feature 002. The derived
    quantities are properties, not fields: there is no way to construct a profile whose
    r_min disagrees with its wheelbase.
    """

    wheelbase_m: float
    steer_max_deg: float
    steer_rate_norm_per_s: float
    v_max_ms: float
    accel_ms2: float
    brake_ms2: float
    radius_margin: float

    # --- Derived. Never stored. ----------------------------------------------------------

    @property
    def steer_max_rad(self) -> float:
        return math.radians(self.steer_max_deg)

    @property
    def r_min_m(self) -> float:
        """Tightest circle the car can physically describe, at full lock and low speed."""
        return self.wheelbase_m / math.tan(self.steer_max_rad)

    @property
    def r_floor_m(self) -> float:
        """Tightest corner a generated track may contain. r_min with the margin applied."""
        return self.r_min_m * self.radius_margin

    @property
    def max_required_steer(self) -> float:
        """Steering a corner at r_floor_m demands, normalised to [0, 1].

        Independent of wheelbase: L cancels between the atan and the radius, so the margin
        is the ONLY parameter that moves this number. That is what makes the margin an
        honest knob rather than one of two interacting ones (research C2). Asserted across
        a wheelbase sweep in test_vehicle.py, because the property is the reason the knob
        is meaningful.
        """
        return math.atan(math.tan(self.steer_max_rad) / self.radius_margin) / self.steer_max_rad

    @property
    def steering_reserve(self) -> float:
        """Fraction of steering left free in the tightest legal corner. 1 - max_required."""
        return 1.0 - self.max_required_steer

    def to_dict(self) -> dict:
        """Serialisable form, derived values included, for the Unity handoff."""
        out = asdict(self)
        out.update(
            r_min_m=self.r_min_m,
            r_floor_m=self.r_floor_m,
            max_required_steer=self.max_required_steer,
            steering_reserve=self.steering_reserve,
        )
        return out


def build_profile() -> VehicleProfile:
    """The single profile this feature uses, assembled from config."""
    return VehicleProfile(
        wheelbase_m=config.WHEELBASE_M,
        steer_max_deg=config.STEER_MAX_DEG,
        steer_rate_norm_per_s=config.STEER_RATE_NORM_PER_S,
        v_max_ms=config.V_MAX_MS,
        accel_ms2=config.ACCEL_MS2,
        brake_ms2=config.BRAKE_MS2,
        radius_margin=config.RADIUS_MARGIN,
    )


def radius_for_steering(steer_norm: float, profile: VehicleProfile) -> float:
    """Turning radius for a normalised steering input. R = L / tan(steer * steer_max).

    Straight ahead has no finite radius, so steer_norm == 0 returns infinity rather than
    raising: the caller almost always wants the minimum over a curve, and an infinity is
    the correct neutral element for that.
    """
    s = abs(float(steer_norm))
    if s > 1.0:
        raise ValueError(f"steering must be within [-1, 1], got {steer_norm}")
    if s == 0.0:
        return math.inf
    return profile.wheelbase_m / math.tan(s * profile.steer_max_rad)


def steering_for_radius(radius_m: float, profile: VehicleProfile) -> float:
    """Normalised steering needed to hold a given radius. Exact inverse of the above.

    Raises below r_min_m, because such a radius is not merely a large steering value: it is
    geometrically unreachable for this car, and silently clipping it to 1.0 would let an
    impossible corner pass the radius check as if it were merely tight.
    """
    r = float(radius_m)
    if r <= 0.0:
        raise ValueError(f"radius must be positive, got {radius_m}")
    if math.isinf(r):
        return 0.0
    if r < profile.r_min_m - 1e-12:
        raise ValueError(
            f"radius {r:.4f} m is below the vehicle's minimum {profile.r_min_m:.4f} m "
            "and cannot be driven at any steering angle"
        )
    return math.atan(profile.wheelbase_m / r) / profile.steer_max_rad


def stopping_distance_m(v_ms: float, decel_ms2: float) -> float:
    """v^2 / (2a). Derives the sensing range; never used to bound the vehicle.

    A ray shorter than this reports a wall the car can no longer avoid, which carries no
    usable information (research C11, FR-025).
    """
    if decel_ms2 <= 0.0:
        raise ValueError(f"deceleration must be positive, got {decel_ms2}")
    return (float(v_ms) ** 2) / (2.0 * float(decel_ms2))


def normalise_speed(values, p99: float):
    """Divide by the given 99th percentile. The only sanctioned way to compare speeds.

    There is deliberately no function in this package that converts a dataset speed into a
    physical unit. The recorded column has no documented unit (feature 002, A7), so any
    such conversion would be an unverifiable assumption propagating into every threshold
    downstream. Normalising by each side's own P99 removes the question instead of
    guessing at it (research C3, FR-004).
    """
    if p99 <= 0.0:
        raise ValueError(f"normalisation divisor must be positive, got {p99}")
    return np.asarray(values, dtype=float) / float(p99)


def export_profile(out_path: Path | None = None) -> Path:
    """Write the profile to JSON for the Unity side to check itself against.

    The C# VehicleProfile mirrors this file field for field. An EditMode test compares the
    two, so a drift between the Python constants and the Unity ones surfaces as a failing
    test rather than as geometry that is quietly wrong for a different car.
    """
    path = Path(out_path) if out_path is not None else config.TRACKS_DIR / "vehicle_profile.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    profile = build_profile()
    payload = {
        "schema_version": 2,
        "source": "python/track/config.py via python.track.vehicle.export_profile",
        "profile": profile.to_dict(),
        # The M1 measurements a keyboard drive is judged against (FR-009). Exported so the
        # live HUD tests against the measured envelope rather than against numbers retyped
        # on the C# side, which would be free to drift from M1 without anything noticing.
        "envelope": {
            "steer_abs_max": config.DATASET_STEER_ABS_MAX,
            "dsteer_p95_track1": config.DATASET_DSTEER_P95_TRACK1,
            "dsteer_p95_track2": config.DATASET_DSTEER_P95_TRACK2,
            "dsteer_max": config.DATASET_DSTEER_MAX,
            "speed_p99": config.DATASET_SPEED_P99,
            "speed_max": config.DATASET_SPEED_MAX,
            # Shape of the speed distribution, unit free. This is the only speed figure that
            # may be compared against the simulation, because the recorded column has no
            # documented unit (FR-004, research C3).
            "speed_max_over_p99": config.DATASET_SPEED_MAX / config.DATASET_SPEED_P99,
            "compare_hz": config.COMPARE_HZ,
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":  # pragma: no cover - thin CLI over export_profile
    written = export_profile()
    p = build_profile()
    print(f"wrote {written}")
    print(f"  r_min             = {p.r_min_m:.4f} m")
    print(f"  r_floor           = {p.r_floor_m:.4f} m  (margin {p.radius_margin})")
    print(f"  max required steer= {p.max_required_steer:.4f}")
    print(f"  steering reserve  = {100 * p.steering_reserve:.1f} %")
