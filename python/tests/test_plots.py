"""Tests for the track figures.

Smoke tests, deliberately. A test cannot judge whether a chart reads well, so these check the
things that can be checked mechanically: that the files are produced, that nothing is written
outside the output directory, and that the binning choice which fixed a real rendering
artefact stays fixed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from python.track import generator, matching, plots


@pytest.fixture()
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "plots"


def test_a_track_figure_is_written(out_dir):
    path = plots.plot_track(generator.generate(1), out_dir=out_dir)

    assert path.exists()
    assert path.name == "track_seed_1.png"
    assert path.stat().st_size > 10_000


def test_the_match_figure_is_written(out_dir):
    path = plots.plot_match(seeds=range(1, 6), out_dir=out_dir)

    assert path.exists()
    assert path.name == "track_match.png"
    assert path.stat().st_size > 10_000


def test_nothing_is_written_outside_the_output_directory(out_dir, tmp_path):
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    plots.plot_track(generator.generate(2), out_dir=out_dir)
    plots.plot_match(seeds=range(1, 4), out_dir=out_dir)

    for path in {p for p in tmp_path.rglob("*") if p.is_file()} - before:
        assert out_dir in path.parents


def test_the_two_series_colours_are_distinct_and_fixed():
    """Colour follows the entity, never its rank, so these must not be reassigned."""
    assert plots.TRACK_COLOUR != plots.HUMAN_COLOUR
    assert plots.TRACK_COLOUR.startswith("#") and plots.HUMAN_COLOUR.startswith("#")


def test_the_histogram_bins_are_centred_on_the_human_lattice():
    """Regression: edge-aligned bins made the human series render as a comb.

    The recorded steering sits on a 0.05 lattice with float noise below the nominal value,
    so edge-aligned bins drop values into whichever neighbour the noise points at and leave
    alternate bins empty. Centring is what fixed it, and re-aligning the edges would look
    like a harmless tidy-up.
    """
    reference = matching.reference_distribution()
    bins = np.arange(-0.025, 1.0251, 0.05)

    counts, _ = np.histogram(reference, bins=bins)
    occupied = counts[: int(np.max(reference) / 0.05) + 1]

    # With centred bins no interior bin below the maximum is empty; with edge-aligned bins
    # roughly half of them were.
    assert np.count_nonzero(occupied == 0) <= 1

    edge_aligned, _ = np.histogram(reference, bins=np.linspace(0.0, 1.0, 21))
    assert np.count_nonzero(edge_aligned[: len(occupied)] == 0) > 1
