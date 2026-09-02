# Tasks: M5, evaluation and comparison

**Feature**: `010-m5-evaluation` | **Spec**: `spec.md` | **Plan**: `plan.md`
**Created**: 2026-09-01

## Format: `[ID] [P?] [Story] Description`

`[P]` marks tasks that touch no shared file and may be done in any order relative to each other.
`[US1]` and so on name the user story a task serves.

## Five orderings this feature must not violate

1. **The trace manifest before any comparison.** Research R3: the `source` column is a stale
   literal on all 60 traces and says `ppo_car_spread_a_sampling`. Any number computed before
   selection is deterministic is a number nobody can reproduce.
2. **`steering_series` before any `|delta steering|` figure.** Research R7: differencing a raw
   50 Hz trace reports a driver 3.8 times smoother than it is, because 67.1 per cent of the
   differences are structurally zero. The rate is not a detail, it is the measurement.
3. **The artefact numbers beside the marginal comparison, in the same table, not in prose after
   it.** Research R5. A reader who sees a chi-square of 20,154 without the 58.6 against 2.5 per
   cent near-zero shares, and the 23.5 against 87.6 per cent left-turn shares, has been told
   something false about driving style.
4. **The two `report.py` repairs before the tables are generated**, not after. A figure printed as
   `72.00 of 24 (300.0% of a lap)` and a "LOSS" branch that cannot report a win would have to be
   regenerated anyway.
5. **The README recipe verified last, and by running it**, not by reading it. SC-006 asks for
   deviations fixed, and a recipe that has only been read has not been tested.

---

## Phase 1: Setup and baselines

- [X] T001 [P] Record in this file the baselines every later number is read against, quoted rather
      than recomputed
  - **The human reference is the COMBINED dataset**, `dataset/dataset/dataset/driving_log.csv`,
    which is track1 plus track2. `python/bc/config.py` sets `DATASET_NAME = "combined"`, so every
    existing figure including M4's KL uses it. The per-track columns differ enough to change
    conclusions, so the reference is named wherever a number appears (research R5)

  | human steering | combined | track1 | track2 |
  |---|---|---|---|
  | n | **32,443** | 10,615 | 21,828 |
  | mean | **-0.0209** | -0.0367 | -0.0132 |
  | variance | **0.15149** | 0.02393 | 0.21333 |
  | exact zeros | **58.6 %** | 79.3 % | 48.4 % |
  | left / right | **23.5 / 18.0 %** | 17.4 / 3.2 % | 26.4 / 25.1 % |
  | sampling rate | **14.08 Hz**, recovered from image filename stamps, median interval 0.0710 s |

  - **RL 009, seed 42 deterministic**, ten held-out runs: steering mean **-0.1862**, variance
    **0.03208**, within 0.025 of zero on **2.5 per cent**, left on **87.6 per cent**;
    `|delta steering|` at `COMPARE_HZ` mean **0.0413**, p95 **0.2103**; **10 of 10** three-lap
    completions, **0.00** wall contacts per run; chi-square homogeneity against combined human
    **20,154.5**, dof 40, no pooling
  - **Scripted driver**, 34 training seeds, `results/heuristic/runs_2026-08-16_15-27-50.csv`:
    **34 of 34** laps, **24.00 of 24** markers, **0** wall contacts, mean lap time **23.655 s**,
    steering variance **0.04994** as pinned in `python/rl/report.py`
  - **BC**, `results/bc/comparison.md`: lattice KL from human **1.1439** unbalanced and **1.2070**
    balanced, on **5,576** validation rows, with `KL_SMOOTHING = 1e-9` applied to every bin
  - **The 50 Hz artefact**, so it is never rediscovered: differencing a raw trace gives
    **67.1 per cent** exactly-zero deltas and a mean of **0.0110** against **0.0417** decimated to
    the decision rate (research R7)
- [X] T002 [P] Confirm the three suites are green before anything changes, so a later regression is
      attributable. Record the counts, including the passed and skipped split that feature 009's
      T054 failed to capture
  - Run 2026-09-01 from the repository root. **Counts taken from `--junit-xml` rather than from the
    terminal summary**, because piping pytest through `tail` is what lost the split in 009's T054
    and it lost it again here on the first two attempts

  | suite | tests | passed | skipped | failures | errors | time |
  |---|---|---|---|---|---|---|
  | `.venv` | **379** | **376** | **3** | 0 | 0 | 256 s |
  | `.venv-bc` | **430** | **430** | **0** | 0 | 0 | 259 s |

  - Against feature 009's T004 baseline of **362 passed plus 3 skipped** and **416 passed**, both
    sides are **+14 passed** with the skip count unchanged. The three skips are the torch dependent
    modules skipping cleanly under `.venv`, which is the behaviour `ENVIRONMENT.md` describes
  - **A correction to 009's T054, recorded because it is the same file's own history.** That task
    wrote "`.venv` collects 376 tests", a figure derived from `--collect-only`. The true split at
    that commit was 376 passed and 3 skipped out of 379, so the number it quoted was the passed
    count by coincidence rather than the collection total. Nothing downstream depended on it
  - **EditMode**: run by the owner and reported as all passing, before this feature changed
    anything. No C# has been touched on this branch
