"""How much steering a track demands, and how close that sits to the human data.

Three things about this module are deliberate and worth stating up front.

**It reports a distance, not a test.** `match_distance` returns a Wasserstein-1 distance
against a threshold. There is no p-value anywhere in this file, and FR-019 forbids one. A
large p-value is not evidence of agreement, only an absence of evidence against it, and
feature 002 exists because that mistake was made here once already (research C8).

**It compares conditional distributions.** A harmonic loop has no straight sections, while
58.6 percent of the human samples are exactly zero steering. Comparing the full distributions
would mostly measure the presence of straights, which is a fact about track topology rather
than about driving, so both sides are taken conditional on being non-zero (research C9).

**It reads the M1 dataset and never writes to it.** The reference distribution comes through
the existing `python.eda` loader rather than a private copy, so a change to how the dataset is
read cannot leave two different answers in the repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import config
from .generator import CentreLine
from .vehicle import VehicleProfile

# The percentiles M1 reports, so a demand summary can be laid beside a human one without
# either being re-binned first.
PERCENTILES: tuple[float, ...] = (5.0, 25.0, 50.0, 75.0, 95.0, 99.0)

# Bin count for the relative-frequency histogram. Fixed rather than chosen per distribution:
# two histograms with different binning are not comparable, and comparability is the whole
# reason Principle IX asks for the histogram.
HISTOGRAM_BINS: int = 20

# Percentiles the SC-010 bound is checked at. The UPPER part of the distribution only, and
# that restriction is not a convenience.
#
# The bound asks whether a track ever demands MORE steering than a human was recorded
# supplying, which is a statement about the upper tail. Applying it to low percentiles asks
# the opposite question and gets a nonsensical answer: a harmonic loop is turning everywhere,
# so its P5 demand is far above a human's, whose P5 is a small correction on a straight. A
# single seed measures 0.28 at P5 against a human 0.05 and would "fail" a bound it is not in
# breach of. That a generated track has no straights is a documented and accepted property
# (research C9), not a defect for this check to rediscover.
BOUND_PERCENTILES: tuple[float, ...] = (50.0, 75.0, 95.0, 99.0)

# NumPy renamed trapz to trapezoid in 2.0 and this project runs on 1.26. Resolved once here
# so the numerical code below reads the same on either version.
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


@dataclass(frozen=True)
class Descriptives:
    """The Principle IX block: n, mean, variance, std, min, max and a histogram.

    Required rather than convenient. The constitution names all six for every distribution the
    project touches, and required steering is one this feature introduces. Percentiles alone
    were the original shape of this type and did not satisfy the principle.
    """

    n: int
    mean: float
    variance: float
    std: float
    min: float
    max: float
    bin_edges: np.ndarray
    relative_frequency: np.ndarray


def describe(values, bins: int = HISTOGRAM_BINS) -> Descriptives:
    """Summarise a distribution. Never touches the disk.

    The histogram carries RELATIVE frequency, not counts. A 2000-sample track and a
    2193-sample reference produce incomparable count histograms, and the comparison is the
    only reason the histogram is here.
    """
    v = np.asarray(values, dtype=float).ravel()
    if v.size == 0:
        raise ValueError("cannot describe an empty distribution")

    counts, edges = np.histogram(v, bins=bins)
    total = counts.sum()

    return Descriptives(
        n=int(v.size),
        mean=float(np.mean(v)),
        # Population variance (ddof=0). These are complete enumerations of a generated track
        # or of a recording, not samples drawn from a larger population.
        variance=float(np.var(v)),
        std=float(np.std(v)),
        min=float(np.min(v)),
        max=float(np.max(v)),
        bin_edges=edges,
        relative_frequency=counts / total if total else counts.astype(float),
    )


@dataclass(frozen=True)
class SteeringDemand:
    """What a driver would have to do to follow this track.

    Values are unsigned. Whether a corner bends left or right is a property of where the
    harmonic phases happened to land, and the M1 human comparison was made on absolute
    steering, so signs would compare two different things.
    """

    seed: int
    required_steer: np.ndarray
    max_required: float
    percentiles: dict[float, float]
    descriptives: Descriptives = field(compare=False)


def required_steering(line: CentreLine, profile: VehicleProfile) -> SteeringDemand:
    """Steering each sample of the centre line demands, normalised to [0, 1].

    `atan(wheelbase / radius) / steer_max`, the bicycle model inverted. This is the same
    relation `vehicle.steering_for_radius` implements, applied to a whole array; it is written
    out here rather than looped over that function because the loop would cost 2000 Python
    calls per track and give an identical answer.
    """
    radius = np.asarray(line.radius, dtype=float)
    steer_max_rad = np.radians(profile.steer_max_deg)

    required = np.arctan(profile.wheelbase_m / radius) / steer_max_rad

    return SteeringDemand(
        seed=line.seed,
        required_steer=required,
        max_required=float(np.max(required)),
        percentiles={p: float(np.percentile(required, p)) for p in PERCENTILES},
        descriptives=describe(required),
    )


def reference_distribution(name: str = "track1") -> np.ndarray:
    """Absolute human steering, conditional on being non-zero.

    Read through the existing M1 loader, never through a private copy of the parsing, and
    strictly read-only: nothing here writes to the dataset or to results.

    The conditional is not a convenience. 58.6 percent of the recorded samples are exactly
    zero, because the human drove down straights; a generated harmonic loop has no straights
    at all. Comparing unconditional distributions would score a perfect track badly for the
    sole reason that it never stops turning (research C9).
    """
    # Imported here rather than at module scope so that importing this module does not pull in
    # pandas and the whole EDA package for callers that only want `describe`.
    from python.eda import loader

    dataset = loader.load_track(name)
    steering = np.abs(np.asarray(dataset.df["steering"], dtype=float))

    return steering[steering > 0.0]


@dataclass(frozen=True)
class MatchReport:
    """How close a track, or a batch of them, sits to the human data.

    `distance` is a distance and `accepted` is a threshold decision. Neither is a hypothesis
    test, and this type has no p-value field by contract (FR-019).
    """

    scope: str
    distance: float
    threshold: float
    accepted: bool
    scales: dict[str, float]
    reference: str
    n_track_samples: int
    n_reference_samples: int
    n_seeds_pooled: int
    note: str


@dataclass(frozen=True)
class DemandBound:
    """Whether a track asks for no more steering than a human was recorded supplying.

    This is what SC-010 is judged on, after the criterion was revised on measurement. The
    original asked the pooled demand to sit within a distance of the human distribution, and
    no track this generator can produce does: required steering is the geometric MINIMUM to
    follow the centre line, while the human column is steering actually applied, corrections
    and overshoot included. A human always steers more than the road demands, so the gap grows
    with every percentile and no shape of track closes it.

    A bound is what the criterion was protecting against: a track demanding more than any
    human ever had to supply would be unfair to an agent trained on that human's data.
    """

    scope: str
    within_bound: bool
    max_required: float
    reference_max: float
    exceedance_fraction: float
    percentile_gaps: dict[float, float]
    worst_percentile: float | None
    n_track_samples: int
    n_reference_samples: int
    n_seeds_pooled: int
    note: str


def demand_bound(demand: SteeringDemand | np.ndarray,
                 reference: np.ndarray | None = None,
                 scope: str | None = None,
                 n_seeds_pooled: int = 1) -> DemandBound:
    """Check that a track's demand is bounded above by the human recording.

    Bounded means two things together, because either alone is easy to satisfy trivially:
    every percentile in `BOUND_PERCENTILES` is at or below the human percentile, and no single
    sample exceeds the human maximum. A distribution can sit under the human curve at every
    percentile and still contain one impossible corner, which is exactly the case an agent
    would fail on, so the maximum is checked separately rather than inferred from P99.

    Only the upper percentiles are checked. See `BOUND_PERCENTILES`: a loop with no straights
    necessarily sits above a human at the bottom of the distribution, and that is an accepted
    property of the generator rather than a breach of this bound.
    """
    if isinstance(demand, SteeringDemand):
        values = demand.required_steer
        scope = scope or f"seed {demand.seed}"
    else:
        values = np.asarray(demand, dtype=float).ravel()
        scope = scope or "batch"

    if reference is None:
        reference = reference_distribution()

    reference_max = float(np.max(reference))

    # Positive gap means the track demands MORE than the human did at that percentile, which
    # is the direction that fails.
    gaps = {
        p: float(np.percentile(values, p) - np.percentile(reference, p))
        for p in BOUND_PERCENTILES
    }
    worst = max(gaps, key=lambda p: gaps[p])

    exceedance = float(np.mean(values > reference_max))
    within = all(g <= 0.0 for g in gaps.values()) and exceedance == 0.0

    note = (
        "SC-010 is a bound, not a distribution match. Required steering is the geometric "
        "minimum needed to follow the centre line, while the reference is steering a human "
        "actually applied, including corrections and overshoot, so the human distribution "
        "lies above the geometric one by construction. What matters is that no generated "
        "track asks for more than a human was ever recorded supplying. Both sides are taken "
        "conditional on non-zero steering (research C9). Only the upper percentiles are "
        "checked, because a loop with no straights necessarily demands more than a human at "
        "the bottom of the distribution, which is an accepted property of the generator. This "
        "is a bound check, not a hypothesis test, and no p-value is reported."
    )

    return DemandBound(
        scope=scope,
        within_bound=within,
        max_required=float(np.max(values)),
        reference_max=reference_max,
        exceedance_fraction=exceedance,
        percentile_gaps=gaps,
        worst_percentile=worst if gaps[worst] > 0.0 else None,
        n_track_samples=int(values.size),
        n_reference_samples=int(np.asarray(reference).size),
        n_seeds_pooled=n_seeds_pooled,
        note=note,
    )


def _wasserstein1(a: np.ndarray, b: np.ndarray) -> float:
    """Wasserstein-1 distance between two empirical distributions.

    Computed from the quantile functions: W1 is the area between them, which for empirical
    samples is the mean absolute difference of the sorted values evaluated on a common
    quantile grid. Written out rather than taken from SciPy so the definition is visible at
    the point where a threshold is applied to it, and so the module keeps its dependencies to
    NumPy.
    """
    a = np.sort(np.asarray(a, dtype=float).ravel())
    b = np.sort(np.asarray(b, dtype=float).ravel())

    if a.size == 0 or b.size == 0:
        raise ValueError("Wasserstein distance needs two non-empty distributions")

    # A fine common grid, at least as dense as the larger sample, so neither side is
    # coarsened to fit the other.
    grid = np.linspace(0.0, 1.0, max(a.size, b.size, 1000))
    qa = np.quantile(a, grid)
    qb = np.quantile(b, grid)

    return float(_trapezoid(np.abs(qa - qb), grid))


def match_distance(demand: SteeringDemand | np.ndarray,
                   reference: np.ndarray | None = None,
                   scope: str | None = None,
                   n_seeds_pooled: int = 1,
                   profile: VehicleProfile | None = None) -> MatchReport:
    """Distance from a track's steering demand to the human reference.

    Accepts either a single `SteeringDemand` or a raw array, so a batch can pool the demand
    across many seeds and score the pool. SC-010 is judged on the pooled figure and never on
    per-seed ones: twenty tracks each missing in a different direction average out to a good
    match, twenty all missing the same way do not, and only the pooled distance separates
    those two cases.
    """
    if isinstance(demand, SteeringDemand):
        values = demand.required_steer
        scope = scope or f"seed {demand.seed}"
    else:
        values = np.asarray(demand, dtype=float).ravel()
        scope = scope or "batch"

    if reference is None:
        reference = reference_distribution()

    distance = _wasserstein1(values, reference)

    cap = profile.max_required_steer if profile is not None else None
    note = (
        "Two limitations apply to every comparison in this module. First, no generated track "
        "can demand more steering than the profile's max_required_steer"
        + (f" ({cap:.3f})" if cap is not None else "")
        + ", because the radius floor forbids a tighter corner, while the human recording "
        "reaches 1.0. Second, no generated track contains a straight, so both sides are taken "
        "conditional on non-zero steering; an unconditional comparison would mostly measure "
        "the absence of straights rather than the driving. This is a distance against a "
        "threshold, not a hypothesis test, and no p-value is reported."
    )

    return MatchReport(
        scope=scope,
        distance=distance,
        threshold=config.MATCH_DISTANCE_THRESHOLD,
        accepted=distance <= config.MATCH_DISTANCE_THRESHOLD,
        # Carried in the report because a bare distance is unreadable: 0.041 is a good match
        # beside a 0.0231 floor and a meaningless one beside a 0.1047 ceiling, and the reader
        # should not have to go and look those up.
        scales={
            "self_consistency": config.W1_SELF_CONSISTENCY,
            "structureless": config.W1_STRUCTURELESS,
            "human_to_human": config.W1_HUMAN_TO_HUMAN,
        },
        reference="track1 |steering|, conditional on non-zero (research C9)",
        n_track_samples=int(np.asarray(values).size),
        n_reference_samples=int(np.asarray(reference).size),
        n_seeds_pooled=n_seeds_pooled,
        note=note,
    )
