# Tasks: Dense Progress Reward

**Input**: Design documents from `/specs/007-dense-progress-reward/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included, and not optional. Constitution Principle VIII requires EditMode tests for
Unity logic and `pytest` for Python. This feature is unusual in that its two central claims are
themselves test assertions rather than prose: the term telescopes, and a loop sums to zero. If
those two tests do not exist, the feature has not been demonstrated, whatever the training curves
say.

**Organization**: Grouped by user story. US1, US2 and US3 are all P1 and are sequential: there is
no run to judge until the term is known to be correct, and no model to evaluate until something has
trained. US4 is P2 and is genuinely parallel to the runs, because it is instrumentation and
reporting.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Four orderings this feature must not violate

**The design writeback comes first.** T001 blocks every code task. This feature *is* a change to
the reward table, so Principle V is not a formality here: the potential, the unwrapping, the clamp
and the derived weight go into `DESIGN.md` 4.5 before the code that implements them.

**The two property tests come before any training run.** T012 and T013 block T020. A training run
against a term that does not telescope measures a different reward from the one the design
describes, and it costs an hour to find out.

**The spread comes before every comparison.** T021, T022 and T023 block T025 and every sentence in
the results that calls one configuration better than another. Feature 006 wrote this ordering down
as the one most likely to be skipped, and it was right to.

**The 0.19 gate from feature 006 may not be reused.** It was measured on cumulative reward, and
this feature changes the scale of cumulative reward. T024 produces the gate this feature uses.
Quoting 0.19 anywhere in this feature's results is a defect, not a shortcut.

---

## Phase 1: Setup

**Purpose**: the design decision, written down, plus the baseline a later regression is measured
against.

- [X] T001 Rewrite `DESIGN.md` 4.5 in a `docs:` commit before any code exists: the potential as the
      arc position along the marker chain (R1), the unwrapping across the finish (R2), the clamp at
      the ring's due marker (R3), the weight derivation `0.5 * 24.0 / ChainLength` with its three
      reasons (R5), and the anti-farming invariant **restated rather than deleted**, showing that
      the progress term contributes exactly zero to circling so the existing arithmetic against
      `SpeedReward` 0.002 is untouched. **Principle V requires this first and this task blocks every
      code task below**
  - Written as an amendment to 4.5, not a new section. Section numbers are cited from every spec
    and renumbering breaks those references silently. 121 lines added, one line changed
  - The existing M3 closeout paragraph, which names the three remedies, gained the line saying
    feature 007 takes the second of them and that the other two stay open and untouched, so a moved
    number is attributable to one remedy
  - **The nominal numbers are now literal rather than approximate.** 4.5 already carried the T060
    and T061 measurement: chain 202.3 m, 24 markers, spacing 8.43 m. So the derived weight is
    `0.5 x 24.0 / 202.3`, about 0.0594 per metre, and at the scripted driver's roughly 0.2 m per
    physics step that is about **0.0119 per step** against a step cost of -0.001. The research
    document had written the chain as "about 202 m"; the design now uses the measured figure
  - **The double charge on reversing is now a number.** 4.5 already fixed wrong-way detection at
    3.43 m of reversing (T061). At the derived weight those 3.43 m also cost about **-0.204** of
    progress on top of the -1.0 wrong-way penalty. Written into the design so the double charge is
    read as a decision rather than as an oversight
  - The `DecisionPeriod: 4` finding from R6 is written into 4.5 as the closing paragraph, so the
    one item M3 left open is now explained in the design rather than only in this feature's research
- [X] T002 [P] Record the pre-feature test baseline in this file: full suite in `.venv` and in
      `.venv-bc`, and the Unity EditMode count. Feature 006 closed at `.venv` 347 passed / 3
      skipped, `.venv-bc` 401 passed, EditMode 109 green. Confirm those still hold on this branch
      before changing anything. Do not pass a second `-q`; `pytest.ini` already sets `addopts = -q`
      and a second one suppresses the pass count
  - Measured 2026-08-25 on this branch: **`.venv` 347 passed, 3 skipped** in 212.5 s, and
    **`.venv-bc` 401 passed** in 217.0 s. Both agree exactly with the counts feature 006 closed at,
    so nothing regressed between the 006 merge and this branch and T047 compares against these
  - Unity EditMode is **not** measured here. 006 closed at 109 green, and confirming that is the
    owner's Test Runner step, not something this task can assert
- [X] T003 [P] Record the pre-feature throughput baseline: feature 006 measured 684 steps/s at
      2,000,000 steps. This is what T023's regression check compares against
  - Recorded: **684 steps/s**, from feature 006's 5,000,000 steps in 7,308.3 s. A drop well below
    about 600 at T023 means the chain is being remeasured per step instead of per track build

**Checkpoint**: the design is written, the baselines are recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the arc geometry. Every user story reads it and none can begin without it.

**CRITICAL**: T001 must be complete before any task in this phase.

- [X] T004 Create `unity/SelfDrivingSim/Assets/Scripts/Track/TrackProgress.cs` with the derived
      chain data from the data model: `SegmentLength[]`, `CumulativeLength[]` and `ChainLength`,
      computed once from `CheckpointRing.Markers` at track build and never per step. Fail loudly at
      build on a zero-length segment rather than dividing by zero in the weight derivation
  - Written as a plain class, **not a MonoBehaviour**, taking `IReadOnlyList<Vector3>` rather than
    transforms. That is what lets T012 and T013 run against a synthetic 24-gon with no track, no car
    and no physics step
- [X] T005 Add the projection to `TrackProgress`: given a world position and the ring's
      `NextIndex`, project onto the segment ending in that marker, clamped to the segment
      endpoints, and return `RawArc` as `CumulativeLength` at the segment start plus the projected
      length
  - **This task found a real ordering trap before any code ran.** `CheckpointRing.StartAt(k)` puts
    the car on marker `k` and then sets `StartIndex` to `k + 1`, because the ring's `StartIndex`
    means "the first marker that was **expected**", not the marker the car is on. Measuring the arc
    from the ring's value would put every episode's origin one marker ahead of the car, so the first
    step of every episode would read as almost a whole lap already banked. `TrackProgress.Reset`
    takes the ring's value and steps back one, in one place, and `OriginIndex` carries the
    explanation so no caller has to remember it
- [X] T006 Add the unwrapping (R2): `Unwrapped = RawArc + LapCount * ChainLength`. There is no
      special case at the finish line and there must not be one
  - Verified against the ring rather than assumed: `Contact` increments `LapCount` in the **same
    call** that wraps `NextIndex` back to `StartIndex`. Had they been one step apart there would be
    a single step per lap where the lap term had not yet arrived and the position dropped by a whole
    chain, which is exactly the -12.0 spike the unwrapping exists to prevent
- [X] T007 Add the clamp (R3): `Ceiling` is `CumulativeLength` at the end of the segment
      terminating in `NextIndex`, and `Clamped = min(Unwrapped, Ceiling)`. This is the mechanism
      that makes a shortcut worth nothing (FR-008)
- [X] T008 Add the per-step advance (R4): compute the advance from the change in projection plus
      any whole segment crossed, not by differencing the running totals. Keep the totals in
      `double` for reporting and for the telescoping test only
  - **Done differently from how the task and R4 wrote it, and `DESIGN.md` 4.5 was amended first
    rather than the code quietly deviating (Principle V).** The position is held in `double` and the
    difference is taken in `double`. The local-advance version was rejected because it is worse, not
    merely more code: the reward is the difference of the **clamped** position, so a local
    computation would have to track whether the previous step was sitting at the ceiling, which
    duplicates the clamp logic into the one place an error would cost most
  - The number that settles it: `float` carries about seven significant digits, so at a kilometre
    driven its ulp is about 0.00006 m, and the telescoping test sums thousands of small terms
    against one large difference. In `double` the ulp there is about `2.3e-13` m, twelve orders of
    magnitude below a 0.2 m step. The cast to `float` happens once, when the distance becomes a
    reward
- [X] T009 Add `HasPrevious` and `Previous` to `TrackProgress`, with a `Reset()` that clears both,
      so the first step of an episode charges nothing (FR-004)
  - `Reset` also clears `Unwrapped`, `Ceiling`, `Clamped` and `AtCeiling`, so a swap to a different
    chain cannot leave anything behind for the next episode to difference against (R7)
- [X] T010 Add `ProgressWeight` to `TrackProgress`, computed at build as `0.5 * 24.0 / ChainLength`
      (R5). **Not a literal.** Generated tracks differ between seeds and a literal would pay
      different fractions of a lap on different tracks
  - Signature is `Configure(markerPositions, checkpointReward)`. The lap payout is derived as
    `LapPayoutFraction * Count * checkpointReward`, so the 24.0 is never written down: it is the
    marker count times what a marker pays. Passing the reward in as a parameter also keeps
    `SelfDrivingSim.Track` clear of `SelfDrivingSim.Agent`, which would otherwise be a layering
    inversion

**Checkpoint**: the geometry exists and is testable without a car, a scene or a physics step.

---

## Phase 3: User Story 1 - The car is told whether it is getting anywhere (P1)

**Goal**: the term is known to be what it claims to be, before a single training step is spent.

**Independent test**: one lap by the scripted driver, summed term against the endpoint difference.

- [X] T011 Create `unity/SelfDrivingSim/Assets/Tests/EditMode/TrackProgressTests.cs` with a
      synthetic polyline the tests hand in directly, so none of them needs a track, a car or a
      scene (FR-022)
- [X] T012 [US1] **The telescoping test.** Sum the term over a trajectory and assert it equals
      `ProgressWeight * (Clamped_end - Clamped_start)` within R9's tolerance: 0.1 per cent relative,
      with an absolute floor of `ProgressWeight * 0.01 m`. This is FR-005 and SC-001, and it blocks
      every training run
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
  - **Counted on 2026-08-26 through `TestRunnerApi`: 132 passed, 0 failed, 0 skipped, in 2.52 s.**
    That is feature 006's closing 109 plus this feature's 23, and it was measured after the
    `episode/markers` and `episode/physics_steps` changes rather than before them. This is the
    Phase 4 gate: T012 telescoping and T013 the loop property are both inside that green run, so
    training may start
- [X] T013 [US1] **The loop test.** A trajectory returning the car to a state it already occupied,
      without crossing the finish forward, sums to zero within the same tolerance. This is FR-007
      and SC-002, and it is what preserves the anti-farming invariant
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
  - **The first EditMode run failed this one, and the failure was in the test.**
    `Circling_for_a_whole_episode_earns_nothing_from_this_term` read 0.23211 against a tolerance of
    0.00038306. The tolerance is the tell: it is `ProgressWeight * 0.01`, so the weight was 0.038306,
    the chain 313.26 m, and the surplus divides out to **6.06 m** against a half-segment of 6.53 m.
    The test seeded `Previous` at `markers[0]` and then teleported the car onto a circle centred
    mid-segment, so it measured the jump, not the loop; it also stopped one step short of closing the
    final turn. Now seeded on the circle itself, run over a whole number of 60-step turns, with the
    angle taken modulo one turn so the closure is exact rather than dependent on `Mathf.Cos` at 628
    radians
  - Worth keeping: the loop property is stated over a path that **returns to where it started**, and
    the first draft of its own test did not return. That is the same class of error the first-step
    rule and the swap reset exist to prevent
- [X] T014 [P] [US1] Test that the term shows no jump at the step a marker is taken beyond what
      that step's movement accounts for. This is the failure mode that R1 rejected the
      distance-to-next-marker potential to avoid, and the test exists so nobody reintroduces it
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
- [X] T015 [P] [US1] Test symmetry: driving a stretch backwards costs exactly what driving it
      forwards paid
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
- [X] T016 [P] [US1] Test the first step of an episode charges zero, and that `Reset()` restores
      that state
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
- [X] T017 [P] [US1] Test the clamp: a position advanced past the due marker earns nothing further
      until the marker is taken
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
- [X] T018 [P] [US1] Test the degenerate chain: a zero-length segment fails at build rather than at
      run time
  - **Green.** Owner-run in the EditMode Test Runner, 2026-08-25. The exact suite count was not
    captured at the time, so T047 re-measures it against feature 006's closing 109 rather than
    against a number quoted from memory here
- [X] T019 [US1] Add the term to `RewardModel.cs`: one constant, one pure function
      `Progress(float advance, float weight)`, one `MarkerProgress` field in `Breakdown`, and
      `MarkerProgress` in `Total`. **The six existing terms keep their names, weights, firing
      conditions and stats keys.** Update `RewardModelTests.cs` for the seven-term sum and for the
      restated anti-farming invariant
  - `RewardModel.Progress(double advanceMetres, float weightPerMetre)`, plus `MarkerProgress` in
    `Breakdown` and in `Total`, which is now a sum of **seven**. The six existing terms are
    untouched
  - **There is deliberately no weight constant in `RewardModel`.** Every other term prices an
    event and is a fixed number; this one prices a distance, and a lap's distance differs between
    generated tracks. The weight is derived per track by `TrackProgress.ProgressWeight`, and a
    constant here would silently pay a different fraction of a lap on every seed
  - Three cases added to `RewardModelTests`: the term adds nothing to a closed loop, it is
    symmetric rather than one-sided, and a lap of it pays half of what its markers pay. The
    existing `Circling_on_open_surface_earns_nothing_per_step` is left as it stands, because the
    new term contributes zero to circling and so the margin it asserts is unchanged
- [X] T020 [US1] Wire the term into `DrivingAgent.cs`: hold the `TrackProgress` instance, charge
      `reward/progress` every physics step after the first, clear it on episode begin, and report
      the term to the trainer statistics with `StatsAggregationMethod` matching the six existing
      terms
  - Charged in `AccrueStepTerms`, the same call site as the step and speed terms, which is reached
    from `OnActionReceived` every physics step because `TakeActionsBetweenDecisions` is on
  - `ResetProgress` re-reads the marker chain **every episode** rather than once at startup. It is
    24 distances against an episode of several hundred steps, so it is not a per-step cost, and
    paying it makes the track-swap case correct without a dirty flag somebody has to remember
  - A degenerate chain throws from `Configure`, which an EditMode test asserts, but the agent
    catches and logs it: an exception out of `OnEpisodeBegin` fires once per episode for the rest
    of the run and buries the first occurrence. `Configure` now clears the weight **before** the
    loop that can throw, and `Step` pays nothing at a zero weight, so a failed chain is inert
    rather than priced with the previous track's weight. That last part is its own test
- [X] T021 [US1] Route `TrainingArea.SwapTo` through the episode-begin reset (R7, FR-011), and add
      the EditMode assertion that a swap leaves no stale previous position. Feature 006 found this
      exact path bypassing the reward reporting; it must not also bypass the reset
  - **No code change needed, and that was checked rather than assumed.** Feature 006's fix already
    has `SwapTo` end the episode through `agent.EndForTrackSwap()`, which calls `ReportEpisode`
    then `EpisodeInterrupted`, so `OnEpisodeBegin` runs and the reset with it. The assertion is
    `A_swap_to_a_different_chain_cannot_leave_a_stale_position_behind` in `TrackProgressTests`
- [X] T022 [US1] **The scripted-driver lap check.** Drive one seed in `Assets/Scenes/Evaluation.unity`
      with the scripted driver and the instrumentation on, and confirm the `reward/progress` total
      for a full lap is **12.0** within tolerance, from any start marker. Record the seed and the
      measured total here. Scene note from 006: the `TrainingArea` component stays removed from that
      instance or the car parks in `Awake`
  - **Measured on seed 1, three consecutive laps, each paying exactly 12.0.** Chain 24 markers,
    201.017 m, weight 0.0597 per metre. Run ended `LapComplete` in 80.7 s with 0 wall contacts and
    72 markers taken, which is 3 x 24

    | lap | steps | progress total | this lap | unwrapped |
    |---|---|---|---|---|
    | 1 | 1365 | 12.0 | 12.0 | 351.82 m |
    | 2 | 2699 | 24.0 | 12.0 | 552.84 m |
    | 3 | 4034 | 36.0 | 12.0 | 753.86 m |

  - **The unwrapping is what the middle column proves.** `Unwrapped` climbs by 201.02 m per lap,
    which is `ChainLength` to the centimetre, so the finish line costs no special case and the one
    step per lap where a reset would charge a whole lap of penalty does not exist. The start was at
    marker 17 of 24, not marker 0, which is the "from any start marker" half of the requirement
  - **Not run in `Evaluation.unity`, and the reason is a defect in this task rather than in the
    code.** That scene was created by feature 006 for the learned driver and has never contained a
    `HeuristicDriver`; the scripted sweeps have always lived in `HeuristicTrack` and
    `HeuristicWeighted`, and neither of those contains a `DrivingAgent`. Composing the two failed
    four times over: the scripted driver commanded zero steering for 1.4 s and hit a wall, with
    `dsteer p95 0.0000`. Ruled out along the way, each with evidence rather than argument: the two
    drivers contending for `CarController.ScriptedMove` (`SetEngaged(false)` did not fix it, and
    the first failure predates any probe), the sensing configuration (identical in both scenes at
    13 rays, 180 degrees, 20 m, mask -1), missing barrier colliders (2 present, a raw cast hits one
    at 12.08 m), and ML-Agents cycling episodes underneath the sweep (`MaxStep` is 0)
  - **What was run instead, and what it is worth.** A probe carrying its own `TrackProgress`,
    driven from the car's position in `HeuristicWeighted.unity`, where the scripted driver already
    completes laps. It makes the same two calls `AccrueStepTerms` makes, in the same order, so it
    measures the real chain off a real generated track and the real `CheckpointRing.LapCount`
    across the finish. What it does not cover is that `DrivingAgent` calls `Step` exactly once per
    physics step, and that is measured by T040's `PhysicsStepsCharged` in the candidate run, which
    was always going to measure it. The probe was deleted after the reading was taken
- [X] T023 [US1] Confirm the throughput has not regressed against T003's 684 steps/s. A drop well
      below about 600 means segment lengths are being recomputed per step instead of per build
  - **No regression. 1,046 steps/s against the 684 baseline**, measured on a throwaway probe run
    against `Training.unity` with the full `config/ppo_car.yaml`, killed after 80,000 steps and its
    `results/` directory deleted. The run id was `ppo_car_007_throughput` and it appears in no
    table, because a killed run is not a result

    | window | steps | seconds | steps/s |
    |---|---|---|---|
    | 10k to 80k, steady state | 70,000 | 66.93 | **1,046** |
    | slowest 10k interval | 10,000 | 11.44 | 874 |
    | fastest 10k interval | 10,000 | 7.87 | 1,271 |

  - **The first summary is excluded and that is not cherry-picking.** Step 0 to 10,000 took 42.96 s
    against a steady-state 9.56 s, because it carries the editor connecting, the first track build
    and the trainer's own warm up. Including it would report 745 steps/s and understate the
    steady rate the check is about
  - **The margin says the chain is measured per build, which is what the check exists to detect.**
    The failure mode is 24 segment lengths recomputed on every physics step; at 50 Hz that is the
    kind of cost that shows as a collapse toward 600, and the rate went up rather than down. The
    per-episode re-read in `ResetProgress` costs 24 distances against several hundred steps, and it
    does not show at this resolution

**Checkpoint**: the term is correct and cheap, demonstrated rather than asserted. Training may
start.

---

## Phase 4: User Story 2 - A policy that reaches markers (P1)

**Goal**: the number that says whether the mechanism worked.

**Independent test**: markers earned per episode against the 006 baseline of 0.249, judged against
a gate measured on that metric.

**CRITICAL**: T012 and T013 must be green before any task in this phase.

- [X] T024 [US2] Extend `python/rl/export_curves.py` for the `reward/progress` key and for the
      behavioural metrics the data model names: `MarkersPerEpisode`, `LapsCompleted`,
      `StalledShare`. Extend `python/tests/test_rl_curves.py` to cover them
  - Columns added: `reward_progress`, `markers_per_episode`, `physics_steps_charged`, and a
    derived `stalled_share`. Seven new cases in `test_rl_curves.py`, 22 in the file, full suite
    green
  - **`LapsCompleted` is the existing `end_lapscompleted` column and is not duplicated under a
    second name.** Two columns holding one measurement is two things to keep in step, and a test
    asserts the second name stays absent
  - **`stalled_share` is derived in the export rather than left to each reader**, over every end
    reason as the denominator. SC-003's second acceptance scenario is that the stall share falls
    without the wall share rising to replace it, which is a question about proportions; a share
    recomputed in three notebooks is three chances to pick a different denominator. Empty rather
    than zero when no episode ended at that summary, and zero when episodes ended and none stalled,
    which are different facts and have separate tests
  - **This task also needed a Unity change, because the trainer was never emitting the metric.**
    `episode/markers` is `CheckpointRing.AwardedCount` at episode end. SC-003 is read on markers
    taken rather than on `reward/checkpoint`, because adding a term changes what a reward number
    means and does not change what reaching a marker means (FR-018)
  - **T040's counter was pulled forward into this task and that was the point.** `episode/markers`
    and `episode/physics_steps` both land before T025, so all four runs share one build. T040 asks
    for `PhysicsStepsCharged` *from the candidate run*; the counter did not exist, and had it
    stayed missing until Phase 6, T029 would have had to be re-run at a cost of about two hours.
    `_physicsStepsCharged` counts in `AccrueStepTerms`, the one place the per-step terms are
    charged, and is reported as a mean so it is the same kind of number as the trainer's own
    `Environment/Episode Length` and their ratio is the one R6 asks for
- [X] T025 [P] [US2] Spread run a: reduced budget, seed 1, the new table, nothing else different.
      Row in `results/EXPERIMENTS.md` in the same session
  - 2M in 2,540.7 s, 787 steps/s. Markers per episode 0.2608, zero laps, step ratio 3.1652
  - **An earlier attempt was killed at 1,440,000 steps** when the background task holding the
    trainer was stopped, and a killed run is discarded rather than resumed. Kept as
    `results/rl/ppo_car_007_spread_a.killed_at_1440k.log`. Every run after it was launched detached
    through `Start-Process`, so stopping a watcher no longer stops training
- [X] T026 [P] [US2] Spread run b: identical, seed 2
  - 2M in 2,597.9 s, 770 steps/s. Markers per episode 0.2290, zero laps, step ratio 3.1536
- [X] T027 [P] [US2] Spread run c: identical, seed 3
  - 2M in 2,649.4 s, 755 steps/s. Markers per episode 0.2576, zero laps, step ratio 3.1627
- [X] T028 [US2] **Write `results/rl/progress_spread.md` before looking at any candidate.** Sample
      standard deviation and gate for markers per episode, laps completed and stalled share, over
      T025 to T027. This is the gate this feature uses, and the 0.19 from feature 006 is not it
      (R8, FR-017)
  - **Written 2026-08-26, before the candidate run was launched.** Gates, two standard deviations
    as in feature 006: markers per episode **0.035** on an sd of 0.0175, stalled share **0.019** on
    an sd of 0.0095, and laps completed needs no arithmetic gate because the floor is exactly zero
    and one lap is the signal. The baseline to beat is **0.249 markers per episode**
  - **The 0.19 gate is retired in the document itself, with the reason.** It was measured on
    cumulative reward, and 006's rescoring trick cannot rescue it here: rescoring works for a
    changed weight and not for an added term, because the baseline runs never charged the term
  - **`markers_per_episode` and `reward_checkpoint` are the same number exactly**, since
    `CheckpointReward` is 1.0. Verified across all 600 rows of the set, largest absolute difference
    0.0000000000, which makes 006's checkpoint figures comparable with no conversion
  - **The warning the set carries:** markers per episode means 0.2491 against 006's 0.249, an order
    of magnitude inside the gate. At 2M the term did not move the metric. Recorded before the
    candidate rather than discovered after it
- [X] T029 [US2] The candidate run: full 006 baseline budget, one change from 006, which is the
      reward table. `config/ppo_car.yaml` is reused unchanged and that is the point. Row in
      `results/EXPERIMENTS.md` in the same session
  - **`ppo_car_007_progress`, 5,000,000 steps in 5,395.4 s, 927 steps/s, uninterrupted.**
    `config/ppo_car.yaml` reused unchanged, `--seed=42` to match `ppo_car_v01` exactly, so the
    reward table is the only difference from feature 006's baseline. Seed confirmed from
    `results/ppo_car_v01/configuration.yaml` rather than from the README, which shows a generic
    `--seed=1`
- [X] T030 [US2] Read markers per episode against 0.249 and against T028's gate (SC-003). Read the
      stall share and confirm any fall is not simply the wall share rising to replace it
  - **SC-003 clears by a factor of about 36.** Markers per episode 1.4987 run mean and 2.6975 over
    the last 50, against a baseline of 0.2490 and a gate of 0.035. By quarter 0.3477, 0.9794,
    2.1148, 2.5528, monotonic rather than a spike
  - **The stall fall is not clean and the row says so.** Stalled 0.3903 to 0.2741, a fall of 11.6
    points, against wall contact 0.4773 to 0.5907, a rise of 11.3 points. Close to a straight
    trade. What the trade cannot explain is the six fold rise in markers and the eight completed
    laps, so the reading is that the car now fails while driving rather than while sitting still
- [X] T031 [US2] Read the lap counter over the run: did any episode complete a lap (SC-004)? No run
      in M3 ever did, across nine runs and more than 12,000,000 steps
  - **Eight laps completed over 13,851 episodes.** Feature 006 completed zero across nine runs and
    more than 12,000,000 steps, so against a floor of exactly zero this is the SC-004 signal. It is
    a small number and is reported as one: 0.06 per cent of episodes
- [X] T032 [US2] Verify FR-010 against this feature's own exported rows: the seven terms sum to the
      trainer's cumulative reward, reported as a percentage of rows that agree. **Do not inherit
      006's check.** Its per-term sum was wrong on 97.4 per cent of rows until the swap bug was
      found, and the reason the defect was found at all was that someone re-ran the check
  - **FR-010 does not hold on this run, and the cause is not identified.** The seven terms sum to
    the trainer's cumulative reward on 4.8 per cent of 500 rows, residual mean +0.3030, sd 0.5110,
    max absolute 4.6014. Re-run against this feature's own rows as the task required, not inherited
  - **There is no eighth term.** All four `AddReward` sites in `DrivingAgent` are mirrored into
    `RewardModel.Breakdown` and there is no lap bonus, so this is an aggregation mismatch rather
    than a missing payment
  - **Two hypotheses tested, neither survived.** Feature 006's straddling-summary idea gives a
    correlation with episodes per summary of -0.002; the successor idea that `EndForTrackSwap`
    reports an episode the trainer counts differently gives -0.097 against the swapped share,
    despite our 13,851 end-reason count against a trainer count implied at about 11,219
  - **What it does track** is activity: +0.643 against `reward/progress` and +0.645 against markers
    per episode, growing by quarter -0.0462, +0.1474, +0.4806, +0.6303. The shape fits a fixed
    disagreement about which episodes enter the two means, whose error scales with the spread of
    episode rewards; testing that needs per-episode records, which this export does not carry
  - **The behavioural results do not depend on it.** Markers, laps and the end-reason mix are counts
    taken on the Unity side
- [X] T033 [US2] Write the FR-018 note into the run's `EXPERIMENTS.md` row: cumulative reward is
      not compared against any 006 run, and the reason is that the table gained a term
  - Written into the `ppo_car_007_progress` row: cumulative reward is not compared against any
    feature 006 run, because the table gained a term and 006's rescoring trick cannot rescue it.
    Rescoring works for a changed weight and not for an added one, since the baseline runs never
    charged the term

**Checkpoint**: the mechanism either worked or did not, against a gate that was fixed first.

---

## Phase 5: User Story 3 - The exported model drives held-out track (P1)

**Goal**: the M3 column, whatever it says.
- [ ] T034 [US3] Export the model and promote it to `unity/SelfDrivingSim/Assets/Models/`. Confirm
      LFS routing with `git check-attr filter -- <path>.onnx` before the blob lands
- [ ] T035 [US3] Run the evaluation sweep on the ten held-out seeds in
      `Assets/Scenes/Evaluation.unity`, deterministic inference, with no trainer attached. Confirm
      the `Couldn't connect to trainer on port 5004. Will perform inference instead.` line, which
      is what makes SC-005's "no trainer" claim checkable
