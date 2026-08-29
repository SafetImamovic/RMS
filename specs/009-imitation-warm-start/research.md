# Research: The imitation warm start

**Feature**: `009-imitation-warm-start` | **Spec**: `specs/009-imitation-warm-start/spec.md`
**Created**: 2026-08-28

Phase 0 for feature 009. Every finding below was read out of the code or the installed trainer
rather than recalled, and each one names the file and line it came from so the plan can be audited
against the source rather than against this document.

Two of these findings changed the design before a task was written. **R5** says the demonstration
file does not pair an observation with the command the expert gave for it, and **R8** says the
trainer's default `steps: 0` never decays the imitation loss. Both are handled in the plan.

---

## R1 - The delegation point exists and is one visibility change

`HeuristicDriver.Decide()` is at `HeuristicDriver.cs:804` and is `private`. It returns
`Vector2(steer, throttle)`, which is exactly the pair `DrivingAgent`'s continuous action space
carries, so FR-001's "call the existing implementation" is a visibility change plus a call, not a
refactor and not an extraction.

What `Decide()` reads: `agent.RayDistancesNorm` and the ray angles, `car.Profile`, and `car.SpeedMs`.
What it writes: the teaching-panel properties (`SteerMostOpen`, `SteerWeighted`, `RawSteer`,
`LastSteer`, `TargetSpeedMs`, `ForwardClearance`) and, in `Delayed` mode only, the reaction state
`_smoothed` and `_delay`.

**Consequence for the plan.** In the default reaction mode the method is a pure function of the
current observation and the current speed, so calling it from a different clock is safe. The
exception is `Delayed`, and R4 makes that a constraint rather than a caveat.

## R2 - The cadence gate is structural, not a risk to be watched

The spec named the cadence as a gate. It is stronger than that: **the recorder physically cannot
record faster than the decision period.**

`Agent.SendInfo` (`Agent.cs:1372`) calls `SendInfoToBrain` only when `m_RequestDecision` is set, and
the demonstration write sits inside `SendInfoToBrain` at `Agent.cs:1140`. With `DecisionPeriod: 4`
the agent requests a decision every fourth physics step, so a `.demo` recorded from this project is
a **12.5 Hz** sampling of a driver that decides at 50 Hz, and no recorder setting changes that.

**Consequence for the plan.** This is the correct sampling rate, because the policy that will be
trained also acts at 12.5 Hz, so the demonstration and the policy share a clock. What is not
guaranteed is that the expert still completes laps at that clock, which is what FR-004 measures and
what Phase 1 gates on.

## R3 - The throttle is the cadence risk, and the steering is not

Feature 005's control law splits cleanly at the decision period.

**Steering costs nothing to subsample.** Under the default reaction mode the steering command is
`RayControllers.WeightedAverage` over the current 13 ray distances, clamped
(`HeuristicDriver.cs:815-831`). It carries no state between steps, so sampling it every fourth step
gives the same command that step would have produced anyway. The only loss is that the three steps
in between hold a command that is up to 60 ms stale.

**The throttle is bang-bang and that is where laps can be lost.** `Decide()` sets throttle to
`+1`, `-1` or `0` from the speed error against a `0.25 m/s` deadband
(`HeuristicDriver.cs:843-856`). Held for four physics steps at `brakeMs2` around `5.85 m/s^2`, the
speed can move about `5.85 * 0.08 = 0.47 m/s` in one decision, which is **1.9 times the deadband**.
A bang-bang controller whose actuation interval exceeds its own deadband oscillates around the
target rather than holding it.

**Consequence for the plan.** The Phase 1 measurement is not a formality. If lap completion falls,
the first thing to read is speed tracking rather than steering, and the failure is a known property
of the controller rather than a mystery. FR-006 pins `DecisionPeriod`, so the response to a
collapse is to report it and stop, exactly as the spec says.

## R4 - `Delayed` reaction mode is incompatible with the agent's clock

`ApplyReaction` (`HeuristicDriver.cs:318`) sizes its delay ring as
`reactionTimeS / Time.fixedDeltaTime` and advances it **once per call**. Called from
`HeuristicDriver.FixedUpdate` that is once per physics step; called from `DrivingAgent.Heuristic`
it is once per decision. The same `reactionTimeS` therefore becomes a **four times longer** delay
in the agent's action path, and the demonstration would be of a slower driver than the one that
produced 34 of 34.

The default is `ReactionMode.Immediate` (`HeuristicDriver.cs:134`), which is memoryless and has no
such problem.

