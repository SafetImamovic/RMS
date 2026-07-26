# Phase 1 Data Model: Data Authenticity & Integrity Checks

Entities are frozen dataclasses (same convention as M1's `TrackDataset`, `IntegrityReport`,
`ColumnFingerprint`). All are pure values — computing one never writes to disk.

---

## `RecordingSession`

One contiguous run of driving-log records. The unit over which time is meaningful (research A1).

| Field | Type | Meaning |
|---|---|---|
| `session_id` | `str` | Derived from the image-path prefix (`track1data`, `track2data`) |
| `start_index` | `int` | First row index of the session within the source frame |
| `end_index` | `int` | Last row index, inclusive |
| `n_rows` | `int` | Number of records |
| `start_time` | `datetime` | Capture time of the first frame |
| `end_time` | `datetime` | Capture time of the last frame |

**Rules**

- Sessions are derived, never assumed. A source with one session (track1, track2) yields one;
  the combined source yields two.
- Sessions are contiguous and non-overlapping in row index, but **may overlap or invert in
  time** — track2 was recorded earlier in the day than track1, so `start_time` is not ordered
  by `start_index` in the combined source. Nothing may assume otherwise.

---

## `TimelineReport`

Per-session verdict on recording continuity (FR-001..FR-003).

| Field | Type | Meaning |
|---|---|---|
| `session_id` | `str` | |
| `n_rows` | `int` | |
| `n_unparseable` | `int` | Rows whose filename yielded no timestamp |
| `is_monotonic` | `bool` | Strictly increasing capture times |
| `n_order_violations` | `int` | Count of non-increasing steps |
| `median_interval_s` | `float` | Median Δt |
| `implied_fps` | `float` | `1 / median_interval_s` |
| `gap_threshold_s` | `float` | The threshold actually used, `GAP_FACTOR × median` |
| `n_gaps` | `int` | Steps exceeding `gap_threshold_s` |
| `gap_tiers` | `dict[str, int]` | Counts at `>2x`, `>5x`, `>1s` — shows the whole tail |
| `largest_gap_s` | `float` | |
| `start_time`, `end_time` | `datetime` | |

**Rules**

- Computed **per session only**. Never across a session boundary (research A1).
- `n_unparseable > 0` is surfaced, never silently dropped (FR-001).
- A clean result is still a result — reported explicitly, not omitted (spec edge case).

---

## `DuplicationReport`

Three duplicate classes counted separately, because each implies a different manipulation
(research A8, FR-004).

| Field | Type | Meaning |
|---|---|---|
| `source` | `str` | Track name |
| `n_exact_duplicate_rows` | `int` | Whole row repeated — row-copying |
| `n_duplicate_image_refs` | `int` | Same center-image path appearing twice — frame reuse |
| `n_duplicate_measurement_tuples` | `int` | Same (steering, throttle, brake, speed), different image |
| `duplicate_row_examples` | `list[int]` | Row indices, capped, for inspection |

**Rules**

- The three counts are never summed into a single "duplicates" figure. The third is expected
  and benign given a 41-level steering lattice; merging them manufactures a false alarm.

---

## `GranularityProfile`

Per numeric column: how finely the value was actually recorded (FR-006..FR-008).

| Field | Type | Meaning |
|---|---|---|
| `column` | `str` | |
| `n_distinct` | `int` | Distinct observed values |
| `classification` | `"discrete" \| "continuous" \| "constant"` | |
| `is_lattice` | `bool` | All values are integer multiples of `spacing` within tolerance |
| `spacing` | `float \| None` | Lattice step, when `is_lattice` |
| `support` | `list[float] \| None` | Full lattice support from min to max |
| `unobserved_support` | `list[float]` | Support points never observed on this track |
| `off_lattice_values` | `list[float]` | Values not on the lattice — the strongest tampering signal |
| `tolerance` | `float` | The tolerance used, reported (FR-008) |
| `evidence` | `str` | One-line plain-language justification |

**Rules**

- `classification == "constant"` when `n_distinct == 1`. Statistics requiring variation must
  not be computed on it — reported as a finding instead (FR-013).
