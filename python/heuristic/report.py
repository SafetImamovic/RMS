"""Turn run records into the comparisons feature 005 is judged on.

Three reports come out of the same rows, and they are deliberately separate because they answer
different questions and are read at different times.

**The controller comparison** (US2). Both controllers over the same seeds, with the two smoothness
measures and the outcome measures side by side. FR-009 forbids collapsing them into a winner: a
controller that steers more smoothly and completes fewer laps is a real result, and it is the
result this feature is most likely to produce.

**The repeat check** (FR-011). The same seed and controller run several times, reporting the
spread. This is the noise floor, and it is the number every other comparison depends on. FR-015
turns on it: a difference smaller than the spread is not a finding.

**The sweep** (US3). Sensing configurations over the same seeds, each difference judged against
that noise floor rather than against zero.

Two rules that are easy to get wrong and are checked by the tests rather than left to care:

- A failed run has an empty ``lap_time_s``, not zero. Averaging zeros for failures reports a fast
  sweep, which is the same mistake as counting only successes arriving through arithmetic instead
  of through omission.
- Results are reported over the seed set with descriptive statistics, never as one seed's outcome.
  The tracks differ in difficulty by construction, so a single seed is a sample of one (FR-012,
  Constitution Principle IX).

Usage::

    python -m python.heuristic.report                      # the newest runs_*.csv
    python -m python.heuristic.report a.csv b.csv          # named files, pooled
    python -m python.heuristic.report --spread repeats.csv # noise floor from its own file

This module reads the run record. Its sibling ``sweep.py`` reads the per-step traces and predates
the record; it stays because the traces it reads are still on disk and still the only evidence for
what happened inside a run.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from python.eda import stats as eda_stats
from python.track import compare_drive
from python.track import config as track_config

REPO = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO / "results" / "heuristic"

#: The columns ``contracts/run-record.md`` fixes. A file missing any of them is refused rather
#: than read for what it has: a reader that silently tolerates a missing column reports a result
#: computed over a quantity that was never recorded.
REQUIRED_COLUMNS = (
    "seed",
    "controller",
    "ray_count",
    "ray_fov_deg",
    "ray_length_m",
    "completed_lap",
    "lap_time_s",
    "checkpoints_awarded",
    "checkpoints_total",
    "checkpoints_skipped",
    "wall_contacts",
    "end_reason",
    "steer_p95_dsteer",
    "steer_sign_changes_per_s",
    "time_scale",
    "duration_s",
)

#: The measures a difference can be claimed in, and the label each is printed under. Both
#: smoothness measures appear, and no combination of them does (FR-009).
MEASURES = (
    ("lap_time_s", "lap time (s)"),
    ("steer_p95_dsteer", "|dsteer| p95"),
    ("steer_sign_changes_per_s", "sign changes /s"),
)


@dataclass(frozen=True)
class Run:
    """One row of the run record.

    ``lap_time_s`` is ``None`` for a run that did not complete a lap, never ``0.0``. The
    distinction is the whole reason the column is allowed to be empty, and collapsing it here
    would undo it three lines after the file was read.
    """

    seed: int
    controller: str
    ray_count: int
    ray_fov_deg: float
    ray_length_m: float
    completed_lap: bool
    lap_time_s: float | None
    checkpoints_awarded: int
    checkpoints_total: int
    checkpoints_skipped: int
    wall_contacts: int
    end_reason: str
    steer_p95_dsteer: float
    steer_sign_changes_per_s: float
    time_scale: float
    duration_s: float

    @property
    def config(self) -> tuple[int, float, float]:
        """The sensing configuration, which a sweep varies and a comparison must hold."""
        return (self.ray_count, self.ray_fov_deg, self.ray_length_m)

    @property
    def config_label(self) -> str:
        return f"{self.ray_count} rays / {self.ray_fov_deg:.0f} deg / {self.ray_length_m:.0f} m"


@dataclass(frozen=True)
class Stats:
    """Descriptive statistics over one measure, with the denominator kept attached.

    ``excluded`` travels with the rest because a mean over three of thirty-four runs and a mean
    over thirty-four are different claims, and a table that prints only the mean makes them look
    like the same one.
    """

    n: int
    excluded: int
    mean: float | None
    sd: float | None
    minimum: float | None
    maximum: float | None

    @property
    def spread(self) -> float | None:
        """Max minus min. The quantity FR-015 compares a difference against."""
        if self.minimum is None or self.maximum is None:
            return None
        return self.maximum - self.minimum


def describe(values: list[float], excluded: int = 0) -> Stats:
    """Descriptive statistics that survive one value and no values.

    ``statistics.stdev`` raises below two points. A report that crashed on a controller which
    completed exactly one lap would be a report that works only when the answer is comfortable.
    """
    if not values:
        return Stats(n=0, excluded=excluded, mean=None, sd=None, minimum=None, maximum=None)

    return Stats(
        n=len(values),
        excluded=excluded,
        mean=statistics.fmean(values),
        sd=statistics.stdev(values) if len(values) >= 2 else None,
        minimum=min(values),
        maximum=max(values),
    )


class RunRecordError(ValueError):
    """The file is not a run record. Raised rather than worked around."""


def _bool(text: str) -> bool:
    return text.strip().lower() in ("true", "1", "yes")


def load_runs(path: Path) -> list[Run]:
    """Read one run record file.

    ``utf-8-sig`` for the same reason ``sweep.py`` uses it: an early writer emitted a BOM and
    those files are still on disk.
    """
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or ())]
        if missing:
            raise RunRecordError(
                f"{path.name} is missing {', '.join(missing)}. "
                "See specs/005-heuristic-ray-driver/contracts/run-record.md"
            )

        runs = []
        for line, row in enumerate(reader, start=2):
            if not (row.get("seed") or "").strip():
                continue  # trailing blank line

            lap = (row["lap_time_s"] or "").strip()
            try:
                runs.append(
                    Run(
                        seed=int(row["seed"]),
                        controller=row["controller"].strip(),
                        ray_count=int(row["ray_count"]),
                        ray_fov_deg=float(row["ray_fov_deg"]),
                        ray_length_m=float(row["ray_length_m"]),
                        completed_lap=_bool(row["completed_lap"]),
                        # Empty means no lap, and empty is not zero. Zero is a lap time, and an
                        # aggregate that averages zeros for failed runs reports a fast sweep.
                        lap_time_s=float(lap) if lap else None,
                        checkpoints_awarded=int(row["checkpoints_awarded"]),
                        checkpoints_total=int(row["checkpoints_total"]),
                        checkpoints_skipped=int(row["checkpoints_skipped"]),
                        wall_contacts=int(row["wall_contacts"]),
                        end_reason=row["end_reason"].strip(),
                        steer_p95_dsteer=float(row["steer_p95_dsteer"]),
                        steer_sign_changes_per_s=float(row["steer_sign_changes_per_s"]),
                        time_scale=float(row["time_scale"]),
                        duration_s=float(row["duration_s"]),
                    )
                )
            except ValueError as exc:
                raise RunRecordError(f"{path.name} line {line}: {exc}") from exc

    return runs


def load_many(paths: list[Path]) -> list[Run]:
    """Pool several files. A sweep may span sessions, and a session is one file."""
    runs: list[Run] = []
    for p in paths:
        runs.extend(load_runs(p))
    return runs


@dataclass(frozen=True)
class Summary:
    """One controller under one sensing configuration, over the seed set."""

    controller: str
    config: tuple[int, float, float]
    config_label: str

    runs: int
    seeds: int
    completed: int

    lap_time: Stats
    p95: Stats
    sign_changes: Stats

    wall_contacts: int
    checkpoints_skipped: int
    end_reasons: dict[str, int]

    @property
    def completion_rate(self) -> float:
        return self.completed / self.runs if self.runs else 0.0


def summarise(runs: list[Run]) -> list[Summary]:
    """Group by controller and sensing configuration, and describe each group.

    Never by seed. The tracks differ in difficulty by construction, so one seed's outcome is a
    sample of one and a table of them invites reading the easiest track as the result (FR-012).
    """
    groups: dict[tuple[str, tuple[int, float, float]], list[Run]] = {}
    for r in runs:
        groups.setdefault((r.controller, r.config), []).append(r)

    summaries = []
    for (controller, config), group in sorted(groups.items()):
        completed = [r for r in group if r.completed_lap and r.lap_time_s is not None]

        end_reasons: dict[str, int] = {}
        for r in group:
            end_reasons[r.end_reason] = end_reasons.get(r.end_reason, 0) + 1

        summaries.append(
            Summary(
                controller=controller,
                config=config,
                config_label=group[0].config_label,
                runs=len(group),
                seeds=len({r.seed for r in group}),
                completed=len(completed),
                # Lap time over completed runs only, stating how many were left out.
                lap_time=describe(
                    [r.lap_time_s for r in completed], excluded=len(group) - len(completed)
                ),
                # Both smoothness measures over every run, completed or not: how a controller
                # steers on a run it failed is exactly as measurable as on one it finished, and
                # dropping the failures would report the smoothness of the successes only.
                p95=describe([r.steer_p95_dsteer for r in group]),
                sign_changes=describe([r.steer_sign_changes_per_s for r in group]),
                wall_contacts=sum(r.wall_contacts for r in group),
                checkpoints_skipped=sum(r.checkpoints_skipped for r in group),
                end_reasons=end_reasons,
            )
        )

    return summaries


@dataclass(frozen=True)
class Spread:
    """The run-to-run noise floor (FR-011), measured by repeating one setting.

    Everything FR-015 says rests on this. It is deliberately returned as ``None`` when nothing
    was repeated rather than defaulted to zero, because a zero noise floor makes every difference
    a finding and would be the most confident possible way to be wrong.
    """

    controller: str
    seed: int
    config_label: str
    repeats: int
    mean_duration_s: float
    by_measure: dict[str, Stats]

    @property
    def sign_change_quantum(self) -> float:
        """The smallest step the sign-change measure can take: one reversal over the run.

        **Measured in T027 and the reason this property exists.** Five repeats all recorded
        exactly four reversals, so the observed spread of that column was 0.0008 per second and
        described nothing but lap-time jitter dividing the same integer. The measure cannot move
        by less than one reversal, which over a 27.3 s lap is 0.0366 per second, forty-six times
        the observed spread. Comparing against the observed range alone would call a quantisation
        step a finding.
        """
        return 1.0 / self.mean_duration_s if self.mean_duration_s > 0 else 0.0

    def threshold(self, measure: str) -> float | None:
        """What a difference in ``measure`` has to beat to be a finding.

        The observed range, except for the sign-change rate, where the integer quantum above is
        the floor. Taking the larger of the two is the honest choice: the measure is noisy by at
        least the quantum whatever the repeats happened to show.
        """
        stats = self.by_measure.get(measure)
        if stats is None or stats.spread is None:
            return None

        if measure == "steer_sign_changes_per_s":
            return max(stats.spread, self.sign_change_quantum)

        return stats.spread


def measure_spread(runs: list[Run]) -> Spread | None:
    """Spread over the largest set of runs sharing controller, seed and configuration.

    Only completed laps, and only runs that ended the same way. An interrupted run is not a
    slower lap, it is not a lap: an early estimate that mixed the two read 28.9 s where the
    comparable runs read 0.100 s, and a noise floor inflated by a factor of 289 would have buried
    every difference this feature exists to find.
    """
    groups: dict[tuple[str, int, tuple[int, float, float]], list[Run]] = {}
    for r in runs:
        if not r.completed_lap or r.lap_time_s is None:
            continue
        groups.setdefault((r.controller, r.seed, r.config), []).append(r)

    repeated = [g for g in groups.values() if len(g) >= 2]
    if not repeated:
        return None

    best = max(repeated, key=len)

    by_measure = {
        "lap_time_s": describe([r.lap_time_s for r in best]),
        "steer_p95_dsteer": describe([r.steer_p95_dsteer for r in best]),
        "steer_sign_changes_per_s": describe([r.steer_sign_changes_per_s for r in best]),
    }

    return Spread(
        controller=best[0].controller,
        seed=best[0].seed,
        config_label=best[0].config_label,
        repeats=len(best),
        mean_duration_s=statistics.fmean([r.duration_s for r in best]),
        by_measure=by_measure,
    )


@dataclass(frozen=True)
class Difference:
    """One measure, between two groups, judged against the noise floor."""

    measure: str
    label: str
    left: str
    right: str
    left_value: float | None
    right_value: float | None
    threshold: float | None

    @property
    def gap(self) -> float | None:
        if self.left_value is None or self.right_value is None:
            return None
        return abs(self.left_value - self.right_value)

    @property
    def exceeds(self) -> bool | None:
        """None when it cannot be judged, which is not the same as False."""
        if self.gap is None or self.threshold is None:
            return None
        return self.gap > self.threshold

    def sentence(self) -> str:
        """FR-015's verdict, in the words the requirement asks for."""
        if self.left_value is None or self.right_value is None:
            return (f"{self.label}: not comparable, "
                    f"{self.left if self.left_value is None else self.right} has no value")

        if self.threshold is None:
            return (f"{self.label}: {self.gap:.4f} apart, but the run-to-run spread is "
                    "unmeasured, so this is not a finding")

        if self.exceeds:
            return (f"{self.label}: {self.gap:.4f} apart, which exceeds the run-to-run spread "
                    f"of {self.threshold:.4f}")

        return (f"{self.label}: {self.gap:.4f} apart, which is smaller than the run-to-run "
                f"spread of {self.threshold:.4f}, so it is not a finding")


