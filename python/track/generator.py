"""Closed race-track centre lines from a single integer seed.

The curve is a polar harmonic loop::

    r(theta) = R0 * (1 + sum_k a_k sin(k theta + phi_k)),    a_k = A / k^2

Two properties of this form are doing real work, and both are reasons it was chosen over
splines or point-and-smooth approaches (research C6):

**It closes by construction.** Every harmonic is an integer multiple of theta, so r(0) equals
r(2 pi) exactly, for any amplitude and any phases. Nothing in this module adjusts endpoints to
make them meet, because there is nothing to adjust. A generator that stitches its ends
together has a seam, and a seam is a discontinuity in curvature that the vehicle feels.

**Its curvature is known in closed form.** r, r' and r'' are sums of sines, so curvature comes
from the polar expression rather than from finite differences. This matters more than it
sounds: the minimum radius over the loop is what decides whether a seed is accepted, so the
accept-or-reject decision is made exactly where numerical differentiation is least accurate
(research C7).

The 1/k^2 falloff is what keeps high harmonics from dominating. Amplitude a_k enters curvature
weighted by k^2, so without the falloff the k=5 term would drive the tightest corner and the
radius floor would reject nearly everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import config

# Where curvature is numerically zero the curve is locally straight and the radius is
# genuinely enormous. np.inf would be the honest value but it propagates through every mean
# and plot downstream, so a large finite stand-in is used instead.
_STRAIGHT_RADIUS_M: float = 1e6


@dataclass(frozen=True)
class TrackSeed:
    """One integer and the record of what happened to it.

    Rejected seeds are kept rather than discarded. A generator that quietly resamples until it
    succeeds has an acceptance rate nobody can see, and a low rate is a finding about the
    radius floor fighting the statistical target, not a nuisance to hide (research C7).
    """

    seed: int
    amplitude: float
    phases: tuple[float, ...]
    accepted: bool = True
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        # rejection_reason is non-empty exactly when accepted is false. Stated as an assertion
        # because every consumer reads one to decide what the other means.
        if self.accepted and self.rejection_reason is not None:
            raise ValueError("an accepted seed cannot carry a rejection reason")
        if not self.accepted and not self.rejection_reason:
            raise ValueError("a rejected seed must say which check failed")
        if len(self.phases) != len(config.HARMONICS):
            raise ValueError(
                f"expected one phase per harmonic ({len(config.HARMONICS)}), "
                f"got {len(self.phases)}")

    def rejected(self, reason: str) -> "TrackSeed":
        """This seed, marked as failing `reason`. The geometry is unchanged."""
        return TrackSeed(
            seed=self.seed,
            amplitude=self.amplitude,
            phases=self.phases,
            accepted=False,
            rejection_reason=reason,
        )


@dataclass(frozen=True)
class CentreLine:
    """The generated closed curve, sampled.

    `radius` holds very large values near inflection points, where curvature approaches zero.
    That is not a defect and is not clipped away as if it were: consumers care about the
    minimum radius and never about the maximum.
    """

    seed: int
    theta: np.ndarray
    x: np.ndarray
    y: np.ndarray
    arc_length: np.ndarray
    curvature: np.ndarray
    radius: np.ndarray
    total_length_m: float

    # Excluded from equality so two lines compare on their geometry, not on their provenance.
    params: TrackSeed = field(compare=False, default=None)  # type: ignore[assignment]

    @property
    def min_radius_m(self) -> float:
        """The tightest corner on the loop. This is the quantity seeds are judged on."""
        return float(np.min(self.radius))


def draw_parameters(seed: int) -> TrackSeed:
    """Draw the amplitude and phases for `seed`.

    Uses a generator instance seeded explicitly, never the global NumPy random state. Global
    state would make the output depend on whatever else in the process drew a number first,
    and SC-007 requires that the same seed produce byte-identical output across runs and
    across processes.
    """
    rng = np.random.default_rng(seed)

    low, high = config.AMPLITUDE_RANGE
    amplitude = float(rng.uniform(low, high))
    phases = tuple(float(p) for p in rng.uniform(0.0, 2.0 * np.pi, size=len(config.HARMONICS)))

    return TrackSeed(seed=seed, amplitude=amplitude, phases=phases)


def _radius_terms(params: TrackSeed, theta: np.ndarray) -> tuple[np.ndarray, ...]:
    """r, r' and r'' for the harmonic sum, all analytic.

    Returned together because the curvature expression needs all three and computing them in
    one place keeps the 1/k^2 amplitude rule from being written out three times.
    """
    r0 = config.TRACK_R0_M

    total = np.zeros_like(theta)
    d1 = np.zeros_like(theta)
    d2 = np.zeros_like(theta)

    for k, phase in zip(config.HARMONICS, params.phases):
        a_k = params.amplitude / (k * k)
        angle = k * theta + phase
        total += a_k * np.sin(angle)
        d1 += a_k * k * np.cos(angle)
        d2 -= a_k * k * k * np.sin(angle)

    return r0 * (1.0 + total), r0 * d1, r0 * d2


def centre_line(params: TrackSeed) -> CentreLine:
    """Sample the closed curve for these parameters."""
    # endpoint=False: the sample at 2 pi would repeat the sample at 0. The track file schema
    # forbids a duplicated first and last point, and a repeated point would also add a
    # zero-length segment to every arc-length and separation calculation downstream.
    theta = np.linspace(0.0, 2.0 * np.pi, config.SAMPLES_PER_TRACK, endpoint=False)

    r, dr, d2r = _radius_terms(params, theta)

    x = r * np.cos(theta)
    y = r * np.sin(theta)

    # Curvature of a polar curve. Signed, so an inflection shows as a sign change rather than
    # as a spurious zero, and the sign is discarded only where the magnitude is wanted.
    denominator = np.power(r * r + dr * dr, 1.5)
    curvature = (r * r + 2.0 * dr * dr - r * d2r) / denominator

    # Radius is the reciprocal of |curvature|, with the straight-line case standing in where
    # curvature underflows. Guarded rather than divided blindly, so no warning is emitted and
    # no infinity reaches a consumer.
    safe = np.abs(curvature) > 1e-12
    radius = np.where(safe, 1.0 / np.where(safe, np.abs(curvature), 1.0), _STRAIGHT_RADIUS_M)

    # Arc length is integrated numerically, unlike curvature. It is not what the accept or
    # reject decision rests on, and ds = sqrt(r^2 + r'^2) dtheta has no elementary closed form
    # for a sum of sines, so an accurate quadrature is the honest choice rather than a
    # pretence of exactness.
    speed = np.sqrt(r * r + dr * dr)
    dtheta = theta[1] - theta[0]

    # The curve is closed, so the segment from the last sample back to the first is a real
    # segment and belongs in the perimeter. Wrapping the speed array is what includes it.
    wrapped = np.concatenate([speed, speed[:1]])
    segment = 0.5 * (wrapped[:-1] + wrapped[1:]) * dtheta

    arc_length = np.concatenate([[0.0], np.cumsum(segment)[:-1]])
    total_length_m = float(np.sum(segment))

    return CentreLine(
        seed=params.seed,
        theta=theta,
        x=x,
        y=y,
        arc_length=arc_length,
        curvature=curvature,
        radius=radius,
        total_length_m=total_length_m,
        params=params,
    )


def generate(seed: int) -> CentreLine:
    """Draw parameters for `seed` and sample the curve. The whole generator, in one call."""
    return centre_line(draw_parameters(seed))
