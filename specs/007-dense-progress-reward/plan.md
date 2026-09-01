# Implementation Plan: Dense Progress Reward

**Branch**: `007-dense-progress-reward` | **Date**: 2026-08-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-dense-progress-reward/spec.md`

## Summary

One new reward term, and everything else in the feature exists to prove that the term is what it
claims to be.

The term is the weighted change, between consecutive physics steps, in the car's arc position along
the chain of 24 checkpoint markers. Written that way it telescopes, so its sum over a trajectory is
the difference between the endpoints and nothing else. That is what makes it safe to add a dense
signal to a table whose anti-farming invariant was argued carefully in `DESIGN.md` 4.5: a loop
earns zero by construction rather than by a weight chosen small enough.

The arc position is clamped at the marker the checkpoint ring says is due next, so the shaping
cannot pay for a shortcut the ring refuses to award. It is unwrapped across the finish line, so
there is no special case on the one step per lap where a naive reset would charge a whole lap's
penalty. Its weight is derived from the measured chain length so that a lap of progress pays 12.0
against the 24.0 a lap of markers already pays, which keeps the marker term the larger signal and
leaves the existing invariant's arithmetic untouched.

The measurement discipline is feature 006's, with one correction it forced. Cumulative reward is
not comparable across the two tables, because adding a term changes the scale of the total, so this
feature gates on behavioural metrics and re-measures the run-to-run spread on those metrics rather
than reusing the 0.19 gate that was measured on cumulative reward.

The feature also closes the one item feature 006 left open. The trainer's episode length and the
count of per-step reward charges disagreed by about 3.16 with a maximum of 4.01, and
`TrainingArea.prefab` sets `DecisionPeriod: 4`. The ratio is the decision period; what remains is
to account for the shortfall below the ceiling, which R6 instruments.

## Technical Context

**Language/Version**: C# (Unity 6000.5.3f1) for the reward term, the arc geometry and the agent
wiring; Python 3.10.11 in `.venv-mlagents` for the trainer and `.venv` for the reporting that joins
this run to the existing columns
**Primary Dependencies**: `com.unity.ml-agents` 4.0.3, `com.unity.ai.inference` 2.6.1, `mlagents`
1.1.0, Communicator API 1.5.0. No new dependency is introduced by this feature
**Storage**: `config/ppo_car.yaml` unchanged and reused, because R10 holds every hyperparameter at
its 006 value; `results/rl/` for the committed curve exports and evaluation records;
`results/<run-id>/` for raw trainer output, git-ignored apart from the exported model
**Testing**: Unity EditMode for the arc geometry and the reward terms, which stay pure functions;
`pytest` for the curve export and the report, extended rather than replaced
**Target Platform**: Windows, Unity Editor connected to `mlagents-learn`, the same as feature 006
**Project Type**: Unity simulation change plus a Python reporting step
**Performance Goals**: the term is one projection onto one polyline segment per physics step, so
the throughput target is simply that it does not move: 684 steps/s was measured in 006 and a
regression below about 600 is a defect to investigate rather than a cost to accept
**Constraints**: FR-014 freezes the observation vector, the action space, the 13/180/20 ray
geometry, the vehicle profile and the track generator. The reward terms must remain pure functions
(FR-022). The checkpoint ring is read and not modified
**Scale/Scope**: one new C# component for the arc geometry, one new term in an existing pure
static class, one field in an existing breakdown struct, one `DESIGN.md` section rewritten, three
identical spread runs plus one candidate run plus one evaluation sweep

No NEEDS CLARIFICATION items remain. Every unknown is resolved in [research.md](./research.md),
R1 to R10.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Spec-Driven** | Spec written before this plan; no code exists on this branch. The branch, the spec directory and `.specify/feature.json` all name `007-dense-progress-reward`. Passes |
| **II. Git-Flow & Atomic Commits** | Branch `007-dense-progress-reward` off `develop`, merged back with `--no-ff`. The `exp` commit type carries the training runs, as it did in 006. Passes |
| **III. Human-Only Commits & Reviewed Handoffs** | The default stands: the agent prepares changes and stops, and commits only on an explicit instruction that covers the work in front of it. No `Co-Authored-By`, no session URL, no tool trailer, in commits, in pull request bodies or in `EXPERIMENTS.md`. Every handoff carries the explain-and-review step. Passes |
| **IV. Multi-Agent Coordination** | File ownership declared below. **No scene and no prefab is edited except `TrainingArea.prefab`, and that only if the arc component cannot be attached at runtime**, which the plan prefers precisely to keep the scene lock uncontested. Passes |
| **V. Design-First** | This feature's entire premise is a change to the reward table, so `DESIGN.md` 4.5 is rewritten before any code: the potential, the unwrapping, the clamp, the derived weight, and the restated anti-farming invariant. Task ordering enforces it, and no code task may start before it lands. Passes |
| **VI. Reproducibility** | `config/ppo_car.yaml` is reused unchanged, so the one change is in the C# table and is visible in the diff. Every run gets a unique id and an `EXPERIMENTS.md` row in the same session. The chain length is computed from the committed track seeds, so the derived weight reproduces from a clean clone. Passes |
| **VII. Dataset Discipline** | The image dataset does not enter this feature. No number is taken from it. Passes |
| **VIII. Test Gates** | The two properties this feature rests on are testable without a scene: the term telescopes, and a loop sums to zero. Both are EditMode assertions over pure functions with a stated tolerance (R9). The shortcut clamp and the episode-reset clearing are also EditMode tests. Passes |
| **IX. Statistical Rigor** | The spread is re-measured on the metrics this feature gates on, because the 006 gate was measured on a quantity FR-018 now forbids comparing. The learned column keeps the same `python.eda.stats.describe` treatment and the same comparison against the human distribution as 006, with 006's caveat about the saturated chi-squared test carried forward rather than dropped. Passes |

**No violations requiring justification.** One deliberate cost is recorded in Complexity Tracking:
this feature adds a component that reads the checkpoint ring's markers without owning them, which
is a second reader of a structure feature 003 owns.

### Declared file ownership (Principle IV)

New:

- `unity/SelfDrivingSim/Assets/Scripts/Track/TrackProgress.cs` - the arc geometry. Segment lengths
  computed once per track build, projection of a position onto the chain, the clamp at the due
  marker, and the unwrapping across the finish. Reads `CheckpointRing`, owns none of it
- `unity/SelfDrivingSim/Assets/Tests/EditMode/TrackProgressTests.cs` - telescoping, the loop
  property, the clamp, the lap boundary, and the reset
- `results/rl/progress_spread.md` - the re-measured noise floor for this feature's metrics

Modified:

- `DESIGN.md` section 4.5 - the new table, the potential, the derivation of the weight, the
  restated invariant. **Written and committed before any code task starts**
- `unity/SelfDrivingSim/Assets/Scripts/Agent/RewardModel.cs` - one new constant, one new pure
  function, one new field in `Breakdown` and its `Total`. The six existing terms keep their names,
  their values and their meanings
- `unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs` - holds the previous arc position,
  charges the term, clears the position on episode begin, and reports the new term to the trainer
  statistics alongside the existing six
- `unity/SelfDrivingSim/Assets/Scripts/Track/TrainingArea.cs` - the swap path routes through the
  episode-begin reset rather than around it (R7)
- `unity/SelfDrivingSim/Assets/Tests/EditMode/RewardModelTests.cs` - the restated anti-farming
  invariant, and the new term's presence in the breakdown sum
- `python/rl/export_curves.py` and `python/rl/report.py` - the new statistics key, and the
  behavioural metrics this feature gates on
- `python/tests/test_rl_curves.py`, `python/tests/test_rl_report.py` - coverage for the above
- `results/EXPERIMENTS.md` - one row per run
- `README.md` - only if a command or a file name changes, which the plan expects it will not

Not touched, and this is a requirement rather than an expectation: `CarAgent.cs`,
`CarController.cs`, `TrackBuilder.cs`, `CheckpointRing.cs`, `StartPlacer.cs`, `SweepRunner.cs`,
`HeuristicDriver.cs`, `ScriptedDriver.cs`, `RayControllers.cs`, `vehicle_profile.json`,
`config/ppo_car.yaml`, `results/tracks/seed_split.json`, and everything under `specs/003-*`,
`specs/004-*`, `specs/005-*`, `specs/006-*`.

## Project Structure

### Documentation (this feature)

```text
specs/007-dense-progress-reward/
├── plan.md              # This file
├── spec.md              # Phase -1
├── research.md          # Phase 0, R1 to R10
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── progress-reward.md  # the term, its inputs, its invariants and its stats key
└── tasks.md             # Phase 2
```

### Source Code (repository root)

```text
unity/SelfDrivingSim/Assets/
├── Scripts/
│   ├── Agent/
│   │   ├── DrivingAgent.cs          # modified: previous position, charge, reset, stats
│   │   ├── RewardModel.cs           # modified: one constant, one function, one field
│   │   └── CarAgent.cs              # unchanged
│   └── Track/
│       ├── TrackProgress.cs         # new: arc position, clamp, unwrap
│       ├── TrainingArea.cs          # modified: swap routes through episode begin
│       ├── CheckpointRing.cs        # unchanged, read only
│       └── TrackBuilder.cs          # unchanged
├── Prefabs/
│   └── TrainingArea.prefab          # touched only if the component cannot be added at runtime
└── Tests/EditMode/
    ├── TrackProgressTests.cs        # new
    └── RewardModelTests.cs          # modified

