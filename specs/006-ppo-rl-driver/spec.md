# Feature Specification: PPO Reinforcement Learning Driver

**Feature Branch**: `006-ppo-rl-driver`
**Created**: 2026-08-17
**Status**: Draft
**Input**: User description: "PPO reinforcement-learning driver (M3). Wrap the existing CarAgent MonoBehaviour in an ML-Agents Agent so the same 19-value observation vector (13 rays + 6 self-state) that the heuristic reads is what the network reads, with 2 continuous actions (steering, throttle). Implement the reward function decided in DESIGN 4.5: +1.0 correct-direction checkpoint, -1.0 wrong-direction checkpoint (scoring the rule CheckpointRing already reports), -5.0 and end episode on wall contact, -0.001 per step, +0.001 x v_norm forward speed, -0.005 x |delta| on steering jerk above the 0.55 P95 threshold from M1. Episodes reset through StartPlacer with the randomized start already fixed in M2 (1.5 m lateral, 10 deg yaw). Train PPO with mlagents-learn on generated training seeds, hold evaluation seeds out, log every run in results/EXPERIMENTS.md and results/tensorboard/, and export a .onnx that drives laps in Unity inference. Measure the run-to-run spread before comparing any two configurations, the same way feature 004 R13 and feature 005 T027 did. Do not tune the heuristic or change the 13/180/20 ray geometry, since both would invalidate the M5 comparison. Deliverable is the RL column of the M5 comparison: lap completion rate and steering smoothness on evaluation seeds, measured against the heuristic and BC numbers already recorded."

## Why this feature exists

The assignment is locked to Unity ML-Agents, and the learned driver it names does not exist. The
project has a track generator, a vehicle, sensing, checkpoints, a scripted driver and an imitation
model. What it does not have is the one thing the topic is about. Every other milestone was, in
part, scaffolding for this one.

The bar has also moved since the reward table was written. When `DESIGN.md` 4.5 fixed those
weights, nothing had ever driven this track. It now has: the scripted driver completes a lap on 34
of 34 training seeds with a steering variance of 0.04994, using nothing but the same rays the
network will read. So "PPO completes laps" is not a result any more. The result is PPO measured
against a baseline that already wins, reported either way.

The third reason is that the reward table is a decision nobody has tested. `DESIGN.md` 4.5 states
plainly that its weights are initial and get tuned in M3. Tuning a reward is the easiest place in
this project to fool oneself, because every run produces a curve that goes up against whatever
reward it was given. The tuning has to be measured against the noise, or it is decoration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A policy that trains at all (Priority: P1)

Someone opens the training scene, starts the trainer from the command line, and watches the
cumulative reward curve rise while cars drive themselves around copies of the track. Episodes
start, accrue reward, end for a stated reason, and start again without human input.

**Why this priority**: nothing else in this feature can be attempted until an episode loop exists
and the trainer talks to it. It is also the point at which the reward table stops being a design
document and becomes something that can be wrong in a way that shows.

**Independent Test**: launch a short training run and confirm the trainer connects, episodes
terminate for the reasons the design lists, and the recorded cumulative reward over the run is
higher at the end than at the start.

**Acceptance Scenarios**:

1. **Given** the training scene and the pinned trainer configuration, **When** training is
   started, **Then** the trainer connects and reports the observation and action shapes the design
   declares, without a manual step to reconcile them
2. **Given** a running training session, **When** an episode ends, **Then** it ends for one of the
   stated terminal conditions and the next episode starts from a randomised legal position
3. **Given** a completed short run, **When** the reward curve is read, **Then** it is available as
   recorded data rather than a screenshot, and the run has an entry describing what it changed
4. **Given** the agent is disabled, **When** the scene is played, **Then** keyboard driving and
   the scripted driver behave exactly as they did before this feature

---

### User Story 2 - The trained model drives the car in Unity (Priority: P1)

Someone takes the model file the training run produced, drops it into the scene, presses play on a
track the agent never trained on, and watches the car drive itself. No trainer process, no Python.

**Why this priority**: equal first, because this is the milestone gate and it is not implied by
the first story. A policy that scores well while attached to the trainer and then drives
differently once exported is a failure that only this test catches.

**Independent Test**: run the exported model in inference on held-out seeds and record what the
car does, with no trainer process running.

