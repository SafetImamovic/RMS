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
