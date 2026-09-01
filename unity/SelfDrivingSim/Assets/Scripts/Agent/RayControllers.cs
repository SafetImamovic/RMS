using System;
using UnityEngine;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// The steering strategies, as pure functions of what the rays report (feature 005, FR-006).
    ///
    /// **These live outside <see cref="HeuristicDriver"/> on purpose.** A strategy is a function
    /// from a distance array to a steering command: no car, no scene, no physics step, no clock.
    /// That is what makes it testable in EditMode, and Constitution Principle VIII asks for the
    /// logic worth testing to be reachable without standing a whole simulation up. Folding these
    /// into the MonoBehaviour would put the one interesting piece of this feature behind
    /// everything that makes testing slow.
    ///
    /// Both take normalised distances, where 1.0 is a clear ray at full range and 0.0 is a wall on
    /// the bumper, and the ray angles in degrees with right positive. Both return a steering
    /// command in [-1, 1] on the car's own scale, which is the ray angle divided by the maximum
    /// steering angle.
    ///
    /// Neither decides speed. The driver derives that from the steering command, so the two
    /// strategies differ in exactly one thing and the comparison in US2 is about steering alone.
    /// </summary>
    public static class RayControllers
    {
        /// <summary>Which strategy a run uses. Selectable per run without editing code (FR-007).</summary>
        public enum Strategy
        {
            /// <summary>Steer at the single most open direction. The naive one.</summary>
            MostOpen = 0,

            /// <summary>Steer at the openness-weighted mean of every direction.</summary>
            WeightedAverage,
        }

        /// <summary>
        /// Steer toward the single most open direction.
        ///
        /// **This controller is expected to chatter, and the prediction is recorded before it was
        /// ever run** (research R2, DESIGN 4.7). It can only command angles that a ray actually
        /// points along. At the stated fan those are multiples of 15 degrees against a 25 degree
        /// steering limit, so the reachable commands are 0, ±0.6 and then ±1.0 once the clamp
        /// takes over. Three magnitudes, nothing in between, so it cannot hold a mid-corner line
        /// and has to alternate between two of them.
        ///
        /// It is kept rather than replaced (FR-006) because the comparison against the smoothed
        /// version is the deliverable, not the smoothed version by itself.
        ///
        /// **Ties break toward the centre, never by array order.** A tie is not exotic: it is what
        /// an open plane reads, where every ray returns exactly 1.0, and T062 confirmed that
        /// reading on FlatGround. Taking the first index found would steer hard left every time
        /// the world went symmetric, and the bug would look like a track problem rather than a
        /// controller problem because it would only appear where there is nothing to see.
        /// </summary>
        public static float MostOpen(
            System.Collections.Generic.IReadOnlyList<float> distancesNorm,
            System.Collections.Generic.IReadOnlyList<float> anglesDeg,
            float steerMaxDeg)
        {
            Validate(distancesNorm, anglesDeg, steerMaxDeg);

            int count = distancesNorm.Count;
            float best = float.NegativeInfinity;
            int bestIndex = -1;
            float bestAbsAngle = float.PositiveInfinity;

            for (int i = 0; i < count; i++)
            {
                float d = distancesNorm[i];
                float absAngle = Mathf.Abs(anglesDeg[i]);

                // Strictly greater wins on distance. On an exact tie the ray closer to straight
                // ahead wins, which is what makes the all-clear fan return 0 instead of turning
                // toward whichever end of the array the loop happened to start at.
                bool better = d > best || (Mathf.Approximately(d, best) && absAngle < bestAbsAngle);
                if (!better)
                {
                    continue;
                }

                best = d;
                bestIndex = i;
                bestAbsAngle = absAngle;
            }

            if (bestIndex < 0)
            {
                return 0f;
            }

            return Mathf.Clamp(anglesDeg[bestIndex] / steerMaxDeg, -1f, 1f);
        }

        /// <summary>
        /// Steer toward the openness-weighted mean of every direction.
        ///
        /// Every ray votes for its own angle, weighted by how far it can see, and the command is
        /// the weighted mean. Nothing snaps to a ray, so the reachable commands are continuous and
        /// the quantisation that makes <see cref="MostOpen"/> chatter is gone by construction
        /// rather than by smoothing after the fact.
        ///
        /// A symmetric reading returns exactly 0 without a special case, because the weights
        /// mirror and the angles cancel. That is the correct answer to "no direction is preferred"
        /// and it is worth having fall out of the arithmetic instead of out of an if statement.
        ///
        /// **Adopting this over the naive one is a decision this feature has to earn** (US2,
        /// FR-009). If the measurement says the naive controller does the job, that gets written
        /// up and this one is justified on its merits or not adopted.
        /// </summary>
        public static float WeightedAverage(
            System.Collections.Generic.IReadOnlyList<float> distancesNorm,
            System.Collections.Generic.IReadOnlyList<float> anglesDeg,
            float steerMaxDeg)
        {
            Validate(distancesNorm, anglesDeg, steerMaxDeg);

            int count = distancesNorm.Count;
            float weighted = 0f;
            float total = 0f;

            for (int i = 0; i < count; i++)
            {
                // Distances are already in [0, 1] and a blocked ray weighs nothing, which is the
                // behaviour wanted: a direction with a wall across it should not pull the car
                // toward itself at all. Clamped rather than trusted, because a caller passing raw
                // metres would otherwise get a plausible-looking answer on the wrong scale.
                float w = Mathf.Clamp01(distancesNorm[i]);
                weighted += w * anglesDeg[i];
                total += w;
            }

            // Every ray blocked to exactly zero. There is no open direction to average, so hold
            // the current heading rather than inventing a turn out of a division by zero.
            if (total <= 1e-6f)
            {
                return 0f;
            }

            return Mathf.Clamp(weighted / total / steerMaxDeg, -1f, 1f);
        }

        /// <summary>Dispatch by name, so a run selects its strategy without a code change.</summary>
        public static float Steer(
            Strategy strategy,
            System.Collections.Generic.IReadOnlyList<float> distancesNorm,
            System.Collections.Generic.IReadOnlyList<float> anglesDeg,
            float steerMaxDeg)
        {
            switch (strategy)
            {
                case Strategy.MostOpen:
                    return MostOpen(distancesNorm, anglesDeg, steerMaxDeg);
                case Strategy.WeightedAverage:
                    return WeightedAverage(distancesNorm, anglesDeg, steerMaxDeg);
                default:
                    throw new ArgumentOutOfRangeException(nameof(strategy), strategy, null);
            }
        }

        /// <summary>
        /// Refuse inputs that would produce a plausible number from nonsense.
        ///
        /// Mismatched array lengths are the failure worth catching hardest: the loop would read
        /// whichever array is shorter and steer confidently using angles that belong to different
        /// rays. That produces a car that drives, badly, for a reason nobody would find by
        /// watching it.
        /// </summary>
        private static void Validate(
            System.Collections.Generic.IReadOnlyList<float> distancesNorm,
            System.Collections.Generic.IReadOnlyList<float> anglesDeg,
            float steerMaxDeg)
        {
            if (distancesNorm == null || anglesDeg == null)
            {
                throw new ArgumentNullException(
                    distancesNorm == null ? nameof(distancesNorm) : nameof(anglesDeg));
            }

            if (distancesNorm.Count != anglesDeg.Count)
            {
                throw new ArgumentException(
                    $"{distancesNorm.Count} distances against {anglesDeg.Count} angles. Each ray " +
                    "needs both, or the steering command is computed from mismatched rays.");
            }

            if (steerMaxDeg <= 0f)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(steerMaxDeg), steerMaxDeg,
                    "the maximum steering angle is the divisor of the command and must be positive");
            }
        }
    }
}
