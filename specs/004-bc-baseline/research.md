# Research: Behavioral Cloning Baseline (M4)

Phase 0. Every unknown in the plan's Technical Context resolved, with the alternative that was
rejected and why. Nothing here is a preference; each decision is either forced by a measurement
or recorded plainly as a choice.

---

## R1 - Which Python environment BC trains in

- **Simply:** neither environment we have can run this feature, so a third one is needed.
- **Measured on 2026-08-04**, not assumed:

  | Environment | numpy | pandas | scipy | matplotlib | torch | CUDA |
  |---|---|---|---|---|---|---|
  | `.venv` | 1.26.4 | 2.1.4 | 1.13.1 | 3.8.4 | absent | - |
  | `.venv-mlagents` | 1.23.5 | absent | absent | absent | 2.6.0+cu124 | available, RTX 3050 6 GB |

- **Decision**: a third environment, `.venv-bc`, pinned in a new `requirements-bc.txt`. It gets
  torch 2.6.0+cu124, pandas, numpy, Pillow and matplotlib.
- **Why not add torch to `.venv`**: `.venv` is the environment M1's committed numbers were
  produced in, on numpy 1.26.4. Installing a large dependency into it invites pip to move numpy,
  and Principle VI created the two-environment rule precisely because a silent numpy change
  would invalidate M1's reproducibility claim without any visible failure.
- **Why not add pandas to `.venv-mlagents`**: that environment exists to run `mlagents`, which
  hard-pins numpy 1.23.5. It is the environment M3 will train in. Disturbing it to serve M4
  risks the milestone that has not started yet.
- **Consequence to record**: BC's numbers are produced under a numpy that matches neither M1's
  nor M3's. That is acceptable because BC computes its own statistics over its own predictions
  and does not reproduce any M1 figure. Where BC compares against the human reference, it uses
  `python/eda`'s functions, so the definitions are shared even when the numpy build is not.
- **Alternative considered**: one unified environment. Rejected: it forces numpy 1.23.5 on
  everything, which is exactly the merge Principle VI forbids.

---

## R2 - How the train/validation split avoids leakage

- **Simply:** cut each recording into contiguous blocks, hold some out, and throw away a guard
  band either side of every boundary.
- **The hazard**: the recording is roughly 14 frames per second of continuous driving. Two
  frames 70 ms apart are nearly the same image with nearly the same steering value. A random
  frame-level split puts one in training and its neighbour in validation, and the reported
  validation error then measures interpolation between adjacent frames rather than
  generalisation. This is the single most common way this project's exact shape reports a good
  number that means nothing.

### The session-level plan was tried first and is not available

The first version of this document chose **session-level holdout**, on the grounds that it makes
the leak-free property parameter-free. That plan is withdrawn. It was checked before any code
was written, and the data does not support it.

**Measured 2026-08-04 on the combined recording:**

| Session | Rows | Time range | Largest gap |
|---|---|---|---|
| `track1data` | 10,615 | 19:25:33 to 19:38:12 | 0.5 s |
| `track2data` | 21,828 | 18:05:37 to 18:31:04 | 0.3 s |

`eda.integrity.split_sessions` yields exactly **two** sessions, one per track, because it
segments on the track marker in the image path. And the timeline check shows why no finer
segmentation is available either: the largest gap anywhere in either recording is **0.5 s**.
These are two continuous takes. There are no natural breaks to cut on.

Session-level holdout therefore degenerates into training on track1 and validating on track2,
which this document had already rejected in its previous version: that measures transfer between
two different driving profiles rather than generalisation within one, and would understate the
model badly. Track1 is 79.3 percent zero steering and track2 is far more active; they are not
two samples of the same thing.

### What replaces it

**Decision**: **contiguous block holdout with a measured guard band.** Each track is cut into
`N_BLOCKS` contiguous blocks by row order. `N_HOLDOUT` evenly spaced blocks per track go to
validation. Every frame within `GUARD_SECONDS` of a block boundary is **discarded from both
sides**, so no training frame is temporally adjacent to any validation frame.

