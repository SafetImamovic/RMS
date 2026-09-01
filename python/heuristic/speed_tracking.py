"""How closely the scripted driver's speed followed the speed it was asking for.

Feature 009 samples the scripted driver at the agent's decision period rather than at
its own ``FixedUpdate``. Research R3 says the steering survives that and the throttle is
where laps can be lost: it is bang-bang against a ``0.25 m/s`` deadband, and one decision
at ``DecisionPeriod: 4`` is long enough for the speed to move about ``0.47 m/s``, which is
1.9 times the deadband. This module turns that prediction into a number.

The trace carries both halves already. ``DriveLogger`` writes ``speed``, the car's forward
speed, and ``target_speed``, what ``HeuristicDriver.TargetSpeedMs`` held at that step. The
error is the mean of ``|speed - target_speed|`` over the rows that have both.

**Rows without a target are skipped, not counted as zero error.** ``target_speed`` is empty
in every scene that has no scripted driver, which is every scene but the demonstration one.
Reading an empty field as zero would say the driver asked for a standstill, and the mean
would be the car's own speed wearing the name of a tracking error.

Usage::

    python -m python.heuristic.speed_tracking results/drive_logs/2026-08-29_13-02-11.csv
    python -m python.heuristic.speed_tracking results/drive_logs        # every trace in it
"""

from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DRIVE_LOGS = REPO / "results" / "drive_logs"


@dataclass(frozen=True)
class SpeedTracking:
    """One trace, reduced to what the cadence gate needs to read."""

    path: Path
    rows: int              # rows in the trace
    tracked: int           # rows carrying a target_speed
    mae: float | None      # mean |speed - target_speed|, None when nothing was tracked
    max_abs: float | None  # the worst single step, which the mean hides
    mean_speed: float | None
    mean_target: float | None

    @property
    def coverage(self) -> float:
        """Fraction of rows that carried a target. Zero means no scripted driver was present."""
        return self.tracked / self.rows if self.rows else 0.0


def _float(text: str | None) -> float | None:
    """A field, or None when it is absent, empty or not a number.

    Empty is the expected case rather than a corruption: it is what a trace from a scene
    without a scripted driver looks like.
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load(path: Path) -> SpeedTracking:
    """Read one drive log and measure its speed tracking."""
    rows = 0
    errors: list[float] = []
    speeds: list[float] = []
    targets: list[float] = []

    with io.open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            speed = _float(row.get("speed"))
            target = _float(row.get("target_speed"))
            if speed is None or target is None:
                continue
            errors.append(abs(speed - target))
            speeds.append(speed)
            targets.append(target)

    if not errors:
        return SpeedTracking(path, rows, 0, None, None, None, None)

    return SpeedTracking(
        path=path,
        rows=rows,
        tracked=len(errors),
        mae=sum(errors) / len(errors),
        max_abs=max(errors),
        mean_speed=sum(speeds) / len(speeds),
        mean_target=sum(targets) / len(targets),
    )


def load_folder(folder: Path) -> list[SpeedTracking]:
    """Every ``.csv`` in a folder, oldest first, so a sweep reads in the order it ran."""
    return [load(p) for p in sorted(folder.glob("*.csv"))]


def format_table(results: list[SpeedTracking]) -> str:
    """One row per trace. The deadband is printed beside the mean because it is the
    threshold that decides whether a number is a wobble or a failure."""
    lines = [
        f"{'trace':<34} {'rows':>7} {'tracked':>8} {'mae m/s':>9} {'max m/s':>9} "
        f"{'speed':>7} {'target':>7}",
        "-" * 86,
    ]
    for r in results:
        if r.mae is None:
            lines.append(f"{r.path.name:<34} {r.rows:>7} {r.tracked:>8} {'-':>9} {'-':>9} "
                         f"{'-':>7} {'-':>7}")
            continue
        lines.append(
            f"{r.path.name:<34} {r.rows:>7} {r.tracked:>8} {r.mae:>9.4f} {r.max_abs:>9.4f} "
            f"{r.mean_speed:>7.3f} {r.mean_target:>7.3f}"
        )
    lines.append("")
    lines.append("The driver's throttle deadband is 0.25 m/s (HeuristicDriver.cs:843-856). A mean")
    lines.append("below it is the bang-bang controller doing what it does; a mean above it is the")
    lines.append("cadence costing the expert its speed, which is what research R3 predicted.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", default=str(DRIVE_LOGS),
                        help="a drive log, or a folder of them")
    args = parser.parse_args(argv)

    target = Path(args.target)
    if target.is_dir():
        results = load_folder(target)
    else:
        results = [load(target)]

    if not results:
        print(f"no traces under {target}")
        return 1

    print(format_table(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
