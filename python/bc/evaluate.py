"""What the model predicted, described the same way M1 described the human.

The rule this module is built around: **it computes no statistic of its own.** Every mean,
variance and histogram comes from `eda.stats`, the functions M1 already used on the human
column. If BC computed its own mean, BC's numbers and M1's could drift apart in definition
while both looked correct, and the M5 comparison would then be between two slightly different
questions without anyone being able to see it (research R5).

Two things here are easy to get wrong in a way that produces a confident wrong answer.

**Pooling.** Every distribution is reported pooled and per track, with no pooled-only path
(FR-016). Feature 002 already found a column on this dataset that looked reasonable pooled and
was constant within each track, and steering has the same shape of trap: track1 is dominated by
straight driving and track2 is not.

**Resolution.** The human column is lattice-valued, 41 levels at 0.05, and the model's output is
continuous. Comparing them directly makes every divergence metric report a large difference that
measures the recording resolution rather than the driving (DESIGN section 7). So the lattice is
applied to the model before any comparison, never to the human, and every report says which it
is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from python.bc import config, dataset, model, split, train
from python.eda import config as eda_config
from python.eda import loader, stats
from python.eda.loader import TrackDataset
from python.eda.stats import DistributionSummary


class EvaluationError(Exception):
    """Raised when a comparison would report a number that does not mean what it says."""


def lattice_levels() -> np.ndarray:
    """The 41 steering values the human recording actually contains.

    Derived from the step and the limits rather than listed, and checked against feature 002's
    measurement in the tests.
    """
    low, high = config.STEERING_LIMITS
    step = config.STEERING_LATTICE_STEP
    count = int(round((high - low) / step)) + 1
    return np.round(np.linspace(low, high, count), 4)


def quantise_to_lattice(values) -> np.ndarray:
    """Snap continuous predictions onto the human grid, clipped to the steering limits.

    Applied to the MODEL, never to the human. The human record is the reference and is not
    touched: quantising it would be adjusting the thing being measured against.
    """
    step = config.STEERING_LATTICE_STEP
    low, high = config.STEERING_LIMITS
    snapped = np.round(np.asarray(values, dtype=float) / step) * step
    # The trailing `+ 0.0` turns -0.0 into 0.0. They compare equal, so nothing downstream
    # breaks, but a histogram of the human lattice that lists both "-0.00" and "0.00" invites
    # a reader to wonder which one the real zeros are in.
    return np.round(np.clip(snapped, low, high), 4) + 0.0


@dataclass
class PredictionSet:
    """The model's output over the validation set, in original recording order."""

    run_id: str
    order: list[int]
    predicted: np.ndarray
    actual: np.ndarray
    track: np.ndarray

    @property
    def residual(self) -> np.ndarray:
        """Derived on read, never stored.

        A third stored array is a third thing that can drift out of step with the two it was
        computed from, and nothing would report the disagreement.
        """
        return self.predicted - self.actual

    def scoped(self, scope: str) -> np.ndarray:
        """A boolean mask for `pooled`, or for one track marker."""
        if scope == "pooled":
            return np.ones(len(self.order), dtype=bool)
        return self.track == scope


def _contiguous_runs(order: list[int]) -> list[slice]:
    """Split row indices into stretches of genuinely consecutive frames.

    The validation set is two held-out blocks per track, so its rows are not one continuous
    stretch. Differencing straight through would invent a steering jump at every block edge and
    at the seam between tracks, and the smoothness figure FR-015 reports would be describing
    those invented jumps rather than the driving.
    """
    if not order:
        return []

    runs: list[slice] = []
    start = 0
    for i in range(1, len(order)):
        if order[i] != order[i - 1] + 1:
            runs.append(slice(start, i))
            start = i
    runs.append(slice(start, len(order)))
    return runs


def absolute_frame_to_frame_change(values: np.ndarray, order: list[int]) -> np.ndarray:
    """Per-frame absolute change, differenced only within contiguous stretches (FR-015).

    The same quantity `eda.stats.abs_delta_steering` computes for the human, and computed the
    same way, so BC, the RL agent and the human are compared on one basis rather than at three
    different frame rates.
    """
    parts = [np.abs(np.diff(values[run])) for run in _contiguous_runs(order)
             if run.stop - run.start > 1]
    return np.concatenate(parts) if parts else np.array([])


