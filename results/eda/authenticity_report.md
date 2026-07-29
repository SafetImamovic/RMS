# Provjera autentičnosti podataka (auto-generisan)

Ovaj izvještaj odgovara na jedno pitanje: **ima li traga friziranju podataka?**

Pravilo koje vrijedi za svaki nalaz ispod: **bez nulte hipoteze nema nalaza.** Gola
brojka ne dokazuje ništa. Prije nego što provjera smije nešto prijaviti, mora reći
kako bi podaci izgledali da je sve u redu (H₀) i kako bi izgledali da je manipulacija
urađena (očekivani potpis). Tek tada odbacivanje ili neodbacivanje nešto znači.

α = 0.05 · SEED = 42 · tolerancija rešetke = 1e-06

## 1. Snimci (sesije)

Vrijeme ima smisla samo unutar jednog snimanja. Spojeni fajl spaja dva snimka, a
staza 2 je snimljena **ranije istog dana** od staze 1 - pa vrijeme na spoju ide
unazad. To nije greška u podacima nego posljedica spajanja, i zato se sve vremenske
provjere rade **po sesiji**.

| sesija | redovi | od | do |
|---|---|---|---|
| track1data | 10,615 | 2019-04-02 19:25:33.671000 | 2019-04-02 19:38:12.752000 |
| track2data | 21,828 | 2019-04-02 18:05:37.641000 | 2019-04-02 18:31:04.870000 |

## 2. Kontinuitet snimka

*Očekivani potpis*: izmiješani redovi → vrijeme prestaje teći naprijed; izrezan blok
→ jedna velika rupa; obrisani pojedinačni redovi → mnogo malih rupa oko 2× medijana.
Zato izvještavamo cijelu raspodjelu Δt, a ne samo maksimum.

| sesija | monotono | narušenja | median Δt | kadrova/s | prag rupe | rupa | >2× | >5× | >1 s | najveća |
|---|---|---|---|---|---|---|---|---|---|---|
| track1data | da | 0 | 0.0710 s | 14.08 | 0.355 s | 1 | 1 | 1 | 0 | 0.474 s |
| track2data | da | 0 | 0.0700 s | 14.29 | 0.350 s | 0 | 2 | 0 | 0 | 0.253 s |

Neparsiranih vremenskih oznaka: 0 (nijedan red nije tiho izbačen).

## 3. Duplikati

Tri vrste, **brojane odvojeno** jer svaka znači nešto drugo. Zbrajanje bi treću
(bezopasnu) pretvorilo u lažnu uzbunu.

| izvor | identični redovi | ponovljene slike | ponovljene četvorke mjerenja |
|---|---|---|---|
| track1 | 0 | 0 | 12 |
| track2 | 0 | 0 | 4 |

## 4. Rezolucija zapisa (granularnost)

Pitanje koje M1 nije postavio, a mijenja koji je test uopšte ispravan.

| izvor | kolona | različitih | klasifikacija | korak | nivoa | neopaženi | van rešetke | najveći ostatak |
|---|---|---|---|---|---|---|---|---|
| track1 | steering | 40 | **discrete** | 0.05 | 41 | [0.95] | nema | 2.00e-07 |
| track1 | throttle | 5,044 | **continuous** | - | - | - | nema | 0.00e+00 |
| track1 | brake | 1 | **constant** | - | - | - | nema | 0.00e+00 |
| track1 | speed | 10,533 | **continuous** | - | - | - | nema | 0.00e+00 |
| track2 | steering | 41 | **discrete** | 0.05 | 41 | - | nema | 2.00e-07 |
| track2 | throttle | 10,127 | **continuous** | - | - | - | nema | 0.00e+00 |
| track2 | brake | 1,708 | **continuous** | - | - | - | nema | 0.00e+00 |
| track2 | speed | 21,722 | **continuous** | - | - | - | nema | 0.00e+00 |

