using System.Globalization;
using UnityEngine;
using UnityEngine.InputSystem;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// The heuristic driver's knobs, on screen, draggable while the car is driving.
    ///
    /// **Why this is not just the Inspector.** The Inspector can already change every one of these
    /// values at runtime, and that is how they were first exposed. It is the wrong instrument for
    /// this job: the moment a threshold changes is the moment worth watching, and reaching the
    /// Inspector means looking away from the car to find a field, then looking back after the
    /// interesting half second has passed. Feeling where a control loop breaks needs a hand on the
    /// slider and eyes on the road.
    ///
    /// It also puts the cause and the effect in the same picture. The panel shows the threshold
    /// beside the forward clearance it is compared against, and the raw command beside the one
    /// that survived the gate, so a change and its consequence are read together rather than
    /// remembered across a glance.
    ///
    /// IMGUI, for the same reasons as <see cref="ObservationDebug"/> and DriveHud: no canvas, no
    /// prefab, no scene wiring, and it cannot break the scene it is dropped into.
    ///
    /// G toggles the panel.
    /// </summary>
    public class HeuristicTuner : MonoBehaviour
    {
        [SerializeField] private HeuristicDriver driver;
        [SerializeField] private bool visible = true;
        [SerializeField] private int fontSize = 12;
        [SerializeField] private float panelWidth = 340f;

        private GUIStyle _label;
        private GUIStyle _header;
        private Texture2D _panelTexture;
        private Texture2D _barTexture;

        private static readonly Color Open = new Color(1.0f, 0.55f, 0.45f);
        private static readonly Color Held = new Color(0.45f, 0.92f, 0.55f);
        private static readonly Color Idle = new Color(0.72f, 0.75f, 0.78f);
        private static readonly Color Accent = new Color(0.55f, 0.80f, 1.0f);

        private void Awake()
        {
            if (driver == null)
            {
                driver = GetComponentInParent<HeuristicDriver>();
            }

            if (driver == null)
            {
                driver = FindAnyObjectByType<HeuristicDriver>();
            }
        }

        private void OnDestroy()
        {
            if (_panelTexture != null) { Destroy(_panelTexture); }
            if (_barTexture != null) { Destroy(_barTexture); }
        }

        private void Update()
        {
            Keyboard keyboard = Keyboard.current;
            if (keyboard == null)
            {
                return;
            }

            if (keyboard.gKey.wasPressedThisFrame)
            {
                visible = !visible;
            }

            // Enter restarts. Handled here rather than in OnGUI, which runs twice per frame for
            // Layout and Repaint, so wasPressedThisFrame would be true in both passes and a
            // single keypress would restart the run twice.
            if (driver != null &&
                (keyboard.enterKey.wasPressedThisFrame || keyboard.numpadEnterKey.wasPressedThisFrame))
            {
                driver.RestartRun();
            }
        }

        private void EnsureStyles()
        {
            if (_label != null)
            {
                return;
            }

            _panelTexture = Solid(new Color(0.06f, 0.08f, 0.10f, 0.86f));
            _barTexture = Solid(Color.white);

            _label = new GUIStyle(GUI.skin.label)
            {
                fontSize = fontSize,
                richText = true,
                font = Font.CreateDynamicFontFromOSFont(
                    new[] { "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New" }, fontSize),
            };

            _header = new GUIStyle(_label)
            {
                fontStyle = FontStyle.Bold,
                fontSize = fontSize + 1,
            };
        }

        private static Texture2D Solid(Color colour)
        {
            var texture = new Texture2D(1, 1);
            texture.SetPixel(0, 0, colour);
            texture.Apply();
            return texture;
        }

        private void OnGUI()
        {
            if (!visible || driver == null)
            {
                return;
            }

            EnsureStyles();

            // Invariant, for the same reason every other readout in this project forces it: the
            // machine locale writes 0,35 and every document these values are compared against
            // writes 0.35.
            CultureInfo previous = CultureInfo.CurrentCulture;
            CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
            try
            {
                Draw(new Rect(12f, Screen.height - 322f, panelWidth, 310f));
            }
            finally
            {
                CultureInfo.CurrentCulture = previous;
            }
        }

        private void Draw(Rect rect)
        {
            GUI.DrawTexture(rect, _panelTexture);
            GUILayout.BeginArea(new Rect(rect.x + 10f, rect.y + 8f, rect.width - 20f,
                                         rect.height - 16f));

            GUI.color = Color.white;
            GUILayout.Label($"HEURISTIC  {driver.ActiveStrategy}   [G] hide", _header);

            DrawModeButtons();

            GUILayout.Space(4f);

            switch (driver.Mode)
            {
                case HeuristicDriver.ReactionMode.Immediate:
                    GUI.color = Idle;
                    GUILayout.Label("  no shaping: the raw command goes to the wheel", _label);
                    GUI.color = Color.white;
                    break;

                case HeuristicDriver.ReactionMode.Delayed:
                    driver.ReactionTimeS = Slider(
                        "reaction", driver.ReactionTimeS, 0f, 0.5f, "{0:F3} s");
                    driver.CommandSmoothingS = Slider(
                        "smoothing", driver.CommandSmoothingS, 0f, 1f, "{0:F3} s");
                    break;

                case HeuristicDriver.ReactionMode.CriticalDistance:
                    driver.CriticalDistanceNorm = Slider(
                        "threshold", driver.CriticalDistanceNorm, 0f, 1f, "{0:F3}");
                    GUI.color = Idle;
                    GUILayout.Label(
                        $"           = {driver.CriticalDistanceNorm * driver.RayLengthM,5:F1} m ahead",
                        _label);
                    GUI.color = Color.white;
                    break;
            }

            GUILayout.Space(6f);
            DrawLive();

            GUILayout.Space(6f);
            DrawRestart();

            GUILayout.EndArea();
        }

        /// <summary>
        /// The three mechanisms as a toolbar, because exactly one may be active.
        ///
        /// Three checkboxes would let two be ticked, and a run shaped by two mechanisms fails for
        /// two reasons at once with no way to attribute either.
        /// </summary>
        private void DrawModeButtons()
        {
            var modes = new[]
            {
                HeuristicDriver.ReactionMode.Immediate,
                HeuristicDriver.ReactionMode.Delayed,
                HeuristicDriver.ReactionMode.CriticalDistance,
            };

            var names = new[] { "immediate", "delayed", "critical" };

            int current = System.Array.IndexOf(modes, driver.Mode);
            int picked = GUILayout.Toolbar(current, names);

            if (picked != current)
            {
                driver.Mode = modes[picked];
            }
        }

        private float Slider(string name, float value, float min, float max, string format)
        {
            GUILayout.BeginHorizontal();
            GUI.color = Accent;
            GUILayout.Label($"  {name,-10}", _label, GUILayout.Width(90f));
            GUI.color = Color.white;

            float next = GUILayout.HorizontalSlider(value, min, max, GUILayout.Width(150f));

            GUI.color = Idle;
            GUILayout.Label(string.Format(CultureInfo.InvariantCulture, format, next), _label);
            GUI.color = Color.white;
            GUILayout.EndHorizontal();

            return next;
        }

        /// <summary>
        /// Cause and effect in the same picture.
        ///
        /// The clearance bar is drawn against the threshold marker, so the moment the gate opens
        /// is visible as the bar crossing the line rather than as a number changing. The raw and
        /// issued commands sit next to each other, so what the gate suppressed is readable at a
        /// glance instead of inferred.
        /// </summary>
        private void DrawLive()
        {
            GUI.color = Color.white;
            GUILayout.Label("live", _header);

            if (driver.Mode == HeuristicDriver.ReactionMode.CriticalDistance)
            {
                GUI.color = driver.GateOpen ? Open : Held;
                GUILayout.Label(
                    $"  clearance {driver.ForwardClearance,5:F3}   gate " +
                    (driver.GateOpen ? "OPEN, steering" : "shut, straight"), _label);
                ClearanceBar(driver.ForwardClearance, driver.CriticalDistanceNorm);
                GUI.color = Color.white;
            }

            DrawStrategyContrast();

            GUI.color = Idle;
            GUILayout.Label($"  raw {driver.RawSteer,6:F3}    issued {driver.LastSteer,6:F3}", _label);
            GUILayout.Label($"  target {driver.TargetSpeedMs,5:F2} m/s   contacts {driver.WallContacts}",
                            _label);

            GUI.color = driver.Outcome == HeuristicDriver.EndReason.LapComplete ? Held
                      : driver.Outcome == HeuristicDriver.EndReason.Running ? Idle : Open;
            GUILayout.Label($"  {driver.Outcome}   {driver.ElapsedS,5:F1} s", _label);
            GUI.color = Color.white;
        }

        /// <summary>
        /// Both strategies side by side, with the idle one shown as a counterfactual.
        ///
        /// This is the point of having two scenes rather than one. Reading that argmax "steers at
        /// the longest ray and ignores the flank" is an argument; watching it command straight
        /// ahead while the weighted average pulls away from a wall the car is about to touch is
        /// the same claim as an observation.
        ///
        /// The divergence bar matters more than either number. On a clear straight both read zero
        /// and agree, which says nothing. The step that ended the argmax run on seed 1 was one
        /// where they disagreed by nearly a full lock, with the centre ray clear at 20 m and the
        /// right flank at 1.46 m.
        /// </summary>
        private void DrawStrategyContrast()
        {
            bool argmaxDriving = driver.ActiveStrategy == RayControllers.Strategy.MostOpen;

            GUI.color = argmaxDriving ? Accent : Idle;
            GUILayout.Label(
                $"  {(argmaxDriving ? ">" : " ")} most open      {driver.SteerMostOpen,6:F3}", _label);

            GUI.color = argmaxDriving ? Idle : Accent;
            GUILayout.Label(
                $"  {(argmaxDriving ? " " : ">")} weighted avg   {driver.SteerWeighted,6:F3}", _label);

            float d = driver.StrategyDivergence;

            // Amber once they differ by more than a ray step, which is 0.6 on the stated fan and
            // the smallest disagreement argmax is capable of expressing.
            GUI.color = d > 0.6f ? Open : (d > 0.05f ? new Color(1f, 0.85f, 0.5f) : Idle);
            GUILayout.Label($"    they differ by {d,5:F3}", _label);
            DivergenceBar(d);
            GUI.color = Color.white;
        }

        private void DivergenceBar(float divergence)
        {
            Rect line = GUILayoutUtility.GetRect(1f, 4f, GUILayout.ExpandWidth(true));

            GUI.color = new Color(1f, 1f, 1f, 0.12f);
            GUI.DrawTexture(line, _barTexture);

            // Scaled against 2.0, the widest possible disagreement, so the bar means the same
            // thing every frame rather than rescaling itself to whatever is happening.
            GUI.color = divergence > 0.6f ? Open : Accent;
            GUI.DrawTexture(new Rect(line.x, line.y,
                                     line.width * Mathf.Clamp01(divergence / 2f), line.height),
                            _barTexture);
        }

        /// <summary>
        /// Start a fresh run at the current settings, without leaving play mode.
        ///
        /// The panel only exists while playing, so a threshold cannot be chosen before pressing
        /// Play. Without this button a sweep meant stopping, editing a field in the Inspector and
        /// pressing Play for every value, which is the workflow this panel was built to replace.
        ///
        /// Bound to Enter as well as the button, because a sweep is a dozen runs and reaching for
        /// the mouse between each one is how a threshold gets left on the wrong value.
        /// </summary>
        private void DrawRestart()
        {
            if (GUILayout.Button("restart run at these settings   [Enter]"))
            {
                driver.RestartRun();
            }
        }

        private void ClearanceBar(float clearance, float threshold)
        {
            Rect line = GUILayoutUtility.GetRect(1f, 6f, GUILayout.ExpandWidth(true));

            GUI.color = new Color(1f, 1f, 1f, 0.12f);
            GUI.DrawTexture(line, _barTexture);

            GUI.color = new Color(0.45f, 0.92f, 0.55f, 0.45f);
            GUI.DrawTexture(new Rect(line.x, line.y, line.width * Mathf.Clamp01(clearance),
                                     line.height), _barTexture);

            // The threshold, as a hairline the bar crosses.
            GUI.color = Color.white;
            GUI.DrawTexture(new Rect(line.x + line.width * Mathf.Clamp01(threshold) - 1f,
                                     line.y - 2f, 2f, line.height + 4f), _barTexture);
        }
    }
}
