# Implementation Plan: The imitation warm start

**Branch**: `009-imitation-warm-start` | **Spec**: `specs/009-imitation-warm-start/spec.md`
**Created**: 2026-08-28

## Summary

Two changes, one in C# and one in YAML.

`DrivingAgent.Heuristic` stops emitting zeros and **delegates** to `HeuristicDriver.Decide()`, which
puts the project's only expert into the agent's own observation and action space and lets
ML-Agents' `DemonstrationRecorder` write a `.demo` from it. `config/ppo_car.yaml` then gains a
`behavioral_cloning` block pointing at that file. Nothing else moves: the reward table, the wall
budget, `MaxStep` and `DecisionPeriod` are all pinned by the spec so the run stays comparable to
features 007 and 008.

**The order is a gate and the task list enforces it.** The expert is measured through the agent's
action path at `DecisionPeriod: 4` **before** anything is recorded in bulk. Research R3 found the
concrete failure mode this guards against: the throttle is bang-bang against a `0.25 m/s` deadband
and one decision period is long enough for the speed to move `0.47 m/s`, so the speed controller is
where 34 of 34 can collapse. If it does, the feature reports it and stops rather than lowering
`DecisionPeriod`.

**Scope note, decided 2026-08-28.** M3 is capped at this feature. Whatever this measures, the next
work item is the M3 closeout and then M5, not a fourth reward-side remedy. The one exception is the
near-gate case in Assumptions, which `results/rl/progress_spread.md` already governs.

## Technical Context

**Language**: C# (Unity 6000.5.3f1, `com.unity.ml-agents` 4.0.3), Python 3 with `mlagents` 1.1.0 in
`.venv-mlagents` for training and reporting.

**Change one, the delegation.** `DrivingAgent.Heuristic` (`DrivingAgent.cs:809`) currently zeroes
the continuous actions, and its XML comment explains why: duplicating the scripted driver into it
would put two implementations of the baseline in the project and the M5 comparison would have no
single answer. **That objection is satisfied by calling rather than copying.** `Decide()`
(`HeuristicDriver.cs:804`) already returns the `(steer, throttle)` pair the action space carries and
is private; it becomes callable and the callback fills the buffer from it. The comment is rewritten
to say what is now true, not deleted.

**Change two, the trainer block.** `behavioral_cloning` with an explicit `demo_path`, `steps`,
`strength` and `samples_per_update`. Research R8 is why three of those four are explicit rather than
defaulted: `steps: 0` makes the schedule constant, so the default applies the imitation loss at full
strength for all 5,000,000 steps and the run would measure imitation rather than reinforcement.

**What is deliberately not touched.** `RewardModel` weights, `wallContactBudget` (stays 0),
`MaxStep` (stays 6000), `DecisionPeriod` (stays 4), and the whole `hyperparameters` block of
`config/ppo_car.yaml`. FR-005 and FR-010 pin these so cumulative reward stays comparable to 007 and
008 and the comparison is 007's terminal with 008's step limit.

**Baseline**: `ppo_car_007_progress`, 5,000,000 steps, seed 42. Markers per episode **1.4987**, wall
share **59.1 per cent**, held-out **6.20 of 24** markers with zero laps. Gate **0.035** from
`results/rl/progress_spread.md`, reused a third time with the caveat that document states.
Throughput read against **903** and **927** steps per second.

## Constitution Check

*GATE: must pass before Phase 0 research. Re-checked after design.*

| Principle | Assessment |
|---|---|
| **I. Spec-Driven** | `spec.md` written 2026-08-27, before this plan. Branch, spec directory and `.specify/feature.json` all name `009-imitation-warm-start`. Passes |
| **II. Git-Flow & Atomic Commits** | Branch off `develop`, merged back with `--no-ff` as 007 and 008 were. Passes |
| **III. Human-Only Commits & Reviewed Handoffs** | The agent commits only on an explicit instruction covering the work in front of it. No `Co-Authored-By`, no session URL, no tool trailer, in commits or in `EXPERIMENTS.md`. Passes |
| **IV. Multi-Agent Coordination** | File ownership declared below. **After R10 the training prefab and both existing training scenes are not edited at all**: the recorder and the scripted driver go into a new single-area `Demonstration.unity`, so "an unedited prefab trains exactly as feature 008 left it" holds by construction rather than by a default value. Passes |
| **V. Design-First** | The delegation changes what heuristic mode means for `DrivingAgent`, and imitation is a trainer input the design does not yet describe. `DESIGN.md` 4.5 and 5 gain the warm start, the demonstration source, and the substitution of `HeuristicDriver` for the BC policy **before any code task starts**. Task ordering enforces it. Passes |
| **VI. Reproducibility** | The `.demo` is committed through LFS (R9) alongside its seed list and recording procedure, so the run reproduces from a clean clone rather than from a procedure someone re-executes. Every run gets a unique id and an `EXPERIMENTS.md` row in the same session. Passes |
| **VII. Dataset Discipline** | The image dataset does not enter this feature, and this feature is where the project states plainly that it cannot: the BC policy reads camera images and the agent reads a 19 value vector, so there is no shared observation space. Passes |
| **VIII. Test Gates** | **Two** properties are testable without a scene, not three: the emitted pair is clamped to the action range, and exactly one component may write `ScriptedMove`. That heuristic mode emits the driver's command rather than zeros needs a scene, because the test assembly cannot name `DrivingAgent` or `ActionBuffers`; it is checked by driving a seed in Phase 3 and the test file says so. The trainer's own `demo_to_buffer` shape check (R7) is a third, free, at load time. Passes with the reduction recorded |
| **IX. Statistical Rigor** | The gate is named on every comparison and its caveat restated rather than dropped. The end-reason mix is read as a whole rather than by its wall share alone, which is the trap feature 008 named. A result landing near the gate earns a fresh three-run spread rather than a verdict. Passes |

