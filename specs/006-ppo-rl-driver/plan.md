# Implementation Plan: PPO Reinforcement Learning Driver

**Branch**: `006-ppo-rl-driver` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-ppo-rl-driver/spec.md`

## Summary

A `Unity.MLAgents.Agent` that wraps the existing `CarAgent` sensing and writes to the same
`CarController.ScriptedMove` path the scripted driver uses, so all three drivers reach the wheels
through one route and the comparison is between policies rather than between plumbing.

The reward is the table `DESIGN.md` 4.5 already fixed, implemented as pure functions over signals
that already exist: the checkpoint ring's award and wrong-way detection, a collision count, the
speed the sensing already normalises, and the change in the commanded steering. Each term is
reported separately to the trainer's statistics, because a total that rises does not say which
term made it rise.

Training runs in a new scene holding several independent copies of the environment, each copy
building its own track from the accepted training seeds and rotating through them. The evaluation
seeds are never loaded by that scene. Evaluation reuses feature 005's sweep runner, so the learned
column and the scripted column come out of the same code and land in the same row shape.

The measurement discipline is the one features 004 and 005 both arrived at: the run-to-run spread
is measured at a reduced training budget before any two configurations are compared, and no
configuration change is called an improvement until it clears that spread.

## Technical Context

**Language/Version**: C# (Unity 6000.5.3f1) for the agent, the reward and the training scene;
Python 3.10.11 in `.venv-mlagents` for the trainer, and `.venv` for the reporting that joins this
column to the existing ones
**Primary Dependencies**: `com.unity.ml-agents` 4.0.3 (already in `Packages/manifest.json`, already
referenced by `SelfDrivingSim.asmdef`), `com.unity.ai.inference` 2.6.1 for inference, `mlagents`
1.1.0 on the Python side, Communicator API 1.5.0 between them
**Storage**: `config/ppo_car.yaml` for the pinned trainer configuration; `results/rl/` for the
committed per-run curve exports and evaluation records; `results/<run-id>/` for the trainer's own
output, which stays git-ignored apart from the exported model; `.onnx` through Git LFS, which
`.gitattributes` already routes
**Testing**: Unity EditMode tests for the reward terms, which are pure functions, and for the
training scene's seed isolation; `pytest` for the curve export and the reporting
**Target Platform**: Windows, Unity Editor connected to `mlagents-learn`. Training runs in the
editor rather than a player build, matching how feature 005 ran its sweep
**Project Type**: Unity simulation feature plus a Python training and reporting step, the same
split features 003 and 005 use
**Performance Goals**: a full training run inside 12 hours on the RTX 3050 (SC-006). The 3DBall
verification reached 700 steps/s with 12 areas on a trivial environment; a WheelCollider car with
13 raycasts will be well below that, and the pilot run measures where
**Constraints**: the agent may observe only what `CarAgent` already produces (FR-001, FR-002).
Physics runs at 50 Hz and the human dataset was recorded at 14.08 Hz, which fixes the decision
period (R2). The sensing geometry, the vehicle, the track generator, the barriers and the
checkpoint logic are all frozen (FR-028)
**Scale/Scope**: 34 training seeds, 10 held-out evaluation seeds, 8 to 16 environment copies per
session, one new scene, four new C# components, one trainer config, two Python modules

No NEEDS CLARIFICATION items remain. The three decisions the spec needed were taken with the owner
before it was written, and every technical unknown is resolved in [research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Spec-Driven** | Spec and checklist written before this plan; no code exists yet. Passes |
| **II. Git-Flow & Atomic Commits** | Branch `006-ppo-rl-driver` off `develop`, matching `specs/006-ppo-rl-driver/`, merged back with `--no-ff`. The `exp` commit type exists for training runs and is used for them. Passes |
| **III. Human-Only Commits** | The agent has run no history-mutating command in this feature. Files are written, explained, and the owner commits. No attribution trailers. Passes |
| **IV. Multi-Agent Coordination** | File ownership declared below. A **new** scene is added rather than editing `Track.unity` or `HeuristicWeighted.unity`, which keeps the scene lock uncontested. Passes |
| **V. Design-First** | Three things this feature decides are architectural and go into `DESIGN.md` before the code that uses them: the decision period and its relation to the 14.08 Hz threshold, the training-area layout, and the reduced-budget spread protocol. `DESIGN.md` 4.5 already holds the reward table and is not restated here. Task ordering enforces the writeback |
| **VI. Reproducibility** | The trainer configuration is a committed file (FR-014), every run carries a unique id tying config, curves, model and log entry together (FR-017), and the seed split comes from the committed `results/tracks/seed_split.json`. The spread is measured rather than determinism asserted (R9) |
| **VII. Dataset Discipline** | The image dataset does not enter this feature. The only number borrowed from it is the 0.55 steering-change threshold M1 measured, which arrives through `DESIGN.md` rather than through the CSV. FR-030 forbids the rest |
| **VIII. Test Gates** | Reward terms are pure functions with EditMode tests, including the cases that decide whether a reward is farmable (R14). Seed isolation is an EditMode test rather than a promise (R15). `pytest` covers the curve export and the report. The keyboard-lap gate is already satisfied by feature 003 T051, so training is permitted to start |
| **IX. Statistical Rigor** | The spread protocol (FR-020, FR-021) is where this principle bites hardest, because reinforcement learning is the noisiest thing this project has measured. The learned column is described with the same `python.eda.stats.describe` used for the human, imitation and scripted columns, and compared against the human distribution with a test rather than a plot (FR-024) |

**No violations requiring justification.** One deliberate complexity is recorded in Complexity
Tracking: the interface extraction that lets feature 005's sweep runner drive a learned policy.

### Declared file ownership (Principle IV)

New:

- `unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs` - the `Unity.MLAgents.Agent`
- `unity/SelfDrivingSim/Assets/Scripts/Agent/RewardModel.cs` - reward terms as pure functions
- `unity/SelfDrivingSim/Assets/Scripts/Vehicle/WallSensor.cs` - collision counting as its own
  component, so nothing in feature 005 has to be edited to share it
- `unity/SelfDrivingSim/Assets/Scripts/Track/TrainingArea.cs` - one self-contained copy
- `unity/SelfDrivingSim/Assets/Scripts/Track/AreaScheduler.cs` - seed rotation across areas
- `unity/SelfDrivingSim/Assets/Scenes/Training.unity` and its area prefab
- `unity/SelfDrivingSim/Assets/Tests/EditMode/RewardModelTests.cs`,
  `TrainingSeedIsolationTests.cs`
- `config/ppo_car.yaml`
- `python/rl/export_curves.py`, `python/rl/report.py`
- `python/tests/test_rl_curves.py`, `python/tests/test_rl_report.py`
- `results/rl/` - committed curve exports, evaluation records and the written comparison

Modified:

- `unity/SelfDrivingSim/Assets/Scripts/Track/SweepRunner.cs` - drives through an interface so the
  evaluation of a learned policy reuses it instead of copying it
- `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs` - implements that interface.
  **Mechanical only**, and a re-run of one recorded seed must reproduce its row
- `DESIGN.md` - sections 4.5 and 5, written before the code they describe
- `.gitignore` - raw trainer output stays out, the exported curves come in
- `README.md` - the M3 recipe, in the same feature that makes it true

Not touched, and this is a requirement rather than an expectation: `CarAgent.cs`, `CarController`,
`TrackBuilder`, `CheckpointRing`, `StartPlacer`, the barrier geometry, `vehicle_profile.json`, and
every file under `specs/003-*`, `specs/004-*`, `specs/005-*`.

## Project Structure

### Documentation (this feature)

```text
specs/006-ppo-rl-driver/
├── plan.md              # This file
├── spec.md              # Phase -1
├── research.md          # Phase 0, R1 to R15
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── reward-events.md    # every reward term, its source signal and its stats key
│   ├── training-config.md  # what config/ppo_car.yaml pins and what a run may vary
│   └── curve-export.md     # the committed CSV shape of a training curve
├── checklists/
│   └── requirements.md  # written with the spec
└── tasks.md             # Phase 2, /speckit-tasks, not created here
```

### Source Code (repository root)

```text
unity/SelfDrivingSim/Assets/
├── Scripts/
│   ├── Agent/
│   │   ├── CarAgent.cs              # unchanged: the sensing the agent reads
│   │   ├── DrivingAgent.cs          # new: observations, actions, reward, episode
│   │   ├── RewardModel.cs           # new: the terms, pure and testable
│   │   └── HeuristicDriver.cs       # modified: implements IRunDriver, behaviour unchanged
│   ├── Vehicle/
│   │   └── WallSensor.cs            # new: counts barrier contacts, owns nothing else
│   └── Track/
│       ├── TrainingArea.cs          # new: one independent copy of the environment
│       ├── AreaScheduler.cs         # new: rotates seeds across areas between episodes
│       └── SweepRunner.cs           # modified: drives IRunDriver, so eval reuses it
├── Scenes/
│   ├── Training.unity               # new: the multi-area training scene
│   └── HeuristicWeighted.unity      # unchanged
├── Prefabs/
│   └── TrainingArea.prefab          # new: track, car, markers, agent, all self-contained
└── Tests/EditMode/
    ├── RewardModelTests.cs          # new
    └── TrainingSeedIsolationTests.cs# new

