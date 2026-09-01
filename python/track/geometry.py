"""Whether a generated centre line is physically usable, and where its checkpoints go.

Closure is not enough. The harmonic form guarantees the curve joins up, but a loop can be
topologically perfect and still fold back to pass within a couple of metres of itself. When
that happens a distance-to-track-edge reading becomes ambiguous, because the nearest edge may
belong to a different part of the lap, and checkpoint ordering stops meaning anything. Both
the crossing check and the separation check are therefore required (research C10).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config
from .generator import CentreLine
from .vehicle import VehicleProfile


@dataclass(frozen=True)
class GeometryReport:
    """Whether a centre line is physically usable.

    Carries `r_floor_m` rather than only the verdict, so a reader can check the decision
    instead of trusting it. A report saying "rejected" with no floor beside it cannot be
    audited later, and these reports are written into the track files themselves.
    """

    seed: int
    min_radius_m: float
    r_floor_m: float
    radius_ok: bool
    self_intersects: bool
    min_separation_m: float
    separation_ok: bool
    total_length_m: float

    @property
    def ok(self) -> bool:
        """Every check passed."""
        return self.radius_ok and not self.self_intersects and self.separation_ok

    @property
    def rejection_reason(self) -> str | None:
        """Which check failed, phrased with the numbers that decided it.

        Reported in a fixed order so that a track failing two checks always names the same
        one, and a batch report stays comparable between runs.
        """
        if not self.radius_ok:
            return (f"tightest corner {self.min_radius_m:.2f} m is below the floor "
                    f"{self.r_floor_m:.2f} m")
        if self.self_intersects:
            return "the centre line crosses itself"
        if not self.separation_ok:
            return (f"the loop passes within {self.min_separation_m:.2f} m of itself, "
                    f"under the minimum {config.MIN_SEPARATION_M:.2f} m")
        return None


@dataclass(frozen=True)
class Checkpoint:
    """One gate on the loop: where it is and which way the track runs through it."""

    index: int
    x: float
    y: float
    s: float
    heading_x: float
    heading_y: float


def _segments_cross(p1, p2, q1, q2) -> np.ndarray:
    """Vectorised segment-crossing test by orientation signs.

    Two segments cross when each straddles the line through the other. Written with cross
    products rather than by solving for an intersection point, because the point is not
    wanted and the division to find it would need its own degenerate case.
    """

    def cross(o, a, b):
        return (a[..., 0] - o[..., 0]) * (b[..., 1] - o[..., 1]) - \
               (a[..., 1] - o[..., 1]) * (b[..., 0] - o[..., 0])

    d1 = cross(q1, q2, p1)
    d2 = cross(q1, q2, p2)
    d3 = cross(p1, p2, q1)
    d4 = cross(p1, p2, q2)

    return ((d1 * d2 < 0) & (d3 * d4 < 0))


def _self_intersects(x: np.ndarray, y: np.ndarray) -> bool:
    """Does the closed polyline cross itself anywhere except at shared endpoints?

    Adjacent segments are excluded: they share a vertex by construction, and a shared vertex
    is not a crossing. The loop wraps, so the last segment is adjacent to the first.
    """
    n = len(x)
    points = np.column_stack([x, y])
    starts = points
    ends = np.roll(points, -1, axis=0)

    for i in range(n):
        # Compare segment i against every segment that is not itself or a neighbour. Only
        # forward pairs are tested, since crossing is symmetric.
        lo = i + 2
        hi = n if i > 0 else n - 1
        if lo >= hi:
            continue

        j = np.arange(lo, hi)
        if _segments_cross(
                starts[i], ends[i], starts[j], ends[j]).any():
            return True

    return False


def _min_separation(x: np.ndarray, y: np.ndarray, arc: np.ndarray,
                    total_length_m: float) -> float:
    """Closest approach between two parts of the loop that are far apart along it.

    The `along the arc` qualifier is the whole point. Neighbouring samples are millimetres
    apart in space and would trivially fail any separation test, so only pairs separated by
    more than `SEPARATION_ARC_WINDOW_M` ALONG the curve are compared. Distance along a closed
    loop is the shorter of the two ways round, otherwise the first and last samples would look
    maximally far apart when they are in fact adjacent.

    The window is wider than the threshold on purpose, and the two must not be conflated: a
    chord is always shorter than the arc it subtends, so a window equal to the threshold fails
    every curve including a perfect circle. See `SEPARATION_ARC_WINDOW_M`.
    """
    points = np.column_stack([x, y])

    along = np.abs(arc[:, None] - arc[None, :])
    along = np.minimum(along, total_length_m - along)

    spatial = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=-1)

    far_enough = along > config.SEPARATION_ARC_WINDOW_M
    if not far_enough.any():
        # Degenerate: a loop shorter than twice the window has no comparable pairs at all.
        return float("inf")

    return float(np.min(spatial[far_enough]))


def check_geometry(line: CentreLine, profile: VehicleProfile) -> GeometryReport:
    """Run every geometric check on a centre line and report all of them.

    Every check runs even when an earlier one has already failed. A report that stopped at the
    first failure would make the batch statistics in T044 lie about why seeds were rejected.
    """
    min_radius_m = line.min_radius_m
    min_separation_m = _min_separation(line.x, line.y, line.arc_length, line.total_length_m)

    return GeometryReport(
        seed=line.seed,
        min_radius_m=min_radius_m,
        r_floor_m=profile.r_floor_m,
        radius_ok=min_radius_m >= profile.r_floor_m,
        self_intersects=_self_intersects(line.x, line.y),
        min_separation_m=min_separation_m,
        separation_ok=min_separation_m >= config.MIN_SEPARATION_M,
        total_length_m=line.total_length_m,
    )


def place_checkpoints(line: CentreLine, n: int = config.N_CHECKPOINTS) -> list[Checkpoint]:
    """Place `n` checkpoints evenly along the loop.

    Spaced by ARC LENGTH, not by the sample parameter. Equal steps in theta are not equal
    steps in distance on a harmonic loop: the radius varies by design, so theta-spaced gates
    would bunch up where the loop is close to the origin and spread out where it bulges. An
    agent rewarded per checkpoint would then be paid unevenly for the same distance covered.

    Positions are interpolated between samples rather than snapped to the nearest one, so the
    spacing is exactly even instead of even to within one sample.
    """
    if n < 1:
        raise ValueError("a track needs at least one checkpoint")

    targets = np.linspace(0.0, line.total_length_m, n, endpoint=False)

    # Wrap the arrays so a target falling between the last sample and the first interpolates
    # across the closure rather than clamping to the end.
    arc = np.concatenate([line.arc_length, [line.total_length_m]])
    xs = np.concatenate([line.x, line.x[:1]])
    ys = np.concatenate([line.y, line.y[:1]])

    x_at = np.interp(targets, arc, xs)
    y_at = np.interp(targets, arc, ys)

    # Heading from a small step forward along the arc, then normalised. Taken from the curve
    # itself rather than from the difference between consecutive checkpoints, which would be
    # a chord across a corner and would point noticeably wide of the track on a tight bend.
    step = line.total_length_m / (4 * len(arc))
    ahead = (targets + step) % line.total_length_m
    hx = np.interp(ahead, arc, xs) - x_at
    hy = np.interp(ahead, arc, ys) - y_at
    norm = np.hypot(hx, hy)
    norm[norm == 0] = 1.0

    return [
        Checkpoint(index=i, x=float(x_at[i]), y=float(y_at[i]), s=float(targets[i]),
                   heading_x=float(hx[i] / norm[i]), heading_y=float(hy[i] / norm[i]))
        for i in range(n)
    ]
