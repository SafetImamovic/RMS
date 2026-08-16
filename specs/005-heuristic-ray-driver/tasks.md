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

- [X] T010 [P] Create `unity/SelfDrivingSim/Assets/Scripts/Agent/RayControllers.cs` with `MostOpen` as a pure static function from a normalised distance array and its ray angles to a steering command in [-1, 1]. **Ties break toward the centre ray, never by array order** (research R9)
  - **Deviation, recorded rather than hidden: `WeightedAverage` was written in the same file at the same time, and T024 was supposed to hold it back.** The header of this file says the naive controller is built first "so the smoothed controller cannot be quietly adopted before the naive one has been measured", and that ordering was set deliberately half an hour before it was broken
  - Kept rather than deleted and re-added, which would be waste, but **the guard is now explicit instead of positional**: US1 and the first comparison run MUST use `MostOpen`, and T031 still decides whether `WeightedAverage` is adopted. The risk the ordering protected against was never the existence of the function, it was writing the comparison with the answer already in hand, and that risk lives in T028 and T030 where it is now stated
  - `MostOpen` is capped by the clamp far more often than expected: any ray beyond ±25 degrees asks for more than full lock, so nine of the thirteen rays produce a saturated command
- [X] T011 [P] Create `unity/SelfDrivingSim/Assets/Tests/EditMode/RayControllerTests.cs` covering `MostOpen`: a clear left, a clear right, the all-clear fan where every ray reads 1.000, and the symmetric fan where the tie must resolve to centre. The symmetric case is a bug that appears only on symmetric readings and would otherwise be blamed on the track
  - **18 tests, all passing.** Run through `TestRunnerApi` rather than by hand, so the result is a number in the console rather than a colour in a window
  - One test pins the R2 prediction directly: sweeping the open ray across the whole fan yields exactly three reachable magnitudes, `{0, 0.6, 1.0}`. If the fan or the steering limit ever moves, that test fails and the chatter argument in DESIGN 4.7 has to be recomputed rather than repeated
  - **One test failed on the first run, and it was the test that was wrong, not the code.** "Wall on the left, so steer right" set every unblocked ray to the same distance, which is an eight-way tie that correctly resolves to the centre. Driving straight past a wall you are parallel to is the right answer
  - That failure was worth keeping, so it is now two tests. `MostOpen_holds_straight_when_the_open_side_is_featureless` pins the behaviour, and `WeightedAverage_turns_where_MostOpen_holds_straight` shows the two controllers already differ in **what they do**, not merely in how smoothly they do it. That is a behavioural difference found before any lap was driven, and US2's comparison now has something concrete to look for

### The driver (FR-002, FR-003, FR-004, FR-005)

- [X] T012 Create `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs`: reads `CarAgent.RayDistancesNorm` and `CarAgent.SpeedForwardNorm`, writes `CarController.ScriptedMove`, all in `FixedUpdate` so runs reproduce (research R6). It MUST NOT read the track file, checkpoint positions, or anything else a learning agent could not see (FR-001)
  - The end conditions do read the checkpoint ring, and that is separate and deliberate: they decide when a run STOPS, never how the car steers. Nothing the ring reports reaches `Decide`, which keeps FR-001 checkable by reading the one method rather than by trusting the class
- [X] T013 Implement the derived target speed in `HeuristicDriver.cs`: from the chosen steering command, the implied radius is `wheelbase / tan(delta * steer_max_rad)` and the target speed is `sqrt(a_lat * R)` capped at `v_max`, with throttle and brake following the error. Every constant comes from `CarController.Profile`, none typed in
  - Reuses `VehicleProfile.RadiusForSteering`, which returns positive infinity for straight ahead, so the neutral case falls out instead of needing a branch
- [X] T014 Implement control handover in `HeuristicDriver.cs`: refuse to engage while `ScriptedDriver.IsRunning`, release `ScriptedMove` to null when disabled, and log which source has the wheel when it changes (FR-003, FR-004)
- [X] T015 Show the active control source in `unity/SelfDrivingSim/Assets/Scripts/Logging/DriveHud.cs`, so an observer can see which of keyboard, `ScriptedDriver` and `HeuristicDriver` is driving (FR-004 requires it visible, not merely unambiguous)
  - Colour coded and named, in both HUD languages. Splitting the vehicle panel to fit it turned up a method called `DrawTilt` that also drew resets, recording and the stability tally and closed a `BeginArea` its caller opened; renamed and the `EndArea` moved back to the caller
- [X] T016 Implement the end conditions in `HeuristicDriver.cs`: lap complete, time limit, wall contact, wrong way, fell through. **The time limit is derived from the slowest T051 lap with margin, not picked** (FR-005, research R9)
  - Seven outcomes rather than five: `NoProgress` was added at 60 s without a new marker, mirroring DESIGN 4.6, so a car wedged against a barrier does not burn the whole 120 s limit
  - Wall contacts are filtered by contact normal rather than by tag. The body collider should only ever meet a barrier, but "should" is not a measurement, and counting a landing as a wall contact would fail laps SC-001 is meant to pass
- [X] T017 Add `HeuristicDriver` to the `Car` object in `unity/SelfDrivingSim/Assets/Scenes/Track.unity`, disabled by default so keyboard behaviour is untouched until it is switched on. **Scene lock applies**; the script, its `.meta` and this scene edit are one commit
  - All three references auto-resolved on `Awake`. Left disabled in the committed scene

**Checkpoint**: the car can be driven by the naive controller. No measurement exists yet.

---

## Phase 3: User Story 1 - A driver that gets round the track (Priority: P1) MVP

**Goal**: a scripted lap, proving the track is completable by something that learned nothing.

**Independent Test**: pick an accepted seed, run the driver, confirm a full lap with every
checkpoint awarded in order and no wall contacts.

- [~] T018 [US1] Run `MostOpen` on an accepted training seed and record the outcome in this file, whatever it is. **A failure here is US2's evidence, not a blocker to be fixed quietly**
  - **Seed 1004, `MostOpen`: WallContact at 5.2 s, 5 of 24 markers, 1 contact.** Repeated once, same outcome at 5.1 s. The driver drives, and it does not finish
  - **It does not fail the way R2 predicted.** The prediction was chatter near 3 Hz. Measured over the 260-sample driving window: **zero steering sign changes.** It never oscillated once. It steered hard left out of the spawn, eased off, and then commanded straight for the last three seconds while the track curved away underneath it, until it met the outside barrier
  - **The likely cause, and it is a property of argmax rather than a bug.** `MostOpen` aims at the single longest ray, and in a curving corridor the longest ray is not the one pointing into the corner: it is the one pointing down the length of the corridor, which is close to straight ahead. Follow-the-gap systematically under-steers on a curve because the deepest gap is biased toward the tangent. That is a better and more specific finding than "it chatters", and it is the one the measurement actually supports
  - **A second cause is not ruled out and matters for T013.** The speed rule is reactive: it derives target speed from the steering command the controller has already chosen, so a car that has not yet decided to turn has not yet decided to slow down. Peak speed in the window was 9.77 m/s against a 6.39 m/s limit at the tightest radius. Whether an anticipatory rule, taking the target speed from the forward ray distance, would fix this is a design change and is deliberately **not** made here. Research R1 rejected that rule as "tunable-looking", and that rejection now looks like it needs revisiting with a measurement behind it
  - **Two measurement traps found in the trace, both of which would have corrupted the US2 comparison.** The drive log runs to 37.4 s while the run ended at 5.2 s, because the logger keeps recording after control is released; every statistic computed over the whole file is diluted by 32 s of a stationary car. And the logged `steering` column is the vehicle's ACTUAL rate-limited angle, not the command the controller issued: 43 distinct values appear, against the three the command can produce. **FR-008 asks for the command, so T022 must record `LastSteer` from the driver and must trim to the run window**
  - The rate limiter is doing what R2 said it would: the quantised command becomes a continuous actual angle. `|dsteer|` per logged step reached 0.2865 against a 0.0740 rate limit, which is the logger sampling on the frame clock and occasionally spanning four physics steps. One more reason the command has to be recorded at source
  - US1 is not closed. `MostOpen` has not completed a lap, so per this file's stated dependency T021 waits on `WeightedAverage` being measured in US2
