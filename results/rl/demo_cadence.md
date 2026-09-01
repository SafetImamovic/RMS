# The scripted driver at the agent's decision period

**Feature 009, tasks T019 to T021.** The demonstration is recorded from the scripted driver
through `DrivingAgent`'s action path, and the agent decides once every four physics steps
(`DecisionPeriod: 4`). The driver's own `FixedUpdate` runs at 50 Hz. So a `.demo` from this
project is a **12.5 Hz sampling of a 50 Hz driver**, and research R2 established that no recorder
setting changes that: the demonstration write sits inside `SendInfoToBrain`, which only runs on a
decision step.

Feature 005 measured 34 of 34 at 50 Hz. This file measures the same driver at 12.5 Hz, and the
phase was written to be allowed to fail here. **It did not fail.**

## The gate

| | feature 005, 50 Hz | this run, 12.5 Hz |
|---|---|---|
| Laps completed | **34 of 34** | **34 of 34** |
| Wall contacts | 0 | **0** |
| Lap time | 26.496 s mean, sd 0.578 | **26.266 s mean, sd 0.531** |
| \|dsteer\| P95 | 0.0496 | **0.0564** |
| Sign changes /s | 0.2370 | **0.2550** |

**Read the lap times carefully.** This scene inherited `lapsToComplete: 3` from
`Evaluation.unity`, so every run here is three laps and the run record's `lap_time_s` is the
three-lap total. The per-lap column divides by three. That is not identical to feature 005's
single-lap measurement, because only the first lap of a three-lap run begins from a standing
start, so the figure here is mildly favourable. It is close enough to say the driver is not
slower, and not exact enough to claim it is faster.

Against feature 005's own noise thresholds, measured from five repeats of one seed:

- **Lap time**, threshold 0.16 s. The per-lap difference is 0.23 s, above it, with the standing
  start caveat above. Not read as a finding.
- **\|dsteer\| P95**, threshold 0.0063. The difference is 0.0068, marginally above it. The
  steering is very slightly coarser at 12.5 Hz, which is what holding a command for four physics
  steps should do.
- **Sign changes /s**, threshold 0.0366/s. The difference is 0.0180/s, **below** it. Not a
  difference.

## Speed tracking, and the prediction that was right

Research R3 predicted the throttle would be where the cadence costs, not the steering: the
throttle is bang-bang against a `0.25 m/s` deadband, and at `brakeMs2` of about `5.85 m/s^2` one
decision is long enough for the speed to move `0.47 m/s`, which is 1.9 times the deadband. The
steering, in `Immediate` mode, is a pure function of the current rays and loses nothing to
subsampling beyond staleness.

Measured over the 34 traces, mean absolute error between `car.SpeedMs` and
`HeuristicDriver.TargetSpeedMs`:

| | value |
|---|---|
| Mean | **0.3089 m/s** |
| Standard deviation | 0.0149 |
| Range | 0.2705 to 0.3400 |
| Deadband | 0.25 m/s |

**The prediction holds and the consequence does not.** Every seed tracks its target speed worse
than the deadband, so the cadence is measurably costing the throttle, exactly where R3 said it
would. It cost zero laps and zero wall contacts. The driver is slower to settle on a speed and
still drives the track.

## Verdict

**The gate passes.** The demonstration source completes 34 of 34 at the clock it will be recorded
at, so Phase 4 is earned and `DecisionPeriod` was not touched to earn it.

## What this run also found

The first attempt at this sweep did not measure a cadence at all. It measured a sensing fault:
`CarAgent.IsSelf` compared transform roots, and `TrainingArea.prefab` makes `Car` and `Track`
siblings under one area root, so **every ray hit on the car's own barriers was discarded as the
car sensing itself**. The fan read 1.0 in all thirteen directions, which is symmetric, so the
steering controller returned exactly zero and the sight limit returned the vehicle maximum. The
car drove straight into a wall at full throttle and the trace showed `steering` at `0.00000` on
every row.

The numbers above were taken **after** that fix (`collider.transform.IsChildOf(transform)`). They
are the first measurements in this project taken by a car that can see its own track.

`Evaluation.unity` has the same layout and produced the held-out figures for features 006, 007 and
008. What that means for M3 is recorded in `DESIGN.md` and is not decided here.

## Per seed

Controller `WeightedAverage`, 13 rays over 180 degrees, `timeScale 4`, `lapsToComplete 3`,
`wallContactBudget 0`, seeds from `results/tracks/seed_split.json` train half.

