# Tasks: Unity Driving Environment (M2)

**Input**: Design documents from `specs/003-unity-environment/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. The spec requires them (FR-009, FR-015, FR-016, SC-007 to SC-010) and
contracts/track-generator-api.md carries a test contract with both directions of evidence.

**Organization**: grouped by user story so each can be finished and checked on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel, different files, no dependency on an unfinished task
- **[Story]**: US1, US2, US3, mapping to the priorities in spec.md
- Every task names the file it touches
- Tasks inserted after the first pass carry a letter suffix (T012a, T044a, T051a). Existing IDs
  stay put, so a review comment that names a task still names the same task

## Path conventions

- Python: `python/track/` for source, `python/tests/` for tests, matching the existing
  `python/eda/` layout
- Unity: `unity/SelfDrivingSim/Assets/`
- Outputs: `results/` and `unity/SelfDrivingSim/Assets/Tracks/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: folders, packages and empty scaffolding, no logic

- [ ] T001 Create `python/track/__init__.py` as an empty package, matching the `python/eda/` layout
- [ ] T002 [P] Install `com.unity.splines` and `com.unity.probuilder` through Window > Package Manager and confirm both appear in `unity/SelfDrivingSim/Packages/manifest.json` and `packages-lock.json`
- [ ] T003 [P] Create `unity/SelfDrivingSim/Assets/Scripts/Vehicle/`, `Scripts/Track/`, `Scripts/Agent/`, `Scripts/Logging/` and `unity/SelfDrivingSim/Assets/Tracks/`
- [ ] T004 [P] Create `unity/SelfDrivingSim/Assets/Tests/EditMode/` with an assembly definition referencing `Unity.InputSystem`, `Unity.Splines` and the project runtime assembly
- [ ] T005 [P] Create `results/tracks/` and `results/drive_logs/`, each with a `.gitkeep`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the vehicle profile. Every number in User Stories 1 and 2 derives from it, so nothing
else can start until it exists and is proven.

**CRITICAL**: no user story work begins until T012 passes.

- [ ] T006 Write every named constant in `python/track/config.py` from the research summary table: `WHEELBASE_M` 2.5, `STEER_MAX_DEG` 25.0, `RADIUS_MARGIN` 1.3, `V_MAX_MS` 10.0, `DATASET_SPEED_P99` 17.49, `TRACK_R0_M` 30.0, `HARMONICS` (2,3,4,5), `AMPLITUDE_RANGE` (0.40, 0.70), `SAMPLES_PER_TRACK` 2000, `TRACK_WIDTH_M` 6.0, `MIN_SEPARATION_M` 12.0, `N_CHECKPOINTS` 24, `START_LATERAL_M` 1.5, `START_YAW_DEG` 10.0, `RAY_COUNT` 13, `RAY_FOV_DEG` 180.0, `RAY_LENGTH_M` 20.0, `COMPARE_HZ` 14.08, `MATCH_DISTANCE_THRESHOLD` 0.05, `W1_SELF_CONSISTENCY` 0.0231, `W1_STRUCTURELESS` 0.1047, `W1_HUMAN_TO_HUMAN` 0.2635, `TRAIN_SEEDS` range(1,41), `EVAL_SEEDS` range(1001,1011). Each carries a comment naming its research decision. No import from `python/eda`
- [ ] T007 Add the M1 calibration envelope constants to `python/track/config.py`, read once from `results/eda/m1_stats.json` and pasted as named values: steering maximum, per-frame steering-change P95 for both recordings and its maximum, speed P99 and maximum. These are the envelope FR-009 reports against
- [ ] T008 Implement the frozen `VehicleProfile` dataclass and `build_profile()` in `python/track/vehicle.py`, with `r_min_m`, `r_floor_m` and `max_required_steer` computed as properties and never stored independently
- [ ] T009 Implement `radius_for_steering`, `steering_for_radius`, `stopping_distance_m` and `normalise_speed` in `python/track/vehicle.py`. No function converts a dataset speed into a physical unit
- [ ] T010 Write `python/tests/test_vehicle.py`: `r_min_m` equals 5.361 m, `r_floor_m` equals 6.969 m, `max_required_steer` equals 0.789; the two steering functions round-trip across `[0, 1]`; `max_required_steer` stays fixed while `wheelbase_m` sweeps 1.5 m to 4.0 m; a radius outside the achievable range is rejected; the radius table in research C1 is reproduced row for row
- [ ] T011 Implement `export_profile()` in `python/track/vehicle.py`, writing `unity/SelfDrivingSim/Assets/Tracks/vehicle_profile.json`, and commit the file
- [ ] T012 Create `unity/SelfDrivingSim/Assets/Scripts/Vehicle/VehicleProfile.cs` mirroring the Python type field for field, plus `unity/SelfDrivingSim/Assets/Tests/EditMode/VehicleProfileMirrorTests.cs` asserting every field matches the committed `vehicle_profile.json`. A drift shows up here rather than as wrong geometry

