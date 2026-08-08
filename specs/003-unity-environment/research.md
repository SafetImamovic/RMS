# Phase 0 Research: Unity Driving Environment (M2)

Odluke koje zatvaraju otvorena tehnička pitanja prije implementacije.
Isti stil kao M1 i feature 002: *Prosto* -> *Odluka* -> *Zašto*.

Sve brojke ispod su izvedene iz M1 mjerenja (`results/eda/m1_stats.json`,
`results/eda/authenticity_report.md`) ili iz eksplicitno navedene geometrijske pretpostavke.
Nijedan prag nije "odabran jer izgleda dobro".

---

## Pojmovnik (pročitaj prvo)

- **Međuosovinsko rastojanje (wheelbase, L)** - razmak između prednje i zadnje osovine.
- **Bicikl model** - najjednostavniji model skretanja vozila: dva prednja točka se zamijene
  jednim u sredini, isto i zadnja. Pri maloj brzini vrijedi `R = L / tan(δ)`, gdje je δ ugao
  prednjeg točka, a R poluprečnik kruga koji auto opisuje.
- **Poluprečnik krivine (radius of curvature)** - poluprečnik kruga koji najbolje prianja uz
  krivu u datoj tački. Mala vrijednost znači oštra krivina.
- **Zakrivljenost (curvature, κ)** - recipročna vrijednost poluprečnika, `κ = 1/R`.
- **Harmonik** - sinusna komponenta. Zbir nekoliko sinusa različitih frekvencija daje
  proizvoljno "talasast" oblik, a da ostane gladak.
- **Podnedovoljno skretanje (understeer)** - pri brzini auto skreće **manje** nego što geometrija
  nalaže, pa je stvarni poluprečnik **veći** od geometrijskog.
- **Rezerva volana (steering headroom)** - koliko volana ostaje neiskorišteno kad auto prati
  krivinu. Ako krivina traži puni zaokret, rezerva je nula i agent nema čime korigovati.
- **Seed** - cijeli broj koji potpuno određuje jedan generisani objekat. Isti seed, isti izlaz.

---

## C1 - Profil vozila i tabela poluprečnika

- **Prosto:** koliko oštro auto može skrenuti, i koje krivine iz toga slijede.
- **Odluka**: `L = 2.5 m`, `δ_max = 25°` (već fiksirano u DESIGN 4.4). Iz bicikl modela:

  | \|steering\| | odakle dolazi | δ | R |
  |---|---|---|---|
  | 0.25 | track1 median (nenultih) | 6.25° | 22.83 m |
  | 0.40 | track1 P75 | 10.00° | 14.18 m |
  | 0.50 | track2 median | 12.50° | 11.28 m |
  | 0.65 | track1 P95 | 16.25° | 8.58 m |
  | **0.79** | **granica koju staza smije tražiti** | 19.73° | **6.96 m** |
  | 0.90 | track1 P99 | 22.50° | 6.04 m |
  | 1.00 | puni zaokret | 25.00° | 5.36 m |

  Apsolutni minimum je `R_min = 5.361 m`. Radni pod je `R_floor = 1.3 × R_min = 6.97 m`.
- **Zašto L = 2.5 m**: to je tipično međuosovinsko rastojanje putničkog auta i jedina veličina u
  cijelom feature-u koja je slobodno izabrana. Zapisano je da svi poluprečnici skaliraju linearno
  s njom, pa promjena L ne kvari nijedan zaključak, samo pomjeri tabelu.

## C2 - Sigurnosna margina JE rezerva volana (ključni nalaz)

- **Prosto:** koliko labaviju krivinu tražimo od one koju auto jedva može, i šta nas to košta.
- **Odluka**: margina **1.3**, dakle `R_floor = 1.3 × R_min`.
- **Zašto**: margina nije proizvoljan faktor sigurnosti nego direktno određuje koliko volana
  agentu ostaje u krivini:

  | margina | R_floor | max steering koji staza traži | rezerva volana |
  |---|---|---|---|
  | 1.00 | 5.36 m | 1.000 | **0 %** |
  | 1.15 | 6.17 m | 0.883 | 11.7 % |
  | **1.30** | **6.97 m** | **0.789** | **21.1 %** |
  | 1.50 | 8.04 m | 0.691 | 30.9 % |

  Pri margini 1.0 najoštrija krivina traži puni zaokret i agent nema **ničim** da koriguje kad ga
  izbaci ka vanjskoj ivici. To nije staza, to je zamka.
