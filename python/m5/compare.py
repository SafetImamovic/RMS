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


def agreement(root: Path) -> list[dict]:
    """Seeds 7 and 13, reported as an agreement line rather than as columns.

    **Three seeds of one training configuration are one driver, not three.** Giving each its own
    column in `DESIGN.md` 7's table would say the project compared three learned drivers against a
    human, which it did not. What the extra seeds establish is that the named column is not a lucky
    draw, so they belong beside it as a spread and nowhere else.
    """
    rows: list[dict] = []
    for run_id in ("ppo_car_009_bc_s7", "ppo_car_009_bc_s13"):
        column = m5.rl_column(root, run_id, "deterministic")
        rows.append(
            {
                "driver": column.name,
                "n": int(column.steering.size),
                "variance": column.steering_stats.variance,
                "delta_mean": float(column.abs_delta_steering.mean()),
                "delta_median": float(np.median(column.abs_delta_steering)),
                "laps_completed": column.laps_completed,
                "laps_possible": column.laps_possible,
                "lap_time_s": column.lap_time_s,
                "wall_contacts": column.wall_contacts,
            }
        )
    return rows


# The coarse bins the relative-frequency histogram is reported on. Wider than the 0.05 lattice
# because a 41-row table is a data file rather than a reading, and the full-resolution version is
# written to `steering_histogram.csv` for the figures to consume.
HISTOGRAM_EDGES = np.array([-1.0, -0.5, -0.3, -0.15, -0.05, -0.0125, 0.0125, 0.05, 0.15, 0.3, 0.5, 1.0])


def relative_histogram(values: np.ndarray, edges: np.ndarray = HISTOGRAM_EDGES) -> np.ndarray:
    """Relative frequencies, as `DESIGN.md` 7.1 asks. Shares, never counts: the columns differ by
    a factor of six in sample size, so counts would compare dataset length rather than behaviour."""
    counts, _ = np.histogram(values, bins=edges)
    total = counts.sum()
    return counts / total if total else counts.astype(float)


def lattice_histogram_frame(result: dict):
    """The full 0.05-resolution relative-frequency histogram, one column per driver.

    Written out rather than printed, because it is the input the Phase 5 figures read: a figure
    drawn from a committed table changes when the table changes, which is what SC-005 asks for.
    """
    import pandas as pd

    support = lattice_support()
    frame = pd.DataFrame({"steering": support})
    for column in result["drivers"] + [result["human"]]:
        counts = counts_on_lattice(column.steering, support)
        frame[column.name] = counts / counts.sum()
    return frame


def build(root: Path) -> dict:
    human = m5.human_column(root)
    drivers = [
        m5.rl_column(root, "ppo_car_009_bc", "deterministic"),
        m5.rl_column(root, "ppo_car_009_bc", "sampling"),
        # No explicit runs path. Passing the gitignored `results/heuristic/runs_*.csv` here
        # overrode the committed export and blanked three cells in a clean clone, which is what
        # running the recipe rather than reading it found (T033).
        m5.heuristic_column(root),
        m5.bc_column(root),
    ]

    return {
        "human": human,
        "drivers": drivers,
        "primary": [compare_axis(d, human, "abs_delta_steering") for d in drivers],
        "secondary": [steering_level_report(d, human) for d in drivers],
        "conditional": [conditional_on_nonzero(d, human) for d in drivers],
        "unquantised_vs_quantised": [compare_axis(d, human, "steering") for d in drivers],
        "agreement": agreement(root),
    }


