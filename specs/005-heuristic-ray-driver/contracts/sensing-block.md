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
  is the single source.
- **Read by** `CarAgent`, on `Awake`, the same way `CarController` already loads `profile`.
- **Mirror-tested by** `python/tests/test_sensing_mirror.py`, in the shape of the existing
  `test_vehicle.py`: the exported file must match the constants it was generated from.

## What the loader must do when the block is missing or wrong

- **Missing block**: refuse and say so. Falling back to hardcoded defaults would reintroduce the
  second copy this contract deletes, and it would do it silently, which is worse than the situation
  today where at least the duplication is visible in the source.
- **Unreadable file**: refuse. `CarAgent` without a sensing configuration has no defensible
  behaviour, and a car that senses with guessed constants produces measurements nobody can trust.
- **`schema_version` unrecognised**: refuse, naming the version found and the version expected.

Refusing loudly at `Awake` costs one obvious error in the console. Guessing costs a sweep whose
numbers look plausible and are not.

## What this contract does not do

**It does not change any value.** 13, 180 and 20 stay exactly as they are. Only where they are read
from moves, so nothing measured in feature 003 is invalidated and FR-018 is not triggered.

Adopting a different arrangement is a separate change, with its own measurement behind it, and it
must state that it invalidates previously measured sensing results and any model trained against
the old arrangement.
