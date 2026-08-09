namespace SelfDrivingSim.Logging
{
    /// <summary>Which language the HUD draws in. Toggled with B.</summary>
    public enum HudLanguage
    {
        English,
        Bosnian,
    }

    /// <summary>
    /// Every piece of text the HUD draws, in both languages.
    ///
    /// Two things are deliberately NOT translated. Requirement and criterion codes (FR-005,
    /// SC-003) stay as they are, because they are identifiers pointing at spec.md and a
    /// translated identifier points nowhere. Symbols and units stay too: P95, dsteer, m/s,
    /// vP99. Those are the notation the research and the M1 report already use, and a reader
    /// switching languages should still be able to match a HUD line to the document it came
    /// from.
    ///
    /// Labels are padded to a fixed width by the HUD, so the longest word in either language
    /// sets the column. Bosnian is the wider of the two here.
    /// </summary>
    public sealed class HudStrings
    {
        // Panel headers
        public string Vehicle;
        public string RunVsM1;

        // Live rows
        public string Speed;
        public string Steering;
        public string Throttle;
        public string Brake;
        public string TurnRadius;
        public string BodyTilt;
        public string Resets;
        public string Recording;
        public string Stability;
        public string Off;
        public string Rows;
        public string Breach;

        // Live row suffixes
        public string OfMax;
        public string Straight;
        public string TriggerAt45;
        public string MinShort;
        public string Degrees;
        public string Seconds;

        // Verdict rows
        public string SteerRange;
        public string PeakSpeed;
        public string Need;
        public string Want;
        public string Cap;
        public string Data;
        public string TrackTwoBand;

        // Messages and controls
        public string MissingEnvelope;
        public string MissingEnvelopeFix;
        public string Controls;

        public static readonly HudStrings English = new HudStrings
        {
            Vehicle = "VEHICLE",
            RunVsM1 = "RUN vs M1",

            Speed = "speed",
            Steering = "steering",
            Throttle = "throttle",
            Brake = "brake",
            TurnRadius = "turn radius",
            BodyTilt = "body tilt",
            Resets = "resets",
            Recording = "recording",
            Stability = "stability",
            Off = "off",
            Rows = "rows",
            Breach = "BREACH",

            OfMax = "of max",
            Straight = "(straight)",
            TriggerAt45 = "(trigger at 45)",
            MinShort = "min",
            Degrees = "deg",
            Seconds = "s",

            SteerRange = "steer range",
            PeakSpeed = "peak speed",
            Need = "need",
            Want = "want",
            Cap = "cap",
            Data = "data",
            TrackTwoBand = "track2 P95 band {0}-{1} (the two recordings differ by 2.33x)",

            MissingEnvelope = "vehicle_profile.json is missing its envelope block.",
            MissingEnvelopeFix = "Run: python -m python.track.vehicle",
            Controls = "W/S drive   A/D steer   C view   1-5 views   H hide   R reset run   B language",
        };

        public static readonly HudStrings Bosnian = new HudStrings
        {
            Vehicle = "VOZILO",
            RunVsM1 = "VOŽNJA vs M1",

            Speed = "brzina",
            Steering = "volan",
            Throttle = "gas",
            Brake = "kočnica",
            TurnRadius = "poluprečnik",
            BodyTilt = "nagib",
            Resets = "resetovanja",
            Recording = "snimanje",
            Stability = "stabilnost",
            Off = "isklj.",
            Rows = "redova",
            Breach = "PRESLO",

            OfMax = "od maks.",
            Straight = "(pravo)",
            TriggerAt45 = "(prag 45)",
            MinShort = "min",
            Degrees = "st.",
            Seconds = "s",

            SteerRange = "opseg volana",
            PeakSpeed = "maks. brzina",
            Need = "treba",
            Want = "traži",
            Cap = "maks.",
            Data = "podaci",
            TrackTwoBand = "track2 P95 opseg {0}-{1} (dvije snimke se razlikuju 2.33x)",

            MissingEnvelope = "vehicle_profile.json nema envelope blok.",
            MissingEnvelopeFix = "Pokreni: python -m python.track.vehicle",
            Controls = "W/S vožnja   A/D volan   C pogled   1-5 pogledi   H sakrij   R reset   B jezik",
        };

        public static HudStrings For(HudLanguage language)
        {
            return language == HudLanguage.Bosnian ? Bosnian : English;
        }
    }
}
