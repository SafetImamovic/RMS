"""Every named constant M4 uses, in one place, each naming the decision it came from.

The rule this module exists to enforce: **a constant defined in two places is a constant that
will disagree.** No numeric literal belongs anywhere else in `python/bc`, with two exceptions
that are not decisions: array indexing, and the candidate values `survey.py` sweeps, which are
what was *considered* rather than what was chosen.

Nothing here was picked because it looked reasonable. Every value is either inherited from an
earlier feature, derived from a measurement recorded in `specs/004-bc-baseline/research.md`, or
labelled plainly as a choice. Where a value is a choice, this file says so.
"""

from __future__ import annotations

from pathlib import Path

from python.eda import config as eda_config

# =========================================================================================
# Shared with the rest of the project
# =========================================================================================

# One seed convention for the whole repository. Imported rather than retyped: M1 and M4
# disagreeing about what seed 42 means would be invisible until someone tried to reproduce a
# figure and got a different one.
SEED: int = eda_config.SEED

REPO_ROOT: Path = eda_config.REPO_ROOT
BC_OUT_DIR: Path = REPO_ROOT / "results" / "bc"
PLOTS_DIR: Path = eda_config.PLOTS_DIR
SPLIT_PATH: Path = BC_OUT_DIR / "split.json"

# The recording M4 trains on. Both tracks, because it is the larger sample and covers both
# driving profiles; results are still reported per track (research R6).
DATASET_NAME: str = "combined"

# =========================================================================================
# Split (research R2)
# =========================================================================================

# What we ask for. What we GET is about 0.177, and that figure is reported rather than
# corrected: blocks are integer-sized and the guard eats into them, so forcing the target
# would mean moving a boundary to hit a number instead of fitting the data.
VAL_FRACTION_TARGET: float = 0.2

# Contiguous blocks per track, and how many of them are held out.
#
# Session-level holdout was the original plan and is not available: the combined recording
# contains exactly two sessions, one per track, and the largest gap in either is 0.5 s. Two
# continuous takes with nothing to cut on.
#
# Ten blocks with two held out, rather than five with one, because two separated held-out
# blocks sample two different parts of the lap. A single contiguous 20 percent stretch could
# be one corner repeated, and the validation error would then describe that corner.
N_BLOCKS: int = 10
N_HOLDOUT: int = 2

# DERIVED, not chosen: the shortest lag at which steering autocorrelation falls below 0.1 on
# both tracks (track1 +0.085, track2 +0.011). Frames closer together than this carry nearly
# the same target, so a validation frame inside the guard of a training frame is scored on
# something the model has effectively already seen.
#
# Discarded from BOTH sides of every boundary. Adjacency is symmetric: guarding only the
# validation side leaves training frames sitting against the cut. Costs 2.8 percent of the
# data, which is cheap for the guarantee.
GUARD_SECONDS: float = 8.0

# =========================================================================================
# Camera augmentation (research R4)
# =========================================================================================

# The side-camera steering correction, drawn per sample from this range.
#
# DESIGN 6.1 originally carried the constant 0.2, inherited from the PilotNet convention. That
# constant was measured to place 40.6 percent of training targets on exactly plus and minus
# 0.20. Since 0.20 is a real lattice point, those two modes are indistinguishable in a
# histogram from genuine human steering, and the prediction distribution is exactly what M5
# compares.
#
# The range keeps a mean of exactly 0.20, so it generalises the old value rather than
# replacing it. 0.05 to 0.35 was swept and rejected: it inflates the genuine above-0.30 tail
# from 27.6 to 33.9 percent, diluting real human data with synthesised values, which is a
# worse fault than the spike it set out to fix.
#
# Still a CHOICE, not a derivation. The true correction for a laterally displaced camera
# depends on speed and curvature, and the dataset documents neither.
CAMERA_OFFSET_RANGE: tuple[float, float] = (0.10, 0.30)

# Drawn once at sample-build time from SEED, never re-drawn per epoch. Re-drawing would be
# stronger augmentation, but the training target distribution would be a different object
# every epoch and this feature has to be able to report what it was.
OFFSET_DRAWN_ONCE: bool = True

# =========================================================================================
# Balancing (research R4, DESIGN 6.2)
# =========================================================================================

# What counts as "near zero" for downsampling: EXACTLY zero, nothing wider.
#
# The neighbouring lattice levels carry 2.6 to 3.8 percent each and are genuine human
# decisions. Widening the band would discard real steering inputs to fix a spike that sits
# entirely on one value.
ZERO_STEERING_BAND: float = 0.0

# How much of the exact-zero mass survives balancing.
#
# DERIVED from a rule rather than picked: reduce the zero spike until it is no larger than the
# next most common lattice value. After the jittered augmentation, exact zeros hold 20.38
# percent of training samples and the runner-up (-0.25) holds 6.17 percent. Keeping 0.30 lands
# zeros at 6.78 percent, just above the runner-up, and takes the sample count from 97,329 to
# 84,031.
#
# Worth remembering when reading the balanced-versus-unbalanced comparison: the three-camera
# augmentation has ALREADY cut exact zeros from 58.6 percent of rows to 19.5 percent of
# samples, so balancing matters less here than the raw row-level figure suggests.
BALANCE_KEEP_FRACTION: float = 0.30

# =========================================================================================
# Model input (DESIGN 6.2, PilotNet standard)
# =========================================================================================

INPUT_HEIGHT: int = 66
INPUT_WIDTH: int = 200
INPUT_CHANNELS: int = 3

# =========================================================================================
# Comparison (feature 002, DESIGN section 7)
# =========================================================================================

# The human steering column is lattice-valued: 41 levels at this step, measured in feature
# 002. M4 stores raw continuous predictions and applies this grid only where the two
# distributions are compared, which is where DESIGN section 7 assigns it (research R3).
STEERING_LATTICE_STEP: float = 0.05

# Bins for every relative-frequency histogram this feature reports, so predictions, residuals
# and the human reference are all binned the same way and remain comparable.
HISTOGRAM_BINS: int = 40
