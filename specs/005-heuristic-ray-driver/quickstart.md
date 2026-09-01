# Quickstart: Heuristic Ray-Following Driver

How to reproduce every number this feature reports, from a clean checkout. Constitution
Principle VI requires this file to stay literally correct: if a command changes, it changes here in
the same feature.

Commands are PowerShell, matching the rest of the project.

**Walked end to end at T048, and every figure below is now measured.** The file was written before
the implementation existed and every figure in it was a prediction; the walk falsified four
commands and two tables. What each of them said before is kept in place rather than deleted, so a
reader can see which predictions this feature got wrong. That is the third feature running in which
the walk falsified something.

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

**Walked:** correct, and idempotent. Re-running it on a clean tree leaves `git diff` empty, which
is worth more than the file being written: a step in a reproduction recipe that dirties the tree
every time it runs gets skipped, and then it stops being reproduced at all.

```powershell
pytest python/tests/test_sensing_mirror.py
```

The mirror test is the point of the block: it fails if the exported file and `config.py` disagree,
which is the drift nothing previously checked. **Walked: 6 passed in 0.07 s.**

## 2. Drive one seed

**Corrected.** This section said to open `Track.unity`, enable `HeuristicDriver` on the `Car`
object and choose a controller in the Inspector. That is not how it was built. FR-007 asks for the
controller to be selectable without editing anything, so:

Open `unity/SelfDrivingSim/Assets/Scenes/HeuristicWeighted.unity` and press Play. Set the seed on
the track builder **before** pressing Play, because the builder runs in `Awake`.

The tuner panel is top left, `G` hides it. The first toolbar picks the controller, the second picks
how the command is shaped, and the sliders move the reaction knobs live. **Changing the controller
restarts the run on purpose**: a run that switched halfway would write one run-record row
describing two controllers, and both smoothness measures would be computed over a window in which
the thing being measured changed.

`HeuristicTrack.unity` is the same scene for the naive controller. Both are kept, because a
demonstration assembled by ticking boxes is one nobody repeats the same way twice.

The vehicle HUD shows which source has the wheel. Exactly one of keyboard, `ScriptedDriver` and
`HeuristicDriver` is in control at any moment (FR-004), and `HeuristicDriver` refuses to engage
while a scripted manoeuvre is running rather than fighting it for the same field.

Each completed lap still prints its `LapReport` line, unchanged from feature 003, and now also
appends a row to `results/heuristic/runs_<timestamp>.csv` and a per-step trace beside it.

**Was predicted:** `WeightedAverage` completes the lap; `MostOpen` may complete it while visibly
sawing at the wheel, and may not complete it at all.

**Measured:** `WeightedAverage` completes it, 27.4 s on training seed 1. `MostOpen` does not
complete it on any of the 34 training seeds under any of three geometries, **0 of 102**, and it
does not saw at the wheel at all. It commits to one wrong direction and holds it into the barrier.

## 3. Compare the two controllers

```powershell
# In Unity: add SweepRunner to the scene, seedSet = Train, timeScale = 2, runOnStart = true,
# fans = the arrangements to compare, press Play.
# Writes results/heuristic/runs_<timestamp>.csv, one row per run.

.venv\Scripts\Activate.ps1
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv
```

**Corrected: it writes nothing.** This section said the reporter writes
`results/heuristic/comparison.md`. It prints to stdout, and the reports that are kept are written
by hand from what it printed, the way `results/heuristic/us4_steering.md` was. Run with no
arguments it reads the newest `runs_*.csv` in `results/heuristic`.

**The prediction this feature exists to test, from research R2.** The rays sit 15 degrees apart and
steering saturates at 25, so `MostOpen` can only command three distinct magnitudes: 0, 0.6 and 1.0.
Everything between is unreachable, so it cannot hold a mid-corner line and must alternate. With the
3.7 per second rate limit, traversing one 0.6 step takes about 162 ms, so the oscillation should
land near 3 Hz.

| Measure | `MostOpen`, predicted | measured | `WeightedAverage`, predicted | measured |
|---|---|---|---|---|
| \|delta steer\| P95 at 14.08 Hz | several times higher | **0.5824**, twelve times | comparable to a human lap | **0.0496**, a sixth of the human 0.30 |
| Steering sign changes per second | near 3 | **0.0080** | low | **0.2370** |
| Completion rate | unknown, possibly acceptable | **0 of 34** | higher | **34 of 34** |

