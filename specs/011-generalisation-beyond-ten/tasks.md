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

- [ ] T001 [US2] Derive the run label in `DrivingAgent` from `BehaviorParameters`: the model asset
      actually loaded and the inference mode actually in effect. This is what goes in the run
      record's controller column
- [ ] T002 [US2] Demote the serialised `runId` to a cross-check. When it is set and disagrees with
      the derived label, log an error naming both. Do not silently prefer either
- [ ] T003 [P] [US2] Update the tooltip, which currently tells the reader to check by eye. The whole
      point of T001 is that nobody has to
- [ ] T004 [US2] Verify the compile from the assemblies and the console, not from the absence of a
      complaint. A missing project dll means the compile failed (this repository has been caught by
      that before)

**Checkpoint**: a run record row can prove which policy produced it.

## Phase 2: the third seed set (US1)

- [ ] T005 [US1] Add `GENERALISATION_SEEDS = range(2001, 2041)` to `python/track/config.py` and a
      batch name that produces it, through the existing generator and the existing acceptance bound.
      **No parameter changes** (FR-002)
- [ ] T006 [US1] Generate the batch, record every rejection with its reason, and **do not retry a
      rejected seed** (FR-003)
- [ ] T007 [US1] Write the accepted set into `results/tracks/seed_split.json` as a third half, and
      record its disjointness from both existing halves the way the file already records the
      existing pair
- [ ] T008 [P] [US1] A test that the three sets are pairwise disjoint, checked from the file rather
      than inferred from the seed ranges (FR-001, SC-001)
- [ ] T009 [P] [US1] A test that every accepted seed has a track file under `Assets/Tracks/`
- [ ] T010 [US1] Check the pooled steering demand of the new set against the same bound both
      existing splits were held to, and record the figure. A later failure must not be blamable on
      tracks the vehicle cannot physically corner
- [ ] T011 [US1] Add the third `SeedSet` enum value and the third `SeedSplitFile` field to
      `SweepRunner`, and warn on sweeping it exactly as the evaluation set warns (FR-006, FR-007)
- [ ] T012 [US1] Commit the seed set and the track files **before the sweep runs**. Ordering 2: a
      regeneration after this point is a visible diff rather than a silent one

**Checkpoint**: a set of tracks exists that nobody has looked at, and the sweep can address it.

## Phase 3: the interval, before the numbers (US3)

- [ ] T013 [US3] Add a Wilson score interval to `python/eda/`, beside the hypothesis tests it will
      be reported next to. Not the normal approximation, which reports `[1.00, 1.00]` on a perfect
      run and claims certainty from a finite sample (research R6)
- [ ] T014 [P] [US3] Tests pinning R6's worked table: 10 of 10, 34 of 34, and 31 of 34, plus the
      case the normal approximation gets wrong
- [ ] T015 [US3] Record the pre-registered reading from research R7 in `results/EXPERIMENTS.md`
      **before the sweep runs**, so the interpretation is fixed before the result exists

**Checkpoint**: what each outcome will mean is written down and dated.

## Phase 4: the sweep and the result (US2, US3)

- [ ] T016 [US2] Reset the evaluation scene: model to `ppo_car_009_bc-5000101.onnx`, deterministic
      inference **on**, seed set to the new one. Research R3 measured it holding seed 13's model
      with deterministic inference off
- [ ] T017 [US2] Run the sweep once. One row per accepted seed, no seed twice (SC-002)
- [ ] T018 [US2] Verify from the written rows, not from the Inspector, that the model and the
      inference mode are the intended ones. Ordering 3
- [ ] T019 [P] [US2] Record the model file's content hash beside its name, so "the same policy" is
      checkable rather than asserted (SC-003)
- [ ] T020 [US3] Report the completion rate with its Wilson interval, beside the held-out rate with
      its own, and state whether the intervals overlap (FR-008, SC-004)
- [ ] T021 [US3] Read the end reasons, not only the rate. A wall contact, a time limit and a
      no-progress stall are three findings, not one
- [ ] T022 [US3] State the result against the pre-registered reading from T015, naming which of R7's
      four cases occurred
- [ ] T023 [US3] State what the result cannot say: same generator, same acceptance bound, so the
      claim is about a distribution rather than about track design (FR-009)
- [ ] T024 [P] Write the outcome into `results/EXPERIMENTS.md` and `DESIGN.md`. **M3's verdict is
      not edited** (SC-005), including if the result is poor
- [ ] T025 [P] Update M3's closing summary, which currently reads "generalisation beyond these ten
      tracks from one generator is unshown", to point at this measurement. That sentence becomes
      false either way once this runs
- [ ] T026 [P] Confirm the report reproduces from a clean clone (FR-010, SC-006)
- [ ] T027 [P] Suites green, em dash check across every file this feature touched
- [ ] T028 Merge to `develop` with `--no-ff`, then to `master`

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
