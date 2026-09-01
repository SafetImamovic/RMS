# Feature Specification: Dense Progress Reward

**Feature Branch**: `007-dense-progress-reward`
**Created**: 2026-08-25
**Status**: Draft
**Input**: User description: "Dense per-step progress reward toward the next checkpoint marker, replacing the sparse 1-in-24 checkpoint signal as the exploration fix for M3."

## Why this feature exists

Feature 006 closed M3 on a negative result, and the result was not "the numbers were bad". It was
a cause. SC-001 measured 0.0 per cent against 95, SC-002 measured 0.0 per cent against 80, and no
evaluation episode reached even one of the 24 markers on any of the 10 held-out seeds. Nine
training runs, one of them 5,000,000 steps, never completed a lap.

The reason is written down and was tested rather than assumed. Three one-change candidates were run
against a measured noise floor of sample sd 0.0924 with a gate of 0.19, and none of them cleared it
in the better direction. The decisive one doubled `SpeedReward` and bought twelve per cent more
speed: a factor of two in pay for a factor of 1.12 in behaviour. A policy that is paid double for
moving and moves twelve per cent more has not been underpaid. It has not found the thing that pays.

So the problem is exploration, and this feature attacks the specific shape of it. Under the M3
table the only reward that says "you are getting somewhere" is +1.0, awarded 24 times per lap, at
markers roughly 8.43 m apart on a track of about 200 m. Across nine runs the policy earned an
average of 0.249 of those per episode. A gradient the agent sees once in a few hundred steps, if at
all, is not a gradient it can climb. Every other term in the table is either a cost of being alive
or a penalty for dying, and both of those are minimised by driving less. That is exactly what the
policy learned: wall share fell from 60.1 per cent to 45.2 per cent while checkpoint reward fell
from 0.394 to 0.245. Driving less is the cheaper way to stop paying -5.0, and nothing in the table
preferred the other one.

**This feature makes progress payable on every step instead of at 24 points on the track.** The car
is told, continuously, whether it moved nearer the finish of the lap or further from it.

**The shaping is potential-based, and that is the whole design, not an implementation detail.** The
new term is the change in a potential function between consecutive steps, where the potential is
the negated distance still to be driven along the marker chain to complete the lap. Written that
way the term telescopes: any path that starts and ends in the same place earns exactly zero from
it, whatever it did in between. That property is what lets this feature add a dense signal without
reopening the question DESIGN 4.5 already settled. The table carries an explicit anti-farming
invariant, that driving in circles on open ground must never earn what a lap through the markers
earns, and a naive "pay for closing the gap to the next marker" term would break it in one line by
paying for a car that oscillates toward a marker and away again. A potential-based term cannot,
because that loop sums to zero by construction. The invariant is preserved by the shape of the
term rather than by a weight chosen carefully enough.

The same property answers the other objection, which is that a dense reward can change what the
optimal policy is and quietly turn M3 into a different problem. Potential-based shaping is the one
form of shaping that provably does not: it changes which behaviours are easy to discover, not
which behaviour is best. That is the claim this feature is making, and it is a claim the tests can
check by summation rather than by argument.

**This feature is a design change under Principle V, so DESIGN 4.5 is rewritten before any code.**
That includes the term's weight, which is not to be picked. It has to be derived from the measured
lap length and stated against the 24.0 a lap already pays, the same way `SpeedReward` was derived
against the 6000-step episode ceiling and not chosen for looking round.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The car is told whether it is getting anywhere (Priority: P1)

Someone drives a lap with the scripted driver, with the reward instrumentation running, and reads
the per-term breakdown afterwards. The progress term is nonzero on almost every step, positive
while the car advances along the track and negative while it backs up, and its total over the
completed lap is a number that can be predicted from the track geometry before the lap is driven.

**Why this priority**: nothing else in this feature can be trusted until the term is known to
measure what it claims to measure. The scripted driver completes 34 of 34 training seeds, so it is
the only driver in the project that can exercise a full lap of the term on demand, and it makes
the term checkable without a training run.