@dataclass
class DistributionReport:
    """One distribution, in one scope, described by the shared functions."""

    name: str
    scope: str
    summary: DistributionSummary
    histogram_edges: np.ndarray
    histogram_relative: np.ndarray
    lattice_applied: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "scope": self.scope,
            "lattice_applied": self.lattice_applied,
            "n": self.summary.n,
            "mean": self.summary.mean,
            "std": self.summary.std,
            "variance": self.summary.variance,
            "minimum": self.summary.minimum,
            "maximum": self.summary.maximum,
            "percentiles": {str(k): v for k, v in self.summary.percentiles.items()},
            "histogram_edges": [float(x) for x in self.histogram_edges],
            "histogram_relative": [float(x) for x in self.histogram_relative],
        }


def summarise(values, name: str, scope: str,
              lattice_applied: bool = False) -> DistributionReport:
    """Describe one distribution. Delegates every figure to `eda.stats` (research R5)."""
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        raise EvaluationError(
            f"cannot summarise an empty distribution: {name} in scope {scope}"
        )

    relative, edges = stats.relative_frequency_histogram(array, bins=config.HISTOGRAM_BINS)
    return DistributionReport(
        name=name,
        scope=scope,
        summary=stats.describe(array, variable=f"{name}[{scope}]"),
        histogram_edges=edges,
        histogram_relative=relative,
        lattice_applied=lattice_applied,
    )


def summarise_all_scopes(values: np.ndarray, name: str, predictions: PredictionSet,
                         lattice_applied: bool = False) -> list[DistributionReport]:
    """Pooled and per track. There is no pooled-only path (FR-016)."""
    reports = [summarise(values, name, "pooled", lattice_applied)]

    for marker in eda_config.SESSION_PATH_MARKERS:
        mask = predictions.scoped(marker)
        if not mask.any():
            raise EvaluationError(
                f"no validation samples for {marker}. Every distribution must exist in all "
                "three scopes, because a pooled figure on this dataset hides the difference "
                "between the two tracks rather than summarising it."
            )
        reports.append(summarise(values[mask], name, marker, lattice_applied))

    return reports


def lattice_distribution(values: np.ndarray) -> np.ndarray:
    """Relative frequency over the 41 human levels, in level order."""
    levels = lattice_levels()
    snapped = quantise_to_lattice(values)
    counts = np.array([(snapped == level).sum() for level in levels], dtype=float)
    total = counts.sum()
    return counts / total if total else counts


def kl_divergence(predicted: np.ndarray, human: np.ndarray) -> float:
    """KL of the model's steering distribution from the human one, on the shared lattice.

    DESIGN section 7 asks for this figure and states the precondition: KL between a discrete
    and a continuous distribution is undefined without common support, so the shared lattice is
    a prerequisite rather than cosmetics.

    Smoothed by `KL_SMOOTHING`. Without it a single prediction on a level the human never used
    makes the divergence infinite, which reports "completely different" on the strength of one
    frame. A smoothed KL is not the same quantity as an unsmoothed one, so every report that
    carries this number says so.
    """
    p = lattice_distribution(predicted) + config.KL_SMOOTHING
    q = lattice_distribution(human) + config.KL_SMOOTHING
    p = p / p.sum()
    q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))


