using System.Collections.Generic;
using System.IO;
using UnityEngine;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Logging
{
    /// <summary>
    /// Measures a keyboard drive against the M1 envelope, live.
    ///
    /// This type computes; DriveHud only draws it, and DriveLogger (task T018) will write
    /// the same quantities to CSV. Keeping the arithmetic in one place is the point: a HUD
    /// that computed its own version of the steering-change percentile could show green
    /// while the log it is supposed to summarise showed red, and the driver would have no
    /// way to know which to believe.
    ///
    /// The one rule that shapes everything here: **per-frame quantities are sampled at
    /// COMPARE_HZ, not per rendered frame.** The dataset's 95th-percentile steering change
    /// of 0.30 was measured at 14.08 frames per second. Unity runs at whatever rate the
    /// machine allows, so differencing steering every frame and comparing that to 0.30 would
    /// measure the difference in frame rate rather than any difference in driving
    /// (research C14). At 120 fps it would report roughly a tenth of the truth.
    /// </summary>
    public class DriveTelemetry : MonoBehaviour
    {
        [SerializeField] private CarController car;

        [Tooltip("Read from Assets/Tracks/vehicle_profile.json at startup. The thresholds the " +
                 "drive is judged against travel with the profile so they cannot drift from M1.")]
        [SerializeField]
        private string profileFileName = "vehicle_profile.json";

        private CalibrationEnvelope _envelope;

        // Samples taken on the COMPARE_HZ clock, not per frame.
        private readonly List<float> _absDeltaSteer = new List<float>(4096);
        private readonly List<float> _speedSamples = new List<float>(4096);
        private float _nextSampleTime;
        private float _lastSampledSteer;
        private bool _hasFirstSample;

        // Cached percentile, recomputed a few times a second rather than every frame.
        private float _cachedP95;
        private float _nextPercentileTime;

        /// <summary>Seconds between samples. The reciprocal of the dataset's frame rate.</summary>
        public float SampleIntervalS => _envelope != null && _envelope.compare_hz > 0f
            ? 1f / _envelope.compare_hz
            : 1f / 14.08f;

        public CalibrationEnvelope Envelope => _envelope;
        public CarController Car => car;

        /// <summary>How long the current drive has been running.</summary>
        public float ElapsedS { get; private set; }

        /// <summary>Samples taken so far on the COMPARE_HZ clock.</summary>
        public int SampleCount => _speedSamples.Count;

        public float MaxSteerRight { get; private set; }
        public float MaxSteerLeft { get; private set; }
        public float MaxAbsDeltaSteer { get; private set; }
        public float MaxSpeedMs { get; private set; }

        /// <summary>Latest steering change between two COMPARE_HZ samples.</summary>
        public float LastAbsDeltaSteer { get; private set; }

        /// <summary>95th percentile of |delta steering| at COMPARE_HZ. The FR-005 figure.</summary>
        public float DeltaSteerP95 => _cachedP95;

        /// <summary>
        /// Ratio of peak speed to the 99th percentile of speed. Unit free, so it is the one
        /// speed quantity that may be held against the dataset (FR-004).
        /// </summary>
        public float SpeedMaxOverP99
        {
            get
            {
                if (_speedSamples.Count < 30)
                {
                    return 0f;
                }

                float p99 = Percentile(_speedSamples, 99f);
                return p99 > 0.001f ? MaxSpeedMs / p99 : 0f;
            }
        }

        private void Awake()
        {
            if (car == null)
            {
                car = GetComponent<CarController>();
            }

            LoadEnvelope();
            ResetRun();
        }

        private void LoadEnvelope()
        {
            string path = Path.Combine(Application.dataPath, "Tracks", profileFileName);
            if (!File.Exists(path))
            {
                Debug.LogWarning($"[DriveTelemetry] {path} not found. " +
                                 "Run: python -m python.track.vehicle");
                return;
            }

            var file = JsonUtility.FromJson<VehicleProfileFile>(File.ReadAllText(path));
            if (file == null || file.envelope == null)
            {
                Debug.LogWarning("[DriveTelemetry] profile file carries no envelope block.");
                return;
            }

            _envelope = file.envelope;
        }

        /// <summary>Start a fresh measurement run. The HUD binds this to a key.</summary>
        public void ResetRun()
        {
            _absDeltaSteer.Clear();
            _speedSamples.Clear();
            ElapsedS = 0f;
            _nextSampleTime = 0f;
            _hasFirstSample = false;
            _lastSampledSteer = 0f;
            MaxSteerRight = 0f;
            MaxSteerLeft = 0f;
            MaxAbsDeltaSteer = 0f;
            MaxSpeedMs = 0f;
            LastAbsDeltaSteer = 0f;
            _cachedP95 = 0f;
            _nextPercentileTime = 0f;
        }

        private void Update()
        {
            if (car == null)
            {
                return;
            }

            ElapsedS += Time.deltaTime;

            // Instantaneous extremes are tracked every frame, because a peak reached between
            // two samples is still a peak the vehicle actually reached (SC-002, SC-005).
            MaxSteerRight = Mathf.Max(MaxSteerRight, car.SteerNorm);
            MaxSteerLeft = Mathf.Min(MaxSteerLeft, car.SteerNorm);
            MaxSpeedMs = Mathf.Max(MaxSpeedMs, car.SpeedMs);

            if (ElapsedS >= _nextSampleTime)
            {
                TakeSample();
                _nextSampleTime += SampleIntervalS;
            }

            if (ElapsedS >= _nextPercentileTime)
            {
                _cachedP95 = Percentile(_absDeltaSteer, 95f);
                _nextPercentileTime = ElapsedS + 0.2f;
            }
        }

        private void TakeSample()
        {
            float steer = car.SteerNorm;
            _speedSamples.Add(car.SpeedMs);

            if (_hasFirstSample)
            {
                // The delta that matters: between consecutive COMPARE_HZ samples, which is
                // what the dataset's figure was measured on.
                LastAbsDeltaSteer = Mathf.Abs(steer - _lastSampledSteer);
                _absDeltaSteer.Add(LastAbsDeltaSteer);
                MaxAbsDeltaSteer = Mathf.Max(MaxAbsDeltaSteer, LastAbsDeltaSteer);
            }

            _lastSampledSteer = steer;
            _hasFirstSample = true;
        }

        /// <summary>Nearest-rank percentile. Copies and sorts, so call it sparingly.</summary>
        private static float Percentile(List<float> values, float percentile)
        {
            if (values == null || values.Count == 0)
            {
                return 0f;
            }

            var sorted = new List<float>(values);
            sorted.Sort();
            int rank = Mathf.CeilToInt((percentile / 100f) * sorted.Count) - 1;
            return sorted[Mathf.Clamp(rank, 0, sorted.Count - 1)];
        }

        // --- Envelope verdicts. Each returns null when there is nothing to judge yet. -------

        /// <summary>SC-002: the drive must reach full lock in both directions.</summary>
        public bool ReachedBothSteeringExtremes =>
            _envelope != null
            && MaxSteerRight >= _envelope.steer_abs_max - 0.01f
            && MaxSteerLeft <= -(_envelope.steer_abs_max - 0.01f);

        /// <summary>
        /// FR-005: the 95th-percentile steering change must sit within a factor of two of the
        /// recorded figure. Judged against track1, which is the profile the generated tracks
        /// target (research C8). Track2's band is reported separately for context.
        /// </summary>
        public bool DeltaSteerWithinFactorTwo
        {
            get
            {
                if (_envelope == null || _absDeltaSteer.Count < 30)
                {
                    return false;
                }

                float target = _envelope.dsteer_p95_track1;
                return DeltaSteerP95 >= target / 2f && DeltaSteerP95 <= target * 2f;
            }
        }

        /// <summary>SC-005: no sample may exceed the maximum the dataset recorded.</summary>
        public bool DeltaSteerWithinRecordedMax =>
            _envelope != null && MaxAbsDeltaSteer <= _envelope.dsteer_max + 1e-4f;

        /// <summary>SC-003, expressed the only unit-free way available (FR-004).</summary>
        public bool SpeedShapeMatches
        {
            get
            {
                if (_envelope == null || _speedSamples.Count < 30)
                {
                    return false;
                }

                float ratio = SpeedMaxOverP99;
                float target = _envelope.speed_max_over_p99;
                return ratio > 0f && Mathf.Abs(ratio - target) / target <= 0.10f;
            }
        }
    }
}
