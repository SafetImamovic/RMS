"""Draw a training run as small multiples: the total, its six terms, and episode length.

**Small multiples rather than one pair of axes.** The series differ in scale by two orders of
magnitude, from a cumulative reward near -5 to a speed term near 0.005, and putting two of them on
one figure with two y-scales invents a relationship between them that the data does not contain.
Eight panels sharing an x-axis let a reader compare shapes without being told a story by the
drawing.

The panel that matters is rarely the first one. A total that wanders says little on its own; the
question is always which term moved, and the six per-term series exist precisely so the answer is
visible rather than inferred (FR-008).

The shaded band on the first panel is the trainer's own per-summary standard deviation, parsed back
out of the run log because the event file does not carry it. Without it a reader cannot tell a
trend from a wander, which for this project's first run was the whole finding.

Usage::

    python -m python.rl.plot_curve results/rl/curves/ppo_car_v01.csv \\
        --log results/rl/ppo_car_v01.log --out results/rl/ppo_car_v01.png

Runs under ``.venv``.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)


INK = "#1f2933"
LINE = "#2f6f9f"
MARK = "#b03a2e"
GRID = "#d8dee3"
MUTED = "#6b7780"

#: Column, title, and the one line of context a reader needs to judge the panel.
PANELS: Sequence[Tuple[str, str, str]] = (
    ("cumulative_reward", "Cumulative reward", "the headline number"),
    ("reward_checkpoint", "reward/checkpoint", "progress: 24 markers make a lap"),
    ("reward_wall", "reward/wall", "-5.0 per barrier hit"),
    ("reward_wrong_way", "reward/wrong_way", "-1.0 per reversal"),
    ("reward_step", "reward/step", "-0.001 per step: reads as episode length"),
    ("reward_speed", "reward/speed", "+0.001 x v_norm"),
    ("reward_jerk", "reward/jerk", "steering changes above 0.55"),
    ("episode_length", "Episode length (steps)", "cap is 6000, so 120 s"),
)

_SUMMARY = re.compile(r"Step: (\d+)\..*Mean Reward: (-?\d+\.\d+)\. Std of Reward: (\d+\.\d+)")


def read_curve(path: str) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def column(rows: Sequence[dict], name: str) -> List[float]:
    """One column as floats, with an absent value becoming NaN so it leaves a gap in the line.

    A gap is the correct drawing of "the trainer did not report this here". Substituting zero
    would draw a spike to a value the run never had.
    """
    values = []
    for row in rows:
        raw = row.get(name, "")
        values.append(float(raw) if raw not in ("", None) else math.nan)
    return values


def read_std_band(log_path: str) -> Dict[int, Tuple[float, float]]:
    """Per-summary mean and standard deviation, parsed out of the trainer's console log."""
    band: Dict[int, Tuple[float, float]] = {}

    with open(log_path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            found = _SUMMARY.search(line)
            if found:
                band[int(found.group(1))] = (float(found.group(2)), float(found.group(3)))

    return band


def plot(curve_path: str, out_path: str, log_path: Optional[str] = None,
         title: Optional[str] = None, subtitle: Optional[str] = None) -> str:
    rows = read_curve(curve_path)
    if not rows:
        raise SystemExit(f"{curve_path} has no rows to draw")

    steps = [int(row["step"]) for row in rows]
    run_id = rows[0].get("run_id", os.path.basename(curve_path))
    band = read_std_band(log_path) if log_path else {}

    figure, axes = plt.subplots(2, 4, figsize=(17, 7.2), sharex=True)
    figure.patch.set_facecolor("white")

    for axis, (key, panel_title, context) in zip(axes.ravel(), PANELS):
        values = column(rows, key)
        axis.plot(steps, values, color=LINE, linewidth=2, solid_capstyle="round")

        if key == "cumulative_reward" and band:
            marked = [s for s in steps if s in band]
            axis.fill_between(
                marked,
                [band[s][0] - band[s][1] for s in marked],
                [band[s][0] + band[s][1] for s in marked],
                color=LINE, alpha=0.15, linewidth=0)

        axis.axhline(0, color=GRID, linewidth=1, zorder=0)
        axis.set_title(panel_title, color=INK, fontsize=11, loc="left", pad=24, fontweight="bold")
        axis.text(0, 1.015, context, transform=axis.transAxes, color=MUTED, fontsize=8.5, va="bottom")
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(GRID)
        axis.tick_params(colors=MUTED, labelsize=8.5)

    # The claim a run makes about itself, drawn rather than asserted: the first and last ten
    # summaries as flat segments, so a reader can see whether the difference is a trend or a wander.
    totals = column(rows, "cumulative_reward")
    if len(totals) >= 20:
        first = sum(totals[:10]) / 10
        last = sum(totals[-10:]) / 10
        head = axes.ravel()[0]
        head.plot([steps[0], steps[9]], [first, first], color=MARK, linewidth=2.5)
        head.plot([steps[-10], steps[-1]], [last, last], color=MARK, linewidth=2.5)
        head.annotate(f"first 10: {first:.2f}", (steps[4], first), textcoords="offset points",
                      xytext=(0, 10), color=MARK, fontsize=8.5, ha="center")
        head.annotate(f"last 10: {last:.2f}", (steps[-5], last), textcoords="offset points",
                      xytext=(0, -16), color=MARK, fontsize=8.5, ha="center")

    for axis in axes[1]:
        axis.set_xlabel("training step", color=MUTED, fontsize=9)

    figure.suptitle(title or f"{run_id}: {steps[-1]:,} steps",
                    color=INK, fontsize=13, x=0.008, ha="left", y=0.985, fontweight="bold")
    figure.text(0.008, 0.945,
                subtitle or ("Shaded band on the first panel is the trainer's per-summary standard "
                             "deviation. reward/checkpoint is the one that decides whether the car "
                             "is going anywhere."),
                color=MUTED, fontsize=9.5, ha="left")

    figure.tight_layout(rect=(0, 0, 1, 0.93))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    figure.savefig(out_path, dpi=140, facecolor="white")
    plt.close(figure)

    return out_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("curve", help="a committed curve CSV from python.rl.export_curves")
    parser.add_argument("--log", default=None, help="the run's console log, for the noise band")
    parser.add_argument("--out", default=None, help="target PNG")
    parser.add_argument("--title", default=None)
    parser.add_argument("--subtitle", default=None)
    args = parser.parse_args(argv)

    out = args.out or os.path.splitext(args.curve)[0] + ".png"
    print("wrote", plot(args.curve, out, args.log, args.title, args.subtitle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
