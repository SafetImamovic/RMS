# Tasks: generalisation beyond the ten held-out tracks

**Feature**: `011-generalisation-beyond-ten` | **Spec**: `spec.md` | **Plan**: `plan.md`
**Created**: 2026-09-02

## Format: `[ID] [P?] [Story] Description`

`[P]` marks tasks that touch no shared file and may be done in any order relative to each other.

## Four orderings this feature must not violate

Restated from `plan.md` because a task list is what gets read during work.

1. **The derived run label before the sweep.** Relabelling cannot be done retroactively.
2. **The seed set generated and committed before the sweep, and never regenerated.** Looked at once
   is the only property that makes it worth running.
3. **The scene reset verified from the run record, not from the Inspector.**
4. **The interval and the pre-registered reading before the numbers exist.**

---

## Phase 1: make the label trustworthy (US2)

- [X] T001 [US2] Derive the run label in `DrivingAgent` from `BehaviorParameters`: the model asset
      actually loaded and the inference mode actually in effect. This is what goes in the run
      record's controller column
  - `DerivedRunLabel()` returns `{model.name}_{deterministic|sampling}`, both read at runtime from
    `BehaviorParameters`. `RunRecord.Controller` now takes that and nothing else
  - Returns an explicit `(no model)` rather than a blank when the behaviour carries none, because an
    empty controller column reads as a missing field rather than as a run that had no policy. That
    case is real: it is what a heuristic-mode run looks like
- [X] T002 [US2] Demote the serialised `runId` to a cross-check. When it is set and disagrees with
      the derived label, log an error naming both. Do not silently prefer either
  - `AssertRunLabelAgrees()`, called from `Initialize` beside the observation-size assertion. An
    empty `runId` is not a disagreement, it is unused
  - **The derived label wins and the error says so**, because a row has one controller column and a
    reader must not have to know which half to trust. The message states that the rows will be
    correct and the scene is what is wrong
- [X] T003 [P] [US2] Update the tooltip, which currently tells the reader to check by eye. The whole
      point of T001 is that nobody has to
  - The old text ended "nothing checks the two agree, so they are worth checking by eye". It now
    says the field is a cross-check the agent will contradict in the console
- [X] T004 [US2] Verify the compile from the assemblies and the console, not from the absence of a
      complaint. A missing project dll means the compile failed (this repository has been caught by
      that before)
  - **The first attempt did not compile, and only the assembly timestamp said so.** The MCP refresh
    call returned success, the console reported nothing, and `SelfDrivingSim.dll` kept its old
    timestamp. `Logs/Editor.log` held the reason: `error CS0012: The type 'ModelAsset' is defined in
    an assembly that is not referenced`
  - `BehaviorParameters.Model` is a `ModelAsset` from `Unity.InferenceEngine`, and
    `SelfDrivingSim.asmdef` referenced only `Unity.InputSystem` and `Unity.ML-Agents`. The package
    was already a project dependency, listed in `DESIGN.md` 8 as `com.unity.ai.inference` 2.6.1; it
    was simply not referenced by this assembly. Added
  - After the fix: `SelfDrivingSim.dll` rebuilt at 18:42, grew from 157,696 to 158,720 bytes,
    console holds zero errors and zero warnings. **The timestamp is the check, not the console**
**Checkpoint**: a run record row can prove which policy produced it.

## Phase 2: the third seed set (US1)

- [X] T005 [US1] Add `GENERALISATION_SEEDS = range(2001, 2041)` to `python/track/config.py` and a
      batch name that produces it, through the existing generator and the existing acceptance bound.
      **No parameter changes** (FR-002)
- [X] T006 [US1] Generate the batch, record every rejection with its reason, and **do not retry a
      rejected seed** (FR-003)
  - **33 of 40 accepted, a rate of 0.825** against training's 0.85 on the same floor. Seven
    rejected, all for the same reason and each recorded with its measured radius: 2002, 2004, 2006,
    2013, 2021, 2024 and 2026 have a tightest corner below the 6.97 m floor
  - Seed 2013 missed by **0.06 m** (6.91 against 6.97) and was not retried, adjusted or nudged
