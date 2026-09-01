# Research: M5, evaluation and comparison

Every finding here was measured on 2026-09-01 against the repository as it stands, not taken from a
summary. Where a number contradicts an existing document, the contradiction is stated.

## R1: the human steering lattice is 41 levels, and one of them is never used

`results/eda/authenticity_stats.json` holds the measurement feature 002 made. Steering on
**track1** is a lattice of spacing **0.05** with **41 support points** from -1.0 to +1.0, of which
**40 are observed**: the level **0.95 never appears**. On **track2** all 41 appear.

**Why it matters and why it is not a footnote.** KL divergence is infinite wherever one
distribution puts mass on a level the other never used. A structural zero in the reference is
exactly that case. `python/bc/config.py` already anticipated this and set `KL_SMOOTHING = 1e-9`,
added to every lattice bin before the divergence and stated wherever the divergence is reported.
M5 inherits that constant and the obligation to state it.

## R2: most of the comparison machinery already exists, and it is in two places

| capability | where | status |
|---|---|---|
| lattice levels, quantisation, lattice histogram | `python/bc/evaluate.py` | exists, used by M4 |
| KL on the lattice with smoothing | `python/bc/evaluate.py`, `python/bc/config.py` | exists, reported in `results/bc/comparison.md` |
| chi-square homogeneity between two drivers | `python/rl/report.py` via `python/eda/authenticity.py` | exists, used for `rl_steering.md` |
| descriptive statistics per distribution | `python/rl/report.py` `summarise` | exists |
| driver column builder from runs plus traces | `python/rl/report.py` `build_column` | exists |
| **two-sample KS test** | nowhere | **must be written** |

So M5 is mostly assembly plus one new test, not a new pipeline. The risk is not that it cannot be
built; the risk is R5 below.

## R3: the 009 traces exist, are complete, and are mislabelled

The six evaluation sweeps of feature 009 wrote **60 per-step traces** into `results/drive_logs/`,
ten per sweep, named by timestamp. They are 50 Hz, about 3,100 rows each for a three-lap run.

**They are attributable only by filename timestamp.** `DriveLogger.sourceLabel` is a
`[SerializeField]` literal rather than the run id, and in `Evaluation.unity` it still reads
**`ppo_car_spread_a_sampling`**, left over from feature 006. Every one of the 60 traces carries
that string in its `source` column, so **the `source` column is wrong on all of them** and must not
be used to select traces.

The timestamps separate cleanly into six clusters of ten, matching the six sweep CSVs:

| sweep | trace window | eval CSV |
|---|---|---|
| seed 42 deterministic | 18:55:48 to 18:58:08 | `runs_2026-08-31_18-56-04` |
| seed 42 sampling | 18:59:33 to 19:01:41 | `runs_2026-08-31_18-59-49` |
| seed 7 deterministic | 12:48 to 12:50 | `runs_2026-09-01_12-48-31` |
| seed 7 sampling | 12:51 to 12:53 | `runs_2026-09-01_12-51-50` |
| seed 13 deterministic | 14:37 to 14:40 | `runs_2026-09-01_14-38-14` |
| seed 13 sampling | 14:41 to 14:43 | `runs_2026-09-01_14-41-28` |

A trace file opens at run **start**, so its timestamp precedes the row it belongs to. The last
sampling trace of seed 42 is 2 s after the previous one, which is the seed 1009 wall contact at
7.16 s, and that agreement is what confirms the mapping rather than assuming it.

**Decision**: fix `sourceLabel` so future traces are self-describing, and select the existing 60 by
timestamp with the mapping recorded in a committed file rather than in a shell loop.

## R4: the pipeline runs end to end on 009 today

Run as a check rather than assumed. Seed 42 deterministic, the ten traces above, against
`eval_ppo_car_009_bc_deterministic.csv`:

```
laps completed    10 of 10   (scripted: 34 of 34)
wall contacts     0.00 per run
steering          n=8788  mean=-0.1859  sd=0.1791  var=0.03208  p95=+0.1150
|delta steering|  n=8778  mean=+0.0413  sd=0.0649  var=0.00422  p95=+0.2103
steering variance 0.03208 against the scripted driver's 0.04994
chi2 homogeneity vs human: statistic=20154.5 dof=40 critical=55.8 p=0 reject_null=True pooled=0
```

