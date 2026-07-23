"""Load and validate the Udacity driving_log dataset (M1 foundational layer).

Three steps, each a separate function so the notebook can show them one at a time:
1. load_track       -> parse the headerless CSV into named columns
2. resolve_image_paths -> turn the recorder's Windows paths into local file paths
3. check_integrity  -> confirm rows x 3 == images, and count any rows whose images are missing

None of these decode image pixels (that is BC / M4). They are string + filesystem-metadata
work only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config


@dataclass
class TrackDataset:
    """A loaded track: its rows plus where its images live."""

    name: str
    csv_path: Path
    img_dir: Path
    df: pd.DataFrame
    # Filled in by resolve_image_paths():
    resolved: bool = False


@dataclass
class IntegrityReport:
    """Result of check_integrity() — plain data, no side effects."""

    name: str
    row_count: int
    image_count: int
    expected_image_count: int  # row_count * 3
    integrity_ok: bool  # image_count == expected_image_count
    unresolved_rows: int  # rows where >=1 of the 3 images is missing on disk
    sample_checked: int  # how many rows were sampled for the existence check
    sample_unresolved: int  # unresolved within the sample

    def summary(self) -> str:
        ok = "OK" if self.integrity_ok else "MISMATCH"
        return (
            f"[{self.name}] rows={self.row_count:,} images={self.image_count:,} "
            f"expected={self.expected_image_count:,} -> {ok}; "
            f"unresolved_rows={self.unresolved_rows:,} "
            f"(sample {self.sample_unresolved}/{self.sample_checked})"
        )


def _basename(path_str: str) -> str:
    """Return just the file name from a path that may use Windows '\\' or POSIX '/'.

    The CSV stores absolute paths from the recorder's machine, e.g.
    'Desktop\\track1data\\IMG\\center_....jpg'. We only want 'center_....jpg'.
    """
    # Normalise both separators, then take the last component.
    return path_str.replace("\\", "/").rsplit("/", 1)[-1].strip()


def load_track(name: str) -> TrackDataset:
    """Load a track ('track1' | 'track2' | 'combined') into a TrackDataset.

    Raises ValueError if the CSV does not have exactly 7 columns (format guard, FR-002),
    so a malformed file fails loudly instead of silently mis-labelling columns.
    """
    if name not in config.TRACK_PATHS:
        raise ValueError(f"Unknown track '{name}'. Options: {list(config.TRACK_PATHS)}")

    paths = config.TRACK_PATHS[name]
    if not paths.csv_path.exists():
        raise FileNotFoundError(
            f"driving_log.csv not found for '{name}': {paths.csv_path}"
        )

    # header=None because the file is headerless; names gives our column labels.
    df = pd.read_csv(paths.csv_path, header=None)

    if df.shape[1] != len(config.COLUMN_NAMES):
        raise ValueError(
            f"Expected {len(config.COLUMN_NAMES)} columns in {paths.csv_path}, "
            f"got {df.shape[1]}. The dataset format may differ from the Udacity standard."
        )
    df.columns = config.COLUMN_NAMES

    # Coerce numeric columns to float (handles scientific notation like 1.058134E-05).
    for col in config.NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="raise")

    return TrackDataset(
        name=name, csv_path=paths.csv_path, img_dir=paths.img_dir, df=df
    )


def resolve_image_paths(ds: TrackDataset) -> TrackDataset:
    """Add basename columns (center_file/left_file/right_file) re-rooted onto img_dir.

    String-only: it does NOT open the images. After this, ds.df has three extra columns
    holding just the file names, which pair with ds.img_dir to form real local paths.
    """
    for cam in ("center", "left", "right"):
        ds.df[f"{cam}_file"] = ds.df[cam].map(_basename)
    ds.resolved = True
    return ds


def check_integrity(ds: TrackDataset) -> IntegrityReport:
    """Verify rows x 3 == image files, and count rows with missing images. No writes.

    Uses one directory listing (a set of file names) and set-membership tests, so it is
    fast even for ~194k images — no per-file stat() call.
    """
    if not ds.resolved:
        _ = resolve_image_paths(ds)

    row_count = len(ds.df)

    # One listing of the IMG/ folder; membership tests against this set are O(1).
    # Count only .jpg files — OS junk like Thumbs.db must not inflate the image count.
    existing: set[str] = (
        {f for f in os.listdir(ds.img_dir) if f.lower().endswith(".jpg")}
        if ds.img_dir.exists()
        else set()
    )
    image_count = len(existing)

    cam_files = ds.df[["center_file", "left_file", "right_file"]]

    # A row is "resolved" only if all three of its images exist.
    def row_missing(row) -> bool:
        return any(fname not in existing for fname in row)

    unresolved_mask = cam_files.apply(row_missing, axis=1)
    unresolved_rows = int(unresolved_mask.sum())

    # Deterministic sample (SEED) for an explicit spot-check figure in the notebook.
    n_sample = min(config.IMAGE_CHECK_SAMPLE_ROWS, row_count)
    sample = (
        cam_files.sample(n=n_sample, random_state=config.SEED)
        if n_sample
        else cam_files.iloc[:0]
    )
    sample_unresolved = int(sample.apply(row_missing, axis=1).sum())

    return IntegrityReport(
        name=ds.name,
        row_count=row_count,
        image_count=image_count,
        expected_image_count=row_count * 3,
        integrity_ok=(image_count == row_count * 3),
        unresolved_rows=unresolved_rows,
        sample_checked=n_sample,
        sample_unresolved=sample_unresolved,
    )