- **Nezavisno od L**: `s_max = atan(tan(25°)/1.3) / 25° = 0.789` - L se skrati. Margina je dakle
  **jedini** parametar koji određuje ovu granicu, što je čini poštenom ručkom za podešavanje.
- **Cijena, i izvještava se otvoreno**: generisana staza nikad ne može tražiti steering iznad
  0.789, dok ljudski podaci idu do 1.0. Izmjereno: 2.60 % uslovnih uzoraka track1 je iznad 0.789,
  dakle granica sjedi na **97.40. percentilu** i dalje ne idemo (mjereno u C15, ne procijenjeno).
  Ovo se **navodi** u izvještaju, ne prešućuje.

## C3 - Brzina: normalizacija umjesto pretvaranja jedinica

- **Prosto:** ne znamo u čemu je izražena brzina u datasetu, pa je ne pretvaramo.
- **Odluka**: `v_max = 10 m/s` za Unity auto. **Svako** poređenje sa datasetom radi se na
  normalizovanoj skali: `v_norm = v / P99(v)` na obje strane. Dataset P99 = 17.49 jedinica,
  Unity P99 = izmjereno iz drive loga.
- **Zašto normalizacija**: feature 002 (A7) je utvrdio da kolona `speed` nema dokumentovanu
  jedinicu. Tvrdnja "top speed je 17.49 m/s" ili "17.49 mph" tražila bi pretpostavku koju ne
  možemo provjeriti, a lažna preciznost bi se onda provukla kroz svaki prag u M3 i M5.
  Normalizacija to pitanje uklanja umjesto da ga riješi pogađanjem.
- **Zašto baš 10 m/s**: to je inženjerski izbor za igrivost, ne tvrdnja o datasetu. Daje krug od
  ~19 s pri `R0 = 30 m`, što je razumna dužina epizode za PPO. Broj je izložen kao imenovana
  konstanta i može se mijenjati bez ijedne posljedice po poređenja, jer su ona normalizovana.

## C4 - Brzina okretanja volana: dokaz o uređaju, ne o vozilu

- **Prosto:** u datasetu volan skoči s kraja na kraj u jednom kadru; pravi volan to ne može.
- **Odluka**: brzina volana se bira tako da čovjek tastaturom postigne **P95 promjene volana
  unutar faktora 2** od snimljene, mjereno pri istoj frekvenciji. Snimljeno: P95 = 0.30 (track1)
  i 0.70 (track2) po kadru na 14.08 kadrova/s.
- **Zašto faktor 2, a ne tačna vrijednost**: dvije staze se međusobno razlikuju za faktor 2.33,
  pa jedna tačna ciljna vrijednost ne postoji. Faktor je pošten opis onoga što podaci dozvoljavaju.
- **Zašto ne pratimo maksimum**: `max |Δsteering| = 1.00` po kadru na obje staze, dakle pun opseg
  u 0.071 s. To je posljedica **tastature ili miša**, a ne letve volana. Auto koji to reprodukuje
  bio bi neupravljiv. Raspodjela promjene volana je dokaz o **načinu snimanja**, ne specifikacija
  vozila. (Isti obrazac kao A8 u feature-u 002: brojka je stvarna, ali znači nešto drugo nego što
  na prvi pogled izgleda.)

## C5 - Kada odustajemo od fizike točkova

- **Prosto:** unaprijed zapisan uslov, da odluka ne padne iz umora.
- **Odluka**: primarni model je fizika sa četiri točka. Prelazi se na pojednostavljeni kinematski
  model ako se u **tri uzastopne jednominutne vožnje tastaturom** desi bilo šta od:
  1. nagib ili valjanje karoserije pređe **45°** iako su u prethodnom koraku sva četiri točka
     bila na tlu;
  2. vozilo u mirovanju, bez ulaza, odluta više od **0.1 m za 10 s**;
  3. vozilo propadne kroz podlogu ili uđe u stanje iz kojeg se ne vraća bez restarta.
- **Zašto ovako**: DESIGN 4.2 kaže "fizika je primarna, kinematika je alternativa ako pravi
  probleme". "Pravi probleme" nije procedura. Ova tri uslova se mogu provjeriti pokretanjem
  simulacije i ne zavise od raspoloženja.
