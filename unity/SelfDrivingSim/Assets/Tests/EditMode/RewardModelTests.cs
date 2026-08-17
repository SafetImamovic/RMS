using System;
using NUnit.Framework;
using SelfDrivingSim.Agent;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The reward table, tested as the pure functions it is (feature 006, FR-006, T008).
    ///
    /// No scene, no car, no trainer. That is the whole reason <see cref="RewardModel"/> sits
    /// outside <c>DrivingAgent</c>: the arithmetic that decides what the policy learns is checkable
    /// in milliseconds, and Constitution Principle VIII asks for exactly that.
    ///
    /// Two of these cases are adversarial rather than descriptive. The circling case and the
    /// standing-still case are the two ways a policy can satisfy this reward without driving, and
    /// they are written down here so that a future change to a weight has to break a test rather
    /// than merely change a number.
    /// </summary>
    public class RewardModelTests
    {
        private const float Tol = 1e-6f;

        // --- the terms, one at a time ---------------------------------------------------------

        [Test]
        public void Checkpoint_pays_once_per_marker_awarded()
        {
            Assert.That(RewardModel.Checkpoints(0), Is.EqualTo(0f).Within(Tol));
            Assert.That(RewardModel.Checkpoints(1), Is.EqualTo(1.0f).Within(Tol));

            // A fast car can cross two markers inside one decision. Paying for one would
            // under-reward the driving the table exists to encourage.
            Assert.That(RewardModel.Checkpoints(2), Is.EqualTo(2.0f).Within(Tol));
        }

        [Test]
        public void Checkpoint_refuses_a_negative_delta()
        {
            // The ring's awarded count never decreases inside an episode, so a negative delta means
            // an episode boundary was missed and the reward would be applied backwards.
            Assert.Throws<ArgumentOutOfRangeException>(() => RewardModel.Checkpoints(-1));
        }

        [Test]
        public void Wrong_way_is_paid_on_the_edge_and_not_on_the_state()
        {
            Assert.That(RewardModel.WrongWay(true), Is.EqualTo(-1.0f).Within(Tol));
            Assert.That(RewardModel.WrongWay(false), Is.EqualTo(0f).Within(Tol));
        }

        [Test]
        public void Wall_contact_costs_five()
        {
            Assert.That(RewardModel.Wall(true), Is.EqualTo(-5.0f).Within(Tol));
            Assert.That(RewardModel.Wall(false), Is.EqualTo(0f).Within(Tol));
        }

        [Test]
        public void Step_always_costs_the_same()
        {
            Assert.That(RewardModel.Step(), Is.EqualTo(-0.001f).Within(Tol));
        }

        // --- the two terms with rules the table does not state --------------------------------

        [Test]
        public void Speed_pays_forwards_only()
        {
            Assert.That(RewardModel.Speed(1f), Is.EqualTo(0.001f).Within(Tol));
            Assert.That(RewardModel.Speed(0.5f), Is.EqualTo(0.0005f).Within(Tol));
            Assert.That(RewardModel.Speed(0f), Is.EqualTo(0f).Within(Tol));

            // Reversing earns nothing. Paying the raw signed value would let a policy sit in
            // reverse collecting the difference between this term and the step cost.
            Assert.That(RewardModel.Speed(-1f), Is.EqualTo(0f).Within(Tol));

            // An overspeed does not pay more than the term is worth.
            Assert.That(RewardModel.Speed(1.7f), Is.EqualTo(0.001f).Within(Tol));
        }

        [Test]
        public void Jerk_is_free_at_and_below_the_threshold_and_costs_above_it()
        {
            Assert.That(RewardModel.Jerk(0f), Is.EqualTo(0f).Within(Tol));
            Assert.That(RewardModel.Jerk(0.54f), Is.EqualTo(0f).Within(Tol));

            // Exactly at the threshold is free: the design says "greater than 0.55".
            Assert.That(RewardModel.Jerk(RewardModel.JerkThreshold), Is.EqualTo(0f).Within(Tol));

            // Just above it, the whole delta is charged rather than the excess, so the term jumps
            // rather than growing from zero. DESIGN 4.5 writes it that way and the discontinuity is
            // a property of the decision, not a bug to be smoothed away later.
            Assert.That(RewardModel.Jerk(0.56f), Is.EqualTo(-0.0028f).Within(1e-5f));

            // Sign of the delta does not matter; a hard turn either way costs the same.
            Assert.That(RewardModel.Jerk(-0.8f), Is.EqualTo(RewardModel.Jerk(0.8f)).Within(Tol));
        }

        [Test]
        public void Jerk_jumps_at_the_threshold_rather_than_easing_in()
        {
            float below = RewardModel.Jerk(RewardModel.JerkThreshold - 1e-4f);
            float above = RewardModel.Jerk(RewardModel.JerkThreshold + 1e-4f);

            Assert.That(below, Is.EqualTo(0f).Within(Tol));
            Assert.That(above, Is.LessThan(-0.0027f));
        }

        // --- the two ways to satisfy this reward without driving ------------------------------

        [Test]
        public void Circling_on_open_surface_earns_nothing_per_step()
        {
            // The failure this guards: a policy that drives in circles in a wide part of the
            // surface collects the speed reward without going anywhere. The defence is arithmetic
            // rather than a rule, so it has to be asserted rather than assumed.
            //
            // At full speed the step cost and the speed reward cancel exactly, so the best
            // sustainable rate is zero per step against 1.0 for reaching the next marker.
            Assert.That(RewardModel.Idle(1f), Is.EqualTo(0f).Within(Tol));

            // At any speed below the maximum it is strictly negative, so loitering is worse than
            // nothing rather than merely no better.
            Assert.That(RewardModel.Idle(0.6f), Is.LessThan(0f));
            Assert.That(RewardModel.Idle(0.99f), Is.LessThan(0f));

            // And the whole point: one marker outweighs a great many circling steps.
            Assert.That(RewardModel.Checkpoints(1), Is.GreaterThan(RewardModel.Idle(1f) * 1000f));
        }

        [Test]
        public void Standing_still_loses_ground_every_step()
        {
            float perStep = RewardModel.Idle(0f);

            Assert.That(perStep, Is.EqualTo(-0.001f).Within(Tol));
            Assert.That(perStep, Is.LessThan(0f));

            // Over a full 6000-step episode a stationary car ends at -6, which is worse than
            // driving into a barrier on the first step. That ordering is deliberate: crashing while
            // trying is preferable to not trying.
            Assert.That(perStep * 6000f, Is.LessThan(RewardModel.WallPenalty));
        }

        // --- the breakdown --------------------------------------------------------------------

        [Test]
        public void Breakdown_sums_to_the_episode_return()
        {
            var b = new RewardModel.Breakdown
            {
                CheckpointProgress = RewardModel.Checkpoints(24),
                WrongDirection = RewardModel.WrongWay(true),
                WallContact = RewardModel.Wall(true),
                StepCostTotal = RewardModel.Step() * 1200f,
                ForwardSpeed = RewardModel.Speed(0.8f) * 1200f,
                SteeringJerk = RewardModel.Jerk(0.9f) * 3f,
            };

            float expected =
                24f - 1f - 5f + (-0.001f * 1200f) + (0.0008f * 1200f) + (-0.0045f * 3f);

            Assert.That(b.Total, Is.EqualTo(expected).Within(1e-4f));
        }

        [Test]
        public void Empty_breakdown_is_zero()
        {
            Assert.That(new RewardModel.Breakdown().Total, Is.EqualTo(0f).Within(Tol));
        }
    }
}
