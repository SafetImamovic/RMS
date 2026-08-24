# Tasks: PPO Reinforcement Learning Driver

**Input**: Design documents from `/specs/006-ppo-rl-driver/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included, and not optional. Constitution Principle VIII requires EditMode tests for
Unity logic and `pytest` for Python. The plan's post-design re-check records that this feature is
testable at all only because the reward terms are separated into pure functions and the seed
isolation is expressible as an assertion over a committed file.

**Organization**: Grouped by user story. US1 and US2 are both P1 and are sequential rather than
parallel: there is no model to drive until something has trained.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Three orderings this feature must not violate

**The design writeback comes first.** T001 blocks every code task, because the decision rate, the
area layout and the spread protocol are design decisions and Principle V puts them in `DESIGN.md`
before the code that implements them.

**The throughput measurement comes before `max_steps`.** T030 blocks T031. The only throughput
figure this project has is 700 steps/s on 3DBall, which `ENVIRONMENT.md` explicitly calls an upper
bound. Choosing a training budget before measuring is how a night gets wasted.

**The spread comes before every comparison.** T046 and T047 block T048 and T049, and block any
sentence in the results that says one configuration is better than another. This is the task
that nothing fails without, which is exactly why features 004 and 005 both wrote it down as the
one most likely to be skipped.

---

## Phase 1: Setup

**Purpose**: the things that must exist before any code, including the one the constitution puts
before implementation.

- [X] T001 Write the M3 decisions into `DESIGN.md` in a `docs:` commit before any code exists: into 4.5, the decision rate of 12.5 Hz with its derivation from the 50 Hz physics clock and the 14.08 Hz dataset rate, what that means for the 0.55 threshold, and the note that the learned agent counts wall contacts through its own component rather than the scripted driver's; into 5, the training-area layout at 300 m separation, the seed rotation policy, the statement that `max_steps` is set from a measured throughput rather than from the current 2M to 5M range, and the reduced-budget spread protocol. **Principle V requires this first**, and this task blocks every code task that follows (research R2, R3, R6, R7, R8, R9)
  - Written as additions to **4.5, 4.6 and 5**, not as new sections. Section numbers are cited from every spec (`DESIGN 4.3`, `DESIGN 4.5`, `DESIGN section 7`) and renumbering breaks those references silently
  - **This task found a contradiction rather than only recording decisions.** Research R5 listed three episode end reasons and missed the stall rule 4.6 already fixed in M2, 60 s without a new checkpoint. Both time limits are kept, because they answer different questions: the stall rule catches a policy that stopped progressing, the total cap bounds one that is merely slow. FR-011, research R5, the data model and T017 were all amended to four reasons **before** any code exists, which is the order Principle I requires
  - 4.5 gained the decision rate with its derivation, and the five rules the reward table alone does not settle: the jerk penalty multiplies the whole delta and is discontinuous at 0.55, the speed term clamps its negative half, the wall penalty precedes the episode end, wrong-way scores on the transition rather than per step, and the agent counts wall contacts through its own component so feature 005's code is untouched
  - 4.5 also closes what M2 deliberately left open. M2 wrote that wrong direction "se prijavljuje, ne boduje" and said the scoring belongs to M3. It now exists, and it uses the ring's own detection rather than a second definition
  - Section 5 lost its `max_steps 2-5M` claim. That range predates any measurement of this environment, and the honest replacement is that a pilot run sets the budget. Removing a number from the design is the point of the task, not a side effect
- [X] T002 [P] Create `results/rl/` with `curves/` beneath it, and add the `.gitignore` rules: raw `events.out.tfevents.*`, `checkpoint*.pt` and intermediate `.onnx` snapshots stay out, while `results/rl/curves/*.csv` and `results/rl/*.md` come in. The asymmetry mirrors `results/heuristic/` and is the resolution of the FR-018 conflict recorded in research R10
  - Written as **one line, `results/ppo_car*/`**, rather than as the pattern this task proposed. The obvious version, `results/**/checkpoint*.pt`, would also have caught `results/bc/run_<id>/checkpoint.pt`, which the existing rules deliberately commit through LFS so the M4 gate can be shown without retraining. Ignoring whole trainer run directories by their run-id prefix costs nothing and touches nothing already decided
  - The rule works because run ids are a convention this feature also fixes: `ppo_car_vNN` for candidates, `ppo_car_spread_*` for the noise-floor runs. **A run id that does not match the prefix silently commits its event files**, which is worth knowing before someone invents a new naming scheme
  - `results/rl/` and `results/rl/curves/` exist on disk but carry no tracked file yet, so they arrive in git with the first exported curve at T032
- [X] T003 [P] Create `python/rl/__init__.py`, `python/rl/export_curves.py` and `python/rl/report.py` with module docstrings only, no logic. The docstrings carry the two rules the tests will enforce: the export never smooths and never resamples, and an absent series writes empty rather than zero
  - The package docstring records the split that is easy to get wrong later: `export_curves` runs under `.venv-mlagents` because the event reader ships with the trainer's own TensorBoard dependency, while `report` runs under `.venv` because it reuses `python.eda.stats` and `python.track.compare_drive`. That is what makes the learned column come out of the same functions as the human and BC columns rather than a parallel implementation
- [X] T004 [P] Measure and record the pre-feature test baseline in this file, running the full suite in `.venv` and in `.venv-bc`, so a later regression is attributable. Do not pass a second `-q` and do not pipe through `tail`; `README.md` records both ways of losing the pass count
  - Measured 2026-08-17: **`.venv` 323 passed, 3 skipped** in 325.9 s, and **`.venv-bc` 377 passed** in 342.4 s. Both agree with the counts `README.md` was corrected to at the end of feature 005, so the README is currently accurate and T060 compares against these two numbers
- [X] T005 [P] Create `unity/SelfDrivingSim/Assets/Models/` and confirm with `git check-attr filter -- <path>.onnx` that `.gitattributes` routes the extension through LFS before the first model lands there. Discovering the routing after committing a 300 KB blob means rewriting history
  - Routing confirmed on the exact target path: `filter: lfs`, `diff: lfs`, `merge: lfs`
  - **The folder was deliberately not created.** A directory made outside the editor arrives without its `.meta`, and T063's merge checklist requires every `Assets/` file to carry one in the same commit. Unity generates the folder and its `.meta` together when the first model is imported at T038, which is the version that satisfies the checklist rather than working around it

**Checkpoint**: the design is written down, the folders exist, and the baseline is recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the agent, the reward, the area and the scene. No user story can begin until an
episode can run.

**CRITICAL**: T001 must be complete before any task in this phase.

### The reward, as pure functions

- [X] T006 [P] Create `unity/SelfDrivingSim/Assets/Scripts/Vehicle/WallSensor.cs`: owns `OnCollisionEnter`, counts barrier contacts, exposes a count and a rising-edge flag consumed once per read. A new component rather than an edit to `HeuristicDriver`, because Unity delivers the callback to every component on the object and feature 005's counting must keep producing the rows it already published (research R3)
  - The contact filter is copied along with the counting, and it is the part worth copying: a contact counts only when its normal is more sideways than vertical, because the road sits under the WheelColliders and a kerb strike or a landing would otherwise end episodes the reward table means to keep running
  - Exposes `TakeNewContact()`, which consumes the edge rather than reporting the state. The wall penalty is terminal, so a latched flag would pay `-5.0` again on every step of an episode that had already ended
- [X] T007 [P] Create `unity/SelfDrivingSim/Assets/Scripts/Agent/RewardModel.cs`: one static function per term from `contracts/reward-events.md`, taking numbers and returning a float. No `MonoBehaviour`, no scene access, no `Time`
  - `Checkpoints` takes a **count**, not a bool. A fast car can cross two markers inside one decision at 12.5 Hz, and paying for one would quietly under-reward exactly the driving the table exists to encourage. It refuses a negative delta, because the ring's awarded count never decreases inside an episode and a negative delta means an episode boundary was missed
  - `Speed` clamps at **both** ends. The negative half is the rule the contract already stated; the upper clamp is new here, so that an overspeed cannot pay more than the term is worth
  - `Idle(speed)` exists only so the farming defence is a function rather than a comment: it is the step cost plus the speed payment, and its sign is what T008 asserts
- [X] T008 [P] Create `unity/SelfDrivingSim/Assets/Tests/EditMode/RewardModelTests.cs` covering all six cases the contract lists: each term's value, the jerk term zero at and below 0.55 and non-zero above it, the speed term zero for negative `v_norm`, the circling case, the standing-still case, and the breakdown summing to the total. **The circling test is the one that matters**: it asserts the sign of the best sustainable per-step return against a checkpoint's `+1.0`, which is the design's defence against reward farming, and it should fail loudly if a weight is ever changed in a way that breaks it
  - 12 test cases. The circling case asserts three things rather than one: that the best sustainable per-step return is exactly zero at full speed, that it is strictly negative below full speed so loitering is worse than nothing rather than merely no better, and that one marker outweighs a thousand circling steps
  - The standing-still case records an ordering that is easy to lose: a stationary car ends a full 6000-step episode at `-6`, which is **worse than driving into a barrier on the first step**. Crashing while trying beats not trying, and that is a property of the weights rather than an accident
  - Two cases cover the discontinuity at 0.55 from both sides, so a later "fix" that eases the penalty in smoothly has to delete a test that says the jump is deliberate

### The shared driver interface (research R13)

- [X] T009 Create `unity/SelfDrivingSim/Assets/Scripts/Agent/IRunDriver.cs` covering exactly what `SweepRunner` uses of a driver: engage and disengage, begin a run, report finished with a reason, and hand over the run-record fields
  - **Three members, not five.** The task assumed the runner needed the end reason and the run-record fields; it does not. Reading the call sites showed it only ever asks whether a run is still going, so the interface is `RunActive`, `RestartRun` and `SetEngaged`. Everything else a driver does, including deciding why a run ended and writing its own row, stays with the driver
  - That also avoids lifting `HeuristicDriver.EndReason` into a shared type. Its member names are written into every row of `results/heuristic/`, and a driver that ends episodes for different reasons should not be sharing that enum
- [X] T010 Make `HeuristicDriver` implement `IRunDriver` in `unity/SelfDrivingSim/Assets/Scripts/Agent/HeuristicDriver.cs`. **Mechanical only.** No behaviour change, no reordering, no renaming of anything that reaches a run record
  - Two lines: the interface on the class declaration, and `RunActive => Outcome == EndReason.Running`, which reads existing state and decides nothing
- [X] T011 Change the serialized driver field in `unity/SelfDrivingSim/Assets/Scripts/Track/SweepRunner.cs` to the interface, so one runner evaluates the scripted driver and the learned policy and FR-023 holds by construction rather than by inspection
  - Unity cannot serialise an interface reference, so the field is a `MonoBehaviour` resolved to `IRunDriver` in `Awake`, with a loud error if the wired component does not implement it. A sweep starting with an unusable driver would spend its whole budget writing rows for a car nobody drove
  - **The field keeps the name `driver`**, on the reasoning that scene YAML binds by field name and a rename would drop an existing reference. **T012 showed that reasoning was sound but did not apply here**: the scene stores `driver: {fileID: 0}` and never had one wired, relying on the `Awake` fallback instead. The name is kept anyway, and the runtime binding was verified rather than assumed
  - `SetStrategy` stayed out of the interface and is called through an `is HeuristicDriver` check. A learned policy has no strategy to select, and its run record carries the run id in the controller column instead
- [X] T012 Verify T010 and T011 changed nothing: re-run the scripted driver on one seed already present in `results/heuristic/runs_2026-08-16_17-26-51.csv` and compare the row field by field. **A difference here means feature 005's published numbers are no longer reproducible**, and the interface extraction is reverted rather than explained
  - Re-ran seed 1, `WeightedAverage`, 13/180/20 at 2x on 2026-08-17. **Every categorical field is identical**: lap completed, 24 of 24 markers, 0 skipped, 0 wall contacts, `LapComplete`
  - The three numeric fields differ inside the spread feature 005 measured from five repeats of this same seed: lap time 27.380 against 27.300, a difference of **0.080 s against a 0.16 s floor**; `|dsteer|` P95 0.0443 against 0.0428, **0.0015 against 0.0063**; sign changes 0.1462 against 0.1466, **0.0004 against 0.0366/s**. The extraction did not change the driver
  - **The gate also corrected a claim rather than only confirming one.** T011 assumed the scene's `driver` reference had to be protected by keeping the field name; the scene never had one, and `SweepRunner.Awake` has always found the driver by search. The runtime binding was checked directly instead: the field resolved to `HeuristicDriver` and the interface cast succeeded
  - EditMode suite at the same time: **105 passed, 0 failed** in 3.21 s, which is the first run including `RewardModelTests`. T059 re-runs it at the end of the feature, but the reward terms are already green rather than merely written

### The agent

- [X] T013 Create `unity/SelfDrivingSim/Assets/Scripts/Agent/DrivingAgent.cs` deriving from `Unity.MLAgents.Agent`, with `CollectObservations` feeding `CarAgent.Observations` in order, and a start-up assertion that `CarAgent.ObservationCount` equals the configured vector size. FR-004: a silent mismatch trains against noise and the reward curve does not show it
  - The assertion reads `BehaviorParameters.BrainParameters.VectorObservationSize` and logs an error naming both numbers and their composition. It deliberately does **not** correct the size: the ray count is frozen for this feature and every recorded baseline depends on it, so the behaviour is what gets fixed
- [X] T014 Implement `OnActionReceived` in `DrivingAgent.cs`: two continuous actions, clamped to -1 to 1, written to `CarController.ScriptedMove`, the same field `HeuristicDriver` writes. PPO's output is unbounded in principle and one large value would otherwise arrive as a full-lock command
- [X] T015 Implement `OnEpisodeBegin` in `DrivingAgent.cs`: place through `StartPlacer` at a random marker with the 1.5 m lateral and 10 degree yaw offset fixed in M2, reset `CheckpointRing` progress and `StartAt` the chosen marker, zero the reward breakdown and clear the steering history (FR-010). The ring's straddled-marker handling is what stops the placement itself reporting wrong-way, and this task must not defeat it (research R4)
  - The reset calls `placer.Place()` and **nothing else**. `StartAt` already calls `ResetProgress` internally, so the counters zero for free; doing both by hand is the mistake that cost feature 005 a sweep, since the ring would wait for marker 0 while the car stood at marker 17 and no gate was ever awarded
  - The random sequence is deliberately **not** reseeded, which is the opposite of what a sweep does. A sweep reseeds so runs repeat; training wants varied starts, because a policy that always begins at the same marker learns one track's order of corners rather than how to drive
- [X] T016 Implement the reward accumulation in `DrivingAgent.cs`, calling `RewardModel` per the contract: an increase in `CheckpointRing.AwardedCount` pays progress, a rising edge on `WrongWay` pays the wrong-direction penalty, `WallSensor` pays the terminal penalty, and the step, speed and jerk terms accrue every step. The jerk delta is measured between decisions, not between physics steps
  - **That falls out of the decision requester rather than needing bookkeeping.** With `TakeActionsBetweenDecisions` true, `OnActionReceived` fires every academy step but repeats the same action between decisions, so the delta on a repeated step is exactly zero and the only non-zero deltas are the ones between real decisions. No step counting, no separate timer
- [X] T017 Implement termination in `DrivingAgent.cs`: barrier contact applies `-5.0` **and then** ends the episode, the lap target ends it, 60 s without a new marker truncates it, and `MaxStep = 6000` truncates it. All four are recorded distinctly, because the trainer bootstraps a truncated episode differently and conflating them teaches the policy that lasting the full time is punished. The stall rule comes from `DESIGN.md` 4.6 and was fixed in M2; the total cap is this feature's addition (research R5)
  - The two truncations call different things on purpose: the stall calls `EpisodeInterrupted()`, which is ML-Agents' own truncation path, while wall contact and the lap target call `EndEpisode()`. The step cap is recorded and left to the framework, which performs that truncation itself
  - Each end reason is also reported as its own statistic (`episode/end_wallcontact` and so on), so the distribution is visible during a run rather than only after one. A run where every late episode ends in `WallContact` is a policy that never learned to avoid a barrier, and the cumulative reward can hide that if the speed term is carrying it
- [X] T018 Report every reward term separately through `Academy.Instance.StatsRecorder.Add` under the keys in `contracts/reward-events.md`, and assert in the same place that the breakdown sums to the agent's cumulative reward (FR-008)
- [X] T019 Add and configure `DecisionRequester` on the agent with `DecisionPeriod = 4` and `TakeActionsBetweenDecisions = true`, giving 12.5 Hz against the 50 Hz physics clock (research R2)

### The area, the seeds and the scene

  - Set on the prefab rather than in code: `DecisionPeriod = 4`, `TakeActionsBetweenDecisions = true`, giving 12.5 Hz against the 50 Hz physics clock
- [X] T020 Create the training seed pool loader reading the `train` half of `results/tracks/seed_split.json`, through a single code path, in `unity/SelfDrivingSim/Assets/Scripts/Track/TrainingArea.cs`
  - Written as `SeedSplit`, a small loader beside the runner rather than a field on the scheduler. A seed list typed into a scene cannot satisfy SC-008, which asks for the separation to be demonstrable from the recorded configuration; reading the committed file means the scene cannot disagree with it
  - `SweepRunner`'s own parser was left alone. It is on the path that produced feature 005's published rows, and the duplication costs about twenty lines against the risk of touching that path again
- [X] T021 [P] Create `unity/SelfDrivingSim/Assets/Tests/EditMode/TrainingSeedIsolationTests.cs` asserting the training pool equals the committed file's 34 training seeds and is disjoint from the 10 evaluation seeds. **A test rather than a review**, because a training run that quietly included an evaluation seed produces a better number and no error (SC-008, research R15)
  - Four tests, not one: the file is readable, the halves do not overlap, the counts are 34 and 10, and neither half repeats a seed. The count assertion is there so a regenerated split cannot silently change the denominator under results already published against it
  - EditMode suite after adding them: **109 passed, 0 failed** in 5.19 s, up from 105
- [X] T022 Implement `TrainingArea.cs`: an area id, the current seed, the episode count on that seed, and ownership of its own `TrackBuilder`, `CheckpointRing`, `StartPlacer`, car, `CarAgent`, `WallSensor` and `DrivingAgent`. No static fields, and no reference to another area (FR-016)
  - Independence needed almost no work, which T007 in research had already found: `TrackBuilder` parents its build under its own transform, and the only mutable static in `Assets/Scripts` belongs to the scripted driver's run record, which the training scene does not use
- [X] T023 Measure `TrackBuilder.Build()` wall-clock cost for one seed and record it here, then choose the rotation interval from that number. The rebuild spans at least three frames by construction, since `SweepRunner.SwapTrack` yields once for the old colliders to leave and once for the new ones to register
  - Measured 2026-08-17 over five seeds: **209.3 ms on the first build, then 61.0, 54.2, 50.9 and 53.4 ms**. The first is not representative; it carries the file read and the first allocations. Steady state is about **55 ms**, producing 24 markers
  - That number sets the interval. Twelve areas rotating on the same episode would be roughly 0.66 s of main-thread work in one frame, and the main thread is shared by every area, so the whole session would stall. **Rotation is every 5 episodes and swaps are queued one at a time**, which keeps the cost off any single frame
  - Rebuilding every episode was the alternative and is rejected on this measurement: early-training episodes end in seconds, so a 55 ms rebuild against a 5 s episode is about one percent of the session spent regenerating geometry, for variety the rotation already provides
- [X] T024 Create `unity/SelfDrivingSim/Assets/Scripts/Track/AreaScheduler.cs`: rotates each area's seed through the 34 training seeds every K episodes, disabling that area's agent across the swap. **Not inside `OnEpisodeBegin`**, which is synchronous and would read colliders that do not exist yet (research R6)
  - Seeds are cycled rather than drawn at random. A random draw over 34 seeds would leave some tracks over-represented by chance across a run's episodes, and that imbalance is invisible in every number the run reports
  - The swap ends the episode that spans it. An episode that began on one track and finished on another is not a fair sample of either
- [X] T025 Create `unity/SelfDrivingSim/Assets/Prefabs/TrainingArea.prefab` holding one complete self-contained copy of the environment
  - Built from **copies of the existing car and track objects**, not assembled from scratch. The vehicle every published baseline was measured on is the one that has to train, and a hand-rebuilt car with a subtly different mass or wheel friction would invalidate the comparison without ever looking wrong
  - Stripped from the copy: `HeuristicDriver`, `HeuristicTuner`, `DriveHud`, `DriveLogger`, `ObservationDebug`, `ObservationProbe`, `ScriptedDriver`, `DriveTelemetry`, `LapReport`. Twelve IMGUI panels and twelve CSV writers in one session are noise and file contention
  - `StabilityMonitor` was stripped too, on evidence rather than tidiness: see T026
- [X] T026 Create `unity/SelfDrivingSim/Assets/Scenes/Training.unity` with the area prefab instanced on a grid at 300 m pitch, which exceeds a roughly 200 m track plus the 20 m ray length so no area's sensing reaches another's barriers (research R7). **A new scene rather than an edit to an existing one**, which keeps the Principle IV scene lock uncontested
  - 12 areas on a 4x3 grid at 300 m pitch. Measured footprint per area is **59 to 82 m**, so with 20 m rays the separation is comfortable
  - **The first play test found a real defect.** Areas build one at a time, so twelve cars spent the opening frames with no ground beneath them: the stability log gained twelve `FellThrough` entries and idle-drift reports of 40 to 60 m, all inside two seconds. `TrainingArea` now parks its car until the area has a track, and un-parks it after the first build. Re-tested: 12 areas built, 12 cars active, episodes running, and **the stability log was not written to at all**
  - That defect also polluted a **committed** file. `results/drive_logs/stability_log.csv` is tracked deliberately as evidence for a feature 003 decision, and the training scene had appended twenty-two junk rows to it. Restored, and `StabilityMonitor` is out of the training prefab so it cannot happen again
  - The trainer writes `Assets/ML-Agents/Timers/` on every session with an agent in the scene. Ignored, along with its generated `.meta`
- [X] T027 Create `config/ppo_car.yaml` per `contracts/training-config.md`, with `max_steps` left unset pending T031 and `summary_freq` pinned at 10000 so every committed curve has the same resolution
  - Validated against the trainer's own parser rather than by eye: `RunOptions.from_dict` returns every value as written, `ScheduleType.LINEAR` included
  - Doing that needs `mlagents.plugins.trainer_type.register_trainer_plugins()` first. Without it the parse fails with **"Invalid trainer type ppo was found"**, which reads like a broken config and is not one; the CLI registers those plugins at startup and a bare import does not
  - `max_steps` is committed as **500000 and labelled provisional in the file itself**. The YAML has to parse, so it needs a number, and the honest number today is the reduced budget the spread runs use. T031 replaces it once T030 has measured throughput
- [X] T028 Set `BehaviorParameters` on the agent: behaviour name `CarDriver` matching the config string exactly, vector observation size 19, two continuous actions. A mismatched behaviour name does not error; the trainer simply sits at zero steps

**Checkpoint**: an episode can run, end for a recorded reason, and start again. Training can begin.

---

## Phase 3: User Story 1 - A policy that trains at all (Priority: P1)

**Goal**: the trainer connects to the scene, episodes accrue reward, the curve rises, and the run
is recorded in a form that survives a clean clone.

**Independent Test**: launch a short run, confirm the trainer connects and reports the expected
shapes, confirm episodes end for the stated reasons, and confirm the recorded cumulative reward is
higher at the end than at the start.

  - Verified on the saved prefab: behaviour name `CarDriver`, vector observation size **19**, **2** continuous actions, one stacked observation
- [X] T029 [US1] Smoke run: start `mlagents-learn config/ppo_car.yaml --run-id=ppo_car_smoke` from the repository root, press Play, and confirm the connection line reports package 4.0.3 and communication version 1.5.0. Record what it printed, because that line is the compatibility proof and `ENVIRONMENT.md` treats it as such
  - Connected first try: `Connected to Unity environment with package version 4.0.3 and communication version 1.5.0`, matching `ENVIRONMENT.md` on both halves
  - Run as one background process against the editor driven over MCP, rather than two hand-held terminals. Worth knowing for later: the trainer must be listening **before** Play, and entering play mode drops the MCP connection for about ten seconds while the domain reloads
- [X] T030 [US1] Pilot run of roughly 100k steps. Measure and record here: steps per second, wall clock, mean episode length, and the share of episodes ending in each of the three reasons. This is the measurement T031 depends on and the only honest input to a training budget
  - **500,000 steps in 814.9 s.** Steady state, excluding the 72.8 s of startup and twelve track builds, is **660 steps/s** with twelve areas
  - That contradicts the expectation this feature was planned against. `ENVIRONMENT.md` called 3DBall's 700 steps/s an upper bound and predicted WheelCollider physics with 13 raycasts would be "substantially slower". It is not, and the plan's worry about a 30 steps/s worst case is dead
  - Episode lengths ran **387 to 727 steps**, so 8 to 15 s against a 6000-step cap. Episodes end early, and `episode/end_lapscompleted` and `episode/end_steplimit` never appear in the event file: every episode ended on a barrier or a stall
  - **The pilot also produced a finding it was not asked for: the policy did not learn.** Cumulative reward went -4.852 over the first ten summaries to -4.332 over the last ten, against a per-summary spread of 2 to 3, and checkpoint reward *fell* from 0.321 to 0.219 against the 24 markers a lap needs. Logged in `results/EXPERIMENTS.md` with what it does and does not say
  - Drawn as small multiples in `results/rl/ppo_car_smoke.png`, with the generator committed beside it. Reading the terms side by side surfaced something the numbers alone had not: **the jerk penalty is a larger influence on the return than progress is.** `reward/jerk` runs -0.3 to -0.6 while `reward/checkpoint` sits near 0.2, so smoothness currently outweighs reaching markers. That is a hypothesis for a tuning run, not a conclusion
  - `reward/speed` peaks at 0.0175 against a step cost near -1.5, so the speed term is about a hundred times too small to matter. It is not being farmed, which the circling test already guaranteed, but it is also teaching nothing
- [X] T031 [US1] Set `max_steps` in `config/ppo_car.yaml` from T030's measured throughput so a full run fits inside 12 hours (SC-006), and write the arithmetic into this task. A number chosen from the design's range instead is the mistake this feature exists to avoid
  - **5,000,000 steps**, which is 2.1 hours at the measured 660 steps/s. The twelve-hour envelope would allow about 28M, and the budget is deliberately short of it: a run nobody can repeat twice in a working day makes the one-change-per-run rule in FR-007 unaffordable
  - The arithmetic is in the config file itself, beside the number, so a reader does not have to find this task to know where 5M came from
- [X] T032 [US1] Implement `python/rl/export_curves.py` per `contracts/curve-export.md`: reads the trainer's event files, writes one CSV per run to `results/rl/curves/`, no smoothing, no resampling, `run_id` repeated on every row, absent series empty rather than zero
  - Split into a reading half and a shaping half. `read_series` imports the event reader lazily and runs under `.venv-mlagents`; `to_rows` and `write_csv` are pure and run anywhere, which is what keeps the tests runnable under `.venv` where the rest of the analysis lives
  - Exercised against the real run rather than a fixture: 50 rows, 10k to 500k. **The empty-not-zero rule earned itself immediately** - `policy_loss` and `value_loss` are genuinely absent at steps 10000 and 20000 because the trainer had not emitted them yet, and writing zeros there would have shown two summaries of perfect loss
  - The export also confirmed FR-008 on live data: at step 10000 the six terms sum to -5.094 against a reported cumulative reward of -5.086
- [X] T033 [P] [US1] Create `python/tests/test_rl_curves.py`: the exporter preserves the trainer's own summary steps, writes empty for a missing series rather than zero, repeats `run_id` on every row, and exports the rows it has when a run ended early
  - 13 tests, all on the pure half. The two that matter most are the pair separating absent from zero: a missing series writes empty, and a genuine `0.0` survives as `0.0`
  - Also covers the case where a run stopped before its first summary, which exports nothing rather than inventing rows from whichever series did emit
- [X] T034 [US1] First full training run `ppo_car_v01`, and its row in `results/EXPERIMENTS.md` **in the same session** (Principle VI, FR-017). The row names the configuration, what it changed from the pilot, the outcome, and whether it is a candidate
  - **5,000,000 steps in 7,308.3 s**, 684 steps/s. One changed thing against the pilot: the budget, 500k to 5M. Seed pinned at 42
  - **The budget hypothesis is retired.** First and last 250 summaries are -4.573 and -4.409 against a spread of 0.512 across the 500 summary means, so the total is flat over ten times the pilot's length. The first-ten to last-ten delta of 0.765 is not a result and the row says so
  - Checkpoint reward fell again, 0.394 to 0.245, which is **0.249 markers per episode against the 24 a lap needs**. `episode/end_lapscompleted` never appears at any point in 5M steps
  - What did move: wall share 60.1 to 45.2 percent, episode length 465 to 548 steps, step cost -1.797 to -2.031. **The policy learned to stall rather than to drive**, which is the cheaper way to stop paying -5.0 and is a reward design finding rather than a tuning one
  - Interrupted once at 1,210,000 steps by a 30-minute cap in the tooling that launched the trainer, and resumed from `CarDriver-1199901` to 5M. Two log segments and two event files, both committed; the exporter merges them. The schedules resumed correctly, verified at `ppo/optimizer_torch.py:108` where the decay reads `policy.get_current_step()` rather than accumulated state
- [X] T035 [US1] Export the curve for `ppo_car_v01` and confirm the six per-term reward series are present in both TensorBoard and the committed CSV. **Watch `reward/checkpoint` first**: a total that rises while that term stays flat is a policy collecting step and speed reward without making progress, which is the failure the per-term reporting exists to expose
  - 500 rows, 10000 to 5000000, all six terms present. `policy_loss` and `value_loss` are empty on most rows, which is the trainer's own emission pattern and the empty-not-zero rule holding
  - Watching `reward/checkpoint` first was the right instruction and it caught the opposite of the expected failure: the term fell while the total stayed flat, so the policy is not farming speed and step reward, it is doing less of everything
  - **FR-008 does not hold.** Measured over every summary rather than one, the terms sum to 0.694 below the cumulative reward on average, off by more than 0.05 on 97.4 percent of rows. The pilot is the same, 0.675 and 96.0 percent. The previous session's claim that the export confirmed FR-008 rested on the step-10000 row, which is one of the 4 percent that agree; the claim is withdrawn in `results/EXPERIMENTS.md`. The cause is not established and is not guessed at
- [X] T036 [US1] Record the distribution of episode end reasons across the run's later phase. Every episode ending in `WallContact` late in training means the policy never learned to avoid a barrier, which the cumulative reward alone can hide if the speed term is carrying it
  - Only two reasons occur in 5M steps: `end_stalled` and `end_wallcontact`. No lap completed, and the 6000-step cap never reached
  - Late fifth of the run: **48.3 percent wall, 51.7 percent stall**, against 60.1 / 39.9 over the first ten summaries. Barrier contact fell and progress fell with it
  - **The distribution is derived, not read.** `DrivingAgent.cs:369` records each reason as `stats.Add(key, 1f)` and `StatsRecorder` averages, so the mean of a constant 1.0 is 1.0 however often it occurs: both tags read exactly `1.0000` and carry no frequency information. The shares come from the wall term instead, which is -5.0 exactly once on a barrier episode and 0 otherwise, so its mean over -5.0 is the wall share and the stall share is the complement. Counting properly needs `StatsAggregationMethod.Sum`, and that should be fixed before any run whose conclusion depends on these counts
- [X] T037 [US1] With `DrivingAgent` disabled, confirm keyboard driving and the scripted driver behave exactly as before this feature (US1 acceptance scenario 4, FR-005). Human check, cannot be delegated
  - Checked by the owner on 2026-08-19 in `Track.unity` and `HeuristicTrack.unity`. `DrivingAgent` is on `Assets/Prefabs/TrainingArea.prefab` and in no scene, so it is already absent from both and there was nothing to disable
  - **Keyboard driving works, with one reported difference: the steering is more sensitive than remembered, turning by a larger angle faster.** The owner judged it good and asked for no change. **FR-005 is recorded as met on evidence rather than on feel**: no commit since `fa9a7c2` touched `CarController.cs`, `VehicleProfile.cs` or the input path — the only 006 commit to touch `Vehicle/` is `46f0e74`, which added `WallSensor.cs` and changed nothing else. Whatever moved the steering predates this feature, so this feature did not change it. The comparison was against memory, not against a recording, which is the honest limit of the check
  - **Finding, unrelated to FR-005: seed 42 has no track file.** `Assets/Tracks/` holds exactly the 34 accepted training seeds and the 10 evaluation seeds; 42 is in neither half and `seed_42.json` does not exist. `TrackBuilder.TrackPath` builds `Assets/Tracks/seed_{seed}.json` and `TrackFile.Load` throws on a missing file, so nothing is built and the car is placed at ride height over empty space and falls. The owner read this as the builder not guaranteeing a start on the surface; the actual cause is narrower and worse — the scene was pointed at a track that was never generated. **Training cannot hit this**: `AreaScheduler` draws only from `SeedSplit.TrainSeeds()`, which is the committed accepted list
  - **Finding: the car gets stuck on seed 1 and not on seed 2, and seed 1 is a legal track.** Seed 1 carries the tightest corner of the seeds sampled, a 7.84 m minimum centre-line radius against 9.76 m for seed 2. The car's own turning circle is 5.36 m from a 2.5 m wheelbase at 25 degrees, and the generator's floor is `RADIUS_MARGIN` 1.3 times that, 6.97 m. Seed 1 clears the floor at 1.46x the car's minimum, so the geometry is legal and the car can physically make the corner. This is the scripted driver failing on the tightest legal corner, not a track defect, and it belongs to the heuristic baseline rather than to this feature


**Checkpoint**: something trains, the curve exists as data, and the run is in the log.

---

## Phase 4: User Story 2 - The trained model drives the car in Unity (Priority: P1)

**Goal**: the exported model drives on a track it never trained on, with no trainer process, and
the gap between the exported model and the trained policy is a measured number.

**Independent Test**: run the exported model in inference on held-out seeds with no trainer
attached, and record what the car does.

- [X] T038 [US2] Stop the run with a **single** `Ctrl+C`, confirm the `Exported ... .onnx` line, and copy the model to `unity/SelfDrivingSim/Assets/Models/` keeping the run id and step suffix in the filename. A second interrupt skips the export and a night of training becomes a checkpoint file
- [X] T039 [US2] Put the model on `BehaviorParameters`, set the behaviour type to inference, and drive one held-out seed with no trainer running (FR-025, US2 acceptance scenario 1)
- [X] T040 [US2] Run the full evaluation over all 10 held-out seeds through `SweepRunner` with the eval seed set and deterministic inference, writing `RunRecord` rows to `results/rl/` with the run id in the controller column (FR-022, FR-023)
- [X] T041 [US2] Repeat T040 with deterministic inference disabled, and report the difference between the two as a number. **FR-026 is this task**: PPO samples while training and the exported model can take the distribution's mean instead, so the same weights are two different drivers and "the model drives worse than training suggested" is the predictable result of not knowing which one is being watched (research R12, SC-005)
- [X] T042 [US2] Measure SC-001 directly: the share of evaluation episodes completing 3 laps without wall contact. **Report the achieved rate whatever it is.** If it is below 95 percent the gate is recorded as not met and the number stands as the finding, the way feature 005 published `MostOpen` completing 0 of 34 laps
- [X] T043 [US2] Measure SC-002: at least one lap on at least 80 percent of the held-out seeds, the same threshold the scripted driver was held to
- [X] T044 [US2] Confirm a learned row and a scripted row load through one `pandas` call with no per-driver special casing. If the reporting needs a branch on driver type, the FR-023 contract was broken and T011 did not deliver what it promised

  - **Two prerequisites were missing from this phase and were built on 2026-08-24, recorded here rather than done quietly.** T039/T040 assumed an evaluation scene and a learned run-record path; neither existed. `DrivingAgent` implemented `IRunDriver` for driving but never wrote a `RunRecord`, and `DrivingAgent` lived only on `TrainingArea.prefab` while `SweepRunner` lived only in `HeuristicWeighted.unity`
  - **`Assets/Scenes/Evaluation.unity`, a new scene** rather than an edit to `HeuristicWeighted.unity`, for the reason T026 gives: a new scene keeps the Principle IV scene lock uncontested. One `TrainingArea` prefab instance with the `TrainingArea` component removed, plus a `SweepRunner` on the eval seed set. The component is removed because it parks the car in `Awake` and waits for `AreaScheduler.SwapTo` to un-park it; this scene has no scheduler, so the car stayed parked and the agent was never stepped. Found by measurement, not by reading: `StepCount` sat at 0 while the Academy had stepped 21,345 times
  - **`RunRecordWriter.Folder`** made settable so learned rows land in `results/rl/` instead of `results/heuristic/`. Set before the first append, because the file opens lazily and is never reopened
  - **A real contract violation, found by the sweep repeating one seed.** `DrivingAgent.Finish` set `_runActive = false` and then called `EndEpisode`, which runs `OnEpisodeBegin` synchronously and armed it straight back to `true`. `SweepRunner` waits on `RunActive` going false, so it never saw a run end: it held `RunsDone` at 0 while ML-Agents cycled episodes and the agent wrote **ten rows, all seed 1001**. Self-restarting is right for training and violates `IRunDriver`, which promises a run stays over until `RestartRun`. Fixed with an `evaluationMode` switch that hands restart ownership to the runner and gates `CheckTermination`, so the agent ends and records nothing between runs
  - **T042, SC-001: 0.0 per cent** of evaluation episodes completed 3 laps without wall contact, against the 95 per cent the criterion asks for. **The gate is not met and the number stands as the finding**, the way feature 005 published `MostOpen` at 0 of 34
  - **T043, SC-002: 0.0 per cent** of held-out seeds saw even one lap, against 80 per cent. Not met. Zero checkpoints of 24 were reached on any of the ten seeds, in either inference mode
  - **T041/FR-026 is the measurement that pays for this phase, and it is not a null result.** Deterministic and sampling inference give *identical outcomes* - 0 laps, 0 checkpoints, 0 wall contacts, all ten runs `Stalled` in both - and *completely different steering*. P95 |delta steer| is **0.0009 deterministic against 0.8079 sampling, a factor of 878**, and direction reversals are **0.0000/s against 5.2083/s**. The same weights really are two different drivers, exactly as R12 predicted; what this policy shows is that the difference is invisible in the outcome because the outcome is on the floor for both. A report quoting only lap rate would have called FR-026 immaterial
  - **T044 passes.** The two learned CSVs and the scripted driver's load through one `pandas.concat` with identical columns and no branch on driver type, and `lap_time_s` arrives as float64 with NaN for the twenty failed runs rather than zeros, so the empty-not-zero rule survives the round trip
  - Evidence: `results/rl/eval_ppo_car_spread_a_deterministic.csv` and `results/rl/eval_ppo_car_spread_a_sampling.csv`, ten rows each. Models promoted to `Assets/Models/` as `ppo_car_spread_{a,b,c}-<step>.onnx`; `spread_a` was evaluated because the three baselines are statistically indistinguishable (widest gap 0.165 inside T047's 0.19 gate) and picking the best of three would be picking noise. **b and c are promoted but not yet evaluated**

**Checkpoint**: a model exists, drives unattached, and its evaluation rows sit in the same shape as
the scripted driver's.

---

## Phase 5: User Story 3 - Reward changes are attributed, not guessed (Priority: P2)

**Goal**: no configuration is called better than another until the difference clears the
run-to-run spread.

**Independent Test**: run one configuration three times unchanged, report the spread, then compare
two configurations against it.

- [X] T045 [US3] Choose the reduced training budget from T030's throughput so that three runs fit in one working day, and record the choice with its arithmetic. State the limitation the plan already names: a policy still improving is noisier than a converged one, so a reduced-budget spread is likely an over-estimate, which is the safe direction for a test asking whether a difference clears the noise (research R9)
  - **Chosen: 2,000,000 steps.** At T030's 660 steps/s that is 3,030 s of training plus about 75 s of startup and twelve track builds, so **52 minutes a run**
  - **The constraint as the task states it does not bind, and pretending it produced the number would be dishonest.** Three runs at the pinned 5M cost 3 x 7,580 s = 6.3 hours, which already fits one working day. The binding constraint is Phase 5 as a whole: T046's three spread runs plus the two named T048 candidates are **five sequential runs** — one editor, one GPU, no parallelism — and 5 x 5M is 10.5 hours, which does not fit
  - **The arithmetic that chose 2M**: a six-hour training envelope inside an eight-hour day, leaving the rest for writing rows and reading curves, is 21,600 s / 5 runs = 4,320 s a run = 2.85M steps at 660 steps/s. Rounded down to 2M for headroom, which puts five runs at 4.3 hours. 2M is also the floor of the 2M-5M range `DESIGN.md` named before anything was measured, so the measurement lands inside the design's guess rather than replacing it
  - **Throughput is quoted conservatively.** T030 measured 660 steps/s over 500k, `ppo_car_v01` 684 over 5M, and `ppo_car_fr008_check` 767 over 90k on 2026-08-19. The slowest of the three is used, and the fastest is the shortest run and the least representative
  - **The limitation R9 names**: a policy still improving is noisier than a converged one, so a spread measured at a reduced budget is likely an over-estimate of the spread at full budget. That is the safe direction — a difference that clears an inflated noise floor still clears the real one
  - **A second limitation R9 does not name, which `ppo_car_v01` created.** That run showed no learning over 5M steps, so "still improving" may not describe this policy at all: the spread would then be measured in a regime where nothing converges. If a tuning candidate does start to learn, its run-to-run variance need not resemble this one's, and T049 should say so rather than treat the number as universal
  - Mechanism for T046: the reduced budget needs its own config, since `mlagents-learn` has no CLI override for `max_steps`. `config/ppo_car_spread.yaml` differs from the pinned `config/ppo_car.yaml` in that one field and nothing else
- [X] T046 [US3] Run `ppo_car_spread_a`, `ppo_car_spread_b` and `ppo_car_spread_c`: identical configuration at the reduced budget, differing only in `--seed`. Three rows in `results/EXPERIMENTS.md`, each written in its own session
  - `ppo_car_spread_a`, seed 1, 2026-08-19: 2,000,000 steps in 2,834.0 s, 706 steps/s, uninterrupted. Cumulative reward mean -4.5070, sd 0.4911 over 200 summaries. Row written in `results/EXPERIMENTS.md`, curve at `results/rl/curves/ppo_car_spread_a.csv`
  - `ppo_car_spread_b`, seed 2, 2026-08-19: 2,000,000 steps in 2,577.4 s, 776 steps/s. Cumulative reward mean -4.6613, sd 0.5022. The two run means differ by 0.154, against a within-run summary spread near 0.50 in both
  - `ppo_car_spread_c`, seed 3, 2026-08-19: 2,000,000 steps in 2,709.4 s, 738 steps/s. Cumulative reward mean -4.6722, sd 0.5360. Set complete
  - **A first attempt at b was discarded, and the cause was a scene left open from T037.** The trainer connected to nothing and timed out, because `HeuristicWeighted.unity` was still the active scene and carries no `BehaviorParameters`. It logged zero summaries, so nothing was lost but the wall clock. The launch sequence now opens `Training.unity` and asserts twelve `CarDriver` agents at behaviour type Default with no model attached, before Play, rather than checking once at the start of a session
  - **The 30-minute cap bit again and is now designed around.** A first attempt died at 1,210,000 steps, the same cap and very nearly the same step count that cut `ppo_car_v01` segment one. That attempt was discarded rather than resumed: T046 wants the three runs identical but for `--seed`, and a resume inside the run that measures the noise floor is the confound the measurement exists to exclude
  - The trainer now runs detached, launched by `Start-Process -WindowStyle Hidden` from a shell that exits immediately, with the PID recorded and progress followed by tailing `results/rl/<run-id>.log`. Nothing holds the process, so nothing can reap it. Detaching only works through `-File script.ps1`; an inline `-Command` with nested quoting produces a process that starts and writes nothing
- [X] T047 [US3] Report the run-to-run spread as a number over a named outcome metric, and state that metric explicitly. **This task blocks every comparison in this feature** (FR-020, SC-003)
  - **The metric is the run mean of `Environment/Cumulative Reward`**, taken over all 200 summaries of a 2M-step run at the T045 budget. Named here so no later comparison has to guess, and chosen over late-phase checkpoint reward deliberately: it is the tightest of the candidates and uses every summary rather than a tail
  - **The spread is sd 0.0924 across the three seeds**, on run means of -4.5070, -4.6613 and -4.6722, a range of 0.1651
  - **The gate for T049 is 0.19**, two standard deviations, rounded up. The observed range of 0.1651 is the cross-check and sits just inside it. A candidate whose run mean differs from its baseline by less than 0.19 is recorded as having made no measurable difference
  - **Between-run spread is five times smaller than within-run spread.** The summaries inside a single run scatter with sd 0.4911 to 0.5360, against 0.0924 between run means. Averaging over a run is therefore a stable statistic even though any individual summary is not, which is what makes a 0.19 gate meaningful at all. It also means a comparison quoted from a handful of summaries rather than a run mean would be reading noise five times larger than the effect it is testing
  - **Three runs is a weak estimate of a standard deviation and the number should be treated as such.** With n = 3 the sd is itself uncertain to roughly 50 per cent, so 0.19 is a working threshold rather than a precise one. A difference near the gate deserves a fourth run before it is called, and T049 should say which side of the gate a result falls on rather than implying the gate is exact
  - **R9's limitation, restated against what was measured.** The plan expected a reduced-budget spread to over-estimate the full-budget spread, because a policy still improving is noisier than a converged one, and that direction is safe. What the runs show is that this policy is not improving at any budget: `ppo_car_v01` was flat over 5M and all three spread runs are flat over 2M. The over-estimate argument therefore does not apply in the way R9 imagined. The risk runs the other way instead: a candidate that actually starts learning may be noisier than these three, so a difference that clears 0.19 is credible while a difference that fails to clear it is weaker evidence of no effect than it looks

- [X] T048 [US3] Run each tuning candidate at the reduced budget, one changed thing per run, each with its own row. A run whose description needs an "and" is two experiments and attributes to neither
  - Both candidates were written into `DESIGN.md` 4.5 before either was implemented, as Principle V requires, in the block "Dva kandidata za tjuniranje". The reward table above it now says explicitly that it is the polazna table and points at which run changed which weight
  - **`ppo_car_jerk_lo`**, `JerkPenalty` -0.005 to -0.001, 2M on seed 1, 3,164.4 s. Run mean **-4.2757**
  - **`ppo_car_wall_lo`**, `WallPenalty` -5.0 to -1.0 with the jerk scale returned to -0.005, 2M on seed 1, 2,598.0 s. Run mean **-3.1479**
  - **A first attempt at `ppo_car_jerk_lo` was killed at 900,000 steps by the tooling that launched the trainer**, the third such kill in this feature. Discarded rather than resumed, for T046's reason: the baselines ran uninterrupted and a resume would differ from them by something other than the reward weight. Evidence kept at `results/ppo_car_jerk_lo.killed_at_900k/` rather than overwritten. Launching the trainer detached from that tooling fixed it, and the rerun reproduced the killed attempt's step-10,000 summary exactly at -5.010
  - Neither weight is kept. The reward table in the repository is back to what `DESIGN.md` 4.5 pins
  - **T048 was extended on 2026-08-24 with a third candidate, `ppo_car_speed_hi`**, on the user's decision, because the two candidates the task originally named both came back negative and T050 had no winner to promote. One change, as FR-007 requires: `SpeedReward` 0.001 to **0.002**. Written into `DESIGN.md` 4.5 before the code, per Principle V
  - **The candidate is bounded by the table's own anti-farming invariant, and that is the finding worth keeping.** `Idle` was written so the step cost and the speed reward cancel exactly at full speed, which is what makes the speed term unable to give a gradient anywhere below full speed. Raising it trades that identity for a margin, and the margin caps the change: `(SpeedReward - 0.001) x 6000 < 24/3` gives `SpeedReward < 0.002333`. **So the imbalance is 240x and the largest legal correction is 2x**
  - The run is pre-registered in both directions: clearing the T047 gate says the step/speed ratio was a constraint; not clearing it says this reward table cannot be fixed by scaling these two weights and the problem is exploration rather than the weights. The second is as reportable as the first
  - `RewardModelTests` caught the change, which is what it was written for. The `Idle(1) == 0` assertion is replaced by the episode-level margin it was protecting, not deleted. A second assertion, `Checkpoints(1) > Idle(1) * 1000`, was **removed rather than retuned**: under the old table `Idle(1)` was zero, so it read `1.0 > 0` and constrained nothing, and promoting a decorative constant into a bound on a weight would invent a requirement the design never made
  - Verified against the loaded assembly rather than assumed: all thirteen reward assertions pass, break-even `v_norm` moves 1.0 to 0.5, and one marker is worth 1000 steps of flat-out circling where it was previously worth unboundedly many
  - **Result (2026-08-24): `ppo_car_speed_hi` ran 2M on seed 1 in 2,518.6 s, uninterrupted, run mean -4.6439, and does not clear the gate** at -0.0373 against 0.19, nor on `reward/checkpoint` at -0.0101 against 0.0631. Zero laps
  - **The decisive number is the mechanism, not the gate.** `reward/speed` went +0.0069 to +0.0150, but a policy that changed nothing at all would have given exactly +0.0138 because the weight doubled. The whole behavioural response is +0.0012, an implied mean `v_norm` of 0.00410 to 0.00459, **twelve per cent more speed for twice the payment**. The weight is not kept
- [X] T049 [US3] For every comparison, state whether the difference exceeds T047's spread. A change that does not clear it is recorded as a change that made no measurable difference, not dropped (FR-021, US3 acceptance scenario 3)
  - **Changing a reward weight changes the scale of the metric, so T047's gate cannot be applied to the raw number.** Read raw, `ppo_car_jerk_lo` beats its baseline by +0.3378 and clears the gate; **+0.2824 of that is bookkeeping**, the same episodes charged at a fifth the scale. Reported without the correction it would have been a false positive
  - **The correction costs no runs, because FR-008 logs the six terms separately.** Each baseline summary rescores exactly as `cumulative_reward - reward_X + reward_X x (new / old)`. Rescored baselines: **-4.3310** for the jerk table, **-2.8294** for the wall table
  - Every comparison is therefore reported three ways: rescored cumulative reward, `reward/checkpoint` which neither candidate touches, and the raw number carrying its confound in writing
  - **`ppo_car_jerk_lo`: +0.0553 against the 0.19 gate, does not clear.** On `reward/checkpoint`, -0.0415 against a 0.0631 gate, also does not clear. Recorded as a change that made no measurable difference
  - **`ppo_car_wall_lo`: -0.3185 against the 0.19 gate, clears, in the worse direction.** The mechanism it was aimed at did work, end reasons moving from 46.8 / 39.9 to 51.4 / 35.4 per cent wall and stalled and holding across all four quarters, but the return fell. FR-021 wants the direction stated, not buried
  - **The `reward/checkpoint` gate is 0.0631**, two standard deviations of the run-mean spread of the same three baseline runs, sd 0.0315. Stated here because T047 named a gate only for cumulative reward
  - **The wall rescoring tightens the baseline spread to sd 0.0540 and the gate was deliberately not tightened with it.** The wall term carried most of the between-seed variance, so rescoring shrinks the baselines' scatter without saying anything about how noisy a different policy is, and `ppo_car_wall_lo`'s within-run sd of 0.5592 is the largest of the five 2M runs
  - **One near-gate reading is flagged rather than called.** `ppo_car_wall_lo`'s checkpoint reward by quarter runs 0.286, 0.237, 0.269, 0.339 where the baselines are flat near 0.25 and every earlier run in M3 fell. Inside its gate on the run mean, so not a result; T047's own remedy for a near-gate reading is a fourth run
  - Neither candidate completed a lap, so **T050 has no winner to promote to full budget**. What the pair establishes is negative and useful: the two weights T048 named are not what stops this policy driving, and the decomposition points instead at a step cost of -1.676 a run against a speed reward of +0.0069
- [X] T050 [US3] Run the winning configuration at full budget and record it as the candidate model, citing the reduced-budget spread as the context in which it won
  - **Closed as unsatisfiable at this reward table, not left open.** Three one-change candidates ran at the reduced budget and none cleared T047's gate in the better direction: `ppo_car_jerk_lo` +0.0553, `ppo_car_wall_lo` -0.3185 (clears, worse), `ppo_car_speed_hi` -0.0373. None completed a lap. There is no winner to promote to full budget, and running one anyway would spend 2.1 hours to restate a result the spread already fixes
  - **The reason is named rather than left as a gap.** A policy paid double for moving that moves twelve per cent more is not constrained by the size of the payment; it has not found the behaviour being paid for. That is exploration, and its remedies are of a different kind from a weight: a curriculum starting nearer a marker, a denser progress signal than one marker in twenty-four, or a warm start from the M4 behavioural-cloning policy. Any of those is a design change under Principle V and a new feature, not a Phase 5 tuning run
  - **Superseded note, kept for the record:** this was previously blocked as written after the first two candidates, because neither was kept and there was nothing to promote. Unblocked only if `ppo_car_speed_hi` clears the T047 gate in the better direction; if it does not, T050 is recorded as unsatisfiable at this reward table and the negative result stands as the Phase 5 outcome
  - A measurement note found while sizing the third candidate and **not yet resolved**: the trainer's `episode_length` (~530) and the number of times the step term is actually charged (`reward/step` over `StepCost`, ~1676) disagree by about 3.16x, and the ratio is not constant, running 1.95 to 4.01 across summaries. `config/ppo_car_spread.yaml` documents an episode as 6000 agent steps at 50 Hz, so the two should share a clock. The reward analysis does not depend on it, because the step and speed terms are accrued at the same call site (`DrivingAgent.AccrueStepTerms`) and their ratio is unaffected, but any statement about *episode length in seconds* does. Worth its own task in the FR-008 family

**Checkpoint**: every number this feature reports has a noise floor behind it.

---

## Phase 6: User Story 4 - The RL column of the final comparison (Priority: P2)

**Goal**: the learned driver described by the same measures as the human, imitation and scripted
columns, including where it loses.

**Independent Test**: produce the learned steering distribution over the held-out seeds and confirm
it uses the measures already used for the other columns.

- [X] T051 [US4] Implement `python/rl/report.py`: the steering command and the per-step `|delta steering|`, both resampled to `COMPARE_HZ` through `python.track.compare_drive.resample`, described with `python.eda.stats.describe`, the same function that described the human column in M1 and the BC column in M4. Difference each run separately before concatenating, because differencing across a seam between runs invents a jump no driver made
- [X] T052 [P] [US4] Create `python/tests/test_rl_report.py`: the per-run differencing, the resampling, and the refusal to average an empty lap time as zero
- [X] T053 [US4] Compare the learned steering distribution against the human distribution with a statistical test rather than a pair of histograms, matching what Principle IX and FR-024 require and what features 002 and 004 already did
- [X] T054 [US4] Place the learned column beside the recorded scripted and imitation columns: lap completion, the two smoothness measures kept separate, and the steering distribution. The scripted driver's figures to beat are 34 of 34 laps and a steering variance of 0.04994
- [X] T055 [US4] Write `results/rl/rl_steering.md` with the reproduction command at the top, the measured column, and **the losses stated plainly**. If the scripted driver wins on a measure, the measure is named and the result is reported (FR-024, US4 acceptance scenario 2, SC-007)
- [X] T056 [US4] Confirm every figure in that document resolves to a run id, and from the run id to a config revision, a curve CSV, a model file and an `EXPERIMENTS.md` row. A figure that resolves to none of them is not reproducible and the run is repeated (SC-004)
  - Done 2026-08-24. `python/rl/report.py` was a **docstring-only stub** from T001 - 37 lines of design-first specification, no code - so T051 implemented against a contract that was already written down, which is what Principle V is for
  - **A third prerequisite was missing, like the two T038-T044 turned up.** The learned driver had no per-step trace: `DriveLogger` existed and was self-contained, but nothing drove it. Wired to `DrivingAgent` and opened and closed **per run**, not per Play session. The session-level file `DriveLogger.OnEnable` writes has one monotonic `t` across all ten runs, so the seams are invisible; `compare_drive.load_drive_log` rejects that file outright, and the stub's own usage line asks for a *directory* of traces. Ten files of exactly 3,000 rows each, 60 s at 50 Hz
  - **T053 caveat, recorded rather than smoothed over.** `chi2_homogeneity` rejects both modes against the human column overwhelmingly - 34,464.4 deterministic and 14,591.8 sampling, against a critical value of 55.8 - and **the test was never going to say anything else** at 8,450 learned samples against 32,443 human ones. A statistic 260 times its critical value measures how much data there is, not how different the drivers are. The ordering is the only informative part, and it is a weak claim in a saturated regime. Named in `results/rl/rl_steering.md` rather than reported as a strong result
  - **The finding that needed the distribution rather than the lap count: the sampling policy's steering variance is 0.04557 against the scripted driver's 0.04994, nine per cent apart, while completing zero laps against 34 of 34.** Feature 005's research rejected steering variance as a standalone measure by argument; this measures it. A driver that never leaves the start can match a lapping driver's steering variance to within a tenth
  - **FR-026 restated on the distribution.** One set of weights, two drivers: identical outcomes, steering variance differing by a factor of 83 and mean |delta steer| by 290. Both modes carry the same systematic left bias, mean -0.115 and -0.122 against the human -0.021, so the bias is in the weights rather than in the sampling
  - T052 is `python/tests/test_rl_report.py`, nine tests. The seam guard is paired with a **counter-test** asserting that the wrong order really would produce a 2.0 jump, so the guard cannot pass because the fixture happened to be flat
  - Written up in `results/rl/rl_steering.md` with the reproduction command at the top and the losses stated plainly (T055). Every figure resolves to run id, config, curve, model, rows, traces and scene (T056)


**Checkpoint**: M5 has its learned column, in the shape the other columns already use.

---

## Phase 7: Polish and Cross-Cutting Concerns

- [ ] T057 Write the **measured** results back into `DESIGN.md` in a `docs:` commit: the throughput actually achieved, the spread actually measured, and the lap rates actually reached against the criterion section 5 states. Decided values went in at T001; only what had to be measured lands here
- [ ] T058 Add the M3 recipe to `README.md` in this feature, per Principle VI: the trainer command from the repository root, the single `Ctrl+C`, the curve export, and the evaluation sweep. The recipe changes in the same feature that makes it true
- [X] T059 Run all Unity EditMode tests through Window > General > Test Runner and confirm green
  - **109 tests, all passing**, run by the owner on 2026-08-24. This is the check that closes the reward-table work: T048 and the third candidate rewrote several `RewardModelTests` assertions against the constants instead of their arithmetic, and those had only been verified by evaluating the same expressions against the loaded assembly, which is not the same as running them as NUnit tests. The Test Runner cannot be driven over MCP - `TestRunnerApi` trips the bridge's user-interaction guard - so this task stays a human step
- [X] T060 Run the full `pytest` suite in `.venv` and `.venv-bc`, and record the counts against T004's baseline. Every new test is accounted for and no existing test regressed
  - Measured 2026-08-24: **`.venv` 338 passed, 3 skipped** in 216.1 s, and **`.venv-bc` 392 passed** in 218.8 s. Against T004's 323 passed / 3 skipped and 377 passed, that is **+15 in both and no regression**
  - **Re-measured after T052 added nine tests: `.venv` 347 passed, 3 skipped** in 201.7 s. Still no regression; the delta against the first measurement is exactly `test_rl_report.py`. `.venv-bc` is expected at 401 by the same argument and is re-run at merge
  - **The fifteen are accounted for exactly.** They are `python/tests/test_rl_curves.py`, this feature's own curve-export tests, which the file did not have at baseline: T004 was recorded in `af298f4` at 11:32 on 2026-08-17 and the file arrived in `0d2589d` at 13:02 the same day, ninety minutes later. The same delta in both environments is what a single shared test file predicts; a difference between them would have meant an environment-dependent test instead
  - `README.md`'s counts are now stale by fifteen in both environments and are corrected in T058, which is the task that owns the recipe
- [ ] T061 Close out the spec: mark each success criterion met or not met with the number that decides it, and record any that this feature could not reach and why
- [ ] T062 Audit what is staged before the merge: no `events.out.tfevents.*`, no `checkpoint*.pt`, no intermediate `.onnx` snapshots, and no `Library/`, `dataset/` or `.venv*/`. The committed model is LFS-routed and the curves are CSV
- [ ] T063 Work the merge checklist in `CONTRIBUTING.md`, confirm every new `Assets/` file has its `.meta`, and confirm each `.meta` sits in the same commit as its file

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 Setup**: T001 blocks everything. T002 to T005 are parallel with each other
- **Phase 2 Foundational**: blocks all user stories. Within it, the reward group (T006 to T008), the
  interface group (T009 to T012) and the seed group (T020, T021) are three independent tracks
- **Phase 3 US1**: needs all of Phase 2. T030 blocks T031
- **Phase 4 US2**: needs US1, because there is no model until something trains
- **Phase 5 US3**: needs US1. Independent of US2, since spread runs need no exported model
- **Phase 6 US4**: needs US2 for evaluation rows, and needs US3 if any figure it reports is a
  comparison between configurations
- **Phase 7 Polish**: last

### The dependency that decides whether the results mean anything

**T047 blocks T048, T049 and every comparative sentence in T055.** The spread is the noise floor,
and FR-021 turns on it. Nothing fails if it is skipped, which is exactly why features 004 and 005
both wrote it down as the task most likely to be lost.

### Within Phase 2

- T006, T007, T008 parallel: three files, no shared state
- T009 to T012 strictly sequential, and T012 is a gate rather than a formality
- T013 to T019 sequential, all in `DrivingAgent.cs`
- T020, T021 parallel with the agent work
- T022 to T026 sequential, ending in the scene, because a scene referencing a script that does not
  compile is a broken scene
- T027, T028 last, and they must agree with each other on the behaviour name and the vector size

### Parallel opportunities

```text
# Phase 1, after T001:
T002  results/rl/ and .gitignore
T003  python/rl/ skeleton
T004  test baseline
T005  Assets/Models/ and the LFS check