This does reintroduce a parameter, which is exactly what the session plan was trying to avoid.
Since no parameter-free option exists in this data, the honest response is to derive the
parameter from a measurement rather than pick it and hope.

**The guard width is derived from steering autocorrelation**, measured per track:

| Lag | track1 | track2 |
|---|---|---|
| 0.07 s | +0.577 | +0.846 |
| 1 s | +0.186 | +0.442 |
| 3 s | +0.183 | +0.224 |
| 5 s | +0.155 | +0.061 |
| **8 s** | **+0.085** | **+0.011** |
| 12 s | +0.031 | -0.069 |

8 s is the shortest lag at which **both** tracks sit below 0.1. Track1's curve is noisy because
79.3 percent of its steering values are zero, so the correlation there is dominated by the zero
mass; track2's decays cleanly and is the one that sets the figure.

**The cost was computed before the value was chosen**, across the options:

| Guard | Blocks | Held out | Train | Val | Discarded | Discard % | Val % |
|---|---|---|---|---|---|---|---|
| 3 s | 10 | 2 | 25,957 | 6,150 | 336 | 1.0 | 19.2 |
| 5 s | 10 | 2 | 25,957 | 5,926 | 560 | 1.7 | 18.6 |
| **8 s** | **10** | **2** | **25,957** | **5,582** | **904** | **2.8** | **17.7** |
| 8 s | 5 | 1 | 25,955 | 6,036 | 452 | 1.4 | 18.9 |
| 8 s | 20 | 4 | 25,959 | 4,676 | 1,808 | 5.6 | 15.3 |

**Chosen: guard 8 s, 10 blocks per track, 2 held out.** It costs 2.8 percent of the data, which
is cheap for the guarantee, and it lands near 17.7 percent validation against a 20 percent
target.

> **The sweep above is an estimate; the achieved figures are slightly different.** The sweep
> converts the guard to a fixed row count (`round(8 * 14.08)` = 113 rows per side), which is
> what makes a fast comparison across nine settings possible. `bc.split` trims by **actual
> timestamps** instead, so it removes however many rows really fall inside 8 s rather than a
> nominal count. Measured on 2026-08-04: **train 25,957, validation 5,576, guard 910, achieved
> fraction 0.1768, minimum train-to-validation gap 8.09 s.** The sweep predicted 5,582 and 904.
> The gap of six rows is the difference between a nominal frame rate and the real intervals,
> and the timestamp version is the authoritative one because it is the one that carries the
> guarantee.

- **Why 10 blocks and 2 held out, not 5 and 1**: two separated held-out blocks per track sample
  two different parts of the lap. A single contiguous 20 percent stretch could be one corner
  repeated, and the validation error would then describe that corner rather than the track.
- **Why not 20 and 4**: it doubles the guard cost to 5.6 percent for a marginal gain in coverage.
- **Why the guard is discarded from both sides**: dropping it only from the validation side
  leaves training frames sitting right against the boundary, and adjacency is symmetric.

**What is still reported rather than forced**: the achieved validation fraction. Blocks are
integer-sized and the guard eats into them, so 17.7 percent is what the rule produces and the
gap to the 20 percent target is recorded, not corrected. Correcting it would mean moving a
boundary to hit a number, which is fitting the split to a target instead of to the data.

**Verification remains machine-checkable.** `verify_no_leak` asserts that the minimum time
distance between any training frame and any validation frame is at least `GUARD_SECONDS`. That
is a stronger and simpler check than the session-overlap test the previous plan called for.

---

## R3 - Where quantisation onto the human lattice happens

- **Simply:** the model emits continuous values; the comparison does the quantising.
- **Established by feature 002**: the human steering column is lattice-valued, 41 levels at a
  step of 0.05. A regression model emits real numbers. Comparing a smooth density against 41
  spikes reports a large difference that is an artefact of recording resolution.
- **Decision**: this feature stores **raw continuous predictions** and records the lattice fact
  beside them. The shared-grid treatment, `round(x / 0.05) * 0.05` clipped to [-1, 1], is applied
  where the two distributions are compared, which is M5, and DESIGN section 7 already assigns it
  there.
