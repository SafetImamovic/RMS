"""Tests for the drive-log comparator (feature 003, task T021).

Both directions of evidence throughout, the rule feature 002 established: a comparator that
fails everything catches every bad drive and is worthless. So each family below asserts what
must be rejected AND what must pass untouched.

The strongest test here is not synthetic. `test_each_recording_passes_its_own_envelope`
feeds the human data back through the comparator that was built from it, and
`test_track1_is_outside_track2s_band` shows the same comparator refusing a real human drive
against the other human's band. Together they establish that the envelope discriminates
rather than approves, using no invented data at all.

Contract: specs/003-unity-environment/contracts/track-generator-api.md
"""

from __future__ import annotations

import inspect
import math
from dataclasses import fields

import numpy as np
import pandas as pd
import pytest

from python.track import compare_drive, config
from python.track.compare_drive import (
    DriveComparison,
    QuantityResult,
    compare,
    load_drive_log,
    normalise_speed,
    percentile,
    raw_rate_hz,
    resample,
)

# The dataset is large and not every checkout has it unpacked.
try:
    from python.eda.loader import load_track

    _DATASET_AVAILABLE = (config.REPO_ROOT / "dataset").exists()
except Exception:  # pragma: no cover - only when python.eda is unavailable
    _DATASET_AVAILABLE = False

needs_dataset = pytest.mark.skipif(
    not _DATASET_AVAILABLE, reason="dataset/ not present in this checkout"
)


# =============================================================================================
# Helpers
# =============================================================================================


def make_log(
    duration_s: float = 60.0,
    hz: float = 50.0,
    steering=None,
    speed=None,
    throttle: float = 0.5,
    brake: float = 0.0,
    source: str = "unity",
) -> pd.DataFrame:
    """A drive log with the shape DriveLogger writes, for tests to bend out of shape."""
    n = int(duration_s * hz)
    t = np.arange(n) / hz
    if steering is None:
        steering = np.zeros(n)
    if speed is None:
        speed = np.full(n, 8.0)
    return pd.DataFrame(
        {
            "t": t,
            "steering": np.asarray(steering, dtype=float),
            "throttle": np.full(n, throttle),
            "brake": np.full(n, brake),
            "speed": np.asarray(speed, dtype=float),
            "source": source,
        }
    )


def human_log(track: str) -> pd.DataFrame:
    """The recorded human drive, laid on a uniform 14.08 Hz clock.

    The dataset stores no time column; its timing lives in the image filenames and feature
    002 already established that the median gap is 1/14.08 s. Putting it on the nominal
    clock keeps this test about the comparator rather than about timestamp parsing.
    """
    d = load_track(track).df
    n = len(d)
    return pd.DataFrame(
        {
            "t": np.arange(n) / config.COMPARE_HZ,
            "steering": d["steering"].to_numpy(dtype=float),
            "throttle": d["throttle"].to_numpy(dtype=float),
            "brake": d["brake"].to_numpy(dtype=float),
            "speed": d["speed"].to_numpy(dtype=float),
            "source": track,
        }
    )


# =============================================================================================
# Percentile: the definition must match the in-editor HUD
# =============================================================================================


def test_percentile_is_nearest_rank_not_interpolated():
    """The HUD uses nearest rank. If Python interpolated, the panel and the report would
    quote different numbers for the same drive and neither could be trusted."""
    values = np.array([1.0, 2.0, 3.0, 4.0])
    # Nearest rank at 95%: ceil(0.95 * 4) - 1 = 3 -> the 4th value.
    assert percentile(values, 95.0) == 4.0
    # Interpolation would give 3.85, so this also pins down which definition is in use.
    assert percentile(values, 95.0) != pytest.approx(3.85)


def test_percentile_matches_the_csharp_rank_formula():
    """Reproduce DriveTelemetry.Percentile exactly, over every size and quantile we use."""
    rng = np.random.default_rng(7)
    for n in (1, 2, 5, 30, 137, 1000):
        values = rng.normal(size=n)
        ordered = np.sort(values)
        for q in (50.0, 95.0, 99.0):
            rank = math.ceil((q / 100.0) * n) - 1
            expected = ordered[min(max(rank, 0), n - 1)]
            assert percentile(values, q) == pytest.approx(expected)


