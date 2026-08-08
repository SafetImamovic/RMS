"""Turning recording rows into training examples, and proving every one of them is real.

Two responsibilities live here, and they are deliberately separated from anything that decodes
pixels. `build_samples` decides **what** the model will be shown and what target goes with it.
`verify_images_exist` confirms that every one of those decisions points at a file that is
actually on disk, before a single epoch runs.

The second one exists because of how this failure presents. A missing image inside a training
loop is usually handled by skipping the row, and a skip is silent: the run completes, the loss
curve looks normal, and every count the run reports is computed over a denominator nobody chose.
So this module never skips. It raises, and it names the first file it could not find.

Reading goes through `eda.loader`. The headerless-CSV parsing and the re-rooting of the
recorder's Windows paths are solved there and are not reimplemented here, so M1 and M4 cannot
develop different opinions about what row 12,000 contains (FR-001).

This module imports no torch. Sample construction is a decision about the data, and keeping it
torch-free means the sample set can be built and inspected under `.venv`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image

from python.bc import config
from python.eda import integrity, loader
from python.eda.loader import TrackDataset


class DatasetError(Exception):
    """Raised when the sample set cannot be trusted. Always names the offending item."""


class Camera(str, Enum):
    """Which of the three recorded viewpoints a sample refers to.

    A string enum rather than a bare string so a typo is an error at construction instead of a
    silently empty filter three steps later. Inherits from `str` so it serialises as its own
    name without a custom encoder.
    """

    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"


# The recorded steering value describes the CENTER camera. A side camera sees the road from a
# laterally displaced position, so the steering that would have produced that view is the
# recorded value corrected toward the road. Left sees the car as too far left, so its target
# steers further right, and the right camera mirrors it.
_OFFSET_SIGN: dict[Camera, float] = {
    Camera.CENTER: 0.0,
    Camera.LEFT: +1.0,
    Camera.RIGHT: -1.0,
}


@dataclass(frozen=True)
class SampleSpec:
    """One training or validation example, before any image is decoded.

    Frozen because a sample's target is the thing this feature reports distributions over. If a
    later stage could quietly rewrite `steering`, the histogram in the results would describe
    something other than what the model was trained on.
    """

    row_index: int
    camera: Camera
    steering: float
    is_augmented: bool
    track: str
    block: int
    camera_offset: float | None

    def __post_init__(self) -> None:
        # The invariant from data-model.md, enforced rather than documented. A center sample
        # marked augmented would be counted as synthetic in every report that follows, and a
        # side sample marked genuine could reach the validation set, which FR-007 forbids.
        expected = self.camera is not Camera.CENTER
        if self.is_augmented != expected:
            raise DatasetError(
                f"row {self.row_index}: camera {self.camera.value} implies "
                f"is_augmented={expected}, got {self.is_augmented}"
            )


def row_block_map(ds: TrackDataset, n_blocks: int = config.N_BLOCKS) -> list[tuple[str, int]]:
    """Which track and which contiguous block each row belongs to, indexed by row position.

    The arithmetic mirrors `bc.split.plan_split` on purpose, and the duplication is checked
    rather than trusted: a test asserts this map agrees with the `block_bounds` of a real plan.
    Copying the rule and hoping it stayed in step is how two modules end up disagreeing about
    which block a boundary row is in, which would put a sample in a different block from the
    row it came from.
    """
    sessions = integrity.split_sessions(ds)
    mapping: list[tuple[str, int]] = [("", -1)] * len(ds.df)

    for session in sessions:
        size = session.n_rows
        if size < n_blocks:
            raise DatasetError(
                f"session {session.session_id} has {size} rows, fewer than the "
                f"{n_blocks} blocks it must be cut into"
            )

        block_len = size // n_blocks
        for block in range(n_blocks):
            lo = session.start_index + block * block_len
            hi = (session.end_index + 1 if block == n_blocks - 1
                  else session.start_index + (block + 1) * block_len)
            for row in range(lo, hi):
                mapping[row] = (session.session_id, block)

    return mapping


def draw_camera_offsets(n_rows: int,
                        seed: int = config.SEED,
                        offset_range: tuple[float, float] = config.CAMERA_OFFSET_RANGE
                        ) -> np.ndarray:
    """One offset per row per side camera, drawn once from the seed. Shape (n_rows, 2).

    Drawn here, in one vectorised call, rather than inside the sample loop, so the values do not
    depend on the order the loop happens to visit rows in. Same seed, same array.

    Drawn ONCE for the whole run and never re-drawn per epoch (`OFFSET_DRAWN_ONCE`). Re-drawing
    would be the stronger augmentation, but then the training target distribution is a different
    object every epoch, and this feature has to be able to state what that distribution was:
    comparing it against the human one is the deliverable.

    The generator is numpy's PCG64 via `default_rng`. `requirements-bc.txt` pins numpy, so the
    stream is fixed for this project. `bc.split` avoided an RNG entirely for the same class of
    concern; here randomness is the point, so it is seeded and pinned instead of avoided.
    """
    low, high = offset_range
    rng = np.random.default_rng(seed)
    return rng.uniform(low, high, size=(n_rows, 2))


def build_samples(ds: TrackDataset,
                  rows: list[int],
                  use_side_cameras: bool,
                  seed: int = config.SEED,
                  offset_range: tuple[float, float] = config.CAMERA_OFFSET_RANGE,
                  n_blocks: int = config.N_BLOCKS) -> list[SampleSpec]:
    """Expand a set of recording rows into the examples the model will actually see.

    With `use_side_cameras` false this returns one center sample per row, every one of them
    carrying the recorded human steering value unmodified. That is the only form permitted for
    the validation set (FR-007): a side-camera target is a value this project invented, and
    scoring a model against our own invention measures agreement with our offset rule rather
    than agreement with the human driver.

    With it true, each row yields three samples. The two side targets are the recorded value
    plus or minus an offset drawn from `CAMERA_OFFSET_RANGE`, clipped to the steering limits.
    The drawn value is stored on the sample, because the fault the jitter replaced was an
    invisible one: a constant 0.2 left no trace in the output while parking 40.6 percent of
    training targets on two lattice points (research R4).
    """
    if not ds.resolved:
        loader.resolve_image_paths(ds)

    # Sorted and de-duplicated so the sample list is a function of which rows were asked for,
    # not of the order they arrived in. Two callers passing the same set get the same offsets.
    ordered = sorted({int(row) for row in rows})
    if not ordered:
        raise DatasetError("no rows were given, so there is nothing to build samples from")

    n_df_rows = len(ds.df)
    out_of_range = [row for row in ordered if row < 0 or row >= n_df_rows]
    if out_of_range:
        raise DatasetError(
            f"row {out_of_range[0]} is outside the recording, which has {n_df_rows:,} rows"
        )

    block_of = row_block_map(ds, n_blocks)
    steering = ds.df["steering"].to_numpy(dtype=float)
    low_limit, high_limit = config.STEERING_LIMITS

    offsets = (draw_camera_offsets(len(ordered), seed, offset_range)
               if use_side_cameras else None)

    cameras = ((Camera.CENTER, Camera.LEFT, Camera.RIGHT) if use_side_cameras
               else (Camera.CENTER,))

    samples: list[SampleSpec] = []
    for position, row in enumerate(ordered):
        track, block = block_of[row]
        recorded = float(steering[row])

        for camera in cameras:
            if camera is Camera.CENTER:
                target, drawn = recorded, None
            else:
                # Column 0 is the left camera's draw, column 1 the right camera's. Separate
                # columns rather than one shared value, so the two synthesised targets for a
                # row are not a mirrored pair sitting the same distance from the human one.
                drawn = float(offsets[position, 0 if camera is Camera.LEFT else 1])
                target = float(
                    np.clip(recorded + _OFFSET_SIGN[camera] * drawn, low_limit, high_limit)
                )

            samples.append(
                SampleSpec(
                    row_index=row,
                    camera=camera,
                    steering=target,
                    is_augmented=camera is not Camera.CENTER,
                    track=track,
                    block=block,
                    camera_offset=drawn,
                )
            )

    return samples


def preprocess(image) -> np.ndarray:
    """Crop, resize, convert to YUV and normalise. Deterministic, no randomness anywhere.

    The four steps and why they are in this order:

    1. **Crop** to rows `CROP_TOP` to `CROP_BOTTOM`. Above the top line is sky and distant
       scenery; below the bottom line is the car's own hood, which is the same shape in every
       frame and therefore cannot inform any steering decision. Both lines were measured on
       real frames rather than inherited (research R9). Cropping first also means the resize
       has less to do.
    2. **Resize** to `INPUT_WIDTH` by `INPUT_HEIGHT`, the PilotNet input (DESIGN 6.2). This
       does not preserve aspect ratio: 320x77 becomes 200x66, so the frame is stretched
       vertically. PilotNet does the same, and consistency matters more than fidelity here
       because every frame is stretched identically.
    3. **YUV**, per DESIGN 6.2. Separating luminance from chrominance means a brightness change
       moves one channel rather than all three, which is what makes the brightness augmentation
       in `augment` a small perturbation instead of a colour shift. Pillow's `YCbCr` is the
       studio-swing form of the same separation; the difference from the analogue YUV of the
       PilotNet paper is a fixed scale and offset, which the first convolution absorbs.
    4. **Normalise** to [-1, 1]. Inputs centred on zero keep the first layer's gradients off the
       flat ends of its activations.

    Takes an RGB array or a PIL image and returns float32 of shape
    (`INPUT_HEIGHT`, `INPUT_WIDTH`, `INPUT_CHANNELS`).
    """
    if isinstance(image, np.ndarray):
        if image.ndim != 3 or image.shape[2] != config.INPUT_CHANNELS:
            raise DatasetError(
                f"expected an RGB array with {config.INPUT_CHANNELS} channels, "
                f"got shape {image.shape}"
            )
        frame = Image.fromarray(image.astype(np.uint8), mode="RGB")
    else:
        frame = image.convert("RGB")

    if frame.size != (config.FRAME_WIDTH, config.FRAME_HEIGHT):
        raise DatasetError(
            f"expected a {config.FRAME_WIDTH}x{config.FRAME_HEIGHT} frame, got "
            f"{frame.size[0]}x{frame.size[1]}. The crop rows are positions in the recorded "
            "frame, so they are meaningless against a different size."
        )

    # (left, upper, right, lower). The full width is kept: the road leaves the frame sideways
    # on the sharp corners, and that is exactly where the steering signal is largest.
    frame = frame.crop((0, config.CROP_TOP, config.FRAME_WIDTH, config.CROP_BOTTOM))
    frame = frame.resize((config.INPUT_WIDTH, config.INPUT_HEIGHT), Image.BILINEAR)

    yuv = np.asarray(frame.convert("YCbCr"), dtype=np.float32)
    half = config.PIXEL_VALUE_MAX / 2.0
    return yuv / half - 1.0


def augment(image: np.ndarray, steering: float,
            rng: np.random.Generator) -> tuple[np.ndarray, float]:
    """Randomly flip and re-light one preprocessed frame. Returns the image and its target.

    **The flip negates the steering.** Principle VIII names this test by hand, and the reason it
    is named is that the failure is silent: a model trained on mirrored images paired with
    unmirrored targets learns to steer into corners, and nothing about the loss curve says so.

    Applied to the output of `preprocess`, not to the raw frame. The flip commutes with the crop
    and the resize because the crop keeps the full width, and the brightness change is a single
    channel operation only because `preprocess` has already separated luminance from
    chrominance.

    Takes an explicit rng and never touches global random state, matching the rule
    `python/track/generator.py` already follows. Two callers with two generators cannot make
    each other's output irreproducible, and a test can hand it a fixed seed.

    Unlike the camera offsets, this is drawn **per epoch** rather than once. That is the
    conventional choice and it costs nothing here: at `FLIP_PROBABILITY` 0.5 the flip's effect
    on the target distribution is exactly symmetrisation, and brightness does not touch the
    target at all, so the distribution this feature reports can still be stated exactly rather
    than sampled.
    """
    flipped = rng.random() < config.FLIP_PROBABILITY
    if flipped:
        # Column axis only. Axis 0 is rows and axis 2 is the colour channels: flipping either
        # would produce an upside-down frame or a channel swap, both of which still train.
        image = np.ascontiguousarray(image[:, ::-1, :])
        steering = -steering

    low, high = config.BRIGHTNESS_RANGE
    factor = rng.uniform(low, high)

    # Undo the normalisation on the luminance channel, scale, put it back. Done on Y alone so
    # the frame gets darker or lighter without its colours shifting, which is what a different
    # time of day looks like and what track2's shadowed sections actually are.
    half = config.PIXEL_VALUE_MAX / 2.0
    image = image.copy()
    luminance = (image[..., 0] + 1.0) * half * factor
    image[..., 0] = np.clip(luminance, 0.0, config.PIXEL_VALUE_MAX) / half - 1.0

    return image, float(steering)


def image_file(ds: TrackDataset, sample: SampleSpec) -> str:
    """The file name this sample's image lives under, from the columns `eda.loader` resolved."""
    if not ds.resolved:
        loader.resolve_image_paths(ds)
    return str(ds.df[f"{sample.camera.value}_file"].iloc[sample.row_index])


