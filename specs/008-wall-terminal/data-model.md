# Data model: the wall terminal

## The budget

| | |
|---|---|
| Name | `wallContactBudget` |
| Owner | `DrivingAgent` |
| Type | serialized `int` |
| Meaning | how many contact **events** an episode survives before the terminal fires |
| Default | chosen after the R4 recovery probe, recorded in `DESIGN.md` 4.6 |
| Zero | reproduces feature 007 exactly, which is what makes the comparison honest |

**It counts events, not steps and not seconds.** Research R2 is the reason this needs saying:
`WallSensor` raises `OnCollisionEnter` once when colliders begin touching and not again until they
separate and meet again, so a car that slides along a barrier for two seconds spends **one** unit of
budget.

## The two measures

| Measure | Definition | Stats key | Why it exists |
|---|---|---|---|
| `WallContactsPerEpisode` | `WallSensor.Contacts` at episode end | `episode/wall_contacts` | Markers per episode cannot be read without it. A policy reaching more markers while touching more barriers is a different result from one reaching more markers cleanly |
| `LateralClearance` | mean over the episode of the minimum normalised ray distance in the side of the fan | `episode/lateral_clearance` | R5. The contact count cannot detect a sustained grind, and this can. Taken from `CarAgent.RayDistancesNorm`, which is already refreshed every physics step, so it costs one accumulator and no new collision handling |

**`LateralClearance` is a proxy and is written down as one.** It measures how close the car runs to
whatever the side rays see, which on a generated track is the barriers. A policy grinding a barrier
holds a side ray near zero for a long run of steps; a policy driving the centre line does not. It
cannot distinguish a barrier from any other obstacle, and there are no other obstacles on these
tracks.

## What is read against what

| Metric | Baseline | Gate | Source of the gate |
|---|---|---|---|
| markers per episode | **1.4987** | **0.035** | `results/rl/progress_spread.md`, feature 007 |
| laps on held-out seeds | 0 of 10 | any lap at all | the floor is exactly zero |
| the 80 per cent bar | 0 per cent | 80 per cent | feature 006 SC-002, restated unchanged |
| wall share of end reasons | 59.1 per cent | reported, not gated | read together with the stall share |
| stalled share | 27.4 per cent | reported, not gated | a wall fall that becomes a stall rise is a trade |
| `WallContactsPerEpisode` | not measured before | reported, not gated | new in this feature |
| `LateralClearance` | not measured before | reported, not gated | new in this feature |
| throughput | 927 steps/s | reported | episodes are expected to lengthen (R6) |

**The gate carries feature 007's caveat rather than a fresh measurement.** Three runs estimate a
standard deviation to roughly 50 per cent, and a candidate that genuinely starts to learn may be
noisier than the runs the gate came from. Clearing 0.035 is credible; failing to clear it is weaker
evidence than it looks; a result landing near it earns a fresh three-run spread rather than a
verdict.

## What is deliberately not modelled

- **Wall time in steps or seconds.** It needs `OnCollisionStay` on `WallSensor`, which is the code
  path behind every committed `results/heuristic/` row. Out of scope, and its own feature if the
  clearance proxy says it is needed.
- **A per-contact cooldown.** Unnecessary: `OnCollisionEnter` is already edge triggered, so a
  resting car cannot be charged repeatedly. FR-001 exists to keep it that way, not to add anything.
- **Any change to the wall penalty.** Feature 006 tested the weight. This feature tests the
  terminal. One change per run.
