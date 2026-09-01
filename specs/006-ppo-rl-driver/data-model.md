# Phase 1 Data Model: PPO Reinforcement Learning Driver

**Feature**: `006-ppo-rl-driver` | **Date**: 2026-08-17

The entities the spec named, with the fields that make them checkable. Nothing here is a class
diagram; it is the set of things that have to exist, what each one carries, and which requirement
fails if it does not.

---

## Observation vector

Not new. It is `CarAgent.Observations`, and this feature only fixes what may be done with it.

| Slot | Count | Source | Range |
|---|---|---|---|
| Ray distances, normalised | 13 | `CarAgent.RayDistancesNorm` | 0 to 1, 1 meaning nothing within 20 m |
| Forward speed, normalised | 1 | `CarAgent.SpeedForwardNorm` | roughly -1 to 1 |
| Lateral speed, normalised | 1 | `CarAgent.SpeedLateralNorm` | roughly -1 to 1 |
| Yaw rate, normalised | 1 | `CarAgent.YawRateNorm` | -1 to 1 |
| Heading forward dot | 1 | `CarAgent.HeadingForwardDot` | -1 to 1 |
| Heading right dot | 1 | `CarAgent.HeadingRightDot` | -1 to 1 |
| Steering, normalised | 1 | `CarAgent.SteerNorm` | -1 to 1 |

**Total 19.** `CarAgent.ObservationCount` computes it and `CarAgent.ObservationName(i)` names each
slot, so the trainer-side vector size and the scene-side vector size have one source.

**Validation.** The agent asserts `ObservationCount` equals the behaviour's configured vector size
at start-up and refuses to run otherwise (FR-004). A silent mismatch trains against garbage, and
the failure is invisible in the reward curve.

---

## Action vector

| Index | Meaning | Range | Applied through |
|---|---|---|---|
| 0 | Steering | -1 to 1 | `CarController.ScriptedMove.steer` |
| 1 | Longitudinal | -1 to 1, negative meaning brake or reverse | `CarController.ScriptedMove.throttle` |

Two continuous actions, matching `DESIGN.md` 4.4 and matching what `HeuristicDriver` writes, so
the learned and scripted drivers differ in policy and in nothing else (FR-003).

**Validation.** Actions are clamped to the range before they reach the controller. PPO's output is
unbounded in principle and a single large value would otherwise reach the steering as a full-lock
command.

---

## Reward breakdown

One per episode, accumulated as the episode runs, reported per term.

| Field | Type | Source signal | Requirement |
|---|---|---|---|
| `checkpointProgress` | float | `CheckpointRing.AwardedCount` increase | FR-006 |
| `wrongDirection` | float | `CheckpointRing.WrongWay` rising edge | FR-006, FR-009 |
| `wallContact` | float | `WallSensor` rising edge | FR-006 |
| `stepCost` | float | one per agent step | FR-006 |
| `forwardSpeed` | float | `CarAgent.SpeedForwardNorm`, positive part | FR-006 |
| `steeringJerk` | float | change in commanded steering between decisions | FR-006 |
| `total` | float | the sum, which must equal the agent's cumulative reward | FR-008 |

**Validation.** The terms must sum to the episode return to within floating-point tolerance. If
they do not, a reward is being applied somewhere that is not in the table, which is the failure
FR-007 exists to prevent.

**State.** Reset to zero in `OnEpisodeBegin`; emitted to the stats recorder and to the episode
record on termination.

---

## Episode

| Field | Type | Notes |
|---|---|---|
| `areaId` | int | which environment copy, so a stuck area is identifiable |
| `seed` | int | the track this episode ran on, always from the training half |
| `startMarkerIndex` | int | from `StartPlacer.LastStartIndex` |
| `steps` | int | agent steps taken |
| `lapsCompleted` | int | from `CheckpointRing.LapCount` |
| `checkpointsAwarded` | int | from `CheckpointRing.AwardedCount` |
| `wallContacts` | int | from `WallSensor` |
| `endReason` | enum | `WallContact`, `LapsCompleted`, `Stalled`, `StepLimit` |
| `reward` | reward breakdown | as above |

**State transitions.**

```text
OnEpisodeBegin
  -> place car at a random marker with 1.5 m lateral and 10 deg yaw offset (StartPlacer)
  -> ring.ResetProgress(); ring.StartAt(markerIndex)
  -> reward breakdown zeroed, jerk history cleared
  -> RUNNING

RUNNING, each agent step
  -> observe, act, accumulate reward terms

RUNNING -> WallContact     when WallSensor reports a new contact      (reward -5.0, EndEpisode)
RUNNING -> LapsCompleted   when ring.LapCount reaches the target      (EndEpisode)
RUNNING -> Stalled         when 60 s pass with no new marker          (truncation, not terminal)
RUNNING -> StepLimit       when steps reach MaxStep                   (truncation, not terminal)
```

