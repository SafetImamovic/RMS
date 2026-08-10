"""The training loop, and the record that makes a run mean something afterwards.

Two things here are load-bearing beyond "the model learns".

**A checkpoint is never stored alone.** Every run writes a `RunRecord` beside its weights,
carrying the seed, the hyperparameters, the device actually used, the sample counts and both
error figures. SC-008 is the requirement, and the reason behind it is that a `.pt` file on its
own is unfalsifiable: a reader cannot tell what produced the number in the report, and neither
can the person who ran it, a month later.

**The mean predictor is computed every time** (FR-011). A model that cannot beat "always guess
the training mean" has learned nothing useful, and on this dataset that is a live possibility
rather than a formality: near-zero steering dominates, so constant zero is a strong strategy.
The record says `beat_baseline: false` when it happens, and that is reported as a result rather
than treated as a failed run (SC-003).

The device is resolved rather than assumed. FR-009 exists because a silent CPU epoch on 67,000
images looks exactly like progress until it is still running an hour later.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset

from python.bc import config, dataset, model, split
from python.bc.dataset import BalancingPolicy, SampleSpec
from python.eda import loader
from python.eda.loader import TrackDataset


class TrainError(Exception):
    """Raised when a run cannot proceed honestly. Always says what to do about it."""


def _jsonable(value):
    """Replace non-finite floats with null, recursively.

    `json.dumps` writes a bare `NaN` by default, which Python reads back happily and every
    strict JSON parser rejects. A run record is an artefact other tools read, so it has to be
    real JSON. A run that stopped before completing an epoch has a genuinely absent training
    error, and null says that; NaN says it in a dialect.
    """
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _float_or_nan(value) -> float:
    """The inverse: a null read back is an absent measurement, not a zero."""
    return float("nan") if value is None else float(value)


@dataclass
class RunRecord:
    """Everything needed to read a run's number without reading the code.

    Written next to the checkpoint **always**, including on an early stop and including when
    the run fails to beat the baseline. A record that only appears on success turns the results
    directory into a survivorship-biased sample of the runs that happened to work.
    """

    run_id: str
    policy: str
    seed: int
    split_digest: str
    device: str
    hyperparameters: dict
    n_train_samples: int
    n_val_samples: int
    duration_s: float
    epochs_completed: int
    val_error: float
    baseline_error: float
    parameter_count: int = 0
    train_error: float = float("nan")
    history: list[dict] = field(default_factory=list)
    balancing: dict = field(default_factory=dict)

    @property
    def beat_baseline(self) -> bool:
        """Derived, never stored independently.

        Stored as a field it could disagree with the two numbers beside it, and a reader would
        have no way to tell which of the three was right.
        """
        return self.val_error < self.baseline_error

    def to_dict(self) -> dict:
        payload = _jsonable(asdict(self))
        payload["beat_baseline"] = self.beat_baseline
        return payload

    def summary(self) -> str:
        verdict = "beat" if self.beat_baseline else "DID NOT BEAT"
        return (
            f"[{self.run_id}] {self.policy}: val {self.val_error:.6f} {verdict} "
            f"baseline {self.baseline_error:.6f} after {self.epochs_completed} epochs "
            f"on {self.device} in {self.duration_s:.0f} s"
        )


def resolve_device(allow_cpu: bool = False) -> torch.device:
    """The device to train on, or a refusal that says how to override it.

    Raises when no usable GPU is found and `allow_cpu` is false. The failure being prevented is
    not a crash: it is a run that quietly starts on the CPU, takes hours instead of minutes,
    and is indistinguishable from a working run until someone looks at the clock.
    """
    if torch.cuda.is_available():
        return torch.device("cuda")

    if allow_cpu:
        return torch.device("cpu")

    raise TrainError(
        "no CUDA device is available. Training on the CPU would take hours rather than "
        "minutes, so it is not the default. Pass --allow-cpu to do it deliberately, or fix "
        "the driver and check with: "
        'python -c "import torch; print(torch.cuda.is_available())"'
    )


def split_digest(path: Path = config.SPLIT_PATH) -> str:
    """A digest of the split file, so a checkpoint cannot be paired with a different split.

    Over the file's bytes rather than over the parsed row lists, because `write_split` already
    guarantees a byte-identical file from the same seed (SC-002). Two digests that differ mean
    the split genuinely differs, not that a dictionary iterated in another order.
    """
    if not path.exists():
        raise TrainError(
            f"no split at {path}. Produce it first: python -m python.bc.split"
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_everything(seed: int) -> None:
    """One seed for Python, numpy and torch.

    Three separate generators, all of which reach into this run. Seeding two of them and
    forgetting the third is the version of this bug that half works, and half-reproducible is
    indistinguishable from not reproducible when a figure has to be defended.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


