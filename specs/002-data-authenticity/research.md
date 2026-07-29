# Phase 0 Research: Data Authenticity & Integrity Checks

Odluke koje zatvaraju otvorena tehnička pitanja prije implementacije.
Isti stil kao M1 (`specs/001-dataset-eda/research.md`): *Prosto* → *Odluka* → *Zašto*.

---

## Pojmovnik (pročitaj prvo)

- **Friziranje podataka** — namjerno ili slučajno mijenjanje podataka tako da izgledaju bolje,
  urednije ili "poželjnije" nego što jesu. Primjeri: izbaciš loše snimke, iskopiraš dobar dio
  da ih ima više, prelijepiš dva snimka u jedan, ručno "popraviš" vrijednosti.
- **Nulta hipoteza (H₀)** — tvrdnja koju testiramo, uvijek oblika "nema efekta / sve je kako
  očekujemo". Test može samo **odbaciti** H₀ ili **ne odbaciti** — nikad je "dokazati".
- **Očekivani potpis (expected signature)** — kako bi podaci izgledali *da* je manipulacija
  urađena. Bez toga provjera ne znači ništa: ne možeš reći da je nešto sumnjivo ako nisi
  unaprijed rekao šta bi sumnjivo izgledalo.
- **Rešetka (lattice)** — pravilna mreža dozvoljenih vrijednosti, npr. …, −0.10, −0.05, 0.00,
  0.05, … Razmak (spacing) je korak rešetke.
- **Diskretna vs kontinualna varijabla** — diskretna ima konačan skup mogućih vrijednosti
  (rešetka), kontinualna može biti bilo koji realan broj u opsegu.
- **Pogrešna specifikacija modela (misspecification)** — kad na podatke primijeniš model koji
  po svojoj prirodi ne može odgovarati. Npr. glatka kriva na rešetkaste podatke. Test tada
  odbacuje model, ali to ne govori ništa o podacima — govori o modelu.
- **χ² test saglasnosti (goodness-of-fit)** — poredi opažene frekvencije po kategorijama sa
  očekivanim po H₀. Za **diskretnu** varijablu kategorije su same vrijednosti — nema binovanja,
  nema proizvoljnog izbora. Zato je χ² ovdje "domaći teren".
- **χ² test homogenosti** — isti račun, drugo pitanje: da li dva uzorka dolaze iz iste
  raspodjele. Tabela kontingencije: redovi = staze, kolone = nivoi rešetke.
- **MAD (median absolute deviation)** — robusna mjera rasipanja; za razliku od standardne
  devijacije, nekoliko ekstremnih vrijednosti je ne pokvari. Koristimo je za detekciju
  outliera jer bi upravo outlieri (friziranje) inače naduvali granicu i sakrili sami sebe.

---

## A1 — Šta je "jedan snimak" i gdje se smije mjeriti kontinuitet vremena

- **Prosto:** vrijeme teče samo unutar jednog snimanja. Combined fajl spaja dva snimka, pa
  vrijeme na spoju "skače unazad" — to nije greška u podacima nego posljedica spajanja.
- **Odluka**: sesija se izvodi iz **prefiksa putanje slike** u CSV-u (`Desktop\track1data\...`
  vs `Desktop\track2data\...`). Sve vremenske provjere rade **po sesiji**, nikad preko spoja.
  Combined izvor se ne izuzima iz analize — segmentira se.
- **Zašto**: track2 je snimljen **18:05–18:31**, track1 **19:25–19:38**, istog dana
  (2019-04-02), a combined ih redom stavlja track1 pa track2. Naivna provjera nad combined
  fajlom prijavila bi skok od ≈ −80 minuta i "otkrila friziranje" u savršeno ispravnom
  datasetu. Ovo je isto ograničenje koje je M1 primijenio na Δsteering (M1 R4) — ista zamka,
  drugi kontekst.

## A2 — Prag za "rupu" u snimku

