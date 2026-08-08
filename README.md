# Simulacija autonomnog vozila (Unity ML-Agents)

**Tema 28 - II parcijalni ispit** · Računarsko modeliranje i simulacija (II ciklus)

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

## Kako radi

```
Kaggle dataset ──▶ EDA (notebook) ──▶ parametri okruženja i rewarda
      │                                        │
      └──▶ BC trening (PyTorch) ──┐            ▼
                                  │      Unity simulacija ◀──▶ PPO trening (mlagents)
                                  ▼            │
                              Evaluacija ◀─────┘  (steering distribucije, metrike)
```

## Struktura repozitorija

| Putanja | Sadržaj |
|---------|---------|
| `unity/SelfDrivingSim/` | Unity projekat: scena sa stazom, vozilo, `CarAgent` |
| `config/ppo_car.yaml` | Hiperparametri PPO treninga |
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
pytest python/tests                  # 87 prolazi, 3 preskočena (bc moduli traže torch)
#   NE dodavati -q: pytest.ini već ima addopts = -q, pa drugi -q ugasi i broj prolaza.

# ---- M3: RL trening (.venv-mlagents) ----
.venv-mlagents\Scripts\Activate.ps1
mlagents-learn config/ppo_car.yaml --run-id=ppo_car_v01   # pa Play u Unity Editoru
tensorboard --logdir results

# ---- M4: BC trening (.venv-bc) ----
.venv-bc\Scripts\Activate.ps1
pytest python/tests                  # 141 prolazi

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
```

Svaki run piše `results/bc/run_<id>/` sa `checkpoint.pt`, `run_record.json` i
`distributions.json`, a poređenje para piše `results/bc/comparison.md`. Svaki trening run se
upisuje i u `results/EXPERIMENTS.md`, u istoj sesiji u kojoj je pokrenut.

Očekivane vrijednosti za gornji recept (izmjereno 2026-08-05, ista mašina): podjela daje 25.957
trening i 5.576 validacionih redova uz razmak 8.09 s; nebalansiran run daje validacionu MSE
**0.086670**, balansiran **0.090899**, oba naspram osnovice od oko 0.1536. Trening se reprodukuje
na **±0.0005** MSE, ne tačnije - GPU bira kernele nedeterministički (DESIGN §6.2, research R13).

**M5 (poređenje RL / BC / čovjek) još nije implementiran.** Ranije je ovdje stajala komanda
`python python/evaluation/compare.py`; taj modul ne postoji.

Detaljan razvojni proces (Play mode, heuristička vožnja, testiranje): [WORKFLOW.md](WORKFLOW.md).

## Status

Projekat u izradi - plan po fazama (M1–M5) u [DESIGN.md](DESIGN.md) §9.

- [x] M1 - analiza dataseta, kalibracija parametara (`results/eda/m1_report.md`)
- [ ] M2 - Unity okruženje (staza, vozilo, agent, heuristička vožnja)
- [ ] M3 - PPO trening
- [ ] M4 - BC trening (dva runa gotova, `results/bc/comparison.md`; ostaje potvrda gate-a)
- [ ] M5 - evaluacija i poređenje

## Licenca

[MIT](LICENSE)
