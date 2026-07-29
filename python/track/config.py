"""Named constants for the M2 driving environment.

Every value here is either measured in M1, derived from a measured value, or a stated
design choice with its reason attached. None is "chosen because it looked right" - that
rule is the whole point of specs/003-unity-environment/research.md, and each constant
below names the decision (C1 to C15) that settled it.

This module adds constants only and NEVER imports from python.eda, so nothing here can
change an M1 number (contract: contracts/track-generator-api.md).
"""

from __future__ import annotations

from pathlib import Path

# --- Paths -------------------------------------------------------------------------------
# python/track/config.py -> repo root
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

TRACKS_DIR: Path = REPO_ROOT / "unity" / "SelfDrivingSim" / "Assets" / "Tracks"
TRACK_RESULTS_DIR: Path = REPO_ROOT / "results" / "tracks"
DRIVE_LOGS_DIR: Path = REPO_ROOT / "results" / "drive_logs"
PLOTS_DIR: Path = REPO_ROOT / "results" / "plots"

# =========================================================================================
# Vehicle (research C1, C2, C3, C4)
# =========================================================================================

# The ONE freely chosen physical dimension. A typical passenger-car wheelbase. Every radius
# in this feature scales linearly with it, which is recorded so that changing it moves the
# radius table without invalidating a single conclusion (C1).
WHEELBASE_M: float = 2.5

# Road-wheel angle at full lock. Fixed by DESIGN 4.4, which maps the action range [-1, 1]
# onto +-25 degrees. M1 confirmed the human driver uses the full range in both directions,
# so the mapping is justified by data rather than by saturation (C1).
STEER_MAX_DEG: float = 25.0

# Safety factor on the minimum turning radius. NOT an arbitrary cushion: it is exactly the
# steering reserve the agent keeps in the tightest corner. At 1.3 a corner demands 0.789 of
# full lock and 21.1 percent stays free for correction. At 1.0 the tightest corner demands
# everything and the agent has nothing left to correct with, which is a trap rather than a
# track (C2). This is the only knob that controls max_required_steer.
RADIUS_MARGIN: float = 1.3

# Top speed of the simulated car. A playability choice, NOT a claim about the dataset: it
# gives a lap of roughly 19 s at TRACK_R0_M. The recorded speed column has no documented
# unit, so a "derived" top speed would smuggle in a conversion nobody can check. This value
# never enters a comparison; FR-004 and normalise_speed handle that instead (C3, FR-003).
V_MAX_MS: float = 10.0

# How fast the steering input may travel, in normalised units per second. Provisional.
# Task T023 settles it by measuring a human keyboard drive: the 95th-percentile steering
# change must land within a factor of two of the recorded human figure at COMPARE_HZ.
# A factor rather than a target, because the two recordings differ by 2.33x between
# themselves and so cannot define one (C4, FR-005).
STEER_RATE_NORM_PER_S: float = 2.0

# Achievable acceleration and braking. Provisional, settled by T024 against the recorded
# speed-change distribution on the normalised scale. The braking figure starts at the P95
# implied deceleration from the dataset (C11), which is also what RAY_LENGTH_M is derived
# from, so the two must be settled together.
ACCEL_MS2: float = 5.0
BRAKE_MS2: float = 5.85

# =========================================================================================
# M1 calibration envelope (research C1, C4, C11)
# =========================================================================================
# Measured from dataset/track{1,2}data/driving_log.csv and reproduced by
# `python -m python.eda.report`. These are the numbers FR-009 reports a keyboard drive
# against. Per-track, never pooled, for every per-frame quantity: pooling across the two
# recordings measures the join rather than the driving (feature 002, A1).

# Steering reaches full lock in both directions on BOTH recordings. Even the robust
# P1-P99 range is (-1, 1), so the action mapping is justified by data (DESIGN 4.4).
DATASET_STEER_ABS_MAX: float = 1.0

