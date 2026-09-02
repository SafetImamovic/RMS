# Simulacija autonomnog vozila (Unity ML-Agents)

**Tema 28 - II parcijalni ispit** · Računarsko modeliranje i simulacija (II ciklus)

![Ljudska vožnja po proceduralno generisanoj stazi](docs/images/human-driving.gif)

Simulacija autonomne vožnje u kojoj se porede dva pristupa učenju upravljanja vozilom:

1. **Reinforcement Learning (PPO)** - agent u Unity simulaciji uči voziti kroz
   pokušaje i grešku, na osnovu raycast senzora i nagrada za napredak po stazi.
2. **Behavioral Cloning (BC)** - konvolucijska mreža (PilotNet) trenirana
   supervizirano na podacima ljudske vožnje
   ([Self-Driving Car Simulator](https://www.kaggle.com/datasets/zaynena/selfdriving-car-simulator):
   slike kamere + steering uglovi, Udacity simulator format, dvije staze).
   *Dataset iz originalne postavke zadatka je uklonjen sa Kagglea; profesor je odobrio
   ovu zamjenu - detalji u [DESIGN.md](DESIGN.md).*

Poenta poređenja: RL uči **zadatak** (proći stazu bez sudara), BC uči **stil**
(imitira čovjeka). Evaluacija poredi distribucije steering odluka RL agenta, BC
modela i ljudske vožnje iz dataseta - koliko se naučena politika približi
prirodnoj vožnji. Dataset dodatno služi za kalibraciju simulacije (rasponi
akcija, reward za glatkoću) - detalji u [DESIGN.md](DESIGN.md).

## Generisanje staza iz seed-a

Staze se ne crtaju ručno nego se generišu iz **jednog cijelog broja**. Isti seed uvijek
daje isti fajl, bajt po bajt, i u istom procesu i u novom, pa se generisana staza može
pregledati u `git diff` kao i svaki drugi izvorni fajl.

Oblik krive je polarna harmonijska petlja:

```
r(theta) = R0 * (1 + suma_k a_k sin(k theta + phi_k)),    a_k = A / k^2
```

Dvije osobine ovog oblika rade stvarni posao. **Zatvara se po konstrukciji**, jer je svaki
harmonik cijeli umnožak od theta, pa se krajevi nikad ne "šiju" naknadno; šav bi bio prekid
u zakrivljenosti koji vozilo osjeti. I **zakrivljenost mu je poznata u zatvorenoj formi**,
pa se odluka o prihvatanju staze donosi analitički, a ne numeričkom derivacijom tamo gdje je
ona najmanje tačna.

**Veza s datasetom nije dekorativna.** Svaka staza se provjerava protiv profila vozila koji
je izveden iz M1 mjerenja, i nosi taj profil sa sobom:

| Provjera | Šta znači |
|---|---|
| Najoštrija krivina | Ne smije ispod `r_floor` 6.97 m, izvedenog iz međuosovinskog rastojanja i maksimalnog zaokreta |
| Samopresijecanje | Zatvorena petlja koja se ne siječe |
| Minimalno razdvajanje | Dva dijela kruga ne smiju proći bliže od 12 m jedan drugom |
| Zahtjev za volanom | Nijedna staza ne smije tražiti **više** volana nego što je čovjek u datasetu ikad dao |

Zadnja stavka je kriterij SC-010. Mjeri se nad **skupom** prihvaćenih staza, ne po jednoj:
dvadeset staza koje svaka promaši na svoju stranu daju dobar prosjek, a dvadeset koje
promaše isto ne daju, i samo skupna brojka razlikuje ta dva slučaja.

Odbijeni seed se **čuva sa razlogom**, nikad se ne pokušava ponovo s podešenim parametrima.
Generator koji tiho uzorkuje dok ne uspije ima stopu prihvatanja koju niko ne vidi, a ta
stopa je nalaz o odnosu između minimalnog poluprečnika i statističkog cilja.

```powershell
# Jedna staza
python -m python.track.export --seed 7

# Oba skupa (train i eval), plus split fajl i izvještaj o seriji
python -m python.track.export --batch all

# Slike: staza sa označenom najoštrijom krivinom, i poređenje sa ljudskim volanom
python -m python.track.plots --seed 7 --match
```

Trenutno stanje: **34 od 40** train seed-ova prihvaćeno (85 posto), svih 10 eval seed-ova
prihvaćeno, skupni zahtjev za volanom unutar ljudskog. Detalji u
`results/tracks/batch_report.md`.

Unity čita gotov fajl i postavlja objekte. **U Unityju nema nijedne statistike**: sve što je
trebalo dokazati dokazano je u Pythonu i zapisano u `seed_<n>.json`, a učitavač odbija fajl
koji ne razumije umjesto da pročita polja koja slučajno prepoznaje.

## Kako radi

```
Kaggle dataset ──▶ EDA (notebook) ──▶ profil vozila ──▶ generator staza (seed)
      │                                    │                      │
      │                                    ▼                      ▼
      └──▶ BC trening (PyTorch) ──┐   parametri i reward    seed_<n>.json
                                  │                              │
                                  ▼                              ▼
                              Evaluacija ◀──── Unity simulacija ◀──▶ PPO (mlagents)
                                        (steering distribucije, metrike)
```

## Struktura repozitorija

| Putanja | Sadržaj |
|---------|---------|
| `unity/SelfDrivingSim/` | Unity projekat: scena sa stazom, vozilo, `CarAgent` |
| `config/ppo_car.yaml` | Hiperparametri PPO treninga |
| `python/track/` | Profil vozila, generator staza, provjere geometrije, izvoz |
| `python/notebooks/` | Analiza dataseta (M1) |
| `python/eda/` | Učitavanje dataseta i statistika (M1) |
| `python/bc/` | Behavioral cloning pipeline (PyTorch, M4) |
| `python/tests/` | Testovi za `eda`, `track` i `bc` |
| `requirements-bc.txt` | Pinovane verzije za `.venv-bc` (M4) |
| `specs/` | Specifikacije i plan po feature-ima (spec-kit) |
| `dataset/` | Kaggle dataset (nije u gitu - vidi Postavljanje) |
| `results/` | Trening logovi, grafovi, trenirani modeli |
| `results/EXPERIMENTS.md` | Jedan red po trening runu (RL i BC) |
| `DESIGN.md` | Arhitektura i sve dizajn odluke |
| `WORKFLOW.md` | Kako Unity radi + razvojni proces |
| `CONTRIBUTING.md` | Git konvencije (git flow, atomic commiti) |
| `ENVIRONMENT.md` | Provjereno stanje mašine i zamke pri instalaciji |

## Preduslovi

Tačne, provjerene verzije i zamke: `ENVIRONMENT.md`.

| Alat | Verzija | Napomena |
|------|---------|----------|
| Unity Hub + Unity Editor | 6000.5.3f1 | preko [Unity Hub](https://unity.com/download); `com.unity.ml-agents` 4.0.3 traži Unity 6000.0+ |
| Python | 3.10.11 | novije verzije nekompatibilne sa `mlagents` |
| Git + Git LFS | aktuelne | `git lfs install` jednom po mašini |
| NVIDIA GPU + CUDA drajveri | - | opciono, ubrzava BC trening |
| Kaggle nalog | - | za preuzimanje dataseta |

## Postavljanje

```powershell
# 1. Kloniraj repo
git clone <remote-url> RMS; cd RMS
git lfs install

# 2. Python okruženja - tri, namjerno odvojena (detalji: ENVIRONMENT.md)
#    .venv za M1 EDA, .venv-mlagents za RL, .venv-bc za BC trening.
#    Razlog: mlagents pinuje numpy==1.23.5, a BC traži noviji numpy uz torch 2.6.
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python/requirements.txt

# 3. Dataset → dataset/ (git-ignorisan; koristimo spojeni dataset/dataset/)
kaggle datasets download -d zaynena/selfdriving-car-simulator -p dataset --unzip
#   (ili ručno sa Kaggle stranice, raspakovati u dataset/)

# 4. BC okruženje (M4) - odvojeno od .venv i .venv-mlagents
py -3.10 -m venv .venv-bc
.venv-bc\Scripts\Activate.ps1
pip install -r requirements-bc.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
#   Mora ispisati True i ime GPU-a. Trening odbija da krene bez GPU-a
#   osim uz izričit --allow-cpu, jer je CPU epoha višesatna.

# 5. Unity projekat
#    Unity Hub → Add → odaberi unity/SelfDrivingSim → otvori
#    (prvi import traje nekoliko minuta - Unity gradi Library/ keš)
```

## Upotreba

Svaka grupa komandi traži svoje okruženje; aktiviraj ga prije nego pokreneš.

```powershell
# ---- M1: analiza dataseta (.venv) ----
.venv\Scripts\Activate.ps1
python -m python.eda.report          # sačuva results/plots + results/eda/m1_stats.json
jupyter notebook python/notebooks/01_dataset_analysis.ipynb   # korak-po-korak notebook
pytest python/tests                  # 357 prolaza, 3 preskočena (bc moduli traže torch)
#   NE dodavati -q: pytest.ini već ima addopts = -q, pa drugi -q ugasi i broj prolaza.
#   Ne skraćivati izlaz sa | tail: -q ispisuje samo tačke dok ne dođe do sažetka,
#   pa odsječen izlaz izgleda kao manji ukupan broj (izmjereno u 005/T046).

# M2 - generisanje staza iz seed-ova (vidi sekciju gore)
python -m python.track.export --batch all

# ---- M3: RL trening (.venv-mlagents) ----
.venv-mlagents\Scripts\Activate.ps1

# 1. Trening. Pokrenuti IZ KORIJENA repozitorija, da trenerov results/ bude projektov results/.
#    Trener prvo osluskuje, pa se onda pritisne Play u Unity Editoru sa otvorenom
#    Assets/Scenes/Training.unity. Ako je otvorena neka druga scena, trener ceka i istekne.
mlagents-learn config/ppo_car.yaml --run-id=ppo_car_v01 --seed=1 --torch-device=cuda
#    Smanjeni budzet za spread i tjuning runove (2M umjesto 5M):
mlagents-learn config/ppo_car_spread.yaml --run-id=ppo_car_spread_a --seed=1 --torch-device=cuda

# 2. Zaustavljanje: JEDAN Ctrl+C i cekati red "Exported ... .onnx".
#    Drugi Ctrl+C preskace izvoz i noc treninga ostaje samo kao checkpoint fajl.

# 3. Kriva kao podatak: destilovani CSV po runu, to je ono sto se commituje.
python -m python.rl.export_curves results/ppo_car_spread_a

# 4. Evaluacija: Assets/Scenes/Evaluation.unity, pa Play. SweepRunner sam prolazi
#    10 izdvojenih seedova i pise redove u results/rl/ i trag po runu u results/drive_logs/.
#    Model i deterministicka inferenca se biraju na BehaviorParameters u toj sceni.

# 5. Izvjestaj za M5 (u .venv, ne u .venv-mlagents):
python -m python.rl.report results/rl/eval_ppo_car_spread_a_deterministic.csv `
    --traces results/rl/traces/deterministic --name spread_a_deterministic `
    --dataset dataset/dataset/dataset/driving_log.csv

tensorboard --logdir results

# ---- M4: BC trening (.venv-bc) ----
.venv-bc\Scripts\Activate.ps1
pytest python/tests                  # 401 prolaz (ništa se ne preskače, torch je tu)

# 1. Podjela train/val: blokovski holdout sa 8 s zaštitnim pojasom.
#    Piše results/bc/split.json. Deterministična - isti fajl bajt po bajt.
python -m python.bc.split

# 2. Dva runa koja se razlikuju u tačno jednoj stvari, politici balansiranja.
#    Oko 5-6 minuta po runu na RTX 3050. --policy i --run-id su obavezni.
python -m python.bc.train --policy none            --run-id bc_unbalanced_v01
python -m python.bc.train --policy downsample_zero --run-id bc_balanced_v01

# 3. Evaluacija po runu, pa poređenje para.
python -m python.bc.evaluate --run bc_unbalanced_v01
python -m python.bc.evaluate --run bc_balanced_v01
python -m python.bc.evaluate --compare bc_balanced_v01 bc_unbalanced_v01

# 4. Opciono: animacija predikcija preko kadrova koje je čovjek vozio (otvorena petlja).
python -m python.bc.playback --run bc_unbalanced_v01 bc_balanced_v01 --track track2data

# ---- Heuristički vozač: vožnja je u Unityju, izvještaj u .venv ----

# 1. Jedan run rukom. Unity → Assets/Scenes/HeuristicWeighted.unity → Play.
#    Panel gore lijevo: [G] sakriva/prikazuje, gornji toolbar bira regulator
#    (MostOpen / WeightedAverage), drugi bira način oblikovanja komande.
#    Promjena regulatora NAMJERNO restartuje run: run koji bi se prebacio na pola
#    opisao bi dva regulatora u jednom redu zapisa.
#    Svaki završen run dopisuje red u results\heuristic\runs_<vrijeme>.csv, a trag
#    po koraku u trace_<vrijeme>.csv. Oba su git-ignorisana; u repozitorij ulaze
#    samo izvještaji (results\heuristic\*.md).

# 2. Sweep preko svih 34 trening seeda, bez izlaska iz Play modea. U sceni dodaj
#    SweepRunner, poveži TrackBuilder / HeuristicDriver / StartPlacer / CarController
#    / CarAgent, pa u Inspectoru: seedSet = Train, timeScale = 2, runOnStart = true,
#    fans = arrangements koje se porede. Play.
#    timeScale 2 je najbrže na čemu se mjerenja reprodukuju; na 4 se mjeri frame
#    clock, a ne vožnja (research R4a). Jedna konfiguracija traje 6.3-7.6 minuta,
#    što NE staje u SC-004 budžet od pet minuta - zapisano kao promašaj, ne zaobiđeno.

# 3. Izvještaj nad zapisom runova (.venv).
.venv\Scripts\Activate.ps1
python -m python.heuristic.report              # najnoviji results\heuristic\runs_*.csv

#    --spread uzima prag šuma iz fajla sa ponovljenim runovima istog seeda; bez njega
#    nijedna razlika nije nalaz (FR-015). --traces dodaje raspodjelu volana (US4) i
#    poređenje sa naučenim vozačem iz results\bc\run_bc_balanced_v01.
python -m python.heuristic.report results\heuristic\runs_A.csv `
    --spread results\heuristic\runs_B.csv `
    --traces results\heuristic\us4
```

Svaki run piše `results/bc/run_<id>/` sa `checkpoint.pt`, `run_record.json` i
`distributions.json`, a poređenje para piše `results/bc/comparison.md`. Svaki trening run se
upisuje i u `results/EXPERIMENTS.md`, u istoj sesiji u kojoj je pokrenut.

Očekivane vrijednosti za gornji recept (izmjereno 2026-08-05, ista mašina): podjela daje 25.957
trening i 5.576 validacionih redova uz razmak 8.09 s; nebalansiran run daje validacionu MSE
**0.086670**, balansiran **0.090899**, oba naspram osnovice od oko 0.1536. Trening se reprodukuje
na **±0.0005** MSE, ne tačnije - GPU bira kernele nedeterministički (DESIGN §6.2, research R13).

Očekivane vrijednosti za heuristički recept (izmjereno 2026-08-16, 34 trening seeda, 13 zraka
preko 180 stepeni, timeScale 2): `WeightedAverage` završava **34 od 34** kruga, prosjek
**26.496 s**, nula dodira zida; `MostOpen` završava **0 od 34** i uvijek udari u zid za oko 2.7 s.
Ponovljivost istog seeda: **0.16 s** raspona po vremenu kruga i **0.0063** po `|dsteer|` P95 nad
pet runova. Izvještaj o raspodjeli volana i poređenje sa BC kolonom:
[results/heuristic/us4_steering.md](results/heuristic/us4_steering.md).

Poređenje za M5 (RL / BC / heuristika / čovjek) radi iz čistog klona, bez dataseta i bez
sirovih tragova. Ulazi su commitovani u `results/comparison/`, po jedan mali CSV po vozaču:

```powershell
.venv\Scripts\Activate.ps1

# 1. Tabela i oba poređenja (primarna osa |Δsteering|, sekundarna nivo volana).
#    Piše results\comparison\m5_comparison.md i steering_histogram.csv.
python -m python.m5.compare

# 2. Tri figure iz istih ulaza. Nijedna se ne snima rukom (SC-005).
python -m python.m5.plots

# 3. Regenerisanje samih ulaza. Ovo je JEDINI korak koji traži sirove tragove i
#    dataset, i pokreće se samo kad se sweep ponovo odvozi.
python -m python.rl.comparison_inputs
#    BC kolona ide kroz .venv-bc, jer .venv nema torch:
.venv-bc\Scripts\Activate.ps1
python -m python.bc.export_predictions --run-id bc_balanced_v01
```

Očekivane vrijednosti za gornji recept: RL 009 deterministički **10 od 10** krugova uz
**62.425 s** i nula dodira zida, heuristika **34 od 34** uz **23.655 s**, a na primarnoj osi
posle kvantizacije na ljudsku rešetku RL deterministički je najbliži čovjeku sa **D = 0.2682**.
Puni izvještaj: [results/comparison/m5_comparison.md](results/comparison/m5_comparison.md).

**Dvije stvari koje recept traži, a nisu u repozitoriju.** Dataset (`dataset/`) i sirovi
tragovi (`results/drive_logs/`, `results/heuristic/**/trace_*.csv`) su git-ignorisani namjerno.
Zato korak 3 postoji odvojeno od koraka 1 i 2: ko samo čita rezultate, ne treba mu ništa osim
klona i `.venv`.

Detaljan razvojni proces (Play mode, heuristička vožnja, testiranje): [WORKFLOW.md](WORKFLOW.md).

## Status

Projekat u izradi - plan po fazama (M1–M5) u [DESIGN.md](DESIGN.md) §9.

- [x] M1 - analiza dataseta, kalibracija parametara (`results/eda/m1_report.md`)
- [x] M2 - Unity okruženje (staza, vozilo, agent, heuristička vožnja)
- [x] M3 - PPO trening. **ISPUNJEN 2026-09-01**, na četvrti pokušaj i preko tri seeda:
      30/30 izdvojenih runova, tri kruga bez dodira zida (DESIGN §5.2)
- [x] M4 - BC trening, dva runa koja se razlikuju u jednoj stvari (`results/bc/comparison.md`)
- [x] M5 - evaluacija i poređenje (`results/comparison/m5_comparison.md`)

## Licenca

[MIT](LICENSE)