- [ ] T012a Write the **decided** vehicle values into `DESIGN.md` sections 4.2 and 4.4 in a `docs:` commit before any Phase 3 code exists: wheelbase 2.5 m, steer_max 25 degrees, radius margin 1.3 and the 21.1 percent steering reserve it buys, `r_min` 5.361 m, `r_floor` 6.969 m, `max_required_steer` 0.789, and the decision that top speed is a stated simulation constant rather than a derived figure. Constitution Principle V requires the design to be written before it is implemented, not after (research C1 to C3)

**Checkpoint**: the car's limits exist in one place, are derived rather than typed twice, Python and C# agree, and DESIGN.md says so before any code depends on it.

---

## Phase 3: User Story 1 - A car you can drive, calibrated to the dataset (Priority: P1) MVP

**Goal**: a keyboard-drivable car on a bounded flat plane whose every limit traces to an M1 measurement.

**Independent Test**: press Play, drive one minute, run the drive log through `compare_drive`, and confirm steering range, steering rate, top speed and acceleration all sit inside the measured envelope with the car still upright.

### Implementation for User Story 1

- [ ] T013 [US1] Create `unity/SelfDrivingSim/Assets/Scenes/FlatGround.unity`: a bounded plane large enough for a full-lock circle plus margin, a chase camera, a light and one spawn point. Scene holds references only, no logic (Principle IV scene lock)
- [ ] T014 [US1] Implement `unity/SelfDrivingSim/Assets/Scripts/Vehicle/CarController.cs` with WheelCollider physics, reading limits from `VehicleProfile` and input through the existing `InputSystem_Actions.inputactions`. W and S for throttle and brake, A and D for steering
- [ ] T015 [US1] Implement the steering ramp in `CarController.cs` using `steer_rate_norm_per_s`, so holding a key moves the input from centre to full lock over a stated time rather than snapping (FR-005, research C4)
- [ ] T016 [US1] Add the boundary or out-of-bounds reset to `CarController.cs` and `FlatGround.unity` so a run cannot end with the car falling indefinitely (FR-012)
- [ ] T017 [US1] Implement `unity/SelfDrivingSim/Assets/Scripts/Vehicle/StabilityMonitor.cs` checking the three research C5 conditions per drive: body tilt or roll past 45 degrees while all four wheels were grounded the previous step, drift over 0.1 m in 10 s with no input, and falling through the surface or entering an unrecoverable state. It records which fired and on which run (FR-011)
- [ ] T018 [US1] Implement `unity/SelfDrivingSim/Assets/Scripts/Logging/DriveLogger.cs` writing `results/drive_logs/<timestamp>.csv` with the dataset's own columns: `steering`, `throttle`, `brake`, `speed`, plus `t` and `source` (FR-008)
- [ ] T019 [US1] Implement `python/track/compare_drive.py`: load a drive log, resample to `COMPARE_HZ`, normalise speed by the log's own P99, compute steering, steering-change and speed distributions, and report per quantity whether it sits inside the M1 envelope, naming any that does not (FR-009, research C14)
- [ ] T020 [US1] Add the `python -m python.track.compare_drive <csv>` command line entry to `python/track/compare_drive.py`
- [ ] T021 [US1] Write `python/tests/test_compare_drive.py`: resampling a synthetic log to 14.08 Hz gives the expected step count and per-step differences; normalisation is by the log's own P99 and never by a unit conversion; a log inside the envelope passes and a log with one quantity pushed outside is named as failing
- [ ] T022 [US1] Drive a full-lock circle in `FlatGround.unity` at low speed, measure the diameter, and confirm it agrees with `r_min_m` 5.361 m within 10 percent. Record the measurement (SC-004, FR-006)
- [ ] T023 [US1] Drive one minute by keyboard, run `compare_drive`, and tune `steer_rate_norm_per_s` in `python/track/config.py` and `VehicleProfile.cs` until the 95th-percentile steering change is within a factor of two of the recorded human figure at 14.08 Hz. Record the achieved value (FR-005, SC-002, SC-005)
- [ ] T024 [US1] Confirm normalised top speed and the achievable acceleration and deceleration agree with the dataset within 10 percent on the normalised scale, adjusting `accel_ms2` and `brake_ms2` in config if not (FR-003, FR-004, FR-007, SC-003)
- [ ] T025 [US1] Run the stress case: full-lock turns at top speed and full-brake stops, three times. Confirm no flip, no surface penetration and no unrecoverable state, and that `StabilityMonitor` did not fire. If it fired on three consecutive drives, switch to the simplified kinematic model and record the run that triggered it (SC-006, FR-010, research C5)
- [ ] T026 [US1] Record the three **empirically settled** values in `DESIGN.md` sections 4.2 and 4.4 in a `docs:` commit: the steering rate from T023, and the acceleration and braking from T024. These are the only vehicle numbers that could not be written before implementation, because they are measured from a human drive rather than decided. Everything else went in at T012a (Principle V)

