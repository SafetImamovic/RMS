"""The committed comparison inputs against the sources they were exported from.

**The whole M5 comparison now reads committed CSVs rather than the raw traces and the Kaggle
dataset**, because neither is in the repository and a clean clone could otherwise not rebuild a
single figure. That trade buys reproducibility and costs a new failure mode: an export that has
drifted from its source is a number nobody can check, and it would drift silently.

These tests are the check. Each is skipped when its source is absent, so a clean clone stays green
while the machine that holds the dataset and the traces verifies the exports on every run.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from python.m5 import columns as m5
from python.rl import comparison_inputs

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "dataset" / "dataset" / "dataset" / "driving_log.csv"
HEURISTIC_RUNS = REPO_ROOT / "results" / "heuristic" / "runs_2026-08-16_15-27-50.csv"
EXPORTS = REPO_ROOT / "results" / "comparison"

pytestmark = pytest.mark.skipif(
    not EXPORTS.exists(), reason="comparison inputs not generated in this checkout"
)


@pytest.mark.skipif(not DATASET.exists(), reason="dataset is gitignored and not present")
def test_the_human_export_still_matches_the_dataset_row_for_row() -> None:
    """Not a statistic comparison. Every steering and speed value, in order."""
    exported = pd.read_csv(EXPORTS / "steering_human_combined.csv", comment="#")
    source = comparison_inputs.export_human(DATASET)

    assert len(exported) == len(source) == 32443
    pd.testing.assert_series_equal(
        exported["steering"], source["steering"], check_names=False
    )
    pd.testing.assert_series_equal(exported["speed"], source["speed"], check_names=False)


@pytest.mark.skipif(not DATASET.exists(), reason="dataset is gitignored and not present")
def test_the_seam_survives_the_export() -> None:
    """Two recording sessions in, two out. A collapsed run column would let a difference cross the
    track1 to track2 junction, which is the defect feature 002 found."""
    exported = pd.read_csv(EXPORTS / "steering_human_combined.csv", comment="#")

    assert set(exported["run"].unique()) == {"track1", "track2"}
    assert m5.human_column(REPO_ROOT).abs_delta_steering.size == 32443 - 2


@pytest.mark.skipif(not HEURISTIC_RUNS.exists(), reason="run record is gitignored, not present")
def test_the_heuristic_run_record_export_matches_its_source() -> None:
    exported = pd.read_csv(EXPORTS / "runs_heuristic_weighted_average.csv")
    source = comparison_inputs.export_heuristic_runs(HEURISTIC_RUNS)

    assert len(exported) == len(source) == 34
    pd.testing.assert_frame_equal(exported, source, check_dtype=False)


def test_every_column_the_comparison_needs_builds_without_the_dataset() -> None:
    """SC-006, as a test rather than as a claim.

    This is the assertion that would have failed before the human and run-record exports existed,
    and it fails again the moment a column reaches back to a gitignored path.
    """
    for column in (
        m5.rl_column(REPO_ROOT, "ppo_car_009_bc", "deterministic"),
        m5.rl_column(REPO_ROOT, "ppo_car_009_bc", "sampling"),
        m5.heuristic_column(REPO_ROOT),
        m5.bc_column(REPO_ROOT),
        m5.human_column(REPO_ROOT),
    ):
        assert column.steering.size > 0
        assert column.runs >= 1

    heuristic = m5.heuristic_column(REPO_ROOT)
    assert heuristic.laps_completed == 34, "the run record must fill the DESIGN 7 cells"
    assert heuristic.lap_time_s == pytest.approx(23.655, abs=5e-3)
