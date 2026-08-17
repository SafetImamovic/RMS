"""Reporting for the PPO reinforcement learning driver (feature 006, M3).

The agent itself lives in Unity, in ``Assets/Scripts/Agent/DrivingAgent.cs``, and the training is
done by ``mlagents-learn`` in the separate ``.venv-mlagents`` environment. Nothing in this package
trains anything or talks to Unity. It reads what the trainer left behind and turns it into the two
artifacts M3 is judged on: a committed curve per run, and the learned column of the M5 comparison.

The split is the one the rest of the project already uses. Unity and the trainer produce
measurements, Python interprets them, and the boundary between the two is a committed file format
rather than a shared object.

**Two environments, on purpose.** ``export_curves`` runs under ``.venv-mlagents``, because the
event-file reader it needs ships with the trainer's own TensorBoard dependency and adds nothing to
the pinned environment. ``report`` runs under ``.venv``, because it reuses ``python.eda.stats`` and
``python.track.compare_drive``, which is how the learned column ends up described by exactly the
same functions that described the human column in M1 and the BC column in M4.
"""