- **Zašto tri vožnje**: jedna loša vožnja može biti slučajnost ili greška vozača.

## C6 - Oblik generatora: polarni harmonici

- **Prosto:** kako napraviti nasumičnu stazu koja se sigurno zatvara i ne siječe samu sebe.
- **Odluka**:

  ```
  r(θ) = R0 · (1 + Σ_{k=2}^{5} a_k · sin(k·θ + φ_k)),   a_k = A / k²
  ```

  `R0 = 30 m`, `A` uzorkovano iz `[0.40, 0.70]`, `φ_k` uniformno iz `[0, 2π)`, sve iz seeda.
- **Zašto polarni oblik, a ne lanac lukova**: nizanje nasumičnih lukova i pravaca **ne zatvara
  petlju**. Kriva završi blizu početka i obično se dva-tri puta presiječe. Naknadna korekcija
  zatvaranja iskrivljuje upravo one poluprečnike koje smo htjeli kontrolisati. U polarnom obliku
  je `r(2π) = r(0)` **po konstrukciji** - zatvaranje je besplatno i ne košta ništa geometrijski.
- **Zašto `a_k = A/k²`**: doprinos harmonika k zakrivljenosti raste otprilike kao `a_k·(k²−1)`.
  Sa `a_k = A/k²` svaki harmonik doprinosi približno jednako (`≈ A`), pa jedan parametar A
  kontroliše ukupnu "talasavost" umjesto četiri nezavisna.
- **Zašto k počinje od 2**: `k = 1` samo pomjeri krug u stranu, ne mijenja mu oblik.
- **Zašto k staje na 5**: viši harmonici traže sve manje amplitude da ne probiju pod poluprečnika,
  pa doprinose sve manje oblika za sve više rizika od odbijanja seeda.
- **Granice iz zdravog razuma, provjerene**: `Σ a_k = 0.4636·A` mora ostati `< 1` da bi `r > 0`.
  Pri `A = 0.70` to je 0.32, daleko od granice. Vezujući uslov je pod poluprečnika, ne pozitivnost.
- **Približna procjena, i zašto se ipak mjeri**: `κ_max ≈ (1 + 4A)/R0`, dakle `A = 0.62` daje
  `R_min ≈ 8.6 m`, a `A = 0.70` daje `≈ 7.9 m`. To je samo orijentir za izbor opsega A;
  **stvarni** minimalni poluprečnik se uvijek računa numerički i provjerava, jer je formula
  aproksimacija za male amplitude.

## C7 - Provjera zakrivljenosti i odbijanje seeda

- **Prosto:** izmjeri najoštriju krivinu; ako je preoštra, baci seed.
- **Odluka**: kriva se uzorkuje na **2000 tačaka**, zakrivljenost se računa iz polarne formule

  ```
  κ(θ) = |r² + 2r'² − r·r''| / (r² + r'²)^{3/2}
  ```

  Seed se **odbija** ako `min(1/κ) < R_floor`. Odbijeni seed se **zapisuje** sa razlogom.
- **Zašto se odbija, a ne popravlja**: generator koji tiho smanjuje A dok ne prođe ima stopu
  prihvatanja koju niko ne vidi. Ako je stopa niska, to je **nalaz** (pod poluprečnika i
  statistički cilj se guraju), a ne sitnica koju treba zagladiti. SC-011 traži najmanje 50 %.
- **Zašto analitička formula, a ne tri tačke**: `r`, `r'` i `r''` su poznati u zatvorenom obliku
  jer je `r` zbir sinusa. Numeričko diferenciranje bi uvelo grešku baš tamo gdje je odluka
  binarna (prihvati/odbij).

## C8 - Poređenje raspodjele: rastojanje, ne test

- **Prosto:** provjeri da staza traži otprilike onakvo skretanje kakvo je čovjek stvarno koristio.
- **Odluka**: za svaku uzorkovanu tačku staze izračunaj traženi steering
  `s(θ) = atan(L / R(θ)) / δ_max`, sakupi po cijeloj stazi (i po cijelom batchu), pa uporedi sa
  **empirijskom** raspodjelom `|steering|` iz M1. Mjera: **Wasserstein-1 rastojanje** na
  normalizovanoj skali, prag prihvatanja izložen kao imenovana konstanta.
