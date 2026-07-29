# Feature Specification: Unity Driving Environment (M2)

**Feature Branch**: `feature/unity-environment`
**Spec Directory**: `specs/003-unity-environment`
**Created**: 2026-07-29
**Status**: Draft
**Input**: User description: "M2 Unity environment: flat-plane keyboard-drivable car calibrated to the M1 dataset, then a seeded procedural track generator whose curve radii are drawn from the measured empirical steering distribution"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A car you can drive, on a flat plane, that behaves like the dataset (Priority: P1) MVP

Open the project, press Play, and drive a car around a large flat surface with the keyboard.
The car steers, accelerates and stops. Nothing else exists yet: no track, no walls, no
checkpoints, no learning agent.

The point is not that it moves. The point is that it moves **the way the recorded human data
says a car in this simulator moves**. If the recorded driver could reach a given speed, so can
this car. If the recorded driver could swing the wheel from lock to lock in a given time, so can
this one. Every limit the vehicle has traces back to a number measured in M1.

**Why this priority**: everything downstream inherits the vehicle. If the car's limits do not
match the dataset, then the track radii calibrated from that dataset are calibrated for a
different car, the reward thresholds are wrong, and the M5 comparison of agent steering against
human steering compares two different machines. Getting this wrong is not a bug that shows up
later; it is a bug that quietly invalidates the conclusion. It is also the smallest piece that
can be demonstrated on its own, and the one that de-risks the physics decision before any track
geometry work is committed.

**Independent Test**: press Play, drive with the keyboard for a minute, and read the recorded
drive log. Confirm the reachable steering range, the steering rate, the top speed and the
acceleration all sit inside the envelope measured from the dataset, and that the vehicle stays
upright and stable throughout.

**Acceptance Scenarios**:

1. **Given** the scene is open, **When** the player presses Play and holds the forward key on a
   flat surface, **Then** the car accelerates smoothly and settles at a top speed that matches
   the dataset's top speed once both are expressed on the same normalised scale.
2. **Given** the car is moving, **When** the player holds a steering key, **Then** the steering
   input ramps from centre to full lock over a period consistent with the recorded human
   steering-change distribution, rather than snapping instantly or crawling.
3. **Given** the car is at full lock and moving slowly, **When** it completes a circle,
   **Then** the radius of that circle equals the vehicle's documented minimum turning radius
   within a stated tolerance.
4. **Given** the player drives normally for one minute, **When** the drive log is compared
   against the dataset, **Then** the distributions of steering, steering change and speed all
   fall inside the recorded envelope, and no sample exceeds a recorded maximum.
5. **Given** the player drives aggressively, including full-lock turns at top speed and
   full-brake stops, **When** the run ends, **Then** the vehicle has not flipped, sunk through
   the surface, or entered a state it cannot recover from.

---

### User Story 2 - Tracks generated from the data, reproducibly, from a seed (Priority: P2)

Instead of one hand-built circuit, the environment produces closed-loop tracks from a numeric
seed. The same seed always produces exactly the same track. Different seeds produce different
tracks that are nonetheless all drawn from the same statistical description: the curvature of
every generated track is sampled so that the steering a driver would need to follow it matches
the steering distribution actually measured in the human dataset.

Every generated track is guaranteed driveable: it closes into a loop, it never crosses itself,
and no corner is tighter than the car can physically turn.

**Why this priority**: a single fixed track cannot distinguish an agent that learned to drive
from an agent that memorised a sequence of turns. Seeded generation turns the environment into a
train/test split, which is the only way the later milestones can claim generalisation rather than
assert it. It also completes M1's own conclusion: M1 established that human steering follows no
standard distribution and that the empirical distribution must be used. Here that empirical
distribution stops being a reference for comparison and becomes the thing the world is built
from.

**Independent Test**: generate a batch of tracks from a list of seeds. Confirm every one closes,
none self-intersects, none contains a corner below the minimum radius, and the distribution of
required steering across the batch is close to the dataset's. Then regenerate the same seeds and
confirm the geometry is identical.

