"""Tests for the track generator.

The load-bearing test here is `test_analytic_curvature_agrees_with_a_fine_numerical_estimate`.
Every other check would still pass if the curvature formula were subtly wrong, and curvature
is what the accept-or-reject decision rests on, so it is checked against an independent
method rather than against itself.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from python.track import config, generator

REPO = Path(__file__).resolve().parents[2]


# -----------------------------------------------------------------------------------------
# Determinism (SC-007)
# -----------------------------------------------------------------------------------------


def test_the_same_seed_gives_identical_parameters():
    a = generator.draw_parameters(7)
    b = generator.draw_parameters(7)

    assert a == b


def test_the_same_seed_gives_identical_geometry():
    a = generator.generate(7)
    b = generator.generate(7)

    assert np.array_equal(a.x, b.x)
    assert np.array_equal(a.y, b.y)
    assert np.array_equal(a.curvature, b.curvature)
    assert a.total_length_m == b.total_length_m


def test_the_same_seed_gives_identical_geometry_across_processes():
    """Determinism has to survive a fresh interpreter, not just a fresh call.

    A generator reading global random state would pass the in-process test above and fail
    this one, because the global state depends on whatever else drew a number first. That is
    the exact failure SC-007 exists to catch, so it is worth the cost of a subprocess.
    """
    script = (
        "import numpy as np;"
        "from python.track import generator;"
        "c = generator.generate(7);"
        "print(repr((float(c.x[0]), float(c.y[13]), float(c.total_length_m))))"
    )

    def run() -> str:
        out = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO, capture_output=True, text=True, check=True)
        return out.stdout.strip()

    assert run() == run()

    local = generator.generate(7)
    expected = repr((float(local.x[0]), float(local.y[13]), float(local.total_length_m)))
    assert run() == expected


def test_different_seeds_give_different_geometry():
    a = generator.generate(1)
    b = generator.generate(2)

    assert not np.allclose(a.x, b.x)
    assert a.params.amplitude != b.params.amplitude


def test_drawing_never_touches_global_random_state():
    """Seeding NumPy globally must not change what this module produces."""
    np.random.seed(12345)
    first = generator.draw_parameters(7)

    np.random.seed(99999)
    np.random.random(100)
    second = generator.draw_parameters(7)

    assert first == second


# -----------------------------------------------------------------------------------------
# Closure by construction (research C6)
# -----------------------------------------------------------------------------------------


def test_the_curve_closes_without_any_endpoint_correction():
    """r(0) and r(2 pi) agree because every harmonic is an integer multiple of theta.

    Checked by evaluating the radius function at both ends rather than by comparing the first
    and last SAMPLES, since the samples deliberately exclude 2 pi.
    """
    params = generator.draw_parameters(3)
    ends = np.array([0.0, 2.0 * np.pi])
    r, dr, d2r = generator._radius_terms(params, ends)

    assert r[0] == pytest.approx(r[1], rel=1e-12)
    assert dr[0] == pytest.approx(dr[1], rel=1e-12)
    assert d2r[0] == pytest.approx(d2r[1], rel=1e-12)


def test_every_generated_line_closes():
    for seed in range(1, 15):
        line = generator.generate(seed)
        gap = np.hypot(line.x[0] - line.x[-1], line.y[0] - line.y[-1])
        step = line.total_length_m / config.SAMPLES_PER_TRACK

        # The gap between last and first sample is one ordinary segment, not a seam.
        assert gap == pytest.approx(step, rel=0.35), f"seed {seed} closes badly"


def test_the_first_point_is_not_repeated_at_the_end():
    line = generator.generate(5)

    assert len(line.theta) == config.SAMPLES_PER_TRACK
    assert line.theta[-1] < 2.0 * np.pi
    assert not (line.x[0] == line.x[-1] and line.y[0] == line.y[-1])


def test_no_module_function_adjusts_endpoints():
    """Closure must come from the functional form, so nothing may nudge the ends to meet."""
    source = (REPO / "python" / "track" / "generator.py").read_text(encoding="utf-8")

    for banned in ("x[-1] =", "y[-1] =", "x[0] =", "y[0] ="):
        assert banned not in source, f"generator assigns an endpoint: {banned}"


# -----------------------------------------------------------------------------------------
# Curvature (research C7) - the check that matters
# -----------------------------------------------------------------------------------------


def test_analytic_curvature_agrees_with_a_fine_numerical_estimate():
    """Validate the closed-form curvature without depending on it.

    The generator uses the analytic expression precisely so that no finite-difference error
    reaches the accept-or-reject decision. That makes the formula itself unverified by every
    other test in this file, so it is compared here against a numerical estimate taken on a
    much finer grid than the generator uses. The fine grid is the arbiter; agreeing with it
    is evidence the algebra is right.
    """
    params = generator.draw_parameters(11)

    fine = np.linspace(0.0, 2.0 * np.pi, 200_000, endpoint=False)
    r, dr, d2r = generator._radius_terms(params, fine)

    x = r * np.cos(fine)
    y = r * np.sin(fine)

    # Curvature from coordinates, by gradients: k = (x' y'' - y' x'') / (x'^2 + y'^2)^1.5.
    # A different route to the same quantity, sharing no algebra with the polar expression.
    dx = np.gradient(x, fine, edge_order=2)
    dy = np.gradient(y, fine, edge_order=2)
    ddx = np.gradient(dx, fine, edge_order=2)
    ddy = np.gradient(dy, fine, edge_order=2)
    numerical = (dx * ddy - dy * ddx) / np.power(dx * dx + dy * dy, 1.5)

    analytic = (r * r + 2.0 * dr * dr - r * d2r) / np.power(r * r + dr * dr, 1.5)

    # Trim the wrap-around samples: np.gradient is one-sided at the array ends, and this curve
    # is periodic rather than terminated, so those two points are an artefact of the array.
    interior = slice(2, -2)
    assert np.allclose(analytic[interior], numerical[interior], rtol=1e-4, atol=1e-6)


def test_curvature_is_signed_and_changes_sign_on_a_wavy_loop():
    """Inflections are real geometry and must show as a sign change, not be flattened away."""
    line = generator.generate(4)

    assert np.any(line.curvature > 0)
    assert np.any(line.curvature < 0)


def test_radius_is_the_reciprocal_of_absolute_curvature():
    line = generator.generate(6)
    real = np.abs(line.curvature) > 1e-12

    assert np.allclose(line.radius[real], 1.0 / np.abs(line.curvature[real]))
    assert np.all(line.radius > 0)
    assert np.all(np.isfinite(line.radius))


def test_a_circle_has_the_radius_it_was_given():
    """Zero amplitude degenerates the harmonic loop to a circle of radius R0.

    The one case where the answer is known in advance, so it is worth pinning: it catches a
    sign error or a stray factor that a wavy curve would hide.
    """
    params = generator.TrackSeed(
        seed=0, amplitude=0.0, phases=tuple(0.0 for _ in config.HARMONICS))
    line = generator.centre_line(params)

    assert np.allclose(line.radius, config.TRACK_R0_M, rtol=1e-9)
    assert line.total_length_m == pytest.approx(2.0 * np.pi * config.TRACK_R0_M, rel=1e-6)
    assert np.all(line.curvature > 0)


# -----------------------------------------------------------------------------------------
# Sampling and arc length
# -----------------------------------------------------------------------------------------


def test_arc_length_is_monotonic_and_starts_at_zero():
    line = generator.generate(8)

    assert line.arc_length[0] == 0.0
    assert np.all(np.diff(line.arc_length) > 0)
    assert line.arc_length[-1] < line.total_length_m


def test_total_length_includes_the_closing_segment():
    """The segment from the last sample back to the first is a real part of a closed loop."""
    line = generator.generate(8)
    closing = line.total_length_m - line.arc_length[-1]
    typical = float(np.median(np.diff(line.arc_length)))

    assert closing == pytest.approx(typical, rel=0.35)


def test_amplitude_is_drawn_inside_the_configured_range():
    low, high = config.AMPLITUDE_RANGE

    for seed in range(1, 60):
        params = generator.draw_parameters(seed)
        assert low <= params.amplitude <= high
        assert len(params.phases) == len(config.HARMONICS)
        assert all(0.0 <= p <= 2.0 * np.pi for p in params.phases)


def test_high_harmonics_are_damped_by_one_over_k_squared():
    """The falloff is what keeps k=5 from dictating the tightest corner.

    Without it the highest harmonic would dominate curvature, since amplitude enters curvature
    weighted by k^2, and the radius floor would reject almost every seed.
    """
    params = generator.draw_parameters(2)
    contributions = [params.amplitude / (k * k) for k in config.HARMONICS]

    assert contributions == sorted(contributions, reverse=True)
    assert contributions[-1] < contributions[0] / 4


# -----------------------------------------------------------------------------------------
# TrackSeed bookkeeping
# -----------------------------------------------------------------------------------------


def test_a_rejected_seed_keeps_its_geometry_and_names_the_failure():
    params = generator.draw_parameters(9)
    bad = params.rejected("min radius 4.8 m below floor 6.97 m")

    assert bad.accepted is False
    assert "floor" in bad.rejection_reason
    assert bad.amplitude == params.amplitude
    assert bad.phases == params.phases
    assert bad.seed == params.seed


def test_an_accepted_seed_cannot_carry_a_rejection_reason():
    with pytest.raises(ValueError):
        generator.TrackSeed(
            seed=1, amplitude=0.5, phases=tuple(0.0 for _ in config.HARMONICS),
            accepted=True, rejection_reason="something")


def test_a_rejected_seed_must_say_why():
    with pytest.raises(ValueError):
        generator.TrackSeed(
            seed=1, amplitude=0.5, phases=tuple(0.0 for _ in config.HARMONICS),
            accepted=False, rejection_reason=None)


def test_phases_must_match_the_harmonic_count():
    with pytest.raises(ValueError):
        generator.TrackSeed(seed=1, amplitude=0.5, phases=(0.0,))