- [X] T003 Write `DESIGN.md` 7 and 7.1 updates in a `docs:` commit **before** any comparison code.
      Principle V. Three things the design does not currently say: that the primary axis is
      `|delta steering|` and why the marginal steering comparison cannot carry the conclusion
      (research R5), that the comparison rate is 14.08 Hz and why differencing at 50 Hz is wrong
      (research R7), and that the BC column has three structurally absent cells rather than missing
      ones (research R6)
  - Written into `DESIGN.md` 7, after the two existing M5 notes and before `### 7.1`, in Bosnian to
    match the document. Four blocks: the straight-line prediction confirmed with numbers and the
    statement that chi-square 20,154.5 is topology and resolution rather than style; the combined
    dataset as the reference with the track1 and track2 columns that reverse the variance
    comparison; 14.08 Hz with the 67.1 per cent structurally zero deltas and the independent
    verification from image filename stamps; and BC's three absent cells as a property
  - **The task's first premise was wrong and the correction matters more than the task.** It says
    the design "does not currently say" the primary axis is `|delta steering|`. It already did.
    The second M5 note, written in feature 003, prescribes "težina ide na metrike izvršenja,
    glatkoća |Δsteering| ... a marginalni histogram ostaje kao kontekst, ne kao glavni rezultat".
    So this feature's axis decision **ratifies an existing design decision** and adds the
    measurement of how large the distortion is, rather than making a new call
  - **That note also carries an obligation the plan first missed**: it asks for the **conditional**
    distribution given nonzero steering wherever distributions are compared. Added as T023a
  - No line removed from `DESIGN.md`, no em dash

## Phase 2: make the traces addressable (US1)

- [X] T004 [US1] Fix `DriveLogger.sourceLabel` in `Evaluation.unity` so future traces carry their
      run id. **Do not rewrite the existing 60.** Their content is correct and rewriting recorded
      data to repair a label is a worse defect than mapping around it
  - **Fixed in code rather than in the scene, because setting the scene field re-arms the same
    trap.** A serialised label holds whatever the scene was last saved with, which is exactly how
    six sweeps came to be stamped `ppo_car_spread_a_sampling`. Added
    `DriveLogger.BeginRun(string label)`, which takes the label from the caller and falls back to
    the serialised value when passed null or empty, so scenes that never set one keep working
  - `DrivingAgent` now calls `trace.BeginRun(runId)` at the one site that opens an evaluation
    trace, so the file describes itself and cannot go stale
  - The existing 60 traces are untouched
  - **Compile verified rather than assumed**: `Assets/Refresh` rebuilt `SelfDrivingSim.dll` and
    `SelfDrivingSim.EditModeTests.dll`, console holds **zero errors and zero warnings**
- [X] T005 [US1] Write `results/rl/trace_manifest.json`: for each of the six feature 009 sweeps, the
      run id, the inference mode, the eval CSV filename, and the ten trace filenames **in seed
      order 1001 to 1010**
  - Written by `python/rl/trace_manifest.py`, committed, so the mapping is regenerated rather than
    hand-maintained. **Six sweeps, 60 traces, no file bound twice**
- [X] T006 [US1] Derive that mapping from filename timestamps, not from the `source` column, and
      record in the manifest that the `source` column is known wrong and why
  - **A timestamp window alone is not sufficient and the task's premise was too weak.** Any window
    wide enough to hold a sweep also catches a neighbouring file: two of the six sweeps returned 11
    and 12 candidates for 10 runs. The manifest instead matches each trace to an evaluation row by
    **content**, requiring the trace's final `t` to equal that row's `duration_s` within 0.06 s,
    consumed in run order. All 60 matched
  - That turns the manifest into a verification rather than an assumption: a missing, truncated or
    misordered trace fails loudly instead of binding the wrong file silently
  - The manifest carries a `source_column_is_wrong` field stating the cause, so a reader who opens
    a trace and sees `ppo_car_spread_a_sampling` finds the explanation without rediscovering it
- [X] T007 [P] [US1] A test asserting the manifest names ten existing files per sweep, that no file
      appears in two sweeps, and that the six eval CSVs it names exist
  - `python/tests/test_trace_manifest.py`, plus two the task did not ask for: that the seed list is
    1001 to 1010 in order, since seed order is what binds trace N to row N, and that every trace's
    duration still matches its row when both are read off disk. Building and verifying are not the
    same thing
