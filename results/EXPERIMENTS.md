# Experiments

One entry per training run, RL or BC, written **in the same session as the run**.

Constitution Principle VI: an unlogged run did not happen. This is not bookkeeping for its own
sake. The defence is an individual interview, and "I tried a few things and this one worked" is
not an answer to "why this value". A run that changed nothing is still worth an entry, because
knowing that a change made no difference is a result.

## How to fill this in

- **Run ID** is the same string passed to the trainer, so the row and the output directory
  cannot drift apart. RL uses `ppo_car_vNN`; BC uses `bc_<policy>_vNN`.
- **Changed** is what differs from the previous run of the same kind, in one line. If it needs
  an "and", that is two experiments and they should have been two runs.
- **Outcome** is what the numbers said, not whether it felt better.
- **Kept** records whether the change survived into the next run. A rejected change with its
  reason is more useful later than a row that quietly disappears.

Details that do not fit a table live beside the run: `results/bc/run_<id>/` for BC,
`results/tensorboard/` for RL.

## BC runs (M4)

| Date | Run ID | Changed | Outcome | Kept |
|---|---|---|---|---|
| 2026-08-05 | `bc_unbalanced_v01` | First BC run. PilotNet, 252,219 parameters, block-holdout split with an 8 s guard, three cameras with jittered offset, no balancing | val MSE **0.086670** against a mean-predictor baseline of 0.153623, so it beat the baseline. Early stopped at epoch 13, best at epoch 8, 337 s on the RTX 3050 | Yes, this is the reference run |
| 2026-08-05 | `bc_balanced_v01` | Exactly one thing: exact-zero steering samples downsampled to 27 percent, 77,871 to 66,783, zero share 20.35 to 7.12 percent. Same seed, split, architecture and hyperparameters | val MSE **0.090899** against a baseline of 0.153992. Beat the baseline, but is **0.004229 worse than unbalanced on accuracy**. Early stopped at epoch 13, 291 s | Both kept. The pair is one experiment: the accuracy loss is the expected price, and whether it buys a closer match to the human distribution is the other axis, measured in `results/bc/comparison.md` |
| 2026-08-08 | `bc_repro_a_v01` | Nothing. Byte-identical configuration to `bc_unbalanced_v01`, same seed 42, run again to measure the reproduction spread (T040) | val MSE **0.086685**, 0.000015 from the reference run. Best at epoch 8, same epoch as the reference. 371 s | Not a candidate model. Kept as evidence for the tolerance in research R13 |
| 2026-08-08 | `bc_repro_b_v01` | Nothing, again. Third run of the same configuration | val MSE **0.086411**, 0.000259 from the reference. Best at epoch 8 again. 328 s. Three runs give range **0.000273**, stdev 0.000154, so the **tolerance is set at 0.0005** | Not a candidate model. The result that matters is that the 0.004229 balancing delta is 15 times this range, so R12 survives the noise |

Notes on the pair, since a table row cannot carry them:

- The two runs differ in the balancing policy and the training sample count, and `compare_runs`
  refuses to render if anything else differs. That refusal is what makes the difference above
  attributable to balancing rather than to balancing plus something unnoticed.
- Both are scored on the same 5,576 unbalanced validation samples (FR-022). Balancing is a
  property of what the model was shown, so applying it to validation would move the yardstick
  along with the model.
- Beating the baseline was not a formality. Near-zero steering dominates this recording, so
  predicting the training mean is a strong strategy, and a run losing to it would have been a
  reportable result rather than a failure (SC-003).
- The learning rate was **not** tuned. Sweeping it against the validation set and then
  reporting validation error would make the headline figure optimistic by an unstatable
  amount. Early stopping does select on validation, which biases it the same way, and that is
  recorded in `config.py` rather than hidden.
- The two `bc_repro_*` rows are **not** four BC models. They are three runs of one configuration,
  logged individually because Principle VI counts runs rather than conclusions, and an
  unlogged run that produced a tolerance everything else is judged against would be the worst
  one to leave out. Only `bc_unbalanced_v01` and `bc_balanced_v01` are reported as results.
- The reported validation errors agree to about the third decimal. The sixth decimal quoted in
  `comparison.md` is below the noise floor, and research R13 says so rather than the tables
  quietly implying a precision the process does not have.

## RL runs (M3)