# Phase 2, three independent tracks:
Track A (reward):     T006, T007, T008
Track B (interface):  T009 -> T010 -> T011 -> T012
Track C (agent):      T013 -> T014 -> T015 -> T016 -> T017 -> T018 -> T019
Track D (area):       T020, T021 -> T022 -> T023 -> T024 -> T025 -> T026
Then:                 T027 -> T028
```

---

## Implementation Strategy

### MVP

Phase 1, Phase 2, Phase 3. That delivers a car that improves at driving through experience, in a
project whose topic is exactly that, and a curve that survives a clean clone.

**Stop and validate there.** If the reward curve rises while `reward/checkpoint` stays flat, the
reward is being farmed and no amount of further training fixes it. That is a Phase 3 finding and it
changes what Phase 5 is tuning.

### Incremental delivery

1. Setup and Foundational, then an episode runs
2. US1: something trains, and the run is recorded. Demo-able
3. US2: the model drives unattached on held-out tracks. This is the milestone gate
4. US3: tuning becomes attributable rather than anecdotal
5. US4: the M5 column

### What to be suspicious of

Four failure modes this feature is unusually exposed to:

- **Skipping T047.** Every later number becomes unfalsifiable, and nothing breaks to warn anyone
- **Tuning against the evaluation seeds.** T021 makes the training pool provable, but nothing stops
  a person from reading eval results and then changing a reward weight. The discipline is that
  tuning decisions cite reduced-budget training results, not evaluation results
- **Choosing `max_steps` before T030.** The design's 2M to 5M range predates any measurement of
  this environment, and `ENVIRONMENT.md` says so about the only throughput figure that exists
- **Letting T012 slide.** The interface extraction touches the code that produced feature 005's
  published rows. If the re-run row differs and the difference is explained rather than fixed, this
  feature has quietly invalidated the baseline it is measured against