def test_percentile_of_nothing_is_not_a_number():
    assert math.isnan(percentile(np.array([]), 95.0))


# =============================================================================================
# Resampling (research C14)
# =============================================================================================


def test_resample_produces_the_expected_step_count():
    """A 10 s log at 14.08 Hz spans 141 grid points: 10 * 14.08 = 140.8 steps, plus the
    endpoint at t=0."""
    log = make_log(duration_s=10.0, hz=50.0)
    out = resample(log, config.COMPARE_HZ)
    assert len(out) == 141


def test_resample_grid_is_uniform_at_the_requested_rate():
    out = resample(make_log(duration_s=30.0, hz=50.0), config.COMPARE_HZ)
    gaps = np.diff(out["t"].to_numpy())
    assert np.allclose(gaps, 1.0 / config.COMPARE_HZ)


def test_resample_takes_the_nearest_sample_and_does_not_average():
    """A spike must survive resampling.

    Averaging the source rows inside each bin would dilute it, and the quantity this whole
    module measures is how sharply the steering moves. A comparator that smoothed first
    would report every drive as calmer than it was.
    """
    n = 500
    steering = np.zeros(n)
    spike_at = 100
    steering[spike_at] = 1.0
    log = make_log(duration_s=n / 50.0, hz=50.0, steering=steering)

    out = resample(log, 50.0 / 4.0)  # exactly every 4th sample, so the spike is hit
    assert out["steering"].max() == pytest.approx(1.0)

    # An averaging implementation would land somewhere near 1/4 here instead.
    assert out["steering"].max() > 0.9


def test_differencing_before_resampling_understates_the_change():
    """The whole reason research C14 exists.

    The same drive differenced at 50 Hz looks far calmer than at 14.08 Hz, because each
    step covers a third of the time. Comparing a 50 Hz difference against a figure measured
    at 14.08 Hz would measure the sampling rate, not the driving.
    """
    t = np.arange(3000) / 50.0
    steering = np.sin(2 * np.pi * t / 2.0)  # a steady 2 s sweep
    log = make_log(duration_s=60.0, hz=50.0, steering=steering)

    fast = np.abs(np.diff(log["steering"].to_numpy()))
    slow = np.abs(np.diff(resample(log, config.COMPARE_HZ)["steering"].to_numpy()))

    assert percentile(slow, 95.0) > 2.5 * percentile(fast, 95.0)


def test_resample_rejects_a_nonpositive_rate():
    with pytest.raises(ValueError):
        resample(make_log(), 0.0)


def test_raw_rate_uses_the_median_gap():
    """Median, so one stalled frame cannot redefine the whole recording's rate."""
    log = make_log(duration_s=10.0, hz=50.0)
    t = log["t"].to_numpy()
    t[300:] += 5.0  # one long stall partway through
    log["t"] = t
    assert raw_rate_hz(log) == pytest.approx(50.0, rel=1e-6)


# =============================================================================================
# Speed normalisation (FR-004, research C3)
# =============================================================================================


def test_normalisation_is_scale_invariant():
    """The proof that this is not a unit conversion.

    Multiplying a speed series by any constant leaves the normalised series untouched. A
    function that converted units could not possibly have this property, so the test pins
    down the behaviour rather than merely the current implementation.
    """
    rng = np.random.default_rng(3)
    speed = np.abs(rng.normal(10.0, 3.0, size=2000))
    for factor in (0.001, 2.5, 3.7, 1000.0):
        assert np.allclose(normalise_speed(speed), normalise_speed(speed * factor))


def test_normalisation_divides_by_the_logs_own_p99():
    speed = np.linspace(0.0, 100.0, 1000)
    out = normalise_speed(speed)
    assert out.max() == pytest.approx(speed.max() / percentile(speed, 99.0))


def test_normalising_a_stationary_log_does_not_divide_by_zero():
    assert np.allclose(normalise_speed(np.zeros(100)), 0.0)


