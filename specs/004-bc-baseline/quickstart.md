# Quickstart: Behavioral Cloning Baseline (M4)

How to reproduce every number this feature reports, from a clean checkout. Constitution
Principle VI requires this file to stay literally correct: if a command changes, it changes here
in the same feature.

Commands are PowerShell, matching the rest of the project.

---

## 0. Prerequisites

- The dataset present under `dataset/` (git-ignored, submitted separately). The combined
  recording lives at `dataset/dataset/dataset/`, with `driving_log.csv` and `IMG/`.
- Python 3.10.11.
- An NVIDIA GPU with CUDA 12.4 drivers, or the willingness to pass `--allow-cpu` and wait.

Verify the dataset before anything else. This should print 32443 and 97329:

```powershell
(Get-Content dataset\dataset\dataset\driving_log.csv | Measure-Object -Line).Lines
(Get-ChildItem dataset\dataset\dataset\IMG -Filter *.jpg | Measure-Object).Count
```

The second number must equal three times the first: one row is three camera images. A mismatch
means the archive did not unpack fully, and every statistic downstream would be computed over
the wrong denominator.

---

## 1. The BC environment

This feature uses its own environment, `.venv-bc`. It is neither `.venv` (M1, no torch) nor
`.venv-mlagents` (RL training, no pandas). Research R1 records why merging them was rejected.

```powershell
py -3.10 -m venv .venv-bc
.\.venv-bc\Scripts\python.exe -m pip install --upgrade pip
.\.venv-bc\Scripts\python.exe -m pip install -r requirements-bc.txt
```

Confirm torch sees the GPU:

```powershell
.\.venv-bc\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Expected on the development machine:

```
2.6.0+cu124 True NVIDIA GeForce RTX 3050 6GB Laptop GPU
```

If `cuda.is_available()` is False, stop and fix the driver. Training will refuse to run on CPU
unless you pass `--allow-cpu` explicitly, which is deliberate: a silent CPU epoch on 97k images is
hours of wasted time that looks like progress.

---

## 2. Plan the split

The split is produced once and shared by both runs, so they are scored on the same yardstick.

```powershell
.\.venv-bc\Scripts\python.exe -m python.bc.split --seed 42 --val-fraction 0.2
```

Writes `results/bc/split.json`. Ten contiguous blocks per track, two held out, everything within
8 s of a boundary discarded from both sides. Expected properties, all checkable in the file:

| Property | Expected |
|---|---|
| `n_train_rows` | 25,957 |
| `n_val_rows` | 5,576 |
| `n_guard_rows` | 910, roughly 2.8 percent |
| `min_train_val_gap_s` | 8.09, and never below 8.0 |
| `val_fraction_actual` | 0.1768, **not** 0.20 |

The last two rows are the point worth understanding.

`min_train_val_gap_s` is the number FR-004 turns on: no training frame is within 8 s of any
validation frame. 8 s is not a round number someone liked. It is the shortest lag at which
steering autocorrelation falls below 0.1 on both tracks (research R2).

`val_fraction_actual` lands near the target rather than on it, because blocks are integer-sized
and the guard eats into them. That gap is reported, never corrected: moving a boundary to hit
0.20 would be fitting the split to a number instead of to the data.

Re-run the same command and diff the file against itself. It must be byte-identical (SC-002).


---

## 3. Train both runs

Two runs, differing in one thing.

```powershell
.\.venv-bc\Scripts\python.exe -m python.bc.train --policy none --run-id bc_unbalanced_v01
.\.venv-bc\Scripts\python.exe -m python.bc.train --policy downsample_zero --run-id bc_balanced_v01
```

Each writes a checkpoint and a `RunRecord` into `results/bc/run_<id>/`. The record carries the
seed, hyperparameters, device, duration, sample counts and both error figures.

Read the headline before going further:

| Field | What it means |
|---|---|
| `val_error` | the model's error on the held-out blocks |
| `baseline_error` | the error of always predicting the training mean |
| `beat_baseline` | false means the model learned nothing useful |

`beat_baseline` false is a legitimate result and is reported as one (SC-003).

**Measured, both runs beat the baseline**, so the negative path this section warned about did not
occur. Expect roughly 5 to 6 minutes per run on an RTX 3050, 13 epochs with the best at epoch 8:

| Run | `val_error` | `baseline_error` | `beat_baseline` |
|---|---|---|---|
| `bc_unbalanced_v01` | 0.086670 | 0.153623 | true |
| `bc_balanced_v01` | 0.090899 | 0.153992 | true |

The warning is kept rather than deleted, because the reason it was written still holds: near-zero
steering dominates this recording, predicting the mean is a strong strategy, and a run losing to
it would be reported rather than retried. It simply is not what happened.

Log both runs in `results/EXPERIMENTS.md` in the same session. Principle VI: an unlogged run did
not happen.

---

## 4. Evaluate and compare

```powershell
.\.venv-bc\Scripts\python.exe -m python.bc.evaluate --run bc_unbalanced_v01
.\.venv-bc\Scripts\python.exe -m python.bc.evaluate --run bc_balanced_v01
.\.venv-bc\Scripts\python.exe -m python.bc.evaluate --compare bc_balanced_v01 bc_unbalanced_v01
```

The first two write per-run distribution reports and figures. The third writes
`results/bc/comparison.md`.

Every distribution appears in three scopes: pooled, track1, track2. Expect the per-track figures
to differ substantially. Feature 002 measured track1 at 79.3 percent zero steering against a far
more active track2, and a pooled histogram hides that difference. If your per-track figures look
identical, something is wrong with the track labelling, not with the data.

The comparison reports two deltas and does not collapse them into a winner:

| Delta | Meaning |
|---|---|
| accuracy | which run predicts the human targets more closely |
| distribution | which run's prediction distribution sits closer to the human one |

A run winning one and losing the other was the expected result. **It is not what happened.**
Measured, both deltas point the same way: balanced loses on accuracy by +0.004229 and on
distribution by +0.063091, so unbalanced wins both.

The reason matters before you interpret your own numbers. Neither model reproduces the human zero
spike at all: the human validation column is 57.2 percent exact zeros and both models sit under 5
percent. The distance from the human distribution is dominated by that gap, and balancing pushes
the model further from zero. What actually moved the prediction distribution was the three-camera
augmentation, not the balancing policy, and that was never framed as a distributional choice.
Research R12 carries the argument.

The two deltas are still reported side by side and still not collapsed into a winner. That rule
governs how the comparison is presented and does not depend on which way the numbers came out.

---

## 5. Tests

```powershell
.\.venv-bc\Scripts\python.exe -m pytest python/tests -p no:warnings
```

Expect **334 passed**. Do not add `-q`: `pytest.ini` already sets `addopts = -q`, so a second one
makes it `-qq` and suppresses the pass count, leaving dots and an exit code. This quickstart
carried that mistake until it was walked end to end.

The same suite under `.venv` gives **280 passed, 3 skipped**, the three skips being the test
modules that need torch.

Both figures were 141 and 87 while this feature stood on its own branch. They changed on
2026-08-09, when feature 003 merged and brought the track generator's tests into the same suite.
Nothing about the BC tests changed; the suite they run in got bigger. That is intentional and worth preserving: `bc.split` and `bc.dataset`
import no torch, so every split-level and sample-level decision stays checkable in the M1
environment.

The three tests Principle VIII names by hand:

- the CSV parses,
- the model accepts the documented input shape,
- augmentation negates steering on a horizontal flip.

The M1 and feature 002 tests also live in `python/tests` and run here too. `requirements-bc.txt`
pins numpy to 1.26.4, the same version `.venv` carries, specifically so those tests are not
being asked to reproduce M1's numbers under a different build. **Verified on 2026-08-08: both
environments report numpy 1.26.4 and pandas 2.1.4**, so the pin is doing what it claims and no
M1 number is being reproduced under a different build. If any of them ever fails only under
`.venv-bc`, that is a finding about environment sensitivity and belongs in the research document
rather than being papered over.

---

## 6. Reproduction expectations

| Step | Claim | Verified |
|---|---|---|
| Split | byte-identical from the same seed | yes, across two processes on one machine |
| Evaluation from a checkpoint | exact, since no randomness is involved | yes, byte-identical outputs including figures |
| Training from the same seed | within **0.0005** absolute on `val_error` | yes, measured over three runs |

**Split.** An earlier version of this table claimed byte-identity "on any machine". Only one
machine was tested, so that is not claimed here. What can be said is stronger in a different
direction: the split contains no randomness at all, since the held-out blocks are chosen by even
spacing rather than drawn, and re-running with a different seed changes only the recorded `seed`
field. Its reproducibility therefore does not depend on numpy's RNG behaving identically across
versions, which is the usual way a seeded split stops reproducing.

**Evaluation.** Re-running from a saved checkpoint reproduced `distributions.json` and
`comparison.md` byte for byte, and the three PNG figures as well. Figures are not free here:
matplotlib can stamp generation metadata and make an otherwise deterministic plot differ on every
save. It does not, so regenerating figures during a review produces no spurious diff.

**Training.** Not bit-exact, and not claimed to be. cuDNN picks kernels non-deterministically,
and forcing determinism costs speed without covering every operation. The tolerance was measured
rather than asserted: three runs of `--policy none --seed 42` gave 0.086670, 0.086685 and
0.086411, a range of 0.000273 and a standard deviation of 0.000154. The stated tolerance of
**0.0005** sits above the observed range, because three runs bound the spread rather than
estimate it (research R13).

Two things that measurement also settled. Divergence appears at epoch 1, so it is kernel
selection rather than a seed applied too late; and everything before the GPU is bit-for-bit
identical, with `baseline_error` matching to the last digit across all three runs. Note also that
the reported figure is the **minimum** over the epochs, which is tighter than the per-epoch
spread: at epoch 4 the three runs differ by 0.005325, roughly twenty times the spread at the
best epoch. The tolerance applies to the reported best-epoch value and to nothing else.

All three claims were verified on one machine, one GPU and one torch build. Nothing here measures
agreement across devices.
