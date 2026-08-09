# Quickstart: Heuristic Ray-Following Driver

How to reproduce every number this feature reports, from a clean checkout. Constitution
Principle VI requires this file to stay literally correct: if a command changes, it changes here in
the same feature.

Commands are PowerShell, matching the rest of the project.

**This file is written before the implementation exists.** Every expected figure below is a
prediction from research, not a measurement, and each is marked as such. Walking this quickstart at
the end of the feature is a task in its own right, and the last two features both found that the
walk falsified something.

## Prerequisites

Feature 003 complete and merged: the track scene, the accepted seeds, the sensing and the
checkpoint counting all come from it. If `pytest python/tests` is green and
`unity/SelfDrivingSim/Assets/Tracks/seed_1.json` exists, this runs.

No new Python dependency. No new Unity package.

## 1. Export the sensing block

```powershell
.venv\Scripts\Activate.ps1
python -m python.track.vehicle
```

Rewrites `unity/SelfDrivingSim/Assets/Tracks/vehicle_profile.json` with a third block beside
`profile` and `envelope`:

```json
"sensing": { "ray_count": 13, "ray_fov_deg": 180.0, "ray_length_m": 20.0 }
```

The values do not change. Only where `CarAgent` reads them from moves, so nothing measured in
feature 003 is invalidated. See `contracts/sensing-block.md`.

```powershell
pytest python/tests/test_sensing_mirror.py
```

The mirror test is the point of the block: it fails if the exported file and `config.py` disagree,
which is the drift nothing previously checked.

## 2. Drive one seed

Open `unity/SelfDrivingSim/Assets/Scenes/Track.unity`, set the seed on the track builder **before**
pressing Play (the builder runs in `Awake`), enable `HeuristicDriver` on the `Car` object, choose a
controller, press Play.

The vehicle HUD shows which source has the wheel. Exactly one of keyboard, `ScriptedDriver` and
`HeuristicDriver` is in control at any moment (FR-004), and `HeuristicDriver` refuses to engage
while a scripted manoeuvre is running rather than fighting it for the same field.

Each completed lap still prints its `LapReport` line, unchanged from feature 003.

**Expected, predicted not measured:** `WeightedAverage` completes the lap. `MostOpen` may complete
it while visibly sawing at the wheel, and may not complete it at all. Both outcomes are results.

## 3. Compare the two controllers

```powershell
# In Unity: set the sweep runner to both controllers over the training seeds, press Play.
# Writes results/heuristic/runs_<timestamp>.csv, one row per run.

.venv\Scripts\Activate.ps1
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv
```

Writes `results/heuristic/comparison.md`.

**The prediction this feature exists to test, from research R2.** The rays sit 15 degrees apart and
steering saturates at 25, so `MostOpen` can only command three distinct magnitudes: 0, 0.6 and 1.0.
Everything between is unreachable, so it cannot hold a mid-corner line and must alternate. With the
3.7 per second rate limit, traversing one 0.6 step takes about 162 ms, so the oscillation should
land near 3 Hz.

| Measure | `MostOpen`, predicted | `WeightedAverage`, predicted |
|---|---|---|
| \|delta steer\| P95 at 14.08 Hz | several times higher | comparable to a human lap |
| Steering sign changes per second | near 3 | low |
| Completion rate | unknown, possibly acceptable | higher |

**If `MostOpen` performs acceptably, that is the finding and it gets written up as one.** The
smoothed controller is then justified on its measured merits or not adopted. A quickstart that
promised the expected answer would be the thing this project keeps catching itself doing.

The report states the two smoothness measures and the outcome measures separately and does not
collapse them into a winner (FR-009). A controller that steers more smoothly and completes fewer
laps is a real result.

## 4. Measure the noise floor before reading any comparison

```powershell
# In Unity: same seed, same controller, three runs.
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv --repeat-check
```

Reports the spread of lap time and both smoothness measures across identical runs.

**Nothing in section 3 or 5 can be interpreted before this number exists.** FR-015 requires a
difference between configurations to exceed run-to-run variation before it is called a finding, and
feature 004 established the pattern in its R13: measure the tolerance, do not assert determinism.

The driver runs in `FixedUpdate`, on the physics clock rather than the frame clock, so the spread
should be small or zero. Should is not a measurement.

## 5. Sweep the sensing geometry

```powershell
# In Unity: the runner iterates configurations and seeds inside one Play session.
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv --sweep
```

The open question, from feature 003's T059: seven of the thirteen rays reported essentially the
same 3 m lateral distance in a 6 m corridor, while the forward cone that carries every cornering
decision held three. T062 saw the same shape at the seed 1004 spawn, where the two perpendicular
rays summed to the track width and the middle of the fan carried all the variation.

Nothing has tested whether that matters.

**Budget, measured from the observed 34.3 s lap over 34 training seeds:**

| Time scale | One configuration |
|---|---|
| 1x | 19.4 min |
| 4x | 4.9 min |
| 8x | 2.4 min |

SC-004 asks for under five minutes, so the sweep runs accelerated. `Time.timeScale` rises;
`Time.fixedDeltaTime` does **not**, because a coarser physics step would mean the sweep measured
the step size rather than the geometry. `Time.maximumDeltaTime` rises with it, or Unity clamps the
steps per frame and the run quietly falls back toward real time.

**Verify the acceleration before trusting it.** Run one seed at the swept scale and at 1x and
confirm the outcome matches. A sweep that is fast and wrong is worse than one that is slow.

The sweep runs on the **34 training seeds only**. Choosing a sensing geometry by measuring on the
evaluation seeds would fit the environment to the tracks the learning agent is later judged on, and
the split exists precisely so that cannot happen.

## Tests

```powershell
pytest python/tests
# Unity: Window > General > Test Runner > EditMode > Run All
```

Do not add `-q`: `pytest.ini` already sets `addopts = -q`, so a second one makes it `-qq` and
suppresses the pass count. This project has now written that mistake into three separate files.

Baseline before this feature: **280 passed, 3 skipped** under `.venv`, **334 passed** under
`.venv-bc`.

The EditMode tests cover both controllers as pure functions, including the two degenerate readings
from research R9: an all-clear fan, where every ray reads 1.000 and the correct answer is to hold
heading, and a perfectly symmetric fan, where `MostOpen` must break the tie toward the centre ray
rather than by array order. The second is a bug that appears only on symmetric readings and would
otherwise be blamed on the track.

## What this feature does not do

- It does **not** satisfy feature 003's human keyboard lap (FR-017). A scripted lap proves the
  track is completable by something; that is a different claim from the vehicle being drivable by a
  person, and T051 already covers the second.
- It does **not** adopt a new sensing arrangement. It measures whether one is warranted and records
  the answer. Applying it is a separate change, with its own consequences for every sensing result
  already measured and any model trained against the old fan.
- It does **not** optimise for lap time. A tuned heuristic stops being a baseline and becomes a
  competitor, and the comparison it supports would then be between two tuned systems.