- [X] T008 [P] [US1] A test pinning the corroboration that makes the mapping trustworthy: seed 42's
      last sampling trace is about 2 s after its predecessor, matching the seed 1009 wall contact
      at 7.16 s, where every other gap is about 16 s
  - Pinned. The test asserts exactly one wall contact in that sweep, that it is seed 1009 at under
    10 s, that the gap **following** it is under 5 s, and that every other gap exceeds 10 s
  - **Six tests, all passing.**

**Checkpoint**: every later number can name the exact files it came from.

## Phase 3: the missing test and the four columns (US2)

- [X] T009 [US2] Add a two-sample **KS test** to the statistics layer. It is the only test in
      `DESIGN.md` 7.1 that exists nowhere in the repository (research R2)
  - `ks_two_sample` in `python/eda/authenticity.py`, beside `chi2_homogeneity`, because
    `python/rl/report.py` already imports that module and one home for hypothesis tests is better
    than two
  - **Deliberately not a `HypothesisTestResult`.** That type carries `dof` and
    `n_categories_pooled`, which are properties of a binned chi-square and meaningless for a test
    that bins nothing. Reusing it would have forced two reported fields to hold placeholders
  - Returns `effect_size` beside the p-value, and `effect_is_material` against a threshold of
    **D = 0.10**. The KS statistic **is** the effect size, being the largest gap between the two
    empirical CDFs on a scale of 0 to 1, independent of sample size. That is exactly why it is
    reported alongside rather than instead
  - The tie caveat is written into the docstring: KS assumes continuous data, so it is the right
    instrument for `|delta steering|` and the wrong one for raw human steering on the 0.05 lattice,
    where the chi-square is better
- [X] T010 [P] [US2] Tests for it: a known-identical pair does not reject, a known-shifted pair
      does, and the p-value is returned rather than only the decision
  - `python/tests/test_ks_two_sample.py`, **seven tests**, the three asked for plus four that
    matter more: that a shift of 0.03 on 60,000 samples per side rejects **without** being
    material, which is the whole reason T026 exists; that `effect_size` equals `statistic` so the
    two printed numbers can never disagree; that the statistic is stable across a twentyfold change
    in sample size while the p-value is not; and that non-finite values are dropped
- [X] T011 [US2] Repair `report.py`'s marker denominator
  - `markers_possible` is now one lap's markers times `laps_to_complete`, and the lap count is
    **inferred from the finished runs** rather than passed in, because it is a scene setting that
    does not appear in the run record. A completed run awarded exactly `total * laps`
  - **Every completed run must agree, and a disagreement raises** instead of picking one: two lap
    counts in a sweep means the rows are not from one configuration
  - With nothing completed there is nothing to infer from and it falls back to one lap, so **M3's
    published columns are unchanged**. Verified: feature 007 still reads `6.20 of 24 (25.8% of a
    lap)`, and feature 009 now reads `72.00 of 72 (100.0% of 3 laps)` rather than `of 24 (300.0%)`
  - The unit label follows the lap count, so the line no longer says "of a lap" about three laps
- [X] T012 [US2] Repair `report.py`'s comparison prose
  - It reported only a loss because it was written when the learned column always lost. It now
    reports **MORE settled**, **LESS settled** or equal, and feature 009 reads MORE at 0.03208
    against the scripted driver's 0.04994
  - Feature 006's caveat now travels with **both** directions rather than only the losing one:
    steering variance is read with the lap count and never alone, because a driver that never moves
    also has low variance
- [X] T013 [US2] Reuse rather than reimplement, and move a helper if it must be shared
  - **The move was forced, not chosen, and the task's framing understated it.** `python.bc.evaluate`
    imports the model and the trainer, so it needs torch and **cannot be imported under `.venv` at
    all**, which is where M5's comparison runs. The lattice arithmetic it held never needed torch
  - `lattice_levels`, `quantise_to_lattice`, `lattice_distribution` and `kl_divergence` moved to a
    new torch-free `python/eda/lattice.py`. `python.bc.evaluate` keeps all four names and delegates,
    so M4's callers and tests are untouched. `python.bc.config` is pure constants and imports
    cleanly without torch, so `STEERING_LATTICE_STEP` and `KL_SMOOTHING` keep their existing home
  - `chi2_homogeneity` and the new `ks_two_sample` are used from `python/eda/authenticity.py` where
    they already live. Nothing was reimplemented
