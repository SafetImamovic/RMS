# Research: Heuristic Ray-Following Driver

Phase 0. Every unknown in the plan's Technical Context resolved, with the alternative that was
rejected and why. Nothing here is a preference; each decision is either forced by an arithmetic
consequence of numbers already in the repository, or recorded plainly as a choice.

Figures come from `unity/SelfDrivingSim/Assets/Tracks/vehicle_profile.json`,
`python/track/config.py` and `results/tracks/seed_split.json`, all computed 2026-08-09.

---

## R1 - Why longitudinal control is not optional

- **Simply:** flat throttle cannot hold the corners this generator produces, so a steering-only
  driver would fail for a reason that has nothing to do with its steering.

The lateral grip limit gives a cornering speed of `sqrt(a_lat * r)`. Taking `a_lat = 5.85 m/s^2`,
the braking figure measured in T024:

| Corner radius | Fastest the car can hold it | As a fraction of v_max |
|---|---|---|
| 6.97 m, the generator's radius floor | 6.39 m/s | 0.639 |
| 10 m | 7.65 m/s | 0.765 |
| 17.1 m | 10.0 m/s | 1.000 |
| 20 m | 10.82 m/s | above v_max, so grip is not the limit |

**The crossover is 17.1 m.** Below that radius, a car at top speed is asking for more lateral
acceleration than the tyres can supply. The generator's floor is 6.97 m, less than half the
crossover, and C9 records that these tracks curve everywhere and contain no straights. A driver
holding full throttle therefore understeers into a barrier on any corner tighter than 17.1 m, and
most corners are.

- **Decision:** the driver commands a target speed derived from its own steering command, not a
  fixed throttle. Having chosen a steering angle `delta`, the implied radius is
  `R = wheelbase / tan(delta * steer_max_rad)`, and the target speed is `sqrt(a_lat * R)` capped
  at `v_max`. Throttle and brake follow from the error between target and actual speed.
- **Rationale:** it uses the steering decision the driver has already made, so it introduces no
  new sensing and no tuned constant. `a_lat`, `wheelbase`, `steer_max` and `v_max` all come from
  the vehicle profile, so retuning the car retunes the driver, which is what the spec's
  assumptions require.
- **Alternatives rejected:** a fixed throttle, which fails as shown above. A speed proportional to
  the forward ray distance, which is tunable-looking and would need a constant chosen by eye; it
  also confuses "the track is clear ahead" with "the corner is gentle", and on a tight corner with
  a long sightline across the apex those are opposite.

## R2 - Why the naive controller will chatter, stated as a prediction before it is built

- **Simply:** the argmax controller can only ask for five distinct steering values, and the two
  nearest are 0.6 apart on a scale that runs from -1 to 1.

The rays sit 15 degrees apart, `180 / (13 - 1)`. Steering saturates at 25 degrees. So a controller
that steers toward the chosen ray's angle can only command `angle / 25`:

| Chosen ray | Angle | Commanded steer |
|---|---|---|
| 6 | 0 deg | 0.00 |
| 5 or 7 | ±15 deg | ±0.60 |
| 4 or 8 | ±30 deg | ±1.20, clamped to ±1.00 |
| anything further out | ±45 deg and beyond | clamped to ±1.00 |

**Three reachable magnitudes: 0, 0.6, 1.0.** Every steering angle between them is unreachable, so
the controller cannot hold a steady mid-corner line. It must alternate between two of those
values, which is the chatter.

The rate limiter shapes it rather than removing it. `steer_rate_norm_per_s` is 3.7, which is 0.074
per 50 Hz step, so traversing one 0.6 step takes 8.1 steps, about 162 ms. A controller flipping
between two neighbouring values therefore produces an oscillation with a period around 320 ms,
near 3 Hz, rather than an instantaneous square wave.

- **Prediction recorded before measurement:** the naive controller oscillates near 3 Hz with a
  steering amplitude near 0.6, and its |delta steer| P95 is several times the smoothed
  controller's.