**Checkpoint**: User Story 1 is complete and demonstrable on its own. No track exists yet.

---

## Phase 4: User Story 2 - Tracks generated from the data, reproducibly, from a seed (Priority: P2)

**Goal**: closed-loop tracks from an integer seed, geometrically driveable, statistically matched to the human steering distribution, committed as JSON and built in Unity.

**Independent Test**: generate a batch, confirm every accepted track closes, does not self-intersect, holds the radius floor and the separation rule, that the pooled required-steering distribution is within the threshold, and that regenerating the same seeds gives byte-identical files.

### Python generator

- [ ] T027 [P] [US2] Implement `draw_parameters(seed)` in `python/track/generator.py` returning a `TrackSeed` with amplitude from `AMPLITUDE_RANGE` and one phase per harmonic, using a seeded generator instance and never global random state
- [ ] T028 [US2] Implement `centre_line(params)` in `python/track/generator.py` sampling `r(theta) = R0 * (1 + sum a_k sin(k theta + phi_k))` with `a_k = A / k^2` at `SAMPLES_PER_TRACK` points, returning `CentreLine` with x, y, cumulative arc length, curvature and radius. Curvature from the closed-form polar expression, never finite differences (research C6, C7)
- [ ] T029 [US2] Write `python/tests/test_generator.py`: the same seed gives identical parameters and geometry across calls and across processes; two different seeds give different geometry; the curve closes by construction with no endpoint correction anywhere in the module; the analytic curvature agrees with a fine numerical estimate within tolerance, which validates the formula without depending on it
- [ ] T030 [US2] Implement `check_geometry(line, profile)` in `python/track/geometry.py` returning a `GeometryReport` with minimum radius against `r_floor_m`, pairwise non-adjacent segment intersection, and minimum separation measured only between points more than `2 * TRACK_WIDTH_M` apart along the arc. The report carries `r_floor_m` so the test is auditable
- [ ] T031 [US2] Implement `place_checkpoints(line, n)` in `python/track/geometry.py`, spaced evenly by arc length and not by the sample parameter, each with position and forward direction
- [ ] T032 [US2] Write `python/tests/test_geometry.py` covering both directions of the contract table: a hand-built curve with a corner below the floor is rejected and one just above it is accepted; an open polyline fails closure and every generated line passes; a hand-built figure of eight is detected and a generated loop is not; a loop whose two sides pass within 3 m fails separation and a generated loop does not; checkpoints are monotonic in arc length and evenly spaced in arc length rather than in theta
- [ ] T033 [P] [US2] Implement `required_steering(line, profile)` in `python/track/matching.py` returning a `SteeringDemand` with `atan(wheelbase / radius) / steer_max` per sample, unsigned, plus the peak and the same percentiles M1 reports
- [ ] T033a [US2] Implement `describe(values)` in `python/track/matching.py` returning a `Descriptives` with n, mean, variance, std, min, max and a relative-frequency histogram, and attach it to every `SteeringDemand`. Constitution Principle IX requires all six for every distribution the project touches, and required steering is one this feature introduces. Relative frequency, not counts, so a 2000-sample track and a 2193-sample reference stay comparable
- [ ] T034 [US2] Implement `reference_distribution()` in `python/track/matching.py`, reading `|steering|` through the existing M1 loader and returning the distribution conditional on being non-zero. Read only, never writes (research C9)
- [ ] T035 [US2] Implement `match_distance(demand, reference)` in `python/track/matching.py` returning a `MatchReport` with the Wasserstein-1 distance, the threshold, the decision, the reference name, both sample counts, and a note stating the 0.789 truncation and the absence of straights. No p-value field, by contract (FR-019)
- [ ] T036 [US2] Write `python/tests/test_matching.py`: the reference scores zero against itself; its two halves score 0.0231, below the threshold; a uniform demand on `[0, 0.789]` scores 0.1047, above it; `max_required` never exceeds the profile's `max_required_steer`; the returned type has no p-value field and no function in the module returns one; the note contains both stated limitations; every `SteeringDemand` carries all six `Descriptives` fields and a histogram that sums to 1
- [ ] T037 [US2] Implement track file serialisation in `python/track/export.py` to schema version 1 exactly as `contracts/track-file-schema.md` specifies, including the `generator` block, the `vehicle_profile` block, the centre line without a repeated first point, the checkpoints, and both reports carried inside the file
- [ ] T038 [US2] Implement `export_track(seed, out_dir)` in `python/track/export.py`: generate, validate, write one file, raise on a rejected seed and write nothing
- [ ] T039 [US2] Implement `generate_batch(seeds, out_dir)` in `python/track/export.py` returning a `BatchReport` with the acceptance rate and every rejection with its reason. A rejected seed is never retried with adjusted parameters (research C7, FR-020)
- [ ] T040 [US2] Add the `python -m python.track.export --seed <n>` and `--batch train|eval` command line entry to `python/track/export.py`
- [ ] T041 [US2] Write `python/tests/test_export.py`: two runs over the same seed list produce byte-identical files (SC-007); a rejected seed produces no file and exactly one recorded rejection; nothing outside the output directory is written; a file whose `geometry_report.radius_ok` is false can never be produced
- [ ] T042 [P] [US2] Implement `python/track/plots.py` producing `results/plots/track_seed_<n>.png` with the centre line and the tightest corner marked, and `results/plots/track_match.png` with the required-steering distribution against the human reference
- [ ] T043 [US2] Write the train and eval split to `results/tracks/seed_split.json` from `export.py`, listing accepted seeds per set and asserting the two are disjoint (FR-022, SC-016)
- [ ] T044 [US2] Write the batch report to `results/tracks/batch_report.md` with the acceptance rate, every rejection and its reason. If the rate is below 50 percent, stop and record it as a design finding rather than lowering the radius floor (SC-011)
- [ ] T044a [US2] Pool the required steering across every accepted track in `generate_batch` and produce one batch-scope `MatchReport` with `n_seeds_pooled`, the distance, the threshold and the three C15 scales. Write it into `results/tracks/batch_report.md` alongside the acceptance rate, and assert in `python/tests/test_export.py` that a batch of 20 or more accepted seeds is within the threshold. This is what SC-010 is judged on. No per-seed report answers it, because 20 tracks each missing in a different direction pool to a good match while 20 missing the same way do not, and only the pooled figure separates the two cases
- [ ] T045 [US2] Run `--batch train` and `--batch eval`, then commit the accepted `unity/SelfDrivingSim/Assets/Tracks/seed_*.json` files, the batch report and the split (FR-021)

