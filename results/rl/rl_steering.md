# The learned column: steering, and what it does not buy

Reproduce with, from the repository root under `.venv`:

```
python -m python.rl.report results/rl/eval_ppo_car_spread_a_deterministic.csv \
    --traces results/rl/traces/deterministic \
    --name spread_a_deterministic \
    --dataset dataset/dataset/dataset/driving_log.csv
```

and the same with `sampling` in place of `deterministic`. Both read the run records and the
per-run traces committed beside them, so the figures below do not depend on a training run being
repeated.

## The column, beside the three already recorded

| driver | laps | steering mean | steering variance | mean \|delta steer\| |
|---|---|---|---|---|
| human (dataset, pooled) | - | -0.0209 | **0.1515** | - |
| scripted `WeightedAverage` (feature 005) | **34 of 34** | - | **0.04994** | - |
| learned `ppo_car_spread_a`, deterministic | **0 of 10** | -0.1153 | 0.00055 | 0.0005 |
| learned `ppo_car_spread_a`, sampling | **0 of 10** | -0.1221 | 0.04557 | 0.1452 |
| learned `ppo_car_007_progress`, deterministic | **0 of 10** | -0.2044 | **0.13458** | 0.0722 |
| learned `ppo_car_007_progress`, sampling | **0 of 10** | -0.2119 | **0.11103** | 0.1545 |

## What the lap column cannot say, and the marker column can

**Every learned row above reads 0 of 10 laps, and they are not the same result.**

| driver | laps | markers of 24 | end reasons | mean run duration |
|---|---|---|---|---|
| `ppo_car_spread_a`, deterministic | 0 of 10 | **0.00** | Stalled x10 | 60.00 s |
| `ppo_car_spread_a`, sampling | 0 of 10 | **0.00** | Stalled x10 | 60.00 s |
| `ppo_car_007_progress`, deterministic | 0 of 10 | **6.20** (25.8 per cent of a lap) | WallContact x10 | 7.24 s |
| `ppo_car_007_progress`, sampling | 0 of 10 | **4.60** (19.2 per cent of a lap) | WallContact x10 | 5.92 s |

**Every duration in this document is derived from a count, not from a clock** (FR-021). `duration_s`
is `DrivingAgent.ElapsedS`, accumulated as one `Time.fixedDeltaTime` per physics step on exactly the
ticks the reward terms are charged, so at 50 Hz it is the physics-step count divided by 50. It is
not wall clock and it is not the trainer's episode length, which counts decisions and runs a factor
of about 3.22 smaller.

Feature 006's policy sat at the start line until the 60 second stall cap on every held-out seed.
Feature 007's drives a quarter of the lap and hits a barrier. Both are a loss against the scripted
driver's 34 of 34, and a report that carried only the lap count would have called them the same
loss. `python/rl/report.py` now prints the marker figure beside the lap figure for this reason, and
says in the loss line whether the driver stopped late or never started.

Learned figures for feature 006 are 8,450 steering samples and 8,440 differences; feature 007's
are far smaller, 1,017 and 831, because its runs end in seven seconds instead of sixty. All are
taken at `COMPARE_HZ` (14.08 Hz)
over ten held-out seeds, each run resampled and differenced separately. Human and scripted figures
are quoted from M1 and feature 005 rather than recomputed, so this document cannot drift from the
ones that published them.

## The losses, stated plainly

**Lap completion: 0 of 10 against the scripted driver's 34 of 34.** No evaluation episode reached
a single one of the 24 checkpoints, in either inference mode, on any held-out seed. Every run
ended `Stalled` at the 60 s cap with zero wall contacts. This is the headline and it is a loss.

**Neither SC-001 nor SC-002 is met.** SC-001 asks for 95 per cent of episodes completing 3 laps
without wall contact; the achieved rate is 0.0 per cent. SC-002 asks for at least one lap on 80
per cent of held-out seeds; the achieved rate is 0.0 per cent.

## The finding that needed the distribution rather than the lap count

**The sampling policy's steering variance is 0.04557 against the scripted driver's 0.04994 - a
difference of nine per cent - and it completes no laps at all.** Feature 005's research rejected
steering variance as a standalone measure on the argument that it cannot separate a smooth large
input from a jittery small one. This is a sharper version of the same point, measured rather than
argued: a driver that never leaves the start can match a lapping driver's steering variance to
within a tenth. Any comparison that led with variance would have called these two drivers close.

**The two inference modes are two different drivers from one set of weights (FR-026).** On
feature 006's weights their outcomes were identical - 0 laps, 0 checkpoints, 0 wall contacts, all
ten runs stalled - and their steering had nothing in common. Variance differed by a factor of 83,
mean \|delta steer\| by a factor of 290.

