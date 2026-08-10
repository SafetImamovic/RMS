# Specification Quality Checklist: Heuristic Ray-Following Driver

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-08
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

Two iterations were needed. Both failures were the same kind, and both are worth recording
because the source description invited them.

**Iteration 1, implementation detail throughout.** The description is written in the vocabulary
of the code, naming `CarAgent`, `CarController.ScriptedMove`, `steerMaxDeg` and `RAY_COUNT`, and
the first draft carried those straight into the requirements. They were replaced with what each
one is for: "the ray distances the vehicle already senses", "the path that exists for external
control", "the vehicle profile's limits". The class names now appear only in the verbatim Input
line, which is a record of what was asked for rather than a requirement.

**Iteration 1, numbers that presuppose the answer.** The description supplies 13 rays, 15 degree
spacing, 5.85 m/s2 of grip and a 6.4 m/s cornering cap. Writing those into requirements would fix
the sensing arrangement in the very document that asks whether it is right, and would restate
vehicle constants that already live in the vehicle profile. The requirements now name the
quantity and its source instead of its current value, and FR-013 deliberately leaves the swept
range open.

**Iteration 2, success criteria phrased as system internals.** SC-003 and SC-005 originally read
as assertions about controller internals. They now describe what a reader can determine from the
recorded results, which is checkable without knowing how the controller works.

**No [NEEDS CLARIFICATION] markers were raised.** Three candidates were considered and all three
resolved against existing project decisions rather than being put to the owner: the seed set is
feature 003's 44 accepted seeds with its existing train and eval split; the vehicle limits come
from the existing profile; and the reporting shape follows the existing driver comparisons. Asking
about any of them would have been asking a question the repository already answers.

**One deliberate asymmetry.** The spec repeatedly requires that a negative result be reported as a
result: US2 scenario 3, US3 scenario 3, US4 scenario 2, FR-009 and FR-015. This is heavier than a
specification usually needs, and it is here because the feature's whole value is as a yardstick.
A baseline quietly adjusted until the learned systems beat it would be worse than no baseline,
since it would make an unearned claim look measured.
