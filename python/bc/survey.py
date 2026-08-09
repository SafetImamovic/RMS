"""Phase 2 reconnaissance for M4: measure the things the design decisions depend on.

This module exists because of what it found. The first plan for the train/validation split
was session-level holdout, chosen so the leak-free property would need no parameter. Running
this survey killed that plan before any training code was written: the combined recording
contains exactly two sessions, one per track, and the largest gap in either is 0.5 s. There
was nothing to cut on.

Everything here is read-only measurement. It trains nothing, writes nothing outside
`results/bc/`, and touches no file under `dataset/`.

**This module deliberately does not import torch.** It needs pandas and `python.eda`, both of
which live in `.venv`, so the reconnaissance runs before `.venv-bc` exists and Phase 1 does
not block Phase 2. Keep it that way: the moment this imports torch, the survey can only run
in an environment that has to be built first.

Run it with:

    .venv/Scripts/python.exe -m python.bc.survey

Writes `results/bc/session_survey.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from python.eda import config as eda_config
from python.eda import integrity, loader, stats
from python.eda.loader import TrackDataset

# =========================================================================================
# Candidate values swept by the survey.
#
# These are deliberately NOT in bc/config.py. This module is what produces the decision;
# reading the decided value back in would make the survey agree with itself by construction.
# bc/config.py holds what was chosen, this holds what was considered.
# =========================================================================================

AUTOCORR_LAGS_S: tuple[float, ...] = (0.07, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)
CANDIDATE_GUARDS_S: tuple[float, ...] = (3.0, 5.0, 8.0)
CANDIDATE_BLOCKS: tuple[tuple[int, int], ...] = ((5, 1), (10, 2), (20, 4))

# Near-zero bands for the balancing decision. The steering column is lattice-valued at a step
# of 0.05 (feature 002), so a band edge between two lattice points would be arbitrary: these
# sit ON lattice points, and 0.0 is its own case because exact zero is most of the mass.
CANDIDATE_ZERO_BANDS: tuple[float, ...] = (0.0, 0.05, 0.10, 0.15)

# Candidate side-camera offset policies. The constant is what DESIGN 6.1 inherited from the
# PilotNet convention; the ranges are what replaced it once the constant was measured to park
# 40.6 percent of training targets on two lattice points.
CANDIDATE_OFFSETS: tuple[tuple[float, float], ...] = (
    (0.20, 0.20),  # the original constant
    (0.15, 0.25),
    (0.10, 0.30),
    (0.05, 0.35),
)

REPORT_PATH: Path = eda_config.REPO_ROOT / "results" / "bc" / "session_survey.md"


@dataclass(frozen=True)
class GuardCost:
    """What one (guard, blocks, holdout) setting costs, in rows."""

    guard_s: float
    n_blocks: int
    n_holdout: int
    n_train: int
    n_val: int
    n_guard: int

    @property
    def total(self) -> int:
        return self.n_train + self.n_val + self.n_guard

    @property
    def discard_fraction(self) -> float:
        return self.n_guard / self.total if self.total else 0.0

    @property
    def val_fraction(self) -> float:
        kept = self.n_train + self.n_val
        return self.n_val / kept if kept else 0.0


def _fps(ds: TrackDataset) -> float:
    """Frames per second, taken from the timeline check rather than assumed.

    Every conversion from seconds to rows in this module goes through this. Hard-coding
    14.08 would silently produce the wrong guard width on any other recording.
    """
    reports = integrity.check_timeline(ds)
    rates = [r.implied_fps for r in reports if r.implied_fps > 0]
    return float(np.median(rates)) if rates else 1.0


def steering_autocorrelation(ds: TrackDataset,
                             lags_s: tuple[float, ...] = AUTOCORR_LAGS_S
                             ) -> pd.DataFrame:
    """Correlation of the steering column with itself at a delay, per session.

    This is what the guard width is derived from. Two frames close in time carry nearly the
    same steering value, so a validation frame sitting beside a training frame is scored on
    something the model has effectively already seen. The lag at which this falls to roughly
    zero is the shortest guard that makes the two sides independent.

    Computed **within** a session, never across one. A correlation spanning the boundary
    between two recordings would be comparing track1's driving against track2's.
    """
    fps = _fps(ds)
    steering = ds.df["steering"].to_numpy(dtype=float)
    sessions = integrity.split_sessions(ds)

    rows = []
    for lag_s in lags_s:
        lag_rows = max(1, int(round(lag_s * fps)))
        entry: dict[str, object] = {"lag_s": lag_s, "lag_rows": lag_rows}

        for session in sessions:
            values = steering[session.start_index : session.end_index + 1]
            entry[session.session_id] = _pearson_at_lag(values, lag_rows)

        rows.append(entry)

    return pd.DataFrame(rows)


def _pearson_at_lag(values: np.ndarray, lag: int) -> float:
    """Pearson correlation between a series and itself shifted by `lag` samples."""
    if lag >= len(values) - 10:
        return float("nan")

    left = values[:-lag].astype(float)
    right = values[lag:].astype(float)
    left = left - left.mean()
    right = right - right.mean()

    denominator = np.sqrt((left * left).sum()) * np.sqrt((right * right).sum())
    if denominator <= 0:
        return float("nan")

    return float((left * right).sum() / denominator)


def held_out_blocks(n_blocks: int, n_holdout: int) -> set[int]:
    """Which block indices are held out, spread evenly rather than taken from one end.

    Evenly spaced matters. Two adjacent held-out blocks are one long contiguous stretch of
    road, which could be a single corner repeated, and the validation error would then
    describe that corner rather than the track.
    """
    if n_holdout <= 0 or n_blocks <= 0:
        return set()

    return {int(round(i * n_blocks / n_holdout)) % n_blocks for i in range(n_holdout)}


def guard_cost(ds: TrackDataset, guard_s: float, n_blocks: int,
               n_holdout: int) -> GuardCost:
    """Rows kept and discarded under one block-holdout setting.

    The guard is removed from **both** sides of every boundary. Removing it only from the
    validation side would leave training frames sitting right against the cut, and temporal
    adjacency is symmetric: it does not matter which side of the boundary the near-duplicate
    is on.
    """
    fps = _fps(ds)
    guard_rows = int(round(guard_s * fps))
    sessions = integrity.split_sessions(ds)

    n_train = n_val = n_guard = 0

    for session in sessions:
        size = session.n_rows
        block_len = size // n_blocks
        hold = held_out_blocks(n_blocks, n_holdout)

        for block in range(n_blocks):
            lo = block * block_len
            hi = size if block == n_blocks - 1 else (block + 1) * block_len
            length = hi - lo

            if block in hold:
                kept = max(0, length - 2 * guard_rows)
                n_val += kept
                n_guard += length - kept
            else:
                n_train += length

    return GuardCost(guard_s, n_blocks, n_holdout, n_train, n_val, n_guard)


def zero_band_survey(ds: TrackDataset,
                     bands: tuple[float, ...] = CANDIDATE_ZERO_BANDS) -> pd.DataFrame:
    """How much of the steering mass sits inside each candidate near-zero band.

    This is what `ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` are chosen against. The
    balancing decision trades a better predictor against a prediction distribution that still
    resembles the human one, and the size of that trade is exactly the mass measured here.

    Reported per session as well as pooled, because feature 002 already showed that pooled
    column statistics mislead on this dataset: track1 is dominated by straight driving and
    track2 is not, so a pooled figure describes neither.
    """
    sessions = integrity.split_sessions(ds)
    steering = ds.df["steering"].to_numpy(dtype=float)

    rows = []
    for band in bands:
        entry: dict[str, object] = {"band": band}

        inside_pooled = np.abs(steering) <= band + 1e-9
        entry["pooled"] = float(inside_pooled.mean())

        for session in sessions:
            values = steering[session.start_index : session.end_index + 1]
            inside = np.abs(values) <= band + 1e-9
            entry[session.session_id] = float(inside.mean())

        rows.append(entry)

    return pd.DataFrame(rows)


def camera_offset_effect(ds: TrackDataset, offset: float = 0.2) -> pd.DataFrame:
    """What the side-camera augmentation does to the target distribution.

    The augmentation is normally justified as "three times the data for free". It is not free.
    A row is turned into three samples whose targets are `s`, `s + offset` and `s - offset`,
    so the 58.6 percent of rows sitting at exactly zero become one third of that mass at zero
    and two thirds of it parked on exactly plus and minus the offset.

    That matters here more than it would in a normal driving project, because the prediction
    distribution is the object M5 compares against the human one. Two artificial modes in the
    training targets are two modes the model is being taught to produce, and the offset is a
    copied convention rather than a measured quantity (research R4).

    Measured rather than argued: this function reports the mass at each band for the row set,
    the center-only sample set and the full three-camera sample set, so the size of the
    distortion is a number.
    """
    steering = ds.df["steering"].to_numpy(dtype=float)
    with_sides = np.concatenate(
        [
            steering,
            np.clip(steering + offset, -1.0, 1.0),
            np.clip(steering - offset, -1.0, 1.0),
        ]
    )

    def band_mass(values: np.ndarray, low: float, high: float) -> float:
        absolute = np.abs(values)
        inside = (absolute > low + 1e-9) & (absolute <= high + 1e-9)
        return float(inside.mean())

    edges = [(0.0, 0.0), (0.0, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20)]

    rows = []
    for low, high in edges:
        if low == high:
            label = "exactly 0"
            center_only = float((steering == 0).mean())
            three_camera = float((with_sides == 0).mean())
        else:
            label = f"{low:.2f} < |s| <= {high:.2f}"
            center_only = band_mass(steering, low, high)
            three_camera = band_mass(with_sides, low, high)

        rows.append(
            {
                "band": label,
                "center_only": center_only,
                "three_camera": three_camera,
            }
        )

    return pd.DataFrame(rows)


def offset_policy_sweep(ds: TrackDataset, seed: int = 42) -> pd.DataFrame:
    """Target distribution under each candidate side-camera offset policy.

    The constant offset concentrates the augmented mass on two lattice points. Drawing the
    offset per sample from a range spreads it instead, and this sweep is how the range was
    chosen rather than guessed.

    Two things are watched, not one. The obvious one is the peak: how much of the training
    mass sits in the single fullest band. The one that actually rules options out is the
    **tail above 0.30**, which is genuine human high-steering data. A range wide enough to
    push augmented samples up into that tail is inflating real data with synthesised values,
    which is a worse fault than the spike it set out to fix.
    """
    steering = ds.df["steering"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)

    edges = [
        (0.0, 0.0), (0.0, 0.05), (0.05, 0.10), (0.10, 0.15),
        (0.15, 0.20), (0.20, 0.25), (0.25, 0.30), (0.30, 1.01),
    ]

    def masses(values: np.ndarray) -> list[float]:
        absolute = np.abs(values)
        out = []
        for low, high in edges:
            if low == high:
                out.append(float((values == 0).mean()))
            else:
                inside = (absolute > low + 1e-9) & (absolute <= high + 1e-9)
                out.append(float(inside.mean()))
        return out

    rows = []
    for low, high in CANDIDATE_OFFSETS:
        if low == high:
            left = np.full(len(steering), low)
            right = np.full(len(steering), low)
            label = f"constant {low:.2f}"
        else:
            left = rng.uniform(low, high, len(steering))
            right = rng.uniform(low, high, len(steering))
            label = f"jitter {low:.2f} to {high:.2f}"

        combined = np.concatenate(
            [
                steering,
                np.clip(steering + left, -1.0, 1.0),
                np.clip(steering - right, -1.0, 1.0),
            ]
        )

        band_masses = masses(combined)
        rows.append(
            {
                "policy": label,
                # The tail bucket is excluded from the peak on purpose. Once the artificial
                # spike is broken up, the fullest band IS the genuine high-steering tail, and
                # a peak column that just reports the tail discriminates nothing.
                "peak_below_030": max(band_masses[:-1]),
                "tail_above_030": band_masses[-1],
            }
        )

    center_masses = masses(steering)
    rows.append(
        {
            "policy": "center camera only",
            "peak_below_030": max(center_masses[:-1]),
            "tail_above_030": center_masses[-1],
        }
    )

    return pd.DataFrame(rows)


def _offset_sweep_table(frame: pd.DataFrame) -> str:
    lines = [
        "| Policy | Fullest band below 0.30 | Mass above 0.30 |",
        "|---|---|---|",
    ]
    for _, row in frame.iterrows():
        lines.append(
            f"| {row['policy']} | {100 * row['peak_below_030']:.1f} % | "
            f"{100 * row['tail_above_030']:.1f} % |"
        )
    return "\n".join(lines)


def _offset_table(frame: pd.DataFrame) -> str:
    lines = [
        "| Band | Center camera only | All three cameras |",
        "|---|---|---|",
    ]
    for _, row in frame.iterrows():
        lines.append(
            f"| {row['band']} | {100 * row['center_only']:.1f} % | "
            f"{100 * row['three_camera']:.1f} % |"
        )
    return "\n".join(lines)


def _sessions_table(ds: TrackDataset) -> str:
    lines = ["| Session | Rows | First | Last |", "|---|---|---|---|"]
    for session in integrity.split_sessions(ds):
        lines.append(
            f"| `{session.session_id}` | {session.n_rows:,} | "
            f"{session.start_time} | {session.end_time} |"
        )
    return "\n".join(lines)


def _timeline_table(ds: TrackDataset) -> str:
    lines = [
        "| Session | Rows | Implied fps | Median interval | Gaps | Largest gap |",
        "|---|---|---|---|---|---|",
    ]
    for report in integrity.check_timeline(ds):
        lines.append(
            f"| `{report.session_id}` | {report.n_rows:,} | {report.implied_fps:.2f} | "
            f"{report.median_interval_s:.4f} s | {report.n_gaps} | "
            f"{report.largest_gap_s:.1f} s |"
        )
    return "\n".join(lines)


def _autocorr_table(frame: pd.DataFrame) -> str:
    session_columns = [c for c in frame.columns if c not in ("lag_s", "lag_rows")]
    header = "| Lag | Rows | " + " | ".join(f"`{c}`" for c in session_columns) + " |"
    divider = "|---" * (2 + len(session_columns)) + "|"

    lines = [header, divider]
    for _, row in frame.iterrows():
        values = " | ".join(f"{row[c]:+.3f}" for c in session_columns)
        lines.append(f"| {row['lag_s']:.2f} s | {int(row['lag_rows'])} | {values} |")
    return "\n".join(lines)


def _guard_table(costs: list[GuardCost]) -> str:
    lines = [
        "| Guard | Blocks | Held out | Train | Val | Discarded | Discard % | Val % |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cost in costs:
        lines.append(
            f"| {cost.guard_s:.0f} s | {cost.n_blocks} | {cost.n_holdout} | "
            f"{cost.n_train:,} | {cost.n_val:,} | {cost.n_guard:,} | "
            f"{100 * cost.discard_fraction:.1f} | {100 * cost.val_fraction:.1f} |"
        )
    return "\n".join(lines)


def _band_table(frame: pd.DataFrame) -> str:
    session_columns = [c for c in frame.columns if c != "band"]
    header = "| Band | " + " | ".join(f"`{c}`" for c in session_columns) + " |"
    divider = "|---" * (1 + len(session_columns)) + "|"

    lines = [header, divider]
    for _, row in frame.iterrows():
        values = " | ".join(f"{100 * row[c]:.1f} %" for c in session_columns)
        label = "exactly 0" if row["band"] == 0.0 else f"|s| <= {row['band']:.2f}"
        lines.append(f"| {label} | {values} |")
    return "\n".join(lines)


def build_report() -> str:
    """Run every measurement and render the report."""
    ds = loader.resolve_image_paths(loader.load_track("combined"))

    report = loader.check_integrity(ds)
    autocorr = steering_autocorrelation(ds)
    bands = zero_band_survey(ds)
    costs = [
        guard_cost(ds, guard, blocks, holdout)
        for guard in CANDIDATE_GUARDS_S
        for blocks, holdout in CANDIDATE_BLOCKS
    ]

    offsets = camera_offset_effect(ds)
    offset_sweep = offset_policy_sweep(ds)
    steering_summary = stats.describe(ds.df["steering"], "steering")

    return f"""# M4 reconnaissance: session survey

