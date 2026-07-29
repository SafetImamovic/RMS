# Dizajn projekta - Tema 28: Simulacija autonomnog vozila (Unity ML-Agents)

**Predmet:** Računarsko modeliranje i simulacija (II ciklus)
**Alat (fiksan):** Unity ML-Agents
**Dataset:** Self-Driving Car Simulator (Udacity) -
https://www.kaggle.com/datasets/zaynena/selfdriving-car-simulator
(Udacity simulator format: slike kamere + `driving_log.csv` sa steering/throttle/brake/speed)

> **Napomena o datasetu:** URL iz postavke zadatka
> (`kaggle.com/datasets/chethuhn/selfdriving-car`) vraća 404 - dataset je uklonjen
> sa Kagglea (provjereno 2026-07-12). **Profesor je odobrio zamjenu (2026-07-23):**
> `zaynena/selfdriving-car-simulator` - etablirani dataset istog domena, u Udacity
> simulator formatu. Ovaj dataset ima **dvije staze**:
>
> | Folder (raspakovano) | Redova u `driving_log.csv` | Sadržaj |
> |----------------------|----------------------------|---------|
> | `track1data/` | 10.615 | Staza 1 (ravna, lakša petlja) |
> | `track2data/` | 21.828 | Staza 2 (planinska, oštre krivine) |
> | `dataset/` | 32.443 | Obje spojene (= track1 + track2) |
>
> Za BC trening i kao ljudsku referencu koristimo **spojeni `dataset/`** (najviše
> podataka, obje vrste vožnje). `driving_log.csv` je **bez headera**, 7 kolona:
> `center, left, right, steering, throttle, brake, speed`. Putanje slika u CSV-u su
> Windows-apsolutne (`Desktop\...\IMG\...`) → preprocessing ih svodi na basename i
> re-rootuje na stvarni `IMG/` folder. Podaci su lokalno pod `dataset/` (git-ignorisan).

---

## 1. Cilj i obim

Dva komplementarna pristupa autonomnoj vožnji, pa njihovo poređenje:

1. **RL agent (Unity ML-Agents, PPO)** - uči vožnju iz interakcije sa simulacijom,
   observacije su raycast senzori + brzina.
2. **Behavioral Cloning (BC) model (PyTorch)** - CNN treniran supervizirano na Kaggle
   datasetu (slika → steering ugao), predstavlja "učenje od čovjeka".

Dataset ulazi u projekat na tri mjesta (sistemski pristup):

| Faza | Upotreba dataseta |
|------|-------------------|
| Dizajn okruženja | Distribucija steering uglova i brzina → rasponi akcija, zakrivljenost staze, reward shaping |
| BC trening | Direktno: slike + steering kao supervizirani skup |
| Evaluacija | Histogram ljudskog steeringa = referenca za ocjenu glatkoće vožnje RL agenta |

---

## 2. Arhitektura sistema

```
┌─────────────────────────┐          ┌──────────────────────────────┐
│  Kaggle dataset         │          │  Unity simulacija            │
│  (slike + driving_log)  │          │  (staza, vozilo, checkpointi)│
└─────┬──────────┬────────┘          └────────┬────────────┬────────┘
      │          │                            │            │
      ▼          ▼                            ▼            │
┌───────────┐ ┌──────────────┐        ┌──────────────┐     │
│ Analiza   │ │ BC trening   │        │ PPO trening  │     │
│ (notebook)│ │ (PyTorch CNN)│        │ (mlagents-   │     │
└─────┬─────┘ └──────┬───────┘        │  learn)      │     │
      │              │                └──────┬───────┘     │
      │ parametri    │                       │ ONNX model  │
      │ (→ Unity i   │                       ▼             ▼
      │  reward)     │                ┌───────────────────────┐
      │              └───────────────▶│  Evaluacija           │
      └──────────────────────────────▶│  (metrike + poređenje)│
                                      └───────────────────────┘
```

---

## 3. Struktura repozitorija

