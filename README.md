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
| `python/bc/` | Behavioral cloning pipeline (PyTorch) |
| `python/evaluation/` | Poređenje RL / BC / ljudski podaci |
| `dataset/` | Kaggle dataset (nije u gitu - vidi Postavljanje) |
| `results/` | Trening logovi, grafovi, trenirani modeli |
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

# 2. Python okruženje
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python/requirements.txt

# 3. Dataset → dataset/ (git-ignorisan; koristimo spojeni dataset/dataset/)
kaggle datasets download -d zaynena/selfdriving-car-simulator -p dataset --unzip
#   (ili ručno sa Kaggle stranice, raspakovati u dataset/)

# 4. Unity projekat
#    Unity Hub → Add → odaberi unity/SelfDrivingSim → otvori
#    (prvi import traje nekoliko minuta - Unity gradi Library/ keš)
```

## Upotreba

```powershell
# M1 - analiza dataseta (EDA): statistika, χ² fit, kalibracija za Unity
python -m python.eda.report          # sačuva results/plots + results/eda/m1_stats.json
jupyter notebook python/notebooks/01_dataset_analysis.ipynb   # korak-po-korak notebook
pytest python/tests -q               # testovi (loader, fingerprint, stats, staze)

# M2 - generisanje staza iz seed-ova (vidi sekciju gore)
python -m python.track.export --batch all

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

Projekat u izradi - plan po fazama (M1–M5) u [DESIGN.md](DESIGN.md) §9.

- [ ] M1 - analiza dataseta, kalibracija parametara
- [ ] M2 - Unity okruženje (staza, vozilo, agent, heuristička vožnja)
- [ ] M3 - PPO trening
- [ ] M4 - BC trening
- [ ] M5 - evaluacija i poređenje

## Licenca

[MIT](LICENSE)
