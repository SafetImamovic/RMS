namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// When a barrier contact ends the episode (feature 008).
    ///
    /// **A plain static class rather than a member of <c>DrivingAgent</c>, and that is the point.**
    /// <c>DrivingAgent</c> derives from ML-Agents' <c>Agent</c>, so a predicate living there can
    /// only be called from an assembly that references ML-Agents, and the EditMode test assembly
    /// deliberately does not. The same reasoning already put the reward arithmetic in
    /// <see cref="RewardModel"/>: the part that decides what the policy learns should be checkable
    /// without a scene, a trainer or a package reference.
    ///
    /// **The wall row of the reward table has two halves and only one has ever been tested.**
    /// Feature 006's `ppo_car_wall_lo` moved the penalty from -5.0 to -1.0 and left the terminal
    /// alone, so it is evidence about the weight. In every M3 run the episode still ended at the
    /// first contact, in both arms of every comparison.
    /// </summary>
    public static class WallTerminal
    {
        /// <summary>
        /// Whether the contact just handled is the one that ends the episode.
        /// </summary>
        /// <param name="contacts">Contacts this episode, including the one being handled, so a
        /// budget of zero ends the episode on the first contact and reproduces feature 007
        /// exactly.</param>
        /// <param name="budget">How many contacts the episode survives. Counts contact EVENTS
        /// rather than steps, because <c>WallSensor</c> raises <c>OnCollisionEnter</c> once when
        /// the colliders begin touching and not again until they separate.</param>
        public static bool EndsEpisode(int contacts, int budget)
        {
            return contacts > budget;
        }
    }
}
