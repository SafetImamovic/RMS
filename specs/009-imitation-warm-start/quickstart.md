# Quickstart: the imitation warm start

## The one-line version

The scripted driver that finishes 34 of 34 training laps has never been shown to the policy. This
feature routes it through the agent's own action path, records what it did, and adds that recording
to the trainer as an imitation loss. The reward table does not change.

## Before anything else: the cadence gate

**Do not record in bulk before this passes.** The scripted driver decides at 50 Hz and the agent
decides at 12.5 Hz, so 34 of 34 does not carry over on its own.

1. Open `Assets/Scenes/Training.unity`, select the agent, set `BehaviorParameters.BehaviorType` to
   **Heuristic Only**.
2. Confirm `HeuristicDriver.Mode` is **Immediate**. `Delayed` sizes its delay ring per call, so on
   the agent's clock the same `reactionTimeS` becomes four times longer (research R4).
3. Run the 34 training seeds and read **lap completion** and **speed tracking** together.

If lap completion collapses, look at speed tracking first: the throttle is bang-bang against a
`0.25 m/s` deadband and one decision period is long enough for the speed to move `0.47 m/s`
(research R3). **Report it and stop the feature. Do not lower `DecisionPeriod`**, which FR-006
pins, because it is the clock every M3 comparison was measured at.

## Record the demonstrations

Add `DemonstrationRecorder` to the agent, set `DemonstrationDirectory` to
`Assets/Demonstrations`, `DemonstrationName` to `heuristic_train34`, and tick `Record`.

Still in **Heuristic Only**, drive the 34 training seeds from `results/tracks/seed_split.json`.
Training seeds only: demonstrations on the ten evaluation seeds would contaminate the one criterion
this project has failed three times.

Then untick `Record` and commit the file through LFS. `*.demo` is in `.gitattributes` for this.

Record its episode count, step count and file size in `results/EXPERIMENTS.md`, and copy the seed
list to `results/rl/demo_seeds.json` so the file's provenance is auditable without opening it.

## Run it

From the repository root. The trainer listens first, then Unity connects.

**Launch the trainer detached**, or a stopped background task takes the run with it. Feature 007
lost a run at 1,440,000 of 2,000,000 steps learning this.

```powershell
$root = "C:\Users\User\Development\RMS"
Start-Process -FilePath "$root\.venv-mlagents\Scripts\mlagents-learn.exe" `
  -ArgumentList "config/ppo_car.yaml", "--run-id=ppo_car_009_bc", "--seed=42", `
                "--torch-device=cuda", "--force" `
  -WorkingDirectory $root `
  -RedirectStandardOutput "$root\results\rl\ppo_car_009_bc.log" `
  -RedirectStandardError  "$root\results\rl\ppo_car_009_bc.err.log"
```

Then open `Assets/Scenes/Training.unity` and press Play. Seed 42 matches `ppo_car_007_progress`,
`ppo_car_008_budget` and `ppo_car_v01`, so the `behavioral_cloning` block is the only difference.

**Check `Losses/Pretraining Loss` in TensorBoard within the first few summaries.** If it is absent
or flat at zero, the demonstration never loaded and the run is measuring feature 007 again. That is
the cheapest way to catch a silently missing warm start, and it costs one glance.

Export the curve when it finishes:

```
.venv-mlagents\Scripts\python.exe -m python.rl.export_curves results/ppo_car_009_bc
```

Evaluate on the held-out seeds: open `Assets/Scenes/Evaluation.unity`, point `BehaviorParameters`
at the new model, press Play. Repeat with deterministic inference off. The two modes are reported
separately and never averaged.

## Read it

**In this order, because the first number can mislead on its own.**

1. **`Losses/Pretraining Loss`**, first. Falling means the policy is fitting the expert. Absent
   means there is no result to read at all.
2. **Markers per episode** against **1.4987**, gated at **0.035**, with the gate's caveat named in
   the same breath: a result landing near it earns a fresh three-run spread rather than a verdict.
3. **The end-reason mix, whole.** A fall in the wall share that turns up as a rise in the stall
   share is a traded failure, not a fixed one. Feature 008 fell into exactly this and named it.
4. **Cumulative reward** against 007 and 008. The comparison is valid because the reward table is
   unchanged, and the claim is backed by the diff rather than asserted.
5. **Held-out laps**, per seed, both inference modes, never averaged. `lapsToComplete` is 3, so a
   recorded lap is three laps and the sentence has to say so.
6. **Throughput** against 903 and 927 steps per second. The BC module adds work per update.

## The two outcomes, both of which are results

**A held-out lap.** M3's milestone is met and the closeout says the limit was exploration, not the
reward table, which retroactively explains why three reward-side features moved nothing.

**No held-out lap.** Then the limit is neither exploration nor the reward, because the policy was
shown the behaviour directly and still could not generalise. The remaining candidates are the
observation's content, the policy class and the vehicle. **That is a publishable answer and it
retires the whole reward-side line of attack**, which is why the feature is worth running either
way.

## After it, whichever way it goes

M3 is capped here by the scope decision of 2026-08-28. Write the milestone closeout into
`DESIGN.md`, then open M5. There is no feature 010.
