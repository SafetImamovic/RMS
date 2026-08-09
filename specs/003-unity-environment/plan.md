# Implementation Plan: Unity Driving Environment (M2)

**Branch**: `feature/unity-environment` | **Date**: 2026-07-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-unity-environment/spec.md`

## Summary

Build the environment the reinforcement-learning agent will later live in, in three slices.
First a car on a flat plane, drivable by keyboard, whose every limit is derived from a statistic
measured in M1. Then a track generator that produces closed loops from an integer seed, with
curvature sampled so the steering needed to follow each track matches the human steering
distribution, and with a hard floor on corner tightness. Finally the sensing and progress
tracking the agent will need, verified by hand while a person drives.

The technical approach splits along a reproducibility line. Everything statistical happens in
Python, where it is testable with pytest and reuses the M1 and feature 002 code: seed to
coefficients, coefficients to centre line, curvature to required steering, distribution distance,
acceptance or rejection. The output is a committed JSON file per accepted seed. Unity reads that
file and builds geometry from it. Unity therefore contains no statistics and no randomness, only
construction, which keeps the part that is hard to test out of the part that needs proving.

Nothing here trains. The deliverable is an environment a human can drive and whose measurements
have been checked one by one.

## Technical Context

**Language/Version**: Python 3.10.11 (generator, tests) and C# on Unity 6000.5.3f1 (scene,
vehicle, sensing)
**Primary Dependencies**: numpy, scipy, matplotlib, pytest, already pinned in
`python/requirements.txt` with no additions. Unity side: `com.unity.ml-agents` 4.0.3 already in
the manifest, plus `com.unity.splines` and ProBuilder to be added through Package Manager
**Storage**: committed JSON track files under `unity/SelfDrivingSim/Assets/Tracks/`; drive logs
written to `results/drive_logs/`
**Testing**: pytest for the generator and all geometry validation; Unity EditMode tests for
checkpoint ordering and for revalidating built geometry against the JSON it came from
**Target Platform**: Windows 11, Unity Editor, single machine
**Project Type**: simulation environment plus a Python geometry library
**Performance Goals**: track generation for 40 seeds in under 30 seconds; the scene runs at a
stable step rate with at least 8 parallel environment copies, since that is what makes the next
milestone's training practical
**Constraints**: no third-party marketplace content; no image data enters this environment; every
number traceable to a measured statistic or a stated geometric assumption; identical output for
identical seeds
**Scale/Scope**: one vehicle, one plane scene, one track scene, roughly 200 m of track per seed,
24 progress markers per track, 13 distance readings per step

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Spec-Driven Development | PASS. spec.md exists and is validated, 16 of 16 checklist items. This plan precedes any code. |
| II. Git-Flow & Atomic Commits | PASS. Branch is `feature/unity-environment`, branched from `develop`, per the `feature/<kebab-desc>` rule. The setup script's numbered form is again not used, same as the two previous features. |
| III. Human-Only Commits | PASS. No git command in this feature is run by an agent. The branch was created by the owner. Every commit is proposed, never executed. |
| IV. Multi-Agent Coordination | PASS with a note. File ownership is declared below. The scene-lock rule becomes real for the first time here, because this is the first feature that touches `.unity` files. |
| V. Design-First Documentation | PASS. DESIGN sections 4.1 to 4.5 already fix the observation set, the action space and the checkpoint range. Where this plan settles something DESIGN left open, it is written back to DESIGN in a `docs:` commit before implementation. |
| V. Writing style (added in 1.3.0) | PASS. No em dashes in any artifact of this feature. Bold used only where it carries the sentence. |
| VI. Reproducibility & Determinism | PASS. Seeds fully determine geometry; track JSON is committed so a track can be rebuilt without rerunning the generator; no new dependency versions. |
| VII. Dataset Discipline | PASS. No image data reaches this environment. The agent senses distances and its own state only, which is the separation the whole RL versus BC comparison rests on. |
| VIII. Test Gates Before Merge | PASS. pytest for the generator, Unity EditMode tests for checkpoint order and geometry, and the blunt rule from WORKFLOW section 5: no keyboard lap, no training. |
| IX. Statistical Rigor | PASS, and it is the point of the feature. The curvature target is the empirical steering distribution measured in M1. FR-019 forbids dressing the match up as a hypothesis test. |

No violations. Complexity Tracking is therefore omitted.

### Note on Principle IV, scene lock

This is the first feature to create `.unity` and `.prefab` files, which git cannot merge safely.
Two scenes are created, `FlatGround.unity` for User Story 1 and `Track.unity` for User Stories 2
and 3. While this branch is open, no other branch may modify either. Logic lives in C# scripts,
which merge fine; the scenes stay as thin as possible, holding references and nothing else.

## Project Structure

### Documentation (this feature)

```text
specs/003-unity-environment/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── track-generator-api.md   # Python generator contract
│   └── track-file-schema.md     # the JSON handoff between Python and Unity
├── checklists/
│   └── requirements.md  # already written and passing
└── tasks.md             # Phase 2 output, not created by /speckit-plan
```

### Source Code (repository root)

```text
python/
├── track/                       # NEW. All geometry and statistics for this feature
│   ├── __init__.py
│   ├── config.py                # vehicle profile and generator constants, all named
│   ├── vehicle.py               # steering to radius, radius to steering, stopping distance
│   ├── generator.py             # seed to coefficients to centre line
│   ├── geometry.py              # curvature, closure, self-intersection, separation
│   ├── matching.py              # required-steering distribution and distance to the dataset
│   └── export.py                # write and validate the track JSON
├── tests/
│   ├── test_vehicle.py          # NEW
│   ├── test_generator.py        # NEW
│   ├── test_geometry.py         # NEW
│   └── test_matching.py         # NEW
└── eda/                         # UNCHANGED. Read only, for the measured distribution