- **This prediction may be wrong, and that is the point.** US2 requires the comparison to be
  reported as measured. If the naive controller turns out to complete laps acceptably, the finding
  is recorded and the smoothed controller is justified on its measured merits or not adopted.
  Feature 003 has already had one recorded prediction falsified this way, in C17, and the
  falsification was more useful than the prediction would have been.

## R3 - What "smoothness" is measured as

- **Simply:** reuse the measure the project already compares drivers with, and add one that
  targets chatter directly.

`DriveTelemetry` already computes |delta steer| P95 resampled to 14.08 Hz, which is the dataset's
own rate, and feature 002 and 004 both report against it. Reusing it is what makes the scripted
driver a fourth column rather than a separate experiment with its own yardstick.

- **Decision:** report two numbers, never combined.
  1. **|delta steer| P95 at 14.08 Hz**, comparable with the human, PPO and BC columns.
  2. **Steering sign changes per second**, which is what chatter actually is. A controller can
     have a modest P95 while reversing direction constantly, and the P95 alone would hide it.
- **Rationale:** FR-009 forbids collapsing smoothness and outcome into one verdict, and the same
  logic applies inside smoothness itself. Amplitude and frequency are different failures.
- **Alternatives rejected:** steering variance alone, which cannot distinguish a smooth large
  correction from a rapid small one. An FFT peak, which is a better description of the oscillation
  but needs a windowing choice that would have to be defended, and the sign-change rate answers the
  same question without one.

## R4 - How a sweep of 34 seeds finishes in under five minutes

- **Simply:** the runs are simulated faster than real time inside a single Play session, because
  starting Unity once per seed would spend the whole budget on startup.

At one times real time, 34 training seeds at the observed 34.3 s lap is 19.4 minutes for a single
configuration, which fails SC-004 outright.

| Time scale | One configuration over 34 seeds |
|---|---|
| 1x | 19.4 min |
| 4x | 4.9 min |
| 8x | 2.4 min |
| 12x | 1.6 min |

- **Decision:** raise `Time.timeScale`, keep `Time.fixedDeltaTime` unchanged, and iterate every
  seed inside one Play session.
- **Why the fixed step must not change:** raising `timeScale` alone asks for more physics steps per
  real second and changes nothing about the simulation itself, so the trajectory is identical to a
  real-time run. Raising `fixedDeltaTime` instead would make the physics coarser and would change
  the result, which would mean the sweep measured the step size rather than the sensing geometry.
  `Time.maximumDeltaTime` has to be raised alongside, or Unity clamps the number of steps it will
  take in one frame and the run silently falls back toward real time.
- **Why one session:** an editor Play-mode entry costs on the order of ten to twenty seconds of
  domain reload. Thirty-four of those is another ten minutes, which exceeds the entire budget on
  its own. The runner rebuilds the track and resets the car between seeds instead of restarting.
- **The chosen scale is measured, not assumed.** 8x is the starting point because it leaves margin,
  but the sweep must verify that a run at the chosen scale produces the same outcome as the same
  seed at 1x. If it does not, the scale is lowered until it does, and the figure that survives is
  recorded. A sweep that is fast and wrong is worse than one that is slow.
- **Alternatives rejected:** headless batch mode, which is the standard answer and would work, but
  costs a player build per configuration and cannot be watched while it runs; the editor path can
  be inspected the moment something looks wrong. Reducing the seed set, which trades the thing
  FR-012 exists to protect, since one track is one sample.

## R5 - Which seeds the sweep runs on

- **Simply:** the 34 training seeds, not the 10 evaluation seeds.

- **Decision:** sweep over `results/tracks/seed_split.json` `train.accepted_seeds`, all 34.
- **Rationale:** the sweep chooses a sensing geometry. If it chose that geometry by measuring on
  the evaluation seeds, every later claim about the learning agent on those seeds would be
  contaminated: the environment itself would have been fitted to them. The split exists precisely
  so this cannot happen, and this is the first feature that could have violated it.
- **Consequence recorded now:** any geometry adopted under FR-018 was selected on training tracks,
  and the evaluation tracks remain untouched by that choice.

## R5a - The development work was done on an evaluation seed (found 2026-08-10)

- **Simply:** R5 says the sweep must run on training seeds, and every measurement taken before
  this entry was taken on seed 1004, which is an evaluation seed.

