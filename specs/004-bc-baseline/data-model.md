# Data Model: Behavioral Cloning Baseline (M4)

Phase 1. The types this feature introduces, what each one guarantees, and the validation rules
that come out of the requirements. Types that already exist in `python/eda` are listed as
dependencies, not redefined.

A rule this whole model follows, taken from `python/track/vehicle.py`: **a value that can be
derived is never also stored.** A stored copy is free to disagree with its source, and the
disagreement is invisible.

---

## Existing types this feature depends on (read-only)

| Type | Module | What this feature uses it for |
|---|---|---|
| `TrackDataset` | `eda.loader` | the loaded recording: the dataframe plus resolved image paths |
| `RecordingSession` | `eda.integrity` | contiguous capture segments; the unit the split operates on |
| `DistributionSummary` | `eda.stats` | the six figures Principle IX requires, for any distribution |

None of these are modified. If this feature needs a field they do not carry, it wraps them
rather than editing `python/eda`, which is owned by features 001 and 002.

---

## `SplitPlan`

The assignment of contiguous blocks to training or validation, plus the guard frames belonging
to neither. Produced once from a seed, written to `results/bc/split.json`, and read by both
training runs so they cannot disagree.

| Field | Type | Meaning |
|---|---|---|
| `seed` | int | the seed the assignment was drawn with |
| `n_blocks`, `n_holdout`, `guard_seconds` | int, int, float | the rule, stored so the file explains itself |
| `train_rows` | list[int] | row indices assigned to training |
| `val_rows` | list[int] | row indices assigned to validation |
| `guard_rows` | list[int] | rows discarded for being within the guard of a boundary |
| `n_train_rows`, `n_val_rows`, `n_guard_rows` | int | derived counts |
| `val_fraction_actual` | float | derived: `n_val_rows / (n_train_rows + n_val_rows)` |
| `val_fraction_target` | float | what was asked for, kept so the gap is visible |
| `block_bounds` | list of (track, block index, first row, last row, first time, last time, assignment) | enough to verify the leak-free property without re-deriving it |
| `min_train_val_gap_s` | float | derived: the smallest time distance between any training frame and any validation frame. The single number FR-004 turns on |

**Validation rules**

- `train_rows`, `val_rows` and `guard_rows` are pairwise disjoint and together cover every row.
  No frame is silently lost or double counted.
- Both training and validation sides are non-empty.
- `min_train_val_gap_s` is at least `guard_seconds`. This is the machine-checkable form of
  FR-004 and is asserted in `test_bc_split.py`. On the current data it should be about 8.0.
- `val_fraction_actual` is **reported, never forced**. Blocks are integer-sized and the guard
  eats into them, so the achieved figure lands near 0.177 against a 0.20 target. Moving a
  boundary to close that gap would be fitting the split to a number instead of to the data
  (research R2).
- Regenerating from the same seed produces a byte-identical file (SC-002).

---

## `SampleSpec`

One training or validation example, before any image is decoded. A row plus which camera it
refers to and what target that camera implies.

| Field | Type | Meaning |
|---|---|---|
| `row_index` | int | index into the loaded recording |
| `camera` | enum: center, left, right | which of the three images |
| `steering` | float | the target after any camera offset |
| `is_augmented` | bool | true for left and right, false for center |
| `track` | str | track1 or track2, from the path marker (research R6) |
| `block` | int | which contiguous block this row belongs to |
| `camera_offset` | float or None | the offset actually drawn for this sample, None for center |

**Validation rules**

- `is_augmented` is true if and only if `camera` is not center.
- **No sample with `is_augmented` true may appear in the validation set** (FR-007). Asserted in
  the tests, not merely intended: a synthesised target is not a human target, and validating
  against one scores the model on our own invention.
- `steering` for a center sample equals the recorded value exactly. For a side camera it is the
  recorded value plus or minus an offset **drawn per sample** from `CAMERA_OFFSET_RANGE`, clipped
  to [-1, 1]. The draw is seeded and happens once, not per epoch, so the training target
  distribution is fixed and inspectable (research R4).
- `camera_offset` is stored on the sample. A drawn value that is not recorded cannot be audited,
  and the whole reason for jittering was that the previous constant was invisible in the output.
- Every `SampleSpec` resolves to an image file that exists. Checked once, before training, over
  the whole set (FR-002).

---

## `BalancingPolicy`

Which of the two runs this is. Deliberately a small closed type rather than a boolean, so the
run record says what it did in words.

| Value | Meaning |
|---|---|
| `none` | train on the recorded sample distribution as it is |
| `downsample_zero` | reduce the near-zero steering samples toward the stated cap |

**Validation rules**

- Applies to the **training** samples only. The validation set is always unbalanced (FR-022),
  or the two runs would be scored on different yardsticks.
- The policy records how many samples it removed and what the resulting steering histogram
  looks like, so the induced distribution shift is a number rather than an assumption (FR-023).

---

## `RunRecord`