**Independent Test**: drive one lap with the scripted driver on a fixed seed, sum the progress term
over the episode, and compare it against the potential difference between the start state and the
lap-completion state. The two must agree to within the tolerance the spec fixes. This delivers
value on its own: it is the evidence that the term is a potential difference and not an
accumulator with a bug in it.

**Acceptance Scenarios**:

1. **Given** a completed lap by the scripted driver, **When** the progress term is summed over the
   episode, **Then** the sum equals the difference in potential between the first and last step,
   which for a full lap is the lap's driving distance times the weight
2. **Given** any episode at all, **When** the car passes a marker, **Then** the progress term shows
   no jump at that step beyond what the car's own movement in that step accounts for
3. **Given** any episode at all, **When** the car drives backwards along the track, **Then** the
   progress term is negative over that stretch and equal in magnitude to what driving the same
   stretch forwards would have paid
4. **Given** a closed loop that returns the car to a state it already occupied, **When** the
   progress term is summed over the loop, **Then** the sum is zero to within the fixed tolerance

---

### User Story 2 - A policy that reaches markers (Priority: P1)

Someone starts a training run with the new reward table and watches the number of markers the
policy earns per episode. It rises off the floor. This is the story M3 could not tell: in nine runs
the mean was 0.249 markers out of the 24 a lap needs, and it went down over the longest run rather
than up.

**Why this priority**: this is the milestone. M3's exit criterion is a trained policy that drives,
and every criterion feature 006 failed failed for the same reason, which is that the policy never
reached a marker. Markers per episode is the metric that separates "the shaping worked" from "the
shaping was elegant".

**Independent Test**: train under the new table with no other change from the 006 baseline
configuration and compare markers earned per episode against the 006 baseline, judged against a
noise floor measured on this metric from identical repeated runs, not against the single number
0.249.

**Acceptance Scenarios**:

1. **Given** a training run under the new table, **When** markers earned per episode is read at the
   end of the run, **Then** it exceeds the 006 baseline by more than the measured noise floor for
   that metric
2. **Given** a training run under the new table, **When** the run's end-reason counts are read,
   **Then** the share of episodes ending stalled has fallen relative to the 006 baseline rather
   than the wall share having simply risen to replace it
3. **Given** the full training run, **When** the lap counter is read, **Then** at least one
   episode in the run completed a lap, which no run in M3 ever did
4. **Given** two runs that differ only in this reward change, **When** their cumulative reward
   curves are compared, **Then** the comparison is refused as meaningless and the behavioural
   metrics are compared instead, because adding a term changes the scale of the total

---

### User Story 3 - The exported model drives held-out track (Priority: P1)

Someone takes the model the run produced, opens the evaluation scene, and runs the ten held-out
seeds with no trainer attached. The car drives. Laps are counted, and the number that comes out is
the M3 column of the final comparison, whatever it says.

**Why this priority**: it is the milestone gate's literal wording, and it is where feature 006 read
0.0 per cent twice. It is separated from User Story 2 because a policy that earns markers in
training and a policy that completes laps in inference are not the same claim, and 006 measured a
factor of 83 between the training and export policies on steering variance.

**Independent Test**: run the existing evaluation sweep on the ten held-out seeds against the new
model and read lap completion, with the sweep's existing warning that it is touching the held-out
half.

**Acceptance Scenarios**:

1. **Given** the exported model and the evaluation scene, **When** the ten held-out seeds are
   driven, **Then** lap completion is recorded per seed and reported whether or not it clears the
   milestone bar
2. **Given** the evaluation run, **When** both inference modes are used, **Then** deterministic and
   sampling results are reported separately, because 006 showed they are not interchangeable
3. **Given** the recorded results, **When** the RL column of the comparison is written, **Then** it
   sits beside the scripted driver's 34 of 34 and the human reference, and names any loss rather
   than omitting it

---

### User Story 4 - The step accounting is settled (Priority: P2)

