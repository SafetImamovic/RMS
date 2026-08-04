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
is cheap for the guarantee, and it lands at 17.7 percent validation against a 20 percent target.

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
- **Decision**: keep 0.2, record it as a **chosen hyperparameter**, and report its effect rather
  than assume it is negligible. Since two runs are already being produced for the balancing
  question, the offset is held identical across both, so it never becomes a confound.
- **What would change this**: if the side-camera augmentation turns out to dominate the result,
  the honest response is a sensitivity check at a second offset value, recorded as a finding.
  That is a follow-up, not a blocker, and it is out of scope unless the first runs suggest it.
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

## Summary of decisions

| ID | Decision | Forced or chosen |
|---|---|---|
| R1 | Third environment `.venv-bc`, pinned in `requirements-bc.txt` | Forced by measurement: neither existing environment has the needed packages |
| R2 | Contiguous block holdout, 10 blocks per track, 2 held out, 8 s guard | Forced: session-level holdout was measured to be unavailable (2 sessions, 0.5 s largest gap). The guard width is derived from steering autocorrelation |
| R3 | Store continuous predictions; quantise at comparison time | Chosen, consistent with DESIGN section 7 |
| R4 | Camera offset stays 0.2, recorded as a choice | Chosen and labelled as such, since no derivation exists |
| R5 | Reuse `stats.describe` and `relative_frequency_histogram` | Forced by Principle IX plus the risk of definition drift |
| R6 | Per-track view from the path marker, one load | Forced by feature 002's pooling finding |
| R7 | Measure loader throughput before building any cache | Chosen, to avoid optimising an unobserved bottleneck |
| R8 | Exact reproduction for evaluation, tolerance for training | Forced by GPU non-determinism |
