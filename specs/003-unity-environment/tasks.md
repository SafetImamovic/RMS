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

- [X] T001 Create `python/track/__init__.py` as an empty package, matching the `python/eda/` layout
- [X] T002 [P] Install `com.unity.splines` and `com.unity.probuilder` through Window > Package Manager and confirm both appear in `unity/SelfDrivingSim/Packages/manifest.json` and `packages-lock.json`
- [X] T003 [P] Create `unity/SelfDrivingSim/Assets/Scripts/Vehicle/`, `Scripts/Track/`, `Scripts/Agent/`, `Scripts/Logging/` and `unity/SelfDrivingSim/Assets/Tracks/`
- [X] T004 [P] Create `unity/SelfDrivingSim/Assets/Tests/EditMode/` with an assembly definition referencing `Unity.InputSystem`, `Unity.Splines` and the project runtime assembly
- [X] T005 [P] Create `results/tracks/` and `results/drive_logs/`, each with a `.gitkeep`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the vehicle profile. Every number in User Stories 1 and 2 derives from it, so nothing
else can start until it exists and is proven.

**CRITICAL**: no user story work begins until T012 passes.

- [X] T006 Write every named constant in `python/track/config.py` from the research summary table: `WHEELBASE_M` 2.5, `STEER_MAX_DEG` 25.0, `RADIUS_MARGIN` 1.3, `V_MAX_MS` 10.0, `DATASET_SPEED_P99` 17.49, `TRACK_R0_M` 30.0, `HARMONICS` (2,3,4,5), `AMPLITUDE_RANGE` (0.40, 0.70), `SAMPLES_PER_TRACK` 2000, `TRACK_WIDTH_M` 6.0, `MIN_SEPARATION_M` 12.0, `N_CHECKPOINTS` 24, `START_LATERAL_M` 1.5, `START_YAW_DEG` 10.0, `RAY_COUNT` 13, `RAY_FOV_DEG` 180.0, `RAY_LENGTH_M` 20.0, `COMPARE_HZ` 14.08, `MATCH_DISTANCE_THRESHOLD` 0.05, `W1_SELF_CONSISTENCY` 0.0231, `W1_STRUCTURELESS` 0.1047, `W1_HUMAN_TO_HUMAN` 0.2635, `TRAIN_SEEDS` range(1,41), `EVAL_SEEDS` range(1001,1011). Each carries a comment naming its research decision. No import from `python/eda`
- [X] T007 Add the M1 calibration envelope constants to `python/track/config.py`, read once from `results/eda/m1_stats.json` and pasted as named values: steering maximum, per-frame steering-change P95 for both recordings and its maximum, speed P99 and maximum. These are the envelope FR-009 reports against
- [X] T008 Implement the frozen `VehicleProfile` dataclass and `build_profile()` in `python/track/vehicle.py`, with `r_min_m`, `r_floor_m` and `max_required_steer` computed as properties and never stored independently
- [X] T009 Implement `radius_for_steering`, `steering_for_radius`, `stopping_distance_m` and `normalise_speed` in `python/track/vehicle.py`. No function converts a dataset speed into a physical unit
- [X] T010 Write `python/tests/test_vehicle.py`: `r_min_m` equals 5.361 m, `r_floor_m` equals 6.969 m, `max_required_steer` equals 0.789; the two steering functions round-trip across `[0, 1]`; `max_required_steer` stays fixed while `wheelbase_m` sweeps 1.5 m to 4.0 m; a radius outside the achievable range is rejected; the radius table in research C1 is reproduced row for row
- [X] T011 Implement `export_profile()` in `python/track/vehicle.py`, writing `unity/SelfDrivingSim/Assets/Tracks/vehicle_profile.json`, and commit the file
- [X] T012 Create `unity/SelfDrivingSim/Assets/Scripts/Vehicle/VehicleProfile.cs` mirroring the Python type field for field, plus `unity/SelfDrivingSim/Assets/Tests/EditMode/VehicleProfileMirrorTests.cs` asserting every field matches the committed `vehicle_profile.json`. A drift shows up here rather than as wrong geometry