**Acceptance Scenarios**:

1. **Given** an exported model and a held-out track seed, **When** the scene is played in
   inference, **Then** the car drives under the model's control with no trainer attached
2. **Given** the same model and seed, **When** the run is compared against what the policy did at
   the end of training, **Then** any difference in behaviour is stated as a measured tolerance
   rather than assumed to be zero
3. **Given** an inference run, **When** it ends, **Then** the same per-run outcome record the
   scripted driver produces is written, so the two are readable side by side

---

### User Story 3 - Reward changes are attributed, not guessed (Priority: P2)

Someone changes exactly one thing in the reward or the hyperparameters, reruns, and can say
whether the difference in the outcome is larger than the difference two identical runs already
show.

**Why this priority**: it depends on training existing, but every number this feature reports
afterwards depends on it. Reinforcement learning is noisier run to run than anything measured in
this project so far, and the two features that came before both found that the noise floor had to
be measured before any comparison meant anything.

**Independent Test**: run the same configuration three times without changing anything, report the
spread of the outcome, then compare any two different configurations against that spread.

**Acceptance Scenarios**:

1. **Given** one fixed configuration, **When** it is run repeatedly without changes, **Then** the
   run-to-run spread of the reported outcome is recorded as a number
2. **Given** two configurations differing in exactly one thing, **When** their outcomes are
   compared, **Then** the comparison states whether the difference exceeds that spread
3. **Given** a change that does not beat the spread, **When** results are written up, **Then** it
   is recorded as a change that made no measurable difference rather than dropped
4. **Given** any training run at all, **When** the session ends, **Then** the run has a log entry
   naming what it changed and what happened, written in that same session

---

### User Story 4 - The RL column of the final comparison (Priority: P2)

Whoever assembles the final comparison can place the learned driver's lap completion and steering
behaviour beside the scripted driver's, the imitation model's and the human's, described by the
same measures.

**Why this priority**: this is what the milestone is for, and it is the deliverable the defence
asks about. It is P2 only because it cannot start until a model exists.

**Independent Test**: produce the learned driver's steering distribution and lap outcomes over the
held-out seeds and confirm they use the same measures as the columns already recorded.

**Acceptance Scenarios**:

1. **Given** a trained model evaluated on the held-out seeds, **When** its steering behaviour is
   summarised, **Then** it uses the same descriptive measures and the same summary shape as the
   human, imitation and scripted columns already in the results
2. **Given** the scripted driver outperforms the learned one on any measure, **When** results are
   written up, **Then** that is stated plainly, with the measure named, rather than omitted
3. **Given** the learned driver is compared against the human steering distribution, **When** the
   comparison is made, **Then** it uses a statistical measure rather than an eyeballed pair of
   histograms

### Edge Cases

- What happens in the first episodes, when the car hits a barrier within seconds? Ending the
  episode on wall contact means the earliest episodes carry almost no experience of a checkpoint,
  and the reward for progress may never be sampled. If nothing ever reaches the first marker, the
  agent is learning only how to stop moving.
- What happens when the car stops moving altogether? The per-step penalty makes standing still
  cost something, but a car that creeps forward slowly enough may still outlast any patience. An
  episode must end on a step limit regardless of what the car is doing.
- What happens when the car drives the loop backwards? It sees open track ahead and the sensing
  cannot tell it apart from the right direction. The wrong-direction rule exists and is currently
  reported without being scored; scoring it is what makes the distinction learnable.
- What happens when a policy learns to farm the forward-speed reward without making progress, for
  example by circling in an open part of the track? A reward that pays for speed pays for it
  whether or not the car is going anywhere.
- What happens when several training copies of the track run in the same scene? Anything shared
  between them, whether a static field, a log file, or a single set of markers, makes one car's
  episode affect another's, and the resulting data would be untraceable.
- What happens when training runs faster than real time? The vehicle's behaviour is produced by a
  physics simulation, and a physics step that is stable at one rate is not automatically stable at
  another. A policy trained against a car that behaves differently under acceleration has learned
  the wrong car.
- What happens when a training run is interrupted, by a crash, a full disk, or a closed laptop?
  A run that cannot be resumed or must be silently discarded still consumed hours.
