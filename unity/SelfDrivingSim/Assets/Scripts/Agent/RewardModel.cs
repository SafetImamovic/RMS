using System;
using UnityEngine;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// The reward table, as pure functions of numbers (feature 006, FR-006).
    ///
    /// **These live outside <c>DrivingAgent</c> for the reason
    /// <see cref="RayControllers"/> lives outside <c>HeuristicDriver</c>.** A reward term is a
    /// function from a measurement to a float: no car, no scene, no trainer, no physics step. That
    /// is what makes it testable in EditMode, and a reward that can only be checked by watching a
    /// car drive is a reward nobody can check.
    ///
    /// The weights are `DESIGN.md` 4.5 and the contract in
    /// `specs/006-ppo-rl-driver/contracts/reward-events.md`. They are not tuning knobs to be
    /// edited in passing: Principle V puts a change to any of them in the design document first,
    /// and FR-007 puts it in its own training run afterwards.
    /// </summary>
    public static class RewardModel
    {
        /// <summary>Reaching the marker that was next, in the correct direction.</summary>
        public const float CheckpointReward = 1.0f;

        /// <summary>Approaching a marker already passed, paid once on the transition.</summary>
        public const float WrongWayPenalty = -1.0f;

        /// <summary>
        /// Touching a barrier. Terminal, and applied before the episode ends.
        ///
        /// Back at DESIGN 4.5's value. `ppo_car_wall_lo` tried -1.0, which did shift the end-reason
        /// mix the way it was meant to, and made the return measurably worse. The weight is not
        /// kept; the result is.
        /// </summary>
        public const float WallPenalty = -5.0f;

        /// <summary>Paid every step, so that standing still costs something.</summary>
        public const float StepCost = -0.001f;

        /// <summary>
        /// Scale on normalised forward speed, paid every step.
        ///
        /// Raised from 0.001 to 0.002 by `ppo_car_speed_hi` (T048, third candidate). The break-even
        /// speed is <see cref="StepCost"/> over this, so it falls from a `v_norm` of 1.0 to 0.5:
        /// the car no longer has to be at maximum speed merely to stop losing. The ceiling is not
        /// taste, it is <see cref="Idle"/>'''s anti-farming arithmetic, which caps this at 0.00233.
        /// DESIGN 4.5 derives it.
        /// </summary>
        public const float SpeedReward = 0.002f;

        /// <summary>
        /// Scale on the steering change, paid only above the threshold.
        ///
        /// Back at DESIGN 4.5's value. `ppo_car_jerk_lo` tried -0.001 and the change did not clear
        /// the T047 gate on either valid metric, so the weight is not kept.
        /// </summary>
        public const float JerkPenalty = -0.005f;

        /// <summary>
        /// Where a steering change starts costing, being the P95 of |delta steering| in the human
        /// dataset (M1, DESIGN 4.5).
        ///
        /// **The threshold carries a rate that this constant cannot.** It was measured at
        /// 14.08 Hz, and the agent decides at 12.5 Hz, so the same driving produces slightly larger
        /// per-step deltas here than in the dataset and the penalty errs strict. Research R2 has
        /// the derivation; every run record carries the decision rate so the number is never read
        /// without it.
        /// </summary>
        public const float JerkThreshold = 0.55f;

        /// <summary>What one episode's return was made of (FR-008, data-model "Reward breakdown").</summary>
        public struct Breakdown
        {
            public float CheckpointProgress;
            public float WrongDirection;
            public float WallContact;
            public float StepCostTotal;
            public float ForwardSpeed;
            public float SteeringJerk;

            /// <summary>
            /// The sum of the six terms.
            ///
            /// It must equal the agent's cumulative reward. If it does not, something is calling
            /// <c>AddReward</c> outside this table, which makes the breakdown a lie and FR-008
            /// unverifiable.
            /// </summary>
            public float Total =>
                CheckpointProgress + WrongDirection + WallContact +
                StepCostTotal + ForwardSpeed + SteeringJerk;
        }

        /// <summary>
        /// Progress reward for markers awarded since the last step.
        ///
        /// Takes a count rather than a bool because a fast car can cross two markers inside one
        /// decision, and paying only one would quietly under-reward exactly the driving the table
        /// means to encourage. The ring decides what counts as awarded; this only prices it.
        /// </summary>
        public static float Checkpoints(int awardedDelta)
        {
            if (awardedDelta < 0)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(awardedDelta), awardedDelta,
                    "the ring's awarded count never decreases within an episode; a negative delta " +
                    "means the episode boundary was missed and the reward would be applied backwards");
            }

            return awardedDelta * CheckpointReward;
        }

        /// <summary>
        /// The wrong-direction penalty, paid on the transition into the state and not while it
        /// lasts.
        ///
        /// The ring latches <c>WrongWay</c>, so a per-step charge would fine one mistake dozens of
        /// times over and would dominate a return that should be decided by progress.
        /// </summary>
        public static float WrongWay(bool enteredWrongWay)
        {
            return enteredWrongWay ? WrongWayPenalty : 0f;
        }

        /// <summary>The barrier penalty, applied before the episode is ended rather than after.</summary>
        public static float Wall(bool contacted)
        {
            return contacted ? WallPenalty : 0f;
        }

        /// <summary>The per-step cost. Constant, and the only term a stationary car still pays.</summary>
        public static float Step()
        {
            return StepCost;
        }

        /// <summary>
        /// Payment for going forwards.
        ///
        /// **Only forwards.** The observation is signed, so paying the raw value would make
        /// reversing earn by the same symmetry that makes it lose, and a policy could sit in
        /// reverse collecting the difference. Clamped above as well: an overspeed on a downhill
        /// should not pay more than the model says the term is worth.
        /// </summary>
        public static float Speed(float speedForwardNorm)
        {
            return SpeedReward * Mathf.Clamp01(speedForwardNorm);
        }

        /// <summary>
        /// The steering-change penalty, above the threshold only.
        ///
        /// **It multiplies the whole delta, not the excess**, which is what `DESIGN.md` 4.5 writes.
        /// The consequence is a discontinuity: 0.549 costs nothing and 0.551 costs 0.00276. That is
        /// a property of the decision, small against a checkpoint's 1.0, and recorded here so it is
        /// not later read as an off-by-one and quietly "fixed" into a different reward.
        ///
        /// The delta is the change between decisions, not between physics steps. At 12.5 Hz against
        /// a 50 Hz clock a per-physics-step delta would be roughly four times smaller and would
        /// almost never cross the threshold, which would leave the term in the table and out of the
        /// behaviour.
        /// </summary>
        public static float Jerk(float steerDelta)
        {
            float magnitude = Mathf.Abs(steerDelta);
            return magnitude > JerkThreshold ? JerkPenalty * magnitude : 0f;
        }

        /// <summary>
        /// What one step is worth when nothing eventful happens: the cost of existing plus the
        /// payment for moving.
        ///
        /// This sum is the arithmetic the whole table rests on. It is at most
        /// <see cref="StepCost"/> + <see cref="SpeedReward"/>, which is +0.001 per step since
        /// `ppo_car_speed_hi` raised the speed scale. **It used to be exactly zero, and the move
        /// from "cannot profit" to "profits slowly" is the part that needs watching**: a policy
        /// driving in circles on open surface now earns something, so the defence against reward
        /// farming is a margin rather than an identity. Over the 6000-step episode of DESIGN 4.6
        /// that margin is +6 against the +24 a lap's markers pay, and <c>RewardModelTests</c>
        /// asserts the ratio so a future weight change cannot erode it silently. DESIGN 4.5
        /// derives the 0.00233 ceiling this weight sits under.
        /// </summary>
        public static float Idle(float speedForwardNorm)
        {
            return Step() + Speed(speedForwardNorm);
        }
    }
}
