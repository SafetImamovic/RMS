"""The demonstration's provenance, as a test rather than as a promise (feature 009, T026).

FR-003 says the demonstration is recorded from **training seeds only**. The ten evaluation
seeds are the criterion this project has failed three times, and an expert demonstrated on
them would answer a different question from the one the milestone asks.

That is easy to state and easy to violate silently: the recording scene's `SweepRunner` has a
`seedSet` field, and flipping it to `Eval` would produce a file that looks entirely normal.
So the seed list is committed beside the file and checked against the split here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DEMO_SEEDS = REPO / "results" / "rl" / "demo_seeds.json"
SPLIT = REPO / "results" / "tracks" / "seed_split.json"


@pytest.fixture(scope="module")
def demo() -> dict:
    return json.loads(DEMO_SEEDS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def split() -> dict:
    return json.loads(SPLIT.read_text(encoding="utf-8"))


def test_every_demonstrated_seed_is_a_training_seed(demo: dict, split: dict) -> None:
    train = set(split["train"]["accepted_seeds"])
    assert set(demo["seeds"]) <= train


def test_no_demonstrated_seed_is_an_evaluation_seed(demo: dict, split: dict) -> None:
    """The one that matters. A leak here contaminates the milestone criterion itself."""
    held_out = set(split["eval"]["accepted_seeds"])
    assert not (set(demo["seeds"]) & held_out)


def test_the_seed_list_has_no_duplicates(demo: dict) -> None:
    """A repeated seed would weight the imitation toward one track without saying so."""
    assert len(demo["seeds"]) == len(set(demo["seeds"]))


def test_the_recorded_count_matches_the_list(demo: dict) -> None:
    assert demo["seed_count"] == len(demo["seeds"])


def test_every_recorded_run_completed(demo: dict) -> None:
    """A demonstration of a failing expert is not a demonstration worth imitating."""
    assert demo["runs_completed"] == demo["seed_count"]
    assert demo["wall_contacts_total"] == 0


def test_the_sample_rate_is_the_agents_clock_not_the_drivers(demo: dict) -> None:
    """Research R2: the recorder cannot sample faster than the decision period."""
    assert demo["decision_period"] == 4
    assert demo["sample_rate_hz"] == pytest.approx(12.5)


def test_the_overrun_is_declared(demo: dict) -> None:
    """The cap recorded past the sweep. Small, known, and written down rather than found later."""
    assert demo["recorded_steps"] >= demo["steps_attributable_to_sweep"]
    overrun = demo["recorded_steps"] - demo["steps_attributable_to_sweep"]
    assert overrun / demo["recorded_steps"] < 0.02
