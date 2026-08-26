# Quickstart: Running the Dense Progress Reward

**Feature**: `007-dense-progress-reward` | **Date**: 2026-08-25

Written for the state after implementation. Until the tasks are done, this is the target the tasks
are aimed at rather than a recipe that runs.

Feature 006's quickstart is not superseded. Everything about starting the trainer, the port, the
version handshake and the killed-run rule still applies, and is not repeated here. This file covers
only what is different, which is the order the runs go in and the checks that come before them.

## Before any run: the term has to be right first

The whole feature rests on two properties, and both are checkable in seconds without a training
run. Do this before spending an hour on a trainer.

```powershell
# Unity EditMode, owner-run from the Test Runner window.
# TestRunnerApi trips the MCP user-interaction guard, so this stays a human step.
#   Window > General > Test Runner > EditMode > Run All
```

The two that decide the feature are in `TrackProgressTests`:

- **Telescoping.** The summed term over a lap equals the endpoint difference, within R9's
  tolerance.
- **The loop property.** A trajectory returning to a state it already occupied sums to zero.

If either fails, no training run is worth starting. The term is not a potential difference and the
run would measure a different reward from the one the design describes.

## The scripted-driver check, which is the real instrument

The scripted driver completes 34 of 34 training seeds, so it is the only driver in the project that
can drive a full lap on demand. Use it to confirm the term against the geometry:

1. Open `Assets/Scenes/Evaluation.unity`. Remember the scene note from feature 006: the
   `TrainingArea` component must stay removed from the instance, because it parks the car in
   `Awake` waiting for an `AreaScheduler` this scene does not have.
2. Run one seed with the scripted driver and the reward instrumentation on.
3. Read the run's `reward/progress` total against `0.5 * 24.0` scaled by the fraction of the chain
   the lap actually covered from its start marker.

A full lap from any start marker covers the whole chain, so the prediction is **12.0**, and it does
not depend on where the lap started. If the measured total is not 12.0 within the tolerance, stop:
either the clamp is firing when it should not, or the unwrapping is wrong at the finish.

## The order of the runs, and why it is this order

**This is the part that is different from feature 006, and getting it wrong makes every later
number unbacked.**

1. **Three identical spread runs first.** Same reduced budget as feature 006 T047, seeds 1, 2 and 3,
   nothing different between them but the trainer seed. Report sample standard deviation and gate
   for **markers earned per episode**, **laps completed** and **stalled share**.
2. **Write `results/rl/progress_spread.md` before looking at any candidate.** The M3 closeout is
   explicit that a gate quoted after the fact is decoration.
3. **Then the candidate run.** One change from the 006 baseline: the reward table gains the
   progress term. Budget, hyperparameters, area count, decision period and seed split all held.
4. **Then evaluation**, on the ten held-out seeds, both inference modes, with the sweep's existing
   warning that it is touching the held-out half.

**Do not reuse the 0.19 gate from feature 006.** It was measured on cumulative reward, and adding a
term changes the scale of cumulative reward, so the two tables' totals are not comparable at all
(FR-018). This is the single easiest mistake to make in this feature, because 0.19 is written down
and looks authoritative.

## Reading the result

The number that says whether the mechanism worked is **markers earned per episode**, against the
006 baseline of **0.249**, judged against the gate measured in step 2.

The number that says whether the milestone moved is **laps completed on the ten held-out seeds**,
against feature 006's **0 of 10** and the scripted driver's **34 of 34**.

Three outcomes, all of them reportable:

- **Markers up past the gate and laps completed.** M3's criteria are re-measured and the closeout
  table is rewritten with the new numbers.
- **Markers up past the gate, no laps.** The shaping worked and something else is the binding
  constraint. That is a result, it names the next feature, and it is written up as such rather than
  as a partial failure.
- **Markers not past the gate.** The dense signal was not the missing piece either. Then the M3
  closeout's remaining two remedies, curriculum and imitation warm start, are what is left, and
  this feature has removed one candidate from three by measurement.

## After every run, in the same session

Unchanged from feature 006 and from Principle VI: a row in `results/EXPERIMENTS.md` naming the one
change and the outcome. An unlogged run did not happen.

## The failures worth recognising

- **A huge reward or penalty on the first step of an episode.** The previous position was not
  cleared. Check the training-area swap path (R7), not just the ordinary episode end.
- **A single step per lap charging about 12.0 negative.** The unwrapping is not happening and the
  position reset at the finish.
- **`reward/progress` near zero on a car that is clearly moving.** The clamp is holding the position
  at the due marker, which means the ring's `NextIndex` and the geometry disagree about which
  segment the car is on.
- **The breakdown stops summing to cumulative reward.** Something else called `AddReward`. That rule
  is inherited from feature 006 and it is what makes FR-010 checkable at all.
- **Throughput drops well below 684 steps/s.** The segment lengths are being recomputed per step
  instead of per track build.
