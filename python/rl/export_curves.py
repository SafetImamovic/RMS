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

The per-term reward series are added through ``StatsRecorder`` on the Unity side. They are the
reason the export exists at all: a total that rises does not say which term raised it, and a flat
``reward/checkpoint`` beneath a rising total is a policy collecting speed and step reward without
going anywhere. Feature 006 wrote six of them; feature 007 made it seven by adding
``reward/progress``, which is also why cumulative reward is not comparable across the two (FR-018).

The behavioural columns are feature 007's, and they are the ones SC-003 and SC-004 are actually
read on. ``markers_per_episode`` and ``reward/progress`` come straight from the trainer;
``LapsCompleted`` in the data model is the existing ``end_lapscompleted`` count and is not
duplicated under a second name; ``stalled_share`` is derived here so that every reader takes it
over the same denominator.

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
    # Feature 007's own term, and the reason cumulative reward is not comparable against any 006
    # run: the table gained a column, so the total it sums to is on a different scale (FR-018).
    ("reward_progress", "reward/progress"),
    # The behavioural metric SC-003 is judged on. Exported beside the reward terms because the
    # question this feature asks is whether the car reaches more markers, not whether the number
    # the trainer prints went up.
    ("markers_per_episode", "episode/markers"),
    # R6's two counts, side by side. The ratio between them should sit at the decision period of
    # 4; feature 006 measured a mean near 3.16 with no way to say why, because only the trainer's
    # half was ever written down.
    ("physics_steps_charged", "episode/physics_steps"),
    # Feature 008. Markers per episode cannot be read without the contact count, and the contact
    # count cannot see a sustained grind, because OnCollisionEnter fires once per touch and not
    # once per step. Lateral clearance is the measure that can, and it is a proxy: it reads how
    # close the car runs to whatever the side rays see, which on these tracks is the barriers.
    ("wall_contacts", "episode/wall_contacts"),
    ("lateral_clearance", "episode/lateral_clearance"),
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

#: Columns computed from the exported ones rather than read from a tag. They are written into the
#: file rather than left to each reader, because a share recomputed three times in three notebooks
#: is three chances to pick a different denominator.
DERIVED: Sequence[str] = ("stalled_share",)

#: The end-reason counts a share is taken over. They are sums rather than means, which is what
#: makes them a denominator at all; a run trained before that change exports them empty, and a
#: share over an empty denominator is empty rather than zero.
END_REASON_COLUMNS: Sequence[str] = (
    "end_wallcontact",
    "end_lapscompleted",
    "end_stalled",
    "end_steplimit",
    "end_trackswapped",
)

HEADER: Sequence[str] = (
    ("run_id", "step") + tuple(name for name, _ in COLUMNS) + tuple(DERIVED)
)

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

        row["stalled_share"] = stalled_share(row)

        rows.append(row)

    return rows


def stalled_share(row: Mapping[str, object]) -> object:
    """The share of the summary's episodes that ended stalled, or empty when it cannot be taken.

    SC-003's second acceptance scenario is that the stall share falls without the wall share simply
    rising to replace it, which is a question about proportions and therefore needs a denominator
    everybody agrees on. That denominator is every end reason the agent reports, so a stall traded
    for a wall contact shows up as one share falling and another rising rather than as a single
    number that improved.

    Empty, not zero, when no end reason was recorded at that step: a summary with no episode ends
    has no share, and zero would read as "nothing stalled".
    """
    total = 0.0
    seen = False

    for name in END_REASON_COLUMNS:
        value = row.get(name)
        if value == "" or value is None:
            continue
        total += float(value)
        seen = True

    if not seen or total <= 0.0:
        return ""

    stalled = row.get("end_stalled")
    return 0.0 if stalled == "" or stalled is None else float(stalled) / total


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
