# Tasks: The wall terminal

**Feature**: `008-wall-terminal` | **Spec**: `spec.md` | **Plan**: `plan.md`
**Created**: 2026-08-26

## Format: `[ID] [P?] [Story] Description`

`[P]` marks tasks that touch no shared file and may be done in any order relative to each other.
`[US1]` and so on name the user story a task serves.

## Four orderings this feature must not violate

1. **`DESIGN.md` before code.** Principle V. The terminal is part of the reward table's contract.
2. **The recovery probe before the budget is chosen.** R4. If the car cannot reverse off a barrier
   the feature buys a slower failure, and that is a reason to stop rather than to continue.
3. **The EditMode properties before any training run.** A run against a budget that does not behave
   as described measures something other than what the spec claims.
4. **The two measures before the candidate run**, not after. Feature 007 learned this the expensive
   way: T040 wanted a counter from the candidate run and the counter did not exist yet, which would
   have cost a two hour re-run had it not been caught.

---

## Phase 1: Setup

- [X] T001 Rewrite `DESIGN.md` 4.5 and 4.6 in a `docs:` commit before any code exists: the wall row
      has a penalty and a terminal, they are separable, feature 006 tested the weight and this
      feature tests the termination. Record the budget field, its default as **to be filled by
      T004**, and the fact that zero reproduces feature 007
- [X] T002 [P] Record the pre-feature baselines in this file, quoted rather than recomputed:
      markers per episode **1.4987**, wall share **59.1 per cent**, stalled share **27.4 per cent**,
      held-out **6.20 of 24** markers and **0 of 10** laps, throughput **927 steps/s**, gate
      **0.035** from `results/rl/progress_spread.md`
  - Recorded, all from `ppo_car_007_progress` unless stated:

    | quantity | value | source |
    |---|---|---|
    | markers per episode, run mean | **1.4987** | curve, 500 summaries |
    | markers per episode, last 50 | 2.6975 | curve |
    | wall share | **59.1 per cent** | end-reason counts, 13,851 episodes |
    | stalled share | **27.4 per cent** | same |
    | track-swapped share | 13.5 per cent | same |
    | episodes completing three laps | 8 | `episode/end_lapscompleted` |
    | held-out markers, deterministic | **6.20 of 24** | `eval_ppo_car_007_progress_deterministic.csv` |
    | held-out markers, sampling | 4.60 of 24 | `eval_ppo_car_007_progress_sampling.csv` |
    | held-out laps | **0 of 10**, both modes | same |
    | throughput | **927 steps/s**, 5M in 5,395.4 s | run log |
    | mean episode length | 485.4 decisions, 1,676 physics steps | curve |
    | physics to decision ratio | 3.2161, sd 0.2829 | curve |
    | gate on markers per episode | **0.035** | `results/rl/progress_spread.md` |

  - **`WallContactsPerEpisode` and `LateralClearance` have no baseline**, because neither was
    measured before this feature. Their first values come from T017 and there is nothing to compare
    them against except each other across runs
- [X] T003 [P] Confirm the EditMode suite is green at **132** and the `.venv` suite at **357 passed,
      3 skipped** before anything changes, so a later regression is attributable
  - **EditMode 132 passed, 0 failed, 0 skipped, in 3.66 s**, run on this branch after the
    `DESIGN.md` change
  - `.venv` **357 passed, 3 skipped** and `.venv-bc` **411 passed**, measured at feature 007's T047
    on identical code earlier today. Not re-run here, because nothing between that measurement and
    this branch touched Python

**Checkpoint**: the design is written and the baselines are recorded.

---

## Phase 2: The gate that can cancel the feature (R4)

**This phase exists to be allowed to fail.** If the car cannot recover from a barrier, a contact
budget converts a seven second `WallContact` ending into a sixty second `Stalled` one and buys
nothing but wall clock.

