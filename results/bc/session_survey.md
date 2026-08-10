# M4 reconnaissance: session survey

Produced by `python -m python.bc.survey`. Every number in research R2 comes from here, so this
file is the thing that has to re-run to the same values, not the prose that quotes it.

Read-only. Trains nothing, writes nothing outside `results/bc/`.

## Integrity (T008)

[combined] rows=32,443 images=97,329 expected=97,329 -> OK; unresolved_rows=0 (sample 0/500)

The expected image count is three times the row count: one recorded moment is a center, left
and right frame. A mismatch means the archive did not unpack fully, and every statistic
downstream would be computed over the wrong denominator.

## Sessions (T006)

| Session | Rows | First | Last |
|---|---|---|---|
| `track1data` | 10,615 | 2019-04-02 19:25:33.671000 | 2019-04-02 19:38:12.752000 |
| `track2data` | 21,828 | 2019-04-02 18:05:37.641000 | 2019-04-02 18:31:04.870000 |

**This is the finding that changed the design.** `split_sessions` segments on the track marker
in the image path, and the combined file carries exactly two. Holding out whole sessions
therefore means training on one track and validating on the other, which measures transfer
between two driving profiles rather than generalisation within one.

## Timeline

| Session | Rows | Implied fps | Median interval | Gaps | Largest gap |
|---|---|---|---|---|---|
| `track1data` | 10,615 | 14.08 | 0.0710 s | 1 | 0.5 s |
| `track2data` | 21,828 | 14.29 | 0.0700 s | 0 | 0.3 s |

Finer segmentation is not available either. There is no gap anywhere long enough to call a
break, so these are two continuous takes with nothing to cut on. Session-level holdout is not
merely coarse here, it is unavailable.

## Steering autocorrelation

| Lag | Rows | `track1data` | `track2data` |
|---|---|---|---|
| 0.07 s | 1 | +0.577 | +0.846 |
| 0.25 s | 4 | +0.026 | +0.462 |
| 0.50 s | 7 | +0.334 | +0.487 |
| 1.00 s | 14 | +0.186 | +0.442 |
| 2.00 s | 28 | +0.235 | +0.345 |
| 3.00 s | 43 | +0.203 | +0.214 |
| 5.00 s | 71 | +0.176 | +0.060 |
| 8.00 s | 113 | +0.085 | +0.011 |
| 12.00 s | 170 | +0.040 | -0.065 |
| 20.00 s | 284 | -0.107 | -0.054 |

The guard width is derived from this table rather than chosen. Two frames close in time carry
nearly the same steering value, so a validation frame beside a training frame is scored on
something the model has effectively already seen. The chosen guard is the shortest lag at which
**both** sessions fall below 0.1.

Track1's curve is noisy, and the reason is in the band table below: most of its steering is
exactly zero, so the correlation there is dominated by the zero mass rather than by driving.
Track2 decays cleanly and is the session that sets the figure.

## Guard cost

| Guard | Blocks | Held out | Train | Val | Discarded | Discard % | Val % |
|---|---|---|---|---|---|---|---|
| 3 s | 5 | 1 | 25,955 | 6,316 | 172 | 0.5 | 19.6 |
| 3 s | 10 | 2 | 25,957 | 6,142 | 344 | 1.1 | 19.1 |
| 3 s | 20 | 4 | 25,959 | 5,796 | 688 | 2.1 | 18.3 |
| 5 s | 5 | 1 | 25,955 | 6,204 | 284 | 0.9 | 19.3 |
| 5 s | 10 | 2 | 25,957 | 5,918 | 568 | 1.8 | 18.6 |
| 5 s | 20 | 4 | 25,959 | 5,348 | 1,136 | 3.5 | 17.1 |
| 8 s | 5 | 1 | 25,955 | 6,036 | 452 | 1.4 | 18.9 |
| 8 s | 10 | 2 | 25,957 | 5,582 | 904 | 2.8 | 17.7 |
| 8 s | 20 | 4 | 25,959 | 4,676 | 1,808 | 5.6 | 15.3 |

Discarded rows are the price of the guarantee. The chosen setting is the one that buys
independence at a cost worth paying, with the held-out blocks spread across the lap rather than
taken as one contiguous stretch that might be a single corner repeated.