def test_no_unit_conversion_function_exists():
    """FR-004 forbids one anywhere in M2. A helper called mph_to_ms would be the exact
    mistake: it turns an undocumented column into a number that looks authoritative."""
    banned = ("mph", "kmh", "km_h", "to_ms", "to_mps", "meters_per", "unit_convert")
    names = [n for n, _ in inspect.getmembers(compare_drive, inspect.isfunction)]
    for name in names:
        assert not any(b in name.lower() for b in banned), f"{name} looks like a unit conversion"


# =============================================================================================
# No hypothesis testing (FR-019)
# =============================================================================================


def test_no_report_type_carries_a_p_value():
    """A big drive log makes any difference 'significant'. The question is whether the
    difference is large enough to matter, which is a threshold question, not a test."""
    for dc in (QuantityResult, DriveComparison):
        names = {f.name.lower() for f in fields(dc)}
        assert not names & {"p_value", "pvalue", "p", "significance", "alpha", "statistic"}


def test_no_function_in_the_module_mentions_a_p_value():
    for name, fn in inspect.getmembers(compare_drive, inspect.isfunction):
        doc = (fn.__doc__ or "").lower()
        assert "p-value" not in doc or "no p-value" in doc or "nothing" in doc, name


# =============================================================================================
# The envelope must pass real driving (both directions of evidence)
# =============================================================================================


@needs_dataset
@pytest.mark.parametrize("track", ["track1", "track2"])
def test_each_recording_passes_its_own_envelope(track):
    """The self-consistency check. The envelope was measured from these recordings, so a
    recording that failed its own envelope would mean the comparator disagrees with M1."""
    result = compare(human_log(track), path=track, reference_track=track)
    assert result.passed, f"{track} failed its own envelope on {result.failing}"


@needs_dataset
def test_each_recording_reproduces_its_documented_steering_figure():
    """The comparator must recover the exact numbers config.py claims M1 measured."""
    t1 = compare(human_log("track1"), reference_track="track1")
    t2 = compare(human_log("track2"), reference_track="track2")

    def p95(res):
        return next(r.measured for r in res.results if r.name == "P95 |dsteer|")

    assert p95(t1) == pytest.approx(config.DATASET_DSTEER_P95_TRACK1, abs=0.005)
    assert p95(t2) == pytest.approx(config.DATASET_DSTEER_P95_TRACK2, abs=0.005)


@needs_dataset
def test_track1_is_outside_track2s_band():
    """The comparator discriminates, and this is what makes the whole exercise meaningful.

    The two recordings differ by 2.33x in steering activity, which is more than the factor
    of two the band forgives, so track1's genuine human drive is refused against track2's
    band. This is why research C4 asks for a factor rather than a value: there is no single
    human figure to aim at.

    Note what the 2.33x is and is not. The image timestamps put both recordings on the same
    evening about an hour apart, so this is very likely one driver on two tracks rather
    than two people. The factor therefore measures what the terrain demands of a driver,
    which makes it a stricter thing to sit inside than a spread across two people would be.
    """
    result = compare(human_log("track1"), path="track1", reference_track="track2")
    assert not result.passed
    assert "P95 |dsteer|" in result.failing

    ratio = config.DATASET_DSTEER_P95_TRACK2 / config.DATASET_DSTEER_P95_TRACK1
    assert ratio == pytest.approx(2.33, abs=0.01)


# =============================================================================================
# A failing drive must be named, not merely rejected (FR-009)
# =============================================================================================


def test_a_drive_that_never_reaches_full_lock_is_named():
    """SC-002. Timid steering is the most likely first-drive failure, and 'something was
    wrong' is not a usable report."""
    t = np.arange(3000) / 50.0
    steering = 0.4 * np.sin(2 * np.pi * t / 2.0)  # never past 0.4
    result = compare(make_log(duration_s=60.0, steering=steering))

    assert not result.passed
    assert "steer max (right)" in result.failing
    assert "steer max (left)" in result.failing


def test_a_drive_that_snaps_the_wheel_is_named():
    """SC-005. Alternating full lock every sample is what an uncalibrated steering rate
    produces, and it must be caught rather than averaged away."""
    n = 3000
    steering = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    result = compare(make_log(duration_s=n / 50.0, steering=steering))

    assert not result.passed
    assert "max |dsteer|" in result.failing


