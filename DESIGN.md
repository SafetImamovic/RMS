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

**Izmjerene vrijednosti (T022 do T025, zatvoreno 31.07.2026.).** Ovo su jedine brojke u
projektu koje dolaze iz mjerenja a ne iz odluke:

| Veličina | Vrijednost | Mjerenje | Odstupanje |
|---|---|---|---|
| `steer_rate_norm_per_s` | **3.7** | P95 \|dsteer\| = 0.2949 na 14.08 Hz, vožnja 67.2 s | 1.7 % od cilja 0.30 |
| `accel_ms2` | **5.0** | izmjereno +4.79 m/s² | -4.2 % |
| `brake_ms2` | **5.85** | izmjereno -5.65 m/s² | -3.4 % |
| poluprečnik punog zaokreta | **5.787 m** | vs `r_min_m` 5.361 m | +7.9 % |

`accel_ms2` i `brake_ms2` su **potvrđeni, nisu podešavani**. Zadatak T024 je dozvoljavao
izmjenu ako mjerenje promaši 10 %, ali nije promašilo, pa vrijednosti ostaju kakve su bile.

Poluprečnik je +7.9 % širi od bicikl modela zato što **oba prednja točka dobijaju isti ugao
zakretanja**, bez Ackermann razlike između unutrašnjeg i vanjskog. Unutrašnja guma zato
struže i gura auto prema vani. To je svojstvo modela, ne greška, i ostaje unutar tolerancije
od 10 %.

**Brzina je dio ovog mjerenja, ne uzgredna okolnost.** Prvi pokušaj poluprečnika držao je
fiksni gas umjesto brzine, dosegao 6.54 m/s, dakle 0.72 g bočnog opterećenja, i prijavio
6.065 m (+13.1 %, pad). Ponovljen pri držanih 2.02 m/s, dakle 0.07 g, daje 5.787 m i prolazi.
Poluprečnik je geometrija i mjerljiv je samo tamo gdje su uglovi klizanja zanemarivi.

**Ništa izmjereno prije popravke fizike točka nije vrijedilo.** Ranije vožnje su za isti
profil prijavljivale ubrzanje između +0.03 i +2.53 m/s². Razlika nikad nisu bili parametri
vozila nego solver trenja koji je oscilovao: jedan impuls trenja mijenja obodnu brzinu točka
za `2*F*dt/(m_točka*r)`, što je 8.4 m/s sa fabričkom krivom, dakle više nego greška koju
ispravlja. Točak je prelijetao i vraćao se svaki korak, i to sa **nula** pogonskog momenta.
Rješenje je `ConfigureVehicleSubsteps(5, 30, 30)`, koje dijeli korak samo za solver točka i
spušta korekciju na 0.67 m/s po podkoraku. Da su `accel_ms2` i `brake_ms2` podešavani prema
starim brojkama, artefakt solvera bi trajno ušao u konfiguraciju.

**Poznato odstupanje: `speed max/P99` = 1.038 naspram trake [1.13, 1.38].** Ovo nije
nedostatak vozila. Odnos mjeri koliko vršna brzina prelazi tipičnu, a auto na ravnoj ploči
bez krivina nema razloga da ikad uspori, pa stoji prikovan za ograničenje od 10 m/s i P99 se
izjednači s maksimumom. Vozač u datasetu je bio na stazi koja ga je tjerala da koči i ponovo
ubrzava. Mjeri se, dakle, **odsustvo staze**, i provjera može proći tek kad US2 generiše
stazu.

> Vožnje T022, T024 i T025 izvodi `ScriptedDriver` fiksnim ulazima, pa su ponovljive i mogu
> se premjeriti poslije svake izmjene (Princip VI). T023 je namjerno **ljudska** vožnja: on
> poredi ljudski steering s ljudskim datasetom, pa bi skripta mjerila samu sebe.

> Izvor: `specs/003-unity-environment/research.md` C1 do C4 i C15. Vrijednosti žive u
> `python/track/config.py`, izvoze se u `unity/.../Assets/Tracks/vehicle_profile.json`, a
> C# kopija se poredi s njim u `VehicleProfileMirrorTests`. Razilaženje pada kao test, ne
> kao tiho pogrešna geometrija.

### 4.3 Observacije (ukupno 19 vrijednosti)
| Observacija | Dim | Napomena |
|-------------|-----|----------|
| Raycast udaljenosti | 13 | 180° naprijed, domet 20 m, normalizovano na [0, 1] |
| Brzina (lokalna, normalizovana) | 2 | naprijed + bočna komponenta |
| Ugaona brzina (yaw) | 1 | |
| Smjer ka sljedećem markeru (dot product) | 2 | forward·dir, right·dir |
| Trenutni steering | 1 | omogućava glatkoću |

**Odlučene vrijednosti senzora (fiksirano u M2, prije bilo kakvog koda faze 5).**

| Veličina | Vrijednost | Odakle |
|---|---|---|
| `RAY_COUNT` | **13** | neparan broj, pa jedna zraka gleda tačno naprijed; 15° razmak |
| `RAY_FOV_DEG` | **180** | polukrug ispred; iza vozila nema šta da se izbjegne na jednosmjernoj petlji |
| `RAY_LENGTH_M` | **20** | **izvedeno, nije izabrano**, vidi ispod |

**Domet od 20 m je izveden iz kočenja, ne odabran.** Pri `v_max_ms` 10 m/s i `brake_ms2`
5.85 m/s^2 put zaustavljanja je `v^2 / (2a)` = 8.55 m. Domet od 20 m je nešto više od
dvostrukog tog puta, pa agent prepreku vidi sa **vremenom da reaguje**, a ne tek sa vremenom
da stane. Domet jednak putu zaustavljanja bio bi formalno dovoljan i praktično beskoristan:
zid bi ušao u vidno polje tačno u trenutku kad je puna kočnica jedini preostali potez.

**Nepogodak mora biti razlučiv od pogotka na nuli (FR-025).** Zraka koja ništa ne pogodi i
zraka koja pogodi zid tik uz branik su suprotne situacije, a naivno kodiranje ih obje svede
na jedan broj blizu ekstrema. Nepogodak se zato kodira kao **1.0** (puna, slobodna
udaljenost), a pogodak kao `udaljenost / RAY_LENGTH_M`, pa pogodak na nuli daje 0.0. Dva
kraja opsega, dvije suprotne stvari.

Ne koristi se ugrađeni `RayPerceptionSensor3D`. Njegovo kodiranje je one-hot po tagu plus
udaljenost, što je više vrijednosti nego što ovdje treba, a broj koji ulazi u mrežu se ne
može pročitati u toku vožnje. T057 traži da se **svaka** observacija vidi uživo i provjeri
protiv situacije čiji je tačan odgovor vidljiv (T062, kapija za M2), i to je lakše nad
sopstvenim, jednostavnijim kodiranjem.

> Izvor: research C11. Vrijednosti žive u `python/track/config.py`. **Ispravka
> (2026-08-04):** za razliku od parametara vozila, ove tri vrijednosti se **ne** prenose u
> `vehicle_profile.json` - eksporter ne piše blok senzora, pa između `CarAgent.cs` i
> `config.py` ne stoji mirror test. Promjena bilo koje od njih traži ručnu izmjenu na oba
> mjesta. Dodavanje bloka bi podiglo schema verziju profila, a taj profil je ugrađen u svaki
> već commitovan track fajl.

**Izmjereno (T059, 2026-08-04, u editoru bez play moda).**

| Provjera | Rezultat | Granica |
|---|---|---|
| Bočne zrake naspram pravih branika, seed 1, pomaci −1.5 do +1.5 m | **greška 0.00 %** | 5 % (SC-013) |
| Svih 13 zraka u sintetičkom koridoru širine 6 m | **greška 0.00 %**, razmak 15.00° | 5 % |
| Ništa u dometu | 13/13 zraka `no hit`, najniža normalizovana vrijednost **1.000** | mora biti 1.000 |
| Branik na 0.10 m od senzora | čita 0.100 m, normalizovano **0.0050**, `hit=true` | ≈ 0.0 |

Mjereno na uzorku 1017 centralne linije, tj. na najravnijem dijelu kruga (lokalni radijus
29 827 m). Branik je poligonalni pomak zakrivljene linije, pa okomita zraka pogađa tačno na
pola širine samo tamo gdje je zakrivljenost zanemariva; u oštroj krivini je prava
udaljenost stvarno različita od 3 m, pa bi ispravna zraka izgledala pogrešno. Sintetički
koridor postoji jer prava staza može provjeriti samo dvije zrake koje gledaju popreko:
lepeza sa pogrešnim razmakom i dalje tačno čita na −90 i +90 ako su joj krajevi tačni.

**Visina senzora je ispravljena tokom T059.** Podrazumijevani pomak je stavljao lepezu na
y = 1.0 m na vozilu čiji je origin na 0.5 m, a branici su visoki 0.8 m - **svaka zraka je
gledala preko svakog branika**. Sada je −0.1 lokalno, dakle lepeza na 0.4 m, na sredini
branika, sa rezervom za propinjanje i poskakivanje karoserije.

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

Gornja tabela je **polazna**, i to je ona koju kod nosi osim dok traje pojedini tjuning run.
Koja težina je u kojem runu promijenjena stoji niže, u „Dva kandidata za tjuniranje“, i u redu tog
runa u `results/EXPERIMENTS.md`.

**Odlučene vrijednosti markera i starta (fiksirano u M2, prije bilo kakvog koda faze 5).**

| Veličina | Vrijednost | Odakle |
|---|---|---|
| `N_CHECKPOINTS` | **24** | oko 8 m razmaka na stazi od ~200 m, dakle nekoliko markera po krivini |
| `START_LATERAL_M` | **1.5** | pola razmaka do ivice pri širini staze 6 m |
| `START_YAW_DEG` | **10** | dovoljno da start ne bude savršen, premalo da bude nemoguć |

**Marker se dodjeljuje samo ako je onaj koji je na redu.** Prsten markera pamti
`next_index`; dodir bilo kojeg drugog ne daje ništa. Bez tog pravila agent koji preskoči
polovinu kruga i uđe na markeru dalje niz stazu bio bi nagrađen za prečicu, a nagrada za
napredak bi mjerila poziciju umjesto pređenog puta. Krug se broji kad se indeks obrne.

**Pogrešan smjer se prijavljuje, ne boduje** (FR-028). Postavlja se kad vozilo priđe već
prođenom markeru. Bodovanje pripada M3, a pravilo iz kojeg bi ono slijedilo pripada ovdje;
razdvojeno je da prvo podešavanje rewarda ne mijenja fajlove koje je M2 proglasio
provjerenim.

**Izmjereno (T060 i T061, 2026-08-04).** Skriptirani prolaz kroz svih 2000 uzoraka seeda 1,
sa ručno primijenjenom `OnTriggerEnter`/`OnTriggerExit` semantikom. Staza 202.3 m, 24
markera, razmak 8.43 m.

| Provjera | Rezultat | Granica |
|---|---|---|
| Jedan krug sa startova 0, 6 i 18 | **24/24 dodijeljeno, 1 krug, 0 preskočenih, bez pogrešnog smjera** - svaki put | SC-014 |
| Okret na pola kruga, poslije 11 markera na s = 98.5 m | pogrešan smjer prijavljen nakon **3.43 m** vožnje unazad | 8.43 m, tj. jedan razmak (SC-015) |

**Ovaj zadatak je našao stvarnu grešku.** Vozilo se postavlja **na** marker, dakle unutar
njegovog trigger volumena, a Unity okida `OnTriggerEnter` za preklapanje nastalo
teleportom jednako kao za ono u koje je vozilo dovezlo. Taj dodir pada na marker koji je
`StartAt` upravo upisao kao prođen, pa bi **svaki randomizovani start prijavio pogrešan
smjer prije nego se vozilo pomjeri**. Riješeno tako što prsten pamti marker u kojem vozilo
stoji i ignoriše ga dok `OnTriggerExit` ne javi da ga je napustilo.

**Start se randomizuje, i to nije kozmetika (research C12).** Epizoda počinje na
**slučajnom markeru**, sa bočnim pomakom do 1.5 m i zakretom do 10 stepeni. Uvijek isti
start znači da agent vidi prvu krivinu staze desetine hiljada puta, a zadnju rijetko, pa
nauči redoslijed umjesto vožnje. Isti razlog stoji iza podjele na train i eval skup seedova:
politika koja je naučila jednu stazu napamet pada na drugoj, a to se vidi samo ako druga
staza postoji.

**Odlučeno za M3 (feature 006, prije koda).**

**Frekvencija odluke.** Fizika ide na 50 Hz (`Fixed Timestep: 0.02`), ljudski dataset je snimljen
na 14.08 Hz (`COMPARE_HZ`), a 50 se sa 14.08 ne dijeli. `DecisionPeriod = 4` daje **12.5 Hz**,
najbližu ostvarivu frekvenciju ispod dataset rate-a; `DecisionPeriod = 3` bi dao 16.67 Hz.
Odlučivati brže nego što je čovjek snimljen znači praviti više promjena komande u sekundi nego
raspodjela iz koje je prag 0.55 izmjeren, čime prag tiho postaje lakši za izbjeći. Na 12.5 Hz je
korak nešto duži nego u datasetu, pa ista putanja daje nešto veće delte po koraku, dakle greška
ide u stranu strožijeg kažnjavanja.

**Prag bez svoje frekvencije nije prag.** 0.55 je P95 od |Δsteering| na 14.08 Hz, pa se frekvencija
odluke upisuje uz svaki run. Feature 005 je istu grešku već sreo: ista vožnja daje različit broj za
glatkoću na fizičkom taktu i na `COMPARE_HZ`.

Ono što tabela sama ne rješava:

- Kazna za nagli steering množi **cijelu** |Δ|, ne višak iznad praga, kako tabela i piše.
  Posljedica je skok: delta 0.549 ne košta ništa, 0.551 košta 0.00276. To je svojstvo odluke,
  zapisano ovdje da se kasnije ne pročita kao greška u kodu.
