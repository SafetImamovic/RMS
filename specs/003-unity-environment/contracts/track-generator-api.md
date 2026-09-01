# Contract: `python/track` generator API

Extends the M1 contract (`specs/001-dataset-eda/contracts/eda-api.md`) and the feature 002
contract, both of which remain binding and unmodified. Signatures below are the contract;
internals may change as long as these hold.

Every function is pure except `export_track` and `generate_batch`, which write only under
`unity/SelfDrivingSim/Assets/Tracks/` and `results/tracks/`.

## config.py

All constants named, none inline. Values and their derivations are in
[research.md](../research.md), summary table at the end.

```python
# Vehicle (research C1, C2)
WHEELBASE_M: float = 2.5
STEER_MAX_DEG: float = 25.0
RADIUS_MARGIN: float = 1.3          # equals 21.1% steering reserve; see vehicle.max_required_steer
V_MAX_MS: float = 10.0              # playability only, never enters a comparison
DATASET_SPEED_P99: float = 17.49    # from results/eda/m1_stats.json

# Generator (research C6)
TRACK_R0_M: float = 30.0
HARMONICS: tuple[int, ...] = (2, 3, 4, 5)
AMPLITUDE_RANGE: tuple[float, float] = (0.40, 0.70)
SAMPLES_PER_TRACK: int = 2000

# Geometry (research C10, C12)
TRACK_WIDTH_M: float = 6.0
MIN_SEPARATION_M: float = 12.0      # 2 x width
N_CHECKPOINTS: int = 24
START_LATERAL_M: float = 1.5
START_YAW_DEG: float = 10.0

# Sensing (research C11)
RAY_COUNT: int = 13
RAY_FOV_DEG: float = 180.0
RAY_LENGTH_M: float = 20.0

# Comparison (research C8, C14, C15)
COMPARE_HZ: float = 14.08
MATCH_DISTANCE_THRESHOLD: float = 0.05   # W1, derived in C15; must stay below 0.1047
W1_SELF_CONSISTENCY: float = 0.0231      # track1 halves against each other, the floor
W1_STRUCTURELESS: float = 0.1047         # track1 against uniform, the discrimination ceiling
W1_HUMAN_TO_HUMAN: float = 0.2635        # track1 against track2, reported for scale

# Seeds (research C13)
TRAIN_SEEDS: range = range(1, 41)
EVAL_SEEDS: range = range(1001, 1011)
```

**Guarantee**: this module adds constants only. It never imports from `python/eda`, so nothing
here can change an M1 number.

## vehicle.py

```python
def build_profile() -> VehicleProfile:
    """The single VehicleProfile, with r_min, r_floor and max_required_steer derived."""

def radius_for_steering(steer_norm: float, profile: VehicleProfile) -> float:
    """Bicycle model: R = L / tan(steer_norm * steer_max). Low-speed geometry."""

def steering_for_radius(radius_m: float, profile: VehicleProfile) -> float:
    """Inverse of the above, normalised to [0, 1]."""

def stopping_distance_m(v_ms: float, decel_ms2: float) -> float:
    """v^2 / (2a). Used to derive the sensing range, not to bound the vehicle."""

def normalise_speed(values, p99: float): ...
    """Divide by the given 99th percentile. The only sanctioned way to compare speeds."""
```

**Contract guarantees**

- `radius_for_steering` and `steering_for_radius` are exact inverses within floating tolerance.
- `profile.max_required_steer` is independent of `wheelbase_m`. A test asserts this across a range
  of wheelbases, because the property is the reason the margin is a meaningful knob (research C2).
- No function converts a dataset speed into a physical unit. There is no such function to call.

## generator.py

```python
def draw_parameters(seed: int) -> TrackSeed:
    """Seed to amplitude and phases. Uses a seeded generator instance, never global state."""

def centre_line(params: TrackSeed) -> CentreLine:
    """Sample r(theta) = R0 * (1 + sum a_k sin(k theta + phi_k)) and its curvature."""
```

**Contract guarantees**

- `draw_parameters(s)` returns identical values on every call and in every process.
- `centre_line` closes by construction. No endpoint adjustment exists in this module.
- Curvature comes from the closed-form polar expression, not from finite differences, because the
  accept-or-reject decision is binary and must not depend on differencing error (research C7).

## geometry.py

```python
def check_geometry(line: CentreLine, profile: VehicleProfile) -> GeometryReport:
    """Minimum radius against the floor, self-intersection, and minimum separation."""

def place_checkpoints(line: CentreLine, n: int) -> list[Checkpoint]:
    """Evenly spaced by ARC LENGTH, not by the sample parameter."""
```

**Contract guarantees**

- `check_geometry` reports `r_floor_m` alongside the verdict, so a reader can see what the test
  was against rather than trusting it.
