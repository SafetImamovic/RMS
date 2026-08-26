using System;
using System.Collections.Generic;
using NUnit.Framework;
using SelfDrivingSim.Track;
using UnityEngine;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The progress term, tested against a polyline the test hands in (feature 007, FR-005, FR-007).
    ///
    /// No track, no car, no physics step. <see cref="TrackProgress"/> takes positions rather than
    /// transforms precisely so that the two properties the whole feature rests on can be asserted
    /// here in milliseconds:
    ///
    /// <list type="number">
    /// <item><b>It telescopes.</b> The sum of the term over any trajectory equals the difference of
    /// the clamped position between the endpoints, and nothing else.</item>
    /// <item><b>A loop earns zero.</b> Any path returning the car to a state it already occupied
    /// pays exactly nothing.</item>
    /// </list>
    ///
    /// The second is what preserves DESIGN 4.5's anti-farming invariant. It is preserved by the
    /// shape of the term rather than by a weight chosen small enough, which is the reason a
    /// one-sided or clamped version of this reward was rejected in the design rather than merely
    /// avoided in the code. **If either of these two fails, no training run is worth starting**:
    /// the run would be measuring a different reward from the one the design describes.
    /// </summary>
    public class TrackProgressTests
    {
        private const int MarkerCount = 24;
        private const float Side = 50f;
        private const float CheckpointReward = 1.0f;

        /// <summary>
        /// Research R9's tolerance: 0.1 per cent relative, with an absolute floor.
        ///
        /// The floor exists because the loop case has an endpoint difference of zero, and a
        /// relative tolerance there is an impossible one. It is deliberately not a machine-epsilon
        /// figure: the test is checking that the term telescopes, not that the polyline is an exact
        /// model of a circle.
        /// </summary>
        private static double Tolerance(TrackProgress p, double expected)
        {
            double floor = p.ProgressWeight * 0.01;
            return Math.Max(Math.Abs(expected) * 0.001, floor);
        }

        // --- the chain the tests drive on -----------------------------------------------------

        /// <summary>A regular 24-gon, so every segment has the same length and the arithmetic is
        /// checkable by hand.</summary>
        private static List<Vector3> Ring(int count = MarkerCount, float radius = Side)
        {
            var markers = new List<Vector3>(count);
            for (int i = 0; i < count; i++)
            {
                float a = 2f * Mathf.PI * i / count;
                markers.Add(new Vector3(radius * Mathf.Cos(a), 0f, radius * Mathf.Sin(a)));
            }

            return markers;
        }

        private static TrackProgress Configured(out List<Vector3> markers)
        {
            markers = Ring();
            var progress = new TrackProgress();
            progress.Configure(markers, CheckpointReward);
            return progress;
        }

        /// <summary>
        /// Walk the car along the chain marker by marker, in <paramref name="stepsPerSegment"/>
        /// physics steps each, exactly as the ring would see it: the due marker advances as each is
        /// reached, and the lap count rises when the due marker comes back round to the start.
        /// </summary>
        private static double DriveMarkers(
            TrackProgress p, List<Vector3> markers, int originIndex, int markersToTake,
            int stepsPerSegment = 20)
        {
            int n = markers.Count;
            double sum = 0.0;
            int laps = 0;

            for (int taken = 0; taken < markersToTake; taken++)
            {
                int from = (originIndex + taken) % n;
                int due = (from + 1) % n;

                for (int s = 1; s <= stepsPerSegment; s++)
                {
                    float t = (float)s / stepsPerSegment;
                    Vector3 at = Vector3.Lerp(markers[from], markers[due], t);
                    sum += p.Step(at, due, laps);
                }

                // The marker is taken on arrival. The ring increments the lap in the same call that
                // wraps the due index, so the two move together here as well.
                if ((due + 1) % n == (originIndex + 1) % n)
                {
                    laps++;
                }
            }

            return sum;
        }

        // --- T004, T010: the chain and the derived weight -------------------------------------

        [Test]
        public void Chain_length_is_the_sum_of_its_segments()
        {
            var p = Configured(out var markers);

            double byHand = 0.0;
            for (int i = 0; i < markers.Count; i++)
            {
                byHand += Vector3.Distance(markers[i], markers[(i + 1) % markers.Count]);
            }

            Assert.That(p.ChainLength, Is.EqualTo(byHand).Within(1e-6));
        }

        [Test]
        public void Weight_is_derived_so_a_lap_of_progress_pays_half_a_lap_of_markers()
        {
            var p = Configured(out _);

            // DESIGN 4.5: alpha x 24.0 / chain length. The point of the test is the product, not
            // the quotient: driving the whole chain must pay half of what taking every marker pays.
            double lapPayout = p.ProgressWeight * p.ChainLength;
            Assert.That(lapPayout,
                Is.EqualTo(TrackProgress.LapPayoutFraction * MarkerCount * CheckpointReward)
                    .Within(1e-4));
        }

        [Test]
        public void Weight_tracks_the_chain_it_was_built_from()
        {
            // A literal weight would pay a different fraction of a lap on every generated seed.
            // Two chains of different size must still both pay 12.0 for a lap.
            var small = new TrackProgress();
            small.Configure(Ring(MarkerCount, 25f), CheckpointReward);

            var large = new TrackProgress();
            large.Configure(Ring(MarkerCount, 100f), CheckpointReward);

            Assert.That(small.ProgressWeight, Is.Not.EqualTo(large.ProgressWeight));
            Assert.That(small.ProgressWeight * small.ChainLength,
                Is.EqualTo(large.ProgressWeight * large.ChainLength).Within(1e-4));
        }

        // --- T018: the degenerate chain -------------------------------------------------------

        [Test]
        public void Coincident_markers_fail_at_configure_rather_than_at_run_time()
        {
            var markers = Ring();
            markers[7] = markers[6];

            // A zero-length segment is a division by zero in the weight and an infinite reward at
            // run time. The build is the only place where noticing it is cheap.
            Assert.Throws<ArgumentException>(() => new TrackProgress().Configure(markers, CheckpointReward));
        }

        [Test]
        public void A_chain_that_failed_validation_pays_nothing_rather_than_paying_the_old_weight()
        {
            // The agent catches the throw and logs it rather than letting an exception out of
            // OnEpisodeBegin once per episode. That only helps if the failed Configure leaves the
            // term inert: keeping the previous track's weight while carrying the new track's
            // geometry would pay a wrong number quietly, which is worse than paying none.
            var p = Configured(out var good);
            Assert.That(p.ProgressWeight, Is.GreaterThan(0f));

            var broken = Ring();
            broken[7] = broken[6];
            Assert.Throws<ArgumentException>(() => p.Configure(broken, CheckpointReward));

            Assert.That(p.ProgressWeight, Is.EqualTo(0f));
            p.Reset(1);
            p.Step(good[0], 1, 0);
            Assert.That(p.Step(Vector3.Lerp(good[0], good[1], 0.5f), 1, 0), Is.EqualTo(0f));
        }

        // --- T016: the first step -------------------------------------------------------------

        [Test]
        public void First_step_of_an_episode_pays_nothing()
        {
            var p = Configured(out var markers);
            p.Reset(1);

            // Deliberately not at the origin: a car placed with lateral offset and yaw is already
            // some way along its first segment. Differencing that against zero would pay out the
            // whole arc position on step one of every episode.
            Vector3 wellAlong = Vector3.Lerp(markers[0], markers[1], 0.9f);
            Assert.That(p.Step(wellAlong, 1, 0), Is.EqualTo(0f));
            Assert.That(p.LastAdvance, Is.EqualTo(0.0));
        }

        [Test]
        public void Reset_restores_the_no_previous_state()
        {
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);
            p.Step(Vector3.Lerp(markers[0], markers[1], 0.5f), 1, 0);
            Assert.That(p.HasPrevious, Is.True);

            p.Reset(1);
            Assert.That(p.HasPrevious, Is.False);
            Assert.That(p.Step(Vector3.Lerp(markers[0], markers[1], 0.5f), 1, 0), Is.EqualTo(0f));
        }

        [Test]
        public void A_swap_to_a_different_chain_cannot_leave_a_stale_position_behind()
        {
            // Feature 006 found TrainingArea.SwapTo ending episodes by a route that bypassed the
            // reward reporting. If the same route bypassed this reset, the first step on the new
            // track would difference against a position belonging to the old one, and it would read
            // as noise rather than as a bug.
            var p = new TrackProgress();
            var first = Ring(MarkerCount, 50f);
            p.Configure(first, CheckpointReward);
            p.Reset(1);
            DriveMarkers(p, first, 0, 6);

            var second = Ring(MarkerCount, 90f);
            p.Configure(second, CheckpointReward);
            p.Reset(1);

            Assert.That(p.Step(second[0], 1, 0), Is.EqualTo(0f));
        }

        // --- T012: telescoping. This one blocks every training run ----------------------------

        [Test]
        public void Sum_over_a_full_lap_equals_the_endpoint_difference()
        {
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            double start = p.Clamped;
            double sum = DriveMarkers(p, markers, 0, MarkerCount);
            double expected = p.ProgressWeight * (p.Clamped - start);

            Assert.That(sum, Is.EqualTo(expected).Within(Tolerance(p, expected)));
        }

        [Test]
        public void A_full_lap_pays_half_of_what_its_markers_pay()
        {
            // The number the scripted-driver check in T022 predicts before the lap is driven:
            // 0.5 x 24 x 1.0 = 12.0, from any start marker, because a lap covers the whole chain.
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            double sum = DriveMarkers(p, markers, 0, MarkerCount);
            Assert.That(sum, Is.EqualTo(12.0).Within(Tolerance(p, 12.0)));
        }

        [Test]
        public void The_prediction_does_not_depend_on_where_the_lap_started()
        {
            // A randomised start changes the origin, not the distance round. If this failed, the
            // per-lap prediction would be a function of the start index and T022 could not check it
            // against one number.
            foreach (int origin in new[] { 0, 5, 13, 23 })
            {
                var p = Configured(out var markers);
                p.Reset((origin + 1) % MarkerCount);
                p.Step(markers[origin], (origin + 1) % MarkerCount, 0);

                double sum = DriveMarkers(p, markers, origin, MarkerCount);
                Assert.That(sum, Is.EqualTo(12.0).Within(Tolerance(p, 12.0)),
                    $"lap starting at marker {origin}");
            }
        }

        [Test]
        public void Telescoping_survives_three_laps()
        {
            // SC-001 of feature 006 asks for three clean laps, so the finish line is crossed twice
            // mid-episode. This is the case a position that reset at the line would fail.
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            double start = p.Clamped;
            double sum = DriveMarkers(p, markers, 0, MarkerCount * 3);
            double expected = p.ProgressWeight * (p.Clamped - start);

            Assert.That(sum, Is.EqualTo(expected).Within(Tolerance(p, expected)));
            Assert.That(sum, Is.EqualTo(36.0).Within(Tolerance(p, 36.0)));
        }

        // --- T013: the loop property. This one blocks every training run ----------------------

        [Test]
        public void A_path_that_returns_where_it_started_earns_exactly_nothing()
        {
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            double sum = 0.0;

            // Out along the segment and back again, twenty times. This is the shape of the farming
            // a one-sided term would pay for: it never takes a marker and never goes anywhere.
            for (int cycle = 0; cycle < 20; cycle++)
            {
                for (int s = 1; s <= 10; s++)
                {
                    sum += p.Step(Vector3.Lerp(markers[0], markers[1], 0.08f * s), 1, 0);
                }

                for (int s = 9; s >= 0; s--)
                {
                    sum += p.Step(Vector3.Lerp(markers[0], markers[1], 0.08f * s), 1, 0);
                }
            }

            Assert.That(sum, Is.EqualTo(0.0).Within(Tolerance(p, 0.0)));
        }

        [Test]
        public void Circling_for_a_whole_episode_earns_nothing_from_this_term()
        {
            // DESIGN 4.5's anti-farming invariant, restated for the new term. Driving in circles on
            // open ground must not earn what a lap through the markers earns. Here it earns zero,
            // so the invariant's existing arithmetic against SpeedReward is untouched.
            var p = Configured(out var markers);
            p.Reset(1);

            const int StepsPerTurn = 60;
            Vector3 centre = Vector3.Lerp(markers[0], markers[1], 0.5f);

            // The angle is taken modulo one turn rather than growing without bound, so the last
            // position is bit-for-bit the first and the test measures the term rather than the
            // precision of Mathf.Cos at 628 radians.
            Vector3 OnCircle(int step)
            {
                float a = 2f * Mathf.PI * (step % StepsPerTurn) / StepsPerTurn;
                return centre + new Vector3(2f * Mathf.Cos(a), 0f, 2f * Mathf.Sin(a));
            }

            // Seed on the circle itself. Seeding at a marker and then starting the circle somewhere
            // else makes the first step a teleport across half a segment, and the sum then measures
            // that jump rather than the loop. That is the same class of error the first-step rule
            // and the swap reset exist to prevent, and it is worth one comment here because the
            // test caught it in its own first draft.
            Assert.That(p.Step(OnCircle(0), 1, 0), Is.EqualTo(0f));

            double sum = 0.0;
            for (int step = 1; step <= 6000; step++)
            {
                sum += p.Step(OnCircle(step), 1, 0);
            }

            // 6000 steps is a whole episode by DESIGN 4.6, and 6000 is a whole number of turns, so
            // the car ends exactly where it began.
            Assert.That(sum, Is.EqualTo(0.0).Within(Tolerance(p, 0.0)));
        }

        // --- T015: symmetry -------------------------------------------------------------------

        [Test]
        public void Driving_a_stretch_backwards_costs_what_driving_it_forwards_paid()
        {
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            double forward = 0.0;
            for (int s = 1; s <= 10; s++)
            {
                forward += p.Step(Vector3.Lerp(markers[0], markers[1], 0.09f * s), 1, 0);
            }

            double back = 0.0;
            for (int s = 9; s >= 0; s--)
            {
                back += p.Step(Vector3.Lerp(markers[0], markers[1], 0.09f * s), 1, 0);
            }

            Assert.That(forward, Is.GreaterThan(0.0));
            Assert.That(back, Is.EqualTo(-forward).Within(Tolerance(p, forward)));
        }

        [Test]
        public void Reversing_past_the_wrong_way_distance_costs_what_the_design_says()
        {
            // DESIGN 4.5 states the double charge as a number so it is not later read as an
            // oversight: 3.43 m of reversing costs about -0.204 of progress on the nominal chain,
            // on top of the -1.0 the ring's wrong-way term charges.
            var p = new TrackProgress();
            var markers = Ring(MarkerCount, 32.2f);  // chain of about 202.3 m, as measured in T060
            p.Configure(markers, CheckpointReward);

            double perMetre = p.ProgressWeight;
            Assert.That(p.ChainLength, Is.EqualTo(202.3).Within(1.0));
            Assert.That(3.43 * perMetre, Is.EqualTo(0.204).Within(0.01));
        }

        // --- T014: no jump at a marker --------------------------------------------------------

        [Test]
        public void Crossing_a_marker_charges_only_that_steps_movement()
        {
            // This is the failure the design rejected the distance-to-next-marker potential to
            // avoid: that version jumps from about zero to a full 8.43 m gap at the instant the
            // marker is taken, charging a whole segment as a penalty for the step in which the car
            // did the right thing.
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            // Right up to marker 1, still due.
            p.Step(Vector3.Lerp(markers[0], markers[1], 0.98f), 1, 0);

            // Marker 1 taken, so the due marker becomes 2 and the car has moved a little past it.
            float atMarker = p.Step(Vector3.Lerp(markers[1], markers[2], 0.02f), 2, 0);

            double segment = p.ChainLength / MarkerCount;
            double movedThisStep = 0.02 * segment + 0.02 * segment;

            Assert.That(atMarker, Is.GreaterThan(0f));
            Assert.That(atMarker, Is.EqualTo(movedThisStep * p.ProgressWeight)
                .Within(Tolerance(p, movedThisStep * p.ProgressWeight)));
        }

        [Test]
        public void Crossing_the_finish_line_charges_only_that_steps_movement()
        {
            // The same claim at the one place per lap where a position that reset would charge a
            // whole lap of penalty in a single step.
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);
            DriveMarkers(p, markers, 0, MarkerCount - 1);

            // Approaching marker 0 again, which is the one that completes the lap.
            p.Step(Vector3.Lerp(markers[23], markers[0], 0.98f), 0, 0);

            // Taken: the ring wraps the due index and increments the lap in the same call.
            float atFinish = p.Step(Vector3.Lerp(markers[0], markers[1], 0.02f), 1, 1);

            double segment = p.ChainLength / MarkerCount;
            double movedThisStep = 0.02 * segment + 0.02 * segment;

            Assert.That(atFinish, Is.GreaterThan(0f));
            Assert.That(atFinish, Is.EqualTo(movedThisStep * p.ProgressWeight)
                .Within(Tolerance(p, movedThisStep * p.ProgressWeight)));
        }

        // --- T017: the clamp ------------------------------------------------------------------

        [Test]
        public void A_car_past_its_due_marker_earns_nothing_further()
        {
            var p = Configured(out var markers);
            p.Reset(1);
            p.Step(markers[0], 1, 0);

            // Marker 1 is still due, but the car is geometrically most of the way to marker 2.
            // The ring refuses to award the shortcut; the geometry must refuse to pay for it.
            double first = p.Step(Vector3.Lerp(markers[1], markers[2], 0.8f), 1, 0);
            double further = p.Step(Vector3.Lerp(markers[2], markers[3], 0.8f), 1, 0);

            Assert.That(p.AtCeiling, Is.True);
            Assert.That(further, Is.EqualTo(0.0).Within(Tolerance(p, 0.0)));

            // And what it did earn is capped at the one segment it was entitled to.
            double segment = p.ChainLength / MarkerCount;
            Assert.That(first, Is.LessThanOrEqualTo(segment * p.ProgressWeight + 1e-4));
        }

        [Test]
        public void The_shortcut_is_worth_no_more_than_the_legal_path()
        {
            // FR-008 stated as a comparison rather than as a property of the clamp: cutting from
            // marker 0 straight across to marker 4 must not pay more than driving the four
            // segments between them.
            var legal = Configured(out var markers);
            legal.Reset(1);
            legal.Step(markers[0], 1, 0);
            double legalSum = DriveMarkers(legal, markers, 0, 4);

            var cutting = Configured(out _);
            cutting.Reset(1);
            cutting.Step(markers[0], 1, 0);

            double cutSum = 0.0;
            for (int s = 1; s <= 80; s++)
            {
                // Straight across the infield to marker 4, never touching 1, 2 or 3, so the ring
                // still has marker 1 due the whole way.
                cutSum += cutting.Step(Vector3.Lerp(markers[0], markers[4], s / 80f), 1, 0);
            }

            Assert.That(cutSum, Is.LessThan(legalSum));
        }
    }
}