Someone asks how long an episode lasts in seconds and gets an answer that two independent counts
agree on.

**Why this priority**: feature 006 closed with this open and said so. The trainer's
`episode_length` reads about 530 while the number of times the step cost is actually charged reads
about 1676, a factor of about 3.16 that is not constant, ranging from 1.95 to 4.01 across
summaries. The reward analysis in 006 did not depend on it, because the step and speed terms accrue
at the same call site and their ratio is unaffected. **This feature's term accrues at that same
call site and its total over a lap is the quantity User Story 1 predicts from geometry**, so the
discrepancy stops being harmless: if the term is charged more often than the agent takes decisions,
the predicted total and the measured total will disagree and the cause will be ambiguous between
this and a real bug.

**Independent Test**: instrument both counts in one run and report either the resolved explanation
or the measured relationship, with the per-lap prediction from User Story 1 stated against whichever
count is the correct denominator.

**Acceptance Scenarios**:

1. **Given** a training run, **When** the trainer's episode length and the count of reward charges
   are both read, **Then** either they agree, or the ratio between them is explained by a named
   mechanism rather than reported as a discrepancy
2. **Given** the explanation, **When** any statement about episode duration in seconds is made in
   the results, **Then** it names which count it is derived from

---

### Edge Cases

- **The first step of an episode.** The potential has no previous value to difference against.
  Charging one is a large spurious reward or penalty on step zero of every episode, which is the
  most repeated event in training and therefore the worst place to have a bug. The first step of an
  episode must charge zero progress.
- **Lap rollover.** When the car crosses the finish, the distance remaining to complete the lap
  drops to zero and then, if the episode continues, jumps back to a full lap. Differenced naively
  that is a single step paying the entire lap's penalty. The potential must be defined so this
  cannot happen, or the step must be excluded, and which of the two is chosen must be stated.
- **Randomised start.** Episodes begin at a random marker with up to 1.5 m of lateral offset and 10
  degrees of yaw, and the ring counts the marker the car stands on as already taken. The lap's
  total remaining distance therefore differs between episodes, so the per-lap total that User Story
  1 predicts is a function of the start index and not one constant.
- **Training-area swap.** Feature 006 found that `TrainingArea.SwapTo` ended episodes by a path that
  never reached the reward reporting, so about one episode in six was counted by the trainer and
  never by the breakdown. A swap must not leave a stale previous potential behind for the next
  episode on that area to difference against.
- **Skipped markers.** The ring already reports contacts with markers that are not the one due. The
  potential is defined over distance along the chain, so a car that cuts across and rejoins further
  along would be paid for the shortcut by the shaping term even though the ring refuses to award
  the marker. The definition must not let the shortcut pay.
- **Wrong-way driving.** The wrong-way penalty already exists and fires after about 3.43 m of
  reversing. The progress term is negative over exactly that stretch, so reversing is now charged
  twice. That is intended, and the size of the combined charge has to be stated rather than
  discovered.
- **A car that is stuck against a wall but still commanded forward.** Progress is zero, the step
  cost still runs, and the speed term pays nothing. Nothing new breaks, but the stall end-reason
  becomes the dominant termination and its share is one of the numbers User Story 2 reads.
- **Numerical scale.** The term is a difference of two distances of order 100 m, taken every step,
  where the per-step movement is of order centimetres. Computing it as a difference of two large
  numbers in single precision is a real loss of significance at the top of the range.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `DESIGN.md` 4.5 MUST be rewritten to state the new reward table, the potential
  function, the derivation of the new term's weight, and the restated anti-farming invariant,
  before any code in this feature is written. This is the Principle V gate and it blocks every
  other requirement here.
- **FR-002**: The system MUST define a potential over the car's state equal to the negated distance
  remaining along the marker chain to complete the current lap, computed from the marker positions
  the checkpoint ring already exposes.
- **FR-003**: The progress term MUST be the difference of that potential between the previous step
  and the current step, and MUST NOT be any other function of distance, including a clamped,
  rectified, or one-sided one.
