# Feature Specification: Heuristic Ray-Following Driver

**Feature Branch**: `005-heuristic-ray-driver`
**Created**: 2026-08-08
**Status**: Draft
**Input**: User description: "Heuristic ray-following driver as a non-learned baseline. A scripted driver reads the 13 normalised ray distances CarAgent already produces and writes CarController.ScriptedMove, so it needs no new sensing and no neural network. Built in two deliberate stages so the design decision is measured rather than asserted: first the naive argmax controller that steers toward the single longest ray, then the measurement showing it chatters because steering snaps to the 15 degree ray spacing while steerMaxDeg is 25, then the distance-weighted average of ray angles that replaces it. Longitudinal control is required, not optional: grip gives about 5.85 m/s2 lateral, so the 6.97 m minimum radius caps cornering at about 6.4 m/s against a 10 m/s top speed, and flat throttle understeers into the barrier. Two purposes beyond the driver itself. It is a fourth column for the M5 comparison, a non-learned baseline that says what a simple heuristic achieves before any PPO or BC result is claimed as an achievement. And it is a cheap measuring instrument for the observation geometry: laps completed, lap time and wall contacts give an objective that can sweep ray FOV and ray count in seconds per configuration, where sweeping the same parameters with PPO runs would cost hours each. The specific open question it should answer is whether the 180 degree fan is misallocated, since T059 measured seven of the thirteen rays reporting essentially the same 3 m lateral distance in a 6 m corridor while the forward cone that carries the cornering information holds only three rays. Scope note: this does not replace T051, which requires a human keyboard lap."

## Why this feature exists

Two claims this project will make at its defence currently have nothing standing behind them.

The first is that the reinforcement learning agent learned something. A reward curve that rises
says the agent improved against its own reward, not that the result is any good. Without a
non-learned reference, "PPO completes laps" cannot be distinguished from "this track is easy
enough that anything completes laps", and the honest version of that sentence is the one the
examiner will ask for.

The second is that the observation geometry is right. The car senses through thirteen rays over
a 180 degree fan. Those numbers were chosen before anything drove, and feature 003's own
measurement (T059) suggests they may be badly distributed: in a 6 metre corridor, seven of the
thirteen rays reported essentially the same 3 metre lateral distance, while the forward cone that
carries every cornering decision held three rays. Nothing has tested whether that matters.

A scripted driver answers both, and it is cheap because the sensing already exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A driver that gets round the track without learning anything (Priority: P1)

Someone selects a track seed, starts the simulation, and watches the car complete laps under
scripted control. No training, no model file, no waiting. The driver reads the same ray distances
the learning agent will read and produces steering and throttle from them directly.

**Why this priority**: everything else in this feature is built on there being a driver at all.
It is also the smallest useful result: a scripted lap proves the track is completable by
something, which is a fact nobody currently has.

**Independent Test**: pick an accepted seed, run the scripted driver, and confirm it completes a
lap with the checkpoint count the track declares and no wall contacts.

**Acceptance Scenarios**:

1. **Given** an accepted track seed and the scripted driver active, **When** the simulation runs,
   **Then** the car completes at least one full lap awarding every checkpoint in order
2. **Given** the scripted driver is active, **When** the run is observed, **Then** no keyboard or
   other human input is required or accepted for control
3. **Given** a corner at the tightest radius the generator produces, **When** the car reaches it,
   **Then** the car slows enough to hold the corner rather than running wide into the barrier
4. **Given** the driver is disabled, **When** the simulation runs, **Then** keyboard control
   behaves exactly as it did before this feature existed

---

### User Story 2 - The chatter is demonstrated before it is fixed (Priority: P1)

The obvious controller steers toward whichever ray reports the greatest distance. Someone builds
that first, records how it behaves, and only then replaces it with a smoothed version. The
recorded comparison is the deliverable, not just the better controller.

**Why this priority**: equal first with the driver itself, because this is the reason the feature
is shaped the way it is. The project's standing rule is that a design decision is measured rather
than asserted. Shipping only the smoothed controller would leave the reader to take on trust that
the simple one was inadequate, and "we tried the obvious thing and here is what it did" is a
stronger answer than "we knew it would not work".

**Independent Test**: run both controllers over the same seeds and compare their recorded steering
traces and outcomes side by side.

**Acceptance Scenarios**:

1. **Given** the naive controller on an accepted seed, **When** the run is recorded, **Then** the
   steering trace and its oscillation are captured as data rather than described in prose
2. **Given** both controllers run over the same seeds under the same conditions, **When** their
   traces are compared, **Then** the difference in steering smoothness is reported as a number
3. **Given** the naive controller turns out to perform acceptably, **When** results are written
   up, **Then** that is recorded as the finding and the smoothed controller is justified on its
   measured merits or not adopted