**That factor of 83 should not be quoted as a property of the two modes, and feature 007 is what
shows why.** It was a ratio taken over a deterministic variance of 0.00055, produced by a car that
barely turned its wheel. Measured on weights that actually steer, the same ratio is **2.86** on
p95 \|delta steer\| (0.8550 against 0.2988) and 0.83 on variance, meaning the deterministic policy
is now the *more* varied of the two. The modes still differ, they still get reported separately and
never averaged, and the size of the difference was never the 83. Deterministic inference takes the distribution's mean and produces a nearly
constant slight left lock (variance 0.00055); sampling reproduces the exploration noise PPO used
while training. Reporting only the lap rate would have made FR-026 look immaterial; it is not, and
the difference would matter enormously for any policy that actually drove.

Both modes carry the same **systematic left bias**, mean -0.115 and -0.122 against the human
column's -0.021. That bias is in the weights rather than in the sampling.

## Against the human distribution, with the caveat the test deserves

`chi2_homogeneity` from `python/eda/authenticity.py` - the same test feature 002 used to ask
whether two tracks share one steering distribution - counted on the dataset's own 0.05 lattice,
41 support points from -1 to +1:

| comparison | chi2 | dof | critical | p | reject H0 | learned n |
|---|---|---|---|---|---|---|
| `spread_a` deterministic vs human | 34,464.4 | 40 | 55.8 | ~0 | yes | 8,450 |
| `spread_a` sampling vs human | 14,591.8 | 40 | 55.8 | ~0 | yes | 8,450 |
| `007_progress` deterministic vs human | 1,986.0 | 34 | 48.6 | ~0 | yes | 1,017 |
| `007_progress` sampling vs human | 1,631.7 | 28 | 41.3 | ~0 | yes | 831 |

Both reject the null that the learned and human steering share one distribution, overwhelmingly.

**The caveat is that this test was never going to say anything else, and saying so is part of
reporting it.** With 8,450 learned samples against 32,443 human ones, chi-squared rejects
differences far too small to matter to a driver; a statistic of 14,591 against a critical value of
55.8 is not a measurement of how different these drivers are, it is a measurement of how much data
there is. The **ordering** is the informative part - sampling is closer to the human distribution
than deterministic is, by a factor of 2.4 on the statistic - and even that is a weak claim to hang
on a test in its saturated regime. The distributional figures in the table above carry more than
the p-value does.

**Feature 007 carries that caveat forward rather than dropping it, and it applies with less force
rather than more.** Its statistics are an order of magnitude smaller, 1,986 and 1,632 against
34,464 and 14,592, and its samples are far fewer, 1,017 and 831 against 8,450. That is not the
policy becoming more human: it is runs that last seven seconds instead of sixty, so there is less
data to saturate the test with. **The test remains in a regime where it measures data volume, so
the rejection is still not the interesting part.** Reading a drop in the statistic as a drop in
difference would be reading the run length.

**What is worth noting is in the distribution table, not the test.** Feature 007's steering
variance is 0.13458 deterministic and 0.11103 sampling, against the human column's 0.1515 and the
scripted driver's 0.04994. Feature 006's deterministic policy sat at 0.00055. A policy that drives
produces a steering distribution of roughly human spread, which feature 005's research predicted
would happen and warned would not by itself mean the driver was any good. It does not: this one
still completes no laps. The variance moving into the human range while the lap count stays at
zero is the same lesson feature 006's row recorded from the other side.

## What resolves to what

Every figure here resolves to a run id, and from there to a config, a curve and an `EXPERIMENTS.md`
row (SC-004):

- `ppo_car_spread_a`, seed 1, `config/ppo_car_spread.yaml` at 2,000,000 steps
- curve: `results/rl/curves/ppo_car_spread_a.csv`; log: `results/rl/ppo_car_spread_a.log`
- model: `unity/SelfDrivingSim/Assets/Models/ppo_car_spread_a-2000063.onnx`
- rows: `results/rl/eval_ppo_car_spread_a_{deterministic,sampling}.csv`
- traces: `results/rl/traces/{deterministic,sampling}/run_01..10.csv`
- scene: `unity/SelfDrivingSim/Assets/Scenes/Evaluation.unity`

`spread_b` and `spread_c` are committed under `Assets/Models/` and **have not been evaluated**.
The three baselines are statistically indistinguishable on the training metric - the widest gap
between their run means is 0.165, inside T047's 0.19 gate - so `spread_a` was taken as
representative rather than as the best of three, and picking the best would have been picking
noise. Evaluating the other two would turn the 0 of 10 above into three independent 0 of 10s.

## Why the number is zero

Not a mystery, and recorded in full in `results/EXPERIMENTS.md`: this reward table cannot be fixed
by scaling its weights. Three one-change tuning candidates were run at the reduced budget and none
cleared the noise floor in the better direction. The clearest of the three doubled the payment for
moving and bought twelve per cent more speed, which is what a policy that has not found the
behaviour looks like, rather than one that is underpaid for it. The remedies named there are of a
different kind from a weight: a curriculum starting nearer a marker, a denser progress signal than
one marker in twenty-four, or a warm start from the M4 behavioural-cloning policy.