def _value(summary: Summary, measure: str) -> float | None:
    stats = {
        "lap_time_s": summary.lap_time,
        "steer_p95_dsteer": summary.p95,
        "steer_sign_changes_per_s": summary.sign_changes,
    }[measure]
    return stats.mean


def compare(summaries: list[Summary], spread: Spread | None) -> list[Difference]:
    """Every pair of groups, on every measure, each judged separately.

    **No pair is reduced to a winner** (FR-009). A controller that steers more smoothly and
    completes fewer laps is a real result and the one this feature is most likely to produce, so
    the measures are returned side by side and the reader does the weighing.
    """
    differences = []
    for i, left in enumerate(summaries):
        for right in summaries[i + 1:]:
            name_l = f"{left.controller} [{left.config_label}]"
            name_r = f"{right.controller} [{right.config_label}]"
            for measure, label in MEASURES:
                differences.append(
                    Difference(
                        measure=measure,
                        label=label,
                        left=name_l,
                        right=name_r,
                        left_value=_value(left, measure),
                        right_value=_value(right, measure),
                        threshold=spread.threshold(measure) if spread else None,
                    )
                )

    return differences


# --- printing --------------------------------------------------------------------------------


def _fmt(value: float | None, places: int = 4) -> str:
    return "-" if value is None else f"{value:.{places}f}"


