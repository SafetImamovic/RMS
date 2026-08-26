# Contract: Progress Reward

**Feature**: `007-dense-progress-reward` | **Source of truth**: `DESIGN.md` section 4.5

Feature 006's `contracts/reward-events.md` fixed how each row of the reward table becomes code.
This contract adds one row and states the rules the row alone does not settle. Changing any line
here is a design change and goes into `DESIGN.md` first (FR-001).

## The added row

| Event | Weight | Fires when | Source signal | Stats key |
|---|---|---|---|---|
| Progress along the marker chain | `ProgressWeight * advance` | every physics step after the first of an episode | `TrackProgress.Clamped`, differenced | `reward/progress` |

`ProgressWeight = 0.5 * 24.0 / ChainLength`, computed at track build. On the nominal 202 m chain
that is about 0.0594 per metre, so a full lap of progress pays 12.0 against the 24.0 a full lap of
markers pays.

The six rows of feature 006's table are unchanged in name, weight, firing condition, source signal
and stats key. This feature adds a term and does not retune the table it was handed.

## Rules the table alone does not settle

**The term is a difference of a potential, and it may not be anything else.** No clamping of the
negative part, no rectification, no separate treatment of approach and retreat. A one-sided version
pays a car that oscillates toward a marker and away again, which is farming, and it is farming that
no weight is small enough to prevent. The symmetry is the defence.

**The first step of an episode charges zero.** There is no previous position to difference against,
and the natural bug is to difference against zero, which pays the entire arc position of a
randomised start on the first step of every episode. That is the single most repeated event in
training.

**The arc position is unwrapped, so the finish line is not a special case.** `Unwrapped` adds
`LapCount * ChainLength` to the raw position, so the step in which the car crosses the finish is
charged exactly the distance it drove in that step. A version that reset the position at the finish
would charge one lap of penalty on one step, once per lap.

**The position may not advance past the marker the ring says is due.** `Clamped` is the minimum of
the unwrapped position and the end of the segment terminating in `CheckpointRing.NextIndex`. A car
that cuts across and rejoins further along sits at the ceiling, earning zero progress while still
paying the step cost, until it returns and takes the marker it skipped. This makes a shortcut
strictly worse than the legal path rather than merely unrewarded.

**The advance is computed from the local projection, not by differencing two running totals.** The
totals are kept in `double` for reporting and for the telescoping test. At the far end of a long
episode the totals are of order a kilometre and the step is of order 0.2 m, and the test in SC-001
compares a sum of thousands of small terms against one large difference, which is where accumulated
error would show.

**The previous position is cleared on every episode begin, including the training-area swap.**
Feature 006 found `TrainingArea.SwapTo` ending episodes by a path that bypassed the reward
reporting. The same path must not bypass this reset: a stale position from a different track
differences into hundreds of metres charged on one step.

**Reversing is charged twice, and that is intended.** The wrong-way penalty fires after about
3.43 m of reversing, and the progress term is negative over exactly that stretch. On the nominal
chain 3.43 m of reversing costs about 0.204 of progress on top of the `-1.0` wrong-way penalty.
The combined figure is stated here so that nobody later reads the double charge as an oversight.

**Nothing else may call `AddReward`.** Inherited unchanged from feature 006's contract. The sum of
the seven terms must equal the episode return, or FR-010 is unverifiable.

## The invariant this row must not break

`DESIGN.md` 4.5 holds an anti-farming invariant: driving in circles on open ground across a whole
episode must earn less than a third of what a lap through the markers earns, that is less than 8.0.

**The progress term contributes exactly zero to circling**, by the loop property, so the
invariant's existing arithmetic is untouched: at `SpeedReward` 0.002 an episode of circling at full
speed earns at most `+6.0`, against the `24.0` a lap of markers pays.

This is the one place where the choice of a potential-based term earns its keep. A term that paid
for closing the gap to the next marker would add unbounded earnings to a circling car, and the
invariant would have to be re-derived against a weight rather than being preserved by the shape of
the term.

## What the tests must cover

| Property | Test | Requirement |
|---|---|---|
| Telescoping over a full lap | sum of the term equals the endpoint difference, within R9's tolerance | FR-005, SC-001 |
| The loop property | a trajectory returning to a previous state sums to zero | FR-007, SC-002 |
| No jump at a marker | the term at the step a marker is taken is accounted for by that step's movement alone | spec US1 scenario 2 |
| Symmetry | driving a stretch backwards costs what driving it forwards paid | spec US1 scenario 3 |
| First step | the term is zero on the first step of an episode | FR-004 |
| The clamp | a position advanced past the due marker earns nothing further | FR-008 |
| The reset | a swap or an episode end clears the previous position | FR-011 |
| Degenerate chain | a zero-length segment fails at build, not at run time | data-model validation |
| The breakdown | the seven terms sum to the episode return | FR-010 |
| The restated invariant | circling for a full episode earns less than a third of a lap of markers | FR-007 |

Every one of these is an EditMode test over pure functions and a polyline handed in by the test.
None of them needs a car, a scene or a physics step, which is the property FR-022 preserves.