- **Prosto:** koliko razmaka između dva kadra je previše da bi bio normalan.
- **Odluka**: prag se izvodi **iz podataka**, ne pogađa: `gap ⇔ Δt > 5 × median(Δt)` po sesiji.
  Izvještavamo i stepenaste brojeve (>2×, >5×, >1 s) da čitalac vidi cijeli rep, i sam median
  i implicirani broj kadrova u sekundi.
- **Zašto 5×**: pri opaženih ~14 kadrova/s (median Δt ≈ 0.070 s) 5× median znači da je
  propušteno ≈ 4–5 uzastopnih kadrova. Jedan preskočen kadar je normalno opterećenje
  simulatora; pet uzastopnih je događaj. Prag vezan za median se sam prilagođava ako se
  brzina snimanja razlikuje po stazi, pa nije "magičan broj" nego pravilo.
- **Očekivani potpis friziranja**: rezanje sredine snimka pravi **jednu veliku rupu**;
  spajanje dva snimka pravi rupu **i** skok u sadržaju; brisanje pojedinačnih "ružnih" redova
  pravi **mnogo malih rupa** na ≈ 2× median. Zato izvještavamo raspodjelu Δt, ne samo maksimum.

## A3 — Kako detektujemo rešetku i koja je tolerancija

- **Prosto:** pogledamo sve različite vrijednosti kolone; ako su sve umnošci istog koraka,
  kolona je rešetkasta.
- **Odluka**: kandidat za korak = **najmanja pozitivna razlika** između susjednih sortiranih
  jedinstvenih vrijednosti. Kolona je rešetkasta ako je svaka vrijednost cijeli umnožak koraka
  unutar tolerancije `atol = 1e-8` (apsolutna, `rtol = 0`). Klasifikacija: **diskretna** ako
  broj različitih vrijednosti ≤ 100 **i** rešetka se poklopi; inače **kontinualna**.
  Tolerancija se ispisuje u izvještaju.
- **Zašto tolerancija**: 0.05 nije tačno predstavljiv u binarnom zapisu; traženje tačne
  jednakosti bi lažno proglasilo rešetku nepostojećom. Tolerancija mora biti daleko ispod
  stvarnog koraka (0.05) da ne bi spojila dva susjedna nivoa.

> **Dopuna A3.1 (implementacija, 2026-07-29): `LATTICE_ATOL` 1e-8 → 1e-6.**
> Prvobitna vrijednost `1e-8` je izvedena iz probe koja je vrijednosti zaokruživala. Nad
> **stvarnim** logom pokazalo se da simulator svaki nivo sa |steering| > 0.45 zapisuje sa
> sistematskim pomakom do **2e-7** (`-0.9500002`, `0.5000001`, …), dok su ±0.7 i ±1.0
> tačni. To je način na koji simulator **piše** kolonu, a ne manipulacija njome — pri
> `1e-8` provjera bi prijavila **18 ispravnih nivoa** kao friziranje, tj. tačno onu lažnu
> uzbunu zbog koje ovaj feature postoji (A10, zadnji red). `1e-6` apsorbuje pomak a ostaje
> 50.000× ispod koraka 0.05.
> Da tolerancija ne bi postala mjesto za skrivanje, `GranularityProfile` sada **uvijek**
> izvještava `max_residual` — stvarno najveće odstupanje od rešetke (2.0e-7), pa čitalac
> vidi koliko je tolerancije potrošeno.

> **Dopuna A3.2 (implementacija): korak rešetke = *najčešća*, ne najmanja razlika.**
> A3 predlaže najmanju pozitivnu razliku kao kandidata za korak. To je tačno dok je kolona
> netaknuta, ali je upravo ta statistika koju friziranje uništava: jedna vrijednost
> pomjerena za 0.023 čini najmanju razliku 0.023, cijela kolona prestane ličiti na rešetku,
> i **krivac se sakrije umjesto da bude imenovan**. Najčešća razlika preživi nekoliko
> izmjena, pa se vrijednosti van rešetke mogu pokazati pojedinačno — a to je nalaz koji nam
> treba. Klasifikacija (diskretna ⇔ ≤ 100 različitih **i** rešetka se poklopi) ostaje kako
> je A3 odlučio.
- **Zašto prag 100**: opaženo je 40–41 nivo za steering naspram 5.090–21.743 za throttle i
  speed — razlika je tri reda veličine, pa granica nije osjetljiva na tačnu vrijednost. Prag
  je izložen kao imenovana konstanta, ne zakopan u kod.