### Unity track construction

- [ ] T046 [US2] Implement `unity/SelfDrivingSim/Assets/Scripts/Track/TrackFile.cs` reading the JSON into types mirroring the schema, with every one of the six failure modes in the contract handled as a refusal naming the offending field: unknown `schema_version`, `vehicle_profile` mismatch against the scene profile, `radius_ok` false, fewer than two centre-line points, checkpoints not monotonic in `s`, and a duplicated first and last point
- [ ] T047 [US2] Write `unity/SelfDrivingSim/Assets/Tests/EditMode/TrackFileLoaderTests.cs` feeding one deliberately broken file per failure mode and asserting each is refused with the field named, plus a committed valid file that loads
- [ ] T048 [US2] Implement `unity/SelfDrivingSim/Assets/Scripts/Track/TrackBuilder.cs` building the drivable surface at `width_m`, barriers along both edges (FR-023) and the checkpoint objects, from a loaded `TrackFile`. It performs no statistics and draws no random numbers
- [ ] T049 [US2] Create `unity/SelfDrivingSim/Assets/Scenes/Track.unity` with the car prefab, the track builder holding a seed field, and the camera. References only, no logic
- [ ] T050 [US2] Write `unity/SelfDrivingSim/Assets/Tests/EditMode/TrackGeometryTests.cs` rebuilding geometry from a committed track file and re-measuring the minimum radius and the checkpoint order, asserting both match what the file claims. Unity and Python disagreeing is caught here, not during training
- [ ] T051 [US2] Drive a full keyboard lap on at least five different accepted seeds without leaving the drivable surface, and record which seeds (SC-012, FR-013 acceptance scenario 6)