- [X] T012a Write the **decided** vehicle values into `DESIGN.md` sections 4.2 and 4.4 in a `docs:` commit before any Phase 3 code exists: wheelbase 2.5 m, steer_max 25 degrees, radius margin 1.3 and the 21.1 percent steering reserve it buys, `r_min` 5.361 m, `r_floor` 6.969 m, `max_required_steer` 0.789, and the decision that top speed is a stated simulation constant rather than a derived figure. Constitution Principle V requires the design to be written before it is implemented, not after (research C1 to C3)

**Checkpoint**: the car's limits exist in one place, are derived rather than typed twice, Python and C# agree, and DESIGN.md says so before any code depends on it.

---

## Phase 3: User Story 1 - A car you can drive, calibrated to the dataset (Priority: P1) MVP

**Goal**: a keyboard-drivable car on a bounded flat plane whose every limit traces to an M1 measurement.

**Independent Test**: press Play, drive one minute, run the drive log through `compare_drive`, and confirm steering range, steering rate, top speed and acceleration all sit inside the measured envelope with the car still upright.

### Implementation for User Story 1

- [X] T013 [US1] Create `unity/SelfDrivingSim/Assets/Scenes/FlatGround.unity`: a bounded plane large enough for a full-lock circle plus margin, a chase camera, a light and one spawn point. Scene holds references only, no logic (Principle IV scene lock)
- [X] T014 [US1] Implement `unity/SelfDrivingSim/Assets/Scripts/Vehicle/CarController.cs` with WheelCollider physics, reading limits from `VehicleProfile` and input through the existing `InputSystem_Actions.inputactions`. W and S for throttle and brake, A and D for steering
- [X] T015 [US1] Implement the steering ramp in `CarController.cs` using `steer_rate_norm_per_s`, so holding a key moves the input from centre to full lock over a stated time rather than snapping (FR-005, research C4)
- [X] T016 [US1] Add the boundary or out-of-bounds reset to `CarController.cs` and `FlatGround.unity` so a run cannot end with the car falling indefinitely (FR-012)
- [X] T017 [US1] Implement `unity/SelfDrivingSim/Assets/Scripts/Vehicle/StabilityMonitor.cs` checking the three research C5 conditions per drive: body tilt or roll past 45 degrees while all four wheels were grounded the previous step, drift over 0.1 m in 10 s with no input, and falling through the surface or entering an unrecoverable state. It records which fired and on which run (FR-011)
  - Tally persists in `PlayerPrefs` and every breach is appended to `results/drive_logs/stability_log.csv`, since the three drives are not expected to happen in one sitting
  - A run shorter than 60 s moves the tally in **neither** direction. C5 specifies one-minute drives, and letting a five-second run clear the counter would make it trivially resettable
  - The idle-speed gate (0.05 m/s) is deliberately looser than the drift it watches for (0.1 m per 10 s = 0.01 m/s); a tighter gate would exclude exactly the case the condition exists to catch
- [X] T018 [US1] Implement `unity/SelfDrivingSim/Assets/Scripts/Logging/DriveLogger.cs` writing `results/drive_logs/<timestamp>.csv` with the dataset's own columns: `steering`, `throttle`, `brake`, `speed`, plus `t` and `source` (FR-008)
  - **Sampled in `FixedUpdate`, at the physics rate, not per rendered frame.** A log written per frame would make its contents depend on the machine's frame rate, so the same drive on two computers would yield two different steering-change distributions. Resampling to `COMPARE_HZ` stays on the Python side (research C14)
  - **Every number formatted with `InvariantCulture`.** This machine's locale is `bs-Latn-BA`, which writes `0,5` rather than `0.5`; a decimal comma inside a comma-separated file splits one column into two and silently misaligns every row after the first. Same hazard applies to `StabilityMonitor` and the HUD, and all three force the invariant culture
- [X] T019 [US1] Implement `python/track/compare_drive.py`: load a drive log, resample to `COMPARE_HZ`, normalise speed by the log's own P99, compute steering, steering-change and speed distributions, and report per quantity whether it sits inside the M1 envelope, naming any that does not (FR-009, research C14)
  - Resampling is **nearest-sample, never averaging**: averaging the rows inside each bin would smooth exactly the steering changes being measured and report every drive as calmer than it was
  - `percentile()` reimplements nearest rank to match `DriveTelemetry.Percentile` in C#. NumPy's interpolated default would make the in-editor HUD and this report quote different numbers for the same drive