def _print_summary(s: Summary) -> None:
    print(f"{s.controller}   [{s.config_label}]")
    print(f"  runs {s.runs} over {s.seeds} seed(s)")
    print(f"  completed  {s.completed} of {s.runs}  ({s.completion_rate:.0%})")

    lap = s.lap_time
    if lap.n:
        print(f"  lap time   n {lap.n}  mean {_fmt(lap.mean, 3)}  sd {_fmt(lap.sd, 3)}  "
              f"min {_fmt(lap.minimum, 3)}  max {_fmt(lap.maximum, 3)}"
              f"   ({lap.excluded} run(s) excluded, no lap)")
    else:
        print(f"  lap time   no completed laps, so no lap time "
              f"({lap.excluded} run(s) excluded)")

    for stats, label in ((s.p95, "|dsteer| p95"), (s.sign_changes, "sign chg/s")):
        print(f"  {label:<10} n {stats.n}  mean {_fmt(stats.mean)}  sd {_fmt(stats.sd)}  "
              f"min {_fmt(stats.minimum)}  max {_fmt(stats.maximum)}")

    per_seed = s.wall_contacts / s.seeds if s.seeds else 0.0
    skipped_per_seed = s.checkpoints_skipped / s.seeds if s.seeds else 0.0
    print(f"  contacts   {s.wall_contacts} total, {per_seed:.2f} per seed")
    print(f"  skipped    {s.checkpoints_skipped} total, {skipped_per_seed:.2f} per seed")

    reasons = ", ".join(f"{k} {v}" for k, v in sorted(s.end_reasons.items()))
    print(f"  ended      {reasons}")
    print()


