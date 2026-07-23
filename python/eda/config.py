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
