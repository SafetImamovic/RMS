"""Descriptive statistics, delta-steering, and distribution fitting (US2).

Everything the course cares about, as small tested functions:
- describe():            sample size, mean, variance/std, min/max, percentiles
- abs_delta_steering():  |steering change between consecutive rows|, PER TRACK (never across
                         the track1->track2 junction of the combined file)
- fit_steering():        fit candidate distributions to the steering "body", rank by AIC,
                         judge the winner with a chi-square goodness-of-fit test + KS check

Why "body": ~60-80% of steering values are exactly 0 (straight driving). No single smooth
curve models that spike, so we report the zero fraction separately (zero_mass) and fit the
SHAPE of the actual (non-zero) steering movements. This is the honest, defensible framing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats as sp_stats

from . import config
from .loader import TrackDataset


# ---------------------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------------------
@dataclass
class DistributionSummary:
    variable: str
    n: int
    mean: float
    std: float
    variance: float
    minimum: float
    maximum: float
    percentiles: dict[float, float]  # e.g. {1: .., 5: .., 50: .., 95: .., 99: ..}


# The percentiles we report for every variable (course "statistički parametri uzorka").
_PERCENTILES = [1, 5, 50, 95, 99]


def describe(series, variable: str) -> DistributionSummary:
    """Descriptive statistics for one variable (matematičko očekivanje, disperzija, ...)."""
    arr = np.asarray(series, dtype=float)
    return DistributionSummary(
        variable=variable,
        n=int(arr.size),
        mean=float(arr.mean()),
        std=float(arr.std(ddof=1)),          # sample std (ddof=1) - unbiased
        variance=float(arr.var(ddof=1)),     # sample variance = disperzija
        minimum=float(arr.min()),
        maximum=float(arr.max()),
        percentiles={p: float(np.percentile(arr, p)) for p in _PERCENTILES},
    )


# ---------------------------------------------------------------------------------------
# Delta-steering (smoothness signal)
# ---------------------------------------------------------------------------------------
def track_delta_steering(ds: TrackDataset) -> np.ndarray:
    """Signed steering change between consecutive rows WITHIN one contiguous track."""
    return np.diff(ds.df["steering"].to_numpy(dtype=float))


def abs_delta_steering(datasets: list[TrackDataset]) -> np.ndarray:
    """|delta steering| across several tracks, each differenced separately then concatenated.

    Passing [track1, track2] instead of the combined file avoids inventing a fake huge jump
    at the seam where the two recordings were glued together (research R4).
    """
    parts = [np.abs(track_delta_steering(ds)) for ds in datasets]
    return np.concatenate(parts) if parts else np.array([])


# ---------------------------------------------------------------------------------------
# Distribution fitting + goodness-of-fit
# ---------------------------------------------------------------------------------------
@dataclass
class FitResult:
    dist_name: str
    params: tuple
    aic: float
    chi2_stat: float
    dof: int
    chi2_critical: float
    chi2_pvalue: float
    alpha: float
    reject_null: bool           # True => the distribution does NOT fit (chi2 > critical)
    ks_stat: float
    ks_pvalue: float
    zero_mass: float            # fraction of the ORIGINAL data that was exactly 0 (straight)
    sat_neg_mass: float         # fraction exactly -1 (full left lock)
    sat_pos_mass: float         # fraction exactly +1 (full right lock)
    interior_mass: float        # fraction that is the genuine continuous body (the fitted part)
    aic_ranking: dict = field(default_factory=dict)  # dist_name -> AIC, for the notebook table


def steering_interior(series) -> np.ndarray:
    """The genuine continuous steering: drop the discrete spikes at 0 and +/-1.

    Steering is really a mixture: point masses at 0 (straight), -1 and +1 (full lock), plus a
    continuous body in between. Only the in-between part can be described by a smooth curve, so
    that is what we fit. The spikes are reported as separate probabilities.
    """
    arr = np.asarray(series, dtype=float)
    return arr[(arr != 0.0) & (arr != -1.0) & (arr != 1.0)]


def _aic(log_likelihood: float, k_params: int) -> float:
    """Akaike Information Criterion. Lower = better; penalises extra parameters."""
    return 2 * k_params - 2 * log_likelihood


def _chi2_goodness_of_fit(data: np.ndarray, dist, params: tuple, k_params: int,
                          alpha: float, n_bins: int = 30) -> tuple[float, int, float, float]:
    """Chi-square GoF with the 'expected >= 5 per bin' rule (merge sparse bins).

    Returns (chi2_stat, dof, critical_value, p_value).
    """
    n = data.size
    # Equal-width bins across the data range; outer edges pushed to +/- inf so the fitted
    # distribution's tail probability is fully accounted for.
    edges = np.linspace(data.min(), data.max(), n_bins + 1)
    edges = edges.copy()
    edges[0], edges[-1] = -np.inf, np.inf

    observed, _ = np.histogram(data, bins=edges)
    cdf = dist.cdf(edges, *params)
    expected = n * np.diff(cdf)

    # Merge adjacent bins left-to-right until every expected count >= 5 (validity rule).
    obs_m: list[float] = []
    exp_m: list[float] = []
    acc_o = acc_e = 0.0
    for o, e in zip(observed, expected):
        acc_o += o
        acc_e += e
        if acc_e >= config.CHI2_MIN_EXPECTED_PER_BIN:
            obs_m.append(acc_o)
            exp_m.append(acc_e)
            acc_o = acc_e = 0.0
    # Fold any leftover into the last bin.
    if acc_e > 0:
        if exp_m:
            obs_m[-1] += acc_o
            exp_m[-1] += acc_e
        else:
            obs_m.append(acc_o)
            exp_m.append(acc_e)

    obs_arr = np.array(obs_m)
    exp_arr = np.array(exp_m)
    chi2_stat = float(np.sum((obs_arr - exp_arr) ** 2 / exp_arr))
    dof = max(len(exp_arr) - 1 - k_params, 1)
    critical = float(sp_stats.chi2.ppf(1 - alpha, dof))
    p_value = float(sp_stats.chi2.sf(chi2_stat, dof))
    return chi2_stat, dof, critical, p_value


def fit_steering(series, alpha: float = config.ALPHA) -> FitResult:
    """Fit candidate distributions to the NON-ZERO steering body, rank by AIC, test the winner.

    Steps (all reproducible, no hidden randomness):
    1. Split off exact zeros -> zero_mass (the straight-driving fraction).
    2. Fit each candidate (norm/laplace/uniform) to the non-zero body via MLE.
    3. Rank by AIC (penalised likelihood); pick the best.
    4. Judge the best with a chi-square goodness-of-fit test (+ KS cross-check).
    """
    full = np.asarray(series, dtype=float)
    n = full.size
    zero_mass = float(np.mean(full == 0.0))
    sat_neg_mass = float(np.mean(full == -1.0))
    sat_pos_mass = float(np.mean(full == 1.0))
    body = steering_interior(full)  # drop 0 and +/-1 spikes; fit only the continuous interior

    ranking: dict[str, float] = {}
    fitted: dict[str, tuple] = {}
    for name in config.STEERING_FIT_CANDIDATES:
        dist = getattr(sp_stats, name)
        params = dist.fit(body)
        log_lik = float(np.sum(dist.logpdf(body, *params)))
        ranking[name] = _aic(log_lik, k_params=len(params))
        fitted[name] = params

    # Winner = lowest AIC.
    best_name = min(ranking, key=ranking.get)
    best_dist = getattr(sp_stats, best_name)
    best_params = fitted[best_name]
    k = len(best_params)

    chi2_stat, dof, critical, chi2_p = _chi2_goodness_of_fit(
        body, best_dist, best_params, k_params=k, alpha=alpha
    )
    ks_stat, ks_p = sp_stats.kstest(body, best_name, args=best_params)

    return FitResult(
        dist_name=best_name,
        params=best_params,
        aic=ranking[best_name],
        chi2_stat=chi2_stat,
        dof=dof,
        chi2_critical=critical,
        chi2_pvalue=chi2_p,
        alpha=alpha,
        reject_null=(chi2_stat > critical),
        ks_stat=float(ks_stat),
        ks_pvalue=float(ks_p),
        zero_mass=zero_mass,
        sat_neg_mass=sat_neg_mass,
        sat_pos_mass=sat_pos_mass,
        interior_mass=float(body.size / n),
        aic_ranking=ranking,
    )


def relative_frequency_histogram(series, bins: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Relative-frequency histogram (counts sum to 1) - counts, edges."""
    arr = np.asarray(series, dtype=float)
    counts, edges = np.histogram(arr, bins=bins, density=False)
    rel = counts / counts.sum()
    return rel, edges
