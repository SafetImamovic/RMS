# Feature Specification: Behavioral Cloning Baseline (M4)

**Feature Branch**: `004-bc-baseline`
**Created**: 2026-08-04
**Status**: Draft
**Input**: User description: "Behavioral cloning baseline (M4): train a PilotNet CNN on the combined Udacity-format dataset to predict steering from a single camera image, and produce the artifacts M5 will compare against the RL agent and the human reference."

## Overview

The project defends a comparison: an RL agent that learned the **task** against a
behavioural-cloning model that learned a **style**. M1 characterised the human data and M2
built the environment the RL agent will train in. This feature builds the other side of the
comparison.

The deliverable is not "a model that drives". It is **a believable number and a believable
distribution**: a validation error that measures generalisation rather than memorisation, and
a prediction distribution that can be held against the human one without the comparison being
an artefact of how it was produced.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A trained model whose validation number means something (Priority: P1)

The student trains a steering-prediction model on the recorded human driving and reads a
validation error. That number has to survive the question "how do you know it did not simply
memorise?", because it is the only evidence the model learned anything at all.

**Why this priority**: this is the MVP. Without a trained model there is nothing to compare,
and without a trustworthy validation split the model's error is unfalsifiable. A naive random
split over a driving recording is the single most common way this exact project reports a
beautiful number that means nothing: consecutive frames are near-identical, so a random split
puts the same moment on both sides and the model is scored on frames it effectively trained on.

**Independent Test**: train once, then check that the validation set contains no frame within
a stated time window of any training frame, and that the reported error is computed on that
set. Delivers a defensible headline number on its own.

**Acceptance Scenarios**:

1. **Given** the combined recording, **When** the split is produced from a fixed seed, **Then** no validation frame shares a recording moment with any training frame, and the boundary rule is stated rather than assumed
2. **Given** the same seed, **When** the split is produced twice, **Then** the two splits are identical
3. **Given** a trained model, **When** validation error is reported, **Then** it is reported alongside the error of a trivial baseline that always predicts the dataset mean, so the reader can see whether the model beat guessing
4. **Given** a machine with no usable GPU, **When** training starts, **Then** the run says so plainly and stops or continues by explicit choice, rather than silently spending hours on CPU

---

### User Story 2 - The artifacts M5 needs to compare three drivers (Priority: P2)

The student needs the model's steering output in a form that can sit beside the RL agent's and
the human's without the comparison measuring the wrong thing.

**Why this priority**: M5 is the graded deliverable and this feature is one of its three inputs.
It is P2 rather than P1 because a model must exist before its output can be described, but the
project fails its main claim without it.

**Independent Test**: run the evaluation over the validation set and confirm the produced
artifacts carry every descriptive statistic Principle IX requires, on a grid shared with the
human reference. Testable without touching training.

**Acceptance Scenarios**:

1. **Given** a trained model, **When** predictions are produced, **Then** they are emitted in original recording order, so that consecutive differences are meaningful
2. **Given** the prediction sequence, **When** it is summarised, **Then** sample size, mean, variance, standard deviation, minimum, maximum and a relative-frequency histogram are reported for the predictions and separately for the residuals
3. **Given** the human column is lattice-valued at a step of 0.05 and the model's output is continuous, **When** the two are compared, **Then** the comparison states which grid it used and why, rather than comparing a smooth curve against 41 spikes
4. **Given** the recordings are two different tracks with different driving profiles, **When** results are reported, **Then** they are reported per track as well as pooled

---

### User Story 3 - Someone else can reproduce the number (Priority: P3)

A reader with the repository and the dataset re-runs the training and obtains the reported
figures, or is told precisely why they cannot.

**Why this priority**: Constitution Principle VI, and the defence is an individual interview
where "it worked on my machine" is not an answer. P3 because the first two stories deliver
value even if reproduction is imperfect.

**Independent Test**: re-run from a clean checkout with the same seed and compare the reported
metrics against the recorded ones.

