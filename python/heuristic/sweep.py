"""Read the driver's per-step traces and report one row per run.

Every trace carries its own configuration on every row, so a folder of traces is
self-describing: nothing has to be written down while driving, and a run cannot be
mislabelled after the fact. That is the same property the run-record contract asks for
(``specs/005-heuristic-ray-driver/contracts/run-record.md``, SC-006).

Usage::

    python -m python.heuristic.sweep                 # every trace in results/heuristic
    python -m python.heuristic.sweep --since 18:00   # only traces written after a time

What it will not do is call a difference between two thresholds a finding. FR-015 requires
a difference to exceed the run-to-run spread first, and that spread is measured by running
the SAME threshold several times. Until at least two runs share a threshold, the spread
column reads "unmeasured" and every comparison below it is provisional.
"""

from __future__ import annotations

import argparse
import csv
import io
import statistics
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRACES = REPO / "results" / "heuristic"


@dataclass(frozen=True)
class Run:
    """One trace file, reduced to the numbers a sweep is judged on."""

    path: Path
    mode: str
    threshold: float
    reaction_s: float
    smoothing_s: float
    duration_s: float
    steps: int
    completed: bool
    outcome: str               # LapComplete, WallContact, ... or "unknown" on old traces
    saturation: float          # fraction of steps commanding full lock
    straight: float            # fraction of steps commanding exactly zero
    sign_changes_per_s: float
    mean_lag: float            # |command - applied|
    max_lag: float
    gate_open: float           # fraction of steps the gate let steering through
    peak_speed: float
    mean_speed: float

    # True when the configuration changed while the run was in progress, which the in-sim
    # panel makes easy to do by accident: dragging a slider mid-lap is the whole point of
    # having it. Such a run is a demonstration, not a data point, because no single
    # threshold describes it. Reading the configuration from the first row alone would
    # have labelled it with whatever the slider happened to be at when Play was pressed.
    config_varied: bool
    config_values: tuple