| seed | laps | checkpoints | walls | end reason | 3-lap time s | per lap s | dsteer P95 | sign/s |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 of 3 | 72 | 0 | LapsCompleted | 80.798 | 26.933 | 0.0492 | 0.1733 |
| 2 | 3 of 3 | 72 | 0 | LapsCompleted | 78.099 | 26.033 | 0.0482 | 0.1537 |
| 3 | 3 of 3 | 72 | 0 | LapsCompleted | 79.059 | 26.353 | 0.0534 | 0.1771 |
| 5 | 3 of 3 | 72 | 0 | LapsCompleted | 77.799 | 25.933 | 0.0575 | 0.2571 |
| 6 | 3 of 3 | 72 | 0 | LapsCompleted | 79.779 | 26.593 | 0.0513 | 0.3761 |
| 7 | 3 of 3 | 72 | 0 | LapsCompleted | 78.699 | 26.233 | 0.0467 | 0.3050 |
| 8 | 3 of 3 | 72 | 0 | LapsCompleted | 76.719 | 25.573 | 0.0456 | 0.2608 |
| 9 | 3 of 3 | 72 | 0 | LapsCompleted | 80.059 | 26.686 | 0.0463 | 0.2499 |
| 10 | 3 of 3 | 72 | 0 | LapsCompleted | 79.859 | 26.620 | 0.0960 | 0.2255 |
| 11 | 3 of 3 | 72 | 0 | LapsCompleted | 78.819 | 26.273 | 0.0495 | 0.1523 |
| 13 | 3 of 3 | 72 | 0 | LapsCompleted | 81.318 | 27.106 | 0.0934 | 0.1722 |
| 14 | 3 of 3 | 72 | 0 | LapsCompleted | 81.358 | 27.119 | 0.0633 | 0.2459 |
| 16 | 3 of 3 | 72 | 0 | LapsCompleted | 79.919 | 26.640 | 0.0663 | 0.2503 |
| 17 | 3 of 3 | 72 | 0 | LapsCompleted | 80.279 | 26.760 | 0.0552 | 0.2492 |
| 18 | 3 of 3 | 72 | 0 | LapsCompleted | 77.199 | 25.733 | 0.0578 | 0.2462 |
| 19 | 3 of 3 | 72 | 0 | LapsCompleted | 80.499 | 26.833 | 0.0999 | 0.1491 |
| 20 | 3 of 3 | 72 | 0 | LapsCompleted | 75.579 | 25.193 | 0.0423 | 0.3970 |
| 21 | 3 of 3 | 72 | 0 | LapsCompleted | 80.718 | 26.906 | 0.0892 | 0.2478 |
| 23 | 3 of 3 | 72 | 0 | LapsCompleted | 77.779 | 25.926 | 0.0467 | 0.2315 |
| 24 | 3 of 3 | 72 | 0 | LapsCompleted | 76.499 | 25.500 | 0.0581 | 0.2615 |
| 25 | 3 of 3 | 72 | 0 | LapsCompleted | 76.759 | 25.586 | 0.0361 | 0.2997 |
| 26 | 3 of 3 | 72 | 0 | LapsCompleted | 80.179 | 26.726 | 0.0482 | 0.2495 |
| 27 | 3 of 3 | 72 | 0 | LapsCompleted | 79.139 | 26.380 | 0.0489 | 0.4045 |
| 29 | 3 of 3 | 72 | 0 | LapsCompleted | 77.639 | 25.880 | 0.0680 | 0.1804 |
| 30 | 3 of 3 | 72 | 0 | LapsCompleted | 78.679 | 26.226 | 0.0514 | 0.2543 |
| 31 | 3 of 3 | 72 | 0 | LapsCompleted | 81.478 | 27.159 | 0.0454 | 0.2578 |
| 32 | 3 of 3 | 72 | 0 | LapsCompleted | 76.819 | 25.606 | 0.0403 | 0.3385 |
| 34 | 3 of 3 | 72 | 0 | LapsCompleted | 77.179 | 25.726 | 0.0451 | 0.3629 |
| 35 | 3 of 3 | 72 | 0 | LapsCompleted | 77.079 | 25.693 | 0.0429 | 0.2595 |
| 36 | 3 of 3 | 72 | 0 | LapsCompleted | 77.319 | 25.773 | 0.0497 | 0.1811 |
| 37 | 3 of 3 | 72 | 0 | LapsCompleted | 78.519 | 26.173 | 0.0699 | 0.3057 |
| 38 | 3 of 3 | 72 | 0 | LapsCompleted | 79.539 | 26.513 | 0.0586 | 0.2389 |
| 39 | 3 of 3 | 72 | 0 | LapsCompleted | 78.339 | 26.113 | 0.0452 | 0.2554 |
| 40 | 3 of 3 | 72 | 0 | LapsCompleted | 79.619 | 26.540 | 0.0519 | 0.3015 |
