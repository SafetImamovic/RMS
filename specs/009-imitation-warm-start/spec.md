# Feature Specification: The imitation warm start

**Feature branch**: `009-imitation-warm-start`
**Created**: 2026-08-27
**Status**: specced, no code
**Input**: Three reward-side interventions later the policy still cannot finish a lap on unseen
track, and the one expert this project owns has never been shown to it.

## Why this feature exists

M3 has now spent three features on the reward table and the milestone has not moved.

| feature | one change | markers per episode | held-out laps |
|---|---|---|---|
| 006 `ppo_car_wall_lo` | wall **penalty** -5.0 to -1.0 | worse | 0 of 10 |
| 007 `ppo_car_007_progress` | dense progress term added | 0.2490 to **1.4987** | 0 of 10 |
| 008 `ppo_car_008_budget` | wall **terminal** lifted to a budget of 3 | 1.4987 to **0.5297** | not measured |

**Two of the three exonerated the thing they changed.** The wall penalty is not what caps this
policy, and neither is the wall terminal; 008 showed the terminal was load bearing in the direction
opposite to its own hypothesis, because lifting it returned the policy to stalling. The third,
feature 007's dense progress term, is the only change in M3 that moved the metric it was aimed at,
and it produced eight three-lap episodes in training and **not one lap on held-out track**.

**M3's closeout named three remedies and this is the last one standing.** DESIGN 4.5 records them:
a curriculum starting nearer a marker, a denser progress signal, or a warm start from the BC policy
M4 produces. Feature 007 took the second. This feature takes the third, and it has to change it
first, for a reason nobody noticed when the sentence was written.

**The BC policy cannot warm start this agent, and the reason is the observation.** The BC pipeline
in DESIGN 6 trains a CNN on the Kaggle dataset's **camera images**. `DrivingAgent` reads a **19
value vector** built from a 13 ray fan plus speeds and heading dots. The two policies share no input
space, so there is no weight in the BC network that means anything to the agent, and no
demonstration in the dataset that the agent could be shown. The remedy as written in DESIGN 4.5 is
unavailable, and that is worth saying plainly rather than quietly substituting something else for
it.

**The project does own an expert in the agent's own observation space.** `HeuristicDriver`, feature
005, reads the **same 19 values** through the same `CarAgent` fan, writes to the same
`CarController`, and completes **34 of 34 training seeds** with 0 wall contacts on seed 1. It is the
only driver in this project that finishes laps on demand, and in nine RL features it has never once
been used as anything but a reference column in a results table.

**The hypothesis this feature tests, stated so it can fail.** The policy's problem is not what the
reward pays for but that it never encounters the behaviour the reward would pay for. Three tuned
reward tables have not produced a lap on unseen track; an expert trajectory set in the agent's own
observation space shows the policy the behaviour directly, and the reward table then has something
to reinforce rather than something to discover. **If a run conditioned on expert demonstrations
still completes no held-out lap, then the limit is not exploration and not the reward**, and the
remaining candidates are the observation's content, the policy class and the vehicle. That is a
publishable answer and it retires the whole reward-side line of attack.

**One change, and it is deliberately the smaller of two.** The trainer gains
`behavioral_cloning` with a demonstration file. It does **not** gain GAIL. GAIL adds a learned
reward signal, which changes the reward table that DESIGN 4.5 pins and makes cumulative reward
incomparable to every run in M3. Behavioural cloning is an auxiliary loss on the policy and leaves
the reward table untouched, so a moved number stays attributable and the curves stay readable
against 007 and 008. GAIL is named in Out of Scope as the follow-up it is.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The scripted driver drives through the agent (Priority: P1)

`DrivingAgent` in heuristic mode produces the scripted driver's commands, so ML-Agents can record
what the expert observed and what it did, in the agent's own observation and action space.

**Why this priority**: it is the mechanism. Without it there is no demonstration file and nothing
else in this feature is measurable.

