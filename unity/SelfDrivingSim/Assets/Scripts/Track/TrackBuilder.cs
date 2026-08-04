using System.Collections.Generic;
using UnityEngine;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Builds the drivable surface, its barriers and its checkpoints from a loaded track file.
    ///
    /// This component performs no statistics and draws no random numbers. Every decision was
    /// made in Python, proved there, and written into the file; here the numbers are turned
    /// into geometry. If this class ever needs to decide something, that decision belongs
    /// upstream where it can be tested against the dataset.
    ///
    /// **Coordinate mapping.** The track file is a plan view: x and y on a flat sheet. Unity's
    /// ground plane is x and z, with y up. So a file point (x, y) becomes a world point
    /// (x, 0, y). Getting this backwards produces a track standing on its edge, which is
    /// obvious, or a mirrored one, which is not: a mirrored track still drives, still closes
    /// and still passes every check, while every left corner has become a right corner and the
    /// steering distribution the track was validated for is reflected. The mapping is written
    /// once, in <see cref="ToWorld"/>, and used everywhere.
    /// </summary>
    public class TrackBuilder : MonoBehaviour
    {
        [Header("Source")]
        [Tooltip("Seed to build. The file is read from Assets/Tracks/seed_<seed>.json.")]
        [SerializeField] private int seed = 1;

        [Tooltip("The car's profile. The track file carries the profile it was validated " +
                 "against and the two are compared; a track built for a different car is " +
                 "refused rather than silently driven.")]
        [SerializeField] private VehicleProfile profile = new VehicleProfile();

        [Header("Surface")]
        [Tooltip("Material for the drivable ribbon. Optional; a default is used when empty.")]
        [SerializeField] private Material surfaceMaterial;

        [Tooltip("Material for the barriers. Optional.")]
        [SerializeField] private Material barrierMaterial;

        [Header("Barriers (FR-023)")]
        [Tooltip("How tall the edge barriers stand, in metres. High enough that the car " +
                 "cannot ride over one, low enough not to block the chase camera.")]
        [SerializeField] private float barrierHeightM = 0.8f;

        [Tooltip("How thick each barrier is, in metres.")]
        [SerializeField] private float barrierThicknessM = 0.4f;

        [Header("Checkpoints")]
        [Tooltip("Height of the checkpoint trigger volumes. They are triggers, never solid, " +
                 "so a car passing through one is recorded and not deflected.")]
        [SerializeField] private float checkpointHeightM = 3f;

        [Tooltip("The ring that counts progress. Each gate is bound to it with its own index " +
                 "as the gates are created. Optional: without one the track still builds and " +
                 "drives, it simply counts nothing.")]
        [SerializeField] private CheckpointRing ring;

        /// <summary>The track currently built, or null.</summary>
        public TrackFileRecord Current { get; private set; }

        /// <summary>The checkpoint objects in progress order.</summary>
        public IReadOnlyList<Transform> Checkpoints => _checkpoints;

        private readonly List<Transform> _checkpoints = new List<Transform>();
        private GameObject _root;

        private void Awake()
        {
            Build();
        }

        /// <summary>Path of the file this builder reads.</summary>
        public string TrackPath =>
            System.IO.Path.Combine(Application.dataPath, "Tracks", $"seed_{seed}.json");

        /// <summary>
        /// Read the file and construct everything. Safe to call repeatedly; the previous build
        /// is destroyed first so a rebuild does not leave two tracks occupying one space.
        /// </summary>
        [ContextMenu("Build track")]
        public void Build()
        {
            Clear();

            TrackFileRecord record = TrackFile.Load(TrackPath, profile);
            Current = record;

            _root = new GameObject($"Track seed {record.seed}");
            _root.transform.SetParent(transform, worldPositionStays: false);

            Vector3[] centre = new Vector3[record.centre_line.Length];
            for (int i = 0; i < centre.Length; i++)
            {
                centre[i] = ToWorld(record.centre_line[i].x, record.centre_line[i].y);
            }

            Vector3[] normals = LateralNormals(centre);

            BuildSurface(centre, normals, record.width_m);
            BuildBarrier(centre, normals, record.width_m, side: +1f);
            BuildBarrier(centre, normals, record.width_m, side: -1f);
            BuildCheckpoints(record);
        }

        /// <summary>Destroy anything a previous build created.</summary>
        public void Clear()
        {
            _checkpoints.Clear();
            Current = null;

            if (_root == null)
            {
                return;
            }

            if (Application.isPlaying)
            {
                Destroy(_root);
            }
            else
            {
                DestroyImmediate(_root);
            }

            _root = null;
        }

        /// <summary>The one place the file's plan view becomes a Unity world position.</summary>
        private static Vector3 ToWorld(float x, float y)
        {
            return new Vector3(x, 0f, y);
        }

        /// <summary>
        /// Unit vectors pointing across the track at each sample.
        ///
        /// The tangent is taken from the neighbours on both sides rather than from the next
        /// point alone. A one-sided difference lags the curve by half a sample, which on a
        /// tight corner shows up as a visibly lopsided ribbon, wider on the outside of every
        /// bend. Indices wrap, because the line is closed and the first sample's previous
        /// neighbour is the last one.
        /// </summary>
        private static Vector3[] LateralNormals(Vector3[] centre)
        {
            int n = centre.Length;
            var normals = new Vector3[n];

            for (int i = 0; i < n; i++)
            {
                Vector3 previous = centre[(i - 1 + n) % n];
                Vector3 next = centre[(i + 1) % n];
                Vector3 tangent = (next - previous).normalized;

                // Rotate the tangent a quarter turn about the up axis.
                normals[i] = new Vector3(tangent.z, 0f, -tangent.x);
            }

            return normals;
        }

        private void BuildSurface(Vector3[] centre, Vector3[] normals, float widthM)
        {
            int n = centre.Length;
            float half = widthM * 0.5f;

            var vertices = new Vector3[n * 2];
            var uvs = new Vector2[n * 2];

            for (int i = 0; i < n; i++)
            {
                vertices[i * 2] = centre[i] + normals[i] * half;
                vertices[i * 2 + 1] = centre[i] - normals[i] * half;

                // v runs along the track so a texture repeats down its length rather than
                // being stretched once around the whole lap.
                float v = i / (float)n;
                uvs[i * 2] = new Vector2(0f, v * n * 0.1f);
                uvs[i * 2 + 1] = new Vector2(1f, v * n * 0.1f);
            }

            var triangles = new List<int>(n * 6);
            for (int i = 0; i < n; i++)
            {
                // The last quad joins back to the first pair, which is what makes the surface
                // closed. The centre line deliberately does not repeat its first point, so
                // without this wrap the track would have a gap one sample wide.
                int a = i * 2;
                int b = i * 2 + 1;
                int c = ((i + 1) % n) * 2;
                int d = ((i + 1) % n) * 2 + 1;

                // Winding matters and is easy to get wrong invisibly. The lateral normal for a
                // tangent of +X is -Z, so ordering these (a, c, b) gives a face normal of -Y:
                // the road faces the ground, is backface-culled from above, and cannot be
                // seen. It is still perfectly solid, because MeshCollider ignores winding, so
                // the symptom is a car driving on an invisible surface rather than an error.
                // (a, b, c) puts the normal at +Y. Checked by rendering, not by reasoning.
                triangles.Add(a); triangles.Add(b); triangles.Add(c);
                triangles.Add(b); triangles.Add(d); triangles.Add(c);
            }

            var surface = new GameObject("Surface");
            surface.transform.SetParent(_root.transform, worldPositionStays: false);

            Mesh mesh = NewMesh("track surface", vertices, triangles, uvs);
            surface.AddComponent<MeshFilter>().sharedMesh = mesh;
            surface.AddComponent<MeshRenderer>().sharedMaterial =
                surfaceMaterial != null ? surfaceMaterial : DefaultMaterial(new Color(0.22f, 0.23f, 0.25f));
            surface.AddComponent<MeshCollider>().sharedMesh = mesh;
        }

        /// <summary>
        /// A wall standing along one edge (FR-023).
        ///
        /// Built as its own mesh rather than a chain of box colliders. A few thousand boxes
        /// would each be a separate collider for the physics engine to consider, and the seams
        /// between them catch a wheel: the car climbs a barely visible step and is thrown.
        /// </summary>
        private void BuildBarrier(Vector3[] centre, Vector3[] normals, float widthM, float side)
        {
            int n = centre.Length;
            float offset = widthM * 0.5f + barrierThicknessM * 0.5f;

            // Four vertices per sample: inner and outer, bottom and top.
            var vertices = new Vector3[n * 4];
            for (int i = 0; i < n; i++)
            {
                Vector3 inner = centre[i] + normals[i] * side * (offset - barrierThicknessM * 0.5f);
                Vector3 outer = centre[i] + normals[i] * side * (offset + barrierThicknessM * 0.5f);
                Vector3 up = Vector3.up * barrierHeightM;

                vertices[i * 4] = inner;
                vertices[i * 4 + 1] = outer;
                vertices[i * 4 + 2] = inner + up;
                vertices[i * 4 + 3] = outer + up;
            }

            var triangles = new List<int>(n * 24);
            for (int i = 0; i < n; i++)
            {
                int c = i * 4;
                int d = ((i + 1) % n) * 4;

                // Inner face, outer face and the top cap. The bottom is left open: it sits on
                // the surface and is never seen, and the triangles would still be simulated.
                AddQuad(triangles, c + 0, d + 0, c + 2, d + 2);
                AddQuad(triangles, d + 1, c + 1, d + 3, c + 3);
                AddQuad(triangles, c + 2, d + 2, c + 3, d + 3);
            }

            // Mirroring the offset mirrors the vertex layout, which reverses the winding, so
            // the two barriers cannot share one triangle order. Built with the left-hand
            // order above and flipped here for the right, rather than written out twice.
            //
            // Left unflipped, the inner barrier renders as a dark line while the outer one is
            // a lit wall: its faces point into the barrier. It still collides correctly, since
            // MeshCollider ignores winding, so nothing fails and the track merely looks wrong.
            if (side < 0f)
            {
                for (int i = 0; i < triangles.Count; i += 3)
                {
                    (triangles[i + 1], triangles[i + 2]) = (triangles[i + 2], triangles[i + 1]);
                }
            }

            var barrier = new GameObject(side > 0 ? "Barrier left" : "Barrier right");
            barrier.transform.SetParent(_root.transform, worldPositionStays: false);

            Mesh mesh = NewMesh("barrier", vertices, triangles, null);
            barrier.AddComponent<MeshFilter>().sharedMesh = mesh;
            barrier.AddComponent<MeshRenderer>().sharedMaterial =
                barrierMaterial != null ? barrierMaterial : DefaultMaterial(new Color(0.75f, 0.76f, 0.78f));
            barrier.AddComponent<MeshCollider>().sharedMesh = mesh;
        }

        private static void AddQuad(List<int> triangles, int a, int b, int c, int d)
        {
            triangles.Add(a); triangles.Add(b); triangles.Add(c);
            triangles.Add(c); triangles.Add(b); triangles.Add(d);
        }

        /// <summary>
        /// Trigger volumes at each checkpoint, parented in progress order.
        ///
        /// Triggers, never solid. A checkpoint that pushed the car would change the driving it
        /// is meant only to measure.
        /// </summary>
        private void BuildCheckpoints(TrackFileRecord record)
        {
            var parent = new GameObject("Checkpoints");
            parent.transform.SetParent(_root.transform, worldPositionStays: false);

            foreach (CheckpointRecord checkpoint in record.checkpoints)
            {
                var gate = new GameObject($"Checkpoint {checkpoint.index:D2}");
                gate.transform.SetParent(parent.transform, worldPositionStays: false);
                gate.transform.position =
                    ToWorld(checkpoint.x, checkpoint.y) + Vector3.up * (checkpointHeightM * 0.5f);

                // Face along the track, so the trigger's local z is the direction of travel
                // and its local x spans the width.
                Vector3 forward = ToWorld(checkpoint.forward_x, checkpoint.forward_y);
                if (forward.sqrMagnitude > 1e-6f)
                {
                    gate.transform.rotation = Quaternion.LookRotation(forward, Vector3.up);
                }

                var box = gate.AddComponent<BoxCollider>();
                box.isTrigger = true;
                // Thin along the direction of travel and full width across it: a gate the car
                // passes THROUGH, not a volume it sits inside for several samples.
                box.size = new Vector3(record.width_m, checkpointHeightM, 0.5f);

                // The gate carries the file's own index, not its position in this loop. They
                // agree today because the loader has already refused any file whose
                // checkpoints are not monotonic in s, but binding to the loop counter would
                // make that agreement a coincidence rather than a checked property.
                gate.AddComponent<CheckpointTrigger>().Bind(ring, checkpoint.index);

                _checkpoints.Add(gate.transform);
            }

            if (ring != null)
            {
                ring.Configure(_checkpoints);
            }
        }

        private static Mesh NewMesh(string name, Vector3[] vertices, List<int> triangles,
                                    Vector2[] uvs)
        {
            var mesh = new Mesh { name = name };

            // A track is 2000 samples, so the surface alone is 4000 vertices and the barriers
            // 8000 each. That is under the 16-bit limit today, but the index format is set
            // explicitly rather than relying on it: raising SAMPLES_PER_TRACK would otherwise
            // fail as scrambled geometry rather than as an error.
            mesh.indexFormat = vertices.Length > 65000
                ? UnityEngine.Rendering.IndexFormat.UInt32
                : UnityEngine.Rendering.IndexFormat.UInt16;

            mesh.vertices = vertices;
            mesh.triangles = triangles.ToArray();
            if (uvs != null)
            {
                mesh.uv = uvs;
            }

            mesh.RecalculateNormals();
            mesh.RecalculateBounds();

            return mesh;
        }

        private static Material DefaultMaterial(Color colour)
        {
            // The project uses the built-in render pipeline. Shader.Find is acceptable here
            // because this runs once per build, not per frame.
            Shader shader = Shader.Find("Standard") ?? Shader.Find("Diffuse");
            return new Material(shader) { color = colour };
        }
    }
}