- [ ] T036 [US3] Repeat in sampling inference. Feature 006 measured a factor of 83 between the two
      on steering variance, so they are reported separately and not averaged
- [ ] T037 [US3] Record lap completion per seed. SC-005 asks for at least one lap; SC-006 is the
      milestone bar of 80 per cent, restated unchanged from feature 006's SC-002, and it is
      recorded met or not met with the number that decides it
- [ ] T038 [US3] Extend `python/rl/report.py` and `python/tests/test_rl_report.py` so the learned
      column carries the new metrics, and regenerate `results/rl/rl_steering.md` with the RL column
      beside the scripted driver's 34 of 34 and the human reference
- [ ] T039 [US3] Carry feature 006's caveat forward rather than dropping it: the chi-squared test
      against the human distribution is saturated at 8,450 against 32,443 samples and measures data
      volume rather than driver difference. If it is reported, it is reported with that sentence

**Checkpoint**: the RL column exists and names its losses.

---

## Phase 6: User Story 4 - The step accounting is settled (P2)

**Goal**: close the one item feature 006 left open.

**These tasks are parallel to Phases 4 and 5.** They need one instrumented run, not a dedicated
one.

- [ ] T040 [P] [US4] Instrument both counts in the candidate run: `PhysicsStepsCharged` from the
      reward path and `TrainerEpisodeLength` from the trainer, per summary
