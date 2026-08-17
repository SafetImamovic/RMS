using System.Collections.Generic;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// The two smoothness measures a run is judged on (feature 005, FR-008, FR-009, research R3).
    ///
    /// **They are never combined into one number.** Amplitude and frequency are different failures:
    /// a controller can hold a modest 95th percentile while reversing direction constantly, and a
    /// single "smoothness score" would average the two into something that describes neither. The
    /// spec forbids collapsing smoothness and outcome into one verdict, and the same argument
    /// applies inside smoothness itself, so this type exposes two properties and no third.
    ///
    /// **What it is fed, and why that is the whole point.** The command the controller ISSUED, not
    /// <see cref="Vehicle.CarController.SteerNorm"/>, which is the vehicle's actual rate-limited
    /// angle after the fact. T018 measured both on the same run: the command can take three values
    /// on the stated fan, and the logged actual angle took 43. FR-008 asks for the command, and a
    /// P95 computed on the actual angle measures the rate limiter rather than the controller.
    ///
    /// **It is fed on the run clock**, so it starts when the driver takes the wheel and stops when
    /// the run ends. The same T018 trace ran to 37.4 s against a run that ended at 5.2 s, because
    /// `DriveLogger` keeps recording after control is released; every statistic over that file was
    /// diluted by 32 s of a stationary car. Here the window cannot include what the driver did not
    /// drive, because nothing outside it is ever sampled.
    ///
    /// Deliberately free of Unity types beyond none at all, so the arithmetic the US2 comparison
    /// rests on is reachable from an EditMode test in milliseconds (Constitution Principle VIII).
    /// </summary>
    public sealed class SteerSmoothness
    {
        /// <summary>
        /// The dataset's own frame rate, and the rate feature 002 and 004 both report against.
        ///
        /// Used only as the fallback. The live value comes from the exported envelope through
        /// <see cref="Logging.DriveTelemetry.SampleIntervalS"/>, so all four columns of the M5
        /// comparison are resampled to one rate rather than to one rate and a copy of it.
        /// </summary>
        public const float DefaultCompareHz = 14.08f;

        /// <summary>
        /// Below this magnitude the command counts as "no direction" rather than as a side.
        ///
        /// <see cref="RayControllers.WeightedAverage"/> is continuous and settles near zero on a
        /// symmetric reading, where floating-point noise alone changes the sign several times a
        /// second. Counting that as chatter would report the noise floor as a behaviour. The same
        /// 1e-3 is what <c>HeuristicDriver</c> treats as straight ahead when it derives a corner
        /// radius, so the two agree about what "not turning" means.
        /// </summary>
        public const float SignEpsilon = 1e-3f;

        private readonly List<float> _absDeltaSteer = new List<float>(2048);

        private float _sampleIntervalS = 1f / DefaultCompareHz;
        private float _nextSampleTimeS;
        private float _lastSampledSteer;
        private bool _hasFirstSample;

        private float _firstTimeS;
        private float _lastTimeS;
        private bool _hasWindow;

        private int _signChanges;
        private int _lastSign;

        /// <summary>
        /// Seconds between resampled points. Setting it discards the run in progress, because a
        /// series half at one rate and half at another is not a series.
        /// </summary>
        public float SampleIntervalS
        {
            get => _sampleIntervalS;
            set
            {
                float wanted = value > 1e-5f ? value : 1f / DefaultCompareHz;
                if (wanted == _sampleIntervalS)
                {
                    return;
                }

                _sampleIntervalS = wanted;
                Reset();
            }
        }

        /// <summary>How many resampled points the P95 was computed over. A run that ended early
        /// has few, and a percentile over a handful of points is a number rather than a measure,
        /// so the count travels with it.</summary>
        public int SampleCount => _absDeltaSteer.Count;

        /// <summary>Direction reversals counted so far.</summary>
        public int SignChanges => _signChanges;

        /// <summary>Seconds between the first and last command this saw. The denominator.</summary>
        public float MeasuredWindowS => _hasWindow ? _lastTimeS - _firstTimeS : 0f;

        /// <summary>
        /// 95th percentile of |delta steer| between consecutive points at the compare rate.
        ///
        /// Nearest-rank, matching <see cref="Logging.DriveTelemetry"/> exactly, because this figure
        /// is put beside the human, PPO and BC columns and two percentile conventions would make a
        /// difference of a rank look like a difference of driving.
        /// </summary>
        public float DeltaSteerP95 => NearestRankPercentile(_absDeltaSteer, 95f);

        /// <summary>
        /// Direction reversals per second. What chatter actually is (research R3).
        ///
        /// **Counted at the rate it is fed, not at the compare rate.** The P95 is resampled to
        /// 14.08 Hz because it is compared against a figure measured there; this is not compared
        /// against anything, and downsampling it would throw away every reversal faster than the
        /// 7.04 Hz that rate can represent. Fed from <c>FixedUpdate</c> it is also independent of
        /// frame rate, which the resampled measure is only approximately.
        /// </summary>
        public float SignChangesPerS
        {
            get
            {
                float window = MeasuredWindowS;
                return window > 1e-4f ? _signChanges / window : 0f;
            }
        }

        /// <summary>Begin a fresh run. Called wherever the driver's own bookkeeping resets.</summary>
        public void Reset()
        {
            _absDeltaSteer.Clear();
            _nextSampleTimeS = 0f;
            _lastSampledSteer = 0f;
            _hasFirstSample = false;
            _firstTimeS = 0f;
            _lastTimeS = 0f;
            _hasWindow = false;
            _signChanges = 0;
            _lastSign = 0;
        }

        /// <summary>
        /// Offer one command, at one instant of the run clock. Call every physics step.
        ///
        /// Both measures are updated from the same call so they cannot end up covering different
        /// windows, which is the failure that would make them disagree about the same run.
        /// </summary>
        /// <param name="commandSteer">What the controller issued, in [-1, 1].</param>
        /// <param name="runTimeS">Seconds since the driver took the wheel, not since startup.</param>
        public void Sample(float commandSteer, float runTimeS)
        {
            if (!_hasWindow)
            {
                _firstTimeS = runTimeS;
                _hasWindow = true;
            }

            _lastTimeS = runTimeS;

            CountSign(commandSteer);

            if (runTimeS < _nextSampleTimeS)
            {
                return;
            }

            if (_hasFirstSample)
            {
                float delta = commandSteer - _lastSampledSteer;
                _absDeltaSteer.Add(delta < 0f ? -delta : delta);
            }

            _lastSampledSteer = commandSteer;
            _hasFirstSample = true;

            // Advance the schedule rather than restarting it from now, so the series does not drift
            // late by a fraction of a physics step every point. The loop catches up after a hitch
            // without emitting duplicate points: a stalled frame should cost samples, not invent
            // ones that read as zero change and pull the percentile down.
            do
            {
                _nextSampleTimeS += _sampleIntervalS;
            }
            while (_nextSampleTimeS <= runTimeS);
        }

        /// <summary>
        /// Count a reversal, treating the deadband as "no direction" rather than as a side.
        ///
        /// A genuine reversal passes through zero, so the last non-zero side is remembered across
        /// the deadband: left, straight, right is one change, while left, straight, left is none.
        /// Resetting on every zero would count a car easing out of a turn and back into it as a
        /// reversal, which is the opposite of chatter.
        /// </summary>
        private void CountSign(float commandSteer)
        {
            int sign = commandSteer > SignEpsilon ? 1
                     : commandSteer < -SignEpsilon ? -1
                     : 0;

            if (sign == 0)
            {
                return;
            }

            if (_lastSign != 0 && sign != _lastSign)
            {
                _signChanges++;
            }

            _lastSign = sign;
        }

        /// <summary>
        /// Nearest-rank percentile, the one convention this project uses.
        ///
        /// Public and static so <see cref="Logging.DriveTelemetry"/> calls this rather than keeping
        /// its own copy. Its own class comment warns that a HUD computing its own version of the
        /// steering-change percentile could show green while the log showed red; two copies of this
        /// method is exactly how that happens.
        /// </summary>
        public static float NearestRankPercentile(IReadOnlyList<float> values, float percentile)
        {
            if (values == null || values.Count == 0)
            {
                return 0f;
            }

            var sorted = new List<float>(values);
            sorted.Sort();

            int rank = (int)System.Math.Ceiling(percentile / 100f * sorted.Count) - 1;
            if (rank < 0) { rank = 0; }
            if (rank >= sorted.Count) { rank = sorted.Count - 1; }

            return sorted[rank];
        }
    }
}