- Separation is measured only between points more than `2 * TRACK_WIDTH_M` apart along the arc, so
  neighbouring samples cannot trivially fail it.
- `place_checkpoints` spaces by arc length. Spacing by theta would bunch markers where the radius
  is small, which is exactly where they matter most.

## matching.py

```python
def required_steering(line: CentreLine, profile: VehicleProfile) -> SteeringDemand: ...

def describe(values: np.ndarray) -> Descriptives:
    """n, mean, variance, std, min, max, and the histogram, for any distribution
    this feature touches. Constitution Principle IX requires all of them."""

def reference_distribution() -> np.ndarray:
    """The measured |steering| from M1, CONDITIONAL on being non-zero (research C9)."""

def match_distance(demand: SteeringDemand, reference: np.ndarray) -> MatchReport:
    """Wasserstein-1 distance and a threshold decision. Never a hypothesis test."""
```

**Contract guarantees**

- `MatchReport` contains **no p-value field**, and no function in this module returns one. A large
  p-value is not evidence of agreement. Reporting the match as a test would repeat the exact error
  that feature 002 was written to correct (FR-019).
- `reference_distribution` reads the dataset through the existing M1 loader and never writes.
- `MatchReport.note` states both known limitations: the truncation at `max_required_steer`, and
  the absence of straight sections.
- `SteeringDemand` carries a full `Descriptives` block, not percentiles alone. Constitution
  Principle IX requires sample size, mean, variance, min, max and a relative-frequency histogram
  for **every** distribution the project touches, and the required-steering distribution is a new
  one introduced by this feature. Percentiles alone would not satisfy it.
- `MatchReport` reports the distance against all three measured scales from research C15, not
  against the threshold alone. A distance of 0.06 means something different when the floor is
  0.0231 and the structureless baseline is 0.1047, and a reader cannot judge it otherwise.

## export.py

```python
def export_track(seed: int, out_dir: Path = TRACKS_DIR) -> Path:
    """Generate, validate, and write one track file. Raises if the seed is rejected."""

def generate_batch(seeds: Iterable[int], out_dir: Path = TRACKS_DIR) -> BatchReport:
    """Export every accepted seed; record every rejected one with its reason.

    Also pools the required steering across every accepted track and produces one
    batch-scope MatchReport. That pooled report, not the per-seed ones, is what
    SC-010 is judged on.
    """
```

**Contract guarantees**

- A rejected seed produces **no** track file and **one** recorded rejection. It is never retried
  with adjusted parameters (research C7).
- `BatchReport` reports the acceptance rate. SC-011 requires at least 50 percent, and a lower rate
  is treated as a design finding about the radius floor conflicting with the statistical target,
  not as something to tune away.
- `BatchReport` carries a **pooled** `MatchReport` with `scope` naming the batch, computed over the
  required steering of every accepted track together. SC-010 asks whether a batch of at least 20
  accepted seeds matches the human distribution, which no per-seed report answers. A batch of 20
  tracks that each miss in a different direction can pool to a good match, and a batch that each
  miss the same way cannot; only the pooled figure distinguishes them.
- `BatchReport` names the pooled sample count, so a batch smaller than the 20 seeds SC-010 requires
  cannot be quoted as if it satisfied it.
- Two runs over the same seed list produce byte-identical files.
- Nothing outside `out_dir` is written.

## Test contract

Each check needs both directions of evidence, the same rule as feature 002.

| Family | Must reject or detect | Must accept or stay silent on |
|---|---|---|
| radius floor | a hand-built curve with a corner below the floor | a curve whose tightest corner is just above it |
| closure | an open polyline | every generated centre line |
| self-intersection | a hand-built figure of eight | a generated loop |
| separation | a loop whose two sides pass within 3 m | a generated loop |
| determinism | two different seeds giving the same geometry | the same seed giving different geometry on re-run |
| steering inverse | a radius outside the achievable range | round-tripping every value in `[0, 1]` |
| wheelbase independence | a `max_required_steer` that moves with wheelbase | it staying fixed across 1.5 m to 4.0 m |
| match distance | a uniform demand distribution scoring 0.1047, above the 0.05 threshold | the reference scoring zero against itself, and its two halves scoring 0.0231, below the threshold |
| pooled batch | a batch of fewer than 20 accepted seeds quoted against SC-010 | a batch of 20 or more producing one `MatchReport` with batch scope |
| descriptives | a `SteeringDemand` missing any of n, mean, variance, min, max | all six present for every distribution the feature touches |

The right-hand column is not optional. A generator that rejects every seed passes every
left-hand test and is useless.

## Unity side contract

`TrackBuilder` reads a track file and builds geometry. It performs no statistics and draws no
random numbers. Its EditMode test rebuilds the geometry from a committed file and re-measures the
minimum radius and the checkpoint order, asserting they match what the file claims. If Unity and
Python disagree about a track, the test says so rather than the agent discovering it during
training.