- [X] T014 [P] [US2] A test that the moved helpers still return what their original callers got
  - `python/tests/test_lattice_move.py`, **nine tests**. The equivalence test compares all four old
    names against the new module and is skipped where torch is absent, so it runs under `.venv-bc`
    and skips under `.venv`: 8 passed 1 skipped, then 9 passed
  - Also pinned: the lattice matches feature 002's published measurement of 41 points at 0.05,
    quantise clips and never returns negative zero, KL of a distribution from itself is zero, and
    **KL stays finite on a level the reference never used** while the unsmoothed form does not.
    That last one is not hypothetical, because track1 never produces 0.95
- [X] T015 [US2] Build the **RL column** from the manifest: seed 42 deterministic as the named
      column. **One RL column, not three.** Three would imply three drivers
  - `python/m5/columns.py`, `rl_column`. n = **8,788** over 10 held-out runs, steering mean
    **-0.1859**, variance **0.03208**, straight **1.1 %**, left **87.6 %**
  - Cross-checked against `python/rl/report.py`, which reads the raw traces by a different path and
    reports the same n and the same variance. Two independent readings agreeing is the check that
    the resampled committed input is faithful
  - **The sampling column is reported beside it and is a second inference mode of the same policy,
    not a second driver.** It earns a row because the two modes disagree about which driver is most
    human-like, which is a result rather than a duplicate
- [X] T016 [P] [US2] Record seeds 7 and 13 as an agreement line with their numbers, not as columns
  - `agreement()` in `python/m5/compare.py`, printed under its own heading that states why it is not
    a column: three seeds of one configuration are one driver, and four columns of it would claim
    the project compared four learned drivers against a human

  | seed run | variance | mean abs delta | runs | run time, three laps |
  |---|---|---|---|---|
  | seed 42, the named column | 0.03208 | 0.0413 | **10 of 10** | 62.425 s |
  | seed 7 | 0.02736 | 0.0334 | **10 of 10** | 62.683 s |
  | seed 13 | 0.03270 | 0.0429 | **10 of 10** | 62.551 s |

  - All three complete every held-out run, and lap times agree within **0.26 s** across a 62 s lap.
    The named column is not a lucky draw
- [X] T017 [P] [US2] Build the **heuristic column** from `results/heuristic/`
  - n = **12,691** over 34 runs, variance **0.04892**, **34 of 34** laps, **0.00** wall contacts,
    mean lap time **23.655 s**
  - The variance reads **0.04892** here against the **0.04994** pinned in `python/rl/report.py`.
    Not a discrepancy and not rounding: `report.py` reads the raw 50 Hz traces, this column reads
    them resampled to 14.08 Hz, and decimating a signal changes which samples are averaged. Both are
    correct at their own rate, which is why ordering 2 exists
- [X] T018 [P] [US2] Build the **BC column** from `results/bc/run_bc_balanced_v01/`, with its three
      absent cells marked absent and caused
  - n = **5,576** validation rows, variance **0.07182**, reproducing feature 004's published
    `distributions.json` to five decimals through a completely different path
  - **Four absent cells, not three.** The task counted lap completion, lap time and wall contacts
    and missed **speed**: the model predicts steering alone. Every one prints its cause in the cell,
    because a blank reads as missing data rather than as a property of the driver
  - Reaching it at all needed `python/bc/export_predictions.py`, run under `.venv-bc`, because the
    comparison runs under `.venv` where torch does not exist
- [X] T019 [P] [US2] Build the **human column** from the **combined** dataset,
      `dataset/dataset/dataset/driving_log.csv`, which is track1 plus track2 and is what
      `DATASET_NAME = "combined"` already selects. **Not a single track**: research R5 records that
      picking track1 alone reverses the variance comparison and moves the straight-line share from
      58.6 to 79.3 per cent
  - n = **32,443**, variance **0.15149**, straight **58.6 %**, left **23.5 %**, matching T001's
    quoted baseline exactly
  - The `run` column is derived from the centre-image path, so the track1 to track2 junction is a
    seam and no difference is ever taken across it. Feature 002 found that seam; this is the third
    feature to honour it
- [X] T020 [US2] Descriptive statistics for every column on steering, speed and `|delta steering|`:
      n, mean, variance, min, max, relative-frequency histogram, as `DESIGN.md` 7.1 lists them
  - Three tables in `results/comparison/m5_comparison.md`, one per variable, plus a coarse-binned
    relative-frequency histogram of steering and the full 0.05-resolution version written to
    `results/comparison/steering_histogram.csv`, which is what the Phase 5 figures read
  - **Speed is reported per driver and never compared across drivers, and the report says so in the
    table's own header.** The Unity columns are the simulator's rigidbody speed; the human column is
    a different simulator's recorded speed in its own units. Their variances are **1.23** and
    **10.69**, a gap that would read as a finding and is a unit mismatch. This is the same class of
    error as R5 and it is disclosed the same way
  - Shares rather than counts everywhere, because the columns differ by a factor of six in n