- [X] T007 [US1] Write the accepted set into `results/tracks/seed_split.json` as a third half, and
      record its disjointness from both existing halves
  - `write_split` already handled an arbitrary number of sets pairwise, so this needed no change
    there. **Train and eval came back byte identical** after regenerating all three, which is the
    check that the generator is still deterministic and that nothing about them moved
- [X] T008 [P] [US1] A test that the three sets are pairwise disjoint, checked from the file rather
      than inferred from the seed ranges (FR-001, SC-001)
- [X] T009 [P] [US1] A test that every accepted seed has a track file under `Assets/Tracks/`
  - `python/tests/test_generalisation_split.py`, five tests. Two the task did not ask for: that no
    **rejected** seed left a track file behind, since a stale file would be a retry by accident, and
    that the acceptance rate still sits near training's, which is the visible consequence of the
    bound not having moved
- [X] T010 [US1] Check the pooled steering demand of the new set against the same bound both
      existing splits were held to, and record the figure
  - **0.695 against a human 1.000**, within bound. Training is 0.789 and held out is 0.738, so the
    new tracks are **easier** on this axis, not harder
  - Recorded in the pre-registration **before the sweep ran**, so a good result could not later be
    sold as "it generalises to harder tracks" and a bad one could not be excused
- [X] T011 [US1] Add the third `SeedSet` enum value and the third `SeedSplitFile` field to
      `SweepRunner`, and warn on sweeping it exactly as the evaluation set warns (FR-006, FR-007)
  - The warning is worded more strictly than the evaluation one: these tracks exist to be looked at
    once, so it names both misuses, choosing a configuration against them and re-running after a
    disappointing result
- [X] T012 [US1] Commit the seed set and the track files **before the sweep runs**. Ordering 2
  - Committed in `28b1ada`, 33 track files plus the split, before the scene was touched

**Checkpoint**: a set of tracks exists that nobody has looked at, and the sweep can address it.

## Phase 3: the interval, before the numbers (US3)

- [X] T013 [US3] Add a Wilson score interval to `python/eda/`
  - `python/eda/intervals.py`. `wald` is there too, and **only so the difference can be shown**:
    research R6 claims the normal approximation reports a zero-width interval at `p = 1`, and a
    claim about a method is worth more when the method is present and tested than when it is
    described. Nothing in this project reports `wald`
  - Kept out of `authenticity.py` because an interval is not a hypothesis test. That module's
    results carry `reject_null` and a p-value and neither means anything here
  - `overlaps` is on the type rather than at each call site, so no caller can compare two rates
    without the comparison the intervals were computed for
- [X] T014 [P] [US3] Tests pinning R6's worked table, plus the case the normal approximation gets
      wrong
  - **Ten tests.** R6's three rows, plus: that the normal approximation reports width zero on the
    same data, that a real separation is still reported as one so the overlap rule does not swallow
    every difference, that the interval stays inside [0, 1] at both ends, that no trials returns
    the whole range rather than a rate, and that the confidence level is derived from the z it was
    computed with rather than being a second literal that can drift
- [X] T015 [US3] Record the pre-registered reading from research R7 in `results/EXPERIMENTS.md`
      **before the sweep runs**
  - Committed in `28b1ada`, in the same commit as the seed set and before the scene was reset

**Checkpoint**: what each outcome will mean is written down and dated.

## Phase 4: the sweep and the result (US2, US3)

- [X] T016 [US2] Reset the evaluation scene
  - **Research R3 was right, and the live editor confirmed it field for field.** The scene held
    `ppo_car_009_bc_s13-5000050.onnx` with `DeterministicInference: false`, and `runId` still read
    `ppo_car_009_bc_s13_sampling`. Running without the reset would have reported seed 13's policy
    sampling its actions as seed 42's driving deterministically
  - Set to `ppo_car_009_bc-5000101.onnx`, deterministic on, `seedSet` to Generalisation, `runId` to
    `ppo_car_009_bc-5000101`. Scene saved
  - Two figures published in M5 were verified against the running scene in passing:
    `VectorObservationSize` is **19** and `MaxStep` is **6000**
