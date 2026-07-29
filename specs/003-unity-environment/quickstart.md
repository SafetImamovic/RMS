# Quickstart: Unity Driving Environment (M2)

Prerequisites: the M1 environment (`.venv`) works, the dataset is unzipped under `dataset/`, and
Unity 6000.5.3f1 opens `unity/SelfDrivingSim`. No new Python dependency is introduced; if M1 runs,
this runs.

Two Unity packages are added once, through Window > Package Manager > Add package by name:
`com.unity.splines` and `com.unity.probuilder`. Both are first-party and are recorded in the
committed `Packages/manifest.json`, so a clean clone picks them up automatically.

## 1. Drive the car on the flat plane (User Story 1)

```powershell
# Nothing to generate. Open the scene and press Play.
#   unity/SelfDrivingSim/Assets/Scenes/FlatGround.unity
# W / S accelerate and brake, A / D steer.
```

Then check the drive against the dataset:

```powershell
.venv\Scripts\Activate.ps1
python -m python.track.compare_drive results\drive_logs\<latest>.csv
```

Expected report: reachable steering spans the full range in both directions, the 95th-percentile
steering change is within a factor of two of the recorded human figure once resampled to 14.08 Hz,
and normalised top speed agrees with the dataset within 10 percent.

## 2. Generate tracks (User Story 2)

```powershell
# One track
python -m python.track.export --seed 7

# The training and evaluation sets
python -m python.track.export --batch train
python -m python.track.export --batch eval
```

Files land in `unity/SelfDrivingSim/Assets/Tracks/seed_<n>.json` and are committed. The batch
report prints the acceptance rate and every rejection with its reason.

```powershell
# Determinism check (SC-007): regenerate and compare byte for byte
python -m python.track.export --seed 7
Copy-Item unity\SelfDrivingSim\Assets\Tracks\seed_7.json $env:TEMP\seed7_a.json
python -m python.track.export --seed 7
if ((Get-FileHash unity\SelfDrivingSim\Assets\Tracks\seed_7.json).Hash -eq (Get-FileHash $env:TEMP\seed7_a.json).Hash) {
    "REPRODUCIBLE"
} else {
    "MISMATCH - investigate before committing"
}
```

## 3. Drive a generated track (User Stories 2 and 3)

Open `unity/SelfDrivingSim/Assets/Scenes/Track.unity`, set the seed on the track builder, press
Play. The observation panel shows every value the future agent will see.

## 4. Tests

```powershell
pytest python/tests -q          # M1, feature 002 and the new generator tests
# Unity: Window > General > Test Runner > EditMode > Run All
```

## Outputs to expect

| Path | What |
|---|---|
| `unity/SelfDrivingSim/Assets/Tracks/seed_*.json` | one committed track per accepted seed |
| `results/tracks/batch_report.md` | acceptance rate, rejections and reasons |
| `results/tracks/seed_split.json` | which seeds are training and which are evaluation |
| `results/drive_logs/*.csv` | keyboard drives, in the dataset's own columns |
| `results/plots/track_seed_*.png` | centre line with the tightest corner marked |
| `results/plots/track_match.png` | required-steering distribution against the human reference |

## What the results should say

| Check | Expected |
|---|---|
| Minimum corner radius, every accepted track | at or above 6.97 m |
| Maximum required steering, every accepted track | at or below 0.789 |
| Self-intersections | none |
| Minimum separation | at or above 12 m |
| Seed acceptance rate | at least 50 percent |
| Match distance, batch of 20 or more | at or below the stated threshold |
| Same seed re-run | byte-identical file |
| Full-lock turning circle, measured in Unity | within 10 percent of 5.36 m |
| Normalised top speed against the dataset | within 10 percent |
| Checkpoints per lap | 24 awarded, none skipped, none double counted |

**If the acceptance rate is below 50 percent, stop.** That means the radius floor and the
statistical target are pulling against each other, which is a design finding rather than a tuning
problem. Lowering the floor to fix it would be trading the agent's steering reserve for a nicer
number, and the reserve is the reason the floor exists.

## Two limitations that are expected, not bugs

1. **No generated track demands steering above 0.789.** The 1.3 safety margin on the corner radius
   is exactly the agent's steering reserve, and it caps what any corner can ask for. The human data
   reaches 1.0, so the coverage stops at roughly the 97th percentile of track1. This is a
   deliberate trade and is stated in every match report.
2. **No generated track contains a straight.** A closed curve built from radial harmonics always
   curves, while the human data is 58.6 percent exactly zero steering. Distribution comparisons are
   therefore made against the conditional distribution given non-zero steering. The consequence for
   M5 is already recorded in DESIGN section 7: lean on execution metrics such as steering
   smoothness, not on raw marginal histograms.

## Definition of done (M2 gate)

- The car drives on the flat plane by keyboard, and its limits are verified against the dataset.
- The instability trigger is written down and has not fired, or it fired and the fallback model is
  in use, with the run that triggered it recorded.
- Tracks generate from seeds, reproducibly, with every geometric check passing on 100 percent of
  accepted tracks.
- Training and evaluation seed sets are disjoint and recorded in the repository.
- A full lap is driveable by keyboard on at least five different accepted seeds.
- Every observation has been read live during a human drive and checked against a situation whose
  answer was visible.
- `pytest` green, Unity EditMode tests green.
- The blunt version, from WORKFLOW section 5: **no keyboard lap, no training.**
