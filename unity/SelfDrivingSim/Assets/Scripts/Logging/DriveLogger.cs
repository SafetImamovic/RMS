using System.Globalization;
using System.IO;
using UnityEngine;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Logging
{
    /// <summary>
    /// Writes a drive to results/drive_logs/&lt;timestamp&gt;.csv in the dataset's own terms.
    ///
    /// The columns are the recorded human ones - <c>steering</c>, <c>throttle</c>,
    /// <c>brake</c>, <c>speed</c> - plus <c>t</c> and <c>source</c> (FR-008). Using the
    /// dataset's names is not cosmetic: compare_drive holds this file against the M1
    /// distributions, and a column named <c>steerAngle</c> in degrees would have to be
    /// converted somewhere, which is the point at which a comparison quietly starts measuring
    /// the conversion instead of the driving.
    ///
    /// **Sampled in FixedUpdate, at the physics rate.** Logging once per rendered frame would
    /// make the file's contents depend on the machine's frame rate, so the same drive on two
    /// computers would produce two different steering-change distributions. The physics step
    /// is fixed (0.02 s by default), so the file has one known rate that Python can resample
    /// from. Research C14 puts the resampling to 14.08 Hz on the Python side, deliberately:
    /// the log keeps the full-rate truth and compare_drive decides what to compare at.
    ///
    /// A run that lasted less than a couple of seconds is deleted rather than written. Play
    /// mode gets entered and left constantly while wiring a scene, and a folder of two-row
    /// CSVs makes it harder to find the drive that mattered.
    /// </summary>
    [RequireComponent(typeof(CarController))]
    public class DriveLogger : MonoBehaviour
    {
        [Tooltip("Value written into the source column. The dataset uses track1 and track2; " +
                 "this names the other side of the comparison.")]
        [SerializeField] private string sourceLabel = "unity";

        [Tooltip("Runs shorter than this are deleted when they end, not kept.")]
        [SerializeField] private float minKeepSeconds = 2f;

        [Tooltip("Rows buffered before the writer flushes to disk. A crash loses at most this " +
                 "many rows; flushing every row would stall the physics step.")]
        [SerializeField] private int flushEveryRows = 256;

        private CarController _car;
        private StreamWriter _writer;
        private string _path;
        private float _elapsed;
        private int _rows;
        private int _sinceFlush;

        /// <summary>Where the current run is being written. Null when not recording.</summary>
        public string CurrentPath => _path;

        /// <summary>Whether a file is open and taking rows.</summary>
        public bool IsRecording => _writer != null;

        /// <summary>Rows written so far this run.</summary>
        public int RowCount => _rows;

        /// <summary>Seconds recorded so far this run.</summary>
        public float ElapsedS => _elapsed;

        /// <summary>The rate rows are written at. The reciprocal of the physics step.</summary>
        public float LogHz => 1f / Time.fixedDeltaTime;

        private void Awake()
        {
            _car = GetComponent<CarController>();
        }

        private void OnEnable()
        {
            BeginRun();
        }

        private void OnDisable()
        {
            // Leaving Play mode must close the file. A StreamWriter that is never disposed
            // loses whatever is still in its buffer, which is the tail of the drive.
            EndRun();
        }

        /// <summary>Close the current file and open a new one. Bound to the telemetry reset key.</summary>
        public void BeginRun()
        {
            EndRun();

            try
            {
                _path = Path.Combine(RepoPaths.DriveLogsDir, $"{RepoPaths.TimestampStamp()}.csv");
                _writer = new StreamWriter(_path, append: false);
                _writer.WriteLine("t,steering,throttle,brake,speed,speed_mag,x,y,z,yaw_deg,source");
            }
            catch (IOException e)
            {
                Debug.LogError($"[DriveLogger] could not open a drive log: {e.Message}");
                _writer = null;
                _path = null;
            }

            _elapsed = 0f;
            _rows = 0;
            _sinceFlush = 0;
        }

        /// <summary>Close the file, discarding it if the run was too short to be worth keeping.</summary>
        public void EndRun()
        {
            if (_writer == null)
            {
                return;
            }

            _writer.Flush();
            _writer.Dispose();
            _writer = null;

            if (_elapsed < minKeepSeconds || _rows == 0)
            {
                TryDelete(_path);
                _path = null;
                return;
            }

            Debug.Log($"[DriveLogger] wrote {_rows:N0} rows over {_elapsed:F1}s at " +
                      $"{LogHz:F0} Hz -> {_path}");
        }

        private static void TryDelete(string path)
        {
            try
            {
                if (path != null && File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch (IOException)
            {
                // Nothing worth failing a drive over.
            }
        }

        private void FixedUpdate()
        {
            if (_writer == null || _car == null)
            {
                return;
            }

            _elapsed += Time.fixedDeltaTime;

            // Every number is formatted invariantly. This machine's locale is bs-Latn-BA,
            // which writes 0,5 rather than 0.5; inside a comma-separated file that turns one
            // column into two and every row after the first would be silently misaligned.
            // The HUD forces the same culture for the same reason.
            // speed is the forward projection, which is what the dataset's own column means
            // and therefore what compare_drive uses. speed_mag is the actual ground speed.
            // Both are recorded because their disagreement is itself a measurement: it is
            // how the car was caught exceeding its stated top speed by 61 percent.
            //
            // Position and heading are here for the turning-circle check (T022), which
            // cannot be done from speed alone: a circle has to be fitted to a path.
            Vector3 p = transform.position;
            _writer.WriteLine(string.Format(
                CultureInfo.InvariantCulture,
                "{0:F4},{1:F5},{2:F4},{3:F4},{4:F5},{5:F5},{6:F4},{7:F4},{8:F4},{9:F3},{10}",
                _elapsed,
                _car.SteerNorm,
                _car.Throttle,
                _car.Brake,
                _car.SpeedMs,
                _car.SpeedMagnitudeMs,
                p.x,
                p.y,
                p.z,
                transform.eulerAngles.y,
                sourceLabel));

            _rows++;
            if (++_sinceFlush >= flushEveryRows)
            {
                _writer.Flush();
                _sinceFlush = 0;
            }
        }
    }
}
