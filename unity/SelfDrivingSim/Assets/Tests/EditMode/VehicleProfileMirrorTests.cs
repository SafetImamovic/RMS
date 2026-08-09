using System.IO;
using NUnit.Framework;
using SelfDrivingSim.Vehicle;
using UnityEngine;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The C# vehicle profile must agree with the Python one, field for field.
    ///
    /// Python owns these numbers: it derives them, tests them, and writes them to
    /// Assets/Tracks/vehicle_profile.json. C# keeps a compiled copy so the car does not
    /// read a file every frame. That duplication is the risk, and this fixture is the
    /// answer to it. Without these tests the two could drift apart and the only symptom
    /// would be tracks validated for a car that does not exist.
    ///
    /// Regenerate the JSON with: python -m python.track.vehicle
    /// </summary>
    public class VehicleProfileMirrorTests
    {
        // Float, not double, on the C# side, so the tolerance has to clear single precision
        // over values around 10. It stays far tighter than any difference that would matter.
        private const float Tolerance = 1e-4f;

        private VehicleProfileRecord _exported;
        private CalibrationEnvelope _envelope;
        private VehicleProfile _compiled;

        [SetUp]
        public void LoadExportedProfile()
        {
            string path = Path.Combine(Application.dataPath, "Tracks", "vehicle_profile.json");
            Assert.IsTrue(
                File.Exists(path),
                $"vehicle_profile.json missing at {path}. Run: python -m python.track.vehicle");

            var file = JsonUtility.FromJson<VehicleProfileFile>(File.ReadAllText(path));
            Assert.AreEqual(2, file.schema_version, "Unrecognised profile schema version.");

            _exported = file.profile;
            _envelope = file.envelope;
            _compiled = new VehicleProfile();
        }

        [Test]
        public void EnvelopeCarriesEveryFigureTheHudJudgesAgainst()
        {
            Assert.IsNotNull(_envelope, "envelope block missing from vehicle_profile.json");
            Assert.AreEqual(1.0f, _envelope.steer_abs_max, Tolerance, "steer_abs_max");
            Assert.AreEqual(0.30f, _envelope.dsteer_p95_track1, Tolerance, "dsteer_p95_track1");
            Assert.AreEqual(0.70f, _envelope.dsteer_p95_track2, Tolerance, "dsteer_p95_track2");
            Assert.AreEqual(1.00f, _envelope.dsteer_max, Tolerance, "dsteer_max");
            Assert.AreEqual(14.08f, _envelope.compare_hz, Tolerance, "compare_hz");

            // Unit free, and the only speed comparison FR-004 permits.
            Assert.AreEqual(1.2552f, _envelope.speed_max_over_p99, 0.001f, "speed_max_over_p99");
            Assert.AreEqual(
                _envelope.speed_max / _envelope.speed_p99,
                _envelope.speed_max_over_p99,
                1e-3f,
                "the exported ratio must agree with the two figures it came from");
        }

        [Test]
        public void CompiledBaseValuesMatchThePythonExport()
        {
            Assert.AreEqual(_exported.wheelbase_m, _compiled.wheelbaseM, Tolerance, "wheelbase_m");
            Assert.AreEqual(_exported.steer_max_deg, _compiled.steerMaxDeg, Tolerance, "steer_max_deg");
            Assert.AreEqual(_exported.steer_rate_norm_per_s, _compiled.steerRateNormPerS, Tolerance, "steer_rate_norm_per_s");
            Assert.AreEqual(_exported.v_max_ms, _compiled.vMaxMs, Tolerance, "v_max_ms");
            Assert.AreEqual(_exported.accel_ms2, _compiled.accelMs2, Tolerance, "accel_ms2");
            Assert.AreEqual(_exported.brake_ms2, _compiled.brakeMs2, Tolerance, "brake_ms2");
            Assert.AreEqual(_exported.radius_margin, _compiled.radiusMargin, Tolerance, "radius_margin");
        }

        [Test]
        public void DerivedValuesMatchThePythonExport()
        {
            // Recomputed on this side rather than read across, so a bug in the C# bicycle
            // model shows up here instead of during a keyboard drive.
            Assert.AreEqual(_exported.r_min_m, _compiled.RMinM, Tolerance, "r_min_m");
            Assert.AreEqual(_exported.r_floor_m, _compiled.RFloorM, Tolerance, "r_floor_m");
            Assert.AreEqual(_exported.max_required_steer, _compiled.MaxRequiredSteer, Tolerance, "max_required_steer");
            Assert.AreEqual(_exported.steering_reserve, _compiled.SteeringReserve, Tolerance, "steering_reserve");
        }

        [Test]
        public void DerivedValuesMatchResearchC1()
        {
            // The published table, asserted on the Unity side too. It is quoted in the
            // research document and on the defense slide; both halves must honour it.
            Assert.AreEqual(5.361f, _compiled.RMinM, 0.001f, "r_min");
            Assert.AreEqual(6.970f, _compiled.RFloorM, 0.001f, "r_floor");
            Assert.AreEqual(0.789f, _compiled.MaxRequiredSteer, 0.001f, "max required steer");
            Assert.AreEqual(0.211f, _compiled.SteeringReserve, 0.001f, "steering reserve");
        }

        [Test]
        public void FullLockRadiusMatchesTheMinimum()
        {
            Assert.AreEqual(_compiled.RMinM, _compiled.RadiusForSteering(1f), Tolerance);
        }

        [Test]
        public void StraightAheadHasNoFiniteRadius()
        {
            Assert.IsTrue(float.IsPositiveInfinity(_compiled.RadiusForSteering(0f)));
        }

        [Test]
        public void SteeringIsUnsignedInRadiusTerms()
        {
            // Left and right describe the same circle. The sign belongs to the track.
            Assert.AreEqual(
                _compiled.RadiusForSteering(0.5f),
                _compiled.RadiusForSteering(-0.5f),
                Tolerance);
        }

        [Test]
        public void SensingRangeStillClearsTheStoppingDistance()
        {
            // FR-025: the ray range is derived from the stopping distance, not chosen. If
            // the braking figure is retuned in T024 without moving RAY_LENGTH_M, this fails.
            const float rayLengthM = 20.0f; // python/track/config.py RAY_LENGTH_M
            float stopping = VehicleProfile.StoppingDistanceM(_compiled.vMaxMs, _compiled.brakeMs2);

            Assert.Less(stopping, 9.0f, "stopping distance drifted from the research C11 figure of 8.5 m");
            Assert.Greater(rayLengthM, 2f * stopping, "ray range must clear twice the stopping distance");
        }
    }
}