**Acceptance Scenarios**:

1. **Given** a seed, **When** a track is generated twice, **Then** the two geometries are
   identical value for value.
2. **Given** any accepted seed, **When** the generated track is measured, **Then** the tightest
   corner has a radius at or above the documented minimum, with the safety margin applied.
3. **Given** any accepted seed, **When** the generated centre line is examined, **Then** it forms
   a single closed loop that does not cross itself.
4. **Given** a batch of accepted seeds, **When** the steering required to follow each track is
   computed and pooled, **Then** the resulting distribution is close to the dataset's measured
   steering distribution under a stated distance measure and a stated threshold.
5. **Given** a candidate seed whose tightest corner falls below the minimum radius, **When**
   generation runs, **Then** that seed is rejected and recorded as rejected, rather than being
   silently adjusted until it passes.
6. **Given** a generated track, **When** the player drives it by keyboard, **Then** a full lap
   can be completed without leaving the drivable surface.

---

### User Story 3 - The learning agent's senses, verified before any training (Priority: P3)

The car carries the sensing and progress-tracking a learning agent will later need: distance
readings in an arc ahead of the vehicle, its own speed and rotation, its heading relative to the
next progress marker, and its current steering. Progress markers are placed around the generated
track in order.

None of this trains anything yet. It is instrumentation, and the goal is to be able to look at
every number the future agent will see, while a human is driving, and confirm each one means what
it claims to mean.

**Why this priority**: an observation that is silently wrong does not crash. It trains a policy
on nonsense for six hours and produces a flat reward curve with no explanation. Checking the
senses against a human drive, where the correct answer is obvious by eye, is far cheaper than
debugging it through a training run.

**Independent Test**: drive by keyboard while every observation value is displayed. Confirm each
distance reading matches the visible distance to the barrier, that the heading value peaks when
the car points at the next marker, and that markers are only awarded in order and only once.

**Acceptance Scenarios**:

1. **Given** the car is a known distance from a barrier, **When** the distance readings are
   inspected, **Then** the reading along that direction matches the true distance within a
   stated tolerance, and readings with nothing in range are clearly distinguishable from
   readings at zero distance.
2. **Given** the car is driving forward along the track, **When** it passes progress markers,
   **Then** they are recorded in track order, each exactly once per lap.
3. **Given** the car turns around and drives backwards along the track, **When** it re-approaches
   a marker it already passed, **Then** the system reports travel in the wrong direction rather
   than awarding progress.
4. **Given** a completed lap, **When** the marker record is examined, **Then** the count of
   markers awarded equals the number of markers on the track.

---

### Edge Cases

- **The vehicle physics turn out to be unstable.** Simulated wheel physics can jitter at rest,
  climb their own contact points, or flip the car under a hard turn at speed. The design names a
  simplified movement model as the fallback, but "it felt wrong" is not a decision procedure.
  This feature must state in advance the observable condition that triggers the switch, so the
  decision is made by evidence and not by fatigue at 2am.
- **The flat plane has no edges.** In User Story 1 there is nothing to stop the car driving off
  the surface forever. The scene needs either a boundary or a reset, or the first acceptance run
  ends with the car falling into empty space.
- **A generated track closes but doubles back on itself.** A loop can be topologically closed
  and still pass so near itself that the two lanes overlap in practice, which makes the distance
  readings ambiguous and the progress markers unorderable. Closure alone is not enough; minimum
  separation between non-adjacent parts of the loop has to be checked too.
- **The recorded speed column has no documented unit.** The dataset never states whether its
  speed values are metres per second, miles per hour, or an internal quantity. Any requirement
  phrased as an absolute speed silently smuggles in an assumption that cannot be checked. This
  was established as a finding in the previous feature and the same discipline applies here.
- **The recording rate and the simulation rate differ.** The dataset was captured at roughly
  fourteen frames per second, while the simulation advances on its own fixed step. Any
  comparison of per-frame change, such as steering change or acceleration, is meaningless until
  both are expressed at the same rate.