- [X] T004 **The recovery probe.** In the editor, no training: place the car against a barrier at a
      representative speed and angle, apply reverse and steer, and record whether it separates and
      within how many physics steps. Try at least a glancing contact and a square one. Record the
      numbers here
  - **The premise holds. The car recovers.** Driven into a barrier at `approachSteer` 0.35 and
    speed_norm 0.723, then given full reverse and opposite steer, it moved **3.28 m in 150 physics
    steps (3 s)**, with one further contact on the way out. A contact budget therefore buys real
    recovery rather than a slower failure, and the feature continues
  - **The second run is the more useful one, and it was not planned.** Holding the throttle *into*
    the barrier instead of reversing moved the car **0.47 m in 250 steps (5 s)**. A car that touches
    a barrier nose-first effectively stops
  - **That measurement substantially defuses the grinding risk this feature was most worried about
    (R5, FR-010).** At 0.47 m per 5 s the progress term pays about 0.028 for grinding, against about
    0.12 per step for driving. Grinding is not a competitive strategy because the vehicle physics
    will not let the car slide along a barrier at speed. The risk is smaller than the spec feared,
    and it is measured rather than argued
  - **`LateralClearance` is unvalidated as a grind detector and must not be relied on yet.** It read
    exactly 1.0 through both runs, including five seconds pressed against a barrier. The reason is
    that both contacts were nose-in, so the barrier was ahead of the car rather than beside it, and
    the side rays correctly saw nothing. **A true parallel slide was never produced**, so the
    measure is neither confirmed nor refuted. T014 keeps it, and T019 must treat a flat clearance
    reading as uninformative rather than as evidence of no grinding, until a parallel case exists
- [X] T004a **Restore the hard step limit before the terminal is lifted (FR-005b).** `DESIGN.md`
      4.6 claimed `MaxStep = 6000` and `TrainingArea.prefab` sets **0**, guarded by `MaxStep > 0`,
      so it has never fired and `episode/end_steplimit` reads zero in every M3 run for that reason
      rather than because episodes were short. With the terminal lifted and `_stepsSinceAward`
      resetting on every marker, a grinding policy that collects one marker per 60 s never
      terminates. Choose the value against measured episode lengths, set it on the prefab, and
      record it in `DESIGN.md` 4.6
  - **`TrainingArea.prefab` now sets `MaxStep: 6000`**, which is 120 s at 50 Hz and is the number
    `DESIGN.md` claimed all along. Feature 007's mean episode was about 1,676 physics steps, so the
    limit sits about three and a half times above it and should rarely fire. Recorded in
    `DESIGN.md` 4.6
- [X] T005 Decide the budget default from T004's numbers and write it into `DESIGN.md` 4.6,
      replacing the placeholder T001 left. If T004 says the car cannot recover, **stop and write the
      negative up instead of continuing**: that is a publishable result about the vehicle rather
      than about the reward
  - **Budget default 3.** Recovery takes about 3 s of reverse, so a handful of contacts per episode
    is survivable without an episode becoming unbounded, and the `MaxStep` limit from T004a is the
    backstop. Zero remains reachable and reproduces feature 007 exactly
  - T004 said the car recovers, so the cancel branch of this task does not fire

**Checkpoint**: either the premise holds and the budget has a number, or the feature stops here with
a reason.

---

## Phase 3: User Story 1 - The car survives a graze (P1)

- [X] T006 [US1] Add `wallContactBudget` to `DrivingAgent` as a serialized `int`, defaulting to
      T005's number, with the comment saying what zero means and why the field counts events rather
      than steps (R2)
- [X] T007 [US1] Change the branch in `CheckTermination`: charge the penalty as it does today, then
      end the episode with `EndReason.WallContact` only when `wall.Contacts` exceeds the budget.
      **The end-reason vocabulary does not change** (FR-004)
- [X] T008 [P] [US1] **The property test.** A contact under budget charges the pinned penalty and
      leaves the episode live
- [X] T009 [P] [US1] **The property test.** The contact that exhausts the budget ends the episode
      with `EndReason.WallContact`, so no downstream reader sees a new reason
