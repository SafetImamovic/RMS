using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using SelfDrivingSim.Agent;
using SelfDrivingSim.Logging;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Runs a controller over a set of seeds inside one Play session (feature 005, T032-T035).
    ///
    /// **Why it is one session and not one per seed** (research R4). At one times real time, 34
    /// training seeds at the observed lap length is 19.4 minutes for a single configuration, which
    /// fails SC-004 outright. Restarting the editor per seed would spend the entire five-minute
    /// budget on startup before a single lap was driven. So the track is torn down and rebuilt in
    /// place, the car is put back on the line, and the run record gains a row, all without leaving
    /// play mode.
    ///
    /// **It writes nothing itself.** <see cref="HeuristicDriver"/> already appends a row when a run
    /// ends, so a swept run and a hand-driven run produce the same row through the same code. A
    /// runner that recorded its own rows would be a second writer of one format, and the first
    /// disagreement between them would be discovered in the analysis.
    ///
    /// **Training seeds only** (research R5). Choosing a sensing geometry against the evaluation
    /// seeds would fit the environment to the tracks the learning agent is later judged on, which
    /// is the same leak as tuning a model on its test set wearing different clothes.
    /// </summary>
    public class SweepRunner : MonoBehaviour
    {
        /// <summary>Which half of the split to run. Anything but <see cref="Train"/> needs a reason.</summary>
        public enum SeedSet
        {
            /// <summary>The 34 accepted training seeds. The only correct choice for a sweep.</summary>
            Train = 0,

            /// <summary>The 10 held-out seeds. For reporting a final result, never for choosing one.</summary>
            Eval,
        }

        /// <summary>
        /// One sensing arrangement to sweep (T036, FR-013, FR-014).
        ///
        /// Ray length is not here. It is derived from the stopping distance rather than chosen
        /// (research C11), so sweeping it would be sweeping a consequence of the braking figure
        /// and calling the result a sensing finding.
        /// </summary>
        [System.Serializable]
        public struct FanConfig
        {
            public int rayCount;
            public float fovDeg;

            public override string ToString()
            {
                return string.Format(CultureInfo.InvariantCulture, "{0} rays / {1:F0} deg",
                                     rayCount, fovDeg);
            }
        }

        [Header("Wiring")]
        [SerializeField] private TrackBuilder track;

        [Tooltip("The driver under test. Anything implementing IRunDriver: the scripted driver, " +
                 "or the learned agent in inference (feature 006, FR-023).\n\n" +
                 "Typed as MonoBehaviour because Unity cannot serialise an interface reference. " +
                 "The field keeps its name so scenes wired before feature 006 keep their " +
                 "reference; only the declared type changed.")]
        [SerializeField] private MonoBehaviour driver;
        [SerializeField] private StartPlacer placer;
        [SerializeField] private CarController car;
        [SerializeField] private CarAgent agent;

        [Header("Seeds")]
        [Tooltip("Which half of results/tracks/seed_split.json to run.\n\n" +
                 "Training seeds only for anything that CHOOSES a configuration (research R5). " +
                 "Picking a geometry against the evaluation seeds fits the environment to the " +
                 "tracks the learning agent is later judged on.")]
        [SerializeField] private SeedSet seedSet = SeedSet.Train;

        [Tooltip("Stop after this many seeds. Zero runs the whole set.\n\n" +
                 "For checking the runner works before spending the full budget on a sweep that " +
                 "was going to be wrong.")]
        [SerializeField] private int maxSeeds;

        [Tooltip("Runs per seed per controller. One is a sweep; more than one measures the " +
                 "run-to-run spread across the whole seed set rather than on one seed, which is " +
                 "what T027's caveat asks for.")]
        [SerializeField] private int repeatsPerSeed = 1;

        [Header("Controllers")]
        [Tooltip("Each controller runs the whole seed set. Every configuration must cover the " +
                 "same seeds (FR-014), or the comparison is between seed sets rather than " +
                 "between controllers.")]
        [SerializeField]
        private RayControllers.Strategy[] controllers =
        {
            RayControllers.Strategy.MostOpen,
            RayControllers.Strategy.WeightedAverage,
        };

        [Header("Sensing (US3)")]
        [Tooltip("Fan arrangements to sweep. Empty runs whatever the scene is already sensing " +
                 "with, which is what a controller comparison wants.\n\n" +
                 "Every arrangement covers the same seeds (FR-014). A sweep in which one " +
                 "configuration saw more seeds than another would be comparing seed sets.")]
        [SerializeField] private FanConfig[] fans;

        [Header("Acceleration")]
        [Tooltip("Simulated seconds per real second.\n\n" +
                 "MEASURED, not picked: T034 runs one seed at this scale and at 1x and keeps the " +
                 "figure at which the outcomes still agree. A sweep that is fast and wrong is " +
                 "worse than one that is slow.")]
        [Range(1f, 20f)]
        [SerializeField] private float timeScale = 4f;

        [Tooltip("Start the sweep as soon as Play begins. Off means calling Begin() by hand, " +
                 "which is what the verification in T034 does.")]
        [SerializeField] private bool runOnStart;

        // --- state, read by the HUD and by whatever is watching a long sweep ------------------

        /// <summary>Whether a sweep is in progress.</summary>
        public bool Running { get; private set; }

        /// <summary>Runs finished so far, across every controller.</summary>
        public int RunsDone { get; private set; }

        /// <summary>Runs this sweep will perform in total, known before it starts.</summary>
        public int RunsPlanned { get; private set; }

        /// <summary>Real seconds since the sweep began. The SC-004 budget is measured on this.</summary>
        public float ElapsedRealS { get; private set; }

        /// <summary>The seeds this sweep will visit, in order.</summary>
        public IReadOnlyList<int> Seeds => _seeds;

        private readonly List<int> _seeds = new List<int>();
        private IRunDriver _driver;
        private float _startedRealAt;
        private float _restoreTimeScale = 1f;
        private float _restoreMaxDelta;

        private void Awake()
        {
            if (track == null) { track = FindAnyObjectByType<TrackBuilder>(); }
            if (driver == null) { driver = FindAnyObjectByType<HeuristicDriver>(); }
            if (placer == null) { placer = FindAnyObjectByType<StartPlacer>(); }
            if (car == null) { car = FindAnyObjectByType<CarController>(); }
            EnsureAgent();
            ResolveDriver();
        }

        /// <summary>
        /// Bind the serialized component to the interface the runner actually talks to
        /// (feature 006, T011).
        ///
        /// **It fails loudly rather than running without a driver.** Unity cannot serialise an
        /// interface, so the field is a <c>MonoBehaviour</c> and the type check happens here
        /// instead of in the inspector. A sweep that started with a null driver would spend its
        /// whole budget writing rows for a car nobody drove, which is the same shape of failure
        /// <see cref="EnsureAgent"/> exists to prevent.
        /// </summary>
        private void ResolveDriver()
        {
            _driver = driver as IRunDriver;

            if (driver != null && _driver == null)
            {
                Debug.LogError(
                    $"{driver.GetType().Name} is wired as the driver but does not implement " +
                    "IRunDriver, so the runner cannot start or stop a run with it.", this);
            }
        }

        /// <summary>
        /// Resolve the agent, late and from more than one place.
        ///
        /// **Resolved on use rather than only in <c>Awake</c>, because once it was not.** A sweep
        /// of three fan arrangements ran with `agent` null, silently skipped every fan change, and
        /// wrote twelve rows that all read `ray_fov_deg 180` while claiming to be three
        /// configurations. The rows were internally consistent and completely wrong, which is the
        /// failure mode this component's own seed check was written to prevent and then reproduced
        /// somewhere else.
        ///
        /// The search goes through the car first because that is where it is, and only then falls
        /// back to the scene. <c>FindAnyObjectByType</c> alone is what failed.
        /// </summary>
        private bool EnsureAgent()
        {
            if (agent != null)
            {
                return true;
            }

            if (car != null)
            {
                agent = car.GetComponent<CarAgent>() ?? car.GetComponentInChildren<CarAgent>(true);
            }

            if (agent == null && driver != null)
            {
                agent = driver.GetComponent<CarAgent>() ?? driver.GetComponentInChildren<CarAgent>(true);
            }

            if (agent == null)
            {
                agent = FindAnyObjectByType<CarAgent>(FindObjectsInactive.Include);
            }

            return agent != null;
        }

        private void Start()
        {
            if (runOnStart)
            {
                Begin();
            }
        }

        /// <summary>
        /// Set up a sweep from code, for a caller that is not the Inspector.
        ///
        /// T034's verification is the first such caller: it runs the same seed at several time
        /// scales in one session, which cannot be done by editing fields between runs because
        /// editing them means leaving play mode, and leaving play mode is the cost this whole
        /// component exists to avoid.
        /// </summary>
        /// <param name="scale">Simulated seconds per real second.</param>
        /// <param name="seedLimit">Stop after this many seeds. Zero runs the whole set.</param>
        /// <param name="repeats">Runs per seed per controller.</param>
        /// <param name="strategies">Controllers to run. Empty leaves the configured set alone.</param>
        public void Configure(float scale, int seedLimit, int repeats,
                              params RayControllers.Strategy[] strategies)
        {
            timeScale = Mathf.Clamp(scale, 1f, 20f);
            maxSeeds = Mathf.Max(0, seedLimit);
            repeatsPerSeed = Mathf.Max(1, repeats);

            if (strategies != null && strategies.Length > 0)
            {
                controllers = strategies;
            }
        }

        /// <summary>
        /// Set the arrangements to sweep, for a caller that is not the Inspector.
        ///
        /// Passing none clears the list, which means "run whatever the scene is already sensing
        /// with". That is the right default for a controller comparison: a sweep that silently
        /// imposed a fan would make every controller figure conditional on a geometry the caller
        /// never chose.
        /// </summary>
        public void ConfigureFans(params FanConfig[] arrangements)
        {
            fans = arrangements ?? new FanConfig[0];
        }

        /// <summary>Start the sweep. Ignored if one is already running.</summary>
        [ContextMenu("Begin sweep")]
        public void Begin()
        {
            if (Running)
            {
                Debug.LogWarning("[SweepRunner] a sweep is already running.", this);
                return;
            }

            if (!LoadSeeds())
            {
                return;
            }

            // Refused before the first lap rather than discovered in the results. A sweep asked
            // for three arrangements that cannot change the fan does not produce a partial
            // answer, it produces a complete and plausible wrong one.
            if (fans != null && fans.Length > 0 && !EnsureAgent())
            {
                Debug.LogError(
                    $"[SweepRunner] {fans.Length} fan arrangement(s) requested but there is no " +
                    "CarAgent in the scene to set them on. Every row would carry the scene's " +
                    "current fan and the sweep would look like it worked.", this);
                return;
            }

            StartCoroutine(RunSweep());
        }

        /// <summary>Stop after the run in progress, restoring the time settings.</summary>
        [ContextMenu("Stop sweep")]
        public void Stop()
        {
            Running = false;
        }

        // --- the seed set --------------------------------------------------------------------

        /// <summary>
        /// Read the seeds from the split file rather than from a list in the Inspector (T035).
        ///
        /// A list typed into a scene is a copy of a decision recorded somewhere else, and the two
        /// drift silently: the split file is what the BC and PPO milestones train against, so a
        /// sweep run over a hand-typed subset would be choosing a geometry against different
        /// tracks from the ones the comparison later uses.
        ///
        /// Refuses loudly rather than falling back to a default set. A sweep over the wrong seeds
        /// produces a complete, plausible, wrong answer, and nothing downstream could tell.
        /// </summary>
        private bool LoadSeeds()
        {
            string path = Path.Combine(RepoPaths.Root, "results", "tracks", "seed_split.json");

            if (!File.Exists(path))
            {
                Debug.LogError(
                    $"[SweepRunner] {path} not found, so there is no seed set to sweep. " +
                    "Run the track generation milestone before sweeping.", this);
                return false;
            }

            SeedSplitFile file;
            try
            {
                file = JsonUtility.FromJson<SeedSplitFile>(File.ReadAllText(path));
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[SweepRunner] {path} could not be read: {e.Message}", this);
                return false;
            }

            SeedSplitHalf half = seedSet == SeedSet.Train ? file?.train : file?.eval;
            if (half == null || half.accepted_seeds == null || half.accepted_seeds.Length == 0)
            {
                Debug.LogError(
                    $"[SweepRunner] {path} carries no accepted_seeds for {seedSet}.", this);
                return false;
            }

            _seeds.Clear();
            _seeds.AddRange(half.accepted_seeds);

            if (maxSeeds > 0 && maxSeeds < _seeds.Count)
            {
                _seeds.RemoveRange(maxSeeds, _seeds.Count - maxSeeds);
            }

            // Every track file has to exist before the first lap, not on the seed that is missing
            // one. A sweep that dies twenty minutes in has spent the whole SC-004 budget learning
            // something a directory listing knew.
            var missing = new List<int>();
            foreach (int seed in _seeds)
            {
                if (!File.Exists(Path.Combine(Application.dataPath, "Tracks", $"seed_{seed}.json")))
                {
                    missing.Add(seed);
                }
            }

            if (missing.Count > 0)
            {
                Debug.LogError(
                    "[SweepRunner] no track file for seed(s) " + string.Join(", ", missing) +
                    ". Export them before sweeping.", this);
                return false;
            }

            if (seedSet == SeedSet.Eval)
            {
                Debug.LogWarning(
                    "[SweepRunner] sweeping the EVALUATION seeds. Research R5 allows this only " +
                    "for reporting a result, never for choosing a configuration: a geometry " +
                    "picked here is fitted to the tracks the learning agent is judged on.", this);
            }

            return true;
        }

        // --- the sweep itself ------------------------------------------------------------------

        private IEnumerator RunSweep()
        {
            int fanCount = fans != null && fans.Length > 0 ? fans.Length : 1;

            Running = true;
            RunsDone = 0;
            RunsPlanned = _seeds.Count * Mathf.Max(1, repeatsPerSeed)
                        * Mathf.Max(1, controllers.Length) * fanCount;
            _startedRealAt = Time.realtimeSinceStartup;

            ApplyTimeSettings();

            Debug.Log(string.Format(CultureInfo.InvariantCulture,
                "[SweepRunner] {0} runs: {1} fans x {2} controllers x {3} seeds x {4} repeats at {5:F1}x",
                RunsPlanned, fanCount, Mathf.Max(1, controllers.Length), _seeds.Count,
                Mathf.Max(1, repeatsPerSeed), timeScale), this);

            // The fan is the outermost loop so every arrangement covers the same seeds under the
            // same controllers (FR-014). Nested the other way, an interrupted sweep would leave
            // one configuration with more seeds than another, and the comparison would be
            // between seed sets wearing the names of two geometries.
            for (int f = 0; f < fanCount; f++)
            {
                yield return ApplyFan(f);

                foreach (RayControllers.Strategy strategy in controllers)
                {
                    // Strategy selection belongs to the scripted driver alone, so it is not in
                    // IRunDriver (feature 006, T011). A learned policy has no strategy to set, and
                    // for it the controller loop runs once and the run record carries the run id
                    // in the controller column instead.
                    if (driver is HeuristicDriver scripted)
                    {
                        scripted.SetStrategy(strategy);
                    }

                    foreach (int seed in _seeds)
                    {
                        yield return SwapTrack(seed);

                        for (int repeat = 0; repeat < Mathf.Max(1, repeatsPerSeed); repeat++)
                        {
                            if (!Running)
                            {
                                break;
                            }

                            yield return RunOnce();
                        }

                        if (!Running)
                        {
                            break;
                        }
                    }

                    if (!Running)
                    {
                        break;
                    }
                }

                if (!Running)
                {
                    break;
                }
            }

            RestoreFan();
            RestoreTimeSettings();
            Running = false;

            Debug.Log(string.Format(CultureInfo.InvariantCulture,
                "[SweepRunner] finished {0} of {1} runs in {2:F1} real seconds. Rows in {3}",
                RunsDone, RunsPlanned, ElapsedRealS, RunRecordWriter.Path ?? "(none)"), this);
        }

        /// <summary>
        /// One run, from the start line to whatever ended it.
        ///
        /// The driver decides when a run is over, and every path out of a run ends in its
        /// <c>Finish</c>, so the loop below waits on the outcome rather than on a timer. A runner
        /// with its own timeout would be a second opinion about when a run stopped, and the two
        /// would disagree exactly on the runs that are hardest to interpret.
        /// </summary>
        private IEnumerator RunOnce()
        {
            _driver.RestartRun();
            _driver.SetEngaged(true);

            // A frame for the restart to take effect before the outcome is believed. Without it
            // the loop can see the PREVIOUS run's terminal outcome and finish instantly, which
            // would fill the record with rows that never drove.
            yield return new WaitForFixedUpdate();

            while (_driver.RunActive)
            {
                ElapsedRealS = Time.realtimeSinceStartup - _startedRealAt;
                yield return null;
            }

            RunsDone++;
            ElapsedRealS = Time.realtimeSinceStartup - _startedRealAt;
        }

        /// <summary>
        /// Tear down the current track and build the next seed's, across a frame boundary.
        ///
        /// **The frame in between is not politeness, it is required.** In play mode
        /// <c>Destroy</c> is deferred to the end of the frame, so clearing and rebuilding in one
        /// breath leaves the car sharing a frame with two sets of barriers, one of them where the
        /// old track was. The first contact would be recorded against the new seed, and the run
        /// record would blame a track the car was never on.
        /// </summary>
        private IEnumerator SwapTrack(int seed)
        {
            _driver.SetEngaged(false);

            if (car != null)
            {
                car.ScriptedMove = null;
            }

            track.Seed = seed;
            track.Clear();

            yield return null;      // the old colliders actually go away here
            track.Build();
            yield return new WaitForFixedUpdate();   // and the new ones register here

            if (placer != null)
            {
                placer.ResetRandom();
                placer.Place();
            }

            yield return new WaitForFixedUpdate();
        }

        // --- sensing (T036) --------------------------------------------------------------------

        /// <summary>
        /// Put the next arrangement on the agent, through the API T008 already built for this.
        ///
        /// <see cref="CarAgent.ConfigureFan"/> sets the fan and raises <c>FanOverridden</c>, which
        /// suppresses the startup drift check. During a sweep the scene is SUPPOSED to disagree
        /// with the exported sensing block, and one error per seed would bury the run the check
        /// exists to protect. Nothing is lost by the suppression: every run record row carries its
        /// own <c>ray_count</c> and <c>ray_fov_deg</c>, so which arrangement produced a figure is
        /// recoverable from the results rather than from the file.
        ///
        /// A frame afterwards, so the resized buffers are filled by a sense before a run reads
        /// them. Reading the first step of a run out of an array that has been reallocated but not
        /// yet written would sense a fan of zeros, which is a wall in every direction.
        /// </summary>
        private IEnumerator ApplyFan(int index)
        {
            if (fans == null || fans.Length == 0)
            {
                yield break;   // no arrangements asked for: run the scene's own fan
            }

            // Never a silent skip. Skipping quietly is what produced twelve rows that all read
            // ray_fov_deg 180 while claiming to be three configurations, and nothing in the
            // results could have said so. Begin() refuses a fan sweep without an agent, and this
            // is the second line of that defence rather than a repeat of it.
            if (!EnsureAgent())
            {
                Debug.LogError(
                    "[SweepRunner] no CarAgent, so the fan cannot be set and this sweep would " +
                    "record every arrangement as the scene's current one. Stopping.", this);
                Running = false;
                yield break;
            }

            FanConfig fan = fans[index];

            if (!_fanSaved)
            {
                _savedFan = new FanConfig { rayCount = agent.RayCount, fovDeg = agent.RayFovDeg };
                _fanSaved = true;
            }

            agent.ConfigureFan(fan.rayCount, fan.fovDeg);
            Debug.Log($"[SweepRunner] sensing with {fan}", this);

            yield return new WaitForFixedUpdate();
        }

        /// <summary>
        /// Put the scene's own fan back when the sweep ends.
        ///
        /// Without this the scene keeps the last swept arrangement for the rest of the session,
        /// and the next hand-driven run would sense with a geometry nobody chose while the
        /// Inspector still showed it. The drift check cannot warn about it either, because
        /// <c>FanOverridden</c> stays raised once a sweep has touched the agent.
        /// </summary>
        private void RestoreFan()
        {
            if (!_fanSaved || agent == null)
            {
                return;
            }

            agent.ConfigureFan(_savedFan.rayCount, _savedFan.fovDeg);
            _fanSaved = false;
        }

        private FanConfig _savedFan;
        private bool _fanSaved;

        // --- time (T033) --------------------------------------------------------------------

        /// <summary>
        /// Raise the clock, and leave the physics step exactly where it is.
        ///
        /// **<c>Time.fixedDeltaTime</c> is not touched, and that is the whole point** (research
        /// R4). A coarser physics step would make the sweep measure the step size rather than the
        /// geometry: the car's contacts, its grip and its steering rate limit are all integrated
        /// there, and a sweep that changed it would compare configurations under different
        /// physics. Raising <c>timeScale</c> alone means more fixed steps per rendered frame, each
        /// one identical to the ones a 1x run takes.
        ///
        /// <c>Time.maximumDeltaTime</c> has to come up with it. It caps the scaled frame delta
        /// that physics is allowed to consume, so at 4x and a frame rate that dips to 15 fps the
        /// default 0.333 s would clamp the catch-up and quietly deliver about 6.7x instead of the
        /// scale that was asked for. The run record would carry the number this field was set to
        /// rather than the one the run achieved, which is a lie of exactly the kind
        /// <c>time_scale</c> exists to prevent.
        ///
        /// **This does not make an accelerated run equivalent to a 1x run**, and nothing here
        /// claims it does. <see cref="CarController"/> integrates the steering rate limit in
        /// <c>Update</c> against the frame clock, so a frame that covers four times the simulated
        /// time moves the wheel four times as far. T034 is the measurement that decides which
        /// scale survives that, and it is a measurement rather than an argument because the answer
        /// is not deducible from this comment.
        /// </summary>
        private void ApplyTimeSettings()
        {
            _restoreTimeScale = Time.timeScale;
            _restoreMaxDelta = Time.maximumDeltaTime;

            Time.timeScale = timeScale;

            // Enough headroom for a frame as slow as 10 per second to still deliver the full
            // scale, rather than silently delivering less.
            Time.maximumDeltaTime = Mathf.Max(_restoreMaxDelta, timeScale * 0.1f);
        }

        private void RestoreTimeSettings()
        {
            Time.timeScale = _restoreTimeScale;
            Time.maximumDeltaTime = _restoreMaxDelta;
        }

        private void OnDisable()
        {
            // Leaving play mode mid-sweep must not strand the editor at 4x. timeScale survives
            // the exit, and the next Play session would run four times too fast with nothing on
            // screen to say why.
            if (Running)
            {
                RestoreFan();
                RestoreTimeSettings();
                Running = false;
            }
        }

        // --- the split file --------------------------------------------------------------------

        [System.Serializable]
        private class SeedSplitFile
        {
            public SeedSplitHalf train;
            public SeedSplitHalf eval;
        }

        [System.Serializable]
        private class SeedSplitHalf
        {
            public int[] accepted_seeds;
        }
    }
}