def image_path(ds: TrackDataset, sample: SampleSpec) -> Path:
    """The full local path to this sample's image."""
    return ds.img_dir / image_file(ds, sample)


class BalancingPolicy(str, Enum):
    """Which of the two runs this is.

    A closed type rather than a boolean, so the run record says what it did in words. `policy:
    downsample_zero` survives being read a month later; `balanced: true` does not say what was
    balanced or how.
    """

    NONE = "none"
    DOWNSAMPLE_ZERO = "downsample_zero"


@dataclass(frozen=True)
class BalancingStats:
    """What the policy actually removed, so the induced distribution shift is a number.

    The reason this is a returned object rather than a log line: the two runs differ in exactly
    one thing, and the comparison between them is the deliverable. A reader who cannot see how
    much was removed cannot tell whether a difference in the results is the policy working or
    the policy barely doing anything.
    """

    policy: BalancingPolicy
    n_before: int
    n_after: int
    n_removed: int
    zero_share_before: float
    zero_share_after: float
    runner_up_value: float
    runner_up_share_after: float
    histogram: dict[str, int]

    def summary(self) -> str:
        return (
            f"[{self.policy.value}] {self.n_before:,} -> {self.n_after:,} samples "
            f"({self.n_removed:,} removed); zero share "
            f"{self.zero_share_before:.2%} -> {self.zero_share_after:.2%}, "
            f"runner-up {self.runner_up_value:+.2f} at {self.runner_up_share_after:.2%}"
        )


