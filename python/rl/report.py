"""The learned column of the M5 comparison, in the shape the other columns already use.

Feature 005 produced the scripted column, feature 004 the imitation column, and M1 the human one.
This module produces the fourth from the same kind of file, using the same functions, so that the
comparison is between drivers rather than between measurement methods.

What is measured, both from the per-step traces rather than from the run record, because the record
carries one summary number per run and M5 needs the distribution behind it:

- The **steering command** the policy issued, resampled to ``config.COMPARE_HZ`` through
  ``python.track.compare_drive.resample``.
- The **per-step \\|delta steering\\|** on that same grid.

Two rules that are easy to get wrong and are checked by the tests:

- **Each run is differenced separately**, and only then concatenated. Differencing across the seam
  between two runs invents a steering jump no driver made, which is the error feature 002 hit at
  the track1 and track2 junction.
- A failed run has an **empty** ``lap_time_s``, not zero. Averaging zeros for failures reports a
  fast driver, which is the same mistake as counting only the successes, arriving through
  arithmetic instead of through omission.

Every figure comes from ``python.eda.stats.describe``, the function that described the human column
in M1 and the BC column in M4. Nothing here computes a statistic of its own, and the comparison
against the human distribution uses a test rather than a pair of histograms, which is what
Principle IX and FR-024 both ask for.

**The losses are reported.** The scripted driver completes 34 of 34 training seeds at a steering
variance of 0.04994. If the learned driver is worse on a measure, this module names the measure and
prints the number (FR-024, SC-007).

Runs under ``.venv``.

Usage::

    python -m python.rl.report results/rl/<runs file> --traces results/rl/<traces dir>
"""


from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from python.eda import config as eda_config
from python.eda.authenticity import chi2_homogeneity
from python.eda.stats import DistributionSummary, describe
from python.track import compare_drive
from python.track import config as track_config

# The scripted driver's published figures, from feature 005. Quoted rather than recomputed:
# they are what SC-007 asks the learned column to be placed beside, and recomputing them here
# would let this module disagree with the document that published them.
SCRIPTED_LAPS = "34 of 34"
SCRIPTED_STEER_VARIANCE = 0.04994

# The dataset's steering lattice: 0.05 apart over [-1, 1], which feature 002 established is what
# the human column actually is. Both distributions are counted on this support so the comparison
# is between drivers rather than between binnings.
LATTICE_STEP = 0.05


@dataclass(frozen=True)
class DriverColumn:
    """One driver's column of the M5 comparison."""

    name: str
    runs: int
    laps_completed: int
    steering: DistributionSummary
    abs_delta_steering: DistributionSummary

    # Feature 007. Lap completion alone cannot tell a policy that drives a quarter of the lap and
    # crashes from one that never moves: both score zero laps. Feature 006's learned column read
    # 0 of 10 laps AND 0.00 markers, and this feature's reads 0 of 10 laps and 6.20 markers, which
    # is the entire difference between the two runs and is invisible without this field.
    markers_mean: float

    # Markers in a WHOLE recorded run, being one lap's markers times `laps_to_complete`. Not one
    # lap's worth: a run that finishes is three laps in `Evaluation.unity` (feature 009).
    markers_possible: int
    end_reasons: dict

    # Feature 008. A driver that reaches further while touching more barriers is a different
    # driver from one that reaches further cleanly, and the lap count says neither.
    wall_contacts_mean: float

    # The values behind the summaries. Kept because the homogeneity test needs counts over the
    # lattice, and a DistributionSummary cannot be un-summarised back into them.
    steering_values: np.ndarray
    abs_delta_values: np.ndarray

    # How many laps a recorded run is. Carried so a reader of the column knows whether "24 markers"
    # meant a whole run or a third of one, which is the difference between M3's columns and M5's.
    # Last, and defaulted, because every field above it is required and a dataclass cannot put a
    # defaulted field before an undefaulted one.
    laps_to_complete: int = 1

    @property
    def lap_rate(self) -> float:
        return self.laps_completed / self.runs if self.runs else float("nan")

    @property
    def marker_rate(self) -> float:
        """Markers taken as a share of the lap, which is what a zero lap count hides."""
        return self.markers_mean / self.markers_possible if self.markers_possible else float("nan")


def load_trace_dir(directory: Path) -> list[pd.DataFrame]:
    """Every trace in a directory, one frame per run, in sorted order.

    **One file per run, and that is a requirement rather than a convention.** A single file
    covering a whole sweep has one monotonic ``t`` across every run in it, so the seams are
    invisible and the per-run differencing below cannot happen. ``DrivingAgent`` opens and
    closes the trace per run for this reason.
    """
    paths = sorted(p for p in directory.glob("*.csv"))
    if not paths:
        raise ValueError(f"no traces in {directory}")
    return [compare_drive.load_drive_log(p) for p in paths]