def _print_spread(spread: Spread | None) -> None:
    print("RUN-TO-RUN SPREAD (FR-011)")
    print("-" * 78)

    if spread is None:
        print("  Unmeasured. No controller, seed and configuration was run twice.")
        print("  Until it is, no difference below is a finding: there is nothing to say a gap")
        print("  is larger than the noise.")
        print()
        return

    print(f"  {spread.repeats} repeats of {spread.controller} on seed {spread.seed} "
          f"[{spread.config_label}]")
    for measure, label in MEASURES:
        stats = spread.by_measure[measure]
        print(f"  {label:<16} mean {_fmt(stats.mean)}  range {_fmt(stats.spread)}  "
              f"sd {_fmt(stats.sd)}")

    quantum = spread.sign_change_quantum
    observed = spread.by_measure["steer_sign_changes_per_s"].spread
    print()
    print(f"  The sign-change rate is an integer count over a duration, so it cannot move by")
    print(f"  less than one reversal: {quantum:.4f} per second at these durations. Its observed")
    print(f"  range of {_fmt(observed)} is below that, so {quantum:.4f} is used as the floor.")
    print()


def report(runs: list[Run], spread: Spread | None) -> None:
    """Print the whole thing, in the order it has to be read.

    The spread comes before the comparison and not after it. FR-015 makes every judgement below
    conditional on it, and a reader who has already formed an opinion from a table of means is
    not going to revise it three paragraphs later.
    """
    summaries = summarise(runs)

    print(f"{len(runs)} run(s), {len(summaries)} controller/configuration group(s)")
    print()

    print("PER CONTROLLER AND CONFIGURATION (FR-012)")
    print("-" * 78)
    for s in summaries:
        _print_summary(s)

    _print_spread(spread)

    print("DIFFERENCES (FR-015)")
    print("-" * 78)
    differences = compare(summaries, spread)
    if not differences:
        print("  Only one group, so there is nothing to compare.")
        return

    pair = None
    for d in differences:
        if (d.left, d.right) != pair:
            pair = (d.left, d.right)
            print(f"  {d.left}  vs  {d.right}")
        print(f"    {d.sentence()}")

    print()
    print("  The two smoothness measures and the outcome measures are reported side by side and")
    print("  never collapsed into one verdict (FR-009). A controller that steers more smoothly")
    print("  and completes fewer laps is a real result.")


