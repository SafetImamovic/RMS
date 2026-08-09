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
  - **`AMPLITUDE_RANGE` widened from (0.40, 0.70) to (0.70, 0.90) on 2026-07-31**, after the first batch was generated and looked at. At the original range all 40 train seeds were accepted but the median tightest corner was 14.9 m against a 6.97 m floor, so no track ever asked for more than about half the steering range and the whole set was gentle blobs
  - At (0.70, 0.90): median tightest corner 9.6 m, acceptance 85 percent (34 of 40), well clear of the 50 percent SC-011 requires. The SC-010 bound still holds at every checked percentile, -0.031 at P50 through -0.358 at P99
  - This does **not** close the gap to human steering and was not meant to. Sweeping the whole usable span moves the P95 gap only from -0.299 to -0.224, because the shortfall is driving behaviour rather than track geometry, which is why SC-010 became a bound
  - **The change exercised the rejection path for the first time.** Six seeds now fail the radius floor, where previously every seed passed and that code never ran outside a test. It immediately exposed a real defect: three tests and `export.pooled_bound` pooled over ALL seeds rather than accepted ones. A rejected seed has a corner under the floor and therefore demands more than full lock, so pooling the six takes the peak from 0.789 to 1.072, past the human maximum, and the bound fails. That reads as a finding about the generator when it is only a seed already excluded. `pooled_bound` now raises on a rejected seed rather than pooling it
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
- [X] T045 [US2] Run `--batch train` and `--batch eval`, then commit the accepted `unity/SelfDrivingSim/Assets/Tracks/seed_*.json` files, the batch report and the split (FR-021)
  - The outputs were already generated and committed; what was missing was the tick and the check that they reproduce. **44 accepted seeds**, eval 10 of 10 and train 34 of 40 at 85 percent, with the two sets disjoint. Rejections are all the radius floor: seeds 4, 12, 15, 22, 28 and 33 have a tightest corner between 5.19 m and 6.26 m against a 6.97 m floor, and none was retried with adjusted parameters
  - **Re-ran `--batch all` into a temporary directory and compared. All 44 files reproduce exactly**, along with `seed_split.json`. `batch_report.md` differs in two lines, both generation timestamps, which `export.py` says up front is where reproducibility is not claimed
  - **The naive comparison says all 44 differ, and it is wrong.** `.gitattributes` sets `* text=auto`, so git stores LF and checks out CRLF on Windows, while a freshly generated file is written LF. Comparing the working-tree copy against fresh output diffs every line of every file. Comparing against `git show HEAD:<path>` gives the real answer, which is zero differences. Worth recording because the false negative looks exactly like a reproducibility failure and would send the next person hunting a bug that is not there

### Unity track construction

- [X] T046 [US2] Implement `unity/SelfDrivingSim/Assets/Scripts/Track/TrackFile.cs` reading the JSON into types mirroring the schema, with every one of the six failure modes in the contract handled as a refusal naming the offending field: unknown `schema_version`, `vehicle_profile` mismatch against the scene profile, `radius_ok` false, fewer than two centre-line points, checkpoints not monotonic in `s`, and a duplicated first and last point
- [X] T047 [US2] Write `unity/SelfDrivingSim/Assets/Tests/EditMode/TrackFileLoaderTests.cs` feeding one deliberately broken file per failure mode and asserting each is refused with the field named, plus a committed valid file that loads
  - Refusal messages format every number with `InvariantCulture`. The machine locale is bs-Latn-BA, so the first run reported `wheelbase_m is 3,1000 in the file` for a file that says `3.1`: a refusal describing a value appearing nowhere in the file it describes, and one that would read differently on another machine. Pinned by a test asserting the message contains `3.1` and not `3,1`
  - `JsonUtility` fills absent fields with zeroes rather than reporting them, so a missing `required_steer_descriptives` block is indistinguishable from one full of zeroes. `n <= 0` is what separates them
  - The tests load the **committed** track files as well as hand-written fixtures. A disagreement between `export.py` and this loader about the schema would not show up in a fixture written to match the loader
