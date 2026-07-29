# WORKFLOW - kako Unity radi i kako radimo na ovom projektu

Ovaj dokument je vodič za rad na projektu za nekoga ko dolazi iz Roblox Studija.
Pravila za git (grane, commiti) su u [CONTRIBUTING.md](CONTRIBUTING.md); dizajn
sistema je u [DESIGN.md](DESIGN.md).

---

## 1. Unity za Roblox developera

Najbrži način da shvatiš Unity: mapiraj pojmove koje već znaš.

| Roblox Studio | Unity | Napomena |
|---------------|-------|----------|
| Place / Experience | **Scene** (`.unity` fajl) | Projekat može imati više scena; mi imamo jednu (`Track.unity`) |
| Explorer | **Hierarchy** panel | Stablo objekata u sceni |
| Properties | **Inspector** panel | Podešavanje selektovanog objekta |
| Part / Model | **GameObject** | Ključna razlika: GameObject je *prazan kontejner* - sve sposobnosti dobija dodavanjem **komponenti** (Transform, Rigidbody, Collider, skripte...) |
| Luau `Script` | **C# skripta** (MonoBehaviour) | Skripta se *ne izvršava sama* - mora biti dodana na GameObject kao komponenta |
| Model koji kopiraš | **Prefab** | Sačuvan GameObject sa svom djecom i komponentama; izmjena prefaba mijenja sve instance |
| Toolbox | **Package Manager** + Asset Store | Mi koristimo samo Package Manager (ML-Agents paket) |
| Studio "Play" | **Play mode** (▶ dugme) | ⚠️ NAJVEĆA ZAMKA: izmjene napravljene tokom Play mode se **gube** kad izađeš iz njega. U Robloxu izmjene u Play testu se isto gube, ali Unity te ništa ne upozorava |
| Team Create | git (nema live kolaboracije) | |
| Output prozor | **Console** panel | `Debug.Log()` umjesto `print()` |
| Workspace, ReplicatedStorage... | Nema toga | Nema client/server podjele - ovo je offline simulacija, sve je "lokalno" |

Ostale bitne razlike:

- **Kod se piše van Unityja.** Unity Editor nije editor koda - dupli klik na skriptu
  otvara vanjski IDE (VS Code / Visual Studio / Rider). Unity automatski rekompajlira
  kad se vratiš u Editor prozor.
- **C# umjesto Luau**: statički tipovi, klase, `void Update()` umjesto
  `RunService.Heartbeat`. Životni ciklus MonoBehaviour skripte:
  `Awake()` → `Start()` → `Update()` (svaki frame) / `FixedUpdate()` (svaki physics tick).
- **Jedinice**: 1 Unity jedinica = 1 metar (Roblox stud ≈ 0.28 m).

## 2. Anatomija Unity projekta

Unity projekat je **folder** (kod nas `unity/SelfDrivingSim/`). Bitno je znati šta
je izvorni kod, a šta generisano:

```
unity/SelfDrivingSim/
├── Assets/            ← IZVOR. Sve što praviš: scene, skripte, prefabi, modeli
├── Packages/          ← IZVOR. manifest.json = lista paketa (kao package.json u npm)
├── ProjectSettings/   ← IZVOR. Podešavanja projekta (fizika, tagovi, kvalitet...)
├── Library/           ← GENERISANO. Keš importovanih asseta. VELIKO (GB). Nikad u git
├── Temp/, Logs/, obj/ ← GENERISANO. Nikad u git
└── UserSettings/      ← GENERISANO. Lični layout editora. Nikad u git
```

Kad neko klonira repo bez `Library/`, Unity ga sam regeneriše pri prvom otvaranju
(traje par minuta) - zato je bezbjedno (i obavezno) ignorisati ga.

### .meta fajlovi - OBAVEZNO ih committati