| Date | Run ID | Changed | Outcome | Kept |
|---|---|---|---|---|
| 2026-08-17 | `ppo_car_smoke` | First run of anything. 12 training areas, 34 training seeds rotating every 5 episodes, reward table as DESIGN 4.5 fixes it, `config/ppo_car.yaml` at its provisional 500k budget | Connected on package 4.0.3 / communication 1.5.0. **500,000 steps in 814.9 s**, so 660 steps/s in steady state. **The policy did not learn.** Cumulative reward went from -4.852 over the first ten summaries to -4.332 over the last ten, inside a per-summary spread of 2 to 3. Checkpoint reward fell, 0.321 to 0.219, against the 24 markers a lap needs. Episodes ran 387 to 727 steps, so 8 to 15 s, and the wall term sat near -3.0 throughout | Not a candidate model. Kept as the throughput measurement (T030) and as the first evidence that 500k steps is not a budget at which this reward produces progress |
| 2026-08-18 | `ppo_car_v01` | One thing: the budget, 500k to **5,000,000 steps**, the value T031 set from the pilot's throughput. Same twelve areas, same seeds, same reward weights, same `config/ppo_car.yaml` otherwise. Seed pinned at 42, which the pilot left to the trainer | **5,000,000 steps in 7,308.3 s across two segments**, 684 steps/s. **The budget is not the explanation.** Ten times the pilot's length and the total is flat: first and last 250 summaries are -4.573 and -4.409, against a standard deviation of 0.512 across the 500 summary means. Checkpoint reward *fell again*, 0.394 to 0.245, so **0.249 markers per episode in the late phase against the 24 a lap needs**. `episode/end_lapscompleted` never appears, at any point in 5M steps. What did move is the policy learning **to stall instead of to drive**: wall share 60.1 to 45.2 percent, episode length 465 to 548 steps, step cost -1.797 to -2.031 | Not a candidate model. Kept as the run that retires the budget hypothesis, and as the evidence that the reward's degenerate solution is passivity |
| 2026-08-19 | `ppo_car_spread_a` | Nothing about the policy. First of the three T046 spread runs: `config/ppo_car_spread.yaml`, which differs from the pinned config in `max_steps` alone (5M to the **2,000,000** T045 chose), `--seed=1`. Same twelve areas, same seeds, same reward weights. **First run carrying the fixed instrumentation**, so its end-reason counts are counts | **2,000,000 steps in 2,834.0 s**, 706 steps/s, uninterrupted. Cumulative reward mean **-4.5070, sd 0.4911** over 200 summaries, range -6.0466 to -3.0214. First 25 to last 25 summaries: -4.7968 to -4.3147, **+0.4820**. **The v01 signature reproduces at 2M**: wall term -2.5283 to -1.9120 and episode length 463.6 to 540.6 steps, while checkpoint reward *fell* 0.2541 to 0.2248 and step cost went -1.4809 to -1.7808. Over 4,990 episodes: **45.6% wall contact, 41.0% stalled, 13.4% track-swapped, zero laps completed, zero step-limit**. Those are read counts, not derived shares | Not a candidate model. Kept as run a of the three T047 needs. The seed changed and the stall-not-drive result did not, which is the first evidence it is a property of the reward rather than of seed 42 |
| 2026-08-19 | `ppo_car_spread_b` | Run b of three. Identical to `ppo_car_spread_a` in every respect except `--seed=2`, which is what T046 requires of the set | **2,000,000 steps in 2,577.4 s**, 776 steps/s, uninterrupted. Cumulative reward mean **-4.6613, sd 0.5022** over 200 summaries, against a's -4.5070 and 0.4911. First 25 to last 25: -4.9286 to -4.4381. The same shape again: episodes lengthen 491.2 to 529.4 steps while checkpoint reward *falls* 0.3351 to 0.2192, the steepest checkpoint decline of the three runs so far. Over 5,093 episodes, 47.9 per cent wall contact, 38.9 per cent stalled, 13.3 per cent track-swapped, zero laps | Not a candidate model. Run b of the three T047 needs. **Two seeds now agree to within 0.15 on the run mean**, which is the first direct evidence about the size of the noise floor, though the number T047 reports needs all three |
| 2026-08-19 | `ppo_car_spread_c` | Run c of three. Identical to a and b except `--seed=3` | **2,000,000 steps in 2,709.4 s**, 738 steps/s, uninterrupted. Cumulative reward mean **-4.6722, sd 0.5360** over 200 summaries. Over 4,866 episodes, 47.0 per cent wall contact, 39.8 per cent stalled, 13.2 per cent track-swapped, zero laps. Late-phase checkpoint reward 0.3212, the highest of the three, and still an eighth of one marker against the 24 a lap needs | Not a candidate model. Completes the set T047 measures. **No run in the set completed a lap**, and the end-reason mix is the same to within two points across all three seeds |
| 2026-08-20 | `ppo_car_jerk_lo` | One thing: `RewardModel.JerkPenalty`, -0.005 to **-0.001**. Same `config/ppo_car_spread.yaml` at 2M, same `--seed=1` as `ppo_car_spread_a`, same twelve areas, every other weight untouched. T048's first candidate, asking whether the smoothness charge was suppressing the steering exploration needed to reach a marker | **2,000,000 steps in 3,164.4 s**, 632 steps/s, uninterrupted. Cumulative reward mean **-4.2757, sd 0.4996** over 200 summaries. **Against the baseline rescored to this candidate's own table (-4.3310) the difference is +0.0553, which does not clear the 0.19 gate**, and on `reward/checkpoint`, which this candidate does not touch, it is **-0.0415 against a 0.0631 gate**, also not clearing. The jerk term fell -0.3531 to -0.0775 where an unchanged policy would give exactly -0.0706, so the wheel is thrashed slightly *more* once it is cheaper. Nothing else moved: 5,162 episodes at 48.0 per cent wall, 38.6 per cent stalled, 13.3 per cent track-swapped against the baseline's 46.8 / 39.9 / 13.3, **zero laps**, and checkpoint reward *fell again* across the run, 0.2793 to 0.2005 | Not a candidate model, and the weight is **not kept**. Recorded as a change that made no measurable difference, which is a result and not a gap: the jerk penalty was not what stopped this policy driving |
| 2026-08-20 | `ppo_car_wall_lo` | One thing: `RewardModel.WallPenalty`, -5.0 to **-1.0**. The jerk scale is back at the pinned -0.005, so this run differs from the baseline in the wall terminal alone. Same `config/ppo_car_spread.yaml` at 2M, same `--seed=1`. T048's second candidate, aiming at the ordering the spread runs exposed: stalling out costs about -3.0 and a wall cost -5.0, so doing nothing was the cheaper option | **2,000,000 steps in 2,598.0 s**, 770 steps/s, uninterrupted. Cumulative reward mean **-3.1479, sd 0.5592**. Against the baseline rescored to this candidate's table (-2.8294) the difference is **-0.3185, which clears the 0.19 gate in the worse direction**. **The mechanism did work**: over 5,350 episodes the end-reason mix is 51.4 per cent wall and 35.4 per cent stalled against the baseline's 46.8 and 39.9, a shift of about 4.5 points that holds across all four quarters rather than fading. `reward/checkpoint` is +0.0318, inside its 0.0631 gate, but its quarter trend runs 0.286, 0.237, 0.269, **0.339** where every baseline is flat near 0.25 and every earlier run fell. **Zero laps**, as in every run of this feature | Not a candidate model, and the weight is **not kept**: it made the return measurably worse. Kept as the run that shows the wall terminal is load-bearing on *which* failure the policy chooses without being what stops it driving, and as the first curve in M3 whose checkpoint reward rises late |
| 2026-08-24 | `ppo_car_speed_hi` | One thing: `RewardModel.SpeedReward`, 0.001 to **0.002**, with the jerk scale and the wall terminal both back at their pinned values, so this run differs from the baseline in the speed scale alone. Same `config/ppo_car_spread.yaml` at 2M, same `--seed=1`. T048's third candidate, added after the first two came back negative, aimed at the imbalance the spread decomposition exposed: a step cost of -1.676 a run against a speed reward of +0.0069 | **2,000,000 steps in 2,518.6 s**, 794 steps/s, uninterrupted. Cumulative reward mean **-4.6439, sd 0.5265**. Against the baseline rescored to this candidate's table (-4.6066) the difference is **-0.0373, which does not clear the 0.19 gate**; on `reward/checkpoint`, which this candidate does not touch, -0.0101 against 0.0631, also not clearing. **The term responded to the weight and the policy did not**: `reward/speed` went +0.0069 to +0.0150 where an unchanged policy would have given exactly +0.0138, so implied mean `v_norm` moved 0.00410 to 0.00459, a **12 per cent** change in speed for a doubled payment. End reasons 49.2 / 37.7 / 13.1 against 46.8 / 39.9 / 13.3 over 5,153 episodes, **zero laps**, and checkpoint reward fell across the run again, 0.276 to 0.232 by quarter | Not a candidate model, and the weight is **not kept**. The pre-registered negative reading: the reward table cannot be fixed by scaling the step and speed weights, so what stops this policy driving is exploration rather than the numbers in the table |
| 2026-08-26 | `ppo_car_007_spread_a` | **Feature 007's reward table**, which is feature 006's six terms plus a seventh: the weighted change per physics step in the car's clamped, unwrapped arc position along the 24 markers. Weight derived per track as `0.5 * 24 / ChainLength`, so a lap pays 12.0. Also new: `episode/markers` and `episode/physics_steps` instrumentation. `config/ppo_car_spread.yaml` at 2M, `--seed=1`, twelve areas, everything else untouched. First of the three T025 to T027 spread runs | **2,000,000 steps in 2,540.7 s**, 787 steps/s, uninterrupted. Markers per episode **0.2608** run mean, 0.2541 over the last 50 summaries. `reward/progress` **0.1379** per episode, which at 0.05970 per metre is **2.31 m of net progress per episode**, about 1.15 per cent of a lap. Over 5,046 episodes: 47.2 per cent wall, 39.6 per cent stalled, 13.2 per cent track-swapped, **zero laps**. `episode/physics_steps` over `Environment/Episode Length` is **3.1652** against the ceiling of 4 | Not a candidate model. Run a of the three T028 needs. **An earlier attempt at this run was killed at 1,440,000 steps** and is discarded, kept only as `results/rl/ppo_car_007_spread_a.killed_at_1440k.log` |
| 2026-08-26 | `ppo_car_007_spread_b` | Run b of three. Identical to `ppo_car_007_spread_a` except `--seed=2` | **2,000,000 steps in 2,597.9 s**, 770 steps/s, uninterrupted. Markers per episode **0.2290** run mean, 0.2326 over the last 50. `reward/progress` 0.1238, which is 2.07 m net per episode. Over 5,181 episodes: 48.9 per cent wall, 37.9 per cent stalled, 13.2 per cent swapped, **zero laps**. Step ratio **3.1536** | Not a candidate model. Run b of three. The lowest marker count of the set and still within 0.032 of the highest, which is what makes the gate small |
| 2026-08-26 | `ppo_car_007_spread_c` | Run c of three. Identical to a and b except `--seed=3` | **2,000,000 steps in 2,649.4 s**, 755 steps/s, uninterrupted. Markers per episode **0.2576** run mean, 0.2714 over the last 50, the highest late-phase figure of the set. `reward/progress` 0.1356, which is 2.27 m net per episode. Over 4,993 episodes: 47.2 per cent wall, 39.5 per cent stalled, 13.3 per cent swapped, **zero laps**. Step ratio **3.1627** | Not a candidate model. Completes the set T028 measures. **No run in the set completed a lap**, and markers per episode means 0.2491 across the three against feature 006's 0.249, so the term did not move the metric at this budget. The gates are in `results/rl/progress_spread.md`, written before any candidate run existed |
| 2026-08-26 | `ppo_car_007_progress` | **The T029 candidate.** One change from feature 006's `ppo_car_v01`: the reward table gains the dense progress term. Full baseline budget, `config/ppo_car.yaml` reused unchanged at 5,000,000 steps, `--seed=42` to match v01 exactly, same twelve areas, same seeds, every existing weight untouched | **5,000,000 steps in 5,395.4 s**, 927 steps/s, uninterrupted. **Markers per episode 1.4987 run mean and 2.6975 over the last 50, against a baseline of 0.2490 and a gate of 0.035.** By quarter 0.3477, 0.9794, 2.1148, 2.5528, which rises monotonically rather than spiking. **Eight episodes completed the full three-lap requirement** over 13,851 episodes, where feature 006 completed no lap at all across nine runs and more than 12,000,000 steps. `episode/end_lapscompleted` fires only at `LapCount >= lapsToComplete`, and `TrainingArea.prefab` sets that to 3, so each of those eight drove three consecutive laps rather than one. `reward/progress` reaches 1.3843 per episode late, which is 23.2 m of net progress, about 11.5 per cent of a lap, against 2.2 m in the spread set. End reasons 59.1 per cent wall, 27.4 per cent stalled, 13.5 per cent swapped, against the spread set's 47.7 / 39.0 / 13.2. **FR-010 does not hold on this run**: the seven terms sum to the trainer's cumulative reward on 4.8 per cent of rows, residual mean +0.3030 | **The first candidate in M3 that moved the metric it was aimed at**, and the first policy in this project to complete a lap. Model kept and promoted for the T034 to T037 evaluation. The stall fall is **not** clean: see the note below |
| 2026-08-27 | `ppo_car_008_budget` | **The wall terminal.** One change from `ppo_car_007_progress`: a barrier contact charges the same pinned -5.0 and ends the episode only once a budget of **3** contacts is spent. The penalty is untouched, so this tests the termination rather than the weight, which is what feature 006's `ppo_car_wall_lo` tested. Also restored: `MaxStep = 6000` on `TrainingArea.prefab`, which `DESIGN.md` had claimed since M3 and the prefab had never carried. `config/ppo_car.yaml` unchanged at 5M, `--seed=42` | **5,000,000 steps in 5,534.6 s**, 903 steps/s, uninterrupted. **Markers per episode 0.5297 against the baseline's 1.4987, a difference of -0.9689 that clears the 0.035 gate in the worse direction.** By quarter 0.3832, 0.4376, 0.5630, 0.7351, still rising but at a fraction of the baseline's 0.3477 to 2.5528. **Zero laps.** The end-reason mix inverted: wall contact 59.1 to **23.2** per cent, stalled 27.4 to **53.8** per cent, and the restored step limit fired on **608 episodes**, 6.9 per cent, where it had never fired before. Episodes ran 612.0 trainer steps against 485.4, so 8,843 episodes fitted in the budget instead of 13,851. `reward/progress` fell 0.7729 to 0.2827, which is 4.74 m of net progress per episode against 12.95 m | Not a candidate model, and the budget is **not kept**. **The terminal was load bearing and lifting it made the policy worse.** Recorded as the run that exonerates the wall terminal the way `ppo_car_wall_lo` exonerated the wall penalty |

Notes on the first full run:

- **The budget hypothesis is dead, and that is the result.** The pilot could not distinguish "too
  few steps" from "wrong weights". At 5M the total is flat over the whole run, and the first-ten to
  last-ten improvement of 0.765 that a reader might quote is not one: split by halves the same
  series moves 0.163 against a summary-mean spread of 0.512. The two remaining candidates from the
  pilot, the jerk penalty's scale and the -5.0 wall terminal, are now the next two runs.
- **The policy did learn something, and it is the wrong thing.** Avoiding the barrier and reaching
  markers are separable, and it took the first: wall share fell by 15 points while checkpoint reward
  fell too, and episodes got 83 steps longer. Driving less is a cheaper way to stop paying -5.0 than
  driving better, and nothing in the current weights prefers the second. That is a reward design
  finding rather than a tuning one.
- **Only two end reasons occur in 5M steps**, `end_stalled` and `end_wallcontact`, splitting about
  evenly (50.1 / 49.9 over the run, 48.3 / 51.7 in the late fifth). No lap was ever completed and the
  6000-step cap was never reached.
- Entropy fell 1.4137 to 1.3220 over 5M steps and floors there, so the policy stayed near its initial
  spread for the whole run rather than committing to a behaviour.
- **The run was interrupted once and resumed**, which the reproduction needs to know. Segment one ran
  0 to 1,210,000 in 1,800.5 s and was killed by a 30-minute cap in the tooling that launched it, not
  by anything in the trainer; segment two resumed from checkpoint `CarDriver-1199901` and ran to
  5,000,000 in 5,507.8 s, exiting cleanly. The trainer warned `Training status file not found`,
  because a killed process never writes `run_logs/training_status.json`. What that costs is
  checkpoint bookkeeping and the lifetime stats history. It does **not** cost the schedules:
  `ppo/optimizer_torch.py:108` computes the decayed learning rate, epsilon and beta from
  `policy.get_current_step()`, which the checkpoint restored, so the linear decay resumed in place.
  The two segments' logs are committed separately, and the run directory holds two event files that
  the exporter merges by tag and step.

### FR-008 does not hold, in this run or in the pilot

The requirement is that the six reported terms sum to the agent's cumulative reward. Measured over
every summary rather than one of them, they do not:

| Run | Summaries | Mean residual | Std | Share off by more than 0.05 |
|---|---|---|---|---|
| `ppo_car_smoke` | 50 | -0.675 | 0.362 | 96.0 percent |
| `ppo_car_v01` | 500 | -0.694 | 0.345 | 97.4 percent |