**Acceptance Scenarios**:

1. **Given** a fixed seed, **When** training is re-run on the same hardware, **Then** the reported metrics match those recorded, within a stated tolerance that acknowledges non-deterministic GPU kernels
2. **Given** a trained checkpoint, **When** evaluation is re-run, **Then** it reproduces the recorded metrics exactly, since evaluation involves no training randomness
3. **Given** the recorded run, **When** a reader inspects it, **Then** the seed, the split boundaries, the hyperparameters and the hardware are all recorded beside the numbers

---

### Edge Cases

- A row in the log references an image file that is not on disk. The run must name the missing file and refuse, not skip silently: a silent skip changes the sample size that every reported statistic is computed over.
- The dataset directory is absent entirely, since it is git-ignored. The failure must name what is missing and how to obtain it, rather than surfacing as an empty-array error deep in training.
- `brake` is constant on one track and not the other. Nothing here should treat pooled column statistics as a property of the data; feature 002 already recorded that trap.
- The two recordings have very different steering profiles: one is 79.3 percent zeros, the other far more active. A pooled histogram hides that, so pooling must be a stated choice, not a default.
- Left and right camera images exist for every row. If the augmentation offset is applied to frames that then land in validation, the validation set contains synthesised targets that no human ever produced.
- Training diverges or plateaus at the mean predictor. The run must be able to report that outcome as a result, rather than presenting a mean-predictor as a trained model.

## Requirements *(mandatory)*

### Functional Requirements

**Data and reuse**

- **FR-001**: The feature MUST read the recordings through the existing loader used by the exploratory analysis, and MUST NOT introduce a second implementation of the headerless-CSV or path-rerooting logic.
- **FR-002**: The feature MUST resolve the recorded Windows-absolute image paths onto the local image directory by filename, and MUST verify that every referenced image exists before training begins.
- **FR-003**: The feature MUST report the sample size it actually trained and validated on, and this MUST reconcile with the number of rows read.

**Split integrity**

- **FR-004**: The train/validation split MUST be leak-free with respect to temporal adjacency: frames close together in a recording MUST NOT be divided across the two sides.
- **FR-005**: The split MUST be derived from a stated seed and MUST be identical across runs and across machines.
- **FR-006**: The split rule and the resulting boundaries MUST be recorded as data, not merely described in prose, so a reader can verify the property in FR-004 rather than trust it.
- **FR-007**: Augmented or synthesised samples MUST NOT appear in the validation set. Validation MUST be measured against recorded human targets only.

**Model and training**

- **FR-008**: The model MUST predict a steering value from a single camera image.
- **FR-009**: Training MUST use the GPU when one is available, and MUST state which device it used. If no usable device is found, the run MUST NOT proceed to a long CPU training silently.
- **FR-010**: The run MUST record its hyperparameters, seed, device, duration and final metrics together with the checkpoint, so a checkpoint is never separated from the conditions that produced it.
- **FR-011**: The reported validation error MUST be accompanied by the error of a mean-predictor baseline on the same validation set.
- **FR-012**: Where the camera-offset augmentation is used, the offset value MUST be recorded as a decision with its justification. If it is a chosen constant rather than a derived one, the feature MUST say so plainly rather than presenting it as derived.

**Comparison artifacts**

- **FR-013**: Predictions MUST be emitted in original recording order, so that per-frame differences can be computed for the smoothness comparison.
- **FR-014**: The feature MUST report, for both the prediction distribution and the residual distribution: sample size, mean, variance, standard deviation, minimum, maximum, and a relative-frequency histogram (Constitution Principle IX).
- **FR-015**: The feature MUST report the per-frame absolute change in predicted steering, on the same resampled basis the project already uses for human and simulated per-frame quantities, so that the three drivers are comparable on smoothness rather than on frame rate.
- **FR-016**: Results MUST be reported per track and pooled, never pooled only.
- **FR-017**: The feature MUST state where quantisation onto the human's 0.05 lattice happens, and MUST NOT report any comparison between a continuous prediction distribution and the lattice-valued human column without that treatment applied or its absence justified.
- **FR-018**: The feature MUST record, as a stated limitation, that the model is never driven in the simulation and that the comparison is therefore at the level of distributions and per-frame smoothness only.

