# Contract: track file schema

The committed handoff between the Python generator and the Unity builder. One file per accepted
seed, at `unity/SelfDrivingSim/Assets/Tracks/seed_<seed>.json`.

This file is the reason Unity contains no statistics. Everything that needed proving was proved
in Python and written here; Unity reads numbers and places objects.

## Version

`schema_version` is currently **1**. A loader that does not recognise the version **must fail
loudly** rather than read the fields it happens to understand. A track built from a
half-understood file looks fine and is wrong.

## Shape

```jsonc
{
  "schema_version": 1,
  "seed": 7,
  "generated_utc": "2026-07-29T12:00:00Z",

  // Enough to regenerate this track from scratch without trusting the sampled points below.
  "generator": {
    "form": "polar_harmonic",
    "r0_m": 30.0,
    "harmonics": [2, 3, 4, 5],
    "amplitude": 0.53,
    "phases": [1.204, 3.881, 0.472, 5.109]
  },

  // The profile this track was validated against. A track is only meaningful for one car.
  "vehicle_profile": {
    "wheelbase_m": 2.5,
    "steer_max_deg": 25.0,
    "radius_margin": 1.3,
    "r_min_m": 5.361,
    "r_floor_m": 6.969,
    "max_required_steer": 0.789
  },

  "width_m": 6.0,
  "total_length_m": 194.3,

  // Ordered, closed. The last point does NOT repeat the first; closure is implied.
  "centre_line": [
    { "x": 30.0, "y": 0.0, "s": 0.0, "radius_m": 24.11, "required_steer": 0.237 }
    // ... SAMPLES_PER_TRACK entries
  ],

  // Ordered by arc length. Index is the progress order.
  "checkpoints": [
    { "index": 0, "x": 30.0, "y": 0.0, "forward_x": 0.0, "forward_y": 1.0, "s": 0.0 }
    // ... N_CHECKPOINTS entries
  ],

  "geometry_report": {
    "min_radius_m": 8.94,
    "r_floor_m": 6.969,
    "radius_ok": true,
    "self_intersects": false,
    "min_separation_m": 21.7,
    "separation_ok": true
  },

  "match_report": {
    "scope": "seed 7",
    "distance": 0.041,
    "threshold": 0.05,
    "accepted": true,
    "scales": {
      "self_consistency": 0.0231,
      "structureless": 0.1047,
      "human_to_human": 0.2635
    },
    "reference": "M1 |steering|, conditional on non-zero",
    "n_track_samples": 2000,
    "n_reference_samples": 2193,
    "note": "No generated track can demand steering above 0.789, so the human distribution is covered to its 97.40th percentile and no further. A harmonic loop contains no straight sections, so this comparison is against the conditional distribution."
  },

  // Constitution Principle IX: every distribution this project touches reports all of these.
  "required_steer_descriptives": {
    "n": 2000,
    "mean": 0.312,
    "variance": 0.0281,
    "std": 0.1676,
    "min": 0.041,
    "max": 0.734,
    "histogram": { "bin_edges": [0.0], "relative_frequency": [0.0] }
  }
}
```

## Field rules

- **`generator` is not decoration.** It carries enough to rebuild the centre line independently.
  A reviewer who does not trust the sampled points can regenerate them and compare. This is what
  makes the committed file auditable rather than merely convenient.
- **`vehicle_profile` travels with the track.** A track validated for one car is not valid for
  another. The Unity builder compares this block against its own profile and refuses to build on
  a mismatch.
- **`centre_line` does not repeat its first point.** Closure is a property of the form, and a
  duplicated endpoint would produce a zero-length segment in every downstream consumer.
- **`s` is arc length**, so checkpoint spacing and separation checks operate on real distance
  rather than on the sample parameter. Spacing by parameter would bunch markers in tight corners.
- **`required_steer` is stored per point**, unsigned. It is derived from `radius_m` and the
  profile, and is stored so Unity can display it during a keyboard drive without reimplementing
  the bicycle model.
- **Both reports are carried inside the file.** Storing them separately invites a track and its
  verdict drifting apart. A file that claims `radius_ok: true` while containing a corner below the
  floor is a contradiction any test can catch.
- **`match_report` contains no p-value.** By contract. See FR-019 and research C8.
- **`match_report.scales` carries the three measured reference distances** from research C15, so a
  reader can judge the distance without holding the derivation in their head. A distance of 0.041
  is only meaningful next to the 0.0231 floor and the 0.1047 structureless baseline.
- **`required_steer_descriptives` is mandatory, not optional.** Constitution Principle IX requires
  sample size, mean, variance, min, max and a relative-frequency histogram for every distribution
  the project touches. The values shown above are illustrative, like every other number in this
  example. A file missing this block fails the loader.

## Failure modes the loader must handle

| Condition | Required behaviour |
|---|---|
| Unknown `schema_version` | Refuse to load, name the version found and the version expected |
| `vehicle_profile` differs from the scene's profile | Refuse to build, name the differing field |
| `geometry_report.radius_ok` is false | Refuse to build. Such a file should not exist; if one does, something wrote it that should not have |
| `centre_line` shorter than two points | Refuse to build |
| `checkpoints` not monotonic in `s` | Refuse to build. Progress ordering is meaningless otherwise |
| `required_steer_descriptives` missing or incomplete | Refuse to load, name the missing field. Principle IX is not optional |
| First and last centre-line points identical | Refuse to build, since closure must be implied and not duplicated |

Every one of these is a refusal, not a warning. A track that builds despite failing a check is
worse than no track, because the failure then surfaces as an unexplained flat reward curve six
hours into a training run.

## What is deliberately absent

- No reward values, no episode configuration, no training hyperparameters. Those belong to M3, and
  putting them here would mean the first tuning pass modifies files this feature claims to have
  verified.
- No visual material, no textures, no colours. The agent senses distance, not appearance.
- No absolute speed in dataset units, anywhere. Speeds are simulation quantities; comparisons are
  normalised (research C3).