The residual is the terms' sum minus `Environment/Cumulative Reward`, so the reported breakdown is
about 0.69 more negative than the total it is supposed to decompose, consistently and in both runs.

The pilot's entry above says the export "confirmed FR-008 on live data" at step 10000, where the
terms summed to -5.094 against -5.086. That check was correct and the conclusion drawn from it was
not: the step-10000 row is one of the 4 percent that happen to agree, and one row cannot establish a
property of 500. The claim is withdrawn here rather than left standing.

What the discrepancy is has not been established and is not guessed at in this entry. The obvious
candidate is that the two numbers average over different sets of episodes - `ReportEpisode` runs on
the paths in `DrivingAgent.Finish` and the step-limit branch, while the trainer's cumulative reward
counts every episode the agent processor sees - but that is a hypothesis for an instrumented check,
not a finding. It does not affect the per-term *trends* this entry rests on, which are what FR-008
was written to expose, and it does affect any claim that a term's absolute value accounts for the
total.

### The end-reason distribution cannot be read from the instrumentation as built

T036 asks for the distribution of end reasons. `DrivingAgent.cs:369` records each one as
`stats.Add("episode/end_" + reason, 1f)`, and `StatsRecorder` averages by default, so the mean of a
constant 1.0 is 1.0 however often it occurs. Both tags read exactly `1.0000` over the whole run and
over the late phase: the series say *which* reasons happened and carry no information about *how
often*. Counting needs `StatsAggregationMethod.Sum`.

The shares quoted above are therefore derived rather than read: the wall term is exactly -5.0 once
on an episode that ends against a barrier and 0 otherwise, so its per-episode mean divided by -5.0
is the wall share, and with only two reasons occurring the stall share is the complement. The
derivation is sound but indirect, and the aggregation method should be fixed before a run whose
conclusion depends on these counts.

Notes on the first run, since a table row cannot carry them:

- **The throughput is the good news.** `ENVIRONMENT.md` warned that 700 steps/s on 3DBall was an
  upper bound and that WheelCollider physics with 13 raycasts would be "substantially slower". It
  is not: 660 steps/s steady state with twelve areas. A 5M-step run is about 2.1 hours, which is
  what makes the tuning FR-007 expects affordable at all.
- **What the run does not say.** It does not say the reward is wrong, or that the budget is the
  only problem, or that the wall penalty is too harsh. Those are the candidate explanations and
  each one is a separate run with one changed thing (FR-007). What it says is that at this budget,
  with these weights, the agent ends episodes against a barrier after 8 to 15 seconds having taken
  a fifth of one marker, and that not one of the six reward terms trended anywhere over 500k steps.
- The per-term series are what make that legible rather than guessed. `reward/checkpoint` flat near
  0.2 underneath a total that wanders between -3.7 and -5.1 is precisely the case FR-008 exists to
  expose, and it was visible in TensorBoard while the run was going rather than afterwards.

### Both instrumentation defects are fixed, and one residual is left unexplained

`ppo_car_fr008_check`, 2026-08-19: 100,000 steps in 165.0 s, the pinned config with `max_steps`
alone reduced. Not an experiment and it gets no table row - it exists to check that the two defects
recorded above are gone, and its curve is committed at
`results/rl/curves/ppo_car_fr008_check.csv`.

**The end-reason series are counts now.** `end_wallcontact` reads 18, 26, 11, 25, 8, 13, 27, 5, 18,
15 over the ten summaries instead of the flat 1.0000 that carried no frequency information.
`end_trackswapped` is non-zero in every window, which is the swap-ended episodes reaching
`ReportEpisode` for the first time.

**The two halves now average over the same episodes.** `reward/wall` equals
`-5.0 x end_wallcontact / total_episodes` exactly on all ten rows - at step 10000,
`-5 x 18/39 = -2.3077` against a recorded -2.307692. That identity is the real check: it can only
hold if the per-term means and the end counts are divided by the same denominator, which is what
`SwapTo` calling `EndEpisode` directly had broken.

**The systematic residual is gone; a small one is not.** `cumulative_reward` minus the six terms:

| step | 10000 | 20000 | 30000 | 40000 | 50000 | 60000 | 70000 | 80000 | 90000 | 100000 |
|---|---|---|---|---|---|---|---|---|---|---|
| residual | -1.5632 | 0.0435 | -0.5353 | -0.3528 | 0.0353 | 0.1345 | -0.0168 | 0.0008 | -0.1902 | -0.0107 |

Before the fix it was -0.694 with the same sign on 97.4% of rows. It is now two-signed, averages
-0.099 excluding the startup window, and sits inside +/-0.02 on four of ten rows.

**What is left is not explained, and saying so is the point.** Episodes straddling a summary
boundary is the obvious candidate and it does not survive checking: the residual does not track
episodes per window, since 16 episodes gives 0.0008 while 21 gives -0.5353. FR-008 sets no numeric
tolerance - "the six terms sum to the total" is a derived check, not a threshold the spec states.
The defect that made the breakdown unreadable is fixed. A residual an order of magnitude smaller and
of no fixed sign is recorded here rather than rounded away.

### The noise floor: sd 0.0924 on the run mean, and a gate of 0.19

Three runs at the T045 budget, identical but for `--seed`, are `ppo_car_spread_a`, `_b` and `_c`
above. This is the number every comparison in M3 is tested against, and it exists so that no
configuration is called better than another on a difference the seed alone could have produced.

**The metric is the run mean of `Environment/Cumulative Reward`** over all 200 summaries of a
2,000,000-step run. Stated explicitly because FR-020 requires it, and chosen over late-phase
checkpoint reward because it is tighter and uses every summary rather than a tail.

| | a (seed 1) | b (seed 2) | c (seed 3) | mean | sd | range |
|---|---|---|---|---|---|---|
| run mean | -4.5070 | -4.6613 | -4.6722 | -4.6135 | **0.0924** | 0.1651 |
| last-50 mean | -4.4003 | -4.5490 | -4.6721 | -4.5404 | 0.1361 | 0.2718 |
| last-50 checkpoint | 0.2012 | 0.2393 | 0.3212 | 0.2539 | 0.0613 | 0.1200 |
| within-run sd | 0.4911 | 0.5022 | 0.5360 | 0.5098 | | |
| episodes | 4,990 | 5,093 | 4,866 | | | |
| wall / stalled / swapped | 45.6 / 41.0 / 13.4 | 47.9 / 38.9 / 13.3 | 47.0 / 39.8 / 13.2 | | | |
| laps completed | 0 | 0 | 0 | | | |

**The gate is 0.19**, two standard deviations rounded up, with the observed range of 0.1651 as a
cross-check just inside it. A candidate whose run mean differs from its baseline by less than 0.19
is recorded as having made no measurable difference, not dropped.

**Between-run spread is five times smaller than within-run spread**, 0.0924 against 0.5098. That is
the result that makes the gate usable: a single summary is far too noisy to compare anything, while
a run mean is stable. It also condemns any comparison quoted from a few summaries, which would be
reading scatter five times larger than the effect being tested.

**Two honest limits.** Three runs estimate a standard deviation to roughly 50 per cent, so 0.19 is
a working threshold and a result landing near it deserves a fourth run rather than a verdict. And
research R9 expected a reduced-budget spread to over-estimate the full-budget one, since a policy
still improving is noisier than a converged one. That argument does not apply here, because this
policy is not improving at any budget: v01 was flat over 5M and all three of these are flat over
2M. The risk points the other way instead. A candidate that genuinely starts to learn may be
noisier than these three, so clearing 0.19 is credible while failing to clear it is weaker evidence
of no effect than it appears.

**What the set says beyond the number.** The end-reason mix is the same to within two points across
three independent seeds, no run completed a lap, and late-phase checkpoint reward sits near 0.25
against the 24 markers a lap needs. The stall-not-drive result first seen in `ppo_car_v01` under
seed 42 is now reproduced under seeds 1, 2 and 3, so it belongs to the reward rather than to a seed.

### The stall fell and the wall rose, nearly one for one

SC-003's second acceptance scenario asks whether a falling stall share is real or whether the wall
share simply rose to replace it. On `ppo_car_007_progress` it is close to a straight trade:

| | spread set | candidate | change |
|---|---|---|---|
| stalled | 0.3903 | 0.2741 | **-11.6 points** |
| wall contact | 0.4773 | 0.5907 | **+11.3 points** |
| track swapped | 0.1324 | 0.1346 | +0.2 points |

The stall share clears its 0.019 gate about six times over, and taken alone that reads as the
mechanism working. It is not enough on its own, and this row exists so nobody quotes it that way.

**What makes it more than a trade is the pair of metrics the trade cannot explain.** Markers per
episode rose six fold and eight episodes drove three laps each. A policy that had merely swapped one failure
for another would show neither. The honest summary is that the car now fails while driving instead
of failing while sitting still, and driving is a prerequisite for the lap it is eventually meant to
finish.

### FR-010 does not hold on the candidate, and the cause is not identified

The seven terms sum to `Environment/Cumulative Reward` on **4.8 per cent** of the 500 rows, with a
residual of mean **+0.3030**, sd 0.5110 and largest absolute value 4.6014. Feature 006 saw a similar
failure at -0.694 on 97.4 per cent of rows, found a real defect behind it, fixed it, and left a
smaller unexplained remainder of -0.099. T032 required this check to be re-run rather than inherited,
which is why it was, and it came back worse.

**There is no eighth term.** Every `AddReward` call in `DrivingAgent` was enumerated: four sites, at
the per-step group, the checkpoint award, the wrong-way penalty and the wall penalty, and all four
are mirrored into `RewardModel.Breakdown`. There is no lap bonus. So this is an aggregation
mismatch, not a missing payment.

**What the residual tracks, and what it does not:**

| against | correlation |
|---|---|
| `reward/progress` | **+0.643** |
| markers per episode | **+0.645** |
| episodes per summary | **-0.002** |
| track-swapped share | -0.097 |

By quarter the residual runs -0.0462, +0.1474, +0.4806, +0.6303 while the progress term runs 0.1813,
0.5078, 1.0915, 1.3109. **It scales with how much the car does, not with how many episodes a summary
holds.**

**Two hypotheses were tested and neither survived.** Feature 006 proposed episodes straddling a
summary boundary; the correlation with episodes per summary is -0.002, which is the same answer 006
reached on different data. The obvious successor was that `EndForTrackSwap` reports an episode the
trainer counts differently, which is attractive because our end-reason counts total 13,851 against a
trainer count implied by `summary_freq / Environment/Episode Length` of about 11,219; but the
per-summary correlation with the swapped share is -0.097, so it does not explain the variation.

