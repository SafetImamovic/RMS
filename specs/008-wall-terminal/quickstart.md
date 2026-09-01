# Quickstart: the wall terminal

## The one-line version

A wall contact used to end the episode. Now it charges the same penalty and the episode continues
until a budget of contacts is spent. Nothing else changes.

## Run it

From the repository root. The trainer listens first, then Unity connects.

**Launch the trainer detached**, or a stopped background task takes the run with it. Feature 007
lost a run at 1,440,000 of 2,000,000 steps learning this.

```powershell
$root = "C:\Users\User\Development\RMS"
Start-Process -FilePath "$root\.venv-mlagents\Scripts\mlagents-learn.exe" `
  -ArgumentList "config/ppo_car.yaml", "--run-id=ppo_car_008_budget", "--seed=42", `
                "--torch-device=cuda", "--force" `
  -WorkingDirectory $root `
  -RedirectStandardOutput "$root\results\rl\ppo_car_008_budget.log" `
  -RedirectStandardError  "$root\results\rl\ppo_car_008_budget.err.log"
```

Then open `Assets/Scenes/Training.unity` and press Play. Seed 42 matches
`ppo_car_007_progress` and `ppo_car_v01`, so the reward table's terminal is the only difference.

Export the curve when it finishes:

```
.venv-mlagents\Scripts\python.exe -m python.rl.export_curves results/ppo_car_008_budget
```

Evaluate on the held-out seeds: open `Assets/Scenes/Evaluation.unity`, point
`BehaviorParameters` at the new model, press Play. Repeat with deterministic inference off. The
two modes are reported separately and never averaged.

## Read it

**In this order, because the first number can mislead on its own.**

1. **Markers per episode** against **1.4987**, gated at **0.035**. This is SC-003's successor and
   the headline.
2. **Wall contacts per episode**, `episode/wall_contacts`. A rise in markers bought with a rise in
   contacts is a different result from a rise bought cleanly.
3. **Lateral clearance**, `episode/lateral_clearance`. If it falls sharply while contacts stay flat,
   the policy found the grinding strategy: research R2 explains why the contact count alone cannot
   see that, because a whole grind registers as one contact.
4. **The end-reason mix.** A fall in the wall share that shows up as a rise in the stall share is a
   traded failure, not a fixed one. Feature 007 hit exactly this and said so.
5. **Laps on the held-out seeds.** The milestone. `lapsToComplete` is 3 in `Evaluation.unity`, so a
   recorded lap is three laps.

## What good and bad look like

| Reading | What it means |
|---|---|
| markers up, contacts flat, clearance flat | the terminal was the constraint. The clean result |
| markers up, contacts up, clearance down | grinding. The number rose for a reason nobody wants (R8) |
| markers flat | the terminal was not the constraint, and it is exonerated the way the penalty was in feature 006 |
| wall share down, stall share up by the same amount | a traded failure. Read the markers before calling it progress |
| episodes far longer, throughput well down | expected, and the stall timeout is now doing the work. Report it (R6, SC-009) |

## Traps

- **The recovery probe comes first.** If the car cannot reverse off a barrier, the budget converts a
  seven second `WallContact` ending into a sixty second `Stalled` one and buys nothing. That is R4
  and it is a gate that can cancel the feature.
- **Do not quote the 0.19 gate.** Feature 006 measured it on cumulative reward and feature 007
  retired it. The gate here is 0.035 on markers per episode, and its caveat travels with it.
- **Do not compare cumulative reward to feature 006.** The table gained a term in feature 007 and
  the scale changed. Comparing to `ppo_car_007_progress` is fine: the table is identical.
- **Feature 007's SC-007 defect is inherited.** The seven terms sum to the trainer's total on 4.8
  per cent of rows. Behavioural counts are Unity-side and unaffected; any claim resting on the
  reward decomposition is not.
- **Watch for `Step: 5000000`, not "Exported".** The trainer exports a checkpoint every 100,000
  steps, so grepping for "Exported" matches long before the run is done.
