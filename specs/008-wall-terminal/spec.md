# Feature Specification: The wall terminal

**Feature branch**: `008-wall-terminal`
**Created**: 2026-08-26
**Status**: specced, no code
**Input**: The wall terminal ends an episode on first contact, so a policy that now drives never
experiences a recovery.

## Why this feature exists

Feature 007 changed which failure the policy has, and this feature asks about the new one.

The dense progress reward worked on its own terms. Markers per episode went **0.2490 to 1.4987**
against a gate of 0.035, the rise was monotonic across quarters, and **eight episodes drove the full
three-lap requirement** where M3 had never completed a single lap in nine runs and more than
12,000,000 steps. On the ten held-out seeds it still completed **zero** laps, so SC-005 and SC-006
were not met and the M3 milestone bar stands unmet.

**What the held-out rows say is unusually specific.** All ten seeds end in `WallContact`, after
about **6.20 of 24 markers** and roughly **seven seconds**. Not one stalled, not one ran out of
time. In training the same shift appears: the wall share rose **47.7 to 59.1 per cent** while the
stall share fell **39.0 to 27.4 per cent**. The car drives, gets a quarter of the way round, and
hits a barrier.

**The mechanism is one branch in `DrivingAgent.CheckTermination`.** The first new wall contact calls
`Finish(EndReason.WallContact)`, so an episode ends on the policy's first mistake. That was
harmless while the policy sat still and never touched a barrier, which is exactly what feature 006
measured: its held-out runs recorded **zero wall contacts** and stalled at the 60 second cap. It
stopped being harmless the moment the car started moving.

**The hypothesis this feature tests, stated so it can fail.** A policy cannot learn to recover from
a mistake it is never allowed to survive. If the episode ends at the first contact, every trajectory
in the buffer that touches a barrier ends there, and the value function has no data about what
follows a graze. Lifting the terminal gives the policy the second half of those trajectories.

**This is not feature 006's `ppo_car_wall_lo`, and the difference is the point.** That run changed
the wall **penalty**, -5.0 to -1.0, and made the return measurably worse while shifting the failure
mix by about 4.5 points. It is evidence about the weight and says nothing about the termination,
because the episode still ended at the first contact in both arms. This feature holds the penalty
at its pinned value and changes only whether the episode continues.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The car survives a graze (Priority: P1)

A policy that touches a barrier and steers away continues its episode, is charged for the contact,
and can go on to reach further markers.

**Why this priority**: it is the mechanism. Nothing else in this feature is measurable until an
episode can outlive a contact.

**Independent test**: an EditMode test drives a synthetic trajectory into a contact and past it, and
asserts the episode is still live and the penalty was charged exactly once.

**Acceptance**:

1. A single contact charges the pinned wall penalty once and does not end the episode.
2. A car held against a barrier is charged once per contact event rather than once per physics step.
3. When the contact budget is exhausted, the episode ends with `EndReason.WallContact` exactly as
   it does today, so the end-reason vocabulary does not change.

### User Story 2 - The policy reaches more markers (Priority: P1)

Training with the lifted terminal reaches more markers per episode than feature 007's candidate.

**Why this priority**: it is the number that says whether surviving contacts is worth anything.

**Independent test**: markers per episode against feature 007's **1.4987**, judged against a gate.

**Acceptance**:

1. Markers per episode is read against 1.4987 and against the gate, and reported either way.
2. Wall contacts per episode is reported beside it, because the two must be read together.
3. The end-reason mix is reported, since a fall in `WallContact` that becomes a rise in `Stalled` is
   a traded failure and not a fixed one, the same check SC-003 forced in feature 007.

### User Story 3 - A lap on held-out track (Priority: P1)

The exported model completes at least one lap on the ten held-out seeds.

**Why this priority**: it is the M3 milestone and the thing this project has never done.

**Independent test**: the evaluation sweep, both inference modes, no trainer attached.

**Acceptance**:

1. Lap completion per seed is recorded for both inference modes.
2. The 80 per cent milestone bar is recorded met or not met with the number that decides it.
3. `lapsToComplete` is 3 in `Evaluation.unity`, so a recorded lap is three laps. The figure is
   reported with that stated rather than left to be discovered.

### Edge Cases

- **The car comes to rest against a barrier and cannot reverse out.** Then the contact budget buys
  nothing and the episode runs to the stall timeout instead, trading a wall ending for a stalled one
  at a cost of 60 seconds of wall clock per episode. This must be measured before the budget is
  chosen, not assumed.
