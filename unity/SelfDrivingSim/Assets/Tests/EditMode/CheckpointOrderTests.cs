using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using SelfDrivingSim.Track;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The progress arithmetic, checked without physics (T056, FR-027, FR-028).
    ///
    /// <see cref="CheckpointRing.Contact"/> is a plain method precisely so these can be
    /// written. Driving a real lap to test the ordering rules would test the collider sizes,
    /// the trigger layer, the physics step and the driver at the same time, and a failure
    /// would not say which of them broke.
    ///
    /// The count is the project's own <c>N_CHECKPOINTS</c>, 24. The last test states it
    /// explicitly rather than deriving it from the ring, because "the number awarded equals
    /// the number the ring holds" is true of an empty ring too.
    /// </summary>
    public class CheckpointOrderTests
    {
        private const int NCheckpoints = 24;

        private GameObject _root;
        private CheckpointRing _ring;

        [SetUp]
        public void SetUp()
        {
            _root = new GameObject("ring under test");
            _ring = _root.AddComponent<CheckpointRing>();
            _ring.Configure(Markers(NCheckpoints));
        }

        [TearDown]
        public void TearDown()
        {
            if (_root != null)
            {
                Object.DestroyImmediate(_root);
            }
        }

        /// <summary>
        /// Markers on a circle, in progress order. The positions are never read by the
        /// ordering rules, but a ring of transforms all sitting on the origin would hide a
        /// future change that started using them.
        /// </summary>
        private List<Transform> Markers(int count)
        {
            var markers = new List<Transform>(count);
            for (int i = 0; i < count; i++)
            {
                var marker = new GameObject($"marker {i:D2}");
                marker.transform.SetParent(_root.transform);

                float theta = 2f * Mathf.PI * i / count;
                marker.transform.position = new Vector3(30f * Mathf.Cos(theta), 0f,
                                                        30f * Mathf.Sin(theta));
                markers.Add(marker.transform);
            }

            return markers;
        }

        /// <summary>Drive from the current expected marker through <paramref name="n"/> gates.</summary>
        private void DriveForward(int n)
        {
            for (int i = 0; i < n; i++)
            {
                Assert.IsTrue(_ring.Contact(_ring.NextIndex),
                              $"gate {i} in order was refused");
            }
        }

        // -----------------------------------------------------------------------------------
        // In order
        // -----------------------------------------------------------------------------------

        [Test]
        public void StartsAtTheFirstMarkerWithNothingTaken()
        {
            Assert.AreEqual(NCheckpoints, _ring.Count);
            Assert.AreEqual(0, _ring.NextIndex);
            Assert.AreEqual(0, _ring.AwardedCount);
            Assert.AreEqual(0, _ring.LapCount);
            Assert.IsFalse(_ring.WrongWay);
        }

        [Test]
        public void InOrderContactAwardsEachMarkerOnce()
        {
            for (int i = 0; i < NCheckpoints; i++)
            {
                Assert.AreEqual(i, _ring.NextIndex, "the expected marker did not advance");
                Assert.IsTrue(_ring.Contact(i), $"marker {i} was not awarded in order");
                Assert.AreEqual(i + 1, _ring.AwardedCount);
            }
        }

        /// <summary>
        /// A gate is a volume the car occupies for several physics steps, so re-entering one
        /// while straddling its edge is normal driving and must not count twice.
        /// </summary>
        [Test]
        public void AMarkerCannotBeAwardedTwice()
        {
            Assert.IsTrue(_ring.Contact(0));
            Assert.IsFalse(_ring.Contact(0), "the same gate was awarded a second time");
            Assert.AreEqual(1, _ring.AwardedCount);
        }

        // -----------------------------------------------------------------------------------
        // Out of order
        // -----------------------------------------------------------------------------------

        /// <summary>
        /// Reaching a gate further round the lap without passing the ones between it is how
        /// an agent learns to cut the track. Nothing is awarded and the ring does not advance.
        /// </summary>
        [Test]
        public void OutOfOrderContactAwardsNothing()
        {
            Assert.IsFalse(_ring.Contact(5), "a gate five ahead was awarded");
            Assert.AreEqual(0, _ring.AwardedCount);
            Assert.AreEqual(0, _ring.NextIndex, "an unawarded contact advanced the ring");
            Assert.AreEqual(1, _ring.SkippedContactCount);
            Assert.IsFalse(_ring.WrongWay, "a gate ahead is a shortcut, not a reversal");
        }

        [Test]
        public void ASkippedGateIsStillAvailableWhenReachedInOrder()
        {
            Assert.IsFalse(_ring.Contact(3));
            DriveForward(4);

            Assert.AreEqual(4, _ring.AwardedCount);
            Assert.IsTrue(_ring.HasPassed(3), "gate 3 was never awarded on the way past");
        }

        // -----------------------------------------------------------------------------------
        // Wrong way (FR-028)
        // -----------------------------------------------------------------------------------

        [Test]
        public void ContactWithAnAlreadyPassedMarkerSetsWrongWay()
        {
            DriveForward(4);
            Assert.IsFalse(_ring.WrongWay);

            Assert.IsFalse(_ring.Contact(3), "an already-taken gate was awarded again");
            Assert.IsTrue(_ring.WrongWay, "driving back through gate 3 was not reported");
            Assert.AreEqual(4, _ring.AwardedCount, "a wrong-way contact changed the count");
        }

        [Test]
        public void AnyAlreadyPassedMarkerSetsWrongWayNotOnlyTheLastOne()
        {
            DriveForward(6);
            Assert.IsFalse(_ring.Contact(1));
            Assert.IsTrue(_ring.WrongWay);
        }

        [Test]
        public void GoingForwardAgainClearsWrongWay()
        {
            DriveForward(4);
            _ring.Contact(3);
            Assert.IsTrue(_ring.WrongWay);

            Assert.IsTrue(_ring.Contact(4), "the expected gate was refused after a reversal");
            Assert.IsFalse(_ring.WrongWay, "resuming the right way round did not clear the flag");
        }

        /// <summary>
        /// The seam at the start line, which the per-lap bookkeeping could easily open a hole
        /// in: the lap wraps, the taken markers are cleared, and the gate immediately behind
        /// the car must still count as taken or a reversal there goes unreported.
        /// </summary>
        [Test]
        public void ReversingAcrossTheStartLineIsStillWrongWay()
        {
            DriveForward(NCheckpoints);
            Assert.AreEqual(1, _ring.LapCount);
            Assert.AreEqual(0, _ring.NextIndex);

            Assert.IsFalse(_ring.Contact(NCheckpoints - 1));
            Assert.IsTrue(_ring.WrongWay,
                          "reversing through the last gate of the previous lap was not reported");
        }

        // -----------------------------------------------------------------------------------
        // Laps
        // -----------------------------------------------------------------------------------

        [Test]
        public void TheIndexWrappingIncrementsTheLapCount()
        {
            DriveForward(NCheckpoints - 1);
            Assert.AreEqual(0, _ring.LapCount, "a lap was counted before the last gate");

            Assert.IsTrue(_ring.Contact(NCheckpoints - 1));
            Assert.AreEqual(1, _ring.LapCount);
            Assert.AreEqual(0, _ring.NextIndex, "the ring did not wrap to the first gate");
        }

        [Test]
        public void ASecondLapCountsAgainAndKeepsAwarding()
        {
            DriveForward(2 * NCheckpoints);

            Assert.AreEqual(2, _ring.LapCount);
            Assert.AreEqual(2 * NCheckpoints, _ring.AwardedCount);
        }

        /// <summary>SC-014, as arithmetic: one lap awards exactly the markers on the track.</summary>
        [Test]
        public void OneSyntheticLapAwardsExactlyNCheckpoints()
        {
            DriveForward(NCheckpoints);

            Assert.AreEqual(NCheckpoints, _ring.AwardedCount);
            Assert.AreEqual(0, _ring.SkippedContactCount);
            Assert.IsFalse(_ring.WrongWay);
        }

        // -----------------------------------------------------------------------------------
        // Randomised start (T058, FR-030)
        // -----------------------------------------------------------------------------------

        /// <summary>
        /// A lap from a randomised start still awards exactly the markers on the track. It is
        /// the property T060 is checked against, and it is the one an offset start could
        /// quietly break: counting a lap on reaching index zero would report one after a few
        /// metres and leave the awarded total short.
        /// </summary>
        [Test]
        public void ALapFromAnOffsetStartStillAwardsNCheckpoints()
        {
            const int start = 17;
            _ring.StartAt(start);
            _ring.Exit(start);

            Assert.AreEqual(start + 1, _ring.NextIndex);
            Assert.IsTrue(_ring.HasPassed(start), "the marker the car stands on is not behind it");
            Assert.AreEqual(0, _ring.LapCount);

            DriveForward(NCheckpoints);

            Assert.AreEqual(NCheckpoints, _ring.AwardedCount);
            Assert.AreEqual(1, _ring.LapCount, "the lap did not complete at the marker it began at");
            Assert.AreEqual(start + 1, _ring.NextIndex);
            Assert.AreEqual(0, _ring.SkippedContactCount);
        }

        /// <summary>
        /// The car is placed AT a marker, meaning inside its trigger volume, and Unity fires
        /// OnTriggerEnter for an overlap that begins by teleport exactly as it does for one
        /// the car drove into. Without the straddle suppression that first contact lands on a
        /// marker `StartAt` has just recorded as passed, so every randomised start would
        /// report the car as reversing before it had moved a metre.
        /// </summary>
        [Test]
        public void TheGateTheCarIsSetDownInsideDoesNotReportWrongWay()
        {
            _ring.StartAt(9);
            Assert.AreEqual(9, _ring.StraddlingIndex);

            Assert.IsFalse(_ring.Contact(9), "the gate under the car was awarded");
            Assert.IsFalse(_ring.WrongWay, "sitting on the start marker read as reversing");
            Assert.AreEqual(0, _ring.SkippedContactCount);
        }

        [Test]
        public void ReversingIntoTheStartGateAfterLeavingItIsWrongWay()
        {
            _ring.StartAt(9);
            _ring.Exit(9);
            Assert.AreEqual(-1, _ring.StraddlingIndex);

            Assert.IsFalse(_ring.Contact(9));
            Assert.IsTrue(_ring.WrongWay, "driving back into the start gate was not reported");
        }

        /// <summary>Leaving some other gate must not clear the suppression on this one.</summary>
        [Test]
        public void ExitingADifferentGateLeavesTheStraddleIntact()
        {
            _ring.StartAt(9);
            _ring.Exit(4);
            Assert.AreEqual(9, _ring.StraddlingIndex);
            Assert.IsFalse(_ring.WrongWay);
        }

        [Test]
        public void StartAtWrapsAnIndexPastTheEnd()
        {
            _ring.StartAt(NCheckpoints - 1);
            Assert.AreEqual(0, _ring.NextIndex);
            Assert.AreEqual(0, _ring.StartIndex);
        }

        // -----------------------------------------------------------------------------------
        // Bounds
        // -----------------------------------------------------------------------------------

        [Test]
        public void ContactWithAnIndexOffTheRingIsIgnored()
        {
            Assert.IsFalse(_ring.Contact(-1));
            Assert.IsFalse(_ring.Contact(NCheckpoints));
            Assert.AreEqual(0, _ring.AwardedCount);
            Assert.AreEqual(0, _ring.SkippedContactCount);
        }

        [Test]
        public void ResetProgressReturnsTheRingToTheStartLine()
        {
            DriveForward(5);
            _ring.Contact(2);
            _ring.ResetProgress();

            Assert.AreEqual(0, _ring.NextIndex);
            Assert.AreEqual(0, _ring.AwardedCount);
            Assert.AreEqual(0, _ring.LapCount);
            Assert.IsFalse(_ring.WrongWay);
            Assert.IsFalse(_ring.HasPassed(0));
        }
    }
}
