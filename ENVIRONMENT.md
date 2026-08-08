# Development environment (verified)

Machine state as actually probed, not as planned. DESIGN §8 holds the *intended* version
pins; this file records what is **installed and verified**. When the two disagree, this file
is the fact and DESIGN §8 needs updating.

Last verified: **2026-07-26** (Windows 11 Pro 10.0.26200)

## Hardware

| Item | Value |
|------|-------|
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU |
| NVIDIA driver | 592.82 |
| VRAM | 6144 MiB |
| Disk (C:) | 476 G total, 388 G used, **89 G free** (82%) |

6 GB VRAM is sufficient for the M4 PilotNet BC training (small CNN, 66×200 input).
M3 PPO uses vector/raycast observations only and is CPU-bound - GPU is not the bottleneck there.

## Toolchain

| Tool | Version | Notes |
|------|---------|-------|
| Unity Hub | installed | `C:\Program Files\Unity Hub\` |
| Unity Editor | **6000.5.3f1** | satisfies `com.unity.ml-agents` minimum of `6000.0` |
| Unity modules | `windowsstandalonesupport`, `WebGLSupport` | standalone required for headless training builds |
| Python | 3.10.11 | matches DESIGN §8 pin |
| Node | v24.18.0 | for MCP servers |
| npm | 11.0.0 | |
| uv | 0.5.24 | for MCP servers / Python tooling |

## Unity project

`unity/SelfDrivingSim/` - 3D Built-In Render Pipeline.

| Package | Version |
|---------|---------|
| `com.unity.ml-agents` | **4.0.3** (released 2026-04-17) |
| `com.unity.ai.inference` | 2.6.1 (pulled as ML-Agents dependency; formerly Sentis) |
| `com.unity.inputsystem` | 1.19.0 |

### ML-Agents 4.0.3 facts (from the installed package, not from memory)

Sources: `Library/PackageCache/com.unity.ml-agents@*/package.json`, `CHANGELOG.md`,
`Documentation~/Installation.md`, `Documentation~/Examples-setup.md`.

- **Minimum Unity is `6000.0`** (raised in 4.0.0). Our 6000.5.3f1 qualifies.
- **Paired Python package is still `mlagents==1.1.0`** - `Installation.md` line 75 states this
  explicitly for this package version. The corresponding repo branch is `release_23`.
- **The package ships no `Samples~` folder.** CHANGELOG 4.0.0: *"Removed broken sample from the
  package (#6230)."* 3DBall and all other example environments are **only** in the GitHub repo.
  `Examples-setup.md` is explicit: *"If you only install the package from the Package Manager,
  you won't be able to access the example environments."*
- The extensions package `com.unity.ml-agents.extensions` was **merged into the main package**
  in 4.0.0 - do not add it separately.
- Tests moved to a companion package `com.unity.ml-agents.tests` in 4.0.2.
- 4.0.1 set the repo-source Torch constraint to 2.8; the PyPI `mlagents==1.1.0` wheel has a
  looser `torch>=2.1.1` and will resolve much higher. See the venv note below.

## Python environments

Three separate venvs, deliberately. Each exists because installing its packages into one of the
others would move numbers already reported from that one.

### `.venv` - M1 EDA (frozen)

| Package | Version |
|---------|---------|
| numpy | 1.26.4 |
| pandas | 2.1.4 |
| scipy | 1.13.1 |

All M1 numbers in `results/eda/m1_stats.json` and `m1_report.md` were produced under these
versions. **Do not install `mlagents` into this venv** - it hard-pins `numpy==1.23.5`, and a
numpy downgrade risks shifting the reported percentiles and fit statistics, which would break
Constitution VI (reproducibility under SEED=42).

### `.venv-mlagents` - M2–M5 training

Created separately so the M1 environment stays reproducible.

Install order matters - **CUDA torch first**, because `mlagents` otherwise resolves the
CPU-only wheel from PyPI:

```
py -3.10 -m venv .venv-mlagents
.venv-mlagents\Scripts\activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install mlagents==1.1.0
mlagents-learn --help
```

Known resolution result for `mlagents==1.1.0`: `numpy-1.23.5`, `protobuf-3.20.3`,
`grpcio-1.48.2`, `onnx-1.15.0`, `tensorboard-2.20.0`, plus `gym`/`PettingZoo`/`huggingface_hub`.
If the `grpcio` wheel fails to build, install `grpcio==1.48.2` on its own first, then retry
`mlagents`.

### `.venv-bc` - M4 behavioural cloning (feature 004)

A third environment rather than reusing `.venv-mlagents`, for the reason that split the first
two: `mlagents` pins `numpy==1.23.5`, BC needs a newer numpy alongside torch 2.6, and resolving
both in one place would have meant re-pinning the RL environment to suit BC.

```
py -3.10 -m venv .venv-bc
.venv-bc\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-bc.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Verified on this machine: Python 3.10.11, `torch 2.6.0+cu124`, CUDA available, device
**NVIDIA GeForce RTX 3050 6GB Laptop GPU**. That device string is what appears in every BC
`run_record.json`, so a record naming a different device was produced elsewhere.

