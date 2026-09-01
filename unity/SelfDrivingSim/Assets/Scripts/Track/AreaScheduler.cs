using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Rotate the training seeds across the areas, between episodes (feature 006, FR-012, T024).
    ///
    /// Episodes draw from all 34 accepted training seeds, and no scene layout of 8 to 16 areas
    /// covers 34 tracks without rotation. Each area therefore starts on a different seed and moves
    /// to the next unused one every <see cref="rotationEvery"/> episodes.
    ///
    /// **The evaluation seeds are never loaded here.** The pool comes from
    /// <see cref="SeedSplit.TrainSeeds"/>, which reads the committed split, so the training scene
    /// cannot quietly disagree with the file that defines the separation (SC-008).
    ///
    /// **One swap at a time.** A rebuild costs about 55 ms of main-thread work (T023), and the main
    /// thread is shared by every area, so twelve areas rotating on the same episode would stall the
    /// whole session for most of a second. Swaps are queued and run one after another instead,
    /// which spreads that cost without any area waiting long for its turn.
    /// </summary>
    public class AreaScheduler : MonoBehaviour
    {
        [Tooltip("Episodes an area runs on one seed before moving to the next.\n\n" +
                 "A rebuild costs about 55 ms (T023) and episodes early in training are short, so " +
                 "rotating every episode would spend a real fraction of the session rebuilding " +
                 "geometry. Five keeps the cost negligible while still showing every area a new " +
                 "track often enough that it cannot learn one loop's corners.")]
        [SerializeField] private int rotationEvery = 5;

        [Tooltip("Areas to schedule. Empty means every TrainingArea in the scene.")]
        [SerializeField] private TrainingArea[] areas;

        /// <summary>The training seeds in use, in the order areas were given them.</summary>
        public IReadOnlyList<int> Pool => _pool;

        private readonly List<int> _pool = new List<int>();
        private int _nextSeedIndex;
        private bool _swapping;

        private IEnumerator Start()
        {
            if (areas == null || areas.Length == 0)
            {
                areas = FindObjectsByType<TrainingArea>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            }

            int[] seeds = SeedSplit.TrainSeeds();
            if (seeds == null || seeds.Length == 0)
            {
                Debug.LogError("[AreaScheduler] no training seeds, so nothing can be trained on.", this);
                yield break;
            }

            _pool.AddRange(seeds);

            if (areas.Length > _pool.Count)
            {
                Debug.LogWarning(
                    $"[AreaScheduler] {areas.Length} areas against {_pool.Count} training seeds, " +
                    "so some areas start on the same track. That is not wrong, but the areas are " +
                    "then less independent as samples than they look.", this);
            }

            // Build every area before any of them drives, one at a time for the same reason swaps
            // are serialised later.
            for (int i = 0; i < areas.Length; i++)
            {
                areas[i].Assign(i);
                yield return areas[i].SwapTo(NextSeed());
            }

            Debug.Log($"[AreaScheduler] {areas.Length} areas over {_pool.Count} training seeds, " +
                      $"rotating every {rotationEvery} episodes.", this);
        }

        private void Update()
        {
            if (_swapping || areas == null || _pool.Count == 0)
            {
                return;
            }

            foreach (TrainingArea area in areas)
            {
                if (area == null || area.AreaId < 0 || area.EpisodesOnSeed < rotationEvery)
                {
                    continue;
                }

                StartCoroutine(SwapOne(area));
                return;
            }
        }

        private IEnumerator SwapOne(TrainingArea area)
        {
            _swapping = true;
            yield return area.SwapTo(NextSeed());
            _swapping = false;
        }

        /// <summary>
        /// The next seed in the pool, wrapping.
        ///
        /// Cycling rather than drawing at random, so that over a session every seed is seen a
        /// similar number of times. A random draw would leave some tracks over-represented by
        /// chance, and with 34 seeds against a training run's episode count that imbalance is
        /// large enough to matter.
        /// </summary>
        private int NextSeed()
        {
            int seed = _pool[_nextSeedIndex % _pool.Count];
            _nextSeedIndex++;
            return seed;
        }
    }
}