**The prediction is falsified, and the falsification is the finding.** The quantisation argument
was right about the cause and wrong about the consequence. `MostOpen` does not oscillate: its P95
is exactly 0.6000, one ray step, so the quantum shows up as a literal quantum rather than as a
3 Hz saw, and its reversal rate is near zero because it does not change its mind. This was
falsified on two independent instruments, the smoothness measure and the run record, before it was
written down.

**If `MostOpen` performs acceptably, that is the finding and it gets written up as one.** It does
not: it never finishes. The smoothed controller is therefore justified on measured merits.

The report states the two smoothness measures and the outcome measures separately and does not
collapse them into a winner (FR-009). A controller that steers more smoothly and completes fewer
laps is a real result, and section 6 is the case where that actually happened.

## 4. Measure the noise floor before reading any comparison

```powershell
# In Unity: same seed, same controller, several runs into one file.
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv `
    --spread results\heuristic\runs_<repeats>.csv
```

**Corrected: the flag is `--spread`, not `--repeat-check`.** `--repeat-check` was never
implemented and exits with `unrecognized arguments`. Passing a separate file is the useful shape:
the repeats and the comparison live in different files, and the noise floor from one is applied to
the other. With no `--spread`, the spread is taken from the runs themselves and is reported as
unmeasured when nothing was repeated.

**Nothing in section 3 or 5 can be interpreted before this number exists.** FR-015 requires a
difference between configurations to exceed run-to-run variation before it is called a finding, and
feature 004 established the pattern in its R13: measure the tolerance, do not assert determinism.

The driver runs in `FixedUpdate`, on the physics clock rather than the frame clock, so the spread
should be small or zero. **Should is not a measurement, and it was not zero.** Five runs of seed 1:

| column | mean | range | sd |
|---|---|---|---|
| `lap_time_s` | 27.3080 | **0.1600** | 0.0593 |
| `steer_p95_dsteer` | 0.0483 | **0.0063** | 0.0026 |
| `steer_sign_changes_per_s` | 0.1466 | 0.0008 | 0.0003 |

**Do not use the 0.0008.** All five runs recorded exactly four reversals, so that column's spread
is lap-time jitter dividing the same integer. The measure cannot move by less than one reversal,
which over a 27.3 s lap is **0.0366 per second**. The reporter uses the larger of the two, and
reading the observed range there would call a quantisation step a finding.

## 5. Sweep the sensing geometry

```powershell
# In Unity: SweepRunner iterates configurations and seeds inside one Play session.
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv `
    --spread results\heuristic\runs_<repeats>.csv
```

**Corrected: there is no `--sweep` flag and none is needed.** The reporter groups by controller
**and** sensing configuration always, so a file holding several arrangements reports them
side by side without being asked.

The open question, from feature 003's T059: seven of the thirteen rays reported essentially the
same 3 m lateral distance in a 6 m corridor, while the forward cone that carries every cornering
decision held three. T062 saw the same shape at the seed 1004 spawn, where the two perpendicular
rays summed to the track width and the middle of the fan carried all the variation.

**Now tested. Nothing dominates.** All four arrangements complete 34 of 34, and the trade is speed
against smoothness:

| Fan | Spacing | Lap time | \|dsteer\| P95 |
|---|---|---|---|
| 13 / 180 deg | 15.0 | 26.508 | **0.0500** |
| 25 / 180 deg | 7.5 | 23.655 | 0.0656 |
| 13 / 120 deg | 10.0 | 22.783 | 0.1156 |
| 13 / 90 deg | 7.5 | **22.043** | 0.1341 |

Lap time follows the **spacing** and roughness follows the **fan width**, which is not what
"sweeping the angular width of the fan" sounds like it measures: varying the field of view at a
fixed ray count varies both at once. 25 over 180 is the row that separates them. 13 over 180 is
kept as a measured decision, not left alone by default.

**Budget. The prediction was wrong in both directions and SC-004 fails.**

| Time scale | One configuration, predicted from a 34.3 s lap | measured |
|---|---|---|
| 1x | 19.4 min | not run |
| 2x | not predicted | **7.56 min** (6.50 at 120 deg, 6.29 at 90) |
| 4x | 4.9 min | 3.80 min, but measuring the frame clock |

