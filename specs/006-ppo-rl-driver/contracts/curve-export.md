# Contract: Committed Training Curve

**Feature**: `006-ppo-rl-driver` | **Files**: `results/rl/curves/<run-id>.csv`

FR-018 requires the recorded curves to exist in a clean clone. The repository ignores the trainer's
raw event files and checkpoints (`.gitignore` lines 46 to 48), and should keep ignoring them. The
bridge is one distilled CSV per run, written by `python/rl/export_curves.py` and committed (R10).

## Schema

One row per summary point, which is every `summary_freq` steps.

| Column | Type | Source series |
|---|---|---|
| `run_id` | string | the run this row belongs to, repeated on every row |
| `step` | int | trainer step |
| `cumulative_reward` | float | `Environment/Cumulative Reward` |
| `episode_length` | float | `Environment/Episode Length` |
| `policy_loss` | float | `Losses/Policy Loss` |
| `value_loss` | float | `Losses/Value Loss` |
| `entropy` | float | `Policy/Entropy` |
| `reward_checkpoint` | float | `reward/checkpoint`, this feature's own series |
| `reward_wrong_way` | float | `reward/wrong_way` |
| `reward_wall` | float | `reward/wall` |
| `reward_step` | float | `reward/step` |
| `reward_speed` | float | `reward/speed` |
| `reward_jerk` | float | `reward/jerk` |
| `end_wallcontact` | float | `episode/end_wallcontact`, a **count** over the summary window |
| `end_lapscompleted` | float | `episode/end_lapscompleted` |
| `end_stalled` | float | `episode/end_stalled` |
| `end_steplimit` | float | `episode/end_steplimit` |
| `end_trackswapped` | float | `episode/end_trackswapped` |

**`run_id` is repeated on every row on purpose**, the same decision feature 005 made for its run
record: a row found in isolation, or a `pandas` frame concatenating several runs, must not need
the filename to say which run it came from.

A series the trainer did not emit writes as empty rather than zero. Zero is a value a loss can
take, and an aggregate that averages absent points as zeros reports a run that never happened.

**The five `end_*` columns are counts, and only because the agent asks for that aggregation.**
`StatsRecorder` averages by default, and the mean of a value that is always `1.0` is `1.0` however
often it was written. `ppo_car_smoke` and `ppo_car_v01` both reported exactly `1.0000` for every
reason that occurred, which says which reasons happened and nothing about how often, so T036's
distribution had to be derived from the wall term instead of read. `DrivingAgent.ReportEpisode`
passes `StatsAggregationMethod.Sum` for these five, and for these five only.

**A run trained before that change must not be re-exported into this schema.** Its event files do
carry `episode/end_*`, so the exporter would happily write them — as the constant `1.0000` that
means nothing, in a column headed like a count. The two runs that predate the change,
`ppo_car_smoke` and `ppo_car_v01`, keep their twelve-column CSVs exactly as committed. Concatenating
them with a later run leaves the five columns absent for those rows, which is the truthful answer
and the one the empty-not-zero rule already gives everywhere else.

`end_trackswapped` is not a policy outcome. It counts episodes the training area cut short to put a
different track under the car, and it exists so the reported episodes are the same set the trainer
averages `Environment/Cumulative Reward` over. Reading it as a driving result is a mistake; reading
it as roughly one episode in six at a five-episode rotation is what it is for.

## What the export must not do

- **It must not smooth.** TensorBoard's default view applies exponential smoothing for display.
  Exporting the smoothed series would commit a picture rather than a measurement, and two runs
  smoothed at different window sizes are not comparable.
- **It must not resample.** Rows land on the trainer's own summary steps, which is why
  `summary_freq` is pinned in the trainer config.
- **It must not drop the tail.** A run that ended early, by interruption or by crash, exports the
  rows it has, and the run's log row says it ended early.

## Reproduction

```text
.venv-mlagents\Scripts\activate
python -m python.rl.export_curves results/ppo_car_vNN --out results/rl/curves/ppo_car_vNN.csv
```

The export reads the event files with the reader that ships with the trainer's own TensorBoard
dependency, so it adds no package to the pinned environment.

## What stays ignored

Raw `events.out.tfevents.*`, `checkpoint.pt` and the trainer's intermediate `.onnx` snapshots.
The final exported model is the exception and is committed through LFS (R11).