- `track1.steering`: 40 distinct values, every one an integer multiple of 0.05 within 1e-06 (largest residual 2e-07) - a lattice with 41 support points, 1 of them never observed
- `track1.throttle`: 5,044 values distinct at tolerance 1e-06 (> 100) - recorded at full float resolution, treated as continuous
- `track1.brake`: one distinct value (0) in all 10,615 rows - constant; statistics that need variation are not computed on it
- `track1.speed`: 10,533 values distinct at tolerance 1e-06 (> 100) - recorded at full float resolution, treated as continuous
- `track2.steering`: 41 distinct values, every one an integer multiple of 0.05 within 1e-06 (largest residual 2e-07) - a lattice with 41 support points, 0 of them never observed
- `track2.throttle`: 10,127 values distinct at tolerance 1e-06 (> 100) - recorded at full float resolution, treated as continuous
- `track2.brake`: 1,708 values distinct at tolerance 1e-06 (> 100) - recorded at full float resolution, treated as continuous
- `track2.speed`: 21,722 values distinct at tolerance 1e-06 (> 100) - recorded at full float resolution, treated as continuous

## 5. Fizička uvjerljivost promjene brzine

Kriterij je namjerno **relativan**: jedinica kolone `speed` nije dokumentovana, pa bi
tvrdnja tipa „ubrzanje je ispod 1 g" tražila pretpostavku koju ne možemo provjeriti,
a lažna preciznost je gora od poštene relativne mjere. Robusno (MAD), jer bi nekoliko
ubačenih skokova naduvalo standardnu devijaciju toliko da granica pređe preko njih i
test prestane da ih vidi.

| sesija | median a | MAD | max \|a\| | prag | outliera |
|---|---|---|---|---|---|
| track1data | -0.813 | 1.459 | 12.81 | 6.48 | 796 |
| track2data | -0.133 | 2.147 | 25.75 | 10.60 | 982 |

## 6. Hipoteze i testovi

χ², a ne KS: KS pretpostavlja kontinualnu raspodjelu, a na rešetkastim podacima ima
vezane vrijednosti i p-vrijednost mu nije tačna. Za diskretnu varijablu kategorije su
same vrijednosti - nema binovanja, dakle nema ni proizvoljnog izbora.

### T1_uniform_gof - track1

- **H₀**: steering je uniformno raspoređen po 41 nivoa rešetke - svaka vrijednost jednako vjerovatna, kako bi ih dao uniformni generator
- χ² = 264,576.53 · dof = 40 (nakon spajanja; spojenih kategorija: 0) · kritično = 55.76 · p = 0
- **Odluka pri α = 0.05**: ODBACUJEMO H₀
- **Značenje**: ODBAČENO, kako smo i očekivali. Steering ima strukturu kakvu uniformni generator slučajnih brojeva ne proizvodi - to je dokaz PROTIV toga da je kolona izmišljena.

### T2_symmetry - track1

- **H₀**: raspodjela steeringa je simetrična oko nule: vozač je nivo +k koristio jednako često kao nivo −k, za svaki nivo k
- χ² = 1,078.73 · dof = 18 (nakon spajanja; spojenih kategorija: 2) · kritično = 28.87 · p = 1.03e-217
- **Odluka pri α = 0.05**: ODBACUJEMO H₀
- **Značenje**: ODBAČENO: lijevo/desno = 1,849 / 344 (odnos 5.375) - razlika je prevelika da bi bila slučajna. Odbacivanje samo po sebi NIJE sumnjivo: ono govori da asimetrija postoji, ne odakle dolazi. Uz to, pri ovolikom uzorku χ² vidi i sasvim malu neravnotežu, pa odnos treba čitati zajedno sa p-vrijednošću. Mehanizam i veličinu efekta vidi u verdiktu.

### T1_uniform_gof - track2

- **H₀**: steering je uniformno raspoređen po 41 nivoa rešetke - svaka vrijednost jednako vjerovatna, kako bi ih dao uniformni generator
- χ² = 198,114.92 · dof = 40 (nakon spajanja; spojenih kategorija: 0) · kritično = 55.76 · p = 0
- **Odluka pri α = 0.05**: ODBACUJEMO H₀
- **Značenje**: ODBAČENO, kako smo i očekivali. Steering ima strukturu kakvu uniformni generator slučajnih brojeva ne proizvodi - to je dokaz PROTIV toga da je kolona izmišljena.

### T2_symmetry - track2

