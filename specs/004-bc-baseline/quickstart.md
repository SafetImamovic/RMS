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
- An NVIDIA GPU with CUDA 12.4 drivers, or the willingness to pass `-AllowCpu` and wait.

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
unless you pass `-AllowCpu` explicitly, which is deliberate: a silent CPU epoch on 97k images is
hours of wasted time that looks like progress.

---

## 2. Plan the split

The split is produced once and shared by both runs, so they are scored on the same yardstick.

```powershell
.\.venv-bc\Scripts\python.exe -m python.bc.split --seed 42 --val-fraction 0.2
```

Writes `results/bc/split.json`. Expected properties, all checkable in the file:

| Property | Expected |
|---|---|
| sessions assigned | every session appears exactly once |
| overlap between sides | none, by construction |
| `val_fraction_actual` | close to 0.20 but **not exactly** 0.20 |

The last row is the point worth understanding. Sessions are whole and unequal, so the achieved
fraction lands near the target rather than on it. That gap is reported, never corrected, because
correcting it would mean cutting a session and reintroducing the leak the split exists to
prevent (research R2).

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
| `val_error` | the model's error on held-out sessions |
| `baseline_error` | the error of always predicting the training mean |
| `beat_baseline` | false means the model learned nothing useful |

`beat_baseline` false is a legitimate result and is reported as one (SC-003). It is most likely
on the unbalanced run, where near-zero steering dominates and predicting zero is a strong
strategy. That outcome is exactly what the two-run design exists to expose.

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

A run winning one and losing the other is the expected result. That trade is the finding, and
resolving it into a single verdict would throw away the reason both runs were trained.

---

## 5. Tests

```powershell
.\.venv-bc\Scripts\python.exe -m pytest python/tests -q -p no:warnings
```

The three tests Principle VIII names by hand:

- the CSV parses,
- the model accepts the documented input shape,
- augmentation negates steering on a horizontal flip.

Note that the M1 and feature 002 tests also live in `python/tests` and will run here under a
different numpy than the one they were written against. If any of them fails only under
`.venv-bc`, that is a finding about environment sensitivity and belongs in the research
document, not a thing to paper over.

---

## 6. Reproduction expectations

| Step | Claim |
|---|---|
| Split | byte-identical from the same seed, on any machine |
| Evaluation from a checkpoint | exact, since no randomness is involved |
| Training from the same seed | within a stated tolerance, on the same hardware |

Training is not claimed to be bit-exact. cuDNN picks kernels non-deterministically, and forcing
determinism costs speed without covering every operation. The tolerance is measured by running
one seed twice and reporting the observed spread, rather than asserted in advance (research R8).