**Independent test**: with the behaviour type set to heuristic, drive one training seed and confirm
the car follows the track under the agent's action path rather than sitting still, and that the
recorder writes a `.demo` file that loads.

**Acceptance**:

1. `DrivingAgent.Heuristic` emits the scripted driver's `(steer, throttle)` rather than zeros.
2. The command is **delegated, not duplicated**: exactly one implementation of the baseline
   controller exists in the project and both paths call it.
3. Exactly one component writes `CarController.ScriptedMove` at a time, as feature 005's FR-004
   requires. The scripted driver is disengaged while the agent is the decision source.
4. A recorded `.demo` file opens in the editor and reports a non-zero episode and step count.

### User Story 2 - The demonstrations are of a driver that drives (Priority: P1)

The recorded set is expert behaviour, measured, rather than assumed to be expert because of who
produced it.

**Why this priority**: the whole feature is worth nothing if the demonstrations are of a car that
crashes. The 34 of 34 figure was measured at the heuristic's own 50 Hz cadence, and the agent
decides every fourth physics step.

**Independent test**: run the scripted driver through the agent's action path on N training seeds
and record lap completion, markers and wall contacts, against feature 005's own figures.

**Acceptance**:

1. Lap completion of the demonstration source is measured **at the agent's decision cadence** and
   reported next to feature 005's 34 of 34.
2. The demonstration set is drawn from **training seeds only**, and the seed list is committed.
3. Episode count, step count and file size of the `.demo` are recorded.

### User Story 3 - The warm-started policy reaches more markers (Priority: P1)

A PPO run with the behavioural cloning loss reaches more markers per episode than feature 007's
candidate.

**Why this priority**: it is the comparison the feature exists to make, against a gate fixed before
the run.

**Independent test**: one full-budget run, one change from `ppo_car_007_progress`, read against
1.4987 and the gate.

**Acceptance**:

1. Markers per episode is read against **1.4987** and the **0.035** gate, with the gate's caveat
   named in the same breath.
2. The end-reason mix is reported, and any fall in the wall share is checked against a rise in the
   stall share rather than read alone, which is the trap 008 fell into and named.
3. Cumulative reward is reported as **comparable** to 007 and 008, and the claim is backed by the
   reward table being unchanged rather than asserted.

### User Story 4 - A lap on held-out track (Priority: P1)

The exported model completes at least one lap on the ten held-out seeds.

**Why this priority**: it is M3's milestone and the reason the previous three features are recorded
as not enough.

**Independent test**: the standard sweep, ten held-out seeds, deterministic and sampling reported
separately.

**Acceptance**:

1. Lap completion per seed, in both inference modes, never averaged across them.
2. The 80 per cent bar recorded met or not met with its number.
3. `lapsToComplete` is 3, so a recorded lap is three laps, stated wherever the number appears.

### Edge Cases

- **The decision cadence may cost the expert its laps.** `DecisionPeriod` is 4 with
  `TakeActionsBetweenDecisions: 1`, so a demonstration is the heuristic sampled every fourth
  physics step with the command held between. The 34 of 34 figure does not carry over
  automatically. **This is a gate: it is measured before any demonstration is recorded in bulk**,
  and if lap completion collapses, the feature stops and reports that rather than lowering
  `DecisionPeriod`, which would change the cadence every M3 comparison was measured at.
- **Demonstrations from held-out seeds would contaminate the milestone.** The held-out lap is the
  criterion this project has failed three times; showing the policy expert trajectories on those
  exact tracks would answer a different question. Training seeds only, and the list is committed.
- **Two writers to `ScriptedMove`.** `HeuristicDriver.FixedUpdate` and
  `DrivingAgent.OnActionReceived` both write it. Feature 005's FR-004 already forbids two sources
  of control; this feature must respect it rather than rediscover it.
