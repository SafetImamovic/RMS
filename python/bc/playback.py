"""Watch the model steer, frame by frame, against what the human did.

The honest framing first, because this is the thing most likely to be over-read. **This is not
the model driving.** It is the model reacting to frames the human drove. Each prediction is made
from a real recorded image, and the next image is whatever the human's steering produced, not
the model's. Nothing here shows whether the policy could keep a car on the road; it shows where
the policy agrees and disagrees with a human, one frame at a time.

Closed-loop driving is possible in principle, in the Udacity simulator these frames came from,
and is not possible in this project's Unity scene: the model has never seen those renders
(DESIGN section 7). Until that exists, this is the most a recorded dataset can honestly show.

Worth watching for rather than a pretty animation: the disagreement is not uniform. The model
tracks the human closely through curves and misses the long straights, where the human holds
exactly zero and the model does not.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from python.bc import config, dataset, evaluate, split
from python.eda import config as eda_config
from python.eda import loader

# Layout. The frame is 320x160, doubled so the road is legible, with a panel underneath for the
# two steering bars.
_SCALE = 2
_PANEL_HEIGHT = 116
_MARGIN = 14


def _font(size: int):
    """Arial if this is Windows, the bundled bitmap font otherwise. Never fails."""
    for candidate in ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_steering_bar(draw: ImageDraw.ImageDraw, top: int, width: int,
                       value: float, label: str, colour: str, font) -> None:
    """One signed bar growing left or right from the centre line.

    Signed rather than absolute, and centred rather than left-aligned, because the quantity is a
    direction. A bar chart that grows from the left would make -0.9 and +0.9 look like different
    magnitudes of the same thing.
    """
    bar_left = _MARGIN + 92
    bar_right = width - _MARGIN
    centre = (bar_left + bar_right) // 2
    half = (bar_right - bar_left) // 2
    height = 20

    draw.text((_MARGIN, top + 2), label, fill="#dddddd", font=font)
    draw.rectangle([bar_left, top, bar_right, top + height], outline="#444444")
    draw.line([centre, top - 3, centre, top + height + 3], fill="#888888")

    extent = int(half * float(np.clip(value, -1.0, 1.0)))
    if extent >= 0:
        draw.rectangle([centre, top + 2, centre + extent, top + height - 2], fill=colour)
    else:
        draw.rectangle([centre + extent, top + 2, centre, top + height - 2], fill=colour)

    draw.text((bar_right + 6 - 64, top + height + 2), f"{value:+.3f}",
              fill=colour, font=font)


_SERIES_COLOURS = {"human": "#ffffff", "unbalanced": "#4da3ff", "balanced": "#ff6b6b"}


def compose_frame(image: Image.Image, values: dict[str, float],
                  row_index: int, track: str, small, scale: float = _SCALE) -> Image.Image:
    """One road frame with a signed steering bar per series."""
    width = int(image.width * scale)
    height = int(image.height * scale)
    panel = _PANEL_HEIGHT + 44 * (len(values) - 2)

    canvas = Image.new("RGB", (width, height + panel), "#111111")
    canvas.paste(image.resize((width, height), Image.BILINEAR), (0, 0))
    draw = ImageDraw.Draw(canvas)

    draw.text((_MARGIN, _MARGIN), f"{track}   row {row_index:,}", fill="#ffffff", font=small)

    for index, (label, value) in enumerate(values.items()):
        _draw_steering_bar(draw, height + 12 + 44 * index, width, value, label,
                           _SERIES_COLOURS.get(label, "#cccccc"), small)

    human = values.get("human", 0.0)
    gaps = "   ".join(
        f"{label} {value - human:+.2f}" for label, value in values.items() if label != "human"
    )
    draw.text((_MARGIN, height + panel - 22), f"difference from human:   {gaps}",
              fill="#ff9f4d", font=small)
    return canvas


def build_playback(run_ids: list[str], track: str | None = None, frames: int = 200,
                   fps: int = 10, colours: int = 64, scale: float = 1.5,
                   out_path: Path | None = None) -> Path:
    """Render a contiguous stretch of validation frames to an animated GIF.

    **Contiguous on purpose.** The validation set is two held-out blocks per track, so its rows
    are not one continuous run. Stitching across a block boundary would cut mid-corner and read
    as the model losing the road, which is a fact about the split rather than about the model.

    **The busiest stretch is chosen, not a representative one.** A straight shows only that
    everyone agrees on roughly zero. This is therefore the hardest window in the block rather
    than a typical one, and the difference reported at the end is worse than the run's average
    by construction. Said here because a reader who assumes otherwise reads the animation as a
    summary of the model rather than as its hardest moments.
    """
    ds = loader.load_track(config.DATASET_NAME)
    plan = split.read_split()

    sets = {run_id: evaluate.predict(run_id, ds=ds, plan=plan) for run_id in run_ids}
    reference = sets[run_ids[0]]

    track = track or eda_config.SESSION_PATH_MARKERS[-1]
    mask = reference.scoped(track)
    if not mask.any():
        raise evaluate.EvaluationError(f"no validation frames for {track}")

    order = [row for row, keep in zip(reference.order, mask) if keep]
    human = reference.actual[mask]

    longest = max(evaluate._contiguous_runs(order), key=lambda run: run.stop - run.start)
    window = min(frames, longest.stop - longest.start)
    activity = np.array([
        np.abs(human[longest][i:i + window]).mean()
        for i in range(0, longest.stop - longest.start - window + 1, 10)
    ])
    offset = int(np.argmax(activity) * 10) if activity.size else 0
    chosen = slice(longest.start + offset, longest.start + offset + window)

    samples = dataset.build_samples(ds, order[chosen], use_side_cameras=False)
    small = _font(15)

    # Short labels, since a bar reading "bc_unbalanced_v01" is mostly run identifier.
    labels = {run_id: run_id.replace("bc_", "").rsplit("_v", 1)[0] for run_id in run_ids}

    rendered = []
    for i, sample in enumerate(samples):
        values = {"human": float(human[chosen][i])}
        for run_id in run_ids:
            values[labels[run_id]] = float(sets[run_id].predicted[mask][chosen][i])
        rendered.append(
            compose_frame(Image.open(dataset.image_path(ds, sample)),
                          values, sample.row_index, track, small, scale)
        )

    # Quantised to a small adaptive palette before saving. Full-colour frames produce a GIF of
    # roughly 28 MB for 200 frames, which is not a thing to put in a repository to make a point
    # that a tenth of the size makes equally well.
    quantised = [frame.quantize(colors=colours, method=Image.MEDIANCUT) for frame in rendered]

    stem = "_".join(labels[run_id] for run_id in run_ids)
    out_path = out_path or (eda_config.PLOTS_DIR / f"bc_playback_{stem}_{track}.gif")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    quantised[0].save(
        out_path, save_all=True, append_images=quantised[1:],
        duration=int(1000 / fps), loop=0, optimize=True,
    )

    print(f"wrote {out_path}  ({out_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  {len(rendered)} frames from {track}, rows {order[chosen][0]:,} "
          f"to {order[chosen][-1]:,}, contiguous")
    for run_id in run_ids:
        gap = float(np.mean(np.abs(sets[run_id].predicted[mask][chosen] - human[chosen])))
        overall = float(np.mean(np.abs(sets[run_id].predicted - sets[run_id].actual)))
        print(f"  {labels[run_id]:12s} mean |difference| here {gap:.4f}, "
              f"over the whole validation set {overall:.4f}")
    print("  open loop: the model reacts to the human's frames and never chooses the next one")
    return out_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Render a BC run's predictions over the frames the human drove."
    )
    parser.add_argument("--run", required=True, nargs="+",
                        help="one or more run ids; each gets its own bar")
    parser.add_argument("--track", default=None,
                        choices=list(eda_config.SESSION_PATH_MARKERS))
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--colours", type=int, default=64)
    parser.add_argument("--scale", type=float, default=1.5)
    args = parser.parse_args()

    build_playback(args.run, track=args.track, frames=args.frames, fps=args.fps,
                   colours=args.colours, scale=args.scale)


if __name__ == "__main__":
    main()
