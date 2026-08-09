using System.Globalization;
using UnityEngine;
using UnityEngine.InputSystem;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Logging
{
    /// <summary>
    /// On-screen readout of everything a keyboard drive is judged on.
    ///
    /// Two panels. The left one is live vehicle state: what the car is doing right now. The
    /// right one is the run summary, each line carrying the M1 figure it is measured against
    /// and a verdict. That second panel is FR-009 made immediate: without it, checking
    /// whether the steering rate is calibrated means driving, stopping, exporting a log and
    /// running compare_drive, which is a slow loop to tune a single number in.
    ///
    /// Drawn with IMGUI deliberately. It needs no canvas, no prefab and no scene wiring, so
    /// it cannot break the scene it is dropped into, and it disappears entirely from a build
    /// that does not include it. This is instrumentation for a human, not part of what the
    /// agent observes.
    ///
    /// H toggles the HUD, R restarts the measurement run.
    /// </summary>
    [RequireComponent(typeof(DriveTelemetry))]
    public class DriveHud : MonoBehaviour
    {
        [SerializeField] private bool visible = true;
        [SerializeField] private int fontSize = 13;

        [Tooltip("Toggled with B and remembered between sessions. Requirement codes and " +
                 "symbols stay untranslated in both languages, since they point at spec.md.")]
        [SerializeField]
        private HudLanguage language = HudLanguage.English;

        private const string LanguagePrefKey = "rms.hud.language";

        [Tooltip("Width of each panel in pixels.")]
        [SerializeField]
        private float panelWidth = 340f;

        private DriveTelemetry _telemetry;
        private CarController _car;
        private DriveLogger _logger;
        private StabilityMonitor _stability;
        private GUIStyle _label;
        private GUIStyle _header;
        private Texture2D _panelTexture;

        private static readonly Color Good = new Color(0.45f, 0.92f, 0.55f);
        private static readonly Color Bad = new Color(1.0f, 0.55f, 0.45f);
        private static readonly Color Idle = new Color(0.72f, 0.75f, 0.78f);

        private void Awake()
        {
            _telemetry = GetComponent<DriveTelemetry>();
            _car = GetComponent<CarController>();

            // Both optional. The HUD is instrumentation and must still draw on a car that
            // has no logger or no stability monitor attached.
            _logger = GetComponent<DriveLogger>();
            _stability = GetComponent<StabilityMonitor>();

            if (PlayerPrefs.HasKey(LanguagePrefKey))
            {
                language = (HudLanguage)PlayerPrefs.GetInt(LanguagePrefKey);
            }
        }

        /// <summary>The active string table.</summary>
        private HudStrings T => HudStrings.For(language);

        private void OnDestroy()
        {
            if (_panelTexture != null)
            {
                Destroy(_panelTexture);
            }
        }

        private void Update()
        {
            Keyboard keyboard = Keyboard.current;
            if (keyboard == null)
            {
                return;
            }

            if (keyboard.hKey.wasPressedThisFrame)
            {
                visible = !visible;
            }

            if (keyboard.rKey.wasPressedThisFrame)
            {
                // One key restarts everything the drive is judged on. If the telemetry
                // restarted but the log did not, the CSV and the panel beside it would be
                // measuring two different runs, and the panel is what the driver trusts.
                _telemetry.ResetRun();
                _stability?.BeginRun();
                _logger?.BeginRun();
            }

            if (keyboard.bKey.wasPressedThisFrame)
            {
                language = language == HudLanguage.English
                    ? HudLanguage.Bosnian
                    : HudLanguage.English;
                PlayerPrefs.SetInt(LanguagePrefKey, (int)language);
                PlayerPrefs.Save();
            }
        }

        private void EnsureStyles()
        {
            if (_label != null)
            {
                return;
            }

            _panelTexture = new Texture2D(1, 1);
            _panelTexture.SetPixel(0, 0, new Color(0.06f, 0.08f, 0.10f, 0.82f));
            _panelTexture.Apply();

            _label = new GUIStyle(GUI.skin.label)
            {
                fontSize = fontSize,
                richText = true,
                // Monospace so the columns line up as values change width. Falls back
                // silently to the default font if the machine has neither.
                font = Font.CreateDynamicFontFromOSFont(
                    new[] { "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New" }, fontSize),
            };

            _header = new GUIStyle(_label)
            {
                fontStyle = FontStyle.Bold,
                fontSize = fontSize + 1,
            };
        }

        private void OnGUI()
        {
            if (!visible || _telemetry == null || _car == null)
            {
                return;
            }

            EnsureStyles();

            // Numbers are formatted invariantly regardless of the display language. This
            // machine's locale writes decimals with a comma, and the HUD has to be readable
            // next to the drive log, the M1 report and the Python constants, all of which
            // use a dot. Switching to Bosnian changes the words, never the notation.
            //
            // The same issue is a genuine hazard for DriveLogger in T018: a comma decimal
            // separator inside a comma-separated file would corrupt every row.
            CultureInfo previous = CultureInfo.CurrentCulture;
            CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
            try
            {
                DrawLivePanel(new Rect(12f, 12f, panelWidth, 290f));
                DrawRunPanel(new Rect(12f + panelWidth + 10f, 12f, panelWidth + 90f, 290f));
            }
            finally
            {
                CultureInfo.CurrentCulture = previous;
            }

            GUI.color = Idle;
            GUI.Label(new Rect(12f, Screen.height - 26f, 900f, 22f), T.Controls, _label);
            GUI.color = Color.white;
        }

        private void DrawLivePanel(Rect rect)
        {
            GUI.DrawTexture(rect, _panelTexture);
            GUILayout.BeginArea(new Rect(rect.x + 10f, rect.y + 8f, rect.width - 20f, rect.height - 16f));

            GUI.color = Color.white;
            GUILayout.Label(T.Vehicle, _header);

            VehicleProfile p = _car.Profile;
            float speed = _car.SpeedMs;

            Row(T.Speed, $"{speed,6:F2} m/s   {speed / Mathf.Max(p.vMaxMs, 0.001f),5:P0} {T.OfMax}");
            Row(T.Steering, $"{_car.SteerNorm,6:F3}      {_car.SteerAngleDeg,5:F1} {T.Degrees}");
            Row(T.Throttle, $"{_car.Throttle,6:F2}");
            Row(T.Brake, $"{_car.Brake,6:F2}");

            // Live turning radius. Drive a full-lock circle and this should read r_min,
            // which is the SC-004 check available without any measurement script.
            float radius = p.RadiusForSteering(_car.SteerNorm);
            Row(T.TurnRadius, float.IsInfinity(radius)
                ? $"     -  {T.Straight}"
                : $"{radius,6:F2} m   {T.MinShort} {p.RMinM:F2}");

            float tiltDeg = Vector3.Angle(transform.up, Vector3.up);
            GUI.color = tiltDeg > 45f ? Bad : Idle;
            Row(T.BodyTilt, $"{tiltDeg,6:F1} {T.Degrees}  {T.TriggerAt45}");
            GUI.color = Color.white;

            Row(T.Resets, $"{_car.ResetCount,6:D}");

            // Whether this drive is actually being written down. Discovering after a good
            // run that nothing was recorded is the failure this line exists to prevent.
            if (_logger != null)
            {
                GUI.color = _logger.IsRecording ? Good : Bad;
                Row(T.Recording, _logger.IsRecording
                    ? $"{_logger.RowCount,6:N0} {T.Rows} @ {_logger.LogHz:F0} Hz"
                    : $"     {T.Off}");
                GUI.color = Color.white;
            }

            // The research C5 tally. Shown even at 0 of 3, because a counter only visible
            // once it is non-zero is a counter nobody trusts.
            if (_stability != null)
            {
                bool breached = _stability.BreachedThisRun;
                GUI.color = breached ? Bad : (_stability.ConsecutiveBadRuns > 0 ? Idle : Good);
                Row(T.Stability, $"{_stability.ConsecutiveBadRuns,6:D}/3   #{_stability.RunIndex}" +
                                 (breached ? $"  {T.Breach}" : string.Empty));
                GUI.color = Color.white;
            }

            GUILayout.EndArea();
        }

        private void DrawRunPanel(Rect rect)
        {
            GUI.DrawTexture(rect, _panelTexture);
            GUILayout.BeginArea(new Rect(rect.x + 10f, rect.y + 8f, rect.width - 20f, rect.height - 16f));

            CalibrationEnvelope env = _telemetry.Envelope;

            GUI.color = Color.white;
            GUILayout.Label(
                $"{T.RunVsM1}   {_telemetry.ElapsedS,5:F1} {T.Seconds}   n={_telemetry.SampleCount} @ {(env != null ? env.compare_hz : 14.08f):F2} Hz",
                _header);

            if (env == null)
            {
                GUI.color = Bad;
                GUILayout.Label(T.MissingEnvelope, _label);
                GUILayout.Label(T.MissingEnvelopeFix, _label);
                GUILayout.EndArea();
                return;
            }

            // SC-002: full lock reached in both directions.
            Verdict(
                T.SteerRange,
                $"{_telemetry.MaxSteerLeft,6:F2} .. {_telemetry.MaxSteerRight,4:F2}",
                $"{T.Need} +-{env.steer_abs_max:F2}",
                _telemetry.ReachedBothSteeringExtremes);

            // FR-005: the headline calibration figure, and the reason the sampling clock
            // matters. Judged against track1 because that is the profile tracks target.
            bool enough = _telemetry.SampleCount >= 30;

            // "P95 |dsteer|" and "vmax/vP99" stay untranslated: they are the notation the
            // research and the M1 report already use, so a reader can match a HUD line to
            // the document it came from whichever language is showing.
            Verdict(
                "P95 |dsteer|",
                $"{_telemetry.DeltaSteerP95,6:F3}",
                $"{T.Want} {env.dsteer_p95_track1 / 2f:F2}-{env.dsteer_p95_track1 * 2f:F2}",
                _telemetry.DeltaSteerWithinFactorTwo,
                !enough);

            // SC-005: nothing may exceed what the dataset actually recorded.
            Verdict(
                "max |dsteer|",
                $"{_telemetry.MaxAbsDeltaSteer,6:F3}",
                $"{T.Cap} {env.dsteer_max:F2}",
                _telemetry.DeltaSteerWithinRecordedMax);

            // SC-003 the only way FR-004 permits: a ratio, so no unit is assumed.
            Verdict(
                "vmax/vP99",
                _telemetry.SpeedMaxOverP99 > 0f ? $"{_telemetry.SpeedMaxOverP99,6:F3}" : "     -",
                $"{T.Data} {env.speed_max_over_p99:F3} +-10%",
                _telemetry.SpeedShapeMatches,
                !enough);

            GUI.color = Idle;
            GUILayout.Space(4f);
            GUILayout.Label($"{T.PeakSpeed} {_telemetry.MaxSpeedMs:F2} m/s", _label);
            GUILayout.Label(
                string.Format(
                    T.TrackTwoBand,
                    (env.dsteer_p95_track2 / 2f).ToString("F2"),
                    (env.dsteer_p95_track2 * 2f).ToString("F2")),
                _label);
            GUI.color = Color.white;

            GUILayout.EndArea();
        }

        // Wide enough for the longest label in either language. Bosnian sets the column:
        // "resetovanja" and "poluprecnik" at 11, "opseg volana" at 12.
        private const int LabelWidth = -14;
        private const int VerdictLabelWidth = -15;

        private void Row(string name, string value)
        {
            GUILayout.Label($"{name.PadRight(-LabelWidth)}{value}", _label);
        }

        private void Verdict(string name, string value, string target, bool ok, bool pending = false)
        {
            GUI.color = pending ? Idle : (ok ? Good : Bad);
            string mark = pending ? "..." : (ok ? "OK " : "NO ");
            GUILayout.Label($"{name.PadRight(-VerdictLabelWidth)}{value}  {mark} {target}", _label);
            GUI.color = Color.white;
        }
    }
}