- **Why not quantise at the model boundary**: quantising discards information a later comparison
  might want, and it is irreversible. Storing the continuous value keeps both options open, and
  the quantised view is one line away whenever it is needed.
- **What this feature must still do**: report at least one comparison against the human column
  with the treatment applied, so the mechanism is demonstrated here rather than deferred whole
  to M5 and discovered to be broken there.

---

## R4 - The camera offset is chosen, not derived

- **Simply:** plus or minus 0.2 is a convention, and this document says so out loud.
- DESIGN section 6.1 states `+0.2` for the left camera and `-0.2` for the right, treating the
  side cameras as if the car were displaced laterally. That figure comes from the widely copied
  NVIDIA PilotNet write-up and the Udacity coursework built on it. It is not derived from this
  dataset, and no derivation of it exists in the sources this project follows.
- **A derivation would need** the lateral distance between the cameras and the lookahead time
  the correction is meant to act over. The dataset documents neither, and the simulator that
  produced it is not the simulator we built.
### Measured 2026-08-04: the effect is not negligible, it is the largest distortion in the pipeline

The previous version of this section said to "report its effect rather than assume it is
negligible". The effect was then measured, and it is large enough to change how the offset is
treated.

| Band | Center camera only | All three cameras |
|---|---|---|
| exactly 0 | 58.6 % | 20.3 % |
| 0.00 < abs(s) <= 0.05 | 2.6 % | 2.6 % |
| 0.05 < abs(s) <= 0.10 | 2.7 % | 2.6 % |
| 0.10 < abs(s) <= 0.15 | 2.6 % | 2.4 % |
| **0.15 < abs(s) <= 0.20** | **2.4 %** | **40.6 %** |

Turning one row into three samples at `s`, `s + 0.2` and `s - 0.2` cuts the exact-zero mass from
58.6 percent to 20.3 percent. That looks like it solves the imbalance the balancing policy
exists to address. It does not solve it, it **moves** it: two thirds of the old zero mass lands
on exactly plus and minus 0.2, and one band goes from 2.4 percent to 40.6 percent of all
training samples.

**Why this is worse than the imbalance it appears to fix.** A spike at zero is honest: the human
really did drive straight most of the time. A spike at plus and minus 0.2 is an artefact of a
copied constant. And 0.20 is a real lattice point, so in a histogram those two modes are
indistinguishable from genuine human steering at 0.20. The prediction distribution is exactly
what M5 compares, and the model is being taught to produce them.

**Consequence for the balancing question.** With side cameras on, exact zeros are already down
to 20.3 percent of training samples, so the zero spike the balancing policy targets is far
smaller than the row-level 58.6 percent implied. The balancing comparison is still worth running,
but it must be read with the offset artefact in view rather than as the only distribution effect
in play.

### Decision: jitter the offset over 0.10 to 0.30

The offset is drawn **per sample** from a uniform range instead of being a constant. The range
was swept before it was chosen:

| Policy | Fullest band below 0.30 | Mass above 0.30 |
|---|---|---|
| constant 0.20 | 40.6 % | 27.4 % |
| jitter 0.15 to 0.25 | 21.7 % | 27.5 % |
| **jitter 0.10 to 0.30** | **19.5 %** | **27.6 %** |
| jitter 0.05 to 0.35 | 19.5 % | 33.9 % |
| center camera only | 58.6 % | 26.1 % |

Two columns, and the second is what rules an option out.

The **fullest band below 0.30** measures the artificial spike. At 0.10 to 0.30 it reaches 19.5
percent, and that figure is the **exact-zero bucket**, not an augmentation artefact: the
augmented mass has been flattened below the natural zero spike, so there is nothing left to
gain by spreading it further.

The **mass above 0.30** is genuine human high-steering data. Center camera only gives the
honest baseline, 26.1 percent, since it contains no synthesised targets at all. A range wide
enough to push augmented samples into that region inflates real data with invented values,
which is a worse fault than the spike it set out to fix. That is exactly what 0.05 to 0.35
does, taking the tail from 27.6 to 33.9 percent for no gain on the peak, so it is rejected.

