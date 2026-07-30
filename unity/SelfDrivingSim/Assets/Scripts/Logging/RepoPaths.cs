using System.IO;
using UnityEngine;

namespace SelfDrivingSim.Logging
{
    /// <summary>
    /// Where run artefacts are written.
    ///
    /// Both the drive log and the stability log belong in the repository's <c>results/</c>
    /// folder, next to the M1 outputs, because the Python side reads them from there and the
    /// quickstart tells the reader to look there. Unity has no built-in notion of "the
    /// repository", so the path is derived from <c>Application.dataPath</c>, which points at
    /// <c>unity/SelfDrivingSim/Assets</c>: three levels up is the repository root.
    ///
    /// That derivation only holds inside the editor. A standalone build has a different
    /// layout and no repository at all, so a build writes to the platform's own persistent
    /// data folder instead. The distinction matters: a build that silently wrote three
    /// directories above itself would scatter files into wherever the player unzipped it.
    /// </summary>
    public static class RepoPaths
    {
        /// <summary>The repository root in the editor, the persistent data folder in a build.</summary>
        public static string Root
        {
            get
            {
#if UNITY_EDITOR
                return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", ".."));
#else
                return Application.persistentDataPath;
#endif
            }
        }

        /// <summary>Where per-drive CSVs land. Created on demand.</summary>
        public static string DriveLogsDir => EnsureDir(Path.Combine(Root, "results", "drive_logs"));

        /// <summary>Creates the directory if it is missing and returns it either way.</summary>
        public static string EnsureDir(string path)
        {
            if (!Directory.Exists(path))
            {
                Directory.CreateDirectory(path);
            }

            return path;
        }

        /// <summary>
        /// A filename-safe timestamp, sortable as text. Colons are illegal in Windows
        /// filenames, so the usual ISO form cannot be used unchanged.
        /// </summary>
        public static string TimestampStamp()
        {
            return System.DateTime.Now.ToString(
                "yyyy-MM-dd_HH-mm-ss",
                System.Globalization.CultureInfo.InvariantCulture);
        }
    }
}
