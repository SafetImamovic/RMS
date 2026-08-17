# Phase 0 Research: PPO Reinforcement Learning Driver

**Feature**: `006-ppo-rl-driver` | **Date**: 2026-08-17

Every item here was resolved against the repository and the installed ML-Agents package rather
than from memory. Package paths refer to
`unity/SelfDrivingSim/Library/PackageCache/com.unity.ml-agents@f1016d3568fd`.

---

## R1: Where the learned agent lives, and what it is allowed to touch

**Decision.** A new `DrivingAgent : Unity.MLAgents.Agent` component sits on the car alongside
`CarAgent`. It reads `CarAgent.Observations` and writes `CarController.ScriptedMove`, the same
field `HeuristicDriver` writes. `CarAgent.cs` is not modified.

**Rationale.** The plumbing is already in place and verified:

- `SelfDrivingSim.asmdef` already lists `Unity.ML-Agents` in its references, so the assembly
  compiles against the package today with no project change.
- `com.unity.ml-agents` 4.0.3 is already in `Packages/manifest.json`, pinned, and its
  end-to-end bridge was verified on 2026-07-26 (`ENVIRONMENT.md`: Communicator API 1.5.0 matched,
  3DBall trained, `.onnx` exported).
- `CarAgent` already exposes exactly the vector the design declares:
  `ObservationCount => rayCount + SelfStateCount` with `SelfStateCount = 6`, and
  `Observations` documented as "the whole observation vector in the order M3 will feed it to the
  network". The wrapping was anticipated when that class was written.
- Writing through `CarController.ScriptedMove` means the human, the scripted driver and the
  network all reach the wheels through one path. A learned driver with its own control path would
  make every difference in the M5 comparison ambiguous between policy and plumbing.

**Alternatives considered.** Making `CarAgent` itself an `Agent` subclass. Rejected: `CarAgent`
is the sensing for all three drivers, and a scene playing the scripted driver would then carry an
ML-Agents agent that requests decisions from nothing. Feature 005's comment at `CarAgent.cs:33`
already names this trap.

---

## R2: Decision rate, and the threshold that depends on it

**Decision.** `DecisionRequester` with `DecisionPeriod = 4` and `TakeActionsBetweenDecisions =
true`, giving 12.5 decisions per second against the 50 Hz physics clock. The steering-change
penalty is evaluated on the change in the commanded steering **between decisions**, and the
decision rate is recorded on every run record and in the design writeback.

**Rationale.** Three fixed numbers meet here:

- `ProjectSettings/TimeManager.asset` sets `Fixed Timestep: 0.02`, so physics is 50 Hz and
  `Academy` steps in `FixedUpdate` (`Runtime/Academy.cs:29`, `AcademyFixedUpdateStepper`).
- `python/track/config.py:188` sets `COMPARE_HZ = 14.08`, the median track1 frame rate, and every
  smoothness figure in features 002, 004 and 005 is computed on that grid.
- `DESIGN.md` 4.5 sets the steering-change penalty threshold at 0.55, which is the P95 of
  `|delta steering|` **in the dataset, at 14.08 Hz**.

50 does not divide by 14.08. `DecisionPeriod = 4` gives 12.5 Hz, the closest achievable rate below
the dataset rate; `DecisionPeriod = 3` gives 16.67 Hz. Deciding faster than the human recording
would let the network make more control changes per second than the distribution the threshold was
measured from, which quietly makes the penalty easier to avoid. Deciding at 12.5 Hz makes each
step slightly longer than a dataset step, so a given trajectory produces slightly larger per-step
deltas, which biases the penalty toward being stricter rather than looser.

Feature 005 hit the same class of error and recorded it: `SteerSmoothness.cs:111` notes that a
figure computed at the physics rate and a figure computed at `COMPARE_HZ` are different numbers
for the same driving. A threshold without its rate is not a threshold.

**Alternatives considered.** Changing the physics timestep to make 14.08 Hz divide evenly.
Rejected outright: the vehicle is a WheelCollider model tuned and measured at 0.02, and every
number features 003 and 005 published came from that timestep. Rescaling 0.55 to the 12.5 Hz grid
was considered and rejected for this feature: the rescaling factor is not derivable without
re-deriving the P95 from the dataset at a second rate, which is M1 work, and the bias runs in the
safe direction.