- [X] T019 [US1] Run `MostOpen` on the tightest-cornered accepted seed and record whether the derived speed holds the corner (SC-002). This is the case that fails first if T013 is wrong
  - The tightest accepted training seed is **37, minimum radius 6.97 m**, which is exactly the generator's radius floor, against a widest of 14.34 m on seed 32. Length 203.0 m, max required steer 0.789
  - **`MostOpen` cannot answer this question, and that is the recorded answer.** It ended in `WallContact` at 2.64 s with 1 marker of 24, so it never reached a tight corner and the derived speed rule was never put under test. The same is true at 120 and 90 degrees, at 1.98 s and 1.92 s. **The failure is in the steering rule, not the speed rule**, so T013 is not implicated by it either way
  - **SC-002 is answered by `WeightedAverage` on the same seed: `LapComplete` in 26.620 s, 24 of 24 markers, zero contacts.** That run does hold the 6.97 m corner, which is the case R1 computed caps cornering at 6.39 m/s against a 10 m/s top speed, so the anticipatory speed rule from T013 and R1a survives the hardest geometry the generator produces
- [ ] T020 [US1] Confirm keyboard control is unchanged with the driver disabled, by driving a lap by hand (SC-007, FR-003)
  - **Blocked: needs a person at the keyboard.** Everything else in US1 is measured; this is the one step that cannot be automated, and feature 003's T051 human lap is the precedent for keeping it that way
- [X] T021 [US1] Record which controller first completed a clean lap, and on which seed, in `specs/005-heuristic-ray-driver/tasks.md`. If `MostOpen` could not, state that and note US1 completes after T024
  - **`WeightedAverage`, on training seed 1, in 27.6 s**, recorded in commit `7b83db7` once the sight-limited speed rule from R1a was in place. Repeated at 27.5 s immediately after, and the five-run T027 set later put it at 27.308 s mean
  - **`MostOpen` has never completed a lap.** Not on seed 1004 where it was first tried, not at any critical-distance threshold between 0.20 and 0.50, and not on any of the 34 training seeds under any of three geometries: **0 of 102**. US1's dependency note was right that it would complete after T024, and the reason is stronger than expected: the naive controller does not merely lose the comparison, it never finishes

**Checkpoint**: the track is demonstrably completable without learning, or it is recorded that the
naive controller cannot do it.

---

## Phase 4: User Story 2 - The chatter is demonstrated before it is fixed (Priority: P1)

**Goal**: the recorded comparison between the two controllers, which is the deliverable, not merely
the better controller.

**Independent Test**: run both controllers over the same seeds and compare their recorded steering
traces and outcomes side by side.

- [X] T022 [US2] Add the two smoothness measures to `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs` or a helper beside it: \|delta steer\| P95 resampled to 14.08 Hz, and steering sign changes per second (research R3). **Both are reported, never combined** (FR-009)
  - In `SteerSmoothness.cs` beside the driver rather than inside it, plain C# with no Unity types, so the arithmetic the whole US2 comparison rests on is reachable from an EditMode test in milliseconds. Twelve cases in `SteerSmoothnessTests.cs`; the full EditMode suite is **87 passed, 0 failed**
  - **Both of T018's measurement traps are now unreachable rather than merely avoided.** The measure is fed `move.x` at the one place the command exists, so it cannot pick up the vehicle's rate-limited angle by accident; and it is fed only from the branch that runs while the driver holds the wheel, so the window is the run and nothing either side. The 32 s stationary tail that diluted the T018 trace cannot be produced by getting the analysis wrong later, because nothing outside the run is ever sampled
  - **The percentile is resampled, and a test pins why.** The same ramp fed at 50 Hz and at 200 Hz gives 0.0200 and 0.0188 against an expected 0.0178, agreeing inside one physics step. Differenced per step instead they would read 0.0050 and 0.00125, a factor of four apart on identical driving, which is research C14's finding about frame rate arriving a second time through the physics rate
  - **The two measures are counted at different rates, on purpose.** The P95 is resampled to 14.08 Hz because it is placed beside the human, PPO and BC columns, which were measured there. The sign-change rate is counted at the rate it is fed, because it is compared against nothing and 14.08 Hz cannot represent a reversal faster than 7.04 Hz: downsampling it would report a controller sawing the wheel back and forth as calm. Verified at 49 changes in a 0.98 s window of alternating full lock, which is 50.0 per second
  - **The deadband is not cosmetic.** `WeightedAverage` is continuous and settles near zero on a symmetric reading, where float noise alone flips the sign every step. Without the 1e-3 band the noise floor would be reported as chatter and the smoother controller would score worse than the one that cannot express a small command at all. The last non-zero side is remembered across the band, so easing out of a turn and back into the same one counts as nothing while a genuine reversal through zero counts once
  - `DriveTelemetry`'s private percentile now calls this one instead of keeping its own copy. Its own class comment warned that two copies is how a HUD shows green while the log it summarises shows red, and feature 005's figure goes in the same table as the one it computes
  - The tuner panel shows both numbers on two lines with **no verdict colour**, because the threshold that would decide a verdict is the run-to-run spread and that is T027. The sample count travels with the percentile: a run that ends at 5 s contributes about 70 points, and a 95th percentile over a handful of them is the maximum wearing a percentile's name
  - **Measured on a live lap, not only in tests.** `HeuristicWeighted`, training seed 1: `WeightedAverage | LapComplete | 27.4s | contacts 0 | markers 24 | dsteer p95 0.0493 (n 385) | sign changes 0.15/s (4 in 27.3s)`. The 385 points over a 27.3 s window is 14.10 Hz, so the resampling is running at the exported rate and not at the physics rate; the window is 0.1 s short of the run, which is the first sample landing one physics step in
  - **Two figures worth carrying into T030 and T031.** The dataset's human 95th percentile is 0.30 on track1, and this controller reads **0.0493**, about a sixth of it. And 0.15 sign changes per second is not chatter by any reading: research R2 predicted a 3 Hz oscillation at 0.6 amplitude, and the measure built specifically to catch that shape reports 4 reversals in a whole lap. **R2 is now falsified twice on two different instruments**, which is a stronger result than the first falsification alone. `MostOpen` has not been measured on this instrument yet and is the comparison T028 exists for
  - **Found while running the suite: `VehicleProfileMirrorTests` had been failing all eight cases since T006**, which bumped `schema_version` 2 to 3 and updated the python mirror test but not the Unity one. Fixed to assert against `VehicleProfileFile.ExpectedSchemaVersion` rather than a literal. Nothing had run the EditMode suite between T006 and here, which is the actual finding
