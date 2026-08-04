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

- [ ] T001 Create `python/bc/__init__.py` as an empty package, matching the `python/eda/` and `python/track/` layout
- [ ] T002 Write `requirements-bc.txt` pinning torch 2.6.0+cu124 with its index URL, plus pandas, numpy, Pillow and matplotlib. Pin exact versions, not ranges: Principle VI requires a reader to reconstruct the environment, and a range reconstructs a different one next month
- [ ] T003 Create `.venv-bc` from Python 3.10.11 and install `requirements-bc.txt`. Confirm `torch.cuda.is_available()` is true and record the reported device name. `.gitignore` already covers `.venv-*/`, so nothing there needs changing
- [ ] T004 [P] Create `results/bc/` with a `.gitkeep`
- [ ] T005 [P] Create `results/EXPERIMENTS.md` with its header and column format. The constitution names it a companion document and Principle VI requires one entry per training run, but the file does not exist yet, so the first BC run would have nowhere to be logged

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
- [ ] T006a Write `python/bc/survey.py` so the T006 measurements are reproducible rather than one-off: session counts and time ranges, per-track timeline gaps, steering autocorrelation against lag, and the guard-cost table across candidate block and guard settings. Write to `results/bc/session_survey.md`. Principle VI: the numbers now sitting in research R2 must re-run to the same values
- [ ] T007 Extend `python/bc/survey.py` to report the steering histogram of the combined dataset, per track and pooled, using `eda.stats.relative_frequency_histogram`. Report what fraction of samples fall in candidate near-zero bands so `ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` can be chosen against a measurement rather than guessed
- [ ] T008 Verify the integrity precondition before anything depends on it: run `eda.loader.check_integrity` over the combined dataset and confirm 32443 rows against 97329 images. Record the result in `results/bc/session_survey.md`. The expected answer is already known from the plan, so a mismatch means the archive is incomplete and every downstream statistic would be computed over the wrong denominator
- [ ] T009 Write the **decided** M4 values into `DESIGN.md` section 6 in a `docs:` commit, before any Phase 3 code exists. Four amendments, all in one logical change:
  - **Split**: section 6.2 currently says "Split: 80/20 train/val" with no mention of leakage. Amend to **contiguous block holdout with an 8 s guard band**, 10 blocks per track and 2 held out. State that consecutive frames are near-duplicates, that a random frame split scores the model on frames it effectively trained on, and that session-level holdout was measured to be unavailable because the file contains two sessions and the largest gap is 0.5 s. Record the achieved 17.7 percent and state that it is reported rather than forced, and record that the guard is derived from steering autocorrelation rather than chosen
  - **Balancing**: section 6.2 states downsampling as a single decision. Amend to two runs, and say what the pair is for: balancing produces the better predictor while deliberately moving the prediction distribution away from the human one, and that distribution is what M5 compares. Record `ZERO_STEERING_BAND` and `BALANCE_KEEP_FRACTION` from T007
  - **Camera offset**: section 6.1 states plus or minus 0.2 as if it were derived. Amend to record it as a **chosen** hyperparameter, held identical across both runs so it never becomes a confound (research R4)
  - **Quantisation**: state that this feature stores raw continuous predictions and that the 0.05 lattice treatment happens at comparison time, which is where DESIGN section 7 already assigns it
- [ ] T010 Write `python/bc/config.py` with every named constant from `contracts/bc-module-api.md`, each carrying a comment naming the decision it came from. Import `SEED` from `eda.config` rather than redefining it. No numeric literal appears anywhere else in the package

**Checkpoint**: the measurements exist, the decisions are written down, and the constants live in
one place before any code reads them.

---

## Phase 3: User Story 1 - A trained model whose validation number means something (Priority: P1) MVP

**Goal**: a trained steering predictor with a validation error that measures generalisation, not
memorisation.

**Independent Test**: produce the split, confirm no validation session overlaps a training
session in time, train once, and read the validation error beside the mean-predictor baseline.

### Split

- [ ] T011 [US1] Implement `plan_split`, `write_split` and `read_split` in `python/bc/split.py`: cut each track into `N_BLOCKS` contiguous blocks, assign `N_HOLDOUT` evenly spaced blocks per track to validation, and discard every frame within `GUARD_SECONDS` of a boundary **from both sides**. Produce the `SplitPlan` fields from `data-model.md`, with `val_fraction_actual` and `min_train_val_gap_s` derived and reported rather than forced
- [ ] T012 [US1] Implement `verify_no_leak` in `python/bc/split.py`, raising when the minimum time distance between any training frame and any validation frame is under `GUARD_SECONDS`, naming both row indices and the distance found. This is the machine-checkable form of FR-004, and it is a stronger check than the session-overlap test the withdrawn plan called for
- [ ] T013 [US1] Add the `python -m python.bc.split --seed <n> --val-fraction <f>` command line entry, writing `results/bc/split.json`
- [ ] T014 [US1] Write `python/tests/test_bc_split.py`: the same seed produces byte-identical output across two calls and across processes; `verify_no_leak` accepts a plan built by `plan_split` on the real recording; a hand-built plan with a training frame 1 s from a validation frame is rejected with both row indices and the distance named; an empty validation side is rejected; train, validation and guard rows are pairwise disjoint and sum to the row count, so no frame is silently lost or double counted; `val_fraction_actual` is asserted to be **reported**, with the test allowing the roughly 0.177 achieved figure to differ from the 0.20 target rather than requiring a match