**A provenance gap that has to be closed first.** `results/heuristic/runs_*.csv` carries 16 columns
(`seed,controller,ray_count,ray_fov_deg,ray_length_m,completed_lap,lap_time_s,checkpoints_awarded,
checkpoints_total,checkpoints_skipped,wall_contacts,end_reason,steer_p95_dsteer,
steer_sign_changes_per_s,time_scale,duration_s`) and **none of them records the reaction mode**.
The 34 of 34 figure cannot be shown to have been measured in `Immediate` mode from the committed
CSV alone.

**Consequence for the plan.** Recording is done in `Immediate` mode, the mode is stated in the
recording procedure, and the Phase 1 measurement re-establishes the baseline in the mode actually
used rather than inheriting a number whose configuration is not written down.

## R5 - The demonstration file pairs an observation with the previous decision's command

This is the finding that most affects what the run will learn, and it is a property of ML-Agents
rather than of this project.

The chain, in order:

1. `Agent.SendInfoToBrain` calls `demoWriter.Record(m_Info, sensors)` at `Agent.cs:1140`, **before**
   the brain has decided anything this step.
2. `DecideAction` (`Agent.cs:1405`) runs after `SendInfo` in the academy order and only then copies
   the new action into `m_Info` via `m_Info.CopyActions(actions)` at `Agent.cs:1412`.
3. `ToInfoActionPairProto` (`GrpcExtensions.cs:42-57`) fills the proto's action from
   `ai.storedActions`, which at record time is still the action from the previous decision.
4. On the Python side, `make_demo_buffer` (`demo_loader.py:33-90`) pairs `current_obs` from
   `pair_infos[idx]` with `current_pair_info.action_info` from the **same** index.

So the buffer that behavioural cloning trains on holds `(obs_t, a_{t-1})`: at `DecisionPeriod: 4`
the expert command is shifted **80 ms** later than the observation that caused it.

**This is not configurable without patching the package**, and patching a package under
`Library/PackageCache` is not reproducible from a clean clone.

**Consequence for the plan.** The lag is accepted and written down rather than worked around, for
three reasons. It is the same pairing every ML-Agents imitation example trains on. FR-006 pins the
decision period, so it cannot be shrunk. And it does not affect the Phase 1 lap measurement at all,
because the car is driven by `OnActionReceived` applying the action decided on that same step; only
the recorded file carries the shift. It is named in Complexity Tracking and it is the first
candidate explanation if the imitation loss falls while behaviour does not follow it.

## R6 - Two writers to `ScriptedMove`, both already gated

`HeuristicDriver.FixedUpdate` writes `car.ScriptedMove = move` at `HeuristicDriver.cs:633`, guarded
by `engaged && !blocked && Outcome == EndReason.Running` (`HeuristicDriver.cs:606`).
`DrivingAgent.OnActionReceived` writes it at `DrivingAgent.cs:381`, guarded by `_engaged`. Feature
005's FR-004 forbids both writing in the same frame.

The existing release path is the one to reuse: when `shouldDrive` goes false the driver clears
`ScriptedMove` to `null` rather than holding a stale command (`HeuristicDriver.cs:620-627`), and
`SetEngaged` (`HeuristicDriver.cs:514`) is the public entry point for that.

**Consequence for the plan.** The design is: `HeuristicDriver` stays on the object as the
implementation, `SetEngaged(false)` keeps it from writing, and `DrivingAgent` is the only writer
while it is the decision source. No new component, no new field to arbitrate ownership.

## R7 - `behavioral_cloning` is present, validated, and its shape is fixed

`BehavioralCloningSettings` (`settings.py:145-153`) carries `demo_path` (required), `steps` (0),
`strength` (1.0), `samples_per_update` (0), `num_epoch` (None) and `batch_size` (None), which
matches the spec's assumption.

`demo_to_buffer` (`demo_loader.py:105`) checks the demo's `action_spec` and observation count
against the policy's and raises rather than training on a mismatch, so a demo recorded from a
different observation layout fails loudly. That is a free contract test.

The loss is plain MSE on the continuous actions
(`components/bc/module.py:_behavioral_cloning_loss`), and the module reports
`Losses/Pretraining Loss` to TensorBoard, which gives the feature a measurable signal that the
warm start is actually being applied rather than silently absent.

## R8 - `steps: 0` never decays the imitation loss, and the default would measure the wrong thing

In `BCModule.__init__` (`components/bc/module.py:33-41`), `steps` becomes `_anneal_steps`, and the
schedule is `LINEAR` only `if self._anneal_steps > 0`, otherwise `CONSTANT`. The module stops
updating when `self.current_lr <= 1e-10` (`module.py:70`), and `current_lr` is only ever reduced by
that schedule (`module.py:99`).

