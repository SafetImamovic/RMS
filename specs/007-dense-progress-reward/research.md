# Phase 0 Research: Dense Progress Reward

**Feature**: `007-dense-progress-reward`
**Date**: 2026-08-25

Every unknown this feature has to settle before code, with the decision taken and the alternatives
that were rejected. The rule feature 006 used holds here: a number that is picked rather than
derived is a defect, and the derivation lives in this file or in `DESIGN.md`, never only in the
code.

---

## R1. What the potential is a function of

**Question.** The spec requires a potential-based shaping term. Potential of what?

**Options considered.**

1. Distance from the car to the next marker.
2. Distance remaining along the marker chain to complete the lap.
3. Arc position of the car along the marker chain, measured forward from the lap start.

**Decision: option 3, an arc position along the chain, and the potential is that position times a
weight.** Options 2 and 3 are the same function up to a sign and an additive constant, so they give
the identical shaping term. Option 3 is chosen as the way to write it because it is the one that
survives the lap boundary, which R2 deals with.

**Why option 1 is wrong, and it is wrong rather than merely worse.** Distance to the next marker is
discontinuous at every marker: the moment a marker is taken, the distance jumps from about zero to
about 8.43 m, and the shaping term differences that jump into a penalty of a full marker gap for
the one step in which the car did the right thing. A car would be paid to approach a marker and
punished for reaching it. Clamping the jump away is exactly the kind of patch that makes the term
stop telescoping, which is the property the entire feature rests on.

**How the arc position is computed.** The checkpoint ring already exposes its markers as an ordered
list of transforms. The chain is the polyline through those positions. The car's arc position is
the length of the chain up to the segment it is on, plus its projection onto that segment. Segment
lengths are computed once per track build, not per step.

**Alternative rejected: the track generator's own centre line.** The generator has a spline and it
is a more faithful arc length than a 24-point polyline. It is rejected because `TrackBuilder` is
frozen by FR-014 and because the marker chain is already the thing the reward is defined against
everywhere else in the table. Using a second notion of progress would mean the shaping term and the
checkpoint term could disagree about which way is forward.

---

## R2. The lap boundary

**Question.** Arc position resets to zero when the car completes a lap. Differenced naively, that
single step charges the entire lap's length as a penalty. What happens there?

**Options considered.**

1. End the episode at lap completion, so the boundary never occurs mid-episode.
2. Charge zero on the rollover step and re-seed the stored position.
3. Track the arc position unwrapped: keep adding lap lengths instead of resetting.

**Decision: option 3, the unwrapped arc position.** The stored quantity is total distance advanced
along the chain since the episode began, and it does not reset at the finish line. The shaping term
is the weighted change in it, so a lap crossing is charged exactly what the car actually drove in
that step and nothing else.

**Why not option 1.** SC-001 of feature 006 asks for three clean laps. Ending the episode at one
lap changes what the milestone measures.

**Why not option 2.** It works, and it was the first idea, but it puts a special case on the one
step per lap that a bug would be hardest to notice in, and it breaks the telescoping property
across the boundary, which then has to be excluded from the test in SC-001. Option 3 needs no
special case and keeps the test total.

**The honest caveat, and it is written down rather than glossed.** The unwrapped position is a
function of the trajectory, not of the instantaneous state, so across a lap boundary this is not
strictly a state potential in the textbook sense. Within a lap it is. What the unwrapping preserves
is the two properties this feature actually needs and tests: the term telescopes, so its sum over
any trajectory is the endpoint difference, and any loop that does not cross the finish line forward
sums to zero. Crossing the finish line forward is the behaviour the milestone is buying, and the
amount it pays is bounded by the lap length. There is no free loop.

---

## R3. Preventing the shortcut from paying

**Question.** The checkpoint ring refuses to award a marker that is not the one due, so a car that
cuts a corner and rejoins further along earns nothing from the checkpoint term. The arc position,
computed geometrically, would jump forward across the shortcut and pay for it.

**Decision. The arc position is clamped so it may not advance past the end of the segment that ends
at the ring's next due marker.** The car may earn progress up to the marker it is allowed to take
and no further. Once that marker is taken, the ceiling moves to the following one. A car that
teleports geometrically ahead of its due marker sits at the ceiling, earning nothing more, until it
comes back and takes the marker it skipped.

