# Contract: `python/bc` module API and test obligations

Phase 1. The interface this feature exposes and the evidence each part must produce. Written
before the code, so the tests can be written against the contract rather than against whatever
the implementation happens to do.

The pattern follows `specs/003-unity-environment/contracts/track-generator-api.md`: every
contract entry carries **both directions of evidence**, a case that must pass and a case that
must fail. A test suite that only shows the happy path proves that the code runs, not that it
is right.

---

## `bc.config`

Every named constant, in one module, each with a comment naming the decision it came from. No
number appears anywhere else in the package.

| Constant | Value | Source |
|---|---|---|
| `SEED` | 42 | matches `eda.config.SEED`, so the project has one seed convention |
| `VAL_FRACTION_TARGET` | 0.2 | DESIGN 6.2's 80/20, as a target rather than a guarantee (research R2) |
| `N_BLOCKS` | 10 | contiguous blocks per track (research R2) |
| `N_HOLDOUT` | 2 | blocks per track assigned to validation, evenly spaced |
| `GUARD_SECONDS` | 8.0 | **derived** from steering autocorrelation: shortest lag where both tracks fall below 0.1 (research R2) |
| `CAMERA_OFFSET` | 0.2 | **chosen, not derived** (research R4) |
| `INPUT_HEIGHT`, `INPUT_WIDTH` | 66, 200 | PilotNet standard, DESIGN 6.2 |
| `STEERING_LATTICE_STEP` | 0.05 | measured in feature 002 |
| `ZERO_STEERING_BAND` | to be decided in the design amendment | what counts as "near zero" for balancing |
| `BALANCE_KEEP_FRACTION` | to be decided in the design amendment | how much of the near-zero mass survives |

**Contract**

- `bc.config` imports nothing from `bc`, and nothing from `eda` except `eda.config` for the
  shared seed. A constant defined in two places is a constant that will disagree.

**Evidence**

- MUST pass: every constant this package uses is reachable from `bc.config`.
- MUST fail: a grep for bare numeric literals in the other `bc` modules finds nothing outside
  test files and array indexing.

---

## `bc.split`

```
plan_split(dataset, seed, val_fraction_target) -> SplitPlan
write_split(plan, path) -> None
read_split(path) -> SplitPlan
verify_no_leak(plan) -> None            # raises, naming the offending pair
```

**Contract**

- Cuts each track into `N_BLOCKS` contiguous blocks by row order and assigns `N_HOLDOUT` evenly
  spaced blocks per track to validation.
- Discards every frame within `GUARD_SECONDS` of a block boundary, **from both sides**.
  Adjacency is symmetric, so guarding only the validation side leaves training frames sitting
  against the boundary.
- Deterministic in the seed, across runs and across processes.
- `verify_no_leak` raises if the minimum time distance between any training frame and any
  validation frame is less than `GUARD_SECONDS`, naming the offending pair of row indices and
  the distance found.
- `SplitPlan.val_fraction_actual` is derived and reported. The function does not move a boundary
  to hit the target: that would be fitting the split to a number instead of to the data.

**Evidence**

- MUST pass: same seed, two calls, byte-identical `split.json` (SC-002).
- MUST pass: `verify_no_leak` accepts a plan built by `plan_split` on the real recording.
- MUST fail: a hand-built plan with a training frame 1 s from a validation frame is rejected,
  and the message names both row indices and the measured distance.
- MUST fail: a plan with an empty validation side is rejected at construction.
- MUST pass: guard frames appear in **neither** side. The sum of train, validation and discarded
  equals the row count, so no frame is silently lost or double counted.
- MUST pass: `val_fraction_actual` may differ from the target. The test asserts the gap is
  reported, not that it is zero. On the current data the expected value is about 0.177.

---

## `bc.dataset`

```
build_samples(dataset, rows, use_side_cameras) -> list[SampleSpec]
apply_balancing(samples, policy) -> tuple[list[SampleSpec], BalancingStats]
preprocess(image) -> array                 # crop, resize, colour space, normalise
augment(image, steering, rng) -> tuple     # horizontal flip and brightness
verify_images_exist(samples) -> None       # raises, naming the first missing file
```

**Contract**

- `build_samples` with `use_side_cameras=False` produces center-only samples, all with
  `is_augmented` false. This is the only form permitted for the validation set (FR-007).
- `apply_balancing` operates on training samples only and returns statistics describing what it
  removed, so the induced shift is measurable (FR-023).
- `augment` **negates steering on a horizontal flip.** The constitution names this test by hand
  in Principle VIII.
- `preprocess` is deterministic. `augment` takes an explicit rng and never touches global random
  state, matching the rule `python/track/generator.py` already follows.