- [X] T020 [US1] Add the `python -m python.track.compare_drive <csv>` command line entry to `python/track/compare_drive.py`
- [X] T021 [US1] Write `python/tests/test_compare_drive.py`: resampling a synthetic log to 14.08 Hz gives the expected step count and per-step differences; normalisation is by the log's own P99 and never by a unit conversion; a log inside the envelope passes and a log with one quantity pushed outside is named as failing
  - 33 tests. The two load-bearing ones use no synthetic data at all: each recording passes **its own** envelope, and track1 is **refused** against track2's band. The second reproduces the documented 2.33x gap between the two recordings independently, and is what shows the envelope discriminates rather than approves. The image timestamps put both recordings on the same evening an hour apart, so that gap is very likely one driver on two tracks, which makes it a measure of what the terrain demands rather than of variation between people
- [X] T022 [US1] Drive a full-lock circle in `FlatGround.unity` at low speed, measure the diameter, and confirm it agrees with `r_min_m` 5.361 m within 10 percent. Record the measurement (SC-004, FR-006)
  - **5.787 m measured against 5.361 m geometric, +7.9 percent. Passes.** Fit residual 0.0002 m over 44.7 s at a mean absolute steering of 0.99998, so the path really was a circle at full lock and not a spiral
  - The remaining 7.9 percent is a property of the model, not an error. Both front wheels are given the **same** steer angle, with no Ackermann differential between inner and outer, so the inner tyre scrubs and pushes the car slightly wide of the bicycle-model radius
  - **Speed is part of this measurement, not an incidental.** A first attempt held a fixed throttle instead of a speed and reached 6.54 m/s, which is 0.72 g of lateral load, and reported 6.065 m: +13.1 percent, a fail. Re-run at a held 2.02 m/s and therefore 0.07 g, it passes. A turning circle is geometry, and it can only be measured where slip angles are negligible
  - Run by `ScriptedDriver.Manoeuvre.FullLockCircle` rather than by hand, so it can be re-measured after any future change to the steering geometry
- [X] T023 [US1] Drive one minute by keyboard, run `compare_drive`, and tune `steer_rate_norm_per_s` in `python/track/config.py` and `VehicleProfile.cs` until the 95th-percentile steering change is within a factor of two of the recorded human figure at 14.08 Hz. Record the achieved value (FR-005, SC-002, SC-005)
  - **Drive 2 (67.2 s, rate 3.7): P95 |dsteer| = 0.2949 against the human 0.30, off by 1.7 percent. Passes, and passes mid-band rather than on the floor.** The retune was computed as 2.0 x (0.30 / 0.1615) = 3.72 and predicted 0.30, so the rate scales linearly with the measured P95 as assumed
  - Five of six quantities pass: both full-lock extremes exactly +-1.0000, max |dsteer| 0.3506, P95 |dspeed| 0.0423 against 0.0416
  - **`speed max/P99` = 1.038 against [1.13, 1.38] fails, and is not a vehicle defect.** The ratio measures how far peak speed exceeds typical speed. On a featureless plane there is never a reason to lift off, so the car sits pinned at its 10 m/s cap and P99 equals the maximum; the dataset's driver was on a track that forced braking and re-acceleration. This measures the **absence of a track** and cannot pass before US2 generates one
  - The turning circle reported from this drive (6.097 m, +13.7 percent) is **not** the T022 result. Its path residual is 0.439 m against 0.0002 m on the scripted run, because a hand-held lock at speed wanders. The scripted low-speed measurement stands
  - Drive 1 (91 s, rate 2.0): P95 |dsteer| = **0.1615**, inside the band [0.15, 0.60] but on its floor. Passing at the floor is not being calibrated: the floor is where the drive is half as active as the human. Rate raised to **3.7**, awaiting a confirming drive
  - **A profile value lives in THREE places**, and the third is easy to miss: `config.py`, `VehicleProfile.cs`, and the **serialised copy inside `FlatGround.unity`**. The scene copy is written when the component is added and a changed C# default never reaches it. The retune above left the scene on 2.0
  - `DriveTelemetry.WarnIfProfileDrifted` now logs an error at Play time if the scene disagrees with `vehicle_profile.json`. The EditMode mirror test cannot catch this, because it compares the compiled default against the JSON and never opens the scene
  - **The confirming drive was deliberately held back until T022, T024 and T025 passed.** Steering rate is calibrated against a human's P95 steering change, and until the substep fix the car could not hold a speed or a line, so a drive would have measured the driver fighting the tyres. This is the one task that cannot be scripted, since a scripted drive would only measure the script (FR-005, SC-002)