python/
├── rl/
│   ├── export_curves.py             # modified: the new stats key
│   └── report.py                    # modified: the behavioural metrics
└── tests/
    ├── test_rl_curves.py            # modified
    └── test_rl_report.py            # modified

results/
├── rl/progress_spread.md            # new: the re-measured noise floor
└── EXPERIMENTS.md                   # modified: one row per run

DESIGN.md                            # modified: 4.5, before any code
config/ppo_car.yaml                  # unchanged, and that is the point
```

**Structure Decision**: the split feature 006 established is kept. The arc geometry goes under
`Track/` rather than under `Agent/`, because it is a property of the track and the car's position on
it, and nothing about it is specific to a learning agent. That placement is what would let a later
feature use the same arc position for a curriculum without touching the reward.

`TrackProgress.cs` is separate from `RewardModel.cs` for the reason feature 006 separated
`RewardModel` from `DrivingAgent`: the reward terms stay pure functions of numbers, and the geometry
that produces those numbers is testable on its own against a polyline it can be handed in a test.
A reward that can only be checked by watching a car drive is a reward nobody can check.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1. No new violations.

- **Principle V** carries more weight in this feature than in any before it, because the change
  *is* a design change and there is nothing else in the feature. `DESIGN.md` 4.5 gains the
  potential, the unwrapping, the clamp and the weight derivation, and the anti-farming invariant is
  restated rather than deleted, the same way 006 restated it when `SpeedReward` moved.
- **Principle VIII** is satisfiable because R1's choice of potential made it so. Distance to the
  next marker, the option rejected in R1, would have had no testable telescoping property at all,
  and the feature's central claim would have rested on prose.
- **Principle IX** met a real conflict and resolved it in R8. The obvious move is to reuse the
  0.19 gate, and it is wrong: that gate was measured on cumulative reward, which FR-018 forbids
  comparing across the two tables. The gate is re-measured on the behavioural metrics, which costs
  three more runs and is the only version of the comparison that means anything.
- **Principle VI** gained a small obligation from R5. The weight depends on the chain length, which
  differs between generated tracks, so the weight is computed at track build rather than stored as
  a literal. The derivation, not the number, is what reproduces.

## Complexity Tracking

> No Constitution Check violations require justification.

| Deliberate cost | Why | Alternative rejected because |
|---|---|---|
| A second reader of `CheckpointRing`'s marker list | The arc geometry needs the ordered markers and the index of the next due marker, both of which the ring already exposes as public read-only surface | Duplicating the marker list into the new component would make two sources of truth for what "forward" means, which is exactly the disagreement R1 rejected the centre-line option to avoid |
| Three extra training runs before any candidate is judged | R8: the 006 gate was measured on a quantity this feature may not compare | Reusing the 0.19 gate would make every comparative claim in this feature unbacked, which Principle IX forbids and which the M3 closeout was careful to avoid |