- Brzina se plaća samo naprijed. `v_norm` je predznačen, pa se negativni dio odsijeca na nulu;
  inače bi vožnja unazad zarađivala po simetriji sa onim što gubi.
- Kazna za zid se dodaje **prije** kraja epizode. Obrnut redoslijed je izbacuje iz epizode kojoj je
  trener pripisuje.
- Pogrešan smjer se boduje na **prelazu** u stanje, ne svaki korak dok stanje traje. Prsten drži
  `WrongWay` kao zapamćeno stanje, pa bi bodovanje po koraku jednu grešku naplatilo desetinama
  puta. Time M3 zatvara ono što je M2 ostavio otvorenim: pravilo je prijavljivalo, sada i boduje, i
  to iz iste detekcije.
- Dodire zida za agenta broji **zaseban component** (`WallSensor`), a ne isti kod kojim ih broji
  heuristički vozač. Unity isporučuje `OnCollisionEnter` svakom componentu na objektu, pa dva
  brojača rade nezavisno. Dupliranje je namjerno: kod koji je proizveo objavljene redove feature-a
  005 se ne dira zbog ušteda od petnaestak linija.
- Svaki član rewarda se prijavljuje zasebno (`reward/checkpoint`, `reward/wrong_way`, `reward/wall`,
  `reward/step`, `reward/speed`, `reward/jerk`), a njihov zbir mora biti jednak povratu epizode.
  **Ukupan reward koji raste ne kaže koji ga je član podigao**, a to je razlika između napretka i
  naplaćivanja nagrade za brzinu u krug.

**Dva kandidata za tjuniranje, odlučena prije koda (T048, feature 006).** Tabela je od početka
pisana kao početna, a mjerenja iz Phase 5 kažu šta u njoj ne radi. Tri seeda na 2M koraka
(`ppo_car_spread_a/b/c`) daju povrat -4.61 koji se razlaže ovako: zid -2.230, korak -1.676,
pogrešan smjer -0.605, steering -0.353, checkpoint +0.251, brzina **+0.0069**.

Iz toga slijede dvije stvari koje tabela nije predvidjela:

- **Nagrada za brzinu je mrtva.** +0.0069 naspram -1.676 za postojanje znači prosječni `v_norm`
  oko 0.004. Vozilo se praktično ne kreće.
- **Zaglaviti se je jeftinije nego udariti.** Zaglavljivanje završava epizodu nakon 60 s, dakle
  oko -3.0 po cijeni koraka, a zid naplaćuje -5.0 odmah. Politika je izabrala dominantnu strategiju
  ispravno; problem je u tabeli, ne u učenju.

Zato se mijenja po jedna težina po runu, svaka u svom redu tabele eksperimenata (FR-007):

| Kandidat | Polje | Sa | Na | Šta testira |
|---|---|---|---|---|
| `ppo_car_jerk_lo` | `JerkPenalty` | -0.005 | **-0.001** | da li kazna za glatkoću guši istraživanje steeringa koje treba da bi se došlo do markera |
| `ppo_car_wall_lo` | `WallPenalty` | -5.0 | **-1.0** | obrće odnos iz gornje tačke: udarac (-1.0) postaje jeftiniji od zaglavljivanja (-3.0) |
| `ppo_car_speed_hi` | `SpeedReward` | 0.001 | **0.002** | spušta prag isplativosti sa `v_norm` 1.0 na 0.5, koliko invarijanta protiv farmanja dopušta (dodan 2026-08-24, obrazložen niže) |

Kazna za steering ostaje živa, ne gasi se na nulu, jer je glatkoća namjera tabele, a prag 0.55 i
dalje nosi svoju frekvenciju. Petina skale skida oko 0.28 pritiska protiv okretanja volana bez
uklanjanja člana.

**Promjena težine mijenja i mjerilo, pa se poređenje ne smije čitati naivno.** Prag 0.19 iz T047 je
izmjeren na jednoj tabeli rewarda; run pod drugom tabelom ima drugu skalu povrata. Zato T049
izvještava na tri načina: povrat baseline runova preskaliran na kandidatove težine iz već
zabilježenih članova (FR-008 to čini tačnim, a ne procjenom), `reward/checkpoint` koji je
nepromijenjen u oba kandidata, i sirovi povrat sa upisanom ogradom. Preskalirane baseline
vrijednosti su **-4.3310** za tabelu sa steeringom -0.001 i **-2.8294** za tabelu sa zidom -1.0.

**Ishod, upisan nakon oba runa (2026-08-20).** Nijedna od dvije težine se ne zadržava, pa gornja
tabela ostaje ta koju kod nosi. `ppo_car_jerk_lo` daje +0.0553 naspram praga 0.19, dakle nema
mjerljive razlike. `ppo_car_wall_lo` daje -0.3185, dakle **prelazi prag, ali na lošiju stranu**:
mješavina razloga kraja se pomjerila tačno kako je predviđeno, sa 46.8 na 51.4 posto zida i sa
39.9 na 35.4 posto zaglavljivanja, a povrat je pao. Nijedan run nije završio krug. Detalji i
brojevi po kvartalima su u `results/EXPERIMENTS.md`.

**Šta ovo ostavlja kao sljedeću hipotezu.** Ni kazna za steering ni terminal za zid nisu ono što
ovu politiku zaustavlja. Dva člana koja nijedan kandidat nije dirao su ona koja je dekompozicija
učinila sumnjivim: **cijena koraka -1.676 po runu naspram nagrade za brzinu +0.0069**, dakle vozilo
plaća 240 puta više za postojanje nego što dobija za kretanje. To je hipoteza za sljedeću izmjenu
dizajna, ne rezultat ovih runova, i mijenja se tek kad bude zapisana ovdje.

**Treći kandidat, odlučen 2026-08-24 (T048 proširen).** Prethodni pasus je bio hipoteza; ovaj
pasus je odluka, i piše se prije koda kako Princip V traži. Mijenja se **`SpeedReward`, sa 0.001 na
0.002**, i to je jedina promjena u tom runu.

**Zašto se mijenja nagrada za brzinu, a ne cijena koraka.** Prag isplativosti je
`|StepCost| / SpeedReward`, pa ga obje promjene pomjeraju jednako. Razlika je u tome šta rade sa
zaglavljivanjem: spuštanje `StepCost` čini stajanje jeftinijim, a zaglavljivanje je već 39.9 posto
završetaka, dok podizanje `SpeedReward` plaća kretanje bez da smanjuje pritisak protiv stajanja.

**Zašto baš 0.002, a ne više.** Ovdje postoji gornja granica koju tabela sama nameće, i nije stvar
ukusa. Član `Idle` je namjerno napisan tako da se pri punoj brzini trošak koraka i nagrada za
brzinu **tačno ponište**, što je odbrana od farmanja: vožnja u krug po otvorenoj površini ne smije
zaraditi koliko i krug kroz markere. Epizoda po DESIGN 4.6 traje najviše 6000 koraka, pa granica
glasi:

```
(SpeedReward - |StepCost|) x 6000  <  24 markera / 3
(SpeedReward - 0.001)      x 6000  <  8         =>  SpeedReward < 0.002333
```

Na 0.002 vožnja u krug punom brzinom donosi najviše +6 kroz cijelu epizodu, naspram +24 za krug,
dakle krug je i dalje četiri puta bolji. Na 0.005 bi krug u mjestu donosio +24 i izjednačio se sa
krugom kroz markere, što bi ugasilo odbranu iz `Idle`.

**Zašto 0.002, a ne 0.0023 koliko granica dopušta.** Ispod plafona se bira okrugao broj sa
rezervom od oko 15 posto, i to zato što prag isplativosti tada ispada tačno `v_norm = 0.5`, što je
veličina koja se da pročitati i provjeriti, a 0.0023 bi dalo 0.435 i ništa ne bi kupilo. Sjedjeti
tačno na ivici invarijante je ionako loše: pri 0.002333 razlika `SpeedReward - |StepCost|` se
računa u `float` aritmetici i granica postaje pitanje zaokruživanja, a ne dizajna.

**Šta ova promjena košta, rečeno brojem.** Pri 0.002 vozilo mora voziti u krug punom brzinom 1000
koraka, dakle 20 s pri 50 Hz, da zaradi koliko nosi jedan marker. Pod starom tabelom nikakva
količina vožnje u krug nije dostizala marker, jer je zarada bila tačno nula. To je cijena gradijenta
i zapisana je ovdje da se kasnije ne pročita kao previd.

**Ishod, upisan nakon runa (2026-08-24).** Težina se **ne zadržava**, pa gornja tabela ostaje ta
koju kod nosi. `ppo_car_speed_hi` daje -0.0373 naspram praga 0.19, dakle nema mjerljive razlike.
Odlučujući broj nije prag nego mehanizam: `reward/speed` je otišao sa +0.0069 na +0.0150, a politika
koja se **nije nimalo promijenila** dala bi tačno +0.0138, jer je težina udvostručena. Cijeli odgovor
u ponašanju je +0.0012, odnosno prosječni `v_norm` sa 0.00410 na 0.00459: **dvanaest posto više
brzine za dvostruko veću platu.**

**Zaključak za koji je run bio pre-registrovan.** Ova tabela se ne može popraviti skaliranjem svojih
težina. Sva tri kandidata su promašila prag u boljem smjeru i nijedan nije završio krug. Vozilo koje
je plaćeno dvostruko za kretanje a kreće se dvanaest posto više nije ograničeno visinom plate - nije
pronašlo ponašanje koje se plaća. To je problem istraživanja prostora, a njegovi lijekovi su druge
vrste od težine: kurikulum koji startuje bliže markeru, gušći signal napretka od jednog markera u
dvadeset četiri, ili topli start iz BC politike koju M4 ionako proizvodi. Svaki od njih je izmjena
dizajna po Principu V i nova feature, ne tjuning run faze 5. **Feature 007 uzima drugi od ta tri
lijeka**, gušći signal napretka, i odlučen je niže. Preostala dva ostaju otvorene feature i nisu
dirana, da bi se pomjeren broj mogao pripisati jednom lijeku.

**Posljedica koju treba reći naglas: ovo je promjena od svega dva puta, a nesrazmjer je 240 puta.**
Prag isplativosti pada sa `v_norm = 1.0`, dakle vozilo je moralo voziti punom brzinom samo da ne
gubi, na `v_norm = 0.5`. To je pomak u pravu stranu, ali invarijanta protiv farmanja ne dozvoljava
više. **Zato je ovaj run pre-registrovan u oba ishoda:** ako pređe prag iz T047, odnos koraka i
brzine jeste bio ograničenje; ako ne pređe, onda se ova tabela ne može popraviti skaliranjem ta dva
člana i problem je istraživanje prostora, ne težine - što je zaključak koji vrijedi jednako kao i
pozitivan.

**Invarijanta se ne briše, nego se zamjenjuje.** `RewardModelTests` je do sada tvrdio
`Idle(1) == 0` tačno, i taj test je ovu promjenu uhvatio, što je i bio razlog da postoji. Zamjenjuje
ga tvrdnja sa marginom: zarada od vožnje u krug kroz cijelu epizodu mora ostati manja od trećine
onoga što nosi krug kroz markere. Tvrdnja da stajanje u mjestu gubi svaki korak ostaje netaknuta,
jer `Idle(0)` i dalje zavisi samo od `StepCost`.

**Odlučeno za feature 007 (gusti signal napretka), prije koda.** Tabela dobija **jedan član**, a
šest postojećih ostaju nepromijenjena po imenu, težini, uslovu okidanja i ključu statistike. Ovaj
feature dodaje član i ne tjunira tabelu koju je zatekao, da bi taj član bio jedina promjenljiva.

| Događaj | Reward | Svrha |
|---------|--------|-------|
| Napredak po lancu markera | +`w × Δs` po koraku fizike, `w = 0.5 × 24.0 / dužina lanca` | gradijent između markera |

**Zašto uopšte.** Jedini član koji je govorio „ideš u pravu stranu“ bio je +1.0, a plaćao se 24 puta
po krugu, na markerima razmaknutim 8.43 m. Kroz devet runova politika je zaradila prosječno **0.249**
markera po epizodi. Signal koji se vidi jednom u nekoliko stotina koraka, ako i tada, nije gradijent
po kojem se može penjati. Svi ostali članovi su ili cijena postojanja ili kazna za umiranje, a oboje
se minimizuju time da se vozi manje, što je tačno ono što je politika naučila.

**Šta je potencijal, i zašto nije udaljenost do sljedećeg markera.** Član je razlika **pozicije po
lancu markera** između dva uzastopna koraka fizike. Lanac je izlomljena linija kroz 24 markera, a
pozicija je dužina lanca do segmenta na kojem je vozilo, plus projekcija vozila na taj segment.
Očigledna alternativa, udaljenost do sljedećeg markera, nije lošija nego pogrešna: ta udaljenost
skače sa oko nule na 8.43 m tačno u trenutku kad marker bude uzet, pa bi razlika naplatila cijeli
razmak kao kaznu za korak u kojem je vozilo uradilo ono što se traži. Vozilo bi bilo plaćeno da
prilazi markeru, a kažnjeno da ga dosegne.

**Zbir se skraćuje do razlike krajeva, i to je cijeli dizajn.** Pošto je član razlika jedne
veličine, njegov zbir po bilo kojoj putanji jednak je razlici te veličine na krajevima putanje i
ničemu više. Posljedica koja se ovdje traži: **svaka putanja koja vrati vozilo u stanje u kojem je
već bilo nosi tačno nulu**, bez obzira šta je radila između.

