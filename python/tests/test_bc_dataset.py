"""What the model is shown, and what target goes with it.

Three failures in this module would be invisible in a training run. A flip that mirrors the
image without negating the target teaches the car to steer into corners while the loss curve
looks ordinary. A silently skipped missing image changes the denominator of every statistic
that follows. An augmented sample reaching the validation set scores the model against a target
this project invented rather than against the human driver. None of the three announces itself,
so each one is asserted here.

Both directions of evidence throughout, per `contracts/bc-module-api.md`.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from python.bc import config, dataset, split
from python.eda import loader


@pytest.fixture(scope="module")
def track():
    try:
        return loader.load_track(config.DATASET_NAME)
    except FileNotFoundError:
        pytest.skip("dataset not present; it is git-ignored and supplied separately")


@pytest.fixture(scope="module")
def plan(track):
    return split.plan_split(track)


@pytest.fixture(scope="module")
def train_samples(track, plan):
    return dataset.build_samples(track, plan.train_rows, use_side_cameras=True)


@pytest.fixture(scope="module")
def val_samples(track, plan):
    return dataset.build_samples(track, plan.val_rows, use_side_cameras=False)


@pytest.fixture(scope="module")
def real_frame(track, val_samples):
    return dataset.preprocess(Image.open(dataset.image_path(track, val_samples[0])))


def synthetic_frame(seed: int = 0) -> np.ndarray:
    """A recorded-size RGB frame with structure, so a mirror test cannot pass by symmetry."""
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 256, size=(config.FRAME_HEIGHT, config.FRAME_WIDTH, 3))
    return frame.astype(np.uint8)


# -----------------------------------------------------------------------------------------
# The flip. Named by hand in Constitution Principle VIII.
# -----------------------------------------------------------------------------------------


def test_a_horizontal_flip_negates_the_steering_target(real_frame):
    """Checked on a non-zero value, so a sign error cannot hide behind zero.

    The constitution names this test explicitly, and the reason is that it is the one
    augmentation bug that trains happily: mirrored images paired with unmirrored targets teach
    the model to steer the wrong way, and the loss still falls.
    """
    target = 0.37

    flipped_seen = False
    for seed in range(50):
        image, steering = dataset.augment(real_frame, target, np.random.default_rng(seed))
        mirrored = np.array_equal(image[..., 1], real_frame[:, ::-1, 1])

        if mirrored:
            flipped_seen = True
            assert steering == pytest.approx(-target), (
                "the image was mirrored but the target was not negated"
            )
        else:
            assert steering == pytest.approx(target), (
                "the target was negated without the image being mirrored"
            )

    assert flipped_seen, "no flip occurred in 50 draws; the test proved nothing"


def test_the_flip_is_a_column_mirror_and_not_a_row_or_channel_one(real_frame):
    """Flipping the wrong axis still produces a plausible-looking array that still trains."""
    for seed in range(50):
        image, steering = dataset.augment(real_frame, 0.37, np.random.default_rng(seed))
        if steering < 0:
            # Chrominance channels are untouched by the brightness change, so they can be
            # compared exactly. Y cannot.
            assert np.array_equal(image[..., 1], real_frame[:, ::-1, 1])
            assert not np.array_equal(image[..., 1], real_frame[::-1, :, 1])
            return

    pytest.fail("no flip occurred in 50 draws")


def test_brightness_moves_luminance_only(real_frame):
    """The reason `preprocess` converts to YUV: a lighting change is one channel, not three.

    Compared against an unflipped draw, since a flip legitimately moves all three channels.
    """
    for seed in range(50):
        image, steering = dataset.augment(real_frame, 0.37, np.random.default_rng(seed))
        if steering > 0:  # no flip on this draw
            assert np.array_equal(image[..., 1], real_frame[..., 1])
            assert np.array_equal(image[..., 2], real_frame[..., 2])
            assert not np.array_equal(image[..., 0], real_frame[..., 0])
            return

    pytest.fail("every draw in 50 flipped; the test proved nothing")


def test_the_same_seed_reproduces_the_same_augmentation(real_frame):
    first = dataset.augment(real_frame, 0.42, np.random.default_rng(11))
    second = dataset.augment(real_frame, 0.42, np.random.default_rng(11))

    assert np.array_equal(first[0], second[0])
    assert first[1] == second[1]


def test_augment_does_not_mutate_its_input(real_frame):
    """An in-place augmentation would corrupt a cached frame for every later epoch."""
    before = real_frame.copy()
    dataset.augment(real_frame, 0.42, np.random.default_rng(5))

    assert np.array_equal(real_frame, before)


def test_augment_never_touches_global_random_state(real_frame):
    """Matching the rule `python/track/generator.py` already follows.

    A function that reaches for the global generator makes every other seeded thing in the
    process irreproducible, and the symptom appears somewhere else entirely.
    """
    np.random.seed(1234)
    expected = np.random.random()

    np.random.seed(1234)
    dataset.augment(real_frame, 0.1, np.random.default_rng(0))

    assert np.random.random() == expected


# -----------------------------------------------------------------------------------------
# Preprocessing
# -----------------------------------------------------------------------------------------


def test_preprocess_returns_the_documented_shape():
    """Named by Constitution Principle VIII."""
    out = dataset.preprocess(synthetic_frame())

    assert out.shape == (config.INPUT_HEIGHT, config.INPUT_WIDTH, config.INPUT_CHANNELS)
    assert out.dtype == np.float32
    assert -1.0 <= out.min() and out.max() <= 1.0


def test_preprocess_is_deterministic():
    frame = synthetic_frame()

    assert np.array_equal(dataset.preprocess(frame), dataset.preprocess(frame))


def test_preprocess_accepts_an_array_and_a_pil_image_identically():
    frame = synthetic_frame()
    from_array = dataset.preprocess(frame)
    from_image = dataset.preprocess(Image.fromarray(frame, mode="RGB"))

    assert np.array_equal(from_array, from_image)


def test_preprocess_rejects_a_frame_of_the_wrong_size():
    """The crop rows are positions in the recorded frame, so they mean nothing against another.

    Silently cropping a differently sized frame would keep the wrong band of the image and
    still return the documented shape, which is the version of this bug that survives review.
    """
    with pytest.raises(dataset.DatasetError, match="320x160"):
        dataset.preprocess(Image.new("RGB", (64, 64)))


def test_preprocess_rejects_an_array_with_the_wrong_channel_count():
    with pytest.raises(dataset.DatasetError, match="channels"):
        dataset.preprocess(np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 1), np.uint8))


def test_the_crop_removes_the_hood_and_the_sky():
    """Guards the measured rows against a later edit that reverts them to the convention.

    Asserted as a property rather than as two literals: the crop must keep the band research
    R9 measured, at full width.
    """
    assert config.CROP_TOP > 0
    assert config.CROP_BOTTOM < config.FRAME_HEIGHT
    assert config.CROP_BOTTOM - config.CROP_TOP == 77


# -----------------------------------------------------------------------------------------
# Samples and the camera offset
# -----------------------------------------------------------------------------------------


def test_no_validation_sample_is_augmented(val_samples):
    """FR-007, asserted over the real split rather than a hand-built example.

    A synthesised target is not a human target. Validating against one measures agreement with
    our own offset rule instead of with the driver.
    """
    assert val_samples, "the validation split produced no samples"
    assert not any(sample.is_augmented for sample in val_samples)
    assert all(sample.camera is dataset.Camera.CENTER for sample in val_samples)
    assert all(sample.camera_offset is None for sample in val_samples)


def test_a_center_sample_carries_the_recorded_value_unmodified(track, val_samples):
    recorded = track.df["steering"].to_numpy(dtype=float)

    for sample in val_samples[:200]:
        assert sample.steering == pytest.approx(recorded[sample.row_index])


def test_side_targets_are_the_recorded_value_plus_or_minus_the_drawn_offset(track,
                                                                            train_samples):
    recorded = track.df["steering"].to_numpy(dtype=float)
    low, high = config.CAMERA_OFFSET_RANGE
    limit_low, limit_high = config.STEERING_LIMITS

    checked = 0
    for sample in train_samples[:3000]:
        if not sample.is_augmented:
            continue

        assert low <= sample.camera_offset <= high
        sign = 1.0 if sample.camera is dataset.Camera.LEFT else -1.0
        expected = np.clip(
            recorded[sample.row_index] + sign * sample.camera_offset, limit_low, limit_high
        )
        assert sample.steering == pytest.approx(expected)
        checked += 1

    assert checked > 0, "no side-camera samples were examined"


def test_clipping_is_exercised_at_both_extremes(track, train_samples):
    """Both rails, on the real recording rather than on a constructed row.

    4.33 percent of training rows sit at -1.0 and 3.54 percent at +1.0, so a correction pushing
    past the limit is common rather than a corner case.
    """
    recorded = track.df["steering"].to_numpy(dtype=float)
    limit_low, limit_high = config.STEERING_LIMITS

    saw_low = saw_high = False
    for sample in train_samples:
        if not sample.is_augmented:
            continue

        value = recorded[sample.row_index]
        sign = 1.0 if sample.camera is dataset.Camera.LEFT else -1.0
        uncorrected = value + sign * sample.camera_offset

        if uncorrected < limit_low:
            assert sample.steering == pytest.approx(limit_low)
            saw_low = True
        elif uncorrected > limit_high:
            assert sample.steering == pytest.approx(limit_high)
            saw_high = True

        if saw_low and saw_high:
            return

    pytest.fail(f"clipping not observed at both limits (low={saw_low}, high={saw_high})")


def test_the_offsets_are_reproducible_from_the_seed():
    first = dataset.draw_camera_offsets(500, seed=config.SEED)
    second = dataset.draw_camera_offsets(500, seed=config.SEED)
    other = dataset.draw_camera_offsets(500, seed=config.SEED + 1)

    assert np.array_equal(first, second)
    assert not np.array_equal(first, other)


def test_the_offsets_do_not_depend_on_the_order_rows_arrive_in(track, plan):
    """Drawn once, up front, rather than inside the sample loop.

    If the draw followed the loop, the same row would get a different offset depending on how
    the caller happened to order its input, and the training target distribution would stop
    being a fixed object this feature can report.
    """
    rows = plan.train_rows[:400]
    forward = dataset.build_samples(track, rows, use_side_cameras=True)
    backward = dataset.build_samples(track, list(reversed(rows)), use_side_cameras=True)

    assert forward == backward


def test_no_lattice_value_dominates_the_training_targets(train_samples):
    """The test that stops the research R4 fault returning silently.

    The constant 0.2 offset put 40.6 percent of training targets on exactly two lattice points,
    two modes the human driver never produced, indistinguishable in a histogram from real
    steering because 0.20 is itself a lattice value. Measured with the jitter in place: the
    largest share is 20.35 percent at zero, the runner-up 6.29 percent at -0.25, and the old
    offending pair now holds 6.10 and 5.78 percent.
    """
    histogram = dataset.steering_histogram(train_samples)
    total = len(train_samples)
    shares = sorted((count / total for count in histogram.values()), reverse=True)

    assert shares[0] < 0.25, "one steering value holds a quarter of the training targets"
    assert sum(shares[:2]) < 0.30, "two values hold nearly a third of the training targets"

    for value in ("+0.20", "-0.20"):
        assert histogram[value] / total < 0.10, (
            f"{value} carries a spike again; the offset may have stopped being jittered"
        )


def test_the_block_map_agrees_with_the_split(track, plan):
    """`bc.dataset` and `bc.split` compute blocks separately, so the duplication is checked.

    Copying the rule and trusting it stayed in step is how a sample ends up in a different
    block from the row it came from, which would put a guarded row back into training.
    """
    mapping = dataset.row_block_map(track)

    for bound in plan.block_bounds:
        for row in range(bound.first_row, bound.last_row + 1):
            assert mapping[row] == (bound.track, bound.block)


def test_a_sample_whose_camera_contradicts_its_augmented_flag_is_rejected():
    with pytest.raises(dataset.DatasetError, match="is_augmented"):
        dataset.SampleSpec(0, dataset.Camera.LEFT, 0.0, False, "track1data", 0, 0.2)

    with pytest.raises(dataset.DatasetError, match="is_augmented"):
        dataset.SampleSpec(0, dataset.Camera.CENTER, 0.0, True, "track1data", 0, None)


def test_build_samples_rejects_a_row_outside_the_recording(track):
    with pytest.raises(dataset.DatasetError, match="outside the recording"):
        dataset.build_samples(track, [len(track.df) + 1], use_side_cameras=False)


# -----------------------------------------------------------------------------------------
# Image existence
# -----------------------------------------------------------------------------------------


def test_every_sample_resolves_to_a_file_that_exists(track, val_samples):
    dataset.verify_images_exist(track, val_samples)


def test_a_missing_image_raises_and_names_the_file(track, plan):
    """FR-002. The failing direction, and the reason it matters is that the alternative is a
    skip: the run completes, the loss curve looks normal, and every count is computed over a
    denominator nobody chose.
    """
    broken = loader.load_track(config.DATASET_NAME)
    loader.resolve_image_paths(broken)
    broken.df.loc[broken.df.index[0], "center_file"] = "definitely_not_a_real_frame.jpg"

    samples = dataset.build_samples(broken, [0, 1], use_side_cameras=False)

    with pytest.raises(dataset.DatasetError, match="definitely_not_a_real_frame.jpg"):
        dataset.verify_images_exist(broken, samples)


# -----------------------------------------------------------------------------------------
# Balancing
# -----------------------------------------------------------------------------------------


def test_the_none_policy_changes_nothing(train_samples):
    kept, stats = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.NONE)

    assert kept == train_samples
    assert stats.n_removed == 0
    assert stats.zero_share_before == stats.zero_share_after


def test_downsampling_reduces_the_zero_spike_below_the_runner_up(train_samples):
    """The rule the keep fraction is derived from, asserted rather than assumed.

    Research R11: the previous 0.30 failed this exact check, because the zero share was counted
    raw while the runner-up was counted on the lattice.
    """
    _, stats = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.DOWNSAMPLE_ZERO)

    assert stats.zero_share_after < stats.zero_share_before
    assert stats.zero_share_after <= stats.runner_up_share_after


def test_downsampling_removes_only_zero_steering_samples(train_samples):
    kept, _ = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.DOWNSAMPLE_ZERO)

    before = sum(1 for s in train_samples if s.steering != 0.0)
    after = sum(1 for s in kept if s.steering != 0.0)

    assert before == after


def test_balancing_accounts_for_every_sample(train_samples):
    """No sample vanishes without being counted, the same guarantee `bc.split` makes on rows."""
    kept, stats = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.DOWNSAMPLE_ZERO)

    assert stats.n_before == len(train_samples)
    assert stats.n_after == len(kept)
    assert stats.n_after + stats.n_removed == stats.n_before
    assert sum(stats.histogram.values()) == stats.n_after


def test_balancing_is_deterministic_and_keeps_recording_order(train_samples):
    first, _ = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.DOWNSAMPLE_ZERO)
    second, _ = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.DOWNSAMPLE_ZERO)

    assert first == second
    assert all(a.row_index <= b.row_index for a, b in zip(first, first[1:]))


def test_surviving_zeros_are_drawn_from_across_the_recording(train_samples):
    """Not taken from the front of the list.

    Keeping the first 27 percent would keep whichever part of the lap the zeros happened to be
    recorded in, and the surviving zeros would describe one straight rather than all of them.
    """
    kept, _ = dataset.apply_balancing(train_samples, dataset.BalancingPolicy.DOWNSAMPLE_ZERO)

    zeros = [s.row_index for s in kept if s.steering == 0.0]
    original = [s.row_index for s in train_samples if s.steering == 0.0]

    assert len(zeros) < len(original)
    # The survivors must span essentially the whole range the originals did, not a prefix.
    assert min(zeros) - min(original) < 0.05 * (max(original) - min(original))
    assert max(original) - max(zeros) < 0.05 * (max(original) - min(original))


def test_an_impossible_keep_fraction_is_rejected(train_samples):
    with pytest.raises(dataset.DatasetError, match="between 0 and 1"):
        dataset.apply_balancing(
            train_samples[:100], dataset.BalancingPolicy.DOWNSAMPLE_ZERO, keep_fraction=1.5
        )
