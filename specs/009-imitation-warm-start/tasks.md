# Tasks: The imitation warm start

**Feature**: `009-imitation-warm-start` | **Spec**: `spec.md` | **Plan**: `plan.md`
**Created**: 2026-08-28

## Format: `[ID] [P?] [Story] Description`

`[P]` marks tasks that touch no shared file and may be done in any order relative to each other.
`[US1]` and so on name the user story a task serves.

## Six orderings this feature must not violate

1. **`DESIGN.md` before code.** Principle V. The warm start is a trainer input the design does not
   describe, and the substitution of `HeuristicDriver` for the M4 BC policy is a correction to a
   sentence `DESIGN.md` 4.5 already contains.
2. **The delegation and its EditMode properties before the cadence gate.** The gate measures the
   expert through the agent's action path, so that path has to exist and be tested first.
3. **The cadence gate before any bulk recording.** FR-004. A demonstration set of a driver that
   stopped finishing laps is worth nothing, and recording 34 seeds to find that out is the expensive
   way to learn it.
4. **The BC hyperparameters written into `EXPERIMENTS.md` before the run starts**, not after. The
   spec's edge case is explicit: a value chosen after seeing the result is a tuned result.
5. **The recording scene before the cadence gate.** Research R10: no object carries both the agent
   and the scripted driver, so T023 to T023b build the scene the gate is measured in.
6. **The `.demo` committed before the run.** Reproducibility, Principle VI. A run whose input is an
   uncommitted binary is a run nobody can repeat.

---

## Phase 1: Setup

- [X] T001 Rewrite `DESIGN.md` 4.5 and 5 in a `docs:` commit before any code exists. Three things:
      the warm start is an **auxiliary loss on the policy, not a reward signal**, so the reward
      table is unchanged; the demonstration source is `HeuristicDriver` and **not** the M4 BC
      policy, with the reason stated plainly (camera images against a 19 value vector, no shared
      observation space); and the M3 remedy list gains the note that the third remedy as originally
      written is unavailable
  - Written into `DESIGN.md` 4.5, immediately after the feature 008 closeout paragraph and before
    `### 4.6`. Six paragraphs: the third remedy as written does not exist and why (camera images
    against a 19 value vector, no shared dimension), `HeuristicDriver` as the substitute with its
    34 of 34, the warm start as an auxiliary loss rather than a reward signal so the table above is
    untouched and GAIL is out of scope, the two measured constraints the demonstrations carry
    (12.5 Hz sampling and the `(obs_t, a_{t-1})` pairing), and the M3 scope cap of 2026-08-28
- [X] T002 [P] Record in `DESIGN.md` 5 that `DrivingAgent.Heuristic` now delegates to the scripted
      driver, and that this does **not** create a second implementation of the baseline, so the M5
      comparison still has one answer
  - Written into `DESIGN.md` 5, after the deterministic-inference paragraph and before `### 5.1`.
    Five paragraphs: `behavioral_cloning` as a trainer input with its four explicit values, why
    `steps: 500000` is what makes it a warm start rather than an imitation run, why
    `samples_per_update` is set at all, `Losses/Pretraining Loss` as the cheap check that the warm
    start is applied, the delegation and why it does not create a second baseline, and the
    training-seeds-only rule for the demonstration set
  - **72 lines added to `DESIGN.md` in total across T001 and T002**, no line removed, no em dash
- [X] T003 [P] Record the pre-feature baselines in this file, quoted rather than recomputed: markers
      per episode **1.4987**, wall share **59.1 per cent**, stalled share **27.4 per cent**,
      held-out **6.20 of 24** markers and **0 of 10** laps, throughput **903** and **927** steps/s,
      gate **0.035** from `results/rl/progress_spread.md`, demonstration source **34 of 34** at
      50 Hz from `results/heuristic/`
  - Recorded. All RL figures from `ppo_car_007_progress` unless the row says otherwise:

    | quantity | value | source |
    |---|---|---|
    | markers per episode, run mean | **1.4987** | curve, 500 summaries |
    | markers per episode, last 50 | 2.6975 | curve |
    | wall share | **59.1 per cent** | end-reason counts, 13,851 episodes |
    | stalled share | **27.4 per cent** | same |
    | track-swapped share | 13.5 per cent | same |
    | episodes completing three laps | 8 | `episode/end_lapscompleted` |
    | held-out markers, deterministic | **6.20 of 24** | `eval_ppo_car_007_progress_deterministic.csv` |
    | held-out markers, sampling | 4.60 of 24 | same run, sampling |
    | held-out laps | **0 of 10**, both modes | same |
    | throughput, feature 007 | **927 steps/s**, 5M in 5,395.4 s | run log |
    | throughput, feature 008 | **903 steps/s**, 5M in 5,534.6 s | run log |
    | mean episode length | 485.4 decisions, 1,676 physics steps | curve |
    | gate on markers per episode | **0.035** | `results/rl/progress_spread.md` |
    | demonstration source, laps | **34 of 34** at 50 Hz | `results/heuristic/`, feature 005 |
    | demonstration source, steering variance | 0.04994 | `results/heuristic/us4_steering.md` |

  - **The demonstration source has no baseline at 12.5 Hz**, which is exactly what T019 to T021
    measure. Speed tracking has no baseline at any cadence, because T017 is what adds it
