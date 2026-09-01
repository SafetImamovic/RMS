"""The trace manifest is the only trustworthy way to select feature 009's traces.

Every M5 number is computed from files this manifest names, so a defect here is a defect in
everything downstream and would not announce itself. These tests pin the two properties that make
the mapping believable: that it is complete and disjoint, and that it reproduces a coincidence no
accidental alignment would.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "results" / "rl" / "trace_manifest.json"

pytestmark = pytest.mark.skipif(
    not MANIFEST.exists(), reason="trace manifest not generated in this checkout"
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_every_sweep_names_ten_existing_traces(manifest: dict) -> None:
    """Ten runs per sweep, ten files, all present on disk."""
    drive_logs = REPO_ROOT / manifest["trace_dir"]
    assert len(manifest["sweeps"]) == 6

    for sweep in manifest["sweeps"]:
        label = f"{sweep['run_id']} {sweep['inference']}"
        assert len(sweep["traces"]) == 10, f"{label} names {len(sweep['traces'])} traces"
        assert len(sweep["seeds"]) == 10, f"{label} names {len(sweep['seeds'])} seeds"
        for name in sweep["traces"]:
            assert (drive_logs / name).is_file(), f"{label} names missing trace {name}"


def test_no_trace_belongs_to_two_sweeps(manifest: dict) -> None:
    """A file bound twice means one sweep is reading another sweep's driving."""
    seen: dict[str, str] = {}
    for sweep in manifest["sweeps"]:
        label = f"{sweep['run_id']} {sweep['inference']}"
        for name in sweep["traces"]:
            assert name not in seen, f"{name} claimed by both {seen[name]} and {label}"
            seen[name] = label
    assert len(seen) == 60


def test_every_named_eval_csv_exists(manifest: dict) -> None:
    for sweep in manifest["sweeps"]:
        assert (REPO_ROOT / sweep["eval_csv"]).is_file(), sweep["eval_csv"]


def test_seeds_are_the_ten_held_out_seeds_in_order(manifest: dict) -> None:
    """Seed order is what binds trace N to evaluation row N. If it drifts, the pairing is wrong."""
    expected = list(range(1001, 1011))
    for sweep in manifest["sweeps"]:
        assert sweep["seeds"] == expected, f"{sweep['run_id']} {sweep['inference']}"


def test_each_trace_duration_matches_its_evaluation_row(manifest: dict) -> None:
    """The property the manifest was built on, re-checked against the files themselves.

    Built and verified are not the same thing: the generator could bind correctly and the manifest
    could then be edited, or the traces replaced. This reads both sides off disk.
    """
    drive_logs = REPO_ROOT / manifest["trace_dir"]
    tolerance = 0.06

    for sweep in manifest["sweeps"]:
        rows = pd.read_csv(REPO_ROOT / sweep["eval_csv"])
        for name, (_, row) in zip(sweep["traces"], rows.iterrows()):
            trace = pd.read_csv(drive_logs / name, usecols=["t"])
            last_t = float(trace["t"].iloc[-1])
            want = float(row["duration_s"])
            assert abs(last_t - want) < tolerance, (
                f"{sweep['run_id']} {sweep['inference']} seed {int(row['seed'])}: "
                f"trace {name} ends at {last_t}s, run record says {want}s"
            )


def test_the_seed_1009_crash_corroborates_the_mapping(manifest: dict) -> None:
    """Feature 009's one lost run is the coincidence that makes the mapping believable.

    Seed 42 under sampling inference hit a barrier on seed 1009 at 7.16 s where every other run of
    that sweep took about 63 s. Its trace therefore opens about 2 s after its predecessor rather
    than the usual 16 s of real time at `timeScale` 4. An alignment that happened to be off by one
    file would not reproduce a 2 s gap sitting exactly on the short run.
    """
    from python.rl.trace_manifest import stamp_of

    sweep = next(
        s
        for s in manifest["sweeps"]
        if s["run_id"] == "ppo_car_009_bc" and s["inference"] == "sampling"
    )
    rows = pd.read_csv(REPO_ROOT / sweep["eval_csv"])

    crashed = rows.index[rows["end_reason"] == "WallContact"].tolist()
    assert crashed == [8], "expected exactly one wall contact, at seed 1009"
    index = crashed[0]

    assert float(rows["duration_s"].iloc[index]) < 10.0
    assert rows["seed"].iloc[index] == 1009

    stamps = [stamp_of(name) for name in sweep["traces"]]
    gaps = [(stamps[i + 1] - stamps[i]).total_seconds() for i in range(len(stamps) - 1)]

    # The gap that FOLLOWS the short run is the short one: the next trace opens as soon as the
    # crashed run ends.
    short_gap = gaps[index]
    others = [g for i, g in enumerate(gaps) if i != index]
    assert short_gap < 5.0, f"gap after the crashed run is {short_gap}s, expected under 5"
    assert min(others) > 10.0, f"another gap is {min(others)}s, expected all over 10"
