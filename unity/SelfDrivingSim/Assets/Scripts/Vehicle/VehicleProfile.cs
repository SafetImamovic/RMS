using System;
using UnityEngine;

namespace SelfDrivingSim.Vehicle
{
    /// <summary>
    /// Every limit the car has, mirroring python/track/config.py field for field.
    ///
    /// The three numbers that matter - the minimum turning radius, the floor a track's
    /// corners may not go below, and the steering such a corner demands - are computed
    /// properties, never serialised fields. A profile whose stored radius disagrees with
    /// its wheelbase is the easiest way for this feature to go quietly wrong, so the type
    /// makes that state impossible to represent.
    ///
    /// The Python side owns these values. This class holds its own copy so the car does not
    /// have to read a file at runtime, and VehicleProfileMirrorTests compares the two
    /// against Assets/Tracks/vehicle_profile.json. A drift fails a test rather than
    /// producing geometry that is silently calibrated for a different car.
    /// </summary>
    [Serializable]
    public class VehicleProfile
    {
        [Tooltip("Distance between axles. The one freely chosen value; every radius scales with it (research C1).")]
        public float wheelbaseM = 2.5f;

        [Tooltip("Road-wheel angle at full lock. Fixed by DESIGN 4.4.")]
        public float steerMaxDeg = 25.0f;

        [Tooltip("How fast the steering input may travel, normalised units per second (research C4).\n\n" +
                 "Settled by T023 from a measured drive, not chosen: at 2.0 a 91 s keyboard drive " +
                 "produced a 95th-percentile steering change of 0.1615, which passed its band but " +
                 "sat on the floor of it. 3.7 targets track1's measured 0.30.")]
        public float steerRateNormPerS = 3.7f;

        [Tooltip("Top speed. A playability choice, never used in a dataset comparison (research C3).")]
        public float vMaxMs = 10.0f;

        [Tooltip("Achievable acceleration, m/s^2.")]
        public float accelMs2 = 5.0f;

        [Tooltip("Achievable deceleration, m/s^2. Also the figure RAY_LENGTH_M is derived from.")]
        public float brakeMs2 = 5.85f;

        [Tooltip("Safety factor on the minimum radius. Equals the steering reserve (research C2).")]
        public float radiusMargin = 1.3f;

        /// <summary>Full lock in radians.</summary>
        public float SteerMaxRad => steerMaxDeg * Mathf.Deg2Rad;

        /// <summary>
        /// Tightest circle the car can describe, at full lock and low speed.
        /// Bicycle model: R = L / tan(delta).
        /// </summary>
        public float RMinM => wheelbaseM / Mathf.Tan(SteerMaxRad);

        /// <summary>Tightest corner a generated track may contain.</summary>
        public float RFloorM => RMinM * radiusMargin;

        /// <summary>
        /// Steering a corner at RFloorM demands, normalised to [0, 1].
        /// Independent of wheelbase: L cancels, so the margin alone controls it (research C2).
        /// </summary>
        public float MaxRequiredSteer =>
            Mathf.Atan(Mathf.Tan(SteerMaxRad) / radiusMargin) / SteerMaxRad;

        /// <summary>Fraction of steering left free in the tightest legal corner.</summary>
        public float SteeringReserve => 1.0f - MaxRequiredSteer;

        /// <summary>
        /// Turning radius for a normalised steering input. Returns positive infinity for
        /// straight ahead, which is the correct neutral element when taking a minimum.
        /// </summary>
        public float RadiusForSteering(float steerNorm)
        {
            float s = Mathf.Abs(Mathf.Clamp(steerNorm, -1f, 1f));
            if (Mathf.Approximately(s, 0f))
            {
                return float.PositiveInfinity;
            }

            return wheelbaseM / Mathf.Tan(s * SteerMaxRad);
        }

        /// <summary>Stopping distance from a speed at a deceleration. v^2 / 2a.</summary>
        public static float StoppingDistanceM(float vMs, float decelMs2)
        {
            return (vMs * vMs) / (2f * decelMs2);
        }
    }