**Checkpoint**: four columns exist and every cell is a number or a caused absence.

## Phase 4: the comparison (US2)

- [X] T021 [US2] **The primary axis.** `|delta steering|` for each driver against human: KS with its
      p-value, computed only through `steering_series` at `COMPARE_HZ`
  - `compare_axis` in `python/m5/compare.py`. Every driver reads a committed input that is already
    at 14.08 Hz, so there is no path in this module that can difference a raw trace

  | driver | mean | median | p95 | D raw | **D on lattice** |
  |---|---|---|---|---|---|
  | RL 009 deterministic | 0.0413 | 0.0127 | 0.2103 | 0.4603 | **0.2682** |
  | RL 009 sampling | 0.1552 | 0.1527 | 0.2999 | 0.5306 | 0.4564 |
  | heuristic | 0.0174 | 0.0075 | 0.0621 | 0.5008 | 0.3780 |
  | BC | 0.0248 | 0.0187 | 0.0693 | 0.5525 | 0.3810 |
  | human combined | 0.1112 | **0.0000** | 0.5500 | reference | reference |

  - **The median is reported beside the mean because the human's mean alone is misleading.** Its
    median change is no change at all, and its mean of 0.1112 is produced by the jumps between
    those holds. A mean-only comparison would describe a driver that does not exist
- [X] T022 [US2] State the rate in the table itself. A smoothness figure without its sampling rate
      is not a measurement (research R7)
  - The heading is `Primary axis: |delta steering| at 14.08 Hz`, and every input CSV carries
    `hz=14.08` in its header comment, so a figure separated from the report still names its rate
- [X] T023 [US2] **The secondary axis.** Steering level on the lattice against human: KL with the
      smoothing constant stated, and chi-square homogeneity

  | driver | KL from human | chi2 | dof |
  |---|---|---|---|
  | RL 009 deterministic | 1.6575 | 20154.5 | 40 |
  | RL 009 sampling | 1.0556 | 12740.6 | 40 |
  | heuristic | 1.3513 | 20639.0 | 40 |
  | BC | 1.2466 | 11554.4 | 40 |

  - **BC reads 1.2466 here against M4's published 1.2070, and both are correct.** M4 compared the
    model against the 5,576 validation rows it was scored on; M5 compares it against the full 32,443
    row combined dataset, because that is the one reference every other column is read against.
    Changing the reference per column to make a number match would be the actual error
  - `KL_SMOOTHING = 1e-9` is applied to every bin and named in the report, because a smoothed KL is
    not the same quantity as an unsmoothed one and the two are not comparable across documents
- [X] T023a [US2] **The conditional comparison `DESIGN.md` 7 already asks for**, and which the first
      draft of the plan missed: the steering distribution **given nonzero steering**, per driver
      against human

  | driver | n turning | KL from human | chi2 |
  |---|---|---|---|
  | RL 009 deterministic | 8691 | 1.1291 | 8221.9 |
  | RL 009 sampling | 7877 | **0.9465** | 4256.5 |
  | heuristic | 12361 | 1.0527 | 8313.9 |
  | BC | 5458 | 0.9787 | 3996.2 |

  - **Conditioning compresses every gap and halves the spread of the field.** The deterministic
    policy's divergence falls from 1.6575 to 1.1291, the largest move of the four. Most of what the
    marginal measured was the straight-line share, and the straight-line share is the track
  - All four still reject at these sample sizes, which is why the divergence is what is read and the
    p-value is a formality
- [X] T024 [US2] **In the same table as T023**, the near-zero share and the left-turn share for
      every driver. Ordering 3
  - In the same table, as columns. A reader cannot see chi-square 20,154.5 without also seeing
    **1.1 against 58.6 per cent** near zero and **87.6 against 23.5 per cent** left
- [X] T025 [P] [US2] Report the **unquantised** steering comparison once, beside the quantised one,
      to show the size of the resolution artefact quantisation removes. SC-002
  - Both are in the primary table as `D raw` and `D on lattice`. The artefact is **large**:
    quantisation moves the deterministic policy from D = 0.4603 to **0.2682**, cutting the apparent
    distance nearly in half, and it moves every driver by at least 0.07
  - **It also changes the answer.** On raw D the deterministic policy leads the heuristic by 0.04;
    on lattice D it leads by **0.11**. The conclusion is read off the quantised axis, with the raw
    figure printed beside it so the size of the correction is visible rather than assumed
- [X] T026 [P] [US2] Report effect size beside every p-value. At 31,202 against 10,615 samples a KS
      test rejects almost any null, so a p-value alone is close to a formality
  - Every KS row prints `D` and `p`. All four p-values round to zero at two significant figures,
    which is exactly the point: **the p-values carry no information here and the D values carry all
    of it.** `ks_two_sample` returns `effect_size` equal to `statistic` so the two can never
    disagree, pinned by a test in `python/tests/test_ks_two_sample.py`