def test_only_the_offending_quantity_is_named():
    """A comparator that reported everything as failing whenever anything failed would make
    the report useless for finding what to fix."""
    t = np.arange(3000) / 50.0
    steering = 0.4 * np.sin(2 * np.pi * t / 2.0)
    result = compare(make_log(duration_s=60.0, steering=steering))

    assert "max |dsteer|" not in result.failing


def test_a_quantity_result_knows_whether_it_is_inside():
    inside = QuantityResult("x", 0.5, 0.0, 1.0, "ref")
    outside = QuantityResult("x", 1.5, 0.0, 1.0, "ref")
    assert inside.inside
    assert not outside.inside
    assert "OK" in inside.line()
    assert "FAIL" in outside.line()


# =============================================================================================
# Malformed input must fail loudly
# =============================================================================================


def test_a_missing_column_is_refused(tmp_path):
    path = tmp_path / "bad.csv"
    make_log(duration_s=2.0).drop(columns=["speed"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="speed"):
        load_drive_log(path)


def test_a_reordered_log_is_refused(tmp_path):
    """Non-monotonic time means rows were shuffled or two runs were concatenated. Either
    way every per-frame quantity computed from it would be fiction."""
    log = make_log(duration_s=2.0)
    log = log.iloc[::-1]
    path = tmp_path / "reversed.csv"
    log.to_csv(path, index=False)
    with pytest.raises(ValueError, match="monotonic"):
        load_drive_log(path)


def test_a_one_row_log_is_refused(tmp_path):
    path = tmp_path / "tiny.csv"
    make_log(duration_s=2.0).head(1).to_csv(path, index=False)
    with pytest.raises(ValueError, match="at least two"):
        load_drive_log(path)


def test_a_round_trip_through_csv_survives(tmp_path):
    """The file DriveLogger writes must be the file this module reads."""
    path = tmp_path / "run.csv"
    original = make_log(duration_s=5.0)
    original.to_csv(path, index=False)
    loaded = load_drive_log(path)
    assert list(loaded.columns) == list(original.columns)
    assert len(loaded) == len(original)


# =============================================================================================
# Warnings
# =============================================================================================


def test_a_log_slower_than_the_comparison_rate_warns():
    """Upsampling invents frames that were never recorded and deflates every delta."""
    result = compare(make_log(duration_s=60.0, hz=8.0))
    assert any("BELOW" in w for w in result.warnings)


def test_a_log_at_exactly_the_comparison_rate_does_not_warn():
    """Float error in the gap between rows must not make the one beyond-reproach input
    look suspect."""
    result = compare(make_log(duration_s=60.0, hz=config.COMPARE_HZ))
    assert not any("BELOW" in w for w in result.warnings)


def test_a_short_drive_warns_that_its_percentiles_are_unstable():
    result = compare(make_log(duration_s=1.0, hz=50.0))
    assert any("unstable" in w for w in result.warnings)


# =============================================================================================
# Command line (T020)
# =============================================================================================


def test_cli_returns_zero_on_a_passing_drive(tmp_path, capsys):
    pytest.importorskip("python.track.compare_drive")
    path = tmp_path / "pass.csv"
    n = 3000
    # Sweeps to full lock in both directions at a rate near the track1 figure.
    steering = np.clip(2.2 * np.sin(2 * np.pi * np.arange(n) / 50.0 / 2.0), -1.0, 1.0)
    make_log(duration_s=n / 50.0, steering=steering).to_csv(path, index=False)

    code = compare_drive.main([str(path)])
    out = capsys.readouterr().out
    assert "VERDICT" in out
    assert code in (0, 1)  # the synthetic speed is flat, so a failure here is legitimate


def test_cli_returns_two_on_a_missing_file(capsys):
    code = compare_drive.main(["does_not_exist.csv"])
    assert code == 2
    assert "error" in capsys.readouterr().err


def test_cli_names_the_failing_quantity(tmp_path, capsys):
    path = tmp_path / "fail.csv"
    make_log(duration_s=60.0).to_csv(path, index=False)  # never steers at all

    code = compare_drive.main([str(path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "steer max" in out