def steering_series(
    frames: list[pd.DataFrame], hz: float = track_config.COMPARE_HZ
) -> tuple[np.ndarray, np.ndarray]:
    """The steering command and the per-step |delta steering|, both at ``hz``.

    **Each run is resampled and differenced on its own, and only then concatenated.** The
    alternative - concatenating first - puts a difference across the seam between two runs,
    which invents a steering change no driver made. Feature 002 hit exactly that at the
    track1/track2 junction, and the tests here pin the correct order.

    The difference is taken AFTER resampling, so the quantity is the change between two
    samples the comparison actually looks at. Differencing at the raw 50 Hz and then
    resampling would report changes over a step the comparison never uses.
    """
    steer_parts: list[np.ndarray] = []
    delta_parts: list[np.ndarray] = []

    for df in frames:
        resampled = compare_drive.resample(df, hz)
        steer = resampled["steering"].to_numpy(dtype=float)
        steer_parts.append(steer)
        # np.diff drops one sample per run, which is correct: the first sample of a run has no
        # predecessor within that run, and borrowing one from the previous run is the seam bug.
        delta_parts.append(np.abs(np.diff(steer)))

    return np.concatenate(steer_parts), np.concatenate(delta_parts)


def lattice_support(step: float = LATTICE_STEP) -> np.ndarray:
    """The steering lattice, -1 to +1 inclusive."""
    n = int(round(2.0 / step))
    return np.round(np.linspace(-1.0, 1.0, n + 1), 10)


def counts_on_lattice(values: np.ndarray, support: np.ndarray) -> np.ndarray:
    """Count ``values`` into the nearest lattice point.

    Nearest point rather than a histogram with its own edges, because the human column IS on
    this lattice: binning it any other way would split one real support point across two bins and
    manufacture a difference the drivers do not have.
    """
    idx = np.abs(values[:, None] - support[None, :]).argmin(axis=1)
    return np.bincount(idx, minlength=support.size).astype(float)


def load_runs(path: Path) -> pd.DataFrame:
    """The run record, with the empty-not-zero rule preserved.

    ``lap_time_s`` arrives as NaN for a failed run because the writer left the field empty.
    That is load-bearing: filling it with zero would let a mean over the column report a fast
    driver, which is the same error as counting only the successes.
    """
    df = pd.read_csv(path)
    if "lap_time_s" in df and df["lap_time_s"].dtype == object:
        df["lap_time_s"] = pd.to_numeric(df["lap_time_s"], errors="coerce")
    return df


def build_column(name: str, runs_path: Path, traces_dir: Path) -> DriverColumn:
    runs = load_runs(runs_path)
    frames = load_trace_dir(traces_dir)
    steer, delta = steering_series(frames)

    # "true" and "1" both appear in committed run records, because the writer changed between
    # features and the older files were not rewritten.
    completed = runs["completed_lap"].astype(str).str.lower().isin(("true", "1"))

    # `checkpoints_total` is the markers in ONE lap. A recorded run is `lapsToComplete` laps, which
    # is 3 in `Evaluation.unity`, so a finished run awards 72 against a total of 24 and the naive
    # denominator prints "72.00 of 24 (300.0% of a lap)". Harmless while nothing finished a lap,
    # which is every run of M3; wrong on the page as soon as one does.
    #
    # The lap count is a scene setting and is not in the run record, so it is INFERRED from the
    # finished runs rather than passed in: a completed run awarded exactly `total * laps`. Every
    # completed run must agree, and a disagreement raises instead of picking one, because two lap
    # counts in one sweep means the rows did not come from one configuration.
    #
    # With nothing completed there is nothing to infer from, and the denominator falls back to a
    # single lap. That is what M3's columns were read as, so their published figures are unchanged.
    per_lap = 0
    if "checkpoints_total" in runs and len(runs):
        per_lap = int(runs["checkpoints_total"].iloc[0])

    laps_to_complete = 1
    if per_lap and completed.any() and "checkpoints_awarded" in runs:
        ratios = {
            int(round(float(a) / per_lap)) for a in runs.loc[completed, "checkpoints_awarded"]
        }
        if len(ratios) > 1:
            raise ValueError(
                f"{name}: completed runs imply more than one lap count {sorted(ratios)}; "
                "the rows are not from one configuration"
            )
        laps_to_complete = max(ratios.pop(), 1)

    possible = per_lap * laps_to_complete

    return DriverColumn(
        name=name,
        runs=len(runs),
        laps_completed=int(completed.sum()),
        steering=describe(steer, "steering"),
        abs_delta_steering=describe(delta, "abs_delta_steering"),
        markers_mean=float(runs["checkpoints_awarded"].mean()) if "checkpoints_awarded" in runs else float("nan"),
        markers_possible=possible,
        laps_to_complete=laps_to_complete,
        end_reasons=dict(runs["end_reason"].value_counts()) if "end_reason" in runs else {},
        wall_contacts_mean=float(runs["wall_contacts"].mean()) if "wall_contacts" in runs else float("nan"),
        steering_values=steer,
        abs_delta_values=delta,
    )