**Invarijanta protiv farmanja ostaje, i ostaje istom aritmetikom.** Tvrdnja je da vožnja u krug po
otvorenoj površini kroz cijelu epizodu mora zaraditi manje od trećine onoga što nosi krug kroz
markere, dakle manje od 8.0. Novi član vožnji u krug donosi **tačno nulu**, po gornjem svojstvu, pa
račun ostaje onaj koji već piše: pri `SpeedReward` 0.002 epizoda vožnje u krug punom brzinom nosi
najviše +6.0, naspram +24 za krug kroz markere. Naivna verzija člana, ona koja plaća smanjenje
udaljenosti do sljedećeg markera, srušila bi invarijantu u jednoj liniji, jer bi vozilo koje se
ljulja prema markeru i nazad zarađivalo neograničeno. **Invarijantu čuva oblik člana, a ne dovoljno
mala težina.**

**Pozicija se ne resetuje na cilju, nego se odmotava.** Pamti se ukupan pređeni put po lancu od
početka epizode, uvećan za `broj krugova × dužina lanca`. Verzija koja bi poziciju vratila na nulu
na startnoj liniji naplatila bi cijeli krug kao kaznu u jednom koraku, jednom po krugu. Odmotavanje
ne traži nikakav poseban slučaj, pa nema ni koraka u kojem bi se greška najteže primijetila.

Ovdje ide i ograda. Odmotana pozicija je funkcija putanje, a ne trenutnog stanja, pa preko startne
linije ovo strogo uzevši nije potencijal nad stanjem; unutar kruga jeste. Ono što odmotavanje čuva
su dva svojstva koja se ovdje i traže i testiraju: zbir se skraćuje do razlike krajeva, i svaka
petlja koja ne pređe startnu liniju u ispravnom smjeru nosi nulu. Prelazak startne linije naprijed
je upravo ono ponašanje koje se plaća, i plaćen je najviše dužinom kruga. Besplatne petlje nema.

**Pozicija ne smije preći marker koji je na redu.** Pravilo da se marker dodjeljuje samo ako je onaj
koji je na redu postoji od M2 i sprečava da prečica bude nagrađena. Geometrijski računata pozicija
bi tu prečicu ipak platila, jer bi skočila naprijed. Zato se pozicija ograničava plafonom na kraju
segmenta koji se završava markerom `next_index`. Vozilo koje presiječe i uključi se dalje niz stazu
stoji na plafonu, ne zarađuje ništa a i dalje plaća korak, i mora se vratiti po marker koji je
preskočilo. Time je prečica **strogo lošija** od legalnog puta, a ne samo nenagrađena.

**Težina se izvodi, ne bira.** Neka krug napretka plaća `alpha` puta ono što plaća krug markera:

```
napredak po krugu  =  alpha × 24.0
težina po metru    =  alpha × 24.0 / dužina lanca
```

**Uzima se `alpha = 0.5`, dakle krug napretka nosi 12.0 naspram 24.0 koje nose markeri.** Tri
razloga, po važnosti:

- **Markeri moraju ostati veći signal.** Na njima je definisan milestone, a gusti član postoji da
  politiku dovede do njih, ne da ih zamijeni. Pri `alpha = 0.5` krug kroz sve markere nosi 36.0, od
  čega su dvije trećine i dalje ono što se mjeri.
- **Član po koraku mora nadmašiti cijenu koraka dovoljno da bude gradijent.** Pri oko 0.2 m po
  koraku fizike, koliko skriptirani vozač postiže, `alpha = 0.5` na lancu od 202.3 m daje oko
  **0.0119 po koraku** naspram cijene koraka -0.001. To je red veličine razlike, a pod starom
  tabelom je signal za napredovanje između markera bio tačno nula.
- **Invarijanta ostaje netaknuta**, po računu iz prethodnog pasusa.

`alpha = 1.0` je odbačeno: krug napretka jednak krugu markera čini dva signala ravnopravnim, pa
svaka greška u geometriji lanca košta koliko i propušten marker. Biranje broja po koraku direktno je
odbačeno iz principa: broj po koraku se ne može uporediti ni sa čim, a udio kruga se poredi sa 24.0
koje već stoje u tabeli. **Težina se računa pri gradnji staze, a ne upisuje kao literal**, jer se
generisane staze razlikuju po seedu i literal bi na različitim stazama plaćao različit udio kruga.
Reprodukuje se izvod, ne broj (Princip VI).

Ono što ni ovaj red tabele sam ne rješava:

- **Prvi korak epizode nosi nulu.** Nema prethodne pozicije za razliku, a prirodna greška je
  razlikovati od nule, čime bi se cijela pozicija po lancu randomizovanog starta isplatila u prvom
  koraku svake epizode. To je najčešći događaj u treningu.
- **Član je simetričan.** Vožnja unazad kroz istu dionicu košta tačno ono što je vožnja naprijed
  platila. Odsijecanje negativnog dijela, po uzoru na ono što se radi sa brzinom, ovdje bi bilo
  farmanje: ljuljanje naprijed-nazad zarađivalo bi po pola ciklusa.
- **Vožnja unazad se sada naplaćuje dva puta, i to je namjerno.** Pogrešan smjer se prijavljuje
  nakon 3.43 m unazad; na nominalnom lancu tih 3.43 m nosi i oko **-0.204** napretka, povrh -1.0 za
  pogrešan smjer. Broj stoji ovdje da se kasnije ne pročita kao previd.
- **Pozicija se drži u `double`, i razlika se uzima u `double`.** Na `float` bi ovo bio problem:
  `float` nosi oko sedam značajnih cifara, pa je pri ukupno pređenih 1000 m najmanji predstavljiv
  pomak oko 0.00006 m, a zbir hiljada malih članova naspram jedne velike razlike je tačno mjesto
  gdje se nakupljena greška vidi. U `double` je ulp na 1024 oko `2.3e-13` m, dakle dvanaest redova
  veličine ispod pomaka od 0.2 m po koraku, i oduzimanje dva velika zbira nema šta da izgubi. Na
  `float` se prelazi tek na kraju, kad razlika postane reward.
  **Ispravka, upisana pri implementaciji (T004, 2026-08-25).** Prva verzija ovog pasusa je tražila
  da se pomak računa lokalno, iz promjene projekcije na tekućem segmentu, umjesto oduzimanjem
  zbirova. To je odbačeno jer je lošije, ne samo složenije: reward je razlika **ograničene**
  pozicije, a ne sirove, pa bi lokalni račun morao pratiti i da li je prethodni korak stajao na
  plafonu. Time bi se logika plafona duplirala na dva mjesta, a plafon je upravo dio u kojem bi
  greška bila najskuplja.
- **Prethodna pozicija se briše na svakom početku epizode**, uključujući i zamjenu staze u trening
  kopiji. Feature 006 je već našao da `TrainingArea.SwapTo` zaobilazi prijavu rewarda; isti put ne
  smije zaobići ni ovo brisanje, jer bi ustajala pozicija sa druge staze u jednom koraku naplatila
  stotine metara.
- **Član ima svoj ključ statistike, `reward/progress`**, i zbir sada sedam članova mora biti jednak
  povratu epizode. Nijedan drugi kod ne smije zvati `AddReward`.

**Prag 0.19 iz T047 se ne smije ponovo upotrijebiti.** Izmjeren je na povratu, a dodavanje člana
mijenja skalu povrata, pa povrat pod ovom tabelom nije uporediv sa povratom pod tabelom feature-a
006. Feature 007 mjeri svoj prag ponovo, istim protokolom tri identična runa, ali na veličinama na
kojima se i sudi: **markeri po epizodi, završeni krugovi i udio zaglavljenih epizoda.** Osnova koju
treba nadmašiti je 0.249 markera po epizodi.

**Run je pre-registrovan u oba ishoda.** Ako markeri po epizodi pređu novoizmjereni prag, rijetkost
signala jeste bila ograničenje i M3 se premjerava. Ako ne pređu, onda ni gusti signal nije bio to,
pa od tri imenovana lijeka ostaju dva, a jedan je uklonjen mjerenjem umjesto mišljenjem. Oba ishoda
se objavljuju.

**Uz ovo se zatvara i jedina otvorena stavka iz M3.** `episode_length` trenera (oko 530) i broj
naplata člana po koraku (oko 1676) razilazili su se za oko 3.16, sa maksimumom 4.01.
`TrainingArea.prefab` postavlja `DecisionPeriod: 4`, a trener broji odluke dok se reward naplaćuje
po koraku fizike, pa je **4 očekivani odnos** i maksimum ga potvrđuje. Ostaje objasniti manjak ispod
plafona, za šta feature 007 instrumentira oba brojača u istom runu. Svaka tvrdnja o trajanju epizode
u sekundama izvodi se iz broja koraka fizike na 50 Hz, i to kaže.

**Ishod, upisan nakon runova (feature 007, 2026-08-26). Član se zadržava.**

Mjereno je oba ishoda koja je pre-registracija imenovala, i pokazao se prvi.

- **Geometrija je potvrđena mjerenjem, ne tvrdnjom.** Skriptirani vozač na seedu 1, tri uzastopna
  kruga, svaki plaća **tačno 12.0**. `Unwrapped` raste za 201.02 m po krugu na lancu od 201.017 m,
  pa odmotavanje preko cilja ne košta nijedan poseban slučaj. Start je bio na markeru 17 od 24,
  dakle ne na nuli.
- **Markeri po epizodi: 0.2490 osnova naspram 1.4987 na kandidatu**, uz prag od 0.035 izmjeren na
  tri identična runa. Po četvrtinama runa 0.3477, 0.9794, 2.1148, 2.5528, dakle monotono, a ne
  skok. **Rijetkost signala jeste bila ograničenje.**
- **Osam epizoda je odvozilo puni zahtjev od tri kruga.** `episode/end_lapscompleted` se pali tek
  na `LapCount >= lapsToComplete`, a `TrainingArea.prefab` to postavlja na 3, pa je svaka od tih
  osam odvozila tri uzastopna kruga, a ne jedan. Nijedan run u M3 nije završio nijedan krug, kroz
  devet runova i preko 12.000.000 koraka.
- **Član plaća onoliko koliko je i projektovan.** U spread setu 0.1324 po epizodi, što je 2.2 m
  neto napretka; na kandidatu kasno 1.3843, što je 23.2 m ili oko 11.5 posto kruga.

**Milestone i dalje nije ispunjen, i to je druga polovina rezultata.** Na deset izdvojenih seedova,
u obje inference varijante, **nijedan krug nije završen**. Ono što se promijenilo je vrsta pada:
politika feature-a 006 je stajala na startu do isteka od 60 s i nije dosegla nijedan marker, dok
ova vozi oko četvrtine kruga i udari u ogradu, uz **6.20 od 24 markera**. Nula naprema 6.20 je prvi
rezultat na izdvojenim stazama koji nije nula, i nije krug.

**Zaglavljivanje je zamijenjeno udarom u ogradu, skoro jedan za jedan.** Udio zaglavljenih 0.3903
na 0.2741, udio udara 0.4773 na 0.5907. Sam po sebi taj par brojeva bi bio zamjena jednog pada
drugim; ono što zamjena ne objašnjava su šestostruko veći markeri i osam krugova.

**Zbir sedam članova ne odgovara povratu trenera, i to je defekt u instrumentaciji a ne u
nagradi.** Slaganje na **4.8 posto** redova, srednji ostatak +0.3030. Nema osmog člana: sva četiri
poziva `AddReward` su preslikana u razbijanje. Uzrok je da razbijanje rewarda i povrat trenera
prosjekuju preko skupova epizoda koji se razlikuju za oko **19 posto**, što istovremeno objašnjava
i manjak u odnosu koraka: `4 x 11219 / 13851 = 3.2398` naspram izmjerenih **3.2161**. Isti defekt
viđen dva puta. Koje se epizode razlikuju traži zapis po epizodi, i to je iskrena granica ovog
feature-a.

**Manjak ispod plafona od 4 je razdvojen.** Epizoda koja se završi usred prozora od 4 koraka može
oduzeti najviše `1.5 / d`, a epizode traju oko 485 odluka, pa taj mehanizam nosi **0.0031** od
manjka od 0.78. Sve ostalo nosi neslaganje skupova epizoda iznad. Stavka koju je M3 ostavio
otvorenom je time zatvorena.

**Red za zid ima dva dijela, i oni se mogu mijenjati odvojeno (feature 008).** Kazna je -5.0, a
terminal je to što epizoda staje na kontaktu. Feature 006 je runom `ppo_car_wall_lo` mijenjao
**kaznu** sa -5.0 na -1.0 i dobio mjerljivo lošiji povrat uz pomak u raspodjeli razloga kraja od oko
4.5 procentna poena; to je dokaz o težini. **Terminal nikad nije testiran**: u svakom runu M3
epizoda se završavala na prvom kontaktu, u obje grane svakog poređenja.

Feature 008 mijenja terminal i drži kaznu na -5.0, pa je pomjeren broj pripisiv jednom od ta dva.
Uvodi se `wallContactBudget`, broj **kontakata** koje epizoda preživi prije nego terminal proradi.
**Budžet broji događaje, ne korake i ne sekunde**: `WallSensor` ima samo `OnCollisionEnter`, pa
vozilo koje se vuče uz ogradu bez odvajanja potroši **jedan** kontakt na cijelo to vučenje. Nula
reprodukuje feature 007 tačno, i to je ono što poređenje čini poštenim.

**Rizik koji taj potez otvara** je da napredak plaća položaj po luku i ne mari kako je vozilo tamo
stiglo, pa je vučenje uz ogradu prema sljedećem markeru isplativo kao i čista vožnja. Danas ta
strategija ne postoji jer prvi kontakt završava epizodu. Mjeri se srednjim minimalnim bočnim
odstojanjem iz postojećeg snopa zraka, a ne brojem kontakata, iz razloga u prethodnom pasusu.

**Ishod, upisan 2026-08-27 nakon jedinog runa feature-a 008.** Odluka: **budžet se ne zadržava**,
`wallContactBudget` ostaje u kodu ali mu je podrazumijevana vrijednost **0**, što tačno reprodukuje
feature 007. Polje ostaje da bi se eksperiment mogao ponoviti bez izmjene koda; vrijednost bilježi
ishod.

