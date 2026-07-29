---
description: "Task list for M1 Dataset EDA"
---

# Tasks: Dataset EDA (M1)

**Input**: Design documents from `/specs/001-dataset-eda/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/eda-api.md

**Tests**: INCLUDED — Constitution VIII (Test Gates) and FR require pytest for loader + stats.

**Organization**: Grouped by user story (US1, US2, US3) so each is independently testable.

**Commit note (Constitution III)**: The AI never runs git. "Commit" below means *the owner
reviews and commits*; each checkpoint is a natural review-and-commit point.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (from spec.md)

## Path Conventions

Python analysis package at `python/eda/`, notebook at `python/notebooks/`, tests at
`python/tests/`, outputs to `results/plots/` and `results/eda/` (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Python environment and package skeleton

- [X] T001 Create `python/requirements.txt` pinning: pandas, numpy, scipy, matplotlib, seaborn, jupyter, pytest (versions compatible with Python 3.10)
- [X] T002 Create package skeleton: `python/eda/__init__.py`, `python/notebooks/`, `python/tests/`, and ensure `results/plots/` and `results/eda/` exist (with `.gitkeep`)
- [X] T003 [P] Create `python/eda/config.py` with `SEED=42`, `ALPHA=0.05`, `COLUMN_NAMES`, `DATASET_ROOT`, `TRACK_PATHS` (track1/track2/combined csv+img paths), `PLOTS_DIR`, `EDA_OUT_DIR` (per contracts/eda-api.md)
- [X] T004 [P] Verify `.gitignore` keeps `results/plots/` and `results/eda/` tracked (only `results/tensorboard/` + large event/checkpoint files are ignored) so M1 figures + reports commit normally

**Checkpoint**: `pip install -r python/requirements.txt` succeeds; `import python.eda.config` works.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The dataset loader every story depends on (parse headerless CSV, resolve paths, integrity). BLOCKS all user stories.

**⚠️ CRITICAL**: No user story can begin until the loader works.

- [X] T005 Implement `load_track(name)` in `python/eda/loader.py` — read headerless CSV into `COLUMN_NAMES`, coerce numeric cols to float (handle scientific notation), raise `ValueError` if column count != 7 (per contracts + FR-002)
- [X] T006 Implement `resolve_image_paths(ds)` in `python/eda/loader.py` — basename + re-root center/left/right onto `img_dir`, string-only (no image decode) (FR-004)
- [X] T007 Implement `check_integrity(ds)` in `python/eda/loader.py` — `rows*3 == image_count`, seeded-sample existence check + full `unresolved_rows` count, side-effect free (FR-003, FR-004, edge: unreadable images)

**Checkpoint**: `load_track("track1")` returns a parsed, resolvable, integrity-checked dataset.

---

## Phase 3: User Story 1 - Verified format & column identity (Priority: P1) 🎯 MVP

**Goal**: Prove the 7-column format and each numeric column's identity from its statistical fingerprint; integrity passes on all three sources.

**Independent Test**: Run analysis on combined + per-track; confirm integrity (`rows×3==images`) and a fingerprint table assigning steering/throttle/brake/speed with evidence.

### Tests for User Story 1 ⚠️ (write first, ensure they FAIL)

- [X] T008 [P] [US1] Test loader in `python/tests/test_loader.py` — parsing 7 cols, `ValueError` on wrong count, path re-root correctness, integrity math, unresolved-row count (uses tiny synthetic CSV + fake IMG fixture in `python/tests/conftest.py`)
- [X] T009 [P] [US1] Test fingerprint in `python/tests/test_fingerprint.py` — on a crafted frame where identities are known, assert `inferred_identity` maps correctly (only-negative→steering, all-zero→brake, ≥0 large→speed, [0,1]→throttle)

### Implementation for User Story 1

- [X] T010 [US1] Create `python/tests/conftest.py` — synthetic 7-col CSV fixture + fake `IMG/` folder with matching filenames
- [X] T011 [P] [US1] Implement `column_fingerprints(ds)` in `python/eda/fingerprint.py` — min, max, %negative, %zero, mean, rule-based `inferred_identity` + one-line `evidence`, independent of `COLUMN_NAMES` (FR-005)
- [X] T012 [US1] Notebook section 1 in `python/notebooks/01_dataset_analysis.ipynb` — step-by-step, plain-language markdown before each cell: (a) load combined, (b) show head + shape, (c) integrity check with explanation, (d) fingerprint table, (e) **visual**: bar chart of %negative/%zero per column making the identity obvious (FR-016, FR-017)

**Checkpoint**: US1 fully demonstrable — "we have proven what our data is."

---

## Phase 4: User Story 2 - Descriptive statistics & distribution fit (Priority: P1)

**Goal**: Describe steering/speed/Δsteering with course statistics; fit steering + χ² goodness-of-fit (+ KS), with per-track comparison. Beginner-narrated and highly visual.

**Independent Test**: Run analysis; confirm descriptive stats + steering fit (AIC ranking, χ² decision, KS) + saved histograms with fitted curve.

### Tests for User Story 2 ⚠️ (write first, ensure they FAIL)

- [X] T013 [P] [US2] Test stats in `python/tests/test_stats.py` — `describe()` returns correct n/mean/variance/min/max on known input; `delta_steering()` does NOT difference across a simulated track junction; `fit_steering()` returns a `FitResult` with valid dof and a boolean decision on a known-normal sample

### Implementation for User Story 2

- [X] T014 [P] [US2] Implement `describe(series)` in `python/eda/stats.py` — n, mean, std, variance, min, max, percentiles (P1/P5/P50/P95/P99) → `DistributionSummary` (FR-006)
- [X] T015 [P] [US2] Implement `delta_steering(ds)` in `python/eda/stats.py` — per-track consecutive diff, never across combined junction (FR, research R4)
- [X] T016 [P] [US2] Implement `relative_frequency_histogram(series, bins)` in `python/eda/stats.py` (FR-007)
- [X] T017 [US2] Implement `fit_steering(series, alpha)` in `python/eda/stats.py` — fit normal/laplace/uniform, rank by AIC, χ² GoF (expected≥5 per bin, dof=bins-1-#params), KS cross-check, zero-mass → `FitResult` (FR-008, FR-009, research R1/R2/R3)
- [X] T018 [US2] Notebook section 2 (descriptive stats) — narrated markdown + **visual**: steering/speed/Δsteering histograms, box/violin for spread, per-track steering overlay (FR-010, FR-016, FR-017)
- [X] T019 [US2] Notebook section 3 (distribution fit) — narrated: explain fit→AIC→χ²→KS in plain language; **visual**: histogram with all 3 fitted curves, winner highlighted, zero-spike annotated, χ²/KS results table; |Δsteering| histogram with P95 threshold line (FR-016, FR-017)

**Checkpoint**: US1 + US2 both demonstrable; the human-steering baseline is statistically characterized.

---

## Phase 5: User Story 3 - Calibration values into the design (Priority: P2)

**Goal**: Emit machine-readable calibration values and write them back into DESIGN §4.4/§4.5.

**Independent Test**: After a run, `results/eda/m1_stats.json` exists with steering range, Δsteering threshold, speed range; DESIGN §4.4/§4.5 updated traceably.

### Implementation for User Story 3

- [X] T020 [US3] Implement `run_m1(primary)` in `python/eda/report.py` — orchestrate load+resolve+integrity, fingerprints, describe+fit, save figures to `PLOTS_DIR`, write `results/eda/m1_report.md` + `results/eda/m1_stats.json` (`CalibrationOutput`), return it; writes only under `results/` (contracts, FR-011, FR-012, FR-014)
- [X] T021 [US3] Notebook section 4 (calibration & conclusions) — narrated: what numbers we hand to Unity and why (steering P1–P99 range, Δsteering P95 threshold, speed range), brake-dead note (FR-013); print `CalibrationOutput`
- [X] T022 [US3] Update `DESIGN.md` §4.4 (steering action range) and §4.5 (abrupt-Δsteering threshold) + typical speed range with the M1-derived values, each traceable to `m1_stats.json` (FR-014, Constitution V) — **owner reviews before commit**

**Checkpoint**: All three stories done; M1 gate satisfiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 [P] Run `pytest python/tests -q` — all green (Constitution VIII gate)
- [X] T024 [P] Reproducibility check — run `run_m1` twice, assert identical `m1_stats.json` under SEED=42 (SC-006)
- [X] T025 Notebook top-to-bottom pass — restart & run-all clean; verify every cell has its plain-language explanation and a plot where a plot helps (FR-016, FR-017); intro cell with the plain-language glossary
- [X] T026 [P] Update `README.md` "Upotreba" if M1 run commands changed; confirm `quickstart.md` steps work end-to-end
- [X] T027 Verify `git status` shows only expected files (no `dataset/`, `.venv/`); `results/plots/` figures + `results/eda/` reports present (Constitution VII/VIII merge checklist)

---

## Dependencies & Execution Order

- **Setup (P1)** → no deps, start immediately.
- **Foundational (P2, loader)** → depends on Setup; **BLOCKS US1/US2/US3**.
- **US1 (P1)** → after Foundational. MVP.
- **US2 (P1)** → after Foundational; independent of US1 (shares loader only).
- **US3 (P2)** → after US1 + US2 (needs fingerprints + stats to emit calibration).
- **Polish** → after all stories.

### Within a story

- Tests first (fail), then implementation.
- `stats.py` functions (T014/T015/T016) can be parallel; `fit_steering` (T017) after them.
- Notebook sections come after their backing functions exist.

### Parallel Opportunities

- T003/T004 (setup) parallel.
- T008/T009 (US1 tests) parallel; T014/T015/T016 (US2 stats fns) parallel.
- US1 and US2 can be developed in parallel once loader (Phase 2) is done — different files
  (`fingerprint.py` vs `stats.py`), only the notebook is shared (coordinate section order).

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 Setup → 2. Phase 2 Foundational (loader) → 3. Phase 3 US1 → **STOP & VALIDATE**:
   integrity + fingerprint prove the data. Demoable on its own.

### Incremental

Setup+Foundational → US1 (MVP, "we know our data") → US2 (statistical characterization) →
US3 (calibration into design) → Polish. Each step adds value without breaking the prior.

---

## Notes

- **Constitution III**: AI never commits/pushes. Each checkpoint = owner reviews & commits.
- [P] = different files, no dependencies.
- Verify tests fail before implementing (US1/US2).
- Notebook is the human-facing deliverable — pedagogical + visual (FR-016/FR-017) is a
  first-class acceptance criterion, not polish.
- Every reported number must be reproducible under SEED=42 (Constitution VI).