class FrameDataset(Dataset):
    """Decodes one frame per item. Augmentation applies to training samples only.

    Images are decoded on demand rather than cached. Research R7 left caching as an option to
    take only if a measurement asked for it, and the measurement did not: the loader reaches
    5,776 images per second across eight workers, which is roughly fifteen seconds an epoch,
    against a GPU that wants 7,595. Caching 67,000 decoded frames would cost about 10 GB of RAM
    to remove a bottleneck worth a few seconds.
    """

    def __init__(self, ds: TrackDataset, samples: list[SampleSpec],
                 augment: bool, seed: int) -> None:
        self.img_dir = ds.img_dir
        self.files = [dataset.image_file(ds, sample) for sample in samples]
        self.targets = np.array([sample.steering for sample in samples], dtype=np.float32)
        self.augment = augment
        self.seed = seed
        self.epoch = 0

    def set_epoch(self, epoch: int) -> None:
        """Makes each epoch's augmentation different but still a function of the seed.

        Without this the workers would replay the same flips every epoch, which is a weaker
        augmentation that also looks identical in the logs.
        """
        self.epoch = epoch

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, float]:
        image = dataset.preprocess(Image.open(self.img_dir / self.files[index]))
        target = float(self.targets[index])

        if self.augment:
            # Derived from the run seed, the epoch and the sample index, so it is reproducible
            # without the workers having to share any state. A generator created per item is
            # cheap next to decoding a JPEG.
            rng = np.random.default_rng((self.seed, self.epoch, index))
            image, target = dataset.augment(image, target, rng)

        return torch.from_numpy(image).permute(2, 0, 1), target


def mean_predictor_error(train_targets: np.ndarray, val_targets: np.ndarray) -> float:
    """The error of always predicting the training mean, on the validation set (FR-011).

    The **training** mean, not the validation mean. Using the validation mean would give the
    baseline information the model never had, making it an unfairly strong opponent and the
    model's win look smaller than it is.
    """
    if not len(train_targets) or not len(val_targets):
        raise TrainError("cannot compute a baseline from an empty set")

    guess = float(np.mean(train_targets))
    return float(np.mean((val_targets - guess) ** 2))


def evaluate(network: nn.Module, dataloader: DataLoader,
             device: torch.device) -> float:
    """Mean squared error over a loader, without gradients."""
    network.eval()
    total = 0.0
    count = 0

    with torch.no_grad():
        for images, targets in dataloader:
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True).float()
            predictions = network(images)
            total += float(((predictions - targets) ** 2).sum())
            count += targets.numel()

    return total / count if count else float("nan")


