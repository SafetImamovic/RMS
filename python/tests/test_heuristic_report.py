"""The run-record reporter (feature 005, T029).

Every case here is built from a fixture CSV written to ``tmp_path``, in the shape
``specs/005-heuristic-ray-driver/contracts/run-record.md`` fixes. Nothing reads the real
``results/heuristic`` folder: a test that depends on measurements someone happened to take is a
test that passes for a reason unrelated to the code.

The centrepiece is the empty ``lap_time_s``. An aggregate that averages zeros for failed runs
reports a fast sweep, which is the same class of mistake as counting only the successes, arriving
through arithmetic instead of through omission. It has a test for the empty case and a test for
the literal zero, because a reader that fixed the first by treating every zero as missing would
break the second and look correct doing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from python.heuristic import report as rp

HEADER = ",".join(rp.REQUIRED_COLUMNS)


def row(
    seed: int = 1,
    controller: str = "WeightedAverage",
    ray_count: int = 13,
    ray_fov_deg: float = 180.0,
    ray_length_m: float = 20.0,
    completed_lap: bool = True,
    lap_time_s: str = "27.400",
    checkpoints_awarded: int = 24,
    checkpoints_total: int = 24,
    checkpoints_skipped: int = 0,
    wall_contacts: int = 0,
    end_reason: str = "LapComplete",
    steer_p95_dsteer: float = 0.0479,
    steer_sign_changes_per_s: float = 0.1461,
    time_scale: float = 1.0,
    duration_s: float = 27.400,
) -> str:
    """One row, with the lap time passed as text so a test can make it empty."""
    return (
        f"{seed},{controller},{ray_count},{ray_fov_deg:.2f},{ray_length_m:.2f},"
        f"{'true' if completed_lap else 'false'},{lap_time_s},"
        f"{checkpoints_awarded},{checkpoints_total},{checkpoints_skipped},{wall_contacts},"
        f"{end_reason},{steer_p95_dsteer:.4f},{steer_sign_changes_per_s:.4f},"
        f"{time_scale:.2f},{duration_s:.3f}"
    )


def write(tmp_path: Path, *rows: str, name: str = "runs_fixture.csv") -> Path:
    path = tmp_path / name
    path.write_text("\n".join((HEADER, *rows)) + "\n", encoding="utf-8")
    return path


def failed_row(**kwargs) -> str:
    """A run that ended without a lap. Its lap time is empty, not zero."""
    defaults = dict(
        completed_lap=False,
        lap_time_s="",
        checkpoints_awarded=5,
        wall_contacts=1,
        end_reason="WallContact",
        duration_s=5.200,
    )
    defaults.update(kwargs)
    return row(**defaults)


# --- the empty lap time, which is what this file exists for ----------------------------------


def test_a_failed_run_is_excluded_from_the_lap_time_mean(tmp_path):
    """The failure must not drag the mean down as a zero.

    Two clean laps at 27.4 and 27.2 average 27.3. Averaged with a zero for the failure they
    average 18.2, which is a plausible-looking number and completely wrong.
    """
    path = write(
        tmp_path,
        row(lap_time_s="27.400", duration_s=27.400),
        row(lap_time_s="27.200", duration_s=27.200),
        failed_row(),
    )

    summary = rp.summarise(rp.load_runs(path))[0]

    assert summary.runs == 3
    assert summary.lap_time.n == 2
    assert summary.lap_time.excluded == 1
    assert summary.lap_time.mean == pytest.approx(27.3)


def test_an_empty_lap_time_loads_as_none_and_not_as_zero(tmp_path):
    path = write(tmp_path, failed_row())

    run = rp.load_runs(path)[0]

    assert run.lap_time_s is None
    assert run.lap_time_s != 0.0


def test_a_lap_time_of_zero_is_a_value_and_is_kept(tmp_path):
    """The mirror of the rule above, and the reason it needs its own case.

    A reader that fixed the empty case by discarding every falsy lap time would pass the test
    above and silently drop a real measurement here. Zero is not reachable in practice, which is
    exactly why nothing would notice.
    """
    path = write(tmp_path, row(lap_time_s="0.000", duration_s=0.0))

    run = rp.load_runs(path)[0]
    summary = rp.summarise([run])[0]

    assert run.lap_time_s == 0.0
    assert summary.lap_time.n == 1
    assert summary.lap_time.excluded == 0


def test_a_group_with_no_completed_laps_reports_no_lap_time_rather_than_zero(tmp_path):
    path = write(tmp_path, failed_row(), failed_row(end_reason="NoProgress"))

    summary = rp.summarise(rp.load_runs(path))[0]

    assert summary.completed == 0
    assert summary.lap_time.n == 0
    assert summary.lap_time.mean is None
    assert summary.lap_time.excluded == 2


# --- the rest of the contract ----------------------------------------------------------------


def test_the_completion_rate_keeps_its_denominator(tmp_path):
    """SC-006 and FR-012: the count and the denominator, not only the percentage.

    A rate of 50 percent over two runs and over thirty-four are different claims.
    """
    path = write(tmp_path, row(), failed_row())

    summary = rp.summarise(rp.load_runs(path))[0]

    assert (summary.completed, summary.runs) == (1, 2)
    assert summary.completion_rate == pytest.approx(0.5)


def test_smoothness_covers_failed_runs_too(tmp_path):
    """How a controller steered on a run it failed is exactly as measurable as on one it won.

    Dropping the failures here would report the smoothness of the successes only, which flatters
    a controller that fails whenever it is about to steer badly.
    """
    path = write(
        tmp_path,
        row(steer_p95_dsteer=0.04),
        failed_row(steer_p95_dsteer=0.60),
    )

    summary = rp.summarise(rp.load_runs(path))[0]

    assert summary.p95.n == 2
    assert summary.p95.mean == pytest.approx(0.32)


def test_end_reasons_are_counted_including_no_progress(tmp_path):
    """``NoProgress`` is the sixth outcome T016 added and the contract now lists.

    A value the writer emits that the reporter cannot count is a hole found at runtime.
    """
    path = write(
        tmp_path,
        row(),
        failed_row(end_reason="NoProgress"),
        failed_row(end_reason="NoProgress"),
        failed_row(end_reason="TimeLimit"),
    )

    summary = rp.summarise(rp.load_runs(path))[0]

    assert summary.end_reasons == {"LapComplete": 1, "NoProgress": 2, "TimeLimit": 1}


def test_groups_are_per_controller_and_configuration_never_per_seed(tmp_path):
    """FR-012. The tracks differ in difficulty by construction, so one seed is a sample of one."""
    path = write(
        tmp_path,
        row(seed=1, controller="MostOpen"),
        row(seed=2, controller="MostOpen"),
        row(seed=1, controller="WeightedAverage"),
        row(seed=1, controller="WeightedAverage", ray_count=9),
    )

    summaries = rp.summarise(rp.load_runs(path))

    assert len(summaries) == 3
    most_open = next(s for s in summaries if s.controller == "MostOpen")
    assert most_open.runs == 2
    assert most_open.seeds == 2


def test_a_file_missing_a_contract_column_is_refused(tmp_path):
    """Refused rather than read for what it has.

    A reader that tolerated a missing column would report a result computed over a quantity that
    was never recorded, and nothing in the output would say so.
    """
    path = tmp_path / "broken.csv"
    path.write_text("seed,controller\n1,MostOpen\n", encoding="utf-8")

    with pytest.raises(rp.RunRecordError) as exc:
        rp.load_runs(path)

    assert "lap_time_s" in str(exc.value)


def test_one_value_has_no_standard_deviation_and_does_not_crash(tmp_path):
    """A controller that completed exactly one lap must still produce a report."""
    path = write(tmp_path, row())

    summary = rp.summarise(rp.load_runs(path))[0]

    assert summary.lap_time.n == 1
    assert summary.lap_time.sd is None
    assert summary.lap_time.spread == pytest.approx(0.0)


# --- the noise floor, and what may be said without it ------------------------------------------


def test_the_spread_is_unmeasured_when_nothing_was_repeated(tmp_path):
    """Returned as None rather than defaulted to zero.

    A zero noise floor makes every difference a finding, which is the most confident possible way
    to be wrong.
    """
    path = write(tmp_path, row(seed=1), row(seed=2))

    assert rp.measure_spread(rp.load_runs(path)) is None


def test_without_a_spread_no_difference_is_a_finding(tmp_path):
    """FR-015, in the words the requirement asks for."""
    path = write(
        tmp_path,
        row(seed=1, controller="MostOpen", steer_p95_dsteer=0.60),
        row(seed=2, controller="WeightedAverage", steer_p95_dsteer=0.04),
    )
    runs = rp.load_runs(path)

    differences = rp.compare(rp.summarise(runs), rp.measure_spread(runs))
    p95 = next(d for d in differences if d.measure == "steer_p95_dsteer")

    assert p95.exceeds is None
    assert "not a finding" in p95.sentence()
    assert "unmeasured" in p95.sentence()


def test_the_spread_uses_only_repeats_of_one_controller_seed_and_configuration(tmp_path):
    path = write(
        tmp_path,
        row(seed=1, lap_time_s="27.400", duration_s=27.400),
        row(seed=1, lap_time_s="27.240", duration_s=27.240),
        row(seed=1, lap_time_s="27.300", duration_s=27.300),
        row(seed=2, lap_time_s="31.000", duration_s=31.000),
    )

    spread = rp.measure_spread(rp.load_runs(path))

    assert spread is not None
    assert spread.repeats == 3
    assert spread.seed == 1
    assert spread.by_measure["lap_time_s"].spread == pytest.approx(0.16)


def test_a_failed_run_never_contributes_to_the_spread(tmp_path):
    """An interrupted run is not a slower lap, it is not a lap.

    An early estimate that mixed the two read 28.9 s where the comparable runs read 0.100 s. A
    noise floor inflated by a factor of 289 would have buried every difference this feature
    exists to find.
    """
    path = write(
        tmp_path,
        row(lap_time_s="27.400", duration_s=27.400),
        row(lap_time_s="27.240", duration_s=27.240),
        failed_row(),
    )

    spread = rp.measure_spread(rp.load_runs(path))

    assert spread is not None
    assert spread.repeats == 2


def test_a_difference_below_the_spread_is_stated_not_to_be_a_finding(tmp_path):
    """The sentence FR-015 requires, checked as text rather than as a boolean.

    Two controllers 0.002 apart on the percentile, against a spread of 0.006. The report has to
    say so in those words rather than print the number and let a reader assume it means
    something.
    """
    path = write(
        tmp_path,
        row(seed=1, controller="A", steer_p95_dsteer=0.0439, lap_time_s="27.24", duration_s=27.24),
        row(seed=1, controller="A", steer_p95_dsteer=0.0502, lap_time_s="27.40", duration_s=27.40),
        row(seed=1, controller="B", steer_p95_dsteer=0.0490, lap_time_s="27.30", duration_s=27.30),
    )
    runs = rp.load_runs(path)

    spread = rp.measure_spread(runs)
    differences = rp.compare(rp.summarise(runs), spread)
    p95 = next(d for d in differences if d.measure == "steer_p95_dsteer")

    assert spread.by_measure["steer_p95_dsteer"].spread == pytest.approx(0.0063)
    assert p95.gap == pytest.approx(0.0019, abs=1e-4)
    assert p95.exceeds is False
    assert "not a finding" in p95.sentence()


def test_a_difference_above_the_spread_is_stated_to_exceed_it(tmp_path):
    path = write(
        tmp_path,
        row(seed=1, controller="A", steer_p95_dsteer=0.0439, lap_time_s="27.24", duration_s=27.24),
        row(seed=1, controller="A", steer_p95_dsteer=0.0502, lap_time_s="27.40", duration_s=27.40),
        row(seed=1, controller="B", steer_p95_dsteer=0.6000, lap_time_s="27.30", duration_s=27.30),
    )
    runs = rp.load_runs(path)

    differences = rp.compare(rp.summarise(runs), rp.measure_spread(runs))
    p95 = next(d for d in differences if d.measure == "steer_p95_dsteer")

    assert p95.exceeds is True
    assert "exceeds the run-to-run spread" in p95.sentence()


def test_the_sign_change_threshold_is_floored_by_one_reversal(tmp_path):
    """T027's finding, encoded so it cannot be lost.

    Five repeats all recorded exactly four reversals, so the observed range of that column was
    0.0008 per second and described nothing but lap-time jitter dividing the same integer. The
    measure cannot move by less than one reversal, 0.0366 per second at these durations. Comparing
    against the observed range would call a quantisation step a finding.
    """
    path = write(
        tmp_path,
        row(seed=1, steer_sign_changes_per_s=0.1461, lap_time_s="27.38", duration_s=27.38),
        row(seed=1, steer_sign_changes_per_s=0.1469, lap_time_s="27.24", duration_s=27.24),
    )

    spread = rp.measure_spread(rp.load_runs(path))
    observed = spread.by_measure["steer_sign_changes_per_s"].spread

    assert observed == pytest.approx(0.0008, abs=1e-5)
    assert spread.sign_change_quantum == pytest.approx(1 / 27.31, abs=1e-3)
    assert spread.threshold("steer_sign_changes_per_s") == pytest.approx(
        spread.sign_change_quantum
    )
    assert spread.threshold("steer_sign_changes_per_s") > observed


def test_the_lap_time_threshold_is_the_observed_range(tmp_path):
    """Only the sign-change column has a quantum. The others use what was measured."""
    path = write(
        tmp_path,
        row(seed=1, lap_time_s="27.400", duration_s=27.400),
        row(seed=1, lap_time_s="27.240", duration_s=27.240),
    )

    spread = rp.measure_spread(rp.load_runs(path))

    assert spread.threshold("lap_time_s") == pytest.approx(0.16)


def test_pooling_several_files_keeps_every_run(tmp_path):
    """A sweep may span sessions, and a session is one file."""
    first = write(tmp_path, row(seed=1), name="runs_a.csv")
    second = write(tmp_path, row(seed=2), name="runs_b.csv")

    runs = rp.load_many([first, second])

    assert len(runs) == 2
    assert {r.seed for r in runs} == {1, 2}


def test_the_report_prints_without_a_spread_and_with_one(tmp_path, capsys):
    """The whole report runs end to end in both states.

    The spread block has to appear before the differences: FR-015 makes every judgement below it
    conditional on it, and a reader who has formed an opinion from a table of means will not
    revise it three paragraphs later.
    """
    path = write(
        tmp_path,
        row(seed=1, controller="A", lap_time_s="27.40", duration_s=27.40),
        row(seed=1, controller="A", lap_time_s="27.24", duration_s=27.24),
        row(seed=1, controller="B", lap_time_s="30.00", duration_s=30.00),
    )
    runs = rp.load_runs(path)

    rp.report(runs, rp.measure_spread(runs))
    out = capsys.readouterr().out

    assert out.index("RUN-TO-RUN SPREAD") < out.index("DIFFERENCES")
    assert "never collapsed into one verdict" in out


# ============================================================================================
# The steering distribution (US4, T041-T043)
# ============================================================================================

import numpy as np


TRACE_HEADER = "t,seed,controller,command_steer,applied_steer,outcome"


def write_trace(tmp_path: Path, steer, seed=1, controller="WeightedAverage",
                hz=50.0, name="trace_a.csv") -> Path:
    """A per-step trace in the shape HeuristicDriver writes."""
    lines = [TRACE_HEADER]
    for i, value in enumerate(steer):
        t = (i + 1) / hz
        lines.append(f"{t:.4f},{seed},{controller},{value:.4f},{value:.4f},Running")

    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_trace_without_the_controller_column_is_skipped(tmp_path):
    """Several hundred pre-existing traces have no seed or controller column.

    They are still the evidence for what happened inside the runs that produced them, but they
    cannot say whose runs those were. Pooling them into whichever distribution was built first
    would attribute one controller's steering to another.
    """
    path = tmp_path / "trace_old.csv"
    path.write_text("t,command_steer\n" + "".join(f"{i/50:.4f},0.1\n" for i in range(60)),
                    encoding="utf-8")

    assert rp.load_trace(path) is None


def test_a_trace_with_almost_no_rows_is_skipped(tmp_path):
    path = write_trace(tmp_path, [0.1] * 5)

    assert rp.load_trace(path) is None


def test_commands_are_resampled_to_the_compare_rate(tmp_path):
    """Not left at the physics rate.

    The whole point of the shared COMPARE_HZ grid is that this figure sits beside the human, BC
    and PPO columns. Left at 50 Hz it would report a rate difference as a driving difference,
    which is research C14 arriving through a different door.
    """
    df = rp.load_trace(write_trace(tmp_path, [0.5] * 250))   # 5 s at 50 Hz

    values = rp.resampled_commands(df)

    # 5 s at 14.08 Hz is about 71 points, against the 250 rows it was built from.
    assert 65 <= values.size <= 75
    assert np.allclose(values, 0.5)


def test_each_run_is_differenced_separately(tmp_path):
    """The seam between two runs is not a steering change any driver made.

    Feature 002 hit this exactly, differencing across the join between two recordings and
    inventing a jump. Here the seam is between two runs on different seeds, where the command
    resets to whatever the next run happens to start at.
    """
    a = rp.load_trace(write_trace(tmp_path, [1.0] * 200, seed=1, name="trace_a.csv"))
    b = rp.load_trace(write_trace(tmp_path, [-1.0] * 200, seed=2, name="trace_b.csv"))

    d = rp.steering_distribution([a, b], "WeightedAverage")

    assert d.abs_delta_steering.maximum == pytest.approx(0.0, abs=1e-9), (
        "differenced across the join this would report a 2.0 step, which is the largest "
        "steering change the command can express and nothing produced it"
    )
    assert d.seeds == 2
    assert d.runs == 2


def test_the_distribution_reports_every_statistic_principle_ix_asks_for(tmp_path):
    rng = np.random.default_rng(0)
    df = rp.load_trace(write_trace(tmp_path, rng.uniform(-1, 1, size=400)))

    d = rp.steering_distribution([df], "WeightedAverage")

    for summary in (d.steering, d.abs_delta_steering):
        assert summary.n > 0
        assert summary.mean is not None
        assert summary.variance > 0
        assert summary.minimum <= summary.maximum
        assert set(summary.percentiles) == {1, 5, 50, 95, 99}


def test_the_histogram_is_relative_frequency(tmp_path):
    """Relative frequency, so two controllers with different run counts are comparable."""
    rng = np.random.default_rng(1)
    df = rp.load_trace(write_trace(tmp_path, rng.uniform(-1, 1, size=400)))

    d = rp.steering_distribution([df], "WeightedAverage")

    assert d.hist_counts.sum() == pytest.approx(1.0)
    assert d.hist_edges.size == d.hist_counts.size + 1


def test_traces_are_grouped_by_the_controller_that_produced_them(tmp_path):
    write_trace(tmp_path, [0.6] * 200, controller="MostOpen", name="trace_1.csv")
    write_trace(tmp_path, [0.6] * 200, controller="MostOpen", seed=2, name="trace_2.csv")
    write_trace(tmp_path, [0.05] * 200, controller="WeightedAverage", name="trace_3.csv")

    ds = {d.controller: d for d in rp.distributions_from(tmp_path)}

    assert set(ds) == {"MostOpen", "WeightedAverage"}
    assert ds["MostOpen"].runs == 2
    assert ds["WeightedAverage"].runs == 1
    assert ds["MostOpen"].steering.mean == pytest.approx(0.6)


def test_no_usable_traces_says_so_rather_than_printing_an_empty_table(tmp_path, capsys):
    rp.report_distributions(rp.distributions_from(tmp_path))
    out = capsys.readouterr().out

    assert "No usable traces" in out


# ============================================================================================
# Against the learned driver (US4 scenario 2, T043)
# ============================================================================================

import json


def learned_entry(name, scope, values, n=100):
    """One `distributions.json` entry in feature 004's shape."""
    lo, hi = min(values), max(values)
    return {
        "name": name,
        "scope": scope,
        "n": n,
        "mean": sum(values) / len(values),
        "std": 0.1,
        "variance": 0.01,
        "minimum": lo,
        "maximum": hi,
        "lattice_applied": False,
        "percentiles": {"1": lo, "5": lo, "50": values[len(values) // 2], "95": hi, "99": hi},
        "histogram_edges": [lo, hi],
        "histogram_relative": [1.0],
    }


def write_learned(tmp_path: Path, deltas, steering=None, run_id="run_bc_fixture_v01") -> Path:
    """A learned column on disk, one scope, in the layout feature 004 writes."""
    steering = steering if steering is not None else [0.0, 0.1, 0.2]
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    path = run_dir / "distributions.json"
    path.write_text(json.dumps([
        learned_entry("abs_delta_predicted", "pooled", deltas),
        learned_entry("predicted_steering", "pooled", steering),
    ]), encoding="utf-8")
    return path


def test_a_missing_learned_column_says_so_rather_than_dropping_the_comparison(tmp_path, capsys):
    """The comparison being absent and the artifact being absent are different statements."""
    write_trace(tmp_path, [0.05] * 200)
    rp.report_against_learned(rp.distributions_from(tmp_path),
                              rp.load_learned(tmp_path / "nothing.json"), None)
    out = capsys.readouterr().out

    assert "No learned column" in out
    assert "is missing" in out


def test_the_learned_column_is_read_and_never_recomputed(tmp_path):
    """Every figure comes off disk. A second definition of the same statistic here is the
    drift feature 004 exists to avoid."""
    path = write_learned(tmp_path, deltas=[0.01, 0.02, 0.03])

    learned = rp.load_learned(path)

    assert len(learned) == 1
    assert learned[0].run_id == "bc_fixture_v01"
    assert learned[0].abs_delta_steering.mean == pytest.approx(0.02)
    assert learned[0].abs_delta_steering.percentiles[95] == pytest.approx(0.03)


def test_a_scope_the_file_does_not_carry_is_skipped_not_faked(tmp_path):
    path = write_learned(tmp_path, deltas=[0.01, 0.02, 0.03])

    assert [c.scope for c in rp.load_learned(path)] == ["pooled"]


def test_the_scripted_win_is_stated_plainly(tmp_path, capsys):
    """US4 scenario 2. A driver that is smoother than the learned one says so."""
    write_trace(tmp_path, [0.0, 0.001] * 200)
    learned = rp.load_learned(write_learned(tmp_path, deltas=[0.5, 0.6, 0.7]))

    rp.report_against_learned(rp.distributions_from(tmp_path), learned, None)
    out = capsys.readouterr().out

    assert "Smoother than the learned driver at mean, p50, p95" in out


def test_the_scripted_loss_is_stated_in_the_same_breath(tmp_path, capsys):
    write_trace(tmp_path, [i * 0.002 for i in range(400)])
    learned = rp.load_learned(write_learned(tmp_path, deltas=[0.001, 0.002, 0.003]))

    rp.report_against_learned(rp.distributions_from(tmp_path), learned, None)
    out = capsys.readouterr().out

    assert "Rougher at mean, p50, p95, p99, max" in out


def test_only_the_steering_change_crosses_between_the_two_drivers(tmp_path):
    """The steering command itself is measured on two different roads, so no claim is made
    in it. Only `|delta steering|` is defined identically on both sides."""
    write_trace(tmp_path, [0.05] * 200)
    learned = rp.load_learned(write_learned(tmp_path, deltas=[0.01, 0.02, 0.03]))
    scripted = rp.distributions_from(tmp_path)[0]

    claims = rp.compare_to_learned(scripted, learned[0])

    assert [c.measure for c in claims] == ["mean", "p50", "p95", "p99", "max"]
    assert all(c.learned == pytest.approx(v)
               for c, v in zip(claims, [0.02, 0.02, 0.03, 0.03, 0.03]))


def test_the_three_reasons_this_is_not_a_head_to_head_are_always_printed(tmp_path, capsys):
    """The learned driver never drives (feature 004 FR-018), the roads differ, and the two
    clocks agree on only one of the two recordings. Omitting any of them turns a distribution
    comparison into a claim about driving."""
    write_trace(tmp_path, [0.05] * 200)
    learned = rp.load_learned(write_learned(tmp_path, deltas=[0.01, 0.02, 0.03]))

    rp.report_against_learned(rp.distributions_from(tmp_path), learned, None)
    out = capsys.readouterr().out

    assert "never drives" in out
    assert "Different roads" in out
    assert "same clock" in out
    assert "no learned column at all" in out


def test_without_a_spread_the_gap_is_not_yet_a_finding(tmp_path, capsys):
    write_trace(tmp_path, [0.05] * 200)
    learned = rp.load_learned(write_learned(tmp_path, deltas=[0.01, 0.02, 0.03]))

    rp.report_against_learned(rp.distributions_from(tmp_path), learned, None)

    assert "run-to-run spread is unmeasured here" in capsys.readouterr().out


def test_the_gap_is_judged_against_the_scripted_side_only(tmp_path, capsys):
    """The learned side has no run-to-run spread on this measure. Feature 004's 0.0005
    tolerance is the best-epoch validation error and nothing else, and borrowing it here
    would judge a distribution against an accuracy figure."""
    write_trace(tmp_path, [0.05] * 200)
    learned = rp.load_learned(write_learned(tmp_path, deltas=[0.01, 0.02, 0.03]))
    spread = rp.measure_spread(rp.load_runs(write(
        tmp_path,
        row(seed=1, lap_time_s="27.400", steer_p95_dsteer=0.0500),
        row(seed=1, lap_time_s="27.240", steer_p95_dsteer=0.0439),
        name="runs_repeat.csv",
    )))

    rp.report_against_learned(rp.distributions_from(tmp_path), learned, spread)
    out = capsys.readouterr().out

    assert "run-to-run spread of 0.0061" in out
    assert "The learned side has no such number" in out
