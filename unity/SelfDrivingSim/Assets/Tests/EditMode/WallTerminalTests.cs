using NUnit.Framework;
using SelfDrivingSim.Agent;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The wall terminal, tested as the pure decision it is (feature 008, T008 to T011).
    ///
    /// **These pin semantics, not wiring.** Whether `CheckTermination` calls this predicate on the
    /// right contact, with the right count, needs a car and a physics step and is verified by the
    /// end-reason counts a training run produces. What is checkable here in milliseconds is the
    /// part a later refactor could silently invert: which contact is the last one.
    ///
    /// The case that matters most is the budget of zero. Feature 008's whole comparison rests on
    /// zero reproducing feature 007 exactly, and if that drifts, every number read against
    /// `ppo_car_007_progress` is read against the wrong baseline.
    /// </summary>
    public class WallTerminalTests
    {
        [Test]
        public void A_budget_of_zero_ends_the_episode_on_the_first_contact()
        {
            // Feature 007's behaviour, and the reason the comparison is honest.
            Assert.IsTrue(WallTerminal.EndsEpisode(contacts: 1, budget: 0));
        }

        [Test]
        public void A_contact_under_budget_leaves_the_episode_live()
        {
            Assert.IsFalse(WallTerminal.EndsEpisode(contacts: 1, budget: 3));
            Assert.IsFalse(WallTerminal.EndsEpisode(contacts: 2, budget: 3));
            Assert.IsFalse(WallTerminal.EndsEpisode(contacts: 3, budget: 3));
        }

        [Test]
        public void The_contact_that_exhausts_the_budget_ends_the_episode()
        {
            Assert.IsTrue(WallTerminal.EndsEpisode(contacts: 4, budget: 3));
        }

        [Test]
        public void The_budget_is_a_count_of_contacts_survived_rather_than_contacts_allowed()
        {
            // Off by one here is the difference between three grazes and four, which is the
            // difference between two runs nobody could tell apart afterwards.
            for (int budget = 0; budget <= 5; budget++)
            {
                for (int contacts = 1; contacts <= budget; contacts++)
                {
                    Assert.IsFalse(
                        WallTerminal.EndsEpisode(contacts, budget),
                        $"contact {contacts} of a budget of {budget} should not end the episode");
                }

                Assert.IsTrue(
                    WallTerminal.EndsEpisode(budget + 1, budget),
                    $"contact {budget + 1} should end an episode with a budget of {budget}");
            }
        }

        [Test]
        public void A_negative_budget_behaves_as_zero_rather_than_as_never_ending()
        {
            // Nothing sets it negative today. The assertion exists so that a serialized field
            // somebody drags to -1 in the Inspector fails safe, ending the episode, rather than
            // producing an episode that no contact can ever stop.
            Assert.IsTrue(WallTerminal.EndsEpisode(contacts: 1, budget: -1));
        }
    }
}