- [X] T027 [US2] Assemble the `DESIGN.md` 7 four-column table with every cell measured or caused.
      SC-001

  | driver | runs completed | laps per run | run time | seconds per lap | contacts | speed |
  |---|---|---|---|---|---|---|
  | RL 009 deterministic | **10 of 10** | 3 | 62.425 s | **20.808 s** | 0.00 | present |
  | RL 009 sampling | 9 of 10 | 3 | 63.334 s | 21.111 s | 0.10 | present |
  | heuristic | **34 of 34** | 1 | 23.655 s | 23.655 s | 0.00 | present |
  | BC | absent | absent | absent | absent | absent | absent |
  | human | absent | absent | absent | absent | absent | present |

  - **Eleven absent cells, each printed with its cause underneath rather than left blank.** BC never
    drives this track and the human recording is of a different simulator. Filling either with a
    proxy would have invented the comparison the milestone is supposed to make
  - **The lap columns were wrong on the first pass and the error was mine, in the writeup as well
    as in the table.** `lap_time_s` in the run record is the whole run, and the RL sweeps run three
    laps per attempt while the scripted sweep runs one. Printing 62.425 against 23.655 in one
    column, and then writing "the scripted driver is 2.6 times faster per lap" under it, compared a
    three-lap run against a single lap. Per lap the learned policy is **faster**, 20.808 s against
    23.655 s, so the claim was not merely imprecise, it was reversed
  - Fixed by carrying `laps_per_run` on the column, which the builder had accepted and discarded
    since it was written, and reporting `seconds_per_lap` as the comparable figure. Pinned by a
    test that asserts the raw figures reverse the per-lap ordering, so the mistake cannot return
  - **The per-lap margin is reported with its own bound.** The two sweeps ran at different
    `timeScale` values over different seed sets, and lap time was a success criterion for neither.
    It is a column in the table, not a finding about driving quality
## Phase 5: figures and the recipe (US3, US4)

- [X] T028 [US3] Overlaid `|delta steering|` distributions, all four drivers, one figure
  - `results/plots/m5_delta_steering.png`, two panels. Left the distributions, right the
    **cumulative** curves after every driver is snapped to the human lattice
  - **The right panel is cumulative rather than a second histogram, and that was a correction.**
    The report leads with the KS statistic, and `D` is a property of the cumulative curves: the
    largest vertical gap from the human's. Drawing the histogram twice would have shown a picture
    and then asked the reader to trust a number computed off something else. `D` is now printed in
    the legend beside each driver and is readable off the drawing
  - The bins are centred on the 0.05 lattice. The first attempt used `linspace(0, 0.6, 49)`, whose
    width does not divide 0.05, so the human's mass aliased into a comb that was a property of the
    binning. That would have been a second artefact laid on top of the one the figure is about
- [X] T029 [P] [US3] Overlaid lattice histograms of steering, all four drivers
  - `results/plots/m5_steering_lattice.png`. The human's 58.6 per cent spike at zero dominates the
    panel, which is the honest drawing of the comparison
  - **The near-zero and left-turn shares are a second panel in the same figure**, not a caption.
    Ordering 3 applied to the drawing rather than only to the table
- [X] T030 [P] [US3] A per-driver summary figure for the defence
  - `results/plots/m5_summary.png`. Four panels: completion, mean `|delta steering|` with the human
    as a dashed reference, KS `D` on the lattice, conditional KL
  - **Execution first, resemblance second**, which is `DESIGN.md` 7's ordering. BC's completion bar
    is labelled "never drives" rather than drawn as zero, because zero is a measurement and this is
    an absence
  - The two resemblance panels visibly disagree, which is the result rather than a defect
- [X] T031 [US3] Every figure produced by a committed script, so a changed input changes the figure.
      SC-005. No figure saved by hand
  - `python/m5/plots.py`, one command. Verified by regenerating all three in a clean clone: the
    files came back **byte for byte identical** to the committed ones
- [X] T032 [P] [US4] The model taxonomy paragraph from `DESIGN.md` 7.1, in the lecture's
      terminology: stochastic, continuous state, discrete time, agent-based, time invariant,
      non-anticipatory
  - In `results/comparison/m5_comparison.md` as a table, each term beside the thing in this project
    that makes it true. A taxonomy recited without its evidence is not a classification
  - **Two of the six needed qualifying, and one number in it was wrong before it was checked.**
    *Stochastic*: the evaluated column is `deterministic` inference, so it is stochastic through its
    environment only, and the two inference modes differ by 0.11 in mean `|delta steering|` because
    of exactly that. *Time invariant*: the 6,000-step episode cap makes **termination** a function
    of elapsed steps, though nothing else is. The cap is a harness, not a dynamic
  - The first draft wrote "21 observations, nine rays". `CarAgent.ObservationCount` is
    `rayCount + SelfStateCount` and the scene runs **13 rays plus six**, so it is **19**. Corrected
    against the code rather than against memory
