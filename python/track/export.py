"""Serialise accepted tracks to the committed handoff format, and generate them in batches.

One file per accepted seed, at `unity/SelfDrivingSim/Assets/Tracks/seed_<seed>.json`, written
to schema version 1. This file is the reason Unity contains no statistics: everything that
needed proving is proved here and written down, and Unity reads numbers and places objects.

**Files are byte-identical across runs.** Two runs over the same seed list produce the same
bytes, which is what makes a committed track file reviewable in a diff and what SC-007 asks
for. That has one consequence worth stating: there is no generation timestamp inside the track
file. A timestamp would change every run and make byte-identical output impossible, so the
generation time is recorded in the batch report instead, where reproducibility is not claimed.

**A rejected seed is never retried with adjusted parameters.** It is recorded with its reason
and left rejected. Resampling until something passes hides the acceptance rate, and the rate is
a finding about the radius floor rather than a nuisance (research C7, FR-020).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import config, geometry, matching
from .generator import CentreLine, TrackSeed, draw_parameters, centre_line
from .vehicle import VehicleProfile, build_profile

SCHEMA_VERSION: int = 1

TRACKS_DIR: Path = (
    Path(__file__).resolve().parents[2] / "unity" / "SelfDrivingSim" / "Assets" / "Tracks")

RESULTS_DIR: Path = Path(__file__).resolve().parents[2] / "results" / "tracks"

# Decimal places used for every float written. Fixed so the output is stable: repr of a float
# is deterministic within a version but noisy to read and fragile to compare across platforms.
_PLACES: int = 6


class SeedRejected(Exception):
    """Raised when a seed fails a geometric check. No file is written."""

    def __init__(self, seed: int, reason: str):
        super().__init__(f"seed {seed} rejected: {reason}")
        self.seed = seed
        self.reason = reason


@dataclass(frozen=True)
class BatchReport:
    """What happened to a list of seeds."""

    name: str
    requested: int
    accepted_seeds: list[int]
    rejections: list[tuple[int, str]]
    generated_utc: str

    @property
    def acceptance_rate(self) -> float:
        return len(self.accepted_seeds) / self.requested if self.requested else 0.0


def _round(value) -> float:
    return round(float(value), _PLACES)


def _profile_block(profile: VehicleProfile) -> dict:
    """The profile the track was validated against. A track is valid for one car only."""
    return {
        "wheelbase_m": _round(profile.wheelbase_m),
        "steer_max_deg": _round(profile.steer_max_deg),
        "radius_margin": _round(profile.radius_margin),
        "r_min_m": _round(profile.r_min_m),
        "r_floor_m": _round(profile.r_floor_m),
        "max_required_steer": _round(profile.max_required_steer),
    }


def _generator_block(params: TrackSeed) -> dict:
    """Enough to rebuild the centre line without trusting the sampled points.

    Not decoration: a reviewer who does not trust the points below can regenerate them from
    this block and compare. That is what makes a committed file auditable.
    """
    return {
        "form": "polar_harmonic",
        "r0_m": _round(config.TRACK_R0_M),
        "harmonics": list(config.HARMONICS),
        "amplitude": _round(params.amplitude),
        "phases": [_round(p) for p in params.phases],
    }


def build_track_document(line: CentreLine, profile: VehicleProfile) -> dict:
    """The whole file, as a dictionary, in schema order.

    Raises `SeedRejected` rather than returning a document for a seed that fails a check. A
    file claiming `radius_ok: false` should not exist, so nothing here can produce one.
    """
    report = geometry.check_geometry(line, profile)
    if not report.ok:
        raise SeedRejected(line.seed, report.rejection_reason or "unknown")

    demand = matching.required_steering(line, profile)
    reference = matching.reference_distribution()
    match = matching.match_distance(demand, reference, profile=profile)
    bound = matching.demand_bound(demand, reference)
    checkpoints = geometry.place_checkpoints(line)
    d = demand.descriptives

    return {
        "schema_version": SCHEMA_VERSION,
        "seed": int(line.seed),
        "generator": _generator_block(line.params),
        "vehicle_profile": _profile_block(profile),
        "width_m": _round(config.TRACK_WIDTH_M),
        "total_length_m": _round(line.total_length_m),
        "centre_line": [
            {
                "x": _round(line.x[i]),
                "y": _round(line.y[i]),
                "s": _round(line.arc_length[i]),
                "radius_m": _round(line.radius[i]),
                "required_steer": _round(demand.required_steer[i]),
            }
            for i in range(len(line.x))
        ],
        "checkpoints": [
            {
                "index": c.index,
                "x": _round(c.x),
                "y": _round(c.y),
                "forward_x": _round(c.heading_x),
                "forward_y": _round(c.heading_y),
                "s": _round(c.s),
            }
            for c in checkpoints
        ],
        "geometry_report": {
            "min_radius_m": _round(report.min_radius_m),
            "r_floor_m": _round(report.r_floor_m),
            "radius_ok": report.radius_ok,
            "self_intersects": report.self_intersects,
            "min_separation_m": _round(report.min_separation_m),
            "separation_ok": report.separation_ok,
        },
        # SC-010 is judged on this block, not on match_report. See the spec revision of
        # 2026-07-31: required steering is the geometric minimum to follow the line, while the
        # human column is steering actually applied, so a distribution match is unachievable
        # and a bound is what the criterion was protecting against.
        "demand_bound": {
            "within_bound": bound.within_bound,
            "max_required": _round(bound.max_required),
            "reference_max": _round(bound.reference_max),
            "exceedance_fraction": _round(bound.exceedance_fraction),
            "percentile_gaps": {f"p{p:g}": _round(g)
                                for p, g in sorted(bound.percentile_gaps.items())},
            "note": bound.note,
        },
        # Retained as a diagnostic. It is no longer the acceptance gate, and carries no
        # p-value by contract (FR-019, research C8).
        "match_report": {
            "scope": match.scope,
            "distance": _round(match.distance),
            "threshold": _round(match.threshold),
            "accepted": match.accepted,
            "scales": {k: _round(v) for k, v in match.scales.items()},
            "reference": match.reference,
            "n_track_samples": match.n_track_samples,
            "n_reference_samples": match.n_reference_samples,
            "note": match.note,
        },
        # Constitution Principle IX: mandatory, not optional. A file missing this block fails
        # the loader.
        "required_steer_descriptives": {
            "n": d.n,
            "mean": _round(d.mean),
            "variance": _round(d.variance),
            "std": _round(d.std),
            "min": _round(d.min),
            "max": _round(d.max),
            "histogram": {
                "bin_edges": [_round(e) for e in d.bin_edges],
                "relative_frequency": [_round(f) for f in d.relative_frequency],
            },
        },
    }


def _write_json(document: dict, path: Path) -> None:
    """Write deterministically: fixed separators, no trailing whitespace, newline at end."""
    text = json.dumps(document, indent=2, ensure_ascii=False, separators=(",", ": "))
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def export_track(seed: int, out_dir: Path | None = None,
                 profile: VehicleProfile | None = None) -> Path:
    """Generate, validate and write one track. Raises on a rejected seed and writes nothing."""
    profile = profile or build_profile()
    out_dir = Path(out_dir) if out_dir is not None else TRACKS_DIR

    line = centre_line(draw_parameters(seed))
    document = build_track_document(line, profile)  # raises before anything is created

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"seed_{seed}.json"
    _write_json(document, path)

    return path


def generate_batch(seeds, out_dir: Path | None = None, name: str = "batch",
                   profile: VehicleProfile | None = None) -> BatchReport:
    """Export every seed that passes, and record every one that does not.

    A rejected seed is never retried with adjusted parameters. Its reason is kept so the batch
    report can state why the acceptance rate is what it is.
    """
    profile = profile or build_profile()
    seeds = list(seeds)

    accepted: list[int] = []
    rejections: list[tuple[int, str]] = []

    for seed in seeds:
        try:
            export_track(seed, out_dir=out_dir, profile=profile)
        except SeedRejected as rejected:
            rejections.append((rejected.seed, rejected.reason))
        else:
            accepted.append(seed)

    return BatchReport(
        name=name,
        requested=len(seeds),
        accepted_seeds=accepted,
        rejections=rejections,
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def pooled_bound(seeds, profile: VehicleProfile | None = None) -> matching.DemandBound:
    """The batch-scope bound SC-010 is judged on.

    No per-seed report answers SC-010: twenty tracks each missing in a different direction pool
    to a good result while twenty missing the same way do not, and only the pooled figure
    separates those cases.
    """
    profile = profile or build_profile()
    pooled = np.concatenate([
        matching.required_steering(centre_line(draw_parameters(s)), profile).required_steer
        for s in seeds])

    return matching.demand_bound(
        pooled, scope="batch", n_seeds_pooled=len(list(seeds)))


def write_split(reports: dict[str, BatchReport],
                out_path: Path | None = None) -> Path:
    """Record which seeds went to which split, and assert the two never overlap.

    A seed appearing in both train and eval would leak the evaluation set into training, and
    the resulting score would measure memorisation. Asserted here rather than checked by
    discipline, because the failure is invisible in every downstream number (FR-022, SC-016).
    """
    out_path = out_path or (RESULTS_DIR / "seed_split.json")

    sets = {name: set(report.accepted_seeds) for name, report in reports.items()}
    names = sorted(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = sets[a] & sets[b]
            if overlap:
                raise ValueError(f"{a} and {b} share seeds: {sorted(overlap)}")

    document = {
        name: {
            "accepted_seeds": sorted(reports[name].accepted_seeds),
            "requested": reports[name].requested,
            "acceptance_rate": _round(reports[name].acceptance_rate),
        }
        for name in names
    }
    document["disjoint"] = True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(document, out_path)

    return out_path


def write_batch_report(reports: dict[str, BatchReport],
                       out_path: Path | None = None,
                       profile: VehicleProfile | None = None) -> Path:
    """Write the acceptance rate, every rejection, and the pooled bound SC-010 is judged on."""
    profile = profile or build_profile()
    out_path = out_path or (RESULTS_DIR / "batch_report.md")

    lines = ["# Track batch report", ""]

    for name in sorted(reports):
        report = reports[name]
        rate = 100 * report.acceptance_rate
        lines += [
            f"## {name}",
            "",
            f"- Requested: {report.requested}",
            f"- Accepted: {len(report.accepted_seeds)} ({rate:.0f} percent)",
            f"- Generated: {report.generated_utc}",
            "",
        ]

        if report.rejections:
            lines += ["### Rejections", ""]
            lines += [f"- seed {seed}: {reason}" for seed, reason in report.rejections]
            lines.append("")
        else:
            lines += ["No seed was rejected.", ""]

        if rate < 50:
            lines += [
                "**Acceptance is below 50 percent.** SC-011 treats this as a design finding "
                "rather than a tuning problem: the radius floor and the statistical target "
                "are pulling against each other. The floor is not to be lowered to fix it.",
                "",
            ]

        if report.accepted_seeds:
            bound = pooled_bound(report.accepted_seeds, profile=profile)
            verdict = "within bound" if bound.within_bound else "OUTSIDE BOUND"
            lines += [
                "### Pooled steering demand",
                "",
                f"Judged on the pooled figure over {bound.n_seeds_pooled} seeds, never on "
                "per-seed ones: twenty tracks each missing in a different direction pool to a "
                "good result while twenty missing the same way do not.",
                "",
            ]

            # SC-010 requires at least 20 pooled seeds. A figure from fewer is still worth
            # reporting, but saying so is what stops it being quoted as if it settled the
            # criterion.
            if bound.n_seeds_pooled >= 20:
                lines += ["This split **does** satisfy SC-010's pooling requirement.", ""]
            else:
                lines += [
                    f"**Not quotable against SC-010.** That criterion requires at least 20 "
                    f"pooled seeds and this split has {bound.n_seeds_pooled}. The figures "
                    "below describe this split only.",
                    "",
                ]

            lines += [
                f"- Verdict: **{verdict}**",
                f"- Peak demand: {bound.max_required:.3f} against a human maximum of "
                f"{bound.reference_max:.3f}",
                f"- Samples above the human maximum: {bound.exceedance_fraction:.4f}",
                "",
                "| percentile | gap against human |",
                "|---|---|",
            ]
            lines += [f"| P{p:g} | {g:+.3f} |"
                      for p, g in sorted(bound.percentile_gaps.items())]
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m python.track.export",
        description="Generate track files from seeds.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", type=int, help="Export one seed.")
    group.add_argument("--batch", choices=("train", "eval", "all"),
                       help="Export a configured split. 'all' also writes the split file and "
                            "the batch report, which need both splits to be meaningful.")
    parser.add_argument("--out-dir", type=Path, default=None)

    args = parser.parse_args(argv)
    profile = build_profile()

    if args.seed is not None:
        try:
            path = export_track(args.seed, out_dir=args.out_dir, profile=profile)
        except SeedRejected as rejected:
            print(f"REJECTED {rejected}")
            return 1
        print(f"wrote {path}")
        return 0

    splits = {"train": config.TRAIN_SEEDS, "eval": config.EVAL_SEEDS}
    wanted = splits if args.batch == "all" else {args.batch: splits[args.batch]}

    reports: dict[str, BatchReport] = {}
    for name, seeds in wanted.items():
        report = generate_batch(seeds, out_dir=args.out_dir, name=name, profile=profile)
        reports[name] = report

        print(f"{name}: {len(report.accepted_seeds)}/{report.requested} accepted "
              f"({100 * report.acceptance_rate:.0f}%)")
        for seed, reason in report.rejections:
            print(f"  seed {seed}: {reason}")

        if report.accepted_seeds:
            bound = pooled_bound(report.accepted_seeds, profile=profile)
            verdict = "within bound" if bound.within_bound else "OUTSIDE BOUND"
            print(f"  pooled demand over {bound.n_seeds_pooled} seeds: {verdict}, "
                  f"max {bound.max_required:.3f} against a human {bound.reference_max:.3f}")

    # The split file and the report describe the relationship BETWEEN the splits, so they are
    # only written when both were generated. Writing them from one split would record a
    # disjointness claim that was never tested.
    if args.batch == "all":
        print(f"wrote {write_split(reports)}")
        print(f"wrote {write_batch_report(reports, profile=profile)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
