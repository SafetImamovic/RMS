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
| 2026-08-26 | `ppo_car_007_progress` | **The T029 candidate.** One change from feature 006's `ppo_car_v01`: the reward table gains the dense progress term. Full baseline budget, `config/ppo_car.yaml` reused unchanged at 5,000,000 steps, `--seed=42` to match v01 exactly, same twelve areas, same seeds, every existing weight untouched | **5,000,000 steps in 5,395.4 s**, 927 steps/s, uninterrupted. **Markers per episode 1.4987 run mean and 2.6975 over the last 50, against a baseline of 0.2490 and a gate of 0.035.** By quarter 0.3477, 0.9794, 2.1148, 2.5528, which rises monotonically rather than spiking. **Eight laps completed** over 13,851 episodes, where feature 006 completed zero across nine runs and more than 12,000,000 steps. `reward/progress` reaches 1.3843 per episode late, which is 23.2 m of net progress, about 11.5 per cent of a lap, against 2.2 m in the spread set. End reasons 59.1 per cent wall, 27.4 per cent stalled, 13.5 per cent swapped, against the spread set's 47.7 / 39.0 / 13.2. **FR-010 does not hold on this run**: the seven terms sum to the trainer's cumulative reward on 4.8 per cent of rows, residual mean +0.3030 | **The first candidate in M3 that moved the metric it was aimed at**, and the first policy in this project to complete a lap. Model kept and promoted for the T034 to T037 evaluation. The stall fall is **not** clean: see the note below |

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
candidate is that the two numbers average over different sets of episodes — `ReportEpisode` runs on
the paths in `DrivingAgent.Finish` and the step-limit branch, while the trainer's cumulative reward
counts every episode the agent processor sees — but that is a hypothesis for an instrumented check,
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
alone reduced. Not an experiment and it gets no table row — it exists to check that the two defects
recorded above are gone, and its curve is committed at
`results/rl/curves/ppo_car_fr008_check.csv`.

**The end-reason series are counts now.** `end_wallcontact` reads 18, 26, 11, 25, 8, 13, 27, 5, 18,
15 over the ten summaries instead of the flat 1.0000 that carried no frequency information.
`end_trackswapped` is non-zero in every window, which is the swap-ended episodes reaching
`ReportEpisode` for the first time.

**The two halves now average over the same episodes.** `reward/wall` equals
`-5.0 x end_wallcontact / total_episodes` exactly on all ten rows — at step 10000,
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
tolerance — "the six terms sum to the total" is a derived check, not a threshold the spec states.
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
episode rose six fold and eight laps were completed. A policy that had merely swapped one failure
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
