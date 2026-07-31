"""Hold a Unity drive log against the M1 envelope (FR-009).

The question this module answers is narrow: **does the simulated car move the way the
recorded human drove?** Not "is it good driving", not "is the difference significant" -
only whether each measured quantity lands inside a band that M1 established.

Three rules shape everything here, and each of them exists because the obvious
implementation would be wrong:

1. **Resample before differencing** (research C14). The dataset's 95th-percentile steering
   change of 0.30 was measured at 14.08 frames per second. Unity writes its log at the
   physics rate, 50 Hz. Differencing that log frame by frame and comparing the result to
   0.30 measures the difference in sampling rate, not in driving - it would report roughly
   a third of the truth.

2. **Never convert a speed into a physical unit** (FR-004, research C3). The recorded
   ``speed`` column has no documented unit. Every speed comparison here goes through a
   ratio or a division by the log's own P99, so no conversion factor is ever assumed.

3. **No p-values** (FR-019). A large drive log makes any difference "significant"; the
   question is whether the difference is large enough to matter, which is a threshold
   question. Nothing in this module returns a test statistic or a probability.

Usage::

    python -m python.track.compare_drive results/drive_logs/2026-07-30_18-22-04.csv
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from python.track import config
from python.track.vehicle import build_profile

# The columns a drive log must carry. Same names as the dataset's own columns, so that no
# renaming step sits between the two sides of the comparison (FR-008).
REQUIRED_COLUMNS: tuple[str, ...] = ("t", "steering", "throttle", "brake", "speed")


# =============================================================================================
# Percentiles
# =============================================================================================


def percentile(values: np.ndarray, q: float) -> float:
    """Nearest-rank percentile, matching the in-editor HUD exactly.

    NumPy's default is linear interpolation between order statistics. The C# HUD uses
    nearest rank, because interpolating requires sorting into a new array and the HUD
    recomputes several times a second. If the two used different definitions, the panel the
    driver watches and the report they run afterwards would disagree slightly on the same
    drive, and there would be no way to tell which one was wrong.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan")

    ordered = np.sort(arr)
    rank = math.ceil((q / 100.0) * ordered.size) - 1
    return float(ordered[min(max(rank, 0), ordered.size - 1)])


# =============================================================================================
# Loading and resampling
# =============================================================================================


def load_drive_log(path: str | Path) -> pd.DataFrame:
    """Read a drive log written by DriveLogger, checking it has what we need."""
    path = Path(path)
    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing column(s) {missing}. "
            f"Expected {list(REQUIRED_COLUMNS)} as written by DriveLogger.cs"
        )

    if len(df) < 2:
        raise ValueError(f"{path.name} has {len(df)} rows; a drive needs at least two.")

    if not df["t"].is_monotonic_increasing:
        raise ValueError(
            f"{path.name} has a non-monotonic t column. Rows were reordered or two runs "
            "were concatenated; either way no per-frame quantity can be trusted."
        )

    return df


def raw_rate_hz(df: pd.DataFrame) -> float:
    """The rate the log was written at, from the median gap between rows.

    Median rather than mean, for the same reason feature 002 used it on the dataset: one
    long gap from a stalled frame would drag a mean and misreport the whole recording.
    """
    gaps = np.diff(df["t"].to_numpy(dtype=float))
    gaps = gaps[gaps > 0]
    if gaps.size == 0:
        return float("nan")
    return 1.0 / float(np.median(gaps))


def resample(df: pd.DataFrame, hz: float = config.COMPARE_HZ) -> pd.DataFrame:
    """Resample a drive log onto a uniform grid at ``hz`` by nearest sample.

    **Nearest sample, deliberately not averaging.** Averaging the 50 Hz rows that fall
    inside each 14.08 Hz bin would smooth the signal, and the thing being measured is how
    sharply the steering moves. Smoothing first would push the 95th-percentile steering
    change down and make every drive look calmer than it was. Nearest-sample is also what
    the dataset's own recorder did: it sampled the simulator state at its frame times, it
    did not integrate between them.
    """
    if hz <= 0:
        raise ValueError(f"hz must be positive, got {hz}")

    t = df["t"].to_numpy(dtype=float)
    step = 1.0 / hz
    grid = np.arange(t[0], t[-1] + 1e-9, step)

    # Index of the sample nearest each grid time.
    right = np.searchsorted(t, grid)
    right = np.clip(right, 1, t.size - 1)
    left = right - 1
    take_left = (grid - t[left]) <= (t[right] - grid)
    idx = np.where(take_left, left, right)

    out = df.iloc[idx].reset_index(drop=True)
    out["t"] = grid
    return out


# =============================================================================================
# Normalisation
# =============================================================================================


