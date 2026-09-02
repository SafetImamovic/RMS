"""The three M5 figures, drawn from the committed comparison inputs.

**Every figure here is produced by this script and none is saved by hand** (SC-005). The inputs are
the same CSVs `python/m5/compare.py` reads, so a changed input changes the figure and a figure can
never drift away from the table it sits beside.

**The artefacts are drawn, not written underneath.** Each figure that could be misread carries the
correction inside the axes: the smoothness figure is drawn twice, raw and with every driver on the
human's 0.05 lattice, because 67.8 per cent of the human's nonzero steering changes land exactly on
that lattice and a raw overlay reports the input device (research R8). The steering-level figure
carries the near-zero share in its own panel, because the generated loop always turns and a reader
who sees only the histogram has been told something false about driving style (research R5).

Usage::

    python -m python.m5.plots

Runs under ``.venv``. Writes into ``results/plots``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)

from python.eda import lattice  # noqa: E402
from python.m5 import columns as m5  # noqa: E402
from python.m5.compare import build, quantised_deltas  # noqa: E402

INK = "#1f2933"
GRID = "#d8dee3"
MUTED = "#6b7780"

#: One colour per driver, held constant across all three figures so a reader who has learned the
#: legend on one does not have to relearn it on the next. The human is black because it is the
#: reference every other series is read against, not another driver.
COLOURS: dict[str, str] = {
    "ppo_car_009_bc_deterministic": "#2f6f9f",
    "ppo_car_009_bc_sampling": "#7aa8c9",
    "heuristic_weighted_average": "#b03a2e",
    "bc_bc_balanced_v01": "#3f8f5f",
    "human_combined": "#1f2933",
}

SHORT: dict[str, str] = {
    "ppo_car_009_bc_deterministic": "RL 009, deterministic",
    "ppo_car_009_bc_sampling": "RL 009, sampling",
    "heuristic_weighted_average": "scripted driver",
    "bc_bc_balanced_v01": "BC (predictions only)",
    "human_combined": "human (combined)",
}


def _style(axes: plt.Axes) -> None:
    axes.grid(True, color=GRID, linewidth=0.6, alpha=0.8)
    axes.set_axisbelow(True)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        axes.spines[spine].set_color(GRID)
    axes.tick_params(colors=MUTED, labelsize=8)


def _share_steps(axes: plt.Axes, values: np.ndarray, edges: np.ndarray, name: str) -> None:
    """A relative-frequency step outline rather than filled bars.

    Shares because the columns differ by a factor of six in sample size, and outlines because five
    overlaid filled histograms hide whichever series is drawn first.
    """
    counts, _ = np.histogram(values, bins=edges)
    shares = counts / counts.sum() if counts.sum() else counts.astype(float)
    axes.step(
        edges[:-1],
        shares,
        where="post",
        color=COLOURS[name],
        linewidth=2.0 if name == "human_combined" else 1.4,
        label=SHORT[name],
    )


def figure_delta(result: dict, out: Path) -> Path:
    """T028: `|delta steering|` for all drivers, raw and on the human lattice.

    **Two panels, not one.** The raw panel is the measurement everyone expects and it is dominated
    by the human's recording resolution; the lattice panel is the same comparison after every driver
    is snapped onto that resolution. Reporting either alone would be an argument rather than a
    result.
    """
    every = result["drivers"] + [result["human"]]
    # Bins centred on the 0.05 lattice rather than an arbitrary linspace. Bins that do not divide
    # the lattice alias against it and draw a comb that is a property of the binning, which would
    # be a second artefact laid on top of the one this figure is about.
    edges = np.arange(-0.025, 0.626, 0.05)

    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    for column in every:
        _share_steps(axes[0], column.abs_delta_steering, edges, column.name)

    # **The right panel is the cumulative distribution, not a second histogram**, because the KS
    # statistic the report leads with is a property of these curves: D is the largest vertical gap
    # between a driver's curve and the human's. Drawing the histogram twice would show the reader a
    # picture and then ask them to trust a number computed from something else.
    for column in every:
        values = np.sort(quantised_deltas(column))
        if values.size == 0:
            continue
        ecdf = np.arange(1, values.size + 1) / values.size
        label = SHORT[column.name]
        if column.name != "human_combined":
            match = next(c for c in result["primary"] if c.driver == column.name)
            label = f"{label} (D = {match.quantised.statistic:.2f})"
        axes[1].step(
            values,
            ecdf,
            where="post",
            color=COLOURS[column.name],
            linewidth=2.0 if column.name == "human_combined" else 1.4,
            label=label,
        )
    axes[1].set_xlim(0.0, 0.6)
    axes[1].set_ylim(0.0, 1.02)
    axes[1].set_ylabel("cumulative share", fontsize=9, color=INK)
    axes[1].legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right")

    axes[0].set_title("Distribution, raw at 14.08 Hz", fontsize=10, color=INK)
    axes[1].set_title(
        "Cumulative, every driver on the human 0.05 lattice.\nD is the largest vertical gap from "
        "the human curve.",
        fontsize=10,
        color=INK,
    )
    for panel in axes:
        _style(panel)
        panel.set_xlabel("|change in steering| between consecutive samples", fontsize=9, color=INK)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("share of samples (log scale)", fontsize=9, color=INK)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK)

    figure.suptitle(
        "Smoothness: |delta steering| at the human's own sampling rate",
        fontsize=12,
        color=INK,
    )
    figure.text(
        0.5,
        0.005,
        "The human holds the wheel still and then jumps: 67.8 per cent of its nonzero changes land "
        "exactly on the 0.05 lattice.\nThe left panel therefore measures the input device as much "
        "as the driving. The right panel is what the conclusion is read off.",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 0.94))
    figure.savefig(out, dpi=150)
    plt.close(figure)
    return out


def figure_lattice(result: dict, out: Path) -> Path:
    """T029: overlaid lattice histograms of steering, with the artefact in its own panel."""
    every = result["drivers"] + [result["human"]]
    support = lattice.levels()

    figure, axes = plt.subplots(
        1, 2, figsize=(11.0, 4.2), gridspec_kw={"width_ratios": [2.4, 1.0]}
    )

    for column in every:
        snapped = lattice.quantise(column.steering)
        counts = np.array([np.sum(np.isclose(snapped, level)) for level in support], dtype=float)
        axes[0].plot(
            support,
            counts / counts.sum(),
            color=COLOURS[column.name],
            linewidth=2.0 if column.name == "human_combined" else 1.3,
            marker="o",
            markersize=2.5,
            label=SHORT[column.name],
        )

    axes[0].set_title("Steering level on the 41-point lattice", fontsize=10, color=INK)
    axes[0].set_xlabel("steering", fontsize=9, color=INK)
    axes[0].set_ylabel("share of samples", fontsize=9, color=INK)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    _style(axes[0])

    # The artefact, in the axes rather than in a caption. Without it the divergences in the report
    # read as a statement about driving style, and they are largely a statement about the track.
    names = [c.name for c in every]
    positions = np.arange(len(names))
    axes[1].barh(
        positions - 0.2,
        [100 * c.straight_share for c in every],
        height=0.36,
        color=[COLOURS[n] for n in names],
        label="near zero",
    )
    axes[1].barh(
        positions + 0.2,
        [100 * c.left_share for c in every],
        height=0.36,
        color=[COLOURS[n] for n in names],
        alpha=0.45,
        label="steering left",
    )
    axes[1].set_yticks(positions)
    axes[1].set_yticklabels([SHORT[n] for n in names], fontsize=8, color=INK)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("per cent of samples", fontsize=9, color=INK)
    axes[1].set_title("Solid: near zero. Faded: left.", fontsize=10, color=INK)
    _style(axes[1])

    figure.suptitle(
        "Steering level, and the track geometry that dominates it",
        fontsize=12,
        color=INK,
    )
    figure.text(
        0.5,
        0.005,
        "The generated loop always turns and is driven one way, so the agents steer left on 76 to "
        "88 per cent of steps against the human's 23.5.\nThe divergences in the report are "
        "therefore mostly topology, which is why the conditional comparison exists.",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    figure.tight_layout(rect=(0, 0.07, 1, 0.94))
    figure.savefig(out, dpi=150)
    plt.close(figure)
    return out


def figure_summary(result: dict, out: Path) -> Path:
    """T030: the defence figure. Four panels, each one number per driver.

    **Execution first, resemblance second**, which is the ordering `DESIGN.md` 7 prescribes: a
    driver that resembles the human and cannot finish a lap has not succeeded at anything.
    """
    drivers = result["drivers"]
    human = result["human"]
    names = [c.name for c in drivers]
    positions = np.arange(len(names))
    bar_colours = [COLOURS[n] for n in names]

    figure, axes = plt.subplots(1, 4, figsize=(13.0, 4.0))

    completion = [
        100.0 * c.laps_completed / c.laps_possible if c.laps_completed is not None else np.nan
        for c in drivers
    ]
    axes[0].bar(positions, completion, color=bar_colours)
    axes[0].set_title("Runs completed (%)", fontsize=10, color=INK)
    axes[0].set_ylim(0, 105)
    for i, value in enumerate(completion):
        if np.isnan(value):
            axes[0].text(i, 4, "never drives", rotation=90, fontsize=8, ha="center", color=MUTED)

    deltas = [float(c.abs_delta_steering.mean()) for c in drivers]
    axes[1].bar(positions, deltas, color=bar_colours)
    axes[1].axhline(
        float(human.abs_delta_steering.mean()), color=INK, linestyle="--", linewidth=1.2
    )
    axes[1].set_title("Mean |delta steering|", fontsize=10, color=INK)

    lattice_d = [comparison.quantised.statistic for comparison in result["primary"]]
    axes[2].bar(positions, lattice_d, color=bar_colours)
    axes[2].set_title("Distance from human,\nsmoothness (KS D, on lattice)", fontsize=10, color=INK)

    conditional = [row["kl_from_human"] for row in result["conditional"]]
    axes[3].bar(positions, conditional, color=bar_colours)
    axes[3].set_title("Distance from human,\nturning only (KL)", fontsize=10, color=INK)

    for panel in axes:
        _style(panel)
        panel.set_xticks(positions)
        panel.set_xticklabels([SHORT[n] for n in names], rotation=30, ha="right", fontsize=8)

    figure.suptitle(
        "M5: execution first, then resemblance. Dashed line is the human.",
        fontsize=12,
        color=INK,
    )
    figure.text(
        0.5,
        0.005,
        "Lower is closer to the human in the two right panels, and they disagree: the deterministic "
        "policy is closest on smoothness,\nthe sampling policy on turning distribution. Noise makes "
        "a policy's distribution more human and its motion less so.",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    figure.tight_layout(rect=(0, 0.08, 1, 0.93))
    figure.savefig(out, dpi=150)
    plt.close(figure)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    out_dir = args.out_dir or args.root / "results" / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = build(args.root)
    written = [
        figure_delta(result, out_dir / "m5_delta_steering.png"),
        figure_lattice(result, out_dir / "m5_steering_lattice.png"),
        figure_summary(result, out_dir / "m5_summary.png"),
    ]
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