```
RMS/
├── DESIGN.md                      # ovaj dokument - arhitektura i dizajn odluke
├── README.md                      # šta je projekat + postavljanje i upotreba
├── WORKFLOW.md                    # kako Unity radi, razvojni proces, testiranje, asseti
├── CONTRIBUTING.md                # git konvencije (git flow, atomic commiti)
├── LICENSE                        # MIT
├── .gitignore                     # Unity generisano, dataset/, .venv, trening output
├── .gitattributes                 # LFS za binarne assete i modele; YAML kao tekst
├── unity/SelfDrivingSim/          # Unity projekat
│   └── Assets/
│       ├── Scenes/Track.unity
│       ├── Scripts/
│       │   ├── CarAgent.cs        # ML-Agents Agent: observacije, akcije, rewardi
│       │   ├── CarController.cs   # fizika vozila (WheelCollider)
│       │   ├── TrackCheckpoints.cs# checkpoint sistem za mjerenje napretka
│       │   ├── CheckpointSingle.cs
│       │   └── DrivingLogger.cs   # CSV log steering odluka agenta (za evaluaciju)
│       ├── Prefabs/               # Car, Checkpoint, TrackSegment
│       └── Models/                # trenirani .onnx modeli
├── config/
│   └── ppo_car.yaml               # PPO hiperparametri (mlagents-learn)
├── python/
│   ├── requirements.txt
│   ├── notebooks/
│   │   └── 01_dataset_analysis.ipynb   # EDA: steering/brzina distribucije → parametri
│   ├── bc/
│   │   ├── dataset.py             # loader za driving_log.csv + slike, augmentacija
│   │   ├── model.py               # PilotNet CNN (NVIDIA arhitektura)
│   │   ├── train.py               # trening, validacija, čuvanje modela
│   │   └── evaluate.py            # MSE na test splitu, histogram predikcija
│   └── evaluation/
│       └── compare.py             # RL log vs BC predikcije vs ljudski podaci
├── dataset/                       # Kaggle dataset, nested (u .gitignore, na GC ide zasebno)
│   ├── track1data/track1data/     #   staza 1: IMG/ + driving_log.csv
│   ├── track2data/track2data/     #   staza 2: IMG/ + driving_log.csv
│   └── dataset/dataset/           #   obje spojene (ovo koristimo za BC + referencu)
└── results/
    ├── EXPERIMENTS.md             # log trening eksperimenata (run-id, izmjena, ishod)
    ├── tensorboard/               # RL trening krive (git-ignorisano; grafovi se izvoze u plots/)
    ├── plots/                     # grafovi za odbranu
    └── logs/                      # CSV logovi vožnje agenta
```

---

## 4. Unity okruženje

### 4.1 Scena
- Zatvorena kružna staza sa lijevim i desnim krivinama različitih radijusa
  (radijusi kalibrisani prema distribuciji steering uglova iz dataseta - dominantno
  blage krivine, par oštrijih).
- Zidovi/ivice staze sa colliderima i tagom `Wall`.
- 20–30 checkpointa ravnomjerno po stazi (mjerenje napretka + detekcija pogrešnog smjera).
- Start pozicija sa malom randomizacijom (pozicija/rotacija) - sprječava overfitting na stazu.

### 4.2 Vozilo
- Rigidbody + 4× WheelCollider (realistična fizika: skretanje prednjim točkovima,
  pogon, kočenje).
- Alternativa ako fizika pravi probleme: pojednostavljen kinematski model
  (transform-based) - odluka u M2, fizika je primarna.

**Profil vozila (fiksirano u M2, feature 003).** Jedno mjesto drži svako ograničenje auta.
Izvor svake vrijednosti je mjerenje iz M1 ili navedena geometrijska pretpostavka; nijedna
nije odabrana jer izgleda dobro. Izvedene veličine se **računaju**, nikad ne čuvaju pored
osnovnih, pa profil ne može doći u stanje da mu poluprečnik ne odgovara međuosovinskom
rastojanju.