- [X] T023 [US2] Write the run record per `contracts/run-record.md` from the Unity side, one row per run, `InvariantCulture` throughout. This project has hit the locale bug three times already
  - `RunRecord` is a plain struct that formats itself and `RunRecordWriter` owns the file, so the two properties the contract actually rests on are testable without a disk or a scene. Six cases in `RunRecordTests.cs`; full EditMode suite **93 passed, 0 failed**
  - **Written at the end of a run rather than by the sweep runner, against the contract's own wording.** The runner is T032 and T027 needs three recorded runs of one seed before anything in Phase 4 or Phase 5 may be interpreted, so waiting would have blocked the blocker. It is also the better arrangement: a hand-driven run and a swept run now produce the same row through the same code, where a sweep recording differently from the runs it was validated against would measure the difference
  - **Four times, not three.** The locale test sets the thread culture to `bs-Latn-BA` and asserts the row still writes `27.400`, and it guards the guard by first checking that culture really does write a comma, so it cannot pass for the wrong reason. The fourth sighting was a tuner log line printing `0,07102273` during T022's verification
  - **Measured on two live runs into one file**, `HeuristicWeighted`, seed 1, appended in order:

    ```
    seed,controller,ray_count,ray_fov_deg,ray_length_m,completed_lap,lap_time_s,checkpoints_awarded,checkpoints_total,checkpoints_skipped,wall_contacts,end_reason,steer_p95_dsteer,steer_sign_changes_per_s,time_scale,duration_s
    1,WeightedAverage,13,180.00,20.00,true,27.380,24,24,0,0,LapComplete,0.0454,0.1462,1.00,27.380
    1,MostOpen,13,180.00,20.00,false,,1,24,0,1,WallContact,0.6000,0.0000,1.00,2.900
    ```

  - **The failure row's `lap_time_s` is empty and not zero**, which is the column's whole purpose, and it still occupies its field so nothing after it shifts left
  - **The first side-by-side number, and it is not the one R2 predicted.** `MostOpen` reads a P95 of **0.6000** against `WeightedAverage`'s **0.0454**, a factor of thirteen. 0.6000 is exactly one ray step, the smallest non-zero magnitude argmax can express on the stated fan, so the quantisation argument in R2 turns up in the measure as a literal quantum rather than as an oscillation. Its sign-change rate over the run was **0.0000**: it does not chatter, it commits to one wrong direction and holds it. **Not yet a finding**, because T027's run-to-run spread does not exist and FR-015 forbids reading a difference before it does
  - `end_reason` gained `NoProgress` in `contracts/run-record.md`. T016 implemented six terminal outcomes rather than the five the contract listed, and a value the writer emits that the contract does not name is a hole the python reader would find at runtime
  - `results/heuristic/runs_*.csv` was already in `.gitignore`, so the record files stay out of the repository and the measured figures live in this file
- [X] T024 [US2] Add `WeightedAverage` to `RayControllers.cs`: the distance-weighted mean of the ray angles over `steer_max_deg`, which returns 0 on a symmetric reading by construction and needs no special case
  - **Done early, in T010, against this file's own stated ordering.** See the note there. Adoption is still T031's decision and is not settled by the function existing
- [X] T025 [P] [US2] Extend `RayControllerTests.cs` to cover `WeightedAverage`, including the symmetric fan returning exactly 0 and the all-clear fan holding heading
  - Covered in the same 18 tests. Symmetric returns exactly 0 at two different magnitudes, confirming it is the symmetry and not the distance that produces the answer
  - A fully blocked fan holds heading rather than dividing by zero, which is the total-weight guard rather than a special case
- [X] T026 [US2] Make the controller selectable for a run without editing code (FR-007), so a comparison runs the same build twice
  - A two-button toolbar at the top of the tuner panel, beside the existing mode toolbar, and `SetStrategy` was already public for the sweep runner to call. Code only, no scene edit
  - **Changing it restarts the run, and that is the point rather than a convenience.** A run that switched controller halfway would write one row of the run record describing two controllers, and both smoothness measures would be computed over a window in which the thing being measured changed. The restart makes a switch cost a run instead of corrupting one
  - The two scenes stay. They are how a demonstration is repeated, since one assembled by ticking boxes is one nobody repeats the same way twice. This is for the other job, which is running the same build twice to compare, and it is what T027 was driven with
- [X] T027 [US2] Measure the run-to-run spread: same seed, same controller, three runs, reporting the spread of lap time and both smoothness measures (FR-011). **Nothing in T028 or Phase 5 may be interpreted before this number exists**
  - **Five runs rather than the three asked for.** Three points give a range and barely a standard deviation, the runs cost 27 s each, and this is the number every later comparison is judged against. `WeightedAverage`, training seed 1, `HeuristicWeighted`, one Play session, all five `LapComplete` with 24 of 24 markers and zero contacts

    | column | mean | min | max | range | sd |
    |---|---|---|---|---|---|
    | `lap_time_s` | 27.3080 | 27.2400 | 27.4000 | **0.1600** | 0.0593 |
    | `steer_p95_dsteer` | 0.0483 | 0.0439 | 0.0502 | **0.0063** | 0.0026 |
    | `steer_sign_changes_per_s` | 0.1466 | 0.1461 | 0.1469 | 0.0008 | 0.0003 |

  - **The sign-change column's 0.0008 is not its resolution, and reading it as one would be the worst mistake available here.** All five runs recorded **exactly four reversals**; the entire spread in that column is lap-time jitter dividing the same integer. The measure cannot move by less than one reversal, which at this duration is **0.0366 per second**, forty-six times the observed spread. **T038 must compare against 0.0366, not against 0.0008**, or it will call a quantisation step a finding
  - **The lap-time spread is 0.16 s over a 27.3 s lap, six parts in a thousand**, and its source is already documented: `CarController` integrates the steering rate limit in `Update` against `Time.deltaTime`, so the wheel advances on the frame clock while the command is issued on the physics clock. Identical inputs, identical seed, identical start, and the path still differs. That is the noise floor of this rig and not something the controllers vary by
  - **The one comparison already in hand clears it easily.** `MostOpen`'s P95 of 0.6000 against `WeightedAverage`'s 0.0483 is a difference of 0.55, which is 87 times the 0.0063 spread. Whatever T028 concludes, it will not be concluding it from noise
  - **A caveat that belongs with the number.** This is one seed and one controller. It measures the rig's repeatability, not the spread across seeds, and FR-015 compares configurations over the seed set. A seed the controller barely completes will vary by more than one it completes comfortably, so 0.16 s is a floor rather than a universal tolerance
  - Driven by an `EditorApplication.update` hook living only in the MCP command's assembly, not in the repository. The real one is `SweepRunner.cs` in T032
