using System.Globalization;
using UnityEngine;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Prints one line per completed lap, carrying everything T051 is judged on.
    ///
    /// **Why this exists rather than reading the overlays.** The lap verdict depends on four
    /// numbers spread across two panels: the lap and skipped counts live in the observation
    /// overlay, the reset counts live in the vehicle HUD. Reading four numbers off two panels
    /// while driving is how a wrong figure ends up in a task record, and the driver is the one
    /// person who cannot look away to check. One line, emitted when the lap closes, is a thing
    /// that can be copied rather than transcribed.
    ///
    /// It reports rather than judges the run in any way that changes it: nothing here touches
    /// the ring, the car or the track, so a lap driven with this component present is the same
    /// lap as one driven without it.
    ///
    /// The counts are captured per lap, not cumulative. A stray reset on lap 1 must not condemn
    /// lap 2, or a driver who recovers can never record a clean lap without restarting the whole
    /// session.
    /// </summary>
    public class LapReport : MonoBehaviour
    {
        [Tooltip("Leave empty to find them on this object or in the scene.")]
        [SerializeField] private CheckpointRing ring;

        [SerializeField] private CarController car;

        [SerializeField] private TrackBuilder builder;

        private int _lastLapCount;
        private float _lapStartTime;
        private int _lapStartAwarded;
        private int _lapStartSkipped;
        private int _lapStartStray;
        private int _lapStartFall;
        private int _wrongWayEvents;
        private bool _wrongWayLatched;

        private void Awake()
        {
            if (ring == null) ring = FindAnyObjectByType<CheckpointRing>();
            if (car == null) car = FindAnyObjectByType<CarController>();
            if (builder == null) builder = FindAnyObjectByType<TrackBuilder>();
        }

        private void Start()
        {
            BeginLap();
        }

        private void Update()
        {
            if (ring == null || car == null)
            {
                return;
            }

            // Counted on the rising edge only. WrongWay is a state that stays true until the
            // next correct marker, so sampling it per frame would report one wrong turn as
            // several hundred.
            if (ring.WrongWay && !_wrongWayLatched)
            {
                _wrongWayEvents++;
            }

            _wrongWayLatched = ring.WrongWay;

            if (ring.LapCount > _lastLapCount)
            {
                Report();
                BeginLap();
            }
        }

        private void BeginLap()
        {
            if (ring == null || car == null)
            {
                return;
            }

            _lastLapCount = ring.LapCount;
            _lapStartTime = Time.time;
            _lapStartAwarded = ring.AwardedCount;
            _lapStartSkipped = ring.SkippedContactCount;
            _lapStartStray = car.StrayResetCount;
            _lapStartFall = car.FallResetCount;
            _wrongWayEvents = 0;
            _wrongWayLatched = false;
        }

        private void Report()
        {
            int awarded = ring.AwardedCount - _lapStartAwarded;
            int skipped = ring.SkippedContactCount - _lapStartSkipped;
            int stray = car.StrayResetCount - _lapStartStray;
            int fall = car.FallResetCount - _lapStartFall;
            float seconds = Time.time - _lapStartTime;

            int seed = builder != null && builder.Current != null ? builder.Current.seed : -1;

            // A lap counts only if the car took every marker in order and never left the road.
            // Skipped markers mean a corner was cut, which is the same failure as leaving the
            // surface with a luckier trajectory (SC-012, FR-013 scenario 6).
            bool clean = skipped == 0 && stray == 0 && fall == 0 && _wrongWayEvents == 0;

            // InvariantCulture throughout. The machine locale is bs-Latn-BA, which writes 42,3
            // for 42.3, and a figure pasted into a task record should not depend on which
            // machine produced it. Feature 003 already hit this once, in the track loader's
            // refusal messages.
            string line = string.Format(
                CultureInfo.InvariantCulture,
                "[LapReport] seed {0} | lap {1} | {2:F1}s | markers {3}/{4} | skipped {5} | " +
                "wrongway {6} | stray {7} | fell {8} | {9}",
                seed, ring.LapCount, seconds, awarded, ring.Count, skipped,
                _wrongWayEvents, stray, fall, clean ? "PASS" : "FAIL");

            if (clean)
            {
                Debug.Log(line, this);
            }
            else
            {
                // A failed lap is a result worth keeping, not a warning to be cleared, but it
                // should stand out in a console full of Log lines.
                Debug.LogWarning(line, this);
            }
        }
    }
}