- [X] T004 [P] Confirm the EditMode suite and the two Python suites are green before anything
      changes, so a later regression is attributable. Record the counts here
  - Run 2026-08-29 from the repository root, each venv's own interpreter rather than an activated
    shell: `.venv\Scripts\python.exe -m pytest` gives **362 passed and 3 skipped** in 261s, and
    `.venv-bc\Scripts\python.exe -m pytest` gives **416 passed** in 234s. Both green
  - The three skips are the torch dependent modules skipping cleanly under `.venv`, which is the
    behaviour `ENVIRONMENT.md` describes. The counts themselves are **82 higher on either side**
    than the **280 and 334** that file quotes, because features 006 to 008 added tests and the
    line was not updated. The skip count is what carries the meaning here, not the totals
  - **The C# side of this baseline was taken late and the task should say so.** The Phase 2
    delegation was already written into `DrivingAgent.cs` and `HeuristicDriver.cs` when this ran,
    so the EditMode count recorded against T015 is a post change count with no pre change
    counterpart. The two Python suites are unaffected either way, since no test in `python/tests`
    reads the Unity assembly. A later EditMode regression is attributable to the feature as a
    whole rather than to a single task inside it
- [X] T005 [P] Add `*.demo filter=lfs diff=lfs merge=lfs -text` to `.gitattributes` under the
      existing LFS block, and confirm `git lfs install` has been run in this clone
  - Added after the `*.h5` row with a four line comment saying why the file is committed rather
    than regenerated. `git lfs version` reports **git-lfs/3.6.0** and `filter.lfs.clean` is set in
    this clone, so the filter is live and a `.demo` will not enter history as a raw blob
  - The warning already in that block is the reason this is done before recording rather than
    after: `docs/images/human-driving.gif` was committed before its rule existed and is still a raw
    blob in history, and a rule added afterwards does not pull it back out

**Checkpoint**: the design is written, the baselines are recorded, and the repository can hold a
`.demo` honestly.

---

## Phase 2: The delegation (US1)

**The mechanism. Nothing else in this feature is measurable without it.**

- [X] T006 [US1] Widen `HeuristicDriver.Decide()` from `private` to `public` in
      `Assets/Scripts/Agent/HeuristicDriver.cs`, and extend its XML comment to name the second
      caller. **No change to the control law**, not one constant
  - `HeuristicDriver.cs:818`, `private Vector2 Decide()` is now `public`. The XML summary gained
    two paragraphs: why it is public (the agent's callback calls it, so the control law stays in
    one place) and that **the caller's clock is not this component's clock**, with R4's warning
    that `Delayed` mode quadruples its own reaction time when called once per decision
  - Control law byte-identical. The diff on this file is the visibility keyword and comment lines
- [X] T007 [US1] Rewrite `DrivingAgent.Heuristic` in `Assets/Scripts/Agent/DrivingAgent.cs` to fill
      the continuous buffer from `HeuristicDriver.Decide()` instead of zeroing it. Clamp to
      `[-1, 1]` on the way out, matching what `OnActionReceived` already does to a policy's output
  - `DrivingAgent.cs:857`. Fills index 0 from `move.x` and index 1 from `move.y`, both through
    `Mathf.Clamp(-1, 1)`, and zeroes any index beyond the two the action space declares
- [X] T008 [US1] Rewrite the XML comment above `Heuristic` so it says what is now true. The old
      comment refuses to **duplicate** the scripted driver; the new one says the callback
      **delegates** to it, and that this is what keeps one implementation of the baseline in the
      project. Do not delete the reasoning, update it
  - Rewritten, not deleted. The new comment keeps the old objection and says how it is satisfied:
    the callback **delegates** rather than duplicates, so the baseline still has one
    implementation and the M5 comparison still has one answer
- [X] T009 [US1] Handle the null case explicitly: if no `HeuristicDriver` is present on the object,
      emit zeros. Heuristic mode has to stay safe on a prefab that has no scripted driver on it,
      which is every training scene and the evaluation scene
  - **The "log once" in this task's first wording was dropped deliberately.** After R10 the null
    case is the *normal* case: only `Demonstration.unity` carries a scripted driver, so a warning
    would fire in every scene where nothing is wrong. Zeros without a log is what heuristic mode
    has always meant outside the demonstration scene, and the XML comment says so
- [X] T010 [US1] Enforce FR-002 at the seam. While `DrivingAgent` is the decision source, call
      `HeuristicDriver.SetEngaged(false)` so its `FixedUpdate` releases `ScriptedMove` rather than
      writing it (research R6). Exactly one writer per frame, which is feature 005's FR-004 and not
      a new rule
  - **Done differently from how this task was written, and the difference matters.**
    `SetEngaged(false)` alone is not enough: `HeuristicDriver.FixedUpdate` keeps running while
    disengaged and **actively clears** `CarController.ScriptedMove` so a released wheel does not
    hold a stale input (`HeuristicDriver.cs:620-627`). That is correct when a human takes over and
    wrong here, because the frame order between two components' `FixedUpdate` is undefined, so a
    merely disengaged driver can null the command the agent wrote in the same physics step
  - `DrivingAgent.ResolveScriptedExpert()`, called from `Awake`, does both: `SetEngaged(false)` and
    then `enabled = false`. Disabling stops the loop outright, and `Decide()` stays callable
    because it is a pure function of the rays and the speed rather than of the run bookkeeping
    (R1). `Awake` still runs on a disabled component, so its reference resolution is unaffected;
    `Start` does not, which skips `BeginRun` and `AdoptCompareRate`, neither of which `Decide()`
    reads
