using System.Globalization;
using UnityEngine;
using SelfDrivingSim.Track;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// Drives the car from the ray distances alone, with no model and no training
    /// (feature 005, DESIGN 4.7).
    ///
    /// **What it may look at, and why the boundary matters (FR-001).** Only
    /// <see cref="CarAgent.RayDistancesNorm"/> and the car's own speed. Not the track file, not
    /// the checkpoint positions, not the centre line. A baseline that can see more than the thing
    /// it is a baseline for measures nothing, and the whole point of this component is to say what
    /// a simple heuristic achieves before any PPO or BC number is called an achievement.
    ///
    /// The end conditions below do read the checkpoint ring, and that is deliberate and separate:
    /// they decide when a RUN STOPS, never how the car steers. Stopping is the harness's business.
    /// Nothing the ring reports reaches <see cref="Decide"/>.
    ///
    /// **Everything happens in FixedUpdate**, the same clock <see cref="CarAgent"/> senses on and
    /// <see cref="CarController"/> applies forces on. A control loop in Update runs at the
    /// rendering rate, so a frame-rate hiccup changes how long an input is held and the trajectory
    /// diverges. FR-011 asks for runs that reproduce, and this is the whole of how that is
    /// achieved (research R6).
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class HeuristicDriver : MonoBehaviour
    {
        /// <summary>Why a run stopped. Written into every run record (FR-010).</summary>
        public enum EndReason
        {
            Running = 0,
            LapComplete,
            TimeLimit,
            WallContact,
            WrongWay,
            FellThrough,
            NoProgress,
        }

        [Header("Controller")]
        [Tooltip("Which steering strategy this run uses. Selectable without a code change so a " +
                 "comparison runs the same build twice rather than two builds once (FR-007).")]
        [SerializeField] private RayControllers.Strategy strategy = RayControllers.Strategy.MostOpen;

        [Tooltip("Off by default. With this disabled the keyboard behaves exactly as it did " +
                 "before this feature existed (FR-003, SC-007).")]
        [SerializeField] private bool engaged;

        [Header("Wiring")]
        [SerializeField] private CarAgent agent;
        [SerializeField] private CarController car;

        [Tooltip("Read only to decide when a run ends, never to decide how to steer.")]
        [SerializeField] private CheckpointRing ring;

        [Header("Run limits")]
        [Tooltip("Laps to complete before the run ends successfully.")]
        [SerializeField] private int lapsToComplete = 1;

        [Tooltip("Seconds before the run is abandoned.\n\n" +
                 "Derived rather than picked: the human laps recorded in T051 came in around " +
                 "34 s, and this driver is not expected to be fast, so three times the human " +
                 "figure with rounding leaves room for a slow but successful lap while still " +
                 "ending a run that is going nowhere. FR-005 needs a defined end state because a " +
                 "sweep that hangs on one seed never finishes.")]
        [SerializeField] private float timeLimitS = 120f;

        [Tooltip("Seconds without a new checkpoint before the run is called stuck. Mirrors the " +
                 "60 s in DESIGN 4.6, so a car wedged against a barrier does not burn the whole " +
                 "time limit.")]
        [SerializeField] private float noProgressLimitS = 60f;

        [Tooltip("End the run on the first wall contact. SC-001 counts a lap only if the car " +
                 "never touched a barrier, so continuing after a contact measures a lap that " +
                 "has already failed.")]
        [SerializeField] private bool endOnWallContact = true;

        // --- Outcome, read by the sweep runner and the run record ------------------------------

        /// <summary>Whether the driver currently holds the wheel.</summary>
        public bool Engaged => engaged;

        /// <summary>Which strategy is in effect.</summary>
        public RayControllers.Strategy ActiveStrategy => strategy;

        /// <summary>Why the run stopped, or <see cref="EndReason.Running"/> while it has not.</summary>
        public EndReason Outcome { get; private set; } = EndReason.Running;

        /// <summary>Simulated seconds since the run began.</summary>
        public float ElapsedS { get; private set; }

        /// <summary>Barrier contacts so far. Zero is what SC-001 requires for a clean lap.</summary>
        public int WallContacts { get; private set; }

        /// <summary>The command last sent to the car, for the HUD and the trace.</summary>
        public float LastSteer { get; private set; }

        /// <summary>The speed the longitudinal rule is currently asking for, in m/s.</summary>
        public float TargetSpeedMs { get; private set; }

        private float _lastProgressS;
        private int _lastAwarded;
        private int _lapsAtStart;
        private int _fallResetsAtStart;
        private bool _wasEngaged;
        private float[] _angles = new float[0];

        private void Awake()
        {
            if (car == null) { car = GetComponent<CarController>(); }
            if (agent == null) { agent = GetComponentInChildren<CarAgent>(); }
            if (agent == null) { agent = FindAnyObjectByType<CarAgent>(); }
            if (ring == null) { ring = FindAnyObjectByType<CheckpointRing>(); }
        }

        private void Start()
        {
            BeginRun();
        }

        /// <summary>Restart the run bookkeeping. The sweep calls this between seeds.</summary>
        public void BeginRun()
        {
            Outcome = EndReason.Running;
            ElapsedS = 0f;
            WallContacts = 0;
            _lastProgressS = 0f;
            _lastAwarded = ring != null ? ring.AwardedCount : 0;
            _lapsAtStart = ring != null ? ring.LapCount : 0;
            _fallResetsAtStart = car != null ? car.FallResetCount : 0;
        }

        /// <summary>Take or release the wheel. The sweep and the Inspector both use this.</summary>
        public void SetEngaged(bool value)
        {
            engaged = value;
        }

        /// <summary>Choose the strategy for the next run (FR-007).</summary>
        public void SetStrategy(RayControllers.Strategy value)
        {
            strategy = value;
        }

        private void FixedUpdate()
        {
            // Exactly one source of control is in effect at a time (FR-004). A scripted manoeuvre
            // is a calibration run with a fixed input sequence, and two components writing
            // ScriptedMove would produce a car driven by whichever ran last in the frame order,
            // which is not a thing anyone could reason about.
            var scripted = GetComponent<ScriptedDriver>();
            bool blocked = scripted != null && scripted.IsRunning;

            bool shouldDrive = engaged && !blocked && Outcome == EndReason.Running;

            if (shouldDrive != _wasEngaged)
            {
                Debug.Log(string.Format(CultureInfo.InvariantCulture,
                    "[HeuristicDriver] control -> {0}{1}",
                    shouldDrive ? "heuristic (" + strategy + ")" : "released",
                    blocked ? ", blocked by ScriptedDriver" : string.Empty), this);
                _wasEngaged = shouldDrive;
            }

            if (!shouldDrive)
            {
                // Release rather than hold the last command, so the keyboard takes over instead
                // of the car continuing on a stale input.
                if (car != null && car.ScriptedMove.HasValue && !blocked)
                {
                    car.ScriptedMove = null;
                }

                return;
            }

            ElapsedS += Time.fixedDeltaTime;

            car.ScriptedMove = Decide();

            CheckEndConditions();
        }

        /// <summary>
        /// The whole control decision: steering from the rays, throttle from the steering.
        ///
        /// Nothing here reads the track, the ring or the clock. Given the same distance array and
        /// the same speed it returns the same command, which is what makes the strategies testable
        /// in isolation and what keeps FR-001 checkable by reading rather than by trusting.
        /// </summary>
        private Vector2 Decide()
        {
            EnsureAngles();

            float steer = RayControllers.Steer(
                strategy, agent.RayDistancesNorm, _angles, car.Profile.steerMaxDeg);

            LastSteer = steer;
            TargetSpeedMs = TargetSpeedFor(steer, car.Profile);

            // Throttle is a bang-bang response to the speed error, not a PID. A PID would settle
            // faster and would also introduce three constants that would have to be tuned, and a
            // tuned heuristic stops being a baseline (spec Out of Scope). ScriptedDriver already
            // holds a speed the same crude way for the same reason.
            float speed = car.SpeedMs;
            float throttle;
            if (speed < TargetSpeedMs - 0.25f)
            {
                throttle = 1f;
            }
            else if (speed > TargetSpeedMs + 0.25f)
            {
                throttle = -1f;
            }
            else
            {
                throttle = 0f;
            }

            return new Vector2(steer, throttle);
        }

        /// <summary>
        /// The fastest the car may go while holding the corner its own steering asks for.
        ///
        /// **Longitudinal control is not an extra here, it is the difference between finishing and
        /// not** (research R1). Grip gives about 5.85 m/s^2 laterally, so the tightest corner the
        /// generator produces, 6.97 m, caps cornering at 6.39 m/s against a 10 m/s top speed. The
        /// crossover is 17.1 m: below that radius, full throttle asks for more lateral
        /// acceleration than the tyres can supply, and C9 records that these tracks curve
        /// everywhere. A flat-throttle driver understeers into a barrier on most corners.
        ///
        /// The radius comes from the steering command through the same bicycle model the track
        /// generator used, so the driver and the tracks agree about what a corner costs. Every
        /// constant is read from the profile rather than typed here, which means retuning the car
        /// retunes the driver instead of leaving it calibrated to a vehicle that no longer exists.
        /// </summary>
        private static float TargetSpeedFor(float steerNorm, VehicleProfile profile)
        {
            float abs = Mathf.Abs(steerNorm);

            // Straight ahead has no finite radius, so grip does not limit anything.
            if (abs < 1e-3f)
            {
                return profile.vMaxMs;
            }

            float radius = profile.RadiusForSteering(abs);
            if (radius <= 0f || float.IsInfinity(radius))
            {
                return profile.vMaxMs;
            }

            // brakeMs2 is the measured deceleration, which is the best figure this project has for
            // what the tyres can do. Using it laterally assumes a roughly circular friction
            // budget, which is the standard simplification and is stated rather than hidden.
            float grip = Mathf.Sqrt(profile.brakeMs2 * radius);
            return Mathf.Min(grip, profile.vMaxMs);
        }

        private void EnsureAngles()
        {
            if (_angles.Length == agent.RayCount)
            {
                return;
            }

            _angles = new float[agent.RayCount];
            for (int i = 0; i < _angles.Length; i++)
            {
                _angles[i] = agent.RayAngleDeg(i);
            }
        }

        /// <summary>
        /// Decide whether the run is over (FR-005).
        ///
        /// Every path out of a run ends here, because a sweep that silently drops a seed reports
        /// an acceptance rate over a denominator that quietly shrank.
        /// </summary>
        private void CheckEndConditions()
        {
            if (ring != null && ring.LapCount - _lapsAtStart >= lapsToComplete)
            {
                Finish(EndReason.LapComplete);
                return;
            }

            if (car != null && car.FallResetCount > _fallResetsAtStart)
            {
                Finish(EndReason.FellThrough);
                return;
            }

            if (ring != null && ring.WrongWay)
            {
                // The forward fan cannot tell a car facing backwards that it is: it sees open
                // track and drives confidently the wrong way (research R9). The ring can tell,
                // so it ends the run rather than the driver pretending to notice.
                Finish(EndReason.WrongWay);
                return;
            }

            if (endOnWallContact && WallContacts > 0)
            {
                Finish(EndReason.WallContact);
                return;
            }

            if (ring != null && ring.AwardedCount != _lastAwarded)
            {
                _lastAwarded = ring.AwardedCount;
                _lastProgressS = ElapsedS;
            }

            if (ElapsedS - _lastProgressS >= noProgressLimitS)
            {
                Finish(EndReason.NoProgress);
                return;
            }

            if (ElapsedS >= timeLimitS)
            {
                Finish(EndReason.TimeLimit);
            }
        }

        private void Finish(EndReason reason)
        {
            Outcome = reason;
            car.ScriptedMove = null;

            string line = string.Format(CultureInfo.InvariantCulture,
                "[HeuristicDriver] {0} | {1} | {2:F1}s | contacts {3} | markers {4}",
                strategy, reason, ElapsedS, WallContacts,
                ring != null ? ring.AwardedCount - 0 : -1);

            if (reason == EndReason.LapComplete)
            {
                Debug.Log(line, this);
            }
            else
            {
                Debug.LogWarning(line, this);
            }
        }

        /// <summary>
        /// Count barrier contacts, and only barrier contacts.
        ///
        /// The road is under the WheelColliders rather than the body, so the body collider should
        /// only ever meet a barrier. "Should" is not a measurement, so contacts are filtered by
        /// their normal: a wall pushes sideways and the ground pushes up. Counting a kerb strike
        /// or a landing as a wall contact would fail laps that SC-001 should pass.
        /// </summary>
        private void OnCollisionEnter(Collision collision)
        {
            if (!engaged || Outcome != EndReason.Running)
            {
                return;
            }

            for (int i = 0; i < collision.contactCount; i++)
            {
                if (Mathf.Abs(collision.GetContact(i).normal.y) < 0.5f)
                {
                    WallContacts++;
                    return;
                }
            }
        }
    }
}
