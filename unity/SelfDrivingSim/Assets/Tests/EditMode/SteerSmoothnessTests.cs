using System;
using NUnit.Framework;
using SelfDrivingSim.Agent;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The two smoothness measures the US2 comparison rests on (feature 005, T022, FR-008, FR-009).
    ///
    /// No scene and no car, for the same reason <see cref="RayControllerTests"/> needs neither: the
    /// arithmetic is the part worth testing, and it was deliberately put in a plain class so it
    /// could be reached in milliseconds.
    ///
    /// Several of these cases pin findings from T018 rather than behaviour someone imagined. The
    /// measure was rebuilt because the drive log could not support it: it recorded the vehicle's
    /// actual rate-limited angle instead of the command, and it kept recording for 32 seconds after
    /// the run ended. Both faults produce a plausible-looking number, which is what makes them
    /// worth a test rather than a comment.
    /// </summary>
    public class SteerSmoothnessTests
    {
        private const float CompareHz = 14.08f;
        private const float CompareIntervalS = 1f / CompareHz;

        private static SteerSmoothness Fresh()
        {
            return new SteerSmoothness { SampleIntervalS = CompareIntervalS };
        }

        /// <summary>Feed a command series at a fixed step, the way FixedUpdate would.</summary>
        private static SteerSmoothness Feed(
            SteerSmoothness s, Func<float, float> command, float stepS, float durationS)
        {
            int steps = (int)Math.Round(durationS / stepS);
            for (int i = 1; i <= steps; i++)
            {
                float t = i * stepS;
                s.Sample(command(t), t);
            }

            return s;
        }

        // -------------------------------------------------------------------------------------
        // |delta steer| P95, resampled to the compare rate
        // -------------------------------------------------------------------------------------

        /// <summary>
        /// The reason the measure resamples at all, stated as a test.
        ///
        /// The same driving fed at 50 Hz and at 200 Hz must produce the same percentile. Differenced
        /// per step instead, the two would come out a factor of four apart, and the report would be
        /// comparing physics rates while appearing to compare controllers (research C14, which
        /// found the same thing about frame rate).
        /// </summary>
        [Test]
        public void The_percentile_does_not_depend_on_the_rate_it_was_fed_at()
        {
            const float slope = 0.25f; // command units per second
            Func<float, float> ramp = t => slope * t;

            float at50 = Feed(Fresh(), ramp, 0.02f, 4f).DeltaSteerP95;
            float at200 = Feed(Fresh(), ramp, 0.005f, 4f).DeltaSteerP95;

            float expected = slope * CompareIntervalS;

            // The tolerance is one physics step's worth of slope, because a resampled point lands on
            // the first step at or after the boundary rather than exactly on it.
            Assert.That(at50, Is.EqualTo(expected).Within(slope * 0.02f));
            Assert.That(at200, Is.EqualTo(expected).Within(slope * 0.02f));

            // And the contrast that makes the point: per-step differencing would have reported
            // 0.005 against 0.00125 for these two, which is the same driving and a different answer.
            Assert.That(Math.Abs(at50 - at200), Is.LessThan(slope * 0.02f),
                "the two rates must agree, or the measure is describing the simulation instead of " +
                "the controller");
        }

        [Test]
        public void A_held_command_has_no_steering_change()
        {
            SteerSmoothness s = Feed(Fresh(), _ => 0.6f, 0.02f, 3f);

            Assert.That(s.DeltaSteerP95, Is.EqualTo(0f).Within(1e-6f));
            Assert.That(s.SampleCount, Is.GreaterThan(30),
                "three seconds at 14.08 Hz is about 42 points, so the percentile is over enough " +
                "of them to mean something");
        }

        /// <summary>
        /// The count travels with the percentile because a short run does not produce a measure.
        ///
        /// The argmax run that ended at 5.2 s on seed 1004 contributes roughly seventy points. One
        /// that ends at half a second contributes seven, and a 95th percentile over seven points is
        /// the maximum wearing a percentile's name.
        /// </summary>
        [Test]
        public void The_sample_count_reflects_the_compare_rate_and_not_the_step_rate()
        {
            SteerSmoothness s = Feed(Fresh(), t => 0.1f * t, 0.02f, 5f);

            // 5 s at 14.08 Hz is about 70 points, and the first one carries no delta.
            Assert.That(s.SampleCount, Is.InRange(66, 71));
        }

        [Test]
        public void Nothing_fed_reports_zero_rather_than_dividing_by_an_empty_window()
        {
            var s = Fresh();

            Assert.That(s.DeltaSteerP95, Is.EqualTo(0f));
            Assert.That(s.SignChangesPerS, Is.EqualTo(0f));
            Assert.That(s.SampleCount, Is.EqualTo(0));
            Assert.That(s.MeasuredWindowS, Is.EqualTo(0f));
        }

        // -------------------------------------------------------------------------------------
        // Sign changes, which is what chatter actually is
        // -------------------------------------------------------------------------------------

        /// <summary>
        /// Full-lock chatter, the failure research R2 predicted and T018 falsified.
        ///
        /// Counted at the rate it is fed rather than at the compare rate on purpose: 25 Hz of
        /// reversal is past what a 14.08 Hz series can represent, and a downsampled count would
        /// report a controller tearing the wheel back and forth as calm.
        /// </summary>
        [Test]
        public void Alternating_full_lock_counts_one_change_per_step()
        {
            var s = Fresh();

            for (int i = 1; i <= 50; i++)
            {
                s.Sample(i % 2 == 0 ? 1f : -1f, i * 0.02f);
            }

            Assert.That(s.SignChanges, Is.EqualTo(49));
            Assert.That(s.MeasuredWindowS, Is.EqualTo(0.98f).Within(1e-4f));
            Assert.That(s.SignChangesPerS, Is.EqualTo(50f).Within(0.5f));
        }

        /// <summary>
        /// Easing out of a turn and back into the same one is not a reversal.
        ///
        /// The deadband is remembered across rather than reset on, because a controller relaxing
        /// through centre and turning the same way again is the ordinary shape of a corner exit.
        /// Counting it would make every smooth lap look like chatter.
        /// </summary>
        [Test]
        public void Passing_through_straight_and_back_the_same_way_is_not_a_change()
        {
            var s = Fresh();
            float[] series = { -0.8f, -0.4f, 0f, 0f, -0.4f, -0.8f };

            for (int i = 0; i < series.Length; i++)
            {
                s.Sample(series[i], (i + 1) * 0.02f);
            }

            Assert.That(s.SignChanges, Is.EqualTo(0));
        }

        [Test]
        public void Passing_through_straight_to_the_other_side_is_one_change()
        {
            var s = Fresh();
            float[] series = { -0.8f, 0f, 0f, 0.8f };

            for (int i = 0; i < series.Length; i++)
            {
                s.Sample(series[i], (i + 1) * 0.02f);
            }

            Assert.That(s.SignChanges, Is.EqualTo(1),
                "a genuine reversal passes through zero, so it must be counted once and not twice");
        }

        /// <summary>
        /// The deadband exists because <see cref="RayControllers.WeightedAverage"/> is continuous.
        ///
        /// It settles near zero on a symmetric reading, where floating-point noise alone changes
        /// the sign several times a second. Without a deadband the noise floor would be reported as
        /// the controller's chatter rate, and the smoother controller would score worse than the
        /// one that cannot express a small command at all.
        /// </summary>
        [Test]
        public void Noise_inside_the_deadband_is_not_chatter()
        {
            var s = Fresh();

            for (int i = 1; i <= 100; i++)
            {
                s.Sample(i % 2 == 0 ? 1e-5f : -1e-5f, i * 0.02f);
            }

            Assert.That(s.SignChanges, Is.EqualTo(0));
            Assert.That(s.SignChangesPerS, Is.EqualTo(0f));
        }

        // -------------------------------------------------------------------------------------
        // The run window, which is the fault T018 found in the drive log
        // -------------------------------------------------------------------------------------

        /// <summary>
        /// The window is what was fed, and nothing either side of it.
        ///
        /// T018's trace ran to 37.4 s against a run that ended at 5.2 s, because `DriveLogger` keeps
        /// recording after control is released. Every statistic over that file was diluted by 32
        /// seconds of a stationary car. Here the driver stops feeding when the run ends, so the
        /// window cannot grow afterwards: the trim is structural rather than a step someone has to
        /// remember to perform in the analysis.
        /// </summary>
        [Test]
        public void The_window_covers_only_what_was_fed()
        {
            var s = Fresh();

            for (int i = 1; i <= 50; i++)
            {
                s.Sample(i % 2 == 0 ? 1f : -1f, i * 0.02f);
            }

            float rateAtEndOfRun = s.SignChangesPerS;

            // The car sits still for the next thirty seconds. Nothing is fed, because nothing is
            // being driven.
            Assert.That(s.MeasuredWindowS, Is.EqualTo(0.98f).Within(1e-4f));
            Assert.That(s.SignChangesPerS, Is.EqualTo(rateAtEndOfRun));
            Assert.That(rateAtEndOfRun, Is.GreaterThan(40f),
                "diluted across a 32 s tail this would read about 1.5 per second, which is a " +
                "different and entirely believable answer");
        }

        [Test]
        public void Reset_starts_a_fresh_run()
        {
            SteerSmoothness s = Feed(Fresh(), t => (float)Math.Sin(t * 20f), 0.02f, 3f);
            Assert.That(s.SampleCount, Is.GreaterThan(0));

            s.Reset();

            Assert.That(s.SampleCount, Is.EqualTo(0));
            Assert.That(s.SignChanges, Is.EqualTo(0));
            Assert.That(s.MeasuredWindowS, Is.EqualTo(0f));
        }

        /// <summary>
        /// Changing the compare rate mid-run discards it, because half a series at one rate and
        /// half at another is not a series and the percentile over it would mean nothing.
        /// </summary>
        [Test]
        public void Changing_the_compare_rate_discards_the_run_in_progress()
        {
            SteerSmoothness s = Feed(Fresh(), t => 0.25f * t, 0.02f, 3f);
            Assert.That(s.SampleCount, Is.GreaterThan(0));

            s.SampleIntervalS = 1f / 30f;

            Assert.That(s.SampleCount, Is.EqualTo(0));
            Assert.That(s.SampleIntervalS, Is.EqualTo(1f / 30f).Within(1e-6f));
        }

        [Test]
        public void A_non_positive_interval_falls_back_to_the_dataset_rate()
        {
            var s = new SteerSmoothness { SampleIntervalS = 0f };

            Assert.That(s.SampleIntervalS,
                Is.EqualTo(1f / SteerSmoothness.DefaultCompareHz).Within(1e-6f));
        }

        // -------------------------------------------------------------------------------------
        // The percentile itself, shared with DriveTelemetry
        // -------------------------------------------------------------------------------------

        /// <summary>
        /// Nearest rank, matching what `DriveTelemetry` computed before this method absorbed it.
        ///
        /// The convention has to be pinned because feature 005's figure is placed in the same table
        /// as the human and BC columns, and a linear-interpolation percentile would differ from
        /// this one by about a rank on a short run. That is small enough to be mistaken for a
        /// difference in driving.
        /// </summary>
        [Test]
        public void The_percentile_is_nearest_rank()
        {
            var values = new System.Collections.Generic.List<float>();
            for (int i = 1; i <= 100; i++)
            {
                values.Add(i);
            }

            Assert.That(SteerSmoothness.NearestRankPercentile(values, 95f), Is.EqualTo(95f));
            Assert.That(SteerSmoothness.NearestRankPercentile(values, 100f), Is.EqualTo(100f));
            Assert.That(SteerSmoothness.NearestRankPercentile(values, 1f), Is.EqualTo(1f));
        }

        [Test]
        public void The_percentile_of_nothing_is_zero_rather_than_an_exception()
        {
            Assert.That(SteerSmoothness.NearestRankPercentile(null, 95f), Is.EqualTo(0f));
            Assert.That(
                SteerSmoothness.NearestRankPercentile(new System.Collections.Generic.List<float>(), 95f),
                Is.EqualTo(0f));
        }

        [Test]
        public void The_percentile_does_not_reorder_the_caller_s_list()
        {
            var values = new System.Collections.Generic.List<float> { 3f, 1f, 2f };

            SteerSmoothness.NearestRankPercentile(values, 95f);

            Assert.That(values, Is.EqualTo(new[] { 3f, 1f, 2f }),
                "the live sample buffer is passed straight in, and sorting it in place would " +
                "corrupt the delta between consecutive points");
        }
    }
}
