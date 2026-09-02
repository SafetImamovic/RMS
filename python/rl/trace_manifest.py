"""Map feature 009's evaluation traces to the sweeps that produced them.

**Why this file exists at all.** `DriveLogger` writes one per-step trace per run into
`results/drive_logs/`, named only by timestamp, and stamps each row with `sourceLabel`. That label
is a `[SerializeField]` literal rather than the run id, and in `Evaluation.unity` it still read
`ppo_car_spread_a_sampling`, left over from feature 006, for every one of feature 009's six sweeps.
So **all 60 traces claim to belong to a feature 006 run** and the `source` column cannot be used to
select them (research R3).

**Why the mapping is by content and not by time.** A timestamp window is the obvious approach and
it is not good enough: two of the six sweeps have a neighbouring file inside any window wide enough
to hold the sweep itself, so the window returns 11 or 12 candidates for 10 runs. Instead each
candidate trace is matched to an evaluation row by its **own recorded duration**: the last `t` in
the trace must equal that row's `duration_s`. A run that lasted 62.801 s produced a trace whose
final timestamp is 62.801 s, and no neighbouring run shares it to within the tolerance.

That makes the manifest a **verification** rather than an assumption. If a trace were missing,
misordered or truncated, the match would fail loudly instead of silently binding the wrong file.

**The corroboration worth keeping.** Feature 009's seed 42 sampling sweep lost seed 1009 to a wall
contact at 7.16 s where every other run took about 63 s. Its trace is 2 s after its predecessor
rather than the usual 16 s of real time, and it matches on duration. An accidental alignment would
not reproduce that.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
from pathlib import Path

import pandas as pd

# The six sweeps of feature 009, each named by the run id, the inference mode, and the timestamp
# the sweep's own run-record CSV carries. The CSV is named at its first write, which is when the
# first run of the sweep finished, so it is a label rather than a start time.
SWEEPS: list[tuple[str, str, str]] = [
    ("ppo_car_009_bc", "deterministic", "2026-08-31_18-56-04"),
    ("ppo_car_009_bc", "sampling", "2026-08-31_18-59-49"),
    ("ppo_car_009_bc_s7", "deterministic", "2026-09-01_12-48-31"),
    ("ppo_car_009_bc_s7", "sampling", "2026-09-01_12-51-50"),
    ("ppo_car_009_bc_s13", "deterministic", "2026-09-01_14-38-14"),
    ("ppo_car_009_bc_s13", "sampling", "2026-09-01_14-41-28"),
]

# How close a trace's final timestamp must be to the run record's duration to count as the same run.
#
# Measured rather than picked. `DriveLogger` samples at the fixed timestep, so a trace's last `t`
# lands on a multiple of 0.02 s while `duration_s` is the run's own elapsed figure. The observed
# disagreement across all 60 traces is under one timestep; 0.06 is three of them, which is loose
# enough for that and far tighter than the roughly 16 s that separates consecutive runs.
DURATION_TOLERANCE_S: float = 0.06

# How far either side of the sweep label to look for its traces. The first trace opens before the
# CSV is named, so the window reaches backwards; a whole sweep is about 160 s of real time at the
# sweep's `timeScale` of 4.
WINDOW_BEFORE_S: float = -90.0
WINDOW_AFTER_S: float = 400.0

_STAMP = re.compile(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})")


def stamp_of(name: str) -> dt.datetime:
    """The timestamp encoded in a drive log or run record filename."""
    m = _STAMP.search(os.path.basename(name))
    if m is None:
        raise ValueError(f"no timestamp in {name!r}")
    return dt.datetime(*(int(g) for g in m.groups()))


def _trace_index(drive_logs: Path) -> dict[str, tuple[dt.datetime, float, int]]:
    """Every candidate trace, with its timestamp, final `t` and row count."""
    index: dict[str, tuple[dt.datetime, float, int]] = {}
    for path in sorted(glob.glob(str(drive_logs / "2026-0*.csv"))):
        try:
            frame = pd.read_csv(path, usecols=["t"])
        except (ValueError, KeyError, pd.errors.ParserError):
            # stability_log.csv and anything else without a `t` column is not a drive trace.
            continue
        if frame.empty:
            continue
        index[path] = (stamp_of(path), float(frame["t"].iloc[-1]), len(frame))
    return index


def match_sweep(
    run_id: str,
    mode: str,
    sweep_stamp: str,
    results_dir: Path,
    index: dict[str, tuple[dt.datetime, float, int]],
) -> dict:
    """Bind one sweep's ten evaluation rows to their ten traces, in seed order.

    Raises rather than returning a partial mapping. A manifest that is right for eight rows and
    quietly wrong for two is worse than no manifest, because every number downstream would inherit
    the error without a way to notice it.
    """
    eval_csv = results_dir / "rl" / f"eval_{run_id}_{mode}.csv"
    rows = pd.read_csv(eval_csv)
    origin = stamp_of(sweep_stamp)

    candidates = sorted(
        (s, path, last_t)
        for path, (s, last_t, _n) in index.items()
        if WINDOW_BEFORE_S <= (s - origin).total_seconds() <= WINDOW_AFTER_S
    )

    # Consumed in order: run N of a sweep cannot have been recorded before run N-1 finished, so the
    # search never looks backwards. That is also what stops a later run stealing an earlier match.
    traces: list[str] = []
    cursor = 0
    for _, row in rows.iterrows():
        want = float(row["duration_s"])
        for k in range(cursor, len(candidates)):
            if abs(candidates[k][2] - want) < DURATION_TOLERANCE_S:
                traces.append(os.path.basename(candidates[k][1]))
                cursor = k + 1
                break
        else:
            raise LookupError(
                f"{run_id} {mode}: no trace within {DURATION_TOLERANCE_S}s of "
                f"duration {want}s for seed {int(row['seed'])}"
            )

    return {
        "run_id": run_id,
        "inference": mode,
        "eval_csv": str(eval_csv.as_posix()),
        "sweep_stamp": sweep_stamp,
        "seeds": [int(s) for s in rows["seed"]],
        "traces": traces,
    }


def build(repo_root: Path) -> dict:
    """The whole manifest, all six sweeps."""
    index = _trace_index(repo_root / "results" / "drive_logs")
    sweeps = [
        match_sweep(run_id, mode, stamp, repo_root / "results", index)
        for run_id, mode, stamp in SWEEPS
    ]
    return {
        "generated_by": "python/rl/trace_manifest.py",
        "trace_dir": "results/drive_logs",
        "matched_on": (
            "the trace's final t against the evaluation row's duration_s, within "
            f"{DURATION_TOLERANCE_S}s, consumed in run order"
        ),
        "source_column_is_wrong": (
            "DriveLogger.sourceLabel is a SerializeField literal rather than the run id, and in "
            "Evaluation.unity it still read ppo_car_spread_a_sampling from feature 006. Every "
            "trace named here carries that string in its source column. Select traces through "
            "this manifest, never through the source column."
        ),
        "sweeps": sweeps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write the manifest (default results/rl/trace_manifest.json)",
    )
    args = parser.parse_args(argv)

    manifest = build(args.root)
    out = args.out or args.root / "results" / "rl" / "trace_manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    total = sum(len(s["traces"]) for s in manifest["sweeps"])
    print(f"wrote {out} with {len(manifest['sweeps'])} sweeps and {total} traces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
