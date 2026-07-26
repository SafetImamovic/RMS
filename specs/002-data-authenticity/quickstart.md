# Quickstart: Run the data authenticity checks

Prerequisites: dataset unzipped under `dataset/` (git-ignored), M1 environment already set up
(`.venv`). **No new dependencies** — if M1 runs, this runs.

```powershell
# From repo root, with the M1 environment active
.venv\Scripts\Activate.ps1

# 1. Run the authenticity battery (both tracks, per session)
python -m python.eda.authenticity     # runs run_authenticity(("track1", "track2"))

# 2. Or read the narrative: notebook section 5
jupyter notebook python/notebooks/01_dataset_analysis.ipynb

# 3. Tests - including the deliberately tampered fixtures
pytest python/tests -q

# 4. Reproducibility check (SC-011): run twice, compare byte-for-byte
python -m python.eda.authenticity
Copy-Item results/eda/authenticity_stats.json $env:TEMP/auth_run1.json
python -m python.eda.authenticity
if ((Get-FileHash results/eda/authenticity_stats.json).Hash -eq (Get-FileHash $env:TEMP/auth_run1.json).Hash) {
    "REPRODUCIBLE"
} else {
    "MISMATCH - investigate before committing"
}
```

> **Note**: `.venv` is the M1 environment (numpy 1.26.4). Do **not** run this from
> `.venv-mlagents` — that environment pins numpy 1.23.5 for ML-Agents and is not the
> environment M1's numbers were produced under. See `ENVIRONMENT.md`.

## Outputs to expect

| Path | What |
|------|------|
| `results/eda/authenticity_report.md` | human-readable report: every check with H₀, result, verdict |
| `results/eda/authenticity_stats.json` | machine-readable `AuthenticityOutput` |
| `results/plots/authenticity_timeline.png` | frame-interval distribution per session, gap threshold marked |
| `results/plots/authenticity_lattice.png` | steering lattice: 41 levels, spacing, unobserved points |
| `results/plots/authenticity_symmetry.png` | left/right level frequencies mirrored, per track |
| `results/plots/authenticity_homogeneity.png` | track1 vs track2 level frequencies overlaid |

**Not written, by design**: `results/eda/m1_report.md` and `results/eda/m1_stats.json` are
M1's reviewed, committed artifacts and are never regenerated (research A9).

## What the results should say

Based on the exploratory probe that motivated this feature, a correct run reports:

| Check | Expected outcome |
|---|---|
| Timeline monotonic | yes, both sessions, zero violations |
| Frame interval | ≈ 0.070–0.071 s → ≈ 14.1–14.3 fps |
| Gaps above threshold | none |
| Duplicate rows / image refs | 0 / 0 |
| Duplicate measurement tuples | small (≈ 12 on track1, ≈ 4 on track2) — expected, benign |
| steering granularity | **discrete**, lattice spacing 0.05, support −1.0…+1.0 (41 levels) |
| steering unobserved support | `+0.95` on track1; none on track2 |
| throttle / speed granularity | continuous (thousands of distinct values) |
| track1 brake | **constant** (single value 0.0) — reported as a finding, not a statistic |
| T1 uniform GoF | reject decisively (good — rules out a uniform RNG) |
| T2 symmetry | reject on track1 (explainable: CCW loop), likely not on track2 |
| T3 homogeneity | reject (good — confirms two genuinely different recordings) |
| Verdicts | ≥ 1 explainable with named mechanism; ≥ 1 carrying a downstream consequence |
| `calibration_unchanged` | `true` — order statistics are unaffected by the discreteness finding |

**If any of the first six rows disagrees with this table, stop.** Either the dataset on disk is
not the one this feature was written against, or a check is wrong. Both are worth knowing before
the numbers go into a report.

## Definition of done

- Every row of the table above is reported, including the ones that come out clean.
- Every finding carries H₀, a decision at α, an interpretation, and an explainable/unexplained
  verdict (SC-008).
- Tampered fixtures are detected **and** clean fixtures raise no false alarm (contract test
  table).
- `pytest` green; two runs produce byte-identical JSON.
- M1 `research.md` R1/R2 amended; per-track brake note and the M5 forward note recorded in
  `DESIGN.md`.
