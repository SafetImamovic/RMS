"""The split is the one thing in M4 that can invalidate every number downstream.

If a training frame sits beside a validation frame, the reported validation error measures
interpolation between near-duplicates rather than generalisation, and nothing built on it
means anything. These tests exist so that failure is loud rather than invisible.

Both directions of evidence throughout, per `contracts/bc-module-api.md`: for each rule, a case
that must pass and a case that must fail. A suite that only shows the happy path proves the
code runs, not that it is right.
"""

from __future__ import annotations

import json

import pytest

from python.bc import config, split
from python.eda import loader


@pytest.fixture(scope="module")
def dataset():
    try:
        return loader.load_track(config.DATASET_NAME)
    except FileNotFoundError:
        pytest.skip("dataset not present; it is git-ignored and supplied separately")


@pytest.fixture(scope="module")
def plan(dataset):
    return split.plan_split(dataset)


# -----------------------------------------------------------------------------------------
# The guarantee
# -----------------------------------------------------------------------------------------


def test_no_training_frame_sits_inside_the_guard(dataset, plan):
    """SC-001 and FR-004, measured rather than inferred from the construction.

    A guard applied correctly and a guard applied to the wrong array look identical until the
    result is measured.
    """
    split.verify_no_leak(dataset, plan)
    assert plan.min_train_val_gap_s >= plan.guard_seconds - 1e-6


def test_a_frame_inside_the_guard_is_rejected(dataset, plan):
    """The failing direction. Move one training row into the validation side's guard zone.

    Without this the suite would only show that a correct split passes, which is also true of
    a checker that always returns None.
    """
    broken = split.SplitPlan(
        seed=plan.seed,
        n_blocks=plan.n_blocks,
        n_holdout=plan.n_holdout,
        guard_seconds=plan.guard_seconds,
        val_fraction_target=plan.val_fraction_target,
        train_rows=list(plan.train_rows),
        val_rows=list(plan.val_rows),
        guard_rows=list(plan.guard_rows),
        block_bounds=list(plan.block_bounds),
    )

    # Promote a guard row into training. Guard rows are by definition within the guard of a
    # validation row, so this is exactly the leak the check exists to catch.
    moved = broken.guard_rows[len(broken.guard_rows) // 2]
    broken.guard_rows.remove(moved)
    broken.train_rows = sorted(broken.train_rows + [moved])
    broken.min_train_val_gap_s = split.measure_min_gap(dataset, broken)

    with pytest.raises(split.SplitError) as caught:
        split.verify_no_leak(dataset, broken)

    message = str(caught.value)
    assert "guard" in message
    assert "generalisation" in message


# -----------------------------------------------------------------------------------------
# The partition
# -----------------------------------------------------------------------------------------


def test_every_row_is_trained_validated_or_guarded(dataset, plan):
    """No frame silently disappears.

    A vanished row changes the denominator of every statistic computed later, which is the
    class of error feature 002 kept finding in this dataset.
    """
    total = plan.n_train_rows + plan.n_val_rows + plan.n_guard_rows
    assert total == len(dataset.df)


def test_the_three_row_sets_are_disjoint(plan):
    train = set(plan.train_rows)
    val = set(plan.val_rows)
    guard = set(plan.guard_rows)

    assert not train & val
    assert not train & guard
    assert not val & guard


def test_overlapping_sets_are_rejected(dataset, plan):
    """The failing direction for the partition rule."""
    broken = split.SplitPlan(
        seed=plan.seed,
        n_blocks=plan.n_blocks,
        n_holdout=plan.n_holdout,
        guard_seconds=plan.guard_seconds,
        val_fraction_target=plan.val_fraction_target,
        train_rows=list(plan.train_rows) + [plan.val_rows[0]],
        val_rows=list(plan.val_rows),
        guard_rows=list(plan.guard_rows),
        block_bounds=list(plan.block_bounds),
        min_train_val_gap_s=plan.min_train_val_gap_s,
    )

    with pytest.raises(split.SplitError) as caught:
        split.verify_no_leak(dataset, broken)

    assert "share" in str(caught.value)


def test_an_empty_validation_side_is_rejected(dataset):
    """Holding out zero blocks is a configuration mistake, not a valid split."""
    with pytest.raises(split.SplitError) as caught:
        split.plan_split(dataset, n_holdout=0)

    assert "empty" in str(caught.value)


# -----------------------------------------------------------------------------------------
# Determinism
# -----------------------------------------------------------------------------------------


def test_the_same_seed_produces_an_identical_file(dataset, tmp_path):
    """SC-002. Compared as text, not as parsed objects.

    Two files that parse to the same structure but differ textually fail the check that
    actually matters, which is whether a reader can see in a diff that nothing moved.
    """
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"

    split.write_split(split.plan_split(dataset, seed=config.SEED), first)
    split.write_split(split.plan_split(dataset, seed=config.SEED), second)

    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_a_written_split_reads_back_unchanged(dataset, tmp_path):
    path = tmp_path / "split.json"
    original = split.plan_split(dataset)
    split.write_split(original, path)
    restored = split.read_split(path)

    assert restored.train_rows == original.train_rows
    assert restored.val_rows == original.val_rows
    assert restored.guard_rows == original.guard_rows
    assert restored.min_train_val_gap_s == pytest.approx(original.min_train_val_gap_s)


def test_the_written_file_carries_the_rule_that_produced_it(dataset, tmp_path):
    """The file has to explain itself. A reader should not need the code to know the rule."""
    path = tmp_path / "split.json"
    split.write_split(split.plan_split(dataset), path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    for key in (
        "seed", "n_blocks", "n_holdout", "guard_seconds",
        "val_fraction_target", "val_fraction_actual", "min_train_val_gap_s",
    ):
        assert key in payload, f"{key} missing from the written split"


# -----------------------------------------------------------------------------------------
# Reported, not forced
# -----------------------------------------------------------------------------------------


def test_the_validation_fraction_is_reported_rather_than_forced(plan):
    """The achieved fraction is allowed to miss the target, and that is the point.

    This test deliberately does NOT assert equality with the target. Blocks are integer-sized
    and the guard eats into them, so hitting 0.20 exactly would mean moving a boundary to
    satisfy a number, which is fitting the split to a target instead of to the data.
    """
    actual = plan.val_fraction_actual
    target = plan.val_fraction_target

    assert 0.10 < actual < target, (
        "the achieved fraction should sit below the target, since the guard only ever removes "
        f"validation rows; got {actual:.4f} against {target:.2f}"
    )


def test_held_out_blocks_are_spread_rather_than_adjacent():
    """Two adjacent held-out blocks are one long stretch of road, possibly a single corner."""
    chosen = sorted(split.held_out_blocks(10, 2))
    assert chosen == [0, 5]

    gaps = [b - a for a, b in zip(chosen, chosen[1:])]
    assert all(gap > 1 for gap in gaps)


def test_a_session_smaller_than_the_block_count_is_rejected(dataset):
    """Cutting 10,615 rows into 20,000 blocks is a mistake, not an empty-block edge case."""
    with pytest.raises(split.SplitError) as caught:
        split.plan_split(dataset, n_blocks=50_000)

    assert "fewer than" in str(caught.value)
