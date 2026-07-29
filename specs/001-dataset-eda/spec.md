# Feature Specification: Dataset EDA (M1)

**Feature Branch**: `001-dataset-eda`
**Created**: 2026-07-23
**Status**: Draft
**Input**: User description: "M1 dataset EDA - analiza Kaggle Udacity self-driving-car simulator dataseta; verifikovati format, potvrditi kolone iz uzorka, izračunati distribucije, prilagoditi raspodjelu + χ² test, izvesti parametre za Unity (§4.4/§4.5). Fokus = Python analiza; Unity se ne dira."

## User Scenarios & Testing *(mandatory)*

The "user" here is the project author preparing evidence and calibration values for the
rest of the project, and the professor grading the statistical rigor at the defense.

### User Story 1 - Verified dataset format and column identity (Priority: P1)

The author needs to prove - not assume - what the headerless `driving_log.csv` contains,
so every later stage (BC training, calibration, evaluation) builds on a confirmed
foundation. Given the professor's statistics focus, column identity must be established
from the data's own statistical fingerprint, backed by the Udacity-standard convention
and the image filenames.

**Why this priority**: Everything downstream depends on the columns meaning what we think
they mean. A wrong mapping silently corrupts BC labels and all calibration values. This is
the M1 gate - nothing else in M1 is trustworthy until this passes.

**Independent Test**: Run the analysis on the combined dataset; confirm it reports the
7-column mapping (center, left, right, steering, throttle, brake, speed), the integrity
check (rows × 3 == image count), and a per-column statistical fingerprint that justifies
each numeric column's identity. Delivers a defensible "we know our data" statement.

**Acceptance Scenarios**:

1. **Given** the combined `dataset/dataset/` folder, **When** the analysis runs, **Then**
   it reports total row count (~32,443) and confirms `rows × 3 == number of images in IMG/`.
2. **Given** the headerless CSV, **When** columns are profiled, **Then** each numeric
   column is assigned an identity (steering/throttle/brake/speed) with the statistical
   evidence (min, max, % negative, % zero) that distinguishes it.
3. **Given** the Windows-absolute image paths (`Desktop\...\IMG\...`), **When**
   preprocessing runs, **Then** each path resolves to an existing local image file via
   basename + re-root, and a sample of resolved paths is verified to exist on disk.

---

### User Story 2 - Descriptive statistics and distribution characterization (Priority: P1)

The author needs the steering, speed, and Δsteering distributions described with the
statistics the course teaches, and the steering distribution fit to a theoretical
distribution and tested for goodness-of-fit.

**Why this priority**: This is the core statistical deliverable the professor grades, and
it produces the numbers that calibrate the Unity environment. Equal top priority with
Story 1 because M1's whole purpose is these outputs.

**Independent Test**: Run the analysis; confirm it produces, for each of steering, speed,
and Δsteering: sample size, mean, variance/std, min, max, and a relative-frequency
histogram; and for steering, a fitted theoretical distribution with a χ² goodness-of-fit
result (statistic, critical value at α, accept/reject) and a KS cross-check.

**Acceptance Scenarios**:

1. **Given** the confirmed steering column, **When** descriptive statistics are computed,
   **Then** sample size, mean, variance/std, min, and max are reported.
2. **Given** the steering distribution, **When** a candidate theoretical distribution is
   fitted, **Then** a χ² goodness-of-fit test reports the χ² statistic, the critical value
   at a stated α, and an accept/reject decision, with a KS test as a cross-check.
3. **Given** each distribution, **When** results are produced, **Then** a relative-frequency
   histogram overlaid with the fitted theoretical curve is saved as a figure.
4. **Given** the two tracks exist, **When** steering is analyzed, **Then** track1 vs track2
   are compared (they differ: track2 is the harder, wider-steering course).

---

### User Story 3 - Calibration values written back into the design (Priority: P2)

The author needs the concrete numbers M1 produces to flow into the design document, so the
Unity milestone (M2) is built on measured values rather than guesses.

**Why this priority**: Without this, M1's numbers stay stranded in a notebook and M2
re-guesses them. It depends on Stories 1–2 being done, so it is P2.

**Independent Test**: After analysis, confirm `DESIGN.md` §4.4 (steering action range) and
§4.5 (abrupt-Δsteering threshold), plus typical speed range, are updated with values
traceable to the M1 report.

**Acceptance Scenarios**:

1. **Given** the computed steering range and percentiles, **When** the design is updated,
   **Then** §4.4 states a steering angle range derived from the data.
2. **Given** the Δsteering distribution, **When** the design is updated, **Then** §4.5
   states an abrupt-steering threshold derived from a stated percentile of |Δsteering|.
3. **Given** the speed distribution, **When** the design is updated, **Then** a typical
   speed range is recorded for environment tuning.

---

### Edge Cases

- **Constant / dead column**: `brake` is 100% zero on track1. If it is also (near-)constant
  on track2, it carries no information and is documented as excluded from analysis, not
  silently dropped.
- **Missing / unreadable images**: a CSV row whose referenced image does not resolve on
  disk must be detected and reported (count of unresolved rows), not crash the run.
- **Heavy zero-steering peak**: ~79% of steering values are exactly 0 (straight driving).
  A single continuous distribution may fit poorly; the characterization must acknowledge
  the zero-inflated shape rather than forcing a bad fit.
- **Scientific-notation / edge numeric values**: speed values like `1.058134E-05` must
  parse correctly as floats.
- **Combined-vs-per-track double counting**: the combined `dataset/` duplicates track1+track2
  images; the analysis must be explicit about which source it is summarizing to avoid
  double counting.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analysis MUST load the combined dataset (`dataset/dataset/`, ~32,443 rows)
  and also be able to load each track separately (track1, track2) for comparison.
