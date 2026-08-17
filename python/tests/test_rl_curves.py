"""The committed curve export keeps what the trainer wrote (feature 006, T033).

The rules under test are the ones a plausible-looking export would quietly break: smoothing,
resampling onto a nicer grid, and writing zero where the trainer wrote nothing. Each of those
produces a file that reads fine and is not the run.

Only the shaping half is exercised here. Reading event files needs the reader that ships with the
trainer's TensorBoard dependency, which lives in ``.venv-mlagents``; ``to_rows`` and ``write_csv``
are pure, so this suite stays runnable under ``.venv`` with the rest of the analysis.
"""

from __future__ import annotations

import csv

import pytest

from python.rl import export_curves


REFERENCE = export_curves.REFERENCE_TAG


def series(**tags):
    """Build a tag -> {step: value} mapping the way the reader returns one."""
    return {tag.replace("__", "/"): points for tag, points in tags.items()}


def test_rows_land_on_the_trainers_own_steps():
    data = {REFERENCE: {10000: 1.5, 20000: 2.5, 30000: 3.5}}

    rows = export_curves.to_rows(data, "ppo_car_v01")

    assert [row["step"] for row in rows] == [10000, 20000, 30000]
    assert [row["cumulative_reward"] for row in rows] == [1.5, 2.5, 3.5]


def test_values_are_written_exactly_as_recorded():
    # A smoothed export would round the spikes off this series, and nothing in the file would say
    # it had happened.
    data = {REFERENCE: {10000: -5.0, 20000: 12.75, 30000: -4.125}}

    rows = export_curves.to_rows(data, "run")

    assert [row["cumulative_reward"] for row in rows] == [-5.0, 12.75, -4.125]


def test_run_id_is_repeated_on_every_row():
    data = {REFERENCE: {10000: 1.0, 20000: 1.0}}

    rows = export_curves.to_rows(data, "ppo_car_spread_a")

    assert all(row["run_id"] == "ppo_car_spread_a" for row in rows)


def test_a_missing_series_writes_empty_rather_than_zero():
    # The distinction matters: zero is a value a loss can take, and averaging absent points as
    # zeros reports a run that did not happen.
    data = {REFERENCE: {10000: 1.0}}

    rows = export_curves.to_rows(data, "run")

    assert rows[0]["policy_loss"] == ""
    assert rows[0]["reward_checkpoint"] == ""


def test_a_gap_inside_a_series_writes_empty_at_that_step_only():
    data = {
        REFERENCE: {10000: 1.0, 20000: 2.0, 30000: 3.0},
        "reward/checkpoint": {10000: 0.5, 30000: 1.5},
    }

    rows = export_curves.to_rows(data, "run")

    assert [row["reward_checkpoint"] for row in rows] == [0.5, "", 1.5]


def test_zero_is_preserved_and_not_confused_with_absent():
    data = {
        REFERENCE: {10000: 1.0},
        "reward/wall": {10000: 0.0},
    }

    rows = export_curves.to_rows(data, "run")

    assert rows[0]["reward_wall"] == 0.0
    assert rows[0]["reward_wall"] != ""


def test_all_six_reward_terms_have_a_column():
    # These are the series this feature adds, and the reason the export exists: a rising total does
    # not say which term raised it.
    names = [name for name, _ in export_curves.COLUMNS]

    for term in ("checkpoint", "wrong_way", "wall", "step", "speed", "jerk"):
        assert f"reward_{term}" in names


def test_a_run_that_stopped_early_exports_the_rows_it_has():
    data = {
        REFERENCE: {10000: 1.0, 20000: 2.0},
        "Losses/Policy Loss": {10000: 0.3},
    }

    rows = export_curves.to_rows(data, "interrupted")

    assert len(rows) == 2
    assert rows[1]["policy_loss"] == ""


def test_no_rows_when_the_reference_series_is_absent():
    # A run that never reached its first summary has nothing to record, and an export that invented
    # rows from the other series would be reporting a run that did not happen.
    data = {"Losses/Policy Loss": {10000: 0.3}}

    assert export_curves.to_rows(data, "run") == []


def test_written_csv_has_the_contract_header_and_order(tmp_path):
    data = {
        REFERENCE: {10000: 1.0},
        "Environment/Episode Length": {10000: 240.0},
        "reward/speed": {10000: 0.02},
    }
    out = tmp_path / "curve.csv"

    export_curves.write_csv(export_curves.to_rows(data, "run"), str(out))

    with open(out, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        row = next(reader)

    assert header == list(export_curves.HEADER)
    assert header[:2] == ["run_id", "step"]
    assert row[header.index("episode_length")] == "240.0"
    assert row[header.index("reward_wall")] == ""


def test_write_creates_the_target_directory(tmp_path):
    out = tmp_path / "curves" / "nested" / "run.csv"

    export_curves.write_csv([{"run_id": "r", "step": 1}], str(out))

    assert out.exists()


@pytest.mark.parametrize("column", ["run_id", "step"])
def test_identity_columns_come_first(column):
    assert column in export_curves.HEADER[:2]