---

## R3: Detecting wall contact without editing feature 005

**Decision.** A new `WallSensor` component on the car owns `OnCollisionEnter`, counts barrier
contacts and exposes a rising-edge flag. `HeuristicDriver` keeps its own detection unchanged.

**Rationale.** `HeuristicDriver.cs:1121-1132` already implements barrier detection and increments
`WallContacts`, and `HeuristicDriver.cs:983` ends a run on it. That code produced every row in
`results/heuristic/`. Unity delivers `OnCollisionEnter` to every `MonoBehaviour` on the object, so
a second component can count the same collisions without the first one knowing. The two counters
are independent by construction, which is what keeps the scripted column reproducible.

**Alternatives considered.** Extracting the detection out of `HeuristicDriver` into a shared
component and having the scripted driver use it. Cleaner on paper, and rejected: it changes the
code path that produced published numbers, for a saving of about fifteen lines. The duplication is
deliberate and is stated in the design writeback so nobody later "fixes" it.

---

## R4: Turning checkpoint progress into reward without putting reward in the ring

**Decision.** `DrivingAgent` polls `CheckpointRing` each physics step and converts deltas into
reward: an increase in `AwardedCount` pays the progress reward, a rising edge on `WrongWay` pays
the wrong-direction penalty. `CheckpointRing` is not modified.

**Rationale.** `CheckpointRing.cs:10` states it directly: "There is no reward logic here and there
must not be." The class already exposes everything needed as public state: `AwardedCount`,
`LapCount`, `NextIndex`, `WrongWay`, `SkippedContactCount`, `LastContactIndex`. FR-009 requires the
wrong-direction rule to be the ring's own detection rather than a second definition, and polling
its flag is exactly that.

The ring also already solved the trap that would otherwise break every episode reset: feature 003
found that placing the car **on** a marker fires `OnTriggerEnter` for the teleport itself, which
would report wrong-way before the car moved, and the ring now tracks a straddled marker
(`StraddlingIndex`) and ignores it until exit. Episode resets place the car on a marker, so this
feature depends on that fix and must not regress it.

**Alternatives considered.** Adding C# events to the ring. Rejected: it is a change to frozen
code (FR-028) for no gain, since polling at the physics rate cannot miss a transition that lasts a
step.

---

## R5: When an episode ends, and how long it may run

**Decision.** Three terminal conditions, matching FR-011:

| Condition | Call | Reward |
|---|---|---|
| Barrier contact | `EndEpisode()` | `-5.0` applied first |
| Required laps completed | `EndEpisode()` | the last checkpoint reward only |
| Step limit reached | `Agent.MaxStep`, which raises `EpisodeInterrupted` semantics internally | nothing extra |

`MaxStep = 6000` agent steps, which is 120 s at 50 Hz.

**Rationale.** The scripted driver's 34 completed laps in
`results/heuristic/runs_2026-08-16_17-26-51.csv` have lap times between 25.28 s and 27.52 s, mean
26.50 s. Three laps at that pace is roughly 80 s, so 120 s leaves a margin of half again for a
policy that is slower than the heuristic without letting a stalled episode run indefinitely.

The distinction between `EndEpisode` and the step limit matters for learning rather than for
bookkeeping. `Agent.cs:548` distinguishes `DoneReason.MaxStepReached`, and the trainer bootstraps
the value function differently for a truncated episode than for a terminal one. Ending a
time-limited episode as if the car had crashed would teach the policy that surviving 120 s is
punished.

**Alternatives considered.** No step limit, relying on the per-step cost to make loitering
unattractive. Rejected by the spec's own edge case: a car that creeps forward slowly still ends no
episode, and one stuck agent in one area starves that area for the rest of the run.

---

## R6: How an area gets a different track, and how often

**Decision.** Each `TrainingArea` builds one seed at scene start. An `AreaScheduler` rotates that
area's seed through the 34 training seeds every `K` episodes, disabling the area's agent for the
few frames the rebuild needs. `K` is a config field, and the first implementation task measures
`TrackBuilder.Build()` cost so `K` is chosen from a number rather than a guess.