- **FR-004**: The progress term MUST be zero on the first step of every episode.
- **FR-005**: The progress term summed over any trajectory MUST equal the potential difference
  between that trajectory's endpoints, to within a stated tolerance, and this MUST be asserted by a
  test rather than argued in prose.
- **FR-006**: The term's weight MUST be derived from the measured lap distance and stated against
  the 24.0 that a lap of markers already pays, with the derivation written in `DESIGN.md` 4.5. A
  value chosen without a stated derivation is a defect in this feature, not a tuning decision.
- **FR-007**: The restated anti-farming invariant MUST hold and MUST be covered by a test: a
  trajectory that returns the car to a state it has already occupied earns zero from the progress
  term, so no amount of circling can earn what a lap earns.
- **FR-008**: The system MUST NOT pay the progress term for distance the checkpoint ring refuses to
  award, so a shortcut that skips markers MUST NOT be worth more than the path through them.
- **FR-009**: The reward breakdown MUST carry the progress term as its own named field, and the six
  existing terms MUST keep their names and meanings unchanged.
- **FR-010**: The per-term breakdown MUST continue to sum to the trainer's cumulative reward, and
  the check that it does MUST run against live data from this feature's own runs rather than being
  inherited from feature 006.
- **FR-011**: Episode reset, including the training-area swap path, MUST clear the stored previous
  potential, so no episode differences against a potential belonging to a different episode or a
  different track.
- **FR-012**: The lap rollover MUST NOT produce a single step charging a lap's worth of potential,
  and the mechanism that prevents it MUST be stated in the design rather than left to the reader of
  the code.
- **FR-013**: The potential MUST be computed in a way that does not lose the per-step movement to
  floating point cancellation at the far end of the lap.
- **FR-014**: The observation vector, the action space, the ray geometry of 13 rays over 180 degrees
  at 20 m, the vehicle profile, and the track generator MUST be unchanged by this feature, because
  all of them are shared with the M5 comparison and with features 004 and 005.
- **FR-015**: The scripted driver, keyboard driving, the heuristic driver and the behavioural
  cloning path MUST behave exactly as they do today when the learning agent is not driving.
- **FR-016**: The seed split MUST be respected unchanged: training draws only from the training
  half, and the evaluation sweep continues to warn when it touches the held-out half.
- **FR-017**: The run-to-run noise floor MUST be measured for the metrics this feature judges
  itself on, from identical repeated runs, and MUST be reported before any two configurations are
  compared.
- **FR-018**: Cumulative reward MUST NOT be compared across the 006 and 007 tables. Adding a term
  changes the scale of the total, which feature 006 established when a candidate read +0.3378 raw
  of which +0.2824 was bookkeeping. Comparisons across the two tables MUST use behavioural metrics.
- **FR-019**: Every training run MUST have a row in `results/EXPERIMENTS.md` naming its one change
  and its outcome, written in the same session as the run.
- **FR-020**: The trained model MUST be exported and MUST drive the ten held-out seeds in the
  evaluation scene with no trainer attached, in both deterministic and sampling inference, with the
  results recorded per seed.
- **FR-021**: The relationship between the trainer's episode length and the number of times a
  per-step reward term is charged MUST be measured and either explained or recorded with the ratio
  and its variability, and any statement of episode duration in seconds MUST name which count it
  came from.
- **FR-022**: The reward terms MUST remain pure functions that are testable without a running
  Unity scene, which is the property that made feature 006 testable at all.
- **FR-023**: `README.md`'s reproduction recipe MUST be updated in this feature if any command,
  scene, or configuration file name changes.

### Key Entities

- **Potential**: a scalar function of the car's position and lap progress, equal to the negated
  remaining distance along the marker chain to complete the lap. It is state, not reward, and it is
  the only new quantity this feature introduces.
- **Progress term**: the per-step reward equal to the weighted change in potential. One new named
  field in the existing reward breakdown.
- **Marker chain**: the existing ordered ring of 24 markers, roughly 8.43 m apart on a track of
  about 200 m. This feature reads it and does not change it.
