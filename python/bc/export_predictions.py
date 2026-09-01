"""Export the BC model's validation predictions so M5 can read them without torch.

**Why this is a separate step and not part of the comparison.** M5's comparison runs under `.venv`,
which has no torch, and running the model needs it. Rather than making the comparison depend on a
torch environment, the predictions are exported once, here, under `.venv-bc`, and committed as a
small CSV. That is the same bargain `python/rl/comparison_inputs.py` makes for the driving traces.

**What it holds and why the human column is in it.** Each row is one validation sample in original
recording order: the model's prediction, the human target it was scored against, and the track the
sample came from. The human column is included rather than re-derived from the dataset because the
validation split is a **subset** chosen by `python.bc.split`, and reconstructing which 5,576 of the
32,443 rows it selected without the split logic would be a second implementation of the split.

**The track column matters for M5.** Feature 004 reports pooled and per-track figures, and the two
tracks differ enough to change conclusions: track1 steering has variance 0.02393 against track2's
0.21333. Any comparison that pools them must say so.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from python.bc import config, evaluate


def export(run_id: str, out: Path, run_dir: Path | None = None) -> pd.DataFrame:
    predictions = evaluate.predict(run_id, run_dir=run_dir)

    frame = pd.DataFrame(
        {
            "order": predictions.order,
            "track": predictions.track,
            "predicted_steering": predictions.predicted,
            "human_steering": predictions.actual,
        }
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# run_id={run_id} rows={len(frame)}\n"
        "# Validation split only, in original recording order, one row per sample.\n"
        "# predicted_steering is continuous; the human column is on the 0.05 lattice.\n"
        "# Quantise the prediction before comparing distributions, never the human column.\n"
    )
    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write(header)
        frame.to_csv(handle, index=False)
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", default=config.DEFAULT_RUN_ID if hasattr(config, "DEFAULT_RUN_ID") else "bc_balanced_v01")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    out = args.out or args.root / "results" / "comparison" / f"bc_predictions_{args.run_id}.csv"
    frame = export(args.run_id, out)
    print(f"wrote {out} with {len(frame)} rows over {frame['track'].nunique()} tracks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
