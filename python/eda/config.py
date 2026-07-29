"""Central configuration for the M1 EDA.

Everything that could look like an "arbitrary pick" lives here as a named, explained
constant, so the notebook and the code never contain unexplained magic numbers, and a
re-run under the same SEED reproduces identical numbers (Constitution VI).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# --- Reproducibility -------------------------------------------------------------------
# Fixed seed so any sampling (e.g. the image-path existence sample) is deterministic.
# 42 is a convention; the value itself does not matter, only that it is fixed and recorded.
SEED: int = 42

# Significance level for the chi-square / KS goodness-of-fit tests.
# 0.05 (5%) is the standard threshold taught in the course; below it we "accept" the fit.
ALPHA: float = 0.05

# --- Dataset format --------------------------------------------------------------------
# The driving_log.csv is HEADERLESS. These are the 7 columns in order (Udacity simulator
# standard, confirmed statistically in DESIGN 6.1).
COLUMN_NAMES: list[str] = [
    "center",    # path to center-camera image
    "left",      # path to left-camera image
    "right",     # path to right-camera image
    "steering",  # normalized ~[-1, 1]; negative = left
    "throttle",  # [0, 1]
    "brake",     # [0, 1]
    "speed",     # >= 0
]

# Numeric columns we actually analyze (indices into COLUMN_NAMES).
NUMERIC_COLUMNS: list[str] = ["steering", "throttle", "brake", "speed"]

# --- Paths -----------------------------------------------------------------------------
# Repo root = two levels up from this file (python/eda/config.py -> repo root).
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

DATASET_ROOT: Path = REPO_ROOT / "dataset"


@dataclass(frozen=True)
class TrackPaths:
    """Where one track's CSV and its IMG/ folder live."""

    csv_path: Path
    img_dir: Path


# The dataset is nested (unzipped as-is): dataset/<name>/<name>/{driving_log.csv, IMG/}.
TRACK_PATHS: dict[str, TrackPaths] = {
    "track1": TrackPaths(
        csv_path=DATASET_ROOT / "track1data" / "track1data" / "driving_log.csv",
        img_dir=DATASET_ROOT / "track1data" / "track1data" / "IMG",
    ),
    "track2": TrackPaths(
        csv_path=DATASET_ROOT / "track2data" / "track2data" / "driving_log.csv",
        img_dir=DATASET_ROOT / "track2data" / "track2data" / "IMG",
    ),
    # "combined" = both tracks concatenated (the source we primarily analyze).
    "combined": TrackPaths(
        csv_path=DATASET_ROOT / "dataset" / "dataset" / "driving_log.csv",
        img_dir=DATASET_ROOT / "dataset" / "dataset" / "IMG",
    ),
}

# --- Outputs ---------------------------------------------------------------------------
# Figures and reports are small and DO get committed (they are defense artifacts).
PLOTS_DIR: Path = REPO_ROOT / "results" / "plots"
EDA_OUT_DIR: Path = REPO_ROOT / "results" / "eda"

# --- Analysis parameters (named so the notebook can explain each) ----------------------
# Number of rows x cameras to sample when verifying image paths exist on disk. A sample
# is enough to prove the re-root logic without stat-ing ~194k files (see research R6).
IMAGE_CHECK_SAMPLE_ROWS: int = 500

# Percentile of |delta-steering| used as the "abrupt steering" threshold for the reward
# (DESIGN 4.5). P95 = flags the sharpest 5% of steering changes as abrupt (research R4).
DELTA_STEERING_PERCENTILE: float = 95.0

# Robust steering range percentiles for the Unity action mapping (research R5): using
# P1..P99 instead of raw min/max avoids mapping the whole range onto rare saturation.
STEERING_RANGE_PERCENTILES: tuple[float, float] = (1.0, 99.0)

# Candidate theoretical distributions for the steering fit. Only SYMMETRIC ones (steering
# has negative values), so no exponential/gamma here (research R1).
STEERING_FIT_CANDIDATES: list[str] = ["norm", "laplace", "uniform"]

# Minimum expected count per bin for the chi-square test to be valid (standard rule,
# research R2). Bins with fewer expected are merged into neighbours.
CHI2_MIN_EXPECTED_PER_BIN: int = 5

# --- Authenticity / integrity checks (feature 002) --------------------------------------
# Everything below is additive. No constant above changes value, so M1's numbers stay
# reproducible (contract: specs/002-data-authenticity/contracts/authenticity-api.md).

# Absolute tolerance for lattice detection. 0.05 is not exactly representable in binary, so
# demanding exact equality would falsely declare a real lattice non-existent.
#
# Research A3 set this to 1e-8 on the strength of an exploratory probe. Running against the
# real log showed that is too tight: every steering level with |value| > 0.45 is recorded
# with a systematic offset of up to 2e-7 (-0.9500002, 0.5000001, ...), while +-0.7 and +-1.0
# are exact. That is how the simulator writes the column, not a manipulation of it, and at
# 1e-8 the check would have reported 18 sound levels as tampered - the exact false alarm
# this feature exists to avoid. 1e-6 absorbs it while staying 50,000x below the 0.05 step,
# so it can never merge two neighbouring levels. The largest residual actually observed is
# reported in every granularity profile, so nothing hides behind the tolerance.
LATTICE_ATOL: float = 1e-6

# A column with at most this many distinct values is a candidate discrete column. Observed:
# ~41 levels for steering vs 5,090-21,743 for throttle/speed - three orders of magnitude, so
# the exact cut-off does not matter, only that it is named and not buried (research A3).
DISCRETE_MAX_DISTINCT: int = 100

# A frame interval counts as a gap when it exceeds this multiple of the session median.
# At ~14 fps, 5x median means ~4-5 consecutive frames were lost: one dropped frame is normal
# simulator load, five in a row is an event. Median-relative, so it self-adjusts (research A2).
GAP_FACTOR: float = 5.0

# Implied acceleration outlier rule: |a - median(a)| > ACCEL_MAD_K * MAD(a). MAD rather than
# standard deviation, because a few injected jumps inflate sigma enough to hide themselves
# (research A7).
ACCEL_MAD_K: float = 5.0

# Substrings in the recorded image path that identify which recording a row belongs to.
# Time is only meaningful inside one session; the combined file concatenates two (research A1).
SESSION_PATH_MARKERS: tuple[str, ...] = ("track1data", "track2data")
