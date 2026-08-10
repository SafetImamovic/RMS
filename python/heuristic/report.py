"""Turn run records into the comparisons feature 005 is judged on.

Three reports come out of the same rows, and they are deliberately separate because they answer
different questions and are read at different times.

**The controller comparison** (US2). Both controllers over the same seeds, with the two smoothness
measures and the outcome measures side by side. FR-009 forbids collapsing them into a winner: a
controller that steers more smoothly and completes fewer laps is a real result, and it is the
result this feature is most likely to produce.

**The repeat check** (FR-011). The same seed and controller run several times, reporting the
spread. This is the noise floor, and it is the number every other comparison depends on. FR-015
turns on it: a difference smaller than the spread is not a finding.

**The sweep** (US3). Sensing configurations over the same seeds, each difference judged against
that noise floor rather than against zero.

Two rules that are easy to get wrong and are checked by the tests rather than left to care:

- A failed run has an empty ``lap_time_s``, not zero. Averaging zeros for failures reports a fast
  sweep, which is the same mistake as counting only successes arriving through arithmetic instead
  of through omission.
- Results are reported over the seed set with descriptive statistics, never as one seed's outcome.
  The tracks differ in difficulty by construction, so a single seed is a sample of one (FR-012,
  Constitution Principle IX).

Not implemented yet. This module is a skeleton committed alongside the plan so the package exists
before the tasks that fill it; see ``specs/005-heuristic-ray-driver/tasks.md``, T028 and T038.
"""
