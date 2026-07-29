# Phase 1 Data Model: Unity Driving Environment (M2)

Python entities are frozen dataclasses, the same convention as `TrackDataset` in M1 and
`RecordingSession` in feature 002. Computing one never writes to disk; only the export step
writes, and only under the declared output directories.

C# entities are plain serialisable types. They mirror the Python ones by field name so that a
mismatch shows up as a deserialisation failure rather than as silently wrong geometry.

---

## `VehicleProfile`

Every limit the car has, in one place, each traceable to a measured statistic or a stated
geometric assumption (research C1 to C4).

| Field | Type | Meaning |
|---|---|---|
| `wheelbase_m` | `float` | Distance between axles. The one freely chosen value; every radius scales with it |
| `steer_max_deg` | `float` | Road-wheel angle at full lock, fixed at 25 by DESIGN 4.4 |
| `steer_rate_norm_per_s` | `float` | How fast the steering input can move, in normalised units per second |
| `v_max_ms` | `float` | Top speed in the simulation. A playability choice, never used in a comparison |
| `accel_ms2` | `float` | Achievable acceleration, from the recorded speed-change distribution |
| `brake_ms2` | `float` | Achievable deceleration, same source |
| `r_min_m` | `float` | Derived, `wheelbase / tan(steer_max)`. Absolute tightest circle |
| `radius_margin` | `float` | Safety factor on `r_min_m`. Also the steering reserve, see rules |
| `r_floor_m` | `float` | Derived, `r_min_m * radius_margin`. The tightest corner a track may contain |
| `max_required_steer` | `float` | Derived, the steering a corner at `r_floor_m` demands |

**Rules**

- `r_min_m`, `r_floor_m` and `max_required_steer` are **derived, never stored independently**. A
  profile that lets them drift out of agreement with `wheelbase_m` is the single easiest way for
  this feature to become quietly wrong.
- `max_required_steer` equals `atan(tan(steer_max) / radius_margin) / steer_max` and is therefore
  **independent of wheelbase**. The margin alone controls it. At margin 1.3 it is 0.789, leaving
  21.1 percent of steering in reserve (research C2).
- `v_max_ms` may never appear in a comparison against the dataset. All speed comparisons are
  normalised by each side's own 99th percentile, because the recorded speed column has no
  documented unit (research C3).
- The C# `VehicleProfile` mirrors this type field for field. The two are checked against each
  other by a test, not by discipline.

---

## `TrackSeed`

One integer and the record of what happened to it.

| Field | Type | Meaning |
|---|---|---|
| `seed` | `int` | Fully determines the track |
| `accepted` | `bool` | Whether it passed every geometric and statistical check |
| `rejection_reason` | `str \| None` | Which check failed, when it did |
| `amplitude` | `float` | The `A` drawn for this seed |
| `phases` | `list[float]` | One phase per harmonic |

**Rules**

- Rejected seeds are **kept**, not discarded. A generator that silently resamples until it
  succeeds has an acceptance rate nobody can see, and a low rate is a finding about the radius
  floor fighting the statistical target rather than a nuisance to hide (research C7).
- `rejection_reason` is non-empty exactly when `accepted` is false.
- The same seed always produces the same `amplitude` and `phases`. No global random state is ever
  consulted.

---

## `CentreLine`

The generated closed curve, sampled.

| Field | Type | Meaning |
|---|---|---|
| `seed` | `int` | |
| `theta` | `ndarray` | Sample parameter, 2000 points over one full turn |
| `x`, `y` | `ndarray` | Cartesian coordinates of the centre line |
| `arc_length` | `ndarray` | Cumulative distance along the curve |
| `curvature` | `ndarray` | Curvature at each sample, from the closed-form polar expression |
| `radius` | `ndarray` | Reciprocal of curvature, clipped at a large finite value where curvature approaches zero |
| `total_length_m` | `float` | Perimeter |

**Rules**

- Closure is a property of the functional form, not of a correction applied afterwards. Nothing
  in this type may adjust the endpoints to meet (research C6).
- `curvature` is computed analytically, because `r`, `r'` and `r''` are known in closed form for a
  sum of sines. Numerical differentiation would introduce error at exactly the point where the
  accept-or-reject decision is made (research C7).
- `radius` may contain very large values at inflection points. Consumers care about the minimum,
  never the maximum.

---

## `GeometryReport`

Whether a centre line is physically usable.

| Field | Type | Meaning |
|---|---|---|
| `seed` | `int` | |
| `min_radius_m` | `float` | Tightest corner |
| `r_floor_m` | `float` | The floor it was tested against, reported so the test is auditable |
| `radius_ok` | `bool` | |
| `self_intersects` | `bool` | Any non-adjacent segment pair crossing |
| `min_separation_m` | `float` | Closest approach between parts of the loop far apart along it |
| `separation_ok` | `bool` | |
| `total_length_m` | `float` | |