The chi-square figure is against the **combined** human reference, per the correction in R5. Against
track1 alone it reads 12,385.3 with dof 28 and 12 lattice levels pooled for sparsity; against
combined nothing needs pooling, because all 41 levels are populated. That is a second reason the
combined column is the right reference and not merely the conventional one.

**Two things fall out of that immediately.**

First, **the learned driver is now steadier than the scripted one**, variance 0.03208 against
0.04994. `report.py` prints that comparison under a branch written when the learned column always
lost, and feature 006's `rl_steering.md` concluded that steering variance alone cannot separate a
driver that laps from one that never moves. It still cannot, but the sign has flipped and the prose
around it is M3-era.

Second, **`report.py` prints `markers 72.00 of 24 (300.0% of a lap)`**. `markers_possible` is 24
while a completed run is three laps. Harmless in M3, where nothing finished; wrong on the page in
M5.

## R5: the marginal steering comparison is measuring the track, not the driver

This is the finding that shapes the feature.

**Correction to the first version of this section, kept rather than silently edited.** It was
written against `track1data` alone and claimed the human straight-line share was 79.3 per cent,
"worse than `DESIGN.md` 7 anticipated". That was wrong. `python/bc/config.py` sets
`DATASET_NAME = "combined"`, and the human reference for every existing figure, including M4's KL,
is **track1 plus track2**, which is the file at `dataset/dataset/dataset/driving_log.csv`. Its
straight-line share is **58.6 per cent**, exactly the number `DESIGN.md` 7 already quotes. The
design was right and the first reading of this section was an artefact of picking one track.

| | human, combined | human, track1 | human, track2 | RL 009, deterministic |
|---|---|---|---|---|
| n | **32,443** | 10,615 | 21,828 | 31,202 |
| mean | **-0.0209** | -0.0367 | -0.0132 | **-0.1862** |
| variance | **0.15149** | 0.02393 | 0.21333 | **0.03208** |
| exact zero, or within 0.025 of zero | **58.6 %** | 79.3 % | 48.4 % | **2.5 %** |
| steering left | **23.5 %** | 17.4 % | 26.4 % | **87.6 %** |
| steering right | **18.0 %** | 3.2 % | 25.1 % | 12.3 % |

**The combined column is the reference. The two per-track columns are shown only because they
differ so much** that a future reader who picks one will get a different answer, which is how this
error happened in the first place.

The finding survives the correction and is still the thing that shapes the feature: the human is
straight on **58.6 per cent** of steps while the agent is within 0.025 of zero on **2.5 per cent**,
and the agent turns **left on 87.6 per cent** because the generated loop is driven in one direction
against the human's near-balanced 23.5 against 18.0.

**One comparison reverses under the correction, and it matters.** Against track1 the RL policy
looked *more* variable than the human, 0.03208 against 0.02393. Against the combined reference the
human is **five times more variable**, 0.15149 against 0.03208. Any statement about whose steering
is more settled depends entirely on which human column is used, so the reference is named every
time the figure appears.

**So the chi-square statistic of 20,154 above is not a finding about driving style.** It is track
geometry and recording resolution restated as a test. Quantising onto the lattice, which
`DESIGN.md` 7 prescribes, fixes the resolution half and does nothing about the geometry half. A
report presenting that number as "RL drives unlike a human" would be confidently wrong, and it is
the artefact both notes in `DESIGN.md` 7 were written to prevent.

**Candidate conditionings, to be chosen in the plan rather than here.**

1. **Compare `|delta steering|` instead of steering level.** Smoothness depends far less on where
   the track happens to turn, it is already computed for every driver, and feature 005's
   `us4_steering.md` already compares the heuristic to BC on exactly this axis. Cheapest and most
   defensible.
2. **Condition on curvature.** Bin steps by local track curvature and compare within bins. Honest,
   but the human side has no curvature signal available, which likely kills it.
3. **Fold by sign.** Compare `|steering|`, removing the one-directional bias but discarding an
   asymmetry that is itself real.
4. **Report the marginal comparison anyway, with the artefact quantified beside it.** Not an
   alternative to the above but an obligation alongside whichever is chosen, because the raw number
   is what a reader would otherwise compute and misread.

## R6: the BC column cannot have three of the table's rows

`results/bc/comparison.md` already reports **KL from human on the lattice**, 1.1439 unbalanced and
1.2070 balanced, on a 5,576 row validation set. The BC model predicts steering from camera images
of another simulator, so it has no lap completion, no lap time and no track. Those cells are stated
as absent with their cause, per SC-001, and never filled with a proxy.

## Open question carried into the plan

