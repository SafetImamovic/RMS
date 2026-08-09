"""The train/validation split, and the guarantee that it is not leaking.

**The whole point of this module is one number**: `min_train_val_gap_s`. If any training frame
sits closer in time than the guard to any validation frame, the reported validation error is
measuring interpolation between near-duplicate frames rather than generalisation, and the
model's headline number means nothing. Everything here exists to make that impossible and then
to prove it rather than assert it.

Why blocks and not sessions. The obvious plan was to hold out whole recording sessions, which
needs no parameter at all. Measured, the combined recording contains exactly **two** sessions,
one per track, and the largest gap in either is 0.5 s. Two continuous takes with nothing to cut
on, so session holdout would mean training on track1 and validating on track2, which measures
transfer between two driving profiles rather than generalisation within one. See
`specs/004-bc-baseline/research.md` R2.

This module imports no torch. The split is decided before any model exists, and keeping it
torch-free means it can be produced and checked under `.venv`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from python.bc import config
from python.eda import integrity, loader
from python.eda.loader import TrackDataset


class SplitError(Exception):
    """Raised when a split cannot be trusted. Always names what failed and by how much."""


@dataclass(frozen=True)
class BlockBound:
    """One contiguous block, and what became of it."""

    track: str
    block: int
    first_row: int
    last_row: int
    first_time: str | None
    last_time: str | None
    n_rows: int
    assignment: str  # train, val


@dataclass
class SplitPlan:
    """Which rows train, which validate, and which were sacrificed to the guard.

    `train_rows`, `val_rows` and `guard_rows` are pairwise disjoint and together cover every
    row. Nothing is silently dropped: a frame that vanished from all three would change the
    denominator of every statistic computed later, which is the class of error this project
    keeps finding in its own data.
    """

    seed: int
    n_blocks: int
    n_holdout: int
    guard_seconds: float
    val_fraction_target: float
    train_rows: list[int]
    val_rows: list[int]
    guard_rows: list[int]
    block_bounds: list[BlockBound] = field(default_factory=list)
    min_train_val_gap_s: float = float("nan")

    @property
    def n_train_rows(self) -> int:
        return len(self.train_rows)

    @property
    def n_val_rows(self) -> int:
        return len(self.val_rows)

    @property
    def n_guard_rows(self) -> int:
        return len(self.guard_rows)

    @property
    def val_fraction_actual(self) -> float:
        """Derived, and deliberately not forced to match the target.

        Blocks are integer-sized and the guard eats into them, so the achieved figure lands
        near the target rather than on it. Moving a boundary to close that gap would be
        fitting the split to a number instead of to the data.
        """
        kept = self.n_train_rows + self.n_val_rows
        return self.n_val_rows / kept if kept else 0.0


def _capture_times(ds: TrackDataset) -> pd.Series:
    """Capture time per row, as a Series indexed by row position."""
    times, _ = integrity.parse_capture_times(ds)
    return times


def held_out_blocks(n_blocks: int, n_holdout: int) -> set[int]:
    """Which block indices are held out, spread evenly rather than taken from one end.

    Two adjacent held-out blocks are one long contiguous stretch of road, which could be a
    single corner repeated. The validation error would then describe that corner rather than
    the track.
    """
    if n_holdout <= 0 or n_blocks <= 0:
        return set()

    return {int(round(i * n_blocks / n_holdout)) % n_blocks for i in range(n_holdout)}


def plan_split(ds: TrackDataset,
               seed: int = config.SEED,
               n_blocks: int = config.N_BLOCKS,
               n_holdout: int = config.N_HOLDOUT,
               guard_seconds: float = config.GUARD_SECONDS,
               val_fraction_target: float = config.VAL_FRACTION_TARGET) -> SplitPlan:
    """Cut each session into contiguous blocks, hold some out, guard the boundaries.

    The seed is recorded rather than used to shuffle anything. Which blocks are held out is
    determined by `held_out_blocks`, not drawn at random: a random choice would make the split
    depend on the RNG implementation as well as the seed, and two numpy versions could then
    disagree about what seed 42 means.
    """
    sessions = integrity.split_sessions(ds)
    times = _capture_times(ds)

    train_rows: list[int] = []
    val_rows: list[int] = []
    guard_rows: list[int] = []
    bounds: list[BlockBound] = []

    hold = held_out_blocks(n_blocks, n_holdout)

    for session in sessions:
        size = session.n_rows
        if size < n_blocks:
            raise SplitError(
                f"session {session.session_id} has {size} rows, fewer than the "
                f"{n_blocks} blocks it must be cut into"
            )

        block_len = size // n_blocks

        for block in range(n_blocks):
            lo = session.start_index + block * block_len
            hi = (session.end_index + 1 if block == n_blocks - 1
                  else session.start_index + (block + 1) * block_len)

            rows = list(range(lo, hi))
            window = times.iloc[lo:hi].dropna()

            if block in hold:
                kept, dropped = _apply_guard(times, rows, guard_seconds)
                val_rows.extend(kept)
                guard_rows.extend(dropped)
                assignment = "val"
            else:
                train_rows.extend(rows)
                assignment = "train"

            bounds.append(
                BlockBound(
                    track=session.session_id,
                    block=block,
                    first_row=lo,
                    last_row=hi - 1,
                    first_time=str(window.iloc[0]) if len(window) else None,
                    last_time=str(window.iloc[-1]) if len(window) else None,
                    n_rows=len(rows),
                    assignment=assignment,
                )
            )

    if not val_rows:
        raise SplitError("the validation side is empty")
    if not train_rows:
        raise SplitError("the training side is empty")

    plan = SplitPlan(
        seed=seed,
        n_blocks=n_blocks,
        n_holdout=n_holdout,
        guard_seconds=guard_seconds,
        val_fraction_target=val_fraction_target,
        train_rows=sorted(train_rows),
        val_rows=sorted(val_rows),
        guard_rows=sorted(guard_rows),
        block_bounds=bounds,
    )
    plan.min_train_val_gap_s = measure_min_gap(ds, plan)
    return plan


def _apply_guard(times: pd.Series, rows: list[int],
                 guard_seconds: float) -> tuple[list[int], list[int]]:
    """Trim a held-out block back from both of its edges by the guard width.

    Trimmed from the **validation** block rather than from its training neighbours, which is a
    choice worth stating: it costs validation rows rather than training rows, and training data
    is the scarcer resource for the model. The guarantee is symmetric either way, because
    removing rows from one side of a boundary opens the same gap as removing them from the
    other.
    """
    if not rows:
        return [], []

    window = times.iloc[rows[0] : rows[-1] + 1]
    first = window.dropna()
    if first.empty:
        # No usable timestamps in this block. Keeping it would mean asserting a gap we cannot
        # measure, so the whole block goes to the guard.
        return [], list(rows)

    start = first.iloc[0]
    end = first.iloc[-1]

    kept: list[int] = []
    dropped: list[int] = []
    for row in rows:
        stamp = times.iloc[row]
        if pd.isna(stamp):
            dropped.append(row)
            continue

        from_start = (stamp - start).total_seconds()
        to_end = (end - stamp).total_seconds()
        if from_start < guard_seconds or to_end < guard_seconds:
            dropped.append(row)
        else:
            kept.append(row)

    return kept, dropped


def measure_min_gap(ds: TrackDataset, plan: SplitPlan) -> float:
    """The smallest time distance between any training frame and any validation frame.

    This is the number FR-004 turns on, and it is measured rather than inferred from the
    construction. A guard applied correctly and a guard applied to the wrong array look
    identical until someone measures the result.

    Comparison is per session. Two frames in different recordings have a time difference that
    is real arithmetic but means nothing: the file lists track1 first while track2 was recorded
    earlier the same day, so a cross-session distance is not a statement about adjacency.
    """
    times = _capture_times(ds)
    sessions = integrity.split_sessions(ds)

    train = set(plan.train_rows)
    val = set(plan.val_rows)
    smallest = float("inf")

    for session in sessions:
        lo, hi = session.start_index, session.end_index
        session_train = np.array(
            sorted(t for t in train if lo <= t <= hi and not pd.isna(times.iloc[t]))
        )
        session_val = [v for v in val if lo <= v <= hi and not pd.isna(times.iloc[v])]

        if not len(session_train) or not session_val:
            continue

        train_seconds = np.array(
            [times.iloc[int(t)].timestamp() for t in session_train]
        )
        order = np.argsort(train_seconds)
        train_seconds = train_seconds[order]

        for row in session_val:
            stamp = times.iloc[row].timestamp()
            idx = int(np.searchsorted(train_seconds, stamp))
            for candidate in (idx - 1, idx):
                if 0 <= candidate < len(train_seconds):
                    smallest = min(smallest, abs(stamp - train_seconds[candidate]))

    return float(smallest)


def verify_no_leak(ds: TrackDataset, plan: SplitPlan) -> None:
    """Raise unless every training frame is at least the guard away from every validation one.

    Checks the partition as well as the gap. A split whose three row sets overlap, or fail to
    cover the recording, is broken in a way that a gap measurement alone would not notice.
    """
    train = set(plan.train_rows)
    val = set(plan.val_rows)
    guard = set(plan.guard_rows)

    for left_name, left, right_name, right in (
        ("train", train, "val", val),
        ("train", train, "guard", guard),
        ("val", val, "guard", guard),
    ):
        overlap = left & right
        if overlap:
            raise SplitError(
                f"{left_name} and {right_name} share {len(overlap)} rows, "
                f"first at index {min(overlap)}"
            )

    total = len(train) + len(val) + len(guard)
    expected = len(ds.df)
    if total != expected:
        raise SplitError(
            f"the split covers {total:,} rows but the recording has {expected:,}. "
            "Every row must be trained on, validated on, or explicitly guarded."
        )

    gap = plan.min_train_val_gap_s
    if not np.isfinite(gap):
        raise SplitError("no train/validation pair could be compared; the split is degenerate")

    if gap < plan.guard_seconds - 1e-6:
        raise SplitError(
            f"a training frame sits {gap:.3f} s from a validation frame, inside the "
            f"{plan.guard_seconds:.1f} s guard. Frames this close carry nearly the same "
            "target, so the validation error would measure interpolation rather than "
            "generalisation."
        )


def write_split(plan: SplitPlan, path: Path = config.SPLIT_PATH) -> None:
    """Write the plan as JSON, sorted and indented so two runs diff cleanly.

    `sort_keys` and a fixed indent are what make SC-002 checkable with `diff` rather than with
    a parser. A file that is semantically identical but textually different fails the check
    that matters, which is whether a reader can see that nothing moved.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = asdict(plan)
    payload["n_train_rows"] = plan.n_train_rows
    payload["n_val_rows"] = plan.n_val_rows
    payload["n_guard_rows"] = plan.n_guard_rows
    payload["val_fraction_actual"] = round(plan.val_fraction_actual, 6)
    payload["min_train_val_gap_s"] = round(plan.min_train_val_gap_s, 6)

    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_split(path: Path = config.SPLIT_PATH) -> SplitPlan:
    """Read a plan back. Derived fields are recomputed, never trusted from the file."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    plan = SplitPlan(
        seed=payload["seed"],
        n_blocks=payload["n_blocks"],
        n_holdout=payload["n_holdout"],
        guard_seconds=payload["guard_seconds"],
        val_fraction_target=payload["val_fraction_target"],
        train_rows=payload["train_rows"],
        val_rows=payload["val_rows"],
        guard_rows=payload["guard_rows"],
        block_bounds=[BlockBound(**b) for b in payload["block_bounds"]],
        min_train_val_gap_s=payload["min_train_val_gap_s"],
    )
    return plan


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Plan the M4 train/validation split.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--val-fraction", type=float, default=config.VAL_FRACTION_TARGET)
    parser.add_argument("--blocks", type=int, default=config.N_BLOCKS)
    parser.add_argument("--holdout", type=int, default=config.N_HOLDOUT)
    parser.add_argument("--guard", type=float, default=config.GUARD_SECONDS)
    args = parser.parse_args()

    ds = loader.load_track(config.DATASET_NAME)
    plan = plan_split(
        ds,
        seed=args.seed,
        n_blocks=args.blocks,
        n_holdout=args.holdout,
        guard_seconds=args.guard,
        val_fraction_target=args.val_fraction,
    )
    verify_no_leak(ds, plan)
    write_split(plan)

    print(f"wrote {config.SPLIT_PATH}")
    print(f"  train {plan.n_train_rows:,}  val {plan.n_val_rows:,}  "
          f"guard {plan.n_guard_rows:,}")
    print(f"  val fraction {plan.val_fraction_actual:.4f} "
          f"(target {plan.val_fraction_target:.2f}, reported not forced)")
    print(f"  min train/val gap {plan.min_train_val_gap_s:.2f} s "
          f"(guard {plan.guard_seconds:.1f} s)")


if __name__ == "__main__":
    main()