- **A policy learns to grind along a barrier.** The progress term pays for arc position and does not
  care how the car got there, so sliding along a wall towards the next marker earns. Under the
  current terminal this is impossible because the first contact ends the episode; lifting it makes
  the strategy available. **This is the main risk the feature carries** and it needs a named check
  rather than a hope.
- **Contacts charged per step rather than per contact.** `WallSensor.TakeNewContact` is edge
  triggered today, and it has to stay that way, or a resting car pays the terminal penalty at 50 Hz.
- **Episodes get much longer.** Surviving contacts raises episode length, which lowers episodes per
  summary and interacts with the episode-set mismatch feature 007 measured. Throughput must be
  re-measured rather than assumed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A wall contact MUST charge the pinned penalty once per contact event.
- **FR-002**: The episode MUST NOT end on a contact until a configured budget is exhausted.
- **FR-003**: The budget MUST be a serialized field with its default recorded in `DESIGN.md`, and it
  MUST be expressible as "terminate on first contact" so the feature 007 behaviour remains
  reachable for comparison.
- **FR-004**: When the budget is exhausted the episode MUST end with `EndReason.WallContact`, so no
  downstream reader learns a new end reason.
- **FR-005**: Wall contacts per episode MUST be reported to the trainer as a new statistic and
  exported, because markers per episode cannot be read without it.
- **FR-006**: The wall penalty weight MUST NOT change in this feature. One change per run.
- **FR-007**: The six other reward terms, their weights, their firing conditions and their stats
  keys MUST NOT change.
- **FR-008**: The scripted, keyboard and heuristic driving paths MUST be unaffected.
- **FR-009**: Any run comparing against feature 007 MUST name the gate it is judged against, and
  MUST NOT quote the 0.19 gate from feature 006, which was retired in feature 007 and measured on a
  different reward table.
- **FR-010**: The wall-grinding risk MUST be checked with a stated measurement, not argued away.

### Key Entities

- **Contact budget**: how many contact events an episode survives before ending. Zero reproduces
  feature 007.
- **`WallContactsPerEpisode`**: the count of charged contact events at episode end.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single contact charges the penalty exactly once and leaves the episode live,
  demonstrated in EditMode.
- **SC-002**: A car resting against a barrier is charged once, not once per physics step.
- **SC-003**: Markers per episode is read against feature 007's 1.4987 and against a stated gate.
- **SC-004**: Wall contacts per episode is reported for every run of this feature.
- **SC-005**: The end-reason mix is reported, and any fall in the wall share is checked against a
  rise in the stall share rather than read alone.
- **SC-006**: At least one lap is completed on the ten held-out seeds, in either inference mode.
- **SC-007**: The 80 per cent milestone bar is recorded met or not met with its number.
- **SC-008**: The wall-grinding check is reported with a number, whichever way it comes out.
- **SC-009**: Throughput is re-measured and reported, since episodes are expected to lengthen.
- **SC-010**: Every run has an `EXPERIMENTS.md` row naming its one change.

## Assumptions

- **Feature 007's gate of 0.035 on markers per episode is reused rather than re-measured**, and the
  caveat `results/rl/progress_spread.md` already states applies: clearing it is credible, failing to
  clear it is weaker evidence than it looks, and a result landing near it earns a fresh spread
  rather than a verdict. Re-measuring costs three runs and about 2.4 hours, and is the first thing
  to spend if the result is ambiguous.
- The reward table is unchanged, so cumulative reward is comparable to feature 007's candidate.
  It is still not comparable to feature 006's, for the reason FR-018 of that feature gives.
- The car is physically able to reverse away from a barrier. This is an assumption and Edge Cases
  requires it be measured.

## Dependencies

- Feature 007, merged to `develop` at `b73b2d6`. Its candidate `ppo_car_007_progress` is the
  baseline every number here is read against.
- `results/rl/progress_spread.md` for the gate and its caveats.

## Out of Scope

- **The wall penalty's weight.** Tested in feature 006 and deliberately untouched here, so that a
  moved number is attributable to the terminal alone.
- **The two remedies M3 named and feature 007 left open**, a curriculum starting nearer a marker and
  an imitation warm start. Both were aimed at exploration, which is the part feature 007 moved, and
  they should be re-argued against the constraint this feature finds rather than picked up in the
  order M3 wrote them.
- **Per-episode records**, which feature 007 named as the way to close its SC-007 accounting defect.
  Independent of this feature and worth its own.