- [X] T011 to T014 [US1] The EditMode properties, **and the constraint that reshaped all four of
      them**
  - **Two of the four cannot be written in this assembly, and that is feature 008's finding not a
    new one.** `SelfDrivingSim.EditModeTests.asmdef` references `SelfDrivingSim`,
    `UnityEngine.TestRunner` and `UnityEditor.TestRunner` and **deliberately not ML-Agents**.
    `DrivingAgent` derives from ML-Agents' `Agent` and `ActionBuffers` is an ML-Agents type, so a
    test cannot name either. Feature 008's T012 hit exactly this and answered it by putting the
    predicate in a plain static class; `RewardModel` is the same pattern, older
  - **Answered the same way rather than by adding a reference.** New
    `Assets/Scripts/Agent/HeuristicCommand.cs` holds the two pure parts: `Clamp(Vector2)`, the
    range the recorded command is allowed to carry, and `ScriptedDriverMayWrite(agentPresent,
    driverEnabled)`, FR-002 as a predicate. `DrivingAgent.Heuristic` calls `Clamp` rather than
    clamping inline, so the tested code is the running code
  - **Five cases in `Assets/Tests/EditMode/HeuristicCommandTests.cs`**: a command inside the space
    passes through, a command outside it is clamped, clamping one component leaves the other alone,
    the scripted driver may write when no agent is present, and it may not while the agent is the
    decision source
  - **What is left to a scene, stated rather than skipped.** That `Heuristic` actually calls
    `Decide()`, and that exactly one component reaches `ScriptedMove` in a physics step, need a car
    and a physics step. T018 is the check: drive one training seed and watch the car follow the
    track rather than sit still. The test file says this in its own header, as
    `WallTerminalTests` does
  - The clamp case is the one that matters most. The trainer validates a demonstration's **shape**
    against the policy's action spec and not its **range** (R7), so an out-of-range command would
    be recorded without complaint and would teach the policy an action it can never take
- [X] T015 [US1] Run the EditMode suite and record the new count against T004's. **Human step**:
      `TestRunnerApi` trips the MCP user-interaction guard, so this is Window > General > Test
      Runner > EditMode > Run All, as feature 008's T031 also recorded
  - **The project compiles clean**, verified rather than assumed: `Assets/Refresh` rebuilt
    `SelfDrivingSim.dll` and `SelfDrivingSim.EditModeTests.dll` with `Tundra build success` and the
    console holds zero errors and zero warnings. The test assembly building at all is the proof
    that `HeuristicCommandTests` compiles against `HeuristicCommand`
  - Expected count: **142**, being feature 008's 137 plus the five new cases
  - **Run by the owner 2026-08-29 after the sensing fix, reported as all passing.** The exact
    count was not captured, so this records a pass rather than a number. It is a weaker record
    than T004's and is left weaker rather than written up as if the figure were read
  - Run **after** `CarAgent.IsSelf` changed, which is the ordering that matters here: the suite
    covers the delegation and the sensing, and both had moved since the last green run

**Checkpoint**: the scripted driver can drive through the agent, and three assertions say so without
a scene.

---

## Phase 3: The cadence gate that can cancel the feature (US2)

**This phase exists to be allowed to fail.** The 34 of 34 figure was measured at the heuristic's own
50 Hz.

**T023 to T023b come first in practice**, because R10 means there is no scene to run this phase in
until they exist. They are numbered in Phase 4 because they belong to the demonstration set; the
dependency notes carry the real order. The agent decides at 12.5 Hz and the recorder cannot record faster (research R2). If the
expert stops finishing laps at that clock, **the feature stops and reports it**. FR-006 pins
`DecisionPeriod`, so lowering it is not the response.

- [X] T016 [US2] Set `BehaviorParameters.BehaviorType` to **Heuristic Only** in the recording scene
      and confirm `HeuristicDriver.Mode` is **Immediate**. Research R4: `Delayed` advances its delay
      ring once per call, so on the agent's clock the same `reactionTimeS` becomes four times
      longer, and the demonstration would be of a slower driver than the one that produced 34 of 34
  - `m_BehaviorType: 1`. **Read the enum before writing the value**: `BehaviorType` is
    `Default = 0, HeuristicOnly = 1, InferenceOnly = 2`, and a first write of 2 would have left the
    scene inferring from a network while the file still said the task was done
  - `HeuristicDriver.reactionMode` is 0, `Immediate`, as this task requires
  - **The inherited `m_Model` override was removed.** The copy carried
    `Models/ppo_car_007_progress-5000081.onnx` over from `Evaluation.unity`. `HeuristicOnly`
    ignores it, so it changed no behaviour, but a recording scene that holds a trained policy
    invites exactly the misreading this feature cannot afford: that the `.demo` came from a
    network. The override is gone and the field now inherits the prefab's `{fileID: 0}`
  - The scene reload after that edit confirmed `Model: null`, `BehaviorType: 1`,
    `VectorObservationSize: 19`, `NumContinuousActions: 2`, `BehaviorName: CarDriver`
- [X] T017 [US2] Add speed tracking to the run record: mean absolute error between `car.SpeedMs` and
      `HeuristicDriver.TargetSpeedMs` over a run. Research R3 is why this is measured before the
      sweep rather than reconstructed after it, and feature 008's T040 is the precedent for adding a
      counter before the run that needs it rather than after
  - **Recorded as a per-step column, not as a run-record field**, decided with the owner. The
    statistic lives in Python, which is where every other statistic in this project lives, and
    `RunRecord`'s schema, written by features 005 to 008 and read by `python/heuristic/report.py`,
    is untouched
  - `Assets/Scripts/Logging/DriveLogger.cs` gains `target_speed` between `yaw_deg` and `source`,
    read from an optional `HeuristicDriver` on the same object. `compare_drive` parses these
    traces with `pd.read_csv`, which is keyed by header name, so the added column moves nothing
  - **Empty, not zero, when no scripted driver is present**, which is every scene but the
    demonstration scene. Zero would claim the driver asked for a standstill, and a mean absolute
    error over those rows would be the car's own speed reported as a tracking error
  - `python/heuristic/speed_tracking.py` computes the mean absolute error, the worst single step,
    and the **coverage**, the fraction of rows that carried a target. Coverage is what tells a
    later reader whether a mean covers a run or a corner of one
  - `python/tests/test_speed_tracking.py`, **7 tests, all passing**. Two of them exist because
    they disagree: the empty target is skipped, and a literal `0.0` target is a real request for a
    standstill. A reader that fixed one by treating every zero as missing would break the other
  - Unity recompiled clean: `SelfDrivingSim.dll` rebuilt, console holds zero errors and zero
    warnings