- **Remaining distance**: the distance from the car to the next marker plus the sum of the gaps
  from that marker round to the lap's finish. It is what makes the potential monotone over a lap
  and free of a jump at each marker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Over a lap driven by the scripted driver, the summed progress term and the endpoint
  potential difference agree to within the tolerance the design fixes, on every seed tested.
- **SC-002**: A trajectory that returns to a previously occupied state earns zero from the progress
  term, to within the same tolerance.
- **SC-003**: Markers earned per episode at the end of a training run exceed the 006 baseline of
  0.249 by more than the noise floor measured for that metric on identical repeated runs.
- **SC-004**: At least one episode during training completes a lap. No run in M3 ever did, across
  nine runs and more than 12,000,000 steps.
- **SC-005**: On the ten held-out seeds in inference, at least one lap is completed. This is the
  criterion that separates a working mechanism from an elegant one, and it is stated separately
  from the milestone bar below so that a partial result is still reportable as a result.
- **SC-006**: On the ten held-out seeds, one lap is completed on 80 per cent of them, which is
  feature 006's SC-002 restated unchanged and is the M3 milestone bar. It is recorded met or not
  met with the number that decides it.
- **SC-007**: The per-term breakdown sums to the trainer's cumulative reward on the runs of this
  feature, checked against live exported data and reported as a percentage of rows that agree.
- **SC-008**: The run-to-run spread is reported before any two configurations are compared, and
  every comparative claim in this feature names it.
- **SC-009**: The keyboard, scripted, heuristic and behavioural cloning paths produce the same
  behaviour after this feature as before, demonstrated rather than asserted.
- **SC-010**: Training throughput stays inside the twelve-hour envelope, and the measured steps per
  second is reported so the envelope claim is checkable.
- **SC-011**: Every run has an `EXPERIMENTS.md` row naming its one change, and every figure in the
  results resolves to a run id, a configuration, a curve, a model and the rows behind it.
- **SC-012**: The relationship between trainer episode length and per-step reward charges is
  reported as either an explanation or a measured ratio with its range, closing the item feature 006
  left open.

### The closeout, with the number that decides each criterion

Written 2026-08-26, after every run this feature made.

| criterion | bar | measured | verdict |
|---|---|---|---|
| SC-001 sum equals endpoint difference | agree within tolerance | 3 laps on seed 1, each paying exactly 12.0; `Unwrapped` climbs 201.02 m per lap against a 201.017 m chain | **met** |
| SC-002 a loop earns zero | zero within tolerance | T013, green in the EditMode suite | **met** |
| SC-003 markers per episode | beat 0.249 by more than 0.035 | **1.4987** run mean, 2.6975 over the last 50 | **met**, by about 36 times the gate |
| SC-004 a lap during training | at least one, ever | **8 episodes completed three laps each**, over 13,851 episodes | **met**, and by more than the criterion asked |
| SC-005 a lap on held-out seeds | at least one | **0**, both inference modes, all ten seeds | **not met** |
| SC-006 the milestone bar | 80 per cent of seeds | **0 per cent** | **not met** |
| SC-007 the breakdown sums to the total | reported as a percentage | **4.8 per cent** of 500 rows, residual mean +0.3030 | **not met** |
| SC-008 spread reported before comparison | written first | `results/rl/progress_spread.md`, written before the candidate run existed | **met** |
| SC-009 the other driving paths unchanged | demonstrated | 132 EditMode green, 357 passed and 3 skipped in `.venv`, 411 passed in `.venv-bc`; the scripted driver completed 3 laps with 0 wall contacts during T022 | **met** |
| SC-010 throughput inside the envelope | reported and inside 12 h | **927 steps/s**, 5,000,000 steps in 5,395.4 s, which is 1.5 h | **met** |
| SC-011 every figure resolves to a run | every run has a row | four runs, four rows, models and curves committed | **met** |
| SC-012 the step accounting | explanation or ratio with range | **3.2161**, sd 0.2829, range 2.1453 to 4.0063, against a ceiling of 4, with the shortfall separated | **met** |