**Feature 006 named this hypothesis first, and feature 007's step accounting confirms the idea
while reversing its direction.** The M3 entry above proposed that "the two numbers average over
different sets of episodes", with `ReportEpisode` running on only some paths while the trainer
"counts every episode the agent processor sees". That predicts the trainer counting **more**
episodes than the reward reporting. The measurement runs the other way: our end-reason counts total
**13,851** against a trainer count implied at **11,219**, so the reward reporting counts about 23
per cent more episodes than the trainer's mean is taken over, not fewer. The general claim is
confirmed and the direction in that sentence is wrong.

**The confirmation comes from the step ratio rather than from the residual**, which is why it
counts as evidence at all. If the two means are taken over episode sets differing by a factor `f`,
then the physics-to-decision ratio is `4f` rather than 4. Measured, `4 x 11219 / 13851 = 3.2398`
against an observed **3.2161**, within 0.024. Two independent symptoms, one arithmetic.

**The likely shape of the answer, stated as a hypothesis and not as a finding.** The residual was
invisible while every episode scored near -4.5 and appeared once episodes ranged from -5 to well
above +20. Any fixed disagreement about *which* episodes enter the two means produces an error
proportional to the spread of episode rewards, which is exactly a residual that grows with activity
while correlating with nothing about episode counts. Testing that needs per-episode records rather
than per-summary aggregates, which this export does not carry.

**What this does and does not put in doubt.** The behavioural results are counts taken on the Unity
side and do not depend on the reward decomposition: markers per episode, laps completed and the end
reason mix are unaffected. What is in doubt is any statement of the form "the total moved and this
term is why", which is the reason FR-018 already forbids comparing this run's cumulative reward to
feature 006's.

### The held-out column: the car drives now, and it still does not finish a lap

`ppo_car_007_progress-5000081` on the ten held-out evaluation seeds in `Assets/Scenes/Evaluation.unity`,
no trainer attached. The `Couldn't connect to trainer on port 5004. Will perform inference instead.`
line is in the editor log for both sweeps, which is what makes the "no trainer" claim checkable
rather than asserted.

| set | markers of 24 | range | laps | mean duration | p95 dsteer | sign changes/s | end reasons |
|---|---|---|---|---|---|---|---|
| 006 `spread_a`, deterministic | 0.00 | 0 to 0 | 0/10 | 60.00 s | 0.0009 | 0.00 | Stalled x10 |
| 006 `spread_a`, sampling | 0.00 | 0 to 0 | 0/10 | 60.00 s | 0.8067 | 5.21 | Stalled x10 |
| **007 `progress`, deterministic** | **6.20** | 4 to 12 | 0/10 | 7.24 s | 0.2988 | 0.82 | WallContact x10 |
| **007 `progress`, sampling** | **4.60** | 2 to 7 | 0/10 | 5.92 s | 0.8550 | 3.84 | WallContact x10 |

Markers per seed, deterministic: 8, 5, 5, 5, 12, 7, 5, 6, 5, 4. Sampling: 6, 6, 3, 4, 6, 7, 2, 6, 2, 4.

**SC-005 is not met and SC-006 is not met.** SC-005 asks for at least one completed lap on held-out
track and there were none, in either inference mode. SC-006 is the milestone bar of 80 per cent of
seeds completing a lap, restated unchanged from feature 006's SC-002, and it stands at **0 per
cent**. Those are the numbers that decide it and they are recorded before anything else in this
section is read.

**What did change is the failure.** Feature 006's policy sat still on all ten seeds until the 60
second stall timeout and earned nothing at all. This one drives about a quarter of the lap and then
hits a barrier, on all ten seeds, in about seven seconds. Zero markers to 6.20 of 24 is the first
non-zero held-out result the RL side of this project has produced.

**Sampling is worse than deterministic here, which is the expected direction and was not true
before.** 4.60 markers against 6.20. Noise added to a policy that is doing something costs it
markers; noise added to a policy that is doing nothing cannot cost anything, which is why feature
006 measured the two modes as identical at zero.

**Feature 006's factor of 83 between the inference modes should not be carried forward as a
property of the modes.** It was measured with a deterministic p95 of 0.0009, a denominator produced
by a car that never turned its wheel, so the ratio described a stalled policy rather than the
difference between sampling and deterministic inference. Measured on a policy that actually steers,
the factor is **2.86** (0.8550 against 0.2988). The two modes are still reported separately and
never averaged, which was the right call for the wrong reason.

**One asymmetry in the bar, stated because it is not obvious.** `lapsToComplete` is 3 in
`Evaluation.unity`, so a row records `completed_lap` only after three laps, while the scripted
driver's 34 of 34 was measured at one lap. The setting is feature 006's and is left untouched for
comparability with their column, but it means the learned driver is being held to a strictly harder
bar than the scripted one. At 6.20 of 24 markers it does not change the verdict.

### Lifting the wall terminal put the policy back to stalling

`ppo_car_008_budget`, 2026-08-27, is the only run that has ever changed the wall **terminal** rather
than the wall **penalty**. The hypothesis was that a policy cannot learn to recover from a mistake
it is never allowed to survive: with the episode ending at the first contact, every trajectory in
the buffer that touches a barrier ends there and the value function has no data about what follows a
graze.

**The hypothesis is refused, and the direction of the refusal is the interesting part.**

| | 007 baseline | 008 candidate |
|---|---|---|
| markers per episode | **1.4987** | **0.5297** |
| markers by quarter | 0.3477, 0.9794, 2.1148, 2.5528 | 0.3832, 0.4376, 0.5630, 0.7351 |
| `reward/progress` per episode | 0.7729, about 12.95 m | 0.2827, about 4.74 m |
| wall contact share | 0.5907 | 0.2320 |
| stalled share | 0.2741 | **0.5376** |
| step limit share | 0.0000 | 0.0688 |
| laps completed | 8 episodes of three laps | **0** |
| episodes in 5M steps | 13,851 | 8,843 |

**The policy did not learn to recover. It went back to stalling.** Wall endings more than halved and
stall endings doubled, which is the degenerate solution M3 identified at the very beginning: driving
less is a cheaper way to stop paying -5.0 than driving better. The first contact ending the episode
had been suppressing that, and removing it handed the option back.

**The budget was barely used.** Contacts per episode averaged **1.218** against a budget of 3, so
the typical episode never came close to spending it and ended stalled instead. The change did not
fail because the budget was too small; it failed because the policy stopped putting itself in a
position to use it.

**Grinding did not happen, and that risk can now be closed.** Lateral clearance averaged **0.6331**
and was flat across quarters at 0.6367, 0.6454, 0.6218, 0.6284, with a run minimum of 0.3231. A
policy riding a barrier would hold that near zero. This matches what T004's probe measured directly:
a car pressed against a barrier moves 0.47 m in 5 seconds, so grinding is not a competitive strategy
because the vehicle cannot slide along a wall at speed. **The risk the feature was most worried about
was real in principle and absent in practice**, and it is closed with a number rather than an
argument.

**The restored step limit was not cosmetic.** `MaxStep = 6000` fired on 608 episodes, 6.9 per cent of
them, where `episode/end_steplimit` had read exactly zero in every run of M3. Without it those
episodes would have run unbounded, because `_stepsSinceAward` resets on every marker and a slow
policy that collects one marker per 60 seconds never trips the stall rule either.

### The physics-to-decision ratio is not capped at 4

Feature 007 measured the ratio at 3.2161 with a maximum of 4.0063 and read the ceiling of 4 as
confirmed, on the reasoning that `DecisionPeriod: 4` bounds it. **This run reads 4.0870 as its mean
and 5.0224 on a single summary**, so 4 is not a ceiling and that reading was wrong.

The episode-set account still explains most of it but no longer all: our end-reason counts total
8,843 against a trainer count implied at 8,399, which predicts `4 x 8399 / 8843 = 3.7993` against a
measured 4.0870. Feature 007's version of this arithmetic landed within 0.024 and this one is out by
0.29.

What changed between the two runs is that the step limit now truncates episodes, which is a fourth
way for an episode to end and one the reward reporting and the trainer may well treat differently.
**That is a hypothesis and it is written as one.** The honest statement is that the ratio is a
measured quantity whose model is incomplete, that 4 is not its upper bound, and that settling it
needs the per-episode records feature 007 already named as a separate feature.

### The jerk penalty was not the constraint, and the naive comparison would have said it was

`ppo_car_jerk_lo`, 2026-08-20, is T048's first tuning candidate: `JerkPenalty` from -0.005 to
-0.001, nothing else, at the T045 budget on seed 1.

**Changing a reward weight changes the scale of the metric, so the T047 gate cannot be applied to
the raw number.** The 0.19 gate was measured on one reward table. Read raw, this run scores -4.2757
against the baseline's -4.6135, a difference of **+0.3378 that clears the gate comfortably** and
would have been reported as the jerk penalty working. It is not. Of that difference, **+0.2824 is
pure bookkeeping**: the same episodes charged at a fifth the scale. What is left is +0.0553.

**The fix costs nothing, because FR-008 already logs the six terms separately.** Each baseline
summary can be rescored exactly to the candidate's table as
`cumulative_reward - reward_jerk + reward_jerk x (new / old)`, which needs no extra run and no
estimate. Rescored, the three baselines give -4.2271, -4.3784 and -4.3875, a mean of **-4.3310**.

| metric | baseline | candidate | difference | gate | verdict |
|---|---|---|---|---|---|
| cumulative reward, rescored | -4.3310 | -4.2757 | **+0.0553** | 0.19 | does not clear |
| `reward/checkpoint` | 0.2510 | 0.2095 | **-0.0415** | 0.0631 | does not clear |
| cumulative reward, raw | -4.6135 | -4.2757 | +0.3378 | 0.19 | confounded, not read as an effect |

The second row is the honest cross-check: `reward/checkpoint` is +1.0 per marker and this candidate
does not touch it, so it needs no rescoring. Its noise floor is the run-mean spread of the same
three runs, sd 0.0315, hence the 0.0631 gate. It moves the wrong way and stays inside its floor.

**The behaviour did not move at all.** End reasons are 48.0 / 38.6 / 13.3 per cent against the
baseline's 46.8 / 39.9 / 13.3, zero laps as in every run of this feature so far, and checkpoint
reward falls across the run again, 0.2793 to 0.2005. The one thing that did respond is the term
itself: -0.0775 where an unchanged policy would give exactly -0.0706, so a cheaper penalty buys
slightly more wheel movement and no more driving.

**A first attempt was killed at 900,000 steps and was discarded rather than resumed.** Its evidence
is kept at `results/ppo_car_jerk_lo.killed_at_900k/` and
`results/rl/ppo_car_jerk_lo.killed_at_900k.log` rather than overwritten with `--force`. The cause
was the tooling that launched the trainer, the third time in this feature after `ppo_car_v01`
segment one and the first spread attempt, both at 1,800 s; this one died at 1,380 s, so it is not a
fixed cap. Discarded for T046's reason: the baselines it is compared against ran uninterrupted, and
a resume would make this run differ from them by something other than the jerk weight. Relaunching
the trainer detached from that tooling ran to 2M without incident, and the rerun reproduced the
killed attempt's step-10,000 summary exactly at -5.010, so seed 1 is deterministic and nothing was
lost but an hour.

