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
