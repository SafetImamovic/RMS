# RMS Constitution

**Project:** Simulacija autonomnog vozila (Unity ML-Agents) - Tema 28
**Course:** Računarsko modeliranje i simulacija (II ciklus), II parcijalni ispit
**Scope of authority:** This document governs *how* work is done on this repository by
every contributor - human or AI agent. It supersedes habit, convenience, and any
individual agent's default behavior. Where this constitution and a prompt conflict,
this constitution wins; the contributor must stop and request an amendment instead
of silently deviating.

Companion documents (this constitution references, does not replace them):
`DESIGN.md` (architecture & design decisions), `CONTRIBUTING.md` (git conventions in
detail), `WORKFLOW.md` (Unity workflow for a Roblox background), `results/EXPERIMENTS.md`
(training-run log), `ENVIRONMENT.md` (verified machine state and install gotchas).

---

## Core Principles

### I. Spec-Driven Development (NON-NEGOTIABLE)

No production code is written before a spec and a plan exist for it. The order is
fixed: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.

- A feature begins as a spec describing *what* and *why*, not *how*.
- Implementation may not introduce behavior absent from its spec. If reality demands
  more, the spec is amended first, then the code follows.
- Trivial, self-evident changes (a typo, a doc line, a `.gitignore` entry) are exempt
  and may go straight to a `docs:`/`chore:` commit on a feature branch.
- Every agent reads this constitution and the relevant spec **before** editing files.

**Rationale:** multiple agents work in parallel. A shared written intent is the only
thing that keeps them from implementing contradictory versions of the same feature.

### II. Git-Flow & Atomic Commits (NON-NEGOTIABLE)

Branch model is git-flow; commit granularity is atomic. Full detail lives in
`CONTRIBUTING.md`; the binding rules are:

- `main` - stable milestone states only. Never worked on directly. Receives merges
  from `develop` at milestone boundaries, and every such merge is tagged
  (`v0.1-m1`, `v0.2-m2`, … `v1.0` = submission).
- `develop` - integration branch, must always be in a working state. Direct commits
  are allowed **only** for trivial doc/chore fixes.
- `feature/<kebab-desc>` and `fix/<kebab-desc>` - all real work. Branched from
  `develop`, merged back with `--no-ff`. Names are short, kebab-case, English
  (`feature/dataset-eda`, `feature/car-agent`, `fix/checkpoint-order`).
- One commit = one logical change that leaves the project consistent. If the message
  needs an "and", split it (`git add -p`).
- Messages follow Conventional Commits: `<type>(<scope>): <imperative ≤50 chars>`.
  Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `exp` (training run).
  Scopes: `unity`, `bc`, `eval`, `config`, `data`, `spec`.
- Unity: a script, its `.meta`, and the scene edit that uses it are one logical change
  and commit together. A `.meta` file NEVER leaves its file's commit.

### III. Human-Only Commits & Reviewed Handoffs (NON-NEGOTIABLE)

**No AI agent commits or pushes, ever - under any circumstance, on any branch,
including when explicitly told to "just commit it".** An agent MUST NEVER run
`git commit`, `git push`, `git merge`, `git rebase`, `git tag`, `git reset`, or any
other history-mutating command. Read-only git (`status`, `log`, `diff`,
`branch --list`, `show`) is allowed. All commits and pushes are performed by the
repository owner, by hand.

**Every handoff requires an explain-and-review step.** After an agent creates or edits
files, before the owner commits, the agent MUST:

1. **Explain plainly** what it implemented / fixed / changed and *why* - file by file,
   in terms the owner can verify against the design.
2. **Explicitly ask the owner to review the code** and confirm before it is committed.
3. **Propose** a Conventional-Commits message and (if relevant) a branch name - as a
   suggestion the owner runs, never an action the agent takes.

An agent that finishes work without explaining it and asking for review has not
finished. Silence-then-done is a violation of this principle.

