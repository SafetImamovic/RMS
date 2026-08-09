using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using SelfDrivingSim.Logging;

namespace SelfDrivingSim.Vehicle
{
    /// <summary>Which of the research C5 conditions fired.</summary>
    public enum StabilityCondition
    {
        /// <summary>C5.1 - body tilted or rolled past the threshold while it was on the ground.</summary>
        BodyFlip,

        /// <summary>C5.2 - stationary, no input, yet the car moved.</summary>
        IdleDrift,

        /// <summary>C5.3 - dropped through the surface.</summary>
        FellThrough,

        /// <summary>C5.3 - came to rest in a state a driver cannot recover from.</summary>
        Unrecoverable,
    }

    /// <summary>One condition firing, on one run.</summary>
    public readonly struct StabilityBreach
    {
        public readonly int RunIndex;
        public readonly StabilityCondition Condition;
        public readonly float AtSecond;
        public readonly string Detail;

        public StabilityBreach(int runIndex, StabilityCondition condition, float atSecond, string detail)
        {
            RunIndex = runIndex;
            Condition = condition;
            AtSecond = atSecond;
            Detail = detail;
        }

        public override string ToString() =>
            string.Format(
                CultureInfo.InvariantCulture,
                "run {0}  {1} at {2:F1}s  ({3})",
                RunIndex, Condition, AtSecond, Detail);
    }