- **The dataset's steering-change distribution reflects an input device, not a vehicle.** The
  recorded driver used a keyboard or mouse, so large instantaneous steering jumps appear in the
  data that no physical steering rack would produce. Treating that distribution as a vehicle
  capability, rather than as evidence about how the recording was made, would produce a car that
  is uncontrollably twitchy.
- **A seed is rejected.** Some seeds will produce corners that are too tight. The rejection must
  be recorded, because a generator that quietly resamples until it succeeds has an acceptance
  rate nobody can see, and an acceptance rate near zero means the statistical target and the
  radius floor are in conflict.

## Requirements *(mandatory)*

### Functional Requirements

#### Vehicle calibration (User Story 1)

- **FR-001**: The environment MUST provide a drivable vehicle on a flat surface, controllable by
  keyboard, with no track, barriers or progress markers required.
- **FR-002**: The vehicle's steering input MUST span the same range as the recorded human
  steering, including the saturated extremes, since the recorded driver reached full lock in both
  directions on both recordings.
- **FR-003**: The vehicle's maximum speed MUST be derived from the recorded speed distribution
  rather than chosen, and MUST be stated together with the percentile it was taken from.
- **FR-004**: All speed comparisons between the simulation and the dataset MUST be made on a
  normalised scale, because the recorded speed column carries no documented unit. No requirement,
  threshold or reported figure may depend on an assumed unit conversion.
- **FR-005**: The vehicle's steering rate MUST be set so that a person driving by keyboard
  produces a 95th-percentile steering change within a factor of two of the recorded human
  figure, once both are expressed at the same rate. A factor rather than an exact match, because
  the recorded figure differs by more than a factor of two between the two recordings and so
  cannot define a single target.
- **FR-006**: The vehicle MUST have a documented minimum turning radius, derived from its
  steering range and its own geometry, and that radius MUST be verifiable by driving a full-lock
  circle and measuring it.
- **FR-007**: The vehicle's achievable acceleration and deceleration MUST cover the range implied
  by the recorded speed changes, expressed on the same normalised scale as FR-004.
- **FR-008**: The environment MUST record a drive log during keyboard driving containing at least
  steering, throttle, braking and speed per step, so that a human drive can be compared directly
  against the dataset.
- **FR-009**: The system MUST report, for a recorded keyboard drive, whether each of steering,
  steering change and speed falls inside the envelope measured from the dataset, and MUST name
  any that does not.
- **FR-010**: The vehicle MUST remain stable through full-lock turning at top speed and through
  full braking, without flipping, penetrating the surface, or entering an unrecoverable state.
- **FR-011**: The feature MUST state in advance the observable condition under which the primary
  vehicle model is abandoned in favour of the simplified fallback, in terms that can be checked
  by running the simulation rather than by opinion.
- **FR-012**: The flat surface MUST either be bounded or the vehicle MUST reset when it leaves
  the drivable area, so that a test run cannot end with the vehicle falling indefinitely.

#### Track generation (User Story 2)

- **FR-013**: The system MUST generate a closed-loop track centre line from a single integer
  seed, such that the same seed always yields identical geometry.
- **FR-014**: Generated tracks MUST be closed by construction rather than closed by a correction
  applied after the fact, so that enforcing closure cannot distort the curvature the generator
  was asked to produce.
- **FR-015**: The system MUST verify that a generated centre line does not intersect itself, and
  MUST verify a minimum separation between parts of the loop that are not neighbours along it.
- **FR-016**: The system MUST compute the radius of curvature along the whole generated centre
  line and MUST reject any track whose tightest corner is below the documented minimum turning
  radius plus a stated safety margin.
- **FR-017**: The safety margin in FR-016 MUST be justified, not merely chosen, on the grounds
  that a corner taken at full lock leaves the driver no steering authority for correction.
- **FR-018**: The system MUST convert a generated track's curvature into the steering a driver
  would need to follow it, and MUST compare the resulting distribution against the steering
  distribution measured in M1.