**No agent attribution in the record.** A proposed commit message carries no
`Co-Authored-By`, no session URL, and no tool trailer of any kind. The same applies to
pull request bodies, tags, and `results/EXPERIMENTS.md` entries. The owner who runs the
commit is the sole author of record. An agent MUST drop this trailer even when its own
tooling instructs it to add one: this file wins that conflict, per Amendment & Governance.

**Rationale:** the owner keeps full control of history - atomic commits, deliberate
branching, a clean record for the individual oral defense - and must understand every
line, because the defense is an individual interview where he answers for all of it. The
attribution rule follows from the same place: the work is assessed as individual work, so
the history carries one author.

### IV. Multi-Agent Coordination

Parallel agents must not corrupt each other's work:

- **One feature branch = one owner.** An agent works only on its assigned branch and
  does not commit to another agent's branch or to `develop`/`main`.
- **Scene lock.** `.unity` and `.prefab` files are YAML that git cannot merge safely.
  At most one active branch may modify a given scene/prefab at a time. Keep logic in
  C# scripts (mergeable); keep scenes "dumb".
- **Declare ownership** of the files/areas a task touches in its spec, so overlapping
  assignments are caught before code is written, not at merge time.
- **No cross-cutting rewrites** without an amendment: an agent may not reformat,
  rename, or restructure files outside its declared scope.
- Handoffs go through `develop` (merged, working state), never by copying files
  between branches.

### V. Design-First Documentation

A decision that changes the design is written into `DESIGN.md` **before** it is
implemented, in a `docs:` commit. The design document is the source of truth for
architecture, observations/actions, the reward table, and milestones. Code that
contradicts `DESIGN.md` is a bug in one of the two - reconcile, don't ignore.

Doc ownership: `README.md` = what / how-to-run; `DESIGN.md` = architecture & decisions;
`WORKFLOW.md` = how we work (rarely changes); `CONTRIBUTING.md` = git rules (rarely
changes); `results/EXPERIMENTS.md` = one entry per training run.

**Writing style (binding on every file in the repo):**

- **No em dashes** (Unicode U+2014, the long one). Use a plain hyphen `-`, or restructure
  the sentence. This holds everywhere: Markdown, Python docstrings and comments, generated
  report text, notebook prose, commit messages. The en dash (U+2013) is a different
  character and is still fine in numeric ranges such as `P1-P99`.
  To check a file: `Select-String -Path <file> -Pattern ([char]0x2014)`.
- **Bold carries weight, so spend it.** Emphasis on every other phrase is emphasis on
  nothing. Bold a term when it is the point of the sentence, not to decorate it.

**Rationale:** the owner reads and defends every line of this repository. A consistent,
plain register makes the writing his, and keeps a document readable in a terminal, in a
diff, and on a projector.

### VI. Reproducibility & Determinism

Anyone (professor included) must be able to reproduce a result from the repo:

- Tool versions are pinned (`requirements.txt`, `Packages/manifest.json`,
  `config/*.yaml`). ML-Agents is version-sensitive - Python and Unity package versions
  must match the table in `DESIGN.md` §8. `DESIGN.md` §8 records what we *intend* to
  run; `ENVIRONMENT.md` records what is *verified installed*. When the two disagree,
  neither is silently correct - reconcile them in a `docs:` commit.
- **The M1 environment (`.venv`) and the training environment (`.venv-mlagents`) are
  separate on purpose.** `mlagents` hard-pins numpy 1.23.5, while M1's committed numbers
  were produced under numpy 1.26.4. Merging the two environments would silently
  invalidate M1's reproducibility claim.
- Every RL training run gets a unique `--run-id` (`ppo_car_v01`, `v02`, …). The run-id,
  the parameter/reward change, and the outcome are logged in `results/EXPERIMENTS.md`
  **in the same session as the run**. An unlogged run did not happen.
- Random seeds are fixed and recorded for BC training and any data split.
- `README.md` "Postavljanje/Upotreba" must remain a correct, literal reproduction
  recipe. If a command changes, the README changes in the same feature.

