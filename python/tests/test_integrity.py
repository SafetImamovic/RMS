"""Tests for the provenance / integrity checks (feature 002, US1 + US2).

Every check family is tested in BOTH directions:

  * it must fire on a deliberately tampered input, and
  * it must stay silent on a clean one.

The second half is not optional. A check that flags a sound dataset as tampered is as
serious a defect as one that misses tampering — and given the combined file splices two
recordings whose clocks run backwards at the junction, it is the failure this feature is
most exposed to (research A1, A10).
"""

from __future__ import annotations

import numpy as np
import pytest

from python.eda import config
from python.eda.integrity import (
    check_duplicates,
    check_plausibility,
    check_timeline,
    implied_acceleration,
    profile_granularity,
    split_sessions,
)

from conftest import (  # pytest puts the test directory on sys.path
    COPIED_COUNT,
    EXCISED_COUNT,
    OFF_LATTICE_NUDGE,
    OFF_LATTICE_ROW,
    SPEED_JUMP_ROW,
)


# =======================================================================================
# T005 — timeline continuity
# =======================================================================================
def test_clean_session_reports_no_violations_and_no_gaps(clean_session):
    """A clean result is still a result: reported explicitly, never omitted."""
    reports = check_timeline(clean_session)
    assert len(reports) == 1
    rep = reports[0]

    assert rep.is_monotonic is True
    assert rep.n_order_violations == 0
    assert rep.n_gaps == 0
    assert rep.n_unparseable == 0
    # Ordinary cadence jitter must not read as a gap at any reporting tier.
    assert rep.gap_tiers[">2x"] == 0
    assert rep.gap_tiers[">1s"] == 0
    # ~14 fps, derived from the data rather than assumed.
    assert 12.0 < rep.implied_fps < 16.0


def test_shuffled_rows_break_monotonicity(shuffled_session):
    """Signature of reordered rows: time stops running forwards."""
    rep = check_timeline(shuffled_session)[0]

    assert rep.is_monotonic is False
    assert rep.n_order_violations > 0
    assert rep.order_violation_examples  # something to go and look at


def test_excised_block_shows_up_as_a_gap(excised_session):
    """Signature of 'I cut out the ugly part': one large hole, order still intact."""
    rep = check_timeline(excised_session)[0]

    # Cutting a block does not disturb the order of what remains — only the gap check
    # can see this, which is why monotonicity alone is not enough.
    assert rep.is_monotonic is True
    assert rep.n_gaps >= 1
    assert rep.largest_gap_s > rep.gap_threshold_s
    assert rep.gap_tiers[">1s"] >= 1
    # ~50 missing frames at ~0.07 s each.
    assert rep.largest_gap_s == pytest.approx(EXCISED_COUNT * 0.070, rel=0.25)


def test_junction_of_two_sessions_raises_no_alarm(two_session_junction):
    """THE false-alarm trap: the second recording predates the first.

    Measured per session, both are clean. Measured across the junction, a naive check
    reports a ~-80 minute jump and 'discovers tampering' in a sound dataset.
    """
    sessions = split_sessions(two_session_junction)
    assert [s.session_id for s in sessions] == ["track1data", "track2data"]
    # Row order and time order disagree — nothing may assume otherwise.
    assert sessions[0].start_index < sessions[1].start_index
    assert sessions[0].start_time > sessions[1].start_time

    reports = check_timeline(two_session_junction)
    assert len(reports) == 2
    for rep in reports:
        assert rep.is_monotonic is True
        assert rep.n_order_violations == 0
        assert rep.n_gaps == 0


# =======================================================================================
# T006 — duplication
# =======================================================================================
def test_copied_block_reports_duplicate_rows_and_images(copied_block_session):
    """Signature of inflating the row count: identical rows AND reused frames."""
    rep = check_duplicates(copied_block_session)

    assert rep.n_exact_duplicate_rows == COPIED_COUNT
    assert rep.n_duplicate_image_refs == COPIED_COUNT
    assert rep.duplicate_row_examples


def test_repeated_measurement_tuples_do_not_inflate_the_other_counts(
    repeated_tuples_session,
):
    """Expected and benign — and it must not be mistaken for row copying.

    With 41 steering levels the value space is small, so identical measurement tuples on
    genuinely different frames are normal. Summing the three counts into one 'duplicates'
    figure would manufacture a false alarm (research A8).
    """
    rep = check_duplicates(repeated_tuples_session)

    assert rep.n_duplicate_measurement_tuples == 3
    assert rep.n_exact_duplicate_rows == 0
    assert rep.n_duplicate_image_refs == 0


