"""Prove each numeric column's identity from its statistics (US1).

The CSV is headerless. Instead of trusting the assumed column order, we look at each numeric
column's "fingerprint" (min, max, % negative, % zero) and deduce what it MUST be:

- steering  -> the only column that goes negative (steer left) and is symmetric around 0
- speed     -> non-negative but with large magnitude (values well above 1)
- brake     -> a [0, 1] column that is (almost) entirely zero in a recording with no braking
- throttle  -> the remaining [0, 1] column, with real positive values

The inference works on column POSITIONS, not on the assumed names, so it can genuinely
confirm (or contradict) the assumed order rather than just repeat it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config
from .loader import TrackDataset

# Numeric columns sit at positions 4..7 (1-based) = indices 3..6 (0-based).
_NUMERIC_POSITIONS = [3, 4, 5, 6]


@dataclass
class ColumnFingerprint:
    column_index: int          # 1-based, matches DESIGN 6.1
    assumed_name: str          # what COLUMN_NAMES claims this column is
    inferred_identity: str     # what the statistics say it is
    minimum: float
    maximum: float
    mean: float
    pct_negative: float
    pct_zero: float
    evidence: str
    matches_assumption: bool


def _col_stats(series) -> dict:
    n = len(series)
    arr = np.asarray(series, dtype=float)
    return {
        "min": float(arr.min()),
        "max": float(arr.max()),
        "mean": float(arr.mean()),
        "pct_negative": 100.0 * float((arr < 0).sum()) / n,
        "pct_zero": 100.0 * float((arr == 0).sum()) / n,
    }


def column_fingerprints(ds: TrackDataset) -> list[ColumnFingerprint]:
    """Return fingerprints for the 4 numeric columns with a rule-based inferred identity."""
    # Compute stats per position (name-independent).
    stats = {pos: _col_stats(ds.df.iloc[:, pos]) for pos in _NUMERIC_POSITIONS}

    remaining = set(_NUMERIC_POSITIONS)
    inferred: dict[int, tuple[str, str]] = {}  # pos -> (identity, evidence)

    # 1) steering = the only column with negative values (biggest %negative, min < 0).
    steer_pos = max(remaining, key=lambda p: stats[p]["pct_negative"])
    if stats[steer_pos]["min"] < 0:
        inferred[steer_pos] = (
            "steering",
            f"only negative-capable column (min={stats[steer_pos]['min']:.3f}, "
            f"{stats[steer_pos]['pct_negative']:.1f}% negative) -> steering (left turns)",
        )
        remaining.discard(steer_pos)

    # 2) speed = non-negative column with large magnitude (max well above the [0,1] controls).
    speed_pos = max(remaining, key=lambda p: stats[p]["max"])
    if stats[speed_pos]["max"] > 1.5:
        inferred[speed_pos] = (
            "speed",
            f"non-negative with large magnitude (max={stats[speed_pos]['max']:.2f}) -> speed",
        )
        remaining.discard(speed_pos)

    # 3) brake vs throttle: both live in [0,1]; the (almost) all-zero one is brake.
    if len(remaining) == 2:
        by_zeros = sorted(remaining, key=lambda p: stats[p]["pct_zero"], reverse=True)
        brake_pos, throttle_pos = by_zeros[0], by_zeros[1]
        inferred[brake_pos] = (
            "brake",
            f"[0,1] column, mostly zero ({stats[brake_pos]['pct_zero']:.1f}% zero) -> brake",
        )
        inferred[throttle_pos] = (
            "throttle",
            f"remaining [0,1] column with positive values "
            f"(max={stats[throttle_pos]['max']:.2f}) -> throttle",
        )
        remaining.discard(brake_pos)
        remaining.discard(throttle_pos)

    # Anything left unresolved is labelled explicitly rather than guessed.
    for pos in remaining:
        inferred[pos] = ("unknown", "could not be disambiguated from statistics")

    fingerprints: list[ColumnFingerprint] = []
    for pos in _NUMERIC_POSITIONS:
        identity, evidence = inferred[pos]
        assumed = config.COLUMN_NAMES[pos]
        s = stats[pos]
        fingerprints.append(
            ColumnFingerprint(
                column_index=pos + 1,
                assumed_name=assumed,
                inferred_identity=identity,
                minimum=s["min"],
                maximum=s["max"],
                mean=s["mean"],
                pct_negative=s["pct_negative"],
                pct_zero=s["pct_zero"],
                evidence=evidence,
                matches_assumption=(identity == assumed),
            )
        )
    return fingerprints
