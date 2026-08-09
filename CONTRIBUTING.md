# CONTRIBUTING - git konvencije

Solo projekat, ali historija se vodi kao da je tim: git flow grane + atomic commiti.
Unity specifičnosti verzionisanja (šta se commita, .meta fajlovi, LFS) su u
[WORKFLOW.md](WORKFLOW.md) §3 - pročitati prije prvog commita.

## Grane (git flow)

```
main ──────●────────────────●──────▶   samo stabilna stanja (kraj milestone-a), tagovano
            \              /
develop ─────●──●──●──●──●──────────▶   integracija; uvijek "radi"
              \       /
feature/* ─────●──●──●                  jedna cjelina posla, kratkoživuća
```

| Grana | Pravilo |
|-------|---------|
| `main` | Nikad se ne radi direktno na njoj. Prima merge samo iz `develop`, na kraju milestone-a. Svaki merge se tagira: `v0.1-m1`, `v0.2-m2`... `v1.0` = predaja |
| `develop` | Integraciona grana. Direktan commit dozvoljen samo za trivijalne doc ispravke |
| `feature/<opis>` | Sav rad. Grana se iz `develop`, merga nazad sa `--no-ff` (čuva se granica feature-a u historiji) |
| `fix/<opis>` | Ispravke bugova, ista pravila kao feature |

Imenovanje: kratko, kebab-case, engleski: `feature/car-agent`,
`feature/bc-training`, `fix/checkpoint-order`, `feature/dataset-eda`.

```powershell
git switch develop
git switch -c feature/car-agent
# ... rad, commiti ...
git switch develop
git merge --no-ff feature/car-agent
git branch -d feature/car-agent
```

## Atomic commiti

Jedan commit = **jedna logička promjena** koja ostavlja projekat u konzistentnom
stanju. Test: možeš li commit opisati jednom rečenicom bez "i"? Ako ne - podijeli
(`git add -p` za djelimično stage-anje).

- ✅ `feat(unity): add checkpoint system with direction detection`
- ✅ `docs: add reward table to DESIGN.md`
- ❌ `feat: add checkpoints, fix car physics and update README` - tri commita
- ❌ `wip` / `changes` / `update` - ništa ne govori

Unity napomena: skripta + njen `.meta` + izmjena scene koja je koristi = jedna
logička promjena, ide zajedno. `.meta` fajl nikad ne smije ostati van commita
svog fajla.

## Format poruke (Conventional Commits)

```
<tip>(<scope>): <opis u imperativu, malim slovom, ≤50 znakova>

<tijelo - opciono: ZAŠTO, ne šta; wrap na 72>
```

| Tip | Kada |
|-----|------|
| `feat` | Nova funkcionalnost (skripta, notebook, model) |
| `fix` | Ispravka pogrešnog ponašanja |
| `docs` | Samo dokumentacija |
| `refactor` | Izmjena koda bez promjene ponašanja |
| `test` | Testovi |
| `chore` | Infrastruktura: .gitignore, verzije paketa, config |
| `exp` | Trening eksperiment (novi run-id, tjuniranje hiperparametara/rewarda) |

Scope (opciono): `unity`, `bc`, `eval`, `config`, `data`.

Primjeri:

```
feat(unity): add raycast observations to CarAgent

exp(config): raise smoothness penalty to 0.01

Agent oscillated on straights in ppo_car_v03; human data shows
near-zero steering variance on straight segments.
```

## Bez atribucije agenta

Poruka commita ne nosi `Co-Authored-By`, link na sesiju alata, niti bilo kakav drugi
trailer koji imenuje agenta. Isto vrijedi za opise pull requestova, tagove i unose u
`results/EXPERIMENTS.md`. Vlasnik repozitorija koji pokreće commit je jedini autor u
zapisu (Ustav, princip III).

Agent koji predlaže commit mora izostaviti taj trailer i onda kada mu vlastiti alat
nalaže da ga doda. Provjera nad cijelom istorijom:

```
git log --all --format='%h %s' --grep='Co-Authored-By'
```

Prazan izlaz je jedini prihvatljiv rezultat.

## Checklist prije commita

1. `git status` - samo očekivani fajlovi? Nema `Library/`, `data/`, `.venv/`?
2. Svaki novi fajl u `Assets/` ima svoj `.meta` u istom commitu?
3. Projekat konzistentan (Unity Console bez grešaka / testovi prolaze)?
4. Poruka po formatu, jedna logička promjena?
5. Binarni fajlovi otišli u LFS? (`git lfs ls-files` ih izlistava)
6. Poruka bez atribucije agenta - nema `Co-Authored-By` ni linka na sesiju?

## Ko commita

**Sve commite radi vlasnik repoa ručno.** AI asistent priprema fajlove i može
predložiti poruku commita, ali nikad ne izvršava `git commit` ni `git push`.