- **The behavioural cloning loss may simply be overridden by PPO.** `steps` decays the BC loss;
  a value that is too small means the warm start washes out before the policy can use it, and one
  that is too large means the run measures imitation rather than reinforcement. The value is chosen
  before the run and recorded, not tuned after seeing the result.
- **A policy that imitates perfectly is still not a policy that generalises.** Matching the expert
  on training seeds and failing on held-out seeds is a real possible outcome, and it is the finding
  if it happens rather than a reason to retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `DrivingAgent.Heuristic` MUST produce the scripted driver's command by **calling the
  existing implementation**, not by reimplementing it. The current XML comment rejecting a
  duplicate stays true and is the reason for the design.
- **FR-002**: Exactly one component MUST write `CarController.ScriptedMove` in any frame.
- **FR-003**: The demonstration set MUST be recorded from training seeds only, and the seed list
  MUST be committed with it.
- **FR-004**: The lap completion of the demonstration source MUST be measured at the agent's
  decision cadence before demonstrations are recorded in bulk, and the feature stops if it
  collapses.
- **FR-005**: The reward table MUST be unchanged. No reward signal is added, `behavioral_cloning`
  is the only trainer change, and cumulative reward stays comparable to 007 and 008.
- **FR-006**: `DecisionPeriod` MUST NOT change in this feature.
- **FR-007**: The `.demo` file MUST be committed or its provenance MUST be reproducible from a
  committed seed list and a committed recording procedure, whichever the LFS rules make honest.
- **FR-008**: The candidate run MUST differ from `ppo_car_007_progress` by the behavioural cloning
  block alone, and MUST have its own `results/EXPERIMENTS.md` row naming that one change.
- **FR-009**: Both the demonstration measurement and the run MUST report Unity-side behavioural
  counts, because feature 007's SC-007 reward-decomposition defect is still unfixed.
- **FR-010**: `wallContactBudget` MUST stay 0 and `MaxStep` MUST stay 6000, so the comparison is
  against feature 007's terminal behaviour with feature 008's step limit in place.

### Key Entities

- **Demonstration set**: a `.demo` file of expert trajectories in the agent's observation and
  action space, with a committed seed list and measured lap completion.
- **`behavioral_cloning`**: the trainer block carrying `demo_path`, `steps` and `strength`. Not a
  reward signal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The agent in heuristic mode drives the car, demonstrated in a scene rather than
  argued from the code.
- **SC-002**: One implementation of the baseline controller exists in the project after this
  feature, demonstrated by the call path.
- **SC-003**: Lap completion of the demonstration source at the agent's decision cadence is
  reported next to feature 005's 34 of 34.
- **SC-004**: The demonstration set's seeds are listed and every one is a training seed.
- **SC-005**: Markers per episode is read against 1.4987 and against the 0.035 gate.
- **SC-006**: The end-reason mix is reported, with the wall and stall shares read together.
- **SC-007**: At least one lap is completed on the ten held-out seeds, in either inference mode.
- **SC-008**: The 80 per cent milestone bar is recorded met or not met with its number.
- **SC-009**: Throughput is re-measured and reported against 903 and 927 steps per second.
- **SC-010**: Every run has an `EXPERIMENTS.md` row naming its one change.
- **SC-011**: The reward table is shown unchanged, so the cumulative reward comparison to 007 and
  008 is backed rather than asserted.

## Assumptions

- **Feature 007's gate of 0.035 on markers per episode is reused a third time rather than
  re-measured**, with the caveat `results/rl/progress_spread.md` states: clearing it is credible,
  failing to clear it is weaker evidence than it looks, and a result landing near it earns a fresh
  three-run spread rather than a verdict.
- `mlagents` 1.1.0 supports `behavioral_cloning` with `demo_path`, `steps`, `strength`,
  `samples_per_update`, `num_epoch` and `batch_size`. Confirmed in the installed trainer's
  `settings.py`; the values this feature uses are chosen at planning time.