**Why this is defensible beyond the numbers.** The true correction for a laterally displaced
camera is not a constant. It depends on how fast the car is moving and how sharply the road is
curving, because it is really a question of how long the car has to return to the line. The
dataset documents neither speed in physical units nor curvature, so the correct value cannot be
computed. A range acknowledges that uncertainty instead of pretending a single number resolves
it.

**The range keeps a mean of exactly 0.20**, so it generalises the value DESIGN 6.1 already
carried rather than replacing it with an unrelated one.

**Drawn once at split time, from the seed, not re-drawn each epoch.** Re-drawing would be
stronger augmentation, but it would make the training target distribution a different object on
every epoch, and this feature has to be able to report what that distribution was. A fixed draw
is inspectable and reproducible; a moving one is neither.

- **Still true**: the offset policy is held identical across both balancing runs, so it never
  becomes a confound between them.
- **No longer acceptable**: treating the offset as a minor hyperparameter fixed in the
  background. A constant that parks 40.6 percent of the training targets on two lattice points
  needed a derivation, and none was available.
- **Constraint that follows** (FR-007): augmented samples never enter validation. The offset is a
  synthesised target no human produced, so validating against it would be scoring the model on
  our own invention.

---

## R5 - Statistics come from feature 002, not from this feature

- **Simply:** the functions Principle IX requires already exist and are tested.
- Available in `python/eda/stats.py`: `describe(series, variable)` returns a
  `DistributionSummary` carrying sample size, mean, variance, standard deviation, minimum and
  maximum, which is exactly the six Principle IX names; `relative_frequency_histogram(series,
  bins)` returns the histogram; `abs_delta_steering(datasets)` computes the per-frame smoothness
  quantity the project already uses for the human reference.
- **Decision**: call them. This feature adds no statistical machinery of its own.
- **Why this matters beyond saving effort**: if BC computed its own mean and histogram, BC's
  numbers and M1's numbers could drift apart in definition while both looked correct, and the
  M5 comparison would be between two slightly different questions. Sharing the function makes
  that impossible.
- **The one thing this feature does add**: residuals are a distribution M1 never had, since M1
  had no model. Residuals are summarised with the same `describe`, so the new distribution is
  described by the old definition.

---

## R6 - Per-track reporting is possible on the combined recording

- **Simply:** the combined file remembers which track each row came from.
- The combined `dataset/dataset/dataset/driving_log.csv` carries the original Windows-absolute
  image paths, and those paths contain `track1data` or `track2data`. Feature 002 already relies
  on this through `config.SESSION_PATH_MARKERS`.
- **Decision**: FR-016's per-track reporting reuses that marker rather than reloading the two
  track files separately. One load, one split, two reported views.
- **Why it matters**: feature 002 found that pooled column statistics are actively misleading on
  this dataset. `brake` looked usable pooled and is constant on track1. The same trap is live for
  steering, where track1 is 79.3 percent zeros and track2 is far more active. A pooled histogram
  is a legitimate view only when the per-track ones sit beside it.

---

## R7 - Hardware limits worth knowing before writing the training loop

- **Simply:** the GPU is small and the bottleneck will be disk, not maths.
- **Measured**: NVIDIA RTX 3050 Laptop, 6 GB VRAM, CUDA available under torch 2.6.0+cu124.
- **Measured**: 97,329 images under the combined `IMG/`, which reconciles exactly with
  32,443 rows times three cameras. The integrity check FR-002 requires therefore has a known
  expected answer before it is ever run.
- The network is roughly 250k parameters. At the standard 66 by 200 input it occupies a trivial
  fraction of 6 GB, so batch size is bounded by throughput rather than by memory.
- **Consequence for the plan**: decoding roughly a hundred thousand JPEGs per epoch is the cost.
  The task list treats loader throughput as the thing to measure first, and leaves caching as an
  option to take only if a measurement says it is needed. Building a cache before measuring
  would be optimising a bottleneck nobody has observed.