**So with the default `steps: 0` the behavioural cloning loss is applied at full strength for all
5,000,000 steps.** The spec's edge case, that too large a value makes the run measure imitation
rather than reinforcement, is the default, not a risk at the edge of the range.

`samples_per_update: 0` has a matching effect on cost: `max_batches` is then 0 and `num_batches`
becomes `possible_batches`, so **every** update iterates the whole demonstration buffer
(`module.py:79-89`). That lands directly on SC-009's throughput comparison against 903 and 927
steps per second.

**Consequence for the plan.** Both values are set explicitly, chosen before the run, and recorded in
the `EXPERIMENTS.md` row, as the spec requires. Neither is tuned after seeing the result.

## R9 - The `.demo` can be committed, and LFS already covers the pattern class

`.gitattributes:28-53` already routes binary asset types through LFS and `git-lfs/3.6.0` is
installed. `.demo` is not yet listed. A demonstration of a few thousand decision steps of a 19 value
observation and a 2 value action is small, on the order of a megabyte, which is the same order as
the BC checkpoint already committed through LFS for the M4 gate.

**Consequence for the plan.** FR-007 is satisfied the honest way: add `*.demo` to the LFS patterns
and commit the file, so the run is reproducible from a clean clone rather than from a procedure
someone has to re-execute. The committed seed list stays alongside it regardless, because it is
what makes the file's provenance auditable.

## R10 - No object in this project carries both the agent and the scripted driver

Found while writing the Phase 2 tasks, and it corrects the plan's first draft.

`DrivingAgent` (guid `9aa5015d...`) appears in exactly two places: `Prefabs/TrainingArea.prefab`
and `Scenes/Evaluation.unity`. `HeuristicDriver` (guid `9473cf4b...`) appears in exactly two other
places: `Scenes/HeuristicTrack.unity` and `Scenes/HeuristicWeighted.unity`. **The intersection is
empty.** Feature 005 built its driver in its own scenes and feature 006 built the agent in the
training prefab, and nothing since has needed them in the same place.

Inside `TrainingArea.prefab` the three components that matter are all on one GameObject named
`Car` (fileID `1027774588058591962`): `CarController`, `CarAgent` and `DrivingAgent`. So
`HeuristicDriver.Awake`, which resolves `car` with `GetComponent<CarController>()` and `agent` with
`GetComponentInChildren<CarAgent>()`, would bind correctly if the component were added to that
object.

**But the training scene is the wrong place to add it, for a reason that has nothing to do with the
scene lock.** `HeuristicDriver.Awake` (`HeuristicDriver.cs:453-461`) resolves `ring`, `placer` and
`track` with `FindAnyObjectByType`. The training scene holds **twelve** areas, each with its own
ring, placer and track, so twelve drivers would each bind to an arbitrary one and eleven of them
would be reading another area's track. `Start` then calls `BeginRun` unconditionally
(`HeuristicDriver.cs:463-470`), so the bookkeeping starts whether or not the driver is engaged.

**Consequence for the plan.** The demonstration is recorded in a **dedicated single-area scene**
rather than by adding `HeuristicDriver` to the training prefab. That scene carries one
`TrainingArea` instance, a `HeuristicDriver` on the `Car` object with `ring`, `placer` and `track`
**wired explicitly** rather than found, and the `DemonstrationRecorder`. Three things follow:
`TrainingArea.prefab` is not modified at all, so the guarantee that an unedited prefab trains
exactly as feature 008 left it is kept by construction rather than by a default value; the
`FindAnyObjectByType` ambiguity cannot arise, because there is one of everything; and the per-seed
recording sweep runs in a scene built for it instead of in a scene built for twelve parallel
learners.

`engaged` already defaults to false (`HeuristicDriver.cs:63`, no initializer), which is what makes
the driver safe to have in a scene at all. That is now a secondary safeguard rather than the
primary one.

---

## What research changed

| Finding | What it changed |
|---|---|
| R5, the recorded pair is `(obs_t, a_{t-1})` | Accepted and documented rather than engineered around; named as the first suspect if the loss falls without behaviour following |
| R8, `steps: 0` means no decay | `steps` and `samples_per_update` are now explicit required decisions in Phase 3 rather than defaults |
| R3, the throttle is the cadence risk | Phase 1 reads speed tracking, not just lap counts, so a collapse is attributable |
| R4, no reaction mode in the committed CSV | Phase 1 re-establishes the baseline in the stated mode instead of inheriting 34 of 34 |
| R1, `Decide()` is private and pure | Confirms FR-001 costs one visibility change, so the "no duplicate baseline" comment stays true |
| R10, no object carries both components | The demonstration gets its own single-area scene; `TrainingArea.prefab` is no longer touched at all |
