# The noise floor for feature 007, and the gates this feature uses

Three runs at the reduced budget, identical but for `--seed`: `ppo_car_007_spread_a`, `_b` and `_c`.
All three carry the dense progress term, so this is the spread of *this* feature's reward table and
not of feature 006's.

**Written before any candidate run existed.** That ordering is the whole point (FR-017, R8). A gate
chosen after seeing the number it judges is not a gate.

## The 0.19 gate from feature 006 may not be reused, and this is why

Feature 006's gate of 0.19 was measured on the run mean of `Environment/Cumulative Reward`. This
feature adds a seventh term to the reward table, which changes the scale of that quantity, so a
difference measured against it is partly bookkeeping and partly policy. Feature 006 hit exactly this
trap on `ppo_car_jerk_lo`, where a raw +0.3378 looked like a clear pass and +0.2824 of it turned out
to be the same episodes charged at a different scale.

The fix there was to rescore the baseline into the candidate's table. That works for a changed
weight and does not work for an added term, because there is no term to rescore: the baseline runs
never charged it.

So this feature is judged on **behaviour rather than on return**. The metrics below are counts of
what the car did, and adding a reward term does not change what reaching a marker means.

## The metrics, and how each is taken

| metric | definition |
|---|---|
| markers per episode | run mean of `episode/markers` over all 200 summaries, which is `CheckpointRing.AwardedCount` at episode end |
| laps completed | sum of `episode/end_lapscompleted` over the run, a count and not a mean |
| stalled share | `episode/end_stalled` summed over the run, divided by every end reason summed over the run |

**Shares are taken over summed counts, not as a mean of per summary shares.** A summary with four
episodes and one with forty would otherwise weigh the same.

**`markers_per_episode` and `reward_checkpoint` are the same number**, exactly, because
`RewardModel.CheckpointReward` is 1.0. Verified on all 600 rows of this set: the largest absolute
difference is 0.0000000000. That matters because it makes feature 006's checkpoint figures directly
comparable to this feature's marker figures with no conversion.

## The set

| | a (seed 1) | b (seed 2) | c (seed 3) | mean | sd | range |
|---|---|---|---|---|---|---|
| markers per episode, run mean | 0.2608 | 0.2290 | 0.2576 | 0.2491 | **0.0175** | 0.0317 |
| markers per episode, last 50 | 0.2541 | 0.2326 | 0.2714 | 0.2527 | 0.0195 | 0.0388 |
| within run sd, markers | 0.1354 | 0.1217 | 0.1281 | 0.1284 | | |
| stalled share | 0.3962 | 0.3793 | 0.3954 | 0.3903 | **0.0095** | 0.0169 |
| wall share | 0.4715 | 0.4885 | 0.4721 | 0.4773 | 0.0097 | 0.0171 |
| track swapped share | 0.1324 | 0.1322 | 0.1326 | 0.1324 | 0.0002 | 0.0004 |
| laps completed | 0 | 0 | 0 | 0 | | |
| episodes | 5,046 | 5,181 | 4,993 | | | |
| `reward/progress`, run mean | 0.1379 | 0.1238 | 0.1356 | 0.1324 | 0.0076 | 0.0141 |
| cumulative reward, run mean | -4.4127 | -4.4902 | -4.4783 | -4.4604 | 0.0418 | 0.0775 |
| steps, wall clock | 2M in 2,540.7 s | 2M in 2,597.9 s | 2M in 2,649.4 s | | | |

## The gates

Two standard deviations, the same rule feature 006 used to turn 0.0924 into 0.19.

| metric | sd | gate | baseline to beat |
|---|---|---|---|
| markers per episode | 0.0175 | **0.035** | **0.249** |
| stalled share | 0.0095 | **0.019** | 0.390 in this set |
| laps completed | 0 | **any lap at all** | 0 |

**Laps completed needs no arithmetic gate.** No run in feature 006 completed a lap across nine runs
and more than 12,000,000 steps, and no run in this set completed one either. Against a floor of
exactly zero, one lap is the signal (SC-004).

## What this set already says, before any candidate

**The term is being paid, and it is tiny.** `reward/progress` averages 0.1324 per episode. At the
derived weight of 0.05970 per metre that is **2.2 metres of net progress per episode**, about **1.1
per cent of a 201 metre lap**, in episodes averaging some 535 steps. The term works exactly as
designed and the policy is barely moving along the chain.

**Markers per episode did not move at this budget.** This set means 0.2491 against feature 006's
0.249, and on the last 50 summaries 0.2527 against 006's spread set at 0.2539. Those differences
are an order of magnitude inside the 0.035 gate. **This is not the feature's verdict**, because the
candidate (T029) runs at the full 5,000,000 step budget and these are 2,000,000 step runs, but it is
a fair warning and it is recorded here rather than discovered later.

**The end reason mix is unchanged too**, at 47.7 wall / 39.0 stalled / 13.2 swapped against feature
006's 46.8 / 39.9 / 13.3. The stall did not fall and the wall did not rise to replace it. Neither
moved.

**The between run spread is far smaller than the within run spread**, 0.0175 against 0.1284 on
markers per episode, a factor of seven. That is what makes a run mean usable and condemns any
comparison quoted from a handful of summaries.

## The step accounting, settled here rather than left to Phase 6

`episode/physics_steps` divided by `Environment/Episode Length`, per summary, then averaged:

| | a | b | c | mean | sd |
|---|---|---|---|---|---|
| ratio | 3.1652 | 3.1536 | 3.1627 | **3.1605** | 0.0061 |

Against the expected ceiling of **4**, which is `DecisionPeriod: 4` with
`TakeActionsBetweenDecisions` on, confirmed in the scene. Feature 006 measured a mean of about 3.16
and could not say why, because only the trainer's half of the ratio was ever recorded. It now
reproduces across three independent seeds to within 0.012, so the shortfall is a stable property of
the setup and not noise. Separating the two mechanisms R6 names is T042.

## Two limits, stated rather than buried

**Three runs estimate a standard deviation to roughly 50 per cent.** These gates are working
thresholds. A candidate landing near one deserves a fourth run rather than a verdict.

**Failing to clear a gate is weaker evidence than clearing one.** Research R9's argument that a
reduced budget over estimates the spread does not apply while the policy is not learning, and all
three of these are flat. The risk runs the other way: a candidate that genuinely starts to learn
will be noisier than these three, so clearing 0.035 is credible while failing to clear it is a
softer negative than it looks.
