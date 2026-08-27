# Research: the wall terminal

## R1. What is being changed, and what feature 006 already settled

The wall row of the reward table has two separable parts: a **penalty** of -5.0 and a **terminal**,
the episode ending at the contact. Feature 006's `ppo_car_wall_lo` changed the penalty to -1.0 and
left the terminal alone. It made the return measurably worse, -0.3185 against a 0.19 gate, and
shifted the end-reason mix by about 4.5 points. That is evidence about the weight.

**Nothing has ever tested the terminal.** In every M3 run the episode ended at the first contact, in
both arms of every comparison. This feature changes the terminal and pins the penalty, so a moved
number is attributable to one of the two.

**Decision**: change the terminal only. FR-006 pins the penalty at -5.0.

## R2. `OnCollisionEnter` is edge triggered and there is no `OnCollisionStay`

`WallSensor` implements `OnCollisionEnter` and nothing else. `TakeNewContact` returns a transition
and clears itself, and `Contacts` counts entries.

**This has a consequence the spec's first draft got backwards.** The worry recorded there was a
resting car being charged at 50 Hz. That cannot happen: Unity raises `OnCollisionEnter` once when
the colliders begin touching and not again until they separate and meet again. FR-002 is therefore
**already satisfied by construction**, and no cooldown is needed.

**The real consequence is worse and points the other way.** A car that touches a barrier and then
slides along it without separating registers **one** contact for the entire grind. So:

- a contact budget counts entries, not wall time, and a budget of three could permit a policy to
  ride a barrier for most of a lap while spending only one of its three;
- `WallContactsPerEpisode` is therefore a weak measure of how much wall the policy is using, and
  cannot on its own answer the grinding question FR-010 asks about.

**Decision**: the budget counts contact entries, because that is what the existing sensor can report
and changing its semantics would change the code path behind every committed `results/heuristic/`
row. **A separate measure of wall time is added rather than repurposing the contact count**, see R5.

## R3. The shape of the budget

Three candidates:

1. **Terminate on the k-th contact.** Simple, keeps `EndReason.WallContact` meaningful, and k = 0
   reproduces feature 007 exactly, which is what makes the comparison honest.
2. **Never terminate on contact**, and let the stall timeout and the step limit end episodes.
   Cleanest hypothesis test, but removes the only pressure against sustained barrier use, and R2
   says the contact count will not even show it happening.
3. **Terminate on cumulative wall time.** Directly targets grinding, but needs contact-state
   tracking the sensor does not have, and couples the feature to a new measurement in the same
   change.

**Decision**: option 1, with the budget as a serialized field, defaulting to a small number. Option
2 is reachable by setting the budget high and is worth one run if option 1 is ambiguous. Option 3 is
out of scope: it changes the sensor and the terminal at once, which is two changes.

## R4. Whether the car can reverse off a barrier at all

**This is an assumption the feature rests on and it has never been measured.** If a car that touches
a barrier comes to rest against it and cannot recover, the budget buys nothing: the episode trades a
`WallContact` ending for a `Stalled` one, sixty seconds later, and every such episode costs sixty
seconds of wall clock instead of seven.

Feature 006's held-out runs recorded **zero** wall contacts, so there is no existing evidence either
way. Feature 007's ended at the first contact by construction, so there is none there either.

**Decision**: measure it before choosing the budget. A scripted probe drives the car into a barrier
at a representative speed and angle, then applies reverse, and records whether the car separates and
within how many physics steps. This is cheap, needs no training run, and its answer decides whether
the feature is worth running at all.

## R5. The grinding risk, and how to measure it

The progress term pays for arc position along the marker chain and is indifferent to how the car got
there. Sliding along a barrier towards the next marker earns exactly what driving there cleanly
earns. Under the current terminal this strategy is unavailable, because the first contact ends the
episode. **Lifting the terminal makes it available for the first time.**

R2 rules out the obvious detector: the contact count will read 1 for an entire grind.

Candidate measures:

- **Wall time**, the number of physics steps spent in contact. Needs `OnCollisionStay` on the
  sensor, which is a change to a component behind committed baselines.
- **Contacts per marker**, entries divided by markers earned. Catches repeated bouncing, misses a
  single sustained grind.
- **Lateral clearance**, the minimum ray distance in the side of the fan, averaged over the episode.
  **Needs no new collision handling**: `CarAgent.RayDistancesNorm` already exists and is already
  sampled every physics step. A policy grinding a barrier holds a side ray near zero for a long
  run of steps, and a policy driving cleanly does not.

**Decision**: report **mean minimum lateral ray clearance per episode**, computed from the existing
fan, alongside contacts per episode. It costs one accumulator, adds no collision handling, and does
not touch the sensor. If it shows grinding, the follow-up is a wall-time terminal, which is R3's
option 3 and its own feature.

## R6. Episode length, throughput, and the accounting defect

Surviving contacts makes episodes longer. Three consequences, none of them optional to check:

- **Throughput falls** in steps per second terms or at least changes, and feature 007 measured 927
  steps/s on the candidate. It must be re-measured, not assumed, which is SC-009.
- **Episodes per summary falls**, which changes the size of the episode-set mismatch feature 007
  measured at about 19 per cent but does not fix it. Any FR-010 style check in this feature inherits
  that defect and must say so rather than re-deriving it.
- **The stall timeout becomes load bearing.** At 60 seconds and 50 Hz that is 3,000 physics steps
  against feature 007's mean episode of about 1,676 charges. A policy that survives contacts and
  crawls could sit in episodes several times longer than any measured so far.

**Decision**: report throughput and mean episode length on every run, and read the stall share as
carefully as the wall share.

## R7. The gate

Feature 007 measured a gate of **0.035** on markers per episode from three identical spread runs,
and 1.4987 is the number to beat. The reward table does not change in this feature, so the metric's
scale does not change either.

**What does change is the dynamics**, and feature 007's own spread document warns that a candidate
which genuinely starts to learn may be noisier than the runs the gate was measured on.

**Decision**: reuse 0.035, state the caveat on every comparison, and treat a result landing near it
as earning a fresh three-run spread rather than a verdict. That is the assumption already recorded
in the spec, and the fresh spread is the first thing to spend 2.4 hours on if the answer is
ambiguous.

## R8. What a negative looks like, written before the run

- **Markers per episode does not clear 1.4987 + 0.035.** Then surviving contacts is not what was
  stopping the policy, and the terminal is exonerated the way the penalty was in feature 006.
- **Markers rise and laps stay at zero on held-out track.** Then the same shape as feature 007
  repeats one level up, and the next constraint is whatever the end-reason mix now says it is.
- **Wall contacts per episode rises sharply while lateral clearance falls.** Then the policy found
  the grinding strategy R5 names, the number rose for a reason nobody wants, and the finding is that
  the terminal was load bearing against a degenerate solution rather than against learning.

All three are publishable and all three are recorded before the run.