| Veličina | Vrijednost | Odakle |
|---|---|---|
| `wheelbase_m` | 2.5 m | jedina slobodno izabrana dimenzija; svi poluprečnici skaliraju linearno s njom |
| `steer_max_deg` | 25° | DESIGN 4.4, potvrđeno M1 analizom punog opsega |
| `radius_margin` | 1.3 | **jednako rezervi volana**, vidi ispod |
| `r_min_m` | **5.361 m** | izvedeno, `L / tan(25°)`, bicikl model pri maloj brzini |
| `r_floor_m` | **6.970 m** | izvedeno, `r_min × 1.3`. Najoštrija krivina koju staza smije imati |
| `max_required_steer` | **0.789** | izvedeno; najviše volana koje staza ikad traži |
| `steering_reserve` | **21.1 %** | `1 - max_required_steer` |
| `v_max_ms` | 10 m/s | **izbor za igrivost, nije tvrdnja o datasetu** |

**Zašto je margina 1.3 važnija nego što izgleda.** Ona nije proizvoljan faktor sigurnosti
nego direktno određuje koliko volana agentu ostaje u najoštrijoj krivini. Pri margini 1.0
najoštrija krivina traži **puni** zaokret i agent nema ničim da koriguje kad ga izbaci ka
vanjskoj ivici; to nije staza nego zamka. Pri 1.3 krivina traži 0.789 i 21.1 % ostaje
slobodno. Veličina `max_required_steer` je **nezavisna od međuosovinskog rastojanja** (L se
skrati), pa je margina jedini parametar koji je pomjera, što je čini poštenom ručkom za
podešavanje.

**Cijena, i navodi se otvoreno.** Nijedna generisana staza ne može tražiti steering iznad
0.789, dok ljudski podaci idu do 1.0. Izmjereno: 2.60 % nenultih uzoraka track1 je iznad te
granice, dakle pokrivamo ljudsku raspodjelu do 97.40. percentila i dalje ne.

**Brzina se ne pretvara, nego normalizuje.** Kolona `speed` u datasetu nema dokumentovanu
jedinicu (nalaz feature-a 002). Zato `v_max_ms` **nikad ne ulazi u poređenje**: obje strane
se dijele svojim vlastitim P99 i porede se bezdimenzionalno. Tvrdnja tipa "top speed je
17.49 m/s" tražila bi pretpostavku koju niko ne može provjeriti, a lažna preciznost bi se
provukla kroz svaki prag u M3 i M5.

**Brzina okretanja volana** (`steer_rate_norm_per_s`) i **ubrzanje/kočenje** se fiksiraju
mjerenjem stvarne vožnje tastaturom (M2 zadaci T023 i T024), jer su to jedine vrijednosti
koje se ne mogu odlučiti unaprijed. Snimljeni skokovi volana punog opsega u jednom kadru su
dokaz o **ulaznom uređaju** (tastatura ili miš), ne specifikacija vozila; auto koji ih
reprodukuje bio bi neupravljiv.

> Izvor: `specs/003-unity-environment/research.md` C1 do C4 i C15. Vrijednosti žive u
> `python/track/config.py`, izvoze se u `unity/.../Assets/Tracks/vehicle_profile.json`, a
> C# kopija se poredi s njim u `VehicleProfileMirrorTests`. Razilaženje pada kao test, ne
> kao tiho pogrešna geometrija.

### 4.3 Observacije (ukupno ~19 vrijednosti + raycast)
| Observacija | Dim | Napomena |
|-------------|-----|----------|
| RayPerceptionSensor3D | 13 zraka × (hit + udaljenost) | 180° naprijed, detektuje `Wall`; ugrađena ML-Agents komponenta |
| Brzina (lokalna, normalizovana) | 2 | naprijed + bočna komponenta |
| Ugaona brzina (yaw) | 1 | |
| Smjer ka sljedećem checkpointu (dot product) | 2 | forward·dir, right·dir |
| Trenutni steering | 1 | omogućava glatkoću |