**Consequence that has to be stated.** A car pinned at the ceiling receives zero progress reward
while still paying the step cost, which is the correct pressure, and it makes the shortcut strictly
worse than the legal path rather than merely unrewarded. This is the mechanism that satisfies
FR-008.

---

## R4. Floating point

**Question.** The unwrapped position grows without bound across a long episode and the per-step
movement is of order 0.2 m against a total that can reach a kilometre. Differencing two `float`
values there loses significant digits.

**Decision. The term is computed from the per-step advance directly, not by differencing two
stored totals.** The advance within a step is the change in the projection on the current segment,
plus whole segment lengths for any segments fully crossed in that step. The unwrapped total is
still kept, in `double`, but only for reporting and for the telescoping test, never as the input to
the reward.

**Why this matters at the size we are at.** A `float` has about seven significant decimal digits.
At a total of 1000 m the representable step is about 0.00006 m, so a 0.2 m advance is still fine
and this is precaution rather than rescue. It is done anyway because the test in SC-001 compares a
sum of several thousand small terms against one large difference, and that comparison is where
accumulated error would actually show up.

---

## R5. The weight, derived rather than chosen

**Question.** What does one lap of progress pay, relative to the 24.0 that one lap of markers pays?

**The geometry.** 24 markers at about 8.43 m of spacing gives a chain length of about 202 m, which
matches `DESIGN.md` 4.5's statement of a track of about 200 m. The exact per-track chain length is
computed at track build time and is the denominator actually used, because generated tracks differ
between seeds.

**The derivation.** Let the shaping pay a fraction of what the markers pay over the same lap:

```
progress reward per lap  =  alpha x 24.0
weight per metre         =  alpha x 24.0 / chain length
```

**Decision: alpha = 0.5, so a lap of progress pays 12.0 against the markers' 24.0.** The reasons,
in the order they matter:

- **The markers must stay the larger signal.** They are what the milestone is defined on, and the
  shaping exists to lead the policy to them, not to replace them. At alpha = 0.5 a policy that
  drives the racing line and takes every marker earns 36.0 per lap, of which two thirds is still
  the thing being measured.
- **The per-step size has to beat the step cost by enough to be a gradient.** At about 0.2 m per
  physics step at the speeds the scripted driver reaches, alpha = 0.5 on a 202 m chain gives about
  0.0119 per step against a step cost of -0.001. That is an order of magnitude, which is the point:
  under the old table the per-step signal for making progress was exactly zero.
- **The anti-farming invariant is unaffected, and this is checked rather than assumed.** The
  invariant in `DESIGN.md` 4.5 is that circling on open ground across a whole episode must earn
  less than a third of a lap of markers, that is less than 8.0. Circling earns zero from the
  shaping term by the loop property, so the invariant's arithmetic is exactly the one already
  written: at `SpeedReward` 0.002 an episode of circling at full speed earns at most +6.0.

**Alternative rejected: alpha = 1.0.** A lap of shaping worth as much as a lap of markers makes the
two signals equal partners, and any error in the arc geometry then costs as much as a missed
marker. Half is enough to give a gradient and keeps the marker term dominant.

**Alternative rejected: picking a per-step number directly.** That is the mistake the M3 closeout
names. A per-step weight is not comparable to anything; a per-lap fraction is comparable to the
24.0 already in the table.

---

## R6. Where the term is charged, and the open 006 item

**Question.** Feature 006 closed with the trainer's `episode_length` at about 530 against about
1676 charges of the step term, a ratio of about 3.16 that varied from 1.95 to 4.01. This feature's
per-lap prediction depends on knowing which count is the denominator, so the item cannot stay open.

**The finding.** `unity/SelfDrivingSim/Assets/Prefabs/TrainingArea.prefab` line 428 sets
`DecisionPeriod: 4`. The trainer counts agent decisions; the reward terms are charged on the
physics step. **Four is therefore the expected ratio, and the measured maximum is 4.01.** The
discrepancy is not a mystery quantity, it is the decision period, and the only thing left to
explain is why the mean falls below the ceiling rather than sitting on it.

**The hypothesis for the shortfall, to be confirmed rather than asserted.** Two mechanisms both
push the ratio under 4 and both are already documented in feature 006:

1. Episodes that end part way through a decision window are charged fewer than four physics steps
   for their last decision.
2. The swap-ended episodes 006 found: about one episode in six at a five-episode rotation was
   counted by the trainer and never reached the reward reporting, which inflates the trainer's
   count relative to the charges.