R5 was written to stop the sweep from choosing a sensing geometry against the tracks the learning
agent is later judged on, and it names this feature as the first that could violate the split. The
violation happened immediately, and not in the sweep: the scene was built on seed 1004 and all of
the exploratory work ran there.

Everything below was measured on an evaluation track and is therefore **illustrative, not
admissible**:

- the saturation finding, that argmax commands full lock 67 percent of the time
- the falsification of the chatter prediction in R2
- the critical-distance gate completing a lap in 24.7 s at a threshold of 0.35
- the run-to-run spread of 0.100 s

**What survives and what does not.** The mechanisms are still real: quantisation to three reachable
commands follows from 15 degree spacing against a 25 degree limit and holds on any track, and the
0.54 s slew between locks is a property of the vehicle. Those are arithmetic, not measurements.
What does not survive is every number attached to a particular track: the completion result, the
threshold, the spread, and the saturation percentage all have to be re-measured on training seeds
before they mean anything.

**The threshold does not transfer.** With the scene moved to seed 1, a training seed, threshold
0.35 does not complete a lap. It reports NoProgress with the gate open 87 percent of steps against
39 on seed 1004, and a mean speed of 1.81 m/s against 7.96. One track is one sample, which FR-012
already says, and a threshold found on one track was never going to be more than a starting point.

**How it was caught, which is worth recording.** Not by noticing the seed. The scene changed from
1004 to 1 at some point and the same configuration started failing, which read as a regression in
the controller. The trace settled it in one comparison: at the first physics step, with identical
placement logged by the placer, ray 06 read 0.3327 on the old runs and 0.4658 on the new ones. Same
pose, different geometry, so it could not be the same track. **A diagnostic that records what the
car sensed, not only what it did, is what turned an unexplained regression into a one-line answer.**

- **Decision:** `HeuristicTrack.unity` stays on a training seed. Seed 1004 is not used again by
  this feature.
- **Consequence:** the sweep in US3 is the only source of admissible numbers, and the results
  quoted in the feature 005 merge commit and in DESIGN 4.7 are marked as measured on an evaluation
  track until they are re-established.

## R1a - Anticipatory speed, and why R1 rejected it wrongly (2026-08-10)

- **Simply:** a speed derived from the steering command cannot slow a car that has not yet decided
  to turn, so the car arrives at the corner already too fast.

R1 derived the target speed from the steering command alone and rejected reading the forward
distance as "tunable-looking". The measurement overturns that. On training seed 1 the car reached a
barrier and wedged nose-first at every gate threshold from 0.20 to 0.50, each run ending at zero
speed with the wheel at full lock and the forward ray at 2.0 m, which is a bumper against a wall.

- **Decision:** take the minimum of two limits. What the corner being turned into can hold, as
  before, and what the car can still stop inside of, `sqrt(2 * a * d)`.
- **It is not a tuned constant.** The relation is the standard stopping formula rearranged, `a` is
  the braking figure measured in T024 and read from the profile, and `d` is the gap the rays already
  report. The one remaining quantity, how far the nose sits ahead of the ray origin, is read from
  the car's own collider: 2.0 m, which is exactly the reading every wedged run ended on.
- **Effect:** it works and it is not sufficient. The wedging stops, the car slows for what it can
  see, and it still hits a barrier at 6.0 s. The remaining failure is not longitudinal, which is
  what R1a was for. It is R2a.

## R2a - Why argmax actually fails: it is blind to walls it does not point at (2026-08-10)

- **Simply:** `MostOpen` steers at the single longest ray and takes no account of a wall two metres
  off the flank.

Measured at the moment of contact on seed 1:

| Ray | Angle | Reading |
|---|---|---|
| 06 | 0 deg | **20.00 m**, clear to the range limit |
| 07 | +15 deg | 2.78 m |
| 10 | +60 deg | 1.46 m |
| 12 | +90 deg | 1.48 m |

The centre ray is the longest, so argmax commands straight ahead, while the car is already running
along a barrier that its right flank is nearly touching. It drives straight and scrapes it.