- The scripted driver's control law is deterministic given the observation, so a demonstration is
  reproducible from a seed list and the recording procedure.

## Dependencies

- Feature 005's `HeuristicDriver` and its 34 of 34 figure, which is the expert this feature uses.
- Feature 007's `ppo_car_007_progress`, the baseline every number here is read against, and
  `results/rl/progress_spread.md` for the gate.
- Feature 008 for the step limit that is now on the prefab and for the budget default of 0.

## Out of Scope

- **GAIL.** It adds a learned reward signal, which changes the reward table DESIGN 4.5 pins and
  makes cumulative reward incomparable to every M3 run. It is the obvious follow-up if behavioural
  cloning moves the metric and the milestone still does not fall.
- **The curriculum starting nearer a marker**, M3's remaining remedy, untouched here so that a
  moved number is attributable to one remedy.
- **Changing `DecisionPeriod`**, which would invalidate the cadence every M3 comparison was
  measured at.
- **The per-episode records debt** feature 007 named and 008 repeated. It blocks honest reading of
  the reward decomposition, not of the behavioural counts this feature rests on.
- **The reward table's weights.** Untouched, and the point of leaving them alone is that this
  feature's result is about exposure to expert behaviour rather than about pay.

## The closeout, with the number that decides each criterion

Written 2026-09-01, after the candidate run, the held-out evaluation and the three-seed spread.

**Which of `quickstart.md`'s two outcomes this landed on.** That file named both in advance: a
held-out lap means the limit was exploration and not the reward table, which retroactively explains
three reward-side features that moved nothing; no held-out lap means the limit is neither, and the
reward-side line is retired anyway. **This landed on the first**, and more completely than the
sentence anticipated: not one lap on one seed but ten of ten on three seeds.

| criterion | number | outcome |
|---|---|---|
| SC-005, markers per episode against 1.4987, gate 0.035 | 2.6321, a rise of 1.1334 | met, gate cleared about thirtyfold |
| SC-006, end-reason mix read whole | wall 57.10 from 59.07, stall 24.90 from 27.41 | met, both shares fell |
| SC-007, at least one held-out lap in either mode | 59 of 60 evaluation runs completed three laps | met |
| SC-008, the 80 per cent bar with its number | 100 per cent deterministic on each of three seeds | met |
| SC-009, throughput against 903 and 927 | 687 steps per second | met, reported with its two causes split |
| SC-010, every run has a row naming its one change | six rows in `EXPERIMENTS.md` | met |
| SC-011, reward table shown unchanged | `git diff be2f9c4..HEAD` over `Assets/Scripts/` holds no reward-bearing line | met |

**What the warm start changed.** It moved the milestone without touching a weight. Markers per
episode 1.4987 to 2.6321, cumulative reward negative to positive for the first time in the project,
held-out laps 0 of 10 to 10 of 10, and a learning curve that is monotone where the previous three
were not. The policy also ends up **faster than the expert it imitated**, 20.808 s per lap against
26.266 s, which is the behaviour an auxiliary-loss BC allows and a pure imitation would not.

**What it did not change.** It did not touch the reward table, by design, which is what keeps the
comparison to 007 and 008 valid. It did not fit the demonstration closely: `Losses/Pretraining Loss`
drifted about eleven per cent over its 500,000 steps rather than descending, so the gain is not from
a tight fit to the expert. It did not establish generalisation beyond the ten held-out tracks of one
generator. And it did not, on its own, separate the sensing fix from the warm start: the 1M sighted
probe argues the fix alone does not explain the result, but the 5M version that would settle it was
not run.

**One thing the spread produced that the feature did not set out to find.** Whole-run training
aggregates ranked the three seeds backwards against their held-out result, while end-of-run measures
ranked them correctly. Recorded with n=3 stated, in `EXPERIMENTS.md` and in `DESIGN.md` 5.2.
