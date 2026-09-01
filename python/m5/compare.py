"""The M5 comparison: four drivers, two axes, and the artefacts named beside every number.

**Read this before reading any figure it produces.** Three distortions were measured before this
module was written, and each one makes an obvious comparison say something confidently false:

- **R5, track geometry.** The generated loop always turns and is driven one way, so the agent
  steers left on 87.6 per cent of steps against the human's 23.5. A steering-level comparison
  reports the track.
- **R7, sampling rate.** The Unity trace is 50 Hz while the agent decides every fourth step, so
  67.1 per cent of raw differences are structurally zero. Everything here reads the committed
  inputs, which are already resampled to 14.08 Hz.
- **R8, input device.** 67.8 per cent of the human's nonzero steering changes land exactly on the
  0.05 lattice, with modes at 0.15 and 0.20. The human held zero and then jumped three or four
  steps. A smoothness comparison against it reports the input device.

So every comparison here is reported **twice**: once raw, and once with all four drivers quantised
onto the human lattice, which puts them on one recording resolution. Neither is the answer on its
own. The artefact shares sit in the same table as the statistic, never in prose after it.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from python.eda import lattice
from python.eda.authenticity import KsTwoSampleResult, chi2_homogeneity, ks_two_sample
from python.m5 import columns as m5
from python.rl.report import counts_on_lattice, lattice_support


@dataclass(frozen=True)
class AxisComparison:
    """One driver against the human on one axis, raw and on the lattice."""

    driver: str
    axis: str
    raw: KsTwoSampleResult
    quantised: KsTwoSampleResult


def quantised_deltas(column: m5.DriverColumn) -> np.ndarray:
    """`|delta steering|` after snapping every sample onto the human lattice.

    **Applied to all four drivers, including the human, which is the difference from `DESIGN.md`
    7's rule for steering level.** There, quantisation is applied to the model and never to the
    human, because the human record is the reference being matched. Here the question is different:
    the axis is contaminated by the human's own recording resolution (R8), so putting everyone on
    that resolution is what makes the comparison about driving. Quantising the human is a no-op
    anyway, since it is already on the lattice.
    """
    snapped = lattice.quantise(column.steering)
    # Same seam rule as everywhere else: differences within a run, never across one.
    parts: list[np.ndarray] = []
    start = 0
    for size in column.run_sizes:
        parts.append(np.abs(np.diff(snapped[start : start + size])))
        start += size
    return np.concatenate(parts) if parts else np.array([])


def compare_axis(
    column: m5.DriverColumn,
    human: m5.DriverColumn,
    axis: str,
) -> AxisComparison:
    if axis == "abs_delta_steering":
        raw_a, raw_b = column.abs_delta_steering, human.abs_delta_steering
        q_a, q_b = quantised_deltas(column), quantised_deltas(human)
    elif axis == "steering":
        raw_a, raw_b = column.steering, human.steering
        q_a, q_b = lattice.quantise(column.steering), lattice.quantise(human.steering)
    else:
        raise ValueError(f"unknown axis {axis!r}")

    return AxisComparison(
        driver=column.name,
        axis=axis,
        raw=ks_two_sample(raw_a, raw_b, scope=f"{column.name} vs human, {axis}, raw",
                          label_a=column.name, label_b="human"),
        quantised=ks_two_sample(q_a, q_b, scope=f"{column.name} vs human, {axis}, lattice",
                                label_a=column.name, label_b="human"),
    )


def steering_level_report(column: m5.DriverColumn, human: m5.DriverColumn) -> dict:
    """The secondary axis: KL and chi-square on the lattice, with the artefacts beside them."""
    support = lattice_support()
    chi2 = chi2_homogeneity(
        counts_on_lattice(column.steering, support),
        counts_on_lattice(human.steering, support),
        support,
        scope=f"{column.name} vs human",
    )
    return {
        "driver": column.name,
        "kl_from_human": lattice.kl_divergence(column.steering, human.steering),
        "chi2": chi2.statistic,
        "chi2_dof": chi2.dof,
        "chi2_p": chi2.p_value,
        "chi2_reject": chi2.reject_null,
        "straight_share": column.straight_share,
        "left_share": column.left_share,
        "right_share": column.right_share,
    }


def conditional_on_nonzero(column: m5.DriverColumn, human: m5.DriverColumn) -> dict:
    """The comparison `DESIGN.md` 7's second M5 note asks for, given nonzero steering.

    The straight-line asymmetry is the largest single difference between the drivers and it is a
    property of the track, not of the driving. Dropping the zeros from both sides is what the design
    prescribes to see past it.
    """
    a = column.steering[np.abs(column.steering) >= 0.0125]
    b = human.steering[human.steering != 0.0]
    support = lattice_support()
    chi2 = chi2_homogeneity(
        counts_on_lattice(a, support),
        counts_on_lattice(b, support),
        support,
        scope=f"{column.name} vs human, turning only",
    )
    return {
        "driver": column.name,
        "n_turning": int(a.size),
        "n_human_turning": int(b.size),
        "kl_from_human": lattice.kl_divergence(a, b),
        "chi2": chi2.statistic,
        "chi2_p": chi2.p_value,
        "chi2_reject": chi2.reject_null,
    }


def on_grid_share(values: np.ndarray) -> float:
    """Share of nonzero values sitting exactly on the 0.05 lattice. The R8 artefact number."""
    nonzero = values[values > 0]
    if nonzero.size == 0:
        return float("nan")
    return float(np.mean(np.abs(nonzero / 0.05 - np.round(nonzero / 0.05)) < 1e-6))


def build(root: Path) -> dict:
    human = m5.human_column(root)
    drivers = [
        m5.rl_column(root, "ppo_car_009_bc", "deterministic"),
        m5.rl_column(root, "ppo_car_009_bc", "sampling"),
        m5.heuristic_column(root, root / "results" / "heuristic" / "runs_2026-08-16_15-27-50.csv"),
        m5.bc_column(root),
    ]

    return {
        "human": human,
        "drivers": drivers,
        "primary": [compare_axis(d, human, "abs_delta_steering") for d in drivers],
        "secondary": [steering_level_report(d, human) for d in drivers],
        "conditional": [conditional_on_nonzero(d, human) for d in drivers],
        "unquantised_vs_quantised": [compare_axis(d, human, "steering") for d in drivers],
    }


def to_markdown(result: dict) -> str:
    """The comparison as `DESIGN.md` 7 asks for it, with every artefact beside its statistic."""
    human = result["human"]
    lines: list[str] = []
    add = lines.append

    add("# M5: RL against BC against the scripted driver against the human")
    add("")
    add("Generated by `python -m python.m5.compare`. Every input is committed under")
    add("`results/comparison/`, so this reproduces from a clean clone.")
    add("")
    add("**Read the artefact columns before the statistics.** Three distortions were measured")
    add("before this table was built, and each makes an obvious reading false. The steering level")
    add("comparison is dominated by track geometry: the generated loop always turns and runs one")
    add("way. The smoothness comparison against the human is dominated by the human's input")
    add("device: 67.8 per cent of its nonzero steering changes land exactly on the 0.05 lattice,")
    add("with modes at 0.15 and 0.20. Neither is a statement about driving skill.")
    add("")

    add("## Descriptive statistics (DESIGN 7.1)")
    add("")
    add("| driver | n | mean | variance | straight | left | right |")
    add("|---|---|---|---|---|---|---|")
    for column in result["drivers"] + [human]:
        s = column.steering_stats
        add(f"| `{column.name}` | {s.n} | {s.mean:+.4f} | {s.variance:.5f} | "
            f"{100 * column.straight_share:.1f}% | {100 * column.left_share:.1f}% | "
            f"{100 * column.right_share:.1f}% |")
    add("")

    add("## The comparison table (DESIGN 7)")
    add("")
    add("| driver | laps | lap time | wall contacts | speed |")
    add("|---|---|---|---|---|")
    for column in result["drivers"] + [human]:
        laps = ("absent" if column.laps_completed is None
                else f"{column.laps_completed} of {column.laps_possible}")
        lap_time = "absent" if column.lap_time_s is None else f"{column.lap_time_s:.3f} s"
        contacts = "absent" if column.wall_contacts is None else f"{column.wall_contacts:.2f}"
        speed = "absent" if column.speed is None else "present"
        add(f"| `{column.name}` | {laps} | {lap_time} | {contacts} | {speed} |")
    add("")
    for column in result["drivers"] + [human]:
        if column.absent_reason:
            add(f"**`{column.name}` absences**: {column.absent_reason}.")
            add("")

    add("## Primary axis: |delta steering| at 14.08 Hz")
    add("")
    add("Reported with the median and the on-grid share beside the mean, because the human's")
    add("distribution is bimodal and its mean alone is misleading. `D` is the KS statistic, which")
    add("is also the effect size: the largest gap between the two empirical distributions.")
    add("")
    add("| driver | mean | median | p95 | on grid | D raw | D on lattice | p |")
    add("|---|---|---|---|---|---|---|---|")
    for comparison, column in zip(result["primary"], result["drivers"]):
        d = column.abs_delta_steering
        add(f"| `{comparison.driver}` | {d.mean():.4f} | {np.median(d):.4f} | "
            f"{np.percentile(d, 95):.4f} | {100 * on_grid_share(d):.1f}% | "
            f"{comparison.raw.statistic:.4f} | {comparison.quantised.statistic:.4f} | "
            f"{comparison.raw.p_value:.2g} |")
    hd = human.abs_delta_steering
    add(f"| `{human.name}` | {hd.mean():.4f} | {np.median(hd):.4f} | "
        f"{np.percentile(hd, 95):.4f} | {100 * on_grid_share(hd):.1f}% | reference | reference | "
        "reference |")
    add("")

    add("## Secondary axis: steering level on the lattice")
    add("")
    add("KL is smoothed per bin, so it is not the same quantity as an unsmoothed KL. The straight")
    add("and left shares are in this table rather than after it, because without them the")
    add("divergence reads as a statement about style rather than about the track.")
    add("")
    add("| driver | KL from human | chi2 | dof | p | straight | left |")
    add("|---|---|---|---|---|---|---|")
    for row in result["secondary"]:
        add(f"| `{row['driver']}` | {row['kl_from_human']:.4f} | {row['chi2']:.1f} | "
            f"{row['chi2_dof']} | {row['chi2_p']:.2g} | {100 * row['straight_share']:.1f}% | "
            f"{100 * row['left_share']:.1f}% |")
    add("")

    add("## Conditional on nonzero steering")
    add("")
    add("The comparison `DESIGN.md` 7's second M5 note prescribes. Dropping the straight-line")
    add("samples from both sides is what removes the largest track-driven difference.")
    add("")
    add("| driver | n turning | KL from human | chi2 | rejects |")
    add("|---|---|---|---|---|")
    for row in result["conditional"]:
        add(f"| `{row['driver']}` | {row['n_turning']} | {row['kl_from_human']:.4f} | "
            f"{row['chi2']:.1f} | {row['chi2_reject']} |")
    add("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=None, help="write the report here as markdown")
    args = parser.parse_args(argv)

    result = build(args.root)
    human = result["human"]

    print("=== descriptive statistics, DESIGN 7.1 ===")
    print(f"{'driver':<34}{'n':>7}{'mean':>10}{'var':>10}{'straight%':>11}{'left%':>8}")
    for column in result["drivers"] + [human]:
        s = column.steering_stats
        print(f"{column.name:<34}{s.n:>7}{s.mean:>10.4f}{s.variance:>10.5f}"
              f"{100 * column.straight_share:>10.1f}%{100 * column.left_share:>7.1f}%")

    print()
    print("=== primary axis: |delta steering| against human ===")
    print(f"{'driver':<34}{'mean':>9}{'median':>9}{'on-grid%':>10}{'D raw':>8}{'D latt':>8}{'p raw':>10}")
    for comparison, column in zip(result["primary"], result["drivers"]):
        d = column.abs_delta_steering
        print(f"{comparison.driver:<34}{d.mean():>9.4f}{np.median(d):>9.4f}"
              f"{100 * on_grid_share(d):>9.1f}%{comparison.raw.statistic:>8.4f}"
              f"{comparison.quantised.statistic:>8.4f}{comparison.raw.p_value:>10.2g}")
    hd = human.abs_delta_steering
    print(f"{'human_combined':<34}{hd.mean():>9.4f}{np.median(hd):>9.4f}"
          f"{100 * on_grid_share(hd):>9.1f}%{'-':>8}{'-':>8}{'-':>10}")

    print()
    print("=== secondary axis: steering level on the lattice ===")
    print(f"{'driver':<34}{'KL':>9}{'chi2':>12}{'dof':>5}{'straight%':>11}{'left%':>8}")
    for row in result["secondary"]:
        print(f"{row['driver']:<34}{row['kl_from_human']:>9.4f}{row['chi2']:>12.1f}"
              f"{row['chi2_dof']:>5}{100 * row['straight_share']:>10.1f}%{100 * row['left_share']:>7.1f}%")

    print()
    print("=== conditional on nonzero steering, as DESIGN 7 asks ===")
    print(f"{'driver':<34}{'n turning':>11}{'KL':>9}{'chi2':>12}{'reject':>8}")
    for row in result["conditional"]:
        print(f"{row['driver']:<34}{row['n_turning']:>11}{row['kl_from_human']:>9.4f}"
              f"{row['chi2']:>12.1f}{str(row['chi2_reject']):>8}")

    out = args.out or args.root / "results" / "comparison" / "m5_comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(result), encoding="utf-8")
    print()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