- [X] T028 [US2] Implement the comparison in `python/heuristic/report.py`: descriptive statistics per controller over the seed set, the two smoothness measures and the outcome measures side by side, and the explicit statement of whether any difference exceeds the T027 spread
  - Filled the skeleton committed with the plan. Standard library only, matching its sibling `sweep.py`; no new dependency. `sweep.py` stays because it reads the per-step traces, which predate the run record and are still the only evidence of what happened inside a run
  - **The spread block prints before the differences, not after.** FR-015 makes every judgement below it conditional on it, and a reader who has formed an opinion from a table of means will not revise it three paragraphs later
  - **T027's quantum is encoded rather than remembered.** `Spread.threshold` returns the observed range for every measure except the sign-change rate, where it returns the larger of the range and one reversal over the mean duration. Without it the reporter would compare against 0.0008 and call a quantisation step a finding
  - **`measure_spread` returns `None` when nothing was repeated, and the report says so.** Defaulting a missing noise floor to zero would make every difference a finding, which is the most confident possible way to be wrong
  - Smoothness is described over every run including failures, while lap time is described over completed runs only. How a controller steered on a run it failed is exactly as measurable as on one it finished, and dropping the failures would flatter a controller that fails whenever it is about to steer badly
  - **The scope limit worth naming: the reporter is finished, the seed set it reports over is not.** Everything measured so far is training seed 1, and `MostOpen` has exactly one recorded run. FR-012 asks for statistics over the seed set, which is 34 training seeds, and collecting that is `SweepRunner.cs` in T032. **T030 and T031 cannot be settled on one seed** and should be read as blocked on US3 rather than on this task, which is an ordering problem in this file and not a gap in the reporter
  - Output over the seven runs recorded so far, which is the reporter working rather than the comparison being complete: `|dsteer| p95` 0.5522 apart against a spread of 0.0063, stated as exceeding it; lap time reported as not comparable, because `MostOpen` has no completed lap to have a lap time
- [X] T029 [P] [US2] Write `python/tests/test_heuristic_report.py` covering the reporter on a fixture CSV, including a failed run with an empty `lap_time_s`, which must be excluded from the lap-time mean rather than averaged as zero
  - 20 cases, every one built from a fixture CSV in `tmp_path`. Nothing reads `results/heuristic`: a test that depends on measurements someone happened to take passes for a reason unrelated to the code. Full python suite **306 passed**
  - **The empty lap time has two tests, not one.** Two clean laps at 27.4 and 27.2 average 27.3; averaged with a zero for a failure they average 18.2, which is plausible-looking and wrong. The second test pins that a literal `0.000` is a value and is kept, because a reader that fixed the first by discarding every falsy lap time would pass the first test and silently drop a real measurement. Zero is unreachable in practice, which is exactly why nothing would notice
  - FR-015's verdict is asserted **as text**, not as a boolean. The requirement is that the report says a sub-spread difference is not a finding in those words, so `"not a finding" in sentence()` is the assertion that matches what was asked for
  - Also pinned: a missing contract column is refused rather than read for what it has; `NoProgress` is counted; a single value yields no standard deviation instead of crashing; and a failed run never contributes to the spread, which is the 28.9 s against 0.100 s mistake encoded so it cannot return
- [X] T030 [US2] Record the measured comparison in `specs/005-heuristic-ray-driver/research.md` against the R2 prediction of a 3 Hz oscillation at 0.6 amplitude. **If the prediction is wrong, the falsification is the finding**, as C17 was in feature 003
  - Written as R2b, over 102 `MostOpen` runs. **R2 was right about the amplitude and wrong about the oscillation**

    | Claim | Predicted | Measured | Verdict |
    |---|---|---|---|
    | Steering amplitude | near 0.6 | P95 **0.5588** | right |
    | P95 against the smoothed controller | several times | 11.2x | right |
    | Oscillation frequency | ~3 Hz, about 6 reversals/s | **0.0077/s** | wrong by three orders of magnitude |

  - **33 of 34 runs at the stated fan reversed direction zero times**; at 120 degrees it is 34 of 34. The controller does not chatter and never did
  - The arithmetic in R2 was sound and the inference from it was not. Quantisation bounds how finely the command can be placed; it says nothing about how often the placement changes, and the argmax turns out to be stable because the longest ray slides smoothly as the car turns rather than flickering between candidates
  - **The falsification is worth more than the prediction would have been.** Had the chatter claim stood unmeasured the obvious remedy was to smooth the command, and DESIGN 4.7 nearly carried a low-pass filter for exactly that reason. Smoothing a controller that does not oscillate would have added a tuned constant, made the baseline less of a baseline, and fixed nothing
- [X] T031 [US2] If `MostOpen` performs acceptably, record that as the result and justify `WeightedAverage` on its measured merits or do not adopt it (spec US2 scenario 3)
  - **`MostOpen` does not perform acceptably. 0 of 102 runs completed a lap**, across 34 training seeds and three geometries, a mean of 2.4 markers of 24 before the first wall contact. The scenario's condition is not met
  - **`WeightedAverage` is adopted, and on completion rather than on smoothness.** 34 of 34 on every geometry tried, against 0 of 34. The smoothness gap is real and large, 0.0500 against 0.5588, but it is not the argument: a controller that never finishes cannot be preferred on how smoothly it fails
  - **It needs no tuned parameter**, which is what a baseline should look like. The critical-distance gate that was tried instead is recorded as a measured negative result: its threshold had to be guessed, it did not transfer between two tracks of equal difficulty, and it never prevented the collision it was aimed at
  - The adoption is not a claim that argmax is a bad idea in general. It is the measured statement that follow-the-gap over a 13-ray fan on these tracks discards the information it needs, which R2a explains and R10 confirms no geometry repairs

**Checkpoint**: the design decision behind the smoothed controller is measured, not asserted.

---

## Phase 5: User Story 3 - Testing whether the sensing geometry is right (Priority: P2)

**Goal**: an answer to the question T059 raised, that seven of thirteen rays may be reporting the
same lateral distance while three carry all the cornering information.

**Independent Test**: run the same seed set under at least two ray arrangements and compare.