- **Consequence for FR-009**: CUDA being available today does not mean it is available on the
  next run. The device is detected, reported, and a CPU fallback requires an explicit flag, so a
  silent multi-hour CPU epoch cannot happen by accident.

---

## R8 - What "reproducible" can honestly claim

- **Simply:** evaluation reproduces exactly; training reproduces to a tolerance.
- Seeding Python, numpy and torch fixes the split, the shuffling and the initialisation. It does
  not make cuDNN's kernel selection deterministic, and forcing determinism costs speed and still
  does not cover every operation.
- **Decision**: claim exact reproduction for **evaluation from a saved checkpoint**, which
  involves no randomness, and tolerance-bounded reproduction for **training**. The tolerance is
  stated with the result rather than chosen in advance, and it is derived by running the same
  seed twice and reporting the observed spread.
- **Why not force full determinism**: a criterion that cannot be met is worse than a looser one
  that can, and SC-007 is written to be satisfiable rather than aspirational.
- **What is recorded per run** (FR-010): seed, hyperparameters, device name, duration, sample
  counts, and final metrics, stored next to the checkpoint so the two cannot be separated.

---

## R9 - The crop is measured, not inherited

**Question.** DESIGN 6.2 says "crop neba/haube" and gives no rows. The Udacity convention is to
remove 60 rows from the top and 25 from the bottom of the 320x160 frame. That convention was
written for a different recording, so it is a starting hypothesis rather than an answer.

**The bottom line, the hood.** The obvious test is temporal: the car's own hood is the same
shape in every frame, so it should have near-zero standard deviation across frames. Run over
800 frames of the whole recording, that test finds **no static pixels anywhere**, minimum 8.82.
Two reasons, both worth recording because both would have produced a wrong crop:

- The hood is reflective. It shows the road and the sky, so its pixels change as the car moves.
- track2 is lit very differently from track1, and pooling the two puts a large lighting variance
  into every pixel in the frame.

Restricting the measurement to one track at a time and to the centre columns, where the hood
arc reaches highest, gives a clean answer:

| Row | track1 centre std | track2 centre std | track1 edge std |
|---|---|---|---|
| 130 | 37.07 | 35.83 | 36.70 |
| 136 | 36.30 | 36.16 | 35.90 |
| **138** | **23.80** | **20.50** | 37.56 |
| 146 | 14.32 | 12.90 | 38.21 |

The drop lands between row 136 and row 138 on **both tracks independently**, while the edge
columns carry straight on. `CROP_BOTTOM = 137`. The convention's 25 rows would have cut two rows
of road as well.

**The top line, the sky.** There is no equivalent physical landmark, so the criterion is which
rows carry steering signal at all. For each image row, correlate that row's horizontal intensity
centroid against the steering target over 1,500 frames. A row showing road ahead swings sideways
with the steering command; sky and distant scenery do not.

| Row | sky pixel fraction | correlation with steering |
|---|---|---|
| 40 | 0.21 | 0.106 |
| 50 | 0.10 | 0.115 |
| 60 | 0.01 | 0.157 |
| 70 | 0.03 | 0.234 |
| 80 | 0.03 | **0.327** |
| 95 | 0.05 | 0.205 |
| 110 | 0.07 | 0.091 |

Signal rises past 0.2 at row 66, peaks near row 80, and is back under 0.2 by row 96. Sweeping the
top line over the retained band 60 to 136:

| CROP_TOP | rows kept | mean correlation per kept row |
|---|---|---|
| 50 | 87 | 0.156 |
| 55 | 82 | 0.158 |
| **60** | **77** | **0.159** |
| 65 | 72 | 0.158 |
| 70 | 67 | 0.154 |

The curve is flat, which is itself the finding: this choice does not matter much, and any value
between 50 and 65 is defensible. 60 is taken because it maximises the mean and is where sky
falls to 1 percent of the row. Note what the flatness rules out: a claim that the crop was tuned
for accuracy. It was not, and a later run that improves after moving this line by five rows is
reporting noise.