- [X] T018 [US2] Drive **one** training seed through the agent's action path and confirm the car
      follows the track rather than sitting still. One seed, by eye, before 34 seeds by script
  - **This task found a sensing fault that predates the feature and invalidates the premise of
    the phase.** The car did not sit still: it drove straight into a barrier at full throttle,
    twice, and the trace explained why. `steering` was exactly `0.00000` on every row and
    `target_speed` was pinned at `10.0`, the vehicle maximum
  - Read live in play mode, `CarAgent.RayDistancesNorm` was **1.0 in all thirteen directions**
    while `Physics.OverlapSphere` at the same moment returned both barrier `MeshCollider`s
    within 25 m. The car was on `Surface`, at its marker, with walls either side, reporting a
    clear road
  - **Cause: `CarAgent.IsSelf` compared transform roots** (`CarAgent.cs:641`,
    `collider.transform.root == transform.root`). `TrainingArea.prefab` makes `Car` and `Track`
    siblings under one area root, so the car's own barriers, surface and checkpoints all shared
    its root and every hit on them was discarded at `CarAgent.cs:609` as the car sensing itself
  - An all-clear fan is a **symmetric** fan, so `RayControllers.WeightedAverage` returns exactly
    zero and `SightLimitedSpeed` returns `vMaxMs`. The scripted driver was never faulty. It was
    computing the correct command for an observation that said the road was empty
  - **Fix**: `collider.transform.IsChildOf(transform)`. The `attachedRigidbody` test above it
    already catches every collider on the car, and the doc comment says the second test exists
    to catch a child collider left without a rigidbody, so scoping it to the car's own subtree
    keeps that intent and drops the collateral. No test pinned the old behaviour
  - After the fix, same scene, same seed: **12 of 13 rays hit**, 2.77 m to 12.96 m, one clear at
    20 m down the road, `SteerNorm -0.452`, `YawRateNorm -0.316`. The trace's `steering` and
    `target_speed` columns both vary, the latter between 5.5 and 10 m/s, which is the corner
    limit and the sight limit doing the work they were written to do
  - **This reaches past feature 009 and the owner has been told.** `Evaluation.unity` produced
    the held-out figures for features 006, 007 and 008 and has the same prefab layout, so those
    runs were measured through the same filter. Whether M3's three failures have a sensing cause
    rather than a reward cause is not decided here and is not this feature's to decide
- [X] T019 [US2] Run all 34 training seeds from `results/tracks/seed_split.json` through the agent's
      action path. Record per seed: lap completion, markers, wall contacts, end reason, and the
      speed tracking error from T017
- [X] T020 [US2] Write the result to `results/rl/demo_cadence.md` as a table against feature 005's
      own figures, with the reaction mode stated, because no committed CSV records it (R4)
- [X] T021 [US2] **The gate.** Read lap completion at 12.5 Hz against **34 of 34** at 50 Hz. If it
      holds, continue to Phase 4. If it collapses, read the speed tracking error first, because R3
      predicts the throttle as the cause: bang-bang against a `0.25 m/s` deadband, and one decision
      is long enough for the speed to move `0.47 m/s`. **Report the number and stop the feature
      either way; do not change `DecisionPeriod`**
- [X] T022 [P] [US2] Record the gate's outcome in `results/EXPERIMENTS.md` whichever way it goes. A
      cadence that costs the expert its laps is a finding about this project's decision period and
      belongs in the log next to the runs
  - **The gate passes. 34 of 34, zero wall contacts, at 12.5 Hz**, against feature 005's 34 of 34
    at 50 Hz. `DecisionPeriod` was not touched
  - Per-lap time 26.266 s mean against 26.496 s. The scene inherited `lapsToComplete: 3`, so the
    run record's `lap_time_s` is a three-lap total and the per-lap figure divides by three, which
    is mildly favourable because only the first lap starts from rest. Recorded as not slower
    rather than as faster
  - `|dsteer|` P95 0.0564 against 0.0496, marginally over the 0.0063 noise threshold. Sign
    changes 0.2550 against 0.2370, **under** the 0.0366/s threshold, so not a difference
  - **R3's prediction was right and cost nothing.** Speed tracking error is 0.3089 m/s mean over
    the 34 traces, sd 0.0149, range 0.2705 to 0.3400, against the throttle's 0.25 m/s deadband.
    Every seed tracks its target worse than the deadband and every seed still finished
  - Written to `results/rl/demo_cadence.md` with the per-seed table, and to
    `results/EXPERIMENTS.md` with the sensing fault that the first attempt at this sweep found

**Checkpoint**: the demonstration source is measured at the clock it will be recorded at, and the
feature has either earned Phase 4 or ended with a number.

---

## Phase 4: The demonstration set (US2)

