# The scripted driver's steering, and where it beats the learned one

The fourth column M5 needs, in the shape features 002 and 004 already use, plus the one
comparison against a learned driver that this feature's data actually supports.

Reproduce with:

```
python -m python.heuristic.report results/heuristic/runs_2026-08-16_17-26-51.csv \
    --spread results/heuristic/runs_2026-08-16_13-43-54.csv \
    --traces results/heuristic/us4
```

The run record and the traces are not in the repository — `.gitignore` keeps raw sweep output
out and the reports that cite it in. The two files above are one sweep of **34 training seeds
against both controllers, 68 runs**, and the `--spread` file is T027's five repeats of seed 1.

## What was measured

Both distributions come from the per-step traces, not from the run record: the record carries
one summary number per run, and M5 needs the distribution behind it.

- The **steering command** the controller issued, resampled to `COMPARE_HZ` = 14.08 Hz by
  nearest sample through `python.track.compare_drive.resample`.
- The **per-step |delta steering|** on that same grid, each run differenced separately and the
  pieces concatenated. Differencing across the seam between two runs invents a jump no driver
  made, which is the error feature 002 hit at the track1/track2 junction.

Every figure below is `python.eda.stats.describe`, the same function that described the human
column in M1 and the BC column in M4. Nothing here computes a statistic of its own.

## The scripted column

| | `MostOpen` | `WeightedAverage` |
|---|---|---|
| runs / seeds | 34 / 34 | 34 / 34 |
| completed laps | 0 of 34 | 34 of 34 |
| samples at 14.08 Hz | 1,850 | 12,691 |
| steering mean | -0.2968 | -0.1998 |
| steering variance | 0.15611 | 0.04994 |
| steering min / max | -1.0000 / +0.6000 | -0.8711 / +0.5437 |
| steering P1 / P50 / P99 | -1.0000 / +0.0000 / +0.0000 | -0.6758 / -0.2299 / +0.4259 |
| \|delta steering\| mean | 0.0534 | 0.0157 |
| \|delta steering\| P95 | 0.6000 | 0.0465 |
| \|delta steering\| max | 0.6000 | 0.2760 |

**The sample counts are not a detail.** `MostOpen` contributes a seventh of the rows because it
ends in a wall after about 2.7 s. A pooled distribution weights each run by how long it survived,
so these are distributions over *steering that happened*, not per-run averages, and a controller
that crashes early is under-represented in its own column rather than penalised in it.

**The scripted column is not zero-mean, and the reason is the track rather than the driver.**
`WeightedAverage` averages -0.1996 over a lap and the per-seed means run from -0.2141 to -0.1893,
**the same sign on 34 of 34 seeds**. The generator samples every centre line as `r(theta)` over
`theta` from 0 to 2 pi, so every track is a closed loop wound the same way and every lap is one
net turn in one direction. The human column pools two recordings and sits at +0.0055. Placing
those side by side in M5 without this sentence would read as a steering bias in the controller;
it is a property of what it was asked to drive.

## Against the learned driver

The BC column is `bc_balanced_v01`, its `predicted_steering` and `abs_delta_predicted` read
straight from `results/bc/run_bc_balanced_v01/distributions.json`.

Only **|delta steering|** crosses between the two. The steering command itself is two different
roads: a mean of -0.20 on a generated loop against -0.02 on the Udacity recordings compares the
tracks, not the drivers.

| \|delta steering\| | `MostOpen` | `WeightedAverage` | `bc_balanced_v01` |
|---|---|---|---|
| mean | 0.0534 | **0.0157** | 0.0248 |
| P50 | 0.0000 | **0.0078** | 0.0187 |
| P95 | 0.6000 | **0.0465** | 0.0692 |
| P99 | 0.6000 | 0.1649 | **0.1121** |
| max | 0.6000 | 0.2760 | **0.2500** |

**`WeightedAverage` moves the wheel less than the learned driver at the mean, the median and the
P95, and more at the P99 and the maximum.** Reported in that order and in one breath, because
both halves were measured. The scripted driver is calmer in the body of the distribution and has
the heavier tail: it holds a steady arc for most of a lap and occasionally corrects harder than
the model ever does on recorded frames.

The three P95 gaps clear **0.0063**, the run-to-run spread T027 measured on that measure over
five repeats. **The learned side has no equivalent number.** Feature 004 measured a reproduction
tolerance of 0.0005 and recorded that it applies to the best-epoch validation error and to
nothing else, so borrowing it here would judge a distribution against an accuracy figure. Every
gap above is therefore above one side's noise floor and unjudged against the other's.

`MostOpen` is smoother than the learned driver at the P50 only, where it reads exactly 0.0000.
That is 34 runs of committing to one direction and holding it into a wall. **Smoothness alone
ranks a crash highly**, which is why FR-009 keeps the outcome measures beside it and why this
table is never read without the completion row above.

## Three things this comparison is not

- **The learned driver never drives.** Feature 004 records it as FR-018: the model reacts to
  frames the human produced, and the next frame is the human's doing, not the model's. Lap
  completion, wall contacts and lap time have no BC column at all. `WeightedAverage` completing
  34 of 34 is not a win over the learned driver; it is a measure the learned driver does not
  have.
- **Different roads.** Unity generated tracks against the Udacity recordings. Both steering
  columns are the command in [-1, 1], so they are the same quantity of two different problems.
- **Nearly, not exactly, the same clock.** The scripted side is resampled to 14.08 Hz, which is
  track1's median frame rate. The learned side is differenced per validation frame, so it sits
  at that rate on track1 by construction and above it on track2. The per-track BC rows are
  0.0201 mean / 0.0516 P95 on track1 and 0.0268 / 0.0768 on track2; the comparison above uses
  the pooled row, and the track1 row is the one measured on the same clock. **The conclusion
  does not turn on the choice**: `WeightedAverage`'s 0.0157 and 0.0465 are below both.