**The balancing experiment**

- **FR-021**: The feature MUST produce two trained runs that differ in exactly one respect, the balancing policy: one trained on the recorded sample distribution, one trained with near-zero steering samples downsampled. Everything else - seed, split, architecture, preprocessing, augmentation, hyperparameters - MUST be held identical, or the difference between them measures more than balancing.
- **FR-022**: Both runs MUST be evaluated on the **same** validation set, and that set MUST be the unbalanced one. Balancing is a property of the training sample; applying it to the validation set would move the yardstick along with the model and make the two runs incomparable.
- **FR-023**: The feature MUST report the difference between the two runs on both axes that the tension concerns: predictive accuracy against the human targets, and distance between the prediction distribution and the human distribution. A run that wins on one and loses on the other is the expected outcome and MUST be reported as such rather than resolved into a single verdict.

**Documentation order**

- **FR-019**: The architecture, input preprocessing, augmentation policy, balancing policy and split strategy MUST be written into the design document before the corresponding code exists (Constitution Principle V). Values that can only be measured, such as achieved error, are recorded afterwards.
- **FR-020**: Where this feature contradicts what the design document already states, the contradiction MUST be recorded as an amendment with its reason, not silently overwritten.

### Key Entities

- **Recording row**: one moment of human driving. Three camera images sharing a timestamp, plus steering, throttle, brake and speed. The timestamp is the row's identity and is what makes temporal adjacency knowable.
- **Split**: an assignment of rows to training or validation, derived from a seed, carrying its boundaries so the leak-free property is checkable.
- **Training run**: a checkpoint together with the seed, hyperparameters, device, duration and metrics that produced it. Never a checkpoint alone.
- **Prediction sequence**: model outputs in recording order, paired with the recorded human value, from which residuals and per-frame changes are derived.
- **Distribution summary**: the six descriptive statistics plus a relative-frequency histogram, for any distribution this feature reports.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No validation frame lies within the stated temporal exclusion window of any training frame, verified by a check over the produced split rather than asserted.
- **SC-002**: The same seed produces byte-identical split boundaries on two separate runs.
- **SC-003**: The trained model's validation error is lower than the mean-predictor baseline on the same validation set. A model that fails this is reported as a negative result rather than presented as trained.
- **SC-004**: Every distribution this feature reports carries all six descriptive statistics and a relative-frequency histogram that sums to one.
- **SC-005**: Prediction and residual distributions are reported for each track separately and for the pool, with the per-track figures visibly different where the underlying driving differs.
- **SC-006**: Re-running evaluation from the saved checkpoint reproduces the recorded metrics exactly.
- **SC-007**: Re-running training from the same seed reproduces the recorded metrics within a stated tolerance, and that tolerance is justified rather than assumed.
- **SC-008**: A reader can determine, from the recorded run alone and without reading the code, what seed, hyperparameters, device and data volume produced the reported number.
- **SC-009**: The design document describes the architecture, preprocessing, augmentation, balancing and split before the implementing code is committed, demonstrable from commit order.
- **SC-010**: Every image referenced by a row used in training or validation exists on disk, and the count reconciles with the reported sample size.
- **SC-011**: Two runs exist, and a reader can verify from the recorded runs that they differ in the balancing policy and in nothing else.
- **SC-012**: Both runs are scored on the same validation set, and that set is confirmed to be unbalanced.
- **SC-013**: The cost of balancing is reported as a number on both axes - accuracy against the human targets, and distance from the human distribution - rather than as a claim that one run is better.

## Assumptions