def orderings(result: dict) -> dict:
    """The three rankings the result is read off, computed rather than typed.

    **Computed because a hand-written conclusion goes stale silently.** If a rerun changed which
    driver leads, a sentence naming the old winner would still read as a finding. These come from
    the same objects the tables are built from, so the prose and the numbers cannot disagree.
    """
    primary = sorted(result["primary"], key=lambda c: c.quantised.statistic)
    raw = sorted(result["primary"], key=lambda c: c.raw.statistic)
    secondary = sorted(result["secondary"], key=lambda row: row["kl_from_human"])
    conditional = sorted(result["conditional"], key=lambda row: row["kl_from_human"])
    return {
        "primary": [(c.driver, c.quantised.statistic) for c in primary],
        "primary_raw": [(c.driver, c.raw.statistic) for c in raw],
        "secondary": [(row["driver"], row["kl_from_human"]) for row in secondary],
        "conditional": [(row["driver"], row["kl_from_human"]) for row in conditional],
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
    add("Three variables, each with n, mean, variance, minimum and maximum, and a")
    add("relative-frequency histogram below. Shares rather than counts throughout, because the")
    add("columns differ by a factor of six in sample size.")
    add("")
    add("### Steering")
    add("")
    add("| driver | n | mean | variance | min | max | straight | left | right |")
    add("|---|---|---|---|---|---|---|---|---|")
    for column in result["drivers"] + [human]:
        d = column.steering_stats
        add(f"| `{column.name}` | {d.n} | {d.mean:+.4f} | {d.variance:.5f} | "
            f"{d.minimum:+.3f} | {d.maximum:+.3f} | "
            f"{100 * column.straight_share:.1f}% | {100 * column.left_share:.1f}% | "
            f"{100 * column.right_share:.1f}% |")
    add("")

    add("### Speed")
    add("")
    add("**The units are not shared and the columns are not comparable to each other.** The Unity")
    add("drivers report the simulator's own rigidbody speed; the human column is the recorded")
    add("speed of a different simulator in its own units. Each is reported so its spread within")
    add("its own driver can be read, and no cross-driver speed statistic is computed anywhere in")
    add("this feature.")
    add("")
    add("| driver | n | mean | variance | min | max |")
    add("|---|---|---|---|---|---|")
    for column in result["drivers"] + [human]:
        d = column.speed_stats
        if d is None:
            add(f"| `{column.name}` | absent | absent | absent | absent | absent |")
            continue
        add(f"| `{column.name}` | {d.n} | {d.mean:.4f} | {d.variance:.5f} | "
            f"{d.minimum:.3f} | {d.maximum:.3f} |")
    add("")

    add("### |delta steering| at 14.08 Hz")
    add("")
    add("| driver | n | mean | variance | min | max |")
    add("|---|---|---|---|---|---|")
    for column in result["drivers"] + [human]:
        d = column.delta_stats
        add(f"| `{column.name}` | {d.n} | {d.mean:.4f} | {d.variance:.5f} | "
            f"{d.minimum:.3f} | {d.maximum:.3f} |")
    add("")

    add("### Relative-frequency histogram of steering")
    add("")
    add("Coarse bins for reading. The full 0.05-resolution version, which the figures are drawn")
    add("from, is `results/comparison/steering_histogram.csv`.")
    add("")
    edges = HISTOGRAM_EDGES
    labels = [f"{edges[i]:+.3g} to {edges[i + 1]:+.3g}" for i in range(len(edges) - 1)]
    every = result["drivers"] + [human]
    add("| bin | " + " | ".join(f"`{c.name}`" for c in every) + " |")
    add("|---" * (len(every) + 1) + "|")
    shares = [relative_histogram(c.steering) for c in every]
    for i, label in enumerate(labels):
        add(f"| {label} | " + " | ".join(f"{100 * sh[i]:.1f}%" for sh in shares) + " |")
    add("")

    add("## The comparison table (DESIGN 7)")
    add("")
    add("**The run length differs between drivers and the table says so in its own columns.** The")
    add("RL sweeps run three laps per attempt and the scripted sweep runs one, so the run record's")
    add("`lap_time_s` is not one quantity. Reading those two numbers side by side would say the")
    add("scripted driver is 2.6 times faster when it is in fact slower per lap. Seconds per lap is")
    add("the comparable figure and it is the one to read.")
    add("")
    add("| driver | runs completed | laps per run | run time | **seconds per lap** | wall contacts"
        " | speed |")
    add("|---|---|---|---|---|---|---|")
    for column in result["drivers"] + [human]:
        laps = ("absent" if column.laps_completed is None
                else f"{column.laps_completed} of {column.laps_possible}")
        per_run = "absent" if column.laps_completed is None else str(column.laps_per_run)
        lap_time = "absent" if column.lap_time_s is None else f"{column.lap_time_s:.3f} s"
        per_lap = ("absent" if column.seconds_per_lap is None
                   else f"**{column.seconds_per_lap:.3f} s**")
        contacts = "absent" if column.wall_contacts is None else f"{column.wall_contacts:.2f}"
        speed = "absent" if column.speed is None else "present"
        add(f"| `{column.name}` | {laps} | {per_run} | {lap_time} | {per_lap} | {contacts} | "
            f"{speed} |")
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

    add("## Agreement across training seeds")
    add("")
    add("**Not columns.** Seeds 7 and 13 are the same training configuration as the named column,")
    add("differing only in `--seed`. Three seeds of one configuration are one driver, and giving")
    add("each a column would claim the project compared three learned drivers against a human.")
    add("What they establish is that the named column is not a lucky draw.")
    add("")
    add("| seed run | n | variance | mean abs delta | median abs delta | laps | lap time | contacts |")
    add("|---|---|---|---|---|---|---|---|")
    named = result["drivers"][0]
    add(f"| `{named.name}` (named) | {named.steering.size} | "
        f"{named.steering_stats.variance:.5f} | {named.abs_delta_steering.mean():.4f} | "
        f"{np.median(named.abs_delta_steering):.4f} | "
        f"{named.laps_completed} of {named.laps_possible} | {named.lap_time_s:.3f} s | "
        f"{named.wall_contacts:.2f} |")
    for row in result["agreement"]:
        lap_time = "absent" if row["lap_time_s"] is None else f"{row['lap_time_s']:.3f} s"
        contacts = "absent" if row["wall_contacts"] is None else f"{row['wall_contacts']:.2f}"
        add(f"| `{row['driver']}` | {row['n']} | {row['variance']:.5f} | "
            f"{row['delta_mean']:.4f} | {row['delta_median']:.4f} | "
            f"{row['laps_completed']} of {row['laps_possible']} | {lap_time} | {contacts} |")
    add("")

    add("## Figures")
    add("")
    add("All three are drawn by `python -m python.m5.plots` from these same committed inputs, so a")
    add("changed input changes the figure and no figure can drift away from this table.")
    add("")
    add("| figure | what it shows |")
    add("|---|---|")
    add("| `results/plots/m5_delta_steering.png` | the primary axis. Left: the raw distributions. "
        "Right: the cumulative curves after every driver is snapped to the human lattice, where "
        "the KS statistic is the largest vertical gap from the human curve and is readable off "
        "the drawing |")
    add("| `results/plots/m5_steering_lattice.png` | the secondary axis, with the near-zero and "
        "left-turn shares in their own panel rather than in a caption |")
    add("| `results/plots/m5_summary.png` | the defence figure: completion first, then the two "
        "resemblance measures, which disagree |")
    add("")

    add("## Model taxonomy, in the lecture's terminology")
    add("")
    add("`DESIGN.md` 7.1 lists six terms for the defence. Each is stated here with the thing in")
    add("this project that makes it true, because a taxonomy recited without its evidence is not a")
    add("classification. **Two of the six needed qualifying once the model was actually built.**")
    add("")
    add("| term | what makes it true here |")
    add("|---|---|")
    add("| **stochastic** | the start pose is randomised per episode, and the track itself is "
        "generated from a seed. **Qualified:** the PPO policy is stochastic in training and during "
        "the sampling column, but the named column is `deterministic` inference, where the policy "
        "returns the distribution mean. That column is stochastic through its environment only, "
        "and the two columns differ by 0.11 in mean abs delta steering because of it |")
    add("| **continuous state** | the observation is 19 continuous floats: 13 ray distances "
        "over a 180 degree fan, plus the six self-state values of `DESIGN.md` 4.3. Nothing is "
        "one-hot and nothing is bucketed |")
    add("| **discrete time** | the Unity physics step is fixed at 0.02 s, and `DecisionPeriod = 4` "
        "means the agent acts every fourth step, so decisions land at 12.5 Hz. The comparison "
        "resamples to the human's 14.08 Hz, which is a different discrete clock again |")
    add("| **agent-based** | one agent holds its own observation, reward and episode, and the "
        "scene's behaviour is the consequence of that agent acting rather than of a system-level "
        "equation |")
    add("| **time invariant** | the dynamics, the reward function and the policy do not depend on "
        "wall-clock or on step index. **Qualified:** the episode has a 6,000-step cap, so "
        "*termination* is a function of elapsed steps even though nothing else is. The cap is a "
        "harness, not a dynamic |")
    add("| **non-anticipatory** | the observation contains only the present ray cast and the "
        "present kinematics. No future checkpoint, no lookahead, no replay of what is about to "
        "happen |")
    add("")

    order = orderings(result)
    lead, lead_d = order["primary"][0]
    second, second_d = order["primary"][1]
    cond_lead, cond_kl = order["conditional"][0]

    add("## The result")
    add("")
    add(f"**On the primary axis the closest driver to the human is `{lead}`**, at KS "
        f"D = {lead_d:.4f} against the next driver's {second_d:.4f}, a margin of "
        f"{second_d - lead_d:.4f}. Full ordering, closest first:")
    add("")
    add("| rank | driver | D on lattice | D raw |")
    add("|---|---|---|---|")
    raw_by_driver = {name: value for name, value in order["primary_raw"]}
    for rank, (name, value) in enumerate(order["primary"], start=1):
        add(f"| {rank} | `{name}` | {value:.4f} | {raw_by_driver[name]:.4f} |")
    add("")
    add("**The ordering does not survive the secondary axis, and that is the finding rather than a "
        "defect.** On steering level given nonzero steering the ordering is:")
    add("")
    add("| rank | driver | KL, turning only |")
    add("|---|---|---|")
    for rank, (name, value) in enumerate(order["conditional"], start=1):
        add(f"| {rank} | `{name}` | {value:.4f} |")
    add("")
    if cond_lead != lead:
        add(f"So `{lead}` leads on smoothness and `{cond_lead}` leads on steering distribution "
            f"(KL {cond_kl:.4f}). The two are the same policy under two inference modes. **Noise "
            "makes a policy's distribution more human and its motion less so**: the sampling mode "
            "draws from the action distribution instead of taking its mean, which spreads the "
            "steering levels toward the human's spread while raising the mean step change from "
            "0.0413 to 0.1552, past the human's own 0.1112. A single answer to \"which driver is "
            "most human-like\" would have to suppress one of these two measurements.")
    else:
        add(f"`{lead}` leads on both axes.")
    add("")
    rl = result["drivers"][0]
    scripted = result["drivers"][2]
    add("**Execution, which `DESIGN.md` 7 puts first.** The learned policy completes "
        f"{rl.laps_completed} of {rl.laps_possible} held-out runs at {rl.laps_per_run} laps each "
        "with zero wall contacts, and two further training seeds do the same. The scripted driver "
        f"completes {scripted.laps_completed} of {scripted.laps_possible} single-lap runs, also "
        "with zero contacts.")
    add("")
    add(f"On seconds per lap the learned policy is **faster**: {rl.seconds_per_lap:.3f} s against "
        f"the scripted driver's {scripted.seconds_per_lap:.3f} s, a margin of "
        f"{scripted.seconds_per_lap - rl.seconds_per_lap:.3f} s. **That margin is not a claim that "
        "the learned policy drives better.** The two sweeps ran at different `timeScale` values "
        "and over different seed sets, and lap time was never a success criterion for either. It "
        "is reported because the table has the column, and it is bounded by that caveat because "
        "the comparison behind it was not designed. The BC model does not drive at all.")
    add("")

    add("## What this comparison cannot say")
    add("")
    add("Four limits, each of them a property of the inputs rather than of the method. Every one "
        "was measured before the comparison was built, not discovered while writing it up.")
    add("")
    add("- **Nothing about BC's driving.** The model was trained on camera images from a different "
        "simulator and predicts steering for frames a human already drove. It has no lap, no lap "
        "time, no wall contact and no speed, and its steering series is an open-loop prediction "
        "rather than a trajectory. Its column answers \"does it predict the human's next steering "
        "value\", which is a different question from the one the other three columns answer.")
    add("- **Little about steering level that is not track geometry.** The generated loop always "
        "turns and is driven one way, so the drivers steer left on 76 to 88 per cent of steps "
        "against the human's 23.5, and hold near-zero steering on 1 to 3 per cent against the "
        "human's 58.6. The chi-square figures above 20,000 are mostly that. The conditional "
        "comparison exists to see past it and it shrinks every divergence, which is the "
        "measurement of how much of the marginal was topology.")
    add("- **Nothing about speed across drivers.** The Unity columns are this simulator's rigidbody "
        "speed and the human column is another simulator's recorded speed in its own units. Their "
        "variances differ by a factor of eight and that is a unit mismatch, not a driving style. "
        "No cross-driver speed statistic is computed anywhere in this feature.")
    add("- **Nothing from the p-values.** Every test here rejects, on samples of 5,576 to 32,443, "
        "where a KS test rejects almost any null. The effect sizes carry the whole result and the "
        "p-values are reported because `DESIGN.md` 7.1 asks for them.")
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

    print()
    print("=== agreement across training seeds, not columns ===")
    print(f"{'seed run':<38}{'var':>10}{'mean|d|':>10}{'laps':>8}{'lap s':>10}")
    for row in result["agreement"]:
        lap_time = "-" if row["lap_time_s"] is None else f"{row['lap_time_s']:.3f}"
        print(f"{row['driver']:<38}{row['variance']:>10.5f}{row['delta_mean']:>10.4f}"
              f"{str(row['laps_completed']) + '/' + str(row['laps_possible']):>8}{lap_time:>10}")

    out = args.out or args.root / "results" / "comparison" / "m5_comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(result), encoding="utf-8")
    print()
    print(f"wrote {out}")

    histogram = out.parent / "steering_histogram.csv"
    lattice_histogram_frame(result).to_csv(histogram, index=False, float_format="%.8f")
    print(f"wrote {histogram}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