- `verify_images_exist` checks the whole set before training and raises naming the first missing
  path. It never skips a row silently, because a silent skip changes the denominator of every
  statistic that follows.

**Evidence**

- MUST pass: horizontal flip negates the steering target, checked on a non-zero value so a
  sign error cannot hide behind zero.
- MUST pass: `preprocess` returns the stated shape for an arbitrary input image.
- MUST pass: the same rng seed produces the same augmentation twice.
- MUST fail: a sample list containing a missing image raises, and the message contains that
  filename.
- MUST fail: `build_samples` for a validation split never yields `is_augmented` true. Asserted
  over the real split, not over a hand-built example.
- MUST pass: side-camera targets equal the recorded value plus or minus `CAMERA_OFFSET`, clipped
  to [-1, 1], with the clipping exercised at both extremes.

---

## `bc.model`

```
build_model() -> Module
parameter_count(model) -> int
```

**Contract**

- Accepts a batch of the shape `preprocess` produces and returns one scalar per sample.
- Contains no data-dependent constant. Every shape comes from `bc.config`.

**Evidence**

- MUST pass: a forward pass on a batch of the documented input shape returns the batch size in
  outputs. The constitution names this test by hand.
- MUST fail: a batch of the wrong channel count raises rather than silently broadcasting.
- MUST pass: `parameter_count` is reported in the run record, so an accidental architecture
  change is visible in a diff of the results rather than only in the code.

---

## `bc.train`

```
resolve_device(allow_cpu) -> Device        # raises unless allow_cpu when no GPU is found
train(policy, split, seed, allow_cpu) -> RunRecord
```

**Contract**

- `resolve_device` **raises** when no usable GPU is found and `allow_cpu` is false. A long CPU
  training that nobody chose is the failure FR-009 exists to prevent.
- Writes the `RunRecord` next to the checkpoint, always, including when the run ends early or
  fails to beat the baseline.
- Computes the mean-predictor baseline on the same validation set and stores it in the record
  (FR-011).
- Seeds Python, numpy and torch from the single seed and records it.
- Stores `split_digest` so a checkpoint can never be silently paired with a different split.

**Evidence**

- MUST fail: with no GPU visible and `allow_cpu` false, `resolve_device` raises, and the message
  says how to override.
- MUST pass: with `allow_cpu` true, it returns a CPU device and the record says so.
- MUST pass: a run that does not beat the baseline still produces a complete `RunRecord` with
  `beat_baseline` false. Tested with a deliberately untrained model, so the negative path is
  exercised without waiting for a real training run.
- MUST pass: the record's `n_val_samples` equals the unbalanced validation count for both
  policies (FR-022).

---

## `bc.evaluate`

```
predict(checkpoint, split) -> PredictionSet
summarise(values, name, scope) -> DistributionReport
quantise_to_lattice(values) -> array
compare_runs(balanced, unbalanced) -> BalancingComparison
```

**Contract**

- `predict` refuses if the checkpoint's `split_digest` does not match the split being used.
- `summarise` delegates to `eda.stats.describe` and `eda.stats.relative_frequency_histogram`.
  It computes no statistic itself (research R5).
- Every distribution is reported pooled and per track. There is no pooled-only path (FR-016).
- `quantise_to_lattice` applies `round(x / step) * step` clipped to [-1, 1], and any report
  built from its output is marked `lattice_applied` true.
- `compare_runs` refuses to render if the two runs differ in anything beyond the balancing
  policy and the training sample count (FR-021).

**Evidence**

- MUST pass: a `DistributionReport`'s relative frequencies sum to 1 within tolerance (SC-004).
- MUST pass: every distribution appears in all three scopes; a report missing `track2` fails.
- MUST fail: `predict` with a mismatched `split_digest` raises rather than returning numbers.
- MUST fail: `compare_runs` on two records that differ in learning rate raises, naming the
  field. This is the test that keeps the headline comparison honest.
- MUST pass: `quantise_to_lattice` maps onto exactly the 41 human levels and no others, checked
  by set equality against the levels feature 002 measured.
- MUST pass: `summarise` on the human column reproduces the figure M1 already recorded for it.
  This is the cross-check that the shared functions really are shared.

---

## Artifacts this feature writes

| Path | Contract |
|---|---|
| `results/bc/split.json` | regenerable byte-identically from the seed |
| `results/bc/run_balanced/` | checkpoint plus `RunRecord`, never one without the other |
| `results/bc/run_unbalanced/` | as above |
| `results/bc/comparison.md` | the two deltas side by side, no single verdict |
| `results/plots/bc_*.png` | prediction against human, residuals, and the two policies overlaid |
| `results/EXPERIMENTS.md` | one entry per run, written in the same session as the run (Principle VI) |

**Nothing is written into `dataset/`, into `python/eda/`, or into Unity `Assets/`.**