# --- the steering distribution (US4, T041-T043) ------------------------------------------------


@dataclass(frozen=True)
class SteeringDistribution:
    """One controller's steering command distribution, in M5's shape.

    **The command, resampled to `COMPARE_HZ`, exactly as features 002 and 004 report.** The
    summary type is `python.eda.stats.DistributionSummary` and the resampling is
    `python.track.compare_drive.resample`, both reused rather than reimplemented, so M5 can put
    this beside the human, BC and PPO columns without a translation step (T041).

    Two distributions, not one. The steering values say where the wheel is held; the absolute
    differences say how sharply it moves, and feature 002 reports both because a driver can sit
    at extreme angles smoothly or at modest angles violently.
    """

    controller: str
    runs: int
    seeds: int
    samples: int
    steering: eda_stats.DistributionSummary
    abs_delta_steering: eda_stats.DistributionSummary
    hist_counts: np.ndarray
    hist_edges: np.ndarray


#: Columns a trace must carry to be usable here. `controller` and `seed` were added when this
#: distribution was first attempted: without them a folder of traces from a sweep is a pile of
#: indistinguishable files.
TRACE_COLUMNS = ("t", "seed", "controller", "command_steer")


def load_trace(path: Path) -> pd.DataFrame | None:
    """Read one per-step trace, or None if it is not one this code can use.

    Returns None rather than raising for a trace written before the `seed` and `controller`
    columns existed. Several hundred of those are on disk and they are still the evidence for
    what happened inside the runs that produced them; they simply cannot say whose runs they were.
    """
    df = pd.read_csv(path, encoding="utf-8-sig")

    if any(c not in df.columns for c in TRACE_COLUMNS):
        return None

    # A run that produced almost nothing cannot contribute a distribution. `MostOpen` ends in
    # about 3 s, which is still ~150 physics steps and ~40 resampled points, so this only drops
    # traces that are effectively empty.
    return df if len(df) >= 20 else None


def resampled_commands(df: pd.DataFrame) -> np.ndarray:
    """The steering command on the COMPARE_HZ grid.

    Resampled by nearest sample through `compare_drive.resample`, which the trace's `t` column
    makes directly usable. Its docstring carries the reason it is nearest-sample rather than an
    average: averaging the 50 Hz rows inside each bin would smooth the very thing being measured
    and make every driver look calmer than it was.
    """
    return resample_to_compare_hz(df)["command_steer"].to_numpy(dtype=float)


def resample_to_compare_hz(df: pd.DataFrame) -> pd.DataFrame:
    return compare_drive.resample(df, hz=track_config.COMPARE_HZ)