config/
└── ppo_car.yaml                     # new: the pinned trainer configuration

python/
├── rl/
│   ├── export_curves.py             # new: trainer event files to committed CSV
│   └── report.py                    # new: the learned column, in the existing shape
└── tests/
    ├── test_rl_curves.py            # new
    └── test_rl_report.py            # new

results/rl/                          # new: curves, evaluation records, the written comparison
```

**Structure Decision**: the feature keeps feature 003's and 005's split. Policy and reward in C#
under `Assets/Scripts/`, analysis in Python under `python/`, results as files under `results/`.

`RewardModel.cs` is separate from `DrivingAgent.cs` for the same reason `RayControllers.cs` was
separated from `HeuristicDriver.cs` in feature 005: the terms are pure functions of numbers, which
is what makes them testable without a scene, a car or a physics step. A reward that can only be
verified by watching a car drive is a reward nobody can verify.

`WallSensor.cs` is a new component rather than an edit to `HeuristicDriver`, because Unity delivers
`OnCollisionEnter` to every component on the object and the scripted driver's own counting must
keep producing the rows feature 005 already published.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1. No new violations.

- **Principle V** gained three concrete writebacks during Phase 0, listed in the table above. The
  decision period is the sharpest of them: it changes the rate at which a threshold measured from
  the human dataset is evaluated, and that is a design fact rather than an implementation detail.
- **Principle VI** met a real conflict and resolved it in R10. The repository ignores
  `results/tensorboard/` and the trainer's event files, while FR-018 requires the curves to survive
  in a clean clone. The resolution is to commit a distilled CSV per run and keep the raw events
  ignored, which keeps the record reproducible without putting binary event logs in history.
- **Principle VIII** is satisfiable only because the reward is separated out and the seed isolation
  is expressible as a test over the committed split. Both were design choices made to make the gate
  reachable rather than claimed.
- **Principle IX** gained its hardest obligation in R9: the spread has to be measured at a budget
  the machine can afford three times, and every comparison then has to be made at that same budget
  or explicitly marked as unbacked.

## Complexity Tracking

> No Constitution Check violations require justification.

Two choices are recorded as deliberate rather than accidental complexity.

| Choice | Why | Simpler alternative rejected because |
|---|---|---|
| Extract `IRunDriver` and have both `HeuristicDriver` and `DrivingAgent` implement it, so `SweepRunner` evaluates either | FR-023 requires the learned column and the scripted column to come out of the same code in the same row shape. One runner producing both is the only version of that claim that cannot drift | Copying `SweepRunner` into an `EvalRunner` would duplicate roughly 600 lines including the seed-split loading, the fan handling and the timing, and the two copies would diverge the first time either is fixed. The duplicated version would also make the two columns comparable only by inspection |
| A separate training scene with several environment copies, instead of training in the existing single-track scene | FR-015 and SC-006 are a throughput requirement, and the 3DBall baseline of 700 steps/s was measured with 12 areas. A single area at roughly one twelfth of that turns a 2M-step run into several days, which leaves no room for the tuning FR-007 expects | Training in `HeuristicWeighted.unity` would also break the scene lock and put training state into the scene feature 005's results were produced from. A single-area scene would be simpler but would spend the milestone's whole budget on one configuration |
