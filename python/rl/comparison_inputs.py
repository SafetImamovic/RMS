"""Export the resampled steering series M5's comparison consumes.

**Why this file exists.** The raw per-step traces are deliberately kept out of the repository:
`results/drive_logs/*.csv` and `results/heuristic/**/trace_*.csv` are both gitignored, by rules two
separate features added on purpose. That is the right call for 36 MB of raw sweep output, and it
leaves M5 unable to reproduce its own figures from a clean clone, which SC-006 forbids.

So the **comparison inputs** are committed instead of the traces: one small CSV per driver holding
exactly what the comparison reads, which is the steering series resampled to `COMPARE_HZ` and
tagged by run. Everything downstream of this file works from a clean clone; regenerating these
files needs the traces and is only done when a sweep is re-run.

**Resampled here rather than at read time, and this is the important part.** Research R7: the Unity
trace is 50 Hz while the agent decides every fourth physics step, so 67.1 per cent of raw
differences are structurally zero and a naive `|delta steering|` reads 3.8 times smoother than the
truth. Resampling to 14.08 Hz is what removes that, and 14.08 Hz is the human recorder's own median
rate, recovered independently from the dataset's image filename stamps.

**The run column is not decoration.** Differences are taken within a run and never across the seam
between two runs, or the difference invents a steering change no driver made. Feature 002 hit
exactly that at the track1/track2 junction. Keeping the run id in the file is what lets every
consumer honour that without knowing how the sweep was shaped.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from python.track import compare_drive
from python.track import config as track_config


def _resampled_run(
    frame: pd.DataFrame, steering_column: str, speed_column: str | None, hz: float
) -> pd.DataFrame:
    """One run's steering and speed, on the uniform grid, in order.

    Speed is carried because `DESIGN.md` 7.1 asks for descriptive statistics on it as well as on
    steering, and it is resampled by the same nearest-sample rule so the two series share a clock.
    """
    renames: dict[str, str] = {}
    if steering_column != "steering":
        renames[steering_column] = "steering"
    if speed_column and speed_column != "speed":
        renames[speed_column] = "speed"
    work = frame.rename(columns=renames) if renames else frame

    if "t" not in work or "steering" not in work:
        raise KeyError(f"trace needs 't' and {steering_column!r}, has {list(frame.columns)[:8]}")

    out = compare_drive.resample(work, hz)
    result = pd.DataFrame({"steering": out["steering"].to_numpy(dtype=float)})
    if "speed" in out:
        result["speed"] = out["speed"].to_numpy(dtype=float)
    return result


def export_rl(
    repo_root: Path,
    run_id: str,
    inference: str,
    hz: float = track_config.COMPARE_HZ,
) -> pd.DataFrame:
    """One RL sweep's ten runs, selected through the trace manifest.

    Through the manifest and never through the trace's own `source` column, which is a stale
    literal on all 60 of feature 009's traces (research R3).
    """
    manifest = json.loads(
        (repo_root / "results" / "rl" / "trace_manifest.json").read_text(encoding="utf-8")
    )
    sweep = next(
        s
        for s in manifest["sweeps"]
        if s["run_id"] == run_id and s["inference"] == inference
    )
    drive_logs = repo_root / manifest["trace_dir"]

    rows: list[pd.DataFrame] = []
    for seed, name in zip(sweep["seeds"], sweep["traces"]):
        frame = pd.read_csv(drive_logs / name)
        run = _resampled_run(frame, "steering", "speed", hz)
        run.insert(0, "run", f"seed{seed}")
        rows.append(run)

    return pd.concat(rows, ignore_index=True)


def export_heuristic(
    traces_dir: Path,
    controller: str = "WeightedAverage",
    hz: float = track_config.COMPARE_HZ,
) -> pd.DataFrame:
    """The scripted driver's runs, one controller.

    **One controller, not both.** The sweep ran `MostOpen` and `WeightedAverage` over the same 34
    seeds, and pooling two control laws into one column would compare M5's other drivers against an
    average of two scripted drivers rather than against the one feature 005 reported.

    The scripted trace names its steering `applied_steer`, which is the command after the driver's
    own smoothing and therefore the one the car actually received. `command_steer` is the value
    before smoothing and would describe an intent rather than a drive.
    """
    rows: list[pd.DataFrame] = []
    for path in sorted(traces_dir.glob("trace_*.csv")):
        frame = pd.read_csv(path)
        if "controller" in frame and controller:
            present = set(frame["controller"].astype(str).unique())
            if controller not in present:
                continue
        seed = int(frame["seed"].iloc[0]) if "seed" in frame else -1
        run = _resampled_run(frame, "applied_steer", "speed_ms", hz)
        run.insert(0, "run", f"seed{seed}_{path.stem}")
        rows.append(run)

    if not rows:
        raise LookupError(f"no {controller} traces under {traces_dir}")
    return pd.concat(rows, ignore_index=True)


def write(frame: pd.DataFrame, out: Path, driver: str, hz: float, note: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = frame.copy()
    frame.insert(0, "driver", driver)
    header = (
        f"# driver={driver} hz={hz} rows={len(frame)} runs={frame['run'].nunique()}\n"
        f"# {note}\n"
        "# Steering resampled to hz by nearest sample. Difference WITHIN a run, never across runs.\n"
    )
    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write(header)
        frame.to_csv(handle, index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--hz", type=float, default=track_config.COMPARE_HZ)
    args = parser.parse_args(argv)

    out_dir = args.out_dir or args.root / "results" / "comparison"

    wrote: list[str] = []
    for run_id, inference in [
        ("ppo_car_009_bc", "deterministic"),
        ("ppo_car_009_bc", "sampling"),
        ("ppo_car_009_bc_s7", "deterministic"),
        ("ppo_car_009_bc_s13", "deterministic"),
    ]:
        frame = export_rl(args.root, run_id, inference, args.hz)
        name = f"steering_{run_id}_{inference}.csv"
        write(
            frame,
            out_dir / name,
            driver=f"{run_id}_{inference}",
            hz=args.hz,
            note="Ten held-out seeds, selected through results/rl/trace_manifest.json.",
        )
        wrote.append(f"{name}: {len(frame)} rows")

    heuristic = export_heuristic(args.root / "results" / "heuristic" / "us4", hz=args.hz)
    write(
        heuristic,
        out_dir / "steering_heuristic_weighted_average.csv",
        driver="heuristic_weighted_average",
        hz=args.hz,
        note="34 training seeds, WeightedAverage controller, applied_steer after smoothing.",
    )
    wrote.append(f"steering_heuristic_weighted_average.csv: {len(heuristic)} rows")

    for line in wrote:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
