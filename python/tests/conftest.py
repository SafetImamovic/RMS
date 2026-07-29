"""Shared pytest fixtures: a tiny synthetic dataset that mimics the real format.

We build a 5-row headerless CSV (7 columns, Windows-style image paths) plus a fake IMG/
folder with matching files, then point config.TRACK_PATHS at it via monkeypatch. This lets
us exercise the loader/fingerprint code without the real ~200k-image dataset.

The second half of this file builds the **deliberately tampered inputs** for feature 002
(research A10). Each one is small, synthetic, and constructed so the correct answer is known
in advance — a detector that has only ever seen clean data has not been demonstrated to work.
Two of them exist for the opposite reason: to prove a check stays *silent* where nothing is
wrong (the two-session junction, and repeated measurement tuples with distinct images).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from python.eda import config as eda_config
from python.eda.config import TrackPaths
from python.eda.loader import TrackDataset

# Known values chosen so each numeric column has an unambiguous identity:
#   steering: has negatives (left turns)        throttle: [0,1] with positives
#   brake:    all zero (no braking in this clip) speed:    large magnitude
_STEERING = [-0.5, 0.0, 0.3, 0.0, -0.2]
_THROTTLE = [0.5, 0.0, 0.8, 0.2, 0.0]
_BRAKE = [0.0, 0.0, 0.0, 0.0, 0.0]
_SPEED = [10.0, 15.0, 0.0, 22.0, 5.0]


@pytest.fixture
def synthetic_track(tmp_path, monkeypatch):
    """Create a 5-row track with all images present, registered as track 'testtrack'."""
    img_dir = tmp_path / "IMG"
    img_dir.mkdir()

    records = []
    for i in range(5):
        ts = f"2020_01_01_00_00_0{i}_000"
        names = {cam: f"{cam}_{ts}.jpg" for cam in ("center", "left", "right")}
        for fname in names.values():
            (img_dir / fname).write_bytes(b"x")  # content irrelevant; only existence matters
        records.append(
            [
                f"Desktop\\clip\\IMG\\{names['center']}",
                f"Desktop\\clip\\IMG\\{names['left']}",
                f"Desktop\\clip\\IMG\\{names['right']}",
                _STEERING[i],
                _THROTTLE[i],
                _BRAKE[i],
                _SPEED[i],
            ]
        )

    csv_path = tmp_path / "driving_log.csv"
    pd.DataFrame(records).to_csv(csv_path, header=False, index=False)

    # Register the synthetic track so load_track("testtrack") works.
    patched = dict(eda_config.TRACK_PATHS)
    patched["testtrack"] = TrackPaths(csv_path=csv_path, img_dir=img_dir)
    monkeypatch.setattr(eda_config, "TRACK_PATHS", patched)

    return {
        "name": "testtrack",
        "csv_path": csv_path,
        "img_dir": img_dir,
        "n_rows": 5,
        "n_images": 15,  # 5 rows x 3 cameras, all present
    }


# =======================================================================================
# Feature 002 — authenticity fixtures (research A10)
# =======================================================================================
#
# These never touch the filesystem. Every integrity/authenticity function is pure and works
# off the DataFrame, so an in-memory TrackDataset is enough and the tests stay fast.

# The real recorder writes ~14 frames/s on both tracks (median dt = 0.070 s).
FRAME_DT = 0.070
# Jitter is real: the simulator does not hit a perfectly even cadence. A check that flags
# ordinary jitter as a gap is broken, so the clean fixture must contain some.
FRAME_JITTER = 0.008
# Track 1's first frame in the real dataset. Using real-looking timestamps keeps the
# filename format honest.
T1_START = datetime(2019, 4, 2, 19, 25, 33, 671_000)
# Track 2 was recorded EARLIER the same day. This is the fact that makes the combined file
# a false-alarm trap (research A1).
T2_START = datetime(2019, 4, 2, 18, 5, 37, 641_000)


def _stamp(when: datetime) -> str:
    """Format a datetime the way the Udacity recorder names its files."""
    return when.strftime("%Y_%m_%d_%H_%M_%S_") + f"{when.microsecond // 1000:03d}"


def build_session_frame(
    session: str = "track1data",
    n: int = 200,
    start: datetime = T1_START,
    dt: float = FRAME_DT,
    jitter: float = FRAME_JITTER,
    seed: int = eda_config.SEED,
) -> pd.DataFrame:
    """One clean, contiguous recording session in the real 7-column format.

    steering sits exactly on the 0.05 lattice; throttle and speed vary continuously; speed
    moves smoothly so the plausibility screen has an ordinary baseline to measure against.
    """
    rng = np.random.default_rng(seed)

    # Frame times: even cadence plus small jitter, quantised to the millisecond because the
    # filename only carries milliseconds.
    offsets = np.cumsum(rng.uniform(dt - jitter, dt + jitter, size=n))
    offsets = offsets - offsets[0]
    times = [start + timedelta(milliseconds=round(o * 1000)) for o in offsets]

    # steering: a random walk on the 0.05 lattice, clipped to +/- 1.0 (20 steps).
    level = np.clip(np.cumsum(rng.integers(-1, 2, size=n)), -20, 20)
    steering = np.round(level * 0.05, 10)

    # throttle / speed: continuous, thousands of possible values, smooth motion.
    throttle = np.round(rng.uniform(0.0, 1.0, size=n), 6)
    speed = np.round(10.0 + 5.0 * np.sin(np.arange(n) / 12.0) + rng.normal(0, 0.05, n), 6)

    rows = []
    for i, when in enumerate(times):
        ts = _stamp(when)
        rows.append(
            [
                f"Desktop\\{session}\\IMG\\center_{ts}.jpg",
                f"Desktop\\{session}\\IMG\\left_{ts}.jpg",
                f"Desktop\\{session}\\IMG\\right_{ts}.jpg",
                float(steering[i]),
                float(throttle[i]),
                0.0,  # brake: never pressed in these clips
                float(speed[i]),
            ]
        )
    return pd.DataFrame(rows, columns=eda_config.COLUMN_NAMES)


def as_dataset(df: pd.DataFrame, name: str = "fixture") -> TrackDataset:
    """Wrap a frame as a TrackDataset. Paths are placeholders — nothing reads them."""
    return TrackDataset(
        name=name,
        csv_path=Path("<in-memory fixture>"),
        img_dir=Path("<in-memory fixture>"),
        df=df.reset_index(drop=True).copy(),
    )


# --- Clean baseline --------------------------------------------------------------------
@pytest.fixture
def clean_session() -> TrackDataset:
    """200 contiguous frames, nothing wrong with them. Every check must stay silent."""
    return as_dataset(build_session_frame(), name="clean")


# --- Tampered: row order ---------------------------------------------------------------
@pytest.fixture
def shuffled_session() -> TrackDataset:
    """Same rows, order destroyed. Expected signature: broken time monotonicity."""
    df = build_session_frame()
    shuffled = df.sample(frac=1.0, random_state=eda_config.SEED)
    return as_dataset(shuffled, name="shuffled")


# --- Tampered: excised block -----------------------------------------------------------
EXCISED_START, EXCISED_COUNT = 100, 50


@pytest.fixture
def excised_session() -> TrackDataset:
    """50 consecutive frames cut out — the signature of 'I removed the ugly part'.

    The remaining rows are still in order, so monotonicity survives; only the gap check
    can see this.
    """
    df = build_session_frame()
    keep = df.drop(index=range(EXCISED_START, EXCISED_START + EXCISED_COUNT))
    return as_dataset(keep, name="excised")


# --- Tampered: copied block ------------------------------------------------------------
COPIED_START, COPIED_COUNT = 20, 30


@pytest.fixture
def copied_block_session() -> TrackDataset:
    """A block of rows copied and appended — the signature of inflating dataset size.

    Produces BOTH exact duplicate rows and duplicate image references, because the copied
    rows carry their original filenames.
    """
    df = build_session_frame()
    block = df.iloc[COPIED_START : COPIED_START + COPIED_COUNT]
    return as_dataset(pd.concat([df, block], ignore_index=True), name="copied")


# --- Clean, but looks duplicated -------------------------------------------------------
@pytest.fixture
def repeated_tuples_session() -> TrackDataset:
    """Repeated (steering, throttle, brake, speed) tuples on DISTINCT frames.

    Expected and benign: with a 41-level steering lattice the value space is small, so
    collisions happen. Counting this together with real duplication manufactures a false
    alarm (research A8), so it gets its own fixture and its own assertion.
    """
    df = build_session_frame()
    donor = df.loc[10, ["steering", "throttle", "brake", "speed"]]
    for row in (60, 61, 62):
        df.loc[row, ["steering", "throttle", "brake", "speed"]] = donor.values
    return as_dataset(df, name="repeated_tuples")


# --- Tampered: value off the lattice ----------------------------------------------------
OFF_LATTICE_ROW, OFF_LATTICE_NUDGE = 77, 0.023


@pytest.fixture
def off_lattice_session() -> TrackDataset:
    """One steering value nudged off the 0.05 lattice.

    Signature of someone recomputing values — smoothing, interpolation, augmentation — and
    writing them back. The strongest single piece of evidence these checks can produce.
    """
    df = build_session_frame()
    df.loc[OFF_LATTICE_ROW, "steering"] = (
        float(df.loc[OFF_LATTICE_ROW, "steering"]) + OFF_LATTICE_NUDGE
    )
    return as_dataset(df, name="off_lattice")


# --- Clean, but full of float representation error --------------------------------------
@pytest.fixture
def float_error_session() -> TrackDataset:
    """On-lattice values that do not compare equal to their exact decimal counterparts.

    0.05 is not exactly representable in binary, so accumulating it produces values like
    0.15000000000000002. These are ON the lattice; a check demanding exact equality would
    wrongly report every one of them as tampered.
    """
    df = build_session_frame()
    n = len(df)
    rng = np.random.default_rng(eda_config.SEED)
    steps = rng.integers(-1, 2, size=n)
    # Deliberately NOT rounded: let the representation error accumulate.
    walk = np.cumsum(steps * 0.05)
    walk = np.clip(walk, -1.0, 1.0)
    df["steering"] = walk
    return as_dataset(df, name="float_error")


# --- Tampered: impossible speed change --------------------------------------------------
SPEED_JUMP_ROW, SPEED_JUMP_VALUE = 18, 900.0
SPEED_JUMP_N = 40


@pytest.fixture
def speed_jump_session() -> TrackDataset:
    """One frame carrying a physically impossible speed.

    Kept short (40 frames) on purpose: at this length a standard-deviation rule at the same
    multiplier is blinded by the very outlier it is meant to find, while the MAD rule is not
    (research A7). The test asserts exactly that contrast.
    """
    df = build_session_frame(n=SPEED_JUMP_N)
    df.loc[SPEED_JUMP_ROW, "speed"] = SPEED_JUMP_VALUE
    return as_dataset(df, name="speed_jump")


# --- Clean, but time runs backwards at the junction --------------------------------------
@pytest.fixture
def two_session_junction() -> TrackDataset:
    """Two sessions concatenated, the second recorded EARLIER than the first.

    This is the real combined file, in miniature. Nothing is wrong with it. A timeline check
    that measures across the junction reports a ~-80 minute jump and 'discovers tampering'
    in a perfectly sound dataset — the exact false alarm this feature is most exposed to.
    """
    first = build_session_frame(session="track1data", n=120, start=T1_START, seed=1)
    second = build_session_frame(session="track2data", n=150, start=T2_START, seed=2)
    return as_dataset(pd.concat([first, second], ignore_index=True), name="junction")


# --- Column that has no variation at all -------------------------------------------------
@pytest.fixture
def constant_column_session() -> TrackDataset:
    """brake never leaves 0.0 — exactly what track 1 looks like in the real dataset.

    A column with one distinct value must be reported as a finding, not fed to statistics
    that need variation (FR-013).
    """
    return as_dataset(build_session_frame(), name="constant_brake")
