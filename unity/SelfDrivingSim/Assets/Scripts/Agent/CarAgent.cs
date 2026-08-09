using System.Collections.Generic;
using System.IO;
using UnityEngine;
using SelfDrivingSim.Track;
using SelfDrivingSim.Vehicle;

// The namespace matches the folder, as the other three do. One consequence to know about
// before M3: inside SelfDrivingSim.Agent the bare name `Agent` binds to this namespace, so
// deriving from ML-Agents' Agent must be written `: Unity.MLAgents.Agent`. Written as `:
// Agent` it fails with CS0118, "namespace used like a type", which reads like a missing
// package rather than a name clash.
namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// What the agent can perceive of the world around it (FR-024, FR-025, research C11).
    ///
    /// This component owns the whole observation vector, nineteen values as DESIGN 4.3 lists
    /// them: thirteen ray distances over the semicircle ahead, then the car's own speed in
    /// two components, its yaw rate, its heading to the next marker as two dot products, and
    /// its current steering. The reward that reads all of it belongs to M3 and is not this
    /// class's business.
    ///
    /// **Every value is normalised, and every divisor is derived rather than picked.** Speed
    /// divides by the profile's top speed and the yaw rate by the fastest rotation the car
    /// can physically produce, which is that same top speed on its own minimum-radius circle.
    /// Both come out of <see cref="VehicleProfile"/>, so retuning the car retunes the
    /// observation scale with it instead of leaving the network reading a stale one.
    ///
    /// **This is a MonoBehaviour, not an ML-Agents <c>Agent</c>, and that is deliberate for
    /// M2.** The whole point of the M2 gate is that a person drives the car by keyboard and
    /// reads every observation live against a situation whose correct answer is visible
    /// (T057, T062). An <c>Agent</c> collects observations only when the Academy steps it,
    /// so during a plain human drive there would be nothing to read. M3 wraps this component
    /// in an <c>Agent</c> and forwards these same values into <c>CollectObservations</c>;
    /// nothing here has to change for that.
    ///
    /// **The built-in <c>RayPerceptionSensor3D</c> is not used** (DESIGN 4.3). Its encoding
    /// is a one-hot over tags plus a distance, which is more values than this project needs,
    /// and the numbers that actually reach the network cannot be read while driving. The
    /// verification tasks are the reason the sensing is written out by hand.
    /// </summary>
    public class CarAgent : MonoBehaviour
    {
        // -----------------------------------------------------------------------------------
        // Sensing constants.
        //
        // These mirror RAY_COUNT, RAY_FOV_DEG and RAY_LENGTH_M in python/track/config.py.
        //
        // Since feature 005 they are ALSO carried in Assets/Tracks/vehicle_profile.json, in a
        // sensing block, and this component checks itself against that block at startup. Two
        // gaps, two mechanisms: a pytest mirror test closes config.py against the exported
        // file, and CheckSensingDrift closes the exported file against this scene. Neither
        // alone is enough, because the mirror test never opens the scene and the drift check
        // never runs in CI.
        //
        // They stay serialised rather than becoming const for two reasons: a sweep sets them at
        // runtime (feature 005, FR-013), and a scene that has gone stale is then visible in the
        // Inspector rather than hidden behind a compiled default.
        // -----------------------------------------------------------------------------------

        [Header("Rays (mirrors python/track/config.py)")]
        [Tooltip("RAY_COUNT. Odd on purpose: an odd count puts one ray exactly dead ahead.")]
        [SerializeField] private int rayCount = 13;

        [Tooltip("RAY_FOV_DEG. The semicircle ahead. Nothing behind the car needs avoiding on " +
                 "a one-way loop, and rays spent looking backwards are observations the " +
                 "network has to learn to ignore.")]
        [SerializeField] private float rayFovDeg = 180f;

        [Tooltip("RAY_LENGTH_M. Derived, not chosen: a little over twice the 8.5 m stopping " +
                 "distance at v_max under P95 braking, so a wall enters view with time to " +
                 "react rather than with time only to stop (DESIGN 4.3, research C11).")]
        [SerializeField] private float rayLengthM = 20f;

        [Header("Origin")]
        [Tooltip("Where the rays start. Leave empty to use this transform, raised by the " +
                 "offset below. Every reported distance is measured from this point, and " +
                 "T059 must measure from the same one: see SensorOrigin.")]
        [SerializeField] private Transform sensorOrigin;

        [Tooltip("Local offset applied when no origin transform is assigned.\n\n" +
                 "The height is the value that matters and it is bounded on both sides. The " +
                 "barriers TrackBuilder raises are 0.8 m tall, so a fan above that sees " +
                 "straight over them and reports a clear track with a wall either side; the " +
                 "road itself is at zero, so a fan too low grazes the surface. The car's own " +
                 "origin sits at 0.5 m in the Track scene, and -0.1 puts the rays at 0.4 m, " +
                 "the middle of the barrier, with room for the body to pitch and bounce " +
                 "without leaving it.")]
        [SerializeField] private Vector3 sensorOffsetLocal = new Vector3(0f, -0.1f, 0f);

        [Header("Self state (FR-026)")]
        [Tooltip("The car whose speed, steering and limits are observed. Leave empty to " +
                 "search this object and its parents.")]
        [SerializeField] private CarController car;

        [Tooltip("The progress markers. The heading observation is measured against this " +
                 "ring's next marker; without one, both heading values read zero.")]
        [SerializeField] private CheckpointRing ring;

        [Header("What counts as an obstacle")]
        [Tooltip("Layers the rays may hit. Everything by default; the car's own colliders are " +
                 "excluded in code rather than by layer, so no project-settings change is " +
                 "needed for the sensing to be correct.")]
        [SerializeField] private LayerMask obstacleMask = ~0;

        /// <summary>Number of rays. The first half of the observation vector's length.</summary>
        public int RayCount => rayCount;

        /// <summary>Angular span ahead, in degrees.</summary>
        public float RayFovDeg => rayFovDeg;

        /// <summary>Range of a single ray, in metres. Also the divisor of the encoding.</summary>
        public float RayLengthM => rayLengthM;

        /// <summary>Degrees between neighbouring rays. 15 at the stated 13 rays over 180.</summary>
        public float RaySpacingDeg => rayCount > 1 ? rayFovDeg / (rayCount - 1) : 0f;

        /// <summary>
        /// The observation itself: one value per ray, in [0, 1], left to right.
        ///
        /// **A miss and a hit at zero are opposite situations and are encoded at opposite ends
        /// of the range** (FR-025). A ray that hits nothing reads <b>1.0</b>: the full, free
        /// distance. A ray that hits reads <c>distance / RayLengthM</c>, so a wall against the
        /// bumper reads <b>0.0</b>. The naive alternative - reporting the range itself on a
        /// miss and calling it a large number - collapses "clear ahead" and "wall at 20 m"
        /// onto one value, which is harmless, but the mirrored mistake of encoding a miss as 0
        /// makes the safest reading identical to the most dangerous one.
        /// </summary>
        public IReadOnlyList<float> RayDistancesNorm => _distancesNorm;

        /// <summary>
        /// Raw hit distances in metres, for the debug panel and for T059. A ray that hit
        /// nothing carries <see cref="RayLengthM"/> here, so read <see cref="RayHit"/> to tell
        /// a genuine hit at the range limit from a miss.
        /// </summary>
        public IReadOnlyList<float> RayDistancesM => _distancesM;

        /// <summary>Whether each ray found anything at all within range.</summary>
        public IReadOnlyList<bool> RayHit => _hitFlags;

        /// <summary>
        /// The point every distance is measured from. T059 parks the car at known distances
        /// from a barrier and checks the readings within 5 percent; measuring that distance
        /// from the bumper while the sensor sits at the car's centre would fail the check on
        /// an offset rather than on the sensing.
        /// </summary>
        public Vector3 SensorOrigin =>
            sensorOrigin != null
                ? sensorOrigin.position
                : transform.TransformPoint(sensorOffsetLocal);

        // -----------------------------------------------------------------------------------
        // Self state (FR-026). Six values, all in [-1, 1].
        // -----------------------------------------------------------------------------------

        /// <summary>
        /// Speed along the car's nose, divided by the profile's top speed. Negative when
        /// reversing, which is a state the car can genuinely be in: holding the brake at a
        /// standstill backs it up.
        /// </summary>
        public float SpeedForwardNorm { get; private set; }

        /// <summary>
        /// Speed across the car, on the same scale. Zero when the car goes where it points
        /// and large when it is sliding, so it is the only observation that tells the agent
        /// it has lost the back end. Reported separately rather than folded into a magnitude
        /// for exactly that reason.
        /// </summary>
        public float SpeedLateralNorm { get; private set; }

        /// <summary>
        /// Yaw rate divided by <see cref="MaxYawRateRadPerS"/>, positive turning right.
        ///
        /// Only the yaw component is observed. Pitch and roll are suspension motion on a car
        /// that is meant never to leave the ground (SC-006), so feeding them in would hand
        /// the network the spring rates as if they were information about the track.
        /// </summary>
        public float YawRateNorm { get; private set; }

        /// <summary>
        /// How squarely the car faces the next marker: the dot product of its heading with
        /// the direction to that marker. 1 is straight at it, 0 is abeam, -1 is directly
        /// away.
        /// </summary>
        public float HeadingForwardDot { get; private set; }

        /// <summary>
        /// Which side the next marker lies on: positive to the right, negative to the left.
        ///
        /// The pair is what makes the heading readable. The forward dot alone is symmetric -
        /// it cannot separate a marker 30 degrees to the left from one 30 degrees to the
        /// right - so an agent given only that value would have to guess which way to turn.
        /// </summary>
        public float HeadingRightDot { get; private set; }

        /// <summary>Steering as commanded, already in [-1, 1]. Lets the agent be smooth.</summary>
        public float SteerNorm { get; private set; }

        /// <summary>
        /// The fastest the car can turn, in radians per second: top speed on the tightest
        /// circle it can describe. Derived from the profile, never typed in, so the yaw
        /// observation cannot end up scaled against a car that no longer exists.
        /// </summary>
        public float MaxYawRateRadPerS =>
            car != null && car.Profile != null && car.Profile.RMinM > 0.01f
                ? car.Profile.vMaxMs / car.Profile.RMinM
                : 1f;

        /// <summary>Length of the observation vector. Thirteen rays plus six (DESIGN 4.3).</summary>
        public int ObservationCount => rayCount + SelfStateCount;

        /// <summary>How many values follow the rays.</summary>
        public const int SelfStateCount = 6;

        /// <summary>
        /// The whole observation vector in the order M3 will feed it to the network: rays
        /// first, then the six self-state values in the order DESIGN 4.3 lists them.
        ///
        /// Held as one array so the debug panel and the future <c>CollectObservations</c>
        /// read the same thing. A panel that assembled its own copy could show a correct
        /// value beside a network being fed a wrong one, and T062 is specified as reading the
        /// panel.
        /// </summary>
        public IReadOnlyList<float> Observations => _observations;

        /// <summary>Names for the panel, index for index with <see cref="Observations"/>.</summary>
        public string ObservationName(int index)
        {
            if (index < rayCount)
            {
                return $"ray {index:D2} @ {RayAngleDeg(index):+0;-0;0}°";
            }

            switch (index - rayCount)
            {
                case 0: return "speed forward";
                case 1: return "speed lateral";
                case 2: return "yaw rate";
                case 3: return "heading forward·dir";
                case 4: return "heading right·dir";
                case 5: return "steering";
                default: return "?";
            }
        }

        private float[] _distancesNorm = new float[0];
        private float[] _distancesM = new float[0];
        private bool[] _hitFlags = new bool[0];
        private float[] _observations = new float[0];

        // Reused so that sensing at 50 Hz allocates nothing.
        private readonly RaycastHit[] _hits = new RaycastHit[16];
        private Rigidbody _body;

        private void Awake()
        {
            _body = GetComponentInParent<Rigidbody>();

            if (car == null)
            {
                car = GetComponentInParent<CarController>();
            }

            Allocate();
            CheckSensingDrift();
        }

        /// <summary>
        /// Whether a sweep is driving the fan, which suppresses the drift check.
        ///
        /// During a sweep the scene deliberately disagrees with the exported block, and one
        /// error per seed would bury the run it was meant to protect. Every run record carries
        /// its own fan, so the configuration behind a figure stays recoverable from the results.
        /// </summary>
        public bool FanOverridden { get; private set; }

        /// <summary>
        /// Set the fan at runtime, for the sensing sweep (feature 005, FR-013).
        ///
        /// Rewriting the exported file per configuration would need a domain reload between
        /// configurations, and SC-004's five minute budget cannot afford one per configuration
        /// let alone per seed.
        ///
        /// <paramref name="lengthM"/> is left alone by default because it is derived from the
        /// stopping distance (research C11) rather than chosen, so sweeping it would be sweeping
        /// a consequence rather than a parameter.
        /// </summary>
        public void ConfigureFan(int count, float fovDeg, float lengthM = -1f)
        {
            rayCount = Mathf.Max(1, count);
            rayFovDeg = Mathf.Clamp(fovDeg, 0f, 360f);

            if (lengthM > 0f)
            {
                rayLengthM = lengthM;
            }

            FanOverridden = true;
            Allocate();
        }

        /// <summary>
        /// Check the serialised fan against the exported sensing block, and shout if they differ.
        ///
        /// This is the same check <see cref="SelfDrivingSim.Logging.DriveTelemetry"/> already runs
        /// over the vehicle profile, for the same reason and against the same failure. The scene
        /// holds its own copy of every serialised value, and retuning a constant in config.py does
        /// not touch it. That happened once already, with the steering rate in T023: the scene kept
        /// 2.0 while everything else moved to 3.7, and the only symptom would have been a drive
        /// that mysteriously failed to improve.
        ///
        /// The Python mirror test cannot catch this. It compares the constants against the JSON
        /// and never opens the scene.
        ///
        /// **It reports and never corrects.** Quietly rewriting the fan would mean the values in
        /// the Inspector no longer describe the run, which is the same class of problem this
        /// exists to catch.
        /// </summary>
        private void CheckSensingDrift()
        {
            if (FanOverridden)
            {
                return;
            }

            string path = Path.Combine(Application.dataPath, "Tracks", "vehicle_profile.json");
            if (!File.Exists(path))
            {
                // A clone that has not run the exporter yet is a setup state, not a corrupted
                // one. DriveTelemetry warns rather than errors here too.
                Debug.LogWarning($"[CarAgent] {path} not found, so the ray fan is unchecked. " +
                                 "Run: python -m python.track.vehicle", this);
                return;
            }

            VehicleProfileFile file;
            try
            {
                file = JsonUtility.FromJson<VehicleProfileFile>(File.ReadAllText(path));
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[CarAgent] could not read {path}: {e.Message}", this);
                return;
            }

            if (file == null)
            {
                Debug.LogError($"[CarAgent] {path} did not parse as a vehicle profile.", this);
                return;
            }

            if (file.schema_version != VehicleProfileFile.ExpectedSchemaVersion)
            {
                Debug.LogError(
                    $"[CarAgent] vehicle_profile.json is schema_version {file.schema_version}, " +
                    $"expected {VehicleProfileFile.ExpectedSchemaVersion}. Regenerate it with " +
                    "python -m python.track.vehicle.", this);
                return;
            }

            if (file.sensing == null)
            {
                Debug.LogError(
                    "[CarAgent] vehicle_profile.json carries no sensing block, so the ray fan " +
                    "is unchecked. Regenerate it with python -m python.track.vehicle.", this);
                return;
            }

            CheckField("ray_count", file.sensing.ray_count, rayCount);
            CheckField("ray_fov_deg", file.sensing.ray_fov_deg, rayFovDeg);
            CheckField("ray_length_m", file.sensing.ray_length_m, rayLengthM);
        }

        private void CheckField(string name, float exported, float inScene)
        {
            const float tol = 1e-4f;
            if (Mathf.Abs(exported - inScene) <= tol)
            {
                return;
            }

            Debug.LogError(
                $"[CarAgent] {name}: the scene is sensing with {inScene} but " +
                $"vehicle_profile.json says {exported}. The serialised copy on this component " +
                "has gone stale. Fix it in the Inspector, then run again: this run senses with " +
                "a different fan from the one every document describes.", this);
        }

        private void OnValidate()
        {
            rayCount = Mathf.Max(1, rayCount);
            rayFovDeg = Mathf.Clamp(rayFovDeg, 0f, 360f);
            rayLengthM = Mathf.Max(0.01f, rayLengthM);

            if (rayCount % 2 == 0)
            {
                Debug.LogWarning(
                    $"[CarAgent] {rayCount} rays is even, so no ray looks straight ahead. " +
                    "The stated value is 13 (DESIGN 4.3).", this);
            }

            Allocate();
        }

        private void Allocate()
        {
            if (_distancesNorm.Length == rayCount)
            {
                return;
            }

            _distancesNorm = new float[rayCount];
            _distancesM = new float[rayCount];
            _hitFlags = new bool[rayCount];
            _observations = new float[rayCount + SelfStateCount];
        }

        /// <summary>
        /// Sensed on the physics clock, not per rendered frame.
        ///
        /// Rays are cast against collider positions, which only move when physics steps, so
        /// sensing in Update would re-measure the same world several times over on a fast
        /// machine and produce observations that changed at the frame rate rather than at the
        /// simulation rate. It is the same reason DriveTelemetry samples on its own clock.
        /// </summary>
        private void FixedUpdate()
        {
            Sense();
        }

        /// <summary>
        /// Cast every ray and refresh the readings. Public so a test or a measurement can
        /// take a reading at a moment of its choosing rather than waiting for a physics step.
        /// </summary>
        public void Sense()
        {
            Allocate();

            Vector3 origin = SensorOrigin;
            Vector3 forward = FlatForward();
            float half = rayFovDeg * 0.5f;

            for (int i = 0; i < rayCount; i++)
            {
                float angle = rayCount > 1 ? -half + i * RaySpacingDeg : 0f;
                Vector3 direction = Quaternion.AngleAxis(angle, Vector3.up) * forward;

                bool hit = NearestHit(origin, direction, out float distance);

                _hitFlags[i] = hit;
                _distancesM[i] = hit ? distance : rayLengthM;
                _distancesNorm[i] = hit ? Mathf.Clamp01(distance / rayLengthM) : 1f;
                _observations[i] = _distancesNorm[i];
            }

            SenseSelf(forward);
        }

        /// <summary>
        /// Refresh the six self-state values and append them to the observation vector
        /// (FR-026).
        ///
        /// Everything is clamped into [-1, 1]. The clamp is a guard, not a scale: the
        /// divisors are the car's own limits, so a value reaching the clamp means the car has
        /// exceeded a limit it is supposed to hold. That has happened before - a governor
        /// comparing against the wrong speed let the car reach 16.2 m/s against a stated 10 -
        /// and an unclamped observation would have handed the network a number outside the
        /// range every other observation lives in rather than showing up as a saturated one.
        /// </summary>
        private void SenseSelf(Vector3 forward)
        {
            Vector3 right = Vector3.Cross(Vector3.up, forward);

            if (car != null && _body != null)
            {
                float vMax = Mathf.Max(0.01f, car.Profile.vMaxMs);
                Vector3 velocity = _body.linearVelocity;

                SpeedForwardNorm = Mathf.Clamp(Vector3.Dot(velocity, forward) / vMax, -1f, 1f);
                SpeedLateralNorm = Mathf.Clamp(Vector3.Dot(velocity, right) / vMax, -1f, 1f);

                // Yaw about world up. Unity yaws right for a positive rotation about +Y, so
                // this already agrees in sign with the steering input beside it in the vector
                // and with RayAngleDeg. Worth stating rather than leaving to be rediscovered:
                // two adjacent observations disagreeing about which way is right trains
                // perfectly well and cannot be read by a person.
                float yawRate = _body.angularVelocity.y;
                YawRateNorm = Mathf.Clamp(yawRate / Mathf.Max(0.01f, MaxYawRateRadPerS), -1f, 1f);

                SteerNorm = Mathf.Clamp(car.SteerNorm, -1f, 1f);
            }
            else
            {
                SpeedForwardNorm = 0f;
                SpeedLateralNorm = 0f;
                YawRateNorm = 0f;
                SteerNorm = 0f;
            }

            Transform marker = ring != null ? ring.NextMarker : null;
            if (marker != null)
            {
                // Flattened for the same reason the ray fan is: a marker's trigger volume is
                // three metres tall and its origin sits half that above the road, so an
                // unflattened direction reads as slightly uphill and the dot product falls
                // short of 1 even with the car aimed straight at it.
                Vector3 toMarker =
                    Vector3.ProjectOnPlane(marker.position - SensorOrigin, Vector3.up);

                if (toMarker.sqrMagnitude > 1e-6f)
                {
                    toMarker.Normalize();
                    HeadingForwardDot = Vector3.Dot(forward, toMarker);
                    HeadingRightDot = Vector3.Dot(right, toMarker);
                }
            }
            else
            {
                HeadingForwardDot = 0f;
                HeadingRightDot = 0f;
            }

            int at = rayCount;
            _observations[at + 0] = SpeedForwardNorm;
            _observations[at + 1] = SpeedLateralNorm;
            _observations[at + 2] = YawRateNorm;
            _observations[at + 3] = HeadingForwardDot;
            _observations[at + 4] = HeadingRightDot;
            _observations[at + 5] = SteerNorm;
        }

        /// <summary>
        /// World direction of ray <paramref name="index"/>, on the ground plane.
        ///
        /// Exposed so the debug panel draws the rays that were actually cast rather than its
        /// own reconstruction of them. A panel drawing a fan that disagrees with the sensing
        /// would be worse than one drawing nothing.
        /// </summary>
        public Vector3 RayDirection(int index)
        {
            return Quaternion.AngleAxis(RayAngleDeg(index), Vector3.up) * FlatForward();
        }

        /// <summary>The angle of ray <paramref name="index"/>, in degrees, right positive.</summary>
        public float RayAngleDeg(int index)
        {
            if (rayCount <= 1)
            {
                return 0f;
            }

            return -rayFovDeg * 0.5f + index * RaySpacingDeg;
        }

        /// <summary>
        /// The car's heading flattened onto the ground plane.
        ///
        /// The rays sweep a horizontal fan, not one fixed to the body. A car pitches nose-down
        /// under braking and rolls in a corner, and a fan rigidly attached to the body tilts
        /// with it: the same wall reads further away because the ray now travels diagonally to
        /// it, and hard enough braking aims the whole fan into the road surface. The distances
        /// would then vary with suspension travel, which is a property of the springs and not
        /// of the track ahead.
        /// </summary>
        private Vector3 FlatForward()
        {
            Vector3 flat = Vector3.ProjectOnPlane(transform.forward, Vector3.up);
            if (flat.sqrMagnitude > 1e-6f)
            {
                return flat.normalized;
            }

            // Nose pointing at the sky or the ground: the heading is whatever the roof says.
            flat = Vector3.ProjectOnPlane(transform.up, Vector3.up);
            return flat.sqrMagnitude > 1e-6f ? flat.normalized : Vector3.forward;
        }

        /// <summary>
        /// Nearest obstacle along one ray, ignoring the car itself.
        ///
        /// Two things are excluded, and both would otherwise be reported as walls.
        ///
        /// **The car.** The origin sits inside the vehicle, so a plain raycast finds the body
        /// collider and the WheelColliders before anything else and every ray reads nearly
        /// zero. Rejecting hits that share this car's Rigidbody handles both, and the
        /// transform-root test catches any child collider that was left without one. Doing it
        /// here rather than with a layer means the sensing is correct in any scene, without a
        /// project-settings change that a fresh clone would have to reproduce.
        ///
        /// **Triggers.** The checkpoints are trigger volumes spanning the full track width
        /// (TrackBuilder), so a fan that saw triggers would report a wall straight ahead
        /// every time the next marker came into range - exactly where the track is clear.
        /// </summary>
        private bool NearestHit(Vector3 origin, Vector3 direction, out float distance)
        {
            distance = 0f;

            int count = Physics.RaycastNonAlloc(
                origin, direction, _hits, rayLengthM, obstacleMask,
                QueryTriggerInteraction.Ignore);

            bool found = false;
            float nearest = float.PositiveInfinity;

            for (int i = 0; i < count; i++)
            {
                if (IsSelf(_hits[i].collider))
                {
                    continue;
                }

                if (_hits[i].distance < nearest)
                {
                    nearest = _hits[i].distance;
                    found = true;
                }
            }

            if (found)
            {
                distance = nearest;
            }

            return found;
        }

        private bool IsSelf(Collider collider)
        {
            if (collider == null)
            {
                return true;
            }

            if (_body != null && collider.attachedRigidbody == _body)
            {
                return true;
            }

            return collider.transform.root == transform.root;
        }

        /// <summary>
        /// Draw the fan in the Scene view: green where the ray is clear, red to the hit point.
        ///
        /// This is how T059 is actually carried out. A number in a panel says a barrier is
        /// 7.3 m away; the gizmo says which barrier, and whether the ray reporting it is the
        /// one being aimed at.
        /// </summary>
        private void OnDrawGizmosSelected()
        {
            if (!Application.isPlaying)
            {
                Sense();
            }

            Vector3 origin = SensorOrigin;
            Vector3 forward = FlatForward();

            for (int i = 0; i < rayCount && i < _distancesM.Length; i++)
            {
                Vector3 direction = Quaternion.AngleAxis(RayAngleDeg(i), Vector3.up) * forward;
                Gizmos.color = _hitFlags[i] ? Color.red : Color.green;
                Gizmos.DrawLine(origin, origin + direction * _distancesM[i]);
            }
        }
    }
}