def _f(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return default


def load(path: Path) -> Run | None:
    """Reduce one trace. Returns None if the file is too short to say anything."""
    # utf-8-sig because an early version of the writer emitted a BOM, and those traces
    # are still on disk. Reading them correctly costs nothing and losing them would
    # mean losing the runs that found the saturation.
    with io.open(path, encoding="utf-8-sig", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("ray12")]

    if len(rows) < 50:
        return None

    cmd = [_f(r, "command_steer") for r in rows]
    applied = [_f(r, "applied_steer") for r in rows]
    lag = [abs(c - a) for c, a in zip(cmd, applied)]
    speed = [_f(r, "speed_ms") for r in rows]
    duration = _f(rows[-1], "t")

    signs = [1 if v > 1e-3 else (-1 if v < -1e-3 else 0) for v in cmd]
    flips = sum(
        1
        for i in range(1, len(signs))
        if signs[i] != 0 and signs[i - 1] != 0 and signs[i] != signs[i - 1]
    )

    gate = [int(r["gate_open"]) for r in rows] if "gate_open" in rows[0] else [1] * len(rows)

    thresholds = sorted({r.get("critical_distance", "") for r in rows})
    modes = sorted({r.get("mode", "?") for r in rows})
    varied = len(thresholds) > 1 or len(modes) > 1

    # The terminal outcome is the last row's outcome column, written by Finish(). Traces
    # recorded before that column existed have no way to say how the run ended, and they
    # are marked unknown rather than guessed at: guessing is what inflated the first
    # noise-floor estimate from 0.100 s to 28.9 s.
    outcome = rows[-1].get("outcome", "") or "unknown"
    completed = outcome == "LapComplete"

    return Run(
        path=path,
        mode=rows[0].get("mode", "?"),
        threshold=_f(rows[0], "critical_distance"),
        reaction_s=_f(rows[0], "reaction_s"),
        smoothing_s=_f(rows[0], "smoothing_s"),
        duration_s=duration,
        steps=len(rows),
        completed=completed,
        outcome=outcome,
        saturation=sum(1 for v in cmd if abs(v) > 0.999) / len(cmd),
        straight=sum(1 for v in cmd if abs(v) < 1e-6) / len(cmd),
        sign_changes_per_s=flips / duration if duration > 0 else 0.0,
        mean_lag=statistics.fmean(lag),
        max_lag=max(lag),
        gate_open=sum(gate) / len(gate),
        peak_speed=max(speed),
        mean_speed=statistics.fmean(speed),
        config_varied=varied,
        config_values=tuple(thresholds),
    )


def spread(runs: list[Run]) -> dict[str, tuple[float, float]] | None:
    """Run-to-run spread over runs sharing a configuration (FR-011).

    This is the noise floor every comparison in this feature depends on, and it cannot be
    computed from a single run per setting. Returns None when no setting was repeated,
    which is a result to report rather than a gap to paper over.
    """
    groups: dict[tuple, list[Run]] = {}
    for r in runs:
        if r.config_varied:
            continue
        if r.outcome != "LapComplete":
            # Only runs that ended the same way are comparable. An interrupted run is not a
            # slower lap, it is not a lap.
            continue
        groups.setdefault((r.mode, r.threshold, r.reaction_s, r.smoothing_s), []).append(r)

    repeated = [g for g in groups.values() if len(g) >= 2]
    if not repeated:
        return None

    best = max(repeated, key=len)
    return {
        "duration_s": (statistics.fmean([r.duration_s for r in best]),
                       max(r.duration_s for r in best) - min(r.duration_s for r in best)),
        "saturation": (statistics.fmean([r.saturation for r in best]),
                       max(r.saturation for r in best) - min(r.saturation for r in best)),
        "n": (len(best), 0.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=TRACES)
    parser.add_argument("--since", default=None,
                        help="only traces whose filename time is at or after HH-MM")
    args = parser.parse_args()

    paths = sorted(args.dir.glob("trace_*.csv"))
    if args.since:
        stamp = args.since.replace(":", "-")
        paths = [p for p in paths if p.stem.split("_")[-1] >= stamp]

    runs = [r for r in (load(p) for p in paths) if r is not None]
    if not runs:
        print(f"no usable traces in {args.dir}")
        return

    runs.sort(key=lambda r: (r.mode, r.threshold, r.path.name))

    print(f"{len(runs)} runs\n")
    head = (f"{'mode':<16}{'thresh':>7}{'dur s':>8}{'outcome':>13}"
            f"{'satur':>8}{'straight':>10}{'flips/s':>9}{'lag mean':>10}{'gate':>7}{'vmax':>7}")
    print(head)
    print("-" * len(head))

    for r in runs:
        print(f"{r.mode:<16}{r.threshold:>7.2f}{r.duration_s:>8.1f}"
              f"{r.outcome[:11]:>13}"
              f"{r.saturation:>8.0%}{r.straight:>10.0%}{r.sign_changes_per_s:>9.2f}"
              f"{r.mean_lag:>10.3f}{r.gate_open:>7.0%}{r.peak_speed:>7.2f}"
              + ("   <- config varied mid-run, not a data point" if r.config_varied else ""))

    print()
    s = spread(runs)
    if s is None:
        print("RUN-TO-RUN SPREAD: unmeasured. No configuration was run twice.")
        print("Until it is, no difference between rows above is a finding (FR-015):")
        print("there is nothing to say a gap is larger than the noise.")
    else:
        print(f"RUN-TO-RUN SPREAD over {int(s['n'][0])} repeats of one setting:")
        print(f"  duration   mean {s['duration_s'][0]:.1f} s, range {s['duration_s'][1]:.1f} s")
        print(f"  saturation mean {s['saturation'][0]:.1%}, range {s['saturation'][1]:.1%}")
        print()
        print("A difference smaller than those ranges is not a finding.")


if __name__ == "__main__":
    main()