Produced by `python -m python.bc.survey`. Every number in research R2 comes from here, so this
file is the thing that has to re-run to the same values, not the prose that quotes it.

Read-only. Trains nothing, writes nothing outside `results/bc/`.

## Integrity (T008)

{report.summary()}

The expected image count is three times the row count: one recorded moment is a center, left
and right frame. A mismatch means the archive did not unpack fully, and every statistic
downstream would be computed over the wrong denominator.

## Sessions (T006)

{_sessions_table(ds)}

**This is the finding that changed the design.** `split_sessions` segments on the track marker
in the image path, and the combined file carries exactly two. Holding out whole sessions
therefore means training on one track and validating on the other, which measures transfer
between two driving profiles rather than generalisation within one.

## Timeline

{_timeline_table(ds)}

Finer segmentation is not available either. There is no gap anywhere long enough to call a
break, so these are two continuous takes with nothing to cut on. Session-level holdout is not
merely coarse here, it is unavailable.

## Steering autocorrelation

{_autocorr_table(autocorr)}

The guard width is derived from this table rather than chosen. Two frames close in time carry
nearly the same steering value, so a validation frame beside a training frame is scored on
something the model has effectively already seen. The chosen guard is the shortest lag at which
**both** sessions fall below 0.1.

Track1's curve is noisy, and the reason is in the band table below: most of its steering is
exactly zero, so the correlation there is dominated by the zero mass rather than by driving.
Track2 decays cleanly and is the session that sets the figure.