- **FR-002**: The analysis MUST parse the headerless CSV into the 7 columns
  `center, left, right, steering, throttle, brake, speed`.
- **FR-003**: The analysis MUST verify dataset integrity by confirming `rows × 3` equals the
  number of image files in the corresponding `IMG/` folder, and report the result.
- **FR-004**: The analysis MUST resolve Windows-absolute image paths to local files via
  basename extraction + re-rooting, and verify a sample of resolved paths exist on disk.
- **FR-005**: The analysis MUST justify each numeric column's identity from a statistical
  fingerprint (min, max, % negative, % zero), independent of the header-less convention.
- **FR-006**: The analysis MUST compute descriptive statistics (sample size, mean,
  variance/std, min, max) for steering, speed, and Δsteering (successive steering difference).
- **FR-007**: The analysis MUST produce relative-frequency histograms for steering, speed,
  and Δsteering, saved as figures.
- **FR-008**: The analysis MUST fit at least one candidate theoretical distribution to the
  steering data and evaluate the fit with a χ² goodness-of-fit test, reporting the χ²
  statistic, degrees of freedom, critical value at a stated α, and accept/reject decision.
- **FR-009**: The analysis MUST include a Kolmogorov–Smirnov test as a cross-check on the
  steering fit.
- **FR-010**: The analysis MUST compare track1 vs track2 steering distributions.
- **FR-011**: The analysis MUST derive and report: a steering angle range (for §4.4), an
  abrupt-|Δsteering| threshold from a stated percentile (for §4.5), and a typical speed range.
- **FR-012**: The analysis MUST be reproducible: given a fixed random seed, re-running
  produces the same reported numbers, and the code that produced every reported number is
  in the repository.
- **FR-013**: The analysis MUST document any dead/constant column (e.g., brake) and its
  exclusion rationale.
- **FR-014**: The resulting calibration values MUST be written back into `DESIGN.md`
  §4.4/§4.5 (and a typical speed range), traceable to the M1 report.
- **FR-015**: The dataset MUST NOT be committed to git; the analysis reads it from the
  git-ignored `dataset/` location.
- **FR-016**: The EDA notebook MUST be pedagogical and beginner-readable - a step-by-step
  narrative where **every step has a plain-language markdown explanation** before the code,
  and every non-obvious choice (why this distribution, why P95, why α=0.05, why ≥5 per bin)
  is justified inline in one sentence. **No unexplained "arbitrary picks"**: any constant or
  method that could look arbitrary must state why it was chosen, or expose it as a labeled,
  explained parameter. A reader new to statistics must be able to follow the notebook top to
  bottom and understand *what* each cell does and *why*.
- **FR-017**: The EDA notebook MUST be **highly visual** - every numeric finding is
  accompanied by a plot wherever a plot communicates it better than a number (histograms,
  fitted-curve overlays, per-track comparisons, the |Δsteering| threshold line, box/violin
  for spread, a bar of column-fingerprint evidence). Figures are clearly titled and labeled
  (axes, units, legend) so they are readable on their own and reusable in the defense slides.

### Key Entities *(include if feature involves data)*

- **Driving log record**: one timestamped sample = three camera image references
  (center/left/right) + steering + throttle + brake + speed. The timestamp in the filenames
  ties the three images to the same instant.
- **Track dataset**: a set of driving log records + `IMG/` folder for one track. Three exist:
  track1 (easy, ~10,615 rows), track2 (hard/mountain, ~21,828 rows), combined (~32,443 rows).
- **Distribution summary**: for a given variable, its descriptive statistics + histogram +
  (for steering) fitted theoretical distribution + goodness-of-fit result.
- **Calibration output**: the concrete values M1 hands to the Unity milestone - steering
  range, abrupt-Δsteering threshold, typical speed range.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Column identity for all 7 columns is stated with supporting evidence, and the
  integrity check (rows × 3 == image count) passes on all three dataset sources.
- **SC-002**: Descriptive statistics (size, mean, variance/std, min, max) are reported for
  steering, speed, and Δsteering.
- **SC-003**: The steering distribution has a documented theoretical fit with a χ²
  goodness-of-fit decision (statistic, critical value at α, accept/reject) and a KS cross-check.
- **SC-004**: At least three saved figures exist: steering, speed, and Δsteering histograms,
  with the fitted curve overlaid where applicable.
- **SC-005**: `DESIGN.md` §4.4 and §4.5 contain data-derived values (steering range, abrupt-
  Δsteering threshold) plus a recorded typical speed range, each traceable to the M1 report.
- **SC-006**: Re-running the analysis with the fixed seed reproduces the reported numbers
  exactly.
- **SC-007**: track1 vs track2 steering distributions are compared quantitatively.

## Assumptions

- The combined `dataset/dataset/` folder is the primary analysis source (author-chosen);
  per-track loading is available for the track1-vs-track2 comparison.
- Column order follows the Udacity simulator standard; this is treated as a hypothesis to be
  confirmed by the statistical fingerprint, not an unverified given.
- The steering column is already in the normalized simulator range (~[-1, 1]); the mapping to
  physical degrees (±°) for Unity is a design decision informed by the observed range, not a
  claim that the raw values are degrees.
- α for the χ² test defaults to 0.05 unless a course convention dictates otherwise.
- Δsteering is defined as the difference between consecutive steering values within a
  contiguous recording (successive rows), used as the smoothness signal.
- Python is the analysis environment (project already commits to a PyTorch/Python stack);
  no Unity work occurs in M1.
- The dataset is present locally under `dataset/` (already downloaded, git-ignored).
