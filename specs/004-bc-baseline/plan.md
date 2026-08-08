# Implementation Plan: Behavioral Cloning Baseline (M4)

**Branch**: `004-bc-baseline` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-bc-baseline/spec.md`

## Summary

Train a steering-prediction CNN on the recorded human driving and produce the artifacts M5
compares against the RL agent. Two runs differing only in balancing policy, evaluated on one
shared unbalanced validation set, split by **whole recording session** so the leak-free
property is structural rather than tuned.

The three things that decide whether this feature is worth anything:

1. **The split is contiguous block holdout with an 8 s guard band.** The obvious plan, holding
   out whole recording sessions, was checked against the data and withdrawn: the combined file
   contains exactly **two** sessions, one per track, and the largest gap in either recording is
   **0.5 s**. There is nothing to cut on. Ten blocks per track, two held out, every frame within
   8 s of a boundary discarded from both sides. The guard width is derived from steering
   autocorrelation and costs 2.8 percent of the data (research R2).
2. **Feature 002 already owns the statistics.** `stats.describe` returns exactly the six figures
   Principle IX names, and `relative_frequency_histogram` returns the histogram. This feature
   calls them; it does not reimplement them.
3. **Neither existing virtual environment can run this.** `.venv` has pandas and no torch;
   `.venv-mlagents` has torch and CUDA but no pandas. Resolved in research as a third
   environment.

## Technical Context

**Language/Version**: Python 3.10.11 (both existing environments; no reason to differ)
**Primary Dependencies**: PyTorch 2.6.0+cu124, pandas, numpy, Pillow, matplotlib. Reuses
`python/eda` for loading, sessioning and descriptive statistics
**Storage**: files only. Checkpoints and run records under `results/bc/`, figures under
`results/plots/`. The dataset stays git-ignored under `dataset/`
**Testing**: pytest, in `python/tests/`, alongside the existing 237 tests
**Target Platform**: Windows 11, NVIDIA RTX 3050 6 GB Laptop GPU, CUDA 12.4
**Project Type**: single Python package, mirroring `python/eda/` and `python/track/`
**Performance Goals**: not a latency feature. The practical target is that one training run
finishes in a sitting, so the balanced/unbalanced pair can be produced and compared the same day
**Constraints**: 6 GB of VRAM, and 97,329 images on disk. The bottleneck is expected to be image
loading, not the network, which is roughly 250k parameters
**Scale/Scope**: 32,443 recorded rows, three cameras each. Two training runs. Four new modules
and their tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Spec-Driven Development | PASS | spec.md written and validated before this plan. No code yet |
| II. Git-Flow & Atomic Commits | PASS as of 2026-08-08 | Was a deviation while Principle II recognised only `feature/<kebab-desc>`. Resolved at T046 by amending the principle to accept the spec-kit `NNN-<kebab-desc>` form (constitution 1.5.0), not by renaming the branch |
| III. Human-Only Commits | PASS | No agent commits. Every handoff explained and offered for review |
| IV. Multi-Agent Coordination | PASS | Ownership declared below. Touches no Unity file, so no scene-lock contention with 003 |
| V. Design-First Documentation | PASS by construction | DESIGN section 6 amendments are sequenced before the code that implements them. No em dashes in any file this feature writes |
| VI. Reproducibility & Determinism | PASS with a decision | Environment question resolved in research. Seeds fixed and recorded; `results/EXPERIMENTS.md` gets an entry per run |
| VII. Dataset Discipline | PASS | Reads through the existing loader, writes nothing into `dataset/`, never places images in Unity `Assets/` |
| VIII. Test Gates Before Merge | PASS | The constitution names three BC tests by hand: CSV parses, model accepts the right input shape, and augmentation negates steering on horizontal flip. All three are in the task list |
| IX. Statistical Rigor | PASS | Reuses `stats.describe` and `relative_frequency_histogram`, so the six figures cannot drift from M1's definitions |

### Declared file ownership (Principle IV)

This feature owns, and nothing else may edit while it is open:

- `python/bc/` (new package)
- `python/tests/test_bc_*.py` (new)
- `DESIGN.md` section 6 only
- `results/bc/`, and `results/plots/bc_*` (new)
- `requirements-bc.txt` (new)

It explicitly does **not** touch `python/eda/`, `python/track/`, any Unity file, or any other
section of `DESIGN.md`. Feature 003 remains free to edit its own areas on its own branch.

## Project Structure

### Documentation (this feature)

```text
specs/004-bc-baseline/
├── plan.md              # This file
├── spec.md              # Written by /speckit-specify
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── bc-module-api.md # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2, created by /speckit-tasks
```

### Source Code (repository root)

```text
python/
├── eda/                      # EXISTING, read-only for this feature
│   ├── loader.py             #   load_track, resolve_image_paths, check_integrity
│   ├── integrity.py          #   split_sessions, parse_capture_times
│   └── stats.py              #   describe, relative_frequency_histogram
├── track/                    # EXISTING, untouched (lives on branch 003)
├── bc/                       # NEW, this feature
│   ├── __init__.py
│   ├── config.py             #   every named constant, one place, comments naming decisions
│   ├── split.py              #   block holdout with guard band, seeded and recorded
│   ├── survey.py             #   the Phase 2 reconnaissance, kept reproducible
│   ├── dataset.py            #   image loading, preprocessing, augmentation, balancing
│   ├── model.py              #   the network
│   ├── train.py              #   training loop, device handling, run record
│   └── evaluate.py           #   predictions, residuals, descriptives, figures, run comparison
└── tests/
    ├── test_bc_split.py      # NEW
    ├── test_bc_dataset.py    # NEW
    ├── test_bc_model.py      # NEW
    └── test_bc_evaluate.py   # NEW

