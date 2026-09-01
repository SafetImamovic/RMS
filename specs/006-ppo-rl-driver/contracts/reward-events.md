# Contract: Reward Events

**Feature**: `006-ppo-rl-driver` | **Source of truth**: `DESIGN.md` section 4.5

The reward table is a design decision that already exists. This contract fixes how each row of it
becomes code: which signal it reads, when it fires, what it is worth, and under which key it is
reported. Changing any line here is a design change and goes into `DESIGN.md` first (FR-007).

## The table

| Event | Weight | Fires when | Source signal | Stats key |
|---|---|---|---|---|
| Checkpoint, correct direction | `+1.0` | `CheckpointRing.AwardedCount` increases | `CheckpointRing` | `reward/checkpoint` |
| Checkpoint, wrong direction | `-1.0` | `CheckpointRing.WrongWay` goes false to true | `CheckpointRing` | `reward/wrong_way` |
| Barrier contact | `-5.0`, then terminal | `WallSensor` reports a new contact | `WallSensor` | `reward/wall` |
| Step cost | `-0.001` | every agent step | the step itself | `reward/step` |
| Forward speed | `+0.001 * v_norm` | every agent step, `v_norm` clamped to its positive part | `CarAgent.SpeedForwardNorm` | `reward/speed` |
| Steering change | `-0.005 * abs(delta)` when `abs(delta) > 0.55` | every decision | commanded steering, differenced between decisions | `reward/jerk` |

## Rules that the table alone does not settle

**The steering-change penalty multiplies the whole delta, not the excess.** `DESIGN.md` writes
`-0.005 x |delta|`, and that is implemented literally. The consequence is a discontinuity: a delta
of 0.549 costs nothing and a delta of 0.551 costs 0.00276. That is a property of the design as
written, it is small relative to a checkpoint, and it is recorded here so nobody later reads the
code as a bug and quietly changes the reward.

**The delta is measured between decisions, not between physics steps.** The agent decides at 12.5
Hz (R2) and the physics runs at 50 Hz, so a per-physics-step delta would be roughly four times
smaller for the same driving and would almost never cross 0.55. The rate is recorded with every
run because a threshold without its rate is not a threshold.

**The speed term pays only for forward motion.** `SpeedForwardNorm` is signed, and paying
`0.001 * v_norm` for a negative value would make reversing a way to earn reward by symmetry with
losing it. The negative part is clamped to zero, so reversing earns nothing and still pays the step
cost.

**The wall penalty is applied before the episode ends, not after.** `AddReward(-5.0)` then
`EndEpisode()`. Reversing the order drops the penalty from the episode the trainer attributes it
to.

**Wrong direction is an edge, not a state.** The ring holds `WrongWay` as a latched flag. Paying
`-1.0` every step the flag is set would fine a single mistake dozens of times over. The penalty
fires on the transition into the state.

**Nothing else may call `AddReward`.** The sum of the six terms must equal the episode return
(data-model, reward breakdown). A seventh reward applied anywhere makes the breakdown a lie and
makes FR-008 unverifiable.

## What the tests must cover

The terms are pure functions of numbers and are tested without a scene:

1. Each term produces its stated value for a representative input.
2. The jerk term is zero at and below the threshold and non-zero above it.
3. The speed term is zero for negative `v_norm`.
4. **The circling case.** A policy driving in circles on open surface collects the speed term and
   pays the step cost. With the speed term capped at `+0.001` and the step cost at `-0.001`, the
   best sustainable rate is zero per step against `+1.0` per checkpoint. The test asserts the sign
   of that sum, because it is the design's defence against reward farming and it should fail loudly
   if a weight is ever changed in a way that breaks it.
5. **The standing-still case.** A stationary car earns nothing and pays the step cost every step,
   so its return decreases monotonically until the step limit.
6. The breakdown sums to the total.
