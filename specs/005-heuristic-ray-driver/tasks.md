# Tasks: Heuristic Ray-Following Driver

**Input**: Design documents from `/specs/005-heuristic-ray-driver/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included, and not optional here. Constitution Principle VIII requires EditMode tests for
Unity logic and `pytest` for Python, and the plan's Post-Design re-check records that this feature
is only fully testable because the two controllers are separated out as pure functions.

**Organization**: Grouped by user story. US1 and US2 are both P1 and share a dependency worth
stating up front rather than hiding.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## A note on the build order of the two controllers

The spec stages this feature deliberately: build the naive controller, measure how it behaves, and
only then replace it. That ordering is preserved here literally. **`MostOpen` is built in the
Foundational phase and `WeightedAverage` is not built until US2**, so the smoothed controller cannot
be quietly adopted before the naive one has been measured.

This creates one real cross-story dependency: if `MostOpen` cannot complete a lap, US1's acceptance
waits on US2 delivering `WeightedAverage`. That is surfaced rather than designed away, because the
alternative is building both up front and then writing a comparison whose conclusion was already
assumed.

---

## Phase 1: Setup

**Purpose**: The things that must exist before any code, including the one the constitution puts
before implementation.

- [X] T001 Write the heuristic driver section into `DESIGN.md`: what the driver is, why it exists as a non-learned baseline, the two controllers, and the derived-speed rule from research R1. **Principle V requires this before implementation, in its own `docs:` commit**, and this task blocks every code task that follows
  - Written as **DESIGN 4.7**, not as a new top-level section. Section numbers are referenced from the specs (`DESIGN 4.3`, `DESIGN section 7`) and renumbering would break those references silently, which is a worse outcome than a slightly deep heading
  - Section 7's comparison table gained a fourth column. That table previously had three, and the missing one was the only column that learns nothing
  - The R2 prediction is recorded there in full, before it can be measured: three reachable steering magnitudes, 0, 0.6 and 1.0, and an oscillation near 3 Hz
- [X] T002 [P] Create `results/heuristic/` and add `.gitignore` rules for it, keeping run CSVs out of git while committing the generated reports, matching how `results/tracks/` is already handled
  - `results/heuristic/runs_*.csv` ignored, `!results/heuristic/*.md` tracked. The asymmetry is the point: a sweep writes one row per seed, controller and configuration, so the raw files grow fast and none of them is worth keeping, while the reports carry the numbers that get cited in `research.md` and DESIGN 4.7. **A cited number has to be checkable from the repository**
- [X] T003 [P] Create the Python package skeleton `python/heuristic/__init__.py` and `python/heuristic/report.py` with module docstrings only, no logic
  - The docstrings carry the two rules the tests will enforce, so they are written down before the code that can get them wrong: an empty `lap_time_s` is excluded rather than averaged as zero, and results are reported over the seed set rather than per seed
- [X] T004 [P] Record the pre-feature test baseline in this file: `280 passed, 3 skipped` under `.venv` and `334 passed` under `.venv-bc`, measured 2026-08-09, so a later regression is attributable
  - Both figures measured on the merged branch after feature 003 landed. They were 87 and 141 before that merge, on a branch where the track generator's tests did not exist

**Checkpoint**: the design is written down and the folders exist.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The sensing block, the naive controller and the driver that carries it. Nothing in any
user story can begin until this is done.

**CRITICAL**: T001 must be complete before any task in this phase.

### The sensing block (FR-013, FR-016)

- [X] T005 Add the sensing constants to the export in `python/track/config.py` so `RAY_COUNT`, `RAY_FOV_DEG` and `RAY_LENGTH_M` are reachable by the exporter, changing no value
  - **No-op, recorded rather than invented.** All three were already module-level constants in `config.py`, so `config.RAY_COUNT` was reachable from the exporter the whole time. The task was written from the plan without checking, and the honest close is that nothing needed doing
- [X] T006 Write the `sensing` block in `python/track/vehicle.py` per `contracts/sensing-block.md`, and bump `schema_version` from 2 to 3
  - The committed `vehicle_profile.json` diff is exactly two things: `schema_version` 2 to 3, and the new block. **No existing value moved**, which is the property FR-018 depends on
  - `test_vehicle.py::test_export_profile_writes_every_derived_value` pinned `schema_version == 2` and had to move to 3. That test failing was the correct behaviour, not an obstacle: Unity refuses a version it does not recognise, so a bump nothing checks would surface as a car that will not start
- [X] T007 [P] Write `python/tests/test_sensing_mirror.py`: the exported block must match the constants it came from, in the shape of the existing `python/tests/test_vehicle.py`. **This test is the whole point of the block** and must fail if either side is edited alone
  - Six tests. Two failed on first run because the committed profile predated the block, which is the test doing its job; regenerating fixed them
  - One test asserts that ray spacing is **not** exported, because a stored spacing would be a third copy able to disagree with the two it is derived from
- [X] T008 Change `unity/SelfDrivingSim/Assets/Scripts/Agent/CarAgent.cs` to load the sensing block on `Awake` the way `CarController` loads the vehicle profile, replacing the three serialised fields. Refuse loudly on a missing block, an unreadable file, or an unrecognised `schema_version`, per the contract. **Never fall back to hardcoded defaults**, which would reintroduce the second copy this removes
  - **The task as written was wrong, and the code said so.** `CarController` does not load the profile: `VehicleProfile` holds a compiled copy, described in its own comment as being there "so the car does not depend on a file at runtime". `DriveTelemetry` is what reads the file, and what it does with the profile block is **check** it against the scene, field by field
  - So `CarAgent` got the same treatment instead: the serialised fields stay, and `CheckSensingDrift` compares them against the exported block at `Awake`. `research.md` R7 and `contracts/sensing-block.md` are corrected in the same commit rather than left describing a design that was not built
  - **Why the existing pattern is the better one.** `DriveTelemetry`'s comment records the incident it was written for: retuning the steering rate from 2.0 to 3.7 in T023 left the scene on 2.0, and the only symptom would have been a drive that mysteriously failed to improve. It also states why a mirror test is not enough, in one line: it compares the compiled default against the JSON and **never opens the scene**. `CarAgent`'s ray fields are serialised the same way and rot the same way
  - Two gaps, two mechanisms. `pytest` closes `config.py` against the exported file; `CheckSensingDrift` closes the exported file against the scene. Neither alone is sufficient, because the mirror test never opens the scene and the drift check never runs in CI
  - `ConfigureFan` added for the sweep (FR-013), setting the fan at runtime and suppressing the drift check while it is overridden, since during a sweep the scene disagrees with the file on purpose and one error per seed would bury the run
- [X] T009 Re-run the T062 observation checks after T008 and confirm the nineteen values are unchanged. The values must not move; only their source does. If any ray reading differs, T008 is wrong
  - **Bit-identical at the seed 1004 spawn.** Ray 00 reads `0.1988517940044403`, heading forward `0.8734288215637207`, `MaxYawRateRadPerS` 1.865230679512024, all matching the T062 record digit for digit
  - The drift check was then verified by breaking it deliberately: `rayCount` set to 11 in the scene, which produced exactly the intended error naming both values. The scene was restored afterwards and `git diff` on `Track.unity` is empty
  - **That negative test failed silently the first time, and the reason is worth recording.** Unity had not recompiled, so the assembly was 2.5 hours stale and none of the new code existed in it. `Unity_ValidateScript` returning clean is a static check and says nothing about what is loaded. This is the second time this session that a stale assembly produced a confident wrong conclusion, the first being the `StartPlacer` fix in feature 003. **Check the assembly timestamp before trusting any in-editor result**

### The naive controller (FR-006, first half)

- [ ] T010 [P] Create `unity/SelfDrivingSim/Assets/Scripts/Agent/RayControllers.cs` with `MostOpen` as a pure static function from a normalised distance array and its ray angles to a steering command in [-1, 1]. **Ties break toward the centre ray, never by array order** (research R9)
- [ ] T011 [P] Create `unity/SelfDrivingSim/Assets/Tests/EditMode/RayControllerTests.cs` covering `MostOpen`: a clear left, a clear right, the all-clear fan where every ray reads 1.000, and the symmetric fan where the tie must resolve to centre. The symmetric case is a bug that appears only on symmetric readings and would otherwise be blamed on the track

### The driver (FR-002, FR-003, FR-004, FR-005)

- [ ] T012 Create `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs`: reads `CarAgent.RayDistancesNorm` and `CarAgent.SpeedForwardNorm`, writes `CarController.ScriptedMove`, all in `FixedUpdate` so runs reproduce (research R6). It MUST NOT read the track file, checkpoint positions, or anything else a learning agent could not see (FR-001)
- [ ] T013 Implement the derived target speed in `HeuristicDriver.cs`: from the chosen steering command, the implied radius is `wheelbase / tan(delta * steer_max_rad)` and the target speed is `sqrt(a_lat * R)` capped at `v_max`, with throttle and brake following the error. Every constant comes from `CarController.Profile`, none typed in
- [ ] T014 Implement control handover in `HeuristicDriver.cs`: refuse to engage while `ScriptedDriver.IsRunning`, release `ScriptedMove` to null when disabled, and log which source has the wheel when it changes (FR-003, FR-004)
- [ ] T015 Show the active control source in `unity/SelfDrivingSim/Assets/Scripts/Logging/DriveHud.cs`, so an observer can see which of keyboard, `ScriptedDriver` and `HeuristicDriver` is driving (FR-004 requires it visible, not merely unambiguous)
- [ ] T016 Implement the end conditions in `HeuristicDriver.cs`: lap complete, time limit, wall contact, wrong way, fell through. **The time limit is derived from the slowest T051 lap with margin, not picked** (FR-005, research R9)
- [ ] T017 Add `HeuristicDriver` to the `Car` object in `unity/SelfDrivingSim/Assets/Scenes/Track.unity`, disabled by default so keyboard behaviour is untouched until it is switched on. **Scene lock applies**; the script, its `.meta` and this scene edit are one commit

**Checkpoint**: the car can be driven by the naive controller. No measurement exists yet.

---

## Phase 3: User Story 1 - A driver that gets round the track (Priority: P1) MVP

**Goal**: a scripted lap, proving the track is completable by something that learned nothing.

**Independent Test**: pick an accepted seed, run the driver, confirm a full lap with every
checkpoint awarded in order and no wall contacts.

- [ ] T018 [US1] Run `MostOpen` on an accepted training seed and record the outcome in this file, whatever it is. **A failure here is US2's evidence, not a blocker to be fixed quietly**
- [ ] T019 [US1] Run `MostOpen` on the tightest-cornered accepted seed and record whether the derived speed holds the corner (SC-002). This is the case that fails first if T013 is wrong
- [ ] T020 [US1] Confirm keyboard control is unchanged with the driver disabled, by driving a lap by hand (SC-007, FR-003)
- [ ] T021 [US1] Record which controller first completed a clean lap, and on which seed, in `specs/005-heuristic-ray-driver/tasks.md`. If `MostOpen` could not, state that and note US1 completes after T024

**Checkpoint**: the track is demonstrably completable without learning, or it is recorded that the
naive controller cannot do it.

---

## Phase 4: User Story 2 - The chatter is demonstrated before it is fixed (Priority: P1)

**Goal**: the recorded comparison between the two controllers, which is the deliverable, not merely
the better controller.

**Independent Test**: run both controllers over the same seeds and compare their recorded steering
traces and outcomes side by side.

- [ ] T022 [US2] Add the two smoothness measures to `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs` or a helper beside it: \|delta steer\| P95 resampled to 14.08 Hz, and steering sign changes per second (research R3). **Both are reported, never combined** (FR-009)
- [ ] T023 [US2] Write the run record per `contracts/run-record.md` from the Unity side, one row per run, `InvariantCulture` throughout. This project has hit the locale bug three times already
- [ ] T024 [US2] Add `WeightedAverage` to `RayControllers.cs`: the distance-weighted mean of the ray angles over `steer_max_deg`, which returns 0 on a symmetric reading by construction and needs no special case
- [ ] T025 [P] [US2] Extend `RayControllerTests.cs` to cover `WeightedAverage`, including the symmetric fan returning exactly 0 and the all-clear fan holding heading
- [ ] T026 [US2] Make the controller selectable for a run without editing code (FR-007), so a comparison runs the same build twice
- [ ] T027 [US2] Measure the run-to-run spread: same seed, same controller, three runs, reporting the spread of lap time and both smoothness measures (FR-011). **Nothing in T028 or Phase 5 may be interpreted before this number exists**
- [ ] T028 [US2] Implement the comparison in `python/heuristic/report.py`: descriptive statistics per controller over the seed set, the two smoothness measures and the outcome measures side by side, and the explicit statement of whether any difference exceeds the T027 spread
- [ ] T029 [P] [US2] Write `python/tests/test_heuristic_report.py` covering the reporter on a fixture CSV, including a failed run with an empty `lap_time_s`, which must be excluded from the lap-time mean rather than averaged as zero
- [ ] T030 [US2] Record the measured comparison in `specs/005-heuristic-ray-driver/research.md` against the R2 prediction of a 3 Hz oscillation at 0.6 amplitude. **If the prediction is wrong, the falsification is the finding**, as C17 was in feature 003
- [ ] T031 [US2] If `MostOpen` performs acceptably, record that as the result and justify `WeightedAverage` on its measured merits or do not adopt it (spec US2 scenario 3)

**Checkpoint**: the design decision behind the smoothed controller is measured, not asserted.

---

## Phase 5: User Story 3 - Testing whether the sensing geometry is right (Priority: P2)

**Goal**: an answer to the question T059 raised, that seven of thirteen rays may be reporting the
same lateral distance while three carry all the cornering information.

**Independent Test**: run the same seed set under at least two ray arrangements and compare.

- [ ] T032 [US3] Create `unity/SelfDrivingSim/Assets/Scripts/Track/SweepRunner.cs`: iterate seeds inside one Play session, rebuilding the track and resetting the car between runs. **Restarting the editor per seed costs more than the entire SC-004 budget** (research R4)
- [ ] T033 [US3] Set `Time.timeScale` and `Time.maximumDeltaTime` in `SweepRunner.cs`, leaving `Time.fixedDeltaTime` alone. A coarser physics step would mean the sweep measured the step size rather than the geometry
- [ ] T034 [US3] Verify the acceleration: run one seed at the swept scale and at 1x and confirm the outcome matches. **A sweep that is fast and wrong is worse than one that is slow.** Lower the scale until they agree and record the figure that survives
- [ ] T035 [US3] Load the seed set from `results/tracks/seed_split.json`, **training seeds only** (research R5). Choosing a geometry against the evaluation seeds would fit the environment to the tracks the learning agent is later judged on
- [ ] T036 [US3] Drive the sensing configuration from the exported block so a sweep is a file the runner writes, not a scene edit (FR-013, depends on T008)
- [ ] T037 [US3] Run the full sweep over at least two arrangements, covering at minimum the angular width of the fan, every configuration over the same seeds (FR-014)
- [ ] T038 [US3] Extend `python/heuristic/report.py` to report the sweep and state whether any difference exceeds the T027 run-to-run spread (FR-015). **A difference smaller than the noise is not a finding** and must be said in those words
- [ ] T039 [US3] Confirm SC-004: one configuration over all 34 training seeds in under five minutes, with the measured time recorded
- [ ] T040 [US3] Write the answer into `specs/005-heuristic-ray-driver/research.md`: whether the current fan is worse than, equal to, or better than the alternatives tried. **If nothing beats the current geometry, record it as measured-and-kept rather than quietly left alone** (spec US3 scenario 3)

**Checkpoint**: the sensing geometry has been tested rather than assumed.

---

## Phase 6: User Story 4 - A fourth column in the final comparison (Priority: P3)

**Goal**: the scripted driver described by the same measures as the human, PPO and BC columns.

**Independent Test**: produce the steering distribution and confirm it uses the same measures as the
existing driver comparisons.

- [ ] T041 [US4] Produce the scripted driver's steering distribution in `python/heuristic/report.py` using the same measures and summary shape as the feature 002 and 004 comparisons, so M5 consumes it without a translation step
- [ ] T042 [US4] Report descriptive statistics for every distribution touched: sample size, mean, variance, min, max, and a relative-frequency histogram (Principle IX)
- [ ] T043 [US4] If the scripted driver outperforms a learned driver on any measure, report it plainly rather than omitting it (spec US4 scenario 2)

**Checkpoint**: M5 has its baseline column.

---

## Phase 7: Polish and Cross-Cutting

- [ ] T044 [P] Update `README.md` with the heuristic driver commands, keeping it a literal reproduction recipe (Principle VI)
- [ ] T045 [P] Reconcile `DESIGN.md` with what was actually built. T001 wrote the intent; this checks the code did not diverge from it
- [ ] T046 Run `pytest python/tests` under `.venv` and `.venv-bc` and record both counts against the T004 baseline
- [ ] T047 Run all Unity EditMode tests and confirm green
- [ ] T048 Walk `specs/005-heuristic-ray-driver/quickstart.md` end to end and correct every figure. **Its expected values are currently predictions, and are marked as such.** The last two features both had the walk falsify something: T042 found a collection error hiding a zero-test run, T068 falsified T023's explanation of the speed check
- [ ] T049 Confirm FR-017: this feature has not satisfied or substituted for feature 003's human keyboard lap, and T051 still stands on its own
- [ ] T050 If the sweep recommends a new arrangement, record the decision with its measurement **before** applying it, stating that it invalidates previously measured sensing results and any model trained against the old fan (FR-018). Applying it is out of scope for this feature

---

## Dependencies and Execution Order

### Phase dependencies

- **Setup (Phase 1)**: T001 blocks everything. Principle V puts the design before the code
- **Foundational (Phase 2)**: blocks all user stories
- **US1 (Phase 3)** and **US2 (Phase 4)**: both P1. US1 may complete before US2 only if `MostOpen`
  completes a clean lap; otherwise T021 waits on T024
- **US3 (Phase 5)**: needs the driver trustworthy first, so it follows US2. It also needs T008,
  because a sweep that edits the scene per configuration cannot meet SC-004
- **US4 (Phase 6)**: needs a completed run to describe, so it follows US2. Independent of US3
- **Polish (Phase 7)**: last

### The one dependency that matters most

**T027 blocks the interpretation of T028, T037 and T038.** The run-to-run spread is the noise floor,
and FR-015 turns on it. Every comparison in this feature is meaningless until that number exists,
and it is the easiest task to skip because nothing fails without it. Feature 004 established the
pattern in R13: measure the tolerance rather than asserting determinism.

### Within Phase 2

- T005, T006 sequential (same subject, and T006 needs T005)
- T007 parallel with T008
- T010 and T011 parallel with the sensing work, different files entirely
- T012 through T016 sequential, all in `HeuristicDriver.cs`
- T017 last, because a scene edit referencing a script that does not compile is a broken scene

### Parallel opportunities

```text
# Phase 1, after T001:
T002  results/heuristic/ and .gitignore
T003  python/heuristic/ skeleton
T004  test baseline

# Phase 2, two independent tracks:
Track A (sensing):    T005 -> T006 -> T008 -> T009,  with T007 alongside
Track B (controller): T010 -> T011,  then T012 -> T013 -> T014 -> T015 -> T016 -> T017
```

---

## Implementation Strategy

### MVP

Phase 1, Phase 2, Phase 3. That delivers a car driving itself round a generated track with no model
and no training, which is a fact this project does not currently have.

**Stop and validate there.** If the naive controller completes clean laps, the shape of US2 changes:
the comparison still runs, but the smoothed controller has to earn its place rather than being
assumed.

### Incremental delivery

1. Setup and Foundational, then the naive controller drives
2. US1: a lap exists. Demo-able
3. US2: the comparison is measured, and the second controller is adopted or not on the evidence
4. US3: the sensing question gets an answer, which may be "the current geometry is fine"
5. US4: the M5 column

### What to be suspicious of

Three failure modes this feature is unusually exposed to:

- **Skipping T027.** Nothing breaks without the noise floor, and every later number becomes
  unfalsifiable. It is the single highest-value task in the list
- **Tuning the heuristic.** Out of Scope says so explicitly. A tuned heuristic stops being a
  baseline and the M5 comparison becomes two tuned systems measured against each other
- **Adopting a sweep result inside this feature.** FR-018 and T050 keep the measurement and the
  change apart, because applying a new fan invalidates every sensing result already recorded and
  any model trained against the old one