- **Zašto se poredi sa *uslovnom* raspodjelom (samo nenulti steering)**: vidi C9. Staza nema
  pravaca, pa nema ni nula. Poređenje sa punom raspodjelom bi mjerilo topologiju staze, ne oblik
  krivina.
- **Zašto Wasserstein, a ne χ² ili KS**: Wasserstein je **rastojanje**, ima jedinicu, i mala
  vrijednost znači "blizu". χ² i KS daju p-vrijednost, a **velika p-vrijednost nije dokaz
  slaganja** - to je tačno ona greška zbog koje je napisan feature 002. FR-019 to izričito
  zabranjuje. Ako neko ipak želi χ² brojku, smije stajati kao deskriptivna mjera, ali odluka o
  prihvatanju se **ne** donosi p-vrijednošću.
- **Odnos prema Principu IX ustava**: Princip IX imenuje χ², KS i KL divergenciju kao mjere
  poređenja. Te odredbe su vezane za dvije druge tačke: χ² i KS za **karakterizaciju ljudskog
  dataseta u M1** (već urađeno, feature 002), a KL i KS za **poređenje RL vs BC vs čovjek u M5**.
  Ovdje se ne karakteriše raspodjela niti se porede dva naučena modela, nego se donosi binarna
  odluka prihvati/odbij o geometriji staze, a za to treba **rastojanje sa pragom**, ne test.
  Princip IX ostaje na snazi za M1 i M5 nepromijenjen. Ova rečenica postoji da razlika bude
  zapisana, a ne prećutna.
- **Zašto se cilja track1 profil**: DESIGN 4.1 traži "dominantno blage krivine, par oštrijih".
  To je track1 (steering nenulti u 21 % kadrova, median 0.25, puni zaokret 0.7 %), a ne track2
  (nenulti 52 %, median 0.50, **puni zaokret 21.9 %**). Track2 profil ostaje kao moguća teža
  postavka za kasnije.

## C9 - Nalaz: generisane staze nemaju pravce

- **Prosto:** zatvorena kriva od harmonika stalno skreće; čovjek je 58.6 % vremena vozio pravo.
- **Odluka**: prihvatamo ograničenje, poredimo **uslovnu** raspodjelu (dato da je steering
  nenulti), i **zapisujemo** posljedicu za M5.
- **Zašto je ovo važno, a ne sitnica**: ako se u M5 direktno uporede histogrami steeringa agenta
  i čovjeka, razlika će biti ogromna i biće **posljedica topologije staze**, a ne razlike u
  vožnji. Naša staza fizički ne dozvoljava vožnju pravo. To pojačava napomenu koja već stoji u
  DESIGN 7: težina poređenja mora biti na **metrikama izvršenja** (glatkoća |Δsteering|,
  prebačaj, učestalost korekcija), a marginalni histogram je kontekst, ne glavni rezultat.
- **Alternativa razmotrena i odbačena za sada**: hibridni oblik (lukovi + pravci + klotoide) bi
  dao prave pravce, ali vraća problem zatvaranja petlje koji polarni oblik rješava besplatno.
  Ostaje kao moguće proširenje ako se pokaže da je nedostatak pravaca stvarna smetnja u M3.

## C10 - Samopresjecanje i minimalno razdvajanje

- **Prosto:** petlja se ne smije presjecati, ni skoro dodirivati.
- **Odluka**: dvije provjere nad uzorkovanom krivom:
  1. **Presjek**: nijedan par nesusjednih segmenata se ne siječe.
  2. **Razdvajanje**: minimalno rastojanje između tačaka koje su po **dužini luka** udaljene više
     od `2 × širina staze` mora biti najmanje `2 × širina staze = 12 m`.
- **Zašto i druga provjera**: petlja može biti topološki ispravna a da dva dijela prolaze na 3 m
  jedan od drugog. Tada zraci senzora "vide" susjedni dio staze kao prepreku, a checkpointi
  postaju nejednoznačni. Zatvorenost sama po sebi nije dovoljna.
- **Širina staze `W = 6 m`**: auto je širok ~1.8 m, pa 6 m daje po ~2 m sa svake strane za
  korekciju. Uslov `W/2 < R_floor` (3 < 6.97) garantuje da unutrašnja ivica u najoštrijoj krivini
  ne kolabira u tačku.

