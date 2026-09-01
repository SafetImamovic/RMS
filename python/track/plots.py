"""Figures for generated tracks.

Two plots, each answering one question:

`track_seed_<n>.png` asks what the track looks like and where its hardest corner is. That is a
path in the plane, so it is drawn as a path with equal axis scaling; a track plotted on
unequal axes is a different shape, and the tightest corner is exactly what the reader is being
asked to judge.

`track_match.png` asks how the steering a track demands compares with what a human supplied.
Two distributions on one axis, as relative frequency rather than counts, since 80000 pooled
track samples and 2193 human ones are not comparable as counts.

Colours are a two-hue categorical pair chosen for colour-vision separation, not for taste:
worst-pair separation is 28.1 in OKLab hundredths under protanopia and 32.9 for normal
vision. Identity is never carried by colour alone here, so both figures also carry a legend or
a direct label.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

# A non-interactive backend, chosen before pyplot is imported. These figures are written to
# files from scripts and tests, and the default backend would try to reach a display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import config, geometry, matching  # noqa: E402
from .generator import CentreLine, draw_parameters, centre_line  # noqa: E402
from .vehicle import VehicleProfile, build_profile  # noqa: E402

PLOTS_DIR: Path = Path(__file__).resolve().parents[2] / "results" / "plots"

# Categorical pair, in fixed order: generated first, human second. Never cycled, never
# reassigned by rank, so the same entity keeps its colour across every figure.
TRACK_COLOUR = "#3B6FD4"
HUMAN_COLOUR = "#D97A1E"

# Text wears text tokens, not the series colour. A coloured mark beside a label carries the
# identity; colouring the words as well makes them harder to read for no added information.
INK = "#1f2328"
INK_MUTED = "#5a6169"
GRID = "#e3e5e8"


def _style(ax) -> None:
    """Recessive axes and grid, so the data is the only prominent thing on the figure."""
    ax.set_facecolor("white")
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_MUTED, labelsize=9)


def plot_track(line: CentreLine, profile: VehicleProfile | None = None,
               out_dir: Path | None = None) -> Path:
    """Draw one track with its tightest corner marked.

    A single series, so there is no legend: the title names what is drawn. The one annotation
    is a direct label on the corner that decides whether the seed is accepted at all.
    """
    profile = profile or build_profile()
    out_dir = Path(out_dir) if out_dir is not None else PLOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    report = geometry.check_geometry(line, profile)
    checkpoints = geometry.place_checkpoints(line)
    tightest = int(np.argmin(line.radius))

    fig, ax = plt.subplots(figsize=(7.0, 7.0), dpi=150)
    _style(ax)

    # Closed loop: the segment from the last sample back to the first is real and is drawn,
    # otherwise the figure shows a gap the track does not have.
    ax.plot(np.append(line.x, line.x[0]), np.append(line.y, line.y[0]),
            color=TRACK_COLOUR, linewidth=2.0, zorder=3)

    # Same colour as the line, because the checkpoints are part of the same entity rather
    # than a second series. A single series takes no legend box, so their count is stated in
    # the caption below instead.
    ax.scatter([c.x for c in checkpoints], [c.y for c in checkpoints],
               s=14, color=TRACK_COLOUR, alpha=0.55, zorder=4)

    ax.scatter([line.x[tightest]], [line.y[tightest]],
               s=90, facecolor="white", edgecolor=INK, linewidth=2.0, zorder=5)

    ax.annotate(
        f"tightest corner {report.min_radius_m:.1f} m\nfloor {profile.r_floor_m:.2f} m",
        xy=(line.x[tightest], line.y[tightest]),
        xytext=(14, 14), textcoords="offset points",
        color=INK, fontsize=9,
        arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=1.0))

    verdict = "accepted" if report.ok else f"rejected: {report.rejection_reason}"
    ax.set_title(f"Track seed {line.seed}  ({verdict})", color=INK, fontsize=12, pad=12)
    ax.set_xlabel("x (m)", color=INK_MUTED, fontsize=10)
    ax.set_ylabel("y (m)", color=INK_MUTED, fontsize=10)

    # Equal aspect, or the shape being judged is not the shape that exists.
    ax.set_aspect("equal", adjustable="datalim")

    ax.text(0.5, -0.09,
            f"length {line.total_length_m:.0f} m   "
            f"closest self-approach {report.min_separation_m:.1f} m   "
            f"{len(checkpoints)} checkpoints, evenly spaced by arc length",
            transform=ax.transAxes, ha="center", color=INK_MUTED, fontsize=9)

    path = out_dir / f"track_seed_{line.seed}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return path


def plot_match(seeds=None, profile: VehicleProfile | None = None,
               out_dir: Path | None = None) -> Path:
    """Draw the pooled required-steering demand against the human recording.

    Relative frequency on a shared set of bins. Counts would be meaningless here: the pooled
    track sample is roughly forty times the size of the human one, so a count histogram would
    say more about how many seeds were generated than about either distribution.

    A single x axis. The two series measure the same quantity, so a second scale would be a
    dual-axis chart, which is the one construction that reliably misleads.
    """
    profile = profile or build_profile()
    seeds = list(seeds if seeds is not None else config.TRAIN_SEEDS)
    out_dir = Path(out_dir) if out_dir is not None else PLOTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    pooled = np.concatenate([
        matching.required_steering(centre_line(draw_parameters(s)), profile).required_steer
        for s in seeds])
    human = matching.reference_distribution()
    bound = matching.demand_bound(pooled, human, scope="train", n_seeds_pooled=len(seeds))

    fig, ax = plt.subplots(figsize=(9.0, 5.0), dpi=150)
    _style(ax)

    # Bin width 0.05 to match the lattice the human steering column is recorded on, with the
    # edges offset by half a step so each lattice value sits at a bin CENTRE.
    #
    # Both halves of that matter. At width 0.025 the bins alias against the lattice and the
    # human series renders as alternating full and empty bars. Aligning edges to the lattice
    # is not enough either: the recorded values carry float noise and sit just below their
    # nominal points, 0.55 appearing as 0.5500001 and 0.15 slightly under, so a value lands in
    # whichever neighbouring bin the noise happens to point at and alternate bins still empty.
    # Centring is robust to noise in either direction. Both series share the bins, or the
    # comparison would be between two griddings rather than two distributions.
    bins = np.arange(-0.025, 1.0251, 0.05)
    for values, colour, label in (
            (human, HUMAN_COLOUR, "human (track1, non-zero steering)"),
            (pooled, TRACK_COLOUR, f"generated tracks (pooled, {len(seeds)} seeds)")):
        weights = np.full(len(values), 1.0 / len(values))
        ax.hist(values, bins=bins, weights=weights, histtype="step",
                color=colour, linewidth=2.0, zorder=3, label=label)

    # The limit that explains the shape, marked rather than left to be inferred. Placed low
    # on the axis: the legend occupies the top right, and at 0.94 of the y range the two
    # collided.
    ax.axvline(profile.max_required_steer, color=INK_MUTED, linewidth=1.2,
               linestyle="--", zorder=2)
    ax.text(profile.max_required_steer - 0.015, ax.get_ylim()[1] * 0.40,
            f"most a track\nmay demand\n({profile.max_required_steer:.3f})",
            ha="right", va="center", color=INK_MUTED, fontsize=9)

    ax.set_title(
        "Steering demanded by generated tracks against steering a human applied",
        color=INK, fontsize=12, pad=12)
    ax.set_xlabel("|steering|, normalised to full lock", color=INK_MUTED, fontsize=10)
    ax.set_ylabel("relative frequency", color=INK_MUTED, fontsize=10)
    ax.set_xlim(0, 1.0)

    legend = ax.legend(frameon=False, fontsize=9, loc="upper right")
    for text in legend.get_texts():
        text.set_color(INK)

    verdict = "within bound" if bound.within_bound else "OUTSIDE BOUND"
    ax.text(
        0.5, -0.16,
        f"SC-010 is a bound, not a match: {verdict}. Peak demand "
        f"{bound.max_required:.3f} against a human maximum of {bound.reference_max:.3f}. "
        f"The human curve lies above by construction, since it carries corrections and "
        f"overshoot on top of what the road required.",
        transform=ax.transAxes, ha="center", va="top", color=INK_MUTED, fontsize=9,
        wrap=True)

    path = out_dir / "track_match.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m python.track.plots", description="Draw figures for generated tracks.")
    parser.add_argument("--seed", type=int, action="append", default=None,
                        help="Draw this seed. Repeatable.")
    parser.add_argument("--match", action="store_true", help="Draw the demand comparison.")
    parser.add_argument("--out-dir", type=Path, default=None)

    args = parser.parse_args(argv)
    profile = build_profile()

    if not args.seed and not args.match:
        parser.error("nothing to draw: pass --seed and/or --match")

    for seed in args.seed or []:
        line = centre_line(draw_parameters(seed))
        print(f"wrote {plot_track(line, profile, out_dir=args.out_dir)}")

    if args.match:
        print(f"wrote {plot_match(profile=profile, out_dir=args.out_dir)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
