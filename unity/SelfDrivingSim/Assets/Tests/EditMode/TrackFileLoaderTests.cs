using System.IO;
using NUnit.Framework;
using UnityEngine;
using SelfDrivingSim.Track;
using SelfDrivingSim.Vehicle;

namespace SelfDrivingSim.Tests
{
    /// <summary>
    /// One deliberately broken file per failure mode in the schema contract, plus the
    /// committed valid file.
    ///
    /// Both directions are needed. A loader asserted only to accept good files is
    /// indistinguishable from one that accepts everything, and this loader's entire job is
    /// refusing. Each test also checks that the message names the offending field, because a
    /// refusal nobody can act on is only marginally better than a crash.
    /// </summary>
    public class TrackFileLoaderTests
    {
        private string _tempDir;
        private VehicleProfile _profile;

        /// <summary>A minimal file that passes every check, as the base for each mutation.</summary>
        private const string ValidJson = @"{
  ""schema_version"": 1,
  ""seed"": 42,
  ""generator"": { ""form"": ""polar_harmonic"", ""r0_m"": 30.0,
                   ""harmonics"": [2,3,4,5], ""amplitude"": 0.5,
                   ""phases"": [0.1,0.2,0.3,0.4] },
  ""vehicle_profile"": { ""wheelbase_m"": 2.5, ""steer_max_deg"": 25.0,
                         ""radius_margin"": 1.3, ""r_min_m"": 5.361,
                         ""r_floor_m"": 6.9696, ""max_required_steer"": 0.789 },
  ""width_m"": 6.0,
  ""total_length_m"": 195.0,
  ""centre_line"": [
    { ""x"": 30.0, ""y"": 0.0, ""s"": 0.0, ""radius_m"": 24.0, ""required_steer"": 0.24 },
    { ""x"": 29.0, ""y"": 1.0, ""s"": 1.4, ""radius_m"": 22.0, ""required_steer"": 0.26 },
    { ""x"": 28.0, ""y"": 2.0, ""s"": 2.8, ""radius_m"": 20.0, ""required_steer"": 0.28 }
  ],
  ""checkpoints"": [
    { ""index"": 0, ""x"": 30.0, ""y"": 0.0, ""forward_x"": 0.0, ""forward_y"": 1.0, ""s"": 0.0 },
    { ""index"": 1, ""x"": 29.0, ""y"": 1.0, ""forward_x"": 0.0, ""forward_y"": 1.0, ""s"": 1.4 }
  ],
  ""geometry_report"": { ""min_radius_m"": 16.4, ""r_floor_m"": 6.9696, ""radius_ok"": true,
                         ""self_intersects"": false, ""min_separation_m"": 22.3,
                         ""separation_ok"": true },
  ""required_steer_descriptives"": { ""n"": 2000, ""mean"": 0.2, ""variance"": 0.01,
                                     ""std"": 0.1, ""min"": 0.05, ""max"": 0.55,
                                     ""histogram"": { ""bin_edges"": [0.0, 0.5, 1.0],
                                                      ""relative_frequency"": [0.6, 0.4] } }
}";

