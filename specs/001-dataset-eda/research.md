# Phase 0 Research: Dataset EDA (M1)

Odluke koje zatvaraju otvorena tehnička pitanja prije implementacije.

---

## Pojmovnik (pročitaj prvo)

Prostim jezikom, jer se koriste dolje:

- **Raspodjela (distribution)** — "oblik" podataka: gdje se gomilaju, koliko su raširene.
  Histogram je slika raspodjele; teoretska raspodjela je formula koja taj oblik opisuje.
- **Normalna** — zvonolika, simetrična ("Gaussova"). **Laplace** — isto simetrična ali
  oštrija na vrhu i sa težim repovima (više ekstrema). **Uniformna** — ravna, sve vrijednosti
  jednako vjerovatne. **Eksponencijalna / Erlang / gamma** — samo za pozitivne brojeve, pad
  udesno (npr. vremena čekanja, brzine).
- **Fit (prilagođavanje)** — nađi parametre teoretske raspodjele koji najbolje pokriju tvoje
  podatke. `scipy` to radi metodom max. vjerodostojnosti (MLE) — samo pozoveš `.fit()`.
- **χ² test saglasnosti (chi-square goodness-of-fit)** — brojka koja kaže koliko fit odstupa
  od podataka. Podijeliš podatke u binove, uporediš opaženo vs očekivano po binu. Ako je
  odstupanje veće od praga → **odbaci** (raspodjela ne valja); ako manje → **prihvati**.
- **KS test (Kolmogorov–Smirnov)** — drugi test istog cilja, ali bez binova: gleda najveći
  razmak između stvarne i teoretske "nakupljene" krive. **D statistic** = veličina tog
  najvećeg razmaka (manje = bolji fit). Koristimo ga kao **drugu provjeru** uz χ².
- **α (alfa)** — prag rizika, standardno 0.05 (5%). Ispod njega "prihvatamo", iznad "odbacujemo".
- **dof (stepeni slobode)** — tehnički broj koji χ² tabela traži; = broj binova − 1 − broj
  parametara koje smo fitovali. Treba ga tačno izračunati da test bude ispravan.
- **percentil (P95, P99...)** — vrijednost ispod koje pada tih % podataka. P95 od |Δsteering|
  = "granica ispod koje je 95% svih promjena volana"; iznad = nagli trzaj.
- **AIC** — brojka za rangiranje više kandidata; manji = bolji, kažnjava složenije raspodjele.
- **Δsteering (delta steering)** — koliko se volan promijenio od prošlog reda do sljedećeg.
  Mjeri **glatkoću** vožnje (mali Δ = glatko, veliki = trzaji).
- **Zero-inflation** — kad podaci imaju gomilu tačno-nula vrijednosti (kod nas ~79% steeringa
  = 0, prava vožnja). Nijedna glatka kriva to ne pokrije, pa nulu tretiramo zasebno.

---

## R1 — Koju raspodjelu fitujemo na steering

- **Prosto:** steering nije jedna kriva nego **mješavina**: tri tačkasta špica (0, −1, +1) +
  kontinualni dio između. Špiceve brojimo posebno, fitujemo samo kontinualni dio.
- **Odluka**: kandidati = **normal, laplace, uniform** (simetrične, dozvoljavaju negativne).
  Fitujemo **interior** (bez 0 i bez ±1), rangiramo po AIC, na pobjedniku radimo χ² + KS.
- **Zašto mješavina (ključno):** steering ima diskretne špiceve — **0** (prava vožnja),
  **−1** i **+1** (puni zaokret volana, zasićenje). Nijedna glatka kriva ne opisuje špic, pa
  ih izvještavamo kao zasebne vjerovatnoće (tačkaste mase) i fitujemo ostatak.
- **Zašto NE exponential/Erlang/gamma**: postoje samo za pozitivne brojeve, a steering ima
  negativne (volan lijevo). Bacamo ih odmah.

> **Stvarni nalaz (M1, combined dataset — ažurirano nakon implementacije):** mase su
> 0=58.6%, −1=4.2%, +1=3.4%, interior=33.8%. Na interioru **uniform** ima najbolji AIC
> (14079 < norm 14602 < laplace 16498), ali **χ² test odbacuje sve** (χ²≈2711 ≫ krit≈40,
> KS D≈0.096, p≈0) na α=0.05. Prvobitna pretpostavka (Laplace pobjeđuje) je **demantovana
> podacima**: interior je raširen preko opsega (track2 = razni uglovi krivina), nije
> zvonolik. **Zaključak:** ljudski steering ne prati standardnu raspodjelu → koristimo
> **empirijsku raspodjelu** kao referencu za poređenje agenata (M5). Odbacivanje je validan,
> koristan nalaz — nije neuspjeh.

