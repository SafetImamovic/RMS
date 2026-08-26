"""Tests for the learned column of the M5 comparison (feature 006, T052).

Three things are pinned here, and they are the three the module's own docstring calls out as
easy to get wrong:

- **Per-run differencing.** Concatenating runs and then differencing invents a steering change
  across the seam. The test constructs two runs whose seam would produce an obvious jump and
  asserts the jump is absent.
- **Resampling before differencing**, so the quantity is the change between two samples the
  comparison actually looks at.
- **An empty lap time is not a zero.** A failed run must not contribute a lap time of zero to
  any aggregate.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from python.rl import report
from python.track import config as track_config

TRACE_COLUMNS = [
    "t", "steering", "throttle", "brake", "speed", "speed_mag",
    "wheel_ms", "motor_nm", "headroom", "x", "y", "z", "yaw_deg", "source",
]


def _trace(steering: list[float], hz: float = 50.0, source: str = "test") -> pd.DataFrame:
    """A minimal drive log in the shape DriveLogger writes."""
    n = len(steering)
    frame = pd.DataFrame(
        {
            "t": np.arange(1, n + 1, dtype=float) / hz,
            "steering": np.asarray(steering, dtype=float),
            "throttle": np.zeros(n),
            "brake": np.zeros(n),
            "speed": np.zeros(n),
            "speed_mag": np.zeros(n),
            "wheel_ms": np.zeros(n),
            "motor_nm": np.zeros(n),
            "headroom": np.ones(n),
            "x": np.zeros(n),
            "y": np.zeros(n),
            "z": np.zeros(n),
            "yaw_deg": np.zeros(n),
            "source": source,
        }
    )
    return frame[TRACE_COLUMNS]


# --- the seam ------------------------------------------------------------------------------


def test_runs_are_differenced_separately_so_no_seam_jump_is_invented():
    # Run A sits at -1.0 throughout, run B at +1.0. Concatenating first and differencing after
    # would produce a single |delta| of 2.0 at the join, which no driver ever commanded.
    seconds = 4.0
    n = int(seconds * 50)
    run_a = _trace([-1.0] * n)
    run_b = _trace([+1.0] * n)

    _, delta = report.steering_series([run_a, run_b])

    assert delta.size > 0
    assert delta.max() == pytest.approx(0.0, abs=1e-9), (
        "a non-zero change can only have come from differencing across the seam"
    )


def test_the_seam_jump_is_what_the_wrong_order_would_produce():
    # The guard above is only meaningful if the wrong order really would show a jump. Pin that,
    # so the test cannot pass because the fixture happens to be flat.
    seconds = 4.0
    n = int(seconds * 50)
    run_a = _trace([-1.0] * n)
    run_b = _trace([+1.0] * n)

    concatenated = np.concatenate(
        [run_a["steering"].to_numpy(), run_b["steering"].to_numpy()]
    )
    wrong = np.abs(np.diff(concatenated))

    assert wrong.max() == pytest.approx(2.0)


def test_each_run_loses_exactly_one_sample_to_differencing():
    # np.diff drops the first sample of each run, because within that run it has no predecessor.
    # Two runs therefore lose two samples, not one.
    run_a = _trace([0.1] * 200)
    run_b = _trace([0.2] * 200)

    steer, delta = report.steering_series([run_a, run_b])

    assert delta.size == steer.size - 2


# --- resampling ----------------------------------------------------------------------------


def test_series_are_taken_at_the_compare_rate_not_the_raw_rate():
    # 10 s at 50 Hz is 500 raw samples and about 141 at COMPARE_HZ. The difference matters:
    # |delta steering| over a 50 Hz step is a smaller number than over a 14.08 Hz step, and the
    # human figure this is compared against was measured at COMPARE_HZ.
    seconds = 10.0
    raw = int(seconds * 50)
    run = _trace(list(np.linspace(-1.0, 1.0, raw)))

    steer, _ = report.steering_series([run])

    expected = int(seconds * track_config.COMPARE_HZ)
    assert steer.size == pytest.approx(expected, abs=2)
    assert steer.size < raw


def test_differencing_happens_after_resampling():
    # A ramp gives a constant step whose size depends entirely on the rate it was measured at.
    seconds = 10.0
    raw = int(seconds * 50)
    run = _trace(list(np.linspace(0.0, 1.0, raw)))

    _, delta = report.steering_series([run])

    at_compare_hz = 1.0 / (seconds * track_config.COMPARE_HZ)
    at_raw_hz = 1.0 / raw
    assert delta.mean() == pytest.approx(at_compare_hz, rel=0.1)
    assert delta.mean() > at_raw_hz * 2, "this is the raw-rate step, so differencing came first"


# --- the empty lap time --------------------------------------------------------------------


def test_a_failed_run_has_no_lap_time_rather_than_a_zero(tmp_path: Path):
    csv = tmp_path / "runs.csv"
    csv.write_text(
        "seed,controller,ray_count,ray_fov_deg,ray_length_m,completed_lap,lap_time_s,"
        "checkpoints_awarded,checkpoints_total,checkpoints_skipped,wall_contacts,end_reason,"
        "steer_p95_dsteer,steer_sign_changes_per_s,time_scale,duration_s\n"
        "1,x,13,180,20,true,42.5,24,24,0,0,LapsCompleted,0.1,0.2,4,42.5\n"
        "2,x,13,180,20,false,,0,24,0,0,Stalled,0.1,0.2,4,60.0\n",
        encoding="utf-8",
    )

    runs = report.load_runs(csv)

    assert runs["lap_time_s"].isna().sum() == 1
    assert (runs["lap_time_s"] == 0).sum() == 0
    # The mean must be the one completed lap, not an average dragged down by a zero.
    assert runs["lap_time_s"].mean() == pytest.approx(42.5)


# --- the lattice the comparison counts on ---------------------------------------------------


def test_lattice_support_is_the_datasets_own_grid():
    support = report.lattice_support()

    assert support.size == 41
    assert support[0] == pytest.approx(-1.0)
    assert support[-1] == pytest.approx(1.0)
    assert np.allclose(np.diff(support), report.LATTICE_STEP)


def test_values_are_counted_into_the_nearest_lattice_point():
    support = report.lattice_support()
    # 0.0 lands on a point; 0.06 is nearest 0.05; -0.99 is nearest -1.0.
    counts = report.counts_on_lattice(np.array([0.0, 0.06, -0.99]), support)

    assert counts.sum() == 3
    assert counts[np.argmin(np.abs(support - 0.0))] == 1
    assert counts[np.argmin(np.abs(support - 0.05))] == 1
    assert counts[np.argmin(np.abs(support + 1.0))] == 1


def test_a_trace_directory_with_no_files_is_an_error_rather_than_an_empty_column(tmp_path: Path):
    with pytest.raises(ValueError, match="no traces"):
        report.load_trace_dir(tmp_path)


# --- feature 007: the markers a zero lap count hides -----------------------------------------


def _runs_csv(path: Path, rows: str) -> Path:
    path.write_text(
        "seed,controller,ray_count,ray_fov_deg,ray_length_m,completed_lap,lap_time_s,"
        "checkpoints_awarded,checkpoints_total,checkpoints_skipped,wall_contacts,end_reason,"
        "steer_p95_dsteer,steer_sign_changes_per_s,time_scale,duration_s\n" + rows,
        encoding="utf-8",
    )
    return path


def _traces(directory: Path, count: int = 2) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        _trace([0.0, 0.1, -0.1, 0.2] * 20).to_csv(directory / f"run_{i:02d}.csv", index=False)
    return directory


def test_the_column_carries_markers_so_two_zero_lap_drivers_can_be_told_apart(tmp_path: Path):
    # This is the whole point of the field. Feature 006's learned column and feature 007's both
    # read zero laps; one never moved and the other drove a quarter of the lap.
    stalled = report.build_column(
        "stalled",
        _runs_csv(tmp_path / "a.csv",
                  "1,x,13,180,20,false,,0,24,0,0,Stalled,0.1,0.2,4,60.0\n"
                  "2,x,13,180,20,false,,0,24,0,0,Stalled,0.1,0.2,4,60.0\n"),
        _traces(tmp_path / "ta"),
    )
    driving = report.build_column(
        "driving",
        _runs_csv(tmp_path / "b.csv",
                  "1,x,13,180,20,false,,8,24,0,1,WallContact,0.1,0.2,4,9.5\n"
                  "2,x,13,180,20,false,,4,24,0,1,WallContact,0.1,0.2,4,5.2\n"),
        _traces(tmp_path / "tb"),
    )

    assert stalled.laps_completed == driving.laps_completed == 0
    assert stalled.markers_mean == 0.0
    assert driving.markers_mean == pytest.approx(6.0)
    assert driving.marker_rate == pytest.approx(0.25)


def test_end_reasons_are_counted_rather_than_summarised(tmp_path: Path):
    column = report.build_column(
        "mixed",
        _runs_csv(tmp_path / "runs.csv",
                  "1,x,13,180,20,false,,8,24,0,1,WallContact,0.1,0.2,4,9.5\n"
                  "2,x,13,180,20,false,,0,24,0,0,Stalled,0.1,0.2,4,60.0\n"
                  "3,x,13,180,20,false,,5,24,0,1,WallContact,0.1,0.2,4,6.0\n"),
        _traces(tmp_path / "t"),
    )

    assert column.end_reasons["WallContact"] == 2
    assert column.end_reasons["Stalled"] == 1


def test_a_completed_lap_is_counted_whether_written_true_or_one(tmp_path: Path):
    # Committed run records carry both spellings, because the writer changed between features and
    # the older files were not rewritten. A column that read only one would under-report laps.
    column = report.build_column(
        "mixed-spelling",
        _runs_csv(tmp_path / "runs.csv",
                  "1,x,13,180,20,true,42.5,24,24,0,0,LapsCompleted,0.1,0.2,4,42.5\n"
                  "2,x,13,180,20,1,41.0,24,24,0,0,LapsCompleted,0.1,0.2,4,41.0\n"
                  "3,x,13,180,20,false,,3,24,0,1,WallContact,0.1,0.2,4,5.0\n"),
        _traces(tmp_path / "t"),
    )

    assert column.laps_completed == 2
    assert column.lap_rate == pytest.approx(2 / 3)


# --- feature 008: barrier use beside the lap count ---------------------------------------------


def test_the_column_carries_wall_contacts(tmp_path: Path):
    column = report.build_column(
        "contacts",
        _runs_csv(tmp_path / "runs.csv",
                  "1,x,13,180,20,false,,8,24,0,3,WallContact,0.1,0.2,4,9.5\n"
                  "2,x,13,180,20,false,,4,24,0,1,WallContact,0.1,0.2,4,5.2\n"),
        _traces(tmp_path / "t"),
    )

    assert column.wall_contacts_mean == pytest.approx(2.0)


def test_two_drivers_with_equal_markers_are_separated_by_their_contacts(tmp_path: Path):
    # The reading feature 008 exists to make possible. Same markers, same zero laps, and one of
    # them got there by bouncing off the barriers.
    clean = report.build_column(
        "clean",
        _runs_csv(tmp_path / "a.csv",
                  "1,x,13,180,20,false,,6,24,0,0,Stalled,0.1,0.2,4,60.0\n"),
        _traces(tmp_path / "ta"),
    )
    scraping = report.build_column(
        "scraping",
        _runs_csv(tmp_path / "b.csv",
                  "1,x,13,180,20,false,,6,24,0,5,WallContact,0.1,0.2,4,12.0\n"),
        _traces(tmp_path / "tb"),
    )

    assert clean.markers_mean == scraping.markers_mean
    assert clean.laps_completed == scraping.laps_completed == 0
    assert clean.wall_contacts_mean == 0.0
    assert scraping.wall_contacts_mean == 5.0
