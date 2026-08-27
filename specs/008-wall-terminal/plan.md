# Implementation Plan: The wall terminal

**Branch**: `008-wall-terminal` | **Spec**: `specs/008-wall-terminal/spec.md`
**Created**: 2026-08-26

## Summary

One change to `DrivingAgent.CheckTermination`: a wall contact charges its pinned penalty and ends
the episode only once a configured budget of contacts is exhausted. The budget is a serialized
field, and zero reproduces feature 007 exactly.

Two measurements come with it, because the change cannot be read without them. **Wall contacts per
episode**, and **mean minimum lateral ray clearance**, which exists because research R2 found that
a car sliding along a barrier without separating registers only one contact and so the contact count
cannot detect a grind.

**The order matters and is enforced by the task list.** The recovery probe (R4) runs before the
budget is chosen, because if the car cannot reverse off a barrier the whole feature buys a slower
failure rather than a better one.

## Technical Context

**Language**: C# (Unity 6000.5.3f1, ML-Agents), Python 3 for export and reporting.

**The one change**: `DrivingAgent.CheckTermination`, the branch that currently reads

```
if (wall != null && wall.TakeNewContact()) { ...; Finish(EndReason.WallContact); return; }
```

becomes a charge plus a budget test. The penalty stays at `RewardModel.WallPenalty` = -5.0, pinned
by FR-006, because feature 006 already tested the weight and this feature tests the terminal.

**What is deliberately not touched**: `WallSensor`. Its `OnCollisionEnter` filter is the code path
behind every committed `results/heuristic/` row, and adding `OnCollisionStay` to measure wall time
would change that path in the same feature that changes the terminal. R5 selects a measure that
needs no change to it.

**Baseline**: `ppo_car_007_progress`, 5,000,000 steps, seed 42. Markers per episode **1.4987**,
wall share **59.1 per cent**, held-out **6.20 of 24** markers with zero laps. Gate **0.035** from
`results/rl/progress_spread.md`, reused with the caveat that document already states.

## Constitution Check

*GATE: must pass before Phase 0 research. Re-checked after design.*

| Principle | Assessment |
|---|---|
| **I. Spec-Driven** | Spec written and committed before this plan. Branch, spec directory and `.specify/feature.json` all name `008-wall-terminal`. Passes |
| **II. Git-Flow & Atomic Commits** | Branch off `develop`, merged back with `--no-ff` as feature 007 was. Passes |
| **III. Human-Only Commits & Reviewed Handoffs** | The agent commits only on an explicit instruction covering the work in front of it. No `Co-Authored-By`, no session URL, no tool trailer, in commits or in `EXPERIMENTS.md`. Passes |
| **IV. Multi-Agent Coordination** | File ownership declared below. **No scene and no prefab is edited except to set the budget field**, and the field defaults so that an unedited prefab reproduces feature 007. Passes |
| **V. Design-First** | The terminal is part of the reward table's contract, so `DESIGN.md` 4.5 and 4.6 gain the budget and its default **before any code task starts**. Task ordering enforces it. Passes |
| **VI. Reproducibility** | `config/ppo_car.yaml` reused unchanged, so the one change is in the C# and visible in the diff. Every run gets a unique id and an `EXPERIMENTS.md` row in the same session. Passes |
| **VII. Dataset Discipline** | The image dataset does not enter this feature. Passes |
| **VIII. Test Gates** | The three properties are testable without a scene: a contact under budget leaves the episode live, a contact at budget ends it with the existing end reason, and the penalty is charged once per contact. EditMode assertions. Passes |
| **IX. Statistical Rigor** | The gate is named on every comparison and its caveat is restated rather than dropped. A result landing near the gate earns a fresh three-run spread rather than a verdict. Passes |

**One violation to record rather than hide.** Feature 007 closed with **SC-007 not met**: the seven
reward terms sum to the trainer's cumulative reward on 4.8 per cent of rows, caused by an
episode-set mismatch of about 19 per cent. This feature inherits that defect. It does not make it
worse and it does not fix it, and every claim here rests on behavioural counts taken Unity-side
rather than on the reward decomposition. Recorded in Complexity Tracking.

### Declared file ownership (Principle IV)

Modified:

- `DESIGN.md` sections 4.5 and 4.6 - the contact budget, its default, and why the terminal is
  separable from the penalty. **Committed before any code task starts**