- [X] T048 [US2] Implement `unity/SelfDrivingSim/Assets/Scripts/Track/TrackBuilder.cs` building the drivable surface at `width_m`, barriers along both edges (FR-023) and the checkpoint objects, from a loaded `TrackFile`. It performs no statistics and draws no random numbers
- [X] T049 [US2] Create `unity/SelfDrivingSim/Assets/Scenes/Track.unity` with the car prefab, the track builder holding a seed field, and the camera. References only, no logic
- [X] T050 [US2] Write `unity/SelfDrivingSim/Assets/Tests/EditMode/TrackGeometryTests.cs` rebuilding geometry from a committed track file and re-measuring the minimum radius and the checkpoint order, asserting both match what the file claims. Unity and Python disagreeing is caught here, not during training
  - **Two winding bugs, neither of which any test could have caught.** `MeshCollider` ignores triangle winding, so the geometry was always correct and always drivable; the failure is purely visual. The surface one was the serious version: with the lateral normal for a tangent of +X being -Z, ordering the quad (a, c, b) gives a face normal of -Y, so the road faced the ground, was backface-culled from above, and was **invisible while remaining perfectly solid**. The second was the inner barrier, which is built by mirroring the offset, and mirroring the layout reverses the winding, so one barrier rendered as a lit wall and the other as a dark line
  - Both were found by rendering the scene and looking at it, which is the only way this class of defect surfaces. Recorded because the instinct on a geometry bug is to write another assertion, and no assertion over the file or the collider would have failed
  - The scene stores references only: four root objects, no baked geometry. `TrackBuilder.Build` runs in `Awake`, so committing the scene commits a seed number rather than 12000 vertices
- [X] T051 [US2] Drive a full keyboard lap on at least five different accepted seeds without leaving the drivable surface, and record which seeds (SC-012, FR-013 acceptance scenario 6)
  - Driven 2026-08-08. **Five seeds, five clean laps, 24 of 24 markers each, zero skipped, zero wrong-way, zero resets of either kind.** The seeds were not picked for convenience: they are the five tightest accepted tracks, so the hardest cases the generator produces all pass
  - | Seed | Tightest corner | Lap time | Set |
    |---|---|---|---|
    | 37 | 6.97 m, on the floor | 34.3 s | train |
    | 29 | 7.47 m | 22.0 s | train |
    | 1003 | 7.49 m | 22.0 s | eval |
    | 1 | 7.85 m | 22.2 s | train |
    | 1004 | 7.90 m | 21.9 s | eval |
  - **The lap times are a finding, not decoration.** Four of the five land within 0.3 s of each other while seed 37 takes **56 percent longer**, on a track the same length as the rest. Every accepted track is about 200 m, so the four sit near 9.1 m/s average while seed 37 averages 5.9 m/s. The radius floor is doing real work rather than being a formality: the one track sitting exactly on it demands a visibly slower lap, and the drop lands close to the 6.4 m/s the grip figures predict for a 6.97 m corner. That is an independent cross-check of `RFloorM` from the driver's seat
  - Both eval seeds were included deliberately. Driving only train seeds would leave the possibility that the eval split happens to contain something undriveable, which is exactly the kind of thing that surfaces later at the worst time
  - **T051 was blocked by a real defect and finding it is the more valuable half of this task.** See the note below; the task could not be attempted until it was fixed
  - `LapReport.cs` was added to make the record trustworthy. The verdict depends on four numbers spread across two overlays, and the person who has to read them is the one driving. It emits one line per completed lap carrying the seed, time, markers, skipped, wrong-way and both reset counts, with a PASS or FAIL, formatted with `InvariantCulture` so a figure pasted into this file does not depend on the machine's locale. The rows above are those lines

**Checkpoint**: seeds produce driveable, committed, reproducible tracks. Nothing senses anything yet.

---

## Phase 5: User Story 3 - The agent's senses, verified before any training (Priority: P3)

**Goal**: every observation the future agent will see, readable live during a human drive, plus ordered progress markers and wrong-way detection.

**Independent Test**: drive by keyboard with the observation panel open. Confirm each distance reading matches the visible distance to a barrier, the heading value peaks when the car points at the next marker, and markers are awarded in order and once each.

### Implementation for User Story 3

