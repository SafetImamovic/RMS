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

Learned figures are 8,450 steering samples and 8,440 differences, taken at `COMPARE_HZ` (14.08 Hz)
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

**The two inference modes are two different drivers from one set of weights (FR-026).** Their
outcomes are identical - 0 laps, 0 checkpoints, 0 wall contacts, all ten runs stalled - and their
steering has nothing in common. Variance differs by a factor of 83, mean \|delta steer\| by a
factor of 290. Deterministic inference takes the distribution's mean and produces a nearly
constant slight left lock (variance 0.00055); sampling reproduces the exploration noise PPO used
while training. Reporting only the lap rate would have made FR-026 look immaterial; it is not, and
the difference would matter enormously for any policy that actually drove.

Both modes carry the same **systematic left bias**, mean -0.115 and -0.122 against the human
column's -0.021. That bias is in the weights rather than in the sampling.

## Against the human distribution, with the caveat the test deserves

`chi2_homogeneity` from `python/eda/authenticity.py` - the same test feature 002 used to ask
whether two tracks share one steering distribution - counted on the dataset's own 0.05 lattice,
41 support points from -1 to +1:

| comparison | chi2 | dof | critical | p | reject H0 |
|---|---|---|---|---|---|
| deterministic vs human | 34,464.4 | 40 | 55.8 | ~0 | yes |
| sampling vs human | 14,591.8 | 40 | 55.8 | ~0 | yes |

Both reject the null that the learned and human steering share one distribution, overwhelmingly.

**The caveat is that this test was never going to say anything else, and saying so is part of
reporting it.** With 8,450 learned samples against 32,443 human ones, chi-squared rejects
differences far too small to matter to a driver; a statistic of 14,591 against a critical value of
55.8 is not a measurement of how different these drivers are, it is a measurement of how much data
there is. The **ordering** is the informative part - sampling is closer to the human distribution
than deterministic is, by a factor of 2.4 on the statistic - and even that is a weak claim to hang
on a test in its saturated regime. The distributional figures in the table above carry more than
the p-value does.

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
