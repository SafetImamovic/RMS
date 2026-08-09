using System.Globalization;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using SelfDrivingSim.Track;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// Prints the whole observation vector to the console on a keypress, for T062.
    ///
    /// **Why this exists rather than reading <see cref="ObservationDebug"/>.** The panel is the
    /// right instrument for spotting a ray that is out of line, because the bars make the fan a
    /// shape rather than nineteen numbers. It is the wrong instrument for recording a result:
    /// T062 has to state which observation was checked against which situation, and nineteen
    /// values transcribed by hand off a panel updating at 50 Hz is how a wrong figure ends up in
    /// a task record. Feature 003 already learned this once, on the lap counts, and the answer
    /// was <see cref="LapReport"/>. This is the same answer for the observation vector.
    ///
    /// It reads <see cref="CarAgent.Observations"/> and changes nothing, so a drive with this
    /// component present is the same drive as one without it.
    ///
    /// P takes a probe. The counter is there so a set of probes pasted into the task record
    /// keeps its order, and so a misfire can be named rather than silently replacing the reading
    /// it was meant to be.
    /// </summary>
    public class ObservationProbe : MonoBehaviour
    {
        [Tooltip("Leave empty to find them on this object, its parents or the scene.")]
        [SerializeField] private CarAgent agent;

        [SerializeField] private CheckpointRing ring;

        [SerializeField] private TrackBuilder builder;

        [Tooltip("Also print the raw hit distances in metres. The normalised row is what the " +
                 "network sees; the metre row is what can be checked against a tape measure.")]
        [SerializeField] private bool includeMetres = true;

        private int _probeCount;
        private readonly StringBuilder _sb = new StringBuilder(512);

        private void Awake()
        {
            if (agent == null) agent = GetComponentInParent<CarAgent>();
            if (agent == null) agent = FindAnyObjectByType<CarAgent>();
            if (ring == null) ring = FindAnyObjectByType<CheckpointRing>();
            if (builder == null) builder = FindAnyObjectByType<TrackBuilder>();
        }

        private void Update()
        {
            Keyboard keyboard = Keyboard.current;
            if (keyboard != null && keyboard.pKey.wasPressedThisFrame)
            {
                Probe();
            }
        }

        /// <summary>Take one reading and print it. Public so a test can call it directly.</summary>
        public void Probe()
        {
            if (agent == null)
            {
                Debug.LogWarning("[ObsProbe] no CarAgent in the scene, nothing to read.", this);
                return;
            }

            _probeCount++;

            int seed = builder != null && builder.Current != null ? builder.Current.seed : -1;

            _sb.Clear();
            _sb.AppendFormat(CultureInfo.InvariantCulture,
                "[ObsProbe] #{0} | seed {1} | {2} values | rays {3} @ {4:F0}deg FOV, {5:F0} m\n",
                _probeCount, seed, agent.ObservationCount, agent.RayCount, agent.RayFovDeg,
                agent.RayLengthM);

            // A miss and a hit at the range limit both normalise to 1.000, and FR-025 turns on
            // the two being distinguishable. They are separated here by printing a miss as
            // dashes rather than as a number, which is the same choice ObservationDebug makes
            // with the word "none".
            _sb.Append("  norm ");
            for (int i = 0; i < agent.RayCount && i < agent.RayDistancesNorm.Count; i++)
            {
                _sb.Append(agent.RayHit[i]
                    ? agent.RayDistancesNorm[i].ToString("F3", CultureInfo.InvariantCulture)
                    : "-----");
                _sb.Append(' ');
            }

            if (includeMetres)
            {
                _sb.Append("\n  m    ");
                for (int i = 0; i < agent.RayCount && i < agent.RayDistancesM.Count; i++)
                {
                    _sb.Append(agent.RayHit[i]
                        ? agent.RayDistancesM[i].ToString("00.00", CultureInfo.InvariantCulture)
                        : "-----");
                    _sb.Append(' ');
                }
            }

            // Angles last rather than first: they are constant for a given ray count, so they
            // are a legend for the rows above rather than a reading. Printed anyway, because a
            // paste that says which ray points where can be checked months later against a
            // scene whose ray count has moved on.
            _sb.Append("\n  deg  ");
            for (int i = 0; i < agent.RayCount; i++)
            {
                _sb.AppendFormat(CultureInfo.InvariantCulture, "{0,5:+0;-0;0} ",
                                 agent.RayAngleDeg(i));
            }

            _sb.AppendFormat(CultureInfo.InvariantCulture,
                "\n  self vfwd {0,6:F3} | vlat {1,6:F3} | yaw {2,6:F3} | hfwd {3,6:F3} | " +
                "hright {4,6:F3} | steer {5,6:F3}",
                agent.SpeedForwardNorm, agent.SpeedLateralNorm, agent.YawRateNorm,
                agent.HeadingForwardDot, agent.HeadingRightDot, agent.SteerNorm);

            if (ring != null && ring.Count > 0)
            {
                _sb.AppendFormat(CultureInfo.InvariantCulture,
                    "\n  ring next {0:D2}/{1} | awarded {2} | lap {3} | skipped {4}{5}",
                    ring.NextIndex, ring.Count, ring.AwardedCount, ring.LapCount,
                    ring.SkippedContactCount, ring.WrongWay ? " | WRONG WAY" : string.Empty);
            }

            Debug.Log(_sb.ToString(), this);
        }
    }
}