- [X] T024 [US1] Confirm normalised top speed and the achievable acceleration and deceleration agree with the dataset within 10 percent on the normalised scale, adjusting `accel_ms2` and `brake_ms2` in config if not (FR-003, FR-004, FR-007, SC-003)
  - **Acceleration +4.79 against 5.00, minus 4.2 percent. Braking -5.65 against -5.85, minus 3.4 percent. Top speed 9.986 against 10.0, nothing above the cap. All pass.** `ACCEL_MS2` and `BRAKE_MS2` are therefore **unchanged**: they were validated, not tuned
  - **Nothing measured before the substep fix was worth anything.** Earlier drives reported acceleration between +0.03 and +2.53 against the same profile, and the difference was never the vehicle parameters, it was the tyre solver oscillating. Tuning `ACCEL_MS2` upward against those numbers would have permanently baked a solver artefact into the config
  - Measure acceleration from the **signed** `speed` column, never `speed_mag`. Magnitude folds reverse onto forward, and the first pass over this run read +2.53 and -2.19 because 643 of 1725 samples were reversing. The manoeuvre now releases the brake at 2.5 s, since stopping from 10 m/s at 5.85 m/s^2 takes 1.7 s and holding the brake past a standstill is the reverse gesture
- [X] T025 [US1] Run the stress case: full-lock turns at top speed and full-brake stops, three times. Confirm no flip, no surface penetration and no unrecoverable state, and that `StabilityMonitor` did not fire. If it fired on three consecutive drives, switch to the simplified kinematic model and record the run that triggered it (SC-006, FR-010, research C5)
  - **Three cycles of full-lock turns at 9.986 m/s with full-brake stops. No breach.** `StabilityMonitor` is confirmed present on the car and wrote no `stability_log.csv`, which is what makes its silence evidence rather than an absence
  - Ride height held between 0.4725 and 0.5000 m throughout, so there was no flip and no surface penetration to detect in the first place
  - The low centre of mass at -0.6 m local is doing this work. Forward friction stiffness was raised to 2.385 during the wheelspin investigation but **sideways friction was deliberately left at stock**, precisely because lateral grip trades against this requirement
- [X] T026 [US1] Record the three **empirically settled** values in `DESIGN.md` sections 4.2 and 4.4 in a `docs:` commit: the steering rate from T023, and the acceleration and braking from T024. These are the only vehicle numbers that could not be written before implementation, because they are measured from a human drive rather than decided. Everything else went in at T012a (Principle V)
  - Written into DESIGN 4.2 as a measured-values table: steering rate 3.7, acceleration 5.0, braking 5.85, plus the turning circle at 5.787 m. Section 4.4 needed no change, since the +-25 degree mapping and its radius table were never in question and are still verified row by row
  - Recorded alongside them: why acceleration and braking are **confirmed rather than tuned**, why the circle sits 7.9 percent wide (same steer angle on both front wheels, no Ackermann differential), why the circle had to be measured at 2 m/s, and why `speed max/P99` cannot pass until a track exists
  - Also recorded: that nothing measured before the substep fix was usable, with the arithmetic. Tuning `accel_ms2` against those earlier figures would have written a solver artefact permanently into the config, which is the failure this task exists to prevent

**Checkpoint**: User Story 1 is complete and demonstrable on its own. No track exists yet.

---

## Phase 4: User Story 2 - Tracks generated from the data, reproducibly, from a seed (Priority: P2)

**Goal**: closed-loop tracks from an integer seed, geometrically driveable, statistically matched to the human steering distribution, committed as JSON and built in Unity.

**Independent Test**: generate a batch, confirm every accepted track closes, does not self-intersect, holds the radius floor and the separation rule, that the pooled required-steering distribution is within the threshold, and that regenerating the same seeds gives byte-identical files.

### Python generator