**Rationale.** The rebuild is not instantaneous and, more importantly, is not synchronous.
`SweepRunner.SwapTrack` (`SweepRunner.cs:461`) is a coroutine for a reason its own comments give:
after `track.Clear()` it yields a frame because "the old colliders actually go away here", and
after `track.Build()` it waits for a fixed update because "the new ones register here". A rebuild
therefore spans at least three frames.

`Agent.OnEpisodeBegin` is a synchronous callback. Rebuilding a track inside it would either read
colliders that do not exist yet, or require blocking, and the first physics step of the new episode
would sense a track that is not there. Rotating between episodes, with the agent disabled across
the swap, is the version that respects both clocks.

Rotation is required rather than optional because of the owner's decision recorded in the spec:
episodes draw from all 34 training seeds (FR-012). With 8 to 16 areas, no single scene layout
covers 34 seeds without rotation.

**Alternatives considered.** One fixed seed per area for the whole run, covering 12 of 34 seeds.
Rejected: it is the "small fixed subset" option the owner declined, and the held-out result would
carry that caveat. Pre-instantiating all 34 tracks in one scene was rejected on memory: each track
carries a surface mesh and two barrier meshes over 2000 centre-line samples.

---

## R7: Independent environment copies

**Decision.** A `TrainingArea` prefab holding its own `TrackBuilder`, `CheckpointRing`,
`StartPlacer`, car, `CarAgent`, `WallSensor` and `DrivingAgent`, instanced by hand into the
training scene at a separation of 300 m. No use of `TrainingAreaReplicator`.

**Rationale.** Independence is already structural rather than something to be built:

- `TrackBuilder.Build()` parents everything it creates under its own transform
  (`TrackBuilder.cs:104-105`, `SetParent(transform, worldPositionStays: false)`), so an area
  offset in the scene carries its whole track with it.
- A repository-wide search for mutable static state in `Assets/Scripts` returns one hit, and it is
  a comment in `HeuristicDriver.cs:780` explaining that the run record's file handle is static and
  does not survive a domain reload. Nothing else shares state between instances.

The separation figure comes from the sensing: rays are physics raycasts of 20 m, and a generated
track is roughly 200 m of centre line, so a 300 m grid pitch keeps one area's barriers outside
every other area's sensing range with room to spare. Cheaper than a physics layer per area, and
visible in the scene view, which matters when something goes wrong.

`TrainingAreaReplicator` exists in the package (`Runtime/Areas/TrainingAreaReplicator.cs`) and
does grid replication, but its `buildOnly` field defaults to `true`, meaning it replicates in a
player build and not in editor play. This project trains in the editor, as feature 005 also ran its
sweep in the editor. Using the replicator would mean either flipping that flag or moving to player
builds, and neither buys anything a prefab instanced twelve times does not.

**Alternatives considered.** One area per physics layer with layer-filtered raycasts. Rejected:
it changes the raycast mask, which is sensing, which is frozen by FR-028.

---

## R8: The trainer configuration and the throughput budget

**Decision.** `config/ppo_car.yaml`, committed, holding the hyperparameters `DESIGN.md` 5 already
names: batch 2048, buffer 20480, learning rate 3e-4 with linear decay, two hidden layers of 256,
gamma 0.99. `max_steps` is set after a pilot run measures throughput, not before.

**Rationale.** `ENVIRONMENT.md` records the only throughput number this project has: 432,000 steps
in 614 s, about 700 steps/s, with 12 parallel agents on 3DBall, and it explicitly says to treat
that as an upper bound because "our car environment (WheelCollider physics + raycast sensors) will
be substantially slower per step". SC-006 allows 12 hours. At 100 steps/s a 12-hour run reaches
4.3M steps; at 30 steps/s it reaches 1.3M. The spread between those is too wide to pick `max_steps`
from a table, and picking it wrong wastes a night either way.

The constitution requires the config to be pinned (Principle VI) and `ENVIRONMENT.md` records that
`mlagents-learn` writes `results/` relative to the working directory, so runs are launched from the
repository root and land in the project's own `results/`.

**Alternatives considered.** Taking `max_steps` from the design's 2M to 5M range directly.
Rejected as the same class of mistake this feature is meant to avoid: a number chosen before
anything was measured, defended afterwards.

