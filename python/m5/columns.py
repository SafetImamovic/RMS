"""The four driver columns of `DESIGN.md` 7, built from committed inputs.

**Every column comes from `results/comparison/`**, not from raw traces, so this module runs from a
clean clone. `python/rl/comparison_inputs.py` and `python/bc/export_predictions.py` produce those
files and are the only things that need the traces or torch.

**What a column can and cannot have is a property of the driver, not an omission.** The BC model
predicts steering from camera images of another simulator: it never drives a lap, so it has no lap
completion, no lap time and no track. Those cells are `None` and the report prints the cause. The
human column is a recording, not a driver in this simulator, so it has no laps either. Filling
either with a proxy would be inventing a comparison.

**Differences are taken within a run.** Every input file carries a `run` column for exactly this
reason: a difference across the seam between two runs invents a steering change no driver made.
Feature 002 hit that at the track1/track2 junction and it is pinned by tests here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from python.eda.stats import DistributionSummary, describe

COMPARISON_DIR = Path("results") / "comparison"

# The combined dataset, being track1 plus track2. `python/bc/config.py` sets
# DATASET_NAME = "combined", so every existing figure including M4's KL uses it. Research R5
# records what happens if a single track is used instead: the straight-line share moves from 58.6
# to 79.3 per cent and the variance comparison against the RL policy reverses outright.
HUMAN_CSV = Path("dataset") / "dataset" / "dataset" / "driving_log.csv"
HUMAN_COLUMNS = ["center", "left", "right", "steering", "throttle", "brake", "speed"]


@dataclass(frozen=True)
class DriverColumn:
    """One column of the comparison table.

    `laps_completed` and `lap_time_s` are `None` where the driver does not drive. `absent_reason`
    says why, and the report prints it in the cell rather than leaving a blank a reader would take
    for missing data.
    """

    name: str
    steering: np.ndarray
    abs_delta_steering: np.ndarray
    speed: np.ndarray | None
    runs: int

    # Samples per run, in the order they appear in `steering`. Carried so any consumer that needs
    # to re-derive differences, for instance after quantising, can honour the same seam rule
    # instead of differencing straight through a run boundary.
    run_sizes: tuple[int, ...]
    laps_completed: int | None
    laps_possible: int | None
    lap_time_s: float | None
    wall_contacts: float | None
    absent_reason: str | None

    @property
    def steering_stats(self) -> DistributionSummary:
        return describe(self.steering, f"{self.name}_steering")

    @property
    def delta_stats(self) -> DistributionSummary:
        return describe(self.abs_delta_steering, f"{self.name}_abs_delta_steering")

    @property
    def speed_stats(self) -> DistributionSummary | None:
        return describe(self.speed, f"{self.name}_speed") if self.speed is not None else None

    @property
    def straight_share(self) -> float:
        """Share of samples within a quarter of a lattice step of zero.

        The artefact number that has to sit beside every steering-level comparison (research R5).
        A tolerance rather than exact equality, because only the human column is on the lattice:
        asking a continuous policy for exact zeros would report 0.0 for a reason that is about
        floating point rather than about driving.
        """
        return float(np.mean(np.abs(self.steering) < 0.0125))

    @property
    def left_share(self) -> float:
        return float(np.mean(self.steering < 0))

    @property
    def right_share(self) -> float:
        return float(np.mean(self.steering > 0))


def run_sizes_of(frame: pd.DataFrame) -> tuple[int, ...]:
    """Samples per run, in file order."""
    return tuple(int(len(g)) for _, g in frame.groupby("run", sort=False))


def deltas_within_runs(frame: pd.DataFrame, column: str = "steering") -> np.ndarray:
    """`|delta|` per run, concatenated. Never across a run boundary."""
    parts = [
        np.abs(np.diff(group[column].to_numpy(dtype=float)))
        for _, group in frame.groupby("run", sort=False)
    ]
    return np.concatenate(parts) if parts else np.array([])


def _driving_column(
    name: str,
    steering_csv: Path,
    runs_csv: Path | None,
    laps_per_run: int,
) -> DriverColumn:
    frame = pd.read_csv(steering_csv, comment="#")
    steering = frame["steering"].to_numpy(dtype=float)
    speed = frame["speed"].to_numpy(dtype=float) if "speed" in frame else None

    laps = lap_time = contacts = None
    if runs_csv is not None and runs_csv.exists():
        runs = pd.read_csv(runs_csv)
        completed = runs["completed_lap"].astype(str).str.lower().isin(("true", "1"))
        laps = int(completed.sum())
        finished = runs.loc[completed, "lap_time_s"].dropna()
        lap_time = float(finished.mean()) if len(finished) else None
        contacts = float(runs["wall_contacts"].mean()) if "wall_contacts" in runs else None

    return DriverColumn(
        name=name,
        steering=steering,
        abs_delta_steering=deltas_within_runs(frame),
        speed=speed,
        runs=int(frame["run"].nunique()),
        run_sizes=run_sizes_of(frame),
        laps_completed=laps,
        laps_possible=int(frame["run"].nunique()) if laps is not None else None,
        lap_time_s=lap_time,
        wall_contacts=contacts,
        absent_reason=None,
    )


def rl_column(root: Path, run_id: str, inference: str) -> DriverColumn:
    return _driving_column(
        name=f"{run_id}_{inference}",
        steering_csv=root / COMPARISON_DIR / f"steering_{run_id}_{inference}.csv",
        runs_csv=root / "results" / "rl" / f"eval_{run_id}_{inference}.csv",
        laps_per_run=3,
    )


def heuristic_column(root: Path, runs_csv: Path | None = None) -> DriverColumn:
    return _driving_column(
        name="heuristic_weighted_average",
        steering_csv=root / COMPARISON_DIR / "steering_heuristic_weighted_average.csv",
        runs_csv=runs_csv,
        laps_per_run=1,
    )


def bc_column(root: Path, run_id: str = "bc_balanced_v01") -> DriverColumn:
    """The BC model's predictions over the validation split.

    **The `run` column here is the track, not a drive.** BC produces one prediction per dataset row
    and never drives, so "within a run" means "within a track": differencing across the
    track1/track2 junction is the seam feature 002 found, and it is the same mistake here.
    """
    frame = pd.read_csv(root / COMPARISON_DIR / f"bc_predictions_{run_id}.csv", comment="#")
    frame = frame.rename(columns={"predicted_steering": "steering", "track": "run"})

    return DriverColumn(
        name=f"bc_{run_id}",
        steering=frame["steering"].to_numpy(dtype=float),
        abs_delta_steering=deltas_within_runs(frame),
        speed=None,
        runs=int(frame["run"].nunique()),
        run_sizes=run_sizes_of(frame),
        laps_completed=None,
        laps_possible=None,
        lap_time_s=None,
        wall_contacts=None,
        absent_reason=(
            "trained on camera images from another simulator, so it never drives this track: "
            "no lap completion, no lap time, no wall contacts, no speed"
        ),
    )


def human_column(root: Path, csv: Path | None = None) -> DriverColumn:
    """The human reference, from the combined dataset.

    **The `run` column is the recording session, derived from the centre-image path.** The dataset
    is two recordings concatenated, and differencing across their junction is exactly the seam
    feature 002 documented.
    """
    path = csv or (root / HUMAN_CSV)
    frame = pd.read_csv(path, header=None, names=HUMAN_COLUMNS)
    frame["run"] = frame["center"].astype(str).str.extract(r"(track\d)", expand=False).fillna("unknown")

    return DriverColumn(
        name="human_combined",
        steering=frame["steering"].to_numpy(dtype=float),
        abs_delta_steering=deltas_within_runs(frame),
        speed=frame["speed"].to_numpy(dtype=float),
        runs=int(frame["run"].nunique()),
        run_sizes=run_sizes_of(frame),
        laps_completed=None,
        laps_possible=None,
        lap_time_s=None,
        wall_contacts=None,
        absent_reason=(
            "a recording of a different simulator, not a driver in this one: no lap completion "
            "and no lap time on these tracks"
        ),
    )
