# Contract: `python/eda` package public API (M1)

The interface the notebook (and pytest) depend on. Signatures are the contract; internals may
change as long as these hold. All functions are pure w.r.t. the filesystem except where noted
(they read the dataset; only `report.*` writes, and only under `results/`).

## config.py (constants)

```python
SEED: int = 42
ALPHA: float = 0.05
COLUMN_NAMES: list[str] = ["center", "left", "right", "steering", "throttle", "brake", "speed"]
DATASET_ROOT: Path                      # repo_root / "dataset"
TRACK_PATHS: dict[str, TrackPaths]      # "track1"|"track2"|"combined" -> (csv_path, img_dir)
PLOTS_DIR: Path                         # repo_root / "results" / "plots"
EDA_OUT_DIR: Path                       # repo_root / "results" / "eda"
```

## loader.py

```python
def load_track(name: str) -> TrackDataset:
    """Load 'track1'|'track2'|'combined': parse headerless CSV into COLUMN_NAMES,
    coerce numeric columns to float. Raises ValueError if column count != 7."""

def resolve_image_paths(ds: TrackDataset) -> TrackDataset:
    """Add resolved center/left/right Path columns via basename + re-root onto img_dir."""

def check_integrity(ds: TrackDataset) -> IntegrityReport:
    """Return row_count, image_count, integrity_ok (rows*3 == images),
    and unresolved_rows (sampled + full count). Never raises on data issues - reports them."""
```

**Contract guarantees**
- `load_track` never silently drops rows; malformed rows surface as a raised error or a
  reported count, never a quiet skip.
- `resolve_image_paths` is path-string only - it does not open image files.
- `check_integrity` is side-effect free (no writes).

## fingerprint.py

```python
def column_fingerprints(ds: TrackDataset) -> list[ColumnFingerprint]:
    """For numeric columns 4-7: min, max, %negative, %zero, mean, inferred_identity, evidence.
    Identity inference is rule-based (only-negative -> steering, etc.) and independent of
    COLUMN_NAMES, so it can CONFIRM the assumed order rather than assume it."""
```

## stats.py

```python
def describe(series) -> DistributionSummary:      # n, mean, std, variance, min, max, percentiles
def delta_steering(ds: TrackDataset) -> Series:   # per-track consecutive diff; no cross-track junction
def fit_steering(series, alpha: float = ALPHA) -> FitResult:
    """Fit candidate dist(s), run χ² GoF (expected>=5 per bin, dof = bins-1-#params),
    KS cross-check, and zero-mass. Returns FitResult with reject_null decision."""
def relative_frequency_histogram(series, bins) -> tuple[counts, edges]
```

**Contract guarantees**
- `delta_steering` computed per contiguous track, never across the combined junction (R4).
- `fit_steering` enforces the expected-count≥5 binning rule; dof accounts for fitted params.
- All stats are deterministic given the input series (no hidden randomness).

## report.py

```python
def run_m1(primary: str = "combined") -> CalibrationOutput:
    """Orchestrate the full M1 analysis: load+resolve+integrity for primary and per-track,
    fingerprints, descriptive stats + fit, save histograms to PLOTS_DIR, write
    m1_report.md + m1_stats.json to EDA_OUT_DIR, return CalibrationOutput."""
```

**Contract guarantees**
- Writes only under `results/` - never touches `dataset/`, never mutates git.
- Given the fixed SEED, two runs produce identical `m1_stats.json` (SC-006).
- `m1_stats.json` contains exactly the CalibrationOutput fields feeding DESIGN §4.4/§4.5.
