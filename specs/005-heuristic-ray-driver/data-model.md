# Data Model: Heuristic Ray-Following Driver

Phase 1. The four entities the spec names, with their fields, the rules that constrain them, and
the state a run moves through.

Nothing here is a database. These are the shapes that cross a boundary: from the simulation to a
file, and from that file to a report. Everything else is local to one method and does not belong
in this document.

---

## Controller strategy

A named way of turning sensed distances into a steering command. Two exist and both are retained
(FR-006).

| Field | Type | Notes |
|---|---|---|
| `name` | enum | `MostOpen` or `WeightedAverage` |
| `Steer(distances, angles)` | pure function | returns steering in [-1, 1] |

**Rules**

- Both are pure functions of the normalised distance array and the fixed ray angles. No state
  between calls, no access to the car, the track or the clock. This is what makes them testable
  without a scene (Principle VIII) and what keeps FR-001 checkable by inspection.
- `MostOpen` selects the ray with the greatest distance and steers toward its angle, divided by
  `steer_max_deg`. **Ties break toward the centre ray, never by array order** (R9). A tie broken by
  index makes the car turn toward whichever end of the loop happens to run first, which is a bug
  that only appears on symmetric readings and would be blamed on the track.
- `WeightedAverage` returns the distance-weighted mean of the ray angles, divided by
  `steer_max_deg`. With all distances equal it returns 0 by construction, which is the correct
  answer to a symmetric reading and needs no special case.
- Both clamp to [-1, 1]. `MostOpen` reaches the clamp often, because a ray at 30 degrees already
  asks for 1.2 (R2); that saturation is the behaviour under study, not a fault to be smoothed.

**What neither does:** longitudinal control. Speed is derived from the steering command by the
driver, not by the strategy, so the two strategies differ in exactly one thing and the comparison
in US2 is about steering alone.

## Sensing configuration

The arrangement of the sensing fan (FR-013, FR-016). Lives in the `sensing` block of
`vehicle_profile.json`; see [contracts/sensing-block.md](./contracts/sensing-block.md).

| Field | Type | Current value | Notes |
|---|---|---|---|
| `ray_count` | int | 13 | Odd, so one ray looks straight ahead |
| `ray_fov_deg` | float | 180.0 | Total span, centred on the nose |
| `ray_length_m` | float | 20.0 | Also the divisor of the normalised reading |

**Rules**

- Exported from `python/track/config.py` and read by `CarAgent`. **One source, so the two copies
  cannot drift** (FR-016). The mirror test enforces the export, and `CarAgent` reading the file
  enforces the rest.
- An even `ray_count` leaves no ray straight ahead. `CarAgent` already warns; the sweep must treat
  such a configuration as a deliberate choice rather than an error, because whether the centre ray
  matters is one of the things US3 asks.
- Ray spacing is derived, `ray_fov_deg / (ray_count - 1)`, never stored. Storing both invites the
  same drift the block exists to prevent.
- **Changing these values invalidates every previously measured sensing result** and any model
  trained against the old arrangement (FR-018). The values do not change in this feature; only
  where they are read from moves.

## Run record

One execution of one controller on one seed under one sensing configuration (FR-010). Written by
the sweep runner, one row per run; see [contracts/run-record.md](./contracts/run-record.md).

| Field | Type | Notes |
|---|---|---|
| `seed` | int | From the committed training split |
| `controller` | enum | `MostOpen` or `WeightedAverage` |
| `ray_count`, `ray_fov_deg`, `ray_length_m` | as above | Repeated per row, so a row is self-describing (SC-006) |
| `completed_lap` | bool | Every checkpoint awarded in order |
| `lap_time_s` | float | Null when no lap completed |
| `checkpoints_awarded` | int | Out of the track's own count |
| `checkpoints_skipped` | int | Non-zero means a corner was cut |
| `wall_contacts` | int | |
| `end_reason` | enum | `LapComplete`, `TimeLimit`, `WallContact`, `WrongWay`, `FellThrough` |
| `steer_p95_dsteer` | float | \|delta steer\| P95 resampled to 14.08 Hz |
| `steer_sign_changes_per_s` | float | The chatter measure |
| `time_scale` | float | What the run was simulated at, so a fast run is never silently compared with a real-time one |

**Rules**

- **Every run produces a record, including a failed one.** A sweep that only records successes
  reports the wrong acceptance rate, and `end_reason` is the field that makes a failure legible.
- `lap_time_s` is null rather than zero when no lap completed. Zero is a lap time; null is not.
- A row carries its full configuration rather than referencing one, because SC-006 requires a
  reader to determine which controller and configuration produced a figure from the results alone.
  The duplication is the point.
- `time_scale` exists because R4 accelerates the simulation. A run at 8x that disagrees with the
  same seed at 1x is a defect in the sweep, and without this field it would be invisible.

## Sweep

A set of run records covering the same seeds across several sensing configurations, reported
together (FR-014, FR-012).

| Field | Type | Notes |
|---|---|---|
| `configurations` | list | Each a sensing configuration |
| `seeds` | list | **Identical across configurations**, or the comparison is void |
| `records` | list | `len(configurations) * len(seeds) * len(controllers)` |
| `noise_floor` | measured | The run-to-run spread from FR-011, measured before any comparison is read |

**Rules**

- Every configuration runs the same seeds (FR-014). A configuration that skipped a seed because it
  crashed there has not scored better on the rest; it has scored worse, and the report must say so.
- **No difference is a finding until it exceeds `noise_floor`** (FR-015). The noise floor comes
  from repeating one seed and controller several times and measuring the spread, following feature
  004's R13 rather than assuming determinism.
- Results are reported over the seed set with descriptive statistics, never as one seed's outcome
  (FR-012, Principle IX). The tracks differ in difficulty by construction, so a single seed is a
  sample of one.
- The sweep runs on the 34 training seeds only (R5). The evaluation seeds are not touched, so no
  later claim about the learning agent on those tracks is contaminated by a geometry chosen against
  them.

## Run lifecycle

The states a single run moves through, and where a record is written.

```text
Configure ──► Build track for seed ──► Place car ──► Engage driver
                                                          │
                                    ┌─────────────────────┤
                                    ▼                     ▼
                              lap completed         failure condition
                              (all markers)     (time limit, wall contact,
                                    │            wrong way, fell through)
                                    └──────────┬──────────┘
                                               ▼
                                     Write record, reset,
                                     next seed in the same session
```

**Rules**

- **Every path reaches a written record** (FR-005, FR-010). There is no exit from this diagram that
  leaves nothing behind, because a sweep that silently drops a seed produces a report whose
  denominator is wrong.
- The time limit is derived rather than picked: the slowest lap recorded in T051 with margin.
- Reset happens inside the session (R4). A sweep that restarted the editor per seed would spend its
  entire budget on domain reloads.
- Control is engaged and released explicitly, and exactly one source holds it (FR-004). The driver
  refuses to engage while `ScriptedDriver` is running rather than fighting it for the same field.