---

## R9: Measuring the run-to-run spread when a run costs a night

**Decision.** The spread is measured from three runs of one identical configuration, differing
only in the trainer seed, at a **reduced budget** chosen so three of them fit in one working day.
Every configuration comparison in this feature is then made at that same reduced budget. Only the
configuration that wins there is run at full budget, and the full-budget result is reported as a
single run with the reduced-budget spread cited as its context.

**Rationale.** FR-020 requires the spread before any comparison, and features 004 (R13) and 005
(T027) both established that the noise floor comes first. But their noise floors were cheap: a BC
run is about five minutes, a heuristic run is seconds. A PPO run at full budget is a night, and
three of them plus the comparisons they enable would consume the milestone.

The reduced budget keeps the discipline and prices it honestly. What it costs is the claim that
the spread at 500k steps bounds the spread at 3M steps, which is not guaranteed and must be stated
rather than assumed: policies that are still improving are noisier than converged ones, so a
reduced-budget spread is likely an over-estimate of a converged spread, which is the safe
direction for a "does this difference clear the noise" test.

**Alternatives considered.** Asserting determinism from a fixed seed. Rejected for the reason
feature 004 rejected it: even with the trainer seed fixed, the environment is a physics simulation
running under a variable frame budget, and 004 measured a non-zero spread across byte-identical
BC configurations that had far fewer moving parts.

---

## R10: Keeping the curves in the repository when the repository ignores them

**Decision.** `python/rl/export_curves.py` reads the trainer's event files and writes one CSV per
run under `results/rl/curves/`, which is committed. The raw event files and checkpoints stay
ignored.

**Rationale.** This is a direct conflict between FR-018 and the repository as it stands.
`.gitignore` lines 46 to 48 ignore `results/tensorboard/`, `results/*/events.out.tfevents.*` and
`results/*/checkpoint*.pt`. FR-018 requires the recorded curves to exist in a clean clone. Both are
right: event files are binary, grow with the run, and are exactly what a repository should not
carry, while a milestone whose evidence is "there was a curve on my machine" is not reproducible.

A distilled CSV of the scalar series, being the cumulative reward, the episode length, the policy
loss and the per-term reward statistics, is small, diffable, and is what every report and plot
actually consumes. The pattern already exists in this project: feature 004 committed
`results/bc/train_*.log` and the comparison Markdown while the checkpoints stayed out.

**Alternatives considered.** Force-adding the event files. Rejected: binary blobs in history that
nothing reads directly. Reading the trainer's `run_logs/timers.json` instead of the event files was
rejected because it carries timing, not learning curves.

---

## R11: The model file

**Decision.** The exported `.onnx` is committed through Git LFS under
`unity/SelfDrivingSim/Assets/Models/`, named for the run that produced it, with the trainer's
step-suffixed filename preserved.

**Rationale.** `.gitattributes:50` already routes `*.onnx` through LFS, and the constitution's
technology constraints already require it. `ENVIRONMENT.md` records that the export happens on the
first `Ctrl+C` and that a second one skips it, which is an operational detail the quickstart has to
carry because losing a night's training to a double interrupt is a real outcome.

Keeping the trainer's step suffix in the name is what ties the file to the run and the log entry
without a separate mapping file.

---

## R12: Whether the exported model drives the way the trained policy did

**Decision.** Evaluation runs with `BehaviorParameters.DeterministicInference` enabled, and FR-026
is satisfied by evaluating the same policy both ways on the same held-out seeds and reporting the
difference as a number.

**Rationale.** The gap is real and has a name in the package.
`Runtime/Policies/BehaviorParameters.cs:245` constructs a `SentisPolicy` with an
`m_DeterministicInference` flag. During training PPO samples from the policy distribution; at
inference the model can either sample or take the distribution's mean. The same weights therefore
produce two different drivers, and "the model drives worse than training suggested" is the
predictable result of not knowing which one is being watched.

Deterministic inference is the right default for the M5 column, because the scripted driver is
deterministic and the imitation model is deterministic, so a stochastic learned driver would be the
only column whose spread came from its own sampling.

**Alternatives considered.** Reporting only the deterministic figure. Rejected: FR-026 asks for the
difference, and the difference is cheap to obtain once the harness runs one of them.