- **Očekivani potpis friziranja**: vrijednosti **van** rešetke u inače rešetkastoj koloni znače
  da je neko računao nove vrijednosti (glađenje, interpolacija, augmentacija) i upisao ih
  nazad. To je najjači pojedinačni dokaz koji ova provjera može dati.

## A4 — Koje nulte hipoteze testiramo na steeringu

Tri testa, tri različita pitanja. Svaki ima *očekivani potpis* — bez toga je gola brojka.

**T1 — χ² saglasnosti: H₀ = steering je uniforman preko 41 nivoa rešetke.**
- Očekujemo **odbacivanje**, ubjedljivo.
- **Zašto to uopšte testiramo ako znamo ishod**: ovo je test protiv **izmišljenih podataka**.
  Da je neko generisao steering slučajnim generatorom (najčešći način da se "napravi" dataset),
  raspodjela bi bila bliska uniformnoj i H₀ se **ne bi** odbacila. Ubjedljivo odbacivanje je
  pozitivan nalaz: podaci imaju strukturu koju uniformni generator ne proizvodi.

**T2 — χ² saglasnosti: H₀ = raspodjela je simetrična, P(+k) = P(−k) za svaki nivo k.**
- Testira se **po stazi**, ne na spojenim podacima.
- **Očekivano**: track1 odbacuje (odnos lijevo/desno 5.375), track2 vjerovatno ne (1.052).
- Odbacivanje na track1 je **objašnjivo** (zatvorena petlja vožena u jednom smjeru), ne
  sumnjivo — vidi A6.

**T3 — χ² homogenosti: H₀ = obje staze dijele istu raspodjelu steeringa.**
- Tabela kontingencije 2 × (zajednička podrška).
- **Očekujemo odbacivanje** (staze se stvarno razlikuju: brdska vs ravna).
- **Zašto je koristan**: da su dvije "staze" u stvari ista vožnja iskopirana i preimenovana
  (klasično naduvavanje veličine dataseta), H₀ se **ne bi** odbacila. Odbacivanje potvrđuje da
  su to dva različita snimka, a ne jedan udvojen.

- **Zašto χ², a ne KS**: KS pretpostavlja kontinualnu raspodjelu; na rešetkastim podacima ima
  vezane vrijednosti (ties) i p-vrijednost mu nije tačna. Za diskretnu varijablu χ² je ispravan
  alat. Ovo je i formalni razlog zašto M1 KS provjera na steeringu nije bila pouzdana.

## A5 — Pravilo za rijetke kategorije i dof

- **Prosto:** ako se neki nivo pojavljuje premalo puta, χ² laže; takve nivoe spajamo.
- **Odluka**: zadržavamo M1 pravilo `CHI2_MIN_EXPECTED_PER_BIN = 5`. Nivoi sa očekivanom
  frekvencijom < 5 spajaju se **simetrično od repova ka centru** (najveći |steering| prvi), da
  spajanje ne pokvari test simetrije T2. Izvještavamo dof **nakon** spajanja i koliko je nivoa
  spojeno.
- **Zašto simetrično**: kod T2 (simetrija) spajanje mora tretirati +k i −k jednako, inače samo
  spajanje uvodi asimetriju i test mjeri vlastitu grešku.
- **Nivo koji se nikad ne pojavi** (npr. +0.95 na track1) ostaje u zajedničkoj podršci za T3 sa
  opaženom frekvencijom 0 — ne briše se — ali ulazi u spajanje repova kao i svaki drugi rijedak
  nivo.

