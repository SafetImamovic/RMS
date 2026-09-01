# Phase 1 Data Model: Dense Progress Reward

**Feature**: `007-dense-progress-reward` | **Date**: 2026-08-25

The things that have to exist, what each carries, and which requirement fails if it does not. This
feature introduces exactly one new quantity, and most of what follows is about the conditions under
which that quantity is meaningful.

---

## Marker chain

Not new. It is `CheckpointRing.Markers`, an ordered list of 24 transforms, read and never written
by this feature.

| Field | Meaning | Source |
|---|---|---|
| `Markers[i].position` | world position of marker `i` | `CheckpointRing` |
| `Count` | 24 | `CheckpointRing.Count` |
| `NextIndex` | the marker the ring will award next | `CheckpointRing.NextIndex` |
| `StartIndex` | the marker the episode began at | `CheckpointRing.StartIndex` |
| `LapCount` | laps completed this episode | `CheckpointRing.LapCount` |

**Derived once per track build, never per step:**

| Field | Meaning | Why once |
|---|---|---|
| `SegmentLength[i]` | distance from marker `i` to marker `i+1`, wrapping | 24 square roots per step is waste, and the polyline does not move |
| `CumulativeLength[i]` | chain distance from marker `StartIndex` to marker `i` | the arc position is a lookup plus one projection |
| `ChainLength` | the sum of all 24 segments, about 202 m | it is the denominator of the derived weight (R5) |

**Validation.** `ChainLength` must be positive and `SegmentLength[i]` must be positive for every
`i`. A degenerate track with two coincident markers would divide by zero in the weight derivation,
and it must fail loudly at build rather than produce an infinite reward at run time.

---

## Arc position

New. The one quantity this feature adds.

| Field | Type | Meaning |
|---|---|---|
| `RawArc` | `double` | chain distance from the episode's start marker to the car's projection on the chain, in metres |
| `Unwrapped` | `double` | `RawArc` plus `LapCount * ChainLength`, so it does not reset at the finish (R2) |
| `Ceiling` | `double` | `CumulativeLength` at the end of the segment terminating in `NextIndex` |
| `Clamped` | `double` | `min(Unwrapped, Ceiling)`, the value the reward actually uses (R3) |
| `HasPrevious` | `bool` | false on the first step of an episode, so nothing is charged (FR-004) |
| `Previous` | `double` | `Clamped` from the previous physics step |

**How `RawArc` is computed.** Find the segment the car is on, which is the one ending in
`NextIndex`. Project the car's position onto that segment, clamped to the segment's endpoints.
`RawArc` is `CumulativeLength` at the segment start plus the projected length along it.

**The advance is computed locally, not by differencing totals** (R4). Within one physics step the
car moves of order 0.2 m and cannot cross more than one segment at any speed this vehicle reaches,
so the advance is the change in the projection plus, if the segment changed, the remainder of the
previous segment. The `double` totals are kept for reporting and for the telescoping test only.

**Validation.**

- `Clamped` is non-decreasing over any step in which the car is driving forward along the chain,
  and non-increasing when it is reversing.
- `Clamped` never exceeds `Ceiling`. This is what makes a shortcut worth nothing (FR-008).
- `HasPrevious` is false immediately after every episode begin, including after a training-area
  swap (FR-011, R7). A stale `Previous` from a different track is the failure mode that would look
  like noise rather than like a bug.

---

## Progress term

New. One field in an existing struct, one function in an existing pure static class.

| Property | Value |
|---|---|
| Name in the breakdown | `MarkerProgress` |
| Stats key | `reward/progress` |
| Fires | every physics step after the first of an episode |
| Value | `ProgressWeight * (Clamped - Previous)` |
| Sign | positive advancing, negative reversing, zero at the ceiling or stationary |
| `ProgressWeight` | `0.5 * 24.0 / ChainLength`, about 0.0594 per metre on a 202 m chain (R5) |

**`ProgressWeight` is computed at track build, not stored as a literal.** Generated tracks differ
between seeds, so a literal would silently pay different fractions of a lap on different tracks.
The derivation reproduces; the number does not (Principle VI, R5).

**Validation, and these are the feature's two central claims:**

1. **Telescoping.** The sum of the term over any trajectory equals
   `ProgressWeight * (Clamped_end - Clamped_start)`, within the tolerance in R9. Asserted in
   `TrackProgressTests`, not argued (FR-005, SC-001).
2. **The loop property.** Any trajectory returning the car to a state it already occupied, without
   crossing the finish line forward, sums to zero within the same tolerance (FR-007, SC-002).

---

## Reward breakdown

Modified. The struct feature 006 built, with one field added.

| Field | Weight | Unchanged by this feature |
|---|---|---|
| `CheckpointProgress` | `+1.0` per marker | yes |
| `WrongDirection` | `-1.0` on the edge | yes |
| `WallContact` | `-5.0`, terminal | yes |
| `StepCostTotal` | `-0.001` per step | yes |
| `ForwardSpeed` | `+0.002 * v_norm` | yes |
| `SteeringJerk` | `-0.005 * abs(delta)` above 0.55 | yes |
| `MarkerProgress` | `ProgressWeight * advance` | **new** |

`Total` is the sum of all seven. **Nothing else may call `AddReward`**, which is the rule feature
006's contract already states and which this feature inherits unchanged. The breakdown summing to
the trainer's cumulative reward is FR-010, and it is checked against this feature's own exported
rows rather than inherited from 006's check.

---

## Run record

Modified. The per-run record feature 006 writes, with the metrics this feature gates on.

| Field | Meaning | Why it is here |
|---|---|---|
| `MarkersPerEpisode` | mean of `CheckpointRing.AwardedCount` at episode end | SC-003, the metric that separates a working mechanism from an elegant one |
| `LapsCompleted` | count of episodes reaching one lap | SC-004, which read zero in every M3 run |
| `StalledShare` | share of episodes ending stalled | SC-003's second acceptance scenario: the stall share must fall, not be replaced by a higher wall share |
| `PhysicsStepsCharged` | count of per-step reward charges | R6, the denominator for any statement in seconds |
| `TrainerEpisodeLength` | the trainer's own count | R6, whose ratio against the above should sit at the decision period of 4 |

**Validation.** `PhysicsStepsCharged / TrainerEpisodeLength` is reported with its range across
summaries, against the expected ceiling of 4. Feature 006 measured a mean of about 3.16 with a
maximum of 4.01 and could not say why; this feature reports the shortfall with the two mechanisms
in R6 separated (FR-021, SC-012).

---

## What is deliberately not modelled

- **A centre-line spline.** Rejected in R1. The marker chain is the only notion of forward this
  reward table has, and a second one could disagree with it.
- **A per-lap reward.** The lap is already worth 24 markers plus 12.0 of progress. Adding a bonus
  for the lap itself would be a third signal for the same event and would need its own derivation.
- **Any change to what the agent observes.** The arc position is a reward input, not an
  observation. FR-014 freezes the 19-value vector, and adding progress to it would change what
  the M5 comparison is comparing.