`requirements-bc.txt` pins exact versions rather than ranges (Principle VI): a range
reconstructs a different environment next month, which is the opposite of what the file is for.

**Which venv runs what.** `python/bc/split.py` and `python/bc/dataset.py` import no torch on
purpose, so every split-level and sample-level decision can still be checked under `.venv`. The
test suite reflects that split: **141 passed** under `.venv-bc`, **87 passed and 3 skipped**
under `.venv`, where the three torch-dependent test modules skip cleanly instead of erroring.

## Example environments (3DBall)

Not available through the Package Manager for 4.0.x. To get them, clone the matching release
branch and open its `Project/` folder as a *separate* Unity project:

```
git clone --branch release_23 https://github.com/Unity-Technologies/ml-agents.git
```

Then Unity Hub → **Add** → **Add project from disk** → select the clone's `Project` folder.
Examples live at `Assets/ML-Agents/Examples`.

Clone this **outside** `RMS/` - it is a reference/verification artifact, not project source,
and must not end up nested in our repo. Cloned to `C:\Users\User\Development\ml-agents\`.

### Gotcha: release_23 does not compile on Unity 6000.5 out of the box

Opening the clone's `Project/` on 6000.5.3f1 raises the *"Enter Safe Mode?"* dialog with one
distinct compilation error, repeated:

```
com.unity.ml-agents\Runtime\Integrations\Match3\Match3ActuatorComponent.cs(61,45): error CS0619:
'Object.GetInstanceID()' is obsolete: 'GetInstanceID is deprecated. Use GetEntityId instead.'
```

Cause: the clone's `Project/Packages/manifest.json` references `file:../../com.unity.ml-agents`,
the **local source in the clone, which is version 4.0.0**, not the 4.0.3 in our project. Unity
6000.5 promoted `GetInstanceID()` to an error-level obsolete, and 4.0.0 predates the fix.
`CS0619` comes from `[Obsolete(..., error: true)]` and therefore **cannot** be silenced with
`#pragma warning disable` - the call site has to change.

Patching that line is **not** sufficient. Rewriting it as
`(int)gameObject.GetEntityId()` merely surfaces the next error - the implicit
`EntityId -> int` conversion operator is *itself* obsolete-as-error - and behind that sit two
further errors from Unity 6000.5's new serialization analyzers:

```
Runtime/Sensors/RigidBodySensorComponent.cs(36,32): error UAC1010
  Field 'm_PoseExtractor' type 'RigidBodyPoseExtractor' is not [Serializable]
Runtime/Inference/TensorProxy.cs(47,23): error UAC1001
  Field 'data' type 'Unity.InferenceEngine.Tensor' is skipped by serialization
```

Those two are in ML-Agents **core runtime** (sensors, inference), not in a sample, and are not
sensibly patchable. Conclusion: **the release_23 source tree (package 4.0.0) is incompatible
with Unity 6000.5.** Do not pursue the 3DBall verification on 6000.5 against a local `file:`
package.

