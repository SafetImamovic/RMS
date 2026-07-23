# M1 — Statistički izvještaj (auto-generisan)

## Integritet
- [track1] rows=10,615 images=31,845 expected=31,845 -> OK; unresolved_rows=0 (sample 0/500)
- [track2] rows=21,828 images=65,484 expected=65,484 -> OK; unresolved_rows=0 (sample 0/500)
- [combined] rows=32,443 images=97,329 expected=97,329 -> OK; unresolved_rows=0 (sample 0/500)

## Identitet kolona (iz statistike)
- kol 4: steering (min=-1.000, max=1.000, %neg=23.5, %nula=58.6) — only negative-capable column (min=-1.000, 23.5% negative) -> steering (left turns)
- kol 5: throttle (min=0.000, max=1.000, %neg=0.0, %nula=50.6) — remaining [0,1] column with positive values (max=1.00) -> throttle
- kol 6: brake (min=0.000, max=1.000, %neg=0.0, %nula=94.6) — [0,1] column, mostly zero (94.6% zero) -> brake
- kol 7: speed (min=0.000, max=21.949, %neg=0.0, %nula=0.0) — non-negative with large magnitude (max=21.95) -> speed

## Deskriptivna statistika
- **steering**: n=32,443 mean=-0.0209 disperzija=0.1515 std=0.3892 min=-1.000 max=1.000 P95=0.800 P99=1.000
- **speed**: n=32,443 mean=10.2114 disperzija=10.6855 std=3.2689 min=0.000 max=21.949 P95=15.275 P99=17.486
- **|delta steering|**: n=32,441 mean=0.1112 disperzija=0.0385 std=0.1963 min=0.000 max=1.000 P95=0.550 P99=1.000

## Fit steeringa (kontinualni interior)
- tačkaste mase: 0 (pravo)=58.6%, -1 (puni lijevo)=4.2%, +1 (puni desno)=3.4%, interior=33.8%
- AIC (interior): norm=14602, laplace=16498, uniform=14079
- pobjednik: uniform, params=(-0.95, 1.9)
- χ²=2710.6 dof=27 kritično=40.1 p=0 → ODBACI (α=0.05)
- KS: D=0.0961 p=1.46e-88

## Kalibracija za Unity (DESIGN §4.4/§4.5)
- steering raspon (sirovi): (-1.0, 1.0)
- steering raspon (robustan P1–P99): (-1.000, 1.000)
- prag |Δsteering| (P95): 0.550
- brzina raspon (min–P99): (0.00, 17.49)
- brake: 94.6% nula (rijetko aktivna)
