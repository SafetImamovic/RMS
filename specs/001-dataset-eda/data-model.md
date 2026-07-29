# Phase 1 Data Model: Dataset EDA (M1)

Conceptual entities for the M1 analysis. This is a read-only analysis feature - there is no
persisted schema beyond the input CSV and the output report; these entities describe the
in-memory and on-disk shapes the code works with.

## DrivingLogRecord

One timestamped sample from a track recording.

| Field | Type | Notes |
|-------|------|-------|
| `center` | str (path) | center-camera image reference; Windows-absolute in raw CSV |
| `left` | str (path) | left-camera image reference |
| `right` | str (path) | right-camera image reference |
| `steering` | float | normalized ~[-1, 1]; negative = left; ~79% exactly 0 |
| `throttle` | float | [0, 1] |
| `brake` | float | [0, 1]; constant 0 on track1 (dead column candidate) |
| `speed` | float | ≥ 0; up to ~22 on track1 |

- **Derived**: `resolved_center/left/right` - local `Path` after basename + re-root.
- **Derived**: `image_id` - shared filename timestamp tying the three cameras together.
- **Validation**: exactly 7 columns per row; numeric columns parse as float (incl. scientific
  notation like `1.058134E-05`); resolved paths point at existing files (sampled).

## TrackDataset

A loaded track: its records plus its `IMG/` folder.

| Field | Type | Notes |
|-------|------|-------|
| `name` | enum | `track1` \| `track2` \| `combined` |
| `csv_path` | Path | `dataset/<name>/<name>/driving_log.csv` |
| `img_dir` | Path | `dataset/<name>/<name>/IMG/` |
| `records` | DataFrame | rows = DrivingLogRecord |
| `row_count` | int | track1 ≈ 10,615; track2 ≈ 21,828; combined ≈ 32,443 |
| `image_count` | int | files in `img_dir` |
| `integrity_ok` | bool | `row_count * 3 == image_count` |
| `unresolved_rows` | int | rows whose images did not resolve on disk |

- **Relationship**: `combined` = track1 records ⧺ track2 records (documented, not re-derived).
- **State**: `raw` → `parsed` (columns named) → `resolved` (paths re-rooted) → `validated`
  (integrity + sample existence checked). Analysis consumes only `validated`.

## ColumnFingerprint

Per numeric column, the statistical evidence that assigns its identity (US1).

| Field | Type | Notes |
|-------|------|-------|
| `column_index` | int | 4–7 (1-based, matching DESIGN §6.1) |
| `min`, `max` | float | |
| `pct_negative` | float | only steering is > 0 here |
| `pct_zero` | float | brake ≈ 100%, steering ≈ 79% |
| `mean` | float | |
| `inferred_identity` | enum | steering \| throttle \| brake \| speed |
| `evidence` | str | one-line rationale (e.g. "only negative-capable column → steering") |

## DistributionSummary

For a variable (steering, speed, Δsteering).

| Field | Type | Notes |
|-------|------|-------|
| `variable` | enum | steering \| speed \| delta_steering |
| `n` | int | sample size |
| `mean`, `std`, `variance` | float | descriptive stats (matematičko očekivanje, disperzija) |
| `min`, `max` | float | |
| `percentiles` | dict | P1, P5, P50, P95, P99 |
| `histogram` | (counts, edges) | relative-frequency histogram |
| `fit` | FitResult \| None | present for steering; None for others |
| `figure_path` | Path | saved histogram (+ fitted curve overlay) |

## FitResult

Goodness-of-fit outcome for a fitted theoretical distribution.

| Field | Type | Notes |
|-------|------|-------|
| `dist_name` | str | e.g. `laplace`, `norm` |
| `params` | tuple | fitted parameters |
| `chi2_stat` | float | computed χ² |
| `dof` | int | bins − 1 − #params |
| `chi2_critical` | float | `chi2.ppf(1−α, dof)` |
| `alpha` | float | 0.05 default |
| `reject_null` | bool | χ²_stat > χ²_critical |
| `ks_stat`, `ks_pvalue` | float | KS cross-check |
| `zero_mass` | float | probability mass at exactly 0 (zero-inflation note) |

## CalibrationOutput

The values M1 hands to M2, written to `results/eda/m1_stats.json` and into `DESIGN.md`.

| Field | Type | Feeds |
|-------|------|-------|
| `steering_range_raw` | (min, max) | §4.4 |
| `steering_range_robust` | (P1, P99) | §4.4 (recommended action map) |
| `delta_steering_threshold` | float | §4.5 (P95 of \|Δsteering\|) |
| `speed_range` | (min, P99) | environment tuning |
| `brake_is_dead` | bool | analysis-scope note |