results/
├── bc/
│   ├── split.json            # session assignment and boundaries, so SC-001 is checkable
│   ├── run_balanced/         # checkpoint + run record + metrics
│   ├── run_unbalanced/
│   └── comparison.md         # the cost of balancing, on both axes
└── plots/
    └── bc_*.png
```

**Structure Decision**: a fourth sibling package under `python/`, matching `eda/` and `track/`
exactly: a `config.py` holding every constant with a comment naming its decision, one module per
responsibility, tests in the shared `python/tests/`. This is the layout the previous two features
established and there is no reason for this one to differ.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1. Three things changed during design and are worth recording.

- **Principle IX got easier, not harder.** Research R5 found that `eda.stats.describe` already
  returns exactly the six figures the principle names, and `relative_frequency_histogram`
  returns the histogram. The contract now forbids `bc.evaluate` from computing any statistic
  itself. This removes the risk that BC's numbers and M1's numbers drift apart in definition
  while both look correct.
- **Principle VIII's three named BC tests are now contract entries**, not intentions: CSV
  parses, model accepts the documented input shape, augmentation negates steering on horizontal
  flip. Each carries a failing case as well as a passing one.
- **Principle VI gained a claim it can actually meet.** Research R8 splits reproducibility into
  exact for evaluation and tolerance-bounded for training, rather than claiming bit-exactness
  that cuDNN will not deliver.

**Agent context file**: the plan template's step to update `CLAUDE.md` between its SPECKIT
markers was skipped. `CLAUDE.md` does not exist and is git-ignored as of 2026-07-26 at the
owner's request. Recreating it to satisfy a template step would undo a deliberate decision.

**Still outstanding, both carried into tasks**: the branch-name deviation below, and the two
DESIGN section 6 amendments (the split, and balancing as two runs) which Principle V requires
be committed before the code they govern.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ~~Branch named `004-bc-baseline`, not `feature/bc-baseline` as Principle II requires~~ **Resolved 2026-08-08, T046** | The spec-kit script generates the numbered form and the repository already carries both shapes from earlier features (`002-data-authenticity` alongside `feature/data-authenticity`) | Resolved by amending Principle II rather than renaming the branch (constitution 1.5.0). Renaming was the other candidate and was rejected: the two shapes in the repository are not one branch renamed but **two different branches**, `002-data-authenticity` at bc09903 and `feature/data-authenticity` at 9301645, both merged into `develop`. A rename would have made this feature comply while leaving the actual pattern undescribed. The number shared with `specs/004-bc-baseline/` is now stated as the reason the form is allowed |
| A third virtual environment, `.venv-bc` | Neither existing environment can run this feature: `.venv` has pandas and no torch, `.venv-mlagents` has torch and CUDA but no pandas, matplotlib or scipy | Adding torch to `.venv` risks pip moving numpy off 1.26.4 and silently invalidating M1's committed numbers, which is the exact failure Principle VI created the two-environment rule to prevent. Adding pandas to `.venv-mlagents` risks disturbing the numpy 1.23.5 pin that mlagents depends on. See research R1 |
| Two training runs rather than one | Spec clarification 1, resolved to option A: the cost of balancing is measured rather than assumed | One run would force a choice between a better predictor and a faithful distribution, and would defend that choice with an argument instead of a number |
