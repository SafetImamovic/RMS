"""Turn a training run's event files into one committed CSV.

FR-018 requires the recorded curves to survive a clean clone, while ``.gitignore`` keeps the
trainer's own output out of the repository. Both are right: event files are binary and grow with
the run, and a milestone whose evidence is "there was a curve on my machine" is not reproducible.
This module is the bridge, and the shape it writes is fixed by
``specs/006-ppo-rl-driver/contracts/curve-export.md``.

Three rules the tests enforce rather than leaving to care:

- **No smoothing.** TensorBoard smooths for display, and exporting the smoothed series would commit
  a picture instead of a measurement. Two runs smoothed at different window sizes are not
  comparable, and nothing in the file would say so.
- **No resampling.** Rows land on the trainer's own summary steps, which is why ``summary_freq`` is
  pinned in ``config/ppo_car.yaml``. A curve resampled to a nicer grid is a curve nobody can line
  up against another run.
- **Absent is empty, not zero.** A series the trainer never emitted writes as an empty field. Zero
  is a value a loss can legitimately take, and an aggregate that averages absent points as zeros
  reports a run that did not happen.

The six per-term reward series are this feature's own, added through ``StatsRecorder`` on the Unity
side. They are the reason the export exists at all: a total that rises does not say which term
raised it, and a flat ``reward/checkpoint`` beneath a rising total is a policy collecting speed and
step reward without going anywhere.

**The reading and the shaping are separate on purpose.** ``read_series`` needs the event reader
that ships with the trainer's TensorBoard dependency and therefore runs under ``.venv-mlagents``;
``to_rows`` and ``write_csv`` are pure and are what the tests exercise, so the test suite stays
runnable under ``.venv`` where the rest of the analysis lives.

Usage::

    python -m python.rl.export_curves results/ppo_car_v01 --out results/rl/curves/ppo_car_v01.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
from typing import Dict, List, Mapping, Optional, Sequence

# The committed column order, and the trainer tag each column comes from. Anything not listed here
# stays out of the CSV: the export is a fixed contract, not a dump of whatever the run emitted.
COLUMNS: Sequence[tuple] = (
    ("cumulative_reward", "Environment/Cumulative Reward"),
    ("episode_length", "Environment/Episode Length"),
    ("policy_loss", "Losses/Policy Loss"),
    ("value_loss", "Losses/Value Loss"),
    ("entropy", "Policy/Entropy"),
    ("reward_checkpoint", "reward/checkpoint"),
    ("reward_wrong_way", "reward/wrong_way"),
    ("reward_wall", "reward/wall"),
    ("reward_step", "reward/step"),
    ("reward_speed", "reward/speed"),
    ("reward_jerk", "reward/jerk"),
    # Counts, not means, and only because the agent asks the trainer to sum them. A run trained
    # before that change wrote these as an average of a constant 1.0 and carried no frequency
    # information; it exports them as empty, which is the honest answer rather than a 1.0 that
    # looks like a count of one.
    ("end_wallcontact", "episode/end_wallcontact"),
    ("end_lapscompleted", "episode/end_lapscompleted"),
    ("end_stalled", "episode/end_stalled"),
    ("end_steplimit", "episode/end_steplimit"),
    ("end_trackswapped", "episode/end_trackswapped"),
)

HEADER: Sequence[str] = ("run_id", "step") + tuple(name for name, _ in COLUMNS)

#: The series that defines which steps get a row. Every run has it, and it is the one a reader
#: looks at first, so a row exists exactly where the headline number does.
REFERENCE_TAG = "Environment/Cumulative Reward"


def find_event_files(run_dir: str) -> List[str]:
    """Every event file under a run directory, including the behaviour subfolder."""
    pattern = os.path.join(run_dir, "**", "events.out.tfevents.*")
    return sorted(glob.glob(pattern, recursive=True))


def read_series(run_dir: str) -> Dict[str, Dict[int, float]]:
    """Read the scalar series out of a run's event files, keyed by tag then by step.

    Imported lazily, because the reader lives in the trainer's environment and this module's
    shaping half has to stay importable under ``.venv``.

    Values are taken exactly as written. No smoothing, and no interpolation onto a shared grid.
    """
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    series: Dict[str, Dict[int, float]] = {}

    for path in find_event_files(run_dir):
        accumulator = EventAccumulator(path)
        accumulator.Reload()

        for tag in accumulator.Tags().get("scalars", []):
            points = series.setdefault(tag, {})
            for event in accumulator.Scalars(tag):
                points[int(event.step)] = float(event.value)

    return series


def to_rows(series: Mapping[str, Mapping[int, float]], run_id: str) -> List[dict]:
    """Shape the series into the committed rows.

    ``run_id`` is repeated on every row, the same decision feature 005 made for its run record: a
    row found in isolation, or a frame concatenating several runs, must not need the filename to
    say where it came from.

    A tag the run never emitted, or a step a tag has no value at, writes as an empty string rather
    than a zero. Zero is a value a loss can take.
    """
    reference = series.get(REFERENCE_TAG, {})
    rows: List[dict] = []

    for step in sorted(reference):
        row = {"run_id": run_id, "step": step}

        for name, tag in COLUMNS:
            value = series.get(tag, {}).get(step)
            row[name] = "" if value is None else value

        rows.append(row)

    return rows


def write_csv(rows: Sequence[dict], out_path: str) -> str:
    """Write the rows in the committed column order, creating the directory if needed."""
    directory = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(directory, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(HEADER))
        writer.writeheader()
        writer.writerows(rows)

    return out_path


def export(run_dir: str, out_path: Optional[str] = None, run_id: Optional[str] = None) -> str:
    """Read a run directory and write its committed curve."""
    resolved_id = run_id or os.path.basename(os.path.normpath(run_dir))
    resolved_out = out_path or os.path.join("results", "rl", "curves", f"{resolved_id}.csv")

    series = read_series(run_dir)
    if not series:
        raise SystemExit(
            f"no event files under {run_dir}. The trainer writes results/<run-id>/ relative to "
            "the working directory, so run this from the repository root."
        )

    rows = to_rows(series, resolved_id)
    if not rows:
        raise SystemExit(
            f"{run_dir} has event files but no '{REFERENCE_TAG}' series, so there is no run to "
            "export. A run that stopped before its first summary has nothing to record."
        )

    return write_csv(rows, resolved_out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", help="the trainer's results/<run-id> directory")
    parser.add_argument("--out", default=None, help="target CSV (default results/rl/curves/<run-id>.csv)")
    parser.add_argument("--run-id", default=None, help="override the run id written into every row")
    args = parser.parse_args(argv)

    path = export(args.run_dir, args.out, args.run_id)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