- [X] T032 [US3] Create `unity/SelfDrivingSim/Assets/Scripts/Track/SweepRunner.cs`: iterate seeds inside one Play session, rebuilding the track and resetting the car between runs. **Restarting the editor per seed costs more than the entire SC-004 budget** (research R4)
  - A coroutine over controllers, then seeds, then repeats. Added to the `TrackBuilder` object in `HeuristicWeighted.unity` with `runOnStart` off; the script, its `.meta` and the scene edit are one commit per the scene lock
  - **It writes nothing itself.** `HeuristicDriver` already appends a row when a run ends, so a swept run and a hand-driven run produce the same row through the same code. A runner with its own writer would be a second author of one format, and the first disagreement between them would surface in the analysis rather than at the keyboard
  - **The frame between tearing down a track and building the next is required, not politeness.** In play mode `Destroy` is deferred to the end of the frame, so clearing and rebuilding in one breath leaves the car sharing a frame with two sets of barriers, one of them where the old track was. The first contact would be recorded against the new seed and the record would blame a track the car was never on. `TrackBuilder.Seed` was added as a setter that deliberately does **not** rebuild, so that ordering stays the caller's decision
  - The wait loop watches `driver.Outcome` rather than a timer. A runner with its own timeout would be a second opinion about when a run stopped, and the two would disagree exactly on the runs that are hardest to interpret
  - Every track file is checked to exist before the first lap. A sweep that dies twenty minutes in has spent the whole SC-004 budget learning something a directory listing knew
- [X] T033 [US3] Set `Time.timeScale` and `Time.maximumDeltaTime` in `SweepRunner.cs`, leaving `Time.fixedDeltaTime` alone. A coarser physics step would mean the sweep measured the step size rather than the geometry
  - `fixedDeltaTime` untouched. `maximumDeltaTime` raised to `max(current, timeScale * 0.1)`, which leaves enough headroom for a frame as slow as ten per second to still deliver the scale that was asked for. Without it Unity clamps the catch-up and the run record's `time_scale` column would carry the number the field was set to rather than the one the run achieved, which is the exact lie that column exists to prevent
  - Restored on `OnDisable` as well as at the end of a sweep. `timeScale` survives leaving play mode, and the next session would run four times too fast with nothing on screen to say why
- [X] T034 [US3] Verify the acceleration: run one seed at the swept scale and at 1x and confirm the outcome matches. **A sweep that is fast and wrong is worse than one that is slow.** Lower the scale until they agree and record the figure that survives
  - Twelve runs, `WeightedAverage` on training seed 1, three repeats at each of 1x, 2x, 4x and 8x, judged against T027's spread. Full table and argument in `research.md` R4a

    | Scale | lap mean | lap range | p95 mean | p95 range | reversals | verdict |
    |---|---|---|---|---|---|---|
    | 1x | 27.280 | 0.080 | 0.0464 | 0.0079 | 4, 4, 4 | reference |
    | 2x | 27.353 | 0.020 | 0.0431 | 0.0024 | 4, 4, 4 | **survives** |
    | 4x | 27.400 | 0.160 | 0.0446 | 0.0024 | 4, 4, **6** | fails |
    | 8x | 27.633 | 0.480 | 0.0538 | 0.0210 | 4, 4, 4 | fails |

  - **Judged the way this task words it, 8x passes, and that would have been the wrong answer.** All twelve completed the lap with 24 of 24 markers and zero contacts. The outcome is the least sensitive thing the record carries and it is not what US2 reports, so the criterion used here is the outcome **and** both smoothness measures staying inside the T027 spread
  - **4x fails in the sign-change column**: one run of three recorded six reversals where every other run at every scale recorded four, which is twice the quantum that measure can resolve. **8x fails on amplitude**: 0.353 s of lap-time drift against a 0.160 s floor, and a within-scale range of 0.480 s, so the rig has stopped reproducing itself
  - **The surviving scale is 2x**, and the degradation is not monotonic: 8x recorded four reversals in all three runs while 4x did not. 4x is not safer than 8x because its reversal count happened to be the thing that broke
  - **This falsifies R4's central claim** that raising `timeScale` alone "changes nothing about the simulation itself". `CarController` integrates the steering rate limit in `Update` against `Time.deltaTime`, so a frame covering four times the simulated time moves the wheel four times as far. R4's table is kept as written because it is the prediction being falsified: it costed acceleration as free
  - **SC-004 is now in direct conflict with the correctness of the numbers**, recorded here rather than at T039 because this is where it was found. 34 seeds at the measured 27.3 s lap take 7.7 minutes at 2x and 5.2 at 3x, so the five-minute budget needs at least 3.1x, which is past where the measurements stop reproducing. The conflict is structural: it would disappear if the steering integration moved to `FixedUpdate`, and that is a change to the vehicle, which this feature's scope forbids
- [X] T035 [US3] Load the seed set from `results/tracks/seed_split.json`, **training seeds only** (research R5). Choosing a geometry against the evaluation seeds would fit the environment to the tracks the learning agent is later judged on
  - Read from the split file, never typed into the scene. A list in the Inspector is a copy of a decision recorded elsewhere and the two drift silently: the split file is what BC and PPO train against, so a sweep over a hand-typed subset would choose a geometry against different tracks from the ones the comparison later uses
  - Refuses loudly on a missing file, an unreadable one, or an empty `accepted_seeds`, rather than falling back to a default set. A sweep over the wrong seeds produces a complete, plausible, wrong answer and nothing downstream could tell
  - `SeedSet.Eval` exists and warns when selected, because reporting a final result on the held-out seeds is legitimate and choosing a configuration on them is not. Verified: all 34 training seeds have a track file in `Assets/Tracks`, and 1001-1010 are the ten evaluation seeds
- [X] T036 [US3] Drive the sensing configuration from the exported block so a sweep is a file the runner writes, not a scene edit (FR-013, depends on T008)
  - **Half of this was already done, and this task's wording is the older of two descriptions.** T008 built `CarAgent.ConfigureFan` and the `FanOverridden` flag that suppresses the drift check, and `contracts/sensing-block.md` was corrected during implementation to say the sweep sets the fan **programmatically at runtime, not by rewriting the file**: rewriting per configuration needs a reload between configurations and SC-004 cannot afford one. A first attempt here added a duplicate `SetFan` before finding the existing API; it was removed rather than left as a second way to do one thing
  - What was missing was the caller. `SweepRunner` gained a `FanConfig[]`, the fan as the **outermost** loop so every arrangement covers the same seeds under the same controllers (FR-014), and a restore of the scene's own fan when the sweep ends. Nested the other way, an interrupted sweep would leave one configuration with more seeds than another and the comparison would be between seed sets wearing the names of two geometries
  - Ray length is deliberately not swept. It is derived from the stopping distance (research C11) rather than chosen, so sweeping it would be sweeping a consequence of the braking figure and calling the result a sensing finding
  - **A two-seed dry run caught a real bug before the full sweep ran, which is the entire reason it was run.** `agent` resolved to null in `Awake` while `track`, `driver`, `placer` and `car` all resolved, `ApplyFan` bailed out **silently**, and twelve rows came back all reading `ray_fov_deg 180.00` while claiming to be three arrangements. The rows were internally consistent and completely wrong
  - The silent bail was the defect, not the null. `SweepRunner` already refuses to start over a missing track file for exactly this reason, and the fan path had no equivalent. Now: the agent is resolved lazily through the car and the driver before falling back to a scene search, `Begin` **refuses to start** a fan sweep it cannot apply, and `ApplyFan` stops the sweep and logs an error rather than continuing. A sweep that cannot vary the thing it is sweeping must not produce a complete, plausible answer
  - Re-run after the fix, two seeds, and the fan does change. `WeightedAverage` on seed 1 reads a P95 of 0.0413 at 180 degrees, 0.0943 at 120 and 0.2031 at 90, against a noise floor of 0.0063
