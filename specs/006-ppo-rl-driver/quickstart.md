# Quickstart: Training and Evaluating the PPO Driver

**Feature**: `006-ppo-rl-driver` | **Date**: 2026-08-17

Written for the state after implementation. Until the tasks are done, this is the target the tasks
are aimed at rather than a recipe that runs.

## Before anything

The keyboard-lap gate is already satisfied. Feature 003 T051 recorded hand-driven laps on seeds 37,
29, 1003, 1 and 1004, so "no keyboard lap, no training" is met and training may start.

The training environment is `.venv-mlagents` and it is separate on purpose. `mlagents` pins
`numpy==1.23.5`, and M1's committed numbers were produced under 1.26.4 in `.venv`. Do not merge
them.

```powershell
.venv-mlagents\Scripts\activate
mlagents-learn --help          # confirms the trainer is installed
```

## One training run

**1. Open the training scene.** `Assets/Scenes/Training.unity`. Do not press Play yet. Pressing
Play before the trainer is listening runs the agents with no policy attached, which wastes the
first seconds of every area and looks like a hung editor.

**2. Start the trainer from the repository root.** The working directory matters: `mlagents-learn`
writes `results/` relative to it, and running it elsewhere scatters output outside the project.

```powershell
cd C:\Users\User\Development\RMS
.venv-mlagents\Scripts\activate
mlagents-learn config/ppo_car.yaml --run-id=ppo_car_v01 --torch-device=cuda
```

Wait for `Listening on port 5004`.

**3. Press Play in the editor.** The connection line names both versions and both must match what
`ENVIRONMENT.md` records:

```text
[INFO] Connected to Unity environment with package version 4.0.3 and communication version 1.5.0
```

**4. Watch the curves.** In a second terminal:

```powershell
tensorboard --logdir results
```

The series worth watching first is not the cumulative reward. It is `reward/checkpoint`: if that
stays flat while the total moves, the policy is collecting step and speed reward without making
progress, which is the failure the per-term reporting exists to make visible.

**5. Stop with a single `Ctrl+C`.** One interrupt exports the `.onnx`. A second one skips the
export, and a night of training is then only a checkpoint file.

```text
[INFO] Exported results\ppo_car_v01\CarDriver\CarDriver-<step>.onnx
```

## After every run, in the same session

An unlogged run did not happen (Principle VI). Three things happen before the terminal is closed:

**1. Export the curve.**

```powershell
python -m python.rl.export_curves results/ppo_car_v01 --out results/rl/curves/ppo_car_v01.csv
```

**2. Copy the model** into `unity/SelfDrivingSim/Assets/Models/`, keeping the step suffix in the
name. It is LFS-tracked already by `.gitattributes`.

**3. Add the row** to `results/EXPERIMENTS.md` under the RL section: run id, what this run changed
from the previous one in one line, what the numbers said, and whether the change was kept.

## Evaluating a model

Evaluation runs the same sweep runner feature 005 used, on the held-out seeds, so the learned rows
and the scripted rows land in the same shape.

1. Open `Assets/Scenes/Training.unity`, or the single-area scene if evaluating visually.
2. Put the `.onnx` on the agent's `BehaviorParameters` and set the behaviour type to inference.
3. Set the sweep runner's seed set to **eval** and its repeats to the number the spread needs.
4. Press Play. Rows land in `results/rl/` with the run id in the controller column.

Then join the columns:

```powershell
deactivate
.venv\Scripts\activate
python -m python.rl.report results/rl/<runs file> --traces results/rl/<traces dir>
```

## The failures worth recognising

| Symptom | Cause | Fix |
|---|---|---|
| Trainer sits at 0 steps, editor plays normally | Behaviour name in the scene does not match `behaviors:` in the config | They must be identical strings; the trainer does not warn |
| `Mismatched observation size` or silently poor learning | Vector size in `BehaviorParameters` does not match `CarAgent.ObservationCount` | The agent asserts this at start-up; read the assertion rather than raising the size to match |
| Communication version mismatch on connect | Wrong `mlagents` version in the active venv | `ENVIRONMENT.md`: package 4.0.3 against pip 1.1.0, Communicator 1.5.0 |
| No `.onnx` after a long run | Two `Ctrl+C` presses | The checkpoint under `results/<run-id>/` still exists; it can be resumed, not exported directly |
| One area does nothing while others train | That area's agent ended an episode during a track swap | The area scheduler disables the agent across the swap; if it stays disabled, the swap did not complete |
| Cars sensing walls that are not there | Areas placed closer than 300 m | Rays are 20 m and a track is roughly 200 m across; the grid pitch is not decoration |

## Reproducing a number that is already in the results

Every reported figure resolves to a run id. From a run id:

- the configuration is `config/ppo_car.yaml` at the revision of that run's commit,
- the curve is `results/rl/curves/<run-id>.csv`,
- the model is `Assets/Models/<run-id>-<step>.onnx`,
- the row is in `results/EXPERIMENTS.md`,
- the evaluation rows carry the run id in their controller column.

If any one of those is missing, the number is not reproducible and the run has to be repeated.
