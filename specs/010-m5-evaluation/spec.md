# Feature Specification: M5, evaluation and comparison

**Feature Branch**: `010-m5-evaluation`
**Created**: 2026-09-01
**Status**: Draft
**Input**: Evaluation and comparison of RL against BC against the human dataset, steering
distributions on a common grid, `results/plots`, and a verified README reproduction recipe.

## Why this exists, and why the number 010 is not a contradiction

The scope decision of 2026-08-28 said there would be **no feature 010**. That decision was about
M3: it forbade a fourth reward-side remedy and sent the remaining budget here. This feature is M5,
which is exactly what that decision redirected the budget to. The number is sequential and carries
no other meaning.

M3 closed **met** on 2026-09-01 (`DESIGN.md` 5.2). Four of five milestones are now decided and
**M5 is at zero**: no RL against BC against human comparison, no `results/plots` for it, no verified
README recipe. M5 is the submission deliverable and the defence's final story.

## What is already in hand

- **A policy that drives.** `ppo_car_009_bc-5000101.onnx` and its two spread siblings, 10/10
  held-out three-lap completions deterministic on each of three training seeds, zero wall contacts.
- **A scripted expert.** `HeuristicDriver`, 34 of 34 training seeds, and `results/heuristic/`.
- **A BC model.** `results/bc/run_bc_balanced_v01/` and its unbalanced counterpart, trained on
  camera images and therefore **not drivable in Unity**.
- **The human reference.** The Kaggle dataset and `results/eda/authenticity_report.md`.
- **Per-step traces.** `DriveLogger` writes them, and `results/rl/traces/` already holds runs.

## The two distortions that must be handled before any comparison

Both are recorded in `DESIGN.md` 7 and are the reason this feature is not just plotting.

1. **Recording resolution is not driving style.** The human steering column is on a grid of 41
   values, step 0.05; the RL policy emits a continuous real number. Compared directly, every
   divergence measure reports a large difference that is an artefact of resolution. The agent's
   output is quantised onto the human grid before comparison. The quantisation is applied to the
   agent, never to the human, because the human record is the reference.
2. **Generated tracks have no straights.** A closed curve built from harmonics is always turning,
   so no point on the lap needs zero steering, while the human drove straight 58.6 per cent of the
   time. A raw marginal histogram comparison would report a large difference caused by the track
   geometry rather than by the driver.

## User Scenarios & Testing

### US1: the comparison table exists and every cell is measured (P1)

The table in `DESIGN.md` 7 has four columns: RL agent, BC model, heuristic driver, human dataset.
Cells the column cannot have are marked as such rather than left blank or filled with a proxy. The
BC model does not drive in Unity, so it has no lap completion and no lap time, and that absence is
stated as a limitation with its cause.

### US2: the distribution comparison is statistical, not visual (P1)

Descriptive statistics for steering, speed and delta steering per driver: sample size, mean,
variance, min, max, relative-frequency histogram. Then the quantified comparison the course asks
for: KL divergence on the common grid plus a two-sample KS test, with the p-value reported. A
visual overlay is produced as well but is never the evidence.

### US3: `results/plots` holds the figures the defence uses (P2)

Overlaid histograms per driver, and the plots named in `DESIGN.md` 7. Every figure is regenerated
by a script rather than saved by hand, so a changed input changes the figure.

### US4: the README recipe reproduces the result from a clean clone (P2)

Every step verified end to end: environment setup, track generation, training, evaluation, plots.
The recipe is run as written, and anything that only works because of state already on this machine
is found by running it and is fixed.

## Measurable Outcomes

- **SC-001**: Every cell of the `DESIGN.md` 7 table is either a measured number or an explicit
  statement of why that column cannot have it.
- **SC-002**: The agent's steering is quantised onto the human grid before any divergence measure
  is computed, and the unquantised comparison is reported alongside it to show the size of the
  artefact that was avoided.
- **SC-003**: KL divergence and a two-sample KS test are reported with the p-value, for RL against
  human, BC against human, and heuristic against human.
- **SC-004**: The straight-line asymmetry from `DESIGN.md` 7 is addressed explicitly, either by
  conditioning on curvature or by stating in the result why the marginal comparison stands anyway.
- **SC-005**: Every figure in `results/plots` for this feature is produced by a committed script.
- **SC-006**: The README recipe is executed from a clean clone and the deviations found are fixed
  rather than documented as caveats.
- **SC-007**: The model taxonomy from `DESIGN.md` 7.1 is written in the lecture's terminology.

## Out of Scope

- **Any further M3 work.** M3 is closed met. A better policy is not this feature's business.
- **Making the BC model drive in Unity.** It trained on another simulator's camera images. The
  comparison is at the distribution level for that reason, which is a stated limitation and not a
  gap to close here.
- **The 5M sighted probe.** Named as unfinished in `DESIGN.md` 5.2. It belongs to M3's record, not
  to M5's deliverable.
- **The per-episode records debt** carried since feature 007.
