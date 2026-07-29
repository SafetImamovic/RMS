"""Provenance and integrity checks on the driving log (feature 002, US1 + US2).

"Friziranje podataka" = tampering with a dataset so it looks better, tidier or more
convenient than it really is: dropping the bad runs, copying a good stretch to inflate the
row count, gluing two recordings together, hand-"fixing" values.

Every function here answers one question of the form *"if someone had done X, what would the
data look like?"* - and then measures whether the data looks like that. A check without a
stated expected signature proves nothing, so each one carries its signature in the docstring.

All functions are pure: they read a TrackDataset and return plain values. Nothing here
writes to disk (only `authenticity.run_authenticity` writes, and only under results/).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from . import config
from .loader import TrackDataset, _basename

# The recorder names frames  <cam>_YYYY_MM_DD_HH_MM_SS_mmm.jpg  - the capture time is the
# only clock the dataset carries, so the whole timeline analysis rests on this pattern.
_TS_PATTERN = re.compile(r"(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_\d{3})")
_TS_FORMAT = "%Y_%m_%d_%H_%M_%S_%f"

# How many example row indices to keep when something is flagged. Enough to go and look,
# not so many that the JSON report becomes a data dump.
_MAX_EXAMPLES = 20


# =======================================================================================
# Entities
# =======================================================================================
@dataclass(frozen=True)
class RecordingSession:
    """One contiguous run of driving-log records - the unit over which time is meaningful.

    Sessions are contiguous and non-overlapping in ROW INDEX, but may invert in TIME: the
    combined file lists track1 first, yet track2 was recorded earlier the same day. Nothing
    downstream may assume `start_time` is ordered by `start_index` (research A1).
    """

    session_id: str
    start_index: int
    end_index: int  # inclusive
    n_rows: int
    start_time: datetime | None
    end_time: datetime | None


@dataclass(frozen=True)
class TimelineReport:
    """Per-session verdict on recording continuity (FR-001..FR-003)."""

    session_id: str
    n_rows: int
    n_unparseable: int
    is_monotonic: bool
    n_order_violations: int
    median_interval_s: float
    implied_fps: float
    gap_threshold_s: float
    n_gaps: int
    gap_tiers: dict[str, int]
    largest_gap_s: float
    start_time: datetime | None
    end_time: datetime | None
    order_violation_examples: list[int] = field(default_factory=list)
    gap_examples: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class DuplicationReport:
    """Three duplicate classes, counted separately because each implies a different act.

    They are never summed. Class 3 is expected and benign on a 41-level steering lattice;
    merging it with classes 1 and 2 manufactures a false alarm (research A8).
    """

    source: str
    n_exact_duplicate_rows: int
    n_duplicate_image_refs: int
    n_duplicate_measurement_tuples: int
    duplicate_row_examples: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class GranularityProfile:
    """How finely one numeric column was actually recorded (FR-006..FR-008)."""

    column: str
    n_distinct: int
    classification: str  # "discrete" | "continuous" | "constant"
    is_lattice: bool
    spacing: float | None
    support: list[float] | None
    unobserved_support: list[float] = field(default_factory=list)
    off_lattice_values: list[float] = field(default_factory=list)
    tolerance: float = config.LATTICE_ATOL
    # Largest distance from any observed value to its nearest lattice point. Reported always,
    # so a reader can see how much of the tolerance was actually consumed rather than having
    # to trust that the tolerance was set honestly.
    max_residual: float = 0.0
    evidence: str = ""


@dataclass(frozen=True)
class PlausibilityReport:
    """Robust screen on per-frame speed change (FR-005, research A7)."""

    session_id: str
    median_accel: float
    mad_accel: float
    max_abs_accel: float
    outlier_threshold: float
    n_outliers: int
    outlier_indices: list[int] = field(default_factory=list)
    units_note: str = ""


# =======================================================================================
# Foundational: sessions and capture times
# =======================================================================================
def parse_capture_times(ds: TrackDataset) -> tuple[pd.Series, int]:
    """Extract capture timestamps from the centre-image filenames.

    Returns `(times, n_unparseable)`. Rows whose filename carries no timestamp come back as
    NaT and are COUNTED - a caller can never mistake "no failures" for "failures were
    quietly dropped" (FR-001).
    """
    names = ds.df["center"].astype(str).map(_basename)
    stamps = names.str.extract(_TS_PATTERN, expand=False)
    times = pd.to_datetime(stamps, format=_TS_FORMAT, errors="coerce")
    n_unparseable = int(times.isna().sum())
    return times, n_unparseable


def _session_labels(ds: TrackDataset) -> pd.Series:
    """Label each row with the recording it came from, read off the image path.

    The recorder wrote absolute paths from its own machine
    (`Desktop\\track1data\\IMG\\...`), so the folder name survives in the CSV and tells us
    which run a row belongs to. A path matching no known marker is labelled `unknown`,
    which keeps a foreign file analysable as a single session instead of crashing.
    """
    paths = ds.df["center"].astype(str).str.replace("\\", "/", regex=False)

    def label(p: str) -> str:
        for marker in config.SESSION_PATH_MARKERS:
            if marker in p:
                return marker
        return "unknown"

    return paths.map(label)


def split_sessions(ds: TrackDataset) -> list[RecordingSession]:
    """Segment a source into contiguous recording sessions (FR-002, research A1).

    track1 and track2 yield one session each; the combined file yields two. Sessions are
    derived from the data, never assumed - and a session boundary is a hard wall: no
    timeline or plausibility figure is ever computed across one.
    """
    labels = _session_labels(ds)
    times, _ = parse_capture_times(ds)

    # A new session starts wherever the label changes. Comparing to the previous row keeps
    # this contiguous: if a label reappeared later it would be a separate session, which is
    # the honest reading of "the file interleaves two recordings".
    changed = labels.ne(labels.shift())
    starts = list(np.flatnonzero(changed.to_numpy()))
    bounds = starts + [len(ds.df)]

    sessions: list[RecordingSession] = []
    for i, start in enumerate(starts):
        end = bounds[i + 1] - 1  # inclusive
        window = times.iloc[start : end + 1].dropna()
        sessions.append(
            RecordingSession(
                session_id=str(labels.iloc[start]),
                start_index=int(start),
                end_index=int(end),
                n_rows=int(end - start + 1),
                start_time=window.iloc[0].to_pydatetime() if len(window) else None,
                end_time=window.iloc[-1].to_pydatetime() if len(window) else None,
            )
        )
    return sessions


def _session_times(ds: TrackDataset, session: RecordingSession) -> pd.Series:
    """Capture times inside one session, unparseable rows dropped, row labels kept.

    Keeping the original row labels means every index we report later points at a real row
    of the CSV, which is what someone re-checking the finding needs.
    """
    times, _ = parse_capture_times(ds)
    times.index = ds.df.index
    return times.iloc[session.start_index : session.end_index + 1].dropna()


# =======================================================================================
# US1 - provenance and integrity audit
# =======================================================================================
def check_timeline(ds: TrackDataset) -> list[TimelineReport]:
    """Is each recording continuous and complete? (FR-003)

    Expected signatures (research A2):
      * rows reordered      -> time stops running forwards (monotonicity breaks)
      * a block cut out     -> ONE large gap, order otherwise intact
      * single rows deleted -> MANY small gaps clustered near 2x the median interval

    So the whole interval distribution is reported, not only the maximum. The gap threshold
    is derived from the data (`GAP_FACTOR x median`), never guessed, and everything is
    computed PER SESSION - measuring across the combined file's junction would report a
    ~-80 minute jump in a perfectly sound dataset (research A1).
    """
    _, n_unparseable_total = parse_capture_times(ds)
    sessions = split_sessions(ds)
    reports: list[TimelineReport] = []

    for session in sessions:
        times = _session_times(ds, session)
        n_unparseable = session.n_rows - len(times)

        deltas = times.diff().dropna()
        dt = deltas.dt.total_seconds().to_numpy()
        labels = deltas.index.to_numpy()

        if dt.size == 0:
            reports.append(
                TimelineReport(
                    session_id=session.session_id,
                    n_rows=session.n_rows,
                    n_unparseable=n_unparseable,
                    is_monotonic=True,
                    n_order_violations=0,
                    median_interval_s=0.0,
                    implied_fps=0.0,
                    gap_threshold_s=0.0,
                    n_gaps=0,
                    gap_tiers={">2x": 0, ">5x": 0, ">1s": 0},
                    largest_gap_s=0.0,
                    start_time=session.start_time,
                    end_time=session.end_time,
                )
            )
            continue

        violations = dt <= 0
        n_violations = int(violations.sum())

        # Median over the forward steps only. On sound data every step is forward so this
        # is just the median; on reordered data it keeps the cadence estimate meaningful
        # instead of letting the negative steps drag it to nonsense.
        forward = dt[dt > 0]
        median_interval = float(np.median(forward)) if forward.size else 0.0
        gap_threshold = config.GAP_FACTOR * median_interval

        tiers = {
            ">2x": int(np.sum(dt > 2 * median_interval)) if median_interval else 0,
            ">5x": int(np.sum(dt > 5 * median_interval)) if median_interval else 0,
            ">1s": int(np.sum(dt > 1.0)),
        }
        is_gap = dt > gap_threshold if gap_threshold else np.zeros_like(dt, dtype=bool)

        reports.append(
            TimelineReport(
                session_id=session.session_id,
                n_rows=session.n_rows,
                n_unparseable=n_unparseable,
                is_monotonic=bool(n_violations == 0),
                n_order_violations=n_violations,
                median_interval_s=median_interval,
                implied_fps=(1.0 / median_interval) if median_interval else 0.0,
                gap_threshold_s=gap_threshold,
                n_gaps=int(is_gap.sum()),
                gap_tiers=tiers,
                largest_gap_s=float(dt.max()),
                start_time=session.start_time,
                end_time=session.end_time,
                order_violation_examples=[int(i) for i in labels[violations][:_MAX_EXAMPLES]],
                gap_examples=[int(i) for i in labels[is_gap][:_MAX_EXAMPLES]],
            )
        )

    # Sanity: the per-session unparseable counts must add up to the whole-source count, so
    # a row can never be lost between the split and the report.
    assert sum(r.n_unparseable for r in reports) == n_unparseable_total
    return reports


def check_duplicates(ds: TrackDataset) -> DuplicationReport:
    """Three duplicate classes, counted separately and never summed (FR-004, research A8).

    1. identical whole row      -> copying rows to inflate the dataset size
    2. repeated image path      -> the same frame written more than once
    3. repeated (steering, throttle, brake, speed) on a DIFFERENT frame
                                -> expected and benign: with 41 steering levels the value
                                   space is small, so collisions happen on their own

    Reporting one merged "duplicates" number would let class 3 masquerade as class 1 and
    turn a sound dataset into a false alarm.
    """
    df = ds.df
    original_columns = [c for c in config.COLUMN_NAMES if c in df.columns]

    dup_rows = df.duplicated(subset=original_columns, keep="first")
    dup_images = df["center"].duplicated(keep="first")
    dup_tuples = df.duplicated(subset=config.NUMERIC_COLUMNS, keep="first")

    # Class 3 is specifically "same numbers, different frame" - a row that also repeats its
    # image belongs to class 1/2 and must not be counted here as well.
    tuples_only = dup_tuples & ~dup_images

    return DuplicationReport(
        source=ds.name,
        n_exact_duplicate_rows=int(dup_rows.sum()),
        n_duplicate_image_refs=int(dup_images.sum()),
        n_duplicate_measurement_tuples=int(tuples_only.sum()),
        duplicate_row_examples=[int(i) for i in df.index[dup_rows][:_MAX_EXAMPLES]],
    )


def implied_acceleration(ds: TrackDataset) -> dict[str, np.ndarray]:
    """Per-session `delta speed / delta t`, keyed by session id.

    Exposed separately from `check_plausibility` so the notebook (and the test that shows
    why MAD beats standard deviation) can work with the raw quantity.
    """
    out: dict[str, np.ndarray] = {}
    for session in split_sessions(ds):
        times = _session_times(ds, session)
        speed = ds.df.loc[times.index, "speed"].to_numpy(dtype=float)
        dt = times.diff().dropna().dt.total_seconds().to_numpy()
        dv = np.diff(speed)
        with np.errstate(divide="ignore", invalid="ignore"):
            accel = np.where(dt > 0, dv / dt, np.nan)
        out[session.session_id] = accel[~np.isnan(accel)]
    return out


def check_plausibility(ds: TrackDataset) -> list[PlausibilityReport]:
    """Does the speed column move the way a real vehicle's speed moves? (FR-005)

    The criterion is deliberately RELATIVE. The `speed` column's unit is undocumented in the
    Udacity format, so a claim like "the acceleration stays under 1 g" would rest on an
    assumption we cannot check - and false precision is worse than an honest relative
    measure. What we can say is which steps stand out against the rest of the same
    recording, which is exactly the signature of splicing or deleting rows.

    Robust by construction: a few injected jumps inflate the standard deviation enough that
    a `k x sigma` band swallows them. The median absolute deviation does not move
    (research A7).
    """
    reports: list[PlausibilityReport] = []

    for session in split_sessions(ds):
        times = _session_times(ds, session)
        row_labels = times.index.to_numpy()
        speed = ds.df.loc[times.index, "speed"].to_numpy(dtype=float)
        dt = times.diff().dropna().dt.total_seconds().to_numpy()
        dv = np.diff(speed)

        valid = dt > 0
        accel = np.full(dt.shape, np.nan)
        accel[valid] = dv[valid] / dt[valid]
        # Each step is attributed to the row it LANDS on, so a reported index points at the
        # frame carrying the implausible value.
        landing = row_labels[1:]

        finite = accel[np.isfinite(accel)]
        if finite.size == 0:
            reports.append(
                PlausibilityReport(
                    session_id=session.session_id,
                    median_accel=0.0,
                    mad_accel=0.0,
                    max_abs_accel=0.0,
                    outlier_threshold=0.0,
                    n_outliers=0,
                    units_note=_UNITS_NOTE,
                )
            )
            continue

        median = float(np.median(finite))
        mad = float(np.median(np.abs(finite - median)))
        deviation = np.abs(accel - median)

        # A zero MAD means the recording has no robust spread at all; then any deviation
        # whatsoever stands out, and saying so is more honest than reporting nothing.
        band = config.ACCEL_MAD_K * mad
        is_outlier = np.where(np.isfinite(accel), deviation > band, False)

        reports.append(
            PlausibilityReport(
                session_id=session.session_id,
                median_accel=median,
                mad_accel=mad,
                max_abs_accel=float(np.max(np.abs(finite))),
                # The upper edge of the |a - median| <= k x MAD band, reported so a reader
                # can see the number the rule actually used.
                outlier_threshold=median + band,
                n_outliers=int(is_outlier.sum()),
                outlier_indices=[int(i) for i in landing[is_outlier][:_MAX_EXAMPLES]],
                units_note=_UNITS_NOTE,
            )
        )

    return reports


_UNITS_NOTE = (
    "The unit of the speed column is not documented in the Udacity format, so this screen "
    "is RELATIVE: it flags steps that stand out against the rest of the same recording. It "
    "makes no absolute physical claim."
)


# =======================================================================================
# US2 - measurement granularity
# =======================================================================================
# Candidate lattice steps are grouped at 1e-12 before taking the most common one: four
# orders of magnitude finer than LATTICE_ATOL, and four coarser than float noise (~1e-16),
# so it separates genuinely different steps without splitting one step into many.
_SPACING_DECIMALS = 12


def _dedupe(sorted_values: np.ndarray, atol: float) -> np.ndarray:
    """Collapse values that differ by less than the tolerance into one.

    Necessary before measuring the step: 0.05 is not exactly representable, so two values
    that are both "0.15" can differ by 1e-17. Without this, the smallest observed step
    would be that float noise rather than the real lattice step.
    """
    kept = [sorted_values[0]]
    for value in sorted_values[1:]:
        if value - kept[-1] > atol:
            kept.append(value)
    return np.asarray(kept)


def _lattice_spacing(unique_values: np.ndarray) -> float | None:
    """The most common step between neighbouring distinct values.

    Research A3 proposes the *smallest* step. That is right when the column is intact, but
    it is exactly the statistic a tampered value destroys: one number nudged by 0.023 makes
    the smallest step 0.023 and the whole column stops looking like a lattice, hiding the
    culprit instead of naming it. The most common step survives a handful of edits, so the
    offending values can be pointed at individually - which is the finding we want.
    """
    if unique_values.size < 2:
        return None
    diffs = np.round(np.diff(unique_values), _SPACING_DECIMALS)
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return None
    steps, counts = np.unique(diffs, return_counts=True)
    return float(steps[int(np.argmax(counts))])


def profile_granularity(ds: TrackDataset) -> list[GranularityProfile]:
    """How finely was each numeric column actually recorded? (FR-006..FR-008)

    This is the question M1 never asked, and it changes what a correct test looks like.
    Steering turns out to live on a 0.05 lattice with 41 possible values - a *discrete*
    variable. Fitting a smooth density to it is misspecified by construction, so M1's
    chi-square rejection was a property of the model, not a discovery about the data.

    Expected signature of tampering: a value that is NOT an integer multiple of the step in
    an otherwise perfect lattice. That means someone computed a new number - smoothing,
    interpolation, augmentation - and wrote it back (research A3).
    """
    atol = config.LATTICE_ATOL
    profiles: list[GranularityProfile] = []

    for column in config.NUMERIC_COLUMNS:
        if column not in ds.df.columns:
            continue
        values = ds.df[column].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        observed = _dedupe(np.unique(values), atol) if values.size else np.array([])
        n_distinct = int(observed.size)

        if n_distinct == 0:
            profiles.append(
                GranularityProfile(
                    column=column,
                    n_distinct=0,
                    classification="constant",
                    is_lattice=False,
                    spacing=None,
                    support=None,
                    tolerance=atol,
                    evidence="no finite values in this column",
                )
            )
            continue

        if n_distinct == 1:
            # No variation at all. Anything needing a spread is undefined here, so this is
            # reported as a finding rather than pushed through a statistic (FR-013).
            profiles.append(
                GranularityProfile(
                    column=column,
                    n_distinct=1,
                    classification="constant",
                    is_lattice=False,
                    spacing=None,
                    support=None,
                    tolerance=atol,
                    evidence=(
                        f"one distinct value ({observed[0]:g}) in all {values.size:,} rows "
                        "- constant; statistics that need variation are not computed on it"
                    ),
                )
            )
            continue

        if n_distinct > config.DISCRETE_MAX_DISTINCT:
            profiles.append(
                GranularityProfile(
                    column=column,
                    n_distinct=n_distinct,
                    classification="continuous",
                    is_lattice=False,
                    spacing=None,
                    support=None,
                    tolerance=atol,
                    evidence=(
                        f"{n_distinct:,} values distinct at tolerance {atol:g} "
                        f"(> {config.DISCRETE_MAX_DISTINCT}) - recorded at full float "
                        "resolution, treated as continuous"
                    ),
                )
            )
            continue

        spacing = _lattice_spacing(observed)
        if spacing is None or spacing <= 0:
            profiles.append(
                GranularityProfile(
                    column=column,
                    n_distinct=n_distinct,
                    classification="continuous",
                    is_lattice=False,
                    spacing=None,
                    support=None,
                    tolerance=atol,
                    evidence=f"{n_distinct} distinct values, no repeating step found",
                )
            )
            continue

        residual = np.abs(observed - spacing * np.round(observed / spacing))
        off_lattice = observed[residual > atol]
        is_lattice = bool(off_lattice.size == 0)
        max_residual = float(residual.max())

        # Support spans observed min..max ON the lattice, so a level that simply never came
        # up is listed as unobserved rather than silently shrinking the support.
        lo = int(np.round(observed[0] / spacing))
        hi = int(np.round(observed[-1] / spacing))
        support = [float(np.round(k * spacing, _SPACING_DECIMALS)) for k in range(lo, hi + 1)]
        unobserved = [
            point
            for point in support
            if not np.any(np.abs(observed - point) <= atol)
        ]

        classification = "discrete" if is_lattice else "continuous"
        if is_lattice:
            evidence = (
                f"{n_distinct} distinct values, every one an integer multiple of "
                f"{spacing:g} within {atol:g} (largest residual {max_residual:.3g}) - a "
                f"lattice with {len(support)} support points, {len(unobserved)} of them "
                "never observed"
            )
        else:
            evidence = (
                f"{n_distinct} distinct values on an otherwise regular {spacing:g} step, "
                f"but {off_lattice.size} value(s) are NOT integer multiples of it (largest "
                f"residual {max_residual:.3g} vs tolerance {atol:g}) - the signature of "
                "recomputed values written back into the log"
            )

        profiles.append(
            GranularityProfile(
                column=column,
                n_distinct=n_distinct,
                classification=classification,
                is_lattice=is_lattice,
                spacing=spacing,
                support=support,
                unobserved_support=unobserved,
                off_lattice_values=[float(v) for v in off_lattice],
                tolerance=atol,
                max_residual=max_residual,
                evidence=evidence,
            )
        )

    return profiles