- [X] T051a [US3] Write the **decided** sensing and marker values into `DESIGN.md` sections 4.3 and 4.5 in a `docs:` commit before any Phase 5 code exists: 13 rays over 180 degrees, 20 m range with its derivation from the P95 stopping distance of 8.5 m, 24 checkpoints, and the start randomisation of a random checkpoint with 1.5 m lateral and 10 degrees of yaw. Principle V requires the design first (research C11, C12)
  - Written into DESIGN 4.3 (sensing) and 4.5 (markers and start). Every figure was checked against `config.py` before being written: stopping distance 8.55 m, ray length 20 m at 2.34 times that, 13 rays at exactly 15 degrees apart, 24 markers, 1.5 m lateral, 10 degrees of yaw
  - **DESIGN 4.3 previously named `RayPerceptionSensor3D` and no longer does.** Its encoding is one-hot per tag plus distance, which is more values than this needs and cannot be read during a drive. T057 requires every observation visible live and T062 requires each checked against a situation whose correct answer is visible, and that is far easier over a simpler encoding we own. Recorded as a change rather than made quietly
  - The no-hit encoding is stated explicitly because FR-025 turns on it: a ray hitting nothing reads 1.0 and a ray hitting a wall at zero range reads 0.0, so the two opposite situations sit at opposite ends of the range instead of collapsing together
- [X] T052 [US3] Implement the raycast sensing in `unity/SelfDrivingSim/Assets/Scripts/Agent/CarAgent.cs`: `RAY_COUNT` 13 rays over `RAY_FOV_DEG` 180 degrees ahead, `RAY_LENGTH_M` 20 m, with a no-hit encoding clearly distinguishable from a hit at zero distance (FR-024, FR-025, research C11)
  - `CarAgent` is a plain `MonoBehaviour`, not an ML-Agents `Agent`, and that is the decision this task turned on. An `Agent` collects observations only when the Academy steps it, so during the human keyboard drive that T057 and T062 are specified as, there would be nothing to read. M3 wraps this component and forwards the same values into `CollectObservations`; nothing here changes for that
  - No-hit reads 1.0 and a hit reads `distance / RAY_LENGTH_M`, so a wall against the bumper reads 0.0 (FR-025). `RayHit` is exposed alongside `RayDistancesM` because a miss stores the full range in metres, and without the flag a miss and a genuine hit at exactly 20 m would be indistinguishable in the debug panel
  - The fan is **horizontal**, built from the heading projected onto the ground plane, not from the body's own forward. A fan fixed to the body tilts with pitch and roll, so the same wall reads further away under braking and hard braking aims the whole fan into the road. The distances would then track suspension travel rather than the track ahead
  - Two exclusions, both of which would otherwise read as walls. The car itself: the origin sits inside the vehicle, so a plain raycast finds the body collider and the WheelColliders first and every ray reads near zero. Rejected by `attachedRigidbody` plus a transform-root fallback, in code rather than by layer, so a fresh clone needs no project-settings change. And triggers: the checkpoints span the full track width, so a fan that saw them would report a wall dead ahead exactly where the track is clear
  - **The three ray constants are not covered by a mirror test.** `vehicle_profile.json` carries no sensing block, so unlike the vehicle limits there is nothing standing between these fields and `config.py`; changing one means changing both by hand. Adding a sensing block would bump the profile schema, which every committed track file embeds, so it was left alone rather than done in passing
  - Namespace note for M3: inside `SelfDrivingSim.Agent` the bare name `Agent` binds to the namespace, so deriving from ML-Agents must be written `: Unity.MLAgents.Agent` or it fails with CS0118, which reads like a missing package rather than a name clash
- [X] T053 [US3] Add the self-state observations to `CarAgent.cs`: own speed, rotation rate, current steering, and heading relative to the next progress marker (FR-026)
  - Six values, exactly as DESIGN 4.3 tabulates them, bringing the vector to 19: speed forward and lateral, yaw rate, heading forward-dot and right-dot, steering. Held in one `Observations` array that the debug panel and M3's `CollectObservations` both read, so a panel cannot show a correct value beside a network being fed a wrong one
  - **Every divisor is derived from `VehicleProfile`, none is typed in.** Speed divides by `v_max_ms`; the yaw rate divides by `v_max_ms / r_min_m`, the fastest rotation the car can physically produce. Retuning the car retunes the observation scale with it rather than leaving the network reading a stale one
  - Lateral speed is reported separately rather than folded into a magnitude, because it is the only observation that says the car is sliding
  - Heading is a **pair** of dot products. The forward dot alone is symmetric and cannot separate a marker 30 degrees left from one 30 degrees right, so an agent given only that value would have to guess which way to turn
  - Sign convention stated once and shared: positive is right for the yaw rate, for the steering and for `RayAngleDeg`. Unity yaws right for a positive rotation about +Y, so `angularVelocity.y` needed no negation. Two adjacent observations disagreeing about which way is right trains perfectly well and cannot be read by a person
