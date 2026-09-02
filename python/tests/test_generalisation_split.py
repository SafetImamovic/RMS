"""The third seed set, and the property that is the whole reason it exists.

**Disjointness is checked from the file, not inferred from the seed ranges.** The ranges are
1 to 40, 1001 to 1010 and 2001 to 2040, so an overlap looks impossible and that is exactly why the
check is worth having: the split file is written by a function that takes whatever reports it is
handed, and a mistake there would produce a plausible file that leaks one set into another. Feature
003 asserted this for the first pair for the same reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT = REPO_ROOT / "results" / "tracks" / "seed_split.json"
TRACKS = REPO_ROOT / "unity" / "SelfDrivingSim" / "Assets" / "Tracks"

pytestmark = pytest.mark.skipif(not SPLIT.exists(), reason="seed split not generated here")

SETS = ("train", "eval", "generalisation")


@pytest.fixture(scope="module")
def split() -> dict:
    return json.loads(SPLIT.read_text(encoding="utf-8"))


def test_the_file_carries_all_three_sets(split: dict) -> None:
    for name in SETS:
        assert name in split, f"{name} missing from {SPLIT.name}"
        assert split[name]["accepted_seeds"], f"{name} has no accepted seeds"


def test_the_three_sets_are_pairwise_disjoint(split: dict) -> None:
    """FR-001, SC-001. Read off the file, never off the ranges."""
    seeds = {name: set(split[name]["accepted_seeds"]) for name in SETS}
    for i, a in enumerate(SETS):
        for b in SETS[i + 1:]:
            overlap = seeds[a] & seeds[b]
            assert not overlap, f"{a} and {b} share seeds {sorted(overlap)}"

    assert split["disjoint"] is True


def test_every_accepted_seed_has_a_track_file(split: dict) -> None:
    """A sweep that dies twenty minutes in has spent its budget learning what a listing knew."""
    missing = [
        seed
        for name in SETS
        for seed in split[name]["accepted_seeds"]
        if not (TRACKS / f"seed_{seed}.json").exists()
    ]
    assert not missing, f"no track file for {missing}"


def test_no_rejected_seed_left_a_track_file_behind(split: dict) -> None:
    """A rejected seed must leave nothing, or a later sweep could pick up a track the acceptance
    bound refused. Feature 003's rule is that a rejected seed is never retried; a stale file on
    disk would be a retry by accident."""
    accepted = {seed for name in SETS for seed in split[name]["accepted_seeds"]}
    rejected = [seed for seed in range(2001, 2041) if seed not in accepted]

    assert rejected, "the generalisation batch rejected nothing, which the 0.85 rate makes unlikely"
    stray = [seed for seed in rejected if (TRACKS / f"seed_{seed}.json").exists()]
    assert not stray, f"rejected seeds still have track files: {stray}"


def test_the_generalisation_set_was_accepted_at_the_same_bound(split: dict) -> None:
    """FR-002. A set generated under a looser bound would answer an easier question.

    The acceptance rate is the visible consequence of the bound. Train ran 0.85 and this set ran
    0.825 on the same floor, which is the agreement that says no parameter moved.
    """
    assert split["generalisation"]["requested"] == 40
    assert 0.7 <= split["generalisation"]["acceptance_rate"] <= 0.95
    assert len(split["generalisation"]["accepted_seeds"]) == 33
