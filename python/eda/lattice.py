"""The human steering lattice, and the divergence measured on it.

**Why this module exists.** These four functions were written for M4 and lived in
`python/bc/evaluate.py`. M5 compares four drivers on the same lattice, and its comparison runs
under `.venv`, which has no torch. `python.bc.evaluate` imports the model and the trainer, so
importing it from there fails outright. The functions themselves have nothing to do with torch:
they are arithmetic on the grid the human recorder wrote.

So they moved here rather than being copied. `python.bc.evaluate` re-exports them under their
original names, and M4's callers and tests are unchanged. Two implementations of one lattice would
be worse than either, because the first disagreement between them would surface as a difference
between drivers.

**The lattice is a measured property of the dataset, not a convention.** Feature 002 established it:
steering is a lattice of step 0.05 with 41 support points from -1.0 to +1.0, every observed value an
integer multiple within 1e-06. Track1 uses 40 of the 41, never producing 0.95; track2 uses all 41.
"""

from __future__ import annotations

import numpy as np

# Imported rather than redefined. `python.bc.config` is pure constants and imports no torch, so it
# is safe to read from an environment that has none. The constants keep their existing home because
# M4's documentation refers to them there by name.
from python.bc import config


def levels(step: float | None = None, limits: tuple[float, float] | None = None) -> np.ndarray:
    """The steering values the human recording actually contains.

    Derived from the step and the limits rather than listed, and checked against feature 002's
    measurement in the tests.
    """
    low, high = limits if limits is not None else config.STEERING_LIMITS
    step = config.STEERING_LATTICE_STEP if step is None else step
    count = int(round((high - low) / step)) + 1
    return np.round(np.linspace(low, high, count), 4)


def quantise(values, step: float | None = None,
             limits: tuple[float, float] | None = None) -> np.ndarray:
    """Snap continuous values onto the human grid, clipped to the steering limits.

    **Applied to the model or the policy, never to the human.** The human record is the reference
    and is not touched: quantising it would be adjusting the thing being measured against.
    """
    low, high = limits if limits is not None else config.STEERING_LIMITS
    step = config.STEERING_LATTICE_STEP if step is None else step
    snapped = np.round(np.asarray(values, dtype=float) / step) * step
    # The trailing `+ 0.0` turns -0.0 into 0.0. They compare equal, so nothing downstream breaks,
    # but a histogram of the human lattice that lists both "-0.00" and "0.00" invites a reader to
    # wonder which one the real zeros are in.
    return np.round(np.clip(snapped, low, high), 4) + 0.0


def distribution(values: np.ndarray, step: float | None = None,
                 limits: tuple[float, float] | None = None) -> np.ndarray:
    """Relative frequency over the lattice levels, in level order."""
    support = levels(step, limits)
    snapped = quantise(values, step, limits)
    counts = np.array([(snapped == level).sum() for level in support], dtype=float)
    total = counts.sum()
    return counts / total if total else counts


def kl_divergence(candidate: np.ndarray, human: np.ndarray,
                  smoothing: float | None = None) -> float:
    """KL of a driver's steering distribution from the human one, on the shared lattice.

    `DESIGN.md` 7 asks for this figure and states the precondition: KL between a discrete and a
    continuous distribution is undefined without common support, so the shared lattice is a
    prerequisite rather than cosmetics.

    Smoothed by `KL_SMOOTHING`. Without it a single value on a level the human never used makes the
    divergence infinite, which reports "completely different" on the strength of one frame. Track1
    never produces 0.95, so this is not hypothetical. **A smoothed KL is not the same quantity as an
    unsmoothed one, so every report carrying this number says so.**
    """
    eps = config.KL_SMOOTHING if smoothing is None else smoothing
    p = distribution(candidate) + eps
    q = distribution(human) + eps
    p = p / p.sum()
    q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))