- **H₀**: raspodjela steeringa je simetrična oko nule: vozač je nivo +k koristio jednako često kao nivo −k, za svaki nivo k
- χ² = 49.47 · dof = 20 (nakon spajanja; spojenih kategorija: 0) · kritično = 31.41 · p = 0.000264
- **Odluka pri α = 0.05**: ODBACUJEMO H₀
- **Značenje**: ODBAČENO: lijevo/desno = 5,768 / 5,485 (odnos 1.052) - razlika je prevelika da bi bila slučajna. Odbacivanje samo po sebi NIJE sumnjivo: ono govori da asimetrija postoji, ne odakle dolazi. Uz to, pri ovolikom uzorku χ² vidi i sasvim malu neravnotežu, pa odnos treba čitati zajedno sa p-vrijednošću. Mehanizam i veličinu efekta vidi u verdiktu.

### T3_homogeneity - track1 vs track2

- **H₀**: obje staze vuku steering iz jedne te iste raspodjele nad zajedničkom podrškom rešetke
- χ² = 4,300.35 · dof = 40 (nakon spajanja; spojenih kategorija: 0) · kritično = 55.76 · p = 0
- **Odluka pri α = 0.05**: ODBACUJEMO H₀
- **Značenje**: ODBAČENO: staze se stvarno različito voze. To potvrđuje da su u pitanju dva različita snimka, a ne jedan snimak iskopiran i preimenovan da bi dataset izgledao veći.

## 7. Verdikti - objašnjivo naspram sumnjivog

Nalaz je dokaz friziranja **samo ako nemamo mehanizam koji ga objašnjava**. Nalaz
može biti objašnjiv **i** i dalje štetan za kasniji milestone - tada nosi i posljedicu
i mjeru ublažavanja.

**Sažetak: 12 nalaza, od toga 0 bez objašnjenja.**

### track1:brake:constant - objašnjivo

- **Nalaz**: track1: kolona 'brake' ima tačno jednu vrijednost u svih 10,615 redova
- **Mehanizam**: staza 1 je ravna zatvorena petlja - vozač nijednom nije zakočio. Obrisana kolona i nikad korištena kolona izgledaju isto u brojkama; razlikuje ih to što ista kolona drugdje varira (track2: 1,708 različitih), dakle format je ispravan i pisač kolone radi
- **Posljedica**: M1 je nad spojenim podacima prijavio brake_is_dead: false (94,6 % nula). To je artefakt spajanja - po stazi je kolona mrtva
- **Mjera**: kočnicu izvještavati po stazi, nikad spojeno; ne koristiti je kao ulaz za model treniran samo na stazi 1

### track1:steering:unobserved_levels - objašnjivo

- **Nalaz**: track1: nivoi [0.95] postoje u rešetki ali se nikad ne pojavljuju
- **Mehanizam**: nivo koji vozač jednostavno nije upotrijebio. Da je neko brisao redove, nestajali bi cijeli opsezi vrijednosti i vidjeli bismo rupu i u vremenu - ovdje je nestao jedan izolovan nivo dok mu susjedi i ogledalni parnjak postoje

### track1data:timeline:gap@10614 - objašnjivo

- **Nalaz**: track1data: rupa od 0.474 s (prag 0.355 s) na redu 10614
- **Mehanizam**: rupa pada na POSLJEDNJI kadar snimka - to je gašenje snimača, ne izrezan komad. Izrezan blok bi ostavio rupu u SREDINI i skok u sadržaju na spoju; ovdje su brzina i steering neprekidni preko nje

### track1:duplicates:tuples - objašnjivo

- **Nalaz**: track1: 12 ponovljenih četvorki mjerenja na različitim kadrovima
- **Mehanizam**: steering ima samo 41 mogući nivo, pa je prostor vrijednosti mali i sudari se dešavaju sami od sebe. Da je riječ o kopiranju redova, ponovile bi se i putanje slika - a njih ima 0

### track2:duplicates:tuples - objašnjivo

- **Nalaz**: track2: 4 ponovljenih četvorki mjerenja na različitim kadrovima
- **Mehanizam**: steering ima samo 41 mogući nivo, pa je prostor vrijednosti mali i sudari se dešavaju sami od sebe. Da je riječ o kopiranju redova, ponovile bi se i putanje slika - a njih ima 0

### track1data:plausibility:outliers - objašnjivo