- What happens if the sensing geometry changes after a model is trained? Every model trained
  against the old arrangement becomes meaningless, which feature 005 already recorded as the
  consequence of adopting a swept configuration.

## Requirements *(mandatory)*

### Functional Requirements

**The learned agent**

- **FR-001**: The learned agent MUST observe exactly what the existing sensing already produces,
  being the 13 normalised ray distances plus the 6 self-state values, in the order the design
  declares. A learned driver that sees more than the scripted one is not comparable to it
- **FR-002**: The learned agent MUST NOT read the track file, checkpoint positions, its own
  position on the track, or any other information the scripted driver is denied
- **FR-003**: The learned agent MUST act through the same two continuous controls the vehicle
  already accepts, and MUST NOT gain a control the other drivers do not have
- **FR-004**: The observation and action shapes the trainer is configured with MUST agree with
  what the scene produces, and that agreement MUST be checked rather than assumed, since a silent
  mismatch trains a policy against noise
- **FR-005**: The existing sensing component MUST keep working unchanged for the scripted driver
  and for human driving. This feature wraps it, and does not replace it

**The reward**

- **FR-006**: The reward MUST implement the events and weights already decided in the design:
  progress through the next marker in the correct direction, a penalty for approaching a passed
  marker, a terminal penalty for wall contact, a per-step cost, a small payment for forward speed,
  and a penalty for steering changes above the threshold measured from the human dataset
- **FR-007**: Any change to a reward weight or to the set of reward events MUST be written into
  the design document before the run that uses it, and MUST be the only thing that run changes
- **FR-008**: Reward MUST be attributable during a run: it MUST be possible to say which events
  produced an episode's return, rather than only its total. A total that rises tells nobody which
  term did it
- **FR-009**: The wrong-direction rule MUST be scored using the detection the checkpoint ring
  already performs, and MUST NOT introduce a second, differently behaving definition of direction

**The episode**

- **FR-010**: Every episode MUST begin from a randomised legal start using the randomisation
  already fixed in the design, so that the agent cannot learn one approach to one corner
- **FR-011**: Every episode MUST end, and MUST end for exactly one recorded reason among wall
  contact, completing the required number of laps, going too long without reaching a new marker,
  and exceeding a total step limit. The last two are both time limits and both are truncations,
  but they answer different questions and a run that conflates them cannot say whether a policy
  was stuck or merely slow
- **FR-012**: Episodes MUST draw their track from the accepted training seeds, varying across the
  run, so that the policy is exposed to the same variety of tracks the scripted driver was
  measured on
- **FR-013**: The accepted evaluation seeds MUST NOT be used for training or for tuning, and it
  MUST be demonstrable from the recorded configuration that they were not

**Training**

- **FR-014**: The trainer configuration MUST live in the repository as a file, MUST be pinned, and
  MUST be the file the run actually used. A hyperparameter that exists only in a shell history is
  not reproducible
- **FR-015**: Training MUST run several copies of the environment in one session, because a policy
  that takes a weekend to train can be tuned once and a policy that takes a night can be tuned
  several times
- **FR-016**: Copies of the environment MUST be independent: one copy's episode, markers, reward
  and records MUST NOT be affected by another's
- **FR-017**: Every training run MUST have a unique identifier that ties the configuration, the
  recorded curves and the produced model together, and MUST be logged with what it changed and
  what happened, in the same session it was run
- **FR-018**: The recorded training curves MUST be kept as data in the repository's results area,
  not only in a local trainer directory that a fresh clone does not have
- **FR-019**: A training run MUST be resumable or explicitly restartable after an interruption,
  and which of the two it is MUST be stated

**Measuring**

- **FR-020**: The run-to-run spread MUST be measured by repeating one identical configuration at
  least three times, and MUST be reported before any two configurations are compared
- **FR-021**: Any claim that one configuration is better than another MUST state whether the
  difference exceeds that spread
- **FR-022**: The trained policy MUST be evaluated on the held-out seeds, and the evaluation MUST
  record, per seed, whether laps were completed, how many markers were awarded, the time taken,
  the number of wall contacts, and the reason the run ended
- **FR-023**: Evaluation MUST use the same per-run record shape and the same smoothness measure
  the scripted driver already produces, so the two columns are read from the same kind of file