- [ ] T041 [US4] Report the ratio against the expected ceiling of **4**, which is
      `DecisionPeriod: 4` at `unity/SelfDrivingSim/Assets/Prefabs/TrainingArea.prefab` line 428
      (R6). Feature 006 measured a mean of about 3.16 with a maximum of 4.01 and could not say why
- [ ] T042 [US4] Separate the two mechanisms R6 names for the shortfall below the ceiling:
      episodes ending part way through a decision window, and swap-ended episodes counted by the
      trainer but not by the reward reporting. Report which accounts for how much, or state that it
      could not be separated and why
- [ ] T043 [US4] Fix any statement of episode duration in seconds in `results/` to name the count
      it is derived from, at 50 Hz on the physics-step count (FR-021, SC-012)

---

## Phase 7: Closeout

- [ ] T044 Write the closeout table into `spec.md`, every criterion with the number that decides
      it, and criteria that are not met stated as not met rather than restated to fit the result.
      This is the format the M3 closeout used and it is the reason that negative result is
      defensible
- [ ] T045 [P] Update `DESIGN.md` 4.5 with the outcome, in the house pattern: the decision, the
      number, and whether the change is kept. If the term is kept, say so; if it is not, the table
      the code carries is the one 4.5 shows
- [ ] T046 [P] Update `README.md` only if a command, a scene or a file name changed. The plan
      expects none did, and confirming that is the task
