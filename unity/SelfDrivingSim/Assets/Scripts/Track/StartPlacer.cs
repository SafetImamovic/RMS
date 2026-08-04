using UnityEngine;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Puts the car down at a random marker, slightly off centre and slightly off straight
    /// (FR-030, research C12, T058).
    ///
    /// **Why the start is randomised at all.** An agent that always begins on the same metre
    /// of the same track learns that metre. It memorises a sequence of turns rather than a
    /// policy for taking a turn, and the failure is invisible during training because
    /// training measures the very episodes the memorisation was built from. Starting anywhere
    /// on the lap, a little off centre and a little off straight, means the only thing worth
    /// learning is how to recover to the racing line and follow it, which is the thing the
    /// M5 comparison is about.
    ///
    /// **This is a separate component and not a few lines inside TrackBuilder.** TrackBuilder
    /// states that it performs no statistics and draws no random numbers, and that is worth
    /// more than the one object saved by folding this into it: the track built for seed 7 is
    /// the same track every run, byte for byte, and it stays reviewable in a diff precisely
    /// because nothing in its construction path can vary. Randomness lives here, where it
    /// affects where the car is put and nothing else.
    /// </summary>
    public class StartPlacer : MonoBehaviour
    {
        [Header("What is being placed")]
        [SerializeField] private CarController car;

        [Tooltip("The markers to choose a start from. Also told where the lap now begins, so " +
                 "that a lap is completed by returning to the chosen marker rather than by " +
                 "reaching marker zero.")]
        [SerializeField] private CheckpointRing ring;

        [Header("Randomisation (python/track/config.py)")]
        [Tooltip("START_LATERAL_M. Half the range: the offset is drawn from -this to +this " +
                 "across the track. 1.5 m on a 6 m track leaves the car comfortably on the " +
                 "surface at either extreme.")]
        [SerializeField] private float startLateralM = 1.5f;

        [Tooltip("START_YAW_DEG. Half the range, in degrees either side of the track " +
                 "direction. Enough that the car must correct its heading, small enough that " +
                 "it is never pointed at a barrier.")]
        [SerializeField] private float startYawDeg = 10f;

        [Tooltip("Height above the road the car body is placed at. The markers sit at the " +
                 "centre of a three-metre trigger volume, so their own y is no use here.\n\n" +
                 "0.5 m is the height the Track scene already spawns the car at, which the " +
                 "suspension was settled against. Dropping the car from higher makes it " +
                 "bounce on the first physics step, and a run that begins with the wheels " +
                 "off the ground begins with the observations meaning nothing.")]
        [SerializeField] private float rideHeightM = 0.5f;

        [Header("Reproducibility")]
        [Tooltip("Negative for a fresh draw each run. Any other value makes the sequence of " +
                 "starts repeatable, which is what turns 'the car span at the start' into " +
                 "something that can be reproduced and looked at (Principle VI).")]
        [SerializeField] private int randomSeed = -1;

        [Tooltip("Place the car once when the scene starts. Off if something else drives the " +
                 "placement, such as the episode reset M3 will add.")]
        [SerializeField] private bool placeOnStart = true;

        private System.Random _random;

        /// <summary>The marker the car was last placed at, or -1.</summary>
        public int LastStartIndex { get; private set; } = -1;

        private void Awake()
        {
            if (car == null)
            {
                car = FindAnyObjectByType<CarController>();
            }

            _random = randomSeed >= 0 ? new System.Random(randomSeed) : new System.Random();
        }

        private void Start()
        {
            // Start, not Awake. TrackBuilder builds in Awake and the markers do not exist
            // before it has, so placing the car any earlier would find an empty ring and
            // leave it wherever the scene put it.
            if (placeOnStart)
            {
                Place();
            }
        }

        /// <summary>Draw a start and put the car there.</summary>
        [ContextMenu("Place car at a random start")]
        public void Place()
        {
            if (ring == null || ring.Count == 0 || car == null)
            {
                Debug.LogWarning("[StartPlacer] nothing to place, or nowhere to place it: " +
                                 $"car {(car == null ? "missing" : "ok")}, " +
                                 $"markers {(ring == null ? 0 : ring.Count)}.", this);
                return;
            }

            _random ??= new System.Random();
            PlaceAt(_random.Next(ring.Count));
        }

        /// <summary>
        /// Put the car at a named marker, still with a random offset and heading. Exposed so
        /// a measurement can pin the position down while leaving the perturbation in place.
        /// </summary>
        public void PlaceAt(int markerIndex)
        {
            if (ring == null || ring.Count == 0 || car == null)
            {
                return;
            }

            _random ??= new System.Random();

            markerIndex = ((markerIndex % ring.Count) + ring.Count) % ring.Count;
            Transform marker = ring.Markers[markerIndex];

            // The marker's own forward is the direction of travel: TrackBuilder rotates each
            // gate to look along the centre line. Flattened, because the gate is a box three
            // metres tall and its transform carries that height in its position, not its
            // rotation, but flattening costs nothing and makes the assumption explicit.
            Vector3 forward = Vector3.ProjectOnPlane(marker.forward, Vector3.up);
            if (forward.sqrMagnitude < 1e-6f)
            {
                forward = Vector3.forward;
            }

            forward.Normalize();
            Vector3 right = Vector3.Cross(Vector3.up, forward);

            float lateral = Range(-startLateralM, startLateralM);
            float yaw = Range(-startYawDeg, startYawDeg);

            Vector3 position = marker.position;
            position.y = 0f;
            position += right * lateral + Vector3.up * rideHeightM;

            Quaternion rotation = Quaternion.AngleAxis(yaw, Vector3.up) *
                                  Quaternion.LookRotation(forward, Vector3.up);

            // Through SetSpawn rather than the transform, so the out-of-bounds reset and the
            // R key both return the car here instead of to wherever the scene left it.
            car.SetSpawn(position, rotation);

            // The lap now begins at the marker the car is standing on. Without this the ring
            // would still expect marker zero, so every start away from the line would read as
            // a skipped gate and the first lap would never complete.
            ring.StartAt(markerIndex);

            LastStartIndex = markerIndex;

            Debug.Log($"[StartPlacer] start at marker {markerIndex:D2} of {ring.Count}, " +
                      $"{lateral:+0.00;-0.00} m across, {yaw:+0.0;-0.0}° off line.");
        }

        private float Range(float min, float max)
        {
            return min + (float)_random.NextDouble() * (max - min);
        }
    }
}
