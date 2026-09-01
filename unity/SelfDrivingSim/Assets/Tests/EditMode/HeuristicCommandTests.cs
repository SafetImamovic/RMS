using NUnit.Framework;
using UnityEngine;
using SelfDrivingSim.Agent;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The delegation's two checkable properties (feature 009, T011 to T014).
    ///
    /// **These pin semantics, not wiring**, for the same reason `WallTerminalTests` says so.
    /// Whether `DrivingAgent.Heuristic` actually calls `HeuristicDriver.Decide`, and whether
    /// exactly one component reaches `CarController.ScriptedMove` in a physics step, needs a car,
    /// a track and a physics step. It cannot be asserted here at all: `DrivingAgent` derives from
    /// ML-Agents' `Agent` and this assembly deliberately does not reference ML-Agents, so the
    /// agent's type is not visible from a test. Those two properties are verified in Phase 3, by
    /// driving a training seed and watching the car follow the track rather than sit still.
    ///
    /// What is checkable in milliseconds is the part a later refactor could silently invert: the
    /// range a recorded command is allowed to carry, and who is allowed to write the command.
    /// </summary>
    public class HeuristicCommandTests
    {
        [Test]
        public void A_command_inside_the_action_space_passes_through_unchanged()
        {
            // The ordinary case. The scripted driver's steering is already normalised against
            // steerMaxDeg and its throttle is bang-bang, so almost every command lands here.
            Vector2 clamped = HeuristicCommand.Clamp(new Vector2(0.42f, -1f));

            Assert.AreEqual(0.42f, clamped.x, 1e-6f);
            Assert.AreEqual(-1f, clamped.y, 1e-6f);
        }

        [Test]
        public void A_command_outside_the_action_space_is_clamped_component_by_component()
        {
            // The case that matters for the demonstration file. The trainer validates a demo's
            // shape against the policy's action spec and not its range (research R7), so an
            // out-of-range command would be recorded without complaint and would teach the policy
            // an action it can never take.
            Vector2 clamped = HeuristicCommand.Clamp(new Vector2(3.5f, -2.25f));

            Assert.AreEqual(1f, clamped.x, 1e-6f);
            Assert.AreEqual(-1f, clamped.y, 1e-6f);
        }

        [Test]
        public void Clamping_one_component_leaves_the_other_alone()
        {
            // Component by component rather than by magnitude. A steering command at full lock
            // must not scale the throttle down with it.
            Vector2 clamped = HeuristicCommand.Clamp(new Vector2(9f, 0.3f));

            Assert.AreEqual(1f, clamped.x, 1e-6f);
            Assert.AreEqual(0.3f, clamped.y, 1e-6f);
        }

        [Test]
        public void The_scripted_driver_may_write_when_no_agent_is_present()
        {
            // Feature 005's own scenes, HeuristicTrack and HeuristicWeighted. Nothing about
            // feature 009 changes what happens there.
            Assert.IsTrue(HeuristicCommand.ScriptedDriverMayWrite(agentPresent: false, driverEnabled: true));
        }

        [Test]
        public void The_scripted_driver_may_not_write_while_the_agent_is_the_decision_source()
        {
            // FR-002, and the reason the driver is disabled rather than merely disengaged: a
            // disengaged driver still runs FixedUpdate and clears ScriptedMove, in a frame order
            // that is undefined against the agent's own write.
            Assert.IsFalse(HeuristicCommand.ScriptedDriverMayWrite(agentPresent: true, driverEnabled: true));
            Assert.IsFalse(HeuristicCommand.ScriptedDriverMayWrite(agentPresent: true, driverEnabled: false));
        }
    }
}
