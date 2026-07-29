# Feature Specification: Data Authenticity & Integrity Checks

**Feature Branch**: `002-data-authenticity`
**Created**: 2026-07-26
**Status**: Draft
**Input**: User description: "Provjera vjerodostojnosti podataka (friziranje podataka) - proširiti M1 EDA statistički rigoroznom baterijom provjera koje testiraju da li je dataset friziran, slučajno oštećen, ili strukturno drugačiji nego što je M1 pretpostavio. Svaka provjera mora imati eksplicitnu nultu hipotezu i dokumentovan očekivani potpis, da se 'sumnjivo' razlikuje od 'objašnjivo procesom koji je podatke stvorio'."

## User Scenarios & Testing *(mandatory)*

The "user" is the project author, who must be able to defend the dataset's trustworthiness
under questioning, and the professor, who places specific emphasis on detecting manipulated
data ("friziranje podataka") and on χ² methodology.

The distinguishing idea of this feature: a finding is only evidence of tampering **relative to
a stated expectation**. Several properties of this dataset look alarming at first glance and
are fully explained by how the data was recorded. The feature must make that distinction
explicit and reproducible, rather than producing a list of scary-looking numbers.

### User Story 1 - Provenance and integrity audit (Priority: P1) 🎯 MVP

The author needs to establish that each recording is a single, continuous, complete session -
not a stitched-together, reordered, trimmed, or padded artifact. This is the check that most
directly answers "was this dataset tampered with?".

**Why this priority**: It is the direct answer to the professor's central question, it is
independent of every other story, and it is the check most likely to actually catch
manipulation. Splicing, trimming, duplicating, or reordering all leave detectable traces in
the recording timeline, and those traces are very difficult to fake convincingly.

**Independent Test**: Run the audit on track1 and track2; confirm it reports, per track,
whether the timeline is strictly increasing, the frame-interval distribution, the count and
location of any gaps, duplicate-row and duplicate-image counts, and whether per-frame changes
in speed are physically plausible. Delivers a defensible "this recording is continuous and
unaltered" statement with numbers behind it.

**Acceptance Scenarios**:

1. **Given** the image filenames carry embedded capture timestamps, **When** the audit runs,
   **Then** it reports what fraction of rows yield a parseable timestamp, and fails loudly
   rather than silently skipping rows it cannot parse.
2. **Given** a per-track timeline, **When** ordering is checked, **Then** the audit reports
   whether timestamps are strictly increasing and the count of any violations.
3. **Given** the frame intervals, **When** they are summarized, **Then** the audit reports the
   median interval, the implied capture rate, and the count of gaps exceeding a stated
   threshold - with the threshold justified, not arbitrary.
4. **Given** the driving log, **When** duplicates are examined, **Then** the audit reports
   exact duplicate rows, duplicate image references, and repeated measurement tuples
   separately, since each implies a different kind of manipulation.
5. **Given** consecutive rows, **When** per-frame change in speed is examined, **Then** the
   audit reports the largest observed change and whether it is physically plausible at the
   observed capture rate.
6. **Given** a track whose audit finds nothing anomalous, **When** results are reported,
   **Then** the clean result is stated explicitly as a positive finding, not omitted.

---

### User Story 2 - Measurement granularity and correctly specified distribution tests (Priority: P1)

The author needs to establish the true measurement granularity of each recorded variable, and
then test the steering distribution with a method that matches that granularity.

This story exists because M1 got this wrong. M1 treated steering as a continuous variable and
fitted continuous densities to it. Steering is in fact recorded on a fixed discrete lattice.
Fitting a continuous density to lattice-valued data is misspecified, and the resulting χ²
rejection was close to guaranteed regardless of which density was chosen.

**Why this priority**: It corrects a stated conclusion in a completed milestone, and it turns
the project's central statistical tool (χ²) from an awkward fit into the textbook-correct
choice. A discrete variable with a known, finite set of outcomes is exactly the situation χ²
goodness-of-fit was designed for - with no binning decisions to defend.

