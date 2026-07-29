"""Orchestrate the full M1 run: figures + report + calibration values (US3).

`run_m1()` ties the pieces together and produces the artifacts the rest of the project
consumes:
- figures  -> results/plots/*.png   (defense-ready)
- report   -> results/eda/m1_report.md    (human-readable)
- numbers  -> results/eda/m1_stats.json   (machine-readable calibration for DESIGN 4.4/4.5)

Writes ONLY under results/. Never touches dataset/ or git (Constitution III/VII).
Deterministic under config.SEED (Constitution VI).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import matplotlib

matplotlib.use("Agg")  # headless: save figures, never open a window
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as sp_stats

from . import config
from .fingerprint import column_fingerprints
from .loader import check_integrity, load_track
from .stats import abs_delta_steering, describe, fit_steering, steering_interior


@dataclass
class CalibrationOutput:
    """The concrete numbers M1 hands to the Unity milestone (M2)."""

    steering_range_raw: tuple[float, float]      # observed min..max -> DESIGN 4.4
    steering_range_robust: tuple[float, float]   # P1..P99 (recommended action map) -> 4.4
    delta_steering_threshold: float              # P95 of |delta steering| -> DESIGN 4.5
    speed_range: tuple[float, float]             # min..P99 -> environment tuning
    steering_zero_pct: float                     # % exact-zero steering (straight driving)
    brake_zero_pct: float                        # % zero brake (how "dead" the column is)
    brake_is_dead: bool                          # True if brake is essentially unused


def _fig_fingerprint(fps, path):
    labels = [fp.inferred_identity for fp in fps]
    pct_neg = [fp.pct_negative for fp in fps]
    pct_zero = [fp.pct_zero for fp in fps]
    maxes = [fp.maximum for fp in fps]
    x = np.arange(len(labels))
    w = 0.38
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 4.5))
    axL.bar(x - w / 2, pct_neg, w, label="% negativnih", color="#c0392b")
    axL.bar(x + w / 2, pct_zero, w, label="% nula", color="#2c7fb8")
    axL.set_xticks(x); axL.set_xticklabels(labels); axL.set_ylabel("procenat (%)")
    axL.set_title("Otisak kolona: negativni / nula"); axL.legend(); axL.grid(True)
    axR.bar(x, maxes, color="#27ae60")
    axR.set_xticks(x); axR.set_xticklabels(labels); axR.set_ylabel("maksimum")
    axR.set_title("Raspon (max)"); axR.grid(True)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def _fig_distributions(steering, speed, abs_delta, p95, path):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    axes[0].hist(steering, bins=60, color="#2c7fb8")
    axes[0].set_title("steering"); axes[0].set_xlabel("ugao volana"); axes[0].grid(True)
    axes[1].hist(speed, bins=60, color="#27ae60")
    axes[1].set_title("speed"); axes[1].set_xlabel("brzina"); axes[1].grid(True)
    axes[2].hist(abs_delta, bins=60, color="#c0392b")
    axes[2].axvline(p95, color="black", linestyle="--", label=f"P95={p95:.3f}")
    axes[2].set_yscale("log"); axes[2].set_title("|delta steering|")
    axes[2].set_xlabel("|promjena volana|"); axes[2].legend(); axes[2].grid(True)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def _fig_fit(steering, res, path):
    body = steering_interior(steering)  # continuous interior only (no 0, no +/-1 spikes)
    xg = np.linspace(-1, 1, 400)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(body, bins=60, density=True, alpha=0.5, color="#95a5a6", label="interior (bez 0, +-1)")
    colors = {"norm": "#2c7fb8", "laplace": "#c0392b", "uniform": "#27ae60"}
    for name in config.STEERING_FIT_CANDIDATES:
        dist = getattr(sp_stats, name)
        params = dist.fit(body)
        lw = 3 if name == res.dist_name else 1.5
        tag = " (AIC)" if name == res.dist_name else ""
        ax.plot(xg, dist.pdf(xg, *params), color=colors[name], lw=lw, label=name + tag)
    decision = "ODBACI" if res.reject_null else "PRIHVATI"
    ax.set_title(f"steering fit  |  chi2={res.chi2_stat:.0f} vs krit={res.chi2_critical:.0f} -> {decision}")
    ax.set_xlabel("ugao volana"); ax.set_ylabel("gustoća"); ax.legend(); ax.grid(True)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def run_m1(primary: str = "combined") -> CalibrationOutput:
    """Run the full M1 analysis, save artifacts, and return the calibration values."""
    config.PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    config.EDA_OUT_DIR.mkdir(parents=True, exist_ok=True)

    ds = load_track(primary)
    t1, t2 = load_track("track1"), load_track("track2")

    integrity = {name: check_integrity(load_track(name)) for name in ("track1", "track2", "combined")}
    fps = column_fingerprints(ds)

    steering_desc = describe(ds.df["steering"], "steering")
    speed_desc = describe(ds.df["speed"], "speed")
    abs_delta = abs_delta_steering([t1, t2])
    delta_desc = describe(abs_delta, "|delta steering|")

    fit = fit_steering(ds.df["steering"])
    p95_delta = float(np.percentile(abs_delta, config.DELTA_STEERING_PERCENTILE))

    lo_pct, hi_pct = config.STEERING_RANGE_PERCENTILES
    brake_zero_pct = next(fp.pct_zero for fp in fps if fp.inferred_identity == "brake")

    calib = CalibrationOutput(
        steering_range_raw=(steering_desc.minimum, steering_desc.maximum),
        steering_range_robust=(
            float(np.percentile(ds.df["steering"], lo_pct)),
            float(np.percentile(ds.df["steering"], hi_pct)),
        ),
        delta_steering_threshold=p95_delta,
        speed_range=(speed_desc.minimum, speed_desc.percentiles[99]),
        steering_zero_pct=fit.zero_mass * 100.0,
        brake_zero_pct=brake_zero_pct,
        brake_is_dead=brake_zero_pct > 99.0,
    )

    # --- figures ---
    _fig_fingerprint(fps, config.PLOTS_DIR / "column_fingerprint.png")
    _fig_distributions(ds.df["steering"], ds.df["speed"], abs_delta, p95_delta,
                       config.PLOTS_DIR / "distributions.png")
    _fig_fit(ds.df["steering"], fit, config.PLOTS_DIR / "steering_fit.png")

    # --- machine-readable calibration ---
    (config.EDA_OUT_DIR / "m1_stats.json").write_text(
        json.dumps(asdict(calib), indent=2), encoding="utf-8"
    )

    # --- human-readable report ---
    report = _render_report(integrity, fps, steering_desc, speed_desc, delta_desc, fit, calib)
    (config.EDA_OUT_DIR / "m1_report.md").write_text(report, encoding="utf-8")

    return calib


def _render_report(integrity, fps, steering, speed, delta, fit, calib) -> str:
    lines = ["# M1 - Statistički izvještaj (auto-generisan)", ""]
    lines.append("## Integritet")
    for rep in integrity.values():
        lines.append(f"- {rep.summary()}")
    lines.append("")
    lines.append("## Identitet kolona (iz statistike)")
    for fp in fps:
        lines.append(f"- kol {fp.column_index}: {fp.inferred_identity} "
                     f"(min={fp.minimum:.3f}, max={fp.maximum:.3f}, "
                     f"%neg={fp.pct_negative:.1f}, %nula={fp.pct_zero:.1f}) - {fp.evidence}")
    lines.append("")
    lines.append("## Deskriptivna statistika")
    for d in (steering, speed, delta):
        lines.append(f"- **{d.variable}**: n={d.n:,} mean={d.mean:.4f} disperzija={d.variance:.4f} "
                     f"std={d.std:.4f} min={d.minimum:.3f} max={d.maximum:.3f} "
                     f"P95={d.percentiles[95]:.3f} P99={d.percentiles[99]:.3f}")
    lines.append("")
    lines.append("## Fit steeringa (kontinualni interior)")
    lines.append(f"- tačkaste mase: 0 (pravo)={fit.zero_mass*100:.1f}%, "
                 f"-1 (puni lijevo)={fit.sat_neg_mass*100:.1f}%, "
                 f"+1 (puni desno)={fit.sat_pos_mass*100:.1f}%, "
                 f"interior={fit.interior_mass*100:.1f}%")
    lines.append(f"- AIC (interior): " + ", ".join(f"{k}={v:.0f}" for k, v in fit.aic_ranking.items()))
    lines.append(f"- pobjednik: {fit.dist_name}, params={tuple(round(p,4) for p in fit.params)}")
    lines.append(f"- χ²={fit.chi2_stat:.1f} dof={fit.dof} kritično={fit.chi2_critical:.1f} "
                 f"p={fit.chi2_pvalue:.3g} → {'ODBACI' if fit.reject_null else 'PRIHVATI'} (α={fit.alpha})")
    lines.append(f"- KS: D={fit.ks_stat:.4f} p={fit.ks_pvalue:.3g}")
    lines.append("")
    lines.append("## Kalibracija za Unity (DESIGN §4.4/§4.5)")
    lines.append(f"- steering raspon (sirovi): {calib.steering_range_raw}")
    lines.append(f"- steering raspon (robustan P1–P99): "
                 f"({calib.steering_range_robust[0]:.3f}, {calib.steering_range_robust[1]:.3f})")
    lines.append(f"- prag |Δsteering| (P95): {calib.delta_steering_threshold:.3f}")
    lines.append(f"- brzina raspon (min–P99): "
                 f"({calib.speed_range[0]:.2f}, {calib.speed_range[1]:.2f})")
    lines.append(f"- brake: {calib.brake_zero_pct:.1f}% nula "
                 f"({'mrtva' if calib.brake_is_dead else 'rijetko aktivna'})")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out = run_m1()
    print("M1 gotov. Kalibracija:")
    print(json.dumps(asdict(out), indent=2))
