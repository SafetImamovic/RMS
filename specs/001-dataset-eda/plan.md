# Implementation Plan: Dataset EDA (M1)

**Branch**: `001-dataset-eda` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-dataset-eda/spec.md`

## Summary

Build a reproducible Python analysis of the Udacity self-driving-car simulator dataset
that (1) verifies the headerless CSV format and proves each column's identity from its
statistical fingerprint, (2) computes descriptive statistics and fits a theoretical
distribution to steering with a χ² goodness-of-fit test (KS cross-check), and (3) derives
concrete calibration values (steering range, abrupt-Δsteering threshold, typical speed
range) written back into `DESIGN.md`. Reusable code lives in a small `python/eda/` package
driven by a notebook; every reported number is produced by committed code under a fixed seed.

## Technical Context

**Language/Version**: Python 3.10.x (locked; ML-Agents compatibility per DESIGN §8)
**Primary Dependencies**: pandas (CSV/data frames), numpy, scipy.stats (distribution fit,
`chi2`, `kstest`), matplotlib (histograms/figures), jupyter (notebook). opencv-python only
if pixel-level image checks are needed; path existence uses `pathlib` (no image decode
required for M1).
**Storage**: Read-only local filesystem — dataset under git-ignored `dataset/`; outputs to
`results/plots/` (figures) and `results/eda/` (text/JSON report).
**Testing**: pytest (`python/tests/`) — loader parsing, path resolution, integrity check,
stats correctness on tiny fixtures.
**Target Platform**: Local dev (Windows, author's NVIDIA machine); analysis is CPU-only.
**Project Type**: Single Python analysis package + notebook (no Unity, no web, no service).
**Performance Goals**: Full run over combined dataset (~32,443 rows) completes in well under
a minute; images are not decoded, only their paths verified, so runtime is I/O-light.
**Constraints**: Fully reproducible under a fixed seed (Constitution VI); dataset never
committed (Constitution VII); statistics are the primary deliverable (Constitution IX).
**Scale/Scope**: 3 dataset sources (track1 ~10,615, track2 ~21,828, combined ~32,443 rows),
~194k image files referenced (paths only), 4 numeric columns, 1 fitted distribution.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Spec-Driven | ✅ | spec.md approved before this plan |
| II. Git-Flow & Atomic | ✅ | Work belongs on `feature/dataset-eda`; commits are the owner's |
| III. Human-Only Commits & Reviewed Handoffs | ✅ | Plan/code changes explained; owner commits. No git mutation by agent |
| IV. Multi-Agent Coordination | ✅ | M1 touches only `python/` + `results/` + DESIGN §4.4/§4.5; no scene/prefab files, no overlap |
| V. Design-First Docs | ✅ | Calibration values flow back into DESIGN (FR-014) |
| VI. Reproducibility | ✅ | Fixed seed, pinned `requirements.txt`, code-in-repo for every number |
| VII. Dataset Discipline | ✅ | Read-only from `dataset/`, path basename+re-root, format validated first |
| VIII. Test Gates | ✅ | pytest for loader + stats; integrity check is an explicit gate |
| IX. Statistical Rigor | ✅ | Descriptive stats + χ² + KS + histogram-vs-theoretical are the core output |

**Result: PASS — no violations, Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-dataset-eda/
├── plan.md              # This file
├── research.md          # Phase 0 output — resolved decisions
├── data-model.md        # Phase 1 output — entities
├── quickstart.md        # Phase 1 output — how to run M1
├── contracts/
│   └── eda-api.md       # Phase 1 output — public functions of the eda package
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
python/
├── requirements.txt          # pinned: pandas, numpy, scipy, matplotlib, jupyter, pytest
├── eda/                      # M1 reusable package (mirrors future bc/, evaluation/)
│   ├── __init__.py
│   ├── config.py             # dataset paths, COLUMN_NAMES, SEED, ALPHA, output dirs
│   ├── loader.py             # load headerless CSV → DataFrame; resolve img paths; integrity check
│   ├── fingerprint.py        # per-column statistical fingerprint → column-identity evidence
│   ├── stats.py              # descriptive stats, Δsteering, distribution fit, chi2 GoF, KS
│   └── report.py             # orchestrate: figures → results/plots, JSON/MD → results/eda
├── notebooks/
│   └── 01_dataset_analysis.ipynb   # narrative EDA calling eda/ (the human-facing report)
└── tests/
    ├── conftest.py           # tiny synthetic CSV + fake IMG/ fixture
    ├── test_loader.py        # parsing, path re-root, integrity check, unresolved-row count
    └── test_stats.py         # descriptive stats + chi2/ks on known inputs

results/
├── plots/                    # steering/speed/Δsteering histograms (+ fitted curve)
└── eda/                      # m1_report.md + m1_stats.json (calibration values)
```

**Structure Decision**: Single Python package `python/eda/` plus a driver notebook. This
mirrors the already-planned `python/bc/` and `python/evaluation/` packages (DESIGN §3), so
M1 establishes the repo's Python conventions (config module, pytest layout) that later
milestones reuse. The notebook is the human-readable deliverable; the package holds the
tested, reusable logic so the notebook stays thin and every number is reproducible.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