- [X] T023 [US2] **Build `Assets/Scenes/Demonstration.unity`, a single-area recording scene.**
      Research R10: no object in this project carries both `DrivingAgent` and `HeuristicDriver`,
      and the twelve-area training scene is the wrong place to put one, because
      `HeuristicDriver.Awake` resolves `ring`, `placer` and `track` with `FindAnyObjectByType` and
      eleven of twelve drivers would bind to another area's track. One `TrainingArea` instance
  - **Built by copying `Scenes/Evaluation.unity` rather than by assembling a scene from parts.**
    That scene is already the single-area arrangement this task describes: one `TrainingArea`
    prefab instance, a `SweepRunner` whose `driver` is the `DrivingAgent`, a `DriveLogger` on the
    `Car`, a camera and a light. Copying inherits the wiring that produced every held-out figure
    in features 006 to 008 instead of re-deriving it, and it makes the diff against `Evaluation`
    the description of what a demonstration run changes
  - Two values retargeted in the copy: `SweepRunner.seedSet` from **1 (Eval) to 0 (Train)**, which
    is FR-003 enforced in the scene rather than remembered at record time, and
    `DriveLogger.sourceLabel` from `ppo_car_spread_a_sampling` to `heuristic_train34`
  - `Evaluation.unity` itself is untouched, confirmed by `git status` showing only the new
    `Demonstration.unity` as untracked
- [X] T023a [US2] Add `HeuristicDriver` to the `Car` object in that scene, beside `CarController`,
      `CarAgent` and `DrivingAgent`, which R10 confirmed are all on the same GameObject. **Wire
      `ring`, `placer` and `track` explicitly in the inspector** rather than leaving them to
      `FindAnyObjectByType`, so the binding is visible in the scene file rather than decided at
      runtime. `engaged` stays false, which is already the field's default
  - Component added through the editor. `strategy` is **1, `WeightedAverage`**, which is the
    control law R3 analysed for the cadence gate rather than the enum's `MostOpen` default;
    `engaged` is 0 and `reactionMode` is 0 (`Immediate`), which is what T016 requires
  - **The five object references were wired by editing the scene YAML, not through the editor
    tooling.** `Unity_ManageGameObject.set_component_property` refused all five with `Property
    'agent' not found. Did you mean: agent?`, listing the field it claimed not to find, and it
    refused them identically with `include_non_public_serialized` set. Its scalar writes in the
    same call succeeded. So the failure is in its object-reference resolver and not in the field
    names, and three attempts was the point to stop retrying it
  - `Evaluation.unity` carried no stripped reference to the prefab's `CheckpointRing`, because
    nothing in that scene referenced the ring directly. One was added, pointing at prefab fileID
    `1942290961503588355`, so `ring` names the ring of this area rather than whichever one
    `FindAnyObjectByType` would have returned
- [X] T023b [US2] Add `DemonstrationRecorder` to the agent **in that scene only**.
      `DemonstrationDirectory` is `Assets/Demonstrations`, `DemonstrationName` is
      `heuristic_train34`, `Record` left false in the committed scene
  - Verified in the saved file: `Record: 0`, `NumStepsToRecord: 0`,
    `DemonstrationName: heuristic_train34`, `DemonstrationDirectory: Assets/Demonstrations`
- [X] T023c [P] [US2] Confirm `TrainingArea.prefab`, `Scenes/Training.unity` and
      `Scenes/Evaluation.unity` are **untouched** in `git status`. This is the guarantee that an
      unedited training path still trains exactly as feature 008 left it, and after R10 it holds by
      construction rather than by a default value
  - `git status` under `Assets/` lists only the new `Demonstration.unity` and its meta, plus the
    Phase 2 source files. `TrainingArea.prefab`, `Scenes/Training.unity` and
    `Scenes/Evaluation.unity` do not appear, so the training path is untouched
- [X] T024 [US2] Record the 34 training seeds with `Record` ticked. **Training seeds only.** The ten
      evaluation seeds are the criterion this project has failed three times, and demonstrating on
      them would answer a different question
  - Recorded 2026-08-29 at `timeScale 4`, 34 of 34 `LapsCompleted`, zero wall contacts
  - **The first attempt was discarded and the reason belongs in this task.** `NumStepsToRecord`
    was left at 0, which means record for as long as the scene runs, and `SweepRunner` finishing
    does **not** stop `DrivingAgent` starting new episodes. The recorder ran about four hours past
    the sweep and produced a 26.9 MB file dominated by the last seed. Deleted rather than trimmed,
    because a `.demo` is a protobuf stream and a partial delete would not be auditable
  - Re-recorded with `NumStepsToRecord: 34000`, sized from the 1x sweep's 2679 simulated seconds
    at 12.5 Hz. The 34 runs account for about 33,509 steps, so about **491 steps, 1.5 per cent**,
    are the expert continuing on the final seed. Declared rather than hidden; the alternative cap
    would have truncated a real run
  - **The recorded 1x sweep also settled a caveat I had left open.** `DESIGN.md` 4.7.2 says 2x is
    the fastest scale at which feature 005's numbers reproduce, and the gate was measured at 4x.
    The 1x recording run reproduces it: per-lap 26.266 s at both scales, 34 of 34 and zero walls at
    both, `|dsteer|` P95 0.0568 against 0.0564. 4x did not distort this measurement
  - **The file name is not the field.** `DemonstrationName` is `heuristic_train34`; ML-Agents wrote
    `heuristictrain34.demo`. `demo_path` must use the written name
- [X] T025 [US2] Untick `Record`, then open the `.demo` in the editor and confirm the importer
      reports a non-zero episode count and step count. This is US1's fourth acceptance criterion
- [X] T026 [P] [US2] Write `results/rl/demo_seeds.json` with the seed list, and assert in a Python
      test that it is a subset of `train.accepted_seeds` in `results/tracks/seed_split.json` and
      disjoint from `eval.accepted_seeds`. FR-003 as a test rather than as a promise
- [X] T027 [P] [US2] Record the demonstration's episode count, step count and file size in
      `results/EXPERIMENTS.md`, and state the sample rate as **12.5 Hz** with the reason (R2)
- [X] T028 [US2] Commit the `.demo` through LFS and confirm with `git lfs ls-files` that it went
      through the filter rather than in as a blob