**Independent Test**: Run the granularity analysis on each track; confirm it reports, per
numeric column, the number of distinct observed values and whether those values lie on a
regular lattice (and if so, its spacing and support). Then confirm the steering distribution is
tested against a stated null hypothesis on that discrete support, reporting the χ² statistic,
degrees of freedom, critical value at α, and decision.

**Acceptance Scenarios**:

1. **Given** each numeric column, **When** granularity is analyzed, **Then** the analysis
   reports the count of distinct values and classifies the column as effectively discrete or
   effectively continuous, with the evidence for that classification.
2. **Given** a column classified as discrete, **When** the lattice is characterized, **Then**
   the analysis reports the spacing, the full support, and which support points are unobserved.
3. **Given** the steering column on its discrete support, **When** a goodness-of-fit test runs,
   **Then** the χ² statistic, degrees of freedom, critical value at α, and accept/reject
   decision are reported against an explicitly stated null hypothesis.
4. **Given** the two tracks, **When** they are compared, **Then** a χ² test of homogeneity
   reports whether their steering distributions are consistent with a common distribution.
5. **Given** the discrete support is symmetric about zero, **When** turn direction is tested,
   **Then** a symmetry test reports whether left and right turn frequencies are consistent
   with a stated null, per track.
6. **Given** the granularity finding, **When** M1's continuous fit is revisited, **Then** the
   analysis states in plain language why the earlier rejection was a consequence of model
   misspecification rather than of the data being unusual.

---

### User Story 3 - Separating explainable findings from suspicious ones (Priority: P2)

The author needs each flagged finding to carry its own interpretation, so that findings which
look alarming but are fully explained by the recording process are not presented as evidence of
tampering - and, conversely, so that genuinely unexplained findings are not buried.

Two findings in this dataset are the worked examples: one track's braking control is never used
at all, and the same track's turns are overwhelmingly in one direction. Both look like signs of
a doctored dataset. Both are consequences of the track layout and the driver's input method.
One of them is nonetheless a real hazard for the later behavioural-cloning milestone.

**Why this priority**: This is what elevates the work from a checklist to a defensible
argument, and it is the part a grader can probe hardest. It depends on Stories 1–2 having
produced findings to classify, so it is P2.

**Independent Test**: Review the produced report; confirm every flagged finding carries a
stated null hypothesis, the observed result, a verdict, and - where the verdict is
"explainable" - the mechanism that explains it. Confirm that findings which are explainable but
still consequential for later milestones are marked as such.

**Acceptance Scenarios**:

1. **Given** any check the feature performs, **When** its result is reported, **Then** the
   report states the null hypothesis, the observed statistic, the decision, and a plain-language
   interpretation.
2. **Given** a finding fully explained by the data-generating process, **When** it is reported,
   **Then** it is classified as explainable and the explaining mechanism is named.
3. **Given** a per-track structural difference that pooled statistics conceal, **When** results
   are reported, **Then** the per-track result is reported alongside the pooled one, and the
   concealment is called out.
4. **Given** a finding that is explainable but consequential for a later milestone, **When** it
   is reported, **Then** the downstream consequence and its mitigation are recorded.
5. **Given** the completed analysis, **When** earlier project conclusions are affected,
   **Then** the affected documents are amended and the amendment is traceable to this feature's
   output.

---

### Edge Cases

- **Time runs backwards at the combined-dataset junction**: the combined source is a
  concatenation of the two tracks, and the second track was recorded *earlier in the same day*
  than the first. A naive timeline check over the combined source would report a large negative
  jump. Timeline continuity MUST be evaluated per contiguous recording, never across a
  junction - the same constraint M1 applied to Δsteering.
- **Floating-point lattice detection**: a spacing such as 0.05 is not exactly representable in
  binary. Lattice detection MUST tolerate representation error rather than requiring exact
  equality, and the tolerance MUST be stated.
- **Sparse and empty categories in χ²**: at least one lattice point is observed zero times on
  one track, and the extreme points are rare. The χ² procedure MUST handle low-expectation
  categories by a stated, consistent rule, and MUST report the degrees of freedom actually used
  after any pooling.
- **Constant column**: one track's braking column takes a single value throughout. Tests that
  require variation are undefined on it; the analysis MUST report this as a finding rather than
  emit a degenerate statistic or crash.