## Near-zero steering mass (T007)

| Band | `pooled` | `track1data` | `track2data` |
|---|---|---|---|
| exactly 0 | 58.6 % | 79.3 % | 48.4 % |
| |s| <= 0.05 | 61.2 % | 81.5 % | 51.3 % |
| |s| <= 0.10 | 63.8 % | 83.9 % | 54.1 % |
| |s| <= 0.15 | 66.4 % | 86.3 % | 56.8 % |

`ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` are chosen against this table. Balancing
trades a better predictor against a prediction distribution that still resembles the human one,
and the size of that trade is the mass measured here.

The per-session split is the point. A pooled figure describes neither recording, which is the
same trap feature 002 recorded for the `brake` column.

## What the side-camera augmentation does to the targets

| Band | Center camera only | All three cameras |
|---|---|---|
| exactly 0 | 58.6 % | 20.3 % |
| 0.00 < |s| <= 0.05 | 2.6 % | 2.6 % |
| 0.05 < |s| <= 0.10 | 2.7 % | 2.6 % |
| 0.10 < |s| <= 0.15 | 2.6 % | 2.4 % |
| 0.15 < |s| <= 0.20 | 2.4 % | 40.6 % |

**The augmentation is not free, and this is the largest single distortion in the pipeline.**

Turning one row into three samples at `s`, `s + 0.2` and `s - 0.2` cuts the exact-zero mass
from 58.6 percent to 20.3 percent, which looks like it solves the imbalance the balancing
policy exists to address. It does not solve it, it **moves** it: two thirds of the old zero mass
lands on exactly plus and minus 0.2, and the band just below 0.20 goes from a few percent to
roughly 43 percent of all training samples.

Three consequences worth stating before any model is trained.

1. **Balancing the zero spike matters far less than the row-level 58.6 percent suggested.** With
   side cameras on, exact zeros are already down to 20.3 percent of training samples.
2. **The offset creates two artificial modes the human never produced as a distribution
   feature.** 0.20 is a real lattice point, so in a histogram those modes are indistinguishable
   from genuine human steering at 0.20. The prediction distribution is what M5 compares, and
   the model is being taught to produce them.
3. **The offset is a copied convention, not a measured quantity** (research R4). A constant that
   parks 43 percent of the training targets on two values deserved a derivation, and there is
   none available in this dataset.

This does not invalidate the augmentation, which is what makes the side images usable at all.
It does mean the offset cannot be treated as a minor hyperparameter held fixed in the
background, and that the balancing comparison must be read with it in view.

### Choosing the offset policy

| Policy | Fullest band below 0.30 | Mass above 0.30 |
|---|---|---|
| constant 0.20 | 40.6 % | 27.4 % |
| jitter 0.15 to 0.25 | 21.7 % | 27.5 % |
| jitter 0.10 to 0.30 | 19.5 % | 27.6 % |
| jitter 0.05 to 0.35 | 19.5 % | 33.9 % |
| center camera only | 58.6 % | 26.1 % |

Two things are watched here, and the second is what decides it.

The **fullest band** is the obvious measure: the constant offset puts 40.6 percent of training
targets in one band, and every jitter range reduces that.

The **mass above 0.30** is the one that rules an option out. That region is genuine human
high-steering data. A range wide enough to push augmented samples up into it is inflating real
data with synthesised values, which is a worse fault than the spike it set out to fix. Center
camera only is the honest baseline for this column, since it contains no synthesised targets
at all.

Widening from 0.15-0.25 to 0.10-0.30 flattens the augmented mass without touching that tail.
Widening again to 0.05-0.35 buys nothing on the peak and inflates the tail, so it is rejected.

The chosen range keeps a mean of exactly 0.20, so it **generalises** the value DESIGN 6.1
already carried rather than replacing it with an unrelated number.

## Pooled steering, for reference

n = 32,443, mean = -0.0209,
variance = 0.1515, std = 0.3892,
min = -1.0000, max = 1.0000

Reported through `eda.stats.describe`, not recomputed here, so this feature's numbers and M1's
cannot drift apart in definition (Principle IX, research R5).
