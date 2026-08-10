using System;
using NUnit.Framework;
using SelfDrivingSim.Agent;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The two steering strategies, tested as the pure functions they are (feature 005, FR-006).
    ///
    /// No scene, no car, no physics step. That is the whole reason `RayControllers` sits outside
    /// `HeuristicDriver`: the one piece of this feature worth testing is reachable in
    /// milliseconds, and Constitution Principle VIII asks for exactly that.
    ///
    /// Two of these cases are the degenerate readings research R9 wrote down before anything was
    /// built, and both are cases a person watching the car drive would never think to produce.
    /// </summary>
    public class RayControllerTests
    {
        // The fan as feature 003 measured it and T062 verified it: 13 rays, 180 degrees, right
        // positive. Built here rather than read from the profile, because a unit test that loads
        // a file is testing the file.
        private const float SteerMaxDeg = 25f;

        private static float[] Angles(int count = 13, float fovDeg = 180f)
        {
            var a = new float[count];
            float spacing = count > 1 ? fovDeg / (count - 1) : 0f;
            for (int i = 0; i < count; i++)
            {
                a[i] = -fovDeg * 0.5f + i * spacing;
            }

            return a;
        }

        private static float[] Uniform(float value, int count = 13)
        {
            var d = new float[count];
            for (int i = 0; i < count; i++)
            {
                d[i] = value;
            }

            return d;
        }

        // -------------------------------------------------------------------------------------
        // MostOpen
        // -------------------------------------------------------------------------------------

        [Test]
        public void MostOpen_steers_toward_the_clearest_ray()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.2f);
            d[9] = 1.0f; // +45 degrees

            float steer = RayControllers.MostOpen(d, angles, SteerMaxDeg);

            // 45 / 25 is 1.8, past the clamp, so the command saturates rather than wrapping.
            Assert.That(steer, Is.EqualTo(1f).Within(1e-5f));
        }

        [Test]
        public void MostOpen_steers_left_for_a_left_opening()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.2f);
            d[5] = 1.0f; // -15 degrees

            float steer = RayControllers.MostOpen(d, angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(-0.6f).Within(1e-5f));
        }

        /// <summary>
        /// The reachable commands are quantised, which is the whole prediction in research R2.
        ///
        /// If this test ever fails it means the fan or the steering limit moved, and the chatter
        /// argument in DESIGN 4.7 has to be recomputed rather than repeated.
        /// </summary>
        [Test]
        public void MostOpen_can_only_reach_three_magnitudes_on_the_stated_fan()
        {
            float[] angles = Angles();
            var reachable = new System.Collections.Generic.HashSet<float>();

            for (int i = 0; i < angles.Length; i++)
            {
                float[] d = Uniform(0.2f);
                d[i] = 1.0f;
                reachable.Add(Math.Abs((float)Math.Round(
                    RayControllers.MostOpen(d, angles, SteerMaxDeg), 4)));
            }

            Assert.That(reachable, Is.EquivalentTo(new[] { 0f, 0.6f, 1f }),
                "the naive controller should reach only 0, 0.6 and 1.0 at 13 rays over 180 " +
                "degrees against a 25 degree limit. Everything between is unreachable, which is " +
                "why it chatters (research R2)");
        }

        /// <summary>
        /// An all-clear fan is what open ground reads, and T062 confirmed it on FlatGround.
        ///
        /// Every ray returns exactly 1.0, so there is no unique longest ray. Taking the first
        /// index found would steer hard left every time the world went symmetric, and the symptom
        /// would appear only where there is nothing to see, so it would be blamed on the track.
        /// </summary>
        [Test]
        public void MostOpen_holds_straight_when_every_ray_is_clear()
        {
            float[] angles = Angles();
            float[] d = Uniform(1.0f);

            float steer = RayControllers.MostOpen(d, angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(0f).Within(1e-6f),
                "a symmetric reading has no preferred direction, so the tie must resolve to the " +
                "centre ray rather than to whichever index the loop reached first");
        }

        [Test]
        public void MostOpen_breaks_a_two_way_tie_toward_the_centre()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.2f);
            d[2] = 0.9f;  // -60 degrees
            d[7] = 0.9f;  // +15 degrees, nearer the nose

            float steer = RayControllers.MostOpen(d, angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(0.6f).Within(1e-5f));
        }

        [Test]
        public void MostOpen_steers_away_from_a_wall_on_one_side()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.5f);
            for (int i = 0; i <= 4; i++)
            {
                d[i] = 0.05f; // left side blocked
            }

            d[7] = 0.9f; // the opening, 15 degrees to the right

            float steer = RayControllers.MostOpen(d, angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(0.6f).Within(1e-5f), "blocked left, opening right");
        }

        /// <summary>
        /// Blocking one side does not by itself produce a turn, and that is correct.
        ///
        /// This case was written first as "wall on the left, so steer right" and failed, because
        /// every unblocked ray including the centre one read the same distance. That is an
        /// eight-way tie, the tie resolves to the centre, and driving straight past a wall you are
        /// parallel to is the right answer.
        ///
        /// Pinned rather than deleted: it is the clearest demonstration that <c>MostOpen</c>
        /// responds to where the longest ray is, not to where the obstacle is. The two coincide
        /// often enough that the difference is easy to miss until a corner arrives.
        /// </summary>
        [Test]
        public void MostOpen_holds_straight_when_the_open_side_is_featureless()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.8f);
            for (int i = 0; i <= 4; i++)
            {
                d[i] = 0.05f;
            }

            float steer = RayControllers.MostOpen(d, angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(0f).Within(1e-6f));
        }

        /// <summary>
        /// The smoothed controller does turn in that same situation, which is the first measured
        /// behavioural difference between the two and not merely a smoothness difference.
        /// </summary>
        [Test]
        public void WeightedAverage_turns_where_MostOpen_holds_straight()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.8f);
            for (int i = 0; i <= 4; i++)
            {
                d[i] = 0.05f;
            }

            Assert.That(RayControllers.MostOpen(d, angles, SteerMaxDeg),
                Is.EqualTo(0f).Within(1e-6f));
            Assert.That(RayControllers.WeightedAverage(d, angles, SteerMaxDeg),
                Is.GreaterThan(0.1f),
                "every ray votes, so a blocked left side pulls the mean to the right even with " +
                "no single standout direction");
        }

        // -------------------------------------------------------------------------------------
        // WeightedAverage
        // -------------------------------------------------------------------------------------

        [Test]
        public void WeightedAverage_returns_zero_on_a_symmetric_reading()
        {
            float[] angles = Angles();

            Assert.That(RayControllers.WeightedAverage(Uniform(1.0f), angles, SteerMaxDeg),
                Is.EqualTo(0f).Within(1e-5f));
            Assert.That(RayControllers.WeightedAverage(Uniform(0.3f), angles, SteerMaxDeg),
                Is.EqualTo(0f).Within(1e-5f),
                "symmetry, not magnitude, is what makes the answer zero");
        }

        [Test]
        public void WeightedAverage_leans_toward_the_open_side()
        {
            float[] angles = Angles();
            float[] d = Uniform(0.2f);
            for (int i = 7; i < d.Length; i++)
            {
                d[i] = 1.0f; // right side open
            }

            float steer = RayControllers.WeightedAverage(d, angles, SteerMaxDeg);

            Assert.That(steer, Is.GreaterThan(0f));
        }

        /// <summary>
        /// The property the whole US2 comparison rests on: the smoothed controller is not confined
        /// to the naive one's three magnitudes.
        /// </summary>
        [Test]
        public void WeightedAverage_is_not_quantised_to_ray_angles()
        {
            float[] angles = Angles();
            var seen = new System.Collections.Generic.HashSet<float>();

            for (int i = 0; i < angles.Length; i++)
            {
                float[] d = Uniform(0.4f);
                d[i] = 1.0f;
                seen.Add((float)Math.Round(
                    RayControllers.WeightedAverage(d, angles, SteerMaxDeg), 4));
            }

            Assert.That(seen.Count, Is.GreaterThan(3),
                "if the smoothed controller reached only as many values as the naive one, it " +
                "would have nothing to offer over it");
        }

        [Test]
        public void WeightedAverage_holds_straight_when_everything_is_blocked()
        {
            float[] angles = Angles();

            float steer = RayControllers.WeightedAverage(Uniform(0f), angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(0f).Within(1e-6f),
                "no open direction to average, so hold heading rather than divide by zero");
        }

        [Test]
        public void WeightedAverage_ignores_a_blocked_ray_rather_than_being_pulled_by_it()
        {
            float[] angles = Angles();
            float[] open = Uniform(0f);
            open[8] = 1.0f; // +30 degrees, the only open direction

            float steer = RayControllers.WeightedAverage(open, angles, SteerMaxDeg);

            Assert.That(steer, Is.EqualTo(30f / SteerMaxDeg).Within(1e-4f).Or.EqualTo(1f),
                "a single open ray at +30 asks for 1.2, which clamps to 1.0");
        }

        // -------------------------------------------------------------------------------------
        // Both, and the inputs that must be refused
        // -------------------------------------------------------------------------------------

        [TestCase(RayControllers.Strategy.MostOpen)]
        [TestCase(RayControllers.Strategy.WeightedAverage)]
        public void Both_stay_inside_the_command_range(RayControllers.Strategy strategy)
        {
            float[] angles = Angles();
            var rng = new System.Random(42);

            for (int trial = 0; trial < 500; trial++)
            {
                var d = new float[angles.Length];
                for (int i = 0; i < d.Length; i++)
                {
                    d[i] = (float)rng.NextDouble();
                }

                float steer = RayControllers.Steer(strategy, d, angles, SteerMaxDeg);
                Assert.That(steer, Is.InRange(-1f, 1f));
            }
        }

        /// <summary>
        /// Mismatched arrays are the failure worth catching hardest: the command would be computed
        /// from distances and angles belonging to different rays, and the car would drive badly
        /// for a reason nobody would find by watching it.
        /// </summary>
        [Test]
        public void Mismatched_arrays_are_refused_rather_than_truncated()
        {
            Assert.Throws<ArgumentException>(
                () => RayControllers.MostOpen(Uniform(0.5f, 13), Angles(11), SteerMaxDeg));
            Assert.Throws<ArgumentException>(
                () => RayControllers.WeightedAverage(Uniform(0.5f, 11), Angles(13), SteerMaxDeg));
        }

        [Test]
        public void A_non_positive_steering_limit_is_refused()
        {
            Assert.Throws<ArgumentOutOfRangeException>(
                () => RayControllers.MostOpen(Uniform(0.5f), Angles(), 0f));
        }

        /// <summary>
        /// An even fan is a legal sweep configuration, not an error, so the strategies must handle
        /// one. With no ray straight ahead, a symmetric reading still has to resolve to zero.
        /// </summary>
        [Test]
        public void An_even_fan_with_no_centre_ray_still_resolves_symmetry_to_zero()
        {
            float[] angles = Angles(12);

            Assert.That(RayControllers.WeightedAverage(Uniform(1.0f, 12), angles, SteerMaxDeg),
                Is.EqualTo(0f).Within(1e-5f));

            // MostOpen cannot return exactly zero here, because no ray points straight ahead.
            // The tie must still resolve to one of the two innermost rays rather than to an
            // outer one, which is the property that matters.
            float steer = RayControllers.MostOpen(Uniform(1.0f, 12), angles, SteerMaxDeg);
            float innermost = Math.Abs(angles[6]) / SteerMaxDeg;
            Assert.That(Math.Abs(steer), Is.EqualTo(innermost).Within(1e-4f));
        }
    }
}
