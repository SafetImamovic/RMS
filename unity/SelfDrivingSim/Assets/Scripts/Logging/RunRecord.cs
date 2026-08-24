using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace SelfDrivingSim.Logging
{
    /// <summary>
    /// One row of the run record (feature 005, T023, `contracts/run-record.md`).
    ///
    /// A run is one controller, on one seed, under one sensing configuration. This type is the row
    /// and nothing else: it holds the values, states the header, and formats itself. It touches no
    /// file, no scene and no clock, so the two properties the contract actually rests on are
    /// testable without any of them.
    ///
    /// **A row is self-describing** (SC-006). The sensing configuration and the controller are
    /// repeated on every row rather than stated once in a header or implied by the filename,
    /// because a reader who finds one row in isolation, or a pandas filter slicing across
    /// configurations, must not have to reconstruct context from somewhere else.
    ///
    /// **Every run writes a row, including a failure.** A sweep that recorded only completed laps
    /// would report an acceptance rate over a denominator that silently shrank, and
    /// <see cref="EndReason"/> is what makes a failure legible rather than absent.
    /// </summary>
    public struct RunRecord
    {
        public int Seed;
        public string Controller;

        public int RayCount;
        public float RayFovDeg;
        public float RayLengthM;

        public bool CompletedLap;

        /// <summary>
        /// Seconds, or negative when no lap completed, which writes as an empty field.
        ///
        /// **Empty rather than zero.** Zero is a lap time, and an aggregate that averages zeros for
        /// failed runs reports a fast sweep. That is the same class of mistake as counting only the
        /// successes, arriving through arithmetic instead of through omission.
        /// </summary>
        public float LapTimeS;

        public int CheckpointsAwarded;
        public int CheckpointsTotal;
        public int CheckpointsSkipped;
        public int WallContacts;
        public string EndReason;

        /// <summary>|delta steer| P95 at the compare rate. Never combined with the next field.</summary>
        public float SteerP95DSteer;

        /// <summary>Direction reversals per second. Never combined with the previous field.</summary>
        public float SteerSignChangesPerS;

        /// <summary>
        /// What the run was simulated at, recorded because the sweep is accelerated (research R4).
        ///
        /// A run at 8x that disagrees with the same seed at 1x is a defect in the sweep rather than
        /// a property of the controller, and without this column that defect would be invisible in
        /// the results rather than merely unexplained.
        /// </summary>
        public float TimeScale;

        public float DurationS;

        /// <summary>The header, in the contract's column order.</summary>
        public static string Header()
        {
            return "seed,controller,ray_count,ray_fov_deg,ray_length_m,completed_lap,lap_time_s," +
                   "checkpoints_awarded,checkpoints_total,checkpoints_skipped,wall_contacts," +
                   "end_reason,steer_p95_dsteer,steer_sign_changes_per_s,time_scale,duration_s";
        }

        /// <summary>
        /// The row, in <see cref="CultureInfo.InvariantCulture"/> whatever the machine is set to.
        ///
        /// **Not a precaution.** The development machine's locale is `bs-Latn-BA`, which writes
        /// `42,3` for `42.3`, and this project has hit that bug four times: in the track loader's
        /// refusal messages, in `LapReport`, in `StabilityMonitor`'s detail strings, and in a tuner
        /// log line found while T022 was being verified. A CSV with comma decimals inside
        /// comma-separated fields is not recoverable by a reader that did not write it, because
        /// nothing in the file says which commas were separators.
        ///
        /// Every conversion here names the culture rather than relying on the caller having set
        /// it, since a formatter that is only correct when someone remembers to wrap it is the
        /// same bug with an extra step.
        /// </summary>
        public string ToCsv()
        {
            var row = new StringBuilder(192);

            row.AppendFormat(CultureInfo.InvariantCulture, "{0},{1},{2},{3:F2},{4:F2},{5},",
                             Seed, Controller, RayCount, RayFovDeg, RayLengthM,
                             CompletedLap ? "true" : "false");

            // The one field that is deliberately allowed to be empty.
            if (LapTimeS >= 0f)
            {
                row.AppendFormat(CultureInfo.InvariantCulture, "{0:F3}", LapTimeS);
            }

            row.AppendFormat(CultureInfo.InvariantCulture,
                             ",{0},{1},{2},{3},{4},{5:F4},{6:F4},{7:F2},{8:F3}",
                             CheckpointsAwarded, CheckpointsTotal, CheckpointsSkipped,
                             WallContacts, EndReason, SteerP95DSteer, SteerSignChangesPerS,
                             TimeScale, DurationS);

            return row.ToString();
        }
    }

    /// <summary>
    /// The run record file: one per Play session, one row per run, appended as runs finish.
    ///
    /// **One file across a sweep rather than one per run**, unlike the per-step trace. The trace is
    /// one run's evidence and is read alone; this is the sweep's result table and is read by pandas
    /// as a frame. A directory of thirty-four single-row files would make the reporter's first job
    /// reassembling what the writer had already taken apart.
    ///
    /// The path is fixed when the first row is written and held for the session, so a sweep that
    /// crosses a minute boundary does not split itself in half.
    /// </summary>
    public static class RunRecordWriter
    {
        private static StreamWriter _writer;
        private static string _path;

        /// <summary>
        /// Which folder under `results/` the session's rows go to. Defaults to the scripted
        /// driver's, because that is who wrote the first three years of these files.
        ///
        /// **Set before the first row, or not at all.** The file opens lazily on the first
        /// <see cref="Append"/> and is not reopened, so a change after that is silently ignored
        /// rather than moving rows already written. `DrivingAgent` sets it to "rl" when it is
        /// configured to record (FR-023, T040), which keeps a learned sweep out of the scripted
        /// driver's directory without changing the row format that makes them loadable together.
        ///
        /// One session writes to one folder. Two drivers recording in the same session would have
        /// the last writer win, which no scene does today and which is worth knowing before one
        /// tries.
        /// </summary>
        public static string Folder { get; set; } = "heuristic";

        /// <summary>Where the current session's rows are going, or null before the first row.</summary>
        public static string Path => _path;

        /// <summary>How many rows this session has written. Shown so a sweep can be checked.</summary>
        public static int RowCount { get; private set; }

        /// <summary>
        /// Append one row, opening the file on the first call.
        ///
        /// Flushed per row on purpose, which is the opposite of the per-step trace's decision and
        /// for the same reason: a row happens once per run rather than fifty times a second, so
        /// flushing costs nothing measurable, and a sweep interrupted at seed thirty keeps the
        /// twenty-nine rows it earned.
        /// </summary>
        public static void Append(RunRecord record)
        {
            if (_writer == null && !Open())
            {
                return;
            }

            _writer.WriteLine(record.ToCsv());
            RowCount++;
        }

        private static bool Open()
        {
            try
            {
                string dir = RepoPaths.EnsureDir(
                    System.IO.Path.Combine(RepoPaths.Root, "results", Folder));
                _path = System.IO.Path.Combine(dir, $"runs_{RepoPaths.TimestampStamp()}.csv");

                _writer = new StreamWriter(_path, false, new UTF8Encoding(false))
                {
                    AutoFlush = true,
                };

                _writer.WriteLine(RunRecord.Header());
                RowCount = 0;

                Debug.Log($"[RunRecordWriter] recording runs to {_path}");
                return true;
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[RunRecordWriter] could not open the run record: {e.Message}");
                _writer = null;
                _path = null;
                return false;
            }
        }

        /// <summary>
        /// Close the session's file. Called when play mode ends.
        ///
        /// Statics do not survive a domain reload, so without this the handle would be dropped
        /// rather than closed. Every row is already flushed, so this loses nothing either way; it
        /// exists so the next session opens a fresh file instead of inheriting a stale handle.
        /// </summary>
        public static void Close()
        {
            if (_writer == null)
            {
                return;
            }

            _writer.Flush();
            _writer.Dispose();
            _writer = null;
            _path = null;
            RowCount = 0;
        }
    }
}
