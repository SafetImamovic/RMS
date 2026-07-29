# Contract: `python/eda` authenticity API

Extends the M1 contract (`specs/001-dataset-eda/contracts/eda-api.md`), which remains binding
and unmodified. Signatures below are the contract; internals may change as long as these hold.

All functions read the dataset and are otherwise pure. **Only `run_authenticity` writes**, and
only under `results/`.

## config.py (additions only)

Existing constants keep their current values. This feature adds:

```python
# Lattice detection (research A3)
LATTICE_ATOL: float = 1e-8          # absolute tolerance; 0.05 is not exactly representable
DISCRETE_MAX_DISTINCT: int = 100    # <= this many distinct values -> candidate discrete column

# Timeline gaps (research A2)
GAP_FACTOR: float = 5.0             # gap <=> dt > GAP_FACTOR * median(dt) within a session

# Plausibility screen (research A7)
ACCEL_MAD_K: float = 5.0            # outlier <=> |a - median| > ACCEL_MAD_K * MAD

# Session segmentation (research A1)
SESSION_PATH_MARKERS: tuple[str, ...] = ("track1data", "track2data")
```

**Guarantee**: no existing constant changes value. `SEED`, `ALPHA`,
`CHI2_MIN_EXPECTED_PER_BIN` are reused as-is, so M1 numbers stay reproducible.

## integrity.py

```python
def split_sessions(ds: TrackDataset) -> list[RecordingSession]:
    """Segment a source into contiguous recording sessions using the image-path prefix.
    track1/track2 yield one session; combined yields two."""

def parse_capture_times(ds: TrackDataset) -> tuple[Series, int]:
    """Extract capture timestamps from center-image filenames.
    Returns (times, n_unparseable). Never silently drops a row."""

def check_timeline(ds: TrackDataset) -> list[TimelineReport]:
    """Per session: monotonicity, order violations, frame-interval summary, gap counts
    at the derived threshold and at the reporting tiers."""

def check_duplicates(ds: TrackDataset) -> DuplicationReport:
    """Exact duplicate rows, duplicate image references, and duplicate measurement
    tuples - counted separately, never summed."""

def profile_granularity(ds: TrackDataset) -> list[GranularityProfile]:
    """Per numeric column: distinct count, discrete/continuous/constant classification,
    lattice spacing and support, unobserved support points, off-lattice values."""

def check_plausibility(ds: TrackDataset) -> list[PlausibilityReport]:
    """Per session: implied acceleration (d speed / dt), robust MAD-based outlier screen."""
```

**Contract guarantees**

- `check_timeline` and `check_plausibility` **never compute across a session boundary**. Given
  the combined source, they return one report per session, never one merged report.
- `parse_capture_times` returns the failure count; a caller cannot mistake "no failures" for
  "failures were dropped".
- `profile_granularity` reports the tolerance it used, and classifies a single-valued column as
  `constant` rather than emitting statistics undefined on it.
- Lattice detection tolerates floating-point representation error; exact equality is never
  required.
- All functions are side-effect free — no writes, no mutation of the input `TrackDataset`.

## authenticity.py

```python
def chi2_uniform_gof(counts, support, alpha: float = ALPHA) -> HypothesisTestResult:
    """T1. H0: steering is uniform over the lattice support.
    Expected rejection. Failing to reject would indicate a uniform RNG produced the column."""

def chi2_symmetry(counts, support, alpha: float = ALPHA) -> HypothesisTestResult:
    """T2. H0: P(+k) == P(-k) for every lattice level k. Per track, never pooled."""

def chi2_homogeneity(counts_a, counts_b, support, alpha: float = ALPHA) -> HypothesisTestResult:
    """T3. H0: both tracks share a common steering distribution over the shared support.
    Failing to reject would indicate one recording duplicated and renamed."""

def classify_findings(...) -> list[Verdict]:
    """Attach explainable/unexplained verdicts, naming the mechanism where explainable
    and recording downstream consequence + mitigation where one exists."""

def run_authenticity(sources: tuple[str, ...] = ("track1", "track2")) -> AuthenticityOutput:
    """Orchestrate: sessions, timeline, duplicates, granularity, plausibility, the three
    tests, verdicts. Save figures to PLOTS_DIR, write authenticity_report.md and
    authenticity_stats.json to EDA_OUT_DIR, return AuthenticityOutput."""
```

**Contract guarantees**

- Every returned `HypothesisTestResult` carries a **non-empty** `null_hypothesis` and
  `interpretation`. A bare statistic is a contract violation.
- `dof` is the value **after** low-expectation pooling, and `n_categories_pooled` records how
  much pooling occurred.
- Pooling merges low-expectation levels symmetrically from the tails inward, so it cannot
  induce the asymmetry that `chi2_symmetry` is measuring.
- A support point observed on one track but not the other is **retained** in the shared support
  for `chi2_homogeneity`, with observed count zero.
- `classify_findings` never returns an `explainable` verdict with an empty `mechanism`.
- `run_authenticity` writes **only** `results/eda/authenticity_report.md`,
  `results/eda/authenticity_stats.json`, and `results/plots/authenticity_*.png`. It never opens
  `m1_report.md` or `m1_stats.json` for writing, and never mutates git.
- Two runs under `SEED=42` produce identical `authenticity_stats.json`.
- `calibration_unchanged` is set from an actual recomputation of the M1 percentiles, not
  assumed.

## Test contract (FR-025)

Each check family requires **both** directions of evidence:

| Family | Must detect | Must NOT false-alarm on |
|---|---|---|
| timeline order | shuffled rows | a clean session |
| timeline gaps | an excised block of consecutive rows | normal frame-interval jitter |
| duplicates | a copied-and-appended block | repeated measurement tuples with distinct images |
| lattice | one value nudged off-lattice | float representation error in on-lattice values |
| plausibility | an injected impossible speed jump | ordinary acceleration |
| session split | — | a synthetic two-session junction (no cross-boundary alarm) |

The right-hand column is not optional. A check that flags a clean dataset as tampered is as
serious a defect as one that misses tampering, and it is the failure mode this feature is most
exposed to — the combined-source time inversion (research A1) is exactly that trap.
