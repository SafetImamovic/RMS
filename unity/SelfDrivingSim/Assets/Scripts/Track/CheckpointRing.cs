using System;
using System.Collections.Generic;
using UnityEngine;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Ordered progress markers around one lap (FR-027, FR-028).
    ///
    /// **There is no reward logic here and there must not be.** This class answers "how far
    /// round is the car, and is it going the right way", nothing else. The reward that reads
    /// those answers belongs to M3, and keeping the two apart is what lets the marker
    /// arithmetic be tested on its own (T056) rather than inferred from a training curve.
    ///
    /// **Contact is a method call, not a collision.** <see cref="Contact"/> is the whole
    /// state machine; <see cref="CheckpointTrigger"/> is a five-line component that turns a
    /// physics trigger into a call to it. That split is deliberate: the ordering rules are
    /// the part that can be subtly wrong, and a test that has to spawn colliders and step
    /// the physics engine to reach them is a test nobody writes.
    /// </summary>
    public class CheckpointRing : MonoBehaviour
    {
        [Tooltip("The body whose contacts count. Assigned by TrackBuilder, or set here when " +
                 "the ring is wired by hand. Left empty, any rigidbody entering a gate is " +
                 "treated as the vehicle.")]
        [SerializeField] private Rigidbody vehicle;

        private readonly List<Transform> _markers = new List<Transform>();

        /// <summary>
        /// Which markers have been taken on the current lap.
        ///
        /// Cleared at each wrap except for the marker that caused the wrap: that one stays
        /// marked, because it is the one immediately behind the car at the moment the lap
        /// rolls over. Clearing it too would open a one-marker blind spot at the start line
        /// where reversing is not detected as reversing.
        /// </summary>
        private bool[] _passed = new bool[0];

        /// <summary>How many markers the ring holds. Zero until configured.</summary>
        public int Count => _markers.Count;

        /// <summary>The markers, in progress order.</summary>
        public IReadOnlyList<Transform> Markers => _markers;

        /// <summary>The only marker that can be awarded right now (FR-027).</summary>
        public int NextIndex { get; private set; }

        /// <summary>
        /// The marker the current lap began at, meaning the first one that was expected.
        ///
        /// Zero for a car that starts on the start line, and anything at all once T058
        /// randomises the start. A lap is completed by returning here, not by reaching index
        /// zero: with a randomised start those are different events, and counting the second
        /// one would report a lap after a few metres of driving.
        /// </summary>
        public int StartIndex { get; private set; }

        /// <summary>The marker the car is driving towards, or null before configuration.</summary>
        public Transform NextMarker =>
            _markers.Count > 0 ? _markers[NextIndex % _markers.Count] : null;

        /// <summary>Markers awarded since the last reset, across all laps.</summary>
        public int AwardedCount { get; private set; }

        /// <summary>Completed laps, counted when <see cref="NextIndex"/> wraps to zero.</summary>
        public int LapCount { get; private set; }

        /// <summary>
        /// Contacts that were neither the expected marker nor a marker already taken: a gate
        /// further round the lap, reached without passing the ones in between. Reported, never
        /// awarded, because awarding it is exactly how an agent learns to cut the track.
        /// </summary>
        public int SkippedContactCount { get; private set; }

        /// <summary>
        /// The car is facing back down the track (FR-028).
        ///
        /// Set by contact with a marker already taken this lap, and cleared by the next
        /// correct one. Reported, never scored: M3 decides what a wrong-way agent is worth,
        /// and it cannot decide that if this class has already priced it in.
        ///
        /// Contact is what raises it rather than a heading test, and the accuracy that buys
        /// is bounded by the marker spacing: after a reversal the car meets the marker behind
        /// it within one interval, which is what SC-015 asks for. A heading test would fire
        /// sooner and also fire on every wide corner entry, where the nose points off the
        /// racing line for a moment without the car having turned round at all.
        /// </summary>
        public bool WrongWay { get; private set; }

        /// <summary>The last marker contacted, or -1. For the debug panel.</summary>
        public int LastContactIndex { get; private set; } = -1;

        /// <summary>
        /// A marker the car is standing inside and has not driven out of yet, or -1.
        ///
        /// This exists because of how a randomised start actually behaves. <see cref="StartAt"/>
        /// is called with the car placed AT a marker, which means placed inside its trigger
        /// volume, and Unity fires OnTriggerEnter on the first physics step for an overlap that
        /// begins by teleport just as readily as for one the car drove into. That contact is
        /// against a marker `StartAt` has just recorded as passed, so without this the very
        /// first step of every randomised start would report the car as going the wrong way
        /// before it had moved at all.
        ///
        /// It is cleared by <see cref="Exit"/> when the car leaves the gate, so it suppresses
        /// exactly one gate for exactly as long as the car is inside it.
        /// </summary>
        private int _straddling = -1;

        /// <summary>The marker the car is currently standing inside, or -1.</summary>
        public int StraddlingIndex => _straddling;

        /// <summary>
        /// Adopt a set of markers in progress order and start a fresh lap.
        ///
        /// The order of the list IS the progress order. TrackBuilder passes them in the order
        /// the file lists them, which the loader has already checked is monotonic in arc
        /// length, so ordering is never decided here.
        /// </summary>
        public void Configure(IReadOnlyList<Transform> markers, Rigidbody carBody = null)
        {
            _markers.Clear();
            if (markers != null)
            {
                _markers.AddRange(markers);
            }

            if (carBody != null)
            {
                vehicle = carBody;
            }

            _passed = new bool[_markers.Count];
            ResetProgress();
        }

        /// <summary>Back to the start line: nothing taken, no lap, not reversing.</summary>
        public void ResetProgress()
        {
            Array.Clear(_passed, 0, _passed.Length);
            NextIndex = 0;
            StartIndex = 0;
            AwardedCount = 0;
            LapCount = 0;
            SkippedContactCount = 0;
            WrongWay = false;
            LastContactIndex = -1;
            _straddling = -1;
        }

        /// <summary>
        /// Begin a lap with the car sitting AT marker <paramref name="index"/> rather than
        /// before marker zero. Used by the randomised start (T058, FR-030).
        ///
        /// The marker the car is standing on counts as taken: it is behind the car, so
        /// driving back through it is a reversal, and it is not a gate the car may be awarded
        /// for having reached. The lap is then completed by coming round to it again, which
        /// awards exactly <see cref="Count"/> markers however the start was drawn.
        /// </summary>
        public void StartAt(int index)
        {
            ResetProgress();

            if (_markers.Count == 0)
            {
                return;
            }

            index = ((index % _markers.Count) + _markers.Count) % _markers.Count;
            _passed[index] = true;

            // The car is standing in this gate, not approaching it. See _straddling.
            _straddling = index;

            StartIndex = (index + 1) % _markers.Count;
            NextIndex = StartIndex;
        }

        /// <summary>
        /// The car has left marker <paramref name="index"/>. Only meaningful for the gate it
        /// was placed inside; every other exit is ignored, so the trigger can report all of
        /// them without having to know which is which.
        /// </summary>
        public void Exit(int index)
        {
            if (index == _straddling)
            {
                _straddling = -1;
            }
        }

        /// <summary>Whether marker <paramref name="index"/> has been taken this lap.</summary>
        public bool HasPassed(int index)
        {
            return index >= 0 && index < _passed.Length && _passed[index];
        }

        /// <summary>
        /// The car has reached marker <paramref name="index"/>. Returns true only if that was
        /// the expected next one.
        ///
        /// Three outcomes, and the middle one is the reason this method exists:
        /// <list type="bullet">
        /// <item>the expected marker: awarded once, and the ring advances</item>
        /// <item>a marker already taken this lap: wrong way, nothing awarded</item>
        /// <item>anything else, meaning a gate further round: counted as skipped, nothing
        /// awarded</item>
        /// </list>
        ///
        /// A marker cannot be awarded twice, because after the award it is no longer the
        /// expected one. That is worth stating plainly: a gate is a volume the car occupies
        /// for several physics steps, and re-entering it while straddling the edge is normal.
        /// </summary>
        public bool Contact(int index)
        {
            if (index < 0 || index >= _markers.Count)
            {
                return false;
            }

            // The gate the car was set down inside is not a gate the car has reached. Ignored
            // outright rather than treated as any of the three outcomes below, until the car
            // has driven out of it.
            if (index == _straddling)
            {
                return false;
            }

            LastContactIndex = index;

            if (index != NextIndex)
            {
                if (_passed[index])
                {
                    WrongWay = true;
                }
                else
                {
                    SkippedContactCount++;
                }

                return false;
            }

            _passed[index] = true;
            AwardedCount++;
            WrongWay = false;

            NextIndex = (index + 1) % _markers.Count;
            if (NextIndex == StartIndex)
            {
                LapCount++;

                // New lap, clean slate, except for the marker just taken. See _passed.
                Array.Clear(_passed, 0, _passed.Length);
                _passed[index] = true;
            }

            return true;
        }

        /// <summary>Whether a collider belongs to the body this ring is watching.</summary>
        internal bool IsVehicle(Collider other)
        {
            if (other == null)
            {
                return false;
            }

            if (vehicle == null)
            {
                // Unconfigured: any rigidbody counts. The track holds nothing else that moves,
                // and refusing every contact would look identical to the markers not working.
                return other.attachedRigidbody != null;
            }

            return other.attachedRigidbody == vehicle;
        }
    }

    /// <summary>
    /// One gate, reporting its own index to the ring when the car drives through it.
    ///
    /// Deliberately thin. Everything it could get wrong is a wiring mistake visible in the
    /// Inspector; everything the ring could get wrong is arithmetic, and that lives where a
    /// test can reach it without physics.
    /// </summary>
    [RequireComponent(typeof(Collider))]
    public class CheckpointTrigger : MonoBehaviour
    {
        [SerializeField] private CheckpointRing ring;
        [SerializeField] private int index;

        /// <summary>This gate's position in progress order.</summary>
        public int Index => index;

        /// <summary>Called by TrackBuilder as each gate is created.</summary>
        public void Bind(CheckpointRing owner, int markerIndex)
        {
            ring = owner;
            index = markerIndex;
        }

        private void OnTriggerEnter(Collider other)
        {
            if (ring == null || !ring.IsVehicle(other))
            {
                return;
            }

            ring.Contact(index);
        }

        // Reported for every gate, though the ring only cares about one: the gate a randomised
        // start set the car down inside. Filtering here would mean this component had to know
        // which gate that was, and the ring already does.
        private void OnTriggerExit(Collider other)
        {
            if (ring == null || !ring.IsVehicle(other))
            {
                return;
            }

            ring.Exit(index);
        }
    }
}