### 4.4 Akcije (kontinualne, 2)
- `steering` ∈ [-1, 1] → mapiran na ±25°. **Potvrđeno M1 analizom:** ljudski steering koristi
  **puni opseg** - čak i robustan raspon P1–P99 iznosi (−1, 1) (track2 ima mnogo punog
  zaokreta), pa je mapiranje cijelog [-1,1] na ±25° opravdano podacima, ne saturacijom.
- `throttle` ∈ [-1, 1] → gas / kočnica. Napomena (M1): kočnica se u datasetu koristi rijetko
  (~95% nula), gas dominira - nije problem jer RL agent uči vlastiti throttle.

> **Ispravka „~95 % nula" (potiče iz feature-a 002, 2026-07-29).** Ta brojka (tačno 94,6 %)
> je izračunata nad **spojenim** datasetom i zato je zavaravajuća. Po stazi:
>
> | staza | različitih vrijednosti `brake` | stvarno stanje |
> |---|---|---|
> | track1 | **1** (samo 0.0, u svih 10.615 redova) | kolona je **konstantna** - mrtva |
> | track2 | 1.708 | kolona se stvarno koristi |
>
> M1 je nad spojenim podacima prijavio `brake_is_dead: false`; to je **artefakt spajanja**,
> jer track2 „oživi" kolonu koja na track1 uopšte ne postoji kao signal. Pravilo koje iz
> ovoga slijedi: **kočnicu izvještavati po stazi, nikad spojeno**, i ne koristiti je kao
> ulaz za model treniran samo na stazi 1. Detalji i verdikt:
> `results/eda/authenticity_report.md`, §4 i §7.
>
> Usput, ovo je i lijep primjer za odbranu: obrisana kolona i nikad korištena kolona
> izgledaju **identično** u brojkama. Razlikuje ih dokaz da pisač kolone radi - a to imamo,
> jer ista kolona na drugoj stazi ima 1.708 različitih vrijednosti.

> Kalibracija izvedena u M1: `results/eda/m1_stats.json` (reproducibilno iz
> `python -m python.eda.report`). Tipične brzine iz dataseta: 0–17.5 (P99), sredina ~10.2.

**Geometrijska posljedica mapiranja ±25° (fiksirano u M2).** Iz `steering ∈ [-1, 1] → ±25°`
i međuosovinskog rastojanja 2.5 m slijedi cijela tabela poluprečnika. Ovo je veza između
akcije agenta i oblika staze, pa stoji ovdje a ne samo u research dokumentu:

| \|steering\| | odakle dolazi | δ | poluprečnik |
|---|---|---|---|
| 0.25 | track1 median nenultih | 6.25° | 22.83 m |
| 0.40 | track1 P75 | 10.00° | 14.18 m |
| 0.50 | track2 median | 12.50° | 11.28 m |
| 0.65 | track1 P95 | 16.25° | 8.58 m |
| **0.79** | **granica koju staza smije tražiti** | 19.73° | **6.97 m** |
| 0.90 | track1 P99 | 22.50° | 6.04 m |
| 1.00 | puni zaokret | 25.00° | 5.36 m |

Tabela se provjerava red po red u `python/tests/test_vehicle.py` i u
`VehicleProfileMirrorTests`, pa ne može tiho odlutati od koda.

### 4.5 Reward funkcija
| Događaj | Reward | Svrha |
|---------|--------|-------|
| Prolazak checkpointa (ispravan smjer) | +1.0 | napredak |
| Prolazak checkpointa (pogrešan smjer) | −1.0 | smjer |
| Sudar sa zidom | −5.0 + kraj epizode | sigurnost |
| Svaki step | −0.001 | podstiče brzinu |
| Brzina naprijed | +0.001 × v_norm | podstiče kretanje |
| Nagli steering (\|Δsteering\| > **0.55**) | −0.005 × \|Δ\| | glatkoća; prag = P95 od \|Δsteering\| iz dataseta (M1) |