- [X] T037 [US3] Run the full sweep over at least two arrangements, covering at minimum the angular width of the fan, every configuration over the same seeds (FR-014)
  - Three arrangements, both controllers, all 34 training seeds, one run each: **204 runs in 1402 real seconds** at the 2x T034 found survives. Then a fourth arrangement, 34 more runs, to separate two things the first three varied together. Full table and argument in `research.md` R10
  - **`MostOpen` completed 0 of 34 under every geometry.** 102 runs, 102 wall contacts, a mean of 2.4 markers of 24 before the first. Widening or narrowing the fan does not help because the fault is not the fan: R2a established that argmax discards every ray but one, and no arrangement of rays fixes a rule that throws all but one away
  - **`WeightedAverage` completed 34 of 34 under every geometry**, so completion does not discriminate between the fans and the trade is between speed and smoothness

    | Fan | Spacing | Lap time | \|dsteer\| P95 |
    |---|---|---|---|
    | 13 / 180 deg | 15.0 | 26.508 | **0.0500** |
    | 25 / 180 deg | 7.5 | 23.655 | 0.0656 |
    | 13 / 120 deg | 10.0 | 22.783 | 0.1156 |
    | 13 / 90 deg | 7.5 | **22.043** | 0.1341 |

  - **The first three arrangements were confounded and the fourth measures by how much.** Varying `ray_fov_deg` at a fixed ray count also varies the spacing, which is what `HeuristicDriver.ForwardCone` uses to size the forward cone, so the sweep was moving the steering input and the speed rule together. 25 rays over 180 has the same 7.5 degree spacing as 13 over 90 with a full-width fan, and it splits them: **lap time follows the spacing** (2.853 s of the 4.465 s gap), **roughness follows the fan width** (the percentile roughly doubles at fixed spacing when the fan narrows). Neither is what "sweeping the angular width of the fan" sounds like it measures
  - Not an averaging artefact: 13 over 90 is faster than 13 over 180 on **34 of 34 seeds** and rougher on **33 of 34**
  - Track rebuild overhead measured at **0.08 s per run, 1 percent of wall time**, so R4's decision to iterate inside one session rather than restart per seed cost essentially nothing
- [X] T038 [US3] Extend `python/heuristic/report.py` to report the sweep and state whether any difference exceeds the T027 run-to-run spread (FR-015). **A difference smaller than the noise is not a finding** and must be said in those words
  - **No extension was needed and none was written.** T028 built the reporter to group by controller **and sensing configuration** and to judge every pairwise difference against the spread, because the contract asked for both from the start. Running it over the 204-row sweep produced the six-group comparison unchanged
  - The sentence FR-015 requires is being earned rather than merely printed. Every `WeightedAverage` fan pair reports its sign-change difference as **"smaller than the run-to-run spread of 0.0366, so it is not a finding"**, which is the correct answer: the three fans genuinely do not differ in reversal rate, and only the quantum floor from T027 prevents 0.0019 apart from being read as a result
- [X] T039 [US3] Confirm SC-004: one configuration over all 34 training seeds in under five minutes, with the measured time recorded
  - **SC-004 is not met, and this is recorded as a failure rather than worked around.** One configuration of the controller that actually completes laps takes **7.56 minutes** at 2x for the incumbent fan, 6.50 at 120 degrees and 6.29 at 90. `MostOpen` passes at 1.17 minutes, which only means a controller that crashes in 4 seconds sweeps quickly
  - The budget needs at least 3.1x. **2x is the fastest scale at which the measurements reproduce** (T034, R4a), so the five-minute budget and the correctness of the numbers cannot both be had. At 4x the sweep would take 3.80 minutes and would be measuring the frame clock
  - The cause is structural: `CarController` integrates the steering rate limit in `Update` against the frame clock. Moving it to `FixedUpdate` would remove the conflict, and that is a change to the vehicle, which this feature's declared scope forbids. **Recorded, not fixed**, and the decision to widen scope is not this task's to take
  - R4's five-minute figure assumed a 34.3 s lap and free acceleration. The lap is 26.5 s and the acceleration is not free, so the two errors point in opposite directions and the second is much the larger
- [X] T040 [US3] Write the answer into `specs/005-heuristic-ray-driver/research.md`: whether the current fan is worse than, equal to, or better than the alternatives tried. **If nothing beats the current geometry, record it as measured-and-kept rather than quietly left alone** (spec US3 scenario 3)
  - Written as R10. **The answer is that nothing dominates the current geometry, and the current geometry does not dominate anything either.** 13 rays over 180 degrees is the smoothest of the four tried and the slowest; 13 over 90 is the fastest and the roughest; all four complete 34 of 34. Every difference exceeds the noise floor, so this is a real trade and not a ranking
  - **Decision: measured and kept.** 13 over 180 stays as a deliberate choice. FR-009 forbids collapsing speed and smoothness into one verdict, and lap time is explicitly out of scope for this feature, so there is no measure in hand that would justify trading smoothness for it
  - **25 over 180 is the candidate worth naming**, 2.853 s faster for 0.0156 of extra roughness at full fan width. Not adopted, because it doubles the ray half of the observation vector and DESIGN 4.3 chose 13 partly for what the network must learn to ignore. That cost is real and this feature does not measure it, so adopting on this feature's numbers would be choosing on whichever measures happened to be in hand
  - Recorded with the warning `contracts/sensing-block.md` requires: adopting any of them invalidates every sensing result measured against the old fan and any model trained against it

**Checkpoint**: the sensing geometry has been tested rather than assumed.

---

## Phase 6: User Story 4 - A fourth column in the final comparison (Priority: P3)

**Goal**: the scripted driver described by the same measures as the human, PPO and BC columns.

**Independent Test**: produce the steering distribution and confirm it uses the same measures as the
existing driver comparisons.

- [X] T041 [US4] Produce the scripted driver's steering distribution in `python/heuristic/report.py` using the same measures and summary shape as the feature 002 and 004 comparisons, so M5 consumes it without a translation step
  - `SteeringDistribution` in `report.py`, built from `eda.stats.describe`, `eda.stats.relative_frequency_histogram` and `compare_drive.resample`. **Nothing here computes a statistic of its own**, which is the rule feature 004's `evaluate.py` was built around: a second definition of "mean steering" in the repository is how two correct-looking numbers answer two different questions in the same table (research R5)
  - Read from the **per-step traces**, not from the run record. The record carries one summary number per run and M5 needs the distribution behind it. `results/heuristic/us4`, one sweep of **34 training seeds against both controllers, 68 runs**
  - **Two distributions, not one**: the steering command at 14.08 Hz, and the per-step `|delta steering|` on the same grid. Feature 002 reports both because a driver can sit at extreme angles smoothly or at modest angles violently
  - **Each run is differenced separately** and the pieces concatenated, never across the join. Differencing across the seam invents a jump no driver made, which feature 002 hit at the track1/track2 junction
  - A trace written before the `seed` and `controller` columns existed returns `None` rather than raising. Several hundred are on disk; they are still evidence about the runs that produced them and they cannot say whose runs they were, so they are skipped rather than pooled into whichever distribution was built first
  - Written to `results/heuristic/us4_steering.md`, which is the artefact M5 consumes. **`.gitignore` needed a fix to allow it**: `results/heuristic/trace_*.csv` does not match `results/heuristic/us4/trace_*.csv`, so 68 raw traces were about to enter history through a subfolder. Added the `**/` forms