- [X] T010 [P] [US1] **The property test.** A budget of zero reproduces feature 007 exactly: the
      first contact ends the episode. This is the test that keeps the comparison honest
- [X] T011 [P] [US1] Test that the penalty is charged once per contact event and not once per
      physics step. It already holds because `OnCollisionEnter` is edge triggered; the test exists
      so a later change to `WallSensor` cannot break it silently (FR-001)
- [X] T012 [US1] Confirm the EditMode suite is green and report the new count against T003's 132
  - **137 passed, 0 failed, 0 skipped, in 2.49 s**, against T003's baseline of 132. The five new
    cases are the whole difference
  - **The predicate lives in a new plain static class, `WallTerminal`, rather than on
    `DrivingAgent`.** The first attempt put it on the agent and the test assembly would not compile:
    `DrivingAgent` derives from ML-Agents' `Agent`, and `SelfDrivingSim.EditModeTests` deliberately
    does not reference ML-Agents. The same reasoning already put the reward arithmetic in
    `RewardModel`, so this follows the existing pattern rather than inventing one, and it needed no
    change to the test assembly's references
  - **These tests pin semantics, not wiring**, and the file says so. Whether `CheckTermination`
    calls the predicate on the right contact with the right count needs a scene, and is verified by
    the end-reason counts the candidate run produces
  - The case that matters most is `A_budget_of_zero_ends_the_episode_on_the_first_contact`. The
    whole comparison against `ppo_car_007_progress` rests on zero reproducing feature 007 exactly

**Checkpoint**: an episode can outlive a contact, and zero still reproduces feature 007.

---

## Phase 4: The two measures (blocking the candidate run)

**These land before T017, not after.** The reason is written into the orderings above.

- [X] T013 Add `WallContactsPerEpisode` to the episode report as `episode/wall_contacts`, taken from
      `WallSensor.Contacts` at episode end, reset on episode begin
- [X] T014 Add `LateralClearance` as `episode/lateral_clearance`: the mean over the episode of the
      minimum normalised ray distance in the side of the fan, from `CarAgent.RayDistancesNorm`,
      accumulated on the same ticks the per-step reward terms are charged. **No change to
      `WallSensor`** (R5)
  - Both accumulate on the same tick the per-step reward terms are charged, so the means are over
    the steps the episode was actually charged for rather than over rendered frames
  - Only rays at 45 degrees or more off the nose count toward clearance. A forward ray sees the
    barrier the car is driving at, which is a different question from how close it is running to
    the wall beside it
  - **The clearance measure carries its T004 caveat in the code comment**, not only in the task
    list: both recovery probes produced nose-in contacts where the barrier is ahead rather than
    beside, the measure read 1.0 throughout, and that is the correct reading for those cases. A flat
    reading is uninformative rather than evidence of no grinding until a parallel slide exists
- [X] T015 [P] Extend `python/rl/export_curves.py` with `wall_contacts` and `lateral_clearance`, and
      `python/tests/test_rl_curves.py` to cover them
  - Three cases, 25 in the file. One of them pins that **a clearance of zero survives the
    empty-not-zero rule**: zero clearance is a car flush against a barrier, which is exactly the
    reading the grinding check looks for, and erasing it as absent would hide the thing being
    hunted
- [X] T016 [P] Extend `python/rl/report.py` and `python/tests/test_rl_report.py` so the held-out
      column carries both, beside the markers column feature 007 added
  - `wall_contacts_mean` on `DriverColumn`, printed beside markers and end reasons. Two cases, 14
    in the file, including one asserting that two drivers with **identical markers and identical
    zero laps** are told apart by their contact counts. That reading is the reason this feature
    added the column at all

**Checkpoint**: the run can be read when it finishes.

---

## Phase 5: User Story 2 - The policy reaches more markers (P1)