Težine su početne - tjuniraju se tokom M3. Svaka promjena se dokumentuje
(tabela eksperimenata u results/).

### 4.6 Kraj epizode
- Sudar sa zidom, ili
- 60 s bez novog checkpointa (zaglavljen), ili
- 3 kompletirana kruga (uspjeh).

---

## 5. RL trening (PPO)

- `mlagents-learn config/ppo_car.yaml --run-id=ppo_car_vXX`
- Početni hiperparametri: batch 2048, buffer 20480, lr 3e-4 (linear decay),
  hidden 256×2, gamma 0.99, max_steps 2–5M.
- 8–16 paralelnih kopija staze u sceni (Training Area pattern) - brži trening.
- Praćenje: TensorBoard (cumulative reward, episode length, policy loss).
- Kriterij uspjeha: agent stabilno završava 3 kruga bez sudara u 95%+ epizoda.
- Izlaz: `.onnx` model → nazad u Unity za inference demo.

## 6. BC pipeline (PyTorch, CUDA)

### 6.1 Format dataseta i referenciranje slika

`driving_log.csv` je **bez header reda**, 7 kolona. **Jedan red = jedan vremenski
trenutak = 3 slike** (tri kamere na vozilu) + 4 mjerena broja:

| Kolona | Sadržaj | Primjer |
|--------|---------|---------|
| 1 | putanja **center** kamere | `Desktop\track1data\IMG\center_2019_04_02_19_25_33_671.jpg` |
| 2 | putanja **left** kamere | `Desktop\track1data\IMG\left_2019_04_02_19_25_33_671.jpg` |
| 3 | putanja **right** kamere | `Desktop\track1data\IMG\right_2019_04_02_19_25_33_671.jpg` |
| 4 | `steering` | `0` |
| 5 | `throttle` | `0` |
| 6 | `brake` | `0` |
| 7 | `speed` | `1.058134E-05` |

Referenciranje:
- Prve 3 kolone su **string putanje** do fajlova (ne sama slika). Sve tri dijele isti
  timestamp u imenu (`..._2019_04_02_19_25_33_671`) - to je jedinstveni ID reda i veže
  center/left/right snimke istog trenutka.
- Putanje su **Windows-apsolutne sa mašine snimatelja** (`Desktop\...\IMG\...`), pa se
  ne mogu koristiti direktno. Preprocessing uzima samo basename i re-rootuje na stvarni
  `IMG/` folder:
  ```python
  filename = row[0].split("\\")[-1]        # "center_..._671.jpg"
  path = IMG_DIR / filename                # stvarna lokalna putanja
  ```
- Provjera integriteta (M1 gate): `broj_redova × 3 == broj_fajlova u IMG/`
  (npr. track1: 10.615 × 3 = 31.845 slika).

#### Kako znamo značenje kolona (dataset je bez headera)

Kaggle stranica ne opisuje kolone, pa se mapiranje ne pretpostavlja - **dokazuje se na
tri nivoa** (princip: verifikuj format iz uzorka, ne iz naslova):

1. **Kolone 1–3 dokazane imenima fajlova** - putanje sadrže `center_/left_/right_`, nema
   sumnje šta je šta.
2. **Kolone 4–7 = Udacity simulator standard** - dataset je output open-source Udacity
   self-driving-car simulatora, koji uvijek piše redoslijed
   `center, left, right, steering, throttle, brake, speed`. To je konvencija, ne dokaz
   iz našeg fajla.