- [X] T033 [US4] Run the README recipe from a **clean clone**, start to finish
  - Done as a real clone into a scratch directory, a fresh `py -3.10 -m venv .venv`, and
    `pip install -r python/requirements.txt`, then the recipe. Not read, run
- [X] T034 [US4] Fix what breaks rather than documenting it as a caveat. SC-006. Anything that only
      works because of state on this machine is found here
  - **Four defects, all of them invisible from this machine.** Every one is fixed rather than
    written down as a caveat

  | what broke | cause | fix |
  |---|---|---|
  | the human column could not be built at all | `dataset/` is gitignored and downloaded from Kaggle | `export_human` writes `steering_human_combined.csv`, 1.2 MB against the dataset's 6.2, and the column reads that |
  | three cells of the `DESIGN.md` 7 table read `absent` | `results/heuristic/runs_*.csv` is gitignored | `export_heuristic_runs` writes the four columns the table needs |
  | those three cells stayed `absent` even after the export existed | `build()` passed the gitignored path explicitly, overriding the committed default | the explicit path removed |
  | **45 tests failed**, where the README promises a green suite | tests that read the dataset failed rather than skipped | `needs_dataset` on exactly those 45, and `needs_traces` on 2 more |

  - **The trace guard was wrong on its first attempt and the clean clone caught it.** It asked
    whether `results/drive_logs/` exists. That directory is tracked and holds a few committed July
    traces, so it exists in every clone while feature 009's 60 gitignored files do not. The guard
    now asks whether the traces the manifest names are on disk. A guard that asks the wrong question
    passes locally and fails in the one place it was written for
- [X] T035 [P] [US4] Record what the clean-clone run actually needed that the recipe did not say
  - **The recipe did not exist.** The README said "M5 (poređenje RL / BC / čovjek) još nije
    implementiran" and pointed at `python/evaluation/compare.py`, a module that was never written.
    Replaced with the three-command recipe, its expected values, and the explicit statement of which
    step needs the dataset and the traces and which two do not
  - The status list claimed M2, M3 and M4 were incomplete. M3 closed **MET** on 2026-09-01 and M4's
    two runs have been reported since 2026-08-05. Corrected
  - `python -m python.bc.export_predictions` takes `--run-id`, not `--run`. Written wrong first,
    caught by reading the parser rather than by running it under `.venv-bc`
  - The suite counts in the README were stale: **409 passed and 4 skipped** under `.venv`, **464**
    under `.venv-bc`, and **321 passed with 92 skipped and zero failures** in a clean clone. All
    three are now in the file, the clean-clone number with its reason
**Checkpoint**: the deliverable exists and reproduces.

## Phase 6: closeout

- [X] T036 Write the comparison's own result: which driver is closest to the human on the primary
      axis, by how much, and whether that ordering survives the secondary axis
  - Written into `results/comparison/m5_comparison.md` as a **generated** section, not typed prose.
    `orderings()` sorts the drivers off the same objects the tables are built from, so the sentence
    naming the winner cannot survive a rerun that changes who wins
  - **On the primary axis the closest driver is `ppo_car_009_bc` deterministic**, D = 0.2682 against
    the next driver's 0.3780, a margin of 0.1098
  - **The ordering does not survive.** On steering level given nonzero steering the closest is
    `ppo_car_009_bc` **sampling** at KL 0.9465, and the deterministic policy is **last** at 1.1291
  - Those are the same policy under two inference modes, which is what makes the disagreement a
    finding rather than a tie. Sampling draws from the action distribution instead of taking its
    mean: the steering levels spread toward the human's spread while the mean step change rises
    from 0.0413 to 0.1552, past the human's own 0.1112. **Noise makes a policy's distribution more
    human and its motion less so**
  - Conditioning narrows the spread between best and worst from 0.60 to 0.18, which measures how
    much of the marginal comparison was track topology
- [X] T037 State plainly what the comparison cannot say, given research R5 and R6: nothing about
      BC's driving, and nothing about steering level that is not partly track geometry
  - Four limits in the report, each a property of the inputs. The task named two; the other two are
    **speed**, which is Unity rigidbody units against another simulator's recorded units with
    variances of 1.23 and 10.69, and **the p-values**, which reject on every row at these sample
    sizes and therefore carry nothing