- [X] T027 [P] [US2] Implement `draw_parameters(seed)` in `python/track/generator.py` returning a `TrackSeed` with amplitude from `AMPLITUDE_RANGE` and one phase per harmonic, using a seeded generator instance and never global random state
- [X] T028 [US2] Implement `centre_line(params)` in `python/track/generator.py` sampling `r(theta) = R0 * (1 + sum a_k sin(k theta + phi_k))` with `a_k = A / k^2` at `SAMPLES_PER_TRACK` points, returning `CentreLine` with x, y, cumulative arc length, curvature and radius. Curvature from the closed-form polar expression, never finite differences (research C6, C7)
- [X] T029 [US2] Write `python/tests/test_generator.py`: the same seed gives identical parameters and geometry across calls and across processes; two different seeds give different geometry; the curve closes by construction with no endpoint correction anywhere in the module; the analytic curvature agrees with a fine numerical estimate within tolerance, which validates the formula without depending on it
- [X] T030 [US2] Implement `check_geometry(line, profile)` in `python/track/geometry.py` returning a `GeometryReport` with minimum radius against `r_floor_m`, pairwise non-adjacent segment intersection, and minimum separation measured only between points more than `2 * TRACK_WIDTH_M` apart along the arc. The report carries `r_floor_m` so the test is auditable
- [X] T031 [US2] Implement `place_checkpoints(line, n)` in `python/track/geometry.py`, spaced evenly by arc length and not by the sample parameter, each with position and forward direction
- [X] T032 [US2] Write `python/tests/test_geometry.py` covering both directions of the contract table: a hand-built curve with a corner below the floor is rejected and one just above it is accepted; an open polyline fails closure and every generated line passes; a hand-built figure of eight is detected and a generated loop is not; a loop whose two sides pass within 3 m fails separation and a generated loop does not; checkpoints are monotonic in arc length and evenly spaced in arc length rather than in theta
- [X] T033 [P] [US2] Implement `required_steering(line, profile)` in `python/track/matching.py` returning a `SteeringDemand` with `atan(wheelbase / radius) / steer_max` per sample, unsigned, plus the peak and the same percentiles M1 reports
- [X] T033a [US2] Implement `describe(values)` in `python/track/matching.py` returning a `Descriptives` with n, mean, variance, std, min, max and a relative-frequency histogram, and attach it to every `SteeringDemand`. Constitution Principle IX requires all six for every distribution the project touches, and required steering is one this feature introduces. Relative frequency, not counts, so a 2000-sample track and a 2193-sample reference stay comparable
- [X] T034 [US2] Implement `reference_distribution()` in `python/track/matching.py`, reading `|steering|` through the existing M1 loader and returning the distribution conditional on being non-zero. Read only, never writes (research C9)
- [X] T035 [US2] Implement `match_distance(demand, reference)` in `python/track/matching.py` returning a `MatchReport` with the Wasserstein-1 distance, the threshold, the decision, the reference name, both sample counts, and a note stating the 0.789 truncation and the absence of straights. No p-value field, by contract (FR-019)
- [X] T036 [US2] Write `python/tests/test_matching.py`: the reference scores zero against itself; its two halves score 0.0231, below the threshold; a uniform demand on `[0, 0.789]` scores 0.1047, above it; `max_required` never exceeds the profile's `max_required_steer`; the returned type has no p-value field and no function in the module returns one; the note contains both stated limitations; every `SteeringDemand` carries all six `Descriptives` fields and a histogram that sums to 1
  - **Pooled W1 across the 40 train seeds is 0.0930 against a 0.05 threshold. SC-010 does not pass, and amplitude cannot make it pass.** Sweeping `AMPLITUDE_RANGE` moves the distance to a floor of 0.0639 at 35 percent acceptance and no further, so the failure is not one of scale
  - **The two distributions are not the same kind of quantity.** `required_steering` is the geometric MINIMUM needed to follow the centre line; the human column is steering a person actually applied, including corrections, overshoot and weaving. A human always steers more than geometry demands. The gap widens monotonically with percentile: -0.025 at P25, -0.129 at P75, -0.299 at P95, -0.501 at P99, and the generated standard deviation is 0.098 against the human 0.196
  - **`W1_STRUCTURELESS` corrected from 0.1047 to 0.1142.** Recomputed from the definition C15 states, agreeing to four decimals between this project's implementation and `scipy.stats.wasserstein_distance`. The same pair reproduces the other two scales exactly (0.0231 and 0.2636 against a recorded 0.2635), so the machinery is not in question. Support was ruled out as the cause: uniform on [0, 1] gives 0.2127 and an unconditional reference 0.3359. No decision changes, since 0.05 sits below both figures. **Research C15 still records 0.1047 and needs the same correction**
  - Neither `AMPLITUDE_RANGE` nor `MATCH_DISTANCE_THRESHOLD` was touched. Both are spec decisions, and moving a threshold until a measurement passes is the failure T044 exists to prevent
