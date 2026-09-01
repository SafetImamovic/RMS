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
- [ ] T015 [US2] Build the **RL column** from the manifest: seed 42 deterministic as the named
      column. **One RL column, not three.** Three would imply three drivers
- [ ] T016 [P] [US2] Record seeds 7 and 13 as an agreement line with their numbers, not as columns
- [ ] T017 [P] [US2] Build the **heuristic column** from `results/heuristic/`
- [ ] T018 [P] [US2] Build the **BC column** from `results/bc/run_bc_balanced_v01/`, with its three
      absent cells marked absent and caused
- [ ] T019 [P] [US2] Build the **human column** from the **combined** dataset,
      `dataset/dataset/dataset/driving_log.csv`, which is track1 plus track2 and is what
      `DATASET_NAME = "combined"` already selects. **Not a single track**: research R5 records that
      picking track1 alone reverses the variance comparison and moves the straight-line share from
      58.6 to 79.3 per cent
- [ ] T020 [US2] Descriptive statistics for every column on steering, speed and `|delta steering|`:
      n, mean, variance, min, max, relative-frequency histogram, as `DESIGN.md` 7.1 lists them

**Checkpoint**: four columns exist and every cell is a number or a caused absence.

## Phase 4: the comparison (US2)

- [ ] T021 [US2] **The primary axis.** `|delta steering|` for each driver against human: KS with its
      p-value, computed only through `steering_series` at `COMPARE_HZ`
- [ ] T022 [US2] State the rate in the table itself. A smoothness figure without its sampling rate
      is not a measurement (research R7)
- [ ] T023 [US2] **The secondary axis.** Steering level on the lattice against human: KL with the
      smoothing constant stated, and chi-square homogeneity
- [ ] T023a [US2] **The conditional comparison `DESIGN.md` 7 already asks for**, and which the first
      draft of the plan missed: the steering distribution **given nonzero steering**, per driver
      against human. The design's second M5 note names it directly, so it is an obligation rather
      than an extra. It is the one comparison of steering level that the straight-line asymmetry
      does not dominate
- [ ] T024 [US2] **In the same table as T023**, the near-zero share and the left-turn share for
      every driver. Ordering 3. Without them the divergence reads as a statement about style
- [ ] T025 [P] [US2] Report the **unquantised** steering comparison once, beside the quantised one,
      to show the size of the resolution artefact quantisation removes. SC-002
- [ ] T026 [P] [US2] Report effect size beside every p-value. At 31,202 against 10,615 samples a KS
      test rejects almost any null, so a p-value alone is close to a formality
- [ ] T027 [US2] Assemble the `DESIGN.md` 7 four-column table with every cell measured or caused.
      SC-001

## Phase 5: figures and the recipe (US3, US4)

- [ ] T028 [US3] Overlaid `|delta steering|` distributions, all four drivers, one figure
- [ ] T029 [P] [US3] Overlaid lattice histograms of steering, all four drivers
- [ ] T030 [P] [US3] A per-driver summary figure for the defence
- [ ] T031 [US3] Every figure produced by a committed script, so a changed input changes the figure.
      SC-005. No figure saved by hand
- [ ] T032 [P] [US4] The model taxonomy paragraph from `DESIGN.md` 7.1, in the lecture's
      terminology: stochastic, continuous state, discrete time, agent-based, time invariant,
      non-anticipatory
- [ ] T033 [US4] Run the README recipe from a **clean clone**, start to finish
- [ ] T034 [US4] Fix what breaks rather than documenting it as a caveat. SC-006. Anything that only
      works because of state on this machine is found here
- [ ] T035 [P] [US4] Record what the clean-clone run actually needed that the recipe did not say

**Checkpoint**: the deliverable exists and reproduces.

## Phase 6: closeout

- [ ] T036 Write the comparison's own result: which driver is closest to the human on the primary
      axis, by how much, and whether that ordering survives the secondary axis
- [ ] T037 State plainly what the comparison cannot say, given research R5 and R6: nothing about
      BC's driving, and nothing about steering level that is not partly track geometry
- [ ] T038 [P] Update `results/EXPERIMENTS.md` with M5's rows
- [ ] T039 [P] Confirm the three suites are green and record the counts against T002's
- [ ] T040 [P] Check every file this feature touched for em dashes and the constitution's style
      rules
- [ ] T041 Merge `010-m5-evaluation` into `develop` with `--no-ff`
- [ ] T042 Merge and tag `v0.5-m5`, at the commit where the gate becomes demonstrable, matching the
      convention feature 009's T057 established
- [ ] T043 State the milestone verdict against the spec's seven success criteria, met or not met,
      each with the number that decides it

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