    /// <summary>
    /// The shape of Assets/Tracks/vehicle_profile.json, written by
    /// <c>python -m python.track.vehicle</c>. Only the tests read this; the car uses the
    /// values compiled into VehicleProfile above.
    /// </summary>
    [Serializable]
    public class VehicleProfileFile
    {
        /// <summary>
        /// 3 since feature 005 added the sensing block. A reader that does not recognise the
        /// version refuses rather than reading a block that may have moved.
        /// </summary>
        public const int ExpectedSchemaVersion = 3;

        public int schema_version;
        public string source;
        public VehicleProfileRecord profile;
        public CalibrationEnvelope envelope;
        public SensingBlock sensing;
    }

    /// <summary>
    /// The ray fan, as Python exported it (feature 005, FR-016).
    ///
    /// These three numbers are serialised a second time on <c>CarAgent</c>, which is what the car
    /// actually senses with. That duplication is the same shape as the vehicle profile's, and it
    /// fails the same way: the scene keeps its own copy, and retuning a constant in
    /// <c>config.py</c> does not touch it.
    ///
    /// It has happened once already on this project, with the steering rate in T023, and the only
    /// symptom was a drive that mysteriously failed to improve. The Python mirror test cannot
    /// catch it, because it compares the constants against the JSON and never opens the scene.
    /// <c>CarAgent</c> checks itself against this block at startup for exactly that reason.
    ///
    /// Ray spacing is deliberately absent: it is <c>ray_fov_deg / (ray_count - 1)</c>, derived at
    /// both ends. A stored spacing would be a third copy able to disagree with the two it came
    /// from.
    ///
    /// Contract: specs/005-heuristic-ray-driver/contracts/sensing-block.md
    /// </summary>
    [Serializable]
    public class SensingBlock
    {
        public int ray_count;
        public float ray_fov_deg;
        public float ray_length_m;
    }

    /// <summary>
    /// The M1 measurements a live drive is judged against (FR-009).
    ///
    /// These are read from the exported file rather than retyped here on purpose. A retyped
    /// threshold is free to drift away from what M1 actually measured, and a HUD showing
    /// green against a drifted threshold is worse than no HUD: it reports a calibration that
    /// was never achieved.
    /// </summary>
    [Serializable]
    public class CalibrationEnvelope
    {
        /// <summary>Full lock, reached in both directions on both recordings.</summary>
        public float steer_abs_max;

        /// <summary>Per-frame steering change at compare_hz, one figure per recording.</summary>
        public float dsteer_p95_track1;
        public float dsteer_p95_track2;

        /// <summary>
        /// Full range in a single frame. Evidence about the recording device, not a target:
        /// a car that reproduced this would be unsteerable (research C4).
        /// </summary>
        public float dsteer_max;

        /// <summary>Dataset units. Never compared directly, only through the ratio below.</summary>
        public float speed_p99;
        public float speed_max;

        /// <summary>
        /// Shape of the speed distribution, unit free. The only speed figure that may be
        /// compared against the simulation, because the recorded column has no documented
        /// unit (FR-004, research C3).
        /// </summary>
        public float speed_max_over_p99;

        /// <summary>Rate every per-frame quantity must be resampled to before comparison.</summary>
        public float compare_hz;
    }

    /// <summary>
    /// Snake-case to match the JSON exactly. Unity's JsonUtility maps by field name, so
    /// renaming any of these to C# convention would silently produce zeroes.
    /// </summary>
    [Serializable]
    public class VehicleProfileRecord
    {
        public float wheelbase_m;
        public float steer_max_deg;
        public float steer_rate_norm_per_s;
        public float v_max_ms;
        public float accel_ms2;
        public float brake_ms2;
        public float radius_margin;
        public float r_min_m;
        public float r_floor_m;
        public float max_required_steer;
        public float steering_reserve;
    }
}
