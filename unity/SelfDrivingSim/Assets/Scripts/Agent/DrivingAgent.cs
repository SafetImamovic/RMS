using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using Unity.MLAgents.Sensors;
using UnityEngine;
using SelfDrivingSim.Logging;
using SelfDrivingSim.Track;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// The learned driver (feature 006, M3): the observation vector the scripted driver reads,
    /// the reward table `DESIGN.md` 4.5 fixed, and an episode that ends for one recorded reason.
    ///
    /// **It wraps <see cref="CarAgent"/> rather than replacing it.** `CarAgent` is the sensing for
    /// all three drivers and stays a plain MonoBehaviour, which is what lets a scene play the
    /// scripted driver without carrying an agent that requests decisions from nothing. The comment
    /// at the top of that class said M3 would wrap it; this is that.
    ///
    /// **It steers through <c>CarController.ScriptedMove</c>**, the same field
    /// <see cref="HeuristicDriver"/> writes. Human, scripted and learned all reach the wheels
    /// through one path, so a difference in the M5 comparison is a difference in policy rather
    /// than in plumbing (FR-003).
    ///
    /// It also implements <see cref="IRunDriver"/>, so the evaluation in US2 runs through feature
    /// 005's sweep runner and the two columns come out of one piece of code (FR-023).
    /// </summary>
    [RequireComponent(typeof(BehaviorParameters))]
    public class DrivingAgent : Unity.MLAgents.Agent, IRunDriver
    {
        [Header("Wiring")]
        [SerializeField] private CarAgent sensing;
        [SerializeField] private CarController car;
        [SerializeField] private CheckpointRing ring;
        [SerializeField] private StartPlacer placer;
        [SerializeField] private WallSensor wall;

        [Tooltip("Only needed by the evaluation sweep, which records which seed a row was " +
                 "measured on. Training never reads it, because the area owns the track there.")]
        [SerializeField] private TrackBuilder track;

        [Header("Evaluation (US2, FR-023)")]
        [Tooltip("Hand episode control to SweepRunner and write a RunRecord row per run (FR-023). " +
                 "OFF by default, and that default is load-bearing rather than cautious. It " +
                 "changes two things at once, and they belong together. " +
                 "First, output: training runs twelve areas for millions of steps and calls " +
                 "ReportEpisode on roughly five thousand episodes a run, so writing a sweep row " +
                 "for each would produce a file nothing asked for and mix training episodes into " +
                 "the evaluation CSV. " +
                 "Second, and less obvious, who owns the restart: in training the agent restarts " +
                 "itself, because ML-Agents wants episodes back to back. IRunDriver promises the " +
                 "opposite - a run ends and RunActive STAYS false until the runner calls " +
                 "RestartRun. Left self-restarting, the sweep never observes a run finishing, so " +
                 "it never advances the seed and the agent drives the first track forever while " +
                 "writing a row each time. Measured before the fix: ten rows, all seed 1001, with " +
                 "RunsDone still zero.")]
        [SerializeField] private bool evaluationMode;

        [Tooltip("What goes in the run record's controller column. " +
                 "The scripted driver writes its strategy there, because that is what varies " +
                 "between its runs. A learned policy has no strategy; what varies between its runs " +
                 "is which training run produced the weights, so the run id goes here and a row " +
                 "stays self-describing (SC-006). Set it to the run id whose .onnx is on " +
                 "BehaviorParameters, and nothing checks the two agree, so they are worth checking " +
                 "by eye.")]
        [SerializeField] private string runId = "";

        [Tooltip("Per-step trace for the M5 steering comparison, one file per run. " +
                 "Optional: leave empty and the sweep still records its RunRecord rows. " +
                 "It is driven per run rather than left to its own OnEnable, which would write " +
                 "one file for the whole Play session. That file would be a single monotonic t " +
                 "spanning ten runs with no way to find the seams, and differencing across a seam " +
                 "invents a steering jump no driver made. `python/rl/report.py` takes a directory " +
                 "of traces for exactly this reason.")]
        [SerializeField] private DriveLogger trace;

        [Header("Episode (DESIGN 4.6)")]
        [Tooltip("Laps that count as success. DESIGN 4.6 says three.")]
        [SerializeField] private int lapsToComplete = 3;

        [Tooltip("Seconds without reaching a new marker before the episode is cut as stalled.\n\n" +
                 "DESIGN 4.6, fixed during M2. It catches a policy that stopped making progress, " +
                 "which is a different question from the total step cap catching one that is " +
                 "merely slow.")]
        [SerializeField] private float stallSeconds = 60f;

        /// <summary>Why the last episode ended. Recorded, and distinct per reason (FR-011).</summary>
        public enum EndReason
        {
            Running = 0,
            WallContact,
            LapsCompleted,
            Stalled,
            StepLimit,

            /// <summary>
            /// The area put a different track under the car and cut the episode short.
            ///
            /// Not a policy outcome, and it is here so the accounting closes rather than to be read
            /// as one. The trainer counts a swap-ended episode in `Environment/Cumulative Reward`
            /// like any other, so leaving it out of the breakdown made the two disagree: see the
            /// FR-008 note in `results/EXPERIMENTS.md` for the 0.69 that cost.
            /// </summary>
            TrackSwapped,
        }

        /// <summary>Why the episode that just ended, ended.</summary>
        public EndReason Outcome { get; private set; } = EndReason.Running;

        /// <summary>Seconds of simulated time in the current episode, for the run record.</summary>
        public float ElapsedS { get; private set; }

        /// <summary>
        /// Barrier contacts in the current episode.
        ///
        /// Read from <see cref="WallSensor"/> rather than counted again here, for the reason the
        /// scripted driver's record gives: two answers to the same question is how a row ends up
        /// internally inconsistent and believed anyway.
        /// </summary>
        public int WallContacts => wall != null ? wall.Contacts : 0;

        /// <summary>
        /// The two smoothness measures, kept apart (FR-009).
        ///
        /// Sampled at <see cref="SteerSmoothness.DefaultCompareHz"/> rather than from a
        /// <c>DriveTelemetry</c>, which the training prefab does not carry. That is the same rate
        /// the scripted and imitation columns were measured at, which is the condition under which
        /// M5 can put the columns beside each other at all.
        /// </summary>
        public SteerSmoothness Smoothness { get; } = new SteerSmoothness();

        /// <summary>What the last episode's return was made of (FR-008).</summary>
        public RewardModel.Breakdown Reward => _reward;

        // --- IRunDriver, for the evaluation sweep (FR-023) -------------------------------------

        /// <inheritdoc />
        public bool RunActive => _runActive;

        /// <inheritdoc />
        public void RestartRun()
        {
            // A request rather than a direct arm, because EndEpisode runs OnEpisodeBegin
            // synchronously and that callback is what decides whether the run is live.
            _restartRequested = true;
            EndEpisode();
        }

        /// <inheritdoc />
        public void SetEngaged(bool value)
        {
            _engaged = value;

            if (!value && car != null)
            {
                // Hand the car back rather than leaving the last command latched. A stale
                // ScriptedMove would keep the wheels turned while the runner swaps the track.
                car.ScriptedMove = null;
            }
        }

        private RewardModel.Breakdown _reward;
        private bool _engaged = true;
        private bool _runActive;
        private bool _restartRequested;
        private int _awardedLast;
        private bool _wrongWayLast;
        private float _steerLast;
        private int _stepsSinceAward;

        private int StallSteps => Mathf.Max(1, Mathf.RoundToInt(stallSeconds / Time.fixedDeltaTime));

        private void Awake()
        {
            if (sensing == null) { sensing = GetComponent<CarAgent>() ?? GetComponentInChildren<CarAgent>(true); }
            if (car == null) { car = GetComponent<CarController>() ?? GetComponentInChildren<CarController>(true); }
            if (ring == null) { ring = GetComponentInParent<CheckpointRing>(); }
            if (placer == null) { placer = GetComponentInParent<StartPlacer>(); }
            if (wall == null) { wall = GetComponent<WallSensor>() ?? GetComponentInChildren<WallSensor>(true); }
            if (track == null) { track = GetComponentInParent<TrackBuilder>(true); }
            if (track == null) { track = FindAnyObjectByType<TrackBuilder>(FindObjectsInactive.Include); }

            AssertObservationSize();
        }

        /// <summary>
        /// Refuse to train against a vector the trainer has the wrong shape for (FR-004).
        ///
        /// **This is the failure that does not announce itself.** If the behaviour is configured
        /// for a different vector size than the scene produces, ML-Agents pads or truncates and
        /// training proceeds against partly meaningless numbers. The reward curve still rises,
        /// because the policy learns whatever it was actually shown, and nothing in the run says
        /// the observation was wrong. Cheaper to stop here.
        /// </summary>
        private void AssertObservationSize()
        {
            if (sensing == null)
            {
                Debug.LogError("[DrivingAgent] no CarAgent to observe through.", this);
                return;
            }

            var parameters = GetComponent<BehaviorParameters>();
            int configured = parameters.BrainParameters.VectorObservationSize;

            if (configured != sensing.ObservationCount)
            {
                Debug.LogError(
                    $"[DrivingAgent] behaviour '{parameters.BehaviorName}' is configured for " +
                    $"{configured} observations but CarAgent produces {sensing.ObservationCount} " +
                    $"({sensing.RayCount} rays plus {CarAgent.SelfStateCount} self-state). " +
                    "Fix the behaviour rather than the sensing: the ray count is frozen for this " +
                    "feature and every recorded baseline depends on it.", this);
            }
        }

        /// <summary>
        /// Feed the network exactly what the scripted driver reads, in the declared order.
        ///
        /// Nothing is added here, and that is the requirement rather than an omission (FR-001,
        /// FR-002). A learned driver that could see the track file, the marker positions or its own
        /// place on the loop would not be comparable to the driver it is measured against.
        /// </summary>
        public override void CollectObservations(VectorSensor sensor)
        {
            if (sensing == null)
            {
                return;
            }

            var observations = sensing.Observations;
            for (int i = 0; i < observations.Count; i++)
            {
                sensor.AddObservation(observations[i]);
            }
        }

        /// <summary>
        /// Place the car, clear the counters, and start the episode from a position the policy has
        /// not seen before (FR-010).
        ///
        /// **The reset goes through <see cref="StartPlacer"/> and nowhere else.** Feature 005 lost
        /// a sweep to the obvious alternative: resetting the car and calling
        /// <c>ring.ResetProgress()</c> separately leaves the ring waiting for marker 0 while the
        /// car stands at marker 17, no gate is ever awarded, and the run dies looking like a
        /// controller fault. <c>Place</c> sets the pose and calls <c>StartAt</c> for the same
        /// marker, which is the only way the two agree.
        ///
        /// The random sequence is deliberately **not** reseeded. A sweep reseeds so that runs
        /// repeat; training wants the opposite, because a policy that always begins at the same
        /// marker learns the order of one track's corners rather than how to drive.
        /// </summary>
        public override void OnEpisodeBegin()
        {
            if (placer != null)
            {
                placer.Place();
            }
            else
            {
                Debug.LogWarning(
                    "[DrivingAgent] no StartPlacer, so the car and the ring restart independently " +
                    "and no marker will be awarded if they disagree.", this);
            }

            if (wall != null)
            {
                wall.ResetCount();
            }

            if (car != null)
            {
                car.ScriptedMove = null;
            }

            // In training the agent arms itself, because the trainer wants episodes back to
            // back. Under a sweep it must not: IRunDriver promises the run stays over until the
            // runner asks for the next one.
            _runActive = !evaluationMode || _restartRequested;
            _restartRequested = false;

            // Only for a run the sweep asked for. In evaluation mode ML-Agents still cycles
            // episodes between runs, and opening a trace for those would fill the directory with
            // files for drives that never happened.
            if (evaluationMode && _runActive && trace != null)
            {
                trace.BeginRun();
            }

            _reward = default;
            ElapsedS = 0f;
            Smoothness.Reset();
            _awardedLast = ring != null ? ring.AwardedCount : 0;
            _wrongWayLast = ring != null && ring.WrongWay;
            _steerLast = 0f;
            _stepsSinceAward = 0;
            Outcome = EndReason.Running;
        }

        /// <summary>
        /// Apply the action, price the step, and decide whether the episode is over.
        ///
        /// Called on every academy step, not only on decision steps, because the decision requester
        /// repeats the last action in between. That is what makes the steering-change term correct
        /// without any bookkeeping: on a repeated step the action is identical, so the delta is
        /// zero, and the only non-zero deltas are the ones between actual decisions (research R2).
        /// </summary>
        public override void OnActionReceived(ActionBuffers actions)
        {
            // Unbounded in principle. One large value would otherwise arrive at the wheels as a
            // full-lock command, which is a control input no policy chose.
            float steer = Mathf.Clamp(actions.ContinuousActions[0], -1f, 1f);
            float throttle = Mathf.Clamp(actions.ContinuousActions[1], -1f, 1f);

            if (_engaged && car != null)
            {
                car.ScriptedMove = new Vector2(steer, throttle);
            }

            AccrueStepTerms(steer);
            AccrueEventTerms();
            CheckTermination();

            _steerLast = steer;
        }

        /// <summary>The terms that are paid every step: existing, moving, and changing the wheel.</summary>
        private void AccrueStepTerms(float steer)
        {
            float step = RewardModel.Step();
            float speed = RewardModel.Speed(sensing != null ? sensing.SpeedForwardNorm : 0f);
            float jerk = RewardModel.Jerk(steer - _steerLast);

            _reward.StepCostTotal += step;
            _reward.ForwardSpeed += speed;
            _reward.SteeringJerk += jerk;

            // Here rather than in FixedUpdate, so the clock and the steering samples advance on
            // exactly the ticks the reward terms are charged on. Two different notions of "a step"
            // in one component is how the episode-length discrepancy in T050 got in.
            ElapsedS += Time.fixedDeltaTime;
            Smoothness.Sample(steer, ElapsedS);

            AddReward(step + speed + jerk);
            _stepsSinceAward++;
        }

        /// <summary>
        /// The terms that are paid on something happening: a marker taken, or the loop entered
        /// backwards.
        ///
        /// Both are read from <see cref="CheckpointRing"/> rather than recomputed, because FR-009
        /// asks for the ring's own detection and a second definition of direction would be a second
        /// thing to keep in agreement. Wrong way is charged on the transition: the flag latches, and
        /// charging it per step would fine one mistake for as long as it lasted.
        /// </summary>
        private void AccrueEventTerms()
        {
            if (ring == null)
            {
                return;
            }

            int awarded = ring.AwardedCount;
            if (awarded > _awardedLast)
            {
                float progress = RewardModel.Checkpoints(awarded - _awardedLast);
                _reward.CheckpointProgress += progress;
                AddReward(progress);
                _stepsSinceAward = 0;
            }

            _awardedLast = awarded;

            bool wrongWay = ring.WrongWay;
            if (wrongWay && !_wrongWayLast)
            {
                float penalty = RewardModel.WrongWay(true);
                _reward.WrongDirection += penalty;
                AddReward(penalty);
            }

            _wrongWayLast = wrongWay;
        }

        /// <summary>
        /// End the episode for exactly one reason, and distinguish the terminal ones from the
        /// truncations (FR-011, DESIGN 4.6).
        ///
        /// **The distinction is not bookkeeping.** The trainer bootstraps the value of a truncated
        /// episode from its final observation, and treats a terminal one as worth nothing beyond
        /// it. Ending a time-limited episode as though the car had crashed would teach the policy
        /// that lasting the full time is punished, which is the opposite of what the step limit is
        /// there for.
        /// </summary>
        private void CheckTermination()
        {
            // Between runs the sweep owns the car and the agent is still being stepped. Ending an
            // episode here would write a row for a run nobody asked for, against whichever seed
            // happened to be loaded.
            if (evaluationMode && !_runActive)
            {
                return;
            }

            if (wall != null && wall.TakeNewContact())
            {
                float penalty = RewardModel.Wall(true);
                _reward.WallContact += penalty;

                // Before EndEpisode, never after: the penalty has to land in the episode the
                // trainer attributes it to.
                AddReward(penalty);
                Finish(EndReason.WallContact);
                return;
            }

            if (ring != null && lapsToComplete > 0 && ring.LapCount >= lapsToComplete)
            {
                Finish(EndReason.LapsCompleted);
                return;
            }

            if (_stepsSinceAward >= StallSteps)
            {
                Finish(EndReason.Stalled);
                return;
            }

            if (StepCount + 1 >= MaxStep && MaxStep > 0)
            {
                // Recorded rather than left to the framework, so the end-reason distribution can
                // tell "slow" from "stuck". ML-Agents performs the truncation itself.
                Outcome = EndReason.StepLimit;
                _runActive = false;
                ReportEpisode();
            }
        }

        private void Finish(EndReason reason)
        {
            Outcome = reason;
            _runActive = false;
            ReportEpisode();

            if (reason == EndReason.Stalled)
            {
                // A truncation, not a failure of the policy's own making.
                EpisodeInterrupted();
                return;
            }

            EndEpisode();
        }

        /// <summary>
        /// Report each reward term separately to the trainer (FR-008).
        ///
        /// **A total that rises does not say which term raised it.** The failure this exists to
        /// expose is a policy collecting the speed and step terms without making progress: the
        /// cumulative reward moves, `reward/checkpoint` stays flat, and nothing else in the run
        /// distinguishes that from learning to drive.
        /// </summary>
        private void ReportEpisode()
        {
            StatsRecorder stats = Academy.Instance.StatsRecorder;

            stats.Add("reward/checkpoint", _reward.CheckpointProgress);
            stats.Add("reward/wrong_way", _reward.WrongDirection);
            stats.Add("reward/wall", _reward.WallContact);
            stats.Add("reward/step", _reward.StepCostTotal);
            stats.Add("reward/speed", _reward.ForwardSpeed);
            stats.Add("reward/jerk", _reward.SteeringJerk);

            // Summed, not averaged. The default aggregation takes the mean, and the mean of a
            // value that is always 1.0 is 1.0 however often it was written: `ppo_car_v01` reported
            // exactly 1.0000 for both reasons that occurred over 5M steps and carried no
            // information about how often either happened. Summing makes the series a count, which
            // is what a distribution needs and what T036 asked for.
            stats.Add(
                "episode/end_" + Outcome.ToString().ToLowerInvariant(),
                1f,
                StatAggregationMethod.Sum);

            WriteRunRecord();
        }

        /// <summary>
        /// The evaluation row for the episode that just ended (FR-023, US2).
        ///
        /// **The same struct the scripted driver writes**, so a learned row and a scripted row load
        /// through one `pandas` call with no branch on driver type. That is T044's check, and it is
        /// the whole point of `RunRecord` being a shared type rather than a per-driver format.
        ///
        /// Called from <see cref="ReportEpisode"/> because every end path already funnels through
        /// there. A second write site would be a second place for the two to drift apart, which is
        /// how the FR-008 residual got in when a swap-ended episode bypassed this method.
        /// </summary>
        private void WriteRunRecord()
        {
            if (!evaluationMode)
            {
                return;
            }

            // Closed before the row is written, so a reader that finds the row can rely on the
            // trace beside it being complete rather than still buffered.
            if (trace != null)
            {
                trace.EndRun();
            }

            // Set before the first Append, which is what RunRecordWriter.Folder requires: the file
            // opens lazily and is never reopened, so this has to happen ahead of any row rather
            // than in a one-time setup that might run after one.
            RunRecordWriter.Folder = "rl";

            if (track == null || track.Current == null)
            {
                Debug.LogError(
                    "[DrivingAgent] no track loaded, so this run cannot say which seed it was " +
                    "measured on and no row was written. A run record without a seed is not a " +
                    "data point, and writing one anyway would put a hole in the sweep that looks " +
                    "like data.", this);
                return;
            }

            RunRecordWriter.Append(new RunRecord
            {
                Seed = track.Current.seed,

                // The run id, not a strategy. A learned policy has none, and what distinguishes
                // one of its runs from another is which training run produced the weights.
                Controller = string.IsNullOrEmpty(runId) ? "(unset)" : runId,

                RayCount = sensing != null ? sensing.RayCount : 0,
                RayFovDeg = sensing != null ? sensing.RayFovDeg : 0f,
                RayLengthM = sensing != null ? sensing.RayLengthM : 0f,

                CompletedLap = Outcome == EndReason.LapsCompleted,

                // Negative writes as an empty field. Zero is a lap time, so a failed run must not
                // contribute one: an aggregate that averages zeros reports a fast sweep.
                LapTimeS = Outcome == EndReason.LapsCompleted ? ElapsedS : -1f,

                CheckpointsAwarded = ring != null ? ring.AwardedCount : 0,
                CheckpointsTotal = ring != null ? ring.Count : 0,
                CheckpointsSkipped = ring != null ? ring.SkippedContactCount : 0,
                WallContacts = WallContacts,
                EndReason = Outcome.ToString(),

                // Side by side, never collapsed into one verdict (FR-009).
                SteerP95DSteer = Smoothness.DeltaSteerP95,
                SteerSignChangesPerS = Smoothness.SignChangesPerS,

                TimeScale = Time.timeScale,
                DurationS = ElapsedS,
            });
        }

        /// <summary>
        /// End the episode because the area is changing track under the car (<see cref="EndReason.TrackSwapped"/>).
        ///
        /// The area owns the swap, so it owns this call. What it must not do is end the episode
        /// itself: the trainer counts every episode that ends, and one ended without passing
        /// through here is in the cumulative reward while its six terms are missing from the
        /// breakdown, which is how the FR-008 residual got in.
        ///
        /// It is <c>EpisodeInterrupted</c> rather than <c>EndEpisode</c> because the episode was
        /// cut by the environment rather than finished by the policy, and the trainer bootstraps
        /// the value of a truncated episode instead of treating the return as complete.
        /// </summary>
        public void EndForTrackSwap()
        {
            Outcome = EndReason.TrackSwapped;
            _runActive = false;
            ReportEpisode();
            EpisodeInterrupted();
        }

        /// <summary>
        /// Hold still when no policy is driving.
        ///
        /// Heuristic mode here means "no decision source", not "the scripted driver". The scripted
        /// driver is <see cref="HeuristicDriver"/> and it has its own component; duplicating it
        /// into this callback would put two implementations of the baseline in the project, and the
        /// M5 comparison would have no single answer to which one produced a figure.
        /// </summary>
        public override void Heuristic(in ActionBuffers actionsOut)
        {
            var continuous = actionsOut.ContinuousActions;
            for (int i = 0; i < continuous.Length; i++)
            {
                continuous[i] = 0f;
            }
        }
    }
}
