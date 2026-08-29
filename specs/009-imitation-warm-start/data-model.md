# Data model: the imitation warm start

## The demonstration set

| | |
|---|---|
| Name | `unity/SelfDrivingSim/Assets/Demonstrations/heuristictrain34.demo`. **Recorded as `heuristic_train34` and written without the underscore**: ML-Agents sanitises `DemonstrationName`. The scene field and the file name differ, and the file name is the one `demo_path` must use |
| Producer | `DemonstrationRecorder` on the agent, driven by `DrivingAgent.Heuristic` delegating to `HeuristicDriver.Decide()` |
| Observation | the agent's own 19 value vector, unchanged. This is the whole reason the source is `HeuristicDriver` and not the M4 BC policy |
| Action | 2 continuous values, `(steer, throttle)`, clamped to `[-1, 1]` |
| Sample rate | **12.5 Hz**, being one sample per decision at `DecisionPeriod: 4`. Not a setting, a structural property (R2) |
| Reaction mode | `Immediate`, stated because no committed CSV records it (R4) |
| Seeds | the 34 training seeds in `results/tracks/seed_split.json`, copied to `results/rl/demo_seeds.json` |
| Committed | yes, through LFS, with `*.demo` added to `.gitattributes` (R9) |
| Recorded | 34,000 info/action pairs, 65 episodes, 4.42 MB, summed reward 4118.14, source completed 34 of 34 with zero wall contacts |
| Cap | `NumStepsToRecord: 34000`. **Not optional.** At 0 the recorder runs for as long as the scene does, and `SweepRunner` finishing does not stop `DrivingAgent` starting new episodes: the first attempt recorded four hours past the sweep and was discarded |
| Declared overrun | the 34 runs account for about 33,509 steps, so about 491 steps, 1.5 per cent, are the expert still driving the final seed. Seed 40 is slightly over-represented |

**The pairing carries a one-decision lag and this is a property of the file, not a defect in the
recording procedure.** Research R5 traced it: the demonstration writer runs before the brain
decides, so each observation is stored with the previous decision's command. At `DecisionPeriod: 4`
that is **80 ms**. It is not configurable, it is what every ML-Agents imitation example trains on,
and it is stated here so that nobody later reads the demo file as `(obs_t, a_t)`.

**Training seeds only.** The held-out lap is the criterion this project has failed three times.
Demonstrations on the ten evaluation seeds would answer a different question, so the seed list is
committed next to the file and is checkable against `seed_split.json`.

## The trainer block

Added to `config/ppo_car.yaml` under `behaviors.CarDriver`. Nothing else in that file changes.

| Key | Value | Why this value, decided before the run |
|---|---|---|
| `demo_path` | the file above | Required. `demo_to_buffer` validates the observation and action spec against the policy's and raises on a mismatch, which is a free contract test (R7) |
| `strength` | **0.5** | The imitation loss scales the policy learning rate. Full strength would make the early policy a copy of the expert; half keeps PPO's own gradient meaningful from the first update. Inside the range ML-Agents documents for imitation as an auxiliary loss |
| `steps` | **500000** | Ten per cent of the 5,000,000 budget. The schedule is `LINEAR` only when this is above zero (R8), so this is what makes it a **warm start** rather than an imitation run: the loss anneals to nothing over the first tenth and the remaining nine tenths are pure PPO against an unchanged reward table |
| `samples_per_update` | **2048** | At the default 0, every update iterates the whole demonstration buffer (R8), which lands on SC-009's throughput comparison. 2048 matches the trainer's `batch_size` so one update costs one batch |
| `num_epoch` | not set | Inherits the trainer's `num_epoch: 3`. Named here so the inheritance is a decision rather than an oversight |
| `batch_size` | not set | Inherits the trainer's `batch_size: 2048`, same reason |

**The reward table is untouched and that is the point.** `behavioral_cloning` is an auxiliary loss
on the policy, not a reward signal. GAIL would add one, would change the table `DESIGN.md` 4.5 pins,
and would make cumulative reward incomparable to every run in M3. FR-005 forbids it and the spec
names GAIL as the follow-up it is.

## The measures

| Measure | Definition | Source | Why it exists |
|---|---|---|---|
| demonstration lap completion | laps completed by the scripted driver through the agent's action path, per training seed | the Phase 3 sweep | FR-004. 34 of 34 was measured at 50 Hz and does not carry over to 12.5 Hz automatically |
| demonstration speed tracking | mean absolute error between `car.SpeedMs` and `TargetSpeedMs` over a run | the Phase 3 sweep | R3. If lap completion falls, this is where it fell, because the throttle is bang-bang against a `0.25 m/s` deadband and one decision is long enough to move the speed `0.47 m/s` |
| `Losses/Pretraining Loss` | the BC module's MSE on continuous actions | TensorBoard, written by the trainer | The cheap proof the warm start is applied at all rather than silently absent. Checked early, not only at the end |
| markers per episode | unchanged from feature 007 | `episode/` stats | The headline, read against 1.4987 and the 0.035 gate |
| end-reason mix | unchanged from feature 008 | `episode/` stats | Read whole. A wall share that falls into a rising stall share is a traded failure, which is the trap 008 named |

## What is read against what

| Metric | Baseline | Gate | Source of the gate |
|---|---|---|---|
| markers per episode | **1.4987** | **0.035** | `results/rl/progress_spread.md`, feature 007 |
| laps on held-out seeds | 0 of 10 | any lap at all | the floor is exactly zero, in either inference mode |
| the 80 per cent bar | 0 per cent | 80 per cent | feature 006 SC-002, restated unchanged |
| wall share of end reasons | 59.1 per cent | reported, not gated | read together with the stall share |
| demonstration lap completion | **34 of 34** at 50 Hz | reported, and it can cancel the feature | feature 005, `results/heuristic/` |
| throughput | 903 and 927 steps/s | reported, not gated | the BC module adds work per update (R8) |
| `lapsToComplete` | 3 | not a metric | stated wherever a lap count appears, because a recorded lap is three laps |

**The gate carries feature 007's caveat rather than a fresh measurement**, for the third time.
Three runs estimate a standard deviation to roughly 50 per cent, so clearing 0.035 is credible,
failing to clear it is weaker evidence than it looks, and a result landing near it earns a fresh
three-run spread rather than a verdict.

## What is deliberately not modelled

- **GAIL.** It adds a learned reward signal. Out of scope by FR-005, named in the spec as the
  follow-up.
- **Any change to `DecisionPeriod`.** FR-006 pins it. Lowering it to save the cadence gate would
  change the clock every M3 comparison was measured at, which would cost more than the gate is
  worth.
- **Correcting the recorded pairing.** R5 says the only route is patching a package under
  `Library/PackageCache`, which a clean clone does not reproduce. The lag is documented instead.
- **Re-measuring the 0.035 gate.** Reused with its caveat, as features 008 did.
- **The M4 BC policy as a demonstration source.** It reads camera images and the agent reads a 19
  value vector. No shared observation space, no shared weights, no shared demonstrations. This is
  the finding that reshaped the feature and it is recorded rather than quietly worked around.