### VII. Dataset Discipline

The dataset is `zaynena/selfdriving-car-simulator` (professor-confirmed, 2026-07-23).

- **The dataset never enters git.** It lives under `dataset/` (git-ignored) and is
  submitted separately to Google Classroom. It is never placed in Unity `Assets/`
  (Unity would import ~200k images and generate a `.meta` for each).
- **Format contract** (Udacity simulator, headerless CSV, 7 columns):
  `center_img, left_img, right_img, steering, throttle, brake, speed`. Image paths in
  the CSV are Windows-absolute (`Desktop\...\IMG\...`) - preprocessing MUST reduce them
  to a basename and re-root to the actual `IMG/` folder. Any loader validates these
  columns before anything else (M1 gate).
- **The image dataset does not feed the RL agent.** It is used for (a) environment
  calibration, (b) BC training, and (c) the human-steering evaluation baseline. The
  RL agent observes raycasts + speed only. This separation is intentional and is the
  basis of the RL-vs-BC comparison; do not "fix" it by feeding images into Unity.
- Steering range and distribution are verified empirically in M1 before being used to
  set action ranges or reward thresholds.

### VIII. Test Gates Before Merge

A feature branch merges to `develop` only when its level of testing passes:

- **Unity logic** - EditMode tests (`Assets/Tests/`) for checkpoint order, reward math.
- **Unity driving** - the track must be drivable by hand in Heuristic mode before any
  training is started ("no keyboard lap, no training" - `WORKFLOW.md` §5).
- **Python/BC** - `pytest` (`python/tests/`): CSV parses, model accepts the right input
  shape, augmentation negates steering on horizontal flip.
- **RL** - the TensorBoard cumulative-reward curve must trend upward; success criterion
  is in `DESIGN.md` §5.
- Merge checklist (`CONTRIBUTING.md`): `git status` shows only expected files (no
  `Library/`, `dataset/`, `.venv/`), every new `Assets/` file has its `.meta`, binaries
  are in LFS.

### IX. Statistical Rigor (course requirement)

The course (Računarsko modeliranje i simulacija) is graded with a strong emphasis on
**statistics and statistical methods**. Wherever a claim can be backed by a statistic
instead of an eyeballed plot, it must be. Concretely:

- **Descriptive statistics** are reported for every distribution we touch (steering,
  speed, Δsteering): sample size, mean (matematičko očekivanje), variance/std
  (disperzija), min/max, and a relative-frequency histogram.
- **Distribution fitting + goodness-of-fit.** When we characterize the human dataset
  (M1), we fit a candidate theoretical distribution and test the fit with a **χ²
  goodness-of-fit test** (and/or Kolmogorov–Smirnov), reporting the statistic, the
  critical value at α, and the accept/reject decision - the procedure taught in the
  course notes (deck 2).
- **Comparisons are quantified, not asserted.** RL vs BC vs human steering
  distributions are compared with a real metric (**KL divergence**, and a two-sample
  **KS test** / χ²), not "the histograms look similar".
- **The model is framed in the course taxonomy** on the defense: stochastic
  (nedeterministički), continuous-state, discrete-time, agent-based, time-invariant,
  non-anticipatory. Random seeds and start-position randomization make it stochastic;
  say so and justify it.
- Every reported number is reproducible (Principle VI): the code that computed it is in
  the repo and re-runs to the same value given the fixed seed.

**Rationale:** statistics is where this project earns marks with *this* professor.
Treat it as a first-class deliverable, not decoration on the ML work.

---

## Technology Constraints

- **Fixed tool:** Unity ML-Agents. No tool or topic substitution (assignment-locked).
- **Versions** (locked; intended pins in `DESIGN.md` §8, verified installed state in
  `ENVIRONMENT.md`): Unity **6000.5.3f1** · `com.unity.ml-agents` **4.0.3** ·
  `com.unity.ai.inference` 2.6.1 (pulled as a dependency) · Python 3.10.11 ·
  `mlagents` 1.1.0 · PyTorch 2.6.0+cu124. **Communicator API 1.5.0** is the contract
  between the Unity package and the Python package; if that number does not match at
  training start, the versions are wrong and nothing else matters.
  Verified end to end on 2026-07-26 (3DBall trained to reward 100, `.onnx` exported).