def normalise_speed(speed: np.ndarray) -> np.ndarray:
    """Divide a speed series by its own 99th percentile.

    This is the *only* operation applied to a speed anywhere in M2. There is deliberately
    no function in this codebase that converts a dataset speed into m/s, mph or anything
    else: the recorded column carries no unit, so any such factor would be invented, and an
    invented factor inside a comparison produces a number that looks like evidence and is
    not (FR-004, research C3).

    P99 rather than the maximum, so a single overshoot does not set the scale for the whole
    drive.
    """
    arr = np.asarray(speed, dtype=float)
    p99 = percentile(np.abs(arr), 99.0)
    if not np.isfinite(p99) or p99 <= 1e-9:
        return np.zeros_like(arr)
    return arr / p99


# =============================================================================================
# Turning circle (T022, SC-004)
# =============================================================================================


@dataclass(frozen=True)
class TurningCircle:
    """A circle fitted to the path the car actually drove at full lock."""

    radius_m: float
    centre_x: float
    centre_z: float
    residual_m: float
    n_samples: int
    duration_s: float
    mean_abs_steer: float

    def agrees_with(self, r_min_m: float, tolerance: float = 0.10) -> bool:
        """SC-004: the driven circle must match the derived minimum within 10 percent."""
        if not np.isfinite(self.radius_m) or r_min_m <= 0:
            return False
        return abs(self.radius_m - r_min_m) / r_min_m <= tolerance


def fit_circle(x: np.ndarray, z: np.ndarray) -> tuple[float, float, float, float]:
    """Least-squares circle through a set of points. Returns (cx, cz, r, residual).

    Algebraic (Kasa) fit: a circle satisfies ``x^2 + z^2 = 2*cx*x + 2*cz*z + k``, which is
    linear in the unknowns, so the fit is one lstsq call with no starting guess and no
    iteration to fail to converge.

    The residual is returned because the fit alone cannot be trusted: a straight line has a
    perfectly good best-fit circle, one of enormous radius, and it would otherwise be
    reported as a measurement rather than as the absence of one.
    """
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    if x.size < 3:
        return (float("nan"),) * 4

    a = np.column_stack([2 * x, 2 * z, np.ones_like(x)])
    b = x**2 + z**2
    (cx, cz, k), *_ = np.linalg.lstsq(a, b, rcond=None)

    r_sq = k + cx**2 + cz**2
    if r_sq <= 0:
        return (float("nan"),) * 4
    r = math.sqrt(r_sq)

    residual = float(np.sqrt(np.mean((np.hypot(x - cx, z - cz) - r) ** 2)))
    return float(cx), float(cz), float(r), residual


def measure_turning_circle(
    df: pd.DataFrame,
    min_abs_steer: float = 0.95,
    min_duration_s: float = 2.0,
) -> TurningCircle | None:
    """Measure the circle the car drove during its longest sustained full-lock turn.

    Returns None when the drive contains no such turn, which is a different answer from a
    bad measurement and has to stay distinguishable from one: it means "go and drive a
    circle", not "the car turns wrongly".

    Needs the ``x`` and ``z`` columns, so it only works on logs written after those were
    added to DriveLogger.
    """
    if not {"x", "z"}.issubset(df.columns):
        return None

    steer = df["steering"].to_numpy(dtype=float)
    t = df["t"].to_numpy(dtype=float)
    at_lock = np.abs(steer) >= min_abs_steer
    if not at_lock.any():
        return None

    # Longest continuous run of full lock. Longest rather than first, because the first is
    # usually the driver discovering the key and the longest is the deliberate circle.
    best_start = best_len = cur_start = cur_len = 0
    for i, on in enumerate(at_lock):
        if on:
            if cur_len == 0:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_start, best_len = cur_start, cur_len
        else:
            cur_len = 0

    if best_len < 3:
        return None

    sl = slice(best_start, best_start + best_len)
    duration = float(t[sl][-1] - t[sl][0])
    if duration < min_duration_s:
        return None

    cx, cz, r, residual = fit_circle(df["x"].to_numpy(float)[sl], df["z"].to_numpy(float)[sl])
    return TurningCircle(
        radius_m=r,
        centre_x=cx,
        centre_z=cz,
        residual_m=residual,
        n_samples=int(best_len),
        duration_s=duration,
        mean_abs_steer=float(np.mean(np.abs(steer[sl]))),
    )


# =============================================================================================
# Report types
# =============================================================================================


@dataclass(frozen=True)
class QuantityResult:
    """One measured quantity held against one band."""

    name: str
    measured: float
    low: float
    high: float
    reference: str
    note: str = ""

    @property
    def inside(self) -> bool:
        return bool(self.low <= self.measured <= self.high)

    def line(self) -> str:
        mark = "OK  " if self.inside else "FAIL"
        return (
            f"  {mark} {self.name:<26} {self.measured:8.4f}   "
            f"band [{self.low:.4f}, {self.high:.4f}]   {self.reference}"
        )


