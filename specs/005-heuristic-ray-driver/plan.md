# Implementation Plan: Heuristic Ray-Following Driver

**Branch**: `005-heuristic-ray-driver` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-heuristic-ray-driver/spec.md`

## Summary

A scripted driver that reads the thirteen ray distances `CarAgent` already produces and writes
`CarController.ScriptedMove`. No new sensing, no model, no training.

It is built in two stages so the design decision is measured rather than asserted: the naive
controller that steers toward the single longest ray, the recorded evidence of how it behaves, and
then the distance-weighted average that replaces it. Longitudinal control is part of the driver
rather than an extra, because the grip limit caps cornering at 6.39 m/s on the generator's tightest
radius against a 10 m/s top speed, so flat throttle understeers into a barrier.

Beyond the driver, two deliverables. It is a non-learned baseline for the M5 comparison, so
"PPO completes laps" can be distinguished from "this track is easy". And it is a fast instrument
for testing the sensing geometry, where a full sweep costs minutes rather than the hours the same
question would cost in PPO runs.

## Technical Context

**Language/Version**: C# (Unity 6000.5.3f1) for the driver and the sweep runner; Python 3.10.11 for
the reporting and the sensing export
**Primary Dependencies**: none added. The driver uses `CarAgent`, `CarController`, `CheckpointRing`
and `DriveLogger`, all from feature 003. Reporting uses the existing `.venv` (numpy, pandas, scipy)
**Storage**: `results/heuristic/` for run records and sweep reports, plain CSV and Markdown.
`unity/SelfDrivingSim/Assets/Tracks/vehicle_profile.json` gains a `sensing` block
**Testing**: Unity EditMode tests for the two controllers, which are pure functions of a distance
array; `pytest` for the sensing mirror test and the report generation
**Target Platform**: Windows, Unity Editor. The sweep runs in the editor rather than a player build
(research R4)
**Project Type**: Unity simulation feature plus a Python reporting step, matching the existing
shape of feature 003
**Performance Goals**: one sensing configuration over all 34 training seeds in under five minutes
(SC-004). Measured budget: 19.4 min at real time, 2.4 min at 8x
**Constraints**: the driver may read only what a learning agent could read (FR-001). It runs on the
physics clock so runs reproduce (R6). It must not change the vehicle, the track generator, the
barriers or the checkpoint logic
**Scale/Scope**: 34 training seeds per configuration, two controllers, at least two sensing
configurations. One new Unity component, one sweep runner, one Python reporter, one exporter change

No NEEDS CLARIFICATION items remain. Every unknown the spec raised is resolved in
[research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| **I. Spec-Driven** | Spec written and merged before this plan. No code exists yet. Passes |
| **II. Git-Flow & Atomic Commits** | Branch `005-heuristic-ray-driver` off `develop`, matching `specs/005-heuristic-ray-driver/` as Principle II requires since v1.5.0. Merges back with `--no-ff`. Passes |
| **III. Human-Only Commits** | The repository owner has explicitly and repeatedly instructed that commits be run on his behalf, and reaffirmed it after being shown that this principle forbids it. Practice diverges from the written rule. **Flagged, not resolved: the clean fix is an amendment, which the owner has not requested.** No attribution trailers appear in any commit, which is the part of this principle still observed exactly |
| **IV. Multi-Agent Coordination** | Declared file ownership below. `Track.unity` is modified, and the scene lock requires no other active branch touch it; M2 is merged and no other feature is open. Passes |
| **V. Design-First** | The driver is an architectural addition and belongs in `DESIGN.md` before it is implemented. **Task ordering enforces this**: the DESIGN section is written first, in its own `docs:` commit. No em dashes, sparing bold, throughout |
| **VI. Reproducibility** | FR-011 is satisfied by measuring the run-to-run spread rather than asserting determinism (R6), following feature 004's R13. Seeds come from the committed split. The sensing configuration moves into a committed file so a run can be repeated from the repository alone |
| **VII. Dataset Discipline** | Not touched. This feature reads no dataset |
| **VIII. Test Gates** | Both controllers are pure functions of a distance array and get EditMode tests, including the tie and all-clear cases from R9. The sensing mirror test is `pytest`. `pytest` and EditMode must both be green before merge |
| **IX. Statistical Rigor** | This is where the feature earns marks and where it is most at risk. The two-controller comparison and the sensing sweep are both comparisons, and FR-015 requires a difference to be shown larger than run-to-run variation before it is called a finding. Descriptive statistics for every reported distribution, and the noise floor measured before any comparison is interpreted |

**No violations requiring justification**, with one flagged conflict on Principle III that is a
standing repository-level matter rather than something this feature introduces.

### Declared file ownership (Principle IV)

New:

- `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs`
- `unity/SelfDrivingSim/Assets/Scripts/Agent/RayControllers.cs`
- `unity/SelfDrivingSim/Assets/Scripts/Track/SweepRunner.cs`
- `unity/SelfDrivingSim/Assets/Tests/EditMode/RayControllerTests.cs`
- `python/heuristic/report.py`, `python/tests/test_heuristic_report.py`
- `python/tests/test_sensing_mirror.py`

Modified:

- `unity/SelfDrivingSim/Assets/Scenes/Track.unity` - adds the driver and the runner. **Scene lock
  applies.**
- `unity/SelfDrivingSim/Assets/Scripts/Agent/CarAgent.cs` - reads the sensing block instead of
  serialised constants. Values unchanged
- `python/track/vehicle.py` and `python/track/config.py` - export the sensing block
- `DESIGN.md` - a section for the heuristic driver, written before implementation

Not touched, and this is a requirement rather than an expectation: `CarController`,
`TrackBuilder`, `CheckpointRing`, the barrier geometry, and every file under `specs/003-*`.

## Project Structure

### Documentation (this feature)

```text
specs/005-heuristic-ray-driver/
├── plan.md              # This file
├── spec.md              # Written during feature 003, merged with it
├── research.md          # Phase 0, R1 to R9
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── run-record.md    # The per-run row every sweep writes
│   └── sensing-block.md # The new block in vehicle_profile.json
├── checklists/
│   └── requirements.md  # Written with the spec
└── tasks.md             # Phase 2, /speckit-tasks, not created here
```

### Source Code (repository root)

```text
unity/SelfDrivingSim/Assets/
├── Scripts/
│   ├── Agent/
│   │   ├── CarAgent.cs              # modified: loads the sensing block
│   │   ├── HeuristicDriver.cs       # new: the driver, owns control handover
│   │   ├── RayControllers.cs        # new: both strategies, pure static functions
│   │   ├── ObservationDebug.cs      # unchanged
│   │   └── ObservationProbe.cs      # unchanged
│   ├── Track/
│   │   └── SweepRunner.cs           # new: iterates seeds in one Play session
│   └── Vehicle/                     # unchanged
├── Tests/EditMode/
│   └── RayControllerTests.cs        # new
└── Tracks/
    └── vehicle_profile.json         # modified: gains a sensing block

