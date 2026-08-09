"""Reporting for the heuristic ray-following driver (feature 005).

The driver itself lives in Unity, in ``Assets/Scripts/Agent/HeuristicDriver.cs``. It writes one
row per run to ``results/heuristic/runs_<timestamp>.csv``, in the shape fixed by
``specs/005-heuristic-ray-driver/contracts/run-record.md``. Everything in this package reads
those rows and turns them into the reports the feature is judged on.

Nothing here simulates anything. The split is the same one the rest of the project uses: Unity
produces measurements, Python interprets them, and the boundary between the two is a committed
file format rather than a shared object.

Runs under ``.venv``. No torch, no Unity, no new dependency.
"""