## A6 — Kako razlikujemo "objašnjivo" od "sumnjivo"

- **Prosto:** nalaz je dokaz friziranja samo ako nemamo mehanizam koji ga objašnjava.
- **Odluka**: svaki nalaz nosi **verdikt** sa tri polja: H₀, ishod, i klasifikaciju
  `explainable` (uz imenovan mehanizam) ili `unexplained`. Nalaz može biti objašnjiv **i** i
  dalje štetan za kasniji milestone — tada nosi i posljedicu i mjeru ublažavanja.
- **Dva radna primjera koja moraju proći kroz ovaj okvir:**

| Nalaz | Izgleda kao | Mehanizam koji objašnjava | Verdikt | Posljedica |
|---|---|---|---|---|
| track1 kočnica ima **1** jedinstvenu vrijednost (0) u svih 10.615 redova | obrisana kolona | staza 1 je ravna petlja; vozač nikad nije zakočio | explainable | M1 je nad spojenim podacima prijavio `brake_is_dead: false` — po stazi je **mrtva**; per-staza izvještavanje obavezno |
| track1 lijevo/desno = **5.375** | selektivno izbačeni desni zaokreti | zatvorena petlja vožena u jednom smjeru (suprotno kazaljci) | explainable | ozbiljan rizik za M4: BC model naučen na track1 vuče lijevo na pravcu → mjera: horizontalno ogledanje slike uz promjenu znaka steeringa |

- **Zašto ovako**: bez ovog koraka izvještaj je lista strašnih brojeva koja profesoru ne
  dokazuje ništa, a projekat izlaže optužbi da je proglasio ispravan dataset frizuranim.

## A7 — Fizička uvjerljivost promjene brzine

- **Prosto:** brzina se ne može promijeniti proizvoljno mnogo između dva susjedna kadra.
- **Odluka**: računamo **implicirano ubrzanje** `Δspeed / Δt` po sesiji i ocjenjujemo ga
  **relativno**, robusnim pravilom: outlier ⇔ `|a − median(a)| > 5 × MAD(a)`. Izvještavamo
  median, MAD, maksimum i broj outliera. **Ne** tvrdimo apsolutnu fizičku granicu.
- **Zašto ne apsolutna granica (npr. 1 g)**: jedinica kolone `speed` u Udacity simulatoru nije
  dokumentovana (nije potvrđeno da su m/s, mph ili interne jedinice). Tvrdnja "ubrzanje je
  ispod 1 g" tražila bi pretpostavku o jedinici koju ne možemo potvrditi — a lažna preciznost
  je gora od poštene relativne mjere. Relativno pravilo hvata ono što nas zanima: **skokove
  koji odudaraju od ostatka istog snimka**, što je upravo potpis spajanja ili brisanja redova.
- **Zašto MAD, a ne standardna devijacija**: nekoliko ubačenih skokova naduva standardnu
  devijaciju toliko da granica pređe preko njih i test prestane da ih vidi. MAD to ne radi.

## A8 — Tri vrste duplikata (i zašto se broje odvojeno)

- **Odluka**: brojimo odvojeno:
  1. **identičan cijeli red** — kopiranje redova radi naduvavanja veličine;
  2. **ponovljena putanja slike** — isti kadar upisan više puta (ista slika, možda druge
     brojke);
  3. **ponovljena četvorka mjerenja** (steering, throttle, brake, speed) uz **različitu** sliku
     — očekivano i bezopasno kod rešetkastog steeringa, jer je prostor vrijednosti mali.
- **Zašto odvojeno**: (1) i (2) su potpis manipulacije, (3) je posljedica diskretizacije.
  Skupno brojanje bi ih pomiješalo i dalo lažnu uzbunu — na track1 ima 12 takvih četvorki, što
  je pri 40 nivoa steeringa statistički očekivano.

## A9 — Gdje idu rezultati i šta se NE dira

