using UnityEngine;

namespace SelfDrivingSim.Environment
{
    /// <summary>
    /// Paints a metric grid onto the ground plane so motion is visible.
    ///
    /// A blank white plane gives a driver no optical flow: the car can be at top speed and
    /// look stationary, which makes the User Story 1 checks (does it accelerate, does the
    /// turning circle close, does it drift at rest) impossible to judge by eye. The grid is
    /// also a measuring tool: the major lines are 10 m apart, so a full-lock circle can be
    /// counted off against them before anyone writes a measurement script.
    ///
    /// The texture is generated in code rather than committed as an image. That keeps the
    /// repository free of a binary needing Git LFS, and it means the grid spacing is a named
    /// constant that a reader can check against the numbers it claims to show, rather than
    /// pixels nobody can verify (Constitution VI).
    /// </summary>
    [ExecuteAlways]
    [RequireComponent(typeof(MeshRenderer))]
    public class GridGround : MonoBehaviour
    {
        [Header("Grid spacing, in metres")]
        [Tooltip("Minor line spacing. One metre gives a clear sense of speed at 10 m/s.")]
        [SerializeField]
        private float minorCellM = 1f;

        [Tooltip("Minor cells between major lines. Major lines are the ones you count when " +
                 "pacing out a turning circle by eye.")]
        [SerializeField]
        private int minorCellsPerMajor = 10;

        [Header("Appearance")]
        [SerializeField] private Color baseColour = new Color(0.78f, 0.80f, 0.82f);
        [SerializeField] private Color minorLineColour = new Color(0.62f, 0.65f, 0.68f);
        [SerializeField] private Color majorLineColour = new Color(0.34f, 0.40f, 0.46f);

        [Tooltip("Texture pixels per minor cell. 64 is plenty; the lines are only a few pixels wide.")]
        [SerializeField]
        private int pixelsPerMinorCell = 64;

        [SerializeField] private int minorLineWidthPx = 2;
        [SerializeField] private int majorLineWidthPx = 6;

        private Material _material;
        private Texture2D _texture;

        private void OnEnable()
        {
            Rebuild();
        }

        private void OnDisable()
        {
            // Created with DontSave, so nothing lands in the scene file, but they still have
            // to be released explicitly or every domain reload leaks one of each.
            SafeDestroy(_material);
            SafeDestroy(_texture);
            _material = null;
            _texture = null;
        }

        /// <summary>Regenerate the texture and reapply it. Safe to call at any time.</summary>
        [ContextMenu("Rebuild grid")]
        public void Rebuild()
        {
            var meshRenderer = GetComponent<MeshRenderer>();
            if (meshRenderer == null)
            {
                return;
            }

            SafeDestroy(_texture);
            _texture = BuildGridTexture();

            if (_material == null)
            {
                // Built-in render pipeline. The ground primitive ships with Default-Material,
                // which is shared and must not be written to, so this component owns its own.
                Shader shader = Shader.Find("Standard");
                if (shader == null)
                {
                    Debug.LogError("[GridGround] Standard shader not found.");
                    return;
                }

                _material = new Material(shader) { name = "GridGround (generated)" };
                _material.hideFlags = HideFlags.DontSave;
            }

            _material.mainTexture = _texture;
            // A road surface is not a mirror. Left glossy, the grid washes out under the
            // directional light at exactly the grazing angles the chase camera looks along.
            _material.SetFloat("_Glossiness", 0.05f);
            _material.SetFloat("_Metallic", 0f);

            // One texture tile covers one MAJOR cell, so the repeat count is however many
            // major cells fit across the plane. Taken from the renderer bounds rather than
            // from the transform scale, so it stays right whatever the plane is scaled to.
            float majorCellM = Mathf.Max(0.001f, minorCellM * minorCellsPerMajor);
            Vector3 size = meshRenderer.bounds.size;
            _material.mainTextureScale = new Vector2(size.x / majorCellM, size.z / majorCellM);

            meshRenderer.sharedMaterial = _material;
        }

        private Texture2D BuildGridTexture()
        {
            int cells = Mathf.Max(1, minorCellsPerMajor);
            int cellPx = Mathf.Max(4, pixelsPerMinorCell);
            int resolution = cells * cellPx;

            var texture = new Texture2D(resolution, resolution, TextureFormat.RGBA32, mipChain: true)
            {
                name = "GridGround texture (generated)",
                hideFlags = HideFlags.DontSave,
                wrapMode = TextureWrapMode.Repeat,
                // Trilinear plus anisotropy: without mip filtering the far half of the plane
                // turns into shimmering noise the moment the car moves, which is worse for
                // judging motion than no grid at all.
                filterMode = FilterMode.Trilinear,
                anisoLevel = 9,
            };

            var pixels = new Color32[resolution * resolution];
            Color32 baseC = baseColour;
            Color32 minorC = minorLineColour;
            Color32 majorC = majorLineColour;

            int minorW = Mathf.Max(1, minorLineWidthPx);
            int majorW = Mathf.Max(minorW, majorLineWidthPx);

            for (int y = 0; y < resolution; y++)
            {
                // A major line sits on the tile edge, because one tile is one major cell.
                bool majorRow = y < majorW;
                bool minorRow = (y % cellPx) < minorW;

                for (int x = 0; x < resolution; x++)
                {
                    bool majorCol = x < majorW;
                    bool minorCol = (x % cellPx) < minorW;

                    Color32 c = baseC;
                    if (minorRow || minorCol) c = minorC;
                    if (majorRow || majorCol) c = majorC;

                    pixels[(y * resolution) + x] = c;
                }
            }

            texture.SetPixels32(pixels);
            texture.Apply(updateMipmaps: true);
            return texture;
        }

        private static void SafeDestroy(Object obj)
        {
            if (obj == null)
            {
                return;
            }

            if (Application.isPlaying)
            {
                Destroy(obj);
            }
            else
            {
                DestroyImmediate(obj);
            }
        }
    }
}