**Two violations recorded rather than hidden.**

Feature 007 closed with **SC-007 not met**: the seven reward terms sum to the trainer's cumulative
reward on 4.8 per cent of rows, from an episode-set mismatch of about 19 per cent. This feature
inherits that defect, does not worsen it and does not fix it. FR-009 is the response: every claim
rests on behavioural counts taken Unity-side rather than on the reward decomposition.

Research R5 found that the recorded demonstration pairs each observation with the **previous**
decision's command, an 80 ms shift at `DecisionPeriod: 4`. It is a property of ML-Agents, it is not
configurable without patching `Library/PackageCache`, and patching that is not reproducible from a
clean clone. Recorded in Complexity Tracking.

### Declared file ownership (Principle IV)

Modified:

- `DESIGN.md` sections 4.5 and 5 - the warm start, why the demonstration source is
  `HeuristicDriver` and not the BC policy, and the imitation loss as a trainer input rather than a
  reward signal. **Committed before any code task starts**
- `unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs` - the `Heuristic` callback and its
  rewritten XML comment
- `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs` - `Decide()` visibility only, and
  the comment saying who else calls it. No change to the control law
- `config/ppo_car.yaml` - the `behavioral_cloning` block and nothing else
- `.gitattributes` - `*.demo` added to the LFS patterns (R9)
- `results/EXPERIMENTS.md` - one row per run
- `results/rl/` - the demonstration measurement, the curves, the held-out rows

Added:

- `results/rl/demo_seeds.json` - the committed training-seed list the demonstration was recorded
  from (FR-003)
- `unity/SelfDrivingSim/Assets/Demonstrations/*.demo` - the demonstration file itself, through LFS
- `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicCommand.cs` - a plain static class holding
  the two parts of the delegation that are testable without a scene: the clamp into the action
  space, and FR-002 as a predicate. **It exists because `SelfDrivingSim.EditModeTests` does not
  reference ML-Agents**, so a test cannot name `DrivingAgent` or `ActionBuffers`; feature 008 hit
  this and answered it with `WallTerminal`, and `RewardModel` is the same pattern older
- `unity/SelfDrivingSim/Assets/Tests/EditMode/HeuristicCommandTests.cs` - five cases over those two
- `unity/SelfDrivingSim/Assets/Scenes/Demonstration.unity` - **a new single-area scene, added
  because research R10 found that no existing object carries both `DrivingAgent` and
  `HeuristicDriver`**. One `TrainingArea` instance, the driver on the `Car` object with `ring`,
  `placer` and `track` wired explicitly rather than resolved by `FindAnyObjectByType`, and the
  `DemonstrationRecorder`

Not touched, and this is a requirement rather than an expectation: `RewardModel.cs`,
`WallTerminal.cs`, `WallSensor.cs`, `CarAgent.cs`, `CarController.cs`, `RayControllers.cs`,
`TrackBuilder.cs`, `CheckpointRing.cs`, `TrackProgress.cs`, `StartPlacer.cs`, `SweepRunner.cs`,
`vehicle_profile.json`, `results/tracks/seed_split.json`, the `hyperparameters` block of
`config/ppo_car.yaml`, **`TrainingArea.prefab` and `Scenes/Training.unity` and
`Scenes/Evaluation.unity`** (R10 moved the recorder into its own scene, so the training path is
not edited at all), and everything under `specs/003-*` through `specs/008-*`.

## Project Structure

### Documentation (this feature)

```
specs/009-imitation-warm-start/
├── spec.md          the hypothesis, stated so it can fail
├── plan.md          this file
├── research.md      R1 to R9, including the recorded-pair lag that reshaped the design
├── data-model.md    the demonstration set, the trainer block, the measures
├── quickstart.md    how to record, how to run, how to read it
└── tasks.md         the ordered work
```

### Source Code (repository root)