## Guard cost

{_guard_table(costs)}

Discarded rows are the price of the guarantee. The chosen setting is the one that buys
independence at a cost worth paying, with the held-out blocks spread across the lap rather than
taken as one contiguous stretch that might be a single corner repeated.

## Near-zero steering mass (T007)

{_band_table(bands)}

`ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` are chosen against this table. Balancing
trades a better predictor against a prediction distribution that still resembles the human one,
and the size of that trade is the mass measured here.

The per-session split is the point. A pooled figure describes neither recording, which is the
same trap feature 002 recorded for the `brake` column.

## What the side-camera augmentation does to the targets

{_offset_table(offsets)}

**The augmentation is not free, and this is the largest single distortion in the pipeline.**

Turning one row into three samples at `s`, `s + 0.2` and `s - 0.2` cuts the exact-zero mass
from 58.6 percent to 20.3 percent, which looks like it solves the imbalance the balancing
policy exists to address. It does not solve it, it **moves** it: two thirds of the old zero mass
lands on exactly plus and minus 0.2, and the band just below 0.20 goes from a few percent to
roughly 43 percent of all training samples.

Three consequences worth stating before any model is trained.

1. **Balancing the zero spike matters far less than the row-level 58.6 percent suggested.** With
   side cameras on, exact zeros are already down to 20.3 percent of training samples.