- [X] T042 [US4] Report descriptive statistics for every distribution touched: sample size, mean, variance, min, max, and a relative-frequency histogram (Principle IX)
  - Every distribution printed carries n, mean, variance, sd, min, max and P1/P5/P50/P95/P99, including the BC columns read in for T043. The histogram is relative frequency, printed as text rather than saved as a PNG: this report is read in a terminal beside the tables it belongs to, and a figure would be a second artefact to keep in step with the numbers next to it
  - **The sample counts are the finding, not the bookkeeping.** `MostOpen` contributes **1,850** samples against `WeightedAverage`'s **12,691**, because it ends in a wall after about 2.7 s. A pooled distribution weights each run by how long it survived, so these describe *steering that happened* and not per-run averages. A controller that crashes early is under-represented in its own column rather than penalised in it, and any reading of the two columns as equally sampled is wrong
  - **The scripted column is not zero-mean, and the cause is the track and not the driver.** `WeightedAverage` averages **-0.1996** over a lap, per-seed means from **-0.2141 to -0.1893**, **the same sign on 34 of 34 seeds**. `generator.py` samples every centre line as `r(theta)` over `theta` in [0, 2 pi), so every track is a closed loop wound the same way and every lap is one net turn in one direction. The human column pools two recordings at **+0.0055**. Placed beside it in M5 without this sentence, a structural property of the generator reads as a steering bias in the controller
  - Cross-check against the run record, which computes the P95 in Unity on the same definition: the record's mean of the per-run P95 is **0.0496**, the trace-pooled P95 is **0.0465**. Two code paths in two languages over the same runs, agreeing to within the difference between pooling and averaging per-run summaries. The C# and python halves of this measure are not drifting
