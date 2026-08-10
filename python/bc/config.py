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
# Augmentation (DESIGN 6.2, research R10)
# =========================================================================================

# Horizontal flip probability. 0.5 rather than a tuned value, because at 0.5 the flip's effect
# on the target distribution is exactly symmetrisation, which can be stated analytically
# instead of sampled.
#
# It is doing real work here, not decoration. Training targets run 43.4 percent left against
# 37.1 percent right, mean -0.0296: both tracks are loops driven in one direction, so the
# recording is genuinely left-biased and a model trained on it would inherit the bias.
FLIP_PROBABILITY: float = 0.5

# Brightness multiplier applied to the luminance channel, drawn per sample per epoch.
#
# MEASURED from the recording rather than taken from the usual 0.5 to 1.5. Mean luminance of
# the cropped frame, over 1,200 frames per track: track1 sits in a narrow band (p5 129.5, p95
# 156.8) while track2 spans 51.4 to 150.6, because track2 has deep shadowed sections. Pooled,
# p5 to p95 is 0.51 to 1.13 of the median.
#
# The upper bound is the part worth defending. Nothing in this recording is brighter than 1.17
# times the median, so synthesising frames at 1.5 would train the model on a lighting condition
# the simulator cannot produce. The range covers the observed spread and stops there.
BRIGHTNESS_RANGE: tuple[float, float] = (0.50, 1.15)

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
# next most common lattice value.
#
# Figures below are the TRAINING SPLIT, 77,871 samples from 25,957 rows. This constant was
# first derived as 0.30 by the survey, over all 32,443 rows and before the split existed. Two
# corrections moved it, and the second is the one that matters:
#
# 1. The row set. The survey saw 97,329 samples; the training split has 77,871. Small effect.
# 2. **The two sides of the rule were counted differently.** The zero share was counted raw
#    while the runner-up was counted on the lattice. A side-camera target of 0.017 is not an
#    exact zero, so it never entered the zero count, but it does land in the +0.00 lattice bin.
#    Comparing the two made the spike look smaller than it is, and 0.30 in fact leaves zeros at
#    7.75 percent against a runner-up at 7.28: it breaks the rule it was derived from.
#
# Counted consistently on the lattice, 0.27 is the largest fraction satisfying the rule: zeros
# 7.12 percent against a runner-up at 7.33. At 0.28 zeros pass it, 7.33 against 7.32. The
# crossing is sharp rather than flat, so the second decimal is real here. Sample count goes
# from 77,871 to 66,783.
#
# The lattice is the right basis because it is where M5 compares the distributions. On raw
# values the runner-up is -1.00 at 3.41 percent, which measures the offset clipping rather than
# the driving: side-camera targets carry a continuous jitter and collide nowhere else.
#
# Worth remembering when reading the balanced-versus-unbalanced comparison: the three-camera
# augmentation has ALREADY cut zeros from 58.5 percent of rows to 20.4 percent of samples, so
# balancing matters less here than the raw row-level figure suggests.
BALANCE_KEEP_FRACTION: float = 0.27

# The range a steering value may occupy. Not a tuning knob: it is the simulator's own output
# range, and feature 002 measured the human column as 41 lattice levels spanning exactly it.
# Side-camera targets are clipped to this, because a corrected target outside the range is one
# the car could never have been asked to execute.
STEERING_LIMITS: tuple[float, float] = (-1.0, 1.0)

# =========================================================================================
# Model input (DESIGN 6.2, PilotNet standard)
# =========================================================================================

INPUT_HEIGHT: int = 66
INPUT_WIDTH: int = 200
INPUT_CHANNELS: int = 3

# The recorded frame, 320x160. Stated so the crop rows below can be read as what they are:
# positions in this frame, not fractions of some other size.
FRAME_HEIGHT: int = 160
FRAME_WIDTH: int = 320

# Where the crop starts and stops. DESIGN 6.2 says "crop neba/haube" and gives no rows; these
# are MEASURED rather than taken from the Udacity convention of 60 and 25 (research R9).
#
# CROP_BOTTOM is the car hood. Measured by per-pixel temporal standard deviation over 500
# frames per track, restricted to the centre columns where the hood arc reaches highest: the
# figure drops from about 36 to about 20 at exactly row 137, independently on both tracks. It
# is not zero below that line because the hood is reflective, which is also why a whole-frame
# temporal test finds no static pixels anywhere and would have missed the hood entirely.
#
# CROP_TOP is the sky and scenery. Measured by correlating each image row's horizontal
# intensity centroid against the steering target over 1,500 frames: the signal rises past 0.2
# at row 66, peaks at 0.33 near row 80, and falls back under 0.2 by row 96. Sky pixels are
# 10 percent of row 50 and 1 percent of row 60. Row 60 is where the retained band's mean
# correlation per row is highest, so the crop keeps the most signal per pixel the model has to
# process.
CROP_TOP: int = 60
CROP_BOTTOM: int = 137