def steering_distribution(traces: list[pd.DataFrame], controller: str,
                          bins: int = 40) -> SteeringDistribution | None:
    """Pool one controller's traces into the two distributions M5 needs.

    **Each run is differenced separately and the pieces concatenated**, never differenced across
    the join. Feature 002 hit this exactly: differencing across the seam between two recordings
    invents a jump that no driver made. Here the seam is between two runs on different seeds,
    where the steering resets to whatever the next run starts at.
    """
    if not traces:
        return None

    steer_parts, delta_parts = [], []
    for df in traces:
        values = resampled_commands(df)
        steer_parts.append(values)
        if values.size >= 2:
            delta_parts.append(np.abs(np.diff(values)))

    steering = np.concatenate(steer_parts)
    deltas = np.concatenate(delta_parts) if delta_parts else np.array([0.0])

    counts, edges = eda_stats.relative_frequency_histogram(steering, bins=bins)

    return SteeringDistribution(
        controller=controller,
        runs=len(traces),
        seeds=len({int(df["seed"].iloc[0]) for df in traces}),
        samples=int(steering.size),
        steering=eda_stats.describe(steering, "steering command"),
        abs_delta_steering=eda_stats.describe(deltas, "|delta steering| @ 14.08 Hz"),
        hist_counts=counts,
        hist_edges=edges,
    )


def distributions_from(directory: Path, bins: int = 40) -> list[SteeringDistribution]:
    """Every usable trace in a directory, grouped by the controller that produced it."""
    by_controller: dict[str, list[pd.DataFrame]] = {}

    for path in sorted(directory.glob("trace_*.csv")):
        df = load_trace(path)
        if df is None:
            continue
        by_controller.setdefault(str(df["controller"].iloc[0]), []).append(df)

    return [
        d
        for name, traces in sorted(by_controller.items())
        if (d := steering_distribution(traces, name, bins=bins)) is not None
    ]


def _print_summary_line(s: eda_stats.DistributionSummary) -> None:
    """Sample size, mean, variance, min, max, and the percentiles (Principle IX, T042)."""
    print(f"  {s.variable}")
    print(f"    n {s.n}   mean {s.mean:+.4f}   variance {s.variance:.5f}   sd {s.std:.4f}")
    print(f"    min {s.minimum:+.4f}   max {s.maximum:+.4f}")
    pct = "  ".join(f"p{int(p)} {v:+.4f}" for p, v in sorted(s.percentiles.items()))
    print(f"    {pct}")


def _print_histogram(counts: np.ndarray, edges: np.ndarray, width: int = 44) -> None:
    """A relative-frequency histogram, printed rather than plotted (Principle IX, T042).

    Text because this report is read in a terminal beside the tables it belongs to. A saved PNG
    would be a second artefact to keep in step with the numbers next to it.
    """
    peak = counts.max() if counts.size else 0.0
    if peak <= 0:
        return

    print("    relative frequency of the steering command")
    for i, share in enumerate(counts):
        if share <= 0:
            continue
        bar = "#" * max(1, int(round(share / peak * width)))
        print(f"      [{edges[i]:+.3f}, {edges[i + 1]:+.3f})  {share:6.3f}  {bar}")


def report_distributions(distributions: list[SteeringDistribution]) -> None:
    print("STEERING COMMAND DISTRIBUTION (US4, FR-019)")
    print("-" * 78)

    if not distributions:
        print("  No usable traces. A trace written before the seed and controller columns")
        print("  existed cannot say which controller produced it, and is skipped rather than")
        print("  pooled into whichever distribution happened to be built first.")
        print()
        return

    for d in distributions:
        print(f"{d.controller}   {d.runs} run(s) over {d.seeds} seed(s), "
              f"{d.samples} samples at {track_config.COMPARE_HZ} Hz")
        _print_summary_line(d.steering)
        _print_summary_line(d.abs_delta_steering)
        _print_histogram(d.hist_counts, d.hist_edges)
        print()

    print("  Reported in the shape features 002 and 004 use, from the same DistributionSummary")
    print("  and the same COMPARE_HZ resampling, so M5 places this beside the human, BC and PPO")
    print("  columns without converting anything (T041).")
    print()


# --- against the learned driver (US4 scenario 2, T043) -----------------------------------------

#: Feature 004's balanced run, which is the one M5 carries as the BC column. Its
#: `distributions.json` is read rather than recomputed: recomputing here would put a second
#: definition of the same statistic in the repository, which is the drift research R5 warned
#: about and the reason feature 004 computes no statistic of its own either.
LEARNED_DISTRIBUTIONS = REPO / "results" / "bc" / "run_bc_balanced_v01" / "distributions.json"

#: The scope to take from that file. `pooled` is both recordings together; feature 004 reports
#: `track1data` and `track2data` alongside it and forbids a pooled-only path, so both are read
#: and the per-track ones are printed under the pooled comparison rather than hidden.
LEARNED_SCOPES = ("pooled", "track1data", "track2data")