### Dataset

- [ ] T015 [US1] Implement `build_samples` and `verify_images_exist` in `python/bc/dataset.py`. Reading goes through `eda.loader`; this module never reimplements the headerless-CSV or path-rerooting logic (FR-001). A missing image raises and names the first offending file, never skips
- [ ] T016 [US1] Implement `preprocess` in `python/bc/dataset.py`: crop, resize to the configured input size, colour-space conversion and normalisation, deterministic throughout
- [ ] T017 [US1] Implement `augment` in `python/bc/dataset.py`: horizontal flip with **steering negation**, plus brightness. Takes an explicit rng and never touches global random state, matching the rule `python/track/generator.py` already follows
- [ ] T018 [US1] Implement `apply_balancing` and the `BalancingPolicy` type in `python/bc/dataset.py`, returning statistics describing exactly how many samples were removed and the resulting histogram, so the induced distribution shift is a number rather than an assumption
- [ ] T019 [US1] Write `python/tests/test_bc_dataset.py`: horizontal flip negates the steering target, checked on a **non-zero** value so a sign error cannot hide behind zero (named by Principle VIII); `preprocess` returns the documented shape; the same rng seed reproduces the same augmentation; a missing image raises with the filename in the message; side-camera targets equal the recorded value plus or minus the offset with clipping exercised at both extremes; **no validation sample ever carries `is_augmented` true**, asserted over the real split rather than a hand-built example

### Model

- [ ] T020 [P] [US1] Implement `build_model` and `parameter_count` in `python/bc/model.py`. Every shape comes from `bc.config`; no data-dependent constant appears here
- [ ] T021 [US1] Write `python/tests/test_bc_model.py`: a forward pass on a batch of the documented input shape returns one output per sample (named by Principle VIII); a batch with the wrong channel count raises rather than silently broadcasting

### Training

- [ ] T022 [US1] Implement `resolve_device` in `python/bc/train.py`, raising when no usable GPU is found unless CPU is explicitly allowed, and stating in the message how to override. A multi-hour CPU epoch nobody chose is the failure FR-009 exists to prevent
- [ ] T023 [US1] Implement the training loop and the `RunRecord` in `python/bc/train.py`: seed Python, numpy and torch from one seed; compute the mean-predictor baseline on the same validation set; store `split_digest`; write the record next to the checkpoint **always**, including on an early stop or a run that fails to beat the baseline
- [ ] T024 [US1] Add the `python -m python.bc.train --policy <none|downsample_zero> --run-id <id>` command line entry to `python/bc/train.py`
- [ ] T025 [US1] Write `python/tests/test_bc_train.py`: `resolve_device` raises with no GPU and no override, and returns a CPU device with one; a deliberately untrained model still produces a complete `RunRecord` with `beat_baseline` false, so the negative path is exercised without waiting for a real run; `n_val_samples` is the unbalanced count under both policies
- [ ] T026 [US1] Run the unbalanced training and record the result: `--policy none --run-id bc_unbalanced_v01`. Log it in `results/EXPERIMENTS.md` **in the same session as the run** (Principle VI)
- [ ] T027 [US1] Run the balanced training and record the result: `--policy downsample_zero --run-id bc_balanced_v01`. Log it in `results/EXPERIMENTS.md` in the same session

**Checkpoint**: two trained runs exist, each with a validation error beside a baseline that says
whether it beat guessing. A run that did not is recorded as a negative result, not discarded.

---

## Phase 4: User Story 2 - The artifacts M5 needs to compare three drivers (Priority: P2)

**Goal**: the model's steering output in a form that can sit beside the RL agent's and the
human's without the comparison measuring the wrong thing.

**Independent Test**: run the evaluation and confirm every reported distribution carries the six
Principle IX figures and a histogram summing to one, in all three scopes.

