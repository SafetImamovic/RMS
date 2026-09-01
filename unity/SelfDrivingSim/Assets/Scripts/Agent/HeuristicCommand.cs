using UnityEngine;

namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// The scripted driver's command as the agent's action pair (feature 009).
    ///
    /// **A plain static class for the same reason <see cref="WallTerminal"/> is one.**
    /// <see cref="DrivingAgent"/> derives from ML-Agents' <c>Agent</c>, and
    /// <c>SelfDrivingSim.EditModeTests</c> deliberately does not reference ML-Agents, so anything
    /// that has to be tested without a scene cannot live on the agent. Feature 008 hit this and
    /// put the wall predicate here; the reward arithmetic in <see cref="RewardModel"/> is the same
    /// pattern older still.
    ///
    /// **What this pins is the boundary between the two drivers' ranges.** The scripted driver
    /// returns a <c>Vector2</c> it built from a steering angle and a bang-bang throttle, and the
    /// agent's action space is two continuous values in <c>[-1, 1]</c>. A demonstration recorded
    /// from a command outside that range would teach the policy an action it can never take, and
    /// the trainer would not complain, because a demonstration is not validated against the range,
    /// only against the shape (specs/009-imitation-warm-start/research.md, R7).
    /// </summary>
    public static class HeuristicCommand
    {
        /// <summary>
        /// Clamp the scripted driver's command into the action space, component by component.
        ///
        /// The same clamp <see cref="DrivingAgent.OnActionReceived"/> applies to a policy's output,
        /// applied here to the expert's, so both drivers reach the wheels through one range.
        /// </summary>
        public static Vector2 Clamp(Vector2 move)
        {
            return new Vector2(
                Mathf.Clamp(move.x, -1f, 1f),
                Mathf.Clamp(move.y, -1f, 1f));
        }

        /// <summary>
        /// Whether the scripted driver may write <c>CarController.ScriptedMove</c> this frame.
        ///
        /// **This is feature 005's FR-004 written as a predicate rather than as a comment.**
        /// Exactly one component writes the command in any frame. While the agent is the decision
        /// source that component is <see cref="DrivingAgent.OnActionReceived"/>, so the scripted
        /// driver must not, and disengaging it is not sufficient on its own: a disengaged
        /// <see cref="HeuristicDriver"/> still runs <c>FixedUpdate</c> and clears the command, in a
        /// frame order that is undefined against the agent's. The driver is disabled outright, and
        /// this predicate is what says so in a test.
        /// </summary>
        public static bool ScriptedDriverMayWrite(bool agentPresent, bool driverEnabled)
        {
            return !agentPresent && driverEnabled;
        }
    }
}