---

### User Story 3 - A cheap way to test whether the sensing geometry is right (Priority: P2)

Someone changes how the rays are arranged, reruns the scripted driver across a set of seeds, and
reads off whether the driver got round more often, faster, or with fewer wall contacts. The whole
sweep finishes in the time a single training run would spend initialising.

**Why this priority**: this is the reason the feature is worth more than the driver alone, but it
depends on the driver existing and being trustworthy first. It is also the part with a real
possibility of a negative result: the geometry may turn out not to matter.

**Independent Test**: run the same seed set under at least two different ray arrangements and
compare the recorded outcomes.

**Acceptance Scenarios**:

1. **Given** a fixed set of accepted seeds, **When** the driver is run under a given ray
   arrangement, **Then** laps completed, lap time and wall contacts are recorded per seed
2. **Given** two ray arrangements measured over the same seeds, **When** their results are
   compared, **Then** the comparison states whether the difference exceeds run-to-run variation
3. **Given** the sweep finds no arrangement meaningfully better than the current one, **When**
   results are written up, **Then** the current geometry is recorded as measured-and-kept rather
   than quietly left alone

---

### User Story 4 - A fourth column in the final comparison (Priority: P3)

Whoever assembles the final comparison can place the scripted driver's steering behaviour beside
the learning agent's, the imitation model's and the human's, described by the same measures.

**Why this priority**: valuable at the defence but not needed to make anything else work, and the
comparison it feeds does not exist yet.

**Independent Test**: produce the scripted driver's steering distribution and confirm it is
described by the same measures already used for the other drivers.

**Acceptance Scenarios**:

1. **Given** a completed scripted run, **When** its steering behaviour is summarised, **Then** it
   uses the same measures and the same summary shape as the existing driver comparisons
2. **Given** the scripted driver outperforms a learned driver on some measure, **When** results
   are written up, **Then** that is reported plainly rather than omitted

### Edge Cases

- What happens when every ray reports the same distance, so no direction is preferred? A
  symmetric reading has no unique longest ray, and the naive controller must not depend on
  whichever index happens to be found first.
- What happens when every ray reports maximum range, because nothing is within sensing distance?
  The driver has no information and must behave predictably rather than arbitrarily.
- What happens when the car is facing backwards after a bad recovery? The sensing fan looks
  forward, so a car pointed the wrong way sees open track and will confidently drive the wrong
  way round the loop.
- What happens when the car is already touching a barrier, so the rays on that side read near
  zero? Steering away is correct, but a controller that only steers cannot reverse out.
- How does the driver behave on a track it cannot complete? It must terminate rather than run
  forever, or a sweep over many seeds never finishes.
- What happens when the scripted driver and human input are both present? Exactly one must have
  control, and which one must be unambiguous.

## Requirements *(mandatory)*

### Functional Requirements

**The driver**

- **FR-001**: The scripted driver MUST derive its control decisions solely from the ray distances
  the vehicle already senses, plus the vehicle's own speed. It MUST NOT read the track file, the
  checkpoint positions, or any other knowledge unavailable to a learning agent, because a
  baseline that can see more than the thing it is a baseline for measures nothing
- **FR-002**: The scripted driver MUST produce both a steering and a longitudinal (throttle and
  brake) decision. A steering-only driver cannot hold the tightest corners the track generator
  produces and would fail for a reason unrelated to its steering logic
- **FR-003**: The scripted driver MUST be switchable on and off, and when off, human keyboard
  control MUST behave exactly as before this feature
- **FR-004**: Exactly one source of control MUST be in effect at a time, and which one MUST be
  visible to an observer during a run
- **FR-005**: The scripted driver MUST reach a defined end state on every run, whether by
  completing a set number of laps, exceeding a time limit, or being stopped by a failure
  condition. An unbounded run makes a multi-seed sweep impossible

**The two controllers**

- **FR-006**: Two steering strategies MUST be implemented and both retained: one selecting the
  single most open sensed direction, and one combining all sensed directions weighted by how open
  each is
- **FR-007**: Both strategies MUST be selectable for a run without editing code, so a comparison
  runs the same build twice rather than two builds once
- **FR-008**: The steering command over a run MUST be recorded at a fixed rate, so that the
  smoothness of the two strategies can be compared as data
- **FR-009**: The comparison between the two strategies MUST report a smoothness measure and an
  outcome measure separately, and MUST NOT collapse them into a single verdict. A strategy that
  steers more smoothly but completes fewer laps is a real result

**Measuring a run**

- **FR-010**: Every run MUST record, per seed: whether a lap was completed, the time taken,
  the number of checkpoints awarded, the number of wall contacts, and the reason the run ended
- **FR-011**: A run MUST be reproducible: the same seed, controller and configuration MUST
  produce the same recorded outcome, or the extent to which it does not MUST be measured and
  stated