- [X] T029 [P] [US2] Record in `data-model.md` and in the `EXPERIMENTS.md` row that the file pairs
      each observation with the **previous** decision's command, an 80 ms shift at
      `DecisionPeriod: 4` (research R5). It is a property of ML-Agents, it is not configurable
      without patching `Library/PackageCache`, and it is written down so nobody later reads the file
      as `(obs_t, a_t)`

**Checkpoint**: the demonstration exists, its provenance is auditable from committed files, and its
one known distortion is documented rather than discovered later.

---

## Phase 5: The candidate run (US3)

- [X] T030 [US3] Add the `behavioral_cloning` block to `config/ppo_car.yaml` under
      `behaviors.CarDriver`. `demo_path` to the committed file, `strength: 0.5`, `steps: 500000`,
      `samples_per_update: 2048`, `num_epoch` and `batch_size` left to inherit. **Nothing else in
      the file changes**, and the diff is the proof of that
  - Added 2026-08-30, after `reward_signals` and before `max_steps`. `git diff --stat` reports
    **47 insertions and 0 deletions**, which is the proof the task asked for rather than a claim
    that nothing moved
  - **Parsed rather than eyeballed.** `RunOptions.from_dict` on the committed file, with
    `register_trainer_plugins()` called first, returns `steps 500000`, `strength 0.5`,
    `samples_per_update 2048`, `num_epoch None`, `batch_size None`, and `demo_path` resolving to an
    existing file from the repository root. `max_steps` is still 5,000,000, `hyperparameters` are
    still 2048 and 3, and `extrinsic` is still `(0.99, 1.0)`
  - `num_epoch: None` and `batch_size: None` are the inheritance the task asked for and not
    omissions: `module.py:47-50` falls back to the trainer's own `batch_size` and `num_epoch`, so
    the BC update runs at 2048 and 3 epochs
- [X] T031 [US3] Comment the block in the file's own register, saying why each value is what it is.
      `steps: 500000` is what makes this a **warm start** rather than an imitation run: research R8
      found the schedule is `LINEAR` only above zero, so the default `steps: 0` would apply the loss
      at full strength for all 5,000,000 steps. `samples_per_update: 2048` bounds the per-update
      cost, which at the default 0 iterates the whole buffer
  - The comment also records **why `demo_path` reads `heuristictrain34` and not
    `heuristic_train34`**: `DemonstrationRecorder.cs:137` strips every character outside
    `[a-zA-Z0-9 -]` from `DemonstrationName`. It belongs in the config because a path that does not
    resolve fails silently, and the next reader should not have to rediscover it
  - The `samples_per_update` comment carries the arithmetic rather than the assertion: at about
    34,000 recorded steps and `n_sequences` 2048, `possible_batches` is 16, and the default 0 would
    run all 16 per epoch, three epochs deep, on every PPO update. At 2048, `max_batches` is 1
- [X] T032 [US3] Confirm FR-010 by reading the prefab rather than by assuming: `wallContactBudget`
      is **0** and `MaxStep` is **6000**, so the comparison is feature 007's terminal with feature
      008's step limit
  - `MaxStep: 6000` at `TrainingArea.prefab:408`, read directly. `DecisionPeriod: 4` and
    `TakeActionsBetweenDecisions: 1` at lines 428 and 430, unchanged, which is also the cadence the
    demonstration was recorded at
  - **`wallContactBudget` is not in the prefab at all**, and reading rather than assuming is what
    turned that up. The effective value is **0**, but it comes from the initialiser at
    `DrivingAgent.cs:101` and not from a serialized field. `git log -S` over `Assets/` finds one
    commit touching the name, `2008996`, and none touching the prefab, so the field has never been
    written into prefab YAML
  - **Consequence, and it is not cosmetic.** Feature 008 varied the budget in source rather than in
    the inspector, which is why `be2f9c4` could put it back to zero with a code change. The value is
    reproducible from a clean clone, but it is invisible to anyone who reads only the prefab. Named
    here so 009's closeout does not describe a scene value that does not exist
  - `grep -rn wallContactBudget unity/SelfDrivingSim/Assets/` returns those two source lines and
    nothing else: no scene, no prefab and no variant overrides it
- [X] T033 [US3] Write the `results/EXPERIMENTS.md` row **before launching**, naming the one change
      and the three chosen values. FR-008, and ordering rule 4: a hyperparameter written down after
      the result is a tuned hyperparameter
  - Written 2026-08-30 as "Pre-registered: the imitation warm start", and **committed before the
    trainer was launched** so the ordering is in the history rather than in a claim about it
  - Carries the three values in a table with a reason each, the unchanged hyperparameters read back
    through `RunOptions.from_dict`, the environment read off the prefab, and the five things that
    will be read fixed in advance
  - **One comparability limit is stated in the row before the numbers exist.** The reward table is
    untouched and the diff over `Assets/Scripts/` since `be2f9c4` contains no reward-bearing line,
    so cumulative reward is in the same units as 007 and 008. The agent is not the same agent:
    `3017764` fixed `CarAgent.IsSelf` and this policy can see its own barriers, which 007 and 008
    could not. `ppo_car_009_sighted_probe` is named as the like-for-like sighted baseline and
    1.4987 as the milestone figure, so the closeout cannot quietly pick whichever suits
