# Contract: the run record

One row per run. Written by the sweep runner in Unity, read by `python/heuristic/report.py`.

A run is one controller, on one seed, under one sensing configuration. The file is CSV at
`results/heuristic/runs_<timestamp>.csv`, with a header, because it is read by pandas and by
people, and because it appends across a sweep that may take minutes.

## Columns

| Column | Type | Rule |
|---|---|---|
| `seed` | int | From `results/tracks/seed_split.json`, `train.accepted_seeds` |
| `controller` | string | `MostOpen` or `WeightedAverage` |
| `ray_count` | int | The configuration this run used |
| `ray_fov_deg` | float | |
| `ray_length_m` | float | |
| `completed_lap` | bool | `true` only when every checkpoint was awarded in order |
| `lap_time_s` | float or empty | **Empty, not zero, when no lap completed.** Zero is a lap time |
| `checkpoints_awarded` | int | |
| `checkpoints_total` | int | The track's own count, so a row is readable without the track file |
| `checkpoints_skipped` | int | Non-zero means a corner was cut |
| `wall_contacts` | int | |
| `end_reason` | string | One of `LapComplete`, `TimeLimit`, `WallContact`, `WrongWay`, `FellThrough` |
| `steer_p95_dsteer` | float | \|delta steer\| P95 resampled to 14.08 Hz |
| `steer_sign_changes_per_s` | float | Direction reversals per second |
| `time_scale` | float | What the run was simulated at |
| `duration_s` | float | Simulated seconds elapsed, whatever the outcome |

Numbers are written with `InvariantCulture`. The development machine's locale is `bs-Latn-BA`,
which writes `42,3` for `42.3`, and this project has now hit that bug three times: in the track
loader's refusal messages, in `LapReport`, and in `StabilityMonitor`'s detail strings. A CSV with
comma decimals inside comma-separated fields is not recoverable by a reader that did not write it.

## Rules that make the file worth having

**Every run writes a row, including a failure.** A sweep that recorded only completed laps would
report an acceptance rate computed over a denominator that silently shrank. `end_reason` is what
makes a failure legible rather than absent.

**A row is self-describing** (SC-006). The sensing configuration and the controller are repeated on
every row rather than being stated once in a header or implied by the filename. The duplication is
deliberate: a reader who finds one row in isolation, or a pandas filter that slices across
configurations, must not have to reconstruct context from somewhere else.

**`time_scale` is recorded because the sweep is accelerated** (research R4). A run at 8x that
disagrees with the same seed at 1x is a defect in the sweep rather than a property of the
controller, and without this column that defect would be invisible in the results.

**`lap_time_s` is empty rather than zero on failure.** An aggregate that averages zeros for failed
runs reports a fast sweep. This is the same class of mistake as counting only successes, arriving
through arithmetic instead of through omission.

## What the reporter must produce from it

Per controller and per sensing configuration, over the seed set rather than per seed (FR-012):

- Completion rate, with the count and the denominator, not only the percentage
- Lap time: n, mean, standard deviation, min, max, computed over completed laps only and stating
  how many were excluded
- Both smoothness measures with the same descriptive statistics
- Wall contacts and skipped checkpoints, totalled and per seed
- The distribution of `end_reason`

And, before any of it is interpreted, **the run-to-run spread** measured under FR-011, so that
FR-015 can be answered: a difference between configurations smaller than that spread is not a
finding, and the report must say so in those words rather than presenting the number and letting a
reader assume it means something.

The two smoothness measures and the outcome measures are reported side by side and **never
collapsed into a single verdict** (FR-009). A controller that steers more smoothly and completes
fewer laps is a real result, and it is the result this feature is most likely to produce.