**Decision.** This feature instruments both counts in one run and reports the ratio against the
ceiling of 4, with the two mechanisms separated. Any statement of episode duration in seconds is
derived from the physics-step count at 50 Hz, and says so.

**Consequence for the per-lap prediction in SC-001.** The prediction is a distance times a weight,
so it does not depend on the decision period at all. The tests sum the term over physics steps
because that is where it is charged.

---

## R7. Episode reset and the training-area swap

**Question.** Where does the stored previous position have to be cleared?

**Decision.** In the agent's episode-begin path, and the training area's swap must route through
that path rather than around it. Feature 006 already found that `TrainingArea.SwapTo` called
`EndEpisode` directly and bypassed the reward reporting; the fix landed for reporting, and this
feature requires the same route to carry the position reset.

**Why this is a first-class risk rather than an edge case.** A stale position from the previous
episode differences against the new episode's first position across a teleport to a different
track. That is a single step charging hundreds of metres of progress or penalty, on the most
frequent event in training, and it would look like noise rather than like a bug.

---

## R8. The noise floor for this feature's metrics

**Question.** Feature 006 measured a noise floor on cumulative reward: sample sd 0.0924, gate 0.19.
That gate cannot be reused here, for two reasons.

**Why not.** First, adding a term changes the scale of cumulative reward, which FR-018 forbids
comparing across the two tables. Second, and more to the point, this feature judges itself on
behavioural metrics, and a spread measured on cumulative reward says nothing about the spread of
markers earned per episode.

**Decision.** Repeat the three-identical-run protocol from feature 006 T047 at the same reduced
budget, and report the sample standard deviation and the gate for the metrics this feature actually
gates on: markers earned per episode, laps completed, and the share of episodes ending stalled.
Feature 006 measured 0.0315 and 0.0631 on `reward/checkpoint`, so a floor on the marker count is
expected to be small, but it is measured and not assumed.

**The protocol is unchanged and that matters.** Same budget, same seeds 1, 2, 3, same everything
except the trainer seed, and the spread is reported before any candidate is compared against it.

---

## R9. The tolerance for the telescoping test

**Question.** SC-001 compares a sum of several thousand per-step terms against one endpoint
difference. Exactly equal is not achievable in floating point. What counts as agreement?

**Decision.** The tolerance is stated as a relative one: the sum and the endpoint difference must
agree to within 0.1 per cent of the endpoint difference, or within the weight times 0.01 m,
whichever is larger. The second clause exists so a trajectory with an endpoint difference near zero,
which is exactly the loop case in SC-002, has an absolute floor rather than an impossible relative
one.

**Why a stated tolerance rather than a machine-epsilon one.** The arc position is a projection onto
a polyline, and the polyline is an approximation of the track. The test is checking that the term
telescopes, not that the geometry is exact.

---

## R10. What the first run changes, and what it does not

**Decision. One change from the 006 baseline: the reward table gains the progress term.**
Hyperparameters, budget, area count, decision period, seed split and every existing weight are held
at their 006 values.

**Why the budget is held rather than raised.** The M3 closeout retired the budget hypothesis with a
5,000,000-step run whose first and last 250 summaries read -4.573 and -4.409 against a standard
deviation of 0.512. Raising the budget in the same run that changes the reward would make the
result unattributable, which is the failure mode FR-019 and the one-change rule exist to prevent.

---

## Summary of decisions

| Item | Decision |
|---|---|
| R1 | Potential is arc position along the 24-marker chain, times a weight |
| R2 | Arc position is unwrapped across lap boundaries, no special case at the finish |
| R3 | Arc position is clamped at the segment ending in the ring's next due marker, so shortcuts pay nothing |
| R4 | The term is computed from the per-step advance; the unwrapped total is `double` and is reporting only |
| R5 | Weight = 0.5 x 24.0 / chain length, so a lap of progress pays 12.0 against the markers' 24.0 |
| R6 | `DecisionPeriod: 4` is the 006 ratio; the shortfall below 4.00 is instrumented and explained |
| R7 | The stored position is cleared in the episode-begin path, and the area swap routes through it |
| R8 | The noise floor is re-measured on behavioural metrics, three identical runs, same protocol as T047 |
| R9 | Telescoping tolerance is 0.1 per cent relative with an absolute floor of the weight times 0.01 m |
| R10 | One change from the 006 baseline, budget included |

No NEEDS CLARIFICATION items remain.
