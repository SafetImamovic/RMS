using System;
using System.Globalization;
using System.IO;
using UnityEngine;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Track
{
    /// <summary>
    /// Thrown when a track file cannot be trusted. Always names the offending field.
    ///
    /// Every check in this file is a refusal rather than a warning. A track that builds
    /// despite failing a check is worse than no track at all, because the failure then
    /// surfaces as an unexplained flat reward curve six hours into a training run, and by
    /// then nobody is looking at the loader.
    /// </summary>
    public class TrackFileException : Exception
    {
        public TrackFileException(string message) : base(message) { }
    }

    /// <summary>
    /// Reads a track written by <c>python -m python.track.export</c>.
    ///
    /// This class is the reason Unity contains no statistics. Everything that needed proving
    /// was proved in Python and written into the file; here the numbers are read, checked for
    /// self-consistency, and handed to whatever places the objects.
    ///
    /// Field names are snake_case throughout the record types because Unity's JsonUtility maps
    /// by field name. Renaming any of them to C# convention would not fail to compile, it
    /// would silently produce zeroes, which is exactly the class of error this loader exists
    /// to catch.
    /// </summary>
    public static class TrackFile
    {
        /// <summary>The only schema this loader understands.</summary>
        public const int ExpectedSchemaVersion = 1;

        /// <summary>Tolerance when comparing the file's profile against the scene's.</summary>
        private const float ProfileTolerance = 1e-3f;

        /// <summary>
        /// Format a number the way the file spells it.
        ///
        /// Every message here quotes a value read out of a JSON file, and JSON writes 3.1.
        /// This machine's locale is bs-Latn-BA, which renders the same float as 3,1000, so a
        /// refusal would describe a value that appears nowhere in the file it is describing.
        /// The drive logger and the HUD force the same culture for the same reason, and there
        /// it was worse: a decimal comma inside a comma-separated file splits one column into
        /// two and silently misaligns every row after the first.
        /// </summary>
        private static string N(float value)
        {
            return value.ToString("0.####", CultureInfo.InvariantCulture);
        }

        /// <summary>
        /// Load and validate a track file.
        /// </summary>
        /// <param name="path">Path to the JSON file.</param>
        /// <param name="sceneProfile">
        /// The profile the scene is running. A track is validated for one car and is not valid
        /// for another, so the file carries the profile it was checked against and the two are
        /// compared here. Pass null to skip that comparison, which is only appropriate in a
        /// tool that is inspecting a file rather than building from it.
        /// </param>
        public static TrackFileRecord Load(string path, VehicleProfile sceneProfile)
        {
            if (!File.Exists(path))
            {
                throw new TrackFileException($"no track file at {path}");
            }

            TrackFileRecord record;
            try
            {
                record = JsonUtility.FromJson<TrackFileRecord>(File.ReadAllText(path));
            }
            catch (Exception e)
            {
                throw new TrackFileException($"{path} is not readable JSON: {e.Message}");
            }

            if (record == null)
            {
                throw new TrackFileException($"{path} parsed to nothing");
            }

            Validate(record, sceneProfile, Path.GetFileName(path));
            return record;
        }

        /// <summary>
        /// Every refusal in the schema contract, checked in the order a reader would.
        ///
        /// Version first: a file from a newer schema may have fields that mean something
        /// different, so nothing else here can be trusted until the version matches.
        /// </summary>
        public static void Validate(TrackFileRecord record, VehicleProfile sceneProfile,
                                    string name)
        {
            if (record.schema_version != ExpectedSchemaVersion)
            {
                throw new TrackFileException(
                    $"{name}: schema_version is {record.schema_version}, expected " +
                    $"{ExpectedSchemaVersion}. Refusing rather than reading the fields that " +
                    "happen to be understood.");
            }

            CheckCentreLine(record, name);
            CheckCheckpoints(record, name);
            CheckGeometryReport(record, name);
            CheckDescriptives(record, name);

            if (sceneProfile != null)
            {
                CheckProfile(record, sceneProfile, name);
            }
        }

        private static void CheckCentreLine(TrackFileRecord record, string name)
        {
            if (record.centre_line == null || record.centre_line.Length < 2)
            {
                int found = record.centre_line?.Length ?? 0;
                throw new TrackFileException(
                    $"{name}: centre_line has {found} points, needs at least 2");
            }

            // Closure is a property of the generating form and must be IMPLIED, never stored
            // as a repeated point. A duplicate would add a zero-length segment to every
            // consumer that walks the line, including arc-length and separation arithmetic.
            CentrePointRecord first = record.centre_line[0];
            CentrePointRecord last = record.centre_line[record.centre_line.Length - 1];

            if (Mathf.Approximately(first.x, last.x) && Mathf.Approximately(first.y, last.y))
            {
                throw new TrackFileException(
                    $"{name}: centre_line repeats its first point at the end " +
                    $"({N(first.x)}, {N(first.y)}). Closure must be implied, not duplicated.");
            }
        }

        private static void CheckCheckpoints(TrackFileRecord record, string name)
        {
            if (record.checkpoints == null || record.checkpoints.Length < 1)
            {
                throw new TrackFileException($"{name}: checkpoints is empty");
            }

            // Progress ordering is the whole purpose of a checkpoint. Out of order, an agent
            // could be rewarded for reaching gate 5 before gate 4, which silently teaches it
            // to cut the track.
            for (int i = 1; i < record.checkpoints.Length; i++)
            {
                if (record.checkpoints[i].s < record.checkpoints[i - 1].s)
                {
                    throw new TrackFileException(
                        $"{name}: checkpoints are not monotonic in s. Index {i} is at " +
                        $"s={N(record.checkpoints[i].s)} after index {i - 1} at " +
                        $"s={N(record.checkpoints[i - 1].s)}.");
                }
            }
        }

        private static void CheckGeometryReport(TrackFileRecord record, string name)
        {
            GeometryReportRecord report = record.geometry_report;
            if (report == null)
            {
                throw new TrackFileException($"{name}: geometry_report is missing");
            }

            // Such a file should not exist. If one does, something wrote it that should not
            // have, and building from it would put a corner on the track that the car
            // physically cannot take.
            if (!report.radius_ok)
            {
                throw new TrackFileException(
                    $"{name}: geometry_report.radius_ok is false. Tightest corner " +
                    $"{N(report.min_radius_m)} m against a floor of " +
                    $"{N(report.r_floor_m)} m.");
            }

            if (report.self_intersects)
            {
                throw new TrackFileException(
                    $"{name}: geometry_report.self_intersects is true");
            }

            if (!report.separation_ok)
            {
                throw new TrackFileException(
                    $"{name}: geometry_report.separation_ok is false, closest approach " +
                    $"{N(report.min_separation_m)} m");
            }
        }

        private static void CheckDescriptives(TrackFileRecord record, string name)
        {
            // Constitution Principle IX is not optional, so a file missing this block is a
            // load failure rather than a missing convenience.
            //
            // JsonUtility fills absent fields with zeroes rather than reporting them, so the
            // absence of the whole block looks identical to a block full of zeroes. n is what
            // separates them: a real distribution has a positive sample count.
            DescriptivesRecord d = record.required_steer_descriptives;
            if (d == null || d.n <= 0)
            {
                throw new TrackFileException(
                    $"{name}: required_steer_descriptives is missing or has n=0. " +
                    "Principle IX requires n, mean, variance, std, min, max and a " +
                    "relative-frequency histogram for every distribution.");
            }

            if (d.histogram == null || d.histogram.relative_frequency == null ||
                d.histogram.relative_frequency.Length == 0)
            {
                throw new TrackFileException(
                    $"{name}: required_steer_descriptives.histogram is missing its " +
                    "relative_frequency");
            }

            if (d.histogram.bin_edges == null ||
                d.histogram.bin_edges.Length != d.histogram.relative_frequency.Length + 1)
            {
                int edges = d.histogram.bin_edges?.Length ?? 0;
                throw new TrackFileException(
                    $"{name}: histogram has {edges} bin_edges for " +
                    $"{d.histogram.relative_frequency.Length} bins, expected " +
                    $"{d.histogram.relative_frequency.Length + 1}");
            }
        }

        private static void CheckProfile(TrackFileRecord record, VehicleProfile scene,
                                         string name)
        {
            VehicleProfileBlock file = record.vehicle_profile;
            if (file == null)
            {
                throw new TrackFileException($"{name}: vehicle_profile block is missing");
            }

            Compare(name, "wheelbase_m", file.wheelbase_m, scene.wheelbaseM);
            Compare(name, "steer_max_deg", file.steer_max_deg, scene.steerMaxDeg);
            Compare(name, "radius_margin", file.radius_margin, scene.radiusMargin);
            Compare(name, "r_min_m", file.r_min_m, scene.RMinM);
            Compare(name, "r_floor_m", file.r_floor_m, scene.RFloorM);
            Compare(name, "max_required_steer", file.max_required_steer,
                    scene.MaxRequiredSteer);
        }

        private static void Compare(string name, string field, float inFile, float inScene)
        {
            if (Mathf.Abs(inFile - inScene) > ProfileTolerance)
            {
                throw new TrackFileException(
                    $"{name}: vehicle_profile.{field} is {N(inFile)} in the file but " +
                    $"{N(inScene)} in the scene. A track is validated for one car and is not " +
                    "valid for another.");
            }
        }
    }

    // ---------------------------------------------------------------------------------------
    // Record types. Snake_case deliberately: JsonUtility maps by field name.
    // ---------------------------------------------------------------------------------------

    [Serializable]
    public class TrackFileRecord
    {
        public int schema_version;
        public int seed;
        public GeneratorBlock generator;
        public VehicleProfileBlock vehicle_profile;
        public float width_m;
        public float total_length_m;
        public CentrePointRecord[] centre_line;
        public CheckpointRecord[] checkpoints;
        public GeometryReportRecord geometry_report;
        public DescriptivesRecord required_steer_descriptives;
    }

    /// <summary>
    /// Enough to rebuild the centre line without trusting the sampled points.
    ///
    /// Not decoration: a reviewer who does not trust the points can regenerate them from this
    /// block and compare, which is what makes a committed track file auditable.
    /// </summary>
    [Serializable]
    public class GeneratorBlock
    {
        public string form;
        public float r0_m;
        public int[] harmonics;
        public float amplitude;
        public float[] phases;
    }

    [Serializable]
    public class VehicleProfileBlock
    {
        public float wheelbase_m;
        public float steer_max_deg;
        public float radius_margin;
        public float r_min_m;
        public float r_floor_m;
        public float max_required_steer;
    }

    [Serializable]
    public class CentrePointRecord
    {
        public float x;
        public float y;
        public float s;
        public float radius_m;

        /// <summary>
        /// Unsigned, derived from radius_m and the profile. Stored rather than recomputed so
        /// the HUD can show it during a keyboard drive without Unity reimplementing the
        /// bicycle model, which would be a second place for it to be wrong.
        /// </summary>
        public float required_steer;
    }

    [Serializable]
    public class CheckpointRecord
    {
        public int index;
        public float x;
        public float y;
        public float forward_x;
        public float forward_y;
        public float s;
    }

    [Serializable]
    public class GeometryReportRecord
    {
        public float min_radius_m;
        public float r_floor_m;
        public bool radius_ok;
        public bool self_intersects;
        public float min_separation_m;
        public bool separation_ok;
    }

    [Serializable]
    public class DescriptivesRecord
    {
        public int n;
        public float mean;
        public float variance;
        public float std;
        public float min;
        public float max;
        public HistogramRecord histogram;
    }

    [Serializable]
    public class HistogramRecord
    {
        public float[] bin_edges;
        public float[] relative_frequency;
    }
}