- `support` spans observed min..max on the lattice, so a never-observed interior point appears
  in `unobserved_support` rather than silently shrinking the support.
- `off_lattice_values` non-empty is a finding in its own right, regardless of any test.

---

## `HypothesisTestResult`

One named test. The shape every statistical claim in this feature must take (FR-009..FR-012,
FR-014).

| Field | Type | Meaning |
|---|---|---|
| `test_id` | `str` | `T1_uniform_gof`, `T2_symmetry`, `T3_homogeneity` |
| `null_hypothesis` | `str` | Stated in plain language, not implied |
| `scope` | `str` | Which track / which pair |
| `statistic` | `float` | χ² value |
| `dof` | `int` | **After** any pooling (FR-010) |
| `critical_value` | `float` | At α |
| `p_value` | `float` | |
| `alpha` | `float` | |
| `reject_null` | `bool` | |
| `n_categories_pooled` | `int` | How many low-expectation levels were merged |
| `interpretation` | `str` | Plain language: what rejecting/not rejecting *means here* |

**Rules**

- `dof` reports the value actually used after pooling, never the naive `k − 1`.
- Pooling is symmetric from the tails inward, so it cannot itself induce asymmetry in T2
  (research A5).
- `interpretation` must state the tampering-relevant meaning — for T1, that failing to reject
  would suggest a uniform random generator produced the column.

---

## `PlausibilityReport`

Physical-plausibility screen on per-frame speed change (FR-005, research A7).

| Field | Type | Meaning |
|---|---|---|
| `session_id` | `str` | |
| `median_accel` | `float` | Median implied `Δspeed / Δt` |
| `mad_accel` | `float` | Median absolute deviation |
| `max_abs_accel` | `float` | |
| `outlier_threshold` | `float` | `median + MAD_K × MAD` |
| `n_outliers` | `int` | |
| `outlier_indices` | `list[int]` | Capped, for inspection |
| `units_note` | `str` | States that speed units are undocumented, so the criterion is relative |

**Rules**

- Robust (MAD-based), never standard-deviation-based: injected jumps inflate σ enough to hide
  themselves (research A7).
- Never asserts an absolute physical bound. Claiming "under 1 g" would require a unit
  assumption the dataset does not document.

---

## `Verdict`

The classification attached to any finding (FR-015, FR-016, research A6).

| Field | Type | Meaning |
|---|---|---|
| `finding_id` | `str` | |
| `summary` | `str` | What was observed |
| `classification` | `"explainable" \| "unexplained"` | |
| `mechanism` | `str \| None` | Required when `explainable`; names the cause |
| `downstream_consequence` | `str \| None` | Where it still bites a later milestone |
| `mitigation` | `str \| None` | What to do about it |

**Rules**

- `classification == "explainable"` **requires** a non-empty `mechanism`. An explainable verdict
  without a named cause is just an assertion.
- Explainable and harmful are independent: the track1 left bias is explainable *and* carries a
  downstream consequence for M4.

---

## `AuthenticityOutput`

The machine-readable top-level result written to `results/eda/authenticity_stats.json`
(FR-017).

| Field | Type |
|---|---|
| `sessions` | `list[RecordingSession]` |
| `timelines` | `list[TimelineReport]` |
| `duplications` | `list[DuplicationReport]` |
| `granularity` | `dict[str, list[GranularityProfile]]` (per track) |
| `plausibility` | `list[PlausibilityReport]` |
| `tests` | `list[HypothesisTestResult]` |
| `verdicts` | `list[Verdict]` |
| `calibration_unchanged` | `bool` |
| `calibration_note` | `str` |
| `seed`, `alpha`, `lattice_tolerance` | `int`, `float`, `float` |

**Rules**

- Serialisable to JSON with no loss; `datetime` fields as ISO-8601 strings.
- `calibration_unchanged` answers FR-018 explicitly rather than leaving it inferred.
- Written only under `results/`; M1's files are never opened for writing.
- Two runs under `SEED=42` produce byte-identical JSON (FR-022, SC-011).