- [X] T054 [US3] Implement `unity/SelfDrivingSim/Assets/Scripts/Track/CheckpointRing.cs`: ordered markers, `next_index`, a marker awarded only when it is the expected next one, and a lap counted when the index wraps. No reward logic, that belongs to M3 (FR-027)
  - **Contact is a method call, not a collision.** `Contact(index)` is the whole state machine and `CheckpointTrigger` is a five-line component that turns a physics trigger into a call to it. That split is what makes T056 writable: a test that had to spawn colliders and step physics to reach the ordering rules would be testing the collider sizes and the physics step at the same time, and a failure would not say which broke
  - Three outcomes, not two: the expected marker is awarded, an already-taken marker is wrong-way, and a gate further round is counted as `SkippedContactCount` and awarded nothing. Awarding the third is exactly how an agent learns to cut the track
  - Re-entering a gate cannot award twice, because after the award it is no longer the expected one. Worth stating: a gate is a volume the car occupies for several physics steps, so straddling its edge is normal driving
  - `TrackBuilder` binds each gate to the ring using the **file's** `checkpoint.index`, not the loop counter. They agree only because the loader has already refused any file whose checkpoints are not monotonic in `s`, and binding to the counter would make that agreement a coincidence rather than a checked property
- [X] T055 [US3] Add wrong-way detection to `CheckpointRing.cs`, set when the vehicle approaches an already-passed marker, reported rather than scored (FR-028)
  - Raised by contact with any marker already taken this lap, cleared by the next correct one, never scored: M3 decides what a wrong-way agent is worth and cannot decide that if this class has priced it in
  - Contact rather than a heading test, and the accuracy that buys is bounded by the marker spacing, which is what SC-015 asks for. A heading test would fire sooner and also fire on every wide corner entry, where the nose points off the line for a moment without the car having turned round
  - The start-line seam is handled explicitly and has its own test. At a lap wrap the taken-markers array is cleared **except** for the marker that caused the wrap, since that one is immediately behind the car; clearing it too would open a one-marker blind spot where a reversal goes unreported
- [X] T056 [US3] Write `unity/SelfDrivingSim/Assets/Tests/EditMode/CheckpointOrderTests.cs`: in-order contact awards each marker exactly once; out-of-order contact awards nothing; contact with an already-passed marker sets wrong-way; the index wrapping increments the lap count; the awarded count over a synthetic lap equals `N_CHECKPOINTS`
  - 15 tests, all five required cases plus the double-award guard, the start-line seam, a skipped gate still being available when reached in order, wrong-way clearing on resumed progress, index bounds, and the three offset-start cases from T058
  - The lap count is asserted against the literal 24 rather than against `ring.Count`, because "the number awarded equals the number the ring holds" is true of an empty ring too
- [X] T057 [US3] Implement `unity/SelfDrivingSim/Assets/Scripts/Agent/ObservationDebug.cs` displaying every observation value live during play, including all 13 distances and the no-hit state (FR-029)
  - Reads `CarAgent.Observations` and recomputes nothing. IMGUI, like `DriveHud`, so it needs no canvas, no prefab and no scene wiring beyond the component itself. O toggles it
  - **The no-hit state is printed as the word `none`, not inferred from the number.** A miss reads 1.000 and a genuine hit at 20 m reads 1.000 too, so the panel is the one place the two are separated (FR-025)
  - A translucent bar under each row, because thirteen numbers changing at 50 Hz cannot be read as a shape, and the shape is what makes a single reversed or mis-angled ray obvious without reading any value
  - Also draws the fan into the game view with GL lines, using `CarAgent.RayDirection` so the drawing cannot disagree with the sensing. Depth testing is left on deliberately: a ray drawn straight through a barrier means that barrier has no collider
  - English only, unlike the bilingual `DriveHud`, because this is developer instrumentation rather than part of the calibration readout
