# Research: generalisation beyond the ten held-out tracks

Every finding here was measured against the repository or the running editor on 2026-09-02, before
any code was written. Where a number is quoted from an earlier feature it says which.

## R1. How many new seeds, and which range

Seeds **2001 to 2040**, requested 40.

- Disjoint from `TRAIN_SEEDS = range(1, 41)` and `EVAL_SEEDS = range(1001, 1011)` by construction,
  and FR-001 requires that be checked rather than trusted to the numbering.
- The training batch accepted **34 of 40, a rate of 0.85**, recorded in
  `results/tracks/seed_split.json`. At the same rate 40 requested gives roughly **34 accepted**.
- **Why not ten, matching the held-out set.** The held-out set's ten runs is what makes its
  100 per cent uninformative about the next track: a Wilson interval on 10 of 10 runs from 0.72 to
  1.00. Thirty-four of thirty-four narrows that to about 0.90 to 1.00. The sweep is cheap enough
  that the sample size is a free choice, so it should not be the limiting factor in what the result
  can say.

## R2. The sweep costs about eleven minutes, so cost is not a constraint

Feature 009's held-out runs took **62.4 s of simulated time** each at `timeScale = 4`, which is
about 15.6 s of wall clock. Thirty-four runs is roughly **9 minutes**, plus editor startup. The
constraint on this feature is care, not compute.

## R3. The evaluation scene currently holds the wrong model, with the wrong inference mode

Read out of `Assets/Scenes/Evaluation.unity` rather than assumed:

| field | current value | what M3 was closed on |
|---|---|---|
| `m_Model` | guid `2ae226b1...`, which resolves to `ppo_car_009_bc_s13-5000050.onnx` | seed 42's `ppo_car_009_bc-5000101.onnx` |
| `m_DeterministicInference` | `0`, meaning off | on |

**This is left over from the last sweep and it is not a mistake anybody made.** It is the scene
being a mutable configuration whose state is invisible in the results. Running this feature's sweep
without resetting those two fields would produce a complete, plausible, wrong answer: seed 13's
policy sampling its actions, reported as seed 42's policy driving deterministically.

## R4. The run record's controller column is a hand-typed string, and its own tooltip says so

`DrivingAgent.runId` is a `[SerializeField] private string`, written into `RunRecord.Controller`
verbatim. Its tooltip reads:

> Set it to the run id whose .onnx is on BehaviorParameters, and nothing checks the two agree, so
> they are worth checking by eye.

**This is feature 010's `sourceLabel` trap in a second place.** There, a serialised literal stamped
all 60 traces with `ppo_car_spread_a_sampling`, and M5 had to reconstruct the mapping by matching
run durations because the label could not be trusted. The fix there was to stop serialising the
label and derive it from the caller. The same fix applies here, and SC-003 requires it: a report
that claims "the same policy" while the evidence is a typed string has asserted rather than checked.

`BehaviorParameters` exposes both facts at runtime, so the label can be derived from the model asset
actually loaded and the inference mode actually in effect.

## R5. `SweepRunner` reads two halves of the split file and refuses anything else

`LoadSeeds` hardcodes `results/tracks/seed_split.json` and selects
`seedSet == SeedSet.Train ? file.train : file.eval`. The hardcoding is deliberate and documented:

> A list typed into a scene is a copy of a decision recorded somewhere else, and the two drift
> silently.

So the third set belongs **in the same file as a third half**, not in a second file and not in an
Inspector list. That needs a third `SeedSet` enum value and a third field on `SeedSplitFile`.

`LoadSeeds` also already warns when the evaluation set is swept. FR-007 asks for the same warning on
the new set, and for the same reason.

## R6. A percentage is not a result at these sample sizes, and the normal interval is degenerate

Both sets are expected to sit at or near 100 per cent completion. At `p = 1` the textbook normal
approximation gives a half-width of zero and reports the interval `[1.00, 1.00]`, which claims
certainty from a finite sample. **The Wilson score interval is used instead**, which stays bounded
away from a point at the extremes and is the standard remedy for exactly this case.

Worked, so the choice is visible rather than asserted:

| runs | successes | normal interval | **Wilson interval** |
|---|---|---|---|
| 10 | 10 | [1.00, 1.00] | **[0.72, 1.00]** |
| 34 | 34 | [1.00, 1.00] | **[0.90, 1.00]** |
| 34 | 31 | [0.81, 1.00] | **[0.77, 0.97]** |

The third row is the one that matters: a drop of three runs out of thirty-four still has an interval
that overlaps the held-out result, so it would **not** be evidence that generalisation failed. That
comparison has to be made against the interval, which is what FR-008 exists to force.

## R7. What a failure would mean, decided before the numbers exist

Pre-registered so the reading is not chosen after seeing the result.

- **All 34 complete.** The policy drives this distribution of tracks, not only the ten it was
  reported on. M3's limit is closed.
- **The intervals overlap.** The evidence does not separate the two sets. Reported as "no
  difference detected at this sample size", never as "generalisation confirmed".
- **The new set is clearly worse and the intervals do not overlap.** A real generalisation gap, and
  the honest reading is that the held-out ten were easier or luckier than the generator's typical
  output. **M3's verdict is not edited**, because M3 was closed on the evidence it named. This
  becomes a recorded limit beside it, in the same way M3's own closeout recorded this one.
- **End reasons are read, not just the rate.** A wall contact, a time limit and a no-progress stall
  are three different failures, and averaging them into "did not finish" would discard the finding.