---

## R13: Evaluating a learned policy through feature 005's sweep runner

**Decision.** Extract an `IRunDriver` interface covering what `SweepRunner` uses of a driver:
engage and disengage, begin a run, report finished with a reason, and hand over the run record
fields. `HeuristicDriver` implements it with no behaviour change; `DrivingAgent` implements it for
inference runs. `SweepRunner`'s serialized field becomes the interface.

**Rationale.** `SweepRunner` already does everything the evaluation needs and nothing it does not:
it loads `results/tracks/seed_split.json` and can select the eval half (`SeedSet` enum), swaps
tracks in one play session, applies a time scale, and writes `RunRecord` rows. `RunRecord` already
carries exactly the fields FR-022 lists, plus the two smoothness measures with the comment at
`RunRecord.cs` that they are "never combined".

The alternative is a second runner, and the cost of that is a second definition of what a run is,
diverging the first time either is fixed. FR-023 is specifically a requirement that the two
columns come from one place.

The risk is that touching `HeuristicDriver` changes published results. It is bounded by making the
change mechanical, by the existing EditMode tests, and by a verification task that re-runs one
recorded seed and compares the row.

**Alternatives considered.** Having `DrivingAgent` masquerade as a `HeuristicDriver` subclass.
Rejected: inheritance from a 1138-line MonoBehaviour to reuse four call sites.

---

## R14: Making the reward attributable, and checking it is not farmable

**Decision.** Each reward term is a static function in `RewardModel`, called by `DrivingAgent`,
accumulated per episode into a breakdown, and reported through
`Academy.Instance.StatsRecorder.Add` under one key per term. EditMode tests cover the terms
individually and cover two adversarial cases explicitly: a car circling in open track, and a car
standing still.

**Rationale.** FR-008 requires attribution, and the package supports it directly:
`Runtime/StatsRecorder.cs:41` exposes `Add`, and anything added there appears in TensorBoard beside
the built-in series. Without it, the only visible signal is the total, and a total that rises while
the checkpoint term stays flat is indistinguishable from progress unless the terms are separated.

The adversarial cases are not hypothetical. The reward pays `+0.001 x v_norm` for forward speed
regardless of direction of travel along the track, so a policy that drives in circles in a wide
part of the surface collects it. The arithmetic decides whether that is stable: the per-step cost
is `-0.001` and the speed term is at most `+0.001`, so circling nets at best zero per step against
`+1.0` per checkpoint, which is the design's own defence and is worth stating as a test rather than
as a hope.

**Alternatives considered.** Logging the breakdown to a CSV only. Rejected: the breakdown is most
useful while the run is in progress, which is exactly when TensorBoard is open and the CSV has not
been written.

---

## R15: Keeping the evaluation seeds out of training

**Decision.** The training scene sources seeds from the `train` half of
`results/tracks/seed_split.json` through a single code path, and an EditMode test asserts that the
training seed pool and the evaluation seed pool are disjoint and that the training pool matches the
committed file.

**Rationale.** SC-008 requires this to be demonstrable from the recorded configuration alone. The
split file already records what is needed and already claims disjointness: it carries 34 accepted
training seeds, 10 evaluation seeds, and a `disjoint: true` field. `SweepRunner` already parses it
(`SeedSplitFile` at `SweepRunner.cs:618`), so the parsing exists and only the assertion is new.

A test is the right instrument rather than a review, because the failure mode is silent: a training
run that quietly included seed 1003 would produce a better evaluation number and no error.

---

## Resolved: what this research changes in the design document

Three items go into `DESIGN.md` before the code that depends on them, per Principle V:

1. **Section 4.5** gains the decision rate and its relationship to the 0.55 threshold (R2), and the
   note that wall-contact counting for the learned agent is a separate component from the scripted
   driver's, deliberately duplicated (R3).
2. **Section 5** gains the training-area layout with its 300 m separation and its reason (R7), the
   seed rotation policy (R6), and the statement that `max_steps` is set from a measured throughput
   rather than from the current 2M to 5M range (R8).
3. **Section 5** also gains the reduced-budget spread protocol (R9), because it is a claim about
   what this project's numbers mean and not an implementation detail.