def train(run_id: str,
          policy: BalancingPolicy,
          seed: int = config.SEED,
          allow_cpu: bool = False,
          max_epochs: int = config.MAX_EPOCHS,
          out_dir: Path | None = None,
          network: nn.Module | None = None) -> RunRecord:
    """One training run. Writes a checkpoint and a `RunRecord`, and returns the record.

    `network` is injectable so the negative path can be tested with a deliberately untrained
    model, without waiting for a real run to fail to learn.
    """
    started = time.perf_counter()
    device = resolve_device(allow_cpu)
    seed_everything(seed)

    ds = loader.load_track(config.DATASET_NAME)
    plan = split.read_split()

    train_samples = dataset.build_samples(ds, plan.train_rows, use_side_cameras=True,
                                          seed=seed)
    # Centre camera only, never balanced, never augmented. FR-007 and FR-022: the validation
    # set is the yardstick, and a yardstick that moves with the policy measures nothing.
    val_samples = dataset.build_samples(ds, plan.val_rows, use_side_cameras=False, seed=seed)

    dataset.verify_images_exist(ds, train_samples)
    dataset.verify_images_exist(ds, val_samples)

    balanced, balancing_stats = dataset.apply_balancing(train_samples, policy, seed=seed)

    train_loader = DataLoader(
        FrameDataset(ds, balanced, augment=True, seed=seed),
        batch_size=config.BATCH_SIZE, shuffle=True,
        num_workers=config.DATALOADER_WORKERS, pin_memory=True,
        persistent_workers=config.DATALOADER_WORKERS > 0,
    )
    val_loader = DataLoader(
        FrameDataset(ds, val_samples, augment=False, seed=seed),
        batch_size=config.BATCH_SIZE, shuffle=False,
        num_workers=config.DATALOADER_WORKERS, pin_memory=True,
        persistent_workers=config.DATALOADER_WORKERS > 0,
    )

    network = (network if network is not None else model.build_model()).to(device)
    optimiser = torch.optim.Adam(network.parameters(), lr=config.LEARNING_RATE)
    criterion = nn.MSELoss()

    baseline = mean_predictor_error(
        np.array([s.steering for s in balanced], dtype=np.float64),
        np.array([s.steering for s in val_samples], dtype=np.float64),
    )

    out_dir = out_dir or (config.BC_OUT_DIR / f"run_{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    best_val = float("inf")
    best_state: dict | None = None
    epochs_without_improvement = 0
    epochs_completed = 0
    train_error = float("nan")
    history: list[dict] = []

    for epoch in range(max_epochs):
        train_loader.dataset.set_epoch(epoch)
        network.train()
        running = 0.0
        seen = 0

        for images, targets in train_loader:
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True).float()

            optimiser.zero_grad(set_to_none=True)
            loss = criterion(network(images), targets)
            loss.backward()
            optimiser.step()

            running += float(loss) * targets.numel()
            seen += targets.numel()

        train_error = running / seen if seen else float("nan")
        val_error = evaluate(network, val_loader, device)
        epochs_completed = epoch + 1
        history.append({
            "epoch": epochs_completed,
            "train_error": train_error,
            "val_error": val_error,
        })
        print(f"  epoch {epochs_completed:3d}  train {train_error:.6f}  val {val_error:.6f}")

        if val_error < best_val:
            best_val = val_error
            # Kept on the CPU so the checkpoint does not depend on a GPU being present to
            # load it, and copied rather than referenced, since the next epoch overwrites it.
            best_state = {k: v.detach().cpu().clone() for k, v in network.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= config.EARLY_STOPPING_PATIENCE:
                print(f"  stopping early: {epochs_without_improvement} epochs without "
                      "improvement")
                break

    if best_state is not None:
        torch.save(best_state, out_dir / "checkpoint.pt")

    record = RunRecord(
        run_id=run_id,
        policy=policy.value,
        seed=seed,
        split_digest=split_digest(),
        device=(torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu"),
        hyperparameters={
            "learning_rate": config.LEARNING_RATE,
            "batch_size": config.BATCH_SIZE,
            "max_epochs": max_epochs,
            "optimiser": "adam",
            "loss": "mse",
            "early_stopping_patience": config.EARLY_STOPPING_PATIENCE,
            "camera_offset_range": list(config.CAMERA_OFFSET_RANGE),
            "brightness_range": list(config.BRIGHTNESS_RANGE),
            "flip_probability": config.FLIP_PROBABILITY,
            "crop": [config.CROP_TOP, config.CROP_BOTTOM],
            "activation": config.ACTIVATION,
        },
        n_train_samples=len(balanced),
        # Always the unbalanced count (FR-022). Both runs are scored on the same yardstick, so
        # this figure is identical across the pair by construction.
        n_val_samples=len(val_samples),
        duration_s=time.perf_counter() - started,
        epochs_completed=epochs_completed,
        val_error=best_val if best_state is not None else float("nan"),
        baseline_error=baseline,
        parameter_count=model.parameter_count(network),
        train_error=train_error,
        history=history,
        balancing={
            "policy": balancing_stats.policy.value,
            "n_before": balancing_stats.n_before,
            "n_after": balancing_stats.n_after,
            "n_removed": balancing_stats.n_removed,
            "zero_share_before": balancing_stats.zero_share_before,
            "zero_share_after": balancing_stats.zero_share_after,
            "runner_up_value": balancing_stats.runner_up_value,
            "runner_up_share_after": balancing_stats.runner_up_share_after,
        },
    )

    write_record(record, out_dir / "run_record.json")
    return record


def write_record(record: RunRecord, path: Path) -> None:
    """Sorted and indented, so two runs diff cleanly and a reader can find a field."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.to_dict(), indent=2, sort_keys=True, ensure_ascii=False,
                   allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_record(path: Path) -> RunRecord:
    """Read a record back. `beat_baseline` is recomputed, never trusted from the file.

    Recomputed because a record is a file a person can edit, and the derived field is the one
    worth being able to edit: it is the verdict. Reading it back would let a losing run claim
    it won without either error figure changing.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("beat_baseline", None)

    for name in ("val_error", "baseline_error", "train_error"):
        if name in payload:
            payload[name] = _float_or_nan(payload[name])

    return RunRecord(**payload)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Train the M4 behavioural cloning baseline.")
    parser.add_argument("--policy", required=True,
                        choices=[p.value for p in BalancingPolicy])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--max-epochs", type=int, default=config.MAX_EPOCHS)
    parser.add_argument("--allow-cpu", action="store_true",
                        help="train on the CPU deliberately; expect hours, not minutes")
    args = parser.parse_args()

    record = train(
        run_id=args.run_id,
        policy=BalancingPolicy(args.policy),
        seed=args.seed,
        allow_cpu=args.allow_cpu,
        max_epochs=args.max_epochs,
    )

    print()
    print(record.summary())
    if not record.beat_baseline:
        print("  This is a reported result, not a failed run (SC-003). Near-zero steering "
              "dominates the data, so the mean predictor is a strong opponent.")
    print(f"  written to {config.BC_OUT_DIR / ('run_' + args.run_id)}")
    print("  Log it in results/EXPERIMENTS.md in this session (Principle VI).")


if __name__ == "__main__":
    main()