        [SetUp]
        public void SetUp()
        {
            _tempDir = Path.Combine(Path.GetTempPath(), "rms_trackfile_tests");
            Directory.CreateDirectory(_tempDir);
            _profile = new VehicleProfile();
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tempDir))
            {
                Directory.Delete(_tempDir, recursive: true);
            }
        }

        private string Write(string json, string name)
        {
            string path = Path.Combine(_tempDir, name);
            File.WriteAllText(path, json);
            return path;
        }

        /// <summary>Load a mutated copy of the valid file and return the refusal message.</summary>
        private string RefusalFor(string find, string replace, string name)
        {
            Assert.That(ValidJson, Does.Contain(find),
                "the fixture no longer contains the text this test mutates");

            string path = Write(ValidJson.Replace(find, replace), name);
            var thrown = Assert.Throws<TrackFileException>(
                () => TrackFile.Load(path, _profile));

            return thrown.Message;
        }

        // -----------------------------------------------------------------------------------
        // The valid direction
        // -----------------------------------------------------------------------------------

        [Test]
        public void AValidFileLoads()
        {
            string path = Write(ValidJson, "valid.json");

            TrackFileRecord record = TrackFile.Load(path, _profile);

            Assert.That(record.seed, Is.EqualTo(42));
            Assert.That(record.schema_version, Is.EqualTo(TrackFile.ExpectedSchemaVersion));
            Assert.That(record.centre_line.Length, Is.EqualTo(3));
            Assert.That(record.checkpoints.Length, Is.EqualTo(2));
            Assert.That(record.geometry_report.radius_ok, Is.True);
            Assert.That(record.required_steer_descriptives.n, Is.EqualTo(2000));
        }

        [Test]
        public void TheCommittedTrackFilesLoad()
        {
            // The real thing, not a fixture. If export.py and this loader ever disagree about
            // the schema, no hand-written fixture would show it.
            string dir = Path.Combine(Application.dataPath, "Tracks");
            if (!Directory.Exists(dir))
            {
                Assert.Ignore("no Tracks folder; run python -m python.track.export --batch all");
            }

            string[] files = Directory.GetFiles(dir, "seed_*.json");
            if (files.Length == 0)
            {
                Assert.Ignore("no committed track files to check");
            }

            foreach (string file in files)
            {
                Assert.DoesNotThrow(() => TrackFile.Load(file, _profile),
                    $"{Path.GetFileName(file)} failed to load");
            }
        }

        [Test]
        public void TheGeneratorBlockIsCarriedSoTheTrackCanBeRebuilt()
        {
            TrackFileRecord record = TrackFile.Load(Write(ValidJson, "gen.json"), _profile);

            Assert.That(record.generator.form, Is.EqualTo("polar_harmonic"));
            Assert.That(record.generator.harmonics.Length,
                        Is.EqualTo(record.generator.phases.Length));
        }

        // -----------------------------------------------------------------------------------
        // One refusal per failure mode
        // -----------------------------------------------------------------------------------

        [Test]
        public void AnUnknownSchemaVersionIsRefusedNamingBothVersions()
        {
            string message = RefusalFor(@"""schema_version"": 1", @"""schema_version"": 2",
                                        "version.json");

            Assert.That(message, Does.Contain("schema_version"));
            Assert.That(message, Does.Contain("2"));
            Assert.That(message, Does.Contain("1"));
        }

        [Test]
        public void AProfileMismatchIsRefusedNamingTheField()
        {
            string message = RefusalFor(@"""wheelbase_m"": 2.5", @"""wheelbase_m"": 3.1",
                                        "profile.json");

            Assert.That(message, Does.Contain("wheelbase_m"));
            Assert.That(message, Does.Contain("3.1"));
        }

        [Test]
        public void RefusalsQuoteNumbersTheWayTheFileSpellsThem()
        {
            // This machine's locale is bs-Latn-BA, which renders 3.1 as "3,1". A refusal
            // formatted in the machine locale describes a value that appears nowhere in the
            // JSON file it is describing, and on a different machine the same message would
            // read differently. Caught by exactly this assertion the first time it ran.
            string message = RefusalFor(@"""wheelbase_m"": 2.5", @"""wheelbase_m"": 3.1",
                                        "locale.json");

            Assert.That(message, Does.Contain("3.1"));
            Assert.That(message, Does.Not.Contain("3,1"));
        }

        [Test]
        public void AProfileMismatchIsSkippedWhenNoSceneProfileIsGiven()
        {
            // A tool inspecting a file has no scene to compare against, and should still be
            // able to read one written for a different car.
            string path = Write(ValidJson.Replace(@"""wheelbase_m"": 2.5",
                                                  @"""wheelbase_m"": 3.1"), "noprofile.json");

            Assert.DoesNotThrow(() => TrackFile.Load(path, null));
        }

        [Test]
        public void ARadiusFailureIsRefused()
        {
            string message = RefusalFor(@"""radius_ok"": true", @"""radius_ok"": false",
                                        "radius.json");

            Assert.That(message, Does.Contain("radius_ok"));
        }

        [Test]
        public void ASelfIntersectingTrackIsRefused()
        {
            string message = RefusalFor(@"""self_intersects"": false",
                                        @"""self_intersects"": true", "cross.json");

            Assert.That(message, Does.Contain("self_intersects"));
        }

        [Test]
        public void ASeparationFailureIsRefused()
        {
            string message = RefusalFor(@"""separation_ok"": true",
                                        @"""separation_ok"": false", "sep.json");

            Assert.That(message, Does.Contain("separation_ok"));
        }

        [Test]
        public void ACentreLineShorterThanTwoPointsIsRefused()
        {
            string json = ValidJson.Replace(
                @"{ ""x"": 29.0, ""y"": 1.0, ""s"": 1.4, ""radius_m"": 22.0, ""required_steer"": 0.26 },
    { ""x"": 28.0, ""y"": 2.0, ""s"": 2.8, ""radius_m"": 20.0, ""required_steer"": 0.28 }",
                "");
            string path = Write(json.Replace(@"0.24 },", "0.24 }"), "short.json");

            var thrown = Assert.Throws<TrackFileException>(
                () => TrackFile.Load(path, _profile));

            Assert.That(thrown.Message, Does.Contain("centre_line"));
            Assert.That(thrown.Message, Does.Contain("at least 2"));
        }

        [Test]
        public void ACentreLineThatRepeatsItsFirstPointIsRefused()
        {
            // Closure must be implied. A duplicated endpoint adds a zero-length segment to
            // every consumer that walks the line.
            string message = RefusalFor(
                @"{ ""x"": 28.0, ""y"": 2.0, ""s"": 2.8, ""radius_m"": 20.0, ""required_steer"": 0.28 }",
                @"{ ""x"": 30.0, ""y"": 0.0, ""s"": 2.8, ""radius_m"": 20.0, ""required_steer"": 0.28 }",
                "closed.json");

            Assert.That(message, Does.Contain("repeats its first point"));
        }

        [Test]
        public void CheckpointsOutOfArcLengthOrderAreRefused()
        {
            string message = RefusalFor(
                @"""forward_y"": 1.0, ""s"": 1.4 }",
                @"""forward_y"": 1.0, ""s"": -0.5 }",
                "order.json");

            Assert.That(message, Does.Contain("monotonic"));
        }

        [Test]
        public void MissingDescriptivesAreRefusedNamingThePrinciple()
        {
            string message = RefusalFor(@"""n"": 2000", @"""n"": 0", "descriptives.json");

            Assert.That(message, Does.Contain("required_steer_descriptives"));
            Assert.That(message, Does.Contain("Principle IX"));
        }

        [Test]
        public void AHistogramWithMismatchedEdgesIsRefused()
        {
            string message = RefusalFor(@"""bin_edges"": [0.0, 0.5, 1.0]",
                                        @"""bin_edges"": [0.0, 1.0]", "hist.json");

            Assert.That(message, Does.Contain("bin_edges"));
        }

        [Test]
        public void AMissingFileIsRefusedRatherThanCrashing()
        {
            var thrown = Assert.Throws<TrackFileException>(
                () => TrackFile.Load(Path.Combine(_tempDir, "absent.json"), _profile));

            Assert.That(thrown.Message, Does.Contain("no track file"));
        }

        [Test]
        public void UnreadableJsonIsRefusedRatherThanCrashing()
        {
            string path = Write("{ this is not json", "broken.json");

            Assert.Throws<TrackFileException>(() => TrackFile.Load(path, _profile));
        }
    }
}