- [X] T037 [US2] Implement track file serialisation in `python/track/export.py` to schema version 1 exactly as `contracts/track-file-schema.md` specifies, including the `generator` block, the `vehicle_profile` block, the centre line without a repeated first point, the checkpoints, and both reports carried inside the file
- [X] T038 [US2] Implement `export_track(seed, out_dir)` in `python/track/export.py`: generate, validate, write one file, raise on a rejected seed and write nothing
- [X] T039 [US2] Implement `generate_batch(seeds, out_dir)` in `python/track/export.py` returning a `BatchReport` with the acceptance rate and every rejection with its reason. A rejected seed is never retried with adjusted parameters (research C7, FR-020)
- [X] T040 [US2] Add the `python -m python.track.export --seed <n>` and `--batch train|eval` command line entry to `python/track/export.py`
- [X] T041 [US2] Write `python/tests/test_export.py`: two runs over the same seed list produce byte-identical files (SC-007); a rejected seed produces no file and exactly one recorded rejection; nothing outside the output directory is written; a file whose `geometry_report.radius_ok` is false can never be produced
- [X] T042 [P] [US2] Implement `python/track/plots.py` producing `results/plots/track_seed_<n>.png` with the centre line and the tightest corner marked, and `results/plots/track_match.png` with the required-steering distribution against the human reference
- [X] T043 [US2] Write the train and eval split to `results/tracks/seed_split.json` from `export.py`, listing accepted seeds per set and asserting the two are disjoint (FR-022, SC-016)
- [X] T044 [US2] Write the batch report to `results/tracks/batch_report.md` with the acceptance rate, every rejection and its reason. If the rate is below 50 percent, stop and record it as a design finding rather than lowering the radius floor (SC-011)
- [X] T044a [US2] Pool the required steering across every accepted track in `generate_batch` and produce one batch-scope `DemandBound` with `n_seeds_pooled`, plus a `MatchReport` kept as a diagnostic. Write both into `results/tracks/batch_report.md` alongside the acceptance rate, and assert in `python/tests/test_export.py` that a batch of 20 or more accepted seeds is **within the bound**. This is what SC-010 is judged on. No per-seed report answers it, because 20 tracks each missing in a different direction pool to a good match while 20 missing the same way do not, and only the pooled figure separates the two cases
  - **SC-010 was revised on 2026-07-31 from a distance match to a bound**, after measurement showed no track this generator can produce satisfies the original. Pooled W1 is 0.0930 against a 0.05 threshold and sweeping `AMPLITUDE_RANGE` bottoms out at 0.0639 with acceptance down at 35 percent. Required steering is the geometric **minimum** to follow the centre line; the dataset column is steering a human **actually applied**, corrections and overshoot included, so the human distribution sits above the geometric one by construction and the gap widens with every percentile
  - The bound checks **upper percentiles only** (`BOUND_PERCENTILES`, P50 and above) plus the maximum. A loop with no straights necessarily demands more than a human at the bottom of the distribution: a single seed measures 0.28 at P5 against a human 0.05. That is research C9's accepted premise, not a breach, and checking low percentiles would fail tracks for having the property the design intends
  - The maximum is checked separately rather than inferred from P99, because a distribution can sit under the human curve at every percentile and still contain one impossible corner, which is exactly what an agent would fail on
  - **Measured on the 40 train seeds: within bound, max demand 0.552 against a human 1.000, zero exceedance, percentile gaps -0.048 at P50 to -0.501 at P99.** `MatchReport` is retained and its 0.0930 pinned by a test, so a change in the generator surfaces rather than passing unnoticed
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