3. **Kolone 4–7 potvrđene statistički** - deskriptivna statistika na track1 (10.615
   redova) daje "otisak" koji jednoznačno veže broj za značenje:

   | kolona | min | max | % negativnih | % nula | zaključak |
   |--------|-----|-----|--------------|--------|-----------|
   | kol 4 | −1.000 | 1.000 | 17.4 % | 79.3 % | jedina negativna, simetrična oko 0, većina 0 (prava vožnja) → **steering** |
   | kol 5 | 0.000 | 1.000 | 0 % | 51.8 % | [0,1], nikad negativna → **throttle** (gas) |
   | kol 6 | 0.000 | 0.000 | 0 % | 100 % | konstantno 0 (u ovom snimku nema kočenja) → **brake** |
   | kol 7 | 0.000 | 21.949 | 0 % | 0 % | uvijek ≥0, velika magnituda (mean 13.15) → **speed** |

   Logika: samo steering može biti negativan (volan lijevo) → kol 4. Speed je uvijek
   pozitivan i velike magnitude → kol 7. Throttle je [0,1] gas → kol 5; brake je
   preostala [0,1] kolona → kol 6.

   Posljedica za analizu: `brake` je 100 % nula na track1 → skoro beskorisna kolona;
   u M1 se provjerava i track2, pa ako je i tamo konstantna, izbacuje se iz obrade.
   **Provjereno (feature 002):** na track2 kolona ima 1.708 različitih vrijednosti, dakle
   nije konstantna i ostaje u obradi - ali se izvještava **po stazi** (vidi §4.4).

> Ovaj postupak (identifikacija promjenljivih preko deskriptivne statistike) je i sam
> dio statističkog naglaska predmeta - vidi §7.1 i M1.

Upotreba kamera u BC-u:
- **center** slika je primarni ulaz: `center → steering`.
- **left/right** slike su augmentacija: koriste se sa korigovanim steeringom
  (`+0.2` za left, `−0.2` za right) kao da je auto pomjeren u stranu - efektivno 3×
  više podataka bez novog snimanja.

### 6.2 Trening

- Ulaz: `driving_log.csv` + slike centralne kamere (lijeva/desna kamera sa
  steering korekcijom ±0.2 kao augmentacija).
- Preprocessing: crop neba/haube, resize 66×200, YUV (PilotNet standard),
  normalizacija; augmentacija: horizontalni flip (+negacija steeringa), random brightness.
- Balansiranje: downsampling uzoraka sa steering ≈ 0 (dataset je dominantno prava vožnja).
- Model: PilotNet (5 conv + 4 FC slojeva, ~250k parametara).
- Split: 80/20 train/val, loss MSE, Adam, early stopping.
- Evaluacija: MSE/MAE na validaciji, scatter predikcija vs stvarni ugao,
  histogram predikcija vs histogram dataseta.

## 7. Evaluacija i poređenje (ključno za odbranu)

`DrivingLogger.cs` tokom evaluacijskih vožnji RL agenta piše CSV:
`time, steering, throttle, speed, checkpoint_index, collision`.

| Metrika | RL agent | BC model | Ljudski podaci (dataset) |
|---------|----------|----------|--------------------------|
| Kompletiranje kruga (%) | ✓ | - (nema simulator ulaz) | - |
| Prosjek \|steering\| | ✓ | ✓ (predikcije) | ✓ |
| Glatkoća: prosjek \|Δsteering\| | ✓ | ✓ | ✓ |
| Histogram steering distribucije | ✓ | ✓ | ✓ |
| Vrijeme kruga | ✓ | - | - |

- Poređenje distribucija: histogrami preklopljeni + KL divergencija prema ljudskoj referenci.
- Zaključak koji se brani: RL uči *zadatak* (proći stazu), BC uči *stil* (imitira čovjeka);
  poređenje pokazuje koliko se RL politika prirodno približi ljudskom stilu.
- BC model se ne vozi u Unityju (trenirao je na slikama drugog simulatora) - to se
  eksplicitno navodi kao ograničenje i razlog zašto je poređenje na nivou distribucija.