A checkpoint is never stored alone. This is what makes SC-008 satisfiable: a reader learns what
produced a number without reading the code.

| Field | Type | Meaning |
|---|---|---|
| `run_id` | str | `bc_balanced_v01`, `bc_unbalanced_v01`, matching the EXPERIMENTS.md convention |
| `policy` | `BalancingPolicy` | the one thing the two runs differ in |
| `seed` | int | |
| `split_digest` | str | digest of `split.json`, so a run cannot be paired with the wrong split |
| `device` | str | the device actually used, reported not assumed (FR-009) |
| `hyperparameters` | mapping | learning rate, batch size, epochs, optimiser, offset |
| `n_train_samples` | int | after balancing, so the effect of the policy is visible |
| `n_val_samples` | int | always the unbalanced count |
| `duration_s` | float | |
| `epochs_completed` | int | may be fewer than requested if stopped early |
| `val_error` | float | the headline number |
| `baseline_error` | float | mean-predictor error on the same validation set (FR-011) |
| `beat_baseline` | bool | derived: `val_error < baseline_error` |

**Validation rules**

- `split_digest` must match the split file being used at evaluation time, or the evaluation
  refuses. Pairing a checkpoint with a different split silently reports a meaningless number.
- `beat_baseline` is derived, never stored independently.
- A run with `beat_baseline` false is still a valid `RunRecord`. It is reported as a negative
  result (SC-003), not discarded.

---

## `PredictionSet`

The model's output over the validation set, in recording order, with everything M5 needs
derived from it.

| Field | Type | Meaning |
|---|---|---|
| `run_id` | str | which run produced this |
| `order` | list[int] | row indices in original recording order (FR-013) |
| `predicted` | array[float] | raw continuous predictions, never quantised at this stage (research R3) |
| `actual` | array[float] | the recorded human values |
| `residual` | array[float] | derived: `predicted - actual` |
| `track` | array[str] | per-sample track label, for the per-track view |

**Validation rules**

- `order` is strictly increasing within a session, so consecutive differences are real
  neighbours and the smoothness quantity in FR-015 means something.
- `residual` is derived on read, never stored as a third array that could drift.
- `predicted` is stored unquantised. The lattice view is produced at comparison time and is
  labelled as such wherever it appears (FR-017).

---

## `DistributionReport`

What this feature emits for every distribution it touches: predictions, residuals, and per-frame
absolute change, each pooled and per track.

| Field | Type | Meaning |
|---|---|---|
| `name` | str | which distribution, for example `predicted_steering` |
| `scope` | str | `pooled`, `track1` or `track2` |
| `summary` | `DistributionSummary` | the six Principle IX figures, from `eda.stats.describe` |
| `histogram` | (edges, relative_frequency) | from `eda.stats.relative_frequency_histogram` |
| `lattice_applied` | bool | whether the 0.05 grid was applied before summarising |

**Validation rules**

- `relative_frequency` sums to 1 within floating tolerance (SC-004).
- Every reported distribution exists in all three scopes. Pooled-only is forbidden (FR-016),
  because feature 002 already showed pooling hides a constant column on this dataset.
- `lattice_applied` is never left implicit. A comparison against the human column with it false
  must carry its justification (FR-017).

---

## `BalancingComparison`

The deliverable that the clarification decision exists to produce.

| Field | Type | Meaning |
|---|---|---|
| `balanced` | `RunRecord` | |
| `unbalanced` | `RunRecord` | |
| `accuracy_delta` | float | derived: difference in validation error |
| `distribution_delta` | float | derived: difference in distance from the human distribution |
| `same_split` | bool | derived: both runs carry the same `split_digest` |
| `differing_fields` | list[str] | derived: which hyperparameters differ between the two records |

**Validation rules**

- `differing_fields` must contain `policy` and `n_train_samples` and **nothing else** (FR-021).
  If it contains anything more, the comparison measures more than balancing and the report says
  so rather than presenting the number.
- `same_split` must be true or the comparison refuses to render.
- The two deltas are reported side by side and are **not** collapsed into a verdict. A run that
  wins on accuracy and loses on distribution is the expected outcome (FR-023).

---

## Entity relationships

```text
TrackDataset (eda)
    |
    +-- split_sessions (eda) --> 2 sessions, one per track (the unit blocks are cut within)
    |                                  |
    |                        cut into N_BLOCKS each, hold out N_HOLDOUT,
    |                        discard anything within GUARD_SECONDS of a boundary
    |                                  |
    |                                  v
    |                             SplitPlan  ---- results/bc/split.json
    |                            /     |     \
    |               train blocks   guard rows   val blocks
    |                     |        (neither)         |
    +--> [SampleSpec] ----+                          +--> [SampleSpec], is_augmented always false
              |
              v
       BalancingPolicy (training samples only)
              |
              v
         RunRecord x2  ---- results/bc/run_*/
              |
              v
        PredictionSet  --> DistributionReport (pooled, track1, track2)
              |
              v
      BalancingComparison  ---- results/bc/comparison.md
```
