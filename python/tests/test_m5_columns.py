"""The four driver columns, and the seam rule every one of them depends on.

Differencing across the boundary between two runs invents a steering change no driver made.
Feature 002 hit it at the track1/track2 junction, feature 006 pinned it for the RL traces, and M5
now applies it to four columns at once, including two where the "run" is a track rather than a
drive. These tests pin the rule and the absences that are properties rather than gaps.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from python.m5 import columns as m5

REPO_ROOT = Path(__file__).resolve().parents[2]
INPUTS = REPO_ROOT / "results" / "comparison"

pytestmark = pytest.mark.skipif(
    not INPUTS.exists(), reason="comparison inputs not generated in this checkout"
)


def test_deltas_are_never_taken_across_a_run_boundary() -> None:
    """Two runs of two samples give two differences, not three."""
    frame = pd.DataFrame(
        {"run": ["a", "a", "b", "b"], "steering": [0.0, 0.1, 1.0, 1.1]}
    )

    deltas = m5.deltas_within_runs(frame)

    assert deltas.size == 2
    assert np.allclose(deltas, [0.1, 0.1])
    # The seam would be |1.0 - 0.1| = 0.9, an invented full-lock swing.
    assert 0.9 not in np.round(deltas, 6)


def test_one_delta_is_lost_per_run_and_that_is_correct() -> None:
    """The first sample of a run has no predecessor within it. Borrowing one is the seam bug."""
    frame = pd.DataFrame(
        {"run": ["a"] * 5 + ["b"] * 7, "steering": np.linspace(0, 1, 12)}
    )

    assert m5.deltas_within_runs(frame).size == 12 - 2


def test_rl_column_matches_the_independently_reported_figures() -> None:
    """Cross-checked against `python.rl.report`, which reads the raw traces by a different path."""
    column = m5.rl_column(REPO_ROOT, "ppo_car_009_bc", "deterministic")

    assert column.runs == 10
    assert column.steering.size == 8788
    assert column.steering_stats.mean == pytest.approx(-0.1859, abs=5e-4)
    assert column.steering_stats.variance == pytest.approx(0.03208, abs=5e-5)
    assert column.laps_completed == 10


def test_bc_column_reproduces_m4s_published_variance() -> None:
    """0.07182 is in `results/bc/run_bc_balanced_v01/distributions.json`, written by feature 004."""
    column = m5.bc_column(REPO_ROOT)

    assert column.steering_stats.variance == pytest.approx(0.07182, abs=5e-5)
    assert column.steering.size == 5576


def test_human_column_is_the_combined_dataset() -> None:
    """Not one track. Research R5: picking track1 alone reverses the variance comparison."""
    column = m5.human_column(REPO_ROOT)

    assert column.steering.size == 32443
    assert column.steering_stats.variance == pytest.approx(0.15149, abs=5e-5)
    assert column.straight_share == pytest.approx(0.586, abs=5e-3)


def test_bc_and_human_declare_their_absences_with_a_cause() -> None:
    """A blank cell reads as missing data. These are properties of the driver."""
    for column in (m5.bc_column(REPO_ROOT), m5.human_column(REPO_ROOT)):
        assert column.laps_completed is None
        assert column.lap_time_s is None
        assert column.absent_reason, f"{column.name} must say why the cells are empty"


def test_bc_has_no_speed_and_the_driving_columns_do() -> None:
    assert m5.bc_column(REPO_ROOT).speed is None
    assert m5.rl_column(REPO_ROOT, "ppo_car_009_bc", "deterministic").speed is not None
    assert m5.human_column(REPO_ROOT).speed is not None


def test_the_human_delta_is_a_discrete_input_signature() -> None:
    """Research R8, pinned so the artefact cannot quietly disappear from the reporting.

    If a future change made the human deltas look continuous, the smoothness comparison would
    silently become a statement about driving rather than about the input device.
    """
    column = m5.human_column(REPO_ROOT)
    deltas = column.abs_delta_steering
    nonzero = deltas[deltas > 0]

    on_grid = np.abs(nonzero / 0.05 - np.round(nonzero / 0.05)) < 1e-6
    assert np.mean(on_grid) > 0.6, "most human steering changes sit exactly on the 0.05 lattice"
    assert np.median(deltas) == 0.0, "the median human steering change is no change at all"

def test_lap_time_is_reported_per_lap_because_the_runs_are_not_the_same_length() -> None:
    """The run record's `lap_time_s` is the whole run, and the sweeps are not the same shape.

    The RL sweeps run three laps per attempt and the scripted sweep runs one. Printing the two raw
    figures in one column said the scripted driver was 2.6 times faster when it is slower per lap.
    Same class of error as comparing the two speed columns in different units.
    """
    rl = m5.rl_column(REPO_ROOT, "ppo_car_009_bc", "deterministic")
    scripted = m5.heuristic_column(REPO_ROOT)

    assert rl.laps_per_run == 3
    assert scripted.laps_per_run == 1
    assert rl.lap_time_s == pytest.approx(62.425, abs=5e-3)
    assert rl.seconds_per_lap == pytest.approx(62.425 / 3, abs=5e-3)
    assert scripted.seconds_per_lap == scripted.lap_time_s
    assert rl.seconds_per_lap < scripted.seconds_per_lap, "the raw figures reverse this"