@dataclass(frozen=True)
class DriveComparison:
    """Everything measured about one drive log."""

    path: str
    source: str
    reference_track: str
    n_rows_raw: int
    n_rows_resampled: int
    duration_s: float
    raw_hz: float
    compare_hz: float
    results: list[QuantityResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    circle: TurningCircle | None = None
    r_min_m: float = 0.0

    @property
    def passed(self) -> bool:
        return all(r.inside for r in self.results)

    @property
    def failing(self) -> list[str]:
        """Names of the quantities outside their band. FR-009 requires naming them."""
        return [r.name for r in self.results if not r.inside]

    def report(self) -> str:
        lines = [
            f"Drive log: {self.path}",
            f"  source={self.source}  rows={self.n_rows_raw:,} at {self.raw_hz:.1f} Hz  "
            f"duration={self.duration_s:.1f}s",
            f"  resampled to {self.compare_hz:.2f} Hz -> {self.n_rows_resampled:,} rows "
            f"(reference: {self.reference_track})",
            "",
        ]
        lines.extend(r.line() for r in self.results)
        lines.append("")

        # SC-004. Reported separately from the envelope quantities because it is not one:
        # it needs a specific manoeuvre rather than a minute of ordinary driving, so a drive
        # without one is incomplete rather than failing.
        if self.circle is None:
            lines.append(
                "  turning circle: no sustained full-lock turn in this drive. "
                "Hold A or D at low speed for a few seconds to measure it (T022)."
            )
        else:
            c = self.circle
            ok = c.agrees_with(self.r_min_m)
            lines.append(
                f"  {'OK  ' if ok else 'FAIL'} turning circle             "
                f"{c.radius_m:8.3f} m  vs r_min {self.r_min_m:.3f} m  "
                f"({100 * (c.radius_m - self.r_min_m) / self.r_min_m:+.1f}%)"
            )
            lines.append(
                f"       fitted over {c.duration_s:.1f}s at mean |steer| "
                f"{c.mean_abs_steer:.3f}, path residual {c.residual_m:.3f} m"
            )
            if c.residual_m > 0.5:
                lines.append(
                    "       ! residual is large; the path was not a clean circle, "
                    "so this radius is not a measurement to trust."
                )
        lines.append("")

        if self.warnings:
            lines.extend(f"  ! {w}" for w in self.warnings)
            lines.append("")
        if self.passed:
            lines.append("VERDICT: inside the M1 envelope on every quantity.")
        else:
            lines.append(f"VERDICT: outside on {', '.join(self.failing)}.")
        return "\n".join(lines)


# =============================================================================================
# The comparison
# =============================================================================================


def compare(
    df: pd.DataFrame,
    path: str = "<dataframe>",
    reference_track: str = "track1",
    hz: float = config.COMPARE_HZ,
) -> DriveComparison:
    """Measure a drive log against the M1 envelope.

    ``reference_track`` selects which recording the steering-rate band comes from. It
    defaults to track1 because that is the profile the generated tracks target (research
    C8). The two recordings differ from each other by a factor of 2.33, so there is no
    single human figure to compare against and pretending otherwise would be the mistake.
    """
    if reference_track not in ("track1", "track2"):
        raise ValueError(f"reference_track must be track1 or track2, got {reference_track!r}")

    warnings: list[str] = []
    raw_hz = raw_rate_hz(df)

    # Upsampling would invent frames that were never recorded, and every per-frame delta
    # computed from them would be smaller than the truth. Worth shouting about.
    #
    # The 0.1 percent tolerance is not slack: a log already written at exactly the
    # comparison rate has gaps that are 1/hz only to floating-point accuracy, so a bare
    # `<` fires on the one input that is beyond reproach.
    if np.isfinite(raw_hz) and raw_hz < hz * 0.999:
        warnings.append(
            f"log rate {raw_hz:.1f} Hz is BELOW the comparison rate {hz:.2f} Hz. "
            "Resampling up invents frames and deflates every per-frame change; "
            "these numbers understate the real steering activity."
        )

    res = resample(df, hz)
    steering = res["steering"].to_numpy(dtype=float)
    speed = res["speed"].to_numpy(dtype=float)

    d_steer = np.abs(np.diff(steering))
    norm_speed = normalise_speed(speed)
    d_speed = np.abs(np.diff(norm_speed))

    if d_steer.size < 30:
        warnings.append(
            f"only {d_steer.size} resampled steps; percentiles below are unstable. "
            f"Drive for at least {30 / hz:.0f}s."
        )

    dsteer_target = (
        config.DATASET_DSTEER_P95_TRACK1
        if reference_track == "track1"
        else config.DATASET_DSTEER_P95_TRACK2
    )

    # The dataset's speed-change figure lives in dataset units. Dividing it by the dataset's
    # own P99 puts it on the same normalised scale as the drive log's, which is the only
    # scale on which the two may be compared at all.
    dspeed_target = config.DATASET_DSPEED_P95 / config.DATASET_SPEED_P99

    speed_shape = float("nan")
    p99 = percentile(np.abs(speed), 99.0)
    if np.isfinite(p99) and p99 > 1e-9:
        speed_shape = float(np.max(np.abs(speed))) / p99
    dataset_shape = config.DATASET_SPEED_MAX / config.DATASET_SPEED_P99

    results = [
        # SC-002. Both extremes, so a drive that only ever turned right does not pass.
        QuantityResult(
            name="steer max (right)",
            measured=float(np.max(steering)) if steering.size else float("nan"),
            low=config.DATASET_STEER_ABS_MAX - 0.01,
            high=config.DATASET_STEER_ABS_MAX + 0.01,
            reference="full lock, both recordings",
        ),
        QuantityResult(
            name="steer max (left)",
            measured=float(np.min(steering)) if steering.size else float("nan"),
            low=-(config.DATASET_STEER_ABS_MAX + 0.01),
            high=-(config.DATASET_STEER_ABS_MAX - 0.01),
            reference="full lock, both recordings",
        ),
        # FR-005, the headline figure. A factor of two, not a target.
        QuantityResult(
            name="P95 |dsteer|",
            measured=percentile(d_steer, 95.0),
            low=dsteer_target / 2.0,
            high=dsteer_target * 2.0,
            reference=f"{reference_track} P95 {dsteer_target:.2f} at {hz:.2f} Hz",
            note="factor of two, because the two recordings differ by 2.33x (research C4)",
        ),
        # SC-005. A cap, so the lower bound is zero rather than a band.
        QuantityResult(
            name="max |dsteer|",
            measured=float(np.max(d_steer)) if d_steer.size else float("nan"),
            low=0.0,
            high=config.DATASET_DSTEER_MAX + 1e-4,
            reference=f"recorded max {config.DATASET_DSTEER_MAX:.2f}",
        ),
        # SC-003, unit free.
        QuantityResult(
            name="speed max/P99",
            measured=speed_shape,
            low=dataset_shape * 0.90,
            high=dataset_shape * 1.10,
            reference=f"dataset {dataset_shape:.3f} +-10%",
            note="a ratio, so no speed unit is assumed (FR-004)",
        ),
        # FR-007. Acceleration and braking, on the normalised scale for the same reason.
        QuantityResult(
            name="P95 |dspeed| (norm)",
            measured=percentile(d_speed, 95.0),
            low=dspeed_target / 2.0,
            high=dspeed_target * 2.0,
            reference=f"dataset {dspeed_target:.4f} at {hz:.2f} Hz",
            note="both sides divided by their own P99 speed",
        ),
    ]

    source = str(res["source"].iloc[0]) if "source" in res.columns and len(res) else "unknown"
    t = df["t"].to_numpy(dtype=float)

    # Fitted on the RAW log, not the resampled one. Resampling exists to make per-frame
    # differences comparable against a 14.08 Hz recording; a circle is a shape in space and
    # gains nothing from being thinned to a third of its points.
    circle = measure_turning_circle(df)
    profile = build_profile()

    return DriveComparison(
        path=str(path),
        source=source,
        reference_track=reference_track,
        n_rows_raw=len(df),
        n_rows_resampled=len(res),
        duration_s=float(t[-1] - t[0]),
        raw_hz=raw_hz,
        compare_hz=hz,
        results=results,
        warnings=warnings,
        circle=circle,
        r_min_m=profile.r_min_m,
    )


def compare_file(
    path: str | Path,
    reference_track: str = "track1",
    hz: float = config.COMPARE_HZ,
) -> DriveComparison:
    """Load a drive log and compare it. The one-call entry point."""
    return compare(load_drive_log(path), path=str(path), reference_track=reference_track, hz=hz)


# =============================================================================================
# Command line
# =============================================================================================


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m python.track.compare_drive",
        description="Hold a Unity drive log against the M1 envelope (FR-009).",
    )
    parser.add_argument("csv", help="drive log written by DriveLogger.cs")
    parser.add_argument(
        "--reference",
        choices=("track1", "track2"),
        default="track1",
        help="which recording the steering-rate band comes from (default: track1)",
    )
    parser.add_argument(
        "--hz",
        type=float,
        default=config.COMPARE_HZ,
        help=f"comparison rate (default: {config.COMPARE_HZ}, the median track1 frame rate)",
    )
    args = parser.parse_args(argv)

    try:
        comparison = compare_file(args.csv, reference_track=args.reference, hz=args.hz)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(comparison.report())
    return 0 if comparison.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
