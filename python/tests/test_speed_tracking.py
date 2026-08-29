"""Speed tracking from a drive log (feature 009, T017).

The case that matters is the **empty** ``target_speed``. Every scene but the demonstration
scene writes that column empty, because no scripted driver is present to have a target. A
reader that treated empty as ``0.0`` would report the car's own speed as a tracking error
and it would look entirely plausible doing it, so there is a test for the empty field and a
separate test for a literal zero, which is a real target the driver can ask for when it
wants the car stopped.

Fixtures are written to ``tmp_path``. Nothing here reads ``results/drive_logs``: a test that
depends on a run somebody happened to record is a test that passes for the wrong reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from python.heuristic import speed_tracking as st

HEADER = ("t,steering,throttle,brake,speed,speed_mag,wheel_ms,motor_nm,headroom,"
          "x,y,z,yaw_deg,target_speed,source")


def row(t: float = 0.02, speed: float = 5.0, target: str = "5.00000",
        source: str = "heuristic_train34") -> str:
    return (f"{t:.4f},0.00000,1.0000,0.0000,{speed:.5f},{speed:.5f},{speed:.5f},"
            f"100.0,0.0000,0.0000,0.5000,0.0000,0.000,{target},{source}")


def write(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join([HEADER] + rows) + "\n", encoding="utf-8")
    return path


def test_mae_is_the_mean_absolute_difference(tmp_path: Path) -> None:
    trace = write(tmp_path / "run.csv", [
        row(speed=5.0, target="5.00000"),   # 0.0
        row(speed=4.0, target="5.00000"),   # 1.0
        row(speed=7.0, target="5.00000"),   # 2.0
    ])

    result = st.load(trace)

    assert result.rows == 3
    assert result.tracked == 3
    assert result.mae == pytest.approx(1.0)
    assert result.max_abs == pytest.approx(2.0)
    assert result.coverage == pytest.approx(1.0)


def test_empty_target_is_skipped_rather_than_read_as_zero(tmp_path: Path) -> None:
    """A trace from a scene with no scripted driver has no tracking error at all."""
    trace = write(tmp_path / "policy.csv", [
        row(speed=6.0, target="", source="ppo_car_008"),
        row(speed=7.0, target="", source="ppo_car_008"),
    ])

    result = st.load(trace)

    assert result.rows == 2
    assert result.tracked == 0
    assert result.mae is None
    assert result.max_abs is None
    assert result.coverage == pytest.approx(0.0)


def test_a_literal_zero_target_is_a_real_target(tmp_path: Path) -> None:
    """Asking for a standstill is a decision. It is not the same as asking for nothing."""
    trace = write(tmp_path / "stopped.csv", [
        row(speed=2.0, target="0.00000"),
    ])

    result = st.load(trace)

    assert result.tracked == 1
    assert result.mae == pytest.approx(2.0)
    assert result.mean_target == pytest.approx(0.0)


def test_a_partly_tracked_trace_reports_its_coverage(tmp_path: Path) -> None:
    """Coverage is what says whether a mean was taken over the whole run or a corner of it."""
    trace = write(tmp_path / "mixed.csv", [
        row(speed=5.0, target="5.00000"),
        row(speed=5.0, target=""),
        row(speed=3.0, target="5.00000"),
        row(speed=5.0, target=""),
    ])

    result = st.load(trace)

    assert result.rows == 4
    assert result.tracked == 2
    assert result.coverage == pytest.approx(0.5)
    assert result.mae == pytest.approx(1.0)


def test_a_trace_with_no_rows_does_not_divide_by_zero(tmp_path: Path) -> None:
    trace = write(tmp_path / "empty.csv", [])

    result = st.load(trace)

    assert result.rows == 0
    assert result.tracked == 0
    assert result.mae is None
    assert result.coverage == pytest.approx(0.0)


def test_a_folder_reads_every_trace_in_name_order(tmp_path: Path) -> None:
    write(tmp_path / "b.csv", [row(speed=4.0, target="5.00000")])
    write(tmp_path / "a.csv", [row(speed=5.0, target="5.00000")])

    results = st.load_folder(tmp_path)

    assert [r.path.name for r in results] == ["a.csv", "b.csv"]
    assert results[0].mae == pytest.approx(0.0)
    assert results[1].mae == pytest.approx(1.0)


def test_the_table_names_an_untracked_trace_rather_than_omitting_it(tmp_path: Path) -> None:
    """A trace that recorded no target is a fact about the scene, so it stays in the table."""
    write(tmp_path / "a.csv", [row(speed=4.0, target="5.00000")])
    write(tmp_path / "b.csv", [row(speed=4.0, target="")])

    text = st.format_table(st.load_folder(tmp_path))

    assert "a.csv" in text
    assert "b.csv" in text
    assert "0.25 m/s" in text
