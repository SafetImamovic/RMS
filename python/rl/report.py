"""The learned column of the M5 comparison, in the shape the other columns already use.

Feature 005 produced the scripted column, feature 004 the imitation column, and M1 the human one.
This module produces the fourth from the same kind of file, using the same functions, so that the
comparison is between drivers rather than between measurement methods.

What is measured, both from the per-step traces rather than from the run record, because the record
carries one summary number per run and M5 needs the distribution behind it:

- The **steering command** the policy issued, resampled to ``config.COMPARE_HZ`` through
  ``python.track.compare_drive.resample``.
- The **per-step \\|delta steering\\|** on that same grid.

Two rules that are easy to get wrong and are checked by the tests:

- **Each run is differenced separately**, and only then concatenated. Differencing across the seam
  between two runs invents a steering jump no driver made, which is the error feature 002 hit at
  the track1 and track2 junction.
- A failed run has an **empty** ``lap_time_s``, not zero. Averaging zeros for failures reports a
  fast driver, which is the same mistake as counting only the successes, arriving through
  arithmetic instead of through omission.

Every figure comes from ``python.eda.stats.describe``, the function that described the human column
in M1 and the BC column in M4. Nothing here computes a statistic of its own, and the comparison
against the human distribution uses a test rather than a pair of histograms, which is what
Principle IX and FR-024 both ask for.

**The losses are reported.** The scripted driver completes 34 of 34 training seeds at a steering
variance of 0.04994. If the learned driver is worse on a measure, this module names the measure and
prints the number (FR-024, SC-007).

Runs under ``.venv``.

Usage::

    python -m python.rl.report results/rl/<runs file> --traces results/rl/<traces dir>
"""