**Nine met, three not.** The three that failed are SC-005, SC-006 and SC-007, and they are not the
same kind of failure.

**SC-005 and SC-006 are the milestone, and the milestone is still not met.** No lap was completed on
held-out track in either inference mode. What changed is the failure: feature 006's policy sat at
the start line until the 60 second stall cap and reached no marker at all, while this one drives a
quarter of the lap and hits a barrier, taking 6.20 of 24 markers on the way. Zero to 6.20 is the
first non-zero held-out result the RL side of this project has produced, and it is not a lap.

**SC-007 is a defect in the instrumentation rather than in the reward.** The behavioural results are
counts taken on the Unity side and do not depend on the decomposition. The cause is identified in
`results/EXPERIMENTS.md` and in T042: the reward breakdown and the trainer's cumulative reward
average over episode sets differing by about 19 per cent. That same mismatch quantitatively explains
the step-ratio shortfall SC-012 reports, so the two are one defect seen twice. Which episodes differ
still needs per-episode records, and naming that is this feature's honest limit.

**The mechanism worked and the milestone did not follow.** The dense progress signal was aimed at
the exploration failure M3 identified, and on its own terms it hit: markers per episode moved for
the first time in M3, and eight episodes drove three consecutive laps during training where the
project had never completed one. It
was not sufficient to produce a lap on unseen track.

## Assumptions

- The 24 markers are ordered and roughly evenly spaced, so the distance along the chain is a usable
  stand-in for distance along the track centre line. The generator's own numbers say about 8.43 m
  of spacing on a track of about 200 m.
- Straight-line distance between consecutive markers is close enough to arc length at this spacing
  that the potential is monotone in real progress. If a generated track has a corner tight enough
  to break that, it is a bug in this assumption and not in the reward.
- The 006 baseline configuration is the comparison point, so hyperparameters, budget, area count
  and seed split are held at their 006 values for the first run of this feature. One change per
  run, as before.
- The existing evaluation scene, sweep runner and run-record path from feature 006 work and are
  reused rather than rebuilt.
- Training runs in `.venv-mlagents` and needs the training scene with play pressed; evaluation
  needs the evaluation scene. Runs killed mid-flight are discarded rather than resumed.
- A dense reward is expected to change how fast learning happens, not what the best behaviour is.
  If the policy ends up optimising the shaping term at the expense of laps, the potential-based
  property has been broken somewhere and that is a defect to find, not a result to report.

## Dependencies

- Feature 006, merged: the agent, the training and evaluation scenes, the per-term reward
  breakdown, the run records, the sweep runner, the noise-floor method, and the baseline numbers
  this feature is measured against.
- Feature 003: the track generator, the checkpoint ring, the start placer and the seed split.
- Feature 005: the scripted driver, which is both the User Story 1 instrument and the 34 of 34
  baseline.
- `DESIGN.md` 4.5, which this feature rewrites before it writes code.
- The constitution's Principles V, VI, VIII and IX.

## Out of Scope

- **Curriculum learning.** Starting the car nearer a marker and widening the distance over lessons
  is the second of the three remedies named at the close of M3. It is a separate feature and is not
  attempted here, so that if the numbers move, it is known which remedy moved them.
- **Imitation warm start.** Recording demonstrations from the scripted driver and pretraining or
  adversarially imitating from them is the third remedy. Also a separate feature. Note for whoever
  writes it that the M4 behavioural cloning model cannot be used directly: it is a convolutional
  network over camera images, and the learning agent reads rays.
- Any change to the ray geometry, the observation vector, the action space or the vehicle.
- Any tuning of the heuristic driver.
- Any change to the seed split or the track generator.
- Re-exporting the feature 006 run archives. Their event files carry end-reason counts as a
  meaningless constant and must not be re-read into the current schema.
- Changing the six existing reward weights. This feature adds a term and leaves the table it was
  handed alone, so that the term is the only variable.
