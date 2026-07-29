# Implementation Plan: Data Authenticity & Integrity Checks

**Branch**: `feature/data-authenticity` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-data-authenticity/spec.md`

## Summary

Extend the existing M1 analysis package with a statistically defensible battery of data
authenticity checks ("friziranje podataka"), answering three questions the oral defence is
likely to probe: *is this recording continuous and unaltered*, *what is the true measurement
granularity of each variable*, and *which alarming-looking findings are actually explained by
how the data was recorded*.

Technical approach: two new pure-analysis modules in `python/eda/` reusing the M1 loader, seed
and α; a reporting entry point that writes new files under `results/eda/` without touching M1's
committed outputs; a new narrated notebook section; and pytest coverage that includes
**deliberately tampered fixtures**, so each check is demonstrated to fire rather than merely to
run.

The feature also corrects a live error in M1: steering was treated as continuous and fitted
with continuous densities, but it is recorded on an exact 0.05 lattice with 41 possible values.
Fitting a continuous density to lattice-valued data is misspecified, which makes M1's χ²
rejection a property of the model rather than a discovery about the data. Correcting this turns
χ² from an awkward fit into the textbook-correct tool - a discrete variable over a known finite
support needs no binning decisions at all.

## Technical Context

**Language/Version**: Python 3.10.11 (existing `.venv`, unchanged by this feature)
**Primary Dependencies**: pandas 2.1.4, numpy 1.26.4, scipy 1.13.1, matplotlib, seaborn - all
already pinned in `python/requirements.txt`; **no new dependencies**
**Storage**: Read-only access to the git-ignored `dataset/`; writes only under `results/eda/`
and `results/plots/`
**Testing**: pytest (`python/tests/`), including synthetic tampered fixtures per research A10
**Target Platform**: Local Windows workstation; analysis is platform-independent
**Project Type**: Analysis library + Jupyter notebook (single project, no services)
**Performance Goals**: Full run over both tracks (32,443 rows) completes in well under a
minute - this is table-scan statistics, not image decoding
**Constraints**: Deterministic under `SEED=42`; no modification of M1's committed outputs;
no Unity work; dataset never enters git
**Scale/Scope**: 2 tracks × ~10.6k and ~21.8k rows; 41-point steering support; 4 numeric columns

**Unknowns**: none remaining. Eleven open technical questions were identified and resolved in
[research.md](./research.md) (A1–A11) before this plan was finalised.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Spec-Driven Development | **PASS** | `spec.md` written and validated before this plan; no code written yet. Order `/speckit-specify` → `/speckit-plan` respected. |
| II. Git-Flow & Atomic Commits | **PASS with note** | Work belongs on a `feature/` branch off `develop`. See *Branch naming* below. |
| III. Human-Only Commits | **PASS** | No agent has run or will run any history-mutating git command. Every artifact is handed to the owner with an explanation and a proposed commit message. |
| IV. Multi-Agent Coordination | **PASS** | File ownership declared below. No Unity scene or prefab is touched, so the scene lock is not engaged. No cross-cutting rewrites. |
| V. Design-First Documentation | **PASS** | The three documentation amendments (research A11) are specified *here*, before implementation, and land as `docs:` changes. |
| VI. Reproducibility & Determinism | **PASS** | Reuses `SEED=42` / `ALPHA=0.05` from `config.py`. No new randomness introduced; all statistics are deterministic functions of the input. FR-022 / SC-011 require a double-run equality check. |
| VII. Dataset Discipline | **PASS** | Read-only on `dataset/`; no images decoded; nothing added to Unity `Assets/`. The RL/BC separation is untouched. |
| VIII. Test Gates Before Merge | **PASS** | pytest coverage required by FR-025, strengthened beyond the M1 bar: each check family needs a tampered fixture that it detects, plus a clean fixture it does *not* false-alarm on. |
| IX. Statistical Rigor | **PASS - this is the feature** | Every check carries an explicit H₀, statistic, dof, critical value at α, and decision. Directly serves the course's χ² emphasis. |

### Branch naming (Principle II)

`setup-plan.ps1` reports `BRANCH: 002-data-authenticity`, but Constitution II mandates
`feature/<kebab-desc>` for all real work, and M1 followed that (`feature/dataset-eda`).
**The plan adopts `feature/data-authenticity`.** The spec directory keeps its `002-` prefix -
spec-kit treats directory name and branch name as independent, so there is no conflict to
resolve, only a convention to apply.

### Declared file ownership (Principle IV)

Created: `python/eda/integrity.py`, `python/eda/authenticity.py`,
`python/tests/test_integrity.py`, `python/tests/test_authenticity.py`,
`results/eda/authenticity_report.md`, `results/eda/authenticity_stats.json`,
`results/plots/authenticity_*.png`

Modified: `python/eda/config.py` (new named constants only, no changes to existing values),
`python/notebooks/01_dataset_analysis.ipynb` (**append section 5 only**),
`specs/001-dataset-eda/research.md` (amend R1/R2), `DESIGN.md` (per-track brake note; §7
forward note)

Explicitly **not** touched: `python/eda/loader.py`, `fingerprint.py`, `stats.py`, `report.py`,
`results/eda/m1_report.md`, `results/eda/m1_stats.json`.

### Constitution issue found (out of scope for this feature, needs an amendment)

> **RESOLVED 2026-07-29** - amended in constitution **v1.2.0**. `README.md` §Preduslovi was
> stale in the same way and was corrected alongside it. The paragraph below is kept as the
> record of why the amendment happened.

The constitution's **Technology Constraints** section still reads *"Unity 2022.3 LTS ·
`com.unity.ml-agents` 3.0.x"*. That is now factually wrong: the verified, working combination
is Unity 6000.5.3f1 with `com.unity.ml-agents` 4.0.3 and pip `mlagents` 1.1.0 (Communicator API
1.5.0 matching on both sides - see `ENVIRONMENT.md`). `DESIGN.md` §8 has been corrected; the
constitution has not.

Per the Amendment clause this requires a `docs(spec):` commit and a version bump - **MINOR**
(guidance materially changed, no principle removed or redefined), so **1.1.0 → 1.2.0**. This is
flagged rather than done: it is outside this feature's declared scope, and Principle I forbids
quietly widening scope. It does not block this feature, which touches no Unity tooling.

## Project Structure

### Documentation (this feature)

```text
specs/002-data-authenticity/
├── plan.md              # This file
├── spec.md              # Feature specification (done)
├── research.md          # Phase 0 output - A1..A11 decisions (done)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── authenticity-api.md   # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist (done, all pass)
└── tasks.md             # Phase 2 output (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
python/
├── eda/
│   ├── config.py           # MODIFIED: new named constants (lattice tol, gap factor, MAD k)
│   ├── loader.py           # unchanged - reused as-is
│   ├── fingerprint.py      # unchanged
│   ├── stats.py            # unchanged
│   ├── report.py           # unchanged (M1 orchestration stays intact)
│   ├── integrity.py        # NEW: sessions, timeline, duplicates, plausibility, lattice
│   └── authenticity.py     # NEW: chi-square GoF / homogeneity / symmetry, verdicts, report
├── notebooks/
│   └── 01_dataset_analysis.ipynb   # MODIFIED: append section 5
└── tests/
    ├── conftest.py                 # MODIFIED: add tampered-input fixtures
    ├── test_integrity.py           # NEW
    └── test_authenticity.py        # NEW

results/
├── eda/
│   ├── m1_report.md                # UNTOUCHED
│   ├── m1_stats.json               # UNTOUCHED
│   ├── authenticity_report.md      # NEW
│   └── authenticity_stats.json     # NEW
└── plots/
    └── authenticity_*.png          # NEW
```

**Structure Decision**: Extend the existing single-package layout rather than introduce a new
package. The two new modules split along a real seam - `integrity.py` answers *structural*
questions about the recording (is it continuous, complete, unduplicated, on-lattice) and needs
no hypothesis testing, while `authenticity.py` answers *distributional* questions and is
entirely hypothesis tests plus verdict classification. Keeping them separate means the
structural checks stay usable on their own, and the χ² work has one obvious home.

The split also honours FR-017's constraint: `authenticity.py` owns all writing, mirroring the
existing convention where only `report.py` writes.

## Complexity Tracking

> No Constitution Check violations. This section is intentionally empty.

The one deviation worth naming is not a violation but a deliberate cost: the tampered-fixture
requirement (FR-025) roughly doubles the test-writing effort versus asserting on clean data
only. It is accepted because a detector demonstrated only on clean input has not been
demonstrated at all - and because "how do you know your check works?" is precisely the question
an examiner asks about a fraud-detection claim.
