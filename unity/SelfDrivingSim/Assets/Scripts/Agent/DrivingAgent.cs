using System.Collections.Generic;
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

        [Tooltip("A CROSS-CHECK, no longer the source. The run record's controller column is " +
                 "derived from the model actually loaded on BehaviorParameters and the inference " +
                 "mode actually in effect, so a row can prove which weights drove it. " +
                 "Set this to the run id you believe is loaded and the agent will contradict you " +
                 "in the console if it is not. Leave it empty and nothing is checked. Either way " +
                 "the recorded label comes from the policy, not from this field (feature 011).")]
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

        [Tooltip("How many barrier contacts an episode survives before the episode ends. " +
                 "Zero reproduces feature 007 exactly: the first contact ends the episode. " +
                 "It counts contact EVENTS, not steps and not seconds, because WallSensor " +
                 "raises OnCollisionEnter once when the colliders begin touching and not " +
                 "again until they separate, so a car that slides along a barrier without " +
                 "separating spends one unit of budget on the whole slide.\n\n" +
                 "Default is ZERO because feature 008 measured a budget of 3 and did not keep " +
                 "it: ppo_car_008_budget reached 0.5297 markers per episode against 1.4987, " +
                 "completed no lap, and its stall share rose from 27.4 to 53.8 per cent. " +
                 "Lifting the terminal did not teach recovery, it handed the policy back the " +
                 "option of driving less. The field stays so the experiment can be repeated " +
                 "without a code change; the default records the outcome.")]
        [SerializeField] private int wallContactBudget = 0;

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

        /// <summary>
        /// How far round the lap the car may claim, and what a metre of it is worth (feature 007).
        ///
        /// Owned here rather than on the ring, because it is reward input and the ring is
        /// deliberately free of reward logic.
        /// </summary>
        private readonly TrackProgress _progress = new TrackProgress();

        /// <summary>Reused so re-reading the chain each episode does not allocate.</summary>
        private readonly List<Vector3> _chain = new List<Vector3>();

        private bool _engaged = true;
        private bool _runActive;
        private bool _restartRequested;
        private int _awardedLast;
        private bool _wrongWayLast;
        private float _steerLast;
        private int _stepsSinceAward;

        /// <summary>
        /// How many physics steps this episode charged reward on (feature 007, R6, US4).
        ///
        /// **The denominator for any statement about an episode in seconds.** Feature 006 could
        /// not say why its ratio against the trainer's own episode length sat near 3.16 when
        /// <c>DecisionPeriod: 4</c> puts the ceiling at 4, because only one of the two counts was
        /// ever recorded. Counting here, at the one place the per-step terms are charged, makes
        /// the ratio measurable rather than argued about.
        /// </summary>
        private int _physicsStepsCharged;

        /// <summary>
        /// Running sum of the minimum lateral ray clearance, and the count of samples in it
        /// (feature 008, R5).
        ///
        /// **This is a proxy for barrier use and is written down as one.** The contact count cannot
        /// detect a sustained grind, because `WallSensor` raises `OnCollisionEnter` once when the
        /// colliders begin touching and not again until they separate, so a car sliding along a
        /// barrier registers one contact for the whole slide. A policy running close to a barrier
        /// holds a side ray near zero for a long run of steps and a policy on the centre line does
        /// not.
        ///
        /// **Unvalidated as a grind detector at the time of writing (T004).** Both recovery probes
        /// produced nose-in contacts, where the barrier is ahead rather than beside the car, and
        /// the measure read 1.0 throughout. That is the correct reading for those cases and says
        /// nothing about a parallel slide, which the probe never produced. A flat reading is
        /// therefore uninformative rather than evidence of no grinding.
        /// </summary>
        private float _clearanceSum;

        private int _clearanceSamples;

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

            ResolveScriptedExpert();

            AssertObservationSize();
            AssertRunLabelAgrees();
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
        /// What actually drove, derived from the policy that actually drove (feature 011, FR-005).
        ///
        /// **The run record used to carry a hand-typed string, and its own tooltip admitted the
        /// problem**: "nothing checks the two agree, so they are worth checking by eye". A row
        /// labelled by eye cannot prove which weights produced it, and feature 009 has the scar to
        /// show for it, where a serialised literal stamped all 60 evaluation traces with the wrong
        /// sweep and M5 had to rebuild the mapping by matching run durations.
        ///
        /// So the label is built here from two things nobody can type: the model asset that
        /// <see cref="BehaviorParameters"/> actually loaded, and the inference mode actually in
        /// effect. <see cref="runId"/> survives as a cross-check and no longer as the source.
        ///
        /// Returns an explicit "(no model)" rather than an empty string when the behaviour has no
        /// model, because a blank controller column reads as a missing field rather than as a run
        /// that had no policy. That case is real: it is what a heuristic-mode run looks like.
        /// </summary>
        private string DerivedRunLabel()
        {
            var parameters = GetComponent<BehaviorParameters>();
            if (parameters == null)
            {
                return "(no behaviour)";
            }

            string model = parameters.Model != null ? parameters.Model.name : "(no model)";
            string inference = parameters.DeterministicInference ? "deterministic" : "sampling";
            return $"{model}_{inference}";
        }

        /// <summary>
        /// Complain when the typed run id and the loaded policy disagree (feature 011, T002).
        ///
        /// **Neither is silently preferred.** The derived label is what gets recorded, because a
        /// row has one controller column and a reader must not have to know which half to trust.
        /// The typed field is now here to be contradicted: a field nobody can contradict is not a
        /// check. An empty <see cref="runId"/> is not a disagreement, it is simply unused.
        /// </summary>
        private void AssertRunLabelAgrees()
        {
            if (string.IsNullOrEmpty(runId))
            {
                return;
            }

            string derived = DerivedRunLabel();
            if (derived.StartsWith(runId, System.StringComparison.Ordinal))
            {
                return;
            }

            Debug.LogError(
                $"[DrivingAgent] runId is '{runId}' but the loaded policy is '{derived}'. " +
                "The run record carries the derived label, so the rows will be correct and the " +
                "scene is what is wrong. Fix the field or the model before reading this sweep.",
                this);
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
                // The run id goes with the file. Leaving the logger's serialised label to describe
                // the run is what made feature 009's 60 traces all claim to be a feature 006 run.
                trace.BeginRun(runId);
            }

            _reward = default;
            ElapsedS = 0f;
            Smoothness.Reset();
            ResetProgress();
            _awardedLast = ring != null ? ring.AwardedCount : 0;
            _wrongWayLast = ring != null && ring.WrongWay;
            _steerLast = 0f;
            _stepsSinceAward = 0;
            _physicsStepsCharged = 0;
            _clearanceSum = 0f;
            _clearanceSamples = 0;
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

        /// <summary>
        /// Re-read the marker chain and start measuring progress from where the car actually is
        /// (feature 007, FR-011, research R7).
        ///
        /// **Called from <see cref="OnEpisodeBegin"/> and nowhere else, which is the point.** Every
        /// episode start reaches this, including the one a training-area swap causes, so no episode
        /// can difference its first step against a position belonging to the previous episode or to
        /// a different track. Feature 006 found <c>TrainingArea.SwapTo</c> ending episodes by a
        /// route that bypassed the reward reporting; a stale chain position would be the same bug
        /// with a worse signature, because it would charge hundreds of metres on one step and read
        /// as noise.
        ///
        /// The chain is re-read per episode rather than once at startup. It is 24 distances against
        /// an episode of several hundred steps, so it is not a per-step cost, and paying it makes
        /// the swap case correct without a dirty flag that somebody has to remember to set.
        /// </summary>
        private void ResetProgress()
        {
            if (ring == null)
            {
                return;
            }

            _chain.Clear();
            for (int i = 0; i < ring.Count; i++)
            {
                Transform marker = ring.Markers[i];
                if (marker != null)
                {
                    _chain.Add(marker.position);
                }
            }

            if (_chain.Count == ring.Count && _chain.Count > 1)
            {
                try
                {
                    _progress.Configure(_chain, RewardModel.CheckpointReward);
                }
                catch (System.ArgumentException e)
                {
                    // A degenerate chain is a generator fault, and TrackProgress throws so that an
                    // EditMode test can assert it. Here it is caught and logged instead: an
                    // exception raised out of OnEpisodeBegin fires once per episode for the rest of
                    // the run, and the resulting wall of identical errors buries the first one.
                    // The weight is left at zero by the failed Configure, so the term pays nothing
                    // rather than paying something wrong.
                    Debug.LogError($"[DrivingAgent] progress disabled for this track: {e.Message}", this);
                }
            }

            // The ring's StartIndex is the first EXPECTED marker, one ahead of the car. TrackProgress
            // takes it as given and steps back itself, so the correction lives in one place.
            _progress.Reset(ring.StartIndex);
        }

        /// <summary>The terms that are paid every step: existing, moving, and changing the wheel.</summary>
        private void AccrueStepTerms(float steer)
        {
            float step = RewardModel.Step();
            float speed = RewardModel.Speed(sensing != null ? sensing.SpeedForwardNorm : 0f);
            float jerk = RewardModel.Jerk(steer - _steerLast);

            // Charged at this call site with the step and speed terms, so all three advance on the
            // same tick. That is what keeps the per-lap total predictable from geometry: the term
            // is a distance, and it does not care how often it is sampled, only that it is sampled
            // on the ticks the car actually moves between.
            float progress = AccrueProgress();

            _reward.StepCostTotal += step;
            _reward.ForwardSpeed += speed;
            _reward.SteeringJerk += jerk;
            _reward.MarkerProgress += progress;

            // Here rather than in FixedUpdate, so the clock and the steering samples advance on
            // exactly the ticks the reward terms are charged on. Two different notions of "a step"
            // in one component is how the episode-length discrepancy in T050 got in.
            ElapsedS += Time.fixedDeltaTime;
            Smoothness.Sample(steer, ElapsedS);

            AddReward(step + speed + jerk + progress);
            _stepsSinceAward++;
            _physicsStepsCharged++;

            // On the same tick as the per-step reward terms, so the mean is over the steps the
            // episode was actually charged for rather than over rendered frames.
            _clearanceSum += MinLateralClearance();
            _clearanceSamples++;
        }

        /// <summary>
        /// Advance the chain position to where the car is now and price the movement.
        ///
        /// Zero on the first step of an episode, whatever the car's position, because there is
        /// nothing to difference against yet.
        /// </summary>
        private float AccrueProgress()
        {
            if (ring == null || car == null || _progress.Count < 2)
            {
                return 0f;
            }

            // Step returns the priced value directly, but the term is taken from LastAdvance and
            // priced here so that every reward in this table goes through RewardModel and the
            // breakdown has exactly one place it can be wrong.
            _progress.Step(car.transform.position, ring.NextIndex, ring.LapCount);

            return RewardModel.Progress(_progress.LastAdvance, _progress.ProgressWeight);
        }

        /// <summary>
        /// The closest the side of the ray fan can see, normalised, or 1.0 when nothing is in
        /// range (feature 008, R5).
        ///
        /// Only rays at 45 degrees or more off the nose count. A ray pointing forwards sees the
        /// barrier the car is driving at, which is a different question from how close the car is
        /// running to the wall beside it.
        /// </summary>
        private float MinLateralClearance()
        {
            if (sensing == null)
            {
                return 1f;
            }

            float lowest = 1f;
            for (int i = 0; i < sensing.RayCount && i < sensing.RayDistancesNorm.Count; i++)
            {
                if (Mathf.Abs(sensing.RayAngleDeg(i)) < 45f)
                {
                    continue;
                }

                lowest = Mathf.Min(lowest, sensing.RayDistancesNorm[i]);
            }

            return lowest;
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

                // Feature 008. The penalty is charged on every contact, exactly as before; what
                // changed is that the episode only ends once the budget is spent.
                //
                // **The two halves of this row are separable and only one of them has ever been
                // tested.** Feature 006's `ppo_car_wall_lo` moved the penalty from -5.0 to -1.0 and
                // left the terminal alone, so it is evidence about the weight. In every M3 run the
                // episode still ended at the first contact, in both arms of every comparison.
                //
                // A policy cannot learn to recover from a mistake it is never allowed to survive:
                // with the terminal at the first contact, every trajectory in the buffer that
                // touches a barrier ends there, and the value function has no data about what
                // follows a graze. Feature 007 made that bind, by producing the first policy that
                // drives far enough to hit anything.
                if (WallTerminal.EndsEpisode(wall.Contacts, wallContactBudget))
                {
                    Finish(EndReason.WallContact);
                }

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
            stats.Add("reward/progress", _reward.MarkerProgress);

            // Markers taken, not reward earned for them. SC-003 is read on this rather than on
            // reward/checkpoint, because adding a term to the table changes what a reward number
            // means and does not change what reaching a marker means (FR-018).
            stats.Add("episode/markers", ring != null ? ring.AwardedCount : 0f);

            // Averaged, like the trainer's own Environment/Episode Length, so the two are the same
            // kind of number and their ratio is the one R6 asks for.
            stats.Add("episode/physics_steps", _physicsStepsCharged);

            // Feature 008. Markers per episode cannot be read without the contact count: a policy
            // reaching further while touching more barriers is a different result from one
            // reaching further cleanly.
            stats.Add("episode/wall_contacts", wall != null ? wall.Contacts : 0f);

            stats.Add(
                "episode/lateral_clearance",
                _clearanceSamples > 0 ? _clearanceSum / _clearanceSamples : 1f);

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

                // Derived from the loaded model and the inference mode, never from the typed
                // field. A learned policy has no strategy; what distinguishes one of its runs from
                // another is which weights drove and whether the actions were sampled, and both of
                // those are readable at runtime. See DerivedRunLabel (feature 011, FR-005).
                Controller = DerivedRunLabel(),

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
        /// The scripted driver, when this object carries one. Null in every training scene.
        /// </summary>
        private HeuristicDriver _expert;

        /// <summary>
        /// Find the scripted driver and take the wheel off it (feature 009, FR-002).
        ///
        /// **Disabling is not the same as disengaging, and the difference is the whole reason this
        /// method exists.** <see cref="HeuristicDriver.SetEngaged"/> stops the driver from writing
        /// a command, but its <c>FixedUpdate</c> keeps running and, while disengaged, actively
        /// clears <c>CarController.ScriptedMove</c> so a released wheel does not hold a stale
        /// input. That is right when a human is taking over and wrong here: the frame order
        /// between two components' <c>FixedUpdate</c> is undefined, so a merely disengaged driver
        /// can null the command this agent wrote in the same physics step. Disabling the component
        /// stops that loop outright, and <see cref="HeuristicDriver.Decide"/> is still callable,
        /// because it is a pure function of the rays and the speed rather than of the run
        /// bookkeeping (specs/009-imitation-warm-start/research.md, R1 and R6).
        ///
        /// Feature 005's FR-004 asks for exactly one writer to <c>ScriptedMove</c> in any frame.
        /// After this runs, that writer is <see cref="OnActionReceived"/> and nothing else.
        /// </summary>
        private void ResolveScriptedExpert()
        {
            _expert = GetComponent<HeuristicDriver>();
            if (_expert == null)
            {
                return;
            }

            _expert.SetEngaged(false);
            _expert.enabled = false;
        }

        /// <summary>
        /// Drive the scripted driver's command through the agent's own action space.
        ///
        /// **This delegates and does not duplicate, which is what the previous version of this
        /// comment was protecting.** It used to return zeros and refuse to copy the scripted
        /// driver's control law into this callback, because two implementations of the baseline
        /// would leave the M5 comparison without a single answer to which one produced a figure.
        /// Feature 009 needed the expert inside the agent's own observation and action space so
        /// ML-Agents could record demonstrations from it, and calling
        /// <see cref="HeuristicDriver.Decide"/> gets that without copying a line: the control law
        /// still lives in exactly one place.
        ///
        /// **Zeros are still the answer when there is no scripted driver on this object**, which
        /// is every training scene and the evaluation scene. Only the demonstration scene carries
        /// one (research R10), so heuristic mode elsewhere means what it always meant, no decision
        /// source.
        ///
        /// The command is clamped the same way a policy's is in <see cref="OnActionReceived"/>,
        /// so the recorded demonstration cannot contain an action the action space does not allow.
        /// </summary>
        public override void Heuristic(in ActionBuffers actionsOut)
        {
            var continuous = actionsOut.ContinuousActions;

            if (_expert == null)
            {
                for (int i = 0; i < continuous.Length; i++)
                {
                    continuous[i] = 0f;
                }

                return;
            }

            Vector2 move = HeuristicCommand.Clamp(_expert.Decide());

            if (continuous.Length > 0) { continuous[0] = move.x; }
            if (continuous.Length > 1) { continuous[1] = move.y; }

            for (int i = 2; i < continuous.Length; i++)
            {
                continuous[i] = 0f;
            }
        }
    }
}