**Decision.** `CROP_TOP = 60`, `CROP_BOTTOM = 137`, keeping 77 of 160 rows at full width. The
full width is kept deliberately: the road leaves the frame sideways on the sharp corners, which
is exactly where the steering signal is largest.

**Rejected.** The Udacity 60/25 pair, on the hood measurement. Cropping the width to centre the
road, because it would discard the corner evidence. Aspect-preserving resize, because DESIGN 6.2
fixes the input at 66x200 and every frame is stretched identically, so the distortion is a
constant the first convolution can absorb.

---

## R10 - The brightness range comes from the recording, not from the convention

**Question.** DESIGN 6.2 asks for "random brightness" without a range. The usual choice is a
multiplier drawn from 0.5 to 1.5.

**Measured.** Mean luminance of the cropped frame, 1,200 frames per track:

| Track | p5 | p50 | p95 | std |
|---|---|---|---|---|
| track1 | 129.5 | 142.6 | 156.8 | 9.0 |
| track2 | 51.4 | 126.6 | 150.6 | 27.5 |

The two tracks are not the same problem. track1 is uniformly lit and sits in a narrow band;
track2 has deep shadowed sections and spans a factor of three. Pooled, p5 to p95 is 0.51 to 1.13
of the median.

**Decision.** `BRIGHTNESS_RANGE = (0.50, 1.15)`, covering the observed spread and stopping there.

**Rejected: 0.5 to 1.5.** Nothing in this recording is brighter than 1.17 times the median, so
the top third of that range trains the model on a lighting condition the simulator cannot
produce. The model is evaluated on this simulator, so robustness to conditions outside it buys
nothing measurable and dilutes the batch.

**The flip probability is 0.5 and is doing real work.** Training targets run 43.4 percent left
against 37.1 percent right, mean -0.0296. Both tracks are loops driven in one direction, so the
recording is genuinely left-biased. 0.5 is chosen over a tuned value because at exactly 0.5 the
flip's effect on the target distribution is symmetrisation, which can be stated analytically
rather than sampled. That matters because this feature has to report the training target
distribution, and the flip is drawn per epoch.

---

## R11 - The balancing fraction, once both sides are counted the same way

**Finding.** `BALANCE_KEEP_FRACTION` was 0.30, derived from the rule "reduce the zero spike until
it is no larger than the next most common lattice value". Recomputed on the training split, 0.30
**breaks that rule**: it leaves zeros at 7.75 percent against a runner-up at 7.28.

**Cause, and it is not the row set.** Moving from all 32,443 rows to the 25,957 training rows
shifts the figures slightly (zeros 20.38 to 20.35 percent, runner-up -0.25 at 6.17 to 6.29).
The real error is that the two sides of the comparison were counted on different bases: the zero
share raw, the runner-up on the 0.05 lattice. A side-camera target of 0.017 is not an exact zero,
so it never entered the zero count, but it does land in the +0.00 lattice bin. The spike was
therefore compared against a number computed a different way, and looked smaller than it is.

**Which basis is right.** The lattice, because that is where M5 compares the distributions. On
raw values the runner-up is -1.00 at 3.41 percent, which is a fact about the offset clipping and
not about the driving: side-camera targets carry a continuous jitter and collide nowhere except
at the clip limits.

**Decision.** `BALANCE_KEEP_FRACTION = 0.27`, the largest fraction satisfying the rule.

| Keep | Samples | Zero share | Runner-up | Rule holds |
|---|---|---|---|---|
| 0.25 | 66,479 | 6.70 | 7.37 | yes |
| **0.27** | **66,783** | **7.12** | **7.33** | **yes** |
| 0.28 | 66,935 | 7.33 | 7.32 | no |
| 0.30 | 67,239 | 7.75 | 7.28 | no |

Unlike the crop sweep in R9, this crossing is sharp rather than flat, so the second decimal is
carrying real information here rather than false precision.

**Removal still targets exactly zero** (`ZERO_STEERING_BAND` 0.0) while the shares are reported
on the lattice. The two are deliberately different: the neighbouring lattice levels are genuine
human decisions and are not candidates for removal, but they do count toward the spike the rule
measures.