- [X] T038 [P] Update `results/EXPERIMENTS.md` with M5's rows
  - A full `## M5: the comparison` section: the execution table, both axes, the result, the limits,
    and the clean-clone verification with its four defects
  - **It opens by stating that no training run and no sweep was performed for this milestone.**
    Every number is read off runs already recorded above. A reader scanning the file for what was
    run would otherwise assume a sweep produced these
- [X] T039 [P] Confirm the three suites are green and record the counts against T002's

  | suite | tests | passed | skipped | failures | against T002 |
  |---|---|---|---|---|---|
  | `.venv` | **414** | **410** | 4 | 0 | +34 passed, +1 skipped |
  | `.venv-bc` | **465** | **465** | 0 | 0 | +35 passed |
  | `.venv`, clean clone | 414 | **322** | 92 | 0 | new measurement |

  - Counts from `--junit-xml`, never from the terminal summary. That is the third feature in a row
    where reading the summary through a pipe lost the split
  - **The clean-clone row is new and is the one that matters for SC-006.** 92 skips against 4 is the
    dataset and the traces being absent, and every skip states which
  - **EditMode**: no C# changed since the owner reported the suite passing at T004. `DrivingAgent`
    and `DriveLogger` were the only two files touched and both were verified compiling with zero
    errors and zero warnings at that point
- [X] T040 [P] Check every file this feature touched for em dashes and the constitution's style
      rules
  - **43 files on the branch, zero em dashes**, checked by iterating the branch diff rather than by
    checking the files I remembered touching
  - Commit messages are subject-only, one `-m`, no body, no agent attribution, as the constitution
    requires
- [X] T041 Merge `010-m5-evaluation` into `develop` with `--no-ff`
  - `29533ef`, 19 commits. No fast forward, so the feature stays legible as a unit
- [X] T042 Merge and tag `v0.5-m5`, at the commit where the gate becomes demonstrable, matching the
      convention feature 009's T057 established
  - **The tag sits on the merge commit into `develop`**, `29533ef`, which is where `v0.3-m3` and
    `v0.4-m4` both sit. Checked rather than assumed: `git log -1 v0.3-m3` is `merge(009)` and
    `v0.4-m4` is the 004 merge, so a tag on a feature-branch commit would have broken the pattern
  - `master` merged from `develop` at `83732ce`, `--no-ff`. Five tags, `master` and `develop` level
- [X] T043 State the milestone verdict against the spec's seven success criteria, met or not met,
      each with the number that decides it

  **M5 is MET, seven of seven.** Written into `DESIGN.md` 7.2 in Bosnian to match that document,
  and into `results/EXPERIMENTS.md` in the log's own terms.

  | criterion | the number that decides it | verdict |
  |---|---|---|
  | SC-001, every cell measured or caused | 11 absent cells, each with its cause printed under the table | **MET** |
  | SC-002, quantised before divergence, unquantised beside it | `D` raw and on lattice in one table; the artefact moves the leader from 0.4603 to **0.2682** | **MET** |
  | SC-003, KL and two-sample KS with p, three drivers against human | four columns, both statistics, p on every row | **MET** |
  | SC-004, straight-line asymmetry addressed | conditional on nonzero steering, plus the shares in the same table as the statistic | **MET** |
  | SC-005, every figure from a committed script | `python/m5/plots.py`; all three regenerate **byte for byte** in a clean clone | **MET** |
  | SC-006, recipe run from a clean clone, deviations fixed | clone made, four defects found, four fixed, none written as a caveat | **MET** |
  | SC-007, taxonomy in the lecture's terminology | six terms, each with its evidence; two qualified, one figure corrected against the code | **MET** |

  - **The milestone's own result is that the two axes name different winners.** Deterministic
    inference is closest on smoothness (D 0.2682), sampling is closest on steering distribution
    (KL 0.9465), and they are the same policy. That is reported as the finding rather than resolved
    into a single ranking, because resolving it would mean suppressing one of two measurements
  - **Three of the seven were satisfied only after something was found wrong.** SC-006 by running
    the recipe rather than reading it, SC-007 by checking the observation count against
    `CarAgent.ObservationCount` rather than against memory, and SC-001 by noticing that
    `lap_time_s` is three laps for one sweep and one lap for another
**Checkpoint**: M5 is closed and the submission has its final story.

---

## Dependency notes

- T005 blocks everything in Phases 3 and 4. Ordering 1.
- T009 blocks T021. The primary axis needs the test that does not exist yet.
- T011 and T012 block T027. Ordering 4: the table would be regenerated otherwise.
- T013 blocks T015 through T019. The columns are built from shared helpers, so the sharing is
  settled before four callers depend on it.
- T021 and T023 block T036. The result is read off both axes, never off one.
- T033 blocks T034. The deviations cannot be fixed before they are found by running.
- T043 depends on every measurement task, and is the last thing written.
