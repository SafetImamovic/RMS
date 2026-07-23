# Quickstart: Run M1 Dataset EDA

Prerequisites: dataset already unzipped under `dataset/` (git-ignored), Python 3.10.

```powershell
# 1. Python environment (from repo root)
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python/requirements.txt

# 2. Sanity: dataset present?
#    Expect: dataset/dataset/dataset/driving_log.csv  and  .../IMG/ with images
Get-ChildItem dataset -Recurse -Filter driving_log.csv | Select-Object FullName

# 3. Run the full M1 analysis (produces figures + report + calibration JSON)
python -m python.eda.report        # runs run_m1(primary="combined")

# 4. Or open the narrative notebook
jupyter notebook python/notebooks/01_dataset_analysis.ipynb

# 5. Tests
pytest python/tests -q
```

## Outputs to expect

| Path | What |
|------|------|
| `results/plots/steering_hist.png` | steering histogram + fitted curve (zero spike marked) |
| `results/plots/speed_hist.png` | speed histogram |
| `results/plots/delta_steering_hist.png` | \|Δsteering\| histogram with P95 line |
| `results/plots/steering_track1_vs_track2.png` | per-track steering comparison |
| `results/eda/m1_report.md` | human-readable statistical report |
| `results/eda/m1_stats.json` | machine-readable calibration values (feed DESIGN §4.4/§4.5) |

## Definition of done (M1 gate)

- Integrity check passes on all three sources (`rows × 3 == images`).
- Column identities confirmed from fingerprints (steering/throttle/brake/speed).
- Descriptive stats + steering χ² GoF (+ KS) reported; figures saved.
- `m1_stats.json` produced; DESIGN §4.4/§4.5 updated with data-derived values.
- `pytest` green; re-run reproduces identical numbers under SEED=42.