**This is a better argument for the weighted controller than the chatter prediction in R2 ever
was.** R2 predicted an oscillation and was falsified: two sign changes in 54 seconds. The real
weakness is structural rather than dynamic, and it follows from what argmax is: a maximum discards
every value except one.

The distance-weighted average fixes it by construction, because every ray votes and a near wall on
one side pulls the mean to the other. Measured on seed 1, `WeightedAverage` with the sight limit
**completes the lap in 27.6 s and again in 27.5 s**, where `MostOpen` cannot finish at any gate
threshold.

- **The gate is not adopted.** It was a patch with a threshold that had to be guessed, that did not
  transfer between two tracks of equal difficulty, and that never prevented the collision it was
  aimed at. `WeightedAverage` needs no tuned parameter at all, which is what a baseline should look
  like. The gate stays in the code as a measured negative result and as a live knob for US3.
- **Both controllers are kept** (FR-006). The point of this feature is not a heuristic that wins,
  it is an honest account of how far a non-learned controller gets, so the failure of the simpler
  one is part of the deliverable rather than something to tidy away.

## R6 - Run-to-run reproducibility, and the control loop's clock

- **Simply:** the driver runs on the physics clock, so the same seed gives the same lap.

Unity's physics is deterministic for identical inputs on the same binary and platform. The usual
way that breaks is a control loop in `Update`, which runs at the rendering rate: a frame-rate hiccup
changes how long an input is held, and the trajectory diverges.

- **Decision:** the driver reads observations and writes its command in `FixedUpdate`, the same
  clock `CarAgent` senses on and `CarController` applies forces on. Nothing about the control
  decision touches `Time.deltaTime`.
- **Measured rather than asserted:** FR-011 is satisfied by running the same seed and controller
  three times and reporting the spread of lap time and steering P95, exactly as feature 004 did for
  training reproducibility in its R13. If the spread is non-zero, the tolerance is stated and every
  later comparison is judged against it. This is also what FR-015 needs: a difference between two
  sensing configurations means nothing until it is larger than the run-to-run spread.
- **Alternatives rejected:** asserting determinism from the engine's documentation. Feature 004
  measured a reproduction tolerance rather than claiming one, and found a real spread; the same
  discipline applies here.

## R7 - One source for the sensing geometry

- **Simply:** the ray configuration is currently written down twice with nothing checking the two
  agree, and this feature needs to vary it, which would make the drift worse.

`RAY_COUNT`, `RAY_FOV_DEG` and `RAY_LENGTH_M` live in `python/track/config.py`. The same three
numbers live as serialised fields on `CarAgent`. `vehicle_profile.json` is exported from config and
mirror-tested by `python/tests/test_vehicle.py`, but **the exporter writes no sensing block**, so
nothing stands between those two copies. `CarAgent`'s own comment says as much: changing a ray
constant means changing it in both places by hand.

- **Decision:** export a `sensing` block into `vehicle_profile.json` alongside the existing
  `profile` and `envelope` blocks, add a `pytest` mirror test in the shape of the existing profile
  test, and add a **startup drift check** that compares the scene's ray fields against the exported
  block, in the shape of `DriveTelemetry.WarnIfProfileDrifted`.

**Corrected 2026-08-09, during implementation.** This entry originally said `CarAgent` should load
the block "the way `CarController` already loads the vehicle profile". That was wrong on two
counts, and the code says so plainly:

- **`CarController` does not load the profile.** `VehicleProfile` holds a compiled copy, described
  in its own comment as being there "so the car does not depend on a file at runtime".
- **`DriveTelemetry` is what reads the file**, and what it does with the profile block is not load
  it but **check it**, field by field, against the serialised copy in the scene.

That check exists because of an incident recorded in its comment: retuning the steering rate from
2.0 to 3.7 in T023 left the scene on 2.0, and the only symptom would have been a drive that
mysteriously failed to improve. **The comment also states why a mirror test alone is not enough:
it compares the compiled default against the JSON and never opens the scene.**

`CarAgent`'s ray fields are serialised in exactly the same way and can go stale in exactly the same
way, so they get the same treatment rather than a new one.