- **FR-024**: The learned driver's steering MUST be summarised with the same descriptive
  statistics used for the human, imitation and scripted columns, and its comparison against the
  human distribution MUST use a statistical test rather than a visual impression

**Inference**

- **FR-025**: The trained policy MUST be exportable to a model file that drives the car in the
  simulation with no trainer process attached
- **FR-026**: The difference between the exported model's behaviour and the policy's behaviour at
  the end of training MUST be measured and stated, not assumed to be zero
- **FR-027**: The model file MUST be versioned in the repository through the binary path the
  project already uses for models, and MUST be identifiable to the run that produced it

**Scope boundaries**

- **FR-028**: This feature MUST NOT change the sensing geometry, the vehicle, the track generator,
  the barriers or the checkpoint logic. A change to any of them invalidates either a baseline
  already measured or a model already trained
- **FR-029**: This feature MUST NOT tune the scripted driver. It is the baseline this feature is
  measured against, and tuning it turns the comparison into two tuned systems
- **FR-030**: This feature MUST NOT feed images to the learned agent. The separation between the
  image dataset and the sensing the agent reads is the basis of the whole comparison

### Key Entities

- **Training area**: one independent copy of the environment inside a training session, carrying
  its own track, vehicle, markers and episode state
- **Episode**: one attempt, from a randomised start to one of the recorded terminal reasons,
  carrying its return and the events that produced it
- **Training run**: one execution of the trainer under one configuration, identified by a run
  identifier that ties together the configuration, the recorded curves, the log entry and the
  produced model
- **Policy artifact**: the exported model file that drives the car without a trainer, traceable to
  the run that produced it
- **Evaluation record**: one run of one policy on one held-out seed, in the same shape the
  scripted driver's run record already uses

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The trained policy completes 3 laps without wall contact in at least 95 percent of
  evaluation episodes, which is the criterion the design already states. If the criterion is not
  met, the rate actually achieved is reported as the finding and the gate is recorded as not met
  rather than restated to fit the result
- **SC-002**: The trained policy completes at least one lap on at least 80 percent of the held-out
  evaluation seeds, the same threshold the scripted driver was held to
- **SC-003**: The run-to-run spread is reported from at least three identical runs before any two
  configurations are compared, and every claimed improvement is stated against it
- **SC-004**: Every training run performed during this feature has a log entry naming its
  configuration change and its outcome, and a reader can go from a reported number to the run that
  produced it without reading code
- **SC-005**: The exported model drives the car in the simulation with no trainer attached, on a
  seed it never trained on, and the difference from training-time behaviour is stated as a number
- **SC-006**: A full training run finishes within a single night, under 12 hours on the project's
  machine, so that more than one configuration can be tried inside the milestone
- **SC-007**: The learned driver's lap completion and steering smoothness are reported beside the
  scripted driver's and the imitation model's, using the same measures, including the cases where
  the learned driver is worse
- **SC-008**: The evaluation seeds appear in no training configuration, demonstrable from the
  recorded configuration files alone


## Closeout (feature 006, 2026-08-24)

Every criterion with the number that decides it. Two are not met, and they are stated as not met
rather than restated to fit the result, which is what SC-001's own wording requires.

| criterion | verdict | the number |
|---|---|---|
| SC-001 | **NOT MET** | 0.0 per cent of evaluation episodes completed 3 laps without wall contact, against 95 per cent. No episode reached any of the 24 checkpoints |
| SC-002 | **NOT MET** | 0.0 per cent of the 10 held-out seeds saw one lap, against 80 per cent |
| SC-003 | met | Spread reported from three identical runs before any comparison: sd 0.0924, gate 0.19. T047 preceded T048, and all three tuning candidates are stated against that gate |
| SC-004 | met | Nine runs, each with an `EXPERIMENTS.md` row naming its one change and its outcome; `rl_steering.md` resolves every figure to run id, config, curve, model, rows, traces and scene |
| SC-005 | met | The exported model drove 10 held-out seeds with no trainer attached (`Couldn't connect to trainer on port 5004. Will perform inference instead.`), and the training-to-export difference is a number: steering variance 0.00055 deterministic against 0.04557 sampling, a factor of 83 |
| SC-006 | met | 5M in 2.0 hours, 2M in 42 to 52 minutes, against the 12-hour envelope |
| SC-007 | met | `results/rl/rl_steering.md` puts lap completion and both smoothness measures beside the scripted and human columns, and names the losses: 0 of 10 laps against 34 of 34, and the steering-variance coincidence |
| SC-008 | met | `SweepRunner` reads the eval half of `results/tracks/seed_split.json`; no training config names a seed, and `AreaScheduler` draws only from `SeedSplit.TrainSeeds()`. The eval sweep logs a warning naming R5 whenever it touches the held-out half |

