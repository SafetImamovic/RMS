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

The table below is the **verified** output of the implemented run (2026-07-29), not a
prediction. Three rows differ from what the exploratory probe originally suggested; each is
marked and explained underneath.

| Check | Expected outcome |
|---|---|
| Timeline monotonic | yes, both sessions, zero violations |
| Unparseable timestamps | 0 — no row is silently dropped |
| Frame interval | track1 0.0710 s (14.08 fps), track2 0.0700 s (14.29 fps) |
| Gaps above threshold | **track1: 1** (0.474 s, on the last row); track2: 0 ⚠️ *revised* |
| Duplicate rows / image refs | 0 / 0 |
| Duplicate measurement tuples | 12 on track1, 4 on track2 — expected, benign |
| steering granularity | **discrete**, lattice spacing 0.05, support −1.0…+1.0 (41 levels) |
| steering max residual | 2.0e-07 on both tracks ⚠️ *new* |
| steering off-lattice values | none |
| steering unobserved support | `+0.95` on track1; none on track2 |
| throttle / speed granularity | continuous (thousands of distinct values) |
| track1 brake | **constant** (single value 0.0) — reported as a finding, not a statistic |
| track2 brake | continuous, 1,708 distinct values |
| Acceleration outliers | 796 (7.5 %) track1, 982 (4.5 %) track2 ⚠️ *new* |
| T1 uniform GoF | reject decisively on both (χ² ≈ 264,577 / 198,115, dof 40, crit 55.76) |
| T2 symmetry | **reject on both** — track1 ratio 5.375 (material), track2 ratio 1.052 (negligible) ⚠️ *revised* |
| T3 homogeneity | reject (χ² ≈ 4,300, dof 40) — confirms two genuinely different recordings |
| Verdicts | 12 findings, **0 unexplained** |
| `calibration_unchanged` | `true` — P95 \|Δsteering\| = 0.5500001, P1–P99 = (−1, 1), both identical to M1 |

**If any row disagrees, stop.** Either the dataset on disk is not the one this feature was
written against, or a check is wrong. Both are worth knowing before the numbers go into a
report.

### The three revisions, and why

1. **`LATTICE_ATOL` widened 1e-8 → 1e-6, and `max_residual` added.** The simulator writes every
   steering level with |value| > 0.45 at a systematic offset of up to 2e-7 (`0.5000001`,
   `-0.9500002`), while ±0.7 and ±1.0 are exact. At 1e-8 the check reported **18 sound levels as
   tampered** — the precise false alarm this feature exists to prevent. See research A3.1. The
   largest residual is now always reported so the tolerance cannot become a hiding place.

2. **track1 has one gap, and it is fine.** 0.474 s ≈ 6 lost frames, and it lands on the
   **final row** of the recording with speed and steering continuous across it: a recorder
   shutdown, not an excision. An excision would sit mid-recording and typically coincide with an
   acceleration extreme — the report checks for that coincidence explicitly and finds none.

3. **T2 rejects on track2 as well, and that is not a problem.** With n = 21,828 a χ² test
   detects a left/right ratio of 1.052. Statistical significance is not practical significance;
   the verdict layer separates the two, classifying track1's 5.375 as material (with an M4
   consequence and mitigation) and track2's 1.052 as negligible.

The acceleration outlier rate (7.5 % / 4.5 %) is high because the implied-acceleration
distribution has a tight core and broad tails — a 5×MAD band lands near P97 by construction.
The multiplier is deliberately **not** tuned to produce a prettier number; that would be
fitting the threshold to the desired answer. The rate is reported and explained instead.

## Definition of done

- Every row of the table above is reported, including the ones that come out clean.
- Every finding carries H₀, a decision at α, an interpretation, and an explainable/unexplained
  verdict (SC-008).
- Tampered fixtures are detected **and** clean fixtures raise no false alarm (contract test
  table).
- `pytest` green; two runs produce byte-identical JSON.
- M1 `research.md` R1/R2 amended; per-track brake note and the M5 forward note recorded in
  `DESIGN.md`.