## C11 - Domet zraka iz zaustavnog puta

- **Prosto:** senzor mora vidjeti zid prije nego što je prekasno zakočiti.
- **Odluka**: `13 zraka, 180° naprijed` (DESIGN 4.3, nepromijenjeno), **domet 20 m**.
- **Zašto 20 m**: iz snimljenog usporenja, normalizovano i prevedeno na `v_max = 10 m/s`:

  | snimljeno | \|Δspeed\|/kadar | usporenje | zaustavni put sa 10 m/s |
  |---|---|---|---|
  | P95 | 0.727 | 5.85 m/s² | **8.5 m** |
  | max | 1.957 | 15.75 m/s² | 3.2 m |

  20 m je nešto više od dvostrukog zaustavnog puta pri uobičajenom (P95) kočenju, plus dužina
  vozila. Senzor kraći od 8.5 m javljao bi zid koji se više ne može izbjeći, dakle ne bi nosio
  upotrebljivu informaciju. Domet se bira po **P95**, a ne po maksimumu, jer maksimalno kočenje
  nije ono na šta se agent smije oslanjati.
- **"Ništa u dometu" mora biti razlučivo od "nula metara"** - to je zaseban zahtjev (FR-024), jer
  su te dvije situacije suprotne, a naivno kodiranje ih izjednači.

## C12 - Checkpointi i randomizacija starta

- **Odluka**: **24 checkpointa**, ravnomjerno po dužini luka. Obim pri `R0 = 30 m` je ~188 m plus
  talasanje, dakle ~8 m između checkpointa, odnosno oko 0.8 s pri punoj brzini.
- **Zašto 24**: DESIGN 4.1 traži 20 do 30. 24 je unutar opsega, dijeli se sa 2, 3, 4, 6, 8 i 12,
  što olakšava dijeljenje staze na sektore kasnije.
- **Randomizacija starta**: slučajan checkpoint kao startna tačka, bočni pomak `±1.5 m` od ose
  (staza je 6 m), i zaokret `±10°`.
- **Zašto slučajan checkpoint, a ne samo pomak**: ako agent uvijek kreće s istog mjesta, može
  naučiti niz poteza umjesto vožnje. Ovo je ista logika kao seed split, samo unutar jedne staze.

## C13 - Protokol seedova i podjela train/test

- **Odluka**: `TRAIN_SEEDS = range(1, 41)`, `EVAL_SEEDS = range(1001, 1011)`, filtrirano na
  prihvaćene. Podjela je zapisana u repozitorijumu, ne u nečijoj glavi. Odbijeni seedovi se
  zapisuju sa razlogom.
- **Zašto razmaknuti opsezi**: 1..40 i 1001..1010 se ne mogu slučajno preklopiti ni kad se skup za
  trening kasnije proširi.
- **Zašto uopšte**: bez odvojenih evaluacionih staza M3 ne može tvrditi da je agent **naučio da
  vozi**, samo da je naučio te staze. Ovo je jedina stvar u cijelom feature-u koja pretvara
  rezultat M3 iz tvrdnje u dokaz.

## C14 - Usklađivanje frekvencija prije bilo kakvog poređenja

- **Prosto:** dataset je snimljen na ~14 kadrova/s, Unity ide svojim korakom.
- **Odluka**: drive log iz Unityja se prije poređenja **presempluje na 14.08 Hz** (median Δt
  track1). Sve veličine "po kadru" (Δsteering, Δspeed) računaju se tek nakon toga.
- **Zašto**: P95 Δsteeringa od 0.30 nema smisla bez frekvencije uz sebe. Poređenje "po kadru" na
  dvije različite frekvencije mjeri razliku u brzini uzorkovanja, ne u vožnji. Ista greška koju
  je feature 002 izbjegao tako što nikad nije računao preko granice sesije.

## C15 - Prag prihvatanja za Wasserstein rastojanje

- **Prosto:** koliko blizu ljudskoj raspodjeli staza mora biti da bi prošla, i odakle taj broj.
- **Odluka**: `MATCH_DISTANCE_THRESHOLD = 0.05`.
- **Zašto uopšte ova odluka postoji**: prva verzija je nosila 0.08 bez ijednog izvođenja, što je
  direktna suprotnost rečenici na vrhu ovog dokumenta da nijedan prag nije odabran jer izgleda
  dobro. Ispravljeno mjerenjem nad samim datasetom.