# Per-frame |delta steering| at 14.08 frames/s. The two recordings differ by a factor of
# 2.33, which is why FR-005 asks for a factor of two rather than a value.
DATASET_DSTEER_P95_TRACK1: float = 0.30
DATASET_DSTEER_P95_TRACK2: float = 0.70
# Full range in a single frame, on both recordings. This is evidence about the INPUT DEVICE
# (keyboard or mouse), not a vehicle capability. A car that reproduces it is unsteerable, so
# the steering rate deliberately does not chase this number (C4).
DATASET_DSTEER_MAX: float = 1.00

# Speed. Pooled P99 is the normalisation divisor for the dataset side of every speed
# comparison; the per-track figures are here so a comparison is never made against the
# wrong recording.
DATASET_SPEED_P99: float = 17.4865  # pooled, results/eda/m1_stats.json
DATASET_SPEED_MAX: float = 21.9494  # pooled
DATASET_SPEED_P99_TRACK1: float = 18.8942
DATASET_SPEED_P99_TRACK2: float = 15.0847

# Per-frame |delta speed|, in dataset units. The P95 figure is what RAY_LENGTH_M derives
# from once translated to V_MAX_MS: the range is chosen for ORDINARY braking, not for the
# hardest brake ever recorded, because an agent may not rely on its maximum (C11).
DATASET_DSPEED_P95: float = 0.7273  # track2, the harder of the two
DATASET_DSPEED_MAX: float = 1.9567  # track2

# Fraction of frames with exactly zero steering, pooled. The reason the distribution
# comparison in matching.py is against the CONDITIONAL distribution: a harmonic loop has no
# straight sections at all, so comparing full distributions would measure track topology
# rather than driving (C9).
DATASET_STEER_ZERO_PCT: float = 58.555

# =========================================================================================
# Generator (research C6, C7)
# =========================================================================================

TRACK_R0_M: float = 30.0
HARMONICS: tuple[int, ...] = (2, 3, 4, 5)
AMPLITUDE_RANGE: tuple[float, float] = (0.40, 0.70)
SAMPLES_PER_TRACK: int = 2000

# =========================================================================================
# Geometry (research C10, C12)
# =========================================================================================

TRACK_WIDTH_M: float = 6.0
MIN_SEPARATION_M: float = 12.0  # 2 x track width
N_CHECKPOINTS: int = 24
START_LATERAL_M: float = 1.5
START_YAW_DEG: float = 10.0

# =========================================================================================
# Sensing (research C11)
# =========================================================================================

RAY_COUNT: int = 13
RAY_FOV_DEG: float = 180.0
# Derived, not chosen: a little over twice the 8.5 m stopping distance at V_MAX_MS under
# P95 braking, plus vehicle length. A sensor shorter than the stopping distance reports a
# wall the car can no longer avoid, which is no information at all. Asserted against
# stopping_distance_m in test_vehicle.py so the derivation cannot silently drift (C11).
RAY_LENGTH_M: float = 20.0

# =========================================================================================
# Comparison (research C8, C14, C15)
# =========================================================================================

# Median frame rate of track1. Every per-frame quantity is resampled to this before any
# comparison, because a per-frame delta means nothing without the rate it was measured at
# (C14).
COMPARE_HZ: float = 14.08

# Wasserstein-1 acceptance threshold, DERIVED in C15 from three distances measured on the
# dataset itself rather than picked. It must stay strictly below W1_STRUCTURELESS or a
# distribution with no structure at all would pass and the decision would discriminate
# nothing; and above W1_SELF_CONSISTENCY or we would be asking the generator to sit closer
# to track1 than track1 sits to itself. 0.05 is the geometric mean of those two bounds.
MATCH_DISTANCE_THRESHOLD: float = 0.05

# The three measured scales, carried in every MatchReport so a bare distance is readable.
W1_SELF_CONSISTENCY: float = 0.0231  # track1 first half vs second half
W1_STRUCTURELESS: float = 0.1047  # track1 vs uniform on [0, max_required_steer]
W1_HUMAN_TO_HUMAN: float = 0.2635  # track1 vs track2

# =========================================================================================
# Seeds (research C13)
# =========================================================================================
# Deliberately far apart so the two sets cannot collide even if training is extended later.
# Without disjoint evaluation tracks, M3 can only claim the agent learned THESE tracks.

TRAIN_SEEDS: range = range(1, 41)
EVAL_SEEDS: range = range(1001, 1011)