- [ ] T028 [US2] Implement `predict` in `python/bc/evaluate.py`, producing the `PredictionSet` in original recording order and refusing when the checkpoint's `split_digest` does not match the split in use. Residuals are derived on read, never stored as a third array that could drift
- [ ] T029 [US2] Implement `summarise` in `python/bc/evaluate.py`, **delegating** to `eda.stats.describe` and `eda.stats.relative_frequency_histogram`. This module computes no statistic of its own: if BC computed its own mean, BC's numbers and M1's could drift apart in definition while both looked correct, and the M5 comparison would be between two slightly different questions (research R5)
- [ ] T030 [P] [US2] Implement `quantise_to_lattice` in `python/bc/evaluate.py`, applying `round(x / step) * step` clipped to [-1, 1], and mark every report built from its output as `lattice_applied`
- [ ] T031 [US2] Add per-track scoping to every report in `python/bc/evaluate.py`, using the `track1data` and `track2data` path markers `eda.config.SESSION_PATH_MARKERS` already defines. There is no pooled-only path: feature 002 showed pooling hides a constant column on this dataset, and the same trap is live for steering
- [ ] T032 [US2] Report the per-frame absolute change in predicted steering in `python/bc/evaluate.py`, reusing the project's existing smoothness quantity so BC, the RL agent and the human are compared on the same basis rather than at three different frame rates (FR-015)
- [ ] T033 [US2] Implement `compare_runs` in `python/bc/evaluate.py`, producing the `BalancingComparison` and **refusing to render** if the two runs differ in anything beyond the balancing policy and the training sample count. Report the accuracy delta and the distribution delta side by side, never collapsed into a verdict
- [ ] T034 [US2] Write `python/tests/test_bc_evaluate.py`: relative frequencies sum to 1 within tolerance; a report missing the `track2` scope fails; `predict` with a mismatched `split_digest` raises; `compare_runs` on two records differing in learning rate raises and names the field; `quantise_to_lattice` maps onto exactly the 41 levels feature 002 measured, by set equality; `summarise` on the human column reproduces the figure M1 already recorded, which is the cross-check that the shared functions really are shared
- [ ] T035 [P] [US2] Implement the figures in `python/bc/evaluate.py` writing `results/plots/bc_*.png`: predictions against human values, the residual distribution, and the two policies' prediction distributions overlaid against the human one
- [ ] T036 [US2] Add the `python -m python.bc.evaluate --run <id>` and `--compare <a> <b>` command line entries
- [ ] T037 [US2] Run the evaluation for both runs and write `results/bc/comparison.md`. Record the two deltas and resist writing a winner: a run that wins on accuracy and loses on distribution is the expected outcome and is the finding this feature exists to produce

**Checkpoint**: M5 has its BC inputs, described by the same functions that describe the human
reference.

---

## Phase 5: User Story 3 - Someone else can reproduce the number (Priority: P3)

**Goal**: the reported figures survive being re-run.

**Independent Test**: re-run each stage and compare against what was recorded.

- [ ] T038 [P] [US3] Run `python -m python.bc.split` twice with the same seed and confirm the two `results/bc/split.json` files are byte-identical (SC-002)
- [ ] T039 [US3] Re-run evaluation from a saved checkpoint and confirm it reproduces the recorded metrics **exactly**. Evaluation involves no randomness, so anything less than exact is a bug rather than a tolerance
- [ ] T040 [US3] Train one seed twice and measure the observed spread between the two runs. Derive the reproduction tolerance from that measurement and record it. The tolerance is **measured, not chosen in advance**: cuDNN picks kernels non-deterministically, and a criterion invented before the measurement would be either unmeetable or meaningless (research R8)
- [ ] T041 [US3] Confirm every `RunRecord` lets a reader determine the seed, hyperparameters, device and data volume without reading the code (SC-008). Read one record as if you had never seen the project and note anything you had to guess

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T042 Run `pytest python/tests -q` under `.venv-bc` and confirm the M1, feature 002 and new BC tests are all green. The older tests were written against numpy 1.26.4 and will run here under a different build; **if any fails only under `.venv-bc`, that is a finding about environment sensitivity and belongs in `research.md`**, not something to paper over
- [ ] T043 Record the **measured** M4 results in `DESIGN.md` section 6 in a `docs:` commit: validation error against baseline for both runs, the achieved split fraction, the balancing cost on both axes, and the reproduction tolerance from T040. The decided values went in at T009; only what had to be measured lands here (Principle V)
- [ ] T044 [P] Update `README.md` so its setup and usage section covers `.venv-bc` as a literal, correct reproduction recipe. Principle VI requires the README to change in the same feature as the commands it documents
- [ ] T045 Walk `specs/004-bc-baseline/quickstart.md` end to end on a clean checkout and confirm every command and every expected figure
- [ ] T046 Resolve the branch-name deviation recorded in `plan.md`: either rename to `feature/bc-baseline` to match Principle II, or amend the constitution to accept the numbered form the spec-kit script produces. The repository currently carries both shapes, so one of the two documents is wrong and it should stop being ambiguous
- [ ] T047 Confirm the M4 gate: a BC model is trained on the combined dataset and its validation metrics are recorded, demonstrable from a clean clone

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