---

## R12 - Balancing lost on both axes, and the reason is the camera augmentation

**What was predicted.** DESIGN 6.2 justified training two runs on a trade: balancing produces
the better predictor while deliberately moving the prediction distribution away from the human
one, and that distribution is what M5 compares. One run wins accuracy, the other wins
distributional closeness, and the trade is the finding.

**What happened.** Balanced lost both.

| Axis | Unbalanced | Balanced | Delta |
|---|---|---|---|
| Validation MSE | 0.086670 | 0.090899 | +0.004229 |
| KL from human, on the lattice | 1.143888 | 1.206980 | +0.063091 |

**Why, and this is the more useful result.** Neither model reproduces the human's zero spike at
all:

| | Exact-zero share |
|---|---|
| Human validation rows | **57.2 percent** |
| Training targets after three-camera augmentation | 20.35 percent |
| Training targets after balancing | 7.12 percent |
| Unbalanced model's predictions | 4.8 percent |
| Balanced model's predictions | 4.6 percent |

The distance from the human distribution is dominated by that missing spike, not by anything
balancing does. Balancing pushes the model further from zero, so it widens the dominant gap
rather than closing it, and loses on the axis it was supposed to win.

**The first-order effect was never framed as a distributional choice.** The three-camera
augmentation cut the zero share from 57 percent of rows to 20 percent of samples before
balancing touched anything. It exists to teach recovery from lateral displacement, which is a
control argument, and its side effect on the prediction distribution is roughly eight times
larger than the effect of the policy that was explicitly chosen for distributional reasons.

**What this does not license.** It does not mean the augmentation should be removed to win the
KL comparison. A model that predicts zero 57 percent of the time would score well on that metric
and drive badly, since the spike is an artefact of a human holding a keyboard steady rather than
a steering strategy worth imitating. The finding is that **the distributional axis was being
driven by a decision nobody was watching**, and M5 needs to know that before it reads anything
into a KL figure.

**Kept as measured.** Both runs stand, the comparison reports both deltas, and the report states
plainly that the predicted trade did not appear. `_read_the_outcome` in `bc.evaluate` branches on
which of the four outcomes occurred rather than asserting the expected one, because a report that
hardcodes the hypothesis cannot contradict it.

---

## R13 - The reproduction tolerance, measured rather than chosen

**Question.** R8 decided that training reproduces to a tolerance and that the tolerance would be
derived by running the same seed twice rather than picked in advance. This is that measurement.

**What was run.** `bc_repro_a_v01` and `bc_repro_b_v01`, both `--policy none --seed 42`, on the
same machine and the same split digest as `bc_unbalanced_v01`. That gives **three** runs of one
configuration rather than two, since the original reference run is the same configuration and
belongs in the sample.

| Run | Reported val MSE | Best epoch | Duration |
|---|---|---|---|
| `bc_unbalanced_v01` | 0.08666985 | 8 | 337 s |
| `bc_repro_a_v01` | 0.08668462 | 8 | 371 s |
| `bc_repro_b_v01` | 0.08641127 | 8 | 328 s |

Mean 0.0865886, sample standard deviation 0.00015373, **range 0.00027334**, which is 0.32 percent
of the mean.

**Where the non-determinism enters, and where it does not.** The `baseline_error` is
0.153622828786396 in all three runs, identical to the last digit, and `n_train_samples`,
`n_val_samples`, `parameter_count` and the split digest all match exactly. Everything before the
GPU is bit-for-bit reproducible: the split, the sample build, the per-sample camera offsets, the
balancing. The spread is confined to training itself, which is what R8 predicted and is worth
having confirmed rather than assumed, because a seeding bug in the data pipeline would look like
GPU noise in the final number and be much more serious.

It enters immediately rather than accumulating from a fixed start. Epoch 1 training error is
0.1322998, 0.1324786 and 0.1321905 across the three, so the runs have already diverged after one
pass. That is the signature of cuDNN selecting different kernels, not of a seed being applied
late.

