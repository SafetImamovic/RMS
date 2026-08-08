# Tasks: Behavioral Cloning Baseline (M4)

**Input**: Design documents from `specs/004-bc-baseline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. Constitution Principle VIII names three BC tests by hand, and
`contracts/bc-module-api.md` carries a test contract with both directions of evidence for every
module.

**Organization**: grouped by user story so each can be finished and checked on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel, different files, no dependency on an unfinished task
- **[Story]**: US1, US2, US3, mapping to the priorities in spec.md
- Every task names the file it touches
- Tasks inserted after the first pass carry a letter suffix. Existing IDs stay put, so a review
  comment that names a task still names the same task

## Path conventions

- Python: `python/bc/` for source, `python/tests/` for tests, matching `python/eda/`
- Outputs: `results/bc/` and `results/plots/`
- The dataset stays where it is, git-ignored, and is never written to

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: the package skeleton and the environment. No logic.

- [X] T001 Create `python/bc/__init__.py` as an empty package, matching the `python/eda/` and `python/track/` layout
- [X] T002 Write `requirements-bc.txt` pinning torch 2.6.0+cu124 with its index URL, plus pandas, numpy, Pillow and matplotlib. Pin exact versions, not ranges: Principle VI requires a reader to reconstruct the environment, and a range reconstructs a different one next month
- [X] T003 Create `.venv-bc` from Python 3.10.11 and install `requirements-bc.txt`. Confirm `torch.cuda.is_available()` is true and record the reported device name. `.gitignore` already covers `.venv-*/`, so nothing there needs changing
- [X] T004 [P] Create `results/bc/` with a `.gitkeep`
- [X] T005 [P] Create `results/EXPERIMENTS.md` with its header and column format. The constitution names it a companion document and Principle VI requires one entry per training run, but the file does not exist yet, so the first BC run would have nowhere to be logged

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: measure the things the design decisions depend on, then write those decisions down
before any code implements them.

**CRITICAL**: no User Story work begins until T009 is committed. Principle V requires the design
to be written before it is implemented, and T006 through T008 exist because three of those
decisions cannot honestly be written until something is measured.

- [X] T006 Write `python/bc/survey.py` and run it: count recording sessions in the combined dataset via `eda.integrity.split_sessions`, report each session's row count, time range and track, and list the validation fractions actually achievable by holding out whole sessions. Write to `results/bc/session_survey.md`
  - **This blocking reconnaissance did its job on 2026-08-04: it killed the planned split before any code was built on it.** Measured ad hoc against `eda` under `.venv`, since the survey needs pandas but no torch, so Phase 1 does not actually block it. `python/bc/survey.py` still has to be written to make the measurement reproducible (see T006a)
  - `split_sessions` yields exactly **two** sessions on the combined file, one per track marker: `track1data` 10,615 rows, `track2data` 21,828 rows. Session-level holdout therefore degenerates into train-on-track1, validate-on-track2, which research R2 had already rejected as measuring transfer between two driving profiles rather than generalisation within one
  - Finer segmentation is not available either. The **largest gap in either recording is 0.5 s** (track1 0.5 s, track2 0.3 s, from `check_timeline`). These are two continuous takes with nothing to cut on
  - **Replacement chosen and recorded in research R2**: contiguous block holdout with a guard band. 10 blocks per track, 2 held out, every frame within 8 s of a boundary discarded from both sides. Costs 904 frames (2.8 percent) and lands at 17.7 percent validation
  - The 8 s guard is **derived, not picked**: it is the shortest lag at which steering autocorrelation falls below 0.1 on both tracks (track1 +0.085, track2 +0.011). Track1's curve is noisy because 79.3 percent of its steering is zero, so track2 sets the figure
- [X] T006a Write `python/bc/survey.py` so the T006 measurements are reproducible rather than one-off: session counts and time ranges, per-track timeline gaps, steering autocorrelation against lag, and the guard-cost table across candidate block and guard settings. Write to `results/bc/session_survey.md`. Principle VI: the numbers now sitting in research R2 must re-run to the same values
- [X] T007 Extend `python/bc/survey.py` to report the steering histogram of the combined dataset, per track and pooled, using `eda.stats.relative_frequency_histogram`. Report what fraction of samples fall in candidate near-zero bands so `ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` can be chosen against a measurement rather than guessed
- [X] T008 Verify the integrity precondition before anything depends on it: run `eda.loader.check_integrity` over the combined dataset and confirm 32443 rows against 97329 images. Record the result in `results/bc/session_survey.md`. The expected answer is already known from the plan, so a mismatch means the archive is incomplete and every downstream statistic would be computed over the wrong denominator
- [X] T009 Write the **decided** M4 values into `DESIGN.md` section 6 in a `docs:` commit, before any Phase 3 code exists. Four amendments, all in one logical change:
  - **Split**: section 6.2 currently says "Split: 80/20 train/val" with no mention of leakage. Amend to **contiguous block holdout with an 8 s guard band**, 10 blocks per track and 2 held out. State that consecutive frames are near-duplicates, that a random frame split scores the model on frames it effectively trained on, and that session-level holdout was measured to be unavailable because the file contains two sessions and the largest gap is 0.5 s. Record the achieved 17.7 percent and state that it is reported rather than forced, and record that the guard is derived from steering autocorrelation rather than chosen
  - **Balancing**: section 6.2 states downsampling as a single decision. Amend to two runs, and say what the pair is for: balancing produces the better predictor while deliberately moving the prediction distribution away from the human one, and that distribution is what M5 compares. Record `ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` from T007
  - **Camera offset**: section 6.1 states plus or minus 0.2 as if it were derived. Amend to a **jittered offset drawn per sample from 0.10 to 0.30**, mean unchanged at 0.20, drawn once from the seed rather than per epoch. Record why: the constant was measured to place **40.6 percent of training targets on exactly two lattice points**, creating modes the human never produced, and 0.20 is a real lattice value so those modes are indistinguishable from genuine steering in a histogram. Record that 0.05 to 0.35 was swept and rejected for inflating the genuine above-0.30 tail from 27.6 to 33.9 percent (research R4)
  - **Quantisation**: state that this feature stores raw continuous predictions and that the 0.05 lattice treatment happens at comparison time, which is where DESIGN section 7 already assigns it
  - Written 2026-08-04 as four block quotes in DESIGN 6.1 and 6.2, each carrying the measurement it rests on rather than only the conclusion. The two values that were open at planning time are now decided and derived: `ZERO_STEERING_BAND = 0.0` because the neighbouring lattice levels carry 2.6 to 3.8 percent each and are genuine human decisions, and `BALANCE_KEEP_FRACTION = 0.30` from the rule "reduce the zero spike until it is no larger than the next most common lattice value" (6.78 percent against the 6.17 percent held by -0.25)
  - **Superseded at T018**: the keep fraction is now 0.27. 0.30 was derived with the zero share counted raw against a runner-up counted on the lattice, and does not in fact satisfy the rule. DESIGN 6.2 and research R11 carry the correction
- [X] T010 Write `python/bc/config.py` with every named constant from `contracts/bc-module-api.md`, each carrying a comment naming the decision it came from. Import `SEED` from `eda.config` rather than redefining it. No numeric literal appears anywhere else in the package

**Checkpoint**: the measurements exist, the decisions are written down, and the constants live in
one place before any code reads them.

---

## Phase 3: User Story 1 - A trained model whose validation number means something (Priority: P1) MVP

**Goal**: a trained steering predictor with a validation error that measures generalisation, not
memorisation.

**Independent Test**: produce the split, confirm no validation session overlaps a training
session in time, train once, and read the validation error beside the mean-predictor baseline.

### Split

- [X] T011 [US1] Implement `plan_split`, `write_split` and `read_split` in `python/bc/split.py`: cut each track into `N_BLOCKS` contiguous blocks, assign `N_HOLDOUT` evenly spaced blocks per track to validation, and discard every frame within `GUARD_SECONDS` of a boundary **from both sides**. Produce the `SplitPlan` fields from `data-model.md`, with `val_fraction_actual` and `min_train_val_gap_s` derived and reported rather than forced
- [X] T012 [US1] Implement `verify_no_leak` in `python/bc/split.py`, raising when the minimum time distance between any training frame and any validation frame is under `GUARD_SECONDS`, naming both row indices and the distance found. This is the machine-checkable form of FR-004, and it is a stronger check than the session-overlap test the withdrawn plan called for
- [X] T013 [US1] Add the `python -m python.bc.split --seed <n> --val-fraction <f>` command line entry, writing `results/bc/split.json`
  - Achieved on 2026-08-04: train 25,957, validation 5,576, guard 910, fraction 0.1768, minimum train-to-validation gap **8.09 s** against the 8.0 s guard
  - These differ by six rows from the sweep in research R2, which estimated the guard as a fixed row count so nine settings could be compared quickly. `bc.split` trims by real timestamps, so it is the authoritative figure and the sweep is the shortlist that led to it
- [X] T014 [US1] Write `python/tests/test_bc_split.py`: the same seed produces byte-identical output across two calls and across processes; `verify_no_leak` accepts a plan built by `plan_split` on the real recording; a hand-built plan with a training frame 1 s from a validation frame is rejected with both row indices and the distance named; an empty validation side is rejected; train, validation and guard rows are pairwise disjoint and sum to the row count, so no frame is silently lost or double counted; `val_fraction_actual` is asserted to be **reported**, with the test allowing the roughly 0.177 achieved figure to differ from the 0.20 target rather than requiring a match

### Dataset

- [X] T015 [US1] Implement `build_samples` and `verify_images_exist` in `python/bc/dataset.py`. Reading goes through `eda.loader`; this module never reimplements the headerless-CSV or path-rerooting logic (FR-001). A missing image raises and names the first offending file, never skips
  - Measured against the real split: 77,871 training samples (3 x 25,957), 5,576 validation samples with **0 augmented**, offsets in 0.1000 to 0.3000 with mean 0.2001, identical output from the same rows in reversed order
  - `verify_images_exist` clears all 77,871 samples in 3.9 s from one directory listing, and raises with the filename when a path is broken
  - `row_block_map` was needed to fill `SampleSpec.track` and `.block`. It duplicates the block arithmetic in `bc.split`, so the duplication is checked rather than trusted: 0 disagreements against the `block_bounds` of the real plan, over all 32,443 rows
- [X] T016 [US1] Implement `preprocess` in `python/bc/dataset.py`: crop, resize to the configured input size, colour-space conversion and normalisation, deterministic throughout
  - Crop rows **measured, not inherited** (research R9). `CROP_BOTTOM = 137`, the row where centre-column temporal standard deviation drops from about 36 to about 20 on both tracks independently. The whole-frame version of that test finds no static pixels at all, because the hood is reflective and the two tracks are lit differently
  - `CROP_TOP = 60`, chosen from a flat sweep. The flatness is recorded so a later run cannot claim the crop was tuned
  - Output verified as float32 (66, 200, 3) in [-1, 1], identical for array and PIL input, with guards on both channel count and frame size
- [X] T017 [US1] Implement `augment` in `python/bc/dataset.py`: horizontal flip with **steering negation**, plus brightness. Takes an explicit rng and never touches global random state, matching the rule `python/track/generator.py` already follows
  - Brightness range **measured, not the conventional 0.5 to 1.5** (research R10). Pooled p5 to p95 luminance is 0.51 to 1.13 of the median, so the range is 0.50 to 1.15. Nothing in the recording is brighter than 1.17 times the median, and the two tracks are not the same problem: track1 spans 129.5 to 156.8 while track2 spans 51.4 to 150.6
  - Flip probability 0.5 is doing real work, not decoration: training targets run 43.4 percent left against 37.1 percent right, mean -0.0296, because both tracks are loops driven in one direction
  - Verified: flip rate 0.498 over 4,000 draws; negation checked on a non-zero target (0.37 to -0.37); the image is the exact column mirror; brightness touches only the Y channel; the same seed reproduces both outputs; the input array is not mutated
- [X] T017a [US1] Implement the jittered side-camera offset in `python/bc/dataset.py`: draw per sample from `CAMERA_OFFSET_RANGE`, seeded, **once at sample-build time rather than per epoch**, and store the drawn value on the `SampleSpec`. A drawn offset that is not recorded cannot be audited, which is the fault the constant had (research R4)
  - Landed with T015 rather than after it: `build_samples` cannot produce `SampleSpec.steering` for a side camera without the draw, so splitting them would have meant writing a target the next task immediately replaced
  - `draw_camera_offsets` draws the whole array in one vectorised call before the sample loop, so the values do not depend on the order rows are visited in
  - Measured while implementing: **5.42 percent of side targets clip to a steering limit.** The recorded data is already heavy at the rails (4.33 percent of training rows at -1.0, 3.54 percent at +1.0), so clipping stacks on genuine mass rather than creating it. Combined, the two limits hold 3.41 and 2.83 percent of training targets, both under the -0.25 runner-up, so the research R4 concentration threshold still holds
- [X] T018 [US1] Implement `apply_balancing` and the `BalancingPolicy` type in `python/bc/dataset.py`, returning statistics describing exactly how many samples were removed and the resulting histogram, so the induced distribution shift is a number rather than an assumption
  - **`BALANCE_KEEP_FRACTION` corrected from 0.30 to 0.27** (research R11). At 0.30 the constant broke the rule it was derived from, leaving zeros at 7.75 percent against a 7.28 percent runner-up
  - The cause was not the row set. The two sides of the rule were counted on different bases: the zero share raw, the runner-up on the 0.05 lattice. A side-camera target of 0.017 is not an exact zero so it never entered the zero count, but it does land in the +0.00 lattice bin
  - Removal still targets exactly zero while the shares are reported on the lattice, and the docstring says why the two differ
  - Achieved: 77,871 to 66,783 samples, 11,088 removed, zero share 20.35 to 7.12 percent against a runner-up at 7.33. Deterministic across calls, and the surviving samples stay in recording order
- [X] T019 [US1] Write `python/tests/test_bc_dataset.py`: horizontal flip negates the steering target, checked on a **non-zero** value so a sign error cannot hide behind zero (named by Principle VIII); `preprocess` returns the documented shape; the same rng seed reproduces the same augmentation; a missing image raises with the filename in the message; side-camera targets equal the recorded value plus or minus the offset with clipping exercised at both extremes; **no validation sample ever carries `is_augmented` true**, asserted over the real split rather than a hand-built example
  - 31 tests. Suite is now 87, passing under both `.venv-bc` and `.venv`: `bc.dataset` imports no torch, so the sample decisions can still be checked in the M1 environment
  - **The flip test was mutation checked.** Removing the negation from `augment` fails it, along with the mirror-axis test. A test named by the constitution is worth confirming actually bites rather than assuming it does
  - Clipping is exercised at both rails on the real recording rather than a constructed row, and the search fails loudly if either rail is never reached
  - The R4 concentration guard is asserted three ways: no single lattice value holds a quarter of the targets, no two hold a third, and +0.20 and -0.20 are each under 10 percent. The last one is the specific shape the old constant offset produced
  - `test_augment_never_touches_global_random_state` covers a failure whose symptom appears in unrelated code: a function reaching for the global generator makes every other seeded thing in the process irreproducible

### Model

- [X] T020 [P] [US1] Implement `build_model` and `parameter_count` in `python/bc/model.py`. Every shape comes from `bc.config`; no data-dependent constant appears here
  - Reproduced without modification, on purpose. A baseline exists to be the standard answer M5 measures against, so tuning the architecture would make it a worse baseline rather than a better one
  - Measured: **252,219 parameters** against DESIGN 6.2's "about 250k", and a flattened size of **1,152** matching the NVIDIA paper. Both are derived from `CONV_LAYERS` and the input size rather than typed in, so a stride change cannot leave a stale literal behind
  - `ACTIVATION` is a recorded choice, not a measurement: ReLU follows the paper, while much of the Udacity-simulator literature prefers ELU. Not tested here, because a baseline that quietly differs from the architecture it cites is harder to defend than one that matches it
- [X] T021 [US1] Write `python/tests/test_bc_model.py`: a forward pass on a batch of the documented input shape returns one output per sample (named by Principle VIII); a batch with the wrong channel count raises rather than silently broadcasting
  - 12 tests. Suite is now 99 under `.venv-bc`; under `.venv` the model file skips cleanly via `importorskip` rather than failing, so the M1 environment still runs 87
  - Beyond the two contract items: the output is asserted **flat**, because an (N, 1) output against an (N,) target broadcasts to (N, N) and MSE over that still falls during training; the output layer is asserted to have no activation, because a rectifier there makes left turns unreachable and looks like a data problem; and `test_the_model_accepts_exactly_what_preprocess_produces` checks the two halves of the pipeline agree on a shape, which is also where the height-first to channel-first permute is documented
  - `conv_output_size` is a hand-written formula, so it is checked against a real `nn.Conv2d` rather than trusted

### Training

- [X] T022 [US1] Implement `resolve_device` in `python/bc/train.py`, raising when no usable GPU is found unless CPU is explicitly allowed, and stating in the message how to override. A multi-hour CPU epoch nobody chose is the failure FR-009 exists to prevent
- [X] T023 [US1] Implement the training loop and the `RunRecord` in `python/bc/train.py`: seed Python, numpy and torch from one seed; compute the mean-predictor baseline on the same validation set; store `split_digest`; write the record next to the checkpoint **always**, including on an early stop or a run that fails to beat the baseline
- [X] T024 [US1] Add the `python -m python.bc.train --policy <none|downsample_zero> --run-id <id>` command line entry to `python/bc/train.py`
- [X] T025 [US1] Write `python/tests/test_bc_train.py`: `resolve_device` raises with no GPU and no override, and returns a CPU device with one; a deliberately untrained model still produces a complete `RunRecord` with `beat_baseline` false, so the negative path is exercised without waiting for a real run; `n_val_samples` is the unbalanced count under both policies
  - 19 tests, none of which run a real epoch. A suite that needs an hour is a suite nobody runs before committing
  - **Found a real defect while writing them.** `json.dumps` writes a bare `NaN` for an absent measurement. Python reads it back happily and every strict JSON parser rejects it, so a run record would have looked fine until something other than Python opened it. Non-finite floats are now written as `null` and read back as nan, and the test parses with `parse_constant` set to fail
  - `beat_baseline` is recomputed on read, and a test hand-edits the field in the file to confirm a losing run cannot claim it won
  - The baseline test asserts the **training** mean is used rather than the validation mean, with numbers chosen so the wrong one would give an unbeatable baseline of 0.0
  - `evaluate` is asserted to average per sample rather than per batch, which an uneven final batch would otherwise skew

---

**Measured before writing the loop, per research R7:**

| Setting | Result |
|---|---|
| GPU step throughput, batch 64 | 7,595 img/s, 8.4 ms per step |
| Peak VRAM | 336 MB of 6 GB |
| Loader, 0 workers | 685 img/s |
| Loader, 8 workers, warm cache | 5,776 img/s |
| **Real epoch, 77,871 distinct images** | **about 1,000 img/s, roughly 80 s** |

R7's prediction holds: the bottleneck is decoding JPEGs, not arithmetic, and 336 MB of 6 GB
means batch size is bounded by throughput rather than memory.

**The warm-cache benchmark was wrong by a factor of five.** It re-read the same few thousand
files, so the operating system served them from memory. An epoch touches 77,871 distinct
images. Recorded in `config.py` next to the constant it justifies, because the benchmark is the
kind that looks rigorous and is not.

Caching was left as an option in R7 and is **not** taken: holding 67,000 decoded frames would
cost roughly 10 GB of RAM to remove a bottleneck worth 80 seconds an epoch.
- [X] T026 [US1] Run the unbalanced training and record the result: `--policy none --run-id bc_unbalanced_v01`. Log it in `results/EXPERIMENTS.md` **in the same session as the run** (Principle VI)
- [X] T027 [US1] Run the balanced training and record the result: `--policy downsample_zero --run-id bc_balanced_v01`. Log it in `results/EXPERIMENTS.md` in the same session

**Checkpoint**: two trained runs exist, each with a validation error beside a baseline that says
whether it beat guessing. A run that did not is recorded as a negative result, not discarded.

---

## Phase 4: User Story 2 - The artifacts M5 needs to compare three drivers (Priority: P2)

**Goal**: the model's steering output in a form that can sit beside the RL agent's and the
human's without the comparison measuring the wrong thing.

**Independent Test**: run the evaluation and confirm every reported distribution carries the six
Principle IX figures and a histogram summing to one, in all three scopes.

- [X] T028 [US2] Implement `predict` in `python/bc/evaluate.py`, producing the `PredictionSet` in original recording order and refusing when the checkpoint's `split_digest` does not match the split in use. Residuals are derived on read, never stored as a third array that could drift
- [X] T029 [US2] Implement `summarise` in `python/bc/evaluate.py`, **delegating** to `eda.stats.describe` and `eda.stats.relative_frequency_histogram`. This module computes no statistic of its own: if BC computed its own mean, BC's numbers and M1's could drift apart in definition while both looked correct, and the M5 comparison would be between two slightly different questions (research R5)
- [X] T030 [P] [US2] Implement `quantise_to_lattice` in `python/bc/evaluate.py`, applying `round(x / step) * step` clipped to [-1, 1], and mark every report built from its output as `lattice_applied`
- [X] T031 [US2] Add per-track scoping to every report in `python/bc/evaluate.py`, using the `track1data` and `track2data` path markers `eda.config.SESSION_PATH_MARKERS` already defines. There is no pooled-only path: feature 002 showed pooling hides a constant column on this dataset, and the same trap is live for steering
- [X] T032 [US2] Report the per-frame absolute change in predicted steering in `python/bc/evaluate.py`, reusing the project's existing smoothness quantity so BC, the RL agent and the human are compared on the same basis rather than at three different frame rates (FR-015)
- [X] T033 [US2] Implement `compare_runs` in `python/bc/evaluate.py`, producing the `BalancingComparison` and **refusing to render** if the two runs differ in anything beyond the balancing policy and the training sample count. Report the accuracy delta and the distribution delta side by side, never collapsed into a verdict
- [X] T034 [US2] Write `python/tests/test_bc_evaluate.py`: relative frequencies sum to 1 within tolerance; a report missing the `track2` scope fails; `predict` with a mismatched `split_digest` raises; `compare_runs` on two records differing in learning rate raises and names the field; `quantise_to_lattice` maps onto exactly the 41 levels feature 002 measured, by set equality; `summarise` on the human column reproduces the figure M1 already recorded, which is the cross-check that the shared functions really are shared
- [X] T035 [P] [US2] Implement the figures in `python/bc/evaluate.py` writing `results/plots/bc_*.png`: predictions against human values, the residual distribution, and the two policies' prediction distributions overlaid against the human one
  - Three figures: `bc_scatter_<run>.png`, `bc_residuals_<run>.png`, `bc_policy_distributions.png`. All per track as well as pooled, since feature 002 already showed pooling hides this dataset's structure
  - The overlay is on a **log** vertical axis. On a linear axis the human's 57.2 percent zero bar makes every other bar invisible, which would hide the whole comparison
  - The picture showed a gap no figure in the plan asked about: **neither model predicts beyond about plus or minus 0.7**, while the human uses the full range and holds 7.4 percent of validation mass on exactly plus or minus 1.00. Range compression is a second distributional failure alongside the missing zero spike
- [X] T035a [US2] Render the model's steering over the frames the human drove, as an animated GIF, so the behaviour can be watched rather than only read off a histogram. `python/bc/playback.py`, `python -m python.bc.playback --run <a> [<b>] --track <t>`
  - Not in the original task list. Added because "can we see the actual driving" is the first question anyone asks of a driving model, and a distribution table does not answer it
  - **Open loop, and the module says so in its first paragraph.** The model reacts to frames the human drove; it never chooses the next one. Nothing here shows whether the policy could keep a car on the road. Closed-loop driving is possible in the Udacity simulator these frames came from and is not possible in this project's Unity scene, which DESIGN section 7 already records
  - Frames are drawn from the **longest contiguous** stretch in a held-out block. Stitching across a block boundary would cut mid-corner and read as the model losing the road, which is a fact about the split
  - The **busiest** window is chosen rather than a representative one, and that is stated in the docstring and in the output: mean absolute difference is 0.375 over this stretch against 0.226 over the whole validation set. The animation shows the model's hardest moments, not its average ones
  - Quantised to a 64-colour palette at 1.5x scale. Full colour at 2x produced 28 MB for 200 frames; the same point survives 9.3 MB
- [X] T036 [US2] Add the `python -m python.bc.evaluate --run <id>` and `--compare <a> <b>` command line entries
- [X] T037 [US2] Run the evaluation for both runs and write `results/bc/comparison.md`. Record the two deltas and resist writing a winner: a run that wins on accuracy and loses on distribution is the expected outcome and is the finding this feature exists to produce

**Checkpoint**: M5 has its BC inputs, described by the same functions that describe the human
reference.

---

## Phase 5: User Story 3 - Someone else can reproduce the number (Priority: P3)

**Goal**: the reported figures survive being re-run.

**Independent Test**: re-run each stage and compare against what was recorded.

- [X] T038 [P] [US3] Run `python -m python.bc.split` twice with the same seed and confirm the two `results/bc/split.json` files are byte-identical (SC-002)
  - Two separate `python -m` invocations, so this is the cross-process form rather than two calls inside one interpreter. `cmp` reports byte-identical, and both are byte-identical to the `split.json` the two checkpoints were trained against. Digest still `f9151b481e7fcd51`, so the check did not invalidate anything downstream
  - **SC-002 passes for a stronger reason than it asks for.** Re-running with `--seed 99` changes exactly one field, `seed` itself: the train, validation and guard row sets are identical. The split contains no randomness at all, because `held_out_blocks` picks the held-out blocks by even spacing rather than by drawing them. The seed is recorded metadata, not an input to any decision
  - That is deliberate and `plan_split` says so, but it is worth stating plainly here: this determinism does not depend on numpy's RNG behaving the same way across versions, which is the usual way a seeded split stops reproducing. Nothing about the split can drift with a library upgrade
  - The consequence is that the seed field in `split.json` cannot be used to tell two splits apart. Anything that needs to distinguish them must compare the digest, which `bc.train` already does
- [X] T039 [US3] Re-run evaluation from a saved checkpoint and confirm it reproduces the recorded metrics **exactly**. Evaluation involves no randomness, so anything less than exact is a bug rather than a tolerance
  - Both runs re-evaluated from their saved checkpoints, plus the comparison. Every output is **byte-identical** to what was recorded: `distributions.json` for each run, and `comparison.md`. Not "matches to six decimals", which is what the printed summary would have shown; the files themselves are unchanged
  - The **figures reproduce byte-for-byte too**, which was not asked for and is not free: matplotlib can stamp generation metadata into a PNG and make an otherwise deterministic plot differ on every save. Measured across two consecutive renders of the scatter, the residuals and the policy overlay, all three md5 sums are unchanged, so the plots can be regenerated in a review without producing a spurious diff
  - Neither `run_record.json` was touched by evaluation, confirmed by comparison against a copy taken beforehand. Evaluation reads the training record and never writes back to it, so re-running cannot quietly revise the number it is supposed to be checking
  - **What this does not show.** Reproduction was on the same machine, the same RTX 3050 and the same torch build the checkpoints were trained on. Exact float agreement across a different GPU, or between GPU and CPU, is not demonstrated by this and should not be claimed from it. That is the same class of question T040 measures for training, and it is worth stating that the two are separate: T040 measures run-to-run spread on one device, not device-to-device
  - The outputs were backed up before the re-run and confirmed restored afterwards, so the recorded artifacts in the working tree are the originals rather than freshly generated look-alikes
- [X] T040 [US3] Train one seed twice and measure the observed spread between the two runs. Derive the reproduction tolerance from that measurement and record it. The tolerance is **measured, not chosen in advance**: cuDNN picks kernels non-deterministically, and a criterion invented before the measurement would be either unmeetable or meaningless (research R8)
  - `bc_repro_a_v01` and `bc_repro_b_v01`, both `--policy none --seed 42`. New run ids rather than a re-run of `bc_unbalanced_v01`, so the reference run and its checkpoint were never overwritten. That makes the sample **three** runs, not two, since the reference is the same configuration
  - val MSE 0.08666985 (reference), 0.08668462, 0.08641127. Mean 0.0865886, stdev 0.00015373, **range 0.00027334**, 0.32 percent of the mean
  - **Tolerance recorded as 0.0005 absolute**, a little under twice the range, in research R13 and the summary table. Set above the measurement rather than at it: three runs bound the spread, they do not estimate it, and a tolerance set exactly at the observed range is met by the runs that produced it and fails on the fourth
  - **The non-determinism was localised, not just measured.** `baseline_error` is 0.153622828786396 in all three to the last digit, and the sample counts, parameter count and split digest match exactly. The split, the sample build, the per-sample camera offsets and the balancing are bit-for-bit reproducible; only training moves. Worth confirming rather than assuming, because a seeding bug in the data pipeline would present as GPU noise in the final number while being a far worse problem
  - Divergence is present at **epoch 1** (train error 0.1322998 / 0.1324786 / 0.1321905), so it is kernel selection rather than a seed applied too late
  - **The reported number is a minimum, and its spread is not the process spread.** All three runs independently chose epoch 8 as best, where the spread is 0.000273; at epoch 4 it is 0.005325 and at epoch 12 it is 0.004381, about twenty times larger. Early stopping reports the minimum of 13 noisy epochs, which is tighter than the noise generating it. The tolerance therefore applies to the reported best-epoch figure and to nothing else, and R13 says so explicitly
  - **The finding this was for**: the balancing accuracy delta of 0.004229 is **15 times** the observed run-to-run range and 8 times the tolerance, and the distribution delta of 0.063091 is far larger again. R12 survives the noise. Had the delta been inside 0.0005, the comparison this whole feature exists to produce would have been unreportable
  - Both runs logged in `results/EXPERIMENTS.md` in the same session, with a note that they are three runs of one configuration rather than four BC models
- [X] T041 [US3] Confirm every `RunRecord` lets a reader determine the seed, hyperparameters, device and data volume without reading the code (SC-008). Read one record as if you had never seen the project and note anything you had to guess
  - **SC-008 passes on its four named items.** `seed` 42, a `hyperparameters` block carrying eleven settings including the augmentation ranges and the crop, `device` naming the exact GPU, and `n_train_samples` / `n_val_samples`. All four are readable from the file with no access to the source
  - The audit was still worth doing, because reading it cold surfaced two things a reader would get **wrong** rather than merely have to look up. Both are confirmed against the file rather than asserted:
  - **`val_error` and `train_error` come from different epochs, and nothing says so.** The record reports `val_error` 0.086670, which is epoch **8**, the best; and `train_error` 0.084994, which is epoch **13**, the last. The final epoch's validation error was 0.090400. A reader who assumes the two headline numbers describe one model state, which is the natural reading, concludes the model generalises better than it fits, and that conclusion is an artifact of the two fields being sampled at different points. The saved checkpoint is epoch 8's, so `val_error` is the honest one to quote; `train_error` does not belong to it
  - **The validation fraction cannot be computed from the record, and the obvious arithmetic gives the wrong answer.** `n_val_samples / (n_train_samples + n_val_samples)` is 6.68 percent. The real held-out fraction is 17.68 percent. The gap is the three-camera augmentation: training counts 3 samples per row, validation counts 1. Nothing in the record states that, and `camera_offset_range` only hints at it. A reader reporting "6.7 percent validation" from this file would be quoting a number that describes nothing
  - Smaller items a reader would have to go elsewhere for: no timestamp, so records cannot be ordered without the `results/EXPERIMENTS.md` entry; no dataset name or row count, only `split_digest`, which identifies the split without naming what it split; no torch or CUDA version, so `device` describes the hardware but not the stack; and no architecture identity beyond `parameter_count`, so 252,219 parameters does not tell a reader this is PilotNet at 66 x 200
  - **Deliberately not fixed here.** The T040 runs were already in flight against this schema when the audit ran, and changing `RunRecord` mid-measurement would have produced records that could not be compared with the two the feature actually reports. The two confirmed misreadings are recorded in `DESIGN.md` at T043 instead, where the measured results are written down, so the numbers arrive with the caveat attached. A schema change belongs to a later feature

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T042 Run `pytest python/tests -q` under `.venv-bc` and confirm the M1, feature 002 and new BC tests are all green. The older tests were written against numpy 1.26.4 and will run here under a different build; **if any fails only under `.venv-bc`, that is a finding about environment sensitivity and belongs in `research.md`**, not something to paper over
  - **141 passed under `.venv-bc`** in 24.5 s, nothing failed. The environment sensitivity this task was watching for did not appear: no M1 or feature 002 test behaves differently against the newer numpy that came with torch
  - **The sensitivity ran the other way, and it was worse than a failure.** Under `.venv`, `test_bc_evaluate.py` imported torch at module level with no guard, which is a **collection** error rather than a test failure, and a collection error interrupts the entire session. The M1 environment was running **zero** tests, not 87. A red suite says something is wrong; this said nothing at all
  - The claim recorded at T019 and T021, that the suite still runs under `.venv`, was true when written and had silently stopped being true. Neither environment reported it: `.venv-bc` was green, and nobody re-ran `.venv` after `bc.evaluate` landed
  - Fixed by giving `test_bc_evaluate.py` the same `pytest.importorskip("torch")` guard that `test_bc_model.py` and `test_bc_train.py` already carried. This is consistency with the existing pattern, not a new decision
  - After the fix: **`.venv` runs 87 passed, 3 skipped**, the 87 matching the figure T019 recorded, with the three torch-dependent modules skipping cleanly. `.venv-bc` still 141. The split is deliberate and worth keeping: `bc.split` and `bc.dataset` import no torch, so every sample-level and split-level decision can still be checked in the M1 environment
  - Unrelated to the tests, found while reading the output: `pytest.ini` already sets `addopts = -q`, so passing `-q` on the command line makes it `-qq` and **suppresses the pass count entirely**, leaving only dots and an exit code. The command in this task's own description does that. Run `pytest python/tests` with no extra `-q` to see the count
- [X] T043 Record the **measured** M4 results in `DESIGN.md` section 6 in a `docs:` commit: validation error against baseline for both runs, the achieved split fraction, the balancing cost on both axes, and the reproduction tolerance from T040. The decided values went in at T009; only what had to be measured lands here (Principle V)
  - One block appended at the end of DESIGN 6.2, in Bosnian to match the document, opening by saying that everything above it is a decision written before the code and that this is the part that had to be measured. That separation is the whole point of the Principle V gate and it is worth being visible in the file rather than only in the task list
  - Carries all four required items: both runs against their baselines with the best epoch named, the achieved 17.68 percent split with the 8.09 s measured gap, both balancing deltas kept apart, and the 0.0005 tolerance with the three-run spread it came from
  - Also carries the two things the measurement contradicted: the predicted accuracy-for-distribution trade did not appear, and neither model predicts beyond about plus or minus 0.7 while the human holds 7.4 percent of validation mass at exactly the rails
  - The two T041 misreadings are recorded here as well, with a note that the schema was deliberately not changed in this feature. That is the compromise T041 chose: the caveat travels with the numbers even though the file format still invites the mistake
  - **Fixed a stale line while in the file.** DESIGN 6.2 still had a bullet reading `BALANCE_KEEP_FRACTION = 0.30` with sample counts 97.329 to 84.031, which were per-image estimates from before the split existed. The 0.30 to 0.27 correction at T018 was written as a new block above it and the older bullet was never updated, so a reader arriving at that line read a withdrawn constant stated as current. Now 0.27 with the real 77.871 to 66.783, and the edit says what it replaced rather than silently overwriting it
  - This is the second instance of the same failure mode in one feature: T042 found a claim that was true when written and had quietly stopped being true. Both were found by re-reading rather than by any check, which is worth noting as a limit of the current setup
- [X] T044 [P] Update `README.md` so its setup and usage section covers `.venv-bc` as a literal, correct reproduction recipe. Principle VI requires the README to change in the same feature as the commands it documents
  - Setup gained a step 4 creating `.venv-bc` from `requirements-bc.txt` with the CUDA check, and the existing step 2 now says why there are three environments rather than leaving a reader to wonder. Usage is grouped by environment, since the previous version listed commands from three venvs as one block with no indication that activating the wrong one makes them fail
  - **Three commands in the old README could not have worked as written**, which is worth listing because the file's purpose is to be copied literally:
    - `python -m python.bc.train` with no arguments. `--policy` and `--run-id` are both required, so this exits with a usage error
    - `python python/evaluation/compare.py`. **`python/evaluation/` does not exist.** It is M5 work that was never written, listed in the repository structure table as though it were there. Both the table row and the command are gone, replaced by an explicit line saying M5 is not implemented and naming the command that used to be advertised
    - `pytest python/tests -q`. `pytest.ini` already sets `addopts = -q`, so the extra flag makes it `-qq` and suppresses the pass count. The README now says not to add it and gives the expected counts per environment instead
  - The BC recipe is the real four-step sequence, split then two runs then evaluate then the optional playback, with the expected figures beside it: 25.957 / 5.576 rows at an 8.09 s gap, 0.086670 and 0.090899 against a baseline near 0.1536, reproducing to 0.0005. A recipe with no expected output cannot tell a reader whether their run went wrong
  - Every command was smoke tested. The three BC entry points parse, `eda.report` imports under `.venv`, and `bc.playback --help` confirms `--run` really does take several ids, which is how the README writes it. `split.json` was compared before and after to confirm the check wrote nothing
  - **`ENVIRONMENT.md` said "Two separate venvs, deliberately" and there are three.** README delegates version detail to that file, so fixing only the README would have pointed readers at a document denying the third environment exists. It now has a `.venv-bc` section with the verified torch 2.6.0+cu124 and device string, the reason it is separate from `.venv-mlagents`, and the 141 against 87-plus-3-skipped test split
  - Also ticked M1 in the status list, which had been unchecked while its results sat committed in `results/eda/`. Third instance in this feature of a claim going stale unnoticed, after T042 and T043
- [X] T045 Walk `specs/004-bc-baseline/quickstart.md` end to end on a clean checkout and confirm every command and every expected figure
  - **Confirmed correct as written**: the dataset preconditions print exactly 32,443 and 97,329 at a ratio of 3; the torch line prints `2.6.0+cu124 True NVIDIA GeForce RTX 3050 6GB Laptop GPU`; all five split figures match, including the 8.09 s gap and the 0.1768 fraction the file is careful to call reported rather than forced; every distribution really does appear in three scopes, 5 quantities x pooled/track1data/track2data = 15 entries
  - **The numpy claim in section 5 is true and had never been checked.** Both environments report numpy 1.26.4 and pandas 2.1.4, so the pin does what it says. Worth recording because **T042's own description assumed the opposite**, saying the older tests "will run here under a different build". They do not, and that is the actual reason no environment sensitivity turned up
  - **A wrong flag, twice.** Sections 0 and 1 both said `-AllowCpu`. The real flag is `--allow-cpu`; the PowerShell-style spelling would fail. This is the exact failure the file exists to prevent, and it survived because nobody had needed the CPU path
  - **Section 5 carried the `-qq` bug**, the same one found in the README at T044: `pytest ... -q -p no:warnings` against a `pytest.ini` that already sets `addopts = -q`. The file that certifies reproduction was itself printing no pass count. Now corrected, with the expected 141 and the `.venv` figure of 87 passed and 3 skipped
  - **Two predictions the runs contradicted, both rewritten rather than deleted.** Section 3 said `beat_baseline` false was most likely on the unbalanced run; both runs beat the baseline and the unbalanced one beat it most comfortably. Section 4 said a run winning one axis and losing the other was the expected result; both deltas went the same way. In each case the original reasoning is kept and marked as not what happened, because the reasoning was sound and the outcome is the finding
  - **Section 6 overclaimed and now does not.** It asserted the split is byte-identical "on any machine" when one machine was tested. Replaced with what was verified, plus the stronger and genuinely machine-independent point that the split has no randomness to reproduce. The tolerance row was still written in the future tense from R8's plan and now carries the measured 0.0005 with its three-run derivation
  - Section 3 also gained the measured table and the 5 to 6 minute runtime, since a quickstart with no expected output cannot tell a reader their run went wrong. One duplicated paragraph introduced during editing was removed
- [X] T046 Resolve the branch-name deviation recorded in `plan.md`: either rename to `feature/bc-baseline` to match Principle II, or amend the constitution to accept the numbered form the spec-kit script produces. The repository currently carries both shapes, so one of the two documents is wrong and it should stop being ambiguous
  - **Resolved by amending the constitution, at the owner's decision.** Principle II now lists `NNN-<kebab-desc>` alongside `feature/` and `fix/`, for spec-kit features specifically, with every other rule unchanged. Constitution **1.5.0**, amendment log updated
  - The reason given in the principle is the shared number: the branch and `specs/NNN-<desc>/` carry the same one, so they cannot drift apart and a reader holding either can find the other. That is a property the `feature/` form does not have
  - **What settled it was measuring the precedent rather than assuming it.** The two shapes in this repository are not one branch renamed: `002-data-authenticity` is at bc09903 and `feature/data-authenticity` is at 9301645, different commits, **both merged into `develop`**. Renaming this branch would have made feature 004 comply while leaving the pattern the repository actually follows undescribed by the rule, and the next spec-kit feature would have re-opened the same deviation
  - Renaming was cheap and reversible, so it was not rejected on cost. It was rejected because it fixes one branch and not the rule
  - `plan.md` updated in both places it recorded the deviation: the Principle II row now reads PASS with the date and the resolution, and the Complexity Tracking row is struck through and carries the commit hashes above rather than being deleted. A resolved deviation is more useful as a record than as an absence
- [X] T047 Confirm the M4 gate: a BC model is trained on the combined dataset and its validation metrics are recorded, demonstrable from a clean clone
  - **Gate met.** The constitution's M4 row asks for PilotNet trained on the combined dataset with validation metrics recorded. Two models exist, both beat their baseline, and every figure quoted in the documents was checked back against the artifacts rather than trusted: all eight of `val_error` for both runs, both baselines, both training sample counts, the validation count and the parameter count match their `run_record.json` exactly. The split file independently reports 25,957 / 5,576 / 910 at 0.176831 with an 8.091 s gap, and both records carry the same digest
  - The metrics live in four tracked documents, so a reader who never runs anything still finds them: `DESIGN.md`, `results/EXPERIMENTS.md`, `README.md` and this feature's `quickstart.md`
  - **A clean clone needs the dataset separately**, since `dataset/` is git-ignored and submitted outside the repository. That is stated in quickstart section 0 with the 32,443 and 97,329 preconditions to check on arrival, so the dependency is documented rather than discovered
  - **The 8.9 MB playback GIF was not covered by Git LFS.** `.gitattributes` listed png, jpg, onnx, pt and the rest, but not `*.gif`, so `git check-attr` reported `filter: unspecified` and the animation would have entered history as an ordinary blob. Adding the rule after the fact does not help: the blob stays in history and only a rewrite removes it. Fixed now, while the file is still untracked, which is the one moment the fix is free. `git check-attr` now reports `filter: lfs`, and git-lfs 3.6.0 is installed
  - **`.gitignore` does not exclude the BC checkpoints, and that is correct here but worth knowing.** The rule is `results/*/checkpoint*.pt`, one level deep, matching the RL layout it was written for. BC writes to `results/bc/run_<id>/checkpoint.pt`, two levels deep, so the pattern misses it. The effect is desirable, because a tracked checkpoint is what makes the gate demonstrable without a retrain, and at 992 KB through LFS the cost is small. Recording it because it is an accident rather than a decision, and the next person to edit either rule should know the two do not line up
  - **Left for the owner, not decided here**: `bc_repro_a_v01` and `bc_repro_b_v01` also carry 992 KB checkpoints each. They are not candidate models, and the evidence T040 needs is in their `run_record.json` rather than their weights. Committing them costs about 2 MB of LFS for models nobody will load. Dropping just the two checkpoints while keeping the records would be reasonable; it is a repository-content call rather than a gate condition, so nothing was deleted

---

## Dependencies & Execution Order

```text
Phase 1 (Setup)
    |
    v
Phase 2 (Foundational)  T006 -> T007 -> T008 -> T009 (DESIGN gate) -> T010
    |
    |  nothing below starts until T009 is committed (Principle V)
    v
Phase 3 (US1, P1)  split -> dataset -> model -> train -> two runs
    |
    v
Phase 4 (US2, P2)  needs a trained checkpoint from Phase 3
    |
    v
Phase 5 (US3, P3)  needs both a split and a checkpoint
    |
    v
Phase 6 (Polish)
```

**Blocking edges worth stating explicitly:**

- T006 blocked T009 and is now done. It is the reason the split strategy changed, so the edge earned its place: the amendment T009 writes is a different amendment than the one originally planned.
- T006a does not block anything, but Principle VI requires it before the research numbers can be called reproducible.
- T007 blocks T009, because the balancing band is chosen against a measured histogram.
- T009 blocks all of Phase 3. This is the Principle V gate and it is the one edge in this plan that is a rule rather than a data dependency.
- T011 blocks T023, since training reads the split rather than producing its own.
- T026 and T027 block all of Phase 4. There is nothing to evaluate before there is something trained.
- T033 requires both runs, so it cannot be done after only the first.

## Parallel opportunities

- T004 and T005 are independent files and can be done together.
- T020 and T021 (the model and its test) are independent of the dataset work in T015 to T019, so the two tracks can proceed side by side once T010 lands.
- T030 and T035 touch different concerns within `evaluate.py` and can be written in either order.
- T038 can run as soon as the split exists, without waiting for any training.
- T044 is independent of everything else in Phase 6.

## Implementation Strategy

**MVP is Phase 1 through Phase 3.** That produces two trained runs with honest validation
numbers, which is the M4 gate. Phases 4 and 5 make the result usable by M5 and defensible under
questioning, but the milestone is reachable without them.

**The cheapest thing that can go wrong is discovered first.** T006 counts the sessions before
anything is built on session-level holdout, and T008 checks the image count before any statistic
is computed over it. Both are minutes of work guarding against a rebuild.

**The two runs are one experiment, not two features.** T026 and T027 differ in one flag and must
stay that way. Every hyperparameter they share is held in `bc.config` precisely so that they
cannot drift apart, and T033 refuses to render the comparison if they did.
