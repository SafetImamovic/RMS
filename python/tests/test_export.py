"""Tests for track file export.

The load-bearing test is `test_two_runs_produce_byte_identical_files`. A committed track file
is only reviewable in a diff if regenerating it changes nothing, and SC-007 asks for exactly
that.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from python.track import config, export, generator, geometry, matching, vehicle

PROFILE = vehicle.build_profile()
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "tracks"


# -----------------------------------------------------------------------------------------
# Reproducibility (SC-007)
# -----------------------------------------------------------------------------------------


def test_two_runs_produce_byte_identical_files(out_dir):
    a = out_dir / "a"
    b = out_dir / "b"

    export.generate_batch(range(1, 6), out_dir=a)
    export.generate_batch(range(1, 6), out_dir=b)

    written = sorted(p.name for p in a.glob("*.json"))
    assert written, "no files were written"

    for name in written:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_the_file_carries_no_timestamp(out_dir):
    """A generation time inside the file would make byte-identical output impossible.

    It is recorded on the BatchReport instead, where reproducibility is not claimed. This is
    a deliberate departure from the illustrative shape in the schema contract, and it is what
    lets a committed track be reviewed in a diff.
    """
    path = export.export_track(1, out_dir=out_dir)
    document = json.loads(path.read_text(encoding="utf-8"))

    assert "generated_utc" not in document
    assert "timestamp" not in json.dumps(document).lower()


def test_files_are_identical_across_processes(out_dir):
    """Determinism has to survive a fresh interpreter, not only a fresh call."""
    local = export.export_track(3, out_dir=out_dir).read_bytes()

    other = out_dir / "subprocess"
    subprocess.run(
        [sys.executable, "-m", "python.track.export", "--seed", "3",
         "--out-dir", str(other)],
        cwd=REPO, capture_output=True, text=True, check=True)

    assert (other / "seed_3.json").read_bytes() == local


# -----------------------------------------------------------------------------------------
# Schema
# -----------------------------------------------------------------------------------------


def test_the_document_matches_the_schema_shape(out_dir):
    document = json.loads(export.export_track(1, out_dir=out_dir).read_text(encoding="utf-8"))

    for key in ("schema_version", "seed", "generator", "vehicle_profile", "width_m",
                "total_length_m", "centre_line", "checkpoints", "geometry_report",
                "match_report", "demand_bound", "required_steer_descriptives"):
        assert key in document, f"missing {key}"

    assert document["schema_version"] == export.SCHEMA_VERSION
    assert document["seed"] == 1


def test_the_generator_block_can_rebuild_the_centre_line(out_dir):
    """The block is auditable, not decorative: it must actually regenerate the points."""
    document = json.loads(export.export_track(4, out_dir=out_dir).read_text(encoding="utf-8"))
    block = document["generator"]

    rebuilt = generator.centre_line(generator.TrackSeed(
        seed=4, amplitude=block["amplitude"], phases=tuple(block["phases"])))

    stored_x = np.array([p["x"] for p in document["centre_line"]])
    # Rebuilt from rounded parameters, so agreement is close rather than exact.
    assert np.allclose(rebuilt.x, stored_x, atol=1e-3)


def test_the_centre_line_does_not_repeat_its_first_point(out_dir):
    document = json.loads(export.export_track(5, out_dir=out_dir).read_text(encoding="utf-8"))
    points = document["centre_line"]

    assert len(points) == config.SAMPLES_PER_TRACK
    assert (points[0]["x"], points[0]["y"]) != (points[-1]["x"], points[-1]["y"])


def test_checkpoints_are_monotonic_in_arc_length(out_dir):
    document = json.loads(export.export_track(5, out_dir=out_dir).read_text(encoding="utf-8"))
    s = [c["s"] for c in document["checkpoints"]]

    assert len(s) == config.N_CHECKPOINTS
    assert s == sorted(s)
    assert [c["index"] for c in document["checkpoints"]] == list(range(len(s)))


def test_the_profile_travels_with_the_track(out_dir):
    """A track validated for one car is not valid for another."""
    document = json.loads(export.export_track(6, out_dir=out_dir).read_text(encoding="utf-8"))
    block = document["vehicle_profile"]

    assert block["wheelbase_m"] == pytest.approx(PROFILE.wheelbase_m)
    assert block["r_floor_m"] == pytest.approx(PROFILE.r_floor_m, abs=1e-6)
    assert block["max_required_steer"] == pytest.approx(PROFILE.max_required_steer, abs=1e-6)


def test_the_descriptives_block_is_complete(out_dir):
    """Principle IX is not optional; a file missing a field must be a loader failure."""
    document = json.loads(export.export_track(7, out_dir=out_dir).read_text(encoding="utf-8"))
    block = document["required_steer_descriptives"]

    for key in ("n", "mean", "variance", "std", "min", "max", "histogram"):
        assert key in block, f"missing {key}"

    assert block["n"] == config.SAMPLES_PER_TRACK
    assert sum(block["histogram"]["relative_frequency"]) == pytest.approx(1.0, abs=1e-4)
    assert len(block["histogram"]["bin_edges"]) == \
        len(block["histogram"]["relative_frequency"]) + 1


def test_no_p_value_appears_anywhere_in_a_written_file(out_dir):
    """By contract, FR-019."""
    text = export.export_track(8, out_dir=out_dir).read_text(encoding="utf-8").lower()

    for banned in ("p_value", "pvalue", "\"p\":", "significance"):
        assert banned not in text, f"a written track file contains {banned}"


def test_the_match_report_carries_the_three_scales(out_dir):
    document = json.loads(export.export_track(9, out_dir=out_dir).read_text(encoding="utf-8"))
    scales = document["match_report"]["scales"]

    assert set(scales) == {"self_consistency", "structureless", "human_to_human"}
    assert scales["structureless"] == pytest.approx(config.W1_STRUCTURELESS, abs=1e-6)


def test_the_bound_block_is_what_records_acceptance(out_dir):
    """SC-010 is judged on demand_bound, not on match_report."""
    document = json.loads(export.export_track(9, out_dir=out_dir).read_text(encoding="utf-8"))
    bound = document["demand_bound"]

    assert bound["within_bound"] is True
    assert bound["exceedance_fraction"] == 0.0
    assert bound["max_required"] < bound["reference_max"]
    assert all(g <= 0.0 for g in bound["percentile_gaps"].values())


# -----------------------------------------------------------------------------------------
# Rejection
# -----------------------------------------------------------------------------------------


def test_a_rejected_seed_produces_no_file_and_one_recorded_rejection(out_dir, monkeypatch):
    """Nothing is written for a seed that fails, and the reason is kept."""
    real = geometry.check_geometry

    def failing(line, profile):
        report = real(line, profile)
        if line.seed == 2:
            return geometry.GeometryReport(
                **{**report.__dict__, "radius_ok": False, "min_radius_m": 1.0})
        return report

    monkeypatch.setattr(geometry, "check_geometry", failing)

    report = export.generate_batch([1, 2, 3], out_dir=out_dir)

    assert report.accepted_seeds == [1, 3]
    assert len(report.rejections) == 1
    assert report.rejections[0][0] == 2
    assert "floor" in report.rejections[0][1]
    assert not (out_dir / "seed_2.json").exists()
    assert report.acceptance_rate == pytest.approx(2 / 3)


def test_export_track_raises_and_writes_nothing_for_a_rejected_seed(out_dir, monkeypatch):
    monkeypatch.setattr(
        geometry, "check_geometry",
        lambda line, profile: geometry.GeometryReport(
            seed=line.seed, min_radius_m=1.0, r_floor_m=profile.r_floor_m, radius_ok=False,
            self_intersects=False, min_separation_m=50.0, separation_ok=True,
            total_length_m=line.total_length_m))

    with pytest.raises(export.SeedRejected):
        export.export_track(1, out_dir=out_dir)

    assert not out_dir.exists() or not list(out_dir.glob("*.json"))


def test_a_file_claiming_radius_ok_false_can_never_be_produced(out_dir):
    """The contradiction the schema forbids: a file whose own report says it is unusable."""
    export.generate_batch(range(1, 11), out_dir=out_dir)

    for path in out_dir.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["geometry_report"]["radius_ok"] is True, path.name
        assert document["geometry_report"]["separation_ok"] is True, path.name
        assert document["geometry_report"]["self_intersects"] is False, path.name


def test_a_rejected_seed_is_never_retried_with_adjusted_parameters():
    """Resampling until something passes would hide the acceptance rate (FR-020, research C7)."""
    source = (REPO / "python" / "track" / "export.py").read_text(encoding="utf-8")

    for banned in ("while not", "retry", "resample", "attempt +="):
        assert banned not in source, f"export.py appears to retry: {banned}"


def test_nothing_outside_the_output_directory_is_written(out_dir, tmp_path):
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    export.generate_batch(range(1, 4), out_dir=out_dir)
    after = {p for p in tmp_path.rglob("*") if p.is_file()}

    for path in after - before:
        assert out_dir in path.parents, f"wrote outside the output directory: {path}"


# -----------------------------------------------------------------------------------------
# Batch and pooled bound
# -----------------------------------------------------------------------------------------


def test_the_batch_report_records_the_acceptance_rate(out_dir):
    report = export.generate_batch(config.TRAIN_SEEDS, out_dir=out_dir, name="train")

    assert report.requested == len(list(config.TRAIN_SEEDS))
    assert report.acceptance_rate == pytest.approx(
        len(report.accepted_seeds) / report.requested)
    assert report.name == "train"
    assert report.generated_utc.endswith("Z")


def test_the_acceptance_rate_clears_the_stated_minimum(out_dir):
    """SC-011: below 50 percent is a design finding, not a tuning problem."""
    report = export.generate_batch(config.TRAIN_SEEDS, out_dir=out_dir, name="train")

    assert report.acceptance_rate >= 0.50


def test_a_batch_of_twenty_or_more_seeds_is_within_the_bound():
    """SC-010, judged on the pooled figure and never on per-seed ones."""
    bound = export.pooled_bound(config.TRAIN_SEEDS)

    assert bound.n_seeds_pooled >= 20
    assert bound.within_bound is True
    assert bound.worst_percentile is None


# -----------------------------------------------------------------------------------------
# Command line
# -----------------------------------------------------------------------------------------


def test_the_cli_exports_one_seed(out_dir, capsys):
    assert export.main(["--seed", "1", "--out-dir", str(out_dir)]) == 0
    assert (out_dir / "seed_1.json").exists()
    assert "wrote" in capsys.readouterr().out


def test_the_cli_exports_a_named_split(out_dir, capsys):
    assert export.main(["--batch", "eval", "--out-dir", str(out_dir)]) == 0

    written = sorted(int(p.stem.split("_")[1]) for p in out_dir.glob("*.json"))
    assert set(written).issubset(set(config.EVAL_SEEDS))
    assert "accepted" in capsys.readouterr().out


def test_the_report_says_when_a_split_is_too_small_to_quote_against_sc010(out_dir, tmp_path):
    """The eval split has 10 seeds and SC-010 requires 20. Saying so is the point."""
    reports = {
        "train": export.generate_batch(config.TRAIN_SEEDS, out_dir=out_dir, name="train"),
        "eval": export.generate_batch(config.EVAL_SEEDS, out_dir=out_dir, name="eval"),
    }
    text = export.write_batch_report(
        reports, out_path=tmp_path / "report.md").read_text(encoding="utf-8")

    assert "Not quotable against SC-010" in text
    assert "does** satisfy SC-010" in text


def test_the_split_file_records_disjoint_sets(out_dir, tmp_path):
    reports = {
        "train": export.generate_batch(config.TRAIN_SEEDS, out_dir=out_dir, name="train"),
        "eval": export.generate_batch(config.EVAL_SEEDS, out_dir=out_dir, name="eval"),
    }
    document = json.loads(
        export.write_split(reports, out_path=tmp_path / "split.json")
        .read_text(encoding="utf-8"))

    assert document["disjoint"] is True
    assert not set(document["train"]["accepted_seeds"]) & set(
        document["eval"]["accepted_seeds"])


def test_overlapping_splits_are_refused(out_dir):
    """A seed in both splits leaks evaluation into training, invisibly."""
    shared = export.generate_batch([1, 2, 3], out_dir=out_dir, name="train")

    with pytest.raises(ValueError, match="share seeds"):
        export.write_split({"train": shared, "eval": shared}, out_path=out_dir / "s.json")


def test_the_cli_requires_one_of_seed_or_batch():
    with pytest.raises(SystemExit):
        export.main([])