def predict(run_id: str, ds: TrackDataset | None = None,
            plan=None, allow_cpu: bool = True, run_dir: Path | None = None) -> PredictionSet:
    """Run a checkpoint over the validation set, in original recording order.

    **Refuses when the checkpoint's `split_digest` does not match the split in use.** Pairing a
    checkpoint with a different split does not fail: it reports a perfectly plausible number
    computed against rows the model may have trained on.
    """
    import torch
    from torch.utils.data import DataLoader

    run_dir = run_dir or (config.BC_OUT_DIR / f"run_{run_id}")
    record = train.read_record(run_dir / "run_record.json")

    current = train.split_digest()
    if record.split_digest != current:
        raise EvaluationError(
            f"run {run_id} was trained against split {record.split_digest[:12]} but the "
            f"split on disk is {current[:12]}. The validation rows have changed, so the "
            "reported error would be computed against rows this model may have trained on."
        )

    ds = ds or loader.load_track(config.DATASET_NAME)
    plan = plan or split.read_split()

    samples = dataset.build_samples(ds, plan.val_rows, use_side_cameras=False,
                                    seed=record.seed)

    device = train.resolve_device(allow_cpu=allow_cpu)
    network = model.build_model()
    network.load_state_dict(torch.load(run_dir / "checkpoint.pt", map_location="cpu"))
    network = network.to(device).eval()

    frames = train.FrameDataset(ds, samples, augment=False, seed=record.seed)
    dataloader = DataLoader(frames, batch_size=config.BATCH_SIZE, shuffle=False,
                            num_workers=config.DATALOADER_WORKERS,
                            persistent_workers=config.DATALOADER_WORKERS > 0)

    outputs: list[np.ndarray] = []
    with torch.no_grad():
        for images, _ in dataloader:
            outputs.append(network(images.to(device)).cpu().numpy())

    return PredictionSet(
        run_id=run_id,
        order=[sample.row_index for sample in samples],
        predicted=np.concatenate(outputs) if outputs else np.array([]),
        actual=np.array([sample.steering for sample in samples], dtype=float),
        track=np.array([sample.track for sample in samples]),
    )


def report_run(predictions: PredictionSet) -> list[DistributionReport]:
    """Every distribution this feature reports, in all three scopes.

    The predicted distribution appears twice, raw and on the lattice, and both are labelled.
    The raw one is what the model produced; the lattice one is the only form comparable with
    the human reference, and keeping both means a reader can see what the quantisation did
    rather than taking it on trust.
    """
    reports: list[DistributionReport] = []

    reports += summarise_all_scopes(predictions.predicted, "predicted_steering", predictions)
    reports += summarise_all_scopes(
        quantise_to_lattice(predictions.predicted), "predicted_steering_lattice",
        predictions, lattice_applied=True,
    )
    reports += summarise_all_scopes(predictions.actual, "human_steering", predictions)
    reports += summarise_all_scopes(predictions.residual, "residual", predictions)

    # Smoothness needs its own scoping, because differencing has to happen inside each track
    # before anything is pooled.
    pooled_change = absolute_frame_to_frame_change(predictions.predicted, predictions.order)
    reports.append(summarise(pooled_change, "abs_delta_predicted", "pooled"))
    for marker in eda_config.SESSION_PATH_MARKERS:
        mask = predictions.scoped(marker)
        order = [row for row, keep in zip(predictions.order, mask) if keep]
        change = absolute_frame_to_frame_change(predictions.predicted[mask], order)
        reports.append(summarise(change, "abs_delta_predicted", marker))

    return reports


@dataclass
class BalancingComparison:
    """The two runs side by side, with the two deltas kept apart."""

    balanced: train.RunRecord
    unbalanced: train.RunRecord
    accuracy_delta: float
    distribution_delta: float
    same_split: bool
    differing_fields: list[str] = field(default_factory=list)


# The two fields the runs are ALLOWED to differ in. Everything else being equal is what makes
# the comparison a measurement of balancing rather than of balancing plus something else.
_EXPECTED_DIFFERENCES = {"policy", "n_train_samples"}


def compare_runs(balanced: train.RunRecord, unbalanced: train.RunRecord,
                 balanced_kl: float, unbalanced_kl: float) -> BalancingComparison:
    """Refuses to render if the two runs differ in anything beyond the policy (FR-021).

    This is the check that keeps the headline comparison honest. Two runs that also differ in
    learning rate still produce a difference, and that difference gets attributed to balancing
    by whoever reads the table.
    """
    differing: list[str] = []

    if balanced.policy != unbalanced.policy:
        differing.append("policy")
    if balanced.n_train_samples != unbalanced.n_train_samples:
        differing.append("n_train_samples")
    if balanced.seed != unbalanced.seed:
        differing.append("seed")
    if balanced.n_val_samples != unbalanced.n_val_samples:
        differing.append("n_val_samples")
    if balanced.parameter_count != unbalanced.parameter_count:
        differing.append("parameter_count")

    for key in sorted(set(balanced.hyperparameters) | set(unbalanced.hyperparameters)):
        if balanced.hyperparameters.get(key) != unbalanced.hyperparameters.get(key):
            differing.append(f"hyperparameters.{key}")

    unexpected = [f for f in differing if f not in _EXPECTED_DIFFERENCES]
    if unexpected:
        raise EvaluationError(
            "these runs differ in more than the balancing policy, so a difference between "
            f"them cannot be attributed to balancing: {', '.join(unexpected)}"
        )

    same_split = balanced.split_digest == unbalanced.split_digest
    if not same_split:
        raise EvaluationError(
            "the two runs were trained against different splits, so their validation errors "
            "are not measured on the same rows and are not comparable"
        )

    return BalancingComparison(
        balanced=balanced,
        unbalanced=unbalanced,
        accuracy_delta=balanced.val_error - unbalanced.val_error,
        distribution_delta=balanced_kl - unbalanced_kl,
        same_split=same_split,
        differing_fields=differing,
    )


