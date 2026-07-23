"""RMS M1 dataset EDA package.

Reusable, tested building blocks for the M1 exploratory analysis of the Udacity
self-driving-car simulator dataset. The notebook `python/notebooks/01_dataset_analysis.ipynb`
is the human-facing narrative; this package holds the logic so every number is reproducible.

Modules:
- config:      constants (paths, seed, alpha, column names)
- loader:      load headerless driving_log.csv, resolve image paths, integrity check
- fingerprint: prove each numeric column's identity from its statistics
- stats:       descriptive stats, delta-steering, distribution fit + chi-square + KS
- report:      orchestrate the full run -> figures + report + calibration JSON
"""
