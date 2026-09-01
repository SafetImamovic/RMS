using System.Collections.Generic;
using NUnit.Framework;
using SelfDrivingSim.Track;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The evaluation seeds stay out of training (feature 006, SC-008, T021).
    ///
    /// **A test rather than a review, because the failure is silent and flattering.** A training
    /// run that quietly included seed 1003 would produce a better evaluation number, no error, and
    /// nothing in the output to say the result was measured on a track the policy had already
    /// learned. By the time anyone suspected it, the run would be a night old.
    ///
    /// These read the committed `results/tracks/seed_split.json` through the same loader the
    /// training scene uses, so the property is asserted about the thing that actually runs rather
    /// than about a copy of the seed list.
    /// </summary>
    public class TrainingSeedIsolationTests
    {
        [Test]
        public void The_split_file_is_readable_from_the_repository()
        {
            Assert.That(SeedSplit.TrainSeeds(), Is.Not.Null,
                "the training half could not be read from " + SeedSplit.Path);
            Assert.That(SeedSplit.EvalSeeds(), Is.Not.Null,
                "the evaluation half could not be read from " + SeedSplit.Path);
        }

        [Test]
        public void Training_and_evaluation_seeds_do_not_overlap()
        {
            var train = new HashSet<int>(SeedSplit.TrainSeeds());
            int[] eval = SeedSplit.EvalSeeds();

            foreach (int seed in eval)
            {
                Assert.That(train.Contains(seed), Is.False,
                    $"evaluation seed {seed} is also a training seed, so any evaluation figure " +
                    "is measured on a track the policy trained on");
            }
        }

        [Test]
        public void The_split_has_the_counts_feature_003_accepted()
        {
            // 34 of 40 requested training seeds and 10 of 10 evaluation seeds were accepted. The
            // numbers are asserted so that a regenerated split cannot silently change the
            // denominator under results that were already published against it.
            Assert.That(SeedSplit.TrainSeeds().Length, Is.EqualTo(34));
            Assert.That(SeedSplit.EvalSeeds().Length, Is.EqualTo(10));
        }

        [Test]
        public void Seeds_are_unique_within_each_half()
        {
            // A duplicate would over-weight one track in the rotation without changing any count
            // that gets reported.
            int[] train = SeedSplit.TrainSeeds();
            int[] eval = SeedSplit.EvalSeeds();

            Assert.That(new HashSet<int>(train).Count, Is.EqualTo(train.Length));
            Assert.That(new HashSet<int>(eval).Count, Is.EqualTo(eval.Length));
        }
    }
}