- **FR-019**: The comparison in FR-018 MUST be reported as a distance with a stated acceptance
  threshold, and MUST NOT be reported as a hypothesis test. A large p-value is not evidence of
  agreement, and presenting one as such would repeat exactly the error the previous feature was
  written to correct.
- **FR-020**: The system MUST record, for any batch of generated tracks, how many candidate seeds
  were rejected and for which reason, so the acceptance rate is visible rather than hidden.
- **FR-021**: Generated track geometry MUST be persisted in a form that can be committed and
  reviewed, so that a track can be rebuilt from the repository without rerunning the generator.
- **FR-022**: The system MUST support declaring disjoint sets of seeds for training and for
  evaluation, and MUST make the split explicit and recorded, so a later milestone can claim
  generalisation rather than assert it.
- **FR-023**: Generated tracks MUST carry barriers along both edges of the drivable surface,
  because the distance sensing in User Story 3 has nothing to detect otherwise.

#### Agent instrumentation (User Story 3)

- **FR-024**: The vehicle MUST provide distance readings in an arc ahead of it, and a reading
  with nothing in range MUST be distinguishable from a reading at zero distance.
- **FR-025**: The maximum sensing distance MUST be derived from the vehicle's stopping distance
  at top speed, since a sensor that reports a barrier later than the vehicle can react to it
  provides no usable information.
- **FR-026**: The vehicle MUST expose its own speed, rotation rate, current steering, and its
  heading relative to the next progress marker.
- **FR-027**: Progress markers MUST be placed in order around a generated track, and MUST be
  awarded only in order and only once per lap.
- **FR-028**: The system MUST detect and report travel in the wrong direction around the track.
- **FR-029**: Every observation value MUST be inspectable live while a human drives, so that each
  can be checked against a situation whose correct answer is visible.
- **FR-030**: The starting position MUST be randomised within a stated range, so that later
  training cannot succeed by memorising a single approach to the first corner.

### Key Entities

- **Vehicle profile**: the set of limits that define the car - steering range, steering rate,
  top speed, acceleration, braking, wheelbase and the minimum turning radius implied by them.
  Every value traces to a measured statistic or to a stated geometric assumption.
- **Track seed**: a single integer that fully determines one track, together with the record of
  whether it was accepted or rejected and why.
- **Track geometry**: the closed centre line produced from a seed, its width, its curvature
  profile along its length, and the required-steering distribution derived from that curvature.
- **Progress marker set**: the ordered sequence of markers around one track, used to measure
  progress and to detect wrong-way travel.
- **Drive log**: the per-step record of a human keyboard drive, in the same variables as the
  dataset, so the two can be compared directly.
- **Calibration envelope**: the ranges and distributions measured from the dataset in M1 that the
  vehicle is required to match, held in one place so that no threshold in this feature is a bare
  number.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person unfamiliar with the project can drive the car on the flat surface using
  only the keyboard, without instruction beyond which keys to press.
- **SC-002**: A recorded keyboard drive reaches the same steering extremes as the human dataset,
  in both directions.
- **SC-003**: The car's top speed and the dataset's top speed agree within 10 percent once both
  are expressed on the same normalised scale.
- **SC-004**: The measured full-lock turning circle agrees with the documented minimum turning
  radius within 10 percent.
- **SC-005**: Across a one-minute keyboard drive, no recorded steering, steering-change or speed
  value exceeds the corresponding maximum measured in the dataset.
- **SC-006**: The vehicle survives a stress run of full-lock turns at top speed and full-brake
  stops without flipping or leaving the surface, and this is repeatable.
- **SC-007**: Regenerating any seed reproduces its track geometry exactly, with no tolerance
  required.
- **SC-008**: 100 percent of accepted tracks have a tightest corner at or above the minimum
  radius plus margin.
- **SC-009**: 100 percent of accepted tracks form a single closed loop with no self-intersection
  and no violation of the minimum separation rule.
