namespace SelfDrivingSim.Agent
{
    /// <summary>
    /// What <c>SweepRunner</c> needs of a driver, and nothing else (feature 006, FR-023, T009).
    ///
    /// **This exists so that one runner evaluates both drivers.** The scripted driver's column and
    /// the learned driver's column have to be measured by the same code, over the same seeds, into
    /// the same row shape, or the M5 comparison is between two measurement methods as much as
    /// between two policies. Copying the runner would duplicate the seed-split loading, the track
    /// swapping, the fan handling and the timing, and the two copies would diverge the first time
    /// either was fixed.
    ///
    /// The interface is deliberately three members. Everything else the runner does it does to the
    /// track, the placer or the agent, and everything else a driver does, including deciding why a
    /// run ended and writing its own row, belongs to the driver rather than to the contract between
    /// them.
    ///
    /// Note what is **not** here: the end reason. The runner only ever asked whether a run was
    /// still going, so that is what it gets. Lifting <c>HeuristicDriver.EndReason</c> into a shared
    /// type would have put its member names into a contract shared with a driver that ends
    /// episodes for different reasons, and those names are already written into every row of
    /// <c>results/heuristic/</c>.
    /// </summary>
    public interface IRunDriver
    {
        /// <summary>
        /// True while a run is still going, false once the driver has decided it is over.
        ///
        /// The driver owns that decision. A runner with its own timeout would be a second opinion
        /// about when a run stopped, and the two would disagree exactly on the runs that are
        /// hardest to interpret.
        /// </summary>
        bool RunActive { get; }

        /// <summary>Discard any finished run and arm a fresh one, without driving it yet.</summary>
        void RestartRun();

        /// <summary>Take control of the car, or give it back.</summary>
        void SetEngaged(bool value);
    }
}