unity/SelfDrivingSim/Assets/
├── Scenes/
│   ├── FlatGround.unity         # NEW. User Story 1
│   └── Track.unity              # NEW. User Stories 2 and 3
├── Scripts/
│   ├── Vehicle/
│   │   ├── CarController.cs     # limits applied, keyboard input
│   │   └── VehicleProfile.cs    # the limits themselves, mirrored from python/track/config.py
│   ├── Track/
│   │   ├── TrackFile.cs         # read the JSON
│   │   ├── TrackBuilder.cs      # build surface, barriers and markers from it
│   │   └── CheckpointRing.cs    # ordering, wrong-way detection
│   ├── Agent/
│   │   ├── CarAgent.cs          # observations and actions only, no reward shaping yet
│   │   └── ObservationDebug.cs  # live display of every observation
│   └── Logging/
│       └── DriveLogger.cs       # write a drive log in the dataset's own columns
├── Tests/
│   └── EditMode/
│       ├── CheckpointOrderTests.cs
│       └── TrackGeometryTests.cs
└── Tracks/
    └── seed_XXXX.json           # committed, one per accepted seed

results/
└── drive_logs/                  # keyboard drive logs, for comparison against the dataset
```

**Structure Decision**: the statistical half lives in `python/track/` and the construction half in
`unity/.../Scripts/`, joined by a committed JSON file. This is not an arbitrary split. Unity code
cannot be exercised by pytest and is slow to test at all, so nothing that needs proving belongs
there. Conversely a Python process cannot build a mesh. Putting the seed, the coefficients, the
curvature check and the distribution match in Python means every claim this feature makes is
covered by a test that runs in under a second, and the Unity side is reduced to reading numbers
and placing objects, which either visibly works or visibly does not.

### Declared file ownership (Principle IV)

Created by this feature: everything marked NEW above, plus the two scenes.
Modified by this feature: `DESIGN.md` sections 4.1 to 4.5, writing back the values this plan
settles; `unity/SelfDrivingSim/Packages/manifest.json` for two package additions;
`python/requirements.txt` only if a dependency turns out to be missing, which is not expected.
Not touched: `python/eda/` in any way, `results/eda/`, anything under `specs/001` or `specs/002`.

## Phase 0 preview

Thirteen decisions are resolved in [research.md](research.md), covering the vehicle profile and
its radius table, the speed normalisation protocol, the steering rate, the instability trigger,
the generator's functional form and coefficient bounds, the curvature matching procedure and its
distance measure, the self-intersection and separation tests, the sensing range, the marker count,
the start randomisation, the seed protocol, the rate-matching protocol between the dataset and the
simulation, and where every artifact lives.

Two of those decisions produce findings that change how a later milestone must be read, and both
are recorded rather than buried:

1. The safety margin on the corner radius is exactly the agent's steering reserve, and it caps
   the steering any generated track can demand. At the chosen margin of 1.3, no track can require
   more than 0.789 of full lock, while the human data reaches 1.0. Generated tracks therefore
   cover the human distribution up to roughly its 97th percentile and no further. The result is
   independent of wheelbase, which makes the margin the only knob that controls it.
2. A closed curve built from radial harmonics has no straight sections, while the human data is
   58.6 percent exactly zero steering. Any comparison of raw steering histograms between agent
   and human will be dominated by that difference in track topology rather than by driving. This
   reinforces the note already written into DESIGN section 7.

## Post-design Constitution re-check

Re-evaluated after Phase 1. Still no violations. The one item worth restating is Principle IX:
the distribution match in `matching.py` returns a distance and an acceptance decision against a
stated threshold, and the contract explicitly forbids reporting it as a p-value. That constraint
exists because feature 002 was written to correct exactly that error, and repeating it in the
very next feature would undo the correction.