The lap is 26.5 s and not 34.3, which helps, and acceleration is not free, which hurts more.
**SC-004's five minutes and the correctness of the numbers cannot both be had**: the budget needs
at least 3.1x and 2x is the fastest scale at which the measurements reproduce. Recorded as a
failure rather than worked around. The cause is that `CarController` integrates the steering rate
limit in `Update`, against the frame clock; moving it to `FixedUpdate` is a change to the vehicle
and outside this feature's scope.

`Time.timeScale` rises; `Time.fixedDeltaTime` does **not**, because a coarser physics step would
mean the sweep measured the step size rather than the geometry. `Time.maximumDeltaTime` rises with
it, or Unity clamps the steps per frame and the run quietly falls back toward real time.

**Verify the acceleration before trusting it.** Run one seed at the swept scale and at 1x and
confirm the outcome matches. A sweep that is fast and wrong is worse than one that is slow.

The sweep runs on the **34 training seeds only**. Choosing a sensing geometry by measuring on the
evaluation seeds would fit the environment to the tracks the learning agent is later judged on, and
the split exists precisely so that cannot happen.

## 6. The steering distribution, and the comparison with BC

```powershell
python -m python.heuristic.report results\heuristic\runs_<timestamp>.csv `
    --spread results\heuristic\runs_<repeats>.csv `
    --traces results\heuristic\us4
```

`--traces` pools the per-step traces in a directory into the two distributions M5 needs, in the
same shape features 002 and 004 use, and then places the scripted driver beside feature 004's BC
column read from `results/bc/run_bc_balanced_v01/distributions.json`.

**Measured, and the scripted driver wins part of it.** On per-step `|delta steering|` at 14.08 Hz,
`WeightedAverage` reads 0.0157 mean and 0.0465 P95 against BC's 0.0248 and 0.0692, and loses in the
tail at 0.1649 against 0.1121. Both halves are printed together.

What that is not: BC never drives, so lap completion has no learned column and 34 of 34 is not a
win; the two drivers are measured on different roads; and the clocks agree on track1 by
construction and not on track2. The report prints all three every time. Written up in
`results/heuristic/us4_steering.md`.

## Tests

```powershell
pytest python/tests
# Unity: Window > General > Test Runner > EditMode > Run All
```

Do not add `-q`: `pytest.ini` already sets `addopts = -q`, so a second one makes it `-qq` and
suppresses the pass count. This project has now written that mistake into three separate files.
**And do not pipe it through `tail`**: with `-q` the progress lines are bare dots until the summary
arrives, so a truncated tail looks like a smaller total. T046 read 179 that way out of a 323-test
run.

Baseline before this feature: **280 passed, 3 skipped** under `.venv`, **334 passed** under
`.venv-bc`.

After it: **323 passed, 3 skipped** under `.venv`, **377 passed** under `.venv-bc`. Both grew by
exactly 43, which is `test_heuristic_report.py` plus `test_sensing_mirror.py`. Unity EditMode:
**93 passed, 0 failed** in 3.21 s.

The EditMode tests cover both controllers as pure functions, including the two degenerate readings
from research R9: an all-clear fan, where every ray reads 1.000 and the correct answer is to hold
heading, and a perfectly symmetric fan, where `MostOpen` must break the tie toward the centre ray
rather than by array order. The second is a bug that appears only on symmetric readings and would
otherwise be blamed on the track.

## What this feature does not do

- It does **not** satisfy feature 003's human keyboard lap (FR-017). A scripted lap proves the
  track is completable by something; that is a different claim from the vehicle being drivable by a
  person, and T051 already covers the second. This feature's own T020 keyboard check is still open
  for the same reason: it needs a person at the keyboard.
- It does **not** adopt a new sensing arrangement. It measures whether one is warranted and records
  the answer, which is that nothing dominates. Applying one is a separate change, with its own
  consequences for every sensing result already measured and any model trained against the old fan.
- It does **not** optimise for lap time. A tuned heuristic stops being a baseline and becomes a
  competitor, and the comparison it supports would then be between two tuned systems. 13 over 180
  is kept although 13 over 90 laps 4.5 s faster, for exactly this reason.
