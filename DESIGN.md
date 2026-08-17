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

### 4.6 Kraj epizode
- Sudar sa zidom, ili
- 60 s bez novog checkpointa (zaglavljen), ili
- 3 kompletirana kruga (uspjeh).

**Dodano za M3 (feature 006).** Uz pravilo zaglavljivanja stoji i tvrda granica `MaxStep = 6000`
koraka, dakle 120 s na 50 Hz. Heuristički vozač vozi krug za 26.5 s u prosjeku (§4.7.2), pa su tri
kruga oko 80 s, a 120 s ostavlja pola toga kao rezervu za politiku koja je sporija od heuristike.

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