Whether M5 reports one RL column or three. The spread gives three checkpoints with near-identical
held-out behaviour; the honest default is one named column plus a line stating the other two agree,
rather than three columns implying three drivers.

## R7: the 50 Hz trace understates steering activity by a factor of about four

Measured on one seed 42 deterministic trace:

| | n | share of deltas exactly zero | mean `|delta steering|` |
|---|---|---|---|
| raw 50 Hz | 3,138 | **67.1 %** | **0.0110** |
| decimated to 12.5 Hz | 784 | 1.0 % | 0.0417 |

The agent decides once every four physics steps (`DecisionPeriod: 4`) and the command is held in
between, so two thirds of the raw differences are structurally zero. Anyone differencing the trace
at 50 Hz gets a driver that appears **3.8 times smoother than it is**. This is the same class of
error as R5, on the axis the plan makes primary.

**The repository already solves this, and M5's instruction is to not solve it again.**
`python/track/config.py` sets `COMPARE_HZ = 14.08`, and `report.py.steering_series` resamples each
run to that rate and differences **after** resampling, per run, so no difference spans the seam
between two runs. `compare_drive.resample` takes the nearest sample rather than averaging, because
averaging would smooth the very quantity being measured.

**14.08 Hz was verified independently rather than trusted.** The human `driving_log.csv` has no time
column, but the centre-image filenames carry millisecond stamps. Recovered from them, the human
median inter-sample interval is **0.0710 s, or 14.08 Hz**, with no session gaps. That matches the
constant already in `config.py` exactly.

**Consequence for the plan**: `|delta steering|` is only ever computed through `steering_series`,
never from a raw trace, and the rate is named wherever the figure is reported.

## R8: the human's steering is a discrete input device, and it dominates the primary axis

Found 2026-09-01 while building the four columns, after the axis had been chosen. It is the same
class of problem as R5 and R7 and it lands on `|delta steering|`, which is the axis the plan made
primary.

| `|delta steering|` at 14.08 Hz | mean | median | p95 | exactly zero | at or above 0.05 |
|---|---|---|---|---|---|
| RL 009 deterministic | 0.0413 | 0.0127 | 0.2103 | 9.2 % | 23.7 % |
| heuristic | 0.0174 | 0.0075 | 0.0621 | 5.2 % | 5.9 % |
| BC | 0.0248 | 0.0187 | 0.0693 | 0.0 % | 11.4 % |
| **human, combined** | **0.1112** | **0.0000** | **0.5500** | **55.3 %** | **44.2 %** |

**The human is the least smooth driver by a factor of 2.7 on the mean, and its median is zero.**
Those two facts together say the distribution is not unimodal and the mean is the wrong summary of
it.

**What it actually is.** Of the human's 14,517 nonzero steering changes, **67.8 per cent land
exactly on the 0.05 lattice**, and the two commonest values are **0.15 at 35.9 per cent** and
**0.20 at 31.1 per cent**, being jumps of three and four lattice steps. A further 4.1 per cent are
exactly 1.00, which is a full-lock reversal. The RL policy's nonzero changes land on that grid
**0.0 per cent** of the time.

So the human record is: hold at exactly zero for most of the drive, then jump by three or four
lattice steps at once. **That is the signature of a discrete input device**, a keyboard or a
stepped control, not of a hand on a continuous wheel.

**Consequence, and it is not that the axis was the wrong choice.** `|delta steering|` remains far
less track-dependent than steering level, which is why it was chosen. But a KS test between the
human column and any automated driver on this axis will reject with a large effect, and **the
finding would be about how the steering was entered rather than about how the car was driven**.
Reporting "the RL policy is smoother than the human" without that sentence would be true and
misleading in the same way the chi-square of 20,154 is true and misleading.

**What the plan must therefore do**, and this is settled here rather than left to the writeup:

1. Report **median and the full shape** beside the mean on this axis, never the mean alone.
2. Report the on-grid share for every driver in the same table, as the artefact number, exactly as
   R5's near-zero and left-turn shares sit beside the steering-level comparison.
3. Report the comparison **twice**: once on raw `|delta steering|`, and once after quantising every
   driver onto the human lattice before differencing, which puts all four on the human's recording
   resolution. That is the same medicine `DESIGN.md` 7 already prescribes for steering level,
   applied to the axis that inherited the problem.
4. Read the **RL against heuristic against BC** comparison as the one that is free of this, because
   all three are continuous outputs recorded by the same machinery.