Razlog: **hipoteza je odbijena, i smjer odbijanja je rezultat.** Tvrdnja je bila da politika ne može
naučiti oporavak od greške koju nikad ne smije preživjeti. `ppo_car_008_budget`, budžet 3, kazna
netaknuta na -5.0, 5.000.000 koraka, seed 42, jedna izmjena u odnosu na `ppo_car_007_progress`, dao
je **0.5297 markera po epizodi naspram 1.4987**, dakle razliku od -0.9689 koja prelazi prag od 0.035
oko 28 puta **u goru stranu**, i **nula krugova** naspram osam epizoda od po tri kruga. Raspodjela
razloga kraja se **obrnula**: sudar sa zidom 59.1 na **23.2** posto, zaglavljen 27.4 na **53.8**
posto, granica koraka 0.0 na 6.9 posto.

**Politika nije naučila oporavak nego se vratila zaglavljivanju**, a to je degenerisano rješenje
koje je M3 imenovao na samom početku: manje voziti je jeftiniji način da se prestane plaćati -5.0
nego bolje voziti. Prvi kontakt koji završava epizodu je tu opciju **potiskivao**, i podizanje
terminala ju je vratilo. **Terminal je bio noseći**, suprotno od onoga što je ovaj feature
pretpostavio.

**Veličina budžeta nije objašnjenje.** Prosjek je bio **1.218 kontakata po epizodi** naspram budžeta
od 3, pa tipična epizoda nikad nije ni prišla trošenju budžeta nego se završavala zaglavljivanjem.
Veći budžet bi bio potrošen još manje.

**Rizik vučenja uz ogradu je zatvoren brojem, i nije se desio.** Srednje bočno odstojanje je
**0.6331**, ravno po četvrtinama na 0.6367, 0.6454, 0.6218, 0.6284, sa minimumom runa 0.3231.
Politika koja jaše ogradu bi to držala blizu nule. To se slaže sa sondom iz T004, gdje se vozilo
pritisnuto uz ogradu pomjerilo 0.47 m za 5 s, pa vučenje nije konkurentna strategija jer fizika
vozila ne dozvoljava klizanje uz ogradu pri brzini. **Mjera i dalje nije potvrđena na stvarnom
paralelnom klizanju**, pa je ovo saglasan dokaz a ne dokaz u strogom smislu; ali uz malo kontakata,
puno zaglavljivanja i ravno odstojanje nema potpisa vučenja koji bi trebalo objašnjavati.

**Polovina milestone-a koja se ovim ne rješava, rečena ovdje da se ishod ne bi čitao kao uspjeh.**
Krug na neviđenoj stazi **nije** postignut, i u ovom feature-u **nije ni mjeren**: sweep po deset
izdvojenih seedova nije pokretan jer model nije kandidat i lošiji je u treningu od politike koja je
već izmjerena na 0 od 10 krugova. Zadnje izmjerene vrijednosti ostaju one feature-a 007, 0 od 10
krugova i 6.20 od 24 markera. Ono što je ovaj feature dodao nije korak prema milestone-u nego
uklanjanje jednog objašnjenja: **ni kazna ni terminal nisu vezujuće ograničenje**, jer je kaznu
oslobodio `ppo_car_wall_lo` u feature-u 006, a terminal ovaj run.

**Feature 009 uzima treći lijek, i morao ga je prvo ispraviti (upisano pri planiranju, 2026-08-28).**
Gore navedena tri lijeka su: kurikulum bliže markeru, gušći signal napretka, i topli start iz BC
politike. Feature 007 je uzeo drugi. Ovaj feature uzima treći, a **treći lijek onako kako je gore
napisan ne postoji**, i to se kaže naglas umjesto da se tiho zamijeni nečim drugim.

**Zašto ne postoji: observacija.** BC pipeline iz §6 trenira CNN nad **slikama kamere** iz Kaggle
dataseta. `DrivingAgent` čita **vektor od 19 vrijednosti** iz lepeze od 13 zraka, plus brzine i
skalarne proizvode kursa (§4.3). Dva prostora observacija nemaju nijednu zajedničku dimenziju, pa u
BC mreži ne postoji težina koja agentu išta znači, niti u datasetu postoji demonstracija koju bi
agent mogao vidjeti. Rečenica iz M3 zatvaranja je napisana prije nego što je iko uporedio ta dva
ulaza.

**Zamjena, i zašto je jedina.** `HeuristicDriver` (feature 005, §4.7) čita **istih 19 vrijednosti**
kroz istu lepezu, piše u isti `CarController`, i završava **34 od 34 trening seeda** (§4.7.2). To je
jedini vozač u projektu koji je istovremeno stručan i u agentovom prostoru observacija. Demonstracije
se snimaju iz njega.

**Topli start nije nagrada, i zato ova tabela ostaje netaknuta.** `behavioral_cloning` je pomoćni
gubitak nad politikom, ne signal nagrade: uči politiku da preslika komandu stručnjaka, a ne mijenja
šta se plaća. Zato kumulativna nagrada iz runa feature-a 009 ostaje uporediva sa 007 i 008, što je
tvrdnja koju potkrepljuje diff nad ovom tabelom a ne rečenica. **GAIL bi dodao naučen signal
nagrade**, promijenio ovu tabelu i uništio to poređenje, pa je izvan obima i imenovan kao naredni
feature ako ikad zatreba.

**Dva ograničenja koja demonstracije nose, izmjerena a ne pretpostavljena.** Prvo, snimak nastaje
samo na koracima odluke, a `DecisionPeriod` je 4, pa je demonstracija stručnjak uzorkovan na
**12.5 Hz** dok on sam odlučuje na 50 Hz. Zbog toga se **34 od 34 ne prenosi automatski** i mjeri se
ponovo prije nego što se išta snimi u količini; ako padne, feature staje i to prijavljuje, jer bi
spuštanje `DecisionPeriod`-a promijenilo takt na kojem je mjereno cijelo M3. Drugo, ML-Agents upisuje
observaciju zajedno sa komandom **prethodne** odluke, pa `.demo` nosi par `(obs_t, a_{t-1})`, dakle
pomak od 80 ms na `DecisionPeriod: 4`. To je svojstvo alata, ne postupka snimanja, i zapisano je da
se datoteka kasnije ne bi čitala kao `(obs_t, a_t)`.

**Obim M3, odlučeno 2026-08-28.** M3 se zatvara ovim feature-om, bez obzira šta izmjeri. Kurikulum,
prvi od tri lijeka, **ostaje neuzet** i nije naredni feature: četiri od pet milestone-a su odlučena
dok je M5 na nuli, a M5 je ono što se predaje. Ako run feature-a 009 padne blizu praga od 0.035,
`results/rl/progress_spread.md` već propisuje jedini dozvoljeni nastavak, a to je svjež spread od tri
runa umjesto presude.

**Ishod, upisan 2026-09-01 nakon runa feature-a 009 i spreada od tri seeda.** Topli start je prošao,
i prošao je ubjedljivo. `ppo_car_009_bc`, jedna izmjena u odnosu na `ppo_car_007_progress` (blok
`behavioral_cloning` nad demonstracijom iz `HeuristicDriver`-a), dao je **2.6321 markera po epizodi
naspram 1.4987**, prvu pozitivnu kumulativnu nagradu u projektu (**+0.0887** na zadnjih deset
sažetaka naspram -1.2612 kod 007 i -6.6515 kod 008), i **10 od 10 krugova na deset izdvojenih
seedova**. Spread od tri seeda (42, 7, 13), sa `--seed` kao jedinom razlikom, daje **10/10
determinističkih na sva tri**, uz **nula dodira zida u trideset determinističkih vožnji**.

**Ova tabela u feature-u 009 nije mijenjana, i to je ono što poređenje sa 007 i 008 čini validnim.**
`git diff be2f9c4..HEAD -- unity/SelfDrivingSim/Assets/Scripts/` ne sadrži nijednu liniju koja nosi
nagradu. Tvrdnja je potkrijepljena diffom, ne rečenicom.

**Četiri feature-a M3, jedna tabela, i šta je svaki od njih eliminisao.**

| feature | šta je mijenjao | ishod | šta je eliminisano |
|---|---|---|---|
| 006 | kaznu za zid, -5.0 na -1.0 (`ppo_car_wall_lo`) | -0.3185, dakle lošije | **težina kazne nije vezujuće ograničenje** |
| 007 | dodao gusti član napretka | 0 na 1.4987 markera, ali 0 od 10 krugova | rijetkost nagrade nije jedini uzrok |
| 008 | terminal na zidu, budžet 3 | 0.5297 markera, povratak zaglavljivanju | **terminal nije ograničenje nego je bio noseći** |
| 009 | topli start iz demonstracija | 2.6321 markera, 10 od 10 krugova | ograničenje je bilo **istraživanje prostora** |

**Dva od ta četiri su oslobodila upravo ono što su mijenjala, i to je rezultat o tabeli rewarda a ne
niz neuspjeha.** Feature 006 je oslobodio težinu kazne, feature 008 terminal; oba su dijelovi istog
reda za zid i oba su izmjerena umjesto pretpostavljena. Feature 007 je pokazao da mehanizam gustog
signala radi dok milestone i dalje ne prolazi. Tek je 009 pomjerio milestone, i pomjerio ga je **ne
dirajući nijednu težinu**. Zajedno ta četiri reda nose jedan zaključak: **tabela rewarda iz ovog
poglavlja nikad nije bila vezujuće ograničenje M3. Ograničenje je bilo istraživanje prostora, a
demonstracija ga je uklonila.**

**Jedno ograničenje tog zaključka, rečeno ovdje jer se inače ne vidi iz brojeva.** Ispravka `IsSelf`
filtera (commit `3017764`) je između feature-a 008 i 009 vratila agentu poglede na vlastitu stazu,
pa 006, 007 i 008 **nisu mjereni istim senzorima** kao 009. Sonda `ppo_car_009_sighted_probe`, ista
konfiguracija kao 007 sa ispravnim senzorima i bez toplog starta, bila je na 1.000.000 koraka
**lošija** od slijepog feature-a 008, što govori da ispravka senzora sama ne objašnjava pomak. Ta
sonda nije vožena do 5.000.000 koraka, pa je razdvajanje uzroka na reward, istraživanje i senzore
**djelimično a ne potpuno**, i tako je i zapisano.

### 4.6 Kraj epizode
- Sudar sa zidom **kad se potroši budžet kontakata** (feature 008), ili
- 60 s bez novog checkpointa (zaglavljen), ili
- 3 kompletirana kruga (uspjeh), ili
- tvrda granica koraka.

**Ispravka, upisana pri planiranju feature-a 008 (2026-08-26).** Prethodna verzija ovog pasusa je
tvrdila da uz pravilo zaglavljivanja stoji i tvrda granica `MaxStep = 6000` koraka. **Ta granica ne
postoji.** `TrainingArea.prefab` postavlja `MaxStep: 0`, a grana u `CheckTermination` je čuvana sa
`MaxStep > 0`, pa se nikad ne pali. Zato `episode/end_steplimit` čita nulu u svakom runu M3, i to
nije zato što epizode nikad nisu bile dovoljno duge nego zato što granice nema. Broj 6000 je bio
namjera koja nije prenesena u prefab.

**Zašto je to sad važno, a do sad nije bilo.** Dok sudar završava epizodu na prvi kontakt, epizode
su ograničene odozgo time što vozilo prije ili kasnije udari. Feature 008 podiže taj terminal, a
`_stepsSinceAward` se resetuje na **svakom** osvojenom markeru, pa politika koja se vuče uz ogradu i
pokupi marker bar jednom u 60 s **nikad ne završi epizodu**. Dužina epizode postaje neograničena, i
to je istovremeno problem za trening, jer bafer puni jedna ogromna epizoda, i za zidni sat.

**Pravilo: tvrda granica koraka mora postojati prije nego se terminal podigne.** Postavljena je na
**`MaxStep: 6000`** u `TrainingArea.prefab` (feature 008, T004a), dakle 120 s na 50 Hz, što je
vrijednost koju je ovaj dokument i ranije tvrdio a prefab je nikad nije nosio. Izbor: heuristički
vozač vozi krug za 26.5 s u prosjeku (§4.7.2), pa su tri kruga oko 80 s, a 120 s ostavlja pola toga
kao rezervu za politiku koja je sporija od heuristike. Prosječna epizoda feature-a 007 je bila oko
1.676 koraka fizike, pa granica stoji oko tri i po puta iznad nje i ne bi trebalo da se pali često;
`episode/end_steplimit` sad ima priliku da bude različit od nule, i ako nije, to se kaže.

**Izmjereno (feature 008, 2026-08-27): granica se pali, i nije kozmetička.** `MaxStep = 6000` je
prekinuo **608 epizoda, 6.9 posto** od njih 8.843 u runu `ppo_car_008_budget`, tamo gdje je
`episode/end_steplimit` čitao tačno nulu u svakom runu M3. Bez nje bi te epizode tekle neograničeno,
jer se `_stepsSinceAward` resetuje na svakom markeru pa spora politika koja pokupi jedan marker u 60
s nikad ne aktivira ni pravilo zaglavljivanja. Epizode su narasle sa 485.4 na **612.0** koraka
odluke, pa je u isti budžet od 5.000.000 koraka stalo 8.843 epizode umjesto 13.851, a to je manje
raznolikog iskustva za istu cijenu i dio razloga zašto je taj run naučio manje.

**Budžet kontakata, podrazumijevano 0 (feature 008).** Vrijednost 0 znači da prvi kontakt završava
epizodu, kao u feature-u 007 i cijelom M3. Isprobana je vrijednost 3 i **nije zadržana**; mjerenja i
razlog su u §4.5.

