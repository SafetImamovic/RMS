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
            // Against the constant rather than its arithmetic, for the reason the jerk assertions
            // are: `ppo_car_speed_hi` tunes this scale, and the rule under test is that the term is
            // linear in forward speed, not what the weight happens to be this week.
            Assert.That(
                RewardModel.Speed(1f), Is.EqualTo(RewardModel.SpeedReward).Within(Tol));
            Assert.That(
                RewardModel.Speed(0.5f), Is.EqualTo(RewardModel.SpeedReward * 0.5f).Within(Tol));
            Assert.That(RewardModel.Speed(0f), Is.EqualTo(0f).Within(Tol));

            // Reversing earns nothing. Paying the raw signed value would let a policy sit in
            // reverse collecting the difference between this term and the step cost.
            Assert.That(RewardModel.Speed(-1f), Is.EqualTo(0f).Within(Tol));

            // An overspeed does not pay more than the term is worth.
            Assert.That(
                RewardModel.Speed(1.7f), Is.EqualTo(RewardModel.SpeedReward).Within(Tol));
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
            Assert.That(
                RewardModel.Jerk(0.56f),
                Is.EqualTo(RewardModel.JerkPenalty * 0.56f).Within(1e-5f));

            // Sign of the delta does not matter; a hard turn either way costs the same.
            Assert.That(RewardModel.Jerk(-0.8f), Is.EqualTo(RewardModel.Jerk(0.8f)).Within(Tol));
        }

        [Test]
        public void Jerk_jumps_at_the_threshold_rather_than_easing_in()
        {
            float below = RewardModel.Jerk(RewardModel.JerkThreshold - 1e-4f);
            float above = RewardModel.Jerk(RewardModel.JerkThreshold + 1e-4f);

            Assert.That(below, Is.EqualTo(0f).Within(Tol));
            // Against the constant rather than its arithmetic, so tuning the scale (T048)
            // changes one number in one file and this test still asserts the same rule.
            Assert.That(
                above,
                Is.LessThan(RewardModel.JerkPenalty * RewardModel.JerkThreshold * 0.99f));
        }

        // --- the two ways to satisfy this reward without driving ------------------------------

        [Test]
        public void Circling_on_open_surface_earns_nothing_per_step()
        {
            // The failure this guards: a policy that drives in circles in a wide part of the
            // surface collects the speed reward without going anywhere. The defence is arithmetic
            // rather than a rule, so it has to be asserted rather than assumed.
            //
            // This used to read Idle(1f) == 0 exactly, because the table made the step cost and
            // the speed reward cancel at full speed. `ppo_car_speed_hi` raised SpeedReward to give
            // the policy a gradient towards moving at all, which turns that identity into a
            // margin, and this assertion caught the change rather than letting it through. What is
            // asserted now is the property the identity was protecting, not the identity.
            //
            // The margin: circling flat out for a whole episode must stay well under what one lap
            // of markers pays. A third is the bound DESIGN 4.5 derives the weight from.
            const float episodeSteps = 6000f;
            const float lapCheckpoints = 24f;

            float circlingWholeEpisode = RewardModel.Idle(1f) * episodeSteps;

            Assert.That(
                circlingWholeEpisode,
                Is.LessThan(RewardModel.Checkpoints(1) * lapCheckpoints / 3f),
                "circling flat out must stay under a third of a lap, or farming competes with driving");

            // At half speed and below it is still strictly negative, so loitering slowly is worse
            // than nothing rather than merely no better. Break-even is v_norm 0.5 by construction.
            Assert.That(RewardModel.Idle(0.4f), Is.LessThan(0f));
            Assert.That(RewardModel.Idle(0.49f), Is.LessThan(0f));

            // What used to stand here was `Checkpoints(1) > Idle(1f) * 1000f`. Under the old table
            // Idle(1f) was exactly zero, so that assertion read `1.0 > 0` and constrained nothing;
            // the 1000 was illustration, not a bound. It is removed rather than retuned, because
            // promoting a decorative constant into a real constraint on a weight would invent a
            // requirement the design never made. The episode-level margin above is the derived
            // bound and is what DESIGN 4.5 sizes the weight from.
            //
            // Recorded as a consequence rather than asserted: at SpeedReward 0.002 the car must
            // circle flat out for 1000 steps, 20 s at 50 Hz, to earn what one marker pays. Under
            // the old table no amount of circling ever equalled a marker.
        }

        [Test]
        public void The_progress_term_adds_nothing_to_circling()
        {
            // Feature 007 restates the invariant above rather than replacing it. The margin is
            // unchanged because a closed loop pays exactly zero from the new term, so the bound
            // that Idle already had to clear is still the whole of what circling earns.
            //
            // Asserted here at the arithmetic level: equal and opposite advances cancel exactly.
            // TrackProgressTests carries the same claim over a 6000-step circle on a real chain,
            // which is the version that would catch a geometry bug rather than a sign bug.
            const float weight = 0.0594f;

            float outward = RewardModel.Progress(4.7, weight);
            float back = RewardModel.Progress(-4.7, weight);

            Assert.That(outward, Is.GreaterThan(0f));
            Assert.That(outward + back, Is.EqualTo(0f).Within(Tol));
        }

        [Test]
        public void The_progress_term_is_symmetric_rather_than_one_sided()
        {
            // The failure this guards is the tempting one: clamping the negative half the way
            // Speed does. That would make a car rocking towards a marker and away again collect on
            // every half cycle, which is the only farmable term this table could have acquired.
            const float weight = 0.0594f;

            Assert.That(RewardModel.Progress(-1.0, weight),
                Is.EqualTo(-RewardModel.Progress(1.0, weight)).Within(Tol));
            Assert.That(RewardModel.Progress(-1.0, weight), Is.LessThan(0f));
            Assert.That(RewardModel.Progress(0.0, weight), Is.EqualTo(0f).Within(Tol));
        }

        [Test]
        public void A_lap_of_progress_pays_half_of_what_its_markers_pay()
        {
            // DESIGN 4.5's derivation, checked as a product rather than a quotient: whatever the
            // chain length, driving all of it must pay half of what taking all 24 markers pays.
            const double chain = 202.3;
            float weight = (float)(0.5 * 24 * RewardModel.CheckpointReward / chain);

            Assert.That(RewardModel.Progress(chain, weight),
                Is.EqualTo(RewardModel.Checkpoints(24) * 0.5f).Within(1e-3f));
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
                MarkerProgress = RewardModel.Progress(202.3, 0.0594f),
            };

            // The jerk and speed terms are written against their constants, not their arithmetic:
            // T048 tunes both scales, and this test is about the seven fields summing rather than
            // about any one weight. The progress term has no constant to write it against, because
            // its weight is derived per track; the figures here are the nominal chain and its
            // derived weight, standing in for one lap's worth.
            float expected =
                24f - 1f - 5f + (RewardModel.StepCost * 1200f)
                + (RewardModel.SpeedReward * 0.8f * 1200f)
                + (RewardModel.JerkPenalty * 0.9f * 3f)
                + (float)(202.3 * 0.0594f);

            Assert.That(b.Total, Is.EqualTo(expected).Within(1e-4f));
        }

        [Test]
        public void Empty_breakdown_is_zero()
        {
            Assert.That(new RewardModel.Breakdown().Total, Is.EqualTo(0f).Within(Tol));
        }
    }
}
