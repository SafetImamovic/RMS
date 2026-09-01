# Contract: Trainer Configuration

**Feature**: `006-ppo-rl-driver` | **File**: `config/ppo_car.yaml`

The trainer configuration is committed and is the file the run actually used (FR-014). A
hyperparameter that exists only in a shell history is not reproducible, and the constitution pins
`config/*.yaml` for exactly this reason.

## Shape

```yaml
behaviors:
  CarDriver:
    trainer_type: ppo
    hyperparameters:
      batch_size: 2048
      buffer_size: 20480
      learning_rate: 3.0e-4
      learning_rate_schedule: linear
      beta: 5.0e-3
      epsilon: 0.2
      lambd: 0.95
      num_epoch: 3
    network_settings:
      normalize: true
      hidden_units: 256
      num_layers: 2
    reward_signals:
      extrinsic:
        gamma: 0.99
        strength: 1.0
    max_steps: <set from the pilot run, R8>
    time_horizon: 128
    summary_freq: 10000
    keep_checkpoints: 5
```

`CarDriver` is the behaviour name and must match `BehaviorParameters.BehaviorName` in the training
scene exactly. A mismatch does not error; the trainer simply never sees the agent, and the run
sits at zero steps.

## What is pinned and what a run may vary

| Field | Status | Why |
|---|---|---|
| `trainer_type` | Pinned | The tool is assignment-locked to PPO |
| `batch_size`, `buffer_size`, `learning_rate`, `hidden_units`, `num_layers`, `gamma` | Starting values from `DESIGN.md` 5 | These are what tuning may change, one at a time, each in its own run with its own log row |
| `normalize` | Pinned true | The observation vector mixes normalised distances with signed speeds, and the ranges differ |
| `max_steps` | Set once from the measured throughput | R8: chosen from a pilot measurement rather than from the design's 2M to 5M range |
| `time_horizon` | Starting value | Interacts with episode length, which R5 fixes at up to 6000 steps |
| `summary_freq` | Pinned 10000 | Fixes the resolution of every committed curve, so two runs' curves are comparable row for row |

## The rule that makes a comparison mean anything

**One run changes one thing.** The run's log row in `results/EXPERIMENTS.md` names that one thing.
A run whose description needs an "and" is two experiments and its result attributes to neither of
them. This is the same rule `results/EXPERIMENTS.md` already states for the BC runs, and feature
004 enforced it in code by refusing to render a comparison when more than one field differed.

## Command line

The run id, the seed and the device are command-line arguments rather than file fields, because
they identify the run rather than configure the trainer:

```text
mlagents-learn config/ppo_car.yaml --run-id=ppo_car_vNN --seed=<n> --torch-device=cuda
```

Run from the repository root, so the trainer's `results/` is the project's `results/`
(`ENVIRONMENT.md`).

## Spread runs

The three runs that establish the noise floor (R9, FR-020) differ from each other in `--seed` and
in nothing else, including `max_steps`, which is set to the reduced budget for all three. Their
run ids carry the shape `ppo_car_spread_a/b/c` so they are not mistaken for candidate models.