- [X] T017 [US2] The candidate run: `config/ppo_car.yaml` unchanged at 5,000,000 steps,
      `--seed=42`, one change from `ppo_car_007_progress`, which is the terminal. Row in
      `results/EXPERIMENTS.md` in the same session. **Launch the trainer detached** (quickstart)
  - **`ppo_car_008_budget`, 5,000,000 steps in 5,534.6 s, 903 steps/s, uninterrupted.** Budget 3,
    `MaxStep` 6000, seed 42, `config/ppo_car.yaml` unchanged. Prefab values were verified before
    launch rather than assumed: a newly added serialized field could have deserialized to 0 on the
    existing prefab and silently reproduced feature 007 for an hour and a half
- [X] T018 [US2] Read markers per episode against **1.4987** and the **0.035** gate, and name the
      gate's caveat in the same sentence. A result landing near the gate earns a fresh three-run
      spread rather than a verdict
  - **Markers per episode 0.5297 against 1.4987, a difference of -0.9689.** That clears the 0.035
    gate roughly 28 times over, **in the worse direction**. The gate's caveat, that a candidate
    which starts to learn may be noisier than the runs the gate came from, does not rescue this: the
    caveat softens a failure to clear, and this cleared
  - Still monotonic by quarter, 0.3832, 0.4376, 0.5630, 0.7351, so the policy is learning something,
    just far more slowly than the baseline's 0.3477 to 2.5528. Nothing near the gate, so no fresh
    three-run spread is owed
- [X] T019 [US2] Read wall contacts per episode and lateral clearance together. **If clearance falls
      sharply while contacts stay flat, the policy is grinding** and that is the finding, whatever
      the marker number says (R8, FR-010)
  - **Contacts per episode 1.218 against a budget of 3.** The typical episode never came close to
    spending the budget. The change did not fail because the budget was too small; it failed because
    the policy stopped putting itself in a position to use it
  - **Lateral clearance 0.6331, flat across quarters at 0.6367, 0.6454, 0.6218, 0.6284, minimum
    0.3231. No grinding.** A policy riding a barrier would hold this near zero
  - **The grinding risk is closed with a number.** It agrees with what T004 measured directly, that
    a car pressed against a barrier moves 0.47 m in 5 s, so grinding is not competitive because the
    vehicle cannot slide along a wall at speed. **The clearance measure still has not been validated
    against a real parallel slide**, so this is consistent evidence rather than proof; but with
    contacts low, stalls high and clearance flat, there is no grinding signature to explain away
- [X] T020 [US2] Read the end-reason mix. A fall in the wall share that appears as a rise in the
      stall share is a traded failure and is reported as one
  - **The mix inverted, and this is the finding.** Wall contact 59.1 to **23.2** per cent, stalled
    27.4 to **53.8** per cent, step limit 0.0 to 6.9 per cent. **The policy went back to stalling**,
    which is the degenerate solution M3 identified at the start: driving less is a cheaper way to
    stop paying -5.0 than driving better
  - The first contact ending the episode had been suppressing that option, and lifting the terminal
    handed it back. **The terminal was load bearing**, in the opposite direction to the hypothesis
- [X] T021 [US2] Report throughput and mean episode length against 927 steps/s, since episodes are
      expected to lengthen (R6, SC-009)
  - Throughput **903 steps/s** against 927, so the run cost about the same wall clock
  - **Episodes ran 612.0 trainer steps against 485.4**, and 2,505.5 physics charges against 1,561.3,
    so only **8,843** episodes fitted into 5M steps against 13,851. Fewer, longer episodes is less
    diverse experience for the same budget, and is part of why this run learned less
  - **The step limit fired on 608 episodes, 6.9 per cent** (SC-009a satisfied, and not by a silent
    zero). Without T004a those episodes would have run unbounded: `_stepsSinceAward` resets on every
    marker, so a slow policy collecting one marker per 60 s never trips the stall rule either
  - **The physics-to-decision ratio is 4.0870, with a single summary at 5.0224, so the ceiling of 4
    is not a ceiling.** Feature 007 read 4 as confirmed from a maximum of 4.0063 and that reading was
    wrong. The episode-set account predicts 3.7993 here against a measured 4.0870, so it no longer
    explains all of it either. The step limit is a fourth end path and the likeliest suspect, stated
    as a hypothesis. Settling it needs the per-episode records feature 007 named as its own feature
