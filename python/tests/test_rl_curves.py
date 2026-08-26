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


def test_all_five_end_reasons_have_a_column():
    # T036 asks for a distribution, and a distribution needs every reason the agent can record,
    # including the ones a healthy run never produces. `end_lapscompleted` absent from the schema
    # would hide the difference between "no lap was completed" and "laps were not counted".
    names = [name for name, _ in export_curves.COLUMNS]

    for reason in ("wallcontact", "lapscompleted", "stalled", "steplimit", "trackswapped"):
        assert f"end_{reason}" in names


def test_an_end_reason_that_never_occurred_writes_empty_rather_than_zero():
    # The distinction the whole export turns on, applied to the counts. A reason absent from the
    # event file means the trainer recorded nothing, which is not the same claim as "it happened
    # zero times", and only one of those two is safe to average across runs.
    data = {
        REFERENCE: {10000: -4.0},
        "episode/end_wallcontact": {10000: 41.0},
    }

    rows = export_curves.to_rows(data, "counts")

    assert rows[0]["end_wallcontact"] == 41.0
    assert rows[0]["end_lapscompleted"] == ""


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


# --- feature 007: the progress term and the behavioural columns ------------------------------


def test_the_progress_term_is_exported_under_its_own_column():
    # The seventh reward term. A run whose total moved without this column moving is a run whose
    # total moved for some other reason, and that distinction is the whole point of the export.
    data = {
        REFERENCE: {10000: -4.0, 20000: -1.5},
        "reward/progress": {10000: 0.8, 20000: 3.2},
    }

    rows = export_curves.to_rows(data, "run")

    assert [row["reward_progress"] for row in rows] == [0.8, 3.2]


def test_markers_per_episode_is_exported_for_sc_003():
    data = {
        REFERENCE: {10000: -4.0},
        "episode/markers": {10000: 0.249},
    }

    rows = export_curves.to_rows(data, "run")

    assert rows[0]["markers_per_episode"] == 0.249


def test_a_run_without_the_new_series_exports_them_empty():
    # Every feature 006 run is one of these. Exporting a zero would put those runs on this
    # feature's axes as though they had scored nothing, rather than as though they never played.
    data = {REFERENCE: {10000: -4.0}}

    rows = export_curves.to_rows(data, "ppo_car_v01")

    assert rows[0]["reward_progress"] == ""
    assert rows[0]["markers_per_episode"] == ""
    assert rows[0]["stalled_share"] == ""


def test_stalled_share_is_taken_over_every_end_reason():
    data = {
        REFERENCE: {10000: -4.0},
        "episode/end_stalled": {10000: 30.0},
        "episode/end_wallcontact": {10000: 60.0},
        "episode/end_steplimit": {10000: 10.0},
    }

    rows = export_curves.to_rows(data, "run")

    assert rows[0]["stalled_share"] == pytest.approx(0.3)


def test_a_stall_traded_for_a_wall_contact_moves_both_shares():
    # SC-003's second acceptance scenario. A stall share that falls because the wall share rose is
    # not the mechanism working, and reading it over a fixed denominator is what makes the two
    # movements visible at once rather than one summary number improving.
    before = export_curves.to_rows(
        {
            REFERENCE: {10000: -4.0},
            "episode/end_stalled": {10000: 80.0},
            "episode/end_wallcontact": {10000: 20.0},
        },
        "run",
    )
    after = export_curves.to_rows(
        {
            REFERENCE: {10000: -4.0},
            "episode/end_stalled": {10000: 40.0},
            "episode/end_wallcontact": {10000: 60.0},
        },
        "run",
    )

    assert before[0]["stalled_share"] == pytest.approx(0.8)
    assert after[0]["stalled_share"] == pytest.approx(0.4)


def test_stalled_share_is_zero_when_ends_were_recorded_but_none_stalled():
    # Distinct from the empty case above: here episodes ended and none of them stalled, which is a
    # share of zero and a real measurement.
    data = {
        REFERENCE: {10000: -4.0},
        "episode/end_wallcontact": {10000: 100.0},
    }

    rows = export_curves.to_rows(data, "run")

    assert rows[0]["stalled_share"] == 0.0


def test_laps_completed_is_not_duplicated_under_a_second_name():
    # The data model's LapsCompleted is the existing end_lapscompleted count. Two columns holding
    # one measurement is two things to keep in step.
    assert "end_lapscompleted" in export_curves.HEADER
    assert "laps_completed" not in export_curves.HEADER