**Ispravka ranijeg čitanja: odnos koraka fizike prema odlukama nije ograničen na 4.** Feature 007 je
izmjerio 3.2161 sa maksimumom 4.0063 i pročitao plafon od 4 kao potvrđen. Ovaj run čita **4.0870**
kao srednju vrijednost i 5.0224 na jednom sažetku, pa 4 nije plafon. Račun preko neslaganja skupova
epizoda predviđa 3.7993 naspram izmjerenih 4.0870, pa ni on više ne objašnjava cijeli razmak.
Granica koraka je četvrti način da se epizoda završi i najvjerovatniji je osumnjičeni; to je
**hipoteza i tako je zapisana**, a za rješavanje traži zapise po epizodi koje je feature 007 već
imenovao kao zaseban posao.

**Razlika između kraja i presjecanja nije kozmetička.** Sudar i tri kruga su terminalni; obje
vremenske granice su presjecanje. Trener drugačije procjenjuje vrijednost presječene epizode, pa bi
završavanje vremenski ograničene epizode kao da je vozilo udarilo u zid naučilo politiku da je
preživjeti 120 s kažnjeno. Zato se razlozi bilježe odvojeno: `WallContact`, `LapsCompleted`,
`Stalled` i `StepLimit`.

### 4.7 Heuristički vozač (feature 005, referentna vrijednost bez učenja)

Skriptovani vozač koji čita **isti vektor observacija** koji čita i agent koji uči, i piše u
`CarController.ScriptedMove`. Nema modela, nema treninga, nema novog senzora.

**Zašto postoji.** Dvije tvrdnje koje ovaj projekat iznosi na odbrani trenutno nemaju šta iza sebe.

Prva je da je RL agent nešto naučio. Kriva nagrade koja raste kaže da se agent popravio u odnosu na
vlastitu nagradu, ne da je rezultat dobar. Bez reference koja ne uči, rečenica "PPO završava
krugove" se ne razlikuje od rečenice "ova staza je dovoljno laka da je svako završi".

Druga je da je geometrija senzora dobra. Trinaest zraka preko 180 stepeni izabrano je prije nego je
išta vozilo. T059 mjeri da u koridoru od 6 m sedam od trinaest zraka javlja praktično isto bočno
rastojanje od 3 m, dok prednji konus, koji nosi svaku odluku u krivini, drži tri zrake. Niko nije
provjerio da li to smeta. Skriptovani vozač daje cilj koji se mjeri u sekundama po konfiguraciji,
gdje bi isto pitanje kroz PPO trening koštalo sate.

**Dva regulatora, oba se zadržavaju.** Prvi bira zraku sa najvećim rastojanjem i skreće prema njenom
uglu. Drugi računa prosjek uglova zraka otežan njihovom otvorenošću.

Redoslijed nije slučajan: naivni se pravi prvi, mjeri se kako se ponaša, i tek onda se zamjenjuje.
Pravilo ovog projekta je da se odluka o dizajnu **mjeri, a ne tvrdi**.

Predviđanje zapisano prije mjerenja: zrake su na 15 stepeni, a upravljanje se zasićuje na 25, pa
naivni regulator može zatražiti samo tri različite veličine skretanja, **0, 0.6 i 1.0**. Sve između
je nedostižno, pa ne može držati liniju kroz krivinu nego mora da alternira. Uz ograničenje brzine
upravljanja od 3.7 po sekundi, jedan korak traje oko 162 ms, što oscilaciju stavlja blizu 3 Hz.

Ako se predviđanje pokaže netačnim, to je nalaz i tako se zapisuje. Feature 003 je već imao jedno
oboreno predviđanje (C17) i obaranje je vrijedilo više od predviđanja.

**Uzdužna kontrola nije dodatak nego uslov.** Granica prianjanja daje brzinu u krivini
`sqrt(a_lat * r)`. Sa `a_lat = 5.85 m/s^2`, na najmanjem poluprečniku koji generator pravi (6.97 m)
auto može držati 6.39 m/s, a maksimalna brzina je 10 m/s. **Prelomna tačka je 17.1 m**: ispod tog
poluprečnika puni gas traži više bočnog ubrzanja nego što gume mogu dati. C9 već kaže da ove staze
zakrivljuju svuda, pa vozač sa punim gasom izlazi u zaštitnu ogradu na većini krivina.

Zato vozač izvodi ciljnu brzinu iz vlastite komande upravljanja: implicirani poluprečnik je
`wheelbase / tan(delta * steer_max_rad)`, a ciljna brzina `sqrt(a_lat * R)` ograničena na `v_max`.
Sve konstante dolaze iz `vehicle_profile.json`, nijedna nije ukucana, pa preštimavanje auta
preštimava i vozača.

**Granica prema agentu koji uči (FR-001).** Vozač smije čitati samo ono što bi čitao i agent: zrake
i vlastitu brzinu. Ne čita fajl staze, ne čita pozicije checkpointa. Baseline koji vidi više od
onoga čemu je baseline ne mjeri ništa. Zato živi u `Assets/Scripts/Agent/`, uz vektor observacija, a
ne uz `Track/`.

**Jedan izvor za geometriju senzora.** `RAY_COUNT`, `RAY_FOV_DEG` i `RAY_LENGTH_M` danas stoje na
dva mjesta, u `python/track/config.py` i kao serijalizovana polja na `CarAgent`, i ništa ne provjerava
da se slažu. Ovaj feature ih mora mijenjati kroz sweep, što bi razilaženje samo pogoršalo, pa se
sele u `sensing` blok u `vehicle_profile.json` koji `CarAgent` učitava isto kao što `CarController`
učitava profil. **Nijedna vrijednost se ne mijenja**, mijenja se samo odakle se čita.

**Šta ovaj vozač nije.** Nije zamjena za ljudski krug tastaturom iz feature 003: skriptovani krug
dokazuje da je staza prohodna, a to je druga tvrdnja od one da je vozilo vozivo za čovjeka. Ne
optimizuje se na vrijeme kruga, jer štimovana heuristika prestaje biti baseline i postaje takmac, pa
bi poređenje u M5 bilo između dva štimovana sistema.

**Zašto heuristika uopšte zaslužuje mjesto pored mreže.** Ne zato što je bolja, nego zato što
odgovara na pitanje koje mreža ne postavlja: koliko problema se riješi bez učenja. Argument nije
akademski. Neuronska mreža na ugradbenom sistemu je luksuz: traži memoriju, računski budžet i
determinističko vrijeme izvršavanja koje mikrokontroler često nema. Algoritam koji radi na trinaest
brojeva i par korijena staje svuda i ponaša se isto svaki put.

Zato se **obje heuristike zadržavaju iako nijedna nije savršena**, i zato se njihovi neuspjesi
zapisuju jednako pažljivo kao i uspjesi. Poređenje u M5 nije "mreža protiv slabijeg protivnika",
nego "koliko dodatnog ponašanja se plaća treningom".

**Predviđanje je oboreno, i to na dva različita instrumenta.** Oscilacija od 3 Hz na amplitudi 0.6
nije se pojavila ni jednom. `MostOpen` ne alternira nego se **opredijeli za jedan pogrešan smjer i
drži ga**: 0.0000 promjena znaka po sekundi, a `|dsteer|` P95 mu je tačno **0.6000**, jedan korak
zrake, dakle kvantizacija se pojavila kao doslovni kvant a ne kao titranje. `WeightedAverage` daje
4 promjene znaka u cijelom krugu (**0.15/s**). Ono što je predviđanje pogodilo je uzrok
(kvantizacija komande), a ne posljedica (oblik greške). Zapisano kao nalaz, kako §4.7 i traži.

### 4.7.1 Mjereni rezultati (seed 1, trening seed)

| Regulator | Uzdužna kontrola | Ishod |
|---|---|---|
| `MostOpen` | samo iz komande upravljanja | sudar sa ogradom, zaglavi se |
| `MostOpen` + kapija na kritičnoj udaljenosti | isto | sudar, na svim pragovima 0.20-0.50 |
| `MostOpen` | + ograničenje brzine na vidljivost | sudar u 6.0 s |
| **`WeightedAverage`** | **+ ograničenje brzine na vidljivost** | **krug završen, 27.6 s i 27.5 s** |

**Zašto argmax pada, izmjereno u trenutku sudara:** zraka 06 pravo naprijed javlja 20 m, zraka 07 na
+15 stepeni javlja 2.78 m, a desni bok je na 1.46 m. Argmax bira najdužu zraku, komanduje pravo, i
struže ogradu uz koju već vozi. **Regulator je slijep na svaki zid u koji ne gleda.**

Prosjek otežan otvorenošću to rješava po konstrukciji: svaka zraka glasa, pa blizak zid zdesna
povlači srednju vrijednost ulijevo. **I ne treba mu nijedan naštimovan parametar**, dok je kapija
bila zakrpa sa pragom koji se morao pogađati i koji se nije prenio sa jedne staze na drugu.

Zapisano i ovo: prvi rezultati ovog feature-a mjereni su na seedu 1004, koji je **evaluacijski**
seed, i to je prekršilo pravilo iz research R5. Ti brojevi su ilustrativni, ne dokazni. Tabela iznad
je sa trening seeda.

### 4.7.2 Mjereni rezultati (svih 34 trening seeda)

Tabela iz §4.7.1 je jedan seed. Staze se po težini razlikuju po konstrukciji, pa je jedan seed
uzorak veličine jedan (Princip IX). Sweep preko cijelog trening skupa, 13 zraka preko 180 stepeni,
timeScale 2:

| Mjera | `MostOpen` | `WeightedAverage` |
|---|---|---|
| Završenih krugova | **0 od 34** | **34 od 34** |
| Vrijeme kruga | nema | 26.496 s prosjek, sd 0.578 |
| Dodiri zida | 34 (po jedan po runu) | 0 |
| \|dsteer\| P95 | 0.5824 prosjek | 0.0496 prosjek |
| Promjene znaka /s | 0.0080 | 0.2370 |

**Naivni regulator ne gubi poređenje, nego ga nikad ne završi.** Nijedan krug ni na jednoj od tri
probane geometrije (0 od 102), i to je jači rezultat od očekivanog gubitka.

Prag šuma iz pet ponovljenih runova istog seeda: **0.16 s** po vremenu kruga, **0.0063** po
`|dsteer|` P95. Sve razlike u tabeli su iznad njega. Za promjene znaka prag nije izmjereni raspon
nego **0.0366/s**, jedna promjena po dužini kruga, jer mjera ne može skočiti za manje od jedne.

**Geometrija senzora je izmjerena, i ništa ne dominira.** Četiri rasporeda, sva četiri završe 34 od
34: 13/180 je najglađi i najsporiji, 13/90 najbrži i najgrublji. Trgovina je stvarna, pa se
**13 preko 180 zadržava kao mjerena odluka**, ne kao zatečena. Vrijeme kruga nije mjera po kojoj
ovaj feature bira (§4.7: heuristika se ne optimizuje na vrijeme kruga).

Cijena mjerenja: jedna konfiguracija traje 6.3-7.6 minuta, a budžet je bio pet. **Promašaj je
zapisan, ne zaobiđen** - potreban bi bio 3.1x, a 2x je najbrže na čemu se brojevi reprodukuju.
Uzrok je strukturni: `CarController` integriše ograničenje brzine upravljanja u `Update`, dakle po
frame clocku. Popravka je izmjena vozila, što je van opsega ovog feature-a.

---

## 5. RL trening (PPO)

- `mlagents-learn config/ppo_car.yaml --run-id=ppo_car_vXX`
- Početni hiperparametri: batch 2048, buffer 20480, lr 3e-4 (linear decay),
  hidden 256×2, gamma 0.99.
- 8–16 paralelnih kopija staze u sceni (Training Area pattern) - brži trening.
- Praćenje: TensorBoard (cumulative reward, episode length, policy loss).
- Kriterij uspjeha: agent stabilno završava 3 kruga bez sudara u 95%+ epizoda.
- Izlaz: `.onnx` model → nazad u Unity za inference demo.

**Odlučeno za M3 (feature 006, prije koda).**

**`max_steps` se ne piše unaprijed.** Ranija verzija ove sekcije je pisala 2-5M, a taj raspon je
star koliko i sekcija: napisan prije nego što je išta u ovom okruženju izmjereno. Jedini broj koji
projekat ima je 700 koraka/s na 3DBall, uz koji `ENVIRONMENT.md` izričito piše da je gornja granica,
jer naše okruženje ima WheelCollider fiziku i 13 raycastova po koraku. Zato budžet postavlja **pilot
run** od oko 100k koraka, iz izmjerene propusnosti i granice od 12 sati. Razlika između 100 i 30
koraka/s je razlika između 4.3M i 1.3M koraka u istoj noći, a to je preširoko da bi se biralo iz
tabele.

**Raspored trening kopija.** Svaka kopija je samostalna: svoj `TrackBuilder`, svoj prsten markera,
svoj `StartPlacer`, svoje vozilo, svoj agent. Kopije stoje na mreži sa korakom **300 m**. Broj nije
proizvoljan: zrake su duge 20 m, a staza ima oko 200 m centralne linije, pa 300 m drži barijere
jedne kopije izvan dosega senzora svake druge. Jeftinije od sloja fizike po kopiji, i vidljivo u
scene view-u, što je bitno kad nešto krene naopako.

**Rotacija seedova.** Epizode se vuku iz svih **34 trening seeda**, a scena za trening 10 eval
seedova ne učitava nikad. Sa 8 do 16 kopija nijedan raspored ne pokriva 34 seeda bez rotacije, pa
svaka kopija mijenja stazu svakih K epizoda. **Ne unutar `OnEpisodeBegin`**: taj callback je sinhron,
a rušenje i gradnja staze traju najmanje tri frame-a, jer stari collideri nestaju u jednom, a novi
se registruju tek u sljedećem fizičkom koraku. Zamjena ide između epizoda, sa isključenim agentom te
kopije.

