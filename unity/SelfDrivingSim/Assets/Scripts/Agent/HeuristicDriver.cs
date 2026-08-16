using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using SelfDrivingSim.Logging;
using SelfDrivingSim.Track;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// Drives the car from the ray distances alone, with no model and no training
    /// (feature 005, DESIGN 4.7).
    ///
    /// **What it may look at, and why the boundary matters (FR-001).** Only
    /// <see cref="CarAgent.RayDistancesNorm"/> and the car's own speed. Not the track file, not
    /// the checkpoint positions, not the centre line. A baseline that can see more than the thing
    /// it is a baseline for measures nothing, and the whole point of this component is to say what
    /// a simple heuristic achieves before any PPO or BC number is called an achievement.
    ///
    /// The end conditions below do read the checkpoint ring, and that is deliberate and separate:
    /// they decide when a RUN STOPS, never how the car steers. Stopping is the harness's business.
    /// Nothing the ring reports reaches <see cref="Decide"/>.
    ///
    /// **The decision happens in FixedUpdate**, the same clock <see cref="CarAgent"/> senses on
    /// and <see cref="CarController"/> applies forces on, so the control loop itself does not
    /// depend on frame rate.
    ///
    /// **That is not sufficient for FR-011, and research R6 originally claimed it was.**
    /// <see cref="CarController"/> reads the command and integrates the steering rate limit in
    /// <c>Update</c>, against <c>Time.deltaTime</c>. The wheel therefore advances on the frame
    /// clock no matter which clock issued the command, so two runs of the same seed on machines
    /// with different frame rates will not follow the same path. It also explains a measurement
    /// that looked wrong: per-sample steering changes of 0.2865 against a rate limit of 0.0740
    /// per physics step, which is a long frame taking a bigger step.
    ///
    /// Moving that integration is a change to the vehicle, which this feature's declared scope
    /// forbids, so it is measured and recorded here rather than fixed quietly. The trace records
    /// both clocks per row so the effect can be quantified instead of argued about.
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class HeuristicDriver : MonoBehaviour
    {
        /// <summary>Why a run stopped. Written into every run record (FR-010).</summary>
        public enum EndReason
        {
            Running = 0,
            LapComplete,
            TimeLimit,
            WallContact,
            WrongWay,
            FellThrough,
            NoProgress,
        }

        [Header("Controller")]
        [Tooltip("Which steering strategy this run uses. Selectable without a code change so a " +
                 "comparison runs the same build twice rather than two builds once (FR-007).")]
        [SerializeField] private RayControllers.Strategy strategy = RayControllers.Strategy.MostOpen;

        [Tooltip("Off by default. With this disabled the keyboard behaves exactly as it did " +
                 "before this feature existed (FR-003, SC-007).")]
        [SerializeField] private bool engaged;

        [Header("Wiring")]
        [SerializeField] private CarAgent agent;
        [SerializeField] private CarController car;

        [Tooltip("Read only to decide when a run ends, never to decide how to steer.")]
        [SerializeField] private CheckpointRing ring;

        [Tooltip("Read only for the seed the run record has to carry. A row that cannot say " +
                 "which track it was measured on is not a data point.")]
        [SerializeField] private TrackBuilder track;

        [Tooltip("Used by RestartRun to put the car and the checkpoint ring back in agreement. " +
                 "Resetting the two separately desynchronises them, because the ring restarts at " +
                 "marker 0 while the car restarts at whichever marker the placer chose.")]
        [SerializeField] private StartPlacer placer;

        [Tooltip("Reseed the start placer on every restart, so every run of a sweep begins from " +
                 "the same place and the threshold is the only thing that changed. " +
                 "Turn this OFF to measure robustness instead: random starts across many runs " +
                 "answer whether a threshold works from anywhere, which is a different and also " +
                 "useful question. Requires a seed on the StartPlacer either way.")]
        [SerializeField] private bool repeatableStart = true;

        [Header("Run limits")]
        [Tooltip("Laps to complete before the run ends successfully.")]
        [SerializeField] private int lapsToComplete = 1;

        [Tooltip("Seconds before the run is abandoned.\n\n" +
                 "Derived rather than picked: the human laps recorded in T051 came in around " +
                 "34 s, and this driver is not expected to be fast, so three times the human " +
                 "figure with rounding leaves room for a slow but successful lap while still " +
                 "ending a run that is going nowhere. FR-005 needs a defined end state because a " +
                 "sweep that hangs on one seed never finishes.")]
        [SerializeField] private float timeLimitS = 120f;

        [Tooltip("Seconds without a new checkpoint before the run is called stuck. Mirrors the " +
                 "60 s in DESIGN 4.6, so a car wedged against a barrier does not burn the whole " +
                 "time limit.")]
        [SerializeField] private float noProgressLimitS = 60f;

        [Tooltip("End the run on the first wall contact. SC-001 counts a lap only if the car " +
                 "never touched a barrier, so continuing after a contact measures a lap that " +
                 "has already failed.")]
        [SerializeField] private bool endOnWallContact = true;

        /// <summary>
        /// How the raw strategy command is turned into the command actually sent.
        ///
        /// **Exactly one mechanism at a time.** Two of these interact in ways that would be
        /// impossible to attribute afterwards: a delayed command that is also gated fails for two
        /// reasons at once, and the sweep would measure their product. The spec's own rule about
        /// not collapsing measures into one verdict applies here too.
        /// </summary>
        public enum ReactionMode
        {
            /// <summary>Send the strategy's command untouched. The baseline.</summary>
            Immediate = 0,

            /// <summary>Delay it, then optionally low-pass it.</summary>
            Delayed,

            /// <summary>Hold straight until something ahead gets close, then steer.</summary>
            CriticalDistance,
        }

        [Header("Reaction (live, tune while playing)")]
        [Tooltip("Which mechanism shapes the command. Exactly one, never two: a command that is " +
                 "both delayed and gated fails for two reasons at once and the measurement " +
                 "cannot attribute either.")]
        [SerializeField] private ReactionMode reactionMode = ReactionMode.Immediate;
        [Tooltip("Seconds between the rays being read and that decision reaching the wheel.\n\n" +
                 "Zero is the current behaviour. Raising it delays the command through a ring " +
                 "buffer, which models a slower reaction.\n\n" +
                 "MEASURED WARNING: the chain already carries about 0.54 s of lag, because the " +
                 "command saturates at full lock 67 percent of the time and the wheel needs " +
                 "0.54 s to cross from one lock to the other at 3.7 per second. Adding delay on " +
                 "top of that is expected to make it worse. The slider exists so that can be " +
                 "measured rather than argued about.")]
        [Range(0f, 0.5f)]
        [SerializeField] private float reactionTimeS;

        [Tooltip("Low-pass the command before it is sent, in seconds. This is the opposite lever " +
                 "to reaction time: instead of delaying a bang-bang command it turns it into a " +
                 "continuous one, which is what the saturation measurement suggests is actually " +
                 "needed.\n\n" +
                 "Zero disables it and leaves the raw command untouched. Note this makes the " +
                 "controller a tuned system rather than a pure baseline, so a value found here " +
                 "is a measurement to record, not a default to adopt quietly.")]
        [Range(0f, 1f)]
        [SerializeField] private float commandSmoothingS;

        [Tooltip("CriticalDistance mode. Hold straight while the forward cone is clearer than " +
                 "this, and steer only once it closes in. Normalised, so 0.35 means 7 m at the " +
                 "current 20 m ray length.\n\n" +
                 "This attacks the saturation directly. Measured on seed 1004, the argmax command " +
                 "sits at full lock for 67 percent of steps, much of it while the track ahead is " +
                 "wide open, and the wheel needs 0.54 s to cross between locks. Not steering " +
                 "until there is something to steer about should cut that.\n\n" +
                 "Set it too high and the car steers constantly, which is where it is now. Too " +
                 "low and it commits to a wall before reacting. The sweet spot is a measurement.")]
        [Range(0f, 1f)]
        [SerializeField] private float criticalDistanceNorm = 0.35f;

        [Header("Diagnostics")]
        [Tooltip("Write one row per physics step to results/heuristic/trace_<time>.csv.\n\n" +
                 "This exists to prove the chain rays -> argmax -> command -> applied steering, " +
                 "one link at a time. The first run of this driver looked like it was not " +
                 "steering, and the drive log could not settle whether the controller chose a " +
                 "bad command or a good command failed to reach the wheels, because it records " +
                 "the vehicle's actual angle and not the command.")]
        [SerializeField] private bool writeTrace;

        [Tooltip("Append one row per finished run to results/heuristic/runs_<time>.csv, per " +
                 "contracts/run-record.md.\n\n" +
                 "On by default, and on for failures as much as for laps. A sweep that recorded " +
                 "only the runs that finished would report an acceptance rate over a denominator " +
                 "that silently shrank, which is the one error in this file that would look like " +
                 "a result.")]
        [SerializeField] private bool writeRunRecord = true;

        // --- Outcome, read by the sweep runner and the run record ------------------------------

        /// <summary>Whether the driver currently holds the wheel.</summary>
        public bool Engaged => engaged;

        /// <summary>
        /// Whether each run writes its per-step trace. Off for a sweep, on for a distribution run.
        ///
        /// US4 needs the steering COMMAND sample by sample, not the per-run summary the record
        /// carries, because a distribution is the samples. Left off by default because a 34 seed
        /// sweep with it on writes 34 files nobody reads, and the trace exists to explain one run
        /// rather than to accumulate.
        /// </summary>
        public bool WriteTrace
        {
            get => writeTrace;
            set => writeTrace = value;
        }

        /// <summary>Which strategy is in effect.</summary>
        public RayControllers.Strategy ActiveStrategy => strategy;

        /// <summary>Why the run stopped, or <see cref="EndReason.Running"/> while it has not.</summary>
        public EndReason Outcome { get; private set; } = EndReason.Running;

        /// <summary>Simulated seconds since the run began.</summary>
        public float ElapsedS { get; private set; }

        /// <summary>Barrier contacts so far. Zero is what SC-001 requires for a clean lap.</summary>
        public int WallContacts { get; private set; }

        /// <summary>The command last sent to the car, for the HUD and the trace.</summary>
        public float LastSteer { get; private set; }

        /// <summary>The speed the longitudinal rule is currently asking for, in m/s.</summary>
        public float TargetSpeedMs { get; private set; }

        /// <summary>The strategy's own output, before reaction delay or smoothing.</summary>
        public float RawSteer { get; private set; }

        /// <summary>
        /// The two smoothness measures for the run in progress (FR-008, FR-009).
        ///
        /// Fed the command rather than the vehicle's actual angle, and fed on this driver's own
        /// run clock, which is what makes both of T018's measurement traps unreachable rather than
        /// merely avoided. It is only ever fed from <see cref="FixedUpdate"/> while the driver
        /// holds the wheel, so a window that includes a stationary car after the run ended cannot
        /// be produced by getting the analysis wrong later.
        /// </summary>
        public SteerSmoothness Smoothness { get; } = new SteerSmoothness();

        /// <summary>|delta steer| P95 at the compare rate, over this run's command. Never
        /// combined with <see cref="SteerSignChangesPerS"/>.</summary>
        public float SteerDeltaP95 => Smoothness.DeltaSteerP95;

        /// <summary>Direction reversals per second over this run's command.</summary>
        public float SteerSignChangesPerS => Smoothness.SignChangesPerS;

        /// <summary>What most-open would command right now, whether or not it is driving.</summary>
        public float SteerMostOpen { get; private set; }

        /// <summary>What the weighted average would command right now, driving or not.</summary>
        public float SteerWeighted { get; private set; }

        /// <summary>
        /// How far apart the two strategies are on this step.
        ///
        /// Worth watching rather than the two values separately: the interesting moments are the
        /// ones where they disagree, and on a clear straight they agree at zero and say nothing.
        /// The failure that killed most-open on seed 1 was a step where this read close to one
        /// full lock, with the centre ray clear at 20 m and the flank at 1.46 m.
        /// </summary>
        public float StrategyDivergence => Mathf.Abs(SteerMostOpen - SteerWeighted);

        // --- Live knobs, driven by the in-sim panel as well as the Inspector -------------------
        //
        // Exposed as properties rather than left as private serialised fields so the on-screen
        // panel can move them mid-run. Tuning a control loop from the Inspector means looking
        // away from the car at the moment the change takes effect, which is the one moment worth
        // watching.

        /// <summary>Which reaction mechanism is active. Exactly one at a time.</summary>
        public ReactionMode Mode
        {
            get => reactionMode;
            set => reactionMode = value;
        }

        /// <summary>Delay between sensing and steering, seconds. Delayed mode.</summary>
        public float ReactionTimeS
        {
            get => reactionTimeS;
            set => reactionTimeS = Mathf.Clamp(value, 0f, 0.5f);
        }

        /// <summary>Low-pass time constant on the command, seconds. Delayed mode.</summary>
        public float CommandSmoothingS
        {
            get => commandSmoothingS;
            set => commandSmoothingS = Mathf.Clamp(value, 0f, 1f);
        }

        /// <summary>Forward clearance below which steering is allowed. CriticalDistance mode.</summary>
        public float CriticalDistanceNorm
        {
            get => criticalDistanceNorm;
            set => criticalDistanceNorm = Mathf.Clamp01(value);
        }

        /// <summary>Ray range in metres, so the panel can show the threshold in real units.</summary>
        public float RayLengthM => agent != null ? agent.RayLengthM : 20f;

        /// <summary>
        /// Delay and smooth the command, both live-tunable while playing.
        ///
        /// Both default to zero, which is a straight pass-through, so the baseline stays the
        /// baseline unless someone deliberately moves a slider. Anything found by moving them is
        /// a measurement to write down, not a default to adopt: a tuned heuristic stops being a
        /// baseline and the M5 comparison becomes two tuned systems measured against each other.
        ///
        /// The delay is a ring buffer sized from the current physics step, so changing the slider
        /// mid-run takes effect on the next step rather than needing a restart.
        /// </summary>
        private float ApplyReaction(float steer)
        {
            if (reactionMode == ReactionMode.CriticalDistance)
            {
                ForwardClearance = ForwardCone();
                _gateOpen = ForwardClearance <= criticalDistanceNorm;

                // Hold the wheel straight while there is nothing to steer about. Straight is the
                // right neutral here rather than "hold the last command": a car that keeps its
                // last turn while the road opens up spirals, and the whole point of the gate is
                // to stop commanding a turn that the situation does not call for.
                _smoothed = 0f;
                _delay = null;
                return _gateOpen ? Mathf.Clamp(steer, -1f, 1f) : 0f;
            }

            ForwardClearance = ForwardCone();
            _gateOpen = true;

            if (reactionMode != ReactionMode.Delayed)
            {
                _delay = null;
                _smoothed = steer;
                return Mathf.Clamp(steer, -1f, 1f);
            }

            if (reactionTimeS > 1e-4f)
            {
                int wanted = Mathf.Max(1, Mathf.RoundToInt(reactionTimeS / Time.fixedDeltaTime));
                if (_delay == null || _delay.Length != wanted)
                {
                    // Resized live. The buffer is primed with the current command rather than
                    // zero, so moving the slider does not inject a phantom straight-ahead.
                    var resized = new float[wanted];
                    for (int i = 0; i < wanted; i++) { resized[i] = steer; }
                    _delay = resized;
                    _delayAt = 0;
                }

                float delayed = _delay[_delayAt];
                _delay[_delayAt] = steer;
                _delayAt = (_delayAt + 1) % _delay.Length;
                steer = delayed;
            }
            else
            {
                _delay = null;
            }

            if (commandSmoothingS > 1e-4f)
            {
                // First-order lag. alpha is derived from the step and the time constant, so the
                // filter behaves the same at any physics rate.
                float alpha = 1f - Mathf.Exp(-Time.fixedDeltaTime / commandSmoothingS);
                _smoothed = Mathf.Lerp(_smoothed, steer, alpha);
                steer = _smoothed;
            }
            else
            {
                _smoothed = steer;
            }

            return Mathf.Clamp(steer, -1f, 1f);
        }

        private float[] _delay;
        private int _delayAt;
        private float _smoothed;
        private bool _gateOpen = true;

        /// <summary>
        /// How far the car can see through the forward cone, normalised. The gate's input.
        /// </summary>
        public float ForwardClearance { get; private set; }

        /// <summary>Whether the critical-distance gate is currently letting steering through.</summary>
        public bool GateOpen => _gateOpen;

        /// <summary>
        /// The narrowest reading in the cone that carries the cornering decision.
        ///
        /// The cone is the rays within one ray-spacing of dead ahead, which is three rays at the
        /// current thirteen-over-180 fan and stays three if the fan is swept. That width is not
        /// arbitrary: feature 003's T059 found that seven of the thirteen rays report essentially
        /// the same lateral distance in a 6 m corridor while the forward cone carries every
        /// cornering decision, and this gate should trigger on that cone rather than on a
        /// side ray that reads 3 m all lap.
        ///
        /// The minimum rather than the centre ray alone, because a corner arrives off-centre
        /// first, and a gate watching only dead ahead opens later than it should.
        /// </summary>
        private float ForwardCone()
        {
            float spacing = Mathf.Max(agent.RaySpacingDeg, 0.01f);
            float narrowest = 1f;

            for (int i = 0; i < agent.RayCount; i++)
            {
                if (Mathf.Abs(agent.RayAngleDeg(i)) <= spacing + 0.01f)
                {
                    narrowest = Mathf.Min(narrowest, agent.RayDistancesNorm[i]);
                }
            }

            return narrowest;
        }

        private float _lastProgressS;
        private int _lastAwarded;
        private int _lapsAtStart;
        private int _fallResetsAtStart;
        private bool _wasEngaged;
        private float[] _angles = new float[0];
        private StreamWriter _trace;
        private readonly StringBuilder _row = new StringBuilder(256);

        /// <summary>
        /// The real frame delta, captured where it exists.
        ///
        /// <c>Time.deltaTime</c> read inside <c>FixedUpdate</c> returns <c>fixedDeltaTime</c>, not
        /// the frame duration. The first version of this trace logged it from there and produced
        /// a column of constant 0.0200, which looked like a perfectly steady frame rate and was
        /// really just the physics step wearing a disguise. Since <see cref="CarController"/>
        /// integrates the steering rate limit against the frame clock, that column was exactly
        /// the one needed and exactly the one wrong.
        /// </summary>
        private float _frameDeltaTime;
        private int _framesSinceStep;

        private void Update()
        {
            _frameDeltaTime = Time.deltaTime;
            _framesSinceStep++;
        }

        private void Awake()
        {
            if (car == null) { car = GetComponent<CarController>(); }
            if (agent == null) { agent = GetComponentInChildren<CarAgent>(); }
            if (agent == null) { agent = FindAnyObjectByType<CarAgent>(); }
            if (ring == null) { ring = FindAnyObjectByType<CheckpointRing>(); }
            if (placer == null) { placer = FindAnyObjectByType<StartPlacer>(); }
            if (track == null) { track = FindAnyObjectByType<TrackBuilder>(); }
        }

        private void Start()
        {
            // Read in Start rather than Awake because DriveTelemetry loads the envelope in its own
            // Awake, and the order between two components' Awake is not defined. Taking the rate
            // here means it is the exported one, not the fallback, on every run.
            AdoptCompareRate();
            BeginRun();
        }

        /// <summary>
        /// Resample the smoothness measure at the rate the rest of the project compares against.
        ///
        /// The figure only means something beside the human, PPO and BC columns if all four were
        /// resampled to the same rate, and that rate lives in the exported envelope rather than in
        /// any one script. <see cref="DriveTelemetry"/> already loads it, so it is asked rather
        /// than the file being opened a second time. Without a telemetry component in the scene the
        /// class falls back to the dataset's 14.08 Hz and says so, because a run measured at a
        /// silently different rate is worse than one that did not measure.
        /// </summary>
        private void AdoptCompareRate()
        {
            var telemetry = GetComponent<DriveTelemetry>();
            if (telemetry == null) { telemetry = FindAnyObjectByType<DriveTelemetry>(); }

            if (telemetry == null)
            {
                Debug.LogWarning(
                    "[HeuristicDriver] no DriveTelemetry in the scene, so the steering percentile " +
                    $"falls back to {SteerSmoothness.DefaultCompareHz} Hz rather than the rate in " +
                    "vehicle_profile.json. Check the two agree before comparing this run to the " +
                    "human or BC columns.", this);
                return;
            }

            Smoothness.SampleIntervalS = telemetry.SampleIntervalS;
        }

        /// <summary>Restart the run bookkeeping. The sweep calls this between seeds.</summary>
        public void BeginRun()
        {
            Outcome = EndReason.Running;
            ElapsedS = 0f;
            WallContacts = 0;
            Smoothness.Reset();
            _lastProgressS = 0f;
            _lastAwarded = ring != null ? ring.AwardedCount : 0;
            _lapsAtStart = ring != null ? ring.LapCount : 0;
            _fallResetsAtStart = car != null ? car.FallResetCount : 0;
        }

        /// <summary>Take or release the wheel. The sweep and the Inspector both use this.</summary>
        public void SetEngaged(bool value)
        {
            engaged = value;
        }

        /// <summary>
        /// Put the car back on the start line and begin a fresh run, without leaving play mode.
        ///
        /// **This is what makes a sweep possible from inside the simulation.** The tuning panel
        /// is IMGUI, so it only exists while playing, which means a threshold cannot be chosen
        /// before pressing Play. Without this the only way to run a second threshold was to stop,
        /// change a field in the Inspector, and press Play again, which is exactly the workflow
        /// the panel was built to avoid.
        ///
        /// The trace rolls over to a new file. One run per file is what lets the analyser treat
        /// each file as one data point, and a run appended to the previous one would carry two
        /// thresholds and be discarded as varied.
        /// </summary>
        public void RestartRun()
        {
            CloseTrace();

            if (car != null)
            {
                car.ScriptedMove = null;
            }

            // Through StartPlacer, never by resetting the car and the ring separately.
            //
            // The obvious version of this method did exactly that: car.ResetToSpawn() plus
            // ring.ResetProgress(). It is wrong, and wrong in a way that looks like a controller
            // problem. ResetProgress sets NextIndex to 0, while the car spawns at whichever
            // marker the placer chose, 17 on seed 1004. The car then drives into marker 18 while
            // the ring is waiting for marker 0, no gate is ever awarded, and the run dies of
            // NoProgress.
            //
            // It cost a sweep. Threshold 0.35 had completed a clean lap five times from a fresh
            // Play, then reported NoProgress on the first restarted run, which reads as the
            // controller being unreliable rather than the harness being broken. StartPlacer.Place
            // sets the pose and calls ring.StartAt for the same marker, which is the only way the
            // two stay consistent.
            if (placer != null)
            {
                // Reseed first. Place draws from a sequence, so without this each restart begins
                // at a different marker with a different offset and heading, and a sweep varying
                // one threshold per run would be varying the start position alongside it. The
                // first attempt at a threshold sweep did exactly that: three thresholds, three
                // outcomes, none of them attributable.
                if (repeatableStart)
                {
                    placer.ResetRandom();
                }

                placer.Place();
            }
            else
            {
                if (car != null) { car.ResetToSpawn(); }
                if (ring != null) { ring.ResetProgress(); }
                Debug.LogWarning(
                    "[HeuristicDriver] no StartPlacer, so the ring restarts at marker 0 while the " +
                    "car restarts at its spawn. If those differ, no marker will ever be awarded.",
                    this);
            }

            // After the placement, so the lap and marker baselines are taken from the reset state
            // rather than from the run that just ended.
            BeginRun();

            _wasEngaged = false;
            _smoothed = 0f;
            _delay = null;

            Debug.Log(string.Format(CultureInfo.InvariantCulture,
                "[HeuristicDriver] restart: {0}, mode {1}, threshold {2:F3}",
                strategy, reactionMode, criticalDistanceNorm), this);
        }

        /// <summary>Choose the strategy for the next run (FR-007).</summary>
        public void SetStrategy(RayControllers.Strategy value)
        {
            strategy = value;
        }

        private void FixedUpdate()
        {
            // Exactly one source of control is in effect at a time (FR-004). A scripted manoeuvre
            // is a calibration run with a fixed input sequence, and two components writing
            // ScriptedMove would produce a car driven by whichever ran last in the frame order,
            // which is not a thing anyone could reason about.
            var scripted = GetComponent<ScriptedDriver>();
            bool blocked = scripted != null && scripted.IsRunning;

            bool shouldDrive = engaged && !blocked && Outcome == EndReason.Running;

            if (shouldDrive != _wasEngaged)
            {
                Debug.Log(string.Format(CultureInfo.InvariantCulture,
                    "[HeuristicDriver] control -> {0}{1}",
                    shouldDrive ? "heuristic (" + strategy + ")" : "released",
                    blocked ? ", blocked by ScriptedDriver" : string.Empty), this);
                _wasEngaged = shouldDrive;
            }

            if (!shouldDrive)
            {
                // Release rather than hold the last command, so the keyboard takes over instead
                // of the car continuing on a stale input.
                if (car != null && car.ScriptedMove.HasValue && !blocked)
                {
                    car.ScriptedMove = null;
                }

                return;
            }

            ElapsedS += Time.fixedDeltaTime;

            Vector2 move = Decide();
            car.ScriptedMove = move;

            // Measured here, at the one place the command exists, rather than reconstructed from a
            // log afterwards. The command is what FR-008 asks for, and this line runs only while
            // the driver is actually driving, which is the run window and nothing either side.
            Smoothness.Sample(move.x, ElapsedS);

            TraceStep(move);

            CheckEndConditions();
        }

        /// <summary>
        /// One row per physics step, carrying every link in the chain from rays to wheels.
        ///
        /// **Why the drive log is not enough.** `DriveLogger` records `CarController.SteerNorm`,
        /// which is the vehicle's actual rate-limited angle after the fact. That cannot separate
        /// "the controller chose badly" from "the controller chose well and the command did not
        /// arrive", and those need completely different fixes. This records the argmax the
        /// controller saw, the command it issued, and the angle the car ended up at, in the same
        /// row, so each link can be checked independently.
        ///
        /// It also records the two clocks. `CarController` integrates steering in `Update` using
        /// `Time.deltaTime`, while this driver commands in `FixedUpdate`, so the rate limiter
        /// advances on the frame clock and a long frame moves the wheel further. That is worth
        /// measuring rather than arguing about.
        /// </summary>
        private void TraceStep(Vector2 move)
        {
            if (!writeTrace)
            {
                return;
            }

            if (_trace == null)
            {
                OpenTrace();
                if (_trace == null)
                {
                    return;
                }
            }

            // What argmax actually picked, recomputed here rather than trusted, so the row can
            // contradict the command if they ever disagree.
            int argmax = -1;
            float best = float.NegativeInfinity;
            for (int i = 0; i < agent.RayCount; i++)
            {
                if (agent.RayDistancesNorm[i] > best)
                {
                    best = agent.RayDistancesNorm[i];
                    argmax = i;
                }
            }

            float argmaxAngle = argmax >= 0 ? agent.RayAngleDeg(argmax) : 0f;
            float argmaxSteer = Mathf.Clamp(argmaxAngle / car.Profile.steerMaxDeg, -1f, 1f);

            _row.Clear();
            _row.AppendFormat(CultureInfo.InvariantCulture, "{0:F4},{1},{2},",
                ElapsedS,
                track != null && track.Current != null ? track.Current.seed : -1,
                strategy);
            _row.AppendFormat(CultureInfo.InvariantCulture,
                "{0},{1:F1},{2:F4},{3:F4},{4:F4},{5:F4},{6:F3},{7:F3},{8:F3},{9:F5},{10:F5}",
                argmax,            // which ray was longest
                argmaxAngle,       // its angle
                argmaxSteer,       // what argmax alone implies
                move.x,            // what the strategy commanded
                car.SteerNorm,     // what the car is actually at, before this step's Update
                move.y,            // throttle command
                car.SpeedMs,       // forward speed
                TargetSpeedMs,     // what the speed rule asked for
                best,              // the longest normalised distance
                _frameDeltaTime,   // the clock CarController integrates steering on, measured
                Time.fixedDeltaTime);

            // How many rendered frames happened since the previous physics step. Zero means the
            // steering rate limiter did not advance at all between these two rows, which is the
            // shape of the problem when physics outruns rendering.
            _row.AppendFormat(CultureInfo.InvariantCulture, ",{0},{1:F4},{2:F4},{3:F4},{4},{5:F4},{6},{7:F4}",
                              _framesSinceStep, RawSteer, reactionTimeS, commandSmoothingS,
                              reactionMode, ForwardClearance, _gateOpen ? 1 : 0,
                              criticalDistanceNorm);
            _row.AppendFormat(CultureInfo.InvariantCulture, ",{0}", Outcome);
            _framesSinceStep = 0;

            for (int i = 0; i < agent.RayCount; i++)
            {
                _row.AppendFormat(CultureInfo.InvariantCulture, ",{0:F4}",
                                  agent.RayDistancesNorm[i]);
            }

            _trace.WriteLine(_row.ToString());
        }

        private void OpenTrace()
        {
            try
            {
                string dir = RepoPaths.EnsureDir(
                    Path.Combine(RepoPaths.Root, "results", "heuristic"));
                string path = Path.Combine(
                    dir, $"trace_{System.DateTime.Now:yyyy-MM-dd_HH-mm-ss}.csv");

                // Buffered on purpose. The first version flushed every physics step, which is
                // fifty disk writes a second, and the frame rate it cost fed straight back into
                // the steering rate limiter that this trace exists to measure. An instrument that
                // changes its subject is not an instrument.
                _trace = new StreamWriter(path, false, new UTF8Encoding(false), 1 << 16)
                {
                    AutoFlush = false,
                };

                // seed and controller on every row, for the same reason the run record repeats
                // its configuration (SC-006): a trace found on its own must say what produced it.
                // Without them a folder of traces from a sweep is a pile of indistinguishable
                // files, and US4's distribution would be computed over whichever ones happened to
                // be there. They were added when that distribution was first attempted.
                var header = new StringBuilder(
                    "t,seed,controller," +
                    "argmax_index,argmax_angle_deg,argmax_steer,command_steer,applied_steer," +
                    "command_throttle,speed_ms,target_speed_ms,argmax_norm,frame_delta_time," +
                    "fixed_delta_time,frames_since_step,raw_steer,reaction_s,smoothing_s," +
                    "mode,forward_clearance,gate_open,critical_distance,outcome");
                for (int i = 0; i < agent.RayCount; i++)
                {
                    header.AppendFormat(CultureInfo.InvariantCulture, ",ray{0:D2}", i);
                }

                _trace.WriteLine(header.ToString());
                Debug.Log($"[HeuristicDriver] tracing to {path}", this);
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[HeuristicDriver] could not open the trace: {e.Message}", this);
                writeTrace = false;
            }
        }

        private void CloseTrace()
        {
            if (_trace == null)
            {
                return;
            }

            _trace.Flush();
            _trace.Dispose();
            _trace = null;
        }

        private void OnDisable()
        {
            CloseTrace();

            // The run record's handle is static and statics do not survive a domain reload, so
            // without this it would be dropped rather than closed. Every row is flushed as it is
            // written, so nothing is lost either way; this is so the next Play session opens a
            // fresh file instead of inheriting a stale handle.
            RunRecordWriter.Close();
        }

        /// <summary>
        /// The whole control decision: steering from the rays, throttle from the steering.
        ///
        /// Nothing here reads the track, the ring or the clock. Given the same distance array and
        /// the same speed it returns the same command, which is what makes the strategies testable
        /// in isolation and what keeps FR-001 checkable by reading rather than by trusting.
        /// </summary>
        private Vector2 Decide()
        {
            EnsureAngles();

            // Both strategies are evaluated every step, but only the selected one is sent.
            //
            // The other is the teaching instrument: the panel shows what the strategy that is NOT
            // driving would have commanded right now, so the moment they disagree is visible while
            // it happens rather than reconstructed from a trace afterwards. It costs two passes
            // over thirteen floats, which is nothing, and both are pure functions so evaluating
            // the idle one cannot affect the run.
            SteerMostOpen = RayControllers.MostOpen(
                agent.RayDistancesNorm, _angles, car.Profile.steerMaxDeg);
            SteerWeighted = RayControllers.WeightedAverage(
                agent.RayDistancesNorm, _angles, car.Profile.steerMaxDeg);

            float steer = strategy == RayControllers.Strategy.MostOpen
                ? SteerMostOpen
                : SteerWeighted;

            RawSteer = steer;
            steer = ApplyReaction(steer);

            LastSteer = steer;

            // Two limits, and the lower wins.
            //
            // The first is what the corner the car is already turning into can hold. The second
            // is what it can still stop inside of. Taking the minimum is the whole of the
            // anticipation: a car may not enter a corner faster than it can leave it, and it may
            // not travel faster than it can stop within what it can see.
            float corner = TargetSpeedFor(steer, car.Profile);
            float sight = SightLimitedSpeed();
            TargetSpeedMs = Mathf.Min(corner, sight);

            // Throttle is a bang-bang response to the speed error, not a PID. A PID would settle
            // faster and would also introduce three constants that would have to be tuned, and a
            // tuned heuristic stops being a baseline (spec Out of Scope). ScriptedDriver already
            // holds a speed the same crude way for the same reason.
            float speed = car.SpeedMs;
            float throttle;
            if (speed < TargetSpeedMs - 0.25f)
            {
                throttle = 1f;
            }
            else if (speed > TargetSpeedMs + 0.25f)
            {
                throttle = -1f;
            }
            else
            {
                throttle = 0f;
            }

            return new Vector2(steer, throttle);
        }

        /// <summary>
        /// The fastest the car may go while holding the corner its own steering asks for.
        ///
        /// **Longitudinal control is not an extra here, it is the difference between finishing and
        /// not** (research R1). Grip gives about 5.85 m/s^2 laterally, so the tightest corner the
        /// generator produces, 6.97 m, caps cornering at 6.39 m/s against a 10 m/s top speed. The
        /// crossover is 17.1 m: below that radius, full throttle asks for more lateral
        /// acceleration than the tyres can supply, and C9 records that these tracks curve
        /// everywhere. A flat-throttle driver understeers into a barrier on most corners.
        ///
        /// The radius comes from the steering command through the same bicycle model the track
        /// generator used, so the driver and the tracks agree about what a corner costs. Every
        /// constant is read from the profile rather than typed here, which means retuning the car
        /// retunes the driver instead of leaving it calibrated to a vehicle that no longer exists.
        /// </summary>
        private static float TargetSpeedFor(float steerNorm, VehicleProfile profile)
        {
            float abs = Mathf.Abs(steerNorm);

            // Straight ahead has no finite radius, so grip does not limit anything.
            if (abs < 1e-3f)
            {
                return profile.vMaxMs;
            }

            float radius = profile.RadiusForSteering(abs);
            if (radius <= 0f || float.IsInfinity(radius))
            {
                return profile.vMaxMs;
            }

            // brakeMs2 is the measured deceleration, which is the best figure this project has for
            // what the tyres can do. Using it laterally assumes a roughly circular friction
            // budget, which is the standard simplification and is stated rather than hidden.
            float grip = Mathf.Sqrt(profile.brakeMs2 * radius);
            return Mathf.Min(grip, profile.vMaxMs);
        }

        /// <summary>
        /// The fastest the car may go and still stop inside what it can see ahead.
        ///
        /// **Why this was added, and why it was rejected first.** Research R1 chose to derive the
        /// target speed from the steering command alone, and rejected anything reading the forward
        /// distance as "tunable-looking". That rejection was wrong and the measurement says so: on
        /// training seed 1 the car reached a barrier and wedged nose-first against it at every gate
        /// threshold from 0.20 to 0.50, ending each run at zero speed with the wheel at full lock.
        /// A speed derived from the steering command cannot slow a car that has not yet decided to
        /// turn, so the car arrives at the corner already too fast to take it.
        ///
        /// **It is not a tuned constant.** `v = sqrt(2 * a * d)` is the standard stopping relation
        /// rearranged, `a` is the braking figure measured in T024 and read from the profile, and
        /// `d` is the gap the rays already report. The only other quantity is how far the nose sits
        /// ahead of the sensor, which is read from the car's own collider rather than typed in: the
        /// rays start at the car's centre, so a wall touching the bumper still reads as half a car
        /// length of clearance.
        /// </summary>
        private float SightLimitedSpeed()
        {
            float clearanceM = ForwardCone() * agent.RayLengthM - NoseOffsetM();

            if (clearanceM <= 0f)
            {
                return 0f;
            }

            return Mathf.Sqrt(2f * car.Profile.brakeMs2 * clearanceM);
        }

        /// <summary>
        /// How far the nose sits ahead of the ray origin, from the collider rather than a guess.
        ///
        /// The rays start at the car's centre, so the distance they report to a wall the bumper is
        /// already touching is half the car's length, not zero. Measured on this vehicle that is
        /// 2.0 m, which is exactly the 0.100 normalised reading every wedged run ended on.
        /// </summary>
        private float NoseOffsetM()
        {
            if (_noseOffsetM > 0f)
            {
                return _noseOffsetM;
            }

            var box = car.GetComponent<BoxCollider>();
            _noseOffsetM = box != null ? box.size.z * 0.5f : 2.0f;
            return _noseOffsetM;
        }

        private float _noseOffsetM;

        private void EnsureAngles()
        {
            if (_angles.Length == agent.RayCount)
            {
                return;
            }

            _angles = new float[agent.RayCount];
            for (int i = 0; i < _angles.Length; i++)
            {
                _angles[i] = agent.RayAngleDeg(i);
            }
        }

        /// <summary>
        /// Decide whether the run is over (FR-005).
        ///
        /// Every path out of a run ends here, because a sweep that silently drops a seed reports
        /// an acceptance rate over a denominator that quietly shrank.
        /// </summary>
        private void CheckEndConditions()
        {
            if (ring != null && ring.LapCount - _lapsAtStart >= lapsToComplete)
            {
                Finish(EndReason.LapComplete);
                return;
            }

            if (car != null && car.FallResetCount > _fallResetsAtStart)
            {
                Finish(EndReason.FellThrough);
                return;
            }

            if (ring != null && ring.WrongWay)
            {
                // The forward fan cannot tell a car facing backwards that it is: it sees open
                // track and drives confidently the wrong way (research R9). The ring can tell,
                // so it ends the run rather than the driver pretending to notice.
                Finish(EndReason.WrongWay);
                return;
            }

            if (endOnWallContact && WallContacts > 0)
            {
                Finish(EndReason.WallContact);
                return;
            }

            if (ring != null && ring.AwardedCount != _lastAwarded)
            {
                _lastAwarded = ring.AwardedCount;
                _lastProgressS = ElapsedS;
            }

            if (ElapsedS - _lastProgressS >= noProgressLimitS)
            {
                Finish(EndReason.NoProgress);
                return;
            }

            if (ElapsedS >= timeLimitS)
            {
                Finish(EndReason.TimeLimit);
            }
        }

        private void Finish(EndReason reason)
        {
            Outcome = reason;
            car.ScriptedMove = null;

            // One last row carrying the terminal outcome.
            //
            // Without it a trace cannot say whether the run finished a lap or was stopped by
            // hand, and the two are indistinguishable by duration alone. That cost a real
            // measurement: a run-to-run spread computed over ten repeats of one setting read
            // 28.9 s, because four of the ten had been interrupted mid-lap. Over the five that
            // actually ran to the same end it is 0.100 s. A noise floor inflated by a factor of
            // 289 would have buried every difference the sweep exists to find.
            TraceStep(new Vector2(LastSteer, 0f));

            // Flush once, here. Per-step flushing was removed because fifty disk writes a second
            // cost enough frame rate to move the steering rate limiter this trace exists to
            // measure. Flushing once when the run ends costs nothing and means the finished file
            // is complete on disk immediately, rather than holding its last rows, including the
            // outcome, in a buffer until play mode stops.
            _trace?.Flush();

            // Both measures on the summary line, side by side and never combined (FR-009). The n
            // travels with the percentile because a run that ended at five seconds contributes
            // about seventy points, and a percentile over a handful of them is not a measure.
            string line = string.Format(CultureInfo.InvariantCulture,
                "[HeuristicDriver] {0} | {1} | {2:F1}s | contacts {3} | markers {4} | " +
                "dsteer p95 {5:F4} (n {6}) | sign changes {7:F2}/s ({8} in {9:F1}s)",
                strategy, reason, ElapsedS, WallContacts,
                ring != null ? ring.AwardedCount - 0 : -1,
                Smoothness.DeltaSteerP95, Smoothness.SampleCount,
                Smoothness.SignChangesPerS, Smoothness.SignChanges, Smoothness.MeasuredWindowS);

            if (reason == EndReason.LapComplete)
            {
                Debug.Log(line, this);
            }
            else
            {
                Debug.LogWarning(line, this);
            }

            WriteRunRecord(reason);
        }

        /// <summary>
        /// Append this run to the run record (T023, `contracts/run-record.md`).
        ///
        /// Written here rather than by the sweep runner, although the contract names the runner as
        /// the writer. The runner does not exist until T032, and T027 needs three runs of one seed
        /// recorded before anything in Phase 4 or Phase 5 may be interpreted. Putting it at the end
        /// of a run instead means a hand-driven run and a swept run produce the same row through
        /// the same code, which is what the comparison needs anyway: a sweep that recorded runs
        /// differently from the runs it was validated against would measure the difference.
        ///
        /// Every field comes from something that already knows it. Nothing here recomputes a
        /// quantity another component owns, because two answers to "how many checkpoints" is how a
        /// row ends up internally inconsistent and believed anyway.
        /// </summary>
        private void WriteRunRecord(EndReason reason)
        {
            if (!writeRunRecord)
            {
                return;
            }

            if (track == null || track.Current == null)
            {
                Debug.LogError(
                    "[HeuristicDriver] no track loaded, so this run cannot say which seed it was " +
                    "measured on and no row was written. A run record without a seed is not a " +
                    "data point, and writing one anyway would put a hole in the sweep that looks " +
                    "like data.", this);
                return;
            }

            RunRecordWriter.Append(new RunRecord
            {
                Seed = track.Current.seed,
                Controller = strategy.ToString(),

                RayCount = agent != null ? agent.RayCount : 0,
                RayFovDeg = agent != null ? agent.RayFovDeg : 0f,
                RayLengthM = agent != null ? agent.RayLengthM : 0f,

                CompletedLap = reason == EndReason.LapComplete,

                // Negative writes as an empty field. Zero is a lap time, so a failed run must not
                // contribute one: an aggregate that averages zeros reports a fast sweep.
                LapTimeS = reason == EndReason.LapComplete ? ElapsedS : -1f,

                CheckpointsAwarded = ring != null ? ring.AwardedCount : 0,
                CheckpointsTotal = ring != null ? ring.Count : 0,
                CheckpointsSkipped = ring != null ? ring.SkippedContactCount : 0,
                WallContacts = WallContacts,
                EndReason = reason.ToString(),

                // Side by side, never collapsed into one verdict (FR-009).
                SteerP95DSteer = Smoothness.DeltaSteerP95,
                SteerSignChangesPerS = Smoothness.SignChangesPerS,

                TimeScale = Time.timeScale,
                DurationS = ElapsedS,
            });
        }

        /// <summary>
        /// Count barrier contacts, and only barrier contacts.
        ///
        /// The road is under the WheelColliders rather than the body, so the body collider should
        /// only ever meet a barrier. "Should" is not a measurement, so contacts are filtered by
        /// their normal: a wall pushes sideways and the ground pushes up. Counting a kerb strike
        /// or a landing as a wall contact would fail laps that SC-001 should pass.
        /// </summary>
        private void OnCollisionEnter(Collision collision)
        {
            if (!engaged || Outcome != EndReason.Running)
            {
                return;
            }

            for (int i = 0; i < collision.contactCount; i++)
            {
                if (Mathf.Abs(collision.GetContact(i).normal.y) < 0.5f)
                {
                    WallContacts++;
                    return;
                }
            }
        }
    }
}
