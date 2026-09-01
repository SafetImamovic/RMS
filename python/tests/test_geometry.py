"""Tests for the geometry checks and checkpoint placement.

Each check is tested in BOTH directions: a hand-built curve that must fail, and a generated
one that must pass. A check only ever asserted to pass is indistinguishable from a check that
always returns true, and these checks decide which seeds become tracks.
"""

from __future__ import annotations

import numpy as np
import pytest

from python.track import config, generator, geometry, vehicle

PROFILE = vehicle.build_profile()


def _line_from_xy(x: np.ndarray, y: np.ndarray, seed: int = 0) -> generator.CentreLine:
    """Wrap raw coordinates as a CentreLine so hand-built shapes can be checked.

    Arc length is integrated around the closure, matching what the generator does, so the
    separation test sees the same notion of distance along the curve.
    """
    dx = np.diff(np.concatenate([x, x[:1]]))
    dy = np.diff(np.concatenate([y, y[:1]]))
    seg = np.hypot(dx, dy)
    arc = np.concatenate([[0.0], np.cumsum(seg)[:-1]])

    return generator.CentreLine(
        seed=seed, theta=np.linspace(0, 2 * np.pi, len(x), endpoint=False),
        x=x, y=y, arc_length=arc,
        curvature=np.zeros_like(x), radius=np.full_like(x, 1e6),
        total_length_m=float(np.sum(seg)),
        params=generator.draw_parameters(seed))


# -----------------------------------------------------------------------------------------
# Radius floor, both directions
# -----------------------------------------------------------------------------------------


def test_a_corner_below_the_floor_is_rejected():
    """A circle tighter than r_floor must fail, and the report must say so with numbers."""
    t = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    tight = PROFILE.r_floor_m * 0.9
    line = _line_from_xy(tight * np.cos(t), tight * np.sin(t))
    line = generator.CentreLine(
        **{**line.__dict__, "radius": np.full(len(t), tight)})

    report = geometry.check_geometry(line, PROFILE)

    assert report.radius_ok is False
    assert report.ok is False
    assert "floor" in report.rejection_reason
    assert f"{tight:.2f}" in report.rejection_reason


def test_a_corner_just_above_the_floor_is_accepted():
    t = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    wide = PROFILE.r_floor_m * 1.001
    line = _line_from_xy(wide * np.cos(t), wide * np.sin(t))
    line = generator.CentreLine(**{**line.__dict__, "radius": np.full(len(t), wide)})

    assert geometry.check_geometry(line, PROFILE).radius_ok is True


def test_the_report_carries_the_floor_it_tested_against():
    """Auditable means the reader can recompute the verdict, not just read it."""
    report = geometry.check_geometry(generator.generate(1), PROFILE)

    assert report.r_floor_m == PROFILE.r_floor_m
    assert report.radius_ok == (report.min_radius_m >= report.r_floor_m)


# -----------------------------------------------------------------------------------------
# Self-intersection, both directions
# -----------------------------------------------------------------------------------------


def test_a_figure_of_eight_is_detected():
    """The classic failure: closed, smooth, and completely unusable as a track."""
    t = np.linspace(0, 2 * np.pi, 600, endpoint=False)
    x = 40 * np.sin(t)
    y = 40 * np.sin(t) * np.cos(t)

    report = geometry.check_geometry(_line_from_xy(x, y), PROFILE)

    assert report.self_intersects is True
    assert report.ok is False
    assert "crosses itself" in report.rejection_reason


def test_a_generated_loop_does_not_cross_itself():
    for seed in range(1, 12):
        report = geometry.check_geometry(generator.generate(seed), PROFILE)
        assert report.self_intersects is False, f"seed {seed} crosses itself"


def test_adjacent_segments_are_not_counted_as_a_crossing():
    """Neighbouring segments share a vertex by construction; that is not an intersection."""
    t = np.linspace(0, 2 * np.pi, 500, endpoint=False)
    circle = _line_from_xy(30 * np.cos(t), 30 * np.sin(t))

    assert geometry.check_geometry(circle, PROFILE).self_intersects is False


# -----------------------------------------------------------------------------------------
# Separation, both directions
# -----------------------------------------------------------------------------------------


def test_a_loop_that_passes_close_to_itself_fails_separation():
    """A pinched loop: never crossing, but the two sides run within a few metres.

    This is exactly the case closure and crossing checks both wave through, and the reason
    research C10 asks for a third check.
    """
    t = np.linspace(0, 2 * np.pi, 800, endpoint=False)
    # A peanut: radius collapses to a narrow waist twice per lap without ever crossing.
    r = 40.0 - 36.5 * np.abs(np.cos(t))
    line = _line_from_xy(r * np.cos(t), r * np.sin(t))

    report = geometry.check_geometry(line, PROFILE)

    assert report.min_separation_m < config.MIN_SEPARATION_M
    assert report.separation_ok is False


def test_a_generated_loop_keeps_its_distance_from_itself():
    for seed in range(1, 12):
        report = geometry.check_geometry(generator.generate(seed), PROFILE)
        assert report.separation_ok is True, (
            f"seed {seed} passes within {report.min_separation_m:.2f} m of itself")