def human_steering(dataset_csv: Path) -> np.ndarray:
    """The human steering column, from the dataset's headerless driving_log."""
    cols = ["center", "left", "right", "steering", "throttle", "brake", "speed"]
    df = pd.read_csv(dataset_csv, header=None, names=cols)
    return df["steering"].to_numpy(dtype=float)


def compare_to_human(
    learned: np.ndarray, human: np.ndarray, scope: str, alpha: float = eda_config.ALPHA
):
    """A test, not a pair of histograms (Principle IX, FR-024).

    ``chi2_homogeneity`` is the same test feature 002 used to ask whether two tracks share one
    steering distribution, reused here for the same question about two drivers. Reusing it
    rather than writing a new one keeps the M5 comparison arguing about drivers instead of
    about methods.
    """
    support = lattice_support()
    return chi2_homogeneity(
        counts_on_lattice(learned, support),
        counts_on_lattice(human, support),
        support,
        alpha=alpha,
        scope=scope,
    )


def _fmt(s: DistributionSummary) -> str:
    return (
        f"n={s.n:>7d}  mean={s.mean:+.4f}  sd={s.std:.4f}  var={s.variance:.5f}  "
        f"p95={s.percentiles[95]:+.4f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", type=Path, help="the run record CSV for this driver")
    parser.add_argument("--traces", type=Path, required=True, help="directory of per-run traces")
    parser.add_argument("--name", default="learned", help="what to call this column")
    parser.add_argument("--dataset", type=Path, default=None, help="driving_log.csv for the human column")
    args = parser.parse_args(argv)

    column = build_column(args.name, args.runs, args.traces)

    print(f"=== {column.name} ===")
    print(f"runs              {column.runs}")
    print(f"laps completed    {column.laps_completed} of {column.runs}   "
          f"(scripted: {SCRIPTED_LAPS})")
    print(f"markers           {column.markers_mean:.2f} of {column.markers_possible}   "
          f"({100 * column.marker_rate:.1f}% of "
          f"{'a lap' if column.laps_to_complete == 1 else f'{column.laps_to_complete} laps'})")
    print(f"end reasons       {column.end_reasons}")
    print(f"wall contacts     {column.wall_contacts_mean:.2f} per run")
    print(f"steering          {_fmt(column.steering)}")
    print(f"|delta steering|  {_fmt(column.abs_delta_steering)}")

    # The loss, named rather than left for the reader to notice (FR-024, SC-007).
    print()
    if column.laps_completed == 0:
        print(f"LOSS  lap completion: {column.laps_completed} of {column.runs} against the "
              f"scripted driver's {SCRIPTED_LAPS}.")
        # Said in the same breath as the loss, because a reader who stops at the lap count cannot
        # tell "drove a quarter of the lap" from "never moved", and those are different results.
        if column.markers_mean > 0:
            print(f"      It reached {column.markers_mean:.2f} of {column.markers_possible} "
                  f"markers on the way, so the loss is where it stopped and not that it never "
                  f"started.")
        else:
            print(f"      It reached no marker at all, so the policy never made progress rather "
                  f"than failing late.")
    # Written when the learned column always lost, and it could only report a loss. Feature 009's
    # policy is the steadier of the two, 0.03208 against 0.04994, so the comparison now reports
    # either direction. The caveat below travels with both, because it is what feature 006 learned:
    # steering variance alone cannot tell a driver that laps from one that never moves.
    variance = column.steering.variance
    if variance > SCRIPTED_STEER_VARIANCE:
        print(f"steering variance {variance:.5f} against the scripted driver's "
              f"{SCRIPTED_STEER_VARIANCE:.5f}: the learned steering is the LESS settled of "
              f"the two.")
    elif variance < SCRIPTED_STEER_VARIANCE:
        print(f"steering variance {variance:.5f} against the scripted driver's "
              f"{SCRIPTED_STEER_VARIANCE:.5f}: the learned steering is the MORE settled of "
              f"the two.")
    else:
        print(f"steering variance {variance:.5f}, equal to the scripted driver's.")
    print("      Read with the lap count, never alone: a driver that never moves also has low "
          "steering variance (feature 006, rl_steering.md).")

    if args.dataset is not None:
        human = human_steering(args.dataset)
        result = compare_to_human(column.steering_values, human, scope=column.name)
        print()
        print(f"chi2 homogeneity vs human: statistic={result.statistic:.1f} "
              f"dof={result.dof} critical={result.critical_value:.1f} "
              f"p={result.p_value:.3g} alpha={result.alpha} "
              f"reject_null={result.reject_null} pooled={result.n_categories_pooled}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