### Cheapening the wall changed which failure the policy picks, and made the return worse

`ppo_car_wall_lo`, 2026-08-20, is T048's second candidate: `WallPenalty` from -5.0 to -1.0, the
jerk scale returned to its pinned -0.005, nothing else, seed 1 at the T045 budget.

**The prediction was specific and it held.** The spread runs showed stalling out costs about -3.0
in step cost over 60 s while a wall cost -5.0 at once, so not trying was cheaper than trying. At
-1.0 that ordering inverts. The end-reason mix moved exactly as that predicts: **wall 46.8 to 51.4
per cent and stalled 39.9 to 35.4**, and the gap against the baselines holds at 3.4, 4.0, 7.1 and
4.1 points across the four quarters rather than fading as training proceeds.

**And the return got measurably worse.** Rescored to the same table the baselines average -2.8294;
this run means -3.1479, a difference of **-0.3185 that clears the 0.19 gate**. FR-021 asks for the
direction to be stated rather than the result buried: this is a change that made a difference, and
the difference is negative. Trading a stall for a crash pays the wall term more often and ends the
episode sooner without buying progress.

| metric | baseline | candidate | difference | gate | verdict |
|---|---|---|---|---|---|
| cumulative reward, rescored | -2.8294 | -3.1479 | **-0.3185** | 0.19 | clears, worse |
| `reward/checkpoint` | 0.2510 | 0.2828 | +0.0318 | 0.0631 | does not clear |

**The rescored spread is tighter than the pinned one, and that is not a free win.** The three
baselines rescored to the wall -1.0 table give sd 0.0540 against 0.0924 on their own table, because
the wall term carried most of the between-seed variance. The gate is still quoted at T047's 0.19
rather than the tighter 0.11, which is the conservative choice: rescoring shrinks the baselines'
spread without saying anything about how noisy a genuinely different policy is, and this run's
within-run sd of 0.5592 is the largest of the five 2M runs so far.

**One signal points somewhere new.** `reward/checkpoint` by quarter runs 0.286, 0.237, 0.269,
**0.339**, where the three baselines sit flat at 0.254, 0.251, 0.245, 0.254 and where
`ppo_car_v01`, `ppo_car_smoke` and all three spread runs *fell* over their length. It does not
clear its gate on the run mean and is not reported as a result. It is recorded because it is the
first upward late-phase checkpoint trend in M3, and because a fourth run is the stated remedy for
exactly this kind of near-gate reading.

**What both candidates together say.** The jerk penalty is not the constraint and the wall terminal
is not either: one changed nothing, the other changed which way the policy fails. Neither completed
a lap, and neither is kept. The two terms neither candidate touched are the ones the spread
decomposition made suspicious: **step cost at -1.676 a run against a speed reward of +0.0069**,
which is a car that is charged 240 times more for existing than it is paid for moving. That is a
hypothesis for the next design change rather than a result from these runs, and it belongs in
`DESIGN.md` before it belongs in a trainer.

### Paying twice as much for speed bought twelve per cent more speed

`ppo_car_speed_hi`, 2026-08-24, is T048's third candidate, added on the user's decision after the
first two came back negative and T050 had no winner to promote. One change: `SpeedReward` from
0.001 to 0.002, seed 1 at the T045 budget.

**The candidate was capped by the table's own invariant, and that cap is the first result.**
`Idle` was written so that at full speed the step cost and the speed reward cancel *exactly*, which
is the design's defence against a policy circling on open surface to farm the speed term. That
identity is also precisely what prevents the speed term from offering a gradient anywhere below
full speed: before this run, the break-even speed was `v_norm = 1.0`, so a car had to be at maximum
speed merely to stop losing money. Raising the weight trades the identity for a margin, and the
margin bounds the change:

```
(SpeedReward - |StepCost|) x 6000  <  24 markers / 3
(SpeedReward - 0.001)      x 6000  <  8          =>  SpeedReward < 0.002333
```

**So the imbalance is 240x and the largest correction the table permits is 2x.** 0.002 was chosen a
little under the ceiling because it puts break-even at exactly `v_norm = 0.5` and leaves the float
arithmetic away from the boundary. This bound was written into `DESIGN.md` 4.5 before the run, and
the run was pre-registered in both directions.

**It did not clear, and the interesting part is why.**

| metric | baseline | candidate | difference | gate | verdict |
|---|---|---|---|---|---|
| cumulative reward, rescored | -4.6066 | -4.6439 | **-0.0373** | 0.19 | does not clear |
| `reward/checkpoint` | 0.2510 | 0.2409 | -0.0101 | 0.0631 | does not clear |
| cumulative reward, raw | -4.6135 | -4.6439 | -0.0304 | 0.19 | confounded, not read as an effect |

The rescoring is the same exact correction T049 used on the first two candidates, and here it is
small: only +0.0069 of the raw difference is bookkeeping, because the speed term is tiny to begin
with. That is itself the point.

**The term responded to the weight; the policy did not respond to the term.** `reward/speed` went
from +0.0069 to +0.0150. A policy that changed *not at all* would have given exactly +0.0138, since
the weight doubled. The entire behavioural response is the remaining +0.0012: implied mean `v_norm`
moved from 0.00410 to 0.00459, **twelve per cent more speed for twice the payment**. Nothing else
moved either. End reasons went 46.8 / 39.9 / 13.3 to 49.2 / 37.7 / 13.1 over 5,153 episodes, no run
completed a lap, and `reward/checkpoint` fell across the run by quarter, 0.276, 0.244, 0.212, 0.232,
against baselines flat near 0.25.

**What the three candidates together establish.** The jerk penalty changed nothing, the wall
terminal changed which failure the policy picks and made the return worse, and the speed scale
changed the accounting more than the driving. None of the three cleared the gate in the better
direction and none completed a lap in 2M steps. **The conclusion is the one the third run was
pre-registered to license: this reward table cannot be fixed by scaling its weights.** A policy that
is paid double for moving and moves twelve per cent more is not being held back by the size of the
payment; it has not found the behaviour the payment is for. That is an exploration problem, and the
remedies are of a different kind from a weight - a curriculum that starts the car nearer a marker,
a denser progress signal than one marker in twenty-four, or a warm start from the behavioural
cloning policy that M4 produces anyway.

**T050 has no winner at any budget, and is recorded as unsatisfiable at this reward table** rather
than left open. Phase 5's outcome is negative and specific: three one-change candidates, a measured
noise floor, and a named reason none of them worked.

---

### The agent could not see its own track, and every number above was measured that way

Feature 009 built a demonstration scene and drove one training seed through it. The car went
straight into a barrier at full throttle. The trace said why: `steering` was exactly `0.00000` on
every row and `target_speed` was pinned at `10.0`, the vehicle maximum.

Read live in play mode, `CarAgent.RayDistancesNorm` was **1.0 in all thirteen directions** while
`Physics.OverlapSphere` at the same instant returned both barrier `MeshCollider`s within 25 m. The
car was on the surface, at its marker, between two walls, reporting an empty road.

**Cause.** `CarAgent.IsSelf` ended with `collider.transform.root == transform.root`.
`TrainingArea.prefab` makes `Car` and `Track` siblings under one area root, so the car's own
barriers, surface and checkpoints shared its root and every hit on them was discarded as the car
sensing itself. The `attachedRigidbody` test above it already caught every collider actually on the
car; the root test only added the rest of the area. Fixed to
`collider.transform.IsChildOf(transform)`.

**Why it hid for four features.** An all-clear fan is a symmetric fan. `RayControllers` returns
exactly zero steering for it and the sight limit returns `vMaxMs`, so a blind car drives straight
and fast into a wall, which reads as a policy that has not learned to steer. Collisions were
unaffected, so wall contacts were recorded normally and the end-reason mix looked plausible
throughout. Nothing in the instrumentation was wrong; the observation feeding it was.

**Scope.** `Evaluation.unity` has the same layout as the prefab and produced the held-out figures
for features 006, 007 and 008. `Training.unity` shares it too. Every RL run in this log was trained
and evaluated through this filter. Whether the M3 result is a finding about the reward table or an
artefact of a sensor that never saw a wall is **not settled by this entry** and is not feature
009's to settle.

**What the fix demonstrably changed, on the scripted driver.** Same scene, same seed, before and
after: thirteen rays clear at 20 m becomes twelve of thirteen hitting between 2.77 m and 12.96 m,
and the steering command goes from a constant zero to a varying one. Across the 34 training seeds
the driver then completed **34 of 34** three-lap runs with **zero wall contacts**, at the agent's
12.5 Hz decision period. Full figures in `results/rl/demo_cadence.md`.

### Pre-registered: does M3's negative result survive the sensing fix?

**Written before launch.** Run id `ppo_car_009_sighted_probe`, seed 42,
`config/ppo_car_sighted_probe.yaml`, which differs from `config/ppo_car.yaml` in `max_steps` alone,
1,000,000 rather than 5,000,000. No `behavioral_cloning` block. The reward table is untouched,
`wallContactBudget` is 0 and `MaxStep` is 6000, so this is feature 008's configuration at a fifth of
the budget with one thing changed that is not in the config at all: the agent can now see its own
barriers.

**Why a short run is the right instrument.** Feature 009's remaining work is a 5M-step warm start
whose purpose is to rescue a policy that could not learn to drive. If the policy could not learn
because it was blind, that work answers a question that no longer exists. One million steps is
enough to see whether the failure mode has changed, and cheap enough that being wrong about it
costs an hour rather than a day.

**Read against feature 008 at the same step count**, not against its final numbers. The comparison
is markers per episode and the end-reason mix at 1M, and the baseline for both is
`results/ppo_car_008_budget`.

**The two outcomes, and what each licenses.**

- **The failure mode is unchanged.** M3's result stands on its own, the reward-side conclusion
  survives with its most obvious confound eliminated, and feature 009 proceeds to T024 with a
  stronger closeout than it could otherwise have written.
- **The policy starts making progress.** M3's three failures were measured through a sensor fault
  and the milestone's verdict is not safe to write from features 006 to 008. The imitation warm
  start is then not obviously needed, and the 2026-08-28 decision that capped M3 at feature 009
  was taken on a premise that no longer holds. That is an owner decision, not a feature decision.

Neither outcome is a milestone figure. This run is a diagnostic and is recorded as one.

### The fix was real and the milestone still fails: a sighted agent does not drive either

`ppo_car_009_sighted_probe`, 1,000,000 steps in 1294 s, 773 steps/s, seed 42, no
`behavioral_cloning`. Read against `ppo_car_008_budget` at the same step count.