- **SC-010**: Across a batch of at least 20 accepted seeds, the pooled required-steering
  distribution is within the stated distance threshold of the dataset's steering distribution.
- **SC-011**: The seed acceptance rate is reported and is at least 50 percent, so that producing
  20 accepted tracks needs no more than 40 candidates. A rate below this means the statistical
  target and the radius floor are pulling against each other, which is a design finding rather
  than a tuning problem.
- **SC-012**: A full lap can be driven by keyboard on every accepted track in a sample of at
  least five seeds, without leaving the drivable surface.
- **SC-013**: Every distance reading, checked at a known position against a barrier, agrees with
  the true distance within 5 percent.
- **SC-014**: Over a completed lap, the number of progress markers awarded equals the number of
  markers on the track, with none skipped and none double-counted.
- **SC-015**: Driving the wrong way is reported within one marker interval of the reversal.
- **SC-016**: Training seeds and evaluation seeds are disjoint, and the split is recorded in the
  repository rather than held in someone's memory.

## Assumptions

- **The M1 calibration is the source of truth for vehicle limits.** The measured figures
  available are: steering on a lattice of 41 levels spanning the full range with both extremes
  used; per-frame steering change with a 95th percentile of 0.30 on the flat track and 0.70 on
  the mountain track, reaching 1.00 at maximum on both; speed with a pooled 99th percentile of
  17.49 and a maximum of 21.95 in dataset units; throttle used in bursts, with a median of zero
  and full throttle on well under 5 percent of frames.
- **Speed units are treated as unknown, and normalisation is the resolution.** The previous
  feature established that the recorded speed column has no documented unit. Rather than assume a
  conversion, both the dataset and the simulation are normalised by their own high percentile, so
  every comparison is unit free. This is the same discipline applied to the acceleration screen in
  the previous feature.
- **The steering-change distribution is treated as evidence about the recording, not as a
  vehicle specification.** The recorded jumps of a full steering range in a single frame come
  from a keyboard or mouse, not from a steering rack. The vehicle's steering rate is therefore
  set so that comparable driving is achievable, not so that the most extreme recorded jump is
  reproducible.
- **The wheelbase is a design choice, stated rather than derived.** The minimum turning radius
  follows from the steering range and the wheelbase through standard low-speed vehicle geometry,
  so the radius scales with whatever wheelbase is chosen. The chosen value is recorded, and every
  radius figure in the feature is understood to scale with it.
- **The low-speed turning geometry is an approximation.** At speed, a real vehicle understeers,
  so the radius it actually achieves is larger than the geometric one. This is the reason a
  safety margin is required on top of the minimum radius rather than designing to the limit.
- **The generated track targets the flat track's driving profile.** The design calls for mostly
  gentle curves with a few sharper ones. That matches the flat recording, where steering is
  non-zero only about a fifth of the time and full lock is rare, rather than the mountain
  recording, where full lock accounts for over a fifth of all frames. The mountain profile is
  left as a possible harder setting for a later milestone.
- **Track construction stays within first-party engine packages.** The governing document forbids
  third-party marketplace content, on the grounds that it usually cannot be redistributed and
  would therefore break the requirement that everything be reproducible from a clean clone.
  Packages installed through the standard package manager are recorded in a committed manifest
  and are not affected by that restriction.
- **No image data reaches this environment.** The recorded images are used for calibration, for
  the behavioural-cloning model, and as an evaluation baseline. The agent in this environment
  senses distances and its own state only. This separation is deliberate and is the basis of the
  later comparison.
- **This feature trains nothing.** Reward shaping, training runs and model export belong to the
  next milestone. The deliverable here is an environment a human can drive and whose every
  measurement has been checked by hand.
- **The exit condition is the milestone gate already recorded in the design document**: the scene,
  the vehicle, the agent scaffolding and the progress markers exist, the vehicle is drivable by
  keyboard, and the observations have been verified. The governing document adds a blunter
  version of the same rule: no keyboard lap, no training.