- [X] T058 [US3] Implement start randomisation in `TrackBuilder.cs` or the spawn logic: a random checkpoint as the start, lateral offset within `START_LATERAL_M` 1.5 m, yaw within `START_YAW_DEG` 10 degrees (FR-030, research C12)
  - Implemented as a separate `Scripts/Track/StartPlacer.cs`, **not** inside `TrackBuilder`. TrackBuilder states that it draws no random numbers, and that is worth more than the one object saved by folding this in: the track built for seed 7 stays byte-identical and reviewable in a diff precisely because nothing in its construction path can vary
  - Placement goes through a new `CarController.SetSpawn`, not through the transform. The spawn is captured in `Awake`, and both the out-of-bounds reset and the R key return the car to whatever was captured then, so teleporting it silently would have had the first reset of the run drag the car back to the scene's original spawn point, most likely off the track
  - `CheckpointRing.StartAt(index)` was added for the same reason. The ring previously always expected marker zero, so every start away from the line would have read as a skipped gate and the first lap would never have completed. A lap is now completed by returning to `StartIndex`, which awards exactly `N_CHECKPOINTS` markers however the start was drawn, and that is the property T060 is checked against
  - `randomSeed` is exposed and negative means a fresh draw. A repeatable sequence of starts is what turns "the car span at the start" into something reproducible (Principle VI)
  - Placed in `Start`, not `Awake`: TrackBuilder builds in `Awake`, so the markers do not exist any earlier
- [X] T059 [US3] Park the car at known distances from a barrier and confirm each distance reading agrees with the true distance within 5 percent, and that a ray with nothing in range is distinguishable from one at zero. Record the measurements (SC-013)
  - Measured in the editor without entering play mode. Raycasts resolve against colliders, not against a running simulation, so parking the car is a matter of setting a transform and calling `Physics.SyncTransforms`. That makes the measurement exactly repeatable, which a hand-parked car is not
  - **Against the real barriers, seed 1.** Measured at centre-line sample 1017, chosen as the largest local radius on the lap (29 827 m, an inflection point). The barrier is a polyline offset from a curved centre line, so a perpendicular ray meets it at exactly half the width only where curvature is negligible; on a tight corner the true distance genuinely differs from 3 m and a correct ray would look wrong. Lateral offsets -1.50, -0.75, 0, +0.75, +1.50 m gave left-ray readings 1.500, 2.250, 3.000, 3.750, 4.500 m and right-ray readings 4.500, 3.750, 3.000, 2.250, 1.500 m, against expectations of exactly those values. **Worst error 0.00 percent** against the 5 percent bound
  - **Against a synthetic 6 m corridor, all thirteen rays.** The real track can only exercise the two rays that look straight across it, and a fan with the wrong spacing still reads correctly at -90 and +90 if its extremes are right, so the angles in between need a geometry whose answer is known for every ray. Readings against `half / sin(angle)`: 3.000/3.000, 3.106/3.106, 3.464/3.464, 4.243/4.243, 6.000/6.000, 11.591/11.591 either side of centre. **Worst error 0.00 percent**, spacing confirmed at 15.00 degrees
  - **FR-025, both ends.** With the car lifted 200 m clear, 13 of 13 rays report no hit and the lowest normalised value is 1.000. With a barrier 0.10 m from the sensor, the ray reads 0.100 m, normalised **0.0050**, `hit=true`. The two opposite situations sit at opposite ends of the range, as designed
  - Sensor origin corrected during this task. The default offset put the fan at y=1.0 on a car whose origin is at 0.5, and the barriers are 0.8 m tall, so **every ray looked straight over every barrier**. It is now -0.1 local, placing the fan at 0.4 m, the middle of the barrier, with room for the body to pitch and bounce without leaving it. Both the code default and the scene were corrected