def test_a_plain_circle_passes_separation():
    """Regression: a circle never approaches itself, so it must not fail this check.

    It did. With the arc window equal to the separation threshold, the closest qualifying pair
    on a circle of radius R is a chord of 2*R*sin(threshold / 2R), which is always shorter
    than the threshold. Every generated track failed at 11.73 to 11.76 m against a 12 m
    minimum while never coming near itself at all.
    """
    t = np.linspace(0, 2 * np.pi, 2000, endpoint=False)
    for radius in (PROFILE.r_floor_m, 16.0, 30.0):
        line = _line_from_xy(radius * np.cos(t), radius * np.sin(t))
        report = geometry.check_geometry(line, PROFILE)

        assert report.separation_ok is True, (
            f"a circle of radius {radius:.2f} m was reported as passing within "
            f"{report.min_separation_m:.2f} m of itself")


def test_the_arc_window_is_wider_than_the_separation_threshold():
    """The invariant that keeps the chord-versus-arc bug from coming back."""
    assert config.SEPARATION_ARC_WINDOW_M > config.MIN_SEPARATION_M


def test_separation_ignores_points_close_along_the_arc():
    """Otherwise every consecutive sample pair would fail it trivially."""
    line = generator.generate(3)
    report = geometry.check_geometry(line, PROFILE)

    step = line.total_length_m / config.SAMPLES_PER_TRACK

    # Consecutive samples are far closer than the minimum separation, yet the check passes,
    # which is only possible if they were excluded by the arc-length window.
    assert step < config.MIN_SEPARATION_M
    assert report.separation_ok is True


def test_separation_measures_the_shorter_way_round_the_loop():
    """The first and last samples are neighbours, not opposite ends.

    Measured naively as |s_i - s_j| they look a full lap apart and would be compared against
    each other despite being adjacent in space.
    """
    line = generator.generate(2)
    report = geometry.check_geometry(line, PROFILE)
    first_to_last = float(np.hypot(line.x[0] - line.x[-1], line.y[0] - line.y[-1]))

    assert first_to_last < config.MIN_SEPARATION_M
    assert report.min_separation_m > first_to_last


# -----------------------------------------------------------------------------------------
# Checkpoints
# -----------------------------------------------------------------------------------------


def test_checkpoints_are_monotonic_in_arc_length():
    points = geometry.place_checkpoints(generator.generate(5))

    s = [p.s for p in points]
    assert s == sorted(s)
    assert len(points) == config.N_CHECKPOINTS
    assert [p.index for p in points] == list(range(config.N_CHECKPOINTS))


def test_checkpoints_are_evenly_spaced_in_arc_length_not_in_theta():
    """The distinction this test exists for: even in distance, uneven in parameter.

    On a harmonic loop the radius varies by design, so a set of gates that is evenly spaced in
    theta is necessarily uneven in distance. Showing the spacing is uniform in arc length AND
    that the underlying curve is not uniform in theta is what separates the two.
    """
    line = generator.generate(5)
    points = geometry.place_checkpoints(line)

    gaps = np.diff([p.s for p in points])
    assert np.allclose(gaps, gaps[0], rtol=1e-9)

    # The curve genuinely varies in speed per unit theta, so this was not uniform by accident.
    per_theta = np.diff(line.arc_length)
    assert per_theta.max() / per_theta.min() > 1.2


def test_checkpoint_positions_lie_on_the_curve():
    line = generator.generate(6)
    points = geometry.place_checkpoints(line)

    for p in points:
        d = np.min(np.hypot(line.x - p.x, line.y - p.y))
        # Within a sample step, since positions are interpolated between samples.
        assert d < 2.0 * line.total_length_m / config.SAMPLES_PER_TRACK


def test_checkpoint_headings_are_unit_vectors_pointing_along_the_track():
    line = generator.generate(6)
    points = geometry.place_checkpoints(line)

    for p in points:
        assert np.hypot(p.heading_x, p.heading_y) == pytest.approx(1.0, abs=1e-9)

    # Consecutive headings turn gradually rather than jumping, which they would if the
    # heading were taken as a chord between checkpoints on a tight corner.
    for a, b in zip(points, points[1:]):
        dot = a.heading_x * b.heading_x + a.heading_y * b.heading_y
        assert dot > 0.0


def test_asking_for_no_checkpoints_is_refused():
    with pytest.raises(ValueError):
        geometry.place_checkpoints(generator.generate(1), n=0)


# -----------------------------------------------------------------------------------------
# Whole-report behaviour
# -----------------------------------------------------------------------------------------


def test_every_check_runs_even_after_one_fails():
    """A report that short-circuits would make the batch rejection statistics lie."""
    t = np.linspace(0, 2 * np.pi, 600, endpoint=False)
    x = 8 * np.sin(t)
    y = 8 * np.sin(t) * np.cos(t)
    line = _line_from_xy(x, y)
    line = generator.CentreLine(**{**line.__dict__, "radius": np.full(len(t), 1.0)})

    report = geometry.check_geometry(line, PROFILE)

    assert report.radius_ok is False
    assert report.self_intersects is True
    assert np.isfinite(report.min_separation_m)


def test_a_passing_report_has_no_rejection_reason():
    report = geometry.check_geometry(generator.generate(1), PROFILE)

    assert report.ok is True
    assert report.rejection_reason is None