- [X] T043 [US4] If the scripted driver outperforms a learned driver on any measure, report it plainly rather than omitting it (spec US4 scenario 2)
  - **It does, and here it is.** `WeightedAverage` against `bc_balanced_v01` on `|delta steering|`, the learned figures read from `results/bc/run_bc_balanced_v01/distributions.json` rather than recomputed:

    | measure | `WeightedAverage` | `bc_balanced_v01` | gap |
    |---|---|---|---|
    | mean | **0.0157** | 0.0248 | 0.0091 scripted lower |
    | P50 | **0.0078** | 0.0187 | 0.0109 scripted lower |
    | P95 | **0.0465** | 0.0692 | 0.0227 scripted lower |
    | P99 | 0.1649 | **0.1121** | 0.0528 learned lower |
    | max | 0.2760 | **0.2500** | 0.0260 learned lower |

  - **The scripted driver is calmer in the body of the distribution and has the heavier tail.** It holds a steady arc for most of a lap and occasionally corrects harder than the model ever does on recorded frames. Both halves are printed in one breath by construction: `report_against_learned` prints the losses in the same block as the wins, so omitting the unflattering half would take an edit rather than an oversight
  - **Only `|delta steering|` crosses.** The steering command itself is two different roads, and a mean of -0.20 against -0.02 compares the tracks. `CROSS_MEASURES` is a named tuple of the statistics both sides define identically, so a statistic that means different things on the two sides cannot arrive by iterating a summary
  - The three P95 gaps clear **0.0063**, T027's run-to-run spread on that measure. **The learned side has no equivalent number**: feature 004's 0.0005 tolerance is the best-epoch validation error and T040 says explicitly it applies to nothing else, so borrowing it here would judge a distribution against an accuracy figure. Every gap is above one side's noise floor and unjudged against the other's, and the report says so rather than implying a two-sided test
  - **`MostOpen` is smoother than the learned driver at the P50, where it reads exactly 0.0000.** That is 34 runs of committing to one direction and holding it into a wall. Smoothness alone ranks a crash highly, so the report prints that sentence under every comparison rather than leaving the reader to notice the completion row above (FR-009)
  - **Three things the comparison is not**, printed every time because any of them omitted turns a distribution comparison into a claim about driving: the learned driver **never drives** (feature 004 FR-018), so lap completion has no BC column and 34 of 34 is not a win but a measure the other side lacks; the roads differ; and the clocks agree on track1 by construction and not on track2. The per-track BC rows are printed for that last reason, and the conclusion does not turn on which is used — 0.0157 and 0.0465 are below both
  - Nine cases in `python/tests/test_heuristic_report.py`, including the missing-artefact path: a learned column that is not on disk prints **"No learned column"** rather than skipping the section, because the comparison being absent and the artefact being absent are different statements. Full suite under `.venv`: **323 passed, 3 skipped** (counted properly in T046; a first reading of 179 was `tail -3` cutting pytest's progress lines and being mistaken for a total)

**Checkpoint**: M5 has its baseline column.

---

## Phase 7: Polish and Cross-Cutting

- [X] T044 [P] Update `README.md` with the heuristic driver commands, keeping it a literal reproduction recipe (Principle VI)
  - Three steps in the "Upotreba" block: one hand-driven run in `HeuristicWeighted`, the sweep through `SweepRunner` with the Inspector fields it actually needs, and the reporter with `--spread` and `--traces` explained by what they do rather than by their names
  - **The recipe carries the two things that make a wrong number**: `timeScale = 2` with the reason 4x measures the frame clock, and the note that without `--spread` no difference is a finding
  - Expected values written in beside the commands: 34 of 34 at 26.496 s against 0 of 34, and the repeat spread of 0.16 s and 0.0063. A recipe with no expected output cannot tell a working run from a broken one
  - **Two stale test counts fixed while here.** `pytest python/tests` was documented as `280 prolazi` under `.venv` and `141 prolazi` under `.venv-bc`; measured now at 323 and 377. The `.venv-bc` figure was stale by 236 tests, which means it predates feature 004 entirely
  - Added the `| tail` warning beside the existing `-q` one. The README already warned that a second `-q` hides the pass count; this feature found the neighbouring way to lose it, and the warning that was there did not cover it
- [X] T045 [P] Reconcile `DESIGN.md` with what was actually built. T001 wrote the intent; this checks the code did not diverge from it
  - **Checked rather than assumed, and the code did not diverge.** The single sensing source exists in `vehicle_profile.json` with `ray_count` 13, `ray_fov_deg` 180 and `ray_length_m` 20, so §4.7's "nijedna vrijednost se ne mijenja, mijenja se samo odakle se čita" is literally true. Both controllers are kept. The driver reads rays and speed and nothing else. It is not tuned on lap time, which T040's decision to keep 13/180 while measuring a faster fan is the evidence for
  - **Three things §4.7 promised to record and had not**, all added: the falsified 3 Hz prediction, the 34-seed results, and the sensing sweep's answer
  - §4.7.1 was one seed and stayed one seed while a 34-seed sweep sat measured. Added **§4.7.2** with the full table rather than editing the seed-1 one, because the single-seed result is what the design was first argued from and overwriting it would hide that the argument was made on a sample of one
  - The prediction paragraph now says what was measured instead of what was expected: `MostOpen` does not oscillate at 3 Hz, it holds one wrong direction at 0.0000 reversals per second with a P95 of exactly 0.6000. **The prediction got the cause right and the consequence wrong**, and §4.7's own rule is that this is a finding
  - §7's comparison table already promised that a heuristic win over a learned driver would be stated openly. It now is, with the pointer to `results/heuristic/us4_steering.md` and with the sentence that separates the win from the non-win: the smoothness win is a win, and 34 of 34 laps is a measure BC does not have
- [X] T046 Run `pytest python/tests` under `.venv` and `.venv-bc` and record both counts against the T004 baseline
  - **`.venv`: 323 passed, 3 skipped** in 256.92 s, against T004's `280 passed, 3 skipped`. **`.venv-bc`: 377 passed** in 264.01 s, against T004's `334 passed`
  - **Both grew by exactly 43**, which is `test_heuristic_report.py` (37) plus `test_sensing_mirror.py` (6), the two files this feature added. The two environments moving by the same amount is the check worth having: a test that only runs where torch is installed would show up as a mismatch here, and none did
  - The 3 skips are the pre-existing ones and are unchanged in count and in reason. Nothing this feature added skips
  - **The count was misread once before it was measured.** `pytest -q | tail -3` was read as a total of 179 and recorded as one in T043; it was the last three progress lines of a 323-test run. `-q` prints no total until the summary line, which `tail` had cut. Recorded because the wrong number was already written into this file before the right one existed, and the T043 note now carries the correction rather than a silent edit
- [X] T047 Run all Unity EditMode tests and confirm green
  - **93 passed, 0 failed, 0 inconclusive, 0 skipped, 3.21 s**, run through `TestRunnerApi` over the whole EditMode suite rather than per file. Same count T023 recorded, so nothing regressed between there and the end of the feature
  - **The fifth sighting of the locale bug is in the result line itself**: Unity logged the duration as `3,21s`. The Editor is running under a comma-decimal culture, which is exactly the condition `RunRecordTests` pins with `bs-Latn-BA`. The run record is written through `InvariantCulture` and is unaffected; a figure formatted for a human by Unity's own default is not, and that is the difference the tests exist to keep
- [X] T048 Walk `specs/005-heuristic-ray-driver/quickstart.md` end to end and correct every figure. **Its expected values are currently predictions, and are marked as such.** The last two features both had the walk falsify something: T042 found a collection error hiding a zero-test run, T068 falsified T023's explanation of the speed check
  - **The walk falsified four commands and two tables**, which makes it three features in a row. Every corrected line keeps what it used to say beside what is true, so a reader can see which predictions this feature got wrong rather than a clean file that looks like it was right all along
  - **Two flags in the file were never implemented**: `--repeat-check` and `--sweep`. Both exit with `unrecognized arguments`. The second is not even needed, since the reporter groups by controller and configuration always. A quickstart nobody walks documents an interface nobody built
  - **"Writes `results/heuristic/comparison.md`" is false.** The reporter prints and writes nothing; the kept reports are written from what it printed. Left as a correction rather than by quietly making the code match the doc, because which of the two is right was a decision and not a typo
  - **Section 2 described the wrong scene and the wrong way to pick a controller**, from before FR-007 was satisfied: Inspector fields on `Track.unity` rather than the toolbar in `HeuristicWeighted.unity`. This is the section a reader follows first, so it was the most expensive line in the file to leave wrong
  - The R2 prediction table now carries a measured column beside the predicted one. Every predicted cell is wrong in a different way: P95 twelve times higher rather than "several", reversals at 0.0080 rather than "near 3", completion 0 of 34 rather than "possibly acceptable"
  - The budget table was predicted from a 34.3 s lap and free acceleration. The lap is 26.5 s, acceleration is not free, and the second error is the larger: 2x measures at **7.56 min** against a five-minute budget. Replaced with the measured rows and the SC-004 failure stated in place
  - Two additions rather than corrections: **section 6** for `--traces` and the BC comparison, which did not exist when the file was written, and the `| tail` warning beside the `-q` one in the tests section. The end-of-feature counts (323, 377, 93) now sit under the baseline ones so the file can be used to tell a working checkout from a broken one
  - Section 1 re-run to confirm: `python -m python.track.vehicle` is idempotent and leaves `git diff` empty; `test_sensing_mirror.py` 6 passed in 0.07 s
- [X] T049 Confirm FR-017: this feature has not satisfied or substituted for feature 003's human keyboard lap, and T051 still stands on its own
  - **Confirmed, and the strongest evidence is that this feature's own keyboard task is still open.** T020 asks for a hand-driven lap with the driver disabled and is recorded as blocked, needing a person at the keyboard. A feature that had quietly absorbed the human lap would have closed that task on the scripted one
  - Feature 003 T051 was completed before this feature existed, on five accepted seeds, and nothing here touched it. No task in this file cites a scripted run as evidence for keyboard drivability, and no scripted figure was written into feature 003's results
  - The code keeps the two apart rather than the documentation doing it alone: exactly one of the driver and the human holds the wheel, and the smoothness measures are fed only from the branch that runs while the driver holds it. A hand-driven lap cannot contribute a sample to a scripted measure even by mistake
  - DESIGN §4.7 states the distinction as a claim rather than an arrangement: a scripted lap proves the track is completable, which is a different sentence from the vehicle being drivable by a person. Both sentences are needed at the defence and only one of them is now backed by this feature
- [X] T050 If the sweep recommends a new arrangement, record the decision with its measurement **before** applying it, stating that it invalidates previously measured sensing results and any model trained against the old fan (FR-018). Applying it is out of scope for this feature
  - **The sweep recommends nothing, so nothing is applied, and the not-applying is the recorded decision.** T040 measured four arrangements: all four complete 34 of 34, 13/180 is the smoothest and slowest, 13/90 the fastest and roughest. Every difference clears the noise floor, so it is a real trade and not a ranking, and there is no measure in hand that justifies trading smoothness for lap time when lap time is explicitly out of this feature's scope
  - **25 over 180 is named rather than buried**: 2.853 s faster for 0.0156 more roughness at full fan width, and not adopted because it doubles the ray half of the observation vector, a cost this feature does not measure. Choosing on the measures that happen to be in hand is how a sweep produces a confident wrong answer
  - The FR-018 warning is written where an adopter would read it, in `contracts/sensing-block.md` and in R10: changing the fan invalidates every sensing result measured against the old one and any model trained against it. **`vehicle_profile.json` still reads 13 / 180.0 / 20.0**, verified in T045

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