- **FR-012**: Results across a set of seeds MUST be reported as a set, not as a single seed's
  outcome. One track is one sample and the tracks differ in difficulty by construction

**The sensing sweep**

- **FR-013**: The arrangement of the sensing rays MUST be variable for the purpose of the sweep,
  covering at minimum the angular width of the fan
- **FR-014**: Every swept configuration MUST be evaluated over the same set of seeds, so that
  differences are attributable to the configuration and not to which tracks were tried
- **FR-015**: The sweep MUST report whether an observed difference between configurations exceeds
  the run-to-run variation measured under FR-011. A difference smaller than the noise is not a
  finding
- **FR-016**: Changing the sensing arrangement MUST keep the two places that describe it in
  agreement, since the sensing geometry is currently stated in both the simulation and the track
  tooling and nothing checks that they match

**Scope boundaries**

- **FR-017**: This feature MUST NOT satisfy or substitute for the human keyboard lap required by
  feature 003. The scripted driver demonstrates that the track is completable, which is a
  different claim from the vehicle being drivable by a person
- **FR-018**: Any change to the sensing arrangement adopted as a result of the sweep MUST be
  recorded as a decision with the measurement behind it before it is applied, and MUST state that
  it invalidates previously measured sensing results and any model trained against the old
  arrangement

### Key Entities

- **Controller strategy**: a named way of turning sensed distances into a steering command. Two
  exist: most-open-direction and openness-weighted-average
- **Run record**: one execution of one controller on one seed under one sensing configuration,
  carrying the outcome measures of FR-010 and enough configuration detail to repeat it
- **Sweep**: a set of run records covering the same seeds across several sensing configurations,
  reported together
- **Sensing configuration**: the arrangement of the sensing fan, being at minimum its angular
  width and the number of directions sensed

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The scripted driver completes a full lap on at least 80 percent of accepted track
  seeds without wall contact
- **SC-002**: The scripted driver completes a lap on the tightest-cornered accepted seed, which is
  the case that fails first if longitudinal control is inadequate
- **SC-003**: The difference in steering smoothness between the two strategies is reported as a
  number over the same seeds, and the report states whether that difference exceeds run-to-run
  variation
- **SC-004**: A complete sweep of one sensing arrangement across the full seed set finishes in
  under five minutes, so that testing a geometry costs less than a coffee rather than an afternoon
- **SC-005**: The sensing sweep produces a stated answer to whether the current fan width is worse
  than, equal to, or better than the alternatives tried, with the measurement supporting it
- **SC-006**: A reader can determine, from the recorded results alone and without reading code,
  which controller and which sensing configuration produced any reported figure
- **SC-007**: Enabling and disabling the scripted driver leaves human keyboard behaviour
  unchanged, confirmed by driving with it disabled

## Assumptions

- The existing sensing already provides what the driver needs. It reports thirteen normalised
  distances over a forward fan, verified accurate to within a fraction of a percent, so no new
  sensing is built here.
- The existing vehicle already accepts an external control input, so the driver supplies commands
  through the path that exists rather than a new one.
- The existing checkpoint ring already counts laps, awards and skipped markers, so lap completion
  is read from it rather than recomputed.
- The 44 accepted track seeds from feature 003 are the seed set. They are already split into a
  training and an evaluation group, and the sweep uses whichever group avoids tuning the sensing
  geometry against the tracks the learning agent will later be evaluated on.
- Vehicle limits come from the existing vehicle profile rather than being restated here, so
  retuning the car retunes the driver.
- This feature does not train anything and produces no model file.
- The scripted driver is not expected to be fast. Completing laps cleanly is the goal; lap time is
  recorded as a comparison measure, not optimised.
- Feature 003 must be complete before the sweep is meaningful, since the sweep changes sensing
  values that feature 003 measured and recorded.

## Dependencies

- Feature 003 supplies the track scene, the accepted seeds, the sensing and the checkpoint
  counting. This feature adds no geometry and no sensing of its own.
- The final comparison milestone consumes this feature's output as an additional column. That
  milestone does not exist yet, so this feature produces its results in the same shape the
  existing driver comparisons use rather than inventing a new one.

## Out of Scope

- Any learned or trained controller. This feature exists precisely to provide the thing a learned
  controller is measured against.
- Optimising the heuristic for lap time. A tuned heuristic stops being a baseline and becomes a
  competitor, and the comparison it supports would then be between two tuned systems.
- Changing the vehicle, the track generator, the barriers or the checkpoint logic.
- Satisfying feature 003's human keyboard lap requirement.
- Adopting a new sensing arrangement. This feature measures whether one is warranted and records
  the answer; applying it is a separate change with its own consequences for already-measured
  results.