- **Tri izmjerene skale**, sve na uslovnoj raspodjeli `|steering| > 0`, mjera W1:

  | poređenje | W1 | šta predstavlja |
  |---|---|---|
  | track1 nasumične polovine (seed 0) | 0.0079 | čisti šum uzorkovanja |
  | track1 prva polovina vs druga | 0.0231 | isti čovjek, ista staza, uz vremenski drift |
  | track1 vs uniformna na [0, 0.789] | **0.1142** | raspodjela **bez ikakve strukture** |
  | track1 vs track2 | 0.2635 | drugi čovjek, drugi profil vožnje |

  (`n = 2193` nenultih na track1, `n = 11253` na track2.)

  > **Ispravka vrijednosti bez strukture: 0.1047 → 0.1142 (2026-07-31, upisano ovdje
  > 2026-08-04, T069).** Ovaj dokument je nosio 0.1047 dok `config.py` nosi 0.1142, pa su
  > kod i istraživanje govorili različito. Ponovno računanje po definiciji koju C15 sam
  > navodi daje **0.1142**, pod dvije nezavisne implementacije: kvantilno-integralni
  > Wasserstein ovog projekta i `scipy.stats.wasserstein_distance`, koje se slažu na četiri
  > decimale. Iste te implementacije reprodukuju druge dvije skale tačno (0.0231, i 0.2636
  > naspram zapisanih 0.2635), pa mašinerija nije sporna, nego samo ova vrijednost. Nosač
  > raspodjele je provjeren kao mogući uzrok i nije: uniformna na [0, 1] daje 0.2127, a
  > bezuslovna referenca 0.3359, ni blizu 0.1047. Porijeklo broja 0.1047 nije utvrđeno.
  >
  > **Nijedna odluka se ne mijenja**, jer 0.05 leži ispod i stare i nove vrijednosti.
  > Izvođenje ispod je zadržano u originalnom obliku, sa starim brojem, jer je to račun
  > kojim je prag **stvarno** izveden; ponovno izvođenje sa 0.1142 dalo bi
  > `sqrt(0.0231 × 0.1142) = 0.0514`, što se takođe zaokružuje na 0.05.

- **Izvođenje**: prag mora biti **strogo ispod** vrijednosti bez strukture, inače bi i
  raspodjela bez strukture prošla i test ne bi razlikovao ništa. Mora biti i **iznad 0.0231**,
  inače od generatora tražimo da bude bliži track1 nego što je track1 sam sebi, što nijedan
  uzorak konačne veličine ne može garantovati. Geometrijska sredina te dvije granice, kako je
  prag izvorno izveden, je `sqrt(0.0231 × 0.1047) = 0.0492`, zaokruženo na **0.05**. Sa
  ispravljenom vrijednošću `sqrt(0.0231 × 0.1142) = 0.0514`, opet **0.05**. Prag je 2.2 puta
  iznad poda i 2.3 puta ispod baseline-a bez strukture.
- **Ako batch ne dostigne 0.05**: to je **nalaz o harmonijskom obliku generatora**, ne dugme za
  podešavanje - isti tretman kao stopa prihvatanja u SC-011. Svako popuštanje praga mora ostati
  strogo ispod 0.1142, jer iznad toga test prestaje da razlikuje staze od šuma.
- **Uzgredna potvrda za C2**: odsijecanje na 0.789 samo po sebi košta `W1 = 0.0027`, dakle
  zanemarivo u odnosu na prag. Truncation nije ono što će oboriti poređenje.

---

## Sažetak izvedenih konstanti

