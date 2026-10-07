# Open House Demo

En terminaldemo til en cybersikkerhedsopstilling. Programmet viser et simuleret
forløb med dataudtræk, filoverførsel, alarmer og blokering. Farvede logs,
progressbarer og grafer opdateres løbende, og forløbet gentager automatisk hvert
tredje minut. Det kræver kun Python 3.8 eller nyere og ingen ekstra pakker.

## Start på Kali Linux

Hent repositoriet én gang, eller kopiér det fra en USB-nøgle:

```bash
git clone https://github.com/fisterloegsovs/openHouseDemo.git
cd openHouseDemo
python3 demo.py
```

Har du allerede klonet projektet, kører du `git pull --ff-only` i projektmappen.
Efter hentning kan demoen køre helt offline. Brug terminalens fuldskærmstilstand
(ofte F11), en mørk baggrund og en skriftstørrelse, der kan læses på afstand.

## Forskellige visninger på forskellige PC'er

Kør én kommando på hver maskine, fra projektmappen:

| PC | Kommando | Visning |
| --- | --- | --- |
| 1 | `python3 demo.py --mode overview --station 1` | Hele hændelsesforløbet og logs |
| 2 | `python3 demo.py --mode extract --station 2` | Navne, demo-id'er og dataudtræk |
| 3 | `python3 demo.py --mode transfer --station 3` | Filer, progressbarer og trafikgraf |
| 4 | `python3 demo.py --mode soc --station 4` | Sikkerhedsalarmer, blokering og inddæmning |
| 5 | `python3 demo.py --mode matrix --station 5` | Animeret Matrix-effekt |

Programmerne bruger computerens ur til at placere sig i samme forløb. De behøver
ingen indbyrdes netværksforbindelse. Med ens `--duration` og korrekt indstillede
ure følger skærmene samme hændelse, også når de startes på forskellige tidspunkter.
Standardvarigheden er 180 sekunder; eksempelvis giver `--duration 300` fem minutter.

En ekstra maskine kan vise `btop` separat. Dets tal er maskinens faktiske aktivitet;
alle grafer og tal i denne demo er simulerede.

## Betjening

- **1–5:** Skift mellem de fem visninger.
- **P** eller **mellemrum:** Pause eller fortsæt.
- **R:** Start forløbet forfra på denne maskine.
- **Q** eller **Ctrl+C:** Afslut og gendan terminalen.

Pause og lokal genstart ændrer denne maskines placering i forløbet. Genstart
programmet for at følge det fælles ur igen. Terminalen skal være mindst 62
kolonner bred og 22 linjer høj; 100 × 32 eller større giver bedre plads.
Visningen tilpasser sig automatisk, når vinduets størrelse ændres.

## Windows

Installér Python 3.8 eller nyere, kopiér/hent projektet, og åbn projektmappen i
Windows Terminal eller PowerShell. Kør eksempelvis:

```powershell
py -3 demo.py --mode soc --station 4
```

De samme argumenter og taster virker her. Hvis bloktegn vises forkert, tilføj
`--ascii`. Farver kan slås fra med `--no-color`. Windows-understøttelsen er
implementeret med standardbiblioteket; den er endnu ikke testet på en Windows-PC.

## Forløbet og demo-data

Forløbet går fra kortlægning til udtræk af 500 personposter, arkivering og en
simuleret overførsel. SOC opdager aktiviteten og blokerer overførslen ved 78 %.
Derefter vises isolering og inddæmning, før næste forløb starter.

Der sendes ingen data, køres ingen eksterne kommandoer, scannes ingen værter og
oprettes ingen arkiver. Værtsnavne, filstørrelser, SQL-tekst, trafik og alarmer
er visuelle effekter. `navne.json` læses lokalt og ændres ikke af demoen.
CPR-felter vises som `******-****`; der genereres ingen CPR-numre.

Navnene er tilfældigt kombinerede fra indbyggede navnelister, ikke hentet fra
personregistre eller officielle lister over godkendte navne. De kan tilfældigvis
matche rigtige personer. Alle skærme er mærket som simulation med fiktive data.

## Kontrol og test

```bash
python3 -m unittest -v
python3 demo.py --mode transfer --frames 1 --no-color
python3 demo.py --mode soc --duration 20 --once
```

Den første kommando tester hændelsesforløbet, layout, data og CLI. Den anden
skriver ét skærmbillede uden at kræve en interaktiv terminal. Den tredje kræver
en terminal og kører ét fuldt, forkortet forløb fra begyndelsen til afslutningen.

## Generér data

Kør fra repositoriets mappe:

```bash
python3 generer.py
```

Kommandoen skriver `navne.csv` og `navne.json` ved siden af scriptet og erstatter
eventuelle eksisterende filer med de samme navne. Et fast seed giver samme
datasæt ved hver kørsel.

- `navne.csv`: semikolonsepareret CSV i UTF-8 med BOM til brug i eksempelvis Excel.
- `navne.json`: UTF-8 JSON, som terminaldemoen læser.

Hver post indeholder `demo_id`, `fornavn`, `mellemnavn`, `efternavn` og
`fuldt_navn`. Mellemnavnet kan være tomt.