def _lattice_key(value: float) -> float:
    """Snap a target onto the human steering lattice, for counting only.

    Counting on the lattice rather than on raw values, because the raw histogram measures the
    wrong thing here. Side-camera targets carry a continuous jitter, so they collide only where
    they clip: an unbinned count reports -1.00 as the second most common value at 3.41 percent,
    which is a fact about the clipping and not about the driving. On the lattice the runner-up
    is -0.25 at 6.29 percent, and the lattice is where M5 compares the distributions anyway.
    """
    step = config.STEERING_LATTICE_STEP
    return round(round(value / step) * step, 4)


def steering_histogram(samples: list[SampleSpec]) -> dict[str, int]:
    """Count samples per lattice level. Keys are formatted so the mapping survives JSON."""
    counts: dict[str, int] = {}
    for sample in samples:
        key = f"{_lattice_key(sample.steering):+.2f}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: float(item[0])))


def apply_balancing(samples: list[SampleSpec],
                    policy: BalancingPolicy,
                    seed: int = config.SEED,
                    keep_fraction: float = config.BALANCE_KEEP_FRACTION,
                    zero_band: float = config.ZERO_STEERING_BAND
                    ) -> tuple[list[SampleSpec], BalancingStats]:
    """Thin the near-zero steering spike, or leave it alone, and report which and by how much.

    **Training samples only.** The validation set is never balanced (FR-022): balancing is a
    property of what the model is shown, and applying it to validation would move the yardstick
    along with the model, leaving the two runs measured against different things.

    `zero_band` is 0.0, meaning exactly zero and nothing wider. The neighbouring lattice levels
    carry 5.7 to 6.3 percent each and are genuine human steering decisions; widening the band to
    catch them would discard real inputs to fix a spike that sits on one value.

    Which samples survive is drawn from the seed rather than taken from the front of the list.
    Taking the first `keep_fraction` would keep whichever part of the lap the zeros happened to
    be recorded in, and the surviving zeros would then describe one straight rather than all of
    them.
    """
    n_before = len(samples)
    zeros = [s for s in samples if abs(s.steering) <= zero_band]

    # Removal targets the band (exactly zero) while the SHARES are counted on the lattice. The
    # two differ, and mixing them is a real trap: a side-camera target of 0.017 is not an exact
    # zero and is never a removal candidate, but it lands in the +0.00 lattice bin and so counts
    # against the rule. Reporting the raw count next to a lattice runner-up would compare two
    # different quantities and make the spike look smaller than it is.
    def _zero_share(items: list[SampleSpec]) -> float:
        if not items:
            return 0.0
        return steering_histogram(items).get("+0.00", 0) / len(items)

    zero_share_before = _zero_share(samples)

    if policy is BalancingPolicy.NONE:
        kept = list(samples)
    elif policy is BalancingPolicy.DOWNSAMPLE_ZERO:
        if not 0.0 <= keep_fraction <= 1.0:
            raise DatasetError(
                f"keep_fraction must be between 0 and 1, got {keep_fraction}"
            )
        rng = np.random.default_rng(seed)
        n_keep = int(round(len(zeros) * keep_fraction))
        survivor_positions = rng.choice(len(zeros), size=n_keep, replace=False) if zeros else []
        survivors = {id(zeros[int(i)]) for i in survivor_positions}

        # Rebuilt in the original order rather than as "non-zeros plus survivors", so the
        # sample list stays in recording order and a later shuffle is the only thing that
        # decides batch composition.
        kept = [
            s for s in samples
            if abs(s.steering) > zero_band or id(s) in survivors
        ]
    else:
        raise DatasetError(f"unknown balancing policy: {policy}")

    after = steering_histogram(kept)
    n_after = len(kept)

    non_zero = [(float(k), v) for k, v in after.items() if float(k) != 0.0]
    runner_value, runner_count = (max(non_zero, key=lambda item: item[1])
                                  if non_zero else (0.0, 0))

    stats = BalancingStats(
        policy=policy,
        n_before=n_before,
        n_after=n_after,
        n_removed=n_before - n_after,
        zero_share_before=zero_share_before,
        zero_share_after=_zero_share(kept),
        runner_up_value=runner_value,
        runner_up_share_after=runner_count / n_after if n_after else 0.0,
        histogram=after,
    )
    return kept, stats


def verify_images_exist(ds: TrackDataset, samples: list[SampleSpec]) -> None:
    """Raise unless every sample resolves to a file on disk. Names the first one that does not.

    Checked over the whole set before training rather than per batch during it, because the
    point is to fail before the run starts. Discovering a missing file forty minutes into an
    epoch means either a crash that wastes the run or a skip that corrupts the counts.

    One directory listing and set membership, not a `stat` per sample. At three samples per row
    the training set is tens of thousands of paths, and the per-file version turns a check into
    a wait long enough that someone eventually removes it.
    """
    if not ds.resolved:
        loader.resolve_image_paths(ds)

    if not ds.img_dir.exists():
        raise DatasetError(f"the image directory does not exist: {ds.img_dir}")

    present = {name for name in os.listdir(ds.img_dir) if name.lower().endswith(".jpg")}

    for sample in samples:
        name = image_file(ds, sample)
        if name not in present:
            raise DatasetError(
                f"missing image for row {sample.row_index} "
                f"({sample.camera.value} camera): {ds.img_dir / name}"
            )
