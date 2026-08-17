using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using Unity.MLAgents.Sensors;
using UnityEngine;
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
        }

        /// <summary>Why the episode that just ended, ended.</summary>
        public EndReason Outcome { get; private set; } = EndReason.Running;

        /// <summary>What the last episode's return was made of (FR-008).</summary>
        public RewardModel.Breakdown Reward => _reward;

        // --- IRunDriver, for the evaluation sweep (FR-023) -------------------------------------

        /// <inheritdoc />
        public bool RunActive => _runActive;

        /// <inheritdoc />
        public void RestartRun()
        {
            _runActive = true;
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

            _reward = default;
            _awardedLast = ring != null ? ring.AwardedCount : 0;
            _wrongWayLast = ring != null && ring.WrongWay;
            _steerLast = 0f;
            _stepsSinceAward = 0;
            _runActive = true;
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
            stats.Add("episode/end_" + Outcome.ToString().ToLowerInvariant(), 1f);
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