| at 1M steps | 008, blind | 009 probe, sighted |
|---|---|---|
| markers per episode, last 10 summaries | 0.3955 | **0.2247** |
| markers per episode, whole run | 0.3745 | **0.2649** |
| cumulative reward | -9.3390 | **-4.4739** |
| episode length | 583.0 | 498.8 |
| ended on wall contact | 5.03 | **12.76** |
| ended stalled | 9.63 | 9.61 |
| wall contacts per episode | 1.3445 | **0.4718** |
| laps completed | none | **none** |

**The pre-registered first outcome holds. M3's negative result survives the sensing fix.** Markers
per episode did not rise, it fell, and no run completed a lap. The policy that could not learn to
drive blind does not learn to drive sighted, at least not in a fifth of feature 008's budget.

**The failure changed shape, and the reward improvement is arithmetic rather than driving.** The
sighted policy ends far more episodes on wall contact, 12.76 against 5.03, while accumulating
**fewer** contacts per episode, 0.4718 against 1.3445, over shorter episodes. It reaches a wall
sooner and terminates there instead of grazing repeatedly. Cumulative reward rises from -9.34 to
-4.47 largely because a shorter episode pays the per-step cost fewer times. This is exactly the
trade feature 008 was caught by and named, applied here to this run's own reading: a failure that
moves is not a failure that is fixed.

**What this does not establish.** One seed, one fifth of the budget, against a run-mean noise floor
of sd 0.0924 measured in feature 007. The 0.11 fall in markers per episode sits close enough to
that band to be called suggestive rather than measured. The negative is the solid part: nothing in
this curve resembles a policy approaching a lap.

**Consequence for feature 009.** The warm start proceeds. Its closeout is now stronger than it could
otherwise have been, because the most obvious confound in M3's three failures has been eliminated by
measurement rather than left open at the defence. The sensing fault remains a real defect that was
present for features 006 to 008; it was not the cause of the milestone failure.

### The demonstration: 34 training seeds, 34,000 decisions, sampled at the agent's clock

`unity/SelfDrivingSim/Assets/Demonstrations/heuristictrain34.demo`, recorded 2026-08-29 from
`HeuristicDriver` through `DrivingAgent.Heuristic` with `BehaviorType` Heuristic Only and no model
assigned.

| | |
|---|---|
| Observation | `(19,)`, `VectorSensor_size19` |
| Action | 2 continuous |
| Info/action pairs | 34,000 |
| Episodes | 65 |
| Summed reward | 4118.14 |
| File size | 4.42 MB |
| Seeds | the 34 training seeds, `results/rl/demo_seeds.json` |
| Runs completed | 34 of 34, zero wall contacts |

**Sampled at 12.5 Hz, not 50 Hz, and that is correct rather than a compromise.** The demonstration
write sits inside `SendInfoToBrain`, which only runs on a decision step, so at `DecisionPeriod: 4`
the recorder physically cannot sample faster (research R2). The policy that will be trained from
this file also acts at 12.5 Hz, so the demonstration and the policy share a clock. The scripted
driver decides at 50 Hz and `results/rl/demo_cadence.md` measures what it loses by being sampled
at a quarter of that: nothing, in laps.

**The file pairs each observation with the previous decision's command.** This is a property of
ML-Agents, not of this project's code, and it is not configurable without patching
`Library/PackageCache` (research R5). At `DecisionPeriod: 4` that is an 80 ms shift. It is written
down here so nobody later reads the file as `(obs_t, a_t)`.

**65 episodes against 34 runs** because each run ends one episode and each track swap ends
another.

**Declared overrun.** `NumStepsToRecord` was 34,000 and the 34 runs account for about 33,509
decision steps, so roughly **491 steps, 1.5 per cent of the file**, are the expert continuing to
drive the final seed after the sweep finished. Seed 40 is therefore slightly over-represented. The
alternative was a cap below the sweep's length, which would have truncated a real run instead.

**The first recording attempt was discarded.** `NumStepsToRecord` was 0, meaning record
indefinitely, and `SweepRunner` finishing does not stop `DrivingAgent` from starting new episodes.
The recorder ran for about four hours past the sweep and produced a 26.9 MB file dominated by one
seed. It was deleted rather than trimmed, because a `.demo` is a protobuf stream and a partial
delete would have been unauditable.

### Pre-registered: the imitation warm start

**Written before launch, 2026-08-30.** Run id `ppo_car_009_bc`, seed 42, `config/ppo_car.yaml`,
5,000,000 steps, `--torch-device=cuda`.

**The one change is a `behavioral_cloning` block.** `git diff --stat config/ppo_car.yaml` reports 47
insertions and 0 deletions, so no hyperparameter above it moved: `batch_size` 2048, `buffer_size`
20480, `learning_rate` 3.0e-4 linear, `beta` 5.0e-3, `epsilon` 0.2, `lambd` 0.95, `num_epoch` 3,
`hidden_units` 256, `num_layers` 2, `max_steps` 5,000,000, `time_horizon` 128, and `extrinsic` at
gamma 0.99 strength 1.0. Read back through `RunOptions.from_dict` rather than by eye.

**The three chosen values, and why each is what it is.** All three were fixed before the run and
none may be revisited after it (FR-008, ordering rule 4).

| value | chosen | why |
|---|---|---|
| `steps` | **500,000** | The anneal schedule is `LINEAR` only above zero (research R8). The default 0 would apply the imitation loss at full strength for all 5M steps, which measures how well PPO copies the scripted driver. At 500,000 the loss decays over the first tenth of the budget and the rest is ordinary RL. |
| `strength` | **0.5** | Half weight. The demonstration drives 34 of 34 training laps but the scripted driver is not the policy M3 is looking for, so the term guides the early policy rather than defining it. |
| `samples_per_update` | **2048** | The default 0 iterates the whole demonstration buffer per update: 16 minibatches per epoch, three epochs, every PPO update. At 2048 it is one. SC-009 compares throughput against 903 and 927 steps/s and a sixteenfold imitation cost would swamp that. |

`num_epoch` and `batch_size` are left unset and inherit 3 and 2048 from the trainer, so the BC
update rides the PPO update's shape rather than adding two more chosen numbers.

**The demonstration** is `heuristictrain34.demo`, the 34 training seeds only, 34,000 info/action
pairs at 12.5 Hz, committed through LFS and described in the section above. The held-out seeds are
absent by construction and `python/tests/test_demo_seeds.py` asserts it.

**The environment is feature 007's terminal with feature 008's step limit**, confirmed by reading
rather than assuming: `MaxStep: 6000` at `TrainingArea.prefab:408`, and `wallContactBudget` **0**
from the initialiser at `DrivingAgent.cs:101`. The field is not serialized into the prefab at all,
so the budget is a source value rather than a scene value; that is how feature 008 varied it and it
is recorded here because reading only the prefab would not show it.

**What will be read, fixed now.**

- **Markers per episode against 1.4987**, feature 007's figure, and against the **0.035** gate. The
  gate's caveat travels with it in the same breath: `results/rl/progress_spread.md` holds that
  clearing it is credible, that failing to clear it is weaker evidence than it looks, and that a
  result landing near it earns a fresh three-run spread rather than a verdict.
- **The end-reason mix whole.** A fall in the wall share appearing as a rise in the stall share is a
  traded failure, not a fixed one. Feature 008 fell into exactly that and named it.
- **Cumulative reward against 007 and 008**, with the diff backing the comparability claim (SC-011).
- **Throughput against 903 and 927 steps per second** (SC-009).
- **`Losses/Pretraining Loss` over the whole run**, not only at the start. It should fall and then
  stop updating once the anneal reaches its floor. Its **absence in the first summaries means the
  demonstration never loaded**, in which case the run is measuring feature 007 again and is killed
  rather than read.

**One comparability limit, stated before the numbers rather than after them.** The reward table is
untouched and the diff over `Assets/Scripts/` since `be2f9c4` contains no reward-bearing line, so
cumulative reward is measured in the same units as 007 and 008. The **agent is not the same agent**:
`CarAgent.IsSelf` was fixed in `3017764` and this policy can see its own barriers, which 007 and 008
could not. `ppo_car_009_sighted_probe` is the like-for-like sighted baseline at 1M steps and is the
honest comparison for the early curve; 1.4987 remains the milestone figure and is read as one.

### The warm start works: `ppo_car_009_bc`

`ppo_car_009_bc`, 5,000,000 steps in 7336.6 s, seed 42, `config/ppo_car.yaml` with the
`behavioral_cloning` block pre-registered above. Read against the values fixed before it ran.

| whole run | 007 `progress` | 008 `budget` | 009 probe, no BC | **009 `bc`** |
|---|---|---|---|---|
| markers per episode | 1.4987 | 0.5297 | 0.2649 | **2.6321** |
| markers per episode, last 10 summaries | 2.7754 | 0.7805 | 0.2247 | **3.5421** |
| cumulative reward, last 10 | -1.2612 | -6.6515 | -4.4104 | **+0.0887** |
| episodes ending in three completed laps | 8 | 0 | 0 | **77** |
| laps in the last 10 summaries | 0 | 0 | 0 | **6** |
| steps per second | 903 | 927 | 782 | **687** |

**The 0.035 gate is cleared by a factor of about thirty.** Markers per episode is **2.6321** against
**1.4987**, a rise of **1.1334**. The gate's caveat is named here rather than in a footnote:
`results/rl/progress_spread.md` holds that clearing it is credible, that failing to clear it is
weaker evidence than it looks, and that a result landing *near* it earns a fresh three-run spread
rather than a verdict. This result does not land near it, so no spread is owed.

**The end-reason mix, read whole, is not a traded failure.** Against feature 007: the wall share
fell from 59.07 to **57.10 per cent** and the stall share *also* fell, from 27.41 to **24.90 per
cent**. Feature 008's pattern, where the wall share fell only because the stall share rose, does not
appear here. Track swaps are flat at 13.46 against 13.11 per cent. What rose is the step-limit share
and the lap share.

**One comparability limit on that mix.** Feature 007 ran with no `MaxStep` at all, so it has no
step-limit category; 009 has 008's 6000. The 4.37 per cent of 009's episodes that end on the step
limit have no counterpart in 007's denominator, so the shares are close but not strictly like for
like. The direction of the markers finding survives it, because truncating long episodes can only
lower markers per episode, not raise it.

**The learning curve is monotone, which none of the previous three were.**

| steps | laps completed | mean markers per episode |
|---|---|---|
| 0 - 500k | 0 | 0.3137 |
| 500k - 1M | 0 | 0.7489 |
| 1M - 1.5M | 0 | 1.7594 |
| 1.5M - 2M | 1 | 2.5320 |
| 2M - 2.5M | 9 | 3.4274 |
| 2.5M - 3M | 5 | 2.9580 |
| 3M - 3.5M | 10 | 3.2878 |
| 3.5M - 4M | 14 | 3.6568 |
| 4M - 4.5M | 17 | 3.8238 |
| 4.5M - 5M | **21** | 3.7205 |