- `unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs` - the budget field, the changed
  branch in `CheckTermination`, the two new statistics, and their reset on episode begin
- `unity/SelfDrivingSim/Assets/Tests/EditMode/` - a new or extended test file for the three
  properties above
- `python/rl/export_curves.py` - two new columns
- `python/tests/test_rl_curves.py` - coverage for them
- `python/rl/report.py`, `python/tests/test_rl_report.py` - the held-out column carries wall
  contacts and clearance
- `results/EXPERIMENTS.md` - one row per run
- `unity/SelfDrivingSim/Assets/Prefabs/TrainingArea.prefab` and
  `unity/SelfDrivingSim/Assets/Scenes/Evaluation.unity` - the budget field only

Not touched, and this is a requirement rather than an expectation: `WallSensor.cs`,
`RewardModel.cs` weights, `CarAgent.cs`, `CarController.cs`, `TrackBuilder.cs`, `CheckpointRing.cs`,
`TrackProgress.cs`, `StartPlacer.cs`, `SweepRunner.cs`, `HeuristicDriver.cs`, `RayControllers.cs`,
`vehicle_profile.json`, `config/ppo_car.yaml`, `results/tracks/seed_split.json`, and everything
under `specs/003-*` through `specs/007-*`.

## Project Structure

### Documentation (this feature)

```
specs/008-wall-terminal/
├── spec.md          the hypothesis, stated so it can fail
├── plan.md          this file
├── research.md      R1 to R8, including the OnCollisionEnter finding that reshaped the design
├── data-model.md    the budget, the two new measures
├── quickstart.md    how to run and read it
└── tasks.md         the ordered work
```

### Source Code (repository root)

```
unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs      the budget and the branch
unity/SelfDrivingSim/Assets/Tests/EditMode/                    the three properties
python/rl/export_curves.py                                     two columns
python/rl/report.py                                            the held-out column
results/EXPERIMENTS.md                                         one row per run
results/rl/                                                    logs, curves, eval rows
```

## Phases

**Phase 0, research.** Done, in `research.md`. R2 changed the design: the contact count cannot
detect a grind, so R5 adds lateral clearance instead of adding `OnCollisionStay`.

**Phase 1, the recovery probe (R4).** Before anything else, and before the budget is chosen. Drive
the car into a barrier and try to reverse out, in the editor, no training. If the car cannot
separate, the budget buys a `Stalled` ending sixty seconds later instead of a `WallContact` ending
now, and the feature's premise is wrong. **This gate can cancel the feature, which is why it is
first.**

**Phase 2, the change and its tests.** The budget field, the branch, the two statistics, the
EditMode properties. Zero reproduces feature 007.

**Phase 3, the candidate run.** Full budget, one change from feature 007, `config/ppo_car.yaml`
unchanged, seed 42 so the comparison is like for like.

**Phase 4, the held-out evaluation.** Both inference modes, no trainer, ten held-out seeds. The M3
milestone bar recorded met or not met with its number.

**Phase 5, closeout.** The grinding check reported with a number whichever way it comes out, the
closeout table, `DESIGN.md` updated with the outcome, and the next feature named.

## Post-Design Constitution Re-Check

The design adds no new component and no new file under `Assets/Scripts`. It adds one serialized
field, one changed branch, two accumulators and two statistics keys. Principle IV's scene lock is
touched only to set the budget, and the default makes an unedited prefab behave as feature 007 did.
**Re-check passes.**

## Complexity Tracking

| Cost | Why it is accepted |
|---|---|
| The feature inherits feature 007's unresolved SC-007 accounting defect | Fixing it needs per-episode records, which feature 007 named as its own separate feature. Every claim here rests on Unity-side counts rather than on the reward decomposition, so the defect does not touch the verdict |
| Lateral clearance is a proxy for wall time, not wall time itself | Measuring wall time needs `OnCollisionStay` on `WallSensor`, which is the code path behind every committed heuristic baseline. R5 takes the proxy from the existing ray fan at the cost of one accumulator. If the proxy shows grinding, a wall-time terminal is its own feature |
| Episodes may get much longer, and the stall timeout becomes load bearing | Measured rather than assumed: throughput and mean episode length are reported on every run (SC-009, R6) |