- **A check with nothing to report**: a clean result MUST be reported as a positive finding.
  Silence is indistinguishable from a check that never ran.
- **Unparseable timestamp**: a filename not matching the expected pattern MUST be counted and
  surfaced, never silently dropped from the timeline.
- **Track missing a support point**: a support point that is never observed on one track but is
  observed on the other MUST be retained in the shared support for the homogeneity comparison,
  not silently removed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analysis MUST extract a capture timestamp for every row from its image
  reference, and MUST report the count of rows for which extraction fails.
- **FR-002**: The analysis MUST evaluate timeline continuity **per contiguous recording** and
  MUST NOT evaluate continuity across the junction between concatenated recordings.
- **FR-003**: The analysis MUST report, per recording: whether timestamps are strictly
  increasing, the number of ordering violations, the median and spread of the frame interval,
  the implied capture rate, the number of gaps exceeding a stated and justified threshold, and
  the session start and end.
- **FR-004**: The analysis MUST report duplicate exact rows, duplicate image references, and
  duplicate measurement tuples as three separate counts.
- **FR-005**: The analysis MUST report the largest and a high-percentile per-frame change in
  speed, and MUST state whether these are physically plausible at the observed capture rate.
- **FR-006**: The analysis MUST report, for every numeric column, the number of distinct
  observed values, and MUST classify each column as effectively discrete or effectively
  continuous from that evidence.
- **FR-007**: For every column classified as discrete, the analysis MUST determine whether its
  values lie on a regular lattice, and if so MUST report the spacing, the full support, and any
  support points that are never observed.
- **FR-008**: Lattice detection MUST tolerate floating-point representation error, and the
  tolerance used MUST be reported.
- **FR-009**: The analysis MUST perform a χ² goodness-of-fit test of the steering distribution
  **on its discrete support**, against an explicitly stated null hypothesis, reporting the
  statistic, degrees of freedom actually used, critical value at α, p-value, and decision.
- **FR-010**: The χ² procedure MUST apply a stated, consistent rule for categories with low
  expected counts, and MUST report the effect of that rule on the degrees of freedom.
- **FR-011**: The analysis MUST perform a χ² test of homogeneity between the two tracks'
  steering distributions over their shared support.
- **FR-012**: The analysis MUST test left/right turn symmetry per track against a stated null
  hypothesis, and report the result per track rather than pooled.
- **FR-013**: The analysis MUST report any column that is constant within a track as a finding,
  and MUST NOT emit statistics that are undefined on a constant column.
- **FR-014**: The analysis MUST report, for every check, a structured result containing: the
  null hypothesis, the observed statistic, the decision at α, and a plain-language
  interpretation.
- **FR-015**: Every finding MUST be classified as either explainable by the data-generating
  process (with the mechanism named) or unexplained, and this classification MUST appear in the
  output.
- **FR-016**: A finding that is explainable but consequential for a later milestone MUST record
  the downstream consequence and its mitigation.
- **FR-017**: Results MUST be written both as a human-readable report and as a machine-readable
  file, without modifying M1's existing outputs in place.
- **FR-018**: The analysis MUST state explicitly whether the granularity finding changes any
  calibration value already handed to the design, and MUST report the outcome either way.
- **FR-019**: M1's recorded distribution-fit findings MUST be amended to record that the
  steering variable is lattice-valued and that the earlier continuous fit was misspecified,
  with the amendment traceable to this feature.
- **FR-020**: The per-track behaviour of any column whose pooled summary concealed a structural
  difference MUST be recorded where that pooled summary is currently stated.
- **FR-021**: A forward note MUST be recorded for the evaluation milestone stating that the
  learned agent emits values on a continuous range while the human baseline is lattice-valued,
  and that comparing their distributions requires accounting for this.
- **FR-022**: All reported results MUST be reproducible: re-running with the fixed project seed
  produces identical reported numbers.
- **FR-023**: The notebook section MUST follow the established pedagogical style - a
  plain-language explanation before every step, every non-obvious constant or method justified
  in one sentence, and no unexplained arbitrary picks. Narration in the same language as the
  existing notebook sections.