**The reported figure is a minimum, and its spread is not the per-epoch spread.** All three runs
independently selected **epoch 8** as their best, and at epoch 8 the three-run spread is 0.000273.
At epoch 4 it is 0.005325 and at epoch 12 it is 0.004381, roughly twenty times larger. Early
stopping reports the minimum over 13 noisy epochs, so the quantity being reproduced is a selected
statistic that is tighter than the process generating it. **The tolerance below applies to the
reported best-epoch validation error and to nothing else.** Quoting it for an intermediate epoch,
or for a run that stopped at a different epoch, would understate the real variation by an order
of magnitude.

**Decision: the reproduction tolerance is 0.0005 absolute on the reported validation MSE**, a
little under twice the observed range. It is set above the measurement rather than at it because
three runs cannot estimate a tail: the range of a sample of three is a lower bound on the spread
of the process, not an estimate of it. A tolerance set exactly at 0.000273 would be met by the
runs that produced it and fail on the fourth.

**What this licenses and what it does not.** Reported validation errors agree to about the third
decimal place, so the fourth is noise and `comparison.md` quoting six decimals states more
precision than the process has. The consequence that matters is for the headline comparison: the
accuracy delta between the balanced and unbalanced runs is 0.004229, **15 times the observed
run-to-run range** and 8 times the tolerance, and the distribution delta of 0.063091 is larger
still. Both findings in R12 survive the noise comfortably, which is the question this measurement
exists to answer. A future difference smaller than 0.0005 would not.

The tolerance is for one machine, one GPU and one torch build. Nothing here measures agreement
across devices, and T039 records the same limit for evaluation.

---

## Summary of decisions

| ID | Decision | Forced or chosen |
|---|---|---|
| R1 | Third environment `.venv-bc`, pinned in `requirements-bc.txt` | Forced by measurement: neither existing environment has the needed packages |
| R2 | Contiguous block holdout, 10 blocks per track, 2 held out, 8 s guard | Forced: session-level holdout was measured to be unavailable (2 sessions, 0.5 s largest gap). The guard width is derived from steering autocorrelation |
| R3 | Store continuous predictions; quantise at comparison time | Chosen, consistent with DESIGN section 7 |
| R4 | Camera offset jittered per sample over 0.10 to 0.30, drawn once from the seed, mean still 0.20 | Forced by measurement: the constant parked 40.6 percent of training targets on two lattice points. The range was swept, and 0.05 to 0.35 rejected for inflating the genuine high-steering tail |
| R5 | Reuse `stats.describe` and `relative_frequency_histogram` | Forced by Principle IX plus the risk of definition drift |
| R6 | Per-track view from the path marker, one load | Forced by feature 002's pooling finding |
| R7 | Measure loader throughput before building any cache | Chosen, to avoid optimising an unobserved bottleneck |
| R8 | Exact reproduction for evaluation, tolerance for training | Forced by GPU non-determinism |
| R9 | Crop rows 60 to 137, full width | The bottom line is forced by measurement, the same row on both tracks. The top line is chosen from a flat sweep, and the flatness is recorded so no later run can claim the crop was tuned |
| R10 | Brightness 0.50 to 1.15, flip at 0.5 | Forced by measurement: the range covers the observed p5 to p95 luminance spread. The usual 0.5 to 1.5 was rejected for synthesising light the simulator never produces |
| R11 | `BALANCE_KEEP_FRACTION` 0.30 to 0.27 | Forced: at 0.30 the constant broke the rule it was derived from, because the zero share was counted raw against a runner-up counted on the lattice |
| R12 | Both runs kept; the predicted trade did not appear | Measured. Balanced lost accuracy and distributional closeness. The distributional axis is dominated by the three-camera augmentation, whose effect is about eight times larger than the policy chosen for distributional reasons |
| R13 | Reproduction tolerance 0.0005 absolute on reported val MSE | Measured over three same-seed runs: range 0.000273, stdev 0.000154. Set above the observed range because three runs bound the spread rather than estimate it. Everything before the GPU reproduces exactly |