    /// <summary>
    /// Decides, by measurement, whether WheelCollider physics is holding up.
    ///
    /// DESIGN 4.2 says physics is the primary model and the simplified kinematic model is the
    /// alternative "if it causes problems". That sentence is not a procedure, and a decision
    /// this large should not come down to how the car felt at midnight. Research C5 replaces
    /// it with three conditions that can be checked by running the simulation, and this
    /// component is those conditions in code:
    ///
    ///   1. body tilt or roll past 45 degrees while all four wheels were on the ground the
    ///      previous physics step;
    ///   2. stationary with no input, yet drifting more than 0.1 m in 10 s;
    ///   3. falling through the surface, or ending in a state that needs a restart.
    ///
    /// The verdict needs **three consecutive one-minute drives** to fire, because one bad run
    /// can be a fluke or a driver error. Both halves of that sentence are enforced here: a run
    /// shorter than a minute does not count toward the tally at all, in either direction. A
    /// five-second run proves nothing about stability, and letting it clear the counter would
    /// make the tally trivially resettable by pressing Play and stopping again.
    ///
    /// The tally survives leaving Play mode, because the three drives are not expected to
    /// happen in one sitting. It is kept in PlayerPrefs and every breach is also appended to
    /// results/drive_logs/stability_log.csv, so if the switch is ever made the evidence for
    /// it is on disk rather than in a memory of what went wrong (FR-011).
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class StabilityMonitor : MonoBehaviour
    {
        [Header("C5.1 - body flip")]
        [Tooltip("Tilt or roll past this angle, while grounded, is a failure. Research C5.")]
        [SerializeField] private float tiltThresholdDeg = 45f;

        [Header("C5.2 - idle drift")]
        [Tooltip("Window over which a stationary car may not move (s).")]
        [SerializeField] private float idleWindowS = 10f;

        [Tooltip("How far a stationary car may drift within the window (m).")]
        [SerializeField] private float idleDriftM = 0.1f;

        [Tooltip("Speed below which the car counts as stationary (m/s).\n\n" +
                 "Must be LOOSER than the drift it is watching for. The condition catches " +
                 "0.1 m over 10 s, which is 0.01 m/s, so a gate tighter than that would " +
                 "exclude exactly the case it exists to detect.")]
        [SerializeField] private float idleSpeedMs = 0.05f;

        [Header("C5.3 - unrecoverable")]
        [Tooltip("Past this angle the car is on its roof or its side.")]
        [SerializeField] private float upsideDownDeg = 120f;

        [Tooltip("How long it must stay there, barely moving, before it counts as stuck (s).")]
        [SerializeField] private float stuckSecondsS = 3f;

        [Header("Verdict")]
        [Tooltip("A run shorter than this does not count toward the tally, in either direction " +
                 "(research C5 specifies one-minute drives).")]
        [SerializeField] private float minRunDurationS = 60f;

        [Tooltip("Consecutive qualifying runs with a breach before the kinematic model is adopted.")]
        [SerializeField] private int consecutiveRunsForSwitch = 3;

        private const string RunIndexKey = "rms.stability.runIndex";
        private const string ConsecutiveKey = "rms.stability.consecutiveBadRuns";
        private const string LogFileName = "stability_log.csv";

        private CarController _car;
        private readonly List<StabilityBreach> _breaches = new List<StabilityBreach>();
        private readonly HashSet<StabilityCondition> _firedThisRun = new HashSet<StabilityCondition>();

        private bool _allGroundedPrevStep;
        private bool _runFinalised;

        private bool _isIdle;
        private float _idleElapsed;
        private Vector3 _idleOrigin;

        private float _upsideDownElapsed;
        private int _resetCountAtLastCheck;
        private int _fallResetsAtRunStart;

        /// <summary>Which run this is. Persisted, so it keeps counting across Play sessions.</summary>
        public int RunIndex { get; private set; }

        /// <summary>Seconds since this run began.</summary>
        public float ElapsedS { get; private set; }

        /// <summary>Everything that fired this session, in order.</summary>
        public IReadOnlyList<StabilityBreach> Breaches => _breaches;

        /// <summary>Whether anything fired on the current run.</summary>
        public bool BreachedThisRun => _firedThisRun.Count > 0;

        /// <summary>Consecutive qualifying runs that ended with at least one breach.</summary>
        public int ConsecutiveBadRuns { get; private set; }

        /// <summary>Whether the run is long enough to count toward the verdict yet.</summary>
        public bool RunQualifies => ElapsedS >= minRunDurationS;

        /// <summary>
        /// The C5 verdict. True means DESIGN 4.2's fallback has been earned: switch to the
        /// simplified kinematic model and record the runs that triggered it.
        /// </summary>
        public bool ShouldSwitchToKinematic => ConsecutiveBadRuns >= consecutiveRunsForSwitch;

        private void Awake()
        {
            _car = GetComponent<CarController>();
            RunIndex = PlayerPrefs.GetInt(RunIndexKey, 0);
            ConsecutiveBadRuns = PlayerPrefs.GetInt(ConsecutiveKey, 0);
            BeginRun();
        }

        /// <summary>
        /// Close the current run and start a fresh one. Bound to the same key that resets the
        /// telemetry, so one keypress restarts everything a drive is judged on.
        /// </summary>
        public void BeginRun()
        {
            FinaliseRun();

            RunIndex++;
            PlayerPrefs.SetInt(RunIndexKey, RunIndex);
            PlayerPrefs.Save();

            ElapsedS = 0f;
            _runFinalised = false;
            _firedThisRun.Clear();
            _allGroundedPrevStep = false;
            _isIdle = false;
            _idleElapsed = 0f;
            _upsideDownElapsed = 0f;
            _resetCountAtLastCheck = _car != null ? _car.ResetCount : 0;
            _fallResetsAtRunStart = _car != null ? _car.FallResetCount : 0;
        }

        private void OnDisable()
        {
            // Leaving Play mode ends the run. Without this, stopping the editor would lose
            // the run entirely and the tally would never advance.
            FinaliseRun();
        }

        /// <summary>
        /// Score the run that just ended. Only runs of at least the minimum duration move the
        /// tally, in either direction.
        /// </summary>
        private void FinaliseRun()
        {
            if (_runFinalised || RunIndex == 0)
            {
                return;
            }

            _runFinalised = true;

            if (ElapsedS < minRunDurationS)
            {
                if (BreachedThisRun)
                {
                    Debug.LogWarning(
                        $"[StabilityMonitor] run {RunIndex} breached but lasted only " +
                        $"{ElapsedS:F0}s, under the {minRunDurationS:F0}s minimum. Not counted " +
                        "toward the C5 tally. Drive a full minute for the run to count.");
                }

                return;
            }

            ConsecutiveBadRuns = BreachedThisRun ? ConsecutiveBadRuns + 1 : 0;
            PlayerPrefs.SetInt(ConsecutiveKey, ConsecutiveBadRuns);
            PlayerPrefs.Save();

            if (ShouldSwitchToKinematic)
            {
                Debug.LogError(
                    $"[StabilityMonitor] {ConsecutiveBadRuns} consecutive qualifying runs " +
                    "breached. Research C5 has been met: adopt the simplified kinematic model " +
                    $"and record the triggering runs. Evidence in results/drive_logs/{LogFileName}");
            }
        }

        private void FixedUpdate()
        {
            if (_car == null)
            {
                return;
            }

            ElapsedS += Time.fixedDeltaTime;

            // A reset teleports the car. Anything measured across that jump is meaningless,
            // so both position-based checks start over.
            if (_car.ResetCount != _resetCountAtLastCheck)
            {
                if (_car.FallResetCount > _fallResetsAtRunStart)
                {
                    Fire(StabilityCondition.FellThrough,
                        $"car dropped below the world, fall reset #{_car.FallResetCount}");
                    _fallResetsAtRunStart = _car.FallResetCount;
                }

                _resetCountAtLastCheck = _car.ResetCount;
                _isIdle = false;
                _upsideDownElapsed = 0f;
            }

            float tiltDeg = Vector3.Angle(transform.up, Vector3.up);
            bool allGrounded = _car.GroundedWheelCount == 4;

            CheckBodyFlip(tiltDeg);
            CheckIdleDrift();
            CheckUnrecoverable(tiltDeg);

            _allGroundedPrevStep = allGrounded;
        }

        /// <summary>
        /// C5.1. The grounded precondition is the whole point of this condition. A car that
        /// takes off over a bump and rotates in the air has not failed at anything, so tilt
        /// alone would report a false failure. Tilting past 45 degrees while all four wheels
        /// were on the ground one step earlier is the physics losing its grip on the car.
        /// </summary>
        private void CheckBodyFlip(float tiltDeg)
        {
            if (tiltDeg > tiltThresholdDeg && _allGroundedPrevStep)
            {
                Fire(StabilityCondition.BodyFlip,
                    FormattableString.Invariant(
                        $"tilt {tiltDeg:F1} deg with all four wheels grounded the previous step"));
            }
        }

        /// <summary>
        /// C5.2. Displacement is measured from where the idle window opened and checked every
        /// step rather than only at the end, so a car that slides out and drifts part of the
        /// way back is still caught. The end-of-window check alone would miss it.
        /// </summary>
        private void CheckIdleDrift()
        {
            bool stationary = Mathf.Abs(_car.SpeedMs) < idleSpeedMs;
            bool noInput = _car.Throttle <= 0f && _car.Brake <= 0f;

            if (!stationary || !noInput)
            {
                _isIdle = false;
                return;
            }

            if (!_isIdle)
            {
                _isIdle = true;
                _idleElapsed = 0f;
                _idleOrigin = transform.position;
                return;
            }

            _idleElapsed += Time.fixedDeltaTime;

            float drift = Vector3.Distance(transform.position, _idleOrigin);
            if (drift > idleDriftM)
            {
                Fire(StabilityCondition.IdleDrift,
                    FormattableString.Invariant(
                        $"drifted {drift:F3} m in {_idleElapsed:F1} s with no input"));
                _isIdle = false;
                return;
            }

            // Survived a full window without drifting. Open a new one rather than stopping,
            // so a car parked for a minute is checked six times, not once.
            if (_idleElapsed >= idleWindowS)
            {
                _idleElapsed = 0f;
                _idleOrigin = transform.position;
            }
        }

        /// <summary>
        /// C5.3, second half. On its roof or its side and not moving is a state a driver
        /// cannot drive out of. The dwell time is what separates it from a car mid-roll,
        /// which may yet land on its wheels.
        /// </summary>
        private void CheckUnrecoverable(float tiltDeg)
        {
            bool overturned = tiltDeg > upsideDownDeg && Mathf.Abs(_car.SpeedMs) < 0.2f;
            if (!overturned)
            {
                _upsideDownElapsed = 0f;
                return;
            }

            _upsideDownElapsed += Time.fixedDeltaTime;
            if (_upsideDownElapsed >= stuckSecondsS)
            {
                Fire(StabilityCondition.Unrecoverable,
                    FormattableString.Invariant(
                        $"overturned at {tiltDeg:F0} deg and stationary for {_upsideDownElapsed:F1} s"));
                _upsideDownElapsed = 0f;
            }
        }

        /// <summary>
        /// Record a breach. Each condition fires at most once per run: a car on its roof
        /// would otherwise log fifty times a second, and the count of log lines would say
        /// more about the physics step than about the number of failures.
        /// </summary>
        private void Fire(StabilityCondition condition, string detail)
        {
            if (!_firedThisRun.Add(condition))
            {
                return;
            }

            var breach = new StabilityBreach(RunIndex, condition, ElapsedS, detail);
            _breaches.Add(breach);
            Debug.LogWarning($"[StabilityMonitor] {breach}");
            Append(breach);
        }

        private void Append(StabilityBreach breach)
        {
            try
            {
                string path = Path.Combine(RepoPaths.DriveLogsDir, LogFileName);
                bool isNew = !File.Exists(path);

                var line = new StringBuilder();
                if (isNew)
                {
                    line.AppendLine("run,timestamp,condition,at_second,detail");
                }

                // Invariant throughout: this machine's locale writes decimal commas, which
                // inside a comma-separated file would split one column into two.
                line.AppendFormat(
                    CultureInfo.InvariantCulture,
                    "{0},{1},{2},{3:F2},\"{4}\"",
                    breach.RunIndex,
                    RepoPaths.TimestampStamp(),
                    breach.Condition,
                    breach.AtSecond,
                    breach.Detail.Replace("\"", "'"));
                line.AppendLine();

                File.AppendAllText(path, line.ToString());
            }
            catch (IOException e)
            {
                // A locked or unwritable file must not take the drive down with it. The
                // console warning above has already recorded what happened.
                Debug.LogWarning($"[StabilityMonitor] could not append to the stability log: {e.Message}");
            }
        }

        /// <summary>Clear the tally. For starting a fresh evaluation after retuning the car.</summary>
        public void ResetVerdict()
        {
            ConsecutiveBadRuns = 0;
            PlayerPrefs.SetInt(ConsecutiveKey, 0);
            PlayerPrefs.Save();
            Debug.Log("[StabilityMonitor] C5 tally cleared.");
        }
    }
}
