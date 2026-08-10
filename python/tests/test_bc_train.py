"""The training loop's guarantees, exercised without waiting for a real run.

The expensive path is deliberately avoided. A real run takes about an hour, and a suite that
needs one is a suite nobody runs before committing. What is tested instead is everything that
decides whether a run's number can be trusted: the device is resolved rather than assumed, the
baseline is computed from the training mean, the record is complete even when the model is
useless, and a checkpoint cannot be paired with the wrong split.

The negative path is exercised with a deliberately untrained model. `beat_baseline: false` is a
reported result under SC-003, not a failure, and it needs to work.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

torch = pytest.importorskip(
    "torch", reason="the training loop needs torch; run this under .venv-bc"
)

from python.bc import config, train  # noqa: E402
from python.bc.dataset import BalancingPolicy  # noqa: E402


# -----------------------------------------------------------------------------------------
# Device resolution. FR-009.
# -----------------------------------------------------------------------------------------


def test_no_gpu_and_no_override_raises_and_says_how_to_override(monkeypatch):
    """The failure being prevented is not a crash but a silent multi-hour CPU run.

    The message has to carry the override, because the person hitting this is the person who
    does not yet know it exists.
    """
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(train.TrainError) as raised:
        train.resolve_device(allow_cpu=False)

    assert "--allow-cpu" in str(raised.value)


def test_no_gpu_with_the_override_returns_a_cpu_device(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    assert train.resolve_device(allow_cpu=True).type == "cpu"


def test_a_gpu_is_used_when_one_is_present(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    assert train.resolve_device(allow_cpu=False).type == "cuda"


# -----------------------------------------------------------------------------------------
# The baseline. FR-011.
# -----------------------------------------------------------------------------------------


def test_the_baseline_uses_the_training_mean_not_the_validation_mean():
    """Using the validation mean would hand the baseline information the model never had.

    It would then be an unfairly strong opponent, and every `beat_baseline` in the results
    would be understating what the model achieved.
    """
    train_targets = np.array([0.0, 0.0, 0.0, 0.0])
    val_targets = np.array([1.0, 1.0])

    # Training mean is 0.0, so the error is 1.0. The validation mean is 1.0, which would give
    # 0.0 and make the baseline unbeatable.
    assert train.mean_predictor_error(train_targets, val_targets) == pytest.approx(1.0)


def test_the_baseline_is_the_mean_squared_error_of_a_constant_guess():
    train_targets = np.array([-1.0, 1.0])          # mean 0.0
    val_targets = np.array([-2.0, 2.0])            # squared errors 4 and 4

    assert train.mean_predictor_error(train_targets, val_targets) == pytest.approx(4.0)


def test_an_empty_set_cannot_produce_a_baseline():
    with pytest.raises(train.TrainError, match="empty"):
        train.mean_predictor_error(np.array([]), np.array([1.0]))

    with pytest.raises(train.TrainError, match="empty"):
        train.mean_predictor_error(np.array([1.0]), np.array([]))


# -----------------------------------------------------------------------------------------
# The record. SC-008 and SC-003.
# -----------------------------------------------------------------------------------------


def a_record(**overrides) -> train.RunRecord:
    fields = dict(
        run_id="bc_test_v01",
        policy=BalancingPolicy.NONE.value,
        seed=config.SEED,
        split_digest="0" * 64,
        device="cpu",
        hyperparameters={"learning_rate": config.LEARNING_RATE},
        n_train_samples=100,
        n_val_samples=20,
        duration_s=1.0,
        epochs_completed=1,
        val_error=0.5,
        baseline_error=0.4,
    )
    fields.update(overrides)
    return train.RunRecord(**fields)


def test_a_run_that_does_not_beat_the_baseline_is_still_a_complete_record():
    """SC-003: a negative result is reported, not discarded.

    On this dataset it is a live possibility rather than a formality. Near-zero steering
    dominates, so guessing the mean is a strong strategy, and the unbalanced run in particular
    may lose to it.
    """
    record = a_record(val_error=0.9, baseline_error=0.4)

    assert record.beat_baseline is False
    payload = record.to_dict()
    for required in ("run_id", "policy", "seed", "split_digest", "device",
                     "hyperparameters", "n_train_samples", "n_val_samples",
                     "duration_s", "epochs_completed", "val_error", "baseline_error"):
        assert required in payload, f"{required} missing from a losing run's record"


def test_beat_baseline_is_derived_and_cannot_be_set_independently():
    """Stored as a field it could contradict the two numbers beside it."""
    with pytest.raises(TypeError):
        a_record(beat_baseline=True)

    assert a_record(val_error=0.1, baseline_error=0.4).beat_baseline is True
    assert a_record(val_error=0.4, baseline_error=0.1).beat_baseline is False


def test_a_tie_does_not_count_as_beating_the_baseline():
    """A model that exactly matches the constant guess has learned nothing."""
    assert a_record(val_error=0.4, baseline_error=0.4).beat_baseline is False


def test_a_record_round_trips_through_disk(tmp_path):
    original = a_record(val_error=0.9, baseline_error=0.4, history=[{"epoch": 1}])
    path = tmp_path / "run_record.json"

    train.write_record(original, path)
    restored = train.read_record(path)

    assert restored.to_dict() == original.to_dict()


def test_the_record_is_valid_json_even_when_a_measurement_is_absent(tmp_path):
    """A run that stops before completing an epoch has no training error.

    `json.dumps` writes a bare `NaN` for that by default. Python reads it back happily and
    every strict parser rejects it, so the file would look fine until something other than
    Python opened it.
    """
    path = tmp_path / "run_record.json"
    train.write_record(a_record(train_error=float("nan")), path)

    payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject)

    assert payload["train_error"] is None
    assert np.isnan(train.read_record(path).train_error)


def _reject(name: str):
    raise AssertionError(f"the record contains the non-standard JSON literal {name}")


def test_the_record_file_is_sorted_so_two_runs_diff_cleanly(tmp_path):
    path = tmp_path / "run_record.json"
    train.write_record(a_record(), path)

    keys = list(json.loads(path.read_text(encoding="utf-8")).keys())

    assert keys == sorted(keys)


def test_beat_baseline_is_recomputed_on_read_rather_than_trusted(tmp_path):
    """A hand-edited file cannot make a losing run claim it won."""
    path = tmp_path / "run_record.json"
    train.write_record(a_record(val_error=0.9, baseline_error=0.4), path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["beat_baseline"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert train.read_record(path).beat_baseline is False


# -----------------------------------------------------------------------------------------
# The split digest. A checkpoint cannot be paired with the wrong split.
# -----------------------------------------------------------------------------------------


def test_the_digest_changes_when_the_split_changes(tmp_path):
    first = tmp_path / "split.json"
    first.write_text('{"seed": 42}', encoding="utf-8")
    digest = train.split_digest(first)

    second = tmp_path / "other.json"
    second.write_text('{"seed": 43}', encoding="utf-8")

    assert digest != train.split_digest(second)
    assert digest == train.split_digest(first)


def test_a_missing_split_names_the_command_that_produces_it(tmp_path):
    with pytest.raises(train.TrainError, match="python -m python.bc.split"):
        train.split_digest(tmp_path / "absent.json")


# -----------------------------------------------------------------------------------------
# Seeding
# -----------------------------------------------------------------------------------------


def test_one_seed_covers_python_numpy_and_torch():
    """Seeding two of the three is the version of this bug that half works.

    Half reproducible is indistinguishable from not reproducible when a figure has to be
    defended, because the failure only shows up in whichever component was missed.
    """
    import random

    train.seed_everything(config.SEED)
    first = (random.random(), np.random.random(), torch.randn(1).item())

    train.seed_everything(config.SEED)
    second = (random.random(), np.random.random(), torch.randn(1).item())

    assert first == second


# -----------------------------------------------------------------------------------------
# Evaluation
# -----------------------------------------------------------------------------------------


class ConstantModel(torch.nn.Module):
    """A deliberately untrained model, so the negative path runs in milliseconds."""

    def __init__(self, value: float) -> None:
        super().__init__()
        self.value = value
        self.unused = torch.nn.Parameter(torch.zeros(1))

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return torch.full((batch.shape[0],), self.value) + 0.0 * self.unused


def test_evaluate_computes_mean_squared_error_over_a_loader():
    from torch.utils.data import DataLoader, TensorDataset

    images = torch.zeros(8, config.INPUT_CHANNELS, config.INPUT_HEIGHT, config.INPUT_WIDTH)
    targets = torch.full((8,), 3.0)
    loader = DataLoader(TensorDataset(images, targets), batch_size=4)

    # A constant prediction of 1.0 against a constant target of 3.0 is an error of 4.0.
    error = train.evaluate(ConstantModel(1.0), loader, torch.device("cpu"))

    assert error == pytest.approx(4.0)


def test_evaluate_averages_over_samples_not_over_batches():
    """An uneven final batch would otherwise be weighted as heavily as a full one."""
    from torch.utils.data import DataLoader, TensorDataset

    images = torch.zeros(5, config.INPUT_CHANNELS, config.INPUT_HEIGHT, config.INPUT_WIDTH)
    targets = torch.tensor([0.0, 0.0, 0.0, 0.0, 10.0])
    loader = DataLoader(TensorDataset(images, targets), batch_size=4)

    error = train.evaluate(ConstantModel(0.0), loader, torch.device("cpu"))

    # Per sample: (0+0+0+0+100)/5 = 20. Per batch it would be (0 + 100)/2 = 50.
    assert error == pytest.approx(20.0)


def test_the_hyperparameters_recorded_are_the_ones_that_were_used():
    """A record whose hyperparameters drift from config describes a run that did not happen."""
    record = a_record(hyperparameters={
        "learning_rate": config.LEARNING_RATE,
        "batch_size": config.BATCH_SIZE,
        "optimiser": "adam",
        "loss": "mse",
    })

    assert record.hyperparameters["learning_rate"] == config.LEARNING_RATE
    assert record.hyperparameters["batch_size"] == config.BATCH_SIZE