@dataclass(frozen=True)
class LearnedDriver:
    """The BC column, as feature 004 wrote it to disk."""

    run_id: str
    scope: str
    abs_delta_steering: eda_stats.DistributionSummary
    steering: eda_stats.DistributionSummary


def _summary_from_json(entry: dict, variable: str) -> eda_stats.DistributionSummary:
    return eda_stats.DistributionSummary(
        variable=variable,
        n=int(entry["n"]),
        mean=float(entry["mean"]),
        std=float(entry["std"]),
        variance=float(entry["variance"]),
        minimum=float(entry["minimum"]),
        maximum=float(entry["maximum"]),
        percentiles={float(p): float(v) for p, v in entry["percentiles"].items()},
    )


def load_learned(path: Path = LEARNED_DISTRIBUTIONS) -> list[LearnedDriver]:
    """Feature 004's steering distributions, one per scope, or [] if they are not on disk.

    Returns [] rather than raising when the file is absent. The learned driver is another
    feature's artefact and this report must still produce its own three sections without it;
    what it must not do is silently omit the comparison, so the caller says the file was
    missing (T043).
    """
    if not path.exists():
        return []

    entries = json.loads(path.read_text(encoding="utf-8"))
    run_id = path.parent.name.removeprefix("run_")

    by_key = {(e["name"], e["scope"]): e for e in entries}
    learned = []
    for scope in LEARNED_SCOPES:
        delta = by_key.get(("abs_delta_predicted", scope))
        steer = by_key.get(("predicted_steering", scope))
        if delta is None or steer is None:
            continue
        learned.append(LearnedDriver(
            run_id=run_id,
            scope=scope,
            abs_delta_steering=_summary_from_json(delta, f"|delta steering| ({scope})"),
            steering=_summary_from_json(steer, f"steering command ({scope})"),
        ))
    return learned


#: The statistics of `|delta steering|` both sides define identically, and the only ones a
#: cross-driver claim may be made in. Named rather than taken from the summary wholesale, so a
#: statistic that means different things on the two sides cannot arrive by iteration.
CROSS_MEASURES = (
    ("mean", lambda s: s.mean),
    ("p50", lambda s: s.percentiles[50]),
    ("p95", lambda s: s.percentiles[95]),
    ("p99", lambda s: s.percentiles[99]),
    ("max", lambda s: s.maximum),
)


@dataclass(frozen=True)
class CrossClaim:
    """One statistic of `|delta steering|`, on both drivers, with the gap between them."""

    measure: str
    scripted: float
    learned: float

    @property
    def gap(self) -> float:
        return abs(self.scripted - self.learned)

    @property
    def scripted_is_smoother(self) -> bool:
        return self.scripted < self.learned


def compare_to_learned(distribution: SteeringDistribution,
                       learned: LearnedDriver) -> list[CrossClaim]:
    """The scripted driver's per-step steering change beside the learned driver's.

    **Only `|delta steering|` crosses.** The steering command itself is measured on different
    roads by two drivers that never met: a mean of -0.20 on a generated loop that turns mostly
    one way says nothing when placed against a mean of -0.02 on the Udacity recordings. Its
    statistics are printed for M5 to carry, and no claim is made in them.
    """
    return [
        CrossClaim(measure=name,
                   scripted=get(distribution.abs_delta_steering),
                   learned=get(learned.abs_delta_steering))
        for name, get in CROSS_MEASURES
    ]


