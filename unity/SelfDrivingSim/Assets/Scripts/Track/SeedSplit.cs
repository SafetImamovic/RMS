using System.IO;
using UnityEngine;
using SelfDrivingSim.Logging;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// The committed train and evaluation seed split, read from one place (feature 006, T020).
    ///
    /// `results/tracks/seed_split.json` is produced by the track generator and committed, and it
    /// already carries what this feature needs: 34 accepted training seeds, 10 evaluation seeds,
    /// and its own `disjoint` claim. Training reads the training half through here and never
    /// touches the other one.
    ///
    /// **Why a loader rather than a field on the scheduler.** SC-008 asks for the separation to be
    /// demonstrable from the recorded configuration alone, and a seed list typed into a scene is
    /// not that. Reading the committed file means the scene cannot disagree with the split, and an
    /// EditMode test can assert the property directly rather than a human checking a list.
    /// </summary>
    public static class SeedSplit
    {
        /// <summary>Where the split lives, relative to the repository root.</summary>
        public static string Path =>
            System.IO.Path.Combine(RepoPaths.Root, "results", "tracks", "seed_split.json");

        /// <summary>The 34 accepted training seeds, or null with an error logged.</summary>
        public static int[] TrainSeeds() => Read(train: true);

        /// <summary>
        /// The 10 accepted evaluation seeds, or null with an error logged.
        ///
        /// **Nothing in the training scene may call this.** It exists for the evaluation harness
        /// and for the test that proves the two halves do not overlap.
        /// </summary>
        public static int[] EvalSeeds() => Read(train: false);

        private static int[] Read(bool train)
        {
            string path = Path;

            if (!File.Exists(path))
            {
                Debug.LogError(
                    $"[SeedSplit] {path} not found, so there is no seed set to train on. " +
                    "Generate the tracks before training.");
                return null;
            }

            SplitFile file;
            try
            {
                file = JsonUtility.FromJson<SplitFile>(File.ReadAllText(path));
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[SeedSplit] {path} could not be read: {e.Message}");
                return null;
            }

            Half half = train ? file?.train : file?.eval;
            if (half?.accepted_seeds == null || half.accepted_seeds.Length == 0)
            {
                Debug.LogError(
                    $"[SeedSplit] {path} carries no accepted_seeds for the " +
                    (train ? "training" : "evaluation") + " half.");
                return null;
            }

            return half.accepted_seeds;
        }

        [System.Serializable]
        private class SplitFile
        {
            public Half train;
            public Half eval;
        }

        [System.Serializable]
        private class Half
        {
            public int[] accepted_seeds;
        }
    }
}
