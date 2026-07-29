---
description: "Task list for Data Authenticity & Integrity Checks"
---

# Tasks: Data Authenticity & Integrity Checks

**Input**: Design documents from `/specs/002-data-authenticity/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/authenticity-api.md

**Tests**: INCLUDED and NON-OPTIONAL - FR-025 requires deliberately tampered fixtures, and
Constitution VIII gates the merge on pytest. A detector demonstrated only on clean data has not
been demonstrated at all.

**Organization**: Grouped by user story (US1, US2, US3) so each is independently testable.

**Commit note (Constitution III)**: The AI never runs git. "Commit" below means *the owner
reviews and commits*; each checkpoint is a natural review-and-commit point.

**Branch (Constitution II)**: `feature/data-authenticity`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (from spec.md)

## Path Conventions

New modules at `python/eda/integrity.py` and `python/eda/authenticity.py`; tests at
`python/tests/`; notebook section appended to `python/notebooks/01_dataset_analysis.ipynb`;
outputs to `results/eda/` and `results/plots/` (per plan.md).

**Do not modify**: `python/eda/loader.py`, `fingerprint.py`, `stats.py`, `report.py`,
`results/eda/m1_report.md`, `results/eda/m1_stats.json`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Named constants so no threshold in this feature is an unexplained magic number

- [X] T001 Add authenticity constants to `python/eda/config.py`: `LATTICE_ATOL=1e-8` → **shipped as `1e-6`**, revised against the real log (research A3.1), `DISCRETE_MAX_DISTINCT=100`, `GAP_FACTOR=5.0`, `ACCEL_MAD_K=5.0`, `SESSION_PATH_MARKERS=("track1data","track2data")` - each with a one-line comment citing its research decision (A3, A3, A2, A7, A1). Change no existing constant value.

**Checkpoint**: `from python.eda import config` exposes the new constants; M1 constants unchanged.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Session segmentation and timestamp parsing - every timeline and plausibility check
depends on knowing where one recording ends. BLOCKS all user stories.

**⚠️ CRITICAL**: Get the session boundary right first. Every cross-boundary computation is a
false alarm waiting to happen (research A1).

- [X] T002 Add tampered-input fixtures to `python/tests/conftest.py`: a clean synthetic session, a row-shuffled variant, a variant with 50 consecutive rows excised, a variant with a block copied and appended, a variant with one steering value nudged off-lattice by 0.023, a variant with an injected impossible speed jump, and a two-session junction where the second session's timestamps precede the first
- [X] T003 Implement `split_sessions(ds)` in `python/eda/integrity.py` - segment a source into contiguous `RecordingSession` values using the image-path prefix; track1/track2 yield one session, combined yields two (FR-002, research A1)
- [X] T004 Implement `parse_capture_times(ds)` in `python/eda/integrity.py` - extract capture timestamps from center-image filenames, returning `(times, n_unparseable)`; never silently drop a row (FR-001)

**Checkpoint**: `split_sessions(load_track("combined"))` returns exactly two sessions whose
`start_time` ordering is *inverted* relative to `start_index` - the track2-before-track1 fact.

---

## Phase 3: User Story 1 - Provenance and integrity audit (Priority: P1) 🎯 MVP

**Goal**: Prove each recording is continuous, complete, unduplicated and physically plausible.

**Independent Test**: Run the audit on track1 and track2; confirm per-track reports of
monotonicity, frame-interval summary, gap counts, three separate duplicate counts, and a robust
acceleration outlier screen. Delivers "this recording is unaltered" with numbers behind it.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T005 [P] [US1] Timeline tests in `python/tests/test_integrity.py` - shuffled fixture reports broken monotonicity; excised-block fixture reports a gap above threshold; clean fixture reports zero gaps and zero violations; **two-session junction fixture raises no cross-boundary alarm** (contract test table)
- [X] T006 [P] [US1] Duplicate tests in `python/tests/test_integrity.py` - copied-block fixture reports exact duplicate rows and duplicate image refs; a fixture with repeated measurement tuples but distinct images reports only the third count and does not inflate the first two (research A8)
- [X] T007 [P] [US1] Plausibility tests in `python/tests/test_integrity.py` - injected-jump fixture reports an acceleration outlier; assert the MAD-based rule flags it where a standard-deviation rule at the same multiplier would not (research A7)

### Implementation for User Story 1

- [X] T008 [US1] Implement `check_timeline(ds)` in `python/eda/integrity.py` - per session: monotonicity, order-violation count, median interval, implied fps, gap threshold `GAP_FACTOR × median`, gap tiers (>2×, >5×, >1s), largest gap, session start/end → `TimelineReport` (FR-003)
- [X] T009 [P] [US1] Implement `check_duplicates(ds)` in `python/eda/integrity.py` - three separate counts, never summed, plus capped example row indices → `DuplicationReport` (FR-004)
- [X] T010 [P] [US1] Implement `check_plausibility(ds)` in `python/eda/integrity.py` - per session implied acceleration `Δspeed/Δt`, median, MAD, `median + ACCEL_MAD_K × MAD` threshold, outlier count and capped indices, plus the `units_note` stating the criterion is relative → `PlausibilityReport` (FR-005)
- [X] T011 [US1] Notebook section 5.1 in `python/notebooks/01_dataset_analysis.ipynb` - narrated: what friziranje is, why the timeline is the hardest thing to fake, why continuity is measured per session (show the combined-source trap explicitly); **visual**: `results/plots/authenticity_timeline.png` = frame-interval distribution per session with the gap threshold marked (FR-023, FR-024)

**Checkpoint**: US1 demonstrable on its own - "the recording is continuous and unaltered".

---

## Phase 4: User Story 2 - Measurement granularity and correctly specified tests (Priority: P1)

**Goal**: Establish the true recording granularity of each variable, then test steering with a
method that matches it - and explain why M1's continuous fit was misspecified.

**Independent Test**: Run granularity profiling on each track; confirm steering is reported as
discrete on a 0.05 lattice with 41 support points, throttle/speed as continuous, track1 brake as
constant. Confirm three χ² results, each with a stated H₀ and post-pooling dof.

### Tests for User Story 2 ⚠️ (write first, ensure they FAIL)

- [X] T012 [P] [US2] Granularity tests in `python/tests/test_integrity.py` - a crafted 0.05-lattice column is classified discrete with spacing 0.05 and its unobserved support points listed; the off-lattice fixture reports the offending value; on-lattice values carrying float representation error are **not** falsely reported off-lattice; a single-valued column is classified `constant` and yields no variance-dependent statistic (FR-008, FR-013)
- [X] T013 [P] [US2] Chi-square tests in `python/tests/test_authenticity.py` - on crafted samples where the answer is known by construction: a uniform sample does **not** reject T1; a symmetric sample does **not** reject T2; two samples drawn from one distribution do **not** reject T3; a strongly skewed sample **does** reject T2; assert `dof` equals the post-pooling value and `n_categories_pooled` is reported (FR-009, FR-010)
- [X] T014 [P] [US2] Pooling test in `python/tests/test_authenticity.py` - assert low-expectation levels merge symmetrically from the tails inward, so pooling alone cannot induce asymmetry in a symmetric input (research A5)

### Implementation for User Story 2

- [X] T015 [US2] Implement `profile_granularity(ds)` in `python/eda/integrity.py` - per numeric column: distinct count, discrete/continuous/constant classification, lattice detection at `LATTICE_ATOL`, spacing, full support, unobserved support points, off-lattice values, reported tolerance, one-line evidence → `GranularityProfile` (FR-006, FR-007, FR-008)
- [X] T016 [US2] Implement the symmetric tail-pooling helper in `python/eda/authenticity.py` - merge levels with expected count < `CHI2_MIN_EXPECTED_PER_BIN` from the tails inward, returning merged counts and the pooled-category count (research A5); required by T017–T019
- [X] T017 [P] [US2] Implement `chi2_uniform_gof(...)` in `python/eda/authenticity.py` - H₀: steering uniform over the lattice support; interpretation MUST state that failing to reject would indicate a uniform RNG produced the column (FR-009, research A4 T1)
- [X] T018 [P] [US2] Implement `chi2_symmetry(...)` in `python/eda/authenticity.py` - H₀: P(+k) = P(−k) per level, evaluated per track, never pooled across tracks (FR-012, research A4 T2)
- [X] T019 [P] [US2] Implement `chi2_homogeneity(...)` in `python/eda/authenticity.py` - H₀: both tracks share one steering distribution over the shared support, retaining support points observed on only one track with count 0; interpretation MUST state that failing to reject would indicate one recording duplicated and renamed (FR-011, research A4 T3)
- [X] T020 [US2] Notebook section 5.2 - narrated: what a lattice is, how we detected it, why χ² on a discrete support needs no binning choices; **visual**: `authenticity_lattice.png` (41 levels, spacing, unobserved points), `authenticity_symmetry.png` (mirrored level frequencies per track), `authenticity_homogeneity.png` (track1 vs track2 overlaid) (FR-023, FR-024)
- [X] T021 [US2] Notebook section 5.2 addendum - keep M1's continuous fit visible and explain in plain language why fitting a smooth density to lattice-valued data is misspecified, so the earlier χ²≈2711 rejection is a property of the model rather than a discovery about the data (FR-019, Assumptions)

**Checkpoint**: US1 + US2 demonstrable; steering is correctly characterised and M1's error is
explained rather than buried.

---

## Phase 5: User Story 3 - Separating explainable findings from suspicious ones (Priority: P2)

**Goal**: Give every finding a verdict, and write the resulting corrections back into the
project's documents.

**Independent Test**: Read the produced report; every finding carries H₀, decision,
interpretation and an explainable/unexplained verdict; the two worked examples (dead brake,
left bias) name their mechanisms and the left bias records its M4 consequence.

### Tests for User Story 3 ⚠️ (write first, ensure they FAIL)

- [X] T022 [P] [US3] Verdict tests in `python/tests/test_authenticity.py` - assert an `explainable` verdict with an empty `mechanism` is impossible to construct (raises), and that a verdict carrying a downstream consequence also carries a mitigation (FR-015, FR-016)

### Implementation for User Story 3

- [X] T023 [US3] Implement `classify_findings(...)` in `python/eda/authenticity.py` - attach `Verdict` values; the track1 constant brake column and the track1 left/right asymmetry must each be classified `explainable` with their mechanism named, and the asymmetry must record its M4 consequence (BC model pulls left) plus mitigation (horizontal flip with sign-flipped steering) (FR-015, FR-016, research A6)
- [X] T024 [US3] Implement the calibration re-check in `python/eda/authenticity.py` - recompute M1's P95 |Δsteering| and P1–P99 steering range and set `calibration_unchanged` + `calibration_note` from the actual comparison, never assumed (FR-018)
- [X] T025 [US3] Implement `run_authenticity(sources)` in `python/eda/authenticity.py` - orchestrate sessions, timeline, duplicates, granularity, plausibility, the three tests and verdicts; save figures to `PLOTS_DIR`; write `results/eda/authenticity_report.md` and `results/eda/authenticity_stats.json`; return `AuthenticityOutput`. Writes only under `results/`; never opens M1's outputs for writing (FR-017, research A9)
- [X] T026 [US3] Notebook section 5.3 - narrated: the explainable-vs-suspicious framework and why a finding without a null model proves nothing; present the verdict table including the dead-brake and left-bias worked examples; print the final `AuthenticityOutput` summary (FR-023)
- [X] T027 [P] [US3] Amend `specs/001-dataset-eda/research.md` R1/R2 - record that steering is lattice-valued (0.05 spacing, 41 levels), that the continuous interior fit was misspecified, and that the "use the empirical distribution" conclusion stands but for the corrected reason; mark the amendment as originating from feature 002 (FR-019)
- [X] T028 [P] [US3] Amend `DESIGN.md` - add the per-track brake note where the pooled 94.6%-zero figure is currently stated, recording that brake is *constant* on track1 and that `brake_is_dead: false` was a pooling artifact (FR-020)
- [X] T029 [P] [US3] Add the M5 forward note to `DESIGN.md` §7 - the RL agent emits continuous steering while the human baseline is lattice-valued; distribution comparison must account for this (e.g. quantise the agent's output onto the same lattice) or it measures recording resolution rather than driving behaviour (FR-021)

**Checkpoint**: All three stories done; findings are interpreted, not just listed.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T030 [P] Run `pytest python/tests -q` - all green, M1 tests still passing (Constitution VIII gate)
- [X] T031 [P] Reproducibility check - run `run_authenticity` twice, assert byte-identical `results/eda/authenticity_stats.json` under SEED=42 (FR-022, SC-011)
- [X] T032 [P] Verify M1 outputs untouched - `git status` shows no modification to `results/eda/m1_report.md` or `results/eda/m1_stats.json` (research A9)
- [X] T033 Notebook top-to-bottom pass on `python/notebooks/01_dataset_analysis.ipynb` - restart & run-all clean; every section-5 cell has its plain-language explanation and a plot where a plot helps (FR-023, FR-024)
- [X] T034 Verify the quickstart expected-results table in `specs/002-data-authenticity/quickstart.md` matches the actual run; if any of the first six rows disagrees, stop and investigate before reporting numbers
- [X] T035 Verify `git status` shows only expected files (no `dataset/`, `.venv*/`); new figures and reports present under `results/` (Constitution VII/VIII merge checklist)

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → no deps, start immediately.
- **Foundational (Phase 2)** → depends on Setup; **BLOCKS US1/US2/US3**.
- **US1 (P1)** → after Foundational. MVP.
- **US2 (P1)** → after Foundational; independent of US1 (different functions, shared module).
- **US3 (P2)** → after US1 + US2 (needs findings to classify and an orchestrator to write them).
- **Polish** → after all stories.

### Within a story

- Tests first (verify they fail), then implementation.
- T016 (pooling helper) blocks T017/T018/T019 - all three χ² tests consume it.
- T023/T024 block T025 (the orchestrator assembles their outputs).
- Notebook sections come after their backing functions exist.

### Parallel Opportunities

- T005/T006/T007 (US1 tests) parallel; T009/T010 (duplicates, plausibility) parallel.
- T012/T013/T014 (US2 tests) parallel; T017/T018/T019 (the three χ² tests) parallel after T016.
- T027/T028/T029 (document amendments) parallel - three different files.
- US1 and US2 can be developed in parallel once Phase 2 is done. Both write to
  `integrity.py`, so coordinate: US1 owns `check_timeline`/`check_duplicates`/
  `check_plausibility`, US2 owns `profile_granularity`. Only the notebook is truly shared -
  agree section order before starting.

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP & VALIDATE**: the
   provenance audit stands alone as "no evidence of tampering, here is the evidence".

### Incremental

Setup + Foundational → US1 (provenance) → US2 (granularity + corrected χ²) → US3 (verdicts +
amendments) → Polish. Each step adds value without breaking the prior.

---

## Notes

- **Constitution III**: AI never commits/pushes. Each checkpoint = owner reviews & commits.
- [P] = different files, no dependencies.
- Verify tests fail before implementing.
- **Every check needs both directions of evidence** (contract test table): it must detect the
  tampered fixture *and* stay silent on the clean one. The combined-source time inversion is
  the false-alarm trap this feature is most exposed to.
- No finding may be reported as a bare number - H₀, decision, interpretation, verdict (SC-008).
- Every reported number must be reproducible under SEED=42 (Constitution VI).