- [X] T060 [US3] Drive a full lap and confirm the number of markers awarded equals the number on the track, none skipped and none double-counted (SC-014)
  - Done as a **scripted sweep**, not a keyboard lap: the car is walked along all 2000 centre-line samples of seed 1 and enter/exit are applied by hand at each step, exactly as OnTriggerEnter and OnTriggerExit would. That tests gate placement, gate size and the file-index binding together, which `CheckpointOrderTests` cannot, since those tests call `Contact` directly. The keyboard lap remains T051's job
  - Seed 1, 24 gates, 202.3 m lap, marker interval 8.43 m. From start gates 0, 6 and 18: **24 of 24 awarded, 1 lap, 0 skipped, no wrong way, every time.** Three starts rather than one because a bug in the wrap bookkeeping shows up at some offsets and not others
  - **This task found a real defect, and the first run of it read `awarded 25 of 24`.** A sweep that begins inside gate 0 and ends by re-entering gate 0 crosses 25 gates for one closed loop, which was a measurement artefact. Tracing it exposed a genuine fault underneath: `StartPlacer` sets the car down AT a marker, meaning inside its trigger volume, and Unity fires OnTriggerEnter for an overlap that begins by teleport just as it does for one the car drove into. That contact lands on the marker `StartAt` has just recorded as passed, so **every randomised start would have reported the car as going the wrong way before it had moved**. Fixed with `CheckpointRing._straddling`: the gate the car was set down inside is ignored outright until `Exit` reports the car has left it. `CheckpointTrigger` gained `OnTriggerExit` for that, and three tests cover it
- [X] T061 [US3] Reverse direction mid-lap and confirm wrong-way is reported within one marker interval of the reversal (SC-015)
  - Same sweep, reversed at the halfway sample after 11 gates, at s=98.5 m. **Wrong way reported after 3.43 m of reversing, against a marker interval of 8.43 m.** Comfortably inside the interval, and it is bounded by construction: contact detection cannot take longer than the distance back to the previous gate
- [ ] T062 [US3] Read every observation live during a human drive and check each against a situation whose correct answer is visible. Record which observation was checked against which situation (FR-029, the M2 gate)
- [X] T063 [US3] Record the **measured** sensing results in `DESIGN.md` sections 4.3 and 4.5 in a `docs:` commit: the ray accuracy from T059 and the wrong-way detection latency from T061. The decided values went in at T051a; only what had to be measured lands here (Principle V)
  - DESIGN 4.3 gained the T059 table (ray accuracy, the no-hit and hit-at-zero readings, and the sensor-height correction). DESIGN 4.5 gained the T060/T061 table (24/24 from three starts, 3.43 m wrong-way latency) and the straddle defect
  - DESIGN 4.3 also carried a false claim that the sensing values travel in `vehicle_profile.json` "like everything else". They do not: the exporter writes no sensing block. Corrected in place rather than left, since a reader would otherwise look for a mirror test that does not exist

**Checkpoint**: all three user stories work independently. The environment is ready for M3.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T064 Record the research C9 finding in `DESIGN.md` section 7: generated tracks contain no straight sections, so the M5 comparison must lean on execution metrics rather than raw marginal steering histograms
  - Written as a second boxed note in DESIGN 7, beside the lattice-resolution note from feature 002. Same shape of hazard, different cause, and the two are easy to confuse: one is about the RESOLUTION of the human record, this one is about the TOPOLOGY of the track. Both would look like dramatic findings and both would be artefacts
  - The figure that makes it concrete: the human drove straight 58.6 percent of the time, and a harmonic loop never does. The agent cannot produce the zero spike that is nearly three fifths of the human record, and no amount of training changes that
- [X] T065 Remove `com.unity.ai.assistant` from `unity/SelfDrivingSim/Packages/manifest.json` before the v1.0 submission tag, or write a justification for shipping a pre-release dependency. Constitution VI's clean-clone rule exists because a pre-release version string can be withdrawn or changed under the same number
  - **Removed rather than justified.** It was the only pre-release version string in the manifest, at `2.17.0-pre.1`, and it is an editor convenience with no bearing on what this project builds or measures
  - Checked before removing rather than assumed: no script under `Assets/` references it and no assembly definition lists it, so nothing in the project depends on it either directly or through an asmdef
  - Justifying it would have meant arguing that a clean clone should resolve a package whose version can be withdrawn or republished under the same number. There is no argument for that when the package does nothing for the project
  - `packages-lock.json` is tracked and regenerates when Unity next resolves, which also prunes the transitive packages this one pulled in. The lockfile change belongs in the same commit as the manifest change, since a manifest and a lockfile that disagree describe two different environments
- [X] T066 [P] Run `pytest python/tests -q` and confirm the M1, feature 002 and new generator tests are all green (Principle VIII)
  - 237 tests, all green, on 2026-08-04. Nothing in Phase 5 touched Python, so this is a regression check rather than new evidence