**Rules**

- Closure alone is not enough. A loop can be topologically fine and still pass within a few metres
  of itself, which makes distance readings ambiguous and marker ordering meaningless. Both checks
  are required (research C10).
- `separation` is measured only between points separated by more than twice the track width along
  the arc, so that neighbouring samples do not trivially fail it.

---

## `SteeringDemand`

What a driver would have to do to follow this track.

| Field | Type | Meaning |
|---|---|---|
| `seed` | `int` | |
| `required_steer` | `ndarray` | `atan(wheelbase / radius) / steer_max` at each sample |
| `max_required` | `float` | Peak demand |
| `percentiles` | `dict[float, float]` | Distribution summary at the same percentiles M1 reports |

**Rules**

- Values are unsigned. Left and right are a property of which way the track happens to bend at
  that point, and the human comparison in M1 was made on absolute steering.
- `max_required` can never exceed the profile's `max_required_steer`. If it does, the radius check
  failed and the seed should already have been rejected.

---

## `MatchReport`

How close a track, or a batch of them, sits to the human data.

| Field | Type | Meaning |
|---|---|---|
| `scope` | `str` | A single seed, or a named batch |
| `distance` | `float` | Wasserstein-1 distance to the reference distribution |
| `threshold` | `float` | The acceptance threshold, reported alongside |
| `accepted` | `bool` | `distance <= threshold` |
| `reference` | `str` | Which empirical distribution was used, and that it is the conditional one |
| `n_track_samples`, `n_reference_samples` | `int` | |
| `note` | `str` | Plain language, including the truncation and the missing-straights caveat |

**Rules**

- `distance` is a **distance**, not a test statistic, and `accepted` is a threshold decision, not
  a rejection of a null hypothesis. No p-value appears in this type. A large p-value is not
  evidence of agreement, and feature 002 exists because that error was made once already
  (FR-019, research C8).
- `reference` records that the comparison is against the **conditional** distribution given
  non-zero steering, because a harmonic loop has no straight sections at all (research C9).
- `note` must state the two known limitations: no track can demand more than the profile's
  `max_required_steer`, and no track contains a straight.

---

## `TrackFile`

The committed handoff between Python and Unity. Full field list in
[contracts/track-file-schema.md](contracts/track-file-schema.md).

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `int` | Bumped whenever the shape changes, so a stale file fails loudly |
| `seed` | `int` | |
| `generator` | `object` | `R0`, harmonics, amplitude, phases: enough to regenerate from scratch |
| `vehicle_profile` | `object` | The profile the track was validated against |
| `centre_line` | `array` | Ordered points, with arc length and radius at each |
| `width_m` | `float` | |
| `checkpoints` | `array` | Ordered, with position and forward direction |
| `geometry_report`, `match_report` | `object` | Carried with the track, not stored separately |

**Rules**

- The file carries **both** the sampled geometry and the parameters that produced it. Sampled
  points are what Unity builds from; the parameters are what makes the file auditable and
  regenerable without trusting it.
- Loading must fail on a `schema_version` it does not recognise, rather than reading what it can.
- The file is committed. A reviewer can rebuild a track without running the generator, which is
  what the clean-clone gate requires.

---

## `DriveLog`

A human keyboard drive, in the dataset's own columns so the two can be compared directly.

| Field | Type | Meaning |
|---|---|---|
| `steering`, `throttle`, `brake`, `speed` | per step | Same names, same order, same meaning as the driving log |
| `t` | per step | Simulation time, needed for rate matching |
| `source` | `str` | Which scene and which seed |

**Rules**

- Before any per-step quantity is compared against the dataset, the log is resampled to 14.08 Hz,
  the median recording rate of track1. A per-frame steering change means nothing without the rate
  it was measured at, and comparing across two different rates measures the sampling difference
  rather than the driving (research C14).
- Speed is normalised by the log's own 99th percentile before comparison, never converted.

---

## `CheckpointRing` (C# only)

Ordered progress markers around one track.

| Field | Type | Meaning |
|---|---|---|
| `checkpoints` | ordered list | Position and forward direction for each |
| `next_index` | `int` | Which one is expected next |
| `laps_completed` | `int` | |
| `wrong_way` | `bool` | Set when the vehicle approaches an already-passed marker |

**Rules**

- A marker is awarded only when it is the expected next one. Out-of-order contact is ignored for
  scoring and, if it is a marker already passed, reported as wrong-way travel.
- A lap completes when the index wraps, not when a timer expires.
- This type has no reward logic. Reward shaping belongs to M3, and putting it here would mean the
  first training run changes a file this feature claims to have verified.