# 255, as a name rather than a literal, so the normalisation below reads as arithmetic on the
# pixel range instead of a magic number.
PIXEL_VALUE_MAX: float = 255.0

# =========================================================================================
# Model architecture (DESIGN 6.2: PilotNet, 5 conv + 4 FC, about 250k parameters)
# =========================================================================================

# The NVIDIA end-to-end network, unchanged. Each entry is (out_channels, kernel, stride).
# Inherited rather than designed: DESIGN 6.2 names the architecture, and this feature is a
# BASELINE. Its job is to be the standard answer that M5 measures the RL agent against, so
# tuning the architecture would make it a worse baseline, not a better one.
CONV_LAYERS: tuple[tuple[int, int, int], ...] = (
    (24, 5, 2),
    (36, 5, 2),
    (48, 5, 2),
    (64, 3, 1),
    (64, 3, 1),
)

# The fully connected widths after the convolutions. The final 1 is the steering output: one
# continuous value, not a class, because the human column is continuous and the lattice is
# applied only at comparison time (research R3).
FC_WIDTHS: tuple[int, ...] = (100, 50, 10, 1)

# A CHOICE, and an unmeasured one. The NVIDIA paper uses ReLU and this follows it. Much of the
# Udacity-simulator literature uses ELU instead and reports it helps; that is not tested here,
# because a baseline that quietly differs from the architecture it cites is harder to defend
# than one that matches it.
ACTIVATION: str = "relu"

# =========================================================================================
# Training (DESIGN 6.2: MSE, Adam, early stopping; sizes from research R12)
# =========================================================================================

# MEASURED, and the measurement confirms what R7 predicted: the bottleneck is decoding JPEGs,
# not arithmetic. At batch 64 the GPU sustains 7,595 images per second, and peak VRAM is 336 MB
# of 6 GB. The loader never gets close to that.
#
# 64 rather than something larger. GPU throughput is flat past it (7,967 at batch 256, five
# percent better) and the loader is the binding constraint either way, so a bigger batch buys
# nothing and costs optimiser steps per epoch.
BATCH_SIZE: int = 64

# 8 of 12 logical cores. Measured 685 images per second with no workers, 4,557 with six, 5,776
# with eight. Four cores are left for the main process and the rest of the machine.
#
# The honest throughput figure took three measurements to pin down, and both earlier ones are
# recorded here because each was wrong in an instructive way:
#
# 1. The benchmark above said 5,776 per second. WARM CACHE: it re-read the same few thousand
#    files, which the operating system served from memory.
# 2. The first real epoch ran at about 1,000 per second, roughly 80 seconds. COLD CACHE: it
#    touched 77,871 distinct images that were not in memory yet.
# 3. A full 13-epoch run averaged **about 22 to 26 seconds per epoch** (337 s and 291 s for the
#    two runs). The images fit in the page cache, so every epoch after the first is warm.
#
# The lesson worth keeping: a throughput number is meaningless without saying whether the cache
# was warm, and a single-epoch timing of a multi-epoch job measures the wrong epoch.
DATALOADER_WORKERS: int = 8

# A CHOICE, inherited from the PilotNet and Udacity convention, and deliberately NOT tuned.
#
# Tuning it would mean sweeping against the validation set, and the validation error is this
# feature's headline number. Selecting a hyperparameter on the set you then report makes the
# reported figure optimistic by an amount nobody can state. An epoch here costs about 15
# seconds, so the sweep would have been cheap: it is skipped because it is wrong, not because
# it is expensive.
LEARNING_RATE: float = 1e-4

# A ceiling, not a target: early stopping decides the real length. Both real runs stopped
# themselves at epoch 13, so the ceiling was never approached.
MAX_EPOCHS: int = 50

# Epochs without validation improvement before stopping.
#
# Worth stating plainly, because it is the one place this design touches the validation set
# during training: early stopping SELECTS on validation error, which makes the reported
# `val_error` slightly optimistic. It is accepted rather than hidden. The comparison between
# the two runs is unaffected, since both use the identical procedure, and DESIGN 6.2 asks for
# early stopping by name. An inner holdout carved from the training blocks would remove the
# bias; it is not built because it would need its own guard band and would cost training data
# to sharpen a number that is already only being compared against itself.
EARLY_STOPPING_PATIENCE: int = 5

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

# Added to every lattice bin before the KL divergence, then renormalised.
#
# Needed rather than chosen. DESIGN section 7 asks for KL against the human reference, and KL
# is infinite wherever the model puts mass on a level the human never used. On 41 levels and a
# 5,576 row validation set that is not hypothetical: the far levels are sparsely populated.
# An infinite divergence would report "completely different" for a single stray prediction,
# which is a fact about one frame rather than about driving style.
#
# 1e-9 is small enough not to move a well-populated bin and large enough to keep the figure
# finite. The smoothing is stated wherever the divergence is reported, because a KL that has
# been smoothed is not the same quantity as one that has not.
KL_SMOOTHING: float = 1e-9