**Resolution: check out the `release/4.0.3` branch, not `release_23`.**

```
git -C C:\Users\User\Development\ml-agents checkout release/4.0.3
```

All three errors disappear and the project compiles clean on 6000.5.3f1. The cause was purely
the version gap - 4.0.3 guards the deprecated API by Unity version, e.g.
`Match3ActuatorComponent.CreateNewSeed()`:

```csharp
#if UNITY_6000_3_OR_NEWER
    return gameObject.GetEntityId().GetHashCode();
#else
    return gameObject.GetInstanceID();
#endif
```

Package mutability (local `file:` vs immutable registry) turned out **not** to be the factor.

**Conclusion: Unity 6000.5.3f1 + ML-Agents 4.0.3 is a working combination.** No need to install
Unity 6000.0 LTS.

> Note: `Installation.md` in the 4.0.3 package tells you to clone `--branch release_23`, but
> that branch ships package source **4.0.0**. The docs are inconsistent with the package they
> ship in. Always match the clone branch to the package version in use.

## Training venv - verified install

`.venv-mlagents` as actually resolved:

| Package | Version |
|---------|---------|
| mlagents | 1.1.0 |
| torch | **2.6.0+cu124** (CUDA build, not the CPU PyPI wheel) |
| numpy | 1.23.5 |
| protobuf | 3.20.3 |
| grpcio | 1.48.2 |

## Running the ML-Agents examples

Examples live in the clone, at `Project/Assets/ML-Agents/Examples/`; training configs at
`config/ppo/*.yaml`.

**Inference only** (C# side check): open
`Assets/ML-Agents/Examples/3DBall/Scenes/3DBall.unity` and press Play. The pretrained `.onnx`
is already assigned in Behavior Parameters.

**Training** (Python bridge check) - Python first, then Play:

```
C:\Users\User\Development\RMS\.venv-mlagents\Scripts\activate
cd C:\Users\User\Development\ml-agents
mlagents-learn config/ppo/3DBall.yaml --run-id=hello3dball
```

Wait for `Listening on port 5004`, then press Play in the Editor. `Ctrl+C` **once** to stop -
that exports the `.onnx`; a second `Ctrl+C` skips the export. Curves via
`tensorboard --logdir results`.

`mlagents-learn` writes `results/` relative to the current directory. For M3, run it from the
`RMS` root so output lands in our own `results/`.

## End-to-end verification (2026-07-26) - PASSED

3DBall trained from scratch through the full Python↔Unity bridge:

```
ml-agents: 1.1.0, ml-agents-envs: 1.1.0, Communicator API: 1.5.0, PyTorch: 2.6.0+cu124
[INFO] Connected to Unity environment with package version 4.0.3 and communication version 1.5.0
[INFO] 3DBall. Step: 132000. Mean Reward: 100.000. Std of Reward: 0.000.
[INFO] Exported results\hello3dball\3DBall\3DBall-432498.onnx
```

- **Communicator API 1.5.0 matches on both sides** - this is the real compatibility proof; the
  Unity package and the pip package negotiate this and refuse to connect on a mismatch.
- Reward reached the 100 ceiling at ~132k steps (~3.6 min); `.onnx` export on `Ctrl+C` works.
- `torch.cuda.is_available()` → `True`, `NVIDIA GeForce RTX 3050 6GB Laptop GPU`.

**Throughput baseline: 432,000 steps in 614 s ≈ 700 steps/s** with 12 parallel agents on a
trivial environment. Our car environment (WheelCollider physics + raycast sensors) will be
substantially slower per step - use this only as an upper bound when sizing `max_steps` in
`config/ppo_car.yaml` for M3.

## Outstanding

- `com.unity.ml-agents` 4.0.3 needs to be (re-)added to `unity/SelfDrivingSim` - it is currently
  absent from that project's `Packages/manifest.json`.