- **Combined dataset.** Training uses the combined recording of both tracks, as the design document already specifies, because it is the larger sample and covers both driving profiles. Per-track reporting preserves the distinction that pooling would hide.
- **Steering only.** The model predicts steering. Throttle and brake are out of scope: the comparison the project defends is about steering style, and brake is degenerate on one of the two tracks.
- **Quantisation belongs to the comparison, not to the model.** This feature stores raw continuous predictions and records that the human column is lattice-valued; the shared-grid treatment is applied where the two are compared. Quantising at the model boundary would discard information a later comparison might want, and the design document already assigns the treatment to the comparison stage.
- **The camera offset is a chosen hyperparameter.** The design document states plus or minus 0.2. No derivation of it exists in the sources this project follows, so it is recorded as a choice, with its effect on the result reported rather than assumed negligible.
- **Reproducibility is bounded by the hardware.** GPU kernels are not bit-deterministic by default, so exact reproduction is claimed for evaluation and tolerance-bounded reproduction for training.
- **The model is never driven.** It trained on another simulator's camera images and the vehicle built in M2 has no camera sensor. This is a stated limitation of the project's design, not a gap this feature closes.

## Dependencies

- The existing exploratory-analysis loader and its established facts about the recording format (features 001 and 002).
- The lattice finding from feature 002: steering takes 41 discrete values at a step of 0.05.
- The dataset itself, which is git-ignored and must be present locally.
- The design document's section 6, which already fixes several of these decisions and which this feature must either honour or amend explicitly.

## Tensions with the existing design *(to be resolved during planning)*

Places where the design document as written today conflicts with the requirements above.
Recorded here so planning resolves them deliberately rather than discovering them in code.

1. **The design says "Split: 80/20 train/val" with no mention of temporal leakage.** A naive random split violates FR-004. The design needs amending, and that amendment is the substantive one in this feature.
2. **The design says to downsample samples with steering near zero, to balance the training set.** Resolved by the clarification below: both policies are trained and the gap between them is measured. The design document still states balancing as a single decision, so it needs amending to describe two runs and to say what the pair is for. Small amendment, but it must be made or the design and the deliverable disagree.
3. **Research C9 pushed M5 toward execution metrics**, because generated tracks contain no straight sections and marginal steering histograms would compare topology rather than driving. But the BC model executes nothing: it produces no trajectory. FR-013 and FR-015 are the proposed resolution - predictions in recording order *do* form a sequence, so per-frame smoothness is available to BC even though lap time and completion rate are not. Planning must confirm that is enough for M5's claim, or narrow the claim.

## Clarifications

### Question 1: Balancing versus distribution fidelity - RESOLVED 2026-08-04

**Context**: DESIGN section 6.2 specifies "Balansiranje: downsampling uzoraka sa steering ≈ 0 (dataset je dominantno prava vožnja)". Feature 002 measured how dominant: 79.3 percent zeros on track1.

**The question**: downsampling the near-zero steering samples produces a better predictor but shifts the prediction distribution away from the human one, and that distribution is the object of M5's central comparison.

**Decision: option A. Train both, report both.** Two runs differing in exactly one thing, the
balancing policy, evaluated on the same validation set with the same seed.

**Why**: the tension is real and neither side of it is obviously right, so choosing one and
defending the choice would be defending a guess. Running both converts the question into a
measurement: the gap between the two prediction distributions **is** the cost of balancing,
stated in numbers rather than asserted. It also protects against the failure mode in option C,
where an unbalanced model collapses toward predicting near-zero and cannot beat the mean
baseline - if that happens, the balanced run is still there and the collapse is itself a
recorded result rather than a dead end.

The cost is one extra training run, which is small next to a PPO run and is the cheapest
experiment in the project. Recorded as FR-021 through FR-023 and SC-011 through SC-013.

Options B and C are not deferred, they are subsumed: this produces both of their outputs.
The custom option, loss weighting instead of discarding, was not taken, because it changes what
the optimiser attends to *and* keeps the sample count, which makes the comparison against the
unbalanced run a two-variable one. Two runs differing in one variable is the point.