def report_against_learned(distributions: list[SteeringDistribution],
                           learned: list[LearnedDriver],
                           spread: Spread | None) -> None:
    """State plainly wherever the scripted driver beats the learned one (US4 scenario 2)."""
    print("AGAINST THE LEARNED DRIVER (US4 scenario 2, T043)")
    print("-" * 78)

    if not learned:
        print(f"  No learned column at {LEARNED_DISTRIBUTIONS}. The comparison is missing")
        print("  because the artefact is missing, which is a different statement from the")
        print("  scripted driver having nothing to compare, and is said rather than skipped.")
        print()
        return

    pooled = learned[0]
    print(f"  Learned column: {pooled.run_id}, predicted steering on the unbalanced validation")
    print(f"  set, scope {pooled.scope}. It is a distribution over frames the HUMAN drove.")
    print()
    for column in learned:
        _print_summary_line(column.abs_delta_steering)
    print()

    for d in distributions:
        claims = compare_to_learned(d, pooled)
        print(f"  |delta steering| per step: {d.controller} against {pooled.run_id}")
        print(f"    {'':>6}  {'scripted':>9}  {'learned':>9}   gap")
        for c in claims:
            side = "scripted lower" if c.scripted_is_smoother else "learned lower"
            print(f"    {c.measure:>6}  {c.scripted:9.4f}  {c.learned:9.4f}   "
                  f"{c.gap:.4f}, {side}")

        wins = [c.measure for c in claims if c.scripted_is_smoother]
        losses = [c.measure for c in claims if not c.scripted_is_smoother]
        if wins:
            print(f"    **Smoother than the learned driver at {', '.join(wins)}.**")
            print("    Reported because it was measured, not because it is the expected")
            print("    direction (US4 scenario 2).")
        if losses:
            print(f"    Rougher at {', '.join(losses)}, said in the same breath.")
        print()

    print("  **Smoothness alone ranks a crash highly**, which is why it is never read apart")
    print("  from the outcome measures above it (FR-009). A controller that commits to one")
    print("  command and holds it moves the wheel by nothing between steps, so a p50 of")
    print("  0.0000 beside a completion rate of 0 percent is a driver going straight into a")
    print("  wall, not a calm one.")
    print()

    p95_threshold = spread.threshold("steer_p95_dsteer") if spread is not None else None
    if p95_threshold is not None:
        print(f"  Judged against the scripted side's run-to-run spread of {p95_threshold:.4f}")
        print("  on the p95 (FR-011). **The learned side has no such number**: every gap above")
        print("  larger than that clears one side's noise floor and is unjudged against the")
        print("  other's. Feature 004 measured a reproduction tolerance of 0.0005 and")
        print("  recorded that it applies to the best-epoch validation error and to nothing")
        print("  else, so a gap here is above one side's noise floor and unjudged against the")
        print("  other's.")
    else:
        print("  The scripted side's run-to-run spread is unmeasured here, so no gap above is")
        print("  a finding yet (FR-015).")
    print()

    print("  Three things this comparison is not, each of which would make it wrong:")
    print("    - **The learned driver never drives.** Feature 004 FR-018 records it: the model")
    print("      reacts to frames the human produced, and the next frame is the human's doing.")
    print("      So lap completion, wall contacts and lap time have no learned column at all.")
    print("      The scripted driver's 34 of 34 is not a win over the learned one; it is a")
    print("      measure the learned one does not have.")
    print("    - **Different roads.** The scripted figures come from generated Unity tracks and")
    print("      the learned ones from the Udacity recordings. Both steering columns are the")
    print("      command in [-1, 1], so they are the same quantity, of two different problems.")
    print("    - **Nearly, not exactly, the same clock.** The scripted side is resampled to")
    print(f"      {track_config.COMPARE_HZ} Hz, which is track1's median frame rate; the")
    print("      learned side is differenced per validation frame, so it sits at that rate on")
    print("      track1 by construction and above it on track2. The per-track learned rows")
    print("      are printed above for exactly this reason.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Report the heuristic run records.")
    parser.add_argument("files", nargs="*", type=Path,
                        help="run record CSVs. Defaults to the newest runs_*.csv.")
    parser.add_argument("--dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--spread", type=Path, default=None,
                        help="take the run-to-run spread from this file instead of the runs")
    parser.add_argument("--traces", type=Path, default=None, nargs="?", const=RUNS_DIR,
                        help="also report the steering distribution from the traces in this "
                             "directory (US4). Defaults to results/heuristic when given bare.")
    parser.add_argument("--learned", type=Path, default=LEARNED_DISTRIBUTIONS,
                        help="feature 004's distributions.json, placed beside the scripted "
                             "driver when --traces is given (T043).")
    args = parser.parse_args()

    paths = args.files
    if not paths:
        found = sorted(args.dir.glob("runs_*.csv"))
        if not found:
            print(f"no run records in {args.dir}")
            return
        paths = [found[-1]]

    runs = load_many(paths)
    if not runs:
        print("no runs in " + ", ".join(p.name for p in paths))
        return

    print("read " + ", ".join(p.name for p in paths))
    print()

    spread_runs = load_runs(args.spread) if args.spread else runs
    spread = measure_spread(spread_runs)
    report(runs, spread)

    if args.traces is not None:
        distributions = distributions_from(args.traces)
        print()
        report_distributions(distributions)
        if distributions:
            report_against_learned(distributions, load_learned(args.learned), spread)


if __name__ == "__main__":
    main()