def test_clean_session_has_no_duplicates_of_any_class(clean_session):
    rep = check_duplicates(clean_session)

    assert rep.n_exact_duplicate_rows == 0
    assert rep.n_duplicate_image_refs == 0
    assert rep.n_duplicate_measurement_tuples == 0


# =======================================================================================
# T007 — physical plausibility
# =======================================================================================
def test_injected_speed_jump_is_flagged(speed_jump_session):
    rep = check_plausibility(speed_jump_session)[0]

    assert rep.n_outliers >= 1
    # The frame before the jump and the jump itself both sit on an impossible step.
    assert {SPEED_JUMP_ROW - 1, SPEED_JUMP_ROW} & set(rep.outlier_indices)
    assert rep.units_note  # the criterion is relative; that must be stated


def test_mad_rule_catches_what_a_std_rule_at_the_same_multiplier_misses(
    speed_jump_session,
):
    """Why MAD and not standard deviation (research A7).

    A large injected jump inflates sigma enough that a `k * sigma` band swallows the very
    outlier it was meant to find. The median absolute deviation is not moved by it.
    """
    accel = implied_acceleration(speed_jump_session)["track1data"]
    k = config.ACCEL_MAD_K

    mad = float(np.median(np.abs(accel - np.median(accel))))
    n_mad_flags = int(np.sum(np.abs(accel - np.median(accel)) > k * mad))
    n_std_flags = int(np.sum(np.abs(accel - np.mean(accel)) > k * np.std(accel, ddof=1)))

    assert n_mad_flags >= 1
    assert n_std_flags == 0, (
        "the standard-deviation rule was expected to be blinded by its own outlier; "
        "if this fires, the fixture no longer demonstrates why MAD is used"
    )


def test_ordinary_acceleration_is_not_flagged(clean_session):
    rep = check_plausibility(clean_session)[0]

    assert rep.n_outliers == 0
    assert rep.mad_accel > 0  # a degenerate spread would make the screen meaningless


def test_plausibility_never_crosses_a_session_boundary(two_session_junction):
    reports = check_plausibility(two_session_junction)

    assert len(reports) == 2
    for rep in reports:
        assert rep.n_outliers == 0


# =======================================================================================
# T012 — measurement granularity
# =======================================================================================
def _profile(ds, column: str):
    return next(p for p in profile_granularity(ds) if p.column == column)


def test_steering_is_recognised_as_a_lattice(clean_session):
    prof = _profile(clean_session, "steering")

    assert prof.classification == "discrete"
    assert prof.is_lattice is True
    assert prof.spacing == pytest.approx(0.05, abs=1e-9)
    assert prof.off_lattice_values == []
    assert prof.tolerance == config.LATTICE_ATOL  # the tolerance used is reported
    assert prof.support is not None
    # The support spans min..max on the lattice, so a level that simply never came up is
    # listed as unobserved rather than silently shrinking the support.
    assert set(prof.unobserved_support).isdisjoint(set(clean_session.df["steering"]))


def test_continuous_columns_are_not_forced_onto_a_lattice(clean_session):
    for column in ("throttle", "speed"):
        prof = _profile(clean_session, column)
        assert prof.classification == "continuous"
        assert prof.n_distinct > config.DISCRETE_MAX_DISTINCT


def test_off_lattice_value_is_reported(off_lattice_session):
    """The strongest single piece of evidence these checks can produce.

    A value off an otherwise perfect lattice means someone computed a new number —
    smoothing, interpolation, augmentation — and wrote it back.
    """
    prof = _profile(off_lattice_session, "steering")
    tampered = float(off_lattice_session.df.loc[OFF_LATTICE_ROW, "steering"])

    assert prof.off_lattice_values
    assert any(v == pytest.approx(tampered) for v in prof.off_lattice_values)
    assert OFF_LATTICE_NUDGE not in (0.0,)  # guard: the fixture must actually nudge


def test_float_representation_error_is_not_reported_as_off_lattice(float_error_session):
    """0.05 is not exactly representable; demanding exact equality would flag everything."""
    prof = _profile(float_error_session, "steering")

    assert prof.is_lattice is True
    assert prof.off_lattice_values == []
    assert prof.spacing == pytest.approx(0.05, abs=1e-9)


def test_single_valued_column_is_classified_constant(constant_column_session):
    """brake never leaves 0.0 — reported as a finding, not fed to statistics (FR-013)."""
    prof = _profile(constant_column_session, "brake")

    assert prof.classification == "constant"
    assert prof.n_distinct == 1
    assert prof.spacing is None
    assert prof.evidence  # a constant column must say so in plain language
