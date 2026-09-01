using System.Collections.Generic;
using UnityEngine;
using SelfDrivingSim.Logging;

namespace SelfDrivingSim.Vehicle
{
    /// <summary>
    /// Drives the car through a fixed manoeuvre so a calibration run does not need a person
    /// holding a key.
    ///
    /// T022, T024 and T025 are all specified as constant inputs: full lock, full throttle,
    /// full brake. Driving those by hand measures how steadily the key was held as much as it
    /// measures the vehicle, and their results are written into DESIGN.md as settled numbers.
    /// A scripted run makes them repeatable, which is what Principle VI asks for, and it means
    /// a tuning change can be re-measured without asking anyone to drive again.
    ///
    /// T023 is deliberately NOT in this list. It exists to compare a human's keyboard steering
    /// against the human dataset (FR-005, SC-002). Scripting it would measure the script.
    ///
    /// The component sets <see cref="CarController.ScriptedMove"/> every frame and releases it
    /// when the sequence ends, so the keyboard takes over again rather than the car locking up.
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class ScriptedDriver : MonoBehaviour
    {
        /// <summary>PlayerPrefs key naming the manoeuvre to run on the next Play.</summary>
        public const string ManoeuvrePrefKey = "SelfDrivingSim.ScriptedManoeuvre";

        public enum Manoeuvre
        {
            /// <summary>Nothing. The keyboard drives, which is the normal case.</summary>
            None = 0,

            /// <summary>Full throttle in a straight line from rest. Settles acceleration and top speed.</summary>
            StraightLine,

            /// <summary>Full lock at low speed, held. The turning circle for T022.</summary>
            FullLockCircle,

            /// <summary>Three full-throttle runs each ended by a full-brake stop. T024.</summary>
            AccelBrake,

            /// <summary>Full-lock turns at top speed and full-brake stops, three times. T025.</summary>
            Stress,
        }

        [Tooltip("Which manoeuvre to run when Play starts. Set to None to drive by keyboard. " +
                 "A value stored in PlayerPrefs under ManoeuvrePrefKey overrides this, which " +
                 "is how a run is launched from outside the editor UI.")]
        [SerializeField] private Manoeuvre manoeuvre = Manoeuvre.None;

        [Tooltip("Leave Play mode automatically once the manoeuvre finishes. This is what " +
                 "closes the drive log, so a scripted run produces a finished file with no " +
                 "further intervention.")]
        [SerializeField] private bool exitPlayModeWhenDone = true;

        /// <summary>One held input, for a fixed time.</summary>
        private readonly struct Segment
        {
            public readonly float Seconds;
            public readonly Vector2 Move;
            public readonly string Label;

            /// <summary>
            /// Speed to hold during this segment, m/s, or zero for no limit.
            ///
            /// Throttle alone does not set a speed, it sets an acceleration, so a segment
            /// asking for "low speed" by holding a small throttle simply accelerates until
            /// drag balances it. The first turning-circle run was meant to be a walking pace
            /// and reached 6.54 m/s, which put 0.72 g through the tyres and widened the
            /// measured circle by 13 percent. A circle is a geometric quantity and has to be
            /// measured slowly enough that slip angles stay negligible.
            /// </summary>
            public readonly float TargetSpeedMs;

            public Segment(float seconds, float steer, float throttle, string label,
                           float targetSpeedMs = 0f)
            {
                Seconds = seconds;
                Move = new Vector2(steer, throttle);
                Label = label;
                TargetSpeedMs = targetSpeedMs;
            }
        }

        private CarController _car;
        private DriveLogger _logger;
        private List<Segment> _plan;
        private int _index;
        private float _held;
        private bool _finished;

        /// <summary>Whether a scripted manoeuvre is currently running.</summary>
        public bool IsRunning => _plan != null && !_finished;

        /// <summary>The manoeuvre in progress, for the debug panel.</summary>
        public Manoeuvre Current { get; private set; }

        private void Awake()
        {
            _car = GetComponent<CarController>();
            _logger = GetComponent<DriveLogger>();

            Current = manoeuvre;

            // A manoeuvre named in PlayerPrefs wins, so a run can be launched without touching
            // the inspector. The key is cleared immediately: a stale value that silently drove
            // the car on the next Play would be worse than no automation at all.
            string stored = PlayerPrefs.GetString(ManoeuvrePrefKey, string.Empty);
            if (!string.IsNullOrEmpty(stored))
            {
                PlayerPrefs.DeleteKey(ManoeuvrePrefKey);
                PlayerPrefs.Save();

                if (System.Enum.TryParse(stored, out Manoeuvre parsed))
                {
                    Current = parsed;
                }
                else
                {
                    Debug.LogError($"[ScriptedDriver] unknown manoeuvre '{stored}', driving by keyboard.");
                }
            }

            _plan = Current == Manoeuvre.None ? null : BuildPlan(Current);
        }

        private void Start()
        {
            if (_plan == null)
            {
                return;
            }

            // The logger opens its file in OnEnable, which has already happened by now. Reopen
            // so the file starts at the first segment rather than containing the frames spent
            // loading the scene.
            _logger?.BeginRun();

            Debug.Log($"[ScriptedDriver] running {Current} over {_plan.Count} segments, " +
                      $"{TotalSeconds():F1}s total.");
        }

        private float TotalSeconds()
        {
            float total = 0f;
            foreach (Segment s in _plan)
            {
                total += s.Seconds;
            }

            return total;
        }

        private void Update()
        {
            if (_plan == null || _finished)
            {
                return;
            }

            if (_index >= _plan.Count)
            {
                Finish();
                return;
            }

            Segment segment = _plan[_index];
            Vector2 move = segment.Move;

            // Hold a speed by cutting the throttle above it and restoring it below. Crude on
            // purpose: a PID would settle faster but would put its own transient into the
            // logged speed, and the quantity being measured here is the path, not the speed.
            if (segment.TargetSpeedMs > 0f && _car.SpeedMagnitudeMs > segment.TargetSpeedMs)
            {
                move.y = 0f;
            }

            _car.ScriptedMove = move;

            _held += Time.deltaTime;
            if (_held >= segment.Seconds)
            {
                _held = 0f;
                _index++;
                if (_index < _plan.Count)
                {
                    Debug.Log($"[ScriptedDriver] {Current} -> {_plan[_index].Label}");
                }
            }
        }

        private void Finish()
        {
            _finished = true;

            // Hand the car back to the keyboard rather than leaving a held input applied.
            _car.ScriptedMove = null;

            Debug.Log($"[ScriptedDriver] {Current} complete.");

            if (!exitPlayModeWhenDone)
            {
                return;
            }

#if UNITY_EDITOR
            // Leaving Play mode disables the logger, which is what flushes and closes the CSV.
            UnityEditor.EditorApplication.isPlaying = false;
#endif
        }

        /// <summary>
        /// The manoeuvres, written as held inputs rather than as target speeds.
        ///
        /// Durations are long enough that the quantity being measured is reached and then
        /// HELD, because the analysis takes per-band means: a run that only touches top speed
        /// for a moment produces a band with three samples in it and no usable mean. Two
        /// earlier drives failed exactly this way, at 4.4 s and 2.4 s, and printed no bands.
        ///
        /// They are also short enough to stay inside boundsRadiusM, which is 250 m. At the
        /// measured 4.81 m/s^2 the car reaches 10 m/s in 2.1 s over 10.4 m and stops again in
        /// 8.5 m, so a straight segment costs about 10 m plus 10 m for every further second.
        /// The out-of-bounds reset teleports the car, and a teleport in the middle of a
        /// measurement puts a false step into speed and position. A 25 s straight run tripped
        /// it at exactly 250 m, which is what these durations were cut to avoid.
        /// </summary>
        private static List<Segment> BuildPlan(Manoeuvre m)
        {
            var plan = new List<Segment>();

            switch (m)
            {
                case Manoeuvre.StraightLine:
                    // Straight, no steering, until the speed has clearly stopped climbing.
                    // About 140 m, which stays inside the bounds.
                    plan.Add(new Segment(15f, 0f, 1f, "full throttle, straight"));
                    plan.Add(new Segment(5f, 0f, 0f, "coast"));
                    break;

                case Manoeuvre.FullLockCircle:
                    // Low speed matters: the turning circle is a geometric property, and at
                    // speed the tyres slide and widen it. Held at 2 m/s, where the lateral
                    // acceleration around a 5.4 m circle is 0.75 m/s^2, under a tenth of a g,
                    // so slip angles stay negligible and what is measured is the geometry.
                    plan.Add(new Segment(3f, 0f, 0.4f, "roll forward", 2f));
                    plan.Add(new Segment(45f, -1f, 0.4f, "full lock left at 2 m/s", 2f));
                    plan.Add(new Segment(3f, 0f, 0f, "coast"));
                    break;

                case Manoeuvre.AccelBrake:
                    for (int i = 0; i < 3; i++)
                    {
                        // Six seconds reaches top speed at 2.1 s and holds it for the rest,
                        // which is both measurements in one segment at about 50 m each.
                        plan.Add(new Segment(6f, 0f, 1f, $"accelerate {i + 1}/3"));
                        // Stopping from 10 m/s at 5.85 m/s^2 takes 1.7 s, so the brake is held
                        // for 2.5 s and no longer. Holding it at a standstill is the reverse
                        // gesture: the first run kept it for 4 s and put 643 reversing samples
                        // into a braking measurement.
                        plan.Add(new Segment(2.5f, 0f, -1f, $"full brake {i + 1}/3"));
                        plan.Add(new Segment(1.5f, 0f, 0f, "settle"));
                    }

                    break;

                case Manoeuvre.Stress:
                    for (int i = 0; i < 3; i++)
                    {
                        plan.Add(new Segment(5f, 0f, 1f, $"reach top speed {i + 1}/3"));
                        plan.Add(new Segment(6f, 1f, 1f, $"full lock right at speed {i + 1}/3"));
                        plan.Add(new Segment(6f, -1f, 1f, $"full lock left at speed {i + 1}/3"));
                        plan.Add(new Segment(4f, 0f, -1f, $"full brake {i + 1}/3"));
                        plan.Add(new Segment(1.5f, 0f, 0f, "settle"));
                    }

                    break;
            }

            return plan;
        }
    }
}