- [X] T017 [US2] Run the sweep once. One row per accepted seed, no seed twice (SC-002)
  - 33 rows, 33 unique seeds, one controller value. `load()` raises on a duplicated seed rather
    than double counting it
- [X] T018 [US2] Verify from the written rows, not from the Inspector, that the model and the
      inference mode are the intended ones. Ordering 3
  - Every row's controller column reads `ppo_car_009_bc-5000101_deterministic`. **This is what
    Phase 1 was for**: before it, that column was the typed string, which still said `s13_sampling`
    at the moment the sweep started
- [X] T019 [P] [US2] Record the model file's content hash beside its name (SC-003)
  - sha256 `64926be52d55b1c01975dc9c015f1b4e2f0462faf711680321265289ba71de9d`, 291,159 bytes, and
    **byte identical to the trainer's own output** at `results/ppo_car_009_bc/CarDriver/`
- [X] T020 [US3] Report the completion rate with its Wilson interval, beside the held-out rate with
      its own, and state whether the intervals overlap (FR-008, SC-004)

  | | held out | **generalisation** |
  |---|---|---|
  | completed | 10 of 10 | **33 of 33** |
  | rate | 100.0 % | **100.0 %** |
  | Wilson 95 % | [72.2, 100.0] | **[89.6, 100.0]** |
  | wall contacts | 0 | **0** |

  - They overlap, necessarily, since both are perfect. **The result is the bound, not the rate**:
    it moved from 72.2 to 89.6 per cent. A bare percentage would have said the two sweeps found the
    same thing
- [X] T021 [US3] Read the end reasons, not only the rate
  - All 33 are `LapsCompleted`. **72 of 72 markers on every run, none skipped**, so no run finished
    by any route other than driving the whole thing
  - Lap-time spread doubled, sd 0.314 s to 0.617 s over three times the runs. Consistent with a
    wider sample of geometries; reported because a mean-only table would have hidden it
- [X] T022 [US3] State the result against the pre-registered reading from T015
  - **Research R7, case 1.** Chosen by `verdict()` from the numbers rather than by preference: the
    branch order is R7's order and the function is what writes the sentence
- [X] T023 [US3] State what the result cannot say (FR-009)
  - Same generator, same acceptance bound, so this is a claim about a distribution of tracks and
    not about track design. And the new tracks are easier on peak steering demand, which is stated
    in the report rather than left for a reader to find in the batch report
- [X] T024 [P] Write the outcome into `results/EXPERIMENTS.md` and `DESIGN.md`. **M3's verdict is
      not edited** (SC-005)
  - `EXPERIMENTS.md` gains the result section; `DESIGN.md` closes item 2 of M3's open list in
    Bosnian. **M3's verdict table is untouched**, and so is the carried-forward sentence itself
- [X] T025 [P] Update M3's closing summary to point at this measurement
  - **The sentence stays as written and a dated pointer follows it.** It records what was true on
    2026-09-01, and rewriting a closed milestone's record to match a later measurement is the thing
    SC-005 exists to prevent. Two of the three carried-forward items remain open and the pointer
    says so
- [X] T026 [P] Confirm the report reproduces from a clean clone (FR-010, SC-006)
- [X] T027 [P] Suites green, em dash check across every file this feature touched

  | suite | passed | skipped | against M5's close |
  |---|---|---|---|
  | `.venv` | **425** | 4 | +15 |
  | `.venv-bc` | **480** | 0 | +15 |

  - Zero em dashes across every file on the branch, checked by iterating the diff
- [X] T028 Merge to `develop` with `--no-ff`, then to `master`
**Checkpoint**: the sentence M3 left open is answered, or is answered as "not at this sample size",
and either is written down.

---

## Dependency notes

- T001 blocks T017. Ordering 1: a sweep run before the label is derived cannot be relabelled.
- T007 blocks T011, which blocks T017. The Unity side cannot read a half that does not exist.
- T012 blocks T016. Ordering 2.
- T013 blocks T020. The interval exists before the number it will describe.
- T015 blocks T017. Ordering 4: the reading is fixed before the result.
- T024 and T025 depend on T022.
