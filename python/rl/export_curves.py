"""Turn a training run's event files into one committed CSV.

FR-018 requires the recorded curves to survive a clean clone, while ``.gitignore`` keeps the
trainer's own output out of the repository. Both are right: event files are binary and grow with
the run, and a milestone whose evidence is "there was a curve on my machine" is not reproducible.
This module is the bridge, and the shape it writes is fixed by
``specs/006-ppo-rl-driver/contracts/curve-export.md``.

Three rules the tests enforce rather than leaving to care:

- **No smoothing.** TensorBoard smooths for display, and exporting the smoothed series would commit
  a picture instead of a measurement. Two runs smoothed at different window sizes are not
  comparable, and nothing in the file would say so.
- **No resampling.** Rows land on the trainer's own summary steps, which is why ``summary_freq`` is
  pinned in ``config/ppo_car.yaml``. A curve resampled to a nicer grid is a curve nobody can line
  up against another run.
- **Absent is empty, not zero.** A series the trainer never emitted writes as an empty field. Zero
  is a value a loss can legitimately take, and an aggregate that averages absent points as zeros
  reports a run that did not happen.

The six per-term reward series are this feature's own, added through ``StatsRecorder`` on the Unity
side. They are the reason the export exists at all: a total that rises does not say which term
raised it, and a flat ``reward/checkpoint`` beneath a rising total is a policy collecting speed and
step reward without going anywhere.

Runs under ``.venv-mlagents``.

Usage::

    python -m python.rl.export_curves results/ppo_car_v01 --out results/rl/curves/ppo_car_v01.csv
"""