```
unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs      the delegation
unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs   Decide() visibility
unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicCommand.cs  the testable parts
unity/SelfDrivingSim/Assets/Tests/EditMode/                    five cases over them
unity/SelfDrivingSim/Assets/Scenes/Demonstration.unity         the recording scene (R10)
unity/SelfDrivingSim/Assets/Demonstrations/                    the .demo, through LFS
config/ppo_car.yaml                                            behavioral_cloning
results/EXPERIMENTS.md                                         one row per run
results/rl/                                                    demo measurement, curves, eval rows
```

## Phases

**Phase 0, research.** Done, in `research.md`. R5 and R8 changed the design. R5 means the recorded
pair carries a one-decision lag that is accepted and written down; R8 means `steps` and
`samples_per_update` are explicit decisions rather than defaults, because the default applies the
imitation loss for the entire run.

**Phase 1, the design writeback.** `DESIGN.md` 4.5 and 5 gain the warm start and the substituted
demonstration source. Principle V, and it blocks every code task.

**Phase 2, the delegation and its tests.** `Decide()` becomes callable, `Heuristic` calls it, the
XML comment is rewritten, `SetEngaged(false)` keeps `HeuristicDriver` off `ScriptedMove` while the
agent drives (R6). EditMode properties for all three.

**Phase 3, the cadence gate.** Drive N training seeds with the behaviour type set to heuristic and
measure lap completion **at the agent's decision cadence**, against feature 005's 34 of 34, in
`Immediate` reaction mode with the mode stated (R4). Read speed tracking alongside lap counts,
because R3 says that is where a collapse would come from. **This gate can cancel the feature, which
is why nothing is recorded in bulk before it.**

**Phase 4, the demonstration set.** Build `Demonstration.unity` first, because R10 found no
existing object carries both components and the twelve-area training scene would give twelve
drivers each bound to an arbitrary area's track. Then record from training seeds only, commit the
seed list, commit the `.demo` through LFS, and record its episode count, step count and file size.

**Phase 5, the candidate run.** `behavioral_cloning` added and nothing else changed from
`ppo_car_007_progress`, seed 42, 5,000,000 steps. `steps`, `strength` and `samples_per_update`
chosen and written into `EXPERIMENTS.md` **before** the run, not tuned after seeing the result.
`Losses/Pretraining Loss` is checked non-zero early, which is the cheap proof the warm start is
actually applied rather than silently absent (R7).

**Phase 6, the held-out evaluation.** The standard sweep, ten held-out seeds, both inference modes
reported separately and never averaged. The 80 per cent bar recorded met or not met with its
number, and `lapsToComplete: 3` stated wherever a lap count appears.

**Phase 7, the M3 closeout.** Not just this feature's closeout. The scope decision above means M3
ends here, so this phase writes the milestone's outcome into `DESIGN.md`, names what the four
features between them established and what they eliminated, and hands off to M5 rather than to a
feature 010.

## Post-Design Constitution Re-Check

The design adds no new component under `Assets/Scripts` and no new field to `DrivingAgent`. It
changes one method body, one method's visibility, one YAML block and one LFS pattern, and it adds a
stock ML-Agents component to a **new** scene rather than to the training prefab. Principle IV's
scene lock is therefore not touched at all on the training path, which is stronger than the first
draft of this plan claimed. Principle V is satisfied by ordering rather than by intention:
Phase 1 blocks Phase 2. **Re-check passes.**

## Complexity Tracking

| Cost | Why it is accepted |
|---|---|
| The demonstration pairs each observation with the previous decision's command, an 80 ms shift (R5) | Not configurable without patching a package under `Library/PackageCache`, which a clean clone would not reproduce. It is the pairing every ML-Agents imitation example trains on, and it does not touch the Phase 3 lap measurement, which drives from the action decided on the same step. Named as the first suspect if the imitation loss falls while behaviour does not follow it |
| The feature inherits feature 007's unresolved SC-007 accounting defect | Fixing it needs per-episode records, which feature 007 named as its own separate feature. FR-009 keeps every claim on Unity-side counts, so the defect does not touch the verdict |
| `HeuristicDriver.Decide()` loses `private` | The alternative is duplicating the control law, which is what the existing XML comment refuses and what would give the M5 comparison two answers. A visibility widening keeps one implementation; the comment is rewritten to name the second caller |
| The imitation loss iterating the whole demonstration buffer per update is a throughput cost (R8) | `samples_per_update` is set explicitly rather than left at 0, and SC-009 re-measures throughput against 903 and 927 steps per second rather than assuming it held |
| A new scene has to exist for recording, because no object carries both components (R10) | The alternative is adding `HeuristicDriver` to `TrainingArea.prefab`, where `Awake` resolves the ring, the placer and the track with `FindAnyObjectByType` and twelve areas would give eleven drivers bound to the wrong track. A single-area scene costs one file and removes the ambiguity entirely, and it leaves the training prefab byte-identical |
| The 34 of 34 baseline's reaction mode is not recorded in any committed CSV (R4) | Phase 3 re-establishes the number in the mode actually used and states the mode, so the comparison rests on a measurement made in this feature rather than on an inherited figure whose configuration is undocumented |
