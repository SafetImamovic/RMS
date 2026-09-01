using System.IO;
using NUnit.Framework;
using UnityEngine;
using SelfDrivingSim.Track;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// Re-measure a committed track's geometry in C# and check it against what the file claims.
    ///
    /// Every other test in this project checks one side or the other. These check that the two
    /// sides agree, which is the failure nothing else can see: Python proves a track is
    /// drivable, Unity builds something subtly different, and the disagreement surfaces months
    /// later as an agent that will not learn. Measured here rather than trusted, so a change
    /// on either side breaks a test instead of a training run.
    /// </summary>
    public class TrackGeometryTests
    {
        private VehicleProfile _profile;
        private string[] _files;

        [SetUp]
        public void SetUp()
        {
            _profile = new VehicleProfile();

            string dir = Path.Combine(Application.dataPath, "Tracks");
            _files = Directory.Exists(dir)
                ? Directory.GetFiles(dir, "seed_*.json")
                : new string[0];

            if (_files.Length == 0)
            {
                Assert.Ignore("no committed tracks; run python -m python.track.export --batch all");
            }
        }

        private TrackFileRecord First()
        {
            return TrackFile.Load(_files[0], _profile);
        }

        // -----------------------------------------------------------------------------------
        // Radius, re-measured from the points
        // -----------------------------------------------------------------------------------

        /// <summary>
        /// Curvature of the circle through three consecutive points.
        ///
        /// Menger curvature: 4 * area / (product of the three side lengths). Independent of
        /// the polar expression Python uses, which is the point. Agreeing with a formula that
        /// shares no algebra with the original is evidence; agreeing with itself is not.
        /// </summary>
        private static float RadiusThrough(Vector2 a, Vector2 b, Vector2 c)
        {
            float area2 = Mathf.Abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x));
            if (area2 < 1e-12f)
            {
                return float.PositiveInfinity;
            }

            return (a - b).magnitude * (b - c).magnitude * (c - a).magnitude / (2f * area2);
        }

        [Test]
        public void TheMinimumRadiusMeasuredInUnityMatchesWhatTheFileClaims()
        {
            TrackFileRecord record = First();
            int n = record.centre_line.Length;

            float smallest = float.PositiveInfinity;
            for (int i = 0; i < n; i++)
            {
                Vector2 a = Point(record, (i - 1 + n) % n);
                Vector2 b = Point(record, i);
                Vector2 c = Point(record, (i + 1) % n);

                smallest = Mathf.Min(smallest, RadiusThrough(a, b, c));
            }

            // Three-point curvature on a sampled curve is close to but not identical with the
            // analytic value, so this is a tolerance rather than an equality. Five percent is
            // far tighter than the gap that would matter: the check being defended is whether
            // the tightest corner clears a floor, and the margin there is measured in metres.
            Assert.That(smallest,
                Is.EqualTo(record.geometry_report.min_radius_m).Within(5f).Percent,
                $"Unity measures {smallest:F2} m where the file claims " +
                $"{record.geometry_report.min_radius_m:F2} m");
        }

        [Test]
        public void EveryCommittedTrackClearsTheRadiusFloorWhenMeasuredInUnity()
        {
            foreach (string file in _files)
            {
                TrackFileRecord record = TrackFile.Load(file, _profile);
                int n = record.centre_line.Length;

                float smallest = float.PositiveInfinity;
                for (int i = 0; i < n; i++)
                {
                    smallest = Mathf.Min(smallest, RadiusThrough(
                        Point(record, (i - 1 + n) % n), Point(record, i),
                        Point(record, (i + 1) % n)));
                }

                Assert.That(smallest, Is.GreaterThan(_profile.RFloorM * 0.95f),
                    $"{Path.GetFileName(file)} has a corner of {smallest:F2} m against a " +
                    $"floor of {_profile.RFloorM:F2} m");
            }
        }

        private static Vector2 Point(TrackFileRecord record, int i)
        {
            return new Vector2(record.centre_line[i].x, record.centre_line[i].y);
        }

        // -----------------------------------------------------------------------------------
        // Arc length and closure
        // -----------------------------------------------------------------------------------

        [Test]
        public void TheTotalLengthMeasuredInUnityMatchesWhatTheFileClaims()
        {
            TrackFileRecord record = First();
            int n = record.centre_line.Length;

            float measured = 0f;
            for (int i = 0; i < n; i++)
            {
                // Includes the closing segment from the last point back to the first, which is
                // a real part of a closed loop and is where an off-by-one would hide.
                measured += (Point(record, (i + 1) % n) - Point(record, i)).magnitude;
            }

            Assert.That(measured, Is.EqualTo(record.total_length_m).Within(1f).Percent);
        }

        [Test]
        public void ArcLengthInTheFileAgreesWithDistanceMeasuredAlongThePoints()
        {
            TrackFileRecord record = First();

            float walked = 0f;
            for (int i = 1; i < record.centre_line.Length; i++)
            {
                walked += (Point(record, i) - Point(record, i - 1)).magnitude;

                // s is what checkpoint spacing and the separation check are built on, so a
                // drift between it and the actual geometry would silently misplace every gate.
                Assert.That(record.centre_line[i].s, Is.EqualTo(walked).Within(0.5f),
                    $"s drifts from measured distance at index {i}");
            }
        }

        [Test]
        public void TheLoopClosesWithinOneSampleStep()
        {
            TrackFileRecord record = First();
            int n = record.centre_line.Length;

            float gap = (Point(record, 0) - Point(record, n - 1)).magnitude;
            float step = record.total_length_m / n;

            Assert.That(gap, Is.LessThan(step * 2f),
                "the last point is further from the first than one ordinary segment, " +
                "so the loop does not close");
        }

        // -----------------------------------------------------------------------------------
        // Checkpoints
        // -----------------------------------------------------------------------------------

        [Test]
        public void CheckpointsAreOrderedAndEvenlySpacedByArcLength()
        {
            TrackFileRecord record = First();
            CheckpointRecord[] gates = record.checkpoints;

            float expected = record.total_length_m / gates.Length;

            for (int i = 1; i < gates.Length; i++)
            {
                Assert.That(gates[i].s, Is.GreaterThan(gates[i - 1].s),
                    $"checkpoint {i} is not after checkpoint {i - 1}");
                Assert.That(gates[i].s - gates[i - 1].s,
                    Is.EqualTo(expected).Within(1f).Percent,
                    $"checkpoints {i - 1} to {i} are not evenly spaced by arc length");
            }
        }

        [Test]
        public void EveryCheckpointLiesOnTheCentreLine()
        {
            TrackFileRecord record = First();
            float step = record.total_length_m / record.centre_line.Length;

            foreach (CheckpointRecord gate in record.checkpoints)
            {
                var at = new Vector2(gate.x, gate.y);
                float nearest = float.PositiveInfinity;

                for (int i = 0; i < record.centre_line.Length; i++)
                {
                    nearest = Mathf.Min(nearest, (Point(record, i) - at).magnitude);
                }

                Assert.That(nearest, Is.LessThan(step * 2f),
                    $"checkpoint {gate.index} sits {nearest:F3} m off the centre line");
            }
        }

        [Test]
        public void CheckpointHeadingsAreUnitVectorsPointingAlongTheTrack()
        {
            TrackFileRecord record = First();

            foreach (CheckpointRecord gate in record.checkpoints)
            {
                var forward = new Vector2(gate.forward_x, gate.forward_y);
                Assert.That(forward.magnitude, Is.EqualTo(1f).Within(0.01f),
                    $"checkpoint {gate.index} has a heading of length {forward.magnitude:F4}");
            }

            // Consecutive gates must turn gradually. A reversed heading would still be a unit
            // vector and would still pass the check above, while pointing the car backwards.
            for (int i = 1; i < record.checkpoints.Length; i++)
            {
                var a = new Vector2(record.checkpoints[i - 1].forward_x,
                                    record.checkpoints[i - 1].forward_y);
                var b = new Vector2(record.checkpoints[i].forward_x,
                                    record.checkpoints[i].forward_y);

                Assert.That(Vector2.Dot(a, b), Is.GreaterThan(0f),
                    $"checkpoint {i} faces away from checkpoint {i - 1}");
            }
        }

        // -----------------------------------------------------------------------------------
        // Required steering, recomputed from the bicycle model
        // -----------------------------------------------------------------------------------

        [Test]
        public void RequiredSteeringRecomputedInUnityMatchesTheStoredValue()
        {
            TrackFileRecord record = First();

            for (int i = 0; i < record.centre_line.Length; i += 97)
            {
                CentrePointRecord point = record.centre_line[i];
                float expected =
                    Mathf.Atan(_profile.wheelbaseM / point.radius_m) / _profile.SteerMaxRad;

                Assert.That(point.required_steer, Is.EqualTo(expected).Within(1e-3f),
                    $"required_steer at index {i} disagrees with the bicycle model");
            }
        }

        [Test]
        public void NoStoredDemandExceedsWhatTheProfilePermits()
        {
            foreach (string file in _files)
            {
                TrackFileRecord record = TrackFile.Load(file, _profile);

                foreach (CentrePointRecord point in record.centre_line)
                {
                    Assert.That(point.required_steer,
                        Is.LessThanOrEqualTo(_profile.MaxRequiredSteer + 1e-3f),
                        $"{Path.GetFileName(file)} demands {point.required_steer:F4}, " +
                        $"above the permitted {_profile.MaxRequiredSteer:F4}");
                }
            }
        }
    }
}