> **Napomena za M5 - rezolucija zapisa nije isto što i stil vožnje**
> *(potiče iz feature-a 002, 2026-07-29)*
>
> RL agent emituje **kontinualan** steering (PPO politika daje realan broj), a ljudska
> referenca je **rešetkasta**: 41 dozvoljena vrijednost, korak 0.05 (vidi
> `results/eda/authenticity_report.md`, §4).
>
> Ako se te dvije raspodjele porede direktno, svaka metrika razlike (KL divergencija, KS,
> χ²) će prijaviti veliku razliku - ali će mjeriti **razliku u rezoluciji zapisa**, a ne
> razliku u vožnji. Ljudski histogram ima 41 tanku iglu; agentov je gladak. To bi izgledalo
> kao dramatičan nalaz, a bio bi artefakt.
>
> **Mjera prije poređenja:** kvantizovati izlaz agenta na **istu rešetku**
> (`round(steering / 0.05) * 0.05`, ograničeno na [−1, 1]) i tek onda porediti. Kvantizacija
> se primjenjuje na agenta, ne na čovjeka - čovjekov zapis je referenca i ne dira se.
>
> Isto vrijedi i za KL divergenciju iz tabele gore: KL između diskretne i kontinualne
> raspodjele nije definisan bez zajedničke podrške, pa je zajednička rešetka preduslov, a
> ne kozmetika.

### 7.1 Statistička obrada (naglasak predmeta)

Predmet insistira na statističkim metodama - poređenje se izvodi statistički, ne "na oko":

- **Deskriptivna statistika** za svaku distribuciju (steering, brzina, Δsteering): obim
  uzorka, aritmetička sredina (matematičko očekivanje), disperzija (varijansa/std),
  min/max, histogram relativnih učestalosti.
- **Prilagođavanje raspodjele + test saglasnosti (M1):** na ljudski steering se prilagodi
  kandidat-raspodjela (normalna / eksponencijalna / mješavina sa pikom oko nule) i
  testira se **χ² testom saglasnosti** (uz Kolmogorov–Smirnov kao dopunu) - računa se
  χ² statistika, kritična vrijednost χ²(n, α), i donosi odluka o prihvatanju/odbacivanju
  hipoteze (postupak iz predavanja).
- **Kvantifikovano poređenje RL vs BC vs čovjek:** KL divergencija + dvouzoračni
  **KS test** (i/ili χ²) umjesto vizuelne procjene; izvještava se p-vrijednost.
- **Taksonomija modela (za odbranu):** model je stohastički (nedeterministički zbog
  randomizacije starta i stohastičke PPO politike), sa kontinualnim stanjima, diskretnim
  vremenom (fiksni Unity timestep), agentski (agent-based), vremenski invarijantan,
  neanticipatorski - terminologijom iz predavanja.

## 8. Verzije alata

| Alat | Verzija | Status |
|------|---------|--------|
| Unity Editor | 6000.5.3f1 | verifikovano 2026-07-26 |
| com.unity.ml-agents (Unity paket) | 4.0.3 | verifikovano (min. Unity 6000.0) |
| com.unity.ai.inference | 2.6.1 | povlači se kao zavisnost ML-Agents paketa |
| Python | 3.10.11 | verifikovano |
| mlagents (pip) | 1.1.0 | verifikovano |
| PyTorch | 2.6.0+cu124 | verifikovano, CUDA aktivna (RTX 3050 6GB) |
| Communicator API | 1.5.0 | usklađen Unity paket ↔ Python paket |
| Ostalo | pandas, numpy, matplotlib, opencv-python, onnx | |

Verzije se zaključavaju u `requirements.txt` - ML-Agents je osjetljiv na
neusklađenost Unity paketa i Python paketa.

Kombinacija je provjerena end-to-end na 3DBall primjeru (`mlagents-learn` → Play →
nagrada 100 → izvezen `.onnx`). Stvarno stanje mašine i zamke pri instalaciji su
dokumentovani u [`ENVIRONMENT.md`](ENVIRONMENT.md) - taj fajl je izvor istine za
instalirane verzije, ova tabela za namjeravane.

## 9. Plan rada (milestones)