**Validation.** Exactly one terminal condition fires per episode and it is recorded (FR-011). The
distinction between `StepLimit` and the other two is not cosmetic: the trainer bootstraps a
truncated episode's value differently, and conflating them teaches the policy that lasting the
full time is a failure (R5).

---

## Training area

| Field | Type | Notes |
|---|---|---|
| `areaId` | int | assigned at scene build, stable for the session |
| `currentSeed` | int | the track currently built |
| `episodesOnSeed` | int | drives rotation |
| Owned children | - | `TrackBuilder`, `CheckpointRing`, `StartPlacer`, car with `CarAgent`, `WallSensor`, `DrivingAgent` |

**Validation.** No field of a training area may be `static`, and no area may hold a reference to
another area's components (FR-016). The one existing static in the codebase, the run record's file
handle, is not used by the training scene.

**Layout.** Areas sit on a grid at 300 m pitch, which exceeds a track's extent plus the 20 m ray
length, so no area's sensing can reach another's barriers (R7).

---

## Seed pool

| Field | Type | Notes |
|---|---|---|
| `trainSeeds` | int[34] | from `results/tracks/seed_split.json`, `train.accepted_seeds` |
| `evalSeeds` | int[10] | same file, `eval.accepted_seeds`, never loaded by the training scene |
| `rotationEvery` | int | episodes on one seed before the area swaps |

**Validation.** The training pool equals the committed file's training half exactly, and the two
pools are disjoint. Asserted by an EditMode test rather than by review, because the failure is
silent and flattering (R15, SC-008).

---

## Training run

One execution of the trainer. This is the entity that ties everything together and the one the
constitution cares most about.

| Field | Type | Notes |
|---|---|---|
| `runId` | string | `ppo_car_vNN`, the `--run-id` passed to the trainer |
| `configPath` | string | `config/ppo_car.yaml`, committed, at the revision used |
| `changedFromPrevious` | string | one line; if it needs an "and", it was two experiments |
| `maxSteps` | int | the budget this run was given |
| `trainerSeed` | int | `--seed`, varied only for the spread runs |
| `areas` | int | environment copies in the scene |
| `wallClockS` | float | for the throughput record and for SC-006 |
| `curvePath` | string | `results/rl/curves/<runId>.csv` |
| `modelPath` | string | the exported `.onnx`, or empty if the run produced none |
| `outcome` | string | what the numbers said, not whether it felt better |

**Validation.** Every run has a row in `results/EXPERIMENTS.md` written in the same session
(Principle VI, FR-017). A run with no row did not happen. A run whose `changedFromPrevious`
contains "and" is split or is not comparable.

---

## Curve sample

One row of a committed training curve.

| Field | Type | Notes |
|---|---|---|
| `step` | int | trainer step |
| `cumulativeReward` | float | the headline series |
| `episodeLength` | float | mean, in agent steps |
| `policyLoss` | float | from the trainer |
| `valueLoss` | float | from the trainer |
| `rewardCheckpoint`, `rewardWall`, `rewardSpeed`, `rewardJerk`, `rewardStep`, `rewardWrongWay` | float | the per-term series this feature adds through the stats recorder |

Full schema in [contracts/curve-export.md](./contracts/curve-export.md).

---

## Evaluation record

Not new. It is feature 005's `RunRecord`, reused unchanged, which is the point of FR-023.

The learned column writes the same fields the scripted column writes: seed, controller, ray count,
fan width, ray length, completed lap, lap time, checkpoints awarded, total and skipped, wall
contacts, end reason, the two smoothness measures kept separate, time scale and duration. The
`controller` field carries the run id, so a row identifies which policy produced it without a
lookup.

**Validation.** A learned row and a scripted row must be readable by the same `pandas` call with no
per-column special casing. If the reporting needs a branch on driver type, the contract was broken.

---

## Policy artifact

| Field | Type | Notes |
|---|---|---|
| `path` | string | `unity/SelfDrivingSim/Assets/Models/<runId>-<step>.onnx`, LFS-tracked |
| `runId` | string | encoded in the filename, not in a side file |
| `deterministicInference` | bool | which of the two drivers this evaluation watched (R12) |

**Validation.** The model file's run id resolves to a row in `results/EXPERIMENTS.md` and to a
curve under `results/rl/curves/`. A model nobody can trace back to a configuration is not evidence
of anything.