**Prag šuma prije svakog poređenja.** Isti postupak koji su feature 004 (R13) i 005 (T027) već
koristili, ali sa cijenom koju PPO nosi: tri identična runa punog budžeta su tri noći. Zato se prag
mjeri na **smanjenom budžetu**, iz tri runa koja se razlikuju samo po `--seed`, i **sva poređenja
konfiguracija se rade na tom istom budžetu**. Puni budžet dobija samo konfiguracija koja je tu
pobijedila. Ograničenje se piše, ne prešućuje: politika koja još uči je bučnija od konvergirane, pa
je prag sa smanjenog budžeta vjerovatno precijenjen, a to je sigurna strana za pitanje je li razlika
iznad šuma.

**Krive kao podaci.** `results/tensorboard/` i `events.out.tfevents.*` ostaju van gita, jer su
binarni i rastu sa runom. Commituje se **destilovani CSV po runu** u `results/rl/curves/`, bez
zaglađivanja i bez presempliranja, sa šest serija po članu rewarda uz standardne. Broj koji se
citira mora biti provjerljiv iz repozitorija, a slika sa nečijeg ekrana to nije.

**Izvezeni model nije politika koja je trenirala.** PPO tokom treninga uzorkuje iz raspodjele, a
`BehaviorParameters` nosi zastavicu za determinističku inferencu, pa iste težine daju dva različita
vozača. Evaluacija za M5 se radi **deterministički**, jer su i heuristika i BC deterministični, a
razlika između dva načina se mjeri i zapisuje umjesto da se pretpostavi.

**Imitacija kao ulaz trenera, ne kao član nagrade (feature 009, odlučeno prije koda, 2026-08-28).**
`config/ppo_car.yaml` dobija blok `behavioral_cloning` i ništa više. Blok nosi `demo_path` do
snimljene datoteke, `strength: 0.5`, `steps: 500000` i `samples_per_update: 2048`; `num_epoch` i
`batch_size` se nasljeđuju od trenera, i to je odluka a ne propust. Tabela nagrade iz §4.5 se ne
dira, budžet kontakata ostaje 0 i `MaxStep` ostaje 6000, pa je poređenje feature-ov 007 terminal sa
feature-ovom 008 granicom koraka.

**`steps` je ono što ovo čini toplim startom, a ne imitacionim runom.** Raspored gubitka je linearan
samo ako je `steps` iznad nule; na podrazumijevanoj nuli je konstantan, pa bi se imitacioni gubitak
primjenjivao punom snagom kroz svih 5.000.000 koraka i run bi mjerio imitaciju umjesto potkrepljenja.
Vrijednost 500.000 je desetina budžeta: gubitak se ugasi kroz prvu desetinu, a preostalih devet
desetina su čist PPO nad nepromijenjenom tabelom. `samples_per_update` se postavlja iz istog razloga
u drugom smjeru: na podrazumijevanoj nuli svaki update prolazi cijeli bafer demonstracija, što se
vidi na propusnosti runa, a 2048 poklapa `batch_size` trenera pa jedan update košta jedan batch.

**Jeftina provjera da je topli start uopšte primijenjen.** Trener piše `Losses/Pretraining Loss` u
TensorBoard. Ako te serije nema ili stoji na nuli, demonstracija se nije učitala i run mjeri feature
007 pod drugim imenom. Gleda se u prvih nekoliko sumarija, ne na kraju.

**Heuristički režim agenta sad delegira, i to ne pravi drugu implementaciju baseline-a.**
`DrivingAgent.Heuristic` je do feature-a 009 vraćao nule, a komentar iznad njega je izričito odbijao
da se skriptirani vozač prepiše u taj callback, jer bi projekat time dobio dva baseline-a i poređenje
u M5 ne bi imalo jedan odgovor. **Ta zamjerka ostaje zadovoljena: callback zove
`HeuristicDriver.Decide()` umjesto da ga kopira**, pa implementacija upravljačkog zakona i dalje
postoji tačno na jednom mjestu. Dok je agent izvor odluke, `HeuristicDriver` je iskopčan i ne piše u
`CarController.ScriptedMove`, čime FR-004 feature-a 005 o jednom izvoru upravljanja ostaje na snazi
umjesto da se ponovo otkriva.

**Demonstracije se snimaju samo sa trening seedova.** Krug na neviđenoj stazi je kriterij koji je
ovaj projekat promašio tri puta; pokazati politici stručne putanje baš na tih deset izdvojenih
seedova bi odgovaralo na drugo pitanje. Lista seedova se commituje uz `.demo`, a datoteka ide kroz
LFS, da bi run bio ponovljiv iz čistog klona a ne iz postupka koji neko mora ponovo odraditi.


### 5.1 Izmjereno (M3, feature 006, upisano nakon runova)

Sve gore je bilo **odlučeno prije koda**. Ovdje su brojevi koji su na kraju izmjereni, uključujući
i one koji obaraju kriterij iz gornje liste.

**Propusnost.** Izmjereno **660 koraka/s** na `ppo_car_smoke` (500k u 814.9 s) i **632 do 794
koraka/s** kroz pet runova od 2M. Gornja granica od 700 koraka/s koju je `ENVIRONMENT.md` upisao
kao optimističnu za 3DBall se pokazala tačnom i za ovo okruženje, uprkos WheelCollider fizici i 13
raycastova. Run od 5M staje u **2.0 sata**, run od 2M u **42 do 52 minute**, dakle SC-006 (ispod 12
sati) je zadovoljen sa velikom rezervom.

**Šum između runova.** Tri identična runa na seedovima 1, 2 i 3 daju srednje vrijednosti -4.5070,
-4.6613 i -4.6722, dakle **uzoračka sd 0.0924** i prag za poređenje **0.19**. Za
`reward/checkpoint` sd je 0.0315 i prag 0.0631. Nalaz koji vrijedi pamtiti: **rasap između runova
je pet puta manji od rasapa unutar runa** (0.0924 naspram ~0.51), pa je srednja vrijednost runa
stabilna dok pojedinačni sažetak nije.

**Kriterij iz gornje liste nije ispunjen, i to je rezultat.** "Agent stabilno završava 3 kruga bez
sudara u 95%+ epizoda" je izmjereno kao **0.0 posto**. Nijedna evaluaciona epizoda nije prošla
nijedan od 24 markera, ni u determinističkoj ni u uzorkujućoj inferenci, ni na jednom od 10
izdvojenih seedova; sve su završile kao `Stalled` na 60 s. Nijedan run u M3 nije završio krug ni
tokom treninga.

**Zašto, rečeno brojem.** Tri kandidata za tjuniranje, svaki sa po jednom izmijenjenom težinom, nisu
prešli prag u boljem smjeru: `ppo_car_jerk_lo` +0.0553, `ppo_car_wall_lo` -0.3185 (prelazi, ali na
lošiju stranu), `ppo_car_speed_hi` -0.0373. Najjasniji od njih je udvostručio platu za kretanje i
kupio **dvanaest posto veću brzinu**. Ova tabela rewarda se ne može popraviti skaliranjem svojih
težina; problem je istraživanje prostora. Puni zapis je u `results/EXPERIMENTS.md` 4.5.

**Determinizam inference je izmjeren, ne pretpostavljen (FR-026).** Ista težina, dva vozača:
ishodi identični (0 krugova, 0 markera, 0 dodira zida, sve `Stalled`), a upravljanje potpuno
različito - varijansa 0.00055 naspram 0.04557, dakle **faktor 83**, i srednji |delta steer| 0.0005
naspram 0.1452, **faktor 290**. Odluka iz gornjeg pasusa da se evaluacija radi deterministički
ostaje, ali sada sa izmjerenom razlikom umjesto sa pretpostavkom.

**Jedan nalaz koji mijenja kako se čita poređenje u M5.** Uzorkujuća politika ima varijansu
upravljanja **0.04557 naspram 0.04994 skriptiranog vozača**, dakle devet posto razlike, a završava
**0 od 10 krugova naspram 34 od 34**. Varijansa upravljanja sama ne razlikuje vozača koji vozi krug
od vozača koji se ne pomjeri sa starta. Detalji u `results/rl/rl_steering.md`.

### 5.2 Zatvaranje M3 (upisano 2026-09-01, nakon feature-a 009 i spreada)

**Verdikt: M3 je ISPUNJEN.** Oba kriterija koja je feature 006 napisao prije koda su prošla, i to u
obje inferencijske grane. Kriteriji se citiraju u obliku u kojem su napisani, ne prepravljeni da
odgovaraju rezultatu, jer to SC-001 izričito traži.

| kriterij | prag | deterministička | uzorkujuća | ishod |
|---|---|---|---|---|
| SC-001, tri kruga bez dodira zida | 95 posto epizoda | **30/30 = 100.0 posto** | 29/30 = 96.7 posto | **ISPUNJEN** |
| SC-002, bar jedan krug na izdvojenim seedovima | 80 posto seedova | **30/30 = 100.0 posto** | 29/30 = 96.7 posto | **ISPUNJEN** |

Trideset vožnji je deset izdvojenih seedova puta tri trening seeda (42, 7 i 13). `lapsToComplete` je
**3**, pa je svaka upisana vožnja tri kruga, i SC-002 je time mjeren strože nego što traži: tražio je
jedan krug, izmjereno je tri. Jedina izgubljena vožnja u šezdeset evaluacionih vožnji je seed 1009
pod uzorkujućom inferencom na trening seedu 42.

**Put do ovoga je bio tri neuspjeha i jedan pogodak**, i tabela u §4.5 kaže šta je svaki od njih
eliminisao. Sažeto: tabela rewarda nije bila kriva, nego istraživanje prostora.

**Šta ostaje otvoreno, imenovano kao otvoreno a ne kao naredni feature.** M3 je zatvoren odlukom od
2026-08-28 i feature 010 se ne piše.

1. **Sadržaj observacije, klasa politike i vozilo nikad nisu ni testirani.** U ranijim verzijama
   ovog zatvaranja bili su navedeni kao preostali osumnjičeni za neuspjeh. Neuspjeha više nema, pa
   oni nisu osumnjičeni nego jednostavno nepromijenjene varijable. Ako neko kasnije traži bolju
   politiku a ne prolaznu, to su tri ručke koje niko nije dirao.
2. **Generalizacija izvan ovih deset staza nije pokazana.** Isti generator, ista raspodjela, deset
   staza dužine 198.5 do 201.6 m. Rezultat kaže da politika vozi ovu raspodjelu, ne bilo koju.
3. **Razdvajanje senzora od istraživanja je djelimično.** Sonda iz §4.5 je vožena do 1.000.000
   koraka umjesto do 5.000.000. Run od 5M te sonde je jedina mjera koja bi to zatvorila.
4. **Agregati po cijelom runu su rangirali tri seeda pogrešno** u odnosu na rezultat na izdvojenim
   stazama: seed 42 ima najviše završenih krugova u treningu (77) i najslabiji je izvan njega, seed
   13 ima najmanje (34) i među najjačima je. Mjere sa kraja runa rangiraju ispravno. Feature-i 006
   do 008 su argumentovani upravo agregatima po cijelom runu. To ne obara njihove zaključke, jer su
   njihovi neuspjesi bili preveliki da bi rang išta značio, ali svaki budući zaključak treba reći
   koji su mu brojevi sa cijelog runa a koji sa kraja. Uzorak je tri seeda i tako je zapisano.

**Naredni posao je M5**, evaluacija i poređenje RL naspram BC naspram ljudskog dataseta, sa
`results/plots` i provjerenim receptom u README. M5 je na nuli i on je ono što se predaje.

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
- **left/right** slike su augmentacija: koriste se sa korigovanim steeringom kao da je auto
  pomjeren u stranu - efektivno 3× više podataka bez novog snimanja.

> **Ispravka korekcije kamera: konstanta ±0.2 → raspon 0.10-0.30 (feature 004, 2026-08-04).**
>
> Prvobitno je ovdje pisalo `+0.2` za left i `−0.2` za right, preuzeto iz NVIDIA PilotNet
> konvencije. Ta konstanta je **izmjerena** prije nego što je bilo šta trenirano, i nije
> bezopasna.
>
> | Pojas | Samo center kamera | Sve tri kamere, konstanta 0.20 |
> |---|---|---|
> | tačno 0 | 58.6 % | 20.3 % |
> | 0.15 < abs(s) <= 0.20 | 2.4 % | **40.6 %** |
>
> Konstanta ne rješava neuravnoteženost, nego je **premješta**: dvije trećine mase koja je
> bila na nuli sleti na tačno ±0.20. Kako je 0.20 stvarna tačka rešetke (korak 0.05, feature
> 002), ta dva vrha se u histogramu **ne razlikuju** od pravog ljudskog steeringa na 0.20. A
> raspodjela predikcija je upravo ono što M5 poredi.
>
> **Odluka: offset se izvlači po uzorku iz uniformnog raspona 0.10-0.30**, srednja vrijednost
> ostaje tačno 0.20. Raspon je biran mjerenjem:
>
> | Politika | Najpuniji pojas ispod 0.30 | Masa iznad 0.30 |
> |---|---|---|
> | konstanta 0.20 | 40.6 % | 27.4 % |
> | jitter 0.15-0.25 | 21.7 % | 27.5 % |
> | **jitter 0.10-0.30** | **19.5 %** | **27.6 %** |
> | jitter 0.05-0.35 | 19.5 % | 33.9 % |
> | samo center | 58.6 % | 26.1 % |
>
> Druga kolona je ta koja odbacuje opcije. Masa iznad 0.30 je **stvarni** ljudski steering u
> oštrim krivinama. Raspon dovoljno širok da gurne sintetizovane uzorke u tu zonu razblažuje
> prave podatke izmišljenim, što je gora greška od vrha koji je trebalo popraviti; zato je
> 0.05-0.35 odbačen. Na 0.10-0.30 najpuniji pojas od 19.5 % je **sama nula**, dakle
> augmentovana masa je već spljoštena ispod prirodnog vrha i šire širenje ne donosi ništa.
>
> Offset se izvlači **jednom, iz sjemena**, a ne iznova svake epohe. Ponovno izvlačenje bi
> bilo jača augmentacija, ali bi raspodjela ciljeva bila drugi objekat u svakoj epohi, a ovaj
> feature mora moći da prijavi kakva je ta raspodjela bila.
>
> Ostaje **izabrana** vrijednost, ne izvedena: tačna korekcija za bočno pomjerenu kameru
> zavisi od brzine i zakrivljenosti, a dataset ne dokumentuje ni jedno ni drugo. Raspon
> priznaje tu neizvjesnost umjesto da se pravi da je jedan broj rješava.