**Checkpoint**: seeds produce driveable, committed, reproducible tracks. Nothing senses anything yet.

---

## Phase 5: User Story 3 - The agent's senses, verified before any training (Priority: P3)

**Goal**: every observation the future agent will see, readable live during a human drive, plus ordered progress markers and wrong-way detection.

**Independent Test**: drive by keyboard with the observation panel open. Confirm each distance reading matches the visible distance to a barrier, the heading value peaks when the car points at the next marker, and markers are awarded in order and once each.

### Implementation for User Story 3

- [ ] T051a [US3] Write the **decided** sensing and marker values into `DESIGN.md` sections 4.3 and 4.5 in a `docs:` commit before any Phase 5 code exists: 13 rays over 180 degrees, 20 m range with its derivation from the P95 stopping distance of 8.5 m, 24 checkpoints, and the start randomisation of a random checkpoint with 1.5 m lateral and 10 degrees of yaw. Principle V requires the design first (research C11, C12)
- [ ] T052 [US3] Implement the raycast sensing in `unity/SelfDrivingSim/Assets/Scripts/Agent/CarAgent.cs`: `RAY_COUNT` 13 rays over `RAY_FOV_DEG` 180 degrees ahead, `RAY_LENGTH_M` 20 m, with a no-hit encoding clearly distinguishable from a hit at zero distance (FR-024, FR-025, research C11)
- [ ] T053 [US3] Add the self-state observations to `CarAgent.cs`: own speed, rotation rate, current steering, and heading relative to the next progress marker (FR-026)
- [ ] T054 [US3] Implement `unity/SelfDrivingSim/Assets/Scripts/Track/CheckpointRing.cs`: ordered markers, `next_index`, a marker awarded only when it is the expected next one, and a lap counted when the index wraps. No reward logic, that belongs to M3 (FR-027)
- [ ] T055 [US3] Add wrong-way detection to `CheckpointRing.cs`, set when the vehicle approaches an already-passed marker, reported rather than scored (FR-028)
- [ ] T056 [US3] Write `unity/SelfDrivingSim/Assets/Tests/EditMode/CheckpointOrderTests.cs`: in-order contact awards each marker exactly once; out-of-order contact awards nothing; contact with an already-passed marker sets wrong-way; the index wrapping increments the lap count; the awarded count over a synthetic lap equals `N_CHECKPOINTS`
- [ ] T057 [US3] Implement `unity/SelfDrivingSim/Assets/Scripts/Agent/ObservationDebug.cs` displaying every observation value live during play, including all 13 distances and the no-hit state (FR-029)
- [ ] T058 [US3] Implement start randomisation in `TrackBuilder.cs` or the spawn logic: a random checkpoint as the start, lateral offset within `START_LATERAL_M` 1.5 m, yaw within `START_YAW_DEG` 10 degrees (FR-030, research C12)
- [ ] T059 [US3] Park the car at known distances from a barrier and confirm each distance reading agrees with the true distance within 5 percent, and that a ray with nothing in range is distinguishable from one at zero. Record the measurements (SC-013)
- [ ] T060 [US3] Drive a full lap and confirm the number of markers awarded equals the number on the track, none skipped and none double-counted (SC-014)
- [ ] T061 [US3] Reverse direction mid-lap and confirm wrong-way is reported within one marker interval of the reversal (SC-015)
- [ ] T062 [US3] Read every observation live during a human drive and check each against a situation whose correct answer is visible. Record which observation was checked against which situation (FR-029, the M2 gate)
- [ ] T063 [US3] Record the **measured** sensing results in `DESIGN.md` sections 4.3 and 4.5 in a `docs:` commit: the ray accuracy from T059 and the wrong-way detection latency from T061. The decided values went in at T051a; only what had to be measured lands here (Principle V)

