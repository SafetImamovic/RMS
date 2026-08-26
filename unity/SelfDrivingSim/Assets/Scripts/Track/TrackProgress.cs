using System;
using System.Collections.Generic;
using UnityEngine;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// How far round the lap the car has driven, in metres along the chain of markers
    /// (feature 007, DESIGN 4.5).
    ///
    /// **This is not a MonoBehaviour and it takes positions, not transforms.** It is handed a
    /// polyline and a point, and it answers with a distance. That is what lets the two properties
    /// the whole feature rests on be asserted in EditMode against a synthetic chain, with no track,
    /// no car and no physics step (FR-022). A reward that can only be checked by watching a car
    /// drive is a reward nobody can check.
    ///
    /// **There is no reward logic here beyond the one weight.** This class answers "how many metres
    /// forward is the car allowed to claim"; <see cref="Agent.RewardModel"/> prices it. The split is
    /// the one <see cref="CheckpointRing"/> already draws between the marker arithmetic and what a
    /// marker is worth.
    ///
    /// The term is the change in <see cref="Clamped"/> between two physics steps, times
    /// <see cref="ProgressWeight"/>. Because it is the difference of a single quantity, its sum
    /// over any trajectory is the difference between that trajectory's endpoints and nothing else,
    /// so **any path that returns the car to where it started earns exactly zero**. That is what
    /// preserves DESIGN 4.5's anti-farming invariant by the shape of the term rather than by a
    /// weight chosen small enough, and it is the property <c>TrackProgressTests</c> asserts.
    /// </summary>
    public class TrackProgress
    {
        /// <summary>
        /// What one lap of progress pays, as a fraction of what one lap of markers pays
        /// (DESIGN 4.5, research R5).
        ///
        /// Half. The markers stay the larger signal because the milestone is defined on them and
        /// this term exists to lead the policy to them, not to replace them. At a half, a lap
        /// through every marker is worth 36.0, of which two thirds is still the thing being
        /// measured. At 1.0 the two signals are equal partners and any error in the chain geometry
        /// costs as much as a missed marker.
        /// </summary>
        public const float LapPayoutFraction = 0.5f;

        private readonly List<Vector3> _markers = new List<Vector3>();

        /// <summary>Length of the segment from marker i to marker i+1, wrapping at the end.</summary>
        private double[] _segment = new double[0];

        /// <summary>Chain distance from marker 0 to marker i. Length Count, so no wrap entry.</summary>
        private double[] _cumulative = new double[0];

        /// <summary>How many markers the chain holds. Zero until configured.</summary>
        public int Count => _markers.Count;

        /// <summary>The whole way round, in metres. About 202.3 m on the generated tracks (T060).</summary>
        public double ChainLength { get; private set; }

        /// <summary>
        /// Reward per metre of forward progress, derived rather than chosen (DESIGN 4.5).
        ///
        /// <c>LapPayoutFraction * Count * checkpointReward / ChainLength</c>. On the nominal chain
        /// that is 0.5 x 24 x 1.0 / 202.3, about 0.0594 per metre, so a car moving at the scripted
        /// driver's pace earns about 0.0119 per physics step against a step cost of -0.001.
        ///
        /// **Computed at configure time and never written as a literal.** Generated tracks differ
        /// between seeds, so a literal would silently pay a different fraction of a lap on
        /// different tracks. What reproduces is the derivation, not the number (Principle VI).
        /// </summary>
        public float ProgressWeight { get; private set; }

        /// <summary>
        /// The marker the car was standing on when the episode began, which is where progress is
        /// measured from.
        ///
        /// **This is one behind <see cref="CheckpointRing.StartIndex"/>, and the difference is not
        /// cosmetic.** <c>StartAt(k)</c> places the car on marker <c>k</c>, records that marker as
        /// already taken, and then sets <c>StartIndex</c> to <c>k + 1</c>, because the ring's
        /// StartIndex means "the first marker that was expected". Measuring the arc from the
        /// expected marker instead of from the car would put every episode's origin one marker
        /// ahead of the car, so the very first step would read as almost a whole lap of progress
        /// already banked. <see cref="Reset"/> takes the ring's value and steps back one, in one
        /// place, so no caller has to remember this.
        /// </summary>
        public int OriginIndex { get; private set; }

        /// <summary>
        /// Metres driven along the chain since the episode began, not reset at the finish line.
        ///
        /// It keeps climbing across laps by design (research R2). A version that reset to zero at
        /// the start line would difference into one step charging a whole lap of penalty, once per
        /// lap, which is the single worst place in the episode to hide an error.
        /// </summary>
        public double Unwrapped { get; private set; }

        /// <summary>
        /// How far the car may claim to have come: the end of the segment that finishes at the
        /// marker the ring says is due.
        ///
        /// This is what makes a shortcut worthless. <see cref="CheckpointRing"/> already refuses to
        /// award a marker that is not next, but the geometry alone would happily pay for the metres
        /// a cutting car covered. Held at the ceiling, that car earns nothing while still paying the
        /// step cost, so cutting is strictly worse than the legal path rather than merely
        /// unrewarded.
        /// </summary>
        public double Ceiling { get; private set; }

        /// <summary>The value the reward is actually a difference of: min of the two above.</summary>
        public double Clamped { get; private set; }

        /// <summary>True while the car is being held back by <see cref="Ceiling"/>. For the debug panel.</summary>
        public bool AtCeiling { get; private set; }

        /// <summary><see cref="Clamped"/> as it stood on the previous physics step.</summary>
        public double Previous { get; private set; }

        /// <summary>
        /// False on the first step of an episode, when there is nothing to difference against.
        ///
        /// The natural bug is to difference against zero, which pays out the entire arc position of
        /// a randomised start on the first step of every episode. That is the most repeated event
        /// in training and therefore the worst one to get wrong.
        /// </summary>
        public bool HasPrevious { get; private set; }

        /// <summary>Metres of claimable progress in the last <see cref="Step"/>. Signed.</summary>
        public double LastAdvance { get; private set; }

        /// <summary>
        /// Adopt a chain of marker positions and derive the weight from it.
        ///
        /// The order of the list IS the progress order, exactly as in
        /// <see cref="CheckpointRing.Configure"/>, and it is never decided here.
        /// </summary>
        /// <param name="markerPositions">World positions of the markers, in progress order.</param>
        /// <param name="checkpointReward">What one marker pays, so the derivation of the weight
        /// against a lap of markers is explicit. Callers pass <c>RewardModel.CheckpointReward</c>;
        /// it is a parameter rather than a reference so this class stays clear of the agent.</param>
        public void Configure(IReadOnlyList<Vector3> markerPositions, float checkpointReward)
        {
            _markers.Clear();
            if (markerPositions != null)
            {
                _markers.AddRange(markerPositions);
            }

            int n = _markers.Count;
            _segment = new double[n];
            _cumulative = new double[n];
            ChainLength = 0.0;

            // Cleared before the loop that can throw, so a chain that fails validation leaves the
            // weight at zero rather than keeping the previous track's. Step treats a zero weight as
            // "this chain is not usable" and pays nothing, which is what a caller that logged the
            // failure and carried on should get.
            ProgressWeight = 0f;

            if (n < 2)
            {
                // Nothing to measure along. The weight stays at zero so a misconfigured ring pays
                // nothing rather than dividing by zero further down.
                Reset(1);
                return;
            }

            for (int i = 0; i < n; i++)
            {
                _cumulative[i] = ChainLength;
                double length = Vector3.Distance(_markers[i], _markers[(i + 1) % n]);

                // A zero-length segment is a degenerate track, and it must fail here rather than
                // become an infinite weight or a division by zero at run time. The build is the
                // only place where this is cheap to notice.
                if (length <= 0.0)
                {
                    throw new ArgumentException(
                        $"TrackProgress: markers {i} and {(i + 1) % n} are coincident, so the " +
                        "chain has a zero-length segment and no progress can be measured along it.",
                        nameof(markerPositions));
                }

                _segment[i] = length;
                ChainLength += length;
            }

            ProgressWeight = (float)(LapPayoutFraction * n * checkpointReward / ChainLength);

            // Reset to the un-randomised default: car on marker 0, first expected marker 1. The
            // agent resets again with the ring's real value at every episode begin.
            Reset(1);
        }

        /// <summary>
        /// Begin an episode, with nothing to difference against.
        ///
        /// **Every episode start must reach this, including the training-area swap.** Feature 006
        /// found <c>TrainingArea.SwapTo</c> ending episodes by a route that never reached the reward
        /// reporting; the same route must not skip this reset either. A position left over from a
        /// different track differences into hundreds of metres charged on a single step, and it
        /// would read as noise rather than as a bug.
        /// </summary>
        /// <param name="ringStartIndex"><see cref="CheckpointRing.StartIndex"/>, passed straight
        /// through. The step back to the marker the car is actually on happens here, so it happens
        /// once. See <see cref="OriginIndex"/>.</param>
        public void Reset(int ringStartIndex)
        {
            OriginIndex = Count > 0 ? (((ringStartIndex - 1) % Count) + Count) % Count : 0;
            Unwrapped = 0.0;
            Ceiling = 0.0;
            Clamped = 0.0;
            Previous = 0.0;
            AtCeiling = false;
            HasPrevious = false;
            LastAdvance = 0.0;
        }

        /// <summary>
        /// Advance to the car's current position and return what that movement is worth.
        ///
        /// Returns zero on the first step after a <see cref="Reset"/>, whatever the car's position,
        /// because there is no previous position to difference against.
        /// </summary>
        /// <param name="carPosition">Where the car is now.</param>
        /// <param name="nextIndex">The ring's <see cref="CheckpointRing.NextIndex"/>: the only
        /// marker that may be awarded, and so the end of the segment the car may claim.</param>
        /// <param name="lapCount">The ring's <see cref="CheckpointRing.LapCount"/>, which is what
        /// keeps <see cref="Unwrapped"/> climbing across the finish line.</param>
        public float Step(Vector3 carPosition, int nextIndex, int lapCount)
        {
            if (Count < 2 || ProgressWeight <= 0f)
            {
                LastAdvance = 0.0;
                return 0f;
            }

            int due = ((nextIndex % Count) + Count) % Count;
            int behind = ((due - 1) % Count + Count) % Count;

            double lapBase = (double)lapCount * ChainLength;
            double arcBehind = ArcFromStart(behind);

            Unwrapped = lapBase + arcBehind + ProjectOnto(behind, carPosition);
            Ceiling = lapBase + arcBehind + _segment[behind];
            Clamped = Math.Min(Unwrapped, Ceiling);
            AtCeiling = Unwrapped >= Ceiling;

            if (!HasPrevious)
            {
                Previous = Clamped;
                HasPrevious = true;
                LastAdvance = 0.0;
                return 0f;
            }

            // Differenced in double on purpose. On float the ulp at a kilometre of driving is
            // about 0.00006 m against a step of about 0.2 m, and the telescoping test sums
            // thousands of small terms against one large difference, which is where accumulated
            // error shows. In double the ulp there is about 2.3e-13 m. The cast to float happens
            // once, at the end, when the distance becomes a reward. DESIGN 4.5 records this.
            LastAdvance = Clamped - Previous;
            Previous = Clamped;

            return (float)(LastAdvance * ProgressWeight);
        }

        /// <summary>Chain distance from <see cref="OriginIndex"/> forward to marker i.</summary>
        private double ArcFromStart(int index)
        {
            double raw = _cumulative[index] - _cumulative[OriginIndex];
            return raw < 0.0 ? raw + ChainLength : raw;
        }

        /// <summary>
        /// How far along the segment leaving marker <paramref name="from"/> the car is, in metres,
        /// clamped to the segment's own ends.
        /// </summary>
        private double ProjectOnto(int from, Vector3 point)
        {
            Vector3 a = _markers[from];
            Vector3 b = _markers[(from + 1) % Count];
            Vector3 ab = b - a;

            float lengthSquared = ab.sqrMagnitude;
            if (lengthSquared <= 0f)
            {
                return 0.0;
            }

            float t = Vector3.Dot(point - a, ab) / lengthSquared;
            t = Mathf.Clamp01(t);
            return t * _segment[from];
        }
    }
}
