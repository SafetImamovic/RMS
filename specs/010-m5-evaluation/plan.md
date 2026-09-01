# Plan: M5, evaluation and comparison

Written 2026-09-01 against `research.md` of the same date. Every decision below either cites a
research finding or is marked as an owner call.

## The decision that shapes the feature

**`|delta steering|` is the primary comparison axis. Steering level is reported as a secondary with
its artefact quantified beside it.** Owner call, 2026-09-01, taken on R5.

R5 measured the problem rather than assuming it: the human is at exact zero on **79.3 per cent** of
track1 steps, the agent is within 0.025 of zero on **2.5 per cent**, and the agent steers left on
**87.6 per cent** because the generated loop runs one way. A marginal steering comparison therefore
reports track geometry with a confident test statistic attached, which is the exact artefact both
notes in `DESIGN.md` 7 exist to prevent.

`|delta steering|` is chosen because it depends far less on where the track happens to turn, it is
already computed for every driver by `python/rl/report.py`, and feature 005's
`results/heuristic/us4_steering.md` already compares the heuristic to BC on it. Curvature
conditioning was rejected: the human dataset carries no curvature signal, so the human column could
not be built.

**The marginal comparison is not dropped.** It is reported with the near-zero share and the
left-turn share printed in the same table, so a reader cannot take the divergence for a statement
about driving style. That obligation is SC-004's "stating in the result why the marginal comparison
stands anyway", answered with numbers rather than prose.

## Sequence

### Phase 1: make the traces addressable (US1 groundwork)

The 60 traces from feature 009 exist but their `source` column is a stale literal (R3). Nothing
downstream can be trusted until selection is deterministic and recorded.

1. Fix `DriveLogger.sourceLabel` in `Evaluation.unity` so future traces are self-describing. Do not
   rewrite the existing 60; their content is fine and rewriting recorded data to fix a label is
   worse than mapping it.
2. Write `results/rl/trace_manifest.json`: for each of the six sweeps, the run id, the inference
   mode, the eval CSV, and the ten trace filenames in seed order. Committed, so the mapping is
   auditable without re-deriving it from timestamps.
3. A test asserting the manifest names ten existing files per sweep and that no file appears twice.

### Phase 2: the fourth column and the missing test (US2)

4. Add a two-sample **KS test** to `python/rl/report.py`. It is the only statistic in
   `DESIGN.md` 7.1 that exists nowhere in the repository (R2).
5. Reuse, do not reimplement: `lattice_levels`, `quantise_to_lattice` and `KL_SMOOTHING` from
   `python/bc/`, `chi2_homogeneity` from `python/eda/authenticity.py`. If a helper has to move to be
   shared, move it and leave the callers working.
6. Build the four driver columns: RL 009, BC, heuristic, human. Each carries descriptive statistics
   for steering, speed and `|delta steering|`: n, mean, variance, min, max, relative-frequency
   histogram, as `DESIGN.md` 7.1 lists them.
7. **One RL column, not three.** The spread's three checkpoints agree to within a lap on held-out
   track, so three columns would imply three drivers. Seed 42 is the named column because it is the
   one the whole feature was measured on; a line states that seeds 7 and 13 agree, with their
   numbers.

### Phase 3: the comparison itself (US2)

8. `|delta steering|`, each driver against human: KS with p-value, and the descriptive pair.
9. Steering level on the lattice, each driver against human: KL with the smoothing stated, plus
   chi-square homogeneity, plus **the near-zero share and left-turn share in the same table**.
10. Report the unquantised steering comparison too, once, to show the size of the resolution
    artefact that quantisation removes. SC-002 asks for exactly this.
11. Every cell of the `DESIGN.md` 7 table is a measured number or an explicit absence with its
    cause. BC has no lap completion and no lap time because it does not drive (R6).

### Phase 4: figures and the recipe (US3, US4)

12. Plots into `results/plots`, each produced by a committed script: overlaid `|delta steering|`
    distributions, overlaid lattice histograms, and a per-driver summary figure.
13. The model taxonomy paragraph from `DESIGN.md` 7.1, in the lecture's terminology.
14. Run the README recipe from a clean clone and fix what breaks. Anything that only works because
    of state on this machine is found by running it, not by reading it.

## Two repairs this feature owes, both found in R4

- `report.py` prints `markers 72.00 of 24 (300.0% of a lap)`. `markers_possible` must account for
  `lapsToComplete`.
- `report.py`'s prose was written when the learned column always lost. The 009 policy is **steadier
  than the scripted driver**, 0.03208 against 0.04994, so the "LOSS" framing needs to become a
  comparison that can report either direction.

## Out of scope, restated from the spec

No further M3 work. No attempt to make BC drive in Unity. The 5M sighted probe belongs to M3's
record. The per-episode records debt stays open.

## Risks

- **The KS test on 31,202 against 10,615 samples will reject almost any null.** At these sample
  sizes a p-value is close to a formality, so the effect size is reported beside it and the
  conclusion is never drawn from the p-value alone.
- **`|delta steering|` is sampling-rate dependent, and R7 measured how badly.** At the raw 50 Hz
  trace rate **67.1 per cent of differences are structurally zero**, because the action is held for
  four physics steps, and the driver reads 3.8 times smoother than it is. The repository already
  solves this: `COMPARE_HZ = 14.08` in `python/track/config.py`, with `steering_series` resampling
  per run and differencing after resampling. **The risk is therefore not the artefact but
  reimplementing around it.** `|delta steering|` is computed only through `steering_series`, never
  from a raw trace, and the rate is named wherever the figure appears.