- **Nalaz**: track1data: 796 kadrova (7.5 %) van pojasa median ± 5×MAD impliciranog ubrzanja
- **Mehanizam**: raspodjela impliciranog ubrzanja ima uzak centar i široke repove (MAD = 1.46, ali maksimum = 12.8): gas i kočnica se pri 14 kadrova/s koriste u naletima, pa pojas od 5×MAD oko uskog centra pada oko 97. percentila. Visok procenat je oblik raspodjele, a ne trag friziranja - potpis spajanja bio bi ekstrem koji se POKLAPA sa rupom u vremenu, a takvog poklapanja nema
- **Posljedica**: apsolutni broj outliera se ne smije citirati kao mjera ispravnosti podataka
- **Mjera**: koristiti ga isključivo relativno - porediti ekstreme sa rupama u vremenu, a ne sa fiksnim pragom

### track2data:plausibility:outliers - objašnjivo

- **Nalaz**: track2data: 982 kadrova (4.5 %) van pojasa median ± 5×MAD impliciranog ubrzanja
- **Mehanizam**: raspodjela impliciranog ubrzanja ima uzak centar i široke repove (MAD = 2.15, ali maksimum = 25.7): gas i kočnica se pri 14 kadrova/s koriste u naletima, pa pojas od 5×MAD oko uskog centra pada oko 97. percentila. Visok procenat je oblik raspodjele, a ne trag friziranja - potpis spajanja bio bi ekstrem koji se POKLAPA sa rupom u vremenu, a takvog poklapanja nema
- **Posljedica**: apsolutni broj outliera se ne smije citirati kao mjera ispravnosti podataka
- **Mjera**: koristiti ga isključivo relativno - porediti ekstreme sa rupama u vremenu, a ne sa fiksnim pragom

### track1:T1 - objašnjivo

- **Nalaz**: track1: uniformnost odbačena (χ² = 264,577, dof = 40)
- **Mehanizam**: stvarna vožnja je dominantno pravo - 79.3 % kadrova ima steering tačno 0. Nijedan uniformni generator to ne proizvodi

### track1:T2:material - objašnjivo

- **Nalaz**: track1: simetrija odbačena, odnos lijevo/desno = 5.375 - velika, stvarna asimetrija
- **Mehanizam**: zatvorena petlja vožena u jednom smjeru (suprotno kazaljci na satu): svaki krug daje isti broj lijevih zaokreta, a desnih gotovo nema
- **Posljedica**: ozbiljan rizik za M4 - BC model naučen na ovim podacima vuče lijevo i na pravcu
- **Mjera**: horizontalno ogledanje slike uz promjenu znaka steeringa (udvostručuje podatke i izjednačava lijevo/desno)

### track2:T1 - objašnjivo

- **Nalaz**: track2: uniformnost odbačena (χ² = 198,115, dof = 40)
- **Mehanizam**: stvarna vožnja je dominantno pravo - 48.4 % kadrova ima steering tačno 0. Nijedan uniformni generator to ne proizvodi

### track2:T2:negligible - objašnjivo

- **Nalaz**: track2: simetrija odbačena, ali odnos lijevo/desno = 1.052 - praktično zanemarivo
- **Mehanizam**: veličina uzorka, ne veličina efekta. Pri desetinama hiljada kadrova χ² vidi i neravnotežu od nekoliko procenata. Statistička značajnost nije isto što i praktična - zato uz svaki test izvještavamo i odnos, a ne samo p-vrijednost

### T3 - objašnjivo

- **Nalaz**: homogenost staza odbačena (χ² = 4,300, dof = 40)
- **Mehanizam**: staze su fizički različite: ravna zatvorena petlja naspram brdske ceste sa oštrim serpentinama

## 8. Da li se M1 kalibracija mijenja?

**NE** - Prag |Δsteering| (P95) ponovo izračunat: 0.5500001 naspram M1 0.5500001. Robustan opseg steeringa (P1–P99): (-1.000, 1.000) naspram M1 (-1.000, 1.000). NEPROMIJENJENO. Razlog: oba broja su percentili, dakle redoslijedne statistike - čitaju se iz sortiranih vrijednosti i potpuno su nezavisne od toga da li varijablu zovemo diskretnom ili kontinualnom. Uzgred, prag je 11 koraka rešetke, što potvrđuje da pada tačno na dozvoljenu vrijednost.