- **Odluka**: novi fajlovi `results/eda/authenticity_report.md` i
  `results/eda/authenticity_stats.json`. **`m1_report.md` i `m1_stats.json` se ne
  regenerišu i ne mijenjaju.**
- **Zašto**: M1 izlazi su pregledani i commitovani artefakti; tiho regenerisanje bi pokidalo
  vezu između onoga što je pregledano i onoga što stoji u repozitoriju. Ispravke M1 zaključaka
  idu u **prozu** (M1 `research.md` R1/R2, `DESIGN.md`), sa naznakom da potiču iz ovog feature-a.
- **Napomena o imenovanju**: fajlovi se **ne** zovu `m2_*`. M2 je Unity milestone
  (`DESIGN.md` §9); ovaj feature nije milestone i ne smije mu otimati ime.

## A10 — Kako dokazujemo da provjere stvarno rade

- **Prosto:** provjera koja je vidjela samo ispravne podatke nije dokazano da išta hvata.
- **Odluka**: za svaku porodicu provjera postoji **namjerno frizuran ulaz** u testovima, malen
  i sintetički, gdje je tačan odgovor poznat po konstrukciji:

| Porodica | Frizuran ulaz | Očekivano |
|---|---|---|
| kontinuitet vremena | izmiješan redoslijed redova | prijavljena narušena monotonost |
| rupe | izbačen blok od 50 uzastopnih redova | prijavljena rupa iznad praga |
| duplikati | blok redova iskopiran i dodat | prijavljeni identični redovi i ponovljene slike |
| rešetka | jedna vrijednost pomjerena za 0.023 | kolona više nije rešetkasta / prijavljena vrijednost van rešetke |
| uvjerljivost | jedan red sa nemogućim skokom brzine | prijavljen outlier ubrzanja |
| segmentacija | sintetički spoj dvije sesije | kontinuitet se **ne** računa preko spoja (nema lažne uzbune) |

- **Zašto i zadnji red**: on testira da provjera **ne** prijavljuje grešku tamo gdje je nema —
  lažna uzbuna je jednako ozbiljna kao propušteni nalaz, jer bi značila da smo ispravan dataset
  proglasili frizuranim.

## A11 — Šta se mijenja u već napisanim dokumentima

- **Odluka**: tri ispravke, sve u prozi, sve traceable na ovaj feature:
  1. **M1 `research.md` R1/R2** — dopuna: steering je rešetkast (korak 0.05, 41 nivo); fit
     kontinualnih gustina na interior je bio **pogrešno specifikovan**, pa je χ² odbacivanje
     bilo posljedica modela, a ne neobičnosti podataka. Zaključak "ne prati standardnu
     raspodjelu → koristi empirijsku" **ostaje ispravan**, ali dobija tačan razlog.
  2. **`DESIGN.md`** — per-staza napomena o mrtvoj kočnici na track1 tamo gdje sada stoji samo
     spojena brojka; i napomena za M5 (tačka 3).
  3. **`DESIGN.md` §7 (evaluacija)** — forward note: RL agent emituje **kontinualan** steering,
     ljudska referenca je **rešetkasta**. Poređenje raspodjela mora to uzeti u obzir (npr.
     kvantizovati agentov izlaz na istu rešetku prije poređenja) — inače poređenje mjeri razliku
     u rezoluciji zapisa, a ne razliku u vožnji.
- **Zašto se M1 kalibracija ne mijenja**: percentili (P95 od |Δsteering| = 0.55, opseg
  P1–P99 = (−1, 1)) su **redoslijedne** statistike — računaju se iz sortiranih vrijednosti i
  potpuno su nezavisne od toga da li varijablu zovemo diskretnom ili kontinualnom. FR-018
  ipak traži da to provjerimo i eksplicitno izjavimo, umjesto da pretpostavimo. Uzgred:
  0.55 = tačno 11 koraka rešetke, što je prijatna potvrda da prag pada na dozvoljenu vrijednost.
