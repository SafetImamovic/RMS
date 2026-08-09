# T062: reading every observation against a visible answer

The M2 gate (FR-029). Nineteen observations, each checked against a situation whose correct answer
is known independently of the thing being checked. Sensing nobody has read is sensing nobody has
checked, and an agent that will not learn because one ray is reversed looks exactly like an agent
that needs more training.

**Status: 17 of 19 observations verified on 2026-08-09.** Outstanding: `steer` away from zero, and
the positive half of `yaw`. Both come from two full-lock runs on `FlatGround`.

## Method, and why it changed

The task was written expecting a person to drive, read the overlay, and judge each value against
what was visible out of the window. Seven of the twelve situations turned out to admit a stronger
check, so they were done differently and the difference is worth stating plainly.

Those seven are static: the car is parked somewhere and the correct answer follows from the track
geometry alone. For those, the answer is not eyeballed, it is **computed from the track JSON in
Python and compared against what Unity's physics actually measured**. Two independent
implementations - an analytic ray/polyline intersection against the source centre line, and
Unity's `Physics.RaycastNonAlloc` against the mesh `TrackBuilder` built from it - have to agree.
That catches things a person watching a barrier go past cannot: a half-degree error in ray
spacing, a sign convention that is right at 90 degrees and wrong at 15, a normalisation divisor
off by a percent.

The script lives at the bottom of this file so the check can be repeated.

The remaining five situations depend on motion - throttle, lock, a slide - and those stay a human
drive, because there is no second implementation of the vehicle dynamics to check against.

`P` prints the whole vector to the console via `ObservationProbe` (on the `Car` object). That is
the instrument for the driving half.

## Constants these expectations are derived from

| Quantity | Value | Source |
|---|---|---|
| Track width | 6.0 m | `TRACK_WIDTH_M`, `python/track/config.py:147` |
| Ray length, the divisor of the normalised reading | 20 m | `CarAgent.rayLengthM` |
| Ray count and spacing | 13 over 180°, so 15° apart | `CarAgent`, mirrors `config.py` |
| Ray 06 | 0°, dead ahead | odd count, on purpose |
| Top speed, the divisor of both speed readings | 10.0 m/s | `vehicle_profile.json` |
| Maximum yaw rate, the divisor of the yaw reading | 1.865 rad/s | 10.0 / 5.361, confirmed live |

At full lock the yaw reading and the forward speed reading should be **the same number**: yaw rate
is `v / r_min` and its divisor is `v_max / r_min`, so the radius cancels and yaw norm reduces to
`v / v_max`. It holds at any speed, so situation 8 does not depend on hitting a particular one.

## Results

### Situations 1-7, verified

| # | Situation | Observations | Expected | Result |
|---|---|---|---|---|
| 1 | Stationary at the seed-1004 spawn, marker 18 next | all 13 rays | every ray within tolerance of the analytic value | **OK — worst disagreement 0.000 m across 12 hits; ray 03 misses in both** |
| 1b | Same | ray 00 + ray 12 | the two perpendicular rays span the road, so their sum is the track width | **OK — 3.977 + 2.056 = 6.033 m against a declared 6.000** |
| 1c | Same | vfwd, vlat, yaw, steer | all zero on a stationary car | **OK — largest magnitude 1.8e-9** |
| 1d | Same | hfwd, hright | match the bearing to marker 18, computed from the JSON | **OK — +0.8734 / -0.4870, agreeing to 5 decimals; marker 29.1° left at 8.51 m** |
| 4 | Parked facing a barrier at 0.586 m | ray 06 | **near 0.000, not 1.000** | **OK — 0.029** |
| 4b | Same | rays 00 and 12 | grazing along the wall, so both miss and read 1.000 | **OK — both 1.000** |
| 4c | Same | rays 01-11 | a flat wall gives `d / cos(a)` | **OK — within 1 mm to ±45°, drifting outward at ±60/75° as the wall curves away** |
| 4d | Same | fan symmetry about ray 06 | mirror pairs equal | **OK — worst pair 0.72 percent apart** |
| 6 | Same pose, marker now off to the right | hright | positive | **OK — +0.9055, bearing +64.9°** |
| 5 | Spawn pose, marker off to the left | hright | negative | **OK — -0.4870, bearing -29.1°** |
| 5b | Both poses | hfwd, hright as a pair | unit magnitude, so the two are not independently scaled | **OK — 1.000000 at both poses** |
| 7 | Parked facing directly away from marker 18 | hfwd | -1.000 | **OK — exactly -1, with hright 1.4e-6** |

