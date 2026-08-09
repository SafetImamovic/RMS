# Contract: the `sensing` block in `vehicle_profile.json`

`unity/SelfDrivingSim/Assets/Tracks/vehicle_profile.json` currently carries two blocks, `profile`
and `envelope`, both written by `python.track.vehicle.export_profile` and both read by Unity. This
contract adds a third.

## Why it exists

The ray configuration is written down twice today. `RAY_COUNT`, `RAY_FOV_DEG` and `RAY_LENGTH_M`
are in `python/track/config.py`; the same three numbers are serialised fields on `CarAgent`.
Nothing checks that they agree. `CarAgent`'s own comment states the consequence plainly: changing a
ray constant means changing it in both places by hand.

This feature makes that worse before it makes it better, because US3 varies the arrangement across
a sweep. A sweep that edited the scene per configuration would be a manual step inside an automated
run, and the two copies would diverge the first time one edit was missed.

So the block is not bookkeeping. **It is what makes FR-013 and FR-016 true at the same time.**

## Shape

```json
{
  "schema_version": 3,
  "source": "python/track/config.py via python.track.vehicle.export_profile",
  "profile":  { "...": "unchanged" },
  "envelope": { "...": "unchanged" },
  "sensing": {
    "ray_count": 13,
    "ray_fov_deg": 180.0,
    "ray_length_m": 20.0
  }
}
```

`schema_version` goes from 2 to 3. The loader must reject a file it does not understand rather than
reading a block that may have moved; feature 003's track loader already works this way.

## Field rules

| Field | Rule |
|---|---|
| `ray_count` | Integer, at least 1. An odd count puts one ray straight ahead; an even count does not, and `CarAgent` warns. The warning stays a warning, because whether the centre ray matters is one of the questions the sweep asks |
| `ray_fov_deg` | Float in (0, 360]. The total span, centred on the nose, not the half-angle |
| `ray_length_m` | Float above 0. Also the divisor of the normalised reading, so changing it rescales every ray observation |

**Ray spacing is not a field.** It is `ray_fov_deg / (ray_count - 1)`, derived at both ends. Storing
it alongside the two values it comes from would create a third copy that can disagree with the
first two, which is the exact failure this block exists to remove.

## Who reads and writes it

- **Written by** `python.track.vehicle.export_profile`, from the constants in `config.py`. Python
  is the single source of the intended values.
- **Mirror-tested by** `python/tests/test_sensing_mirror.py`: the exported file must match the
  constants it was generated from.
- **Drift-checked at startup** against the ray fields serialised on `CarAgent` in the scene, in the
  shape of `DriveTelemetry.WarnIfProfileDrifted`.

**Corrected 2026-08-09, during implementation.** This section originally said `CarAgent` would load
the block on `Awake`, "the same way `CarController` already loads `profile`". `CarController` does
no such thing: `VehicleProfile` holds a compiled copy so the car does not depend on a file at
runtime, and `DriveTelemetry` is what reads the file, in order to **check** the scene rather than to
feed it.

## The two gaps, and why one mechanism cannot close both

| Gap | Closed by | Why the other cannot |
|---|---|---|
| `config.py` disagrees with the exported file | `pytest` mirror test | It never opens the Unity scene |
| The exported file disagrees with the scene | Startup drift check | It runs in the editor, not in CI |

The second gap is not hypothetical. `DriveTelemetry`'s comment records the incident that produced
that check: retuning the steering rate from 2.0 to 3.7 left the scene on 2.0, and **the only
symptom would have been a drive that mysteriously failed to improve.** `CarAgent`'s ray fields are
serialised the same way and can go stale the same way.

## What the drift check must do

- **Fields disagree**: `Debug.LogError` naming the field, the scene's value and the exported value,
  and stating that this run is sensing with the wrong fan. Match the wording style of
  `DriveTelemetry.CheckField`, which tells the reader where to fix it rather than only that
  something is wrong.
- **Missing block**: error, naming the regeneration command. A file predating this contract has no
  `sensing` key, and silence would leave the reader assuming it had been checked.
- **`schema_version` unrecognised**: error, naming the version found and the version expected.
- **File missing entirely**: warn rather than error, matching `DriveTelemetry`. A clone that has not
  run the exporter yet is a setup state, not a corrupted one.

**The check never overwrites the scene.** It reports. A check that silently corrected the fan would
mean the values in the Inspector no longer describe the run, which is the same class of problem it
exists to catch.

## Varying the fan for a sweep

The sweep sets `ray_count` and `ray_fov_deg` on `CarAgent` programmatically at runtime, not by
rewriting this file. Rewriting per configuration would need a reload between configurations, which
SC-004's five minute budget cannot afford.

**The drift check is suppressed while a sweep is running**, because during a sweep the scene
deliberately disagrees with the exported file and one error per seed would bury the run. Every run
record carries its own `ray_count`, `ray_fov_deg` and `ray_length_m`, so the configuration a figure
came from is recoverable from the results rather than from this file.

## What this contract does not do

**It does not change any value.** 13, 180 and 20 stay exactly as they are. Only where they are read
from moves, so nothing measured in feature 003 is invalidated and FR-018 is not triggered.

Adopting a different arrangement is a separate change, with its own measurement behind it, and it
must state that it invalidates previously measured sensing results and any model trained against
the old arrangement.
