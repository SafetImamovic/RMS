using System.Collections;
using UnityEngine;
using SelfDrivingSim.Agent;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// One independent copy of the environment (feature 006, FR-016, T022).
    ///
    /// **Independence is the requirement, not a nicety.** Several copies run in one training
    /// session, and if one copy's markers, episode or records could be reached by another, a
    /// reward would be attributable to nothing and the data would be untraceable. Independence is
    /// mostly structural already: `TrackBuilder` parents everything it builds under its own
    /// transform, so an area offset in the scene carries its whole track with it, and the only
    /// mutable static in `Assets/Scripts` belongs to the scripted driver's run record, which the
    /// training scene does not use.
    ///
    /// Areas sit at 300 m pitch (DESIGN 5). Rays are 20 m and a generated track is roughly 200 m of
    /// centre line, so no area's sensing can reach another area's barriers. That is cheaper than a
    /// physics layer per area, and it does not touch the raycast mask, which is sensing and frozen
    /// for this feature.
    /// </summary>
    public class TrainingArea : MonoBehaviour
    {
        [Header("Wiring (all of it inside this area)")]
        [SerializeField] private TrackBuilder track;
        [SerializeField] private CheckpointRing ring;
        [SerializeField] private StartPlacer placer;
        [SerializeField] private DrivingAgent agent;
        [SerializeField] private CarController car;

        /// <summary>Which copy this is. Assigned by the scheduler, stable for the session.</summary>
        public int AreaId { get; private set; } = -1;

        /// <summary>The seed currently built here.</summary>
        public int CurrentSeed { get; private set; } = -1;

        /// <summary>Episodes finished since this area last changed track.</summary>
        public int EpisodesOnSeed =>
            agent == null || !_built ? 0 : agent.CompletedEpisodes - _episodesAtSwap;

        /// <summary>The agent driving in this area, for the scheduler to pause across a swap.</summary>
        public DrivingAgent Agent => agent;

        private int _episodesAtSwap;
        private bool _built;

        private void Awake()
        {
            if (track == null) { track = GetComponentInChildren<TrackBuilder>(true); }
            if (ring == null) { ring = GetComponentInChildren<CheckpointRing>(true); }
            if (placer == null) { placer = GetComponentInChildren<StartPlacer>(true); }
            if (agent == null) { agent = GetComponentInChildren<DrivingAgent>(true); }
            if (car == null) { car = GetComponentInChildren<CarController>(true); }

            // **The car is parked until this area has a track under it.**
            //
            // Areas are built one at a time, so without this every car spends the first frames
            // over nothing and falls. Measured before the fix: twelve areas produced twelve
            // "car dropped below the world" entries and idle-drift reports of 40 to 60 m, all
            // within the first two seconds of a session. The car is not merely misplaced there,
            // it is in free fall while the physics that the whole model rests on runs.
            if (car != null)
            {
                car.gameObject.SetActive(false);
            }
        }

        /// <summary>Name the area, once, so a log line can say which copy misbehaved.</summary>
        public void Assign(int areaId)
        {
            AreaId = areaId;
            name = $"TrainingArea {areaId}";
        }

        /// <summary>
        /// Put a different track under this area's car, across the frames the rebuild needs.
        ///
        /// **This cannot happen inside <c>OnEpisodeBegin</c>**, which is why it is a coroutine
        /// owned by the area rather than something the agent does for itself. The callback is
        /// synchronous, while a rebuild spans at least three frames: `Destroy` is deferred to the
        /// end of the frame in play mode, so the old colliders are still present immediately after
        /// `Clear`, and the new ones only register on the following physics step. An episode
        /// started in between would sense a track that is half gone and half not there yet.
        ///
        /// The agent is disabled across the swap so it cannot act, or end an episode, on a world
        /// that is mid-rebuild.
        /// </summary>
        public IEnumerator SwapTo(int seed)
        {
            bool wasEnabled = agent != null && agent.enabled;

            if (agent != null)
            {
                agent.SetEngaged(false);
                agent.enabled = false;
            }

            if (car != null)
            {
                car.ScriptedMove = null;
            }

            track.Seed = seed;
            track.Clear();

            yield return null;                        // old colliders actually go away here
            track.Build();
            yield return new WaitForFixedUpdate();    // and the new ones register here

            CurrentSeed = seed;

            // Only now is there something to stand on. On the first build this also un-parks the
            // car; on later swaps it is already active and this changes nothing.
            if (car != null && !car.gameObject.activeSelf)
            {
                car.gameObject.SetActive(true);
                yield return new WaitForFixedUpdate();
            }

            _built = true;

            if (placer != null)
            {
                placer.Place();
            }

            yield return new WaitForFixedUpdate();

            if (agent != null)
            {
                agent.enabled = wasEnabled;
                agent.SetEngaged(true);

                // The episode that spans a swap is not a fair sample of either track, so it is
                // ended rather than allowed to finish on a course it did not start on.
                agent.EndEpisode();
                _episodesAtSwap = agent.CompletedEpisodes;
            }
        }
    }
}