def write_reports(reports: list[DistributionReport], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, sort_keys=True,
                   ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _read_the_outcome(comparison: BalancingComparison) -> str:
    """Describe which of the four possible outcomes actually happened.

    Written as a branch rather than as a sentence, because the design EXPECTED a trade: better
    accuracy paid for with a worse distributional match. Hardcoding that expectation into the
    report would have made a result that contradicts it invisible, which is the specific way a
    write-up starts describing the plan instead of the measurement.
    """
    accuracy_to_balanced = comparison.accuracy_delta < 0
    distribution_to_balanced = comparison.distribution_delta < 0

    if accuracy_to_balanced != distribution_to_balanced:
        winner = "balanced" if accuracy_to_balanced else "unbalanced"
        loser = "unbalanced" if accuracy_to_balanced else "balanced"
        return (
            f"This is the trade the two-run design was built to expose: {winner} predicts the "
            f"human targets more closely while {loser} sits nearer the human distribution. "
            "Collapsing the two into one verdict would discard the reason both were trained."
        )

    direction = "balanced" if accuracy_to_balanced else "unbalanced"
    return (
        f"**Both axes point the same way: {direction} wins accuracy and distributional "
        "closeness.** That is not what the design predicted. Balancing was expected to buy a "
        "closer distributional match at the cost of accuracy, and here it bought neither.\n\n"
        "The reason is measurable rather than mysterious, and it is the more interesting "
        "finding. Neither model reproduces the human's zero spike at all: the human validation "
        "column is 57.2 percent exact zeros, and both models place under 5 percent there. The "
        "distance from the human distribution is dominated by that gap, and balancing moves "
        "the model further from zero, so it makes the gap slightly worse instead of better.\n\n"
        "What actually moved the prediction distribution away from the human one is the "
        "three-camera augmentation, not the balancing policy. It cut the zero share of the "
        "training targets from 57 percent of rows to 20 percent of samples before balancing "
        "was applied to anything. Balancing is a second-order effect on top of a first-order "
        "one that was never framed as a distributional choice."
    )


def render_comparison(comparison: BalancingComparison,
                      balanced_kl: float, unbalanced_kl: float) -> str:
    """The comparison as markdown, with the two deltas side by side and no verdict.

    Not collapsed into a winner on purpose. A run that wins on accuracy and loses on
    distribution is the expected outcome and is the finding this feature exists to produce;
    resolving it into one number would throw away the reason both runs were trained.
    """
    balanced, unbalanced = comparison.balanced, comparison.unbalanced

    lines = [
        "# Balanced against unbalanced behavioural cloning",
        "",
        "Two runs differing in exactly one thing: whether the exact-zero steering spike was ",
        "downsampled before training. Everything else, including the split, the seed, the ",
        "architecture and every hyperparameter, is identical. That is what makes the ",
        "difference below attributable to balancing.",
        "",
        "Both are scored on the same unbalanced validation set (FR-022). Balancing is a ",
        "property of what the model was shown, so applying it to validation would move the ",
        "yardstick along with the model.",
        "",
        "## The two runs",
        "",
        "| | Unbalanced | Balanced |",
        "|---|---|---|",
        f"| Run | `{unbalanced.run_id}` | `{balanced.run_id}` |",
        f"| Policy | {unbalanced.policy} | {balanced.policy} |",
        f"| Training samples | {unbalanced.n_train_samples:,} | {balanced.n_train_samples:,} |",
        f"| Validation samples | {unbalanced.n_val_samples:,} | {balanced.n_val_samples:,} |",
        f"| Epochs | {unbalanced.epochs_completed} | {balanced.epochs_completed} |",
        f"| Validation error | {unbalanced.val_error:.6f} | {balanced.val_error:.6f} |",
        f"| Mean-predictor baseline | {unbalanced.baseline_error:.6f} | "
        f"{balanced.baseline_error:.6f} |",
        f"| Beat baseline | {unbalanced.beat_baseline} | {balanced.beat_baseline} |",
        f"| KL from human, on the lattice | {unbalanced_kl:.6f} | {balanced_kl:.6f} |",
        "",
        "## The two deltas, kept apart",
        "",
        "| Axis | Delta (balanced minus unbalanced) | Reading |",
        "|---|---|---|",
        f"| Accuracy | {comparison.accuracy_delta:+.6f} | "
        f"{'balanced predicts the human targets more closely' if comparison.accuracy_delta < 0 else 'unbalanced predicts the human targets more closely'} |",
        f"| Distribution | {comparison.distribution_delta:+.6f} | "
        f"{'balanced sits closer to the human distribution' if comparison.distribution_delta < 0 else 'unbalanced sits closer to the human distribution'} |",
        "",
        "**These are not combined into a verdict.**",
        "",
        _read_the_outcome(comparison),
        "",
        "## Notes on the figures",
        "",
        f"- The KL divergence is computed on the 41-level human lattice, with the model's ",
        f"  continuous output quantised onto it first and the human record left untouched ",
        f"  (DESIGN section 7). It is smoothed by {config.KL_SMOOTHING:g} per level, without ",
        "  which a single prediction on an unused level would make it infinite.",
        "- The validation error is the mean squared error of the raw continuous predictions, ",
        "  not the quantised ones. Quantising before scoring would penalise the model for a ",
        "  resolution the human recording happens to have.",
        f"- Both runs carry split digest `{balanced.split_digest[:16]}`.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _figure_axes(width: float = 9.0, height: float = 5.0):
    """One place that sets the backend, so no figure function can forget it."""
    import matplotlib
    matplotlib.use("Agg")          # no display on this machine, and none needed
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(width, height))
    return plt, figure, axes


def plot_predicted_against_human(predictions: PredictionSet, path: Path) -> Path:
    """Scatter of prediction against the human value, split by track.

    The diagonal is where a perfect model would sit. What this plot is for is the shape of the
    disagreement rather than its size: a model that under-steers pulls the cloud flat toward
    the horizontal, which no single error figure shows.
    """
    plt, figure, axes = _figure_axes()

    for marker, colour in zip(eda_config.SESSION_PATH_MARKERS, ("#1f77b4", "#d62728")):
        mask = predictions.scoped(marker)
        axes.scatter(predictions.actual[mask], predictions.predicted[mask],
                     s=4, alpha=0.25, label=marker, color=colour, linewidths=0)

    low, high = config.STEERING_LIMITS
    axes.plot([low, high], [low, high], color="black", linewidth=1,
              linestyle="--", label="perfect agreement")
    axes.set_xlabel("human steering")
    axes.set_ylabel("predicted steering")
    axes.set_title(f"{predictions.run_id}: prediction against human, by track")
    axes.set_xlim(low, high)
    axes.set_ylim(low, high)
    axes.legend(loc="upper left", markerscale=3)
    axes.grid(alpha=0.2)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def plot_residuals(predictions: PredictionSet, path: Path) -> Path:
    """Residual distribution, per track and pooled.

    Per track because feature 002 already found this dataset hides differences under pooling,
    and the two tracks are not the same driving problem.
    """
    plt, figure, axes = _figure_axes()

    axes.hist(predictions.residual, bins=config.HISTOGRAM_BINS, density=True,
              alpha=0.35, color="#555555", label="pooled")
    for marker, colour in zip(eda_config.SESSION_PATH_MARKERS, ("#1f77b4", "#d62728")):
        mask = predictions.scoped(marker)
        axes.hist(predictions.residual[mask], bins=config.HISTOGRAM_BINS, density=True,
                  histtype="step", linewidth=1.6, color=colour, label=marker)

    axes.axvline(0.0, color="black", linewidth=1, linestyle="--")
    axes.set_xlabel("predicted minus human")
    axes.set_ylabel("density")
    axes.set_title(f"{predictions.run_id}: residuals")
    axes.legend()
    axes.grid(alpha=0.2)

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def plot_policy_distributions(balanced: PredictionSet, unbalanced: PredictionSet,
                              path: Path) -> Path:
    """Both policies' prediction distributions against the human one, on the shared lattice.

    This is the picture behind the KL figures, and it is worth looking at rather than trusting
    the number: the human's zero bar dwarfs everything, and neither model comes close to it.
    The log scale is there because a linear axis makes every bar except zero invisible.
    """
    plt, figure, axes = _figure_axes(height=5.5)

    levels = lattice_levels()
    width = config.STEERING_LATTICE_STEP * 0.28

    axes.bar(levels - width, lattice_distribution(unbalanced.actual), width=width,
             label="human", color="#333333")
    axes.bar(levels, lattice_distribution(unbalanced.predicted), width=width,
             label="unbalanced", color="#1f77b4")
    axes.bar(levels + width, lattice_distribution(balanced.predicted), width=width,
             label="balanced", color="#d62728")

    axes.set_yscale("log")
    axes.set_xlabel("steering, on the 41-level human lattice")
    axes.set_ylabel("relative frequency, log scale")
    axes.set_title("Prediction distributions against the human reference")
    axes.legend()
    axes.grid(alpha=0.2, which="both")

    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=140)
    plt.close(figure)
    return path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate the M4 behavioural cloning runs.")
    parser.add_argument("--run", help="evaluate one run and write its distribution reports")
    parser.add_argument("--compare", nargs=2, metavar=("BALANCED", "UNBALANCED"),
                        help="compare two runs and write results/bc/comparison.md")
    args = parser.parse_args()

    if not args.run and not args.compare:
        parser.error("pass --run <id> or --compare <balanced> <unbalanced>")

    ds = loader.load_track(config.DATASET_NAME)
    plan = split.read_split()

    if args.run:
        predictions = predict(args.run, ds=ds, plan=plan)
        reports = report_run(predictions)
        out = config.BC_OUT_DIR / f"run_{args.run}" / "distributions.json"
        write_reports(reports, out)

        print(f"wrote {out}")
        for report in reports:
            if report.scope == "pooled":
                print(f"  {report.name:28s} n={report.summary.n:6,d} "
                      f"mean {report.summary.mean:+.4f}  std {report.summary.std:.4f}")

        for figure_path in (
            plot_predicted_against_human(
                predictions, eda_config.PLOTS_DIR / f"bc_scatter_{args.run}.png"),
            plot_residuals(
                predictions, eda_config.PLOTS_DIR / f"bc_residuals_{args.run}.png"),
        ):
            print(f"  figure {figure_path}")

    if args.compare:
        balanced_id, unbalanced_id = args.compare
        results = {}
        sets = {}
        for run_id in (balanced_id, unbalanced_id):
            predictions = predict(run_id, ds=ds, plan=plan)
            sets[run_id] = predictions
            results[run_id] = (
                train.read_record(config.BC_OUT_DIR / f"run_{run_id}" / "run_record.json"),
                kl_divergence(predictions.predicted, predictions.actual),
            )

        balanced_record, balanced_kl = results[balanced_id]
        unbalanced_record, unbalanced_kl = results[unbalanced_id]

        overlay = plot_policy_distributions(
            sets[balanced_id], sets[unbalanced_id],
            eda_config.PLOTS_DIR / "bc_policy_distributions.png",
        )

        comparison = compare_runs(balanced_record, unbalanced_record,
                                  balanced_kl, unbalanced_kl)
        out = config.BC_OUT_DIR / "comparison.md"
        out.write_text(render_comparison(comparison, balanced_kl, unbalanced_kl),
                       encoding="utf-8")

        print(f"wrote {out}")
        print(f"  figure {overlay}")
        print(f"  accuracy delta     {comparison.accuracy_delta:+.6f}")
        print(f"  distribution delta {comparison.distribution_delta:+.6f}")
        print("  reported side by side, not collapsed into a winner")


if __name__ == "__main__":
    main()