- [X] T034 [US3] Launch `ppo_car_009_bc`, 5,000,000 steps, seed 42, detached as `quickstart.md`
      shows. Feature 007 lost a run at 1,440,000 steps to a stopped background task and that is why
      the launch is detached rather than convenient
  - Launched 2026-08-30 via `Start-Process` exactly as `quickstart.md` gives it, `--seed=42`,
    `--torch-device=cuda`, `--force`, logs to `results/rl/ppo_car_009_bc.log` and `.err.log`
  - **The editor had `Demonstration.unity` open, not `Training.unity`.** Caught before Play by
    asking the editor for its active scene rather than assuming the last session left it right.
    Recording scenes carry `BehaviorType` Heuristic Only and a `DemonstrationRecorder`, so pressing
    Play there would have connected nothing to the waiting trainer and, worse, could have started
    writing a second demonstration
  - `Training.unity` verified before Play: prefab `m_BehaviorType: 0` (Default), `m_Model:
    {fileID: 0}` (no model assigned), twelve areas, and no `DemonstrationRecorder` or behaviour-type
    override anywhere in the scene file
  - The trainer echoes the parsed `behavioral_cloning` block into its own log at startup, so the
    log itself records `demo_path`, `steps: 500000`, `strength: 0.5`, `samples_per_update: 2048`
    and `num_epoch/batch_size: None`. The run's configuration is auditable from the run's own
    artefacts and not only from the config file
- [X] T035 [US3] Within the first few summaries, confirm `Losses/Pretraining Loss` is present and
      non-zero in TensorBoard. **If it is absent, the demonstration never loaded and the run is
      measuring feature 007 again.** Kill it, fix the path, relaunch. One glance, and it saves two
      hours
  - **Passed.** `Losses/Pretraining Loss` is **1.250184 at step 30,000**, read out of the run's
    event file with `EventAccumulator` rather than off a TensorBoard screenshot. `Losses/Policy
    Loss` 0.020442 and `Losses/Value Loss` 0.094813 are alongside it
  - **The check is only valid after the first PPO update, and this task as written could have
    killed a healthy run.** At the step 10,000 summary the whole `Losses/` group was absent, not
    just the pretraining tag: `buffer_size` is 20480, so no update had happened and no loss of any
    kind had been written yet. Read at the first summary, "absent" means "too early"; read after
    20,480 steps it means what the task intends
  - The distinguishing test is therefore **`Losses/Pretraining Loss` absent while `Losses/Policy
    Loss` is present**. That is a missing demonstration. All three absent together is a run that
    has not updated yet. Recorded here because the next feature to reuse this check will meet the
    same trap
- [X] T036 [US3] Export the curve with `python -m python.rl.export_curves results/ppo_car_009_bc`
  - Wrote `results/rl/curves/ppo_car_009_bc.csv`, 500 summary rows, step 10,000 to 5,000,000
- [X] T037 [US3] Read **markers per episode** against **1.4987** and the **0.035** gate, with the
      gate's caveat named in the same breath rather than in a footnote
  - **2.6321 against 1.4987, a rise of 1.1334 against a gate of 0.035.** Cleared by about thirty
    times the gate's width, so the caveat's "near the gate earns a spread rather than a verdict"
    branch does not apply and no three-run spread is owed
  - Last ten summaries 3.5421 against feature 007's 2.7754, so the result holds whether the
    comparison is whole-run or end-of-run. Reported both ways rather than whichever is larger
- [X] T038 [US3] Read the **end-reason mix whole**. A fall in the wall share that turns up as a rise
      in the stall share is a traded failure, not a fixed one. Feature 008 fell into exactly this
      and named it, and this task exists so 009 does not repeat it
  - **Not a trade.** Against 007 the wall share fell 59.07 to 57.10 per cent and the stall share
    *also* fell, 27.41 to 24.90. Track swaps flat at 13.46 against 13.11. What rose is the lap
    share, 0.058 to 0.527 per cent, and the step-limit share
  - **The one limit on that comparison, stated rather than buried.** Feature 007 ran with no
    `MaxStep`, so it has no step-limit category at all, and 009's 4.37 per cent of episodes ending
    on 008's 6000-step limit have no counterpart in 007's denominator. The shares are close but not
    strictly like for like. The markers finding survives it in direction, because truncating long
    episodes can only lower markers per episode
- [X] T039 [US3] Report cumulative reward against 007 and 008, and **back the comparability claim
      with the diff** showing the reward table unchanged rather than asserting it. SC-011
  - **+0.0887 over the last ten summaries, against -1.2612 for 007 and -6.6515 for 008.** First
    non-negative cumulative reward in the project
  - Comparability backed as the task demands: `git diff be2f9c4..HEAD --
    unity/SelfDrivingSim/Assets/Scripts/` contains no reward-bearing line. Six files changed since
    008 closed and none of them touch `AddReward`, `SetReward` or the reward table
- [X] T040 [US3] Report throughput against **903** and **927** steps per second. SC-009. The BC
      module adds work per update and this is where that shows
  - **687 steps per second**, 5,000,000 steps in 7336.6 s. Steady-state 686 after dropping the
    first five summaries, so startup is not what moved it
  - **The fall splits in two and the probe is what makes that sayable.** The sighted probe has no
    BC module and ran at **782**, so roughly half the drop from 903 and 927 predates this feature
    and belongs to the sensing fix restoring ray hits that were previously discarded. BC accounts
    for 782 to 687
  - Both runs were on the same machine in different sessions, so this is a reading of two
    measurements and not a controlled one. Said that way in `EXPERIMENTS.md` too
