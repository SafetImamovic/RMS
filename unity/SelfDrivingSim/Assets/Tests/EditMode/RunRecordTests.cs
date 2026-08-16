using System.Globalization;
using System.Threading;
using NUnit.Framework;
using SelfDrivingSim.Logging;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// The run record row (feature 005, T023, `contracts/run-record.md`).
    ///
    /// No file is written here. The row formats itself, so the two properties the contract actually
    /// rests on, the invariant decimal point and the empty lap time, are testable without touching
    /// a disk or a scene.
    /// </summary>
    public class RunRecordTests
    {
        private const string BosnianLocale = "bs-Latn-BA";

        private static RunRecord CompletedLap()
        {
            return new RunRecord
            {
                Seed = 1,
                Controller = "WeightedAverage",
                RayCount = 13,
                RayFovDeg = 180f,
                RayLengthM = 20f,
                CompletedLap = true,
                LapTimeS = 27.4f,
                CheckpointsAwarded = 24,
                CheckpointsTotal = 24,
                CheckpointsSkipped = 0,
                WallContacts = 0,
                EndReason = "LapComplete",
                SteerP95DSteer = 0.0493f,
                SteerSignChangesPerS = 0.1465f,
                TimeScale = 1f,
                DurationS = 27.4f,
            };
        }

        private static RunRecord FailedRun()
        {
            RunRecord r = CompletedLap();
            r.Seed = 1004;
            r.Controller = "MostOpen";
            r.CompletedLap = false;
            r.LapTimeS = -1f;
            r.CheckpointsAwarded = 5;
            r.CheckpointsSkipped = 1;
            r.WallContacts = 1;
            r.EndReason = "WallContact";
            r.DurationS = 5.2f;
            return r;
        }

        [Test]
        public void The_header_matches_the_contract_column_order()
        {
            Assert.That(RunRecord.Header(), Is.EqualTo(
                "seed,controller,ray_count,ray_fov_deg,ray_length_m,completed_lap,lap_time_s," +
                "checkpoints_awarded,checkpoints_total,checkpoints_skipped,wall_contacts," +
                "end_reason,steer_p95_dsteer,steer_sign_changes_per_s,time_scale,duration_s"));
        }

        [Test]
        public void A_row_has_one_field_per_header_column()
        {
            int columns = RunRecord.Header().Split(',').Length;

            Assert.That(CompletedLap().ToCsv().Split(',').Length, Is.EqualTo(columns));
            Assert.That(FailedRun().ToCsv().Split(',').Length, Is.EqualTo(columns),
                "the empty lap time must still occupy its field, or every column after it shifts " +
                "left by one and the file parses into the wrong quantities without complaining");
        }

        /// <summary>
        /// The bug this project has hit four times, pinned so it cannot arrive a fifth.
        ///
        /// The development machine's locale is `bs-Latn-BA`, which writes 42,3 for 42.3. A CSV with
        /// comma decimals inside comma-separated fields is not recoverable by a reader that did not
        /// write it, because nothing in the file says which commas were separators. It has appeared
        /// in the track loader's refusal messages, in `LapReport`, in `StabilityMonitor`'s detail
        /// strings, and in a tuner log line found while T022 was being verified.
        ///
        /// The thread culture is set here rather than the formatter being wrapped by the caller,
        /// because a formatter that is only correct when someone remembers to wrap it is the same
        /// bug with an extra step.
        /// </summary>
        [Test]
        public void Every_number_uses_a_decimal_point_under_the_machine_locale()
        {
            CultureInfo previous = Thread.CurrentThread.CurrentCulture;
            try
            {
                Thread.CurrentThread.CurrentCulture = new CultureInfo(BosnianLocale);

                // Guard the guard: if this ever stops writing a comma, the test below stops
                // testing anything and would pass for the wrong reason.
                Assert.That(27.4f.ToString("F3"), Does.Contain(","),
                    "the locale under test must be one that writes comma decimals, or this case " +
                    "proves nothing");

                string row = CompletedLap().ToCsv();

                Assert.That(row.Split(',').Length, Is.EqualTo(RunRecord.Header().Split(',').Length));
                Assert.That(row, Does.Contain("27.400"));
                Assert.That(row, Does.Contain("0.0493"));
                Assert.That(row, Does.Contain("180.00"));
            }
            finally
            {
                Thread.CurrentThread.CurrentCulture = previous;
            }
        }

        /// <summary>
        /// A failed run's lap time is empty, and empty is not zero.
        ///
        /// An aggregate that averages zeros for failed runs reports a fast sweep. That is the same
        /// class of mistake as counting only the successes, arriving through arithmetic instead of
        /// through omission, and it is the one this column exists to make impossible.
        /// </summary>
        [Test]
        public void A_failed_run_writes_an_empty_lap_time_rather_than_a_zero()
        {
            string[] fields = FailedRun().ToCsv().Split(',');
            int lapTime = System.Array.IndexOf(RunRecord.Header().Split(','), "lap_time_s");

            Assert.That(fields[lapTime], Is.EqualTo(string.Empty));
            Assert.That(fields[lapTime], Is.Not.EqualTo("0.000"));
        }

        [Test]
        public void A_failed_run_still_records_its_outcome_and_its_configuration()
        {
            string[] header = RunRecord.Header().Split(',');
            string[] fields = FailedRun().ToCsv().Split(',');

            string Field(string name) => fields[System.Array.IndexOf(header, name)];

            Assert.That(Field("completed_lap"), Is.EqualTo("false"));
            Assert.That(Field("end_reason"), Is.EqualTo("WallContact"));
            Assert.That(Field("wall_contacts"), Is.EqualTo("1"));
            Assert.That(Field("checkpoints_awarded"), Is.EqualTo("5"));
            Assert.That(Field("checkpoints_skipped"), Is.EqualTo("1"));

            // SC-006: a row found in isolation says what produced it, without the filename, the
            // header, or a neighbouring row.
            Assert.That(Field("seed"), Is.EqualTo("1004"));
            Assert.That(Field("controller"), Is.EqualTo("MostOpen"));
            Assert.That(Field("ray_count"), Is.EqualTo("13"));
            Assert.That(Field("ray_fov_deg"), Is.EqualTo("180.00"));
            Assert.That(Field("ray_length_m"), Is.EqualTo("20.00"));
            Assert.That(Field("time_scale"), Is.EqualTo("1.00"));
        }

        /// <summary>
        /// The smoothness columns keep enough digits to be worth comparing.
        ///
        /// T027 measures the run-to-run spread, and nothing in Phase 4 or Phase 5 may be
        /// interpreted before that number exists. A column rounded coarser than the spread would
        /// decide the answer at the formatter rather than at the measurement: the lap-time spread
        /// over five clean repeats was 0.100 s, so a duration written to three decimals resolves it
        /// a hundred times over.
        /// </summary>
        [Test]
        public void The_measured_columns_keep_more_precision_than_the_spread_they_are_judged_by()
        {
            string[] header = RunRecord.Header().Split(',');
            string[] fields = CompletedLap().ToCsv().Split(',');

            string Field(string name) => fields[System.Array.IndexOf(header, name)];

            Assert.That(Field("steer_p95_dsteer"), Is.EqualTo("0.0493"));
            Assert.That(Field("steer_sign_changes_per_s"), Is.EqualTo("0.1465"));
            Assert.That(Field("duration_s"), Is.EqualTo("27.400"));
            Assert.That(Field("lap_time_s"), Is.EqualTo("27.400"));
        }
    }
}
