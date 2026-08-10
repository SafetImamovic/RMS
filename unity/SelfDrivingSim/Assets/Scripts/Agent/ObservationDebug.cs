using System.Globalization;
using UnityEngine;
using UnityEngine.InputSystem;
using SelfDrivingSim.Track;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// Every observation the agent will see, on screen, while a person drives (FR-029).
    ///
    /// This panel is the M2 gate. T062 is passed by reading each value here against a
    /// situation whose correct answer is visible out of the window: a barrier three metres
    /// off the left front wing, a marker directly ahead, a car sitting still. Sensing that
    /// has never been read is sensing nobody has checked, and an agent that will not learn
    /// because ray 7 is reversed looks exactly like an agent that needs more training.
    ///
    /// It reads <see cref="CarAgent.Observations"/> rather than recomputing anything. A panel
    /// that assembled its own copy could show a correct value beside a network being fed a
    /// wrong one, which would make it worse than no panel at all.
    ///
    /// IMGUI for the same reasons as DriveHud: no canvas, no prefab, no scene wiring, and it
    /// cannot break the scene it is dropped into. English only, unlike DriveHud, because this
    /// is developer instrumentation rather than part of the calibration readout.
    ///
    /// O toggles the panel.
    /// </summary>
    public class ObservationDebug : MonoBehaviour
    {
        [SerializeField] private CarAgent agent;

        [Tooltip("Optional. Shown beside the observations so a marker award can be seen at " +
                 "the moment it happens, which is what T060 and T061 are checked against.")]
        [SerializeField] private CheckpointRing ring;

        [SerializeField] private bool visible = true;
        [SerializeField] private int fontSize = 12;
        [SerializeField] private float panelWidth = 400f;

        [Tooltip("Also draw the ray fan into the game view as coloured lines. Useful while " +
                 "parking the car for T059; needs Gizmos enabled in the Game view.")]
        [SerializeField] private bool drawRays = true;

        private GUIStyle _label;
        private GUIStyle _header;
        private Texture2D _panelTexture;
        private Texture2D _barTexture;
        private Material _lineMaterial;

        private static readonly Color Hit = new Color(1.0f, 0.55f, 0.45f);
        private static readonly Color Clear = new Color(0.45f, 0.92f, 0.55f);
        private static readonly Color Idle = new Color(0.72f, 0.75f, 0.78f);

        private void Awake()
        {
            if (agent == null)
            {
                agent = GetComponentInParent<CarAgent>();
            }
        }

        private void OnDestroy()
        {
            if (_panelTexture != null)
            {
                Destroy(_panelTexture);
            }

            if (_barTexture != null)
            {
                Destroy(_barTexture);
            }

            if (_lineMaterial != null)
            {
                Destroy(_lineMaterial);
            }
        }

        /// <summary>
        /// A vertex-coloured material for the GL lines. Unity's built-in Internal-Colored
        /// shader, which exists precisely for debug drawing, with depth testing left on so a
        /// ray that passes behind a barrier is hidden by it. That occlusion is information:
        /// a ray drawn straight through a wall means the wall has no collider.
        /// </summary>
        private void EnsureLineMaterial()
        {
            if (_lineMaterial != null)
            {
                return;
            }

            _lineMaterial = new Material(Shader.Find("Hidden/Internal-Colored"))
            {
                hideFlags = HideFlags.HideAndDontSave,
            };

            _lineMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            _lineMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            _lineMaterial.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
            _lineMaterial.SetInt("_ZWrite", 0);
        }

        private void Update()
        {
            Keyboard keyboard = Keyboard.current;
            if (keyboard != null && keyboard.oKey.wasPressedThisFrame)
            {
                visible = !visible;
            }
        }

        private void EnsureStyles()
        {
            if (_label != null)
            {
                return;
            }

            _panelTexture = Solid(new Color(0.06f, 0.08f, 0.10f, 0.82f));
            _barTexture = Solid(Color.white);

            _label = new GUIStyle(GUI.skin.label)
            {
                fontSize = fontSize,
                richText = true,
                // Monospace, so thirteen rows of numbers form columns rather than a ragged
                // block that has to be read one line at a time.
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
            if (!visible || agent == null)
            {
                return;
            }

            EnsureStyles();

            // Invariant, for the same reason DriveHud forces it: this machine's locale writes
            // 0,73 and every document these values are checked against writes 0.73.
            CultureInfo previous = CultureInfo.CurrentCulture;
            CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
            try
            {
                Draw(new Rect(Screen.width - panelWidth - 12f, 12f, panelWidth,
                              26f + (agent.ObservationCount + 6) * (fontSize + 5f)));
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
            GUILayout.Label($"OBSERVATIONS  {agent.ObservationCount} values   [O] hide",
                            _header);

            DrawRays();
            DrawSelfState();
            DrawRing();

            GUILayout.EndArea();
        }

        private void DrawRays()
        {
            GUI.color = Idle;
            GUILayout.Label("rays        angle   norm   metres", _label);

            for (int i = 0; i < agent.RayCount && i < agent.RayDistancesNorm.Count; i++)
            {
                bool hit = agent.RayHit[i];

                // The no-hit state is spelled out as a word, not inferred from the number
                // (FR-025). A miss reads 1.000 and a genuine hit at the range limit reads
                // 1.000 too, so the two are separated here and nowhere else on screen.
                GUI.color = hit ? Hit : Clear;
                string metres = hit
                    ? $"{agent.RayDistancesM[i],6:F2} m"
                    : "   none";

                GUILayout.Label(
                    $"  {i:D2}  {agent.RayAngleDeg(i),+6:F0}°  {agent.RayDistancesNorm[i],6:F3}  {metres}",
                    _label);

                Bar(agent.RayDistancesNorm[i], hit ? Hit : Clear);
            }
        }

        /// <summary>
        /// A one-pixel-tall bar under each ray. Thirteen numbers changing at 50 Hz are hard to
        /// read as a shape, and the shape is the point: the fan should sweep smoothly and dip
        /// where a barrier is, so a single ray out of line is visible without reading any
        /// value at all.
        /// </summary>
        private void Bar(float value01, Color colour)
        {
            Rect line = GUILayoutUtility.GetRect(1f, 2f, GUILayout.ExpandWidth(true));
            GUI.color = new Color(colour.r, colour.g, colour.b, 0.35f);
            GUI.DrawTexture(new Rect(line.x, line.y, line.width * Mathf.Clamp01(value01),
                                     line.height), _barTexture);
        }

        private void DrawSelfState()
        {
            GUILayout.Space(4f);
            GUI.color = Color.white;
            GUILayout.Label("self state", _header);
            GUI.color = Idle;

            int at = agent.RayCount;
            for (int i = 0; i < CarAgent.SelfStateCount; i++)
            {
                float value = agent.Observations[at + i];
                GUILayout.Label($"  {agent.ObservationName(at + i),-20} {value,7:F3}", _label);
                Bar((value + 1f) * 0.5f, Idle);
            }

            GUI.color = Color.white;
        }

        private void DrawRing()
        {
            if (ring == null || ring.Count == 0)
            {
                return;
            }

            GUILayout.Space(4f);
            GUI.color = ring.WrongWay ? Hit : Clear;
            GUILayout.Label(
                $"marker {ring.NextIndex:D2}/{ring.Count}   awarded {ring.AwardedCount}   " +
                $"lap {ring.LapCount}   skipped {ring.SkippedContactCount}" +
                (ring.WrongWay ? "   WRONG WAY" : string.Empty),
                _label);
            GUI.color = Color.white;
        }

        /// <summary>
        /// The fan drawn in the world, so a reading can be traced to the barrier that produced
        /// it. CarAgent draws the same lines as gizmos when it is selected; this draws them
        /// while driving, when nothing is selected and the Inspector is not being watched.
        /// </summary>
        private void OnRenderObject()
        {
            if (!drawRays || !visible || agent == null)
            {
                return;
            }

            EnsureLineMaterial();

            Vector3 origin = agent.SensorOrigin;

            // SetPass is not optional. Without an active pass the GL calls are issued against
            // whatever material the previous draw left bound, which renders as nothing at all
            // on some frames and as coloured lines on others.
            _lineMaterial.SetPass(0);

            GL.PushMatrix();
            GL.Begin(GL.LINES);
            for (int i = 0; i < agent.RayCount && i < agent.RayDistancesM.Count; i++)
            {
                GL.Color(agent.RayHit[i] ? Hit : Clear);
                Vector3 direction = agent.RayDirection(i);
                GL.Vertex(origin);
                GL.Vertex(origin + direction * agent.RayDistancesM[i]);
            }

            GL.End();
            GL.PopMatrix();
        }
    }
}