- [X] T067 [P] Run all Unity EditMode tests through Window > General > Test Runner and confirm green
  - **54 tests, 0 failed, 0 skipped, 0 inconclusive**, on 2026-08-04, after the Phase 5 additions. Run through `TestRunnerApi` with an `EditMode` filter rather than by clicking the Test Runner window; it is the same runner the window drives, and driving it from code makes the result reproducible and quotable
  - Green on 2026-07-31 after `TrackFileLoaderTests` (16) and `TrackGeometryTests` (9) were added, alongside the 8 `VehicleProfileMirrorTests`. Left open because this is the final gate and Phase 5 will add `CheckpointOrderTests` (T056)
- [X] T069 Correct `research.md` C15: it records `W1_STRUCTURELESS` as 0.1047 while `config.py` now carries 0.1142. Recomputing from the definition C15 itself states gives 0.1142 under both this project's Wasserstein implementation and `scipy.stats.wasserstein_distance`, agreeing to four decimals, while the same pair reproduces the other two scales exactly (0.0231, and 0.2636 against a recorded 0.2635). Support was ruled out as the cause: a uniform on [0, 1] gives 0.2127 and an unconditional reference 0.3359. No decision changes, since the threshold 0.05 sits below both figures, but the research document and the code currently disagree
- [X] T070 Update `contracts/track-file-schema.md` to match what `export.py` actually writes, in two places. First, there is **no `generated_utc` field**: a timestamp changes every run and makes byte-identical output impossible, which is what SC-007 requires and what lets a committed track be reviewed in a diff, so generation time moved to the batch report where reproducibility is not claimed. Second, the file carries a **`demand_bound` block**, which is what SC-010 is judged on after the criterion was revised from a distribution match to a bound; `match_report` is retained beside it as a diagnostic. The contract as written describes neither, so a reader following it would expect a field that is absent and miss one that decides acceptance
  - Both fixed in `contracts/track-file-schema.md`: the example shape lost `generated_utc` and gained `demand_bound`, and two new field rules explain why there is no timestamp and why the bound rather than the match decides acceptance. The stale `structureless: 0.1047` in the example and in the prose was corrected to 0.1142 at the same time, since T069 had just moved it
  - Verified against a real committed file rather than against the code: `seed_1.json` carries exactly the twelve top-level keys the contract now lists

- [X] T068 Walk `specs/003-unity-environment/quickstart.md` end to end on a clean checkout and confirm every command and every expected figure in its two tables
  - **Every geometric figure in the results table holds, checked across all 44 accepted tracks rather than a sample**: minimum radius 6.97 m against a 6.97 m floor, minimum separation 20.88 m against a claimed 12 m, maximum required steering 0.789 against a 0.789 cap, no self-intersections, acceptance 85 percent on train and 100 percent on eval against a 50 percent floor
  - The determinism block was run verbatim in PowerShell as written and prints `REPRODUCIBLE`. `seed_7.json` is unchanged against the committed blob afterwards, so the check does not dirty the tree
  - `compare_drive` runs and five of its six checks pass on a real lap. Both listed plots exist; `track_contact_sheet.png` also exists and was missing from the outputs table, now added
  - **The walk falsified a recorded prediction, which is the main result of this task.** T023 explained the `speed max/P99` failure as caused by the absence of a track and stated it "cannot pass before US2 generates one". Tracks now exist and six real laps measure **1.0001 to 1.0074** against a required [1.130, 1.381], which is worse than the 1.038 the flat plane scored. The cause is C9, already recorded: these tracks have no straights, so the car is corner-limited for the whole lap and its speed never peaks. Written up as research C17, and the quickstart now states it as a known and explained mismatch instead of promising a pass
  - **`pytest python/tests -q` carried the `-qq` bug**, the same one found in the 004 quickstart and README: `pytest.ini` already sets `addopts = -q`, so the flag suppresses the pass count. Corrected, with the expected result recorded: **237 passed** under `.venv`
  - Section 3 was thin on operating the scene and gained three things the walk showed a reader needs: that the seed must be set before entering play mode because the builder runs in `Awake`, that both overlays are **on by default** so pressing `O` or `H` turns them off rather than on, and the `LapReport` line with what `PASS` means
  - Section 1 gained a warning to choose the drive log deliberately. After section 3 has been run the newest log is a track drive, and the speed check reads differently on a track log than on the flat-plane log that section intends
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
