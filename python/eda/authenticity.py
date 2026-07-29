"""Hypothesis tests, verdicts, and the authenticity report (feature 002, US2 + US3).

The rule this whole module exists to enforce: **no null model, no finding**. A number on its
own proves nothing. Before any check is allowed to raise a concern it has to say what the
data would look like if the concern were unfounded (the null hypothesis, H0), and what it
would look like if the manipulation had happened (the expected signature). Only then does
rejecting or failing to reject mean anything.

Three tests run on the steering column, because steering is the one variable that is
recorded on a lattice and therefore the one where a chi-square test is exactly right —
the categories are the values themselves, so there is no binning choice to argue about.

  T1  uniform goodness-of-fit  — is the column just noise from a random generator?
  T2  symmetry                 — does the driver steer left and right equally?
  T3  homogeneity              — are the two tracks really two different recordings?

For T1 and T3 the interesting direction is FAILING to reject. That is the direction that
would say "this looks generated" or "this looks like one recording copied twice".

Only `run_authenticity` writes anything, and only under results/ (Constitution III/VII).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # headless: save figures, never open a window (same as M1)
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as sp_stats

from . import config
from .integrity import (
    DuplicationReport,
    GranularityProfile,
    PlausibilityReport,
    RecordingSession,
    TimelineReport,
    _session_times,
    check_duplicates,
    check_plausibility,
    check_timeline,
    profile_granularity,
    split_sessions,
)
from .loader import load_track


# =======================================================================================
# Entities
# =======================================================================================
@dataclass(frozen=True)
class HypothesisTestResult:
    """One named test. The shape every statistical claim in this feature must take.

    `dof` is the value AFTER pooling, never the naive k-1, and `interpretation` states what
    the outcome means *for the question of tampering* — not merely whether p < alpha.
    """

    test_id: str
    null_hypothesis: str
    scope: str
    statistic: float
    dof: int
    critical_value: float
    p_value: float
    alpha: float
    reject_null: bool
    n_categories_pooled: int
    interpretation: str


@dataclass(frozen=True)
class Verdict:
    """The classification attached to any finding (FR-015, FR-016, research A6).

    Two rules are enforced in the constructor rather than left to discipline, because both
    are ways a report can look rigorous while saying nothing:

      * `explainable` without a named mechanism is an assertion, not an explanation.
      * a downstream consequence without a mitigation leaves the reader worse off than
        silence — they now know something is wrong and not what to do about it.

    Explainable and harmful are independent. The track 1 left bias is fully explained by the
    track being a one-way loop, and still poisons a behavioural-cloning model.
    """

    finding_id: str
    summary: str
    classification: str  # "explainable" | "unexplained"
    mechanism: str | None = None
    downstream_consequence: str | None = None
    mitigation: str | None = None

    def __post_init__(self) -> None:
        if self.classification not in ("explainable", "unexplained"):
            raise ValueError(
                f"classification must be 'explainable' or 'unexplained', "
                f"got {self.classification!r}"
            )
        if self.classification == "explainable" and not (self.mechanism or "").strip():
            raise ValueError(
                f"verdict {self.finding_id!r} is marked explainable but names no mechanism; "
                "an explanation without a cause is just an assertion (FR-015)"
            )
        if (self.downstream_consequence or "").strip() and not (self.mitigation or "").strip():
            raise ValueError(
                f"verdict {self.finding_id!r} records a downstream consequence but no "
                "mitigation; naming a problem without a remedy is worse than silence (FR-016)"
            )


@dataclass(frozen=True)
class AuthenticityOutput:
    """The machine-readable top-level result (FR-017)."""

    sources: list[str]
    sessions: list[RecordingSession]
    timelines: list[TimelineReport]
    duplications: list[DuplicationReport]
    granularity: dict[str, list[GranularityProfile]]
    plausibility: list[PlausibilityReport]
    tests: list[HypothesisTestResult]
    verdicts: list[Verdict]
    calibration_unchanged: bool
    calibration_note: str
    seed: int = config.SEED
    alpha: float = config.ALPHA
    lattice_tolerance: float = config.LATTICE_ATOL


# =======================================================================================
# T016 — low-expectation pooling
# =======================================================================================
def pool_symmetric(
    observed: np.ndarray,
    expected: np.ndarray,
    min_expected: float = config.CHI2_MIN_EXPECTED_PER_BIN,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Merge low-expectation categories from the tails inward, symmetrically.

    The chi-square approximation stops being trustworthy when a category's expected count
    is tiny, so sparse categories have to be merged. M1's rule (>= 5 expected per bin) is
    kept unchanged.

    What matters here is the *direction* of merging. Levels are merged in mirrored pairs,
    outermost first, so the same depth is removed from each tail. Merging one tail deeper
    than the other would introduce an asymmetry that the symmetry test would then dutifully
    detect — the test would be measuring its own preprocessing (research A5).

    Returns `(observed, expected, n_categories_pooled)` where the last value is how many
    categories disappeared, so the caller can report the dof it actually used.
    """
    observed = np.asarray(observed, dtype=float)
    expected = np.asarray(expected, dtype=float)
    k = expected.size
    if k < 3:
        return observed, expected, 0

    depth = 1
    while 2 * depth < k:
        left_ok = expected[:depth].sum() >= min_expected
        right_ok = expected[k - depth :].sum() >= min_expected
        interior_ok = bool((expected[depth : k - depth] >= min_expected).all())
        if left_ok and right_ok and interior_ok:
            break
        depth += 1

    if 2 * depth >= k:
        # Everything is sparse: collapse to two bins. Degenerate, but honest — and the
        # resulting dof of 1 tells the reader exactly how little the test can see.
        pooled_obs = np.array([observed[: k // 2].sum(), observed[k // 2 :].sum()])
        pooled_exp = np.array([expected[: k // 2].sum(), expected[k // 2 :].sum()])
        return pooled_obs, pooled_exp, k - 2

    if depth == 1:
        return observed, expected, 0

    pooled_obs = np.concatenate(
        [[observed[:depth].sum()], observed[depth : k - depth], [observed[k - depth :].sum()]]
    )
    pooled_exp = np.concatenate(
        [[expected[:depth].sum()], expected[depth : k - depth], [expected[k - depth :].sum()]]
    )
    return pooled_obs, pooled_exp, k - pooled_obs.size


def _chi2(observed: np.ndarray, expected: np.ndarray, dof: int, alpha: float):
    statistic = float(np.sum((observed - expected) ** 2 / expected))
    dof = max(int(dof), 1)
    critical = float(sp_stats.chi2.ppf(1 - alpha, dof))
    p_value = float(sp_stats.chi2.sf(statistic, dof))
    return statistic, dof, critical, p_value


# =======================================================================================
# T017-T019 — the three tests
# =======================================================================================
def chi2_uniform_gof(
    counts,
    support,
    alpha: float = config.ALPHA,
    scope: str = "",
) -> HypothesisTestResult:
    """T1. H0: steering is uniformly distributed over the lattice support.

    We expect this to be rejected, decisively — and that is the point. This is the test
    against *invented* data. The commonest way to manufacture a dataset is to draw numbers
    from a random generator, and a uniform generator produces exactly the distribution H0
    describes. Failing to reject would therefore be the alarm: it would say the column has
    no driving structure in it at all (research A4 T1).
    """
    observed = np.asarray(counts, dtype=float)
    n = observed.sum()
    expected = np.full(observed.size, n / observed.size)

    obs_p, exp_p, n_pooled = pool_symmetric(observed, expected)
    statistic, dof, critical, p_value = _chi2(obs_p, exp_p, obs_p.size - 1, alpha)
    reject = statistic > critical

    if reject:
        meaning = (
            "ODBAČENO, kako smo i očekivali. Steering ima strukturu kakvu uniformni "
            "generator slučajnih brojeva ne proizvodi — to je dokaz PROTIV toga da je "
            "kolona izmišljena."
        )
    else:
        meaning = (
            "NIJE odbačeno. Steering se ne razlikuje od uniformnog šuma, a to je upravo "
            "ono što bi dao generator slučajnih brojeva. Na stvarnom snimku ovo je "
            "uzbuna, a ne prolaz."
        )

    return HypothesisTestResult(
        test_id="T1_uniform_gof",
        null_hypothesis=(
            f"steering je uniformno raspoređen po {len(support)} nivoa rešetke — svaka "
            "vrijednost jednako vjerovatna, kako bi ih dao uniformni generator"
        ),
        scope=scope,
        statistic=statistic,
        dof=dof,
        critical_value=critical,
        p_value=p_value,
        alpha=alpha,
        reject_null=bool(reject),
        n_categories_pooled=n_pooled,
        interpretation=meaning,
    )


def chi2_symmetry(
    counts,
    support,
    alpha: float = config.ALPHA,
    scope: str = "",
) -> HypothesisTestResult:
    """T2. H0: P(+k) == P(-k) for every lattice level k. Evaluated per track, never pooled
    across tracks.

    Under H0 the best estimate of each mirrored pair's shared probability is the average of
    the two observed counts, so the expected count for both members of a pair is
    `(n_minus + n_plus) / 2`.

    Pairs are the unit of pooling here, which makes symmetric pooling automatic: a pair is
    either kept whole or merged whole, so preprocessing can never favour one side. Sparse
    pairs are merged from the largest |steering| inward.

    Rejection is not automatically suspicious. A closed loop driven in one direction is
    asymmetric by construction — see the verdict layer (research A6).
    """
    observed = np.asarray(counts, dtype=float)
    levels = np.asarray(support, dtype=float)

    # Pair each negative level with its mirror image. The zero level is its own mirror and
    # carries no information about left-right balance, so it takes no part.
    order = np.argsort(levels)
    levels, observed = levels[order], observed[order]
    negatives = levels < 0
    positives = levels > 0

    minus = observed[negatives][::-1]  # ordered by increasing |level|
    plus = observed[positives]
    n_pairs = min(minus.size, plus.size)
    minus, plus = minus[:n_pairs], plus[:n_pairs]

    pair_expected = (minus + plus) / 2.0

    # Merge sparse pairs inward from the largest |steering|.
    depth = n_pairs
    while depth > 1 and pair_expected[depth - 1 :].sum() < config.CHI2_MIN_EXPECTED_PER_BIN:
        depth -= 1
    while depth > 1 and not (pair_expected[: depth - 1] >= config.CHI2_MIN_EXPECTED_PER_BIN).all():
        depth -= 1

    minus_p = np.append(minus[: depth - 1], minus[depth - 1 :].sum())
    plus_p = np.append(plus[: depth - 1], plus[depth - 1 :].sum())
    exp_p = (minus_p + plus_p) / 2.0

    keep = exp_p > 0
    minus_p, plus_p, exp_p = minus_p[keep], plus_p[keep], exp_p[keep]

    obs_all = np.concatenate([minus_p, plus_p])
    exp_all = np.concatenate([exp_p, exp_p])
    # One free parameter per pair is estimated from the data (the shared probability), so
    # the dof is the number of retained pairs, not twice that.
    statistic, dof, critical, p_value = _chi2(obs_all, exp_all, exp_p.size, alpha)
    reject = statistic > critical

    left_total, right_total = float(minus.sum()), float(plus.sum())
    ratio = left_total / right_total if right_total else float("inf")

    if reject:
        meaning = (
            f"ODBAČENO: lijevo/desno = {left_total:,.0f} / {right_total:,.0f} "
            f"(odnos {ratio:.3f}) — razlika je prevelika da bi bila slučajna. Odbacivanje "
            "samo po sebi NIJE sumnjivo: ono govori da asimetrija postoji, ne odakle "
            "dolazi. Uz to, pri ovolikom uzorku χ² vidi i sasvim malu neravnotežu, pa "
            "odnos treba čitati zajedno sa p-vrijednošću. Mehanizam i veličinu efekta "
            "vidi u verdiktu."
        )
    else:
        meaning = (
            f"NIJE odbačeno: lijevo/desno = {left_total:,.0f} / {right_total:,.0f} "
            f"(odnos {ratio:.3f}), u skladu sa stazom koja podjednako skreće na obje "
            "strane."
        )

    return HypothesisTestResult(
        test_id="T2_symmetry",
        null_hypothesis=(
            "raspodjela steeringa je simetrična oko nule: vozač je nivo +k koristio "
            "jednako često kao nivo −k, za svaki nivo k"
        ),
        scope=scope,
        statistic=statistic,
        dof=dof,
        critical_value=critical,
        p_value=p_value,
        alpha=alpha,
        reject_null=bool(reject),
        n_categories_pooled=int(n_pairs - exp_p.size),
        interpretation=meaning,
    )


def chi2_homogeneity(
    counts_a,
    counts_b,
    support,
    alpha: float = config.ALPHA,
    scope: str = "",
) -> HypothesisTestResult:
    """T3. H0: both tracks share one steering distribution over the shared support.

    A 2 x k contingency table. A support point observed on only one track is RETAINED with
    an observed count of zero — dropping it would quietly shrink the comparison to whatever
    the two tracks happen to have in common.

    We expect rejection: the tracks genuinely differ (a flat loop vs a mountain road).
    Failing to reject is the alarm — it is what you would see if the two "tracks" were one
    recording copied and renamed to double the dataset size (research A4 T3).
    """
    a = np.asarray(counts_a, dtype=float)
    b = np.asarray(counts_b, dtype=float)
    total = a.sum() + b.sum()

    column_totals = a + b
    row_totals = np.array([a.sum(), b.sum()])
    expected_a = row_totals[0] * column_totals / total
    expected_b = row_totals[1] * column_totals / total

    # Pool on the weaker row's expectations, then apply the same merge to both rows so the
    # table stays rectangular and the two rows stay comparable.
    weaker = expected_a if row_totals[0] <= row_totals[1] else expected_b
    _, _, n_pooled = pool_symmetric(column_totals, weaker)

    depth = 1 + n_pooled // 2
    k = column_totals.size
    if n_pooled:
        def merge(v: np.ndarray) -> np.ndarray:
            return np.concatenate([[v[:depth].sum()], v[depth : k - depth], [v[k - depth :].sum()]])

        a, b = merge(a), merge(b)
        column_totals = a + b
        expected_a = row_totals[0] * column_totals / total
        expected_b = row_totals[1] * column_totals / total

    keep = column_totals > 0
    obs_all = np.concatenate([a[keep], b[keep]])
    exp_all = np.concatenate([expected_a[keep], expected_b[keep]])
    n_columns = int(keep.sum())

    statistic, dof, critical, p_value = _chi2(obs_all, exp_all, n_columns - 1, alpha)
    reject = statistic > critical

    if reject:
        meaning = (
            "ODBAČENO: staze se stvarno različito voze. To potvrđuje da su u pitanju dva "
            "različita snimka, a ne jedan snimak iskopiran i preimenovan da bi dataset "
            "izgledao veći."
        )
    else:
        meaning = (
            "NIJE odbačeno: staze su statistički nerazlučive. Na podacima označenim kao "
            "dvije različite staze ovo je uzbuna — tako izgleda jedan snimak iskopiran i "
            "preimenovan."
        )

    return HypothesisTestResult(
        test_id="T3_homogeneity",
        null_hypothesis=(
            "obje staze vuku steering iz jedne te iste raspodjele nad zajedničkom "
            "podrškom rešetke"
        ),
        scope=scope,
        statistic=statistic,
        dof=dof,
        critical_value=critical,
        p_value=p_value,
        alpha=alpha,
        reject_null=bool(reject),
        n_categories_pooled=int(len(support) - n_columns),
        interpretation=meaning,
    )


# =======================================================================================
# T023 — verdicts
# =======================================================================================
# Above this ratio a left/right imbalance is a shape of the track, not a rounding artefact.
# Below it, a rejection on a large sample is statistically real but practically nothing —
# and saying so is the whole point of separating significance from size.
_MATERIAL_LR_RATIO = 1.5


def classify_findings(
    granularity: dict[str, list[GranularityProfile]],
    timelines: list[TimelineReport],
    duplications: list[DuplicationReport],
    plausibility: list[PlausibilityReport],
    tests: list[HypothesisTestResult],
    row_counts: dict[str, int],
    lr_ratios: dict[str, float],
    zero_pct: dict[str, float],
) -> list[Verdict]:
    """Turn measurements into findings that mean something (FR-015, FR-016, research A6).

    A finding is evidence of tampering only if we have NO mechanism that explains it. This
    is the step that stops the report from being a list of frightening numbers — and it is
    also what stops the project from accusing a sound dataset of being faked.

    Conditions are read off the actual reports, so a verdict cannot survive the data
    changing underneath it. The mechanisms are prose, because that is what they are: human
    knowledge about how the recording was made.
    """
    verdicts: list[Verdict] = []

    # --- constant columns -----------------------------------------------------------
    for source, profiles in granularity.items():
        for profile in profiles:
            if profile.classification != "constant":
                continue
            # A deleted column and a never-used column look identical in the numbers. What
            # tells them apart is whether the SAME column varies on another recording: if it
            # does, the format is fine and the writer works, so the flat one is behaviour.
            elsewhere = {
                other: next(
                    (p.n_distinct for p in other_profiles if p.column == profile.column), 0
                )
                for other, other_profiles in granularity.items()
                if other != source
            }
            varies_elsewhere = ", ".join(
                f"{other}: {n:,} različitih" for other, n in elsewhere.items()
            )
            verdicts.append(
                Verdict(
                    finding_id=f"{source}:{profile.column}:constant",
                    summary=(
                        f"{source}: kolona '{profile.column}' ima tačno jednu vrijednost u "
                        f"svih {row_counts.get(source, 0):,} redova"
                    ),
                    classification="explainable",
                    mechanism=(
                        "staza 1 je ravna zatvorena petlja — vozač nijednom nije zakočio. "
                        "Obrisana kolona i nikad korištena kolona izgledaju isto u brojkama; "
                        f"razlikuje ih to što ista kolona drugdje varira ({varies_elsewhere}), "
                        "dakle format je ispravan i pisač kolone radi"
                    ),
                    downstream_consequence=(
                        "M1 je nad spojenim podacima prijavio brake_is_dead: false (94,6 % "
                        "nula). To je artefakt spajanja — po stazi je kolona mrtva"
                    ),
                    mitigation=(
                        "kočnicu izvještavati po stazi, nikad spojeno; ne koristiti je kao "
                        "ulaz za model treniran samo na stazi 1"
                    ),
                )
            )

    # --- steering lattice -------------------------------------------------------------
    for source, profiles in granularity.items():
        for profile in profiles:
            if profile.column != "steering":
                continue
            if profile.off_lattice_values:
                verdicts.append(
                    Verdict(
                        finding_id=f"{source}:steering:off_lattice",
                        summary=(
                            f"{source}: {len(profile.off_lattice_values)} vrijednost(i) "
                            f"steeringa nije cijeli umnožak koraka {profile.spacing}"
                        ),
                        classification="unexplained",
                    )
                )
            if profile.unobserved_support:
                verdicts.append(
                    Verdict(
                        finding_id=f"{source}:steering:unobserved_levels",
                        summary=(
                            f"{source}: nivoi {profile.unobserved_support} postoje u "
                            "rešetki ali se nikad ne pojavljuju"
                        ),
                        classification="explainable",
                        mechanism=(
                            "nivo koji vozač jednostavno nije upotrijebio. Da je neko "
                            "brisao redove, nestajali bi cijeli opsezi vrijednosti i "
                            "vidjeli bismo rupu i u vremenu — ovdje je nestao jedan "
                            "izolovan nivo dok mu susjedi i ogledalni parnjak postoje"
                        ),
                    )
                )

    # --- timeline ---------------------------------------------------------------------
    for report in timelines:
        if not report.is_monotonic:
            verdicts.append(
                Verdict(
                    finding_id=f"{report.session_id}:timeline:order",
                    summary=(
                        f"{report.session_id}: {report.n_order_violations} koraka u kojima "
                        "vrijeme ne teče naprijed"
                    ),
                    classification="unexplained",
                )
            )
        for row in report.gap_examples:
            at_end = row >= report.n_rows - 1
            verdicts.append(
                Verdict(
                    finding_id=f"{report.session_id}:timeline:gap@{row}",
                    summary=(
                        f"{report.session_id}: rupa od {report.largest_gap_s:.3f} s "
                        f"(prag {report.gap_threshold_s:.3f} s) na redu {row}"
                    ),
                    classification="explainable" if at_end else "unexplained",
                    mechanism=(
                        "rupa pada na POSLJEDNJI kadar snimka — to je gašenje snimača, ne "
                        "izrezan komad. Izrezan blok bi ostavio rupu u SREDINI i skok u "
                        "sadržaju na spoju; ovdje su brzina i steering neprekidni preko nje"
                    )
                    if at_end
                    else None,
                )
            )

    # --- duplication ------------------------------------------------------------------
    for report in duplications:
        if report.n_exact_duplicate_rows or report.n_duplicate_image_refs:
            verdicts.append(
                Verdict(
                    finding_id=f"{report.source}:duplicates:rows",
                    summary=(
                        f"{report.source}: {report.n_exact_duplicate_rows} identičnih "
                        f"redova, {report.n_duplicate_image_refs} ponovljenih slika"
                    ),
                    classification="unexplained",
                )
            )
        if report.n_duplicate_measurement_tuples:
            verdicts.append(
                Verdict(
                    finding_id=f"{report.source}:duplicates:tuples",
                    summary=(
                        f"{report.source}: {report.n_duplicate_measurement_tuples} "
                        "ponovljenih četvorki mjerenja na različitim kadrovima"
                    ),
                    classification="explainable",
                    mechanism=(
                        "steering ima samo 41 mogući nivo, pa je prostor vrijednosti mali i "
                        "sudari se dešavaju sami od sebe. Da je riječ o kopiranju redova, "
                        "ponovile bi se i putanje slika — a njih ima 0"
                    ),
                )
            )

    # --- plausibility -----------------------------------------------------------------
    for report in plausibility:
        if report.n_outliers == 0:
            continue
        n_rows = row_counts.get(report.session_id.replace("data", ""), 0)
        pct = 100.0 * report.n_outliers / n_rows if n_rows else float("nan")
        verdicts.append(
            Verdict(
                finding_id=f"{report.session_id}:plausibility:outliers",
                summary=(
                    f"{report.session_id}: {report.n_outliers:,} kadrova ({pct:.1f} %) van "
                    f"pojasa median ± {config.ACCEL_MAD_K:g}×MAD impliciranog ubrzanja"
                ),
                classification="explainable",
                mechanism=(
                    "raspodjela impliciranog ubrzanja ima uzak centar i široke repove "
                    f"(MAD = {report.mad_accel:.2f}, ali maksimum = {report.max_abs_accel:.1f}): "
                    "gas i kočnica se pri 14 kadrova/s koriste u naletima, pa pojas od "
                    "5×MAD oko uskog centra pada oko 97. percentila. Visok procenat je "
                    "oblik raspodjele, a ne trag friziranja — potpis spajanja bio bi "
                    "ekstrem koji se POKLAPA sa rupom u vremenu, a takvog poklapanja nema"
                ),
                downstream_consequence=(
                    "apsolutni broj outliera se ne smije citirati kao mjera ispravnosti "
                    "podataka"
                ),
                mitigation=(
                    "koristiti ga isključivo relativno — porediti ekstreme sa rupama u "
                    "vremenu, a ne sa fiksnim pragom"
                ),
            )
        )

    # --- hypothesis tests --------------------------------------------------------------
    for result in tests:
        if result.test_id == "T1_uniform_gof":
            verdicts.append(
                Verdict(
                    finding_id=f"{result.scope}:T1",
                    summary=(
                        f"{result.scope}: uniformnost {'odbačena' if result.reject_null else 'NIJE odbačena'} "
                        f"(χ² = {result.statistic:,.0f}, dof = {result.dof})"
                    ),
                    classification="explainable" if result.reject_null else "unexplained",
                    mechanism=(
                        "stvarna vožnja je dominantno pravo — "
                        f"{zero_pct.get(result.scope, float('nan')):.1f} % kadrova ima "
                        "steering tačno 0. Nijedan uniformni generator to ne proizvodi"
                    )
                    if result.reject_null
                    else None,
                )
            )
        elif result.test_id == "T2_symmetry":
            if not result.reject_null:
                continue
            ratio = lr_ratios.get(result.scope, float("nan"))
            material = ratio > _MATERIAL_LR_RATIO or ratio < 1 / _MATERIAL_LR_RATIO
            if material:
                verdicts.append(
                    Verdict(
                        finding_id=f"{result.scope}:T2:material",
                        summary=(
                            f"{result.scope}: simetrija odbačena, odnos lijevo/desno = "
                            f"{ratio:.3f} — velika, stvarna asimetrija"
                        ),
                        classification="explainable",
                        mechanism=(
                            "zatvorena petlja vožena u jednom smjeru (suprotno kazaljci na "
                            "satu): svaki krug daje isti broj lijevih zaokreta, a desnih "
                            "gotovo nema"
                        ),
                        downstream_consequence=(
                            "ozbiljan rizik za M4 — BC model naučen na ovim podacima vuče "
                            "lijevo i na pravcu"
                        ),
                        mitigation=(
                            "horizontalno ogledanje slike uz promjenu znaka steeringa "
                            "(udvostručuje podatke i izjednačava lijevo/desno)"
                        ),
                    )
                )
            else:
                verdicts.append(
                    Verdict(
                        finding_id=f"{result.scope}:T2:negligible",
                        summary=(
                            f"{result.scope}: simetrija odbačena, ali odnos lijevo/desno = "
                            f"{ratio:.3f} — praktično zanemarivo"
                        ),
                        classification="explainable",
                        mechanism=(
                            "veličina uzorka, ne veličina efekta. Pri desetinama hiljada "
                            "kadrova χ² vidi i neravnotežu od nekoliko procenata. "
                            "Statistička značajnost nije isto što i praktična — zato uz "
                            "svaki test izvještavamo i odnos, a ne samo p-vrijednost"
                        ),
                    )
                )
        elif result.test_id == "T3_homogeneity":
            verdicts.append(
                Verdict(
                    finding_id="T3",
                    summary=(
                        f"homogenost staza {'odbačena' if result.reject_null else 'NIJE odbačena'} "
                        f"(χ² = {result.statistic:,.0f}, dof = {result.dof})"
                    ),
                    classification="explainable" if result.reject_null else "unexplained",
                    mechanism=(
                        "staze su fizički različite: ravna zatvorena petlja naspram brdske "
                        "ceste sa oštrim serpentinama"
                    )
                    if result.reject_null
                    else None,
                )
            )

    return verdicts


# =======================================================================================
# T024 — does any of this change M1's calibration?
# =======================================================================================
def recheck_calibration(track_datasets) -> tuple[bool, str]:
    """Recompute the two numbers M1 handed to Unity, and compare (FR-018).

    The expectation is that nothing moves, and there is a reason: both figures are
    PERCENTILES. A percentile is an order statistic — it is read off the sorted values, so
    it does not care whether we call the variable discrete or continuous. But FR-018 asks us
    to check rather than assume, so we check. M1's own files are read, never rewritten
    (research A9).
    """
    from .stats import abs_delta_steering  # local import: M1 module stays untouched

    m1_path = config.EDA_OUT_DIR / "m1_stats.json"
    if not m1_path.exists():
        return False, f"M1 kalibracija nije pronađena na {m1_path} — poređenje nije moguće."

    m1 = json.loads(m1_path.read_text(encoding="utf-8"))

    tracks = [ds for ds in track_datasets]
    delta_threshold = float(
        np.percentile(abs_delta_steering(tracks), config.DELTA_STEERING_PERCENTILE)
    )
    pooled_steering = np.concatenate([ds.df["steering"].to_numpy(float) for ds in tracks])
    lo_pct, hi_pct = config.STEERING_RANGE_PERCENTILES
    robust_range = (
        float(np.percentile(pooled_steering, lo_pct)),
        float(np.percentile(pooled_steering, hi_pct)),
    )

    delta_same = np.isclose(delta_threshold, m1["delta_steering_threshold"], atol=1e-9)
    range_same = np.allclose(robust_range, m1["steering_range_robust"], atol=1e-9)
    unchanged = bool(delta_same and range_same)

    spacing_steps = delta_threshold / 0.05
    note = (
        f"Prag |Δsteering| (P{config.DELTA_STEERING_PERCENTILE:g}) ponovo izračunat: "
        f"{delta_threshold:.7f} naspram M1 {m1['delta_steering_threshold']:.7f}. "
        f"Robustan opseg steeringa (P{lo_pct:g}–P{hi_pct:g}): "
        f"({robust_range[0]:.3f}, {robust_range[1]:.3f}) naspram M1 "
        f"({m1['steering_range_robust'][0]:.3f}, {m1['steering_range_robust'][1]:.3f}). "
        f"{'NEPROMIJENJENO' if unchanged else 'PROMIJENJENO — istražiti prije M2'}. "
        "Razlog: oba broja su percentili, dakle redoslijedne statistike — čitaju se iz "
        "sortiranih vrijednosti i potpuno su nezavisne od toga da li varijablu zovemo "
        f"diskretnom ili kontinualnom. Uzgred, prag je {spacing_steps:.0f} koraka rešetke, "
        "što potvrđuje da pada tačno na dozvoljenu vrijednost."
    )
    return unchanged, note


# =======================================================================================
# T025 — orchestration, figures, report
# =======================================================================================
def counts_on_support(values, support, atol: float = config.LATTICE_ATOL) -> np.ndarray:
    """Count how many observations land on each lattice level.

    Values are matched to their NEAREST support point rather than compared for equality,
    because the recorder writes levels above 0.45 with a systematic offset of up to 2e-7
    (research A3.1). A value further than `atol` from every support point is not counted —
    that would be an off-lattice value, and `profile_granularity` reports those separately.
    """
    v = np.asarray(values, dtype=float)
    s = np.asarray(support, dtype=float)
    nearest = np.abs(v[:, None] - s[None, :]).argmin(axis=1)
    distance = np.abs(v - s[nearest])
    nearest = nearest[distance <= atol]
    return np.bincount(nearest, minlength=s.size).astype(float)


def _steering_support(profiles: dict[str, list[GranularityProfile]]) -> list[float]:
    """The union of both tracks' lattice supports.

    A level seen on only one track stays in, with a count of zero on the other. Intersecting
    instead would quietly shrink the comparison to whatever the tracks happen to have in
    common — and a missing level is exactly the kind of thing we are looking for.
    """
    points: set[float] = set()
    for column_profiles in profiles.values():
        for profile in column_profiles:
            if profile.column == "steering" and profile.support:
                points.update(profile.support)
    return sorted(points)


def _fig_timeline(timelines, deltas: dict[str, np.ndarray], path) -> None:
    fig, axes = plt.subplots(1, len(timelines), figsize=(6 * len(timelines), 4), squeeze=False)
    for ax, report in zip(axes[0], timelines):
        ax.hist(deltas[report.session_id], bins=60, color="#2c7fb8")
        ax.axvline(
            report.gap_threshold_s,
            color="black",
            linestyle="--",
            label=f"prag rupe = {report.gap_threshold_s:.3f} s",
        )
        # The tail is the whole point of this figure; a linear axis hides it completely.
        ax.set_yscale("log")
        ax.set_title(
            f"{report.session_id}: razmak između kadrova\n"
            f"median {report.median_interval_s:.3f} s ≈ {report.implied_fps:.1f} kadrova/s, "
            f"rupa: {report.n_gaps}"
        )
        ax.set_xlabel("Δt (s)")
        ax.set_ylabel("broj kadrova (log)")
        ax.legend()
        ax.grid(True)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _fig_lattice(profiles: dict[str, list[GranularityProfile]], path) -> None:
    sources = list(profiles)
    fig, axes = plt.subplots(len(sources), 1, figsize=(11, 3.2 * len(sources)), squeeze=False)
    for ax, source in zip(axes[:, 0], sources):
        profile = next(p for p in profiles[source] if p.column == "steering")
        support = np.array(profile.support or [])
        unobserved = set(profile.unobserved_support)
        colors = ["#c0392b" if float(x) in unobserved else "#2c7fb8" for x in support]
        ax.vlines(support, 0, 1, colors=colors, lw=2)
        ax.set_yticks([])
        ax.set_xlim(-1.08, 1.08)
        ax.set_title(
            f"{source}: rešetka steeringa — korak {profile.spacing}, "
            f"{len(support)} nivoa, {profile.n_distinct} opaženih "
            f"(crveno = nikad opaženo; najveći ostatak {profile.max_residual:.1e})"
        )
        ax.set_xlabel("ugao volana")
        ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _fig_symmetry(counts: dict[str, np.ndarray], support, tests, path) -> None:
    support = np.asarray(support, dtype=float)
    sources = list(counts)
    fig, axes = plt.subplots(1, len(sources), figsize=(6.5 * len(sources), 4.2), squeeze=False)
    for ax, source in zip(axes[0], sources):
        c = counts[source]
        levels = support[support > 0]
        right = c[support > 0]
        # Mirror the negative side onto the same axis so the two are directly comparable —
        # that is exactly the comparison the symmetry test makes.
        left = np.array([c[np.isclose(support, -x)].sum() for x in levels])
        width = 0.02
        ax.bar(levels - width / 2, left, width, label="lijevo (−k)", color="#c0392b")
        ax.bar(levels + width / 2, right, width, label="desno (+k)", color="#2c7fb8")
        ax.set_yscale("log")
        result = next((t for t in tests if t.test_id == "T2_symmetry" and t.scope == source), None)
        title = f"{source}: simetrija po |k|"
        if result:
            decision = "ODBACI" if result.reject_null else "ZADRŽI"
            title += f"\nχ²={result.statistic:.1f} dof={result.dof} → H₀ {decision}"
        ax.set_title(title)
        ax.set_xlabel("|ugao volana|")
        ax.set_ylabel("broj kadrova (log)")
        ax.legend()
        ax.grid(True)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _fig_homogeneity(counts: dict[str, np.ndarray], support, result, path) -> None:
    support = np.asarray(support, dtype=float)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    colors = {"track1": "#c0392b", "track2": "#2c7fb8"}
    for i, (source, c) in enumerate(counts.items()):
        # Relative frequency, not raw counts: track2 has twice the rows, and the question
        # is whether the SHAPES differ.
        ax.bar(
            support + (i - 0.5) * 0.02,
            c / c.sum(),
            0.02,
            label=f"{source} (n={c.sum():,.0f})",
            color=colors.get(source),
        )
    ax.set_yscale("log")
    decision = "ODBACI" if result.reject_null else "ZADRŽI"
    ax.set_title(
        f"Poređenje staza po nivoima rešetke — χ²={result.statistic:,.0f} "
        f"dof={result.dof} → H₀ {decision}"
    )
    ax.set_xlabel("ugao volana")
    ax.set_ylabel("relativna frekvencija (log)")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    raise TypeError(f"not JSON serialisable: {type(value)!r}")


def run_authenticity(sources: tuple[str, ...] = ("track1", "track2")) -> AuthenticityOutput:
    """Run the whole authenticity battery and write the artifacts (FR-017).

    Writes ONLY `results/eda/authenticity_*.{md,json}` and
    `results/plots/authenticity_*.png`. M1's `m1_report.md` and `m1_stats.json` are read for
    the calibration comparison and never opened for writing: they are reviewed, committed
    artifacts, and silently regenerating them would break the link between what was reviewed
    and what is in the repository (research A9).
    """
    config.PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    config.EDA_OUT_DIR.mkdir(parents=True, exist_ok=True)

    datasets = {name: load_track(name) for name in sources}

    sessions: list[RecordingSession] = []
    timelines: list[TimelineReport] = []
    duplications: list[DuplicationReport] = []
    plausibility: list[PlausibilityReport] = []
    granularity: dict[str, list[GranularityProfile]] = {}
    interval_samples: dict[str, np.ndarray] = {}
    row_counts: dict[str, int] = {}

    for name, ds in datasets.items():
        row_counts[name] = len(ds.df)
        track_sessions = split_sessions(ds)
        sessions.extend(track_sessions)
        timelines.extend(check_timeline(ds))
        duplications.append(check_duplicates(ds))
        plausibility.extend(check_plausibility(ds))
        granularity[name] = profile_granularity(ds)
        for session in track_sessions:
            times = _session_times(ds, session)
            interval_samples[session.session_id] = (
                times.diff().dropna().dt.total_seconds().to_numpy()
            )

    support = _steering_support(granularity)
    support_arr = np.asarray(support, dtype=float)
    counts = {
        name: counts_on_support(ds.df["steering"], support) for name, ds in datasets.items()
    }

    lr_ratios: dict[str, float] = {}
    zero_pct: dict[str, float] = {}
    for name, c in counts.items():
        left, right = c[support_arr < 0].sum(), c[support_arr > 0].sum()
        lr_ratios[name] = float(left / right) if right else float("inf")
        zero_pct[name] = 100.0 * float(c[np.isclose(support_arr, 0.0)].sum()) / c.sum()

    tests: list[HypothesisTestResult] = []
    for name, c in counts.items():
        tests.append(chi2_uniform_gof(c, support, scope=name))
        tests.append(chi2_symmetry(c, support, scope=name))
    names = list(counts)
    homogeneity = chi2_homogeneity(
        counts[names[0]], counts[names[1]], support, scope=f"{names[0]} vs {names[1]}"
    )
    tests.append(homogeneity)

    verdicts = classify_findings(
        granularity,
        timelines,
        duplications,
        plausibility,
        tests,
        row_counts,
        lr_ratios,
        zero_pct,
    )
    calibration_unchanged, calibration_note = recheck_calibration(list(datasets.values()))

    _fig_timeline(timelines, interval_samples, config.PLOTS_DIR / "authenticity_timeline.png")
    _fig_lattice(granularity, config.PLOTS_DIR / "authenticity_lattice.png")
    _fig_symmetry(counts, support, tests, config.PLOTS_DIR / "authenticity_symmetry.png")
    _fig_homogeneity(
        counts, support, homogeneity, config.PLOTS_DIR / "authenticity_homogeneity.png"
    )

    output = AuthenticityOutput(
        sources=list(sources),
        sessions=sessions,
        timelines=timelines,
        duplications=duplications,
        granularity=granularity,
        plausibility=plausibility,
        tests=tests,
        verdicts=verdicts,
        calibration_unchanged=calibration_unchanged,
        calibration_note=calibration_note,
    )

    (config.EDA_OUT_DIR / "authenticity_stats.json").write_text(
        json.dumps(asdict(output), indent=2, default=_json_default, ensure_ascii=False),
        encoding="utf-8",
    )
    (config.EDA_OUT_DIR / "authenticity_report.md").write_text(
        _render_report(output), encoding="utf-8"
    )
    return output


def _render_report(output: AuthenticityOutput) -> str:
    lines = [
        "# Provjera autentičnosti podataka (auto-generisan)",
        "",
        "Ovaj izvještaj odgovara na jedno pitanje: **ima li traga friziranju podataka?**",
        "",
        "Pravilo koje vrijedi za svaki nalaz ispod: **bez nulte hipoteze nema nalaza.** Gola",
        "brojka ne dokazuje ništa. Prije nego što provjera smije nešto prijaviti, mora reći",
        "kako bi podaci izgledali da je sve u redu (H₀) i kako bi izgledali da je manipulacija",
        "urađena (očekivani potpis). Tek tada odbacivanje ili neodbacivanje nešto znači.",
        "",
        f"α = {output.alpha} · SEED = {output.seed} · tolerancija rešetke = "
        f"{output.lattice_tolerance:g}",
        "",
        "## 1. Snimci (sesije)",
        "",
        "Vrijeme ima smisla samo unutar jednog snimanja. Spojeni fajl spaja dva snimka, a",
        "staza 2 je snimljena **ranije istog dana** od staze 1 — pa vrijeme na spoju ide",
        "unazad. To nije greška u podacima nego posljedica spajanja, i zato se sve vremenske",
        "provjere rade **po sesiji**.",
        "",
        "| sesija | redovi | od | do |",
        "|---|---|---|---|",
    ]
    for s in output.sessions:
        lines.append(f"| {s.session_id} | {s.n_rows:,} | {s.start_time} | {s.end_time} |")

    lines += [
        "",
        "## 2. Kontinuitet snimka",
        "",
        "*Očekivani potpis*: izmiješani redovi → vrijeme prestaje teći naprijed; izrezan blok",
        "→ jedna velika rupa; obrisani pojedinačni redovi → mnogo malih rupa oko 2× medijana.",
        "Zato izvještavamo cijelu raspodjelu Δt, a ne samo maksimum.",
        "",
        "| sesija | monotono | narušenja | median Δt | kadrova/s | prag rupe | rupa | >2× | >5× | >1 s | najveća |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in output.timelines:
        lines.append(
            f"| {t.session_id} | {'da' if t.is_monotonic else '**NE**'} | "
            f"{t.n_order_violations} | {t.median_interval_s:.4f} s | {t.implied_fps:.2f} | "
            f"{t.gap_threshold_s:.3f} s | {t.n_gaps} | {t.gap_tiers['>2x']} | "
            f"{t.gap_tiers['>5x']} | {t.gap_tiers['>1s']} | {t.largest_gap_s:.3f} s |"
        )
    lines += [
        "",
        f"Neparsiranih vremenskih oznaka: {sum(t.n_unparseable for t in output.timelines)} "
        "(nijedan red nije tiho izbačen).",
        "",
        "## 3. Duplikati",
        "",
        "Tri vrste, **brojane odvojeno** jer svaka znači nešto drugo. Zbrajanje bi treću",
        "(bezopasnu) pretvorilo u lažnu uzbunu.",
        "",
        "| izvor | identični redovi | ponovljene slike | ponovljene četvorke mjerenja |",
        "|---|---|---|---|",
    ]
    for d in output.duplications:
        lines.append(
            f"| {d.source} | {d.n_exact_duplicate_rows} | {d.n_duplicate_image_refs} | "
            f"{d.n_duplicate_measurement_tuples} |"
        )

    lines += [
        "",
        "## 4. Rezolucija zapisa (granularnost)",
        "",
        "Pitanje koje M1 nije postavio, a mijenja koji je test uopšte ispravan.",
        "",
        "| izvor | kolona | različitih | klasifikacija | korak | nivoa | neopaženi | van rešetke | najveći ostatak |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for source, profiles in output.granularity.items():
        for p in profiles:
            lines.append(
                f"| {source} | {p.column} | {p.n_distinct:,} | **{p.classification}** | "
                f"{p.spacing if p.spacing else '—'} | "
                f"{len(p.support) if p.support else '—'} | "
                f"{p.unobserved_support or '—'} | {p.off_lattice_values or 'nema'} | "
                f"{p.max_residual:.2e} |"
            )
    lines.append("")
    for source, profiles in output.granularity.items():
        for p in profiles:
            lines.append(f"- `{source}.{p.column}`: {p.evidence}")

    lines += [
        "",
        "## 5. Fizička uvjerljivost promjene brzine",
        "",
        "Kriterij je namjerno **relativan**: jedinica kolone `speed` nije dokumentovana, pa bi",
        "tvrdnja tipa „ubrzanje je ispod 1 g\" tražila pretpostavku koju ne možemo provjeriti,",
        "a lažna preciznost je gora od poštene relativne mjere. Robusno (MAD), jer bi nekoliko",
        "ubačenih skokova naduvalo standardnu devijaciju toliko da granica pređe preko njih i",
        "test prestane da ih vidi.",
        "",
        "| sesija | median a | MAD | max \\|a\\| | prag | outliera |",
        "|---|---|---|---|---|---|",
    ]
    for p in output.plausibility:
        lines.append(
            f"| {p.session_id} | {p.median_accel:.3f} | {p.mad_accel:.3f} | "
            f"{p.max_abs_accel:.2f} | {p.outlier_threshold:.2f} | {p.n_outliers:,} |"
        )

    lines += [
        "",
        "## 6. Hipoteze i testovi",
        "",
        "χ², a ne KS: KS pretpostavlja kontinualnu raspodjelu, a na rešetkastim podacima ima",
        "vezane vrijednosti i p-vrijednost mu nije tačna. Za diskretnu varijablu kategorije su",
        "same vrijednosti — nema binovanja, dakle nema ni proizvoljnog izbora.",
        "",
    ]
    for t in output.tests:
        lines += [
            f"### {t.test_id} — {t.scope}",
            "",
            f"- **H₀**: {t.null_hypothesis}",
            f"- χ² = {t.statistic:,.2f} · dof = {t.dof} (nakon spajanja; spojenih kategorija: "
            f"{t.n_categories_pooled}) · kritično = {t.critical_value:.2f} · p = {t.p_value:.3g}",
            f"- **Odluka pri α = {t.alpha}**: "
            f"{'ODBACUJEMO H₀' if t.reject_null else 'NE odbacujemo H₀'}",
            f"- **Značenje**: {t.interpretation}",
            "",
        ]

    unexplained = [v for v in output.verdicts if v.classification == "unexplained"]
    lines += [
        "## 7. Verdikti — objašnjivo naspram sumnjivog",
        "",
        "Nalaz je dokaz friziranja **samo ako nemamo mehanizam koji ga objašnjava**. Nalaz",
        "može biti objašnjiv **i** i dalje štetan za kasniji milestone — tada nosi i posljedicu",
        "i mjeru ublažavanja.",
        "",
        f"**Sažetak: {len(output.verdicts)} nalaza, od toga {len(unexplained)} bez "
        "objašnjenja.**",
        "",
    ]
    for v in output.verdicts:
        tag = "objašnjivo" if v.classification == "explainable" else "**NEOBJAŠNJENO**"
        lines += [f"### {v.finding_id} — {tag}", "", f"- **Nalaz**: {v.summary}"]
        if v.mechanism:
            lines.append(f"- **Mehanizam**: {v.mechanism}")
        if v.downstream_consequence:
            lines.append(f"- **Posljedica**: {v.downstream_consequence}")
        if v.mitigation:
            lines.append(f"- **Mjera**: {v.mitigation}")
        lines.append("")

    lines += [
        "## 8. Da li se M1 kalibracija mijenja?",
        "",
        f"**{'NE' if output.calibration_unchanged else 'DA'}** — {output.calibration_note}",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    result = run_authenticity()
    unresolved = [v for v in result.verdicts if v.classification == "unexplained"]
    print(f"Gotovo. Nalaza: {len(result.verdicts)}, neobjašnjenih: {len(unresolved)}")
    for v in unresolved:
        print(f"  ! {v.finding_id}: {v.summary}")