2. **The offset creates two artificial modes the human never produced as a distribution
   feature.** 0.20 is a real lattice point, so in a histogram those modes are indistinguishable
   from genuine human steering at 0.20. The prediction distribution is what M5 compares, and
   the model is being taught to produce them.
3. **The offset is a copied convention, not a measured quantity** (research R4). A constant that
   parks 43 percent of the training targets on two values deserved a derivation, and there is
   none available in this dataset.

This does not invalidate the augmentation, which is what makes the side images usable at all.
It does mean the offset cannot be treated as a minor hyperparameter held fixed in the
background, and that the balancing comparison must be read with it in view.

### Choosing the offset policy

{_offset_sweep_table(offset_sweep)}

Two things are watched here, and the second is what decides it.

The **fullest band** is the obvious measure: the constant offset puts 40.6 percent of training
targets in one band, and every jitter range reduces that.

The **mass above 0.30** is the one that rules an option out. That region is genuine human
high-steering data. A range wide enough to push augmented samples up into it is inflating real
data with synthesised values, which is a worse fault than the spike it set out to fix. Center
camera only is the honest baseline for this column, since it contains no synthesised targets
at all.

Widening from 0.15-0.25 to 0.10-0.30 flattens the augmented mass without touching that tail.
Widening again to 0.05-0.35 buys nothing on the peak and inflates the tail, so it is rejected.

The chosen range keeps a mean of exactly 0.20, so it **generalises** the value DESIGN 6.1
already carried rather than replacing it with an unrelated number.

## Pooled steering, for reference

n = {steering_summary.n:,}, mean = {steering_summary.mean:.4f},
variance = {steering_summary.variance:.4f}, std = {steering_summary.std:.4f},
min = {steering_summary.minimum:.4f}, max = {steering_summary.maximum:.4f}

Reported through `eda.stats.describe`, not recomputed here, so this feature's numbers and M1's
cannot drift apart in definition (Principle IX, research R5).
"""


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = build_report()
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