**What this feature could not reach, and why.** SC-001 and SC-002 both depend on the policy driving,
and it never did. The cause is identified rather than left open: the reward table cannot be fixed by
scaling its weights. Three one-change candidates were run against a measured noise floor and none
cleared it in the better direction; the clearest doubled the payment for moving and bought twelve
per cent more speed. That is a policy which has not found the behaviour, not one underpaid for it,
so the remedy is exploration - a curriculum starting nearer a marker, a denser progress signal than
one marker in twenty-four, or a warm start from the M4 behavioural-cloning policy. Each is a design
change under Principle V and a new feature, not a Phase 5 tuning run. T050 is closed as
unsatisfiable at this reward table for the same reason.

**One measurement question is left open and is recorded rather than buried.** The trainer's
`episode_length` (~530) and the number of times the step term is actually charged
(`reward/step` over `StepCost`, ~1676) disagree by about 3.16x, and the ratio is not constant
(1.95 to 4.01 across summaries). The reward analysis does not depend on it, because the step and
speed terms accrue at the same call site and their ratio is unaffected, but any statement about
episode length **in seconds** does. It belongs to the FR-008 family and is noted under T050.

## Assumptions

- The sensing, the vehicle, the checkpoint ring, the start placement and the track loading all
  exist and are verified from features 003 and 005. This feature adds no sensing and no geometry.
- The accepted seeds are already split into 34 training and 10 evaluation seeds, disjoint, and
  that split is the one this feature uses.
- The toolchain is the verified one: Unity 6000.5.3f1 with `com.unity.ml-agents` 4.0.3 against
  `mlagents` 1.1.0 in the separate training environment, communicating over API 1.5.0. The
  training environment stays separate from the analysis environment, as the constitution requires.
- Training happens on the project's RTX 3050. Throughput targets are set against that machine and
  are stated rather than implied.
- The keyboard lap gate is already satisfied: feature 003 recorded hand-driven laps on five
  accepted seeds, so training is permitted to start.
- The scripted driver's results and the imitation model's results are already recorded, so this
  feature compares against numbers that exist rather than producing both sides of a comparison.
- The reward weights in the design are a starting point, explicitly labelled as such, and changing
  them is expected work rather than a deviation.
- Reinforcement learning is expected to be noisier between identical runs than anything measured
  so far in this project, which is why the spread is measured before anything is compared.

## Dependencies

- Feature 003 supplies the scene, the vehicle, the sensing, the checkpoint ring, the start
  randomisation and the accepted seed split.
- Feature 005 supplies the baseline this feature is measured against, the per-run record shape,
  the smoothness measure and the reporting code that turns traces into a column.
- Feature 004 supplies the imitation column and the pattern for measuring a reproduction spread
  before attributing a difference to a change.
- `DESIGN.md` sections 4.5 and 5 supply the reward table, the training configuration outline and
  the success criterion. Any change to them is a design commit that precedes the code.
- The final comparison milestone consumes this feature's evaluation output as the learned column.

## Out of Scope

- Changing the sensing arrangement. Feature 005 measured the alternatives and deliberately did not
  adopt one, precisely because adopting it would invalidate models trained against the current
  arrangement, which is what this feature produces.
- Tuning the scripted driver, for the same reason feature 005 refused to: a tuned baseline stops
  being a baseline.
- Any learning algorithm other than PPO. The tool is assignment-locked and the design names PPO.
- Feeding camera images to the learned agent. That path belongs to the imitation model and keeping
  them separate is what the comparison rests on.
- Curriculum learning, or any staged increase in difficulty beyond drawing episodes from the
  training seeds. If the measured result argues for it, that is an amendment, not a silent
  addition.
- Assembling the final comparison document. This feature produces its column in the shape the
  other columns already use; putting them side by side belongs to the last milestone.