**Checkpoint**: all three user stories work independently. The environment is ready for M3.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T064 Record the research C9 finding in `DESIGN.md` section 7: generated tracks contain no straight sections, so the M5 comparison must lean on execution metrics rather than raw marginal steering histograms
- [ ] T065 Remove `com.unity.ai.assistant` from `unity/SelfDrivingSim/Packages/manifest.json` before the v1.0 submission tag, or write a justification for shipping a pre-release dependency. Constitution VI's clean-clone rule exists because a pre-release version string can be withdrawn or changed under the same number
- [ ] T066 [P] Run `pytest python/tests -q` and confirm the M1, feature 002 and new generator tests are all green (Principle VIII)
- [ ] T067 [P] Run all Unity EditMode tests through Window > General > Test Runner and confirm green
- [ ] T068 Walk `specs/003-unity-environment/quickstart.md` end to end on a clean checkout and confirm every command and every expected figure in its two tables
- [ ] T069 Confirm the M2 gate: the scene, vehicle, agent scaffolding and markers exist, the vehicle is keyboard drivable, and the observations have been verified. The blunt version from WORKFLOW section 5 is no keyboard lap, no training

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: needs Setup. Blocks every user story, because both the car and the track floor derive from the profile. T012a, the DESIGN.md writeback, is the last of them and gates Phase 3 by Principle V
- **User Story 1 (Phase 3)**: needs Phase 2, T012a included
- **User Story 3 (Phase 5)**: T051a, the second DESIGN.md writeback, comes before any Phase 5 code for the same reason
- **User Story 2 (Phase 4)**: needs Phase 2. Its Python half is independent of User Story 1; its Unity half reuses the car from T014
- **User Story 3 (Phase 5)**: needs Phase 2, and needs a built track from T048 to have barriers to sense and markers to order
- **Polish (Phase 6)**: needs the stories that are wanted

### User story dependencies

- **US1 (P1)**: independent once the profile exists. Deliverable on its own
- **US2 (P2)**: the Python generator T027 to T045 is fully independent of US1 and can proceed in parallel. Driving a generated lap (T051) needs the car from US1
- **US3 (P3)**: needs US2's built track. Nothing in it depends on US1 beyond the car existing

### Within each story

- Decided design values go into `DESIGN.md` before the code that implements them (T012a, T051a). Only values that must be measured are written back afterwards (T026, T063). Principle V
- Tests are written alongside the code they cover and must fail before the code exists
- Types before functions, functions before the command line entry, generation before Unity construction
- Every measurement task (T022 to T025, T051, T059 to T062) comes after the thing it measures

### Parallel opportunities

- T002 to T005 in Setup
- T027, T033 and T042 within US2, different files
- The whole Python half of US2 alongside the whole of US1, if two people are working
- T066 and T067 in Polish

---

## Parallel Example: User Story 2, Python half

```text
Task: "Implement draw_parameters in python/track/generator.py"
Task: "Implement required_steering in python/track/matching.py"
Task: "Implement plots in python/track/plots.py"
```

---

## Implementation Strategy

### MVP first, User Story 1 only

1. Phase 1 Setup
2. Phase 2 Foundational, the blocking one
3. Phase 3 User Story 1
4. Stop and validate: drive a minute, run `compare_drive`, confirm the envelope
5. This alone de-risks the physics decision before any geometry work is committed

### Incremental delivery

1. Setup and Foundational, the profile is proven
2. User Story 1, a calibrated car exists
3. User Story 2, seeded tracks exist and are committed
4. User Story 3, the senses are verified
5. Each stage is demonstrable without the next

### Notes

- [P] means different files with no unfinished dependency
- Commit after each task or logical group. Every commit is proposed to the owner, never run by an agent (Principle III)
- `FlatGround.unity` and `Track.unity` are scene-locked while this branch is open. No other branch may touch them (Principle IV)
- If the seed acceptance rate lands below 50 percent, that is a design finding to record, not a number to tune away