### 6.2 Trening

- Ulaz: `driving_log.csv` + slike centralne kamere (lijeva/desna kamera sa steering
  korekcijom iz raspona 0.10-0.30 kao augmentacija, vidi §6.1).
- Preprocessing: crop neba/haube, resize 66×200, YUV (PilotNet standard),
  normalizacija; augmentacija: horizontalni flip (+negacija steeringa), random brightness.
- Model: PilotNet (5 conv + 4 FC slojeva, ~250k parametara).
- Loss MSE, Adam, early stopping.
- Evaluacija: MSE/MAE na validaciji, scatter predikcija vs stvarni ugao,
  histogram predikcija vs histogram dataseta.

> **Split: 80/20 slučajno → blokovski holdout sa zaštitnim pojasom (feature 004, 2026-08-04).**
>
> Prvobitno je pisalo samo "Split: 80/20 train/val". Snimak ide na ~14 kadrova u sekundi, pa
> su dva kadra razmaknuta 70 ms **skoro ista slika sa skoro istim steeringom**. Slučajna
> podjela po kadru stavi jedan u trening a susjeda u validaciju, i prijavljena greška onda
> mjeri interpolaciju između susjednih kadrova, a ne generalizaciju. To je najčešći način da
> projekat ovog oblika prijavi lijep broj koji ne znači ništa.
>
> **Holdout po sesijama je prvo probavan i nije dostupan.** `split_sessions` daje tačno **dvije**
> sesije na spojenom fajlu (po jedna po stazi), a najveći prekid igdje u snimcima je **0.5 s**.
> To su dva neprekidna snimka, nema se šta rezati. Holdout po sesiji bi značio trening na
> track1 i validacija na track2, što mjeri prenos između dva profila vožnje, a ne
> generalizaciju unutar jednog.
>
> **Odluka: svaka staza se siječe na 10 uzastopnih blokova, 2 ravnomjerno raspoređena bloka
> idu u validaciju, i svaki kadar unutar 8 s od granice se odbacuje sa OBJE strane.**
>
> Zaštitni pojas od 8 s je **izveden iz autokorelacije steeringa**, ne izabran: to je najkraći
> pomak na kojem obje staze padnu ispod 0.1 (track1 +0.085, track2 +0.011). Odbacuje se sa obje
> strane jer je susjedstvo simetrično; čuvanje samo validacione strane ostavlja trening kadrove
> priljubljene uz granicu.
>
> | Guard | Blokova | Izdvojeno | Trening | Val | Odbačeno | Odbačeno % | Val % |
> |---|---|---|---|---|---|---|---|
> | 8 s | 10 | 2 | 25.957 | 5.576 | 910 | 2.8 | 17.68 |
>
> **Dostignutih 17.7 % se prijavljuje, ne ispravlja.** Blokovi su cjelobrojni a pojas ih grize,
> pa to je ono što pravilo proizvede. Pomjeranje granice da se pogodi 20 % bilo bi
> podešavanje podjele prema broju umjesto prema podacima.
>
> Provjera je mašinska: `min_train_val_gap_s` mora biti najmanje 8.0. Izmjereno
> 2026-08-04: **8.09 s**.

> **Crop: "nebo/hauba" → izmjereni redovi 60 i 137 (feature 004, 2026-08-05).**
>
> Prvobitno je pisalo samo "crop neba/haube", bez brojeva. Udacity konvencija je 60 redova
> odozgo i 25 odozdo na kadru 320x160, ali je pisana za drugi snimak, pa je to hipoteza a ne
> odgovor.
>
> **Donja granica (hauba) je izmjerena i ispala je 137, ne 135.** Očekivani test je vremenski:
> hauba je isti oblik u svakom kadru, pa bi trebala imati standardnu devijaciju blizu nule kroz
> kadrove. Nad 800 kadrova cijelog snimka taj test **ne nađe nijedan statičan piksel** (minimum
> 8.82), iz dva razloga koja oba vrijedi zapisati: hauba je reflektivna, a track2 je osvijetljen
> bitno drugačije od track1, pa spajanje staza ubaci veliku varijansu u svaki piksel. Mjereno po
> jednoj stazi i po centralnim kolonama, vrijednost pada sa oko 36 na oko 20 tačno između reda
> 136 i 138, **nezavisno na obje staze**, dok rubne kolone nastave ravno.
>
> **Gornja granica nema fizički orijentir**, pa je kriterij koji redovi uopšte nose signal:
> korelacija horizontalnog težišta intenziteta svakog reda sa steeringom, nad 1.500 kadrova.
> Signal pređe 0.2 na redu 66, vrhunac je 0.33 oko reda 80, i vrati se ispod 0.2 do reda 96.
>
> | CROP_TOP | Redova ostaje | Srednja korelacija po redu |
> |---|---|---|
> | 50 | 87 | 0.156 |
> | 60 | 77 | **0.159** |
> | 70 | 67 | 0.154 |
>
> Kriva je ravna, i **to je nalaz**: ovaj izbor ne mijenja mnogo. Uzeto je 60 jer daje najveću
> srednju vrijednost i jer tu nebo padne na 1 % reda. Ravna kriva istovremeno isključuje tvrdnju
> da je crop podešavan prema tačnosti; run koji se popravi nakon pomjeranja ove linije za pet
> redova prijavljuje šum.
>
> **Odluka: `CROP_TOP = 60`, `CROP_BOTTOM = 137`, puna širina.** Širina se ne siječe namjerno:
> na oštrim krivinama put izlazi iz kadra bočno, a to je tačno mjesto gdje je steering signal
> najveći.

> **Balansiranje: jedna odluka → dva trening runa (feature 004, 2026-08-04).**
>
> Prvobitno je pisalo "downsampling uzoraka sa steering ≈ 0" kao jedna odluka. Problem je što
> downsampling pravi bolji prediktor, a **namjerno pomjera raspodjelu predikcija dalje od
> ljudske** - a upravo tu raspodjelu M5 poredi. Učiti bolje i porediti pošteno vuku na
> suprotne strane.
>
> **Odluka: treniraju se dva runa koja se razlikuju u tačno jednoj stvari, politici
> balansiranja.** Sve ostalo (sjeme, split, arhitektura, preprocessing, augmentacija,
> hiperparametri) je identično, inače razlika između njih mjeri više od balansiranja. Oba se
> ocjenjuju na **istom, nebalansiranom** validacionom skupu: balansiranje je svojstvo trening
> uzorka, a primjena na validaciju bi pomjerila mjerilo zajedno sa modelom.
>
> Razlika između ta dva runa **jeste** cijena balansiranja, izražena u brojevima umjesto
> tvrdnjom. Prijavljuje se na obje ose (tačnost i udaljenost od ljudske raspodjele) i **ne**
> svodi se na jednog pobjednika: run koji dobije na jednoj a izgubi na drugoj osi je očekivani
> ishod i on je nalaz.
>
> **Ispravka udjela zadržanih nula: 0.30 → 0.27 (2026-08-05).** Pravilo je bilo "smanjuj vrh na
> nuli dok ne bude veći od sljedeće najčešće vrijednosti na rešetki". Prebrojano na trening
> podjeli, 0.30 **krši to pravilo**: ostavlja nule na 7.75 % naspram 7.28 % za `-0.25`.
>
> Uzrok nije skup redova nego to što su **dvije strane poređenja brojane različito**: udio nula
> sirovo, a takmac na rešetki od 0.05. Cilj bočne kamere od 0.017 nije tačna nula pa nikad nije
> ušao u brojač nula, ali pada u kanticu +0.00 na rešetki. Vrh je time poređen sa brojem
> računatim drugačije i djelovao je manji nego što jeste. Rešetka je ispravna osnova jer se tu i
> poredi u M5; na sirovim vrijednostima takmac je -1.00 sa 3.41 %, a to mjeri odsijecanje
> ofseta, ne vožnju.
>
> | Keep | Uzoraka | Udio nula | Takmac | Pravilo važi |
> |---|---|---|---|---|
> | 0.25 | 66.479 | 6.70 % | 7.37 % | da |
> | **0.27** | **66.783** | **7.12 %** | **7.33 %** | **da** |
> | 0.30 | 67.239 | 7.75 % | 7.28 % | ne |
>
> **Izmjerene vrijednosti (poslije jitter augmentacije iz §6.1):**
>
> | Vrijednost | Udio trening uzoraka |
> |---|---|
> | tačno 0.00 | **20.38 %** |
> | −0.25 | 6.17 % |
> | −0.20 | 6.16 % |
> | ±0.15 | ~5.98 % |
>
> - `ZERO_STEERING_BAND = 0.0`, dakle **samo tačne nule**. Susjedni nivoi rešetke (±0.05,
>   ±0.10) nose po 2.6-3.8 % i to su stvarne ljudske odluke; širenje pojasa bi bacalo prave
>   uzorke da bi se popravio vrh koji je cijeli na tačnoj nuli.
> - `BALANCE_KEEP_FRACTION = 0.27`, izvedeno iz pravila: **spusti vrh na nuli dok ne bude veći
>   od sljedeće najčešće vrijednosti rešetke.** Zadržavanje 0.27 daje 7.12 % naspram 7.33 %
>   koliko nosi −0.25. Uzorak padne sa 77.871 na 66.783.
>   (Ovaj red je 2026-08-08 usklađen sa ispravkom iznad. Ranije je nosio 0.30 i brojke
>   97.329 → 84.031, koje su bile procjena po slikama prije nego što je split postojao;
>   ispravka 0.30 → 0.27 je bila upisana samo u blok iznad, pa je čitalac koji dođe pravo na
>   ovaj red čitao odbačenu vrijednost.)
>
> Napomena koja se lako previdi: poslije augmentacije sa tri kamere tačne nule su već pale sa
> 58.6 % (po redovima) na 19.5 % (po uzorcima). Balansiranje je zato **manje presudno** nego
> što sirova brojka od 58.6 % sugeriše, i poređenje dva runa treba čitati sa artefaktom
> offseta iz §6.1 u vidu.

> **Kvantizacija na ljudsku rešetku pripada poređenju, ne modelu (feature 004).**
>
> Model emituje kontinualne vrijednosti; ljudska kolona je rešetkasta (41 nivo, korak 0.05).
> M4 čuva **sirove kontinualne predikcije** i uz njih zapisuje činjenicu o rešetki. Tretman
> zajedničke rešetke (`round(s / 0.05) * 0.05`, ograničeno na [−1, 1]) primjenjuje se tamo
> gdje se raspodjele porede, dakle u M5, gdje ga §7 već i smješta. Kvantizacija na izlazu
> modela bi nepovratno bacila informaciju koju kasnije poređenje možda traži.

> **Izmjereni rezultati M4 (feature 004, 2026-08-08).**
>
> Sve iznad su **odluke**, upisane prije koda. Ovaj blok je ono što je moralo biti **izmjereno**,
> i piše se poslije runova (Princip V).
>
> **Dva runa, oba na istom nebalansiranom validacionom skupu od 5.576 uzoraka:**
>
> | | Nebalansiran | Balansiran |
> |---|---|---|
> | Run | `bc_unbalanced_v01` | `bc_balanced_v01` |
> | Trening uzoraka | 77.871 | 66.783 |
> | Validaciona MSE | **0.086670** | **0.090899** |
> | Osnovica (prediktor srednje vrijednosti) | 0.153623 | 0.153992 |
> | Pobijedio osnovicu | da | da |
> | Najbolja epoha | 8 | 8 |
> | Epoha ukupno / trajanje | 13 / 337 s | 13 / 291 s |
>
> Osnovica nije formalnost: vožnja je pretežno pravo, pa je predviđanje srednje vrijednosti jaka
> strategija, i run koji joj izgubi bio bi nalaz koji se prijavljuje, ne neuspjeh (SC-003).
>
> **Dostignuta podjela:** 25.957 trening redova, 5.576 validacionih, 910 odbačenih u pojasu,
> dakle **17.68 %** validacije. Izmjeren najmanji razmak trening-validacija **8.09 s** naspram
> pojasa od 8.0 s.
>
> **Cijena balansiranja, na obje ose:**
>
> | Osa | Razlika (balansiran − nebalansiran) | Čitanje |
> |---|---|---|
> | Tačnost | +0.004229 | nebalansiran bliže ljudskim ciljevima |
> | Raspodjela (KL na rešetki) | +0.063091 | nebalansiran bliže ljudskoj raspodjeli |
>
> **Predviđena razmjena se nije pojavila.** §6.2 je očekivao da balansiranje kupi bližu
> raspodjelu po cijenu tačnosti; izgubilo je na **obje** ose. Razlog je mjerljiv: nijedan model
> ne reprodukuje ljudski vrh na nuli (ljudska validaciona kolona je 57.2 % tačnih nula, oba
> modela su ispod 5 %), pa je udaljenost od ljudske raspodjele dominirana tim jazom, a
> balansiranje pomjera model **dalje** od nule. Raspodjelu je pomjerila augmentacija sa tri
> kamere, ne politika balansiranja: ona je oborila nule sa 57 % redova na 20.35 % uzoraka prije
> nego što je balansiranje išta dotaklo. Detaljno u `results/bc/comparison.md` i research R12.
>
> Drugi nalaz sa iste slike, koji nijedna planirana figura nije tražila: **nijedan model ne
> predviđa preko oko ±0.7**, dok čovjek koristi pun raspon i drži 7.4 % validacione mase na
> tačno ±1.00. Sabijanje raspona je druga distribuciona greška, uz nedostajući vrh na nuli.
>
> **Tolerancija reprodukcije: 0.0005 apsolutno na prijavljenoj validacionoj MSE.** Izmjerena, ne
> izabrana unaprijed (research R13). Tri runa istog sjemena daju 0.086670 / 0.086685 / 0.086411,
> dakle raspon **0.000273** i standardnu devijaciju 0.000154; tolerancija je postavljena iznad
> raspona jer tri runa ograničavaju rasipanje, ne procjenjuju ga. Sve prije GPU-a se reprodukuje
> bit po bit: osnovica je 0.153622828786396 u sva tri runa do zadnje cifre, pa su split, gradnja
> uzoraka, ofseti kamera i balansiranje deterministični, a rasipanje je isključivo u treningu.
>
> Posljedica koja se tiče čitanja gornjih tabela: razlika u tačnosti od 0.004229 je **15 puta**
> veća od izmjerenog raspona, pa poređenje dva runa preživljava šum. Šesta decimala u tabelama
> je ispod praga šuma i ne treba je citirati.
>
> **Dvije stvari koje `run_record.json` navodi na pogrešno čitanje** (T041, nije popravljeno u
> ovoj feature jer bi promjena šeme razdvojila nove zapise od dva koja se ovdje prijavljuju):
>
> - `val_error` i `train_error` **nisu iz iste epohe**. `val_error` je najbolja (epoha 8),
>   `train_error` je posljednja (epoha 13). Sačuvani checkpoint je iz epohe 8, pa je `val_error`
>   ispravan broj za citiranje; `train_error` uz njega ne pripada tom modelu.
> - **Udio validacije se ne može izračunati iz zapisa.** `n_val_samples / (n_train_samples +
>   n_val_samples)` daje 6.68 %, a stvarno izdvojeno je 17.68 %. Razlika je augmentacija sa tri
>   kamere: trening broji 3 uzorka po redu, validacija 1. Zapis to nigdje ne kaže.