python/
├── track/
│   ├── config.py                    # modified: sensing constants exported
│   └── vehicle.py                   # modified: writes the sensing block
├── heuristic/
│   └── report.py                    # new: reads run records, writes the comparison
└── tests/
    ├── test_sensing_mirror.py       # new
    └── test_heuristic_report.py     # new

results/heuristic/                   # new: run records and sweep reports
```

**Structure Decision**: the feature follows feature 003's split exactly. Simulation logic in C#
under `Assets/Scripts/`, with the control policy in `Agent/` because it is a policy over the
observation vector and must not reach into `Track/` (FR-001). Analysis and reporting in Python
under `python/`, because that is where every other comparison in this project is computed and
because the M5 comparison will consume this output alongside the others.

`RayControllers.cs` is separate from `HeuristicDriver.cs` on purpose. The two strategies are pure
functions from a distance array to a steering command, which is what makes them EditMode testable
without a scene, a car or a physics step. Mixing them into the MonoBehaviour would put the one
piece of logic worth testing behind everything that makes testing hard.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1. No new violations.

- **Principle V** is the one the design changed. Exporting the sensing block and having `CarAgent`
  read it is an architectural change, not an implementation detail, so it goes into `DESIGN.md`
  with the rest of the section rather than arriving as a surprise in a diff.
- **Principle VI** is strengthened rather than threatened: moving the sensing constants into a
  committed file means a run can be reproduced from the repository, which was not previously true
  of a scene-edited ray count.
- **Principle IX** gained a concrete obligation during Phase 1. `contracts/run-record.md` fixes the
  per-run fields, and the reporter must produce descriptive statistics over the seed set rather
  than a single seed's outcome, because FR-012 and Principle IX both say the same thing from
  different directions.
- **Principle VIII** is satisfiable in full only because `RayControllers` is separated out. Had the
  strategies lived inside the MonoBehaviour, the honest position would have been that the logic is
  covered by play-mode observation rather than by tests.

## Complexity Tracking

> No Constitution Check violations require justification.

One item is worth recording as deliberate rather than accidental complexity:

| Choice | Why | Simpler alternative rejected because |
|---|---|---|
| `CarAgent` loads its sensing from `vehicle_profile.json` rather than keeping serialised fields | FR-013 needs the arrangement variable for the sweep and FR-016 needs the two copies to agree. One change satisfies both by construction | Keeping the fields and adding a test that reads the scene YAML would detect drift without preventing it, and would break every time the scene is re-serialised. Keeping the fields and varying them by hand per sweep configuration would make a 34-seed sweep a manual scene edit, which defeats SC-004 |