Laps are still arriving at the end of the budget and markers are still near their maximum, so the
run is not obviously converged. That is an observation, not a case for a longer budget.

**The sensing fix is not what did this, and the probe is why that can be said rather than assumed.**
At a matched 1,000,000 steps, with identical sensing and identical config apart from the BC block:

| at 1M steps | 009 probe, no BC | 009 `bc` |
|---|---|---|
| markers per episode, whole | 0.2649 | **0.5470** |
| markers per episode, last 10 | 0.2247 | **1.0571** |
| cumulative reward, last 10 | -4.4104 | **-3.7469** |

The sighted probe was *worse* than blind feature 008 at the same point. The warm start is the
difference.

**Cumulative reward is positive for the first time in this project**, +0.0887 over the last ten
summaries against -1.2612 for 007 and -6.6515 for 008. The comparison is backed rather than
asserted: `git diff be2f9c4..HEAD -- unity/SelfDrivingSim/Assets/Scripts/` contains **no
reward-bearing line**, so the reward table that produced these three numbers is the same table
(SC-011).

**Throughput is 687 steps per second against 903 and 927** (SC-009), and the loss splits in two.
The sighted probe, which has no BC module at all, ran at **782**, so roughly half the fall predates
this feature and belongs to the sensing fix restoring ray hits that were previously discarded. The
BC module accounts for the rest, 782 to 687. Both runs were on the same machine but in different
sessions, so this attribution is a reading of two measurements rather than a controlled one.

**`Losses/Pretraining Loss` behaves as R8 describes, in the part that matters** (T041). It is
present from the first PPO update at step 30,000, non-zero through step **520,000**, and exactly
**0.0 from step 540,000 to the end** without exception, which is the module declining to update once
the linear anneal drives its learning rate below 1e-10. `steps: 500000` did what it was set to do.

**What it does not do is fall much.** 1.2502 at 30,000 against 1.1186 at 520,000, about eleven per
cent, wandering rather than descending. The task expected a fall and then a cut-off; it got a
shallow drift and then a cut-off. A reading, offered as one: the policy is being pulled by PPO and
by the expert at the same time, and at `strength: 0.5` over 500,000 steps it never sits still long
enough to fit the demonstration closely. Whether a deeper fit would help is not answerable from this
run and is not asked of it.

**What this does not establish.** 77 lap endings out of 14,607 episodes is **0.53 per cent**, on
training tracks the demonstration was recorded from. The milestone bar is 80 per cent on the ten
held-out seeds and this entry says nothing about it. One seed, one run, no spread. The held-out
evaluation in Phase 6 is the number that decides M3, and it has not been measured yet.

### The held-out column: M3's bar is met, in both inference modes

`ppo_car_009_bc-5000101.onnx`, the final checkpoint of the run above, on the ten held-out seeds in
`Assets/Scenes/Evaluation.unity`. `lapsToComplete` is **3**, so every completed row below is three
laps, and `checkpoints_awarded` of 72 is 24 markers taken three times. The two inference modes are
reported separately and are never averaged.

| held-out, 10 seeds | 006 `spread_a` | 007 `progress` | **009 `bc`** |
|---|---|---|---|
| laps, deterministic | 0/10 | 0/10 | **10/10** |
| laps, sampling | 0/10 | 0/10 | **9/10** |
| markers, deterministic | 0.00 | 6.20 of 24 | **24.0 of 24** |
| markers, sampling | 0.00 | 4.60 of 24 | **22.3 of 24** |
| wall contacts, deterministic | 0 | 10 | **0** |
| wall contacts, sampling | 0 | 10 | **1** |
| end reason, deterministic | Stalled x10 | WallContact x10 | **LapsCompleted x10** |
| end reason, sampling | Stalled x10 | WallContact x10 | **LapsCompleted x9, WallContact x1** |

**SC-007 is met and SC-008 is met.** SC-007 asked for at least one completed lap on held-out track
in either mode; there are nineteen across the two. SC-008 is the milestone bar of 80 per cent of
seeds completing a lap, restated unchanged from feature 006's SC-002 and failed three times before
this. It stands at **100 per cent deterministic** and **90 per cent sampling**. Both clear it.

The markers rows are capped at 24 so they can be read against feature 007's column, which was
measured on policies that never finished a lap. Uncapped, the deterministic mean is 72.0 of 72 and
the sampling mean is 65.5.

**Per seed.** Deterministic: 72, 72, 72, 72, 72, 72, 72, 72, 72, 72. Sampling: 72, 72, 72, 72, 72,
72, 72, 72, **7**, 72. The single sampling failure is seed **1009**, a wall contact at 7 markers
after 7.16 s, which is the same first-quarter crash that was feature 007's only outcome.

**Sampling is worse than deterministic, and the gap is now small.** Nine of ten against ten of ten,
22.3 markers against 24.0. Feature 007 measured the same direction at 4.60 against 6.20. What has
changed is the size: a policy that is doing the task well loses one seed to injected noise where a
policy doing it badly lost a quarter of its markers.

**Where the noise goes is the steering, and the lap survives it.** |dsteer| P95 is **0.2870**
deterministic against **0.8277** sampling, and sign changes are **0.3941/s** against **4.2592/s**,
a factor of 10.8. The sampled policy saws at the wheel roughly eleven times as often and still
completes three laps on nine of ten tracks. The deterministic figure of 0.3941/s is the number to
carry into M5's steering comparison, not the sampled one.

**The policy is faster than the expert it was warm started from.** Three laps in **62.425 s** mean
deterministic, 20.808 s per lap, against the scripted driver's **26.266 s** per lap in
`results/rl/demo_cadence.md`. That is about 9.6 m/s against 7.6 m/s, near enough 26 per cent
quicker. Behavioural cloning seeded the policy and PPO then optimised past the demonstrator, which
is the outcome the auxiliary-loss form of BC is supposed to allow and the pure-imitation form is
not. The comparison is across seed sets, expert on the 34 training seeds and policy on the ten
held-out ones, and it survives that only because the generator produces near constant length
tracks: the ten held-out tracks measure **198.5 m to 201.6 m**, a spread of 1.6 per cent.

**That constant length is also why the lap times look suspiciously alike** and are not a defect.
Ten different tracks, ten times within 0.9 s of each other, is what a constant speed policy does on
loops of near identical circumference. It was checked before the result was believed.

**Two comparability limits, both stated because neither changes the verdict.** Feature 007's
held-out column was measured before the ray self-filter fix of `3017764`, so its 6.20 was produced
by an agent that could not see its own track; the honest reading of the 007 column is a lower bound
on what that configuration could have done. And this evaluation runs with `MaxStep = 6000`, which
007's did not have; at 62 s of three-lap driving against a 480 s limit it was never close to firing.

**What this does not establish.** One training seed, one run, one checkpoint, ten evaluation tracks
from one generator. It says M3's bar is met by this policy on this track distribution. It does not
say the reward table was ever the problem, and the M3 closeout is where that is argued.

### Pre-registered: is the held-out pass a property of the policy or of seed 42?

Written **before** either run is launched, on 2026-08-31, so the reading cannot be chosen after the
numbers are in.

M3's bar is met above on **one training seed**. `results/rl/progress_spread.md` measured the
run-to-run noise of this setup and its whole point is that a single run is a weak claim. The bar is
a milestone and the thesis will be defended on it, so it gets a spread.

**Two more runs: `ppo_car_009_bc_s7` and `ppo_car_009_bc_s13`.** 5,000,000 steps each,
`config/ppo_car.yaml` byte for byte as it stands at commit `5784a8d`, `behavioral_cloning` block
included, the same `heuristictrain34.demo`. **`--seed` is the only thing that differs**, at 7 and
13 against 42. Same machine, same scene, same reward table.

**What counts as agreement.** Each run's final checkpoint is evaluated on the ten held-out seeds in
**deterministic** inference, and the criterion is the milestone's own: **at least 80 per cent of
seeds completing three laps**. Three of three runs clearing it says M3's pass is a property of the
method. Sampling inference is run and reported for each, but the milestone is read off
deterministic, as it was above.

**What counts as disagreement, and it is written now rather than argued later.** If any run lands
below 80 per cent, the honest report is a **range across seeds**, not a mean and not the best of
three, and the M3 closeout says the method clears the bar on some seeds and not others. One run out
of three failing does not retract the pass and does not confirm it; it changes the claim from "the
method works" to "the method works often", and that sentence goes into `DESIGN.md` in those words.

**Also recorded per run, for comparison with the seed 42 column**: markers per episode over the
whole run and over the last ten summaries, cumulative reward over the last ten, the count of
three-lap episodes, and the end-reason mix. These are the training-side numbers, and they are
secondary. The held-out percentage is what this spread exists to test.

**What this spread does not do.** Three seeds is not a distribution, the evaluation tracks are the
same ten in every run, and no run uses a different generator. It answers whether seed 42 was lucky.
It does not answer whether the ten held-out tracks are representative, which is a separate question
and belongs to M5.

### The spread's answer: seed 42 was not lucky, and it was the weakest of the three

The runs pre-registered above, read against the criterion fixed before they were launched.
`ppo_car_009_bc_s7` and `ppo_car_009_bc_s13`, 5,000,000 steps each, `config/ppo_car.yaml` as at
commit `5784a8d`, `--seed` the only difference.

**Held-out, ten seeds, `lapsToComplete: 3`. The milestone is read off deterministic.**

| | seed 42 | seed 7 | seed 13 |
|---|---|---|---|
| laps, deterministic | **10/10** | **10/10** | **10/10** |
| laps, sampling | 9/10 | **10/10** | **10/10** |
| markers, deterministic, capped at 24 | 24.00 | 24.00 | 24.00 |
| markers, sampling, capped at 24 | 22.30 | 24.00 | 24.00 |
| wall contacts, deterministic | 0 | 0 | 0 |
| wall contacts, sampling | 1 | 0 | 0 |
| three-lap time, deterministic | 62.425 s | 62.683 s | 62.551 s |
| \|dsteer\| P95, deterministic | 0.2870 | 0.1709 | 0.3306 |

**The agreement condition is met, three of three.** The pre-registration said three of three runs
clearing 80 per cent deterministic says M3's pass is a property of the method rather than of seed
42. All three clear it at **100 per cent**, with **zero wall contacts in thirty deterministic
runs**. The disagreement wording written in advance does not apply and is not used.

**Sampling, reported separately as US4 requires and never averaged with the above**: 9/10, 10/10,
10/10. Seed 42's single failure on seed 1009 is the only lap lost anywhere in the spread, sixty
evaluation runs in total. Both later seeds complete that track under noise.

**Seed 42 was the weakest of the three, which is the opposite of the worry that motivated this.**
It is the only one to drop a sampling seed and it has the lowest cumulative reward of the three.
The spread was run because a single-seed milestone claim is thin; it turns out the single seed
understated the method.