- **Two gaps, two mechanisms.** The `pytest` mirror test closes config against the exported file.
  The startup drift check closes the exported file against the scene. Either alone leaves a way for
  the fan the car actually senses with to differ from the fan every document describes.
- **FR-013 is satisfied differently than planned.** The sweep sets the fan on `CarAgent`
  programmatically at runtime rather than by rewriting a file, which is simpler, needs no reload
  between configurations, and is what SC-004's budget wants anyway. The drift check is suppressed
  for the duration of a sweep, because during a sweep the scene deliberately disagrees with the
  exported file, and an error per seed would bury the run.
- **The values do not change.** 13, 180 and 20 stay exactly as they are; only where they are read
  from moves. Nothing measured in feature 003 is invalidated by this, and FR-018 is not triggered,
  because no new arrangement is adopted here.
- **Alternatives rejected:** a test that reads the scene YAML and compares against config, which
  would detect drift without preventing it, and would break whenever the scene is re-serialised.
  Leaving it alone, which the spec explicitly forbids in FR-016.

## R8 - Where the driver lives, and who has control

- **Simply:** it is a policy over the observation vector, so it sits with the observation code, and
  it must never be able to fight the existing scripted driver for the wheel.

`CarController.ScriptedMove` is a nullable `Vector2`; setting it takes control and setting it to
null returns control to the keyboard. `ScriptedDriver` already uses exactly this path, which is the
mechanism FR-003 and FR-004 need and the reason no new control path is built.

- **Decision:** `Assets/Scripts/Agent/HeuristicDriver.cs`, in `SelfDrivingSim.Agent`. It reads
  `CarAgent.RayDistancesNorm` and `CarAgent.SpeedForwardNorm` and writes `CarController.ScriptedMove`.
- **Rationale:** FR-001 forbids it reading the track file or checkpoint positions. Placing it in
  `Agent`, beside the observation vector and away from `Track`, makes that boundary visible in the
  folder structure rather than only in a requirement. It also reads exactly what the learning agent
  will read, which is what makes it a fair baseline.
- **Control conflict:** `HeuristicDriver` refuses to engage while `ScriptedDriver.IsRunning`, logs
  which source has the wheel when it changes, and the HUD displays it. FR-004 asks for exactly one
  source in effect and for that to be visible to an observer, and two components silently writing
  the same field would satisfy neither.
- **Note for whoever writes it:** inside `SelfDrivingSim.Agent` the bare name `Agent` binds to the
  namespace, so deriving from ML-Agents' type must be written `Unity.MLAgents.Agent`. `CarAgent`
  already carries this warning and it cost time once.

## R9 - The degenerate readings the spec lists as edge cases

- **Simply:** each of the spec's edge cases has a defined answer, chosen now rather than discovered
  during a sweep.

| Situation | Reading | Behaviour |
|---|---|---|
| Every ray at maximum range, nothing in sensing distance | all 1.000 | Hold the current heading and the target speed. There is no information, so inventing a turn would be arbitrary. This is the normal state on `FlatGround`, verified in T062 |
| Perfectly symmetric reading, no unique longest ray | ties | The weighted average returns 0 naturally. The argmax controller must break ties toward the centre ray, never by index order, or the car turns toward whichever end of the array the loop happens to start at |
| Car against a barrier, rays on that side near zero | one side near 0 | Steering away is correct but insufficient, because a car already touching cannot always steer out. The run ends and is recorded as a wall contact, which is what FR-010 counts. Reversing out is not attempted: a baseline that recovers is a more complicated thing than the one being measured |
| Car facing backwards after a recovery | open track ahead | The driver will confidently drive the wrong way, because the forward fan cannot tell. The run ends on the wrong-way signal the checkpoint ring already produces, recorded as the reason the run ended |
| Track the driver cannot complete | any | A time limit ends the run, derived rather than picked: the slowest human lap recorded in T051 with generous margin. FR-005 requires a defined end state and a sweep that hangs on one seed never finishes |

- **Rationale for ending rather than recovering:** every recovery behaviour added to the baseline
  makes it less of a baseline. The spec's Out of Scope section already excludes tuning for lap
  time; recovery is the same category of creep. A failed run is a data point, and FR-010 requires
  the reason to be recorded.
