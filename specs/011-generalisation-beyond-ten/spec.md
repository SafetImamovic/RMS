# Feature Specification: Generalisation beyond the ten held-out tracks

**Feature Branch**: `011-generalisation-beyond-ten`
**Created**: 2026-09-02
**Status**: Draft
**Input**: User description: "generalisation beyond the ten held-out tracks"

## Why this exists

M3 closed met on 2026-09-01 and its own closing summary recorded a limit rather than hiding it:

> Generalisation beyond these ten tracks from one generator is unshown.

This feature closes that sentence, or fails to and says so. It runs no training. It reads the
policy that already exists, `results/ppo_car_009_bc/.../ppo_car_009_bc.onnx`, and asks it to drive
tracks nobody has ever looked at.

**The problem is not that seeds 1001 to 1010 were seen by the policy.** They were not: research R5's
rule held, every configuration choice was made against training seeds, and the eval seeds were only
ever read to report a result. The problem is that **they were read to report a result four times**,
across features 006, 007, 008 and 009. Each reading informed which experiment came next. That is
selection pressure at the level of the researcher rather than the model, and it is invisible in any
single feature's numbers. A set of tracks that has never been looked at once is the only thing that
removes it.

**What this feature cannot show, stated up front so no result overclaims.** The new seeds come from
the same generator with the same acceptance bound, so a pass says the policy drives *this
distribution* of tracks rather than *these ten* of them. It says nothing about a different
generator, a different track topology, or a real road. That is a larger claim and it is out of
scope here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A third seed set that has never been looked at (Priority: P1)

A track set disjoint from both existing splits is generated, accepted by the same bound, and
recorded in the same split file the other two live in.

**Why this priority**: nothing else in the feature can run without it, and the property that makes
it worth running is that it is generated once and swept once.

**Independent Test**: `results/tracks/seed_split.json` carries a third half whose accepted seeds
intersect neither `train` nor `eval`, and every accepted seed has a track file.

**Acceptance Scenarios**:

1. **Given** the existing split file, **When** the new set is generated, **Then** its accepted seeds
   are disjoint from seeds 1 to 40 and from 1001 to 1010, and the file records that disjointness the
   way it already records the existing pair.
2. **Given** a seed the generator rejects, **When** the batch runs, **Then** the rejection and its
   reason are recorded and the seed is **not** retried with adjusted parameters.
3. **Given** the accepted set, **When** the pooled steering demand is checked, **Then** it is within
   the same bound the other two splits were held to, so a later failure cannot be blamed on tracks
   the vehicle physically cannot corner.

---

### User Story 2 - The sweep, run once, on a policy chosen before the tracks existed (Priority: P1)

The existing `ppo_car_009_bc` policy drives the new set in deterministic inference, and the run
record is written the same way M3's was.

**Why this priority**: this is the measurement. Everything else is scaffolding for it.

**Independent Test**: an evaluation CSV exists with one row per new seed, carrying lap completion,
lap time, wall contacts and end reason, in the same schema as `eval_ppo_car_009_bc_deterministic.csv`.

**Acceptance Scenarios**:

1. **Given** the new seed set, **When** the sweep runs, **Then** every seed produces exactly one row
   and no seed is run twice.
2. **Given** the sweep is configured, **When** it starts, **Then** the model, the inference mode and
   the seed set are recorded alongside the result, so a reader can tell what produced it without
   opening the scene.
3. **Given** a seed the policy fails, **When** the row is written, **Then** the end reason
   distinguishes a wall contact from a time limit from no progress, because "did not finish" is
   three different findings.

---

### User Story 3 - The result read against M3's own bar, and the interval stated (Priority: P2)

The new numbers are compared against SC-001 and SC-002 as M3 defined them, and the comparison
carries an interval rather than a bare percentage.

**Why this priority**: a percentage over n runs without an interval invites a reader to compare it
against the held-out 100 per cent as though the difference were meaningful.

**Independent Test**: the report states the completion rate, its confidence interval, and whether
the held-out result sits inside it.

**Acceptance Scenarios**:

1. **Given** both sets of runs, **When** the result is written, **Then** it states plainly whether
   M3's bar is met on tracks nobody looked at, and does not restate M3's verdict as though this
   feature re-earned it.
2. **Given** any drop from the held-out figure, **When** it is reported, **Then** it is reported
   with the interval and with the sample sizes, not as a bare difference.

## Requirements *(mandatory)*

- **FR-001**: The new seed set MUST be disjoint from both existing splits, and the disjointness MUST
  be checked rather than assumed from the seed numbering.
- **FR-002**: The new set MUST be generated by the existing generator with the existing acceptance
  bound and no parameter changes. A set generated under a looser bound would answer an easier
  question.
- **FR-003**: A rejected seed MUST be recorded with its reason and MUST NOT be retried with adjusted
  parameters, matching the rule feature 003 already enforces.
- **FR-004**: The sweep MUST use the existing `ppo_car_009_bc` policy unchanged. No retraining, no
  fine tuning, no checkpoint selection against the new tracks.
- **FR-005**: The sweep MUST run in deterministic inference, matching the column M3 was closed on,
  and MUST record that it did.
- **FR-006**: The seed set the sweep runs MUST come from the split file, never from a list typed
  into a scene, matching the rule `SweepRunner.LoadSeeds` already enforces for the other two.
- **FR-007**: Sweeping the new set MUST warn as loudly as sweeping the evaluation set does, and for
  the same reason: it may report a result and may never be used to choose a configuration.
- **FR-008**: The result MUST be reported with an interval and with both sample sizes.
- **FR-009**: The report MUST state that the new tracks come from the same generator, so the claim
  is about a distribution rather than about track design in general.
- **FR-010**: The comparison inputs and the report MUST reproduce from a clean clone, matching
  M5's SC-006. Raw traces stay out of the repository; what the report reads is committed.

## Measurable Outcomes

- **SC-001**: The new seed set is disjoint from both existing splits, verified by a test, and every
  accepted seed has a track file.
- **SC-002**: Every accepted seed produces exactly one evaluation row, and no seed appears twice.
- **SC-003**: The policy file used is identified by name and content hash in the report, so the
  claim "the same policy" is checkable rather than asserted.
- **SC-004**: The completion rate on the new set is reported with a confidence interval and beside
  the held-out rate with its own.
- **SC-005**: Whatever the outcome, it is written into `results/EXPERIMENTS.md` and `DESIGN.md`
  including the case where the policy does worse, and M3's closed verdict is not edited to match.
- **SC-006**: The report reproduces from a clean clone.

## Out of Scope

- **Any training.** No PPO run, no fine tuning, no checkpoint sweep. The policy is an input.
- **Any change to the generator or its acceptance bound.** A different track distribution is a
  different question and would make the result unattributable.
- **Reopening M3.** M3 is closed met on the evidence it was closed on. This feature adds a
  measurement beside that verdict; it does not revise it, and a poor result here is a finding about
  generalisation rather than a retraction.
- **A second inference mode.** Deterministic only, matching M3's column. Sampling would double the
  sweep for a comparison M5 has already made.