| Konstanta | Vrijednost | Izvor |
|---|---|---|
| `WHEELBASE_M` | 2.5 | izabrano, zapisano, sve skalira linearno (C1) |
| `STEER_MAX_DEG` | 25 | DESIGN 4.4 |
| `R_MIN_M` | 5.361 | izvedeno, `L/tan(25°)` |
| `RADIUS_MARGIN` | 1.3 | C2, jednako 21.1 % rezerve volana |
| `R_FLOOR_M` | 6.97 | izvedeno |
| `V_MAX_MS` | 10.0 | igrivost, ne tvrdnja o datasetu (C3) |
| `DATASET_SPEED_P99` | 17.49 | M1 `m1_stats.json` |
| `TRACK_R0_M` | 30.0 | C6, daje krug ~19 s |
| `HARMONICS` | k = 2..5 | C6 |
| `AMPLITUDE_RANGE` | 0.40 do 0.70 | C6 |
| `SAMPLES_PER_TRACK` | 2000 | C7 |
| `TRACK_WIDTH_M` | 6.0 | C10 |
| `MIN_SEPARATION_M` | 12.0 | C10, `2 × širina` |
| `RAY_COUNT`, `RAY_FOV_DEG` | 13, 180 | DESIGN 4.3 |
| `RAY_LENGTH_M` | 20.0 | C11, iz zaustavnog puta pri P95 kočenju |
| `N_CHECKPOINTS` | 24 | C12 |
| `START_LATERAL_M`, `START_YAW_DEG` | 1.5, 10 | C12 |
| `COMPARE_HZ` | 14.08 | C14, median frekvencija track1 |
| `MATCH_DISTANCE_THRESHOLD` | 0.05 | C15, geometrijska sredina poda 0.0231 i baseline-a 0.1047 |
| `TRAIN_SEEDS`, `EVAL_SEEDS` | 1..40, 1001..1010 | C13 |

## C16 - Postavljanje auta u Start() se ne primjenjuje (nađeno pri T051, 2026-08-08)

**Simptom.** Na seedu 37 auto se pojavi izvan staze i propadne kroz svijet nakon oko 1.4 s.
`[StartPlacer] start at marker 17 of 24` se uredno ispiše, dakle marker je nađen i izbor je
napravljen, ali auto tamo nije.

**Šta je izmjereno.** Dva zapažanja zajedno lociraju grešku:

- Na **seedu 1** auto završi na `(30.675788, 0)`, što je tačno checkpoint 0 tog seeda, na devet
  cifara, a 53.8 m od markera 17 koji je log prijavio. Auto se nikad nije pomjerio sa pozicije
  koju mu je scena dala.
- Na **seedu 37**, poslije pada, **isti** `ResetToSpawn` ga korektno vrati na marker 17 uz
  pomak od 0.95 m.

Ista metoda, suprotan ishod. Razlika je **kada**: poza upisana prije prvog fizičkog koraka se
odbaci, jer se autorska transformacija tijela commita kad se fizika inicijalizuje, a to je
poslije svih `Start()` poziva. Isti upis iz `FixedUpdate` ostane. Zato je reset zbog izlaska van
granica uvijek radio, a samo početno postavljanje nije.

**Zašto je bilo skoro nevidljivo.** Scena parkira auto tačno na prvi checkpoint **seeda 1**, a to
je i podrazumijevani seed u `TrackBuilder`. Na seedu 1 se auto vrati na svoj put i sve izgleda
ispravno postavljeno. Svaki drugi seed ga vrati izvan **svoje** staze. Seed 37 ide po x samo do
25.51, a auto stoji na 30.68, dakle oko 5 m iza kraja staze.

**Popravka, dvije stvari.** `StartPlacer` postavlja auto u prvom `FixedUpdate` umjesto u
`Start()`. `CarController.ResetToSpawn` upisuje pozu na **Rigidbody**, ne samo na Transform, uz
privremeno gašenje interpolacije preko teleporta: uz `RigidbodyInterpolation.Interpolate` tijelo
drži pozu i vodi Transform, pa je upis samo u Transform ionako bio pogrešan bez obzira na trenutak.

**Posljedica koju vrijedi zapisati.** Ovo je bilo tiho oboriti cijeli M3. Trening počinje
randomizovanim startom po lapu (C12), a svaki takav start bi vraćao auto na jedno te isto mjesto
sa seeda 1. Agent bi učio jednu tačku staze, epizode bi počinjale identično, i mjera koja to
otkriva ne postoji jer trening mjeri upravo one epizode iz kojih je memorizacija nastala.

---

## Šta ovaj feature svjesno NE rješava

- Nagrađivanje i trening. To je M3.
- Vizuelni izgled staze preko onoga što je potrebno da se vidi gdje je put.
- Pravci na stazi (C9), ostavljeno kao moguće proširenje.
- Steering iznad 0.789 (C2), fizički nedostižan uz izabranu marginu i tako se i izvještava.