## 7. Evaluacija i poređenje (ključno za odbranu)

`DrivingLogger.cs` tokom evaluacijskih vožnji RL agenta piše CSV:
`time, steering, throttle, speed, checkpoint_index, collision`.

| Metrika | RL agent | BC model | Heuristički vozač | Ljudski podaci (dataset) |
|---------|----------|----------|-------------------|--------------------------|
| Kompletiranje kruga (%) | ✓ | - (nema simulator ulaz) | ✓ | - |
| Prosjek \|steering\| | ✓ | ✓ (predikcije) | ✓ | ✓ |
| Glatkoća: prosjek \|Δsteering\| | ✓ | ✓ | ✓ | ✓ |
| Histogram steering distribucije | ✓ | ✓ | ✓ | ✓ |
| Vrijeme kruga | ✓ | - | ✓ | - |

**Četvrta kolona je heuristički vozač iz §4.7**, i ona je jedina koja ne uči ništa. Bez nje se
rezultat RL agenta poredi samo sa samim sobom i sa modelom koji se ne vozi u Unityju. Sa njom se
može reći koliko je od uspjeha zasluga učenja, a koliko činjenica da je staza prohodna i za
jednostavnu heuristiku. Ako heuristika pobijedi naučenog vozača na nekoj mjeri, to se navodi
otvoreno.

**Ta kolona sad postoji i pobijedila je na dijelu mjere**, u `results/heuristic/us4_steering.md`.
Po koraku `|Δsteering|` na 14.08 Hz, `WeightedAverage` je mirniji od BC modela na sredini
raspodjele (prosjek 0.0157 naspram 0.0248, P95 0.0465 naspram 0.0692) i grublji u repu (P99 0.1649
naspram 0.1121). Oba se navode zajedno. Ono što se **ne** navodi kao pobjeda je 34 od 34 završena
kruga: BC se ne vozi, pa tu nema kolone da se izgubi, i to je razlika između mjere na kojoj se
pobjeđuje i mjere koju druga strana nema.

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

> **Druga napomena za M5 - generisane staze nemaju pravce**
> *(potiče iz feature-a 003, research C9, 2026-08-04)*
>
> Zatvorena kriva sastavljena od harmonika **stalno skreće**: nigdje na krugu nema dionice
> na kojoj je potreban steering nula. Čovjek je u datasetu vozio pravo **58.6 % vremena**.
>
> Posljedica je ista po obliku kao ona gore, ali iz drugog uzroka. Ako se u M5 direktno
> uporede marginalni histogrami steeringa agenta i čovjeka, razlika će biti ogromna i biće
> **posljedica topologije staze**, a ne razlike u vožnji. Naša staza fizički ne dozvoljava
> vožnju pravo, pa agent ne može proizvesti pik na nuli koji čini skoro tri petine ljudskog
> zapisa. Nijedan iznos treninga to ne mijenja.
>
> **Mjera prije poređenja:** težina ide na **metrike izvršenja** - glatkoća |Δsteering|,
> prebačaj, učestalost korekcija, vrijeme kruga - a marginalni histogram ostaje kao
> kontekst, ne kao glavni rezultat. Gdje se raspodjele ipak porede, poredi se **uslovna**
> raspodjela (dato da je steering nenulti), što je isti izbor koji već stoji iza SC-010.
>
> Hibridni oblik staze (lukovi + pravci + klotoide) dao bi prave pravce, ali vraća problem
> zatvaranja petlje koji polarni oblik rješava besplatno. Odbačeno za sada; ostaje kao
> proširenje ako se nedostatak pravaca pokaže kao stvarna smetnja u M3.

**Izmjereno pred M5, upisano 2026-09-01 prije ijedne linije koda za poređenje.** Obje napomene gore
su napisane kao predviđanja. Sada su provjerene na politici koja stvarno vozi krugove, pa se ovdje
upisuju brojevi umjesto očekivanja, zajedno sa tri stvari koje predviđanja nisu obuhvatila.

**Prvo, predviđanje o nedostatku pravaca je tačno, i veličina je sada poznata.**

| | čovjek, spojeni dataset | RL 009, deterministički |
|---|---|---|
| n | 32.443 | 31.202 |
| udio nultog steeringa (čovjek), odnosno unutar 0.025 od nule (agent) | **58.6 %** | **2.5 %** |
| skreće lijevo | 23.5 % | **87.6 %** |
| skreće desno | 18.0 % | 12.3 % |
| varijansa steeringa | **0.15149** | 0.03208 |

Agent skreće lijevo na skoro devet od deset koraka jer se generisana petlja vozi u jednom smjeru.
Hi-kvadrat test homogenosti nad rešetkom daje **20.154,5** uz 40 stepeni slobode. **Taj broj nije
nalaz o stilu vožnje**, nego topologija staze i rezolucija zapisa izražene kao test. Kvantizacija na
rešetku, koju prva napomena propisuje, rješava polovinu koja se tiče rezolucije i ne dira polovinu
koja se tiče staze.

**Odluka ostaje ona koju druga napomena već propisuje**: primarna osa poređenja je **|Δsteering|**,
a marginalni histogram steeringa ostaje kontekst. Uz njega se u istoj tabeli navode udio nultog
steeringa i udio skretanja lijevo, da se divergencija ne bi čitala kao tvrdnja o stilu. Uslovna
raspodjela uz nenulti steering, koju druga napomena traži, računa se i navodi.

**Drugo, referenca je spojeni dataset, i to nije formalnost.** `python/bc/config.py` postavlja
`DATASET_NAME = "combined"`, pa svaka postojeća brojka, uključujući KL iz M4, koristi track1 plus
track2. Razlika između staza je dovoljno velika da mijenja zaključak: track1 ima **79.3 %** nula i
varijansu 0.02393, track2 **48.4 %** i varijansu 0.21333. Mjereno prema track1 politika izgleda
**varijabilnija** od čovjeka, a prema spojenom datasetu je čovjek **pet puta varijabilniji**.
**Referenca se imenuje svaki put kad se brojka navede.**

**Treće, brzina uzorkovanja je dio mjere, ne detalj.** Trag iz Unityja je na 50 Hz, a agent odlučuje
svaki četvrti fizički korak, pa se komanda drži između odluka. Diferenciranjem sirovog traga na
50 Hz **67.1 % razlika je strukturno nula** i srednji |Δsteering| ispadne **0.0110** umjesto
**0.0417**, dakle vozač izgleda 3,8 puta glađi nego što jeste.

Zato se poređenje radi na **14.08 Hz**, što je `COMPARE_HZ` u `python/track/config.py`, sa
preuzorkovanjem po vožnji i diferenciranjem **nakon** preuzorkovanja. Ta vrijednost je provjerena
nezavisno: ljudski `driving_log.csv` nema kolonu vremena, ali imena centralnih slika nose milisekunde,
i medijan razmaka izvučen iz njih je **0.0710 s**, dakle 14.08 Hz. `|Δsteering|` se računa isključivo
kroz `report.py.steering_series`, nikad iz sirovog traga, i brzina se navodi uz svaku brojku.

**Četvrto, BC kolona nema tri reda iz tabele gore, i to je svojstvo a ne propust.** BC model
predviđa steering iz slika kamere drugog simulatora, pa nema kompletiranje kruga, nema vrijeme kruga
i nema stazu. Te ćelije se označavaju kao odsutne sa navedenim uzrokom i **nikad se ne popunjavaju
zamjenskom mjerom**.

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

### 7.2 Zatvaranje M5 (upisano 2026-09-02, nakon feature-a 010)

**Verdikt: M5 je ISPUNJEN.** Svih sedam kriterija iz `specs/010-m5-evaluation/spec.md` je prošlo, a
svaki se čita iz broja, ne iz tvrdnje. Puni izvještaj:
[`results/comparison/m5_comparison.md`](results/comparison/m5_comparison.md).

| kriterij | šta traži | izmjereno | ishod |
|---|---|---|---|
| SC-001 | svaka ćelija tabele iz §7 je broj ili razlog odsustva | 11 odsutnih ćelija, svaka sa uzrokom ispisanim ispod | **ISPUNJEN** |
| SC-002 | kvantizacija na ljudsku rešetku prije divergencije, uz nekvantizovano poređenje | `D` sirovo i na rešetci u istoj tabeli; artefakt pomjera vodećeg vozača sa 0.4603 na **0.2682** | **ISPUNJEN** |
| SC-003 | KL i dvouzoračni KS sa p-vrijednošću, za sva tri vozača | četiri kolone, oba testa, p uz svaku | **ISPUNJEN** |
| SC-004 | asimetrija pravca riješena eksplicitno | uslovna raspodjela uz nenula volan, plus udjeli u istoj tabeli kao statistika | **ISPUNJEN** |
| SC-005 | svaka figura iz commitovane skripte | `python/m5/plots.py`, tri figure, reprodukovane bajt po bajt iz čistog klona | **ISPUNJEN** |
| SC-006 | recept izvršen iz čistog klona, odstupanja popravljena | klon pravljen, četiri defekta nađena i popravljena, nijedan zapisan kao caveat | **ISPUNJEN** |
| SC-007 | taksonomija modela terminologijom sa predavanja | šest pojmova, svaki uz stvar koja ga čini tačnim; dva zahtijevala ogradu | **ISPUNJEN** |

**Nalaz: dvije ose imenuju različitog pobjednika, i to je rezultat, ne defekt.** Na primarnoj osi
(`|Δsteering|`, kvantizovano) najbliži čovjeku je **deterministička** politika, `D = 0.2682` naspram
sljedećih 0.3780. Na raspodjeli nivoa volana uz nenula volan najbliža je **sampling** politika,
`KL = 0.9465`, dok je deterministička posljednja sa 1.1291. To je ista politika u dva režima
inferencije. Šum čini raspodjelu politike ljudskijom, a njeno kretanje manje ljudskim: sampling
podiže srednji `|Δsteering|` sa 0.0413 na 0.1552, iznad ljudskih 0.1112. Jedan odgovor na pitanje
"ko je najsličniji čovjeku" morao bi da prećuti jedno od dva mjerenja.

**Uslovljavanje sabija cijelo polje.** Izbacivanje uzoraka pravca sa obje strane, kako druga M5
napomena u §7 traži, pomjera determinističku politiku sa 1.6575 na 1.1291, najveći pomak od četiri,
i sužava raspon između najboljeg i najgoreg sa 0.60 na 0.18. Ono što je marginalna raspodjela
mjerila bila je uglavnom količina pravca, a količina pravca je staza.

**Izvršenje, koje §7 stavlja prvo, nije blizu.** Naučena politika završava 10 od 10 izdvojenih
runova po tri kruga bez ijednog dodira zida, i dva dodatna trening seeda rade isto. Heuristika
završava 34 od 34 jednokružna runa, takođe bez dodira. Po sekundi po krugu naučena politika je brža,
**20.808 s** naspram **23.655 s**, ali ta razlika nosi svoju ogradu: dva sweepa su vožena na
različitom `timeScale` i nad različitim skupovima seedova, a vrijeme kruga nije bilo kriterij uspjeha
ni za jednog. BC ne vozi uopšte.

**Šta poređenje ne može reći.** Ništa o BC vožnji, jer BC predviđa volan za kadrove koje je čovjek
već provozao u drugom simulatoru. Malo o nivou volana što nije geometrija staze: generisana petlja
uvijek skreće i vozi se u jednom smjeru, pa vozači skreću lijevo na 76 do 88 posto koraka naspram
ljudskih 23.5. Ništa o brzini između vozača, jer su jedinice različite. I ništa iz p-vrijednosti,
jer na 5.576 do 32.443 uzoraka testovi odbacuju skoro svaku nultu hipotezu.

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