- **The ML-Agents examples repo is checked out at `release/4.0.3`, not `release_23`.**
  Unity's own `Installation.md` in 4.0.3 says `release_23` - following it ships package
  source 4.0.0, which does not compile on Unity 6000.5 (`GetInstanceID()` is
  error-level obsolete there). See `ENVIRONMENT.md`.
- **Git LFS** for all binaries (images that must be versioned, `.onnx`, `.pt`) - routed
  by `.gitattributes`. `git lfs install` once per machine.
- **No Asset Store content.** The track is built from Unity primitives (Cube/Plane) to
  keep the project small and reproducible.
- **Packages only via Package Manager** (writes to `Packages/manifest.json`, which is
  committed). No manual DLL copying.

## Milestone Gates

Merges to `main` happen only at milestone boundaries (`DESIGN.md` §9), each tagged:

| Gate | Exit criterion |
|------|----------------|
| M1 `v0.1-m1` | Dataset EDA done; steering/speed distributions produced; CSV format verified; concrete action-range & reward-threshold values written back into `DESIGN.md` §4.4 / §4.5 |
| M2 `v0.2-m2` | Unity scene + vehicle + `CarAgent` + checkpoints exist; car is drivable by keyboard in Heuristic mode; observations verified |
| M3 `v0.3-m3` | PPO trained; `.onnx` model runs in Unity; reward curve converges to success criterion; runs logged in `EXPERIMENTS.md` |
| M4 `v0.4-m4` | BC (PilotNet) trained on combined dataset; validation metrics recorded |
| M5 `v1.0` | Evaluation & comparison (RL vs BC vs human distributions); plots in `results/plots/`; README reproduction recipe verified end-to-end |

A gate is not "reached" until its exit criterion is demonstrable from a clean clone.

## Amendment & Governance

- This constitution supersedes all other working practices. A conflict between it and a
  task, prompt, or habit is resolved in its favor; the contributor stops and proposes
  an amendment rather than deviating quietly.
- **Amendments** are made by editing this file in a `docs(spec):` commit whose body
  states what changed and why. Version bumps follow semver:
  - **MAJOR** - a principle is removed or redefined in a backward-incompatible way.
  - **MINOR** - a new principle or section is added, or guidance is materially expanded.
  - **PATCH** - wording, typo, or non-semantic clarification.
- Every spec, plan, and review checks compliance with these principles. Added complexity
  must be justified against Principle I (spec) and VI (reproducibility) - if it isn't in
  the spec and can't be reproduced, it doesn't ship.
- Runtime / day-to-day guidance for agents lives in `WORKFLOW.md` and `CONTRIBUTING.md`;
  this constitution states the non-negotiable principles those documents operationalize.

### Amendment log

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-07-23 | Ratified - 8 principles, milestone gate table |
| 1.1.0 | 2026-07-23 | Added Principle IX (Statistical Rigor) |
| 1.2.0 | 2026-07-29 | Technology Constraints corrected to the verified toolchain (Unity 6000.5.3f1, ml-agents 4.0.3, Communicator API 1.5.0, `release/4.0.3` checkout); `ENVIRONMENT.md` added as a companion document; Principle VI gained the intended-vs-verified rule and the two-environment rule |
| 1.3.0 | 2026-07-29 | Principle V gained a binding writing-style rule: no em dashes, sparing bold. Applied across the repository in the same commit |
| 1.4.0 | 2026-08-05 | Principle III gained the no-attribution rule: commit messages, pull request bodies, tags and run-log entries carry no tool trailers |

**Version:** 1.4.0 | **Ratified:** 2026-07-23 | **Last Amended:** 2026-08-05