**The training-side numbers do not rank the seeds the way the held-out numbers do, and that is the
most useful thing this spread produced.**

| whole run | seed 42 | seed 7 | seed 13 |
|---|---|---|---|
| markers per episode | 2.6321 | 2.4851 | **2.3210** |
| markers per episode, last 10 | 3.5421 | 3.8649 | **4.5105** |
| cumulative reward, last 10 | 0.0887 | 1.0062 | **1.1906** |
| episodes ending in three laps | **77** | 47 | 34 |
| wall share | 57.10 % | 58.63 % | 56.97 % |
| stall share | 24.90 % | 23.73 % | 25.16 % |

**Training lap count runs backwards against held-out result here.** Seed 42 finished 77 three-lap
episodes in training and is the weakest on held-out track; seed 13 finished 34 and is among the
strongest. Markers per episode over the whole run tells the same inverted story, while markers over
the **last ten summaries** and cumulative reward over the last ten both rank the seeds in the order
the held-out column does. The reading offered, and it is a reading: a whole-run aggregate averages
in the early policy, so a run that spends longer learning and ends better scores worse on it than a
run that plateaus early. **Three seeds is not enough to call this a law**, and it is recorded as an
observation with its n stated.

**Why it matters beyond this feature.** Features 006, 007 and 008 were argued largely on whole-run
training aggregates, because no policy of theirs ever finished a lap to be measured any other way.
This spread shows those aggregates ranking three policies in the wrong order on the one criterion
the milestone cares about. It does not overturn their conclusions, which were about failures so
large no ranking was needed. It does mean the M3 closeout should say which of its numbers are
whole-run aggregates and which are end-of-run, and should not lean on the former.

**One process note, recorded because it cost a run.** Seed 7's first attempt died at 1,270,000 of
5,000,000 when the Unity editor terminated and took the detached trainer's socket with it
(`BrokenPipeError`, then `EOFError`). `run_logs/training_status.json` had not been written, so
`--resume` would have restored the weights but restarted the step counter and the behavioural
cloning anneal, which is a different schedule from the one seed 42 got. It was restarted clean
instead rather than silently breaking the "`--seed` is the only difference" condition this spread
depends on. The partial log is kept as `ppo_car_009_bc_s7.killed_at_1270k.log`, and its orphaned
checkpoints are quarantined in that run's `stale_killed_at_1270k/` so nothing can select them by
step number later. This is the second run the project has lost to the editor, after feature 007's
at 1,440,000. A headless player build driven by `mlagents-learn --env=` would remove the editor
from the loop and is the standing fix, not yet done.

**What the spread still does not establish.** The same ten evaluation tracks in every run, one
generator, one track distribution, three seeds. It answers whether seed 42 was lucky. It does not
answer whether these ten tracks are representative, which belongs to M5.

## M3 closing summary

Written 2026-09-01, when the milestone closed. The full entries for each run are above; this is the
one table the milestone is read from.

| feature | run | one change | markers/ep | held-out laps, deterministic |
|---|---|---|---|---|
| 006 | `ppo_car_spread_a` | baseline reward table | 0.0000 | 0/10 |
| 006 | `ppo_car_wall_lo` | wall penalty -5.0 to -1.0 | worse by 0.3185 | not evaluated |
| 007 | `ppo_car_007_progress` | dense progress term added | 1.4987 | 0/10 |
| 008 | `ppo_car_008_budget` | wall terminal lifted, budget 3 | 0.5297 | not evaluated |
| 009 | `ppo_car_009_sighted_probe` | sensing fix, no warm start, 1M only | 0.2649 | not evaluated |
| **009** | **`ppo_car_009_bc`** | **`behavioral_cloning` block** | **2.6321** | **10/10** |
| **009** | **`ppo_car_009_bc_s7`** | **seed 7** | **2.4851** | **10/10** |
| **009** | **`ppo_car_009_bc_s13`** | **seed 13** | **2.3210** | **10/10** |

**M3 is MET.** SC-001 at **30/30 = 100.0 per cent** deterministic (bar 95) and 29/30 = 96.7 per cent
sampling. SC-002 at **30/30 = 100.0 per cent** deterministic (bar 80) and 29/30 = 96.7 per cent
sampling. Thirty runs is ten held-out seeds times three training seeds. `lapsToComplete` is 3, so
SC-002 was measured three times stricter than it asks.

**The reward table was never the binding constraint.** Feature 006 exonerated the wall penalty's
weight, feature 008 exonerated its terminal, feature 007 showed a dense signal works without moving
the milestone, and feature 009 moved the milestone without touching a single weight. Two of four
features exonerated the thing they changed, which is a finding about the reward table rather than a
run of bad luck. The constraint was exploration, and a demonstration removed it.

**Carried forward as unfinished, not as failure.** The 5M sighted probe that would fully separate
reward from exploration from sensing was not run, so that separation is partial. Generalisation
beyond these ten tracks from one generator is unshown. And whole-run training aggregates ranked the
three seeds backwards against held-out result, so future readings should say which numbers are
whole-run and which are end-of-run.

---

## M5: the comparison

### The four columns, and the two axes that disagree

Written 2026-09-02, feature `010-m5-evaluation`. Generated by `python -m python.m5.compare` from
committed inputs under `results/comparison/`; the full report is
[`results/comparison/m5_comparison.md`](comparison/m5_comparison.md).

**No training run and no sweep was performed for M5.** Every number below is read off runs already
recorded above, through inputs exported once and committed. That is the point of the feature: it
measures, it does not produce.

**Execution, which `DESIGN.md` 7 puts first.**

| driver | runs completed | laps per run | seconds per lap | wall contacts |
|---|---|---|---|---|
| `ppo_car_009_bc` deterministic | **10 of 10** | 3 | **20.808** | 0.00 |
| `ppo_car_009_bc` sampling | 9 of 10 | 3 | 21.111 | 0.10 |
| heuristic `WeightedAverage` | **34 of 34** | 1 | 23.655 | 0.00 |
| `bc_balanced_v01` | absent, never drives this track | | | |
| human, combined dataset | absent, a recording of another simulator | | | |

**Seconds per lap, not run time, and the first draft of this table had it wrong.** The run record's
`lap_time_s` is the whole run: the RL sweeps run three laps per attempt and the scripted sweep runs
one. Printed raw, 62.425 against 23.655 says the scripted driver is 2.6 times faster. Per lap the
learned policy is faster. The margin carries its own bound: the two sweeps ran at different
`timeScale` values over different seed sets and lap time was a success criterion for neither.

**Primary axis, `|delta steering|` at 14.08 Hz.** KS statistic `D`, which is also the effect size.
Every driver quantised onto the human's 0.05 lattice first, because 67.8 per cent of the human's
nonzero steering changes land exactly on it and a raw comparison measures the input device.

| driver | mean | median | D raw | **D on lattice** |
|---|---|---|---|---|
| `ppo_car_009_bc` deterministic | 0.0413 | 0.0127 | 0.4603 | **0.2682** |
| heuristic `WeightedAverage` | 0.0174 | 0.0075 | 0.5008 | 0.3780 |
| `bc_balanced_v01` | 0.0248 | 0.0187 | 0.5525 | 0.3810 |
| `ppo_car_009_bc` sampling | 0.1552 | 0.1527 | 0.5306 | 0.4564 |
| human, combined | 0.1112 | **0.0000** | reference | reference |

**Quantisation nearly halves the deterministic policy's distance** (0.4603 to 0.2682) and widens
its lead over the scripted driver from 0.04 to 0.11. The size of that correction is why both are
printed.

**Secondary axis, steering level on the lattice**, marginal and conditional on nonzero steering.

| driver | KL, all samples | **KL, turning only** | chi2, all | dof |
|---|---|---|---|---|
| `ppo_car_009_bc` deterministic | 1.6575 | 1.1291 | 20154.5 | 40 |
| `ppo_car_009_bc` sampling | **1.0556** | **0.9465** | 12740.6 | 40 |
| heuristic `WeightedAverage` | 1.3513 | 1.0527 | 20639.0 | 40 |
| `bc_balanced_v01` | 1.2466 | 0.9787 | 11554.4 | 40 |

All reject. At 5,576 to 32,443 samples per side a KS or chi-square test rejects almost any null, so
the effect sizes carry the result and the p-values are reported because `DESIGN.md` 7.1 asks.

### The result: the two axes name different winners, and that is the finding

**On smoothness the deterministic policy is closest to the human**, D = 0.2682 against the next
driver's 0.3780. **On steering distribution given turning, the sampling policy is closest**,
KL = 0.9465 against the deterministic policy's 1.1291, which is last of the four.

These are **the same policy under two inference modes**. Sampling draws from the action distribution
instead of taking its mean. That spreads the steering levels toward the human's spread while raising
the mean step change from 0.0413 to 0.1552, past the human's own 0.1112. **Noise makes a policy's
distribution more human and its motion less so.** A single answer to "which driver is most
human-like" would have to suppress one of the two measurements.

**Conditioning compresses the whole field.** Dropping the straight-line samples from both sides, as
`DESIGN.md` 7's second M5 note prescribes, moves the deterministic policy from 1.6575 to 1.1291, the
largest move of the four, and narrows the spread between best and worst from 0.60 to 0.18. Most of
what the marginal measured was the straight-line share, and the straight-line share is the track.

### What the comparison cannot say

- **Nothing about BC's driving.** It predicts steering for frames a human already drove, in another
  simulator. Four of its cells are absent as a property, not as missing data.
- **Little about steering level that is not geometry.** The generated loop always turns and runs one
  way: 76 to 88 per cent left against the human's 23.5, and 1 to 3 per cent near zero against 58.6.
- **Nothing about speed across drivers.** Unity rigidbody speed against another simulator's recorded
  units. Variances 1.23 and 10.69, which is a unit mismatch and would read as a finding.
- **Nothing from the p-values**, for the sample-size reason above.

### Reproducibility: the recipe was run, not read

A real clone into a scratch directory, a fresh `py -3.10 -m venv .venv`, then the recipe. Both
commands reproduced every figure and every table **byte for byte**. Four defects were found and
fixed rather than documented:

| defect | cause |
|---|---|
| the human column could not be built at all | `dataset/` is gitignored and downloaded from Kaggle |
| three table cells read `absent` | `results/heuristic/runs_*.csv` is gitignored |
| they stayed `absent` after the export existed | `build()` passed the ignored path explicitly |
| **45 tests failed** where the README promises green | dataset-reading tests failed rather than skipped |

The clean clone also caught a wrong fix: the first trace guard asked whether `results/drive_logs/`
exists, and that directory is tracked and holds committed July traces, so it exists in every clone
while feature 009's 60 gitignored files do not. Suite in a clean clone is now **321 passed, 92
skipped, zero failures**.