- [X] T041 [P] [US3] Report `Losses/Pretraining Loss` over the run, not only at the start. It should
      fall and then stop being updated once the anneal reaches its floor, and a curve that does
      neither means the block is not behaving as R8 describes
  - **The cut-off is exactly R8.** Present from the first PPO update at step 30,000, non-zero
    through step **520,000**, and 0.0 at every summary from **540,000** to 5,000,000 without
    exception. That is the module declining to update once the linear anneal drives its learning
    rate under 1e-10. `steps: 500000` did what it was set to do
  - **The fall is the half the task expected and did not get.** 1.2502 at 30,000 against 1.1186 at
    520,000, about eleven per cent, wandering rather than descending. Recorded as a shallow drift
    rather than written up as a fall
  - A reading, offered as a reading: at `strength: 0.5` the policy is pulled by PPO and by the
    expert at once and never sits still long enough to fit the demonstration closely. Whether a
    closer fit would help is not answerable from one run and this feature does not ask it

**Checkpoint**: the candidate is trained and read against the numbers fixed before it ran.

---

## Phase 6: The held-out evaluation (US4)

- [X] T042 [US4] Export the `.onnx` and commit it through LFS with the run id in its name, as
      features 006 to 008 did
- [X] T043 [US4] Run the standard sweep on the ten held-out seeds, **deterministic** inference
- [X] T044 [US4] Run it again with **sampling** inference. The two modes are reported separately and
      **never averaged**, which is US4's first acceptance criterion
- [X] T045 [US4] Record lap completion per seed in both modes. State `lapsToComplete: 3` wherever a
      lap count appears, because a recorded lap is three laps and the sentence has to say so
- [X] T046 [US4] Record the **80 per cent bar met or not met with its number**. SC-008, and it is
      feature 006's SC-002 restated unchanged
- [X] T047 [P] [US4] Record markers on held-out track against feature 007's **6.20 of 24**
- [X] T048 [P] [US4] Write the held-out result into `results/EXPERIMENTS.md` in the same session as
      the run, not later

**Checkpoint**: M3's milestone criterion is measured and recorded, met or not.

---

## Phase 7: The M3 closeout and the handoff to M5

**This phase closes the milestone, not only the feature.** The scope decision of 2026-08-28 caps M3
here: whatever Phase 6 measured, the next work item is M5 and there is no feature 010.

- [X] T049 Write the feature's own closeout: what the warm start changed, what it did not, and
      which of the two outcomes in `quickstart.md` this run landed on
- [X] T050 Write the **M3 closeout** into `DESIGN.md` 4.5 and 5. Four features, one table: 006 the
      wall penalty, 007 the dense progress term, 008 the wall terminal, 009 the imitation warm
      start. Say for each what it changed and what it eliminated. **Two of the four exonerated the
      thing they changed, and that is a result about the reward table rather than a series of
      failures**
- [X] T051 State the milestone's verdict plainly, met or not met, against SC-001 and SC-002 as
      feature 006 first wrote them. A negative milestone recorded with its cause is the outcome this
      project's constitution asks for, and it is defensible at the interview
- [X] T052 Name what remains as candidates now that the reward-side line is retired: the
      observation's content, the policy class, and the vehicle. Name them as candidates, not as
      future features, because M3 is closed
- [X] T053 [P] Update `results/EXPERIMENTS.md` with the closing summary row for M3
- [X] T054 [P] Confirm the three suites are green and record the counts against T004's
  - Run 2026-09-01 from the repository root, each venv's own interpreter. **Both Python suites exit
    0.** `.venv` collects **376 tests** against T004's 365 (362 passed plus 3 skipped), and
    `.venv-bc` collects **430** against T004's 416. The rises of 11 and 14 are this feature's own
    additions, `test_demo_seeds.py` and `test_speed_tracking.py` among them
  - **The pass and skip split was not captured separately this time, and the task says so rather
    than quoting T004's format as if it had been.** Both runs were piped through `tail`, which
    landed on the warnings block instead of the summary line, so what is recorded is the collected
    total plus a green exit rather than the passed-and-skipped breakdown. The exit code carries the
    verdict here. The three torch dependent skips under `.venv` are unchanged behaviour and were
    not re-counted
  - **The EditMode suite is outstanding and is a human step.** `TestRunnerApi` trips the MCP
    user-interaction guard, as T015 and feature 008's T031 both recorded, so it is Window > General
    > Test Runner > EditMode > Run All. Expected **142**, unchanged from T015, because Phase 6 and
    Phase 7 touched no C# at all: `git diff --name-only 5784a8d..HEAD -- Assets/Scripts/` returns
    nothing
- [X] T055 [P] Check every file this feature touched for em dashes and for the writing rules in the
      constitution's style section
- [ ] T056 Merge `009-imitation-warm-start` into `develop` with `--no-ff`
- [ ] T057 **Outstanding milestone merges and tags.** `master` is 164 commits behind `develop` and
      only `v0.1-m1` exists. M2, M3 and M4 all closed without their merge or their tag. Merge and
      tag `v0.2-m2`, `v0.3-m3` and `v0.4-m4` so a gate is demonstrable from a clean clone, which is
      what the constitution's Milestone Gates section actually requires
- [ ] T058 Open the M5 feature: evaluation and comparison, RL against BC against the human dataset,
      the steering-distribution work in `DESIGN.md` 7 and 7.1, `results/plots`, and the README
      reproduction recipe verified end to end. It is the submission deliverable and it is at zero

**Checkpoint**: M3 is closed with a verdict, the repository's milestone history is honest, and M5 is
open.

---

## Dependency notes

- T001 blocks everything. Principle V
- T006 to T010 block T016. The action path has to exist before the expert can be measured through it
- **T023 to T023b block T016 as well.** R10: the phase has no scene to run in until they exist
- T021 blocks Phase 4. This is the gate and it can end the feature
- T024 blocks T030. The trainer cannot point at a file that does not exist
- T028 blocks T034. Ordering rule 5
- T033 blocks T034. Ordering rule 4
- T035 gates the rest of Phase 5. A run without the imitation loss is feature 007 with a longer name
- T046 blocks T051. The milestone verdict needs the milestone's number