Situations 2 and 3, the asymmetric left-and-right barrier checks, are subsumed. They existed to
catch a reversed or mis-ordered fan, and situation 1 does that far harder: a mirrored fan would
not reproduce twelve analytic distances, it would reproduce none of them. Situation 4d covers the
symmetry case directly.

**The single most important reading is situation 4 against 4b, both from the same frame.** A wall
on the bumper reads 0.029 and a clear horizon reads 1.000. FR-025 turns on those being opposite,
and the mirrored mistake - encoding a miss as 0 - would have made the safest reading identical to
the most dangerous one.

### Situations 8-12, driven

First drive on seed 1004, five probes, 2026-08-09.

| # | Situation | Observations | Expected | Result |
|---|---|---|---|---|
| 11 | Reverse | vfwd | negative | **OK — -0.171 (probe #4)** |
| 10 | Flat out on the track | vfwd | approaches 1.000 | **0.905 (probe #3). See the note below: this is C17, not a fault** |
| 12a | Cornering | yaw | non-zero | **OK — -0.139 (probe #5)** |
| 12b | Cornering | vlat | non-zero | **OK — 0.039 (probe #5), a 2.6 degree slip angle** |
| 8, 9 | Full lock | steer, yaw sign | steer near ±1, yaw sign matching | **outstanding, see below** |

**The two cornering probes cross-check each other through the bicycle model.** Probe #5 reads
8.54 m/s at a yaw rate of -0.259 rad/s, which is a 32.9 m radius and needs steer 0.174 - a gentle
left. Probe #3 reads 9.05 m/s at -0.005 yaw norm, a 970 m radius, which is straight. Speed and yaw
are consistent with one another at both points, and they were not derived from each other.

**`vfwd` peaking at 0.905 rather than 1.000 is C17 arriving from a third direction.** These tracks
contain no straights, so the car is corner-limited for the whole lap and never reaches `v_max`.
The `speed max/P99` check says this, the six lap measurements in C17 say it, and now the speed
observation says it. Reaching 1.000 needs `FlatGround`, which has room to accelerate.

### What is still missing, and why the first attempt could not have found it

**`steer` read 0.000 in all five probes, including probe #5 where the car was demonstrably
cornering.** That is not a car that does not steer. It is a measurement the driver cannot take:
steering recentres at `steerRateNormPerS`, which is 3.7, so releasing A or D to reach P drains a
real 0.174 to zero in under fifty milliseconds - under three frames at 50 Hz.

`ObservationProbe` now also reports the **signed extreme of steer, yaw and vlat, and the range of
vfwd, since the last probe**, sampled in `FixedUpdate`. Holding the key and pressing P afterwards
now records the peak instead of the recentred value.

**Full lock cannot be held on a generated track, and the original instruction to try was wrong.**
Minimum turning radius is 5.361 m, so a full-lock circle is 10.7 m across, against a track 6.0 m
wide. The car hits a barrier before the circle closes. Situations 8 and 9 belong on
`FlatGround.unity`, which is open ground; `CarAgent`, `ObservationDebug` and `ObservationProbe`
have been added to its car for that purpose.

Two things follow from moving there. Heading reads zero, because there is no marker ring - already
verified in situations 1d, 5, 6 and 7. And **every ray should read 1.000**, because there is
nothing to hit anywhere on the plane, which is a third reading of the miss encoding on an entirely
open field.

| # | Situation, on `FlatGround` | Expected | Result |
|---|---|---|---|
| 8 | Hold **A** and **W** together, circle for a few seconds, press **P** while still holding | peak steer near -1.000, peak yaw negative, **\|peak yaw\| equal to vfwd** | |
| 9 | Hold **D** and **W**, same | peak steer near +1.000, peak yaw positive, same magnitude match | |
| 10b | Hold **W** in a straight line until the speed stops rising | vfwd reaches 1.000 without exceeding it. Pinned at exactly 1.000 while still accelerating would mean the clamp is hiding a governor fault, which has happened once on this project | |
| 8b | Any of the above | all 13 rays | all 1.000, nothing to hit | |

## Coverage

| Observation | Covered by | Status |
|---|---|---|
| rays 00-12, all thirteen | 1 (analytic, 12 hits + 1 miss), 4c, 4d | done |
| speed forward | 1c (zero), 10, 11 | **done** - 0.905 forward, -0.171 reverse |
| speed lateral | 1c (zero), 12b | **done** - 0.039 cornering |
| yaw rate | 1c (zero), 12a | **done negative** - -0.139; positive still to come from situation 9 |
| heading forward·dir | 1d, 7 | done |
| heading right·dir | 1d, 5, 6, 5b | done |
| steering | 1c (zero) | **outstanding** - never observed away from zero |

Seventeen of nineteen fully verified. What remains is one observation, `steer`, plus the positive
half of `yaw`, and both come from the same two runs on `FlatGround`.

## Two findings from running this

**The car cannot be repositioned by writing `transform` in play mode.** The first teleport was
silently discarded and the car was back at spawn on the next read. The Rigidbody owns the pose and
overwrites the transform at the next physics step; `Rigidbody.position` works. This is research
C16 - the spawn defect - reproduced from the opposite direction, and it is the same trap that hid
that bug for so long, because the write appears to succeed.

**`MaxYawRateRadPerS` reads 1.865 live**, matching 10.0 / 5.361 derived from the profile. The
divisor is derived rather than typed, so this confirms the chain from `vehicle_profile.json`
through `CarController.Profile` into the observation scale.

## Repeating the ray check

`Unity_ManageGameObject get_component` on `CarAgent` returns `RayDistancesM`, `RayHit` and the six
self-state values directly, so the readings do not have to be transcribed. Take the car's
`SensorOrigin` and `transform.forward` from the same call, then:

- build the two barrier faces by offsetting the centre line by `width_m / 2` along its normal
- `right = (forward.z, -forward.x)` in the track's 2D frame, matching `Vector3.Cross(Vector3.up, forward)`
- ray direction at angle `a` is `cos(a) * forward + sin(a) * right`, right positive
- intersect against every segment of both faces, nearest hit within 20 m, miss otherwise

Verified poses on seed 1004, for reference:

| Pose | Rigidbody position | Rigidbody rotation (xyzw) |
|---|---|---|
| Spawn, marker 18 next | -8.517873, 0.5, -32.632267 | 0, 0.28664, 0, 0.95804 |
| Facing a barrier at 0.586 m | -23.8563, 0.5, -17.2741 | 0, 0.4462, 0, 0.89493 |
| Facing directly away from marker 18 | -8.517873, 0.5, -32.632267 | 0, -0.825342, 0, 0.564633 |

## Verdict

- Seed used: 1004, plus `FlatGround` for the lock runs
- Date: 2026-08-09
- Outcome: **17 of 19 observations verified.** Gate not yet closed. `steer` has never been read
  away from zero, and until it has, nothing rules out an observation that is wired to a constant.
  That is exactly the kind of fault this task exists to catch, so the gate stays open on it.