## R2 — Kako računamo χ² (binovi i dof)

- **Prosto:** podijelimo steering u ~20-30 kanti, uporedimo koliko ih stvarno padne u svaku
  vs koliko bi teoretski trebalo, saberemo odstupanja.
- **Odluka**: χ² se računa na **interioru** (špicevi 0 i ±1 su van fita — vidi R1). Binovi tako
  da **svaka očekivana kanta ima ≥5 vrijednosti** (spoji rijetke repove). dof = binovi − 1 −
  broj fitovanih parametara. Izvještavamo: χ² vrijednost, dof, kritičnu vrijednost na α, i
  odluku prihvati/odbaci.
- **Zašto ≥5 po binu**: to je pravilo koje čini χ² test ispravnim; sa premalim kantama test laže.

## R3 — Čemu KS test

- **Prosto:** druga, nezavisna provjera fita; ako se i χ² i KS slože, jači zaključak.
- **Odluka**: KS (`scipy.stats.kstest`) na tijelu raspodjele, izvještavamo D statistic + p-value
  uz χ² odluku.
- **Napomena**: KS p-value je malo preoptimističan kad parametre vadimo iz istog uzorka — to
  kažemo otvoreno, ne skrivamo.

## R4 — Kako definišemo Δsteering (glatkoća)

- **Prosto:** razlika volana između dva uzastopna reda, ali samo unutar iste staze.
- **Odluka**: `Δ = steering[i] − steering[i−1]`, računato **unutar jedne staze** (nikad preko
  spoja track1→track2 u combined fajlu). Prag naglog trzaja za reward (DESIGN §4.5) = **P95** od
  |Δsteering|.
- **Zašto per-staza**: combined fajl spaja dva snimka; razlika preko spoja bi izmislila lažan
  ogroman skok. P95 hvata stvarne oštre korekcije bez kažnjavanja normalne vožnje.

## R5 — Raspon steeringa → Unity akcije (DESIGN §4.4)

- **Prosto:** izmjerimo koliko čovjek okreće volan, pa preporučimo raspon za agenta; koristimo
  P1–P99 umjesto krajnjih min/max.
- **Odluka**: izvještavamo min/max i P1/P99. Preporuka: Unity steering mapirati na **P1–P99**
  raspon, ne sirovi min/max. Tačne ± stepene bira M2; M1 daje mjeru.
- **Zašto P1–P99**: sirovi min/max (−1..1) su rijetke saturacije; P1–P99 je stvarni radni raspon.

## R6 — Kako provjeravamo slike

- **Prosto:** provjerimo da putanje iz CSV-a stvarno pokazuju na postojeće fajlove, na uzorku;
  ne otvaramo same slike.
- **Odluka**: provjeri postojanje na **seeded uzorku** (~500 redova × 3 kamere) + puni broj
  neriješenih redova. Bez dekodiranja piksela (to je BC/M4).
- **Zašto uzorak**: provjera svih ~194k fajlova je spora i nepotrebna za M1 (nama treba
  integritet formata, ne sadržaj slika).

## R7 — Primarni izvor i dvostruko brojanje

- **Prosto:** glavna analiza na spojenom datasetu; staze zasebno samo za poređenje track1 vs
  track2. Uvijek jasno koji izvor gledamo.
- **Odluka**: primarni = combined `dataset/dataset/`. track1/track2 učitavamo zasebno samo za
  poređenje i za per-staza Δsteering. Svaki grafik kaže koji izvor sažima.
- **Zašto**: combined duplira slike obje staze; miješanje "combined" i "po stazi" brojki bi
  dvaput brojalo iste podatke.

## R8 — Ponovljivost

- **Prosto:** jedan config fajl sa seed-om i putanjama da svako pokretanje da identične brojeve.
- **Odluka**: `config.py` drži `SEED=42`, `ALPHA=0.05`, putanje, izlazne foldere, imena kolona.
  Sva slučajnost ide preko seeded numpy generatora. Brojke se pišu u
  `results/eda/m1_stats.json`; notebook priča priču. `requirements.txt` zaključava verzije.
- **Zašto**: centralizovan seed/α/putanje = re-run daje iste brojeve (kriterij SC-006), lako za
  demonstrirati na odbrani.