Uz svaki fajl/folder u `Assets/` Unity kreira `IstoIme.meta` fajl koji sadrži
**GUID** - trajni identitet asseta. Sve reference u Unityju (npr. "ova skripta je
na ovom objektu", "ovaj prefab koristi ovaj materijal") idu preko GUID-a, ne preko
putanje.

Pravila:
1. `.meta` fajlovi idu u git, uvijek.
2. Fajl u `Assets/` se preimenuje/premješta **kroz Unity Editor** (ili zajedno sa
   svojim `.meta` fajlom), nikad samo fajl - inače Unity generiše novi GUID i sve
   reference pucaju ("Missing Script" greške).

## 3. Verzionisanje Unity projekta (git)

### Šta ide u git, a šta ne

| U git | Ne (u `.gitignore`) |
|-------|---------------------|
| `Assets/` + svi `.meta` | `Library/`, `Temp/`, `Logs/`, `obj/`, `UserSettings/` |
| `Packages/manifest.json` | `Build/` |
| `ProjectSettings/` | IDE fajlovi (`.vs/`, `*.csproj`, `*.sln` - Unity ih regeneriše) |
| `config/`, `python/`, dokumentacija | `data/` (dataset - prevelik; ide na GC zasebno) |
| `results/plots/`, mali CSV logovi | `results/tensorboard/` (veliki event fajlovi), `.venv/` |

### Jednokratno podešavanje (uradi jednom, kad instaliraš Unity)

U Unity Editoru: **Edit → Project Settings → Editor**:
- *Version Control*: **Visible Meta Files** (default u novim verzijama)
- *Asset Serialization*: **Force Text** (default) - scene i prefabi se snimaju kao
  čitljiv YAML pa git diff ima smisla

### Git LFS (Large File Storage)

Binarni asseti (slike, 3D modeli, trenirani `.onnx`/`.pt` modeli) ne valjaju u
običnom gitu - svaka verzija ostaje u historiji zauvijek. `.gitattributes` u
korijenu već usmjerava te tipove na LFS. Prije prvog commita takvih fajlova:

```powershell
git lfs install    # jednom po mašini (Git za Windows obično već ima LFS)
```

Provjera: `git lfs ls-files` poslije dodavanja treba izlistati binarne fajlove.

### Konflikti u scenama

`.unity` i `.prefab` su YAML, ali git ih praktično ne zna spajati. Pravila:
1. **Jedna grana = jedan čovjek dira scenu.** Za solo projekat: ne drži izmjene
   scene na dvije grane istovremeno.
2. Logiku drži u skriptama (lako se mergaju), scenu drži "glupom".
3. Ako konflikt ipak nastane: uzmi jednu stranu cijelu (`git checkout --theirs/--ours`),
   pa ručno ponovi manju izmjenu u Editoru. (Unity ima i UnityYAMLMerge alat,
   ali za solo rad je overkill.)

## 4. Razvojni tok (dan u životu)

```
1. git switch develop && git pull
2. git switch -c feature/checkpoint-system        (vidi CONTRIBUTING.md)
3. Otvori Unity Hub → projekat; VS Code za kod
4. Piši skriptu → Alt-Tab u Unity (rekompajlira) → Console za greške
5. Testiraj u Play mode (▶)                       (vidi sekciju 5)
6. Izađi iz Play mode PA TEK ONDA podešavaj vrijednosti u Inspectoru
7. git status → provjeri da su tu samo očekivani fajlovi (+ .meta parovi!)
8. Atomic commit(i)                               (vidi CONTRIBUTING.md)
9. Merge u develop kad je feature cjelina
```

Korak 6 je zamka br. 1 za početnike: nađeš dobru vrijednost tokom Play mode,
izađeš, vrijednost se resetuje. Trik: tokom Play mode desni klik na komponentu
→ *Copy Component*, izađi iz Play mode, desni klik → *Paste Component Values*.

### ML-Agents specifičan tok (M3 faza)

Trening ne ide kroz Play dugme nego kroz Python:

```
1. Aktiviraj Python venv:  .venv\Scripts\Activate.ps1
2. mlagents-learn config/ppo_car.yaml --run-id=ppo_car_v01
3. Kad ispiše "Listening on port 5004..." → pritisni ▶ u Unity Editoru
4. Prati trening:  tensorboard --logdir results   (http://localhost:6006)
5. Prekid: Ctrl+C u terminalu (model se snima); nastavak: --resume
6. Gotov model: results/ppo_car_v01/CarAgent.onnx → kopiraj u
   unity/SelfDrivingSim/Assets/Models/ → prevuci na agenta u Inspectoru
   (Behavior Parameters → Model) → Play = agent vozi sam bez Pythona
```

Svaki run dobija novi `--run-id` (v01, v02...) - run-id + izmjena parametara se
bilježi u `results/EXPERIMENTS.md` da se zna šta je probano.

## 5. Testiranje

Tri nivoa, od jeftinijeg ka skupljem:

1. **Heuristic mode (ručna vožnja)** - `CarAgent` ima `Heuristic()` metodu koja
   mapira tastaturu (WASD) na akcije. Behavior Parameters → Behavior Type →
   *Heuristic Only* → Play → voziš auto sam. Ovim se provjerava: fizika vozila,
   checkpointi, rewardi (gledaš ih u Console). **Pravilo projekta: dok stazu ne
   možeš sam odvesti tastaturom, nema smisla puštati trening.**
2. **Unity Test Framework** (Window → General → Test Runner) - EditMode testovi
   za čistu logiku (npr. redoslijed checkpointa, računanje rewarda). Testovi žive
   u `Assets/Tests/`. Pišemo ih za logiku koja ne zavisi od fizike.
3. **Python testovi** - `pytest` za BC pipeline (loader parsira CSV, model prima
   ispravan shape, augmentacija negira steering pri flipu). Žive u `python/tests/`.

Za RL sam trening je "test": TensorBoard kriva reward-a mora rasti; kriterij
uspjeha je u DESIGN.md §5.

## 6. Asset management

- **Folderi u `Assets/`**: `Scenes/`, `Scripts/`, `Prefabs/`, `Models/` (ONNX),
  `Materials/`, `Tests/`. Sve novo ide u svoj folder - Unity ne nameće red, mi ga
  namećemo.
- **Prefab za sve što se ponavlja**: checkpoint, segment staze, training area
  (kopija staze za paralelni trening). Izmjena prefaba = izmjena svih kopija.
- **Paketi samo kroz Package Manager** (Window → Package Manager → Add by name →
  `com.unity.ml-agents`). To upisuje verziju u `Packages/manifest.json` koji je u
  gitu → svako ko klonira dobije iste pakete. Nikakvo ručno kopiranje DLL-ova.
- **Bez Asset Store nabacivanja**: staza se pravi od Unity primitiva (Cube/Plane), pa
  projekat ostaje malen i reproducibilan.
- **Dataset nije asset**: živi u `data/` (git-ignorisan), nikad u `Assets/` -
  Unity bi pokušao importovati svih ~10k slika i napraviti `.meta` za svaku.

## 7. Dokumentacija - ko šta pokriva

| Fajl | Sadržaj | Kad se mijenja |
|------|---------|----------------|
| `README.md` | Šta je projekat, kako ga pokrenuti | Kad se promijeni setup/komande |
| `DESIGN.md` | Arhitektura, odluke, reward funkcija, milestones | Kad se promijeni dizajn (uz `docs:` commit) |
| `WORKFLOW.md` | Ovaj fajl - kako se radi | Rijetko |
| `CONTRIBUTING.md` | Git pravila | Rijetko |
| `results/EXPERIMENTS.md` | Log trening eksperimenata (run-id, izmjena, ishod) | Svaki trening run |
| Kod | XML doc komentari (`///`) samo na public API skripti | Uz kod |

Princip: odluka koja mijenja dizajn prvo se upiše u DESIGN.md, pa se implementira.
