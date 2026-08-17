using UnityEngine;

namespace SelfDrivingSim.Vehicle
{
    /// <summary>
    /// Count barrier contacts for whoever is driving (feature 006, FR-006).
    ///
    /// **This duplicates counting that <c>HeuristicDriver</c> already does, and the duplication is
    /// deliberate** (research R3, DESIGN 4.5). Unity delivers <c>OnCollisionEnter</c> to every
    /// component on the object, so the two counters run independently and neither can disturb the
    /// other. Extracting the scripted driver's version into a shared component would be tidier by
    /// about fifteen lines and would change the code path that produced every row in
    /// <c>results/heuristic/</c>, which is the baseline this feature is measured against.
    ///
    /// The filter is the same one feature 005 arrived at, and it is a measurement rather than an
    /// assumption. The road sits under the WheelColliders rather than under the body, so the body
    /// collider should only ever meet a barrier; "should" is not evidence, so a contact counts only
    /// when its normal is more sideways than vertical. Counting a kerb strike or a landing as a
    /// wall contact would end episodes the reward table means to keep running.
    /// </summary>
    public class WallSensor : MonoBehaviour
    {
        /// <summary>
        /// How sideways a contact normal has to be before it counts as a wall.
        ///
        /// A wall pushes across the car and the ground pushes up it. At 0.5 the split is a
        /// 60 degree cone around vertical, which is well clear of both the road surface and the
        /// barrier faces the track generator produces.
        /// </summary>
        private const float LateralNormalMax = 0.5f;

        /// <summary>Contacts since the last <see cref="ResetCount"/>. The episode record's field.</summary>
        public int Contacts { get; private set; }

        /// <summary>
        /// True once per new contact, and false until another one happens.
        ///
        /// **Read it exactly once per step.** The reward for hitting a barrier is terminal, so the
        /// caller needs the transition rather than the state; a flag that stayed set would pay the
        /// penalty again on every step of an episode that has already ended.
        /// </summary>
        public bool TakeNewContact()
        {
            if (!_pending)
            {
                return false;
            }

            _pending = false;
            return true;
        }

        /// <summary>Clear both the count and any unread edge. Called when an episode begins.</summary>
        public void ResetCount()
        {
            Contacts = 0;
            _pending = false;
        }

        private bool _pending;

        private void OnCollisionEnter(Collision collision)
        {
            for (int i = 0; i < collision.contactCount; i++)
            {
                if (Mathf.Abs(collision.GetContact(i).normal.y) >= LateralNormalMax)
                {
                    continue;
                }

                Contacts++;
                _pending = true;
                return;
            }
        }
    }
}