- **FR-024**: The notebook section MUST be visual - every numeric finding accompanied by a plot
  wherever a plot communicates it better than a number, with titled and labelled figures
  readable on their own and reusable in defence slides.
- **FR-025**: Both new analysis modules MUST have automated test coverage, including tests on
  crafted inputs where the correct answer is known by construction - specifically, inputs that
  are deliberately tampered with, to prove the checks actually detect manipulation.
- **FR-026**: The dataset MUST NOT be committed; the analysis reads it from the existing
  ignored location.

### Key Entities *(include if feature involves data)*

- **Recording session**: a contiguous run of driving log records from a single track, with a
  start time, an end time, and an expected frame cadence. The unit over which timeline
  continuity is meaningful.
- **Integrity finding**: the result of one structural check - what was checked, what was
  observed, whether it is anomalous, and how confident that judgement is.
- **Measurement granularity profile**: for one numeric column, its distinct-value count, its
  discrete-or-continuous classification, and, when discrete, its lattice spacing, full support,
  and unobserved support points.
- **Hypothesis test result**: a named null hypothesis, the test statistic, degrees of freedom,
  critical value at α, p-value, decision, and plain-language interpretation.
- **Verdict**: the classification attached to a finding - explainable (with named mechanism) or
  unexplained - plus any downstream consequence and mitigation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every row in both tracks yields a capture timestamp, or the exact number of
  failures is reported.
- **SC-002**: For each track, timeline continuity is reported as a verdict backed by the
  ordering-violation count, the frame-interval summary, and the gap count.
- **SC-003**: Duplicate rows, duplicate image references, and duplicate measurement tuples are
  each reported as an explicit count for each track.
- **SC-004**: Every numeric column carries a discrete-or-continuous classification with its
  distinct-value count as evidence.
- **SC-005**: The steering column's lattice spacing, full support, and unobserved support
  points are reported per track.
- **SC-006**: The steering distribution has a χ² goodness-of-fit result on its discrete support
  with a stated null hypothesis, reported degrees of freedom, and a decision at α.
- **SC-007**: A χ² homogeneity result between the two tracks and a per-track symmetry result are
  both reported with stated null hypotheses.
- **SC-008**: Every reported finding carries a null hypothesis, a decision, an interpretation,
  and an explainable-or-unexplained verdict - no finding is reported as a bare number.
- **SC-009**: At least one finding is correctly classified as explainable with its mechanism
  named, and at least one explainable finding records a downstream consequence and mitigation.
- **SC-010**: The automated tests include at least one deliberately tampered input per check
  family, and the corresponding check flags it.
- **SC-011**: Re-running the analysis with the fixed seed reproduces every reported number
  exactly.
- **SC-012**: M1's affected findings are amended, the per-track concealed difference is recorded
  where the pooled summary is stated, and the evaluation-milestone forward note exists.
- **SC-013**: The notebook section runs top to bottom without error and every step has a
  plain-language explanation preceding it.

## Assumptions

- The recording timestamps embedded in image filenames are the authoritative timeline; no
  separate time column exists in the driving log.
- Both new analysis modules live alongside the existing analysis package and reuse its loader,
  seed, and α, rather than re-implementing dataset access.
- M1's existing outputs are treated as immutable historical artifacts. This feature writes new
  output files and amends M1's *narrative* findings by editing the specification and report
  prose, not by regenerating M1's machine-readable output in place.
- The existing continuous distribution fit is **retained** in the notebook rather than deleted,
  and presented alongside the corrected discrete treatment. Showing why the first approach was
  misspecified is pedagogically stronger than silently replacing it, and it preserves the
  reviewed history of the project.
- α remains 0.05, consistent with M1, unless the course convention dictates otherwise.
- The plausibility threshold for per-frame speed change is derived from the observed capture
  rate and a defensible bound on vehicle acceleration, and is stated in the output rather than
  hard-coded silently.
- Analysis is Python-side only; no Unity work occurs in this feature and no milestone gate for
  the Unity environment depends on it.
- The dataset is present locally at the existing ignored path.
- This feature sits between M1 and M2 in sequence but does not block M2 from starting, since it
  changes no value the Unity environment consumes unless FR-018 finds otherwise.