- [ ] T047 Run the full suite in `.venv` and `.venv-bc` and the Unity EditMode suite, and compare
      against T002. Every new test is accounted for by name; no existing test regressed
- [ ] T048 Merge checklist: no em dashes in any file this feature touched
      (`Select-String -Path <file> -Pattern ([char]0x2014)`), every `Assets/` file carries its
      `.meta` in the same commit, `.onnx` routed through LFS, no `Co-Authored-By` or session
      trailer in any commit message or in `EXPERIMENTS.md`, and every run in the feature has its
      row
- [ ] T049 State the next feature. If markers rose and laps did not, name what the binding
      constraint now looks like. If markers did not rise, then the dense signal was not it either,
      and the M3 closeout's remaining two remedies, curriculum and imitation warm start, are what
      is left. Either way this feature has removed one candidate from three by measurement, and
      that is the sentence the closeout should be able to write

---

## Dependencies

```text
T001  ->  everything
T004..T010            (geometry)      ->  T011..T018 (tests)
T012, T013            (the two claims)->  T020, and every run from T025 on
T019, T020, T021      (wiring)        ->  T022, T023
T024                  (export)        ->  T025..T027
T025, T026, T027      (spread runs)   ->  T028
T028                  (the gate)      ->  T030, T031, and every comparative sentence
T029                  (candidate run) ->  T030..T033, T034, T040
T034..T037            (evaluation)    ->  T038, T039
T040..T042            (accounting)    ->  T043
everything            ->  T044..T049
```

## Parallel opportunities

- T002 and T003 are independent of each other.
- T014 to T018 are five independent test cases in one new file; they touch no shared state.
- T025, T026 and T027 are three training runs and are parallel only in the sense that their order
  does not matter. **They are not parallel on this machine**: feature 006 recorded four runs killed
  mid-flight by launching tooling, and killed runs are discarded rather than resumed.
- Phase 6 runs alongside Phases 4 and 5 and needs no run of its own.

## Notes carried from feature 006 that apply unchanged

- `mlagents-learn` lives in `.venv-mlagents`, not the root `.venv`.
- Training needs `Training.unity` active and Play pressed; evaluation needs `Evaluation.unity`,
  with the `TrainingArea` component removed from that instance.
- Git Bash `kill -0` cannot see Windows PIDs. Use `tasklist`, and watch the *python* worker rather
  than the `mlagents-learn.exe` shim.
- Unity EditMode tests are owner-run from the Test Runner window. `TestRunnerApi` trips the MCP
  user-interaction guard, so this stays a human step.
- The `ppo_car_smoke` and `ppo_car_v01` archives must not be re-exported into the current schema.
  Their event files carry `episode/end_*` as a meaningless constant 1.0.
