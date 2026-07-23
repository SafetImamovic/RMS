# Simulacija autonomnog vozila (Unity ML-Agents)

**Tema 28 — II parcijalni ispit** · Računarsko modeliranje i simulacija (II ciklus)

Simulacija autonomne vožnje u kojoj se porede dva pristupa učenju upravljanja vozilom:

1. **Reinforcement Learning (PPO)** — agent u Unity simulaciji uči voziti kroz
   pokušaje i grešku, na osnovu raycast senzora i nagrada za napredak po stazi.
2. **Behavioral Cloning (BC)** — konvolucijska mreža (PilotNet) trenirana
   supervizirano na podacima ljudske vožnje
   ([Self-Driving Car Simulator](https://www.kaggle.com/datasets/zaynena/selfdriving-car-simulator):
   slike kamere + steering uglovi, Udacity simulator format, dvije staze).
   *Dataset iz originalne postavke zadatka je uklonjen sa Kagglea; profesor je odobrio
   ovu zamjenu — detalji u [DESIGN.md](DESIGN.md).*

Poenta poređenja: RL uči **zadatak** (proći stazu bez sudara), BC uči **stil**
(imitira čovjeka). Evaluacija poredi distribucije steering odluka RL agenta, BC
modela i ljudske vožnje iz dataseta — koliko se naučena politika približi
prirodnoj vožnji. Dataset dodatno služi za kalibraciju simulacije (rasponi
akcija, reward za glatkoću) — detalji u [DESIGN.md](DESIGN.md).

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
| `python/bc/` | Behavioral cloning pipeline (PyTorch) |
| `python/evaluation/` | Poređenje RL / BC / ljudski podaci |
| `dataset/` | Kaggle dataset (nije u gitu — vidi Postavljanje) |
| `results/` | Trening logovi, grafovi, trenirani modeli |
| `DESIGN.md` | Arhitektura i sve dizajn odluke |
| `WORKFLOW.md` | Kako Unity radi + razvojni proces |
| `CONTRIBUTING.md` | Git konvencije (git flow, atomic commiti) |

## Preduslovi

| Alat | Verzija | Napomena |
|------|---------|----------|
| Unity Hub + Unity Editor | 2022.3 LTS | preko [Unity Hub](https://unity.com/download) |
| Python | 3.10.x | novije verzije nekompatibilne sa `mlagents` |
| Git + Git LFS | aktuelne | `git lfs install` jednom po mašini |
| NVIDIA GPU + CUDA drajveri | — | opciono, ubrzava BC trening |
| Kaggle nalog | — | za preuzimanje dataseta |

## Postavljanje

```powershell
# 1. Kloniraj repo
git clone <remote-url> RMS; cd RMS
git lfs install

# 2. Python okruženje
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python/requirements.txt

# 3. Dataset → dataset/ (git-ignorisan; koristimo spojeni dataset/dataset/)
kaggle datasets download -d zaynena/selfdriving-car-simulator -p dataset --unzip
#   (ili ručno sa Kaggle stranice, raspakovati u dataset/)

# 4. Unity projekat
#    Unity Hub → Add → odaberi unity/SelfDrivingSim → otvori
#    (prvi import traje nekoliko minuta — Unity gradi Library/ keš)
```

## Upotreba

```powershell
# RL trening (pa pritisni Play u Unity Editoru kad trainer javi da sluša)
mlagents-learn config/ppo_car.yaml --run-id=ppo_car_v01

# Praćenje treninga
tensorboard --logdir results

# BC trening
python -m python.bc.train

# Evaluacija i poređenje
python python/evaluation/compare.py
```

Detaljan razvojni proces (Play mode, heuristička vožnja, testiranje): [WORKFLOW.md](WORKFLOW.md).

## Status

Projekat u izradi — plan po fazama (M1–M5) u [DESIGN.md](DESIGN.md) §9.

- [ ] M1 — analiza dataseta, kalibracija parametara
- [ ] M2 — Unity okruženje (staza, vozilo, agent, heuristička vožnja)
- [ ] M3 — PPO trening
- [ ] M4 — BC trening
- [ ] M5 — evaluacija i poređenje

## Licenca

[MIT](LICENSE)