- [X] T022 [US2] Write the inherited-defect note into the run's `EXPERIMENTS.md` row: feature 007's
      SC-007 accounting defect is not fixed here, behavioural counts are Unity-side and unaffected,
      and no claim rests on the reward decomposition

**Checkpoint**: the mechanism either worked or did not, against a gate that was fixed first.

---

## Phase 6: User Story 3 - A lap on held-out track (P1)

  - Written into the row: feature 007's SC-007 accounting defect is inherited and not fixed, the
    behavioural counts are Unity-side and unaffected, and no claim here rests on the reward
    decomposition. Cumulative reward is **especially** unreadable on this run, because a budget of 3
    lets one episode absorb four -5.0 penalties where only one could ever land before
- [ ] T023 [US3] Export and promote the model to `Assets/Models/`, confirming LFS routing with
      `git check-attr filter` before the blob lands
- [ ] T024 [US3] Evaluation sweep, ten held-out seeds, deterministic, no trainer. Confirm the
      `Couldn't connect to trainer` line, which is what makes the no-trainer claim checkable
- [ ] T025 [US3] Repeat in sampling inference. Reported separately, never averaged. **Do not quote
      feature 006's factor of 83**, which feature 007 showed was a ratio over a near-zero
      denominator; the honest figure on a driving policy was 2.86
- [ ] T026 [US3] Record lap completion per seed and the 80 per cent bar, met or not met with the
      number. State that `lapsToComplete` is 3, so a recorded lap is three laps
- [ ] T027 [US3] Regenerate `results/rl/rl_steering.md` with this feature's column beside the
      scripted driver's 34 of 34, feature 007's, and the human reference

**Checkpoint**: the milestone is answered with a number.

---

## Phase 7: Closeout

- [ ] T028 Write the closeout table into `spec.md`, every criterion with the number that decides it
- [ ] T029 [P] Update `DESIGN.md` 4.5 and 4.6 with the outcome in the house pattern: the decision,
      the reason, the measured number, and the milestone half stated in the same section so it
      cannot be read as a success on its own
- [ ] T030 [P] Update `README.md` only if a command, a scene or a file name changed. The plan
      expects none did, and confirming it is the task
- [ ] T031 Run `.venv`, `.venv-bc` and the Unity EditMode suite and compare against T003
- [ ] T032 Merge checklist: no em dashes in any file this feature touched
- [ ] T033 State the next feature. **If the terminal was not the constraint either**, then two
      one-change candidates have now been exonerated and the next question is whether the vehicle or
      the observation is what limits this policy, rather than the reward. Say so plainly

---

## Dependencies

```text
T001            ->  everything
T004            ->  T005  (and T005 may cancel the feature)
T004a           ->  T006  the episode must have an upper bound before the terminal is lifted
T005            ->  T006
T006, T007      ->  T008..T012
T008..T012      ->  T017
T013..T016      ->  T017          the measures land before the run, not after
T017            ->  T018..T023
T023..T026      ->  T027
everything      ->  T028..T033
```

## Parallel opportunities

- T002 and T003 are independent.
- T008 to T011 are four independent EditMode cases.
- T015 and T016 touch different Python modules.
- **T017 is one 5,000,000 step run of about 1.5 hours and the machine must be left alone for it.**
  Feature 007 lost a run to a background task being stopped; launch detached.

## Notes carried from feature 007 that apply unchanged

- Launch training through `Start-Process`, never as a child of a shell task.
- The real editor log is `unity/SelfDrivingSim/Logs/Editor.log`.
- Unity stalls on a pending asset refresh while unfocused; `AppActivate` on the editor PID clears it.
- `AssetDatabase.Refresh()` and `EnterPlaymode()` in one command deadlock. Split them.
- Watch for `Step: 5000000`, not "Exported", which matches every checkpoint export.