| M | Sadržaj | Izlaz |
|---|---------|-------|
| M1 | Kaggle dataset + EDA notebook (deskriptivna statistika, prilagođavanje raspodjele, χ² test saglasnosti) | distribucije steering/brzina → konkretni parametri za 4.4 i 4.5 + statistički izvještaj |
| M2 | Unity projekat: scena, vozilo, CarAgent, checkpointi; heuristička vožnja (ručno upravljanje) radi | vozilo vozivo tastaturom, observacije provjerene |
| M3 | PPO trening + tjuniranje rewarda | .onnx model, TensorBoard krive, agent završava krugove |
| M4 | BC trening na datasetu | treniran CNN, validacijske metrike |
| M5 | Evaluacija, poređenje, grafovi, README | results/plots, finalna priča za odbranu |

Redoslijed M3/M4 može biti paralelan (RL trening traje - u međuvremenu BC).

## 10. Rizici

| Rizik | Mitigacija |
|-------|------------|
| WheelCollider fizika nestabilna | fallback: kinematski model (odluka kraj M2) |
| RL ne konvergira | curriculum: prvo šira staza / manje kazne, pa pooštriti; više paralelnih arena |
| Verzijski konflikt ML-Agents | tačne verzije iz sekcije 8, testirati "hello world" (3DBall) prije vlastite scene |
| Dataset struktura drugačija od očekivane | M1 prvo verifikuje format (driving_log.csv kolone) prije svega ostalog |
| Reward hacking (agent vrti u krug) | checkpoint sistem sa smjerom + kazna za pogrešan smjer |

## 11. Srodni projekti (prior art)

Ne izmišljamo toplu vodu - pristup je etabliran; ovi projekti služe kao referenca
za dizajn i kao "related work" na odbrani. Kod se ne kopira (samostalna
realizacija + individualna odbrana), preuzimaju se provjereni obrasci.

| Projekat | Šta je | Šta preuzimamo |
|----------|--------|----------------|
| [Unity Karting Microgame + ML-Agents](https://learn.unity.com/project/karting-template) | Unityjev **službeni** template: kart uči voziti stazu raycast senzorima (KartAgent komponenta) | Validacija cijelog našeg pristupa (raycast + PPO + checkpointi); referentna struktura reward funkcije i agent skripte |
| [udacity/self-driving-car-sim](https://github.com/udacity/self-driving-car-sim) | Open-source Unity simulator iz kojeg potiče format našeg dataseta (`driving_log.csv`) | Referenca za postavku kamere na vozilu i format logovanja (naš `DrivingLogger.cs` piše kompatibilne kolone); dokaz da je dataset "Unity-native" |
| [OzAltagar7/Smarticar](https://github.com/OzAltagar7/Smarticar) | ML-Agents self-driving auto, 8 raycasta | Poređenje broja/rasporeda zraka |
| [grantgasser/autonomous-vehicles-mlagents-unity](https://github.com/grantgasser/autonomous-vehicles-mlagents-unity) | Držanje trake u Unity okruženju (RL) | Ideje za reward shaping |
| [mchrbn/unity-traffic-simulation](https://github.com/mchrbn/unity-traffic-simulation) | Waypoint traffic sistem (raskrsnice, semafori) | Kontekst za odbranu: proširenje ka multi-agent saobraćaju (potencijal za magistarski) |
| [AWSIM (Autoware)](https://autowarefoundation.github.io/AWSIM-Labs/) | Industrijski AV simulator baziran na Unityju | Argument da je Unity legitiman alat za AV simulaciju, ne samo igre |

Zaključak za dizajn: naša kombinacija (raycast observacije, PPO, checkpoint
reward) odgovara Unityjevom službenom Karting ML-Agents obrascu - dodana
vrijednost ovog projekta je integracija stvarnog dataseta (kalibracija + BC
poređenje), što nijedan od navedenih projekata nema.

## 12. Predaja (Google Classroom)

- Unity projekat (bez Library/ foldera), Python kod, config, DESIGN.md, README.md
- Dataset (zip ili link, kako profesor traži "dataset + izvorne datoteke")
- results/ sa grafovima i treniranim modelima (.onnx, .pt)
- README: tačni koraci reprodukcije (instalacija → trening → evaluacija)
