# Open House Terminal Shows

To **separate terminalprogrammer** til en cybersikkerhedsopstilling:

- **Red team — `red_team.py`:** Et grønt hacker-show med root-console,
  sessions, navneudtræk, hex-buffers, progressbarer og filoverførsler.
- **Blue team — `blue_team.py`:** En cyanfarvet SOC-terminal med overvågning,
  røde alarmer, trafik, bevismateriale og hændelseshåndtering.

Hvert program har egne visninger og sit eget simulerede forløb. Der er ingen
menu, som skifter mellem holdene. Panelerne fylder hele terminalens højde og
bredde: én kolonne på smalle vinduer, to på almindelige vinduer og tre på brede
skærme. Logs og buffers fortsætter med at bevæge sig mellem faserne.

Begge programmer kræver kun **Python 3.8 eller nyere**, ingen ekstra pakker.
Efter hentning kan de køre helt offline.

## Hent eller opdater på Kali Linux

```bash
git clone https://github.com/fisterloegsovs/openHouseDemo.git
cd openHouseDemo
```

Har du allerede projektet, kører du `git pull --ff-only` i projektmappen.
Brug terminalens fuldskærmstilstand (ofte F11) og en skriftstørrelse, der kan
læses på afstand. Programmerne aflæser terminalens faktiske størrelse og
tilpasser sig automatisk ved ændringer. En enkelt kolonne i højre kant er
reserveret for at undgå, at terminalen scroller.

## Red team

![Eksempel på red-team-terminalen](assets/red-team.png)

```bash
python3 red_team.py
```

Vælg forskellige visninger på forskellige maskiner:

| PC | Kommando | Visning |
| --- | --- | --- |
| 1 | `python3 red_team.py --mode overview --station 1` | Root-session, buffers og overførsler |
| 2 | `python3 red_team.py --mode extract --station 2` | Personregister med opdigtede navne |
| 3 | `python3 red_team.py --mode transfer --station 3` | Filer, progressbarer og pakkestrøm |
| 4 | `python3 red_team.py --mode recon --station 4` | Fiktive værter, porte og sessions |
| 5 | `python3 red_team.py --mode matrix --station 5` | Matrix-effekt over hele skærmen |

Forløbet går fra kortlægning til sessions, udtræk af 500 navne, arkivering og
en fuldført overførsel. Der vises ingen SOC-respons i dette program.
`demo.py` fungerer stadig som en genvej til red-team-programmet.

## Blue team

![Eksempel på blue-team-terminalen](assets/blue-team.png)

```bash
python3 blue_team.py
```

| PC | Kommando | Visning |
| --- | --- | --- |
| 6 | `python3 blue_team.py --mode overview --station 6` | SOC-overblik og sensorer |
| 7 | `python3 blue_team.py --mode alerts --station 7` | Alarmkø og korrelation |
| 8 | `python3 blue_team.py --mode traffic --station 8` | Trafik, flows og policy |
| 9 | `python3 blue_team.py --mode response --station 9` | Triage, blokering og isolering |
| 10 | `python3 blue_team.py --mode evidence --station 10` | Fiktive hex-buffers og bevismateriale |

Blue-team-forløbet går fra normal overvågning til afvigelser, kritiske alarmer,
blokering og inddæmning. Det kræver ikke navnedatasættet. De to hold har
selvstændige historier; de udveksler ingen data og påvirker ikke hinanden.

## Betjening og gentagelse

- **1–5:** Skift visning inden for det program, du har startet.
- **P** eller **mellemrum:** Pause eller fortsæt.
- **R:** Start forløbet forfra på denne maskine.
- **Q** eller **Ctrl+C:** Afslut og gendan terminalen.

Forløbene gentager automatisk hver 180. sekund. Tilføj eksempelvis
`--duration 300` for fem minutter. Programmerne bruger computerens ur, så
flere maskiner inden for samme hold kan vise samme fase uden netværksforbindelse.
Det kræver ens varighed og korrekt indstillede ure. Pause og lokal genstart
ændrer denne maskines fase; genstart programmet for at følge fælles tid igen.

Terminalen skal være mindst 62 kolonner bred og 22 linjer høj. 100 × 32 eller
større giver plads til flere paneler. Ved 150 kolonner får du seks paneler.

En ekstra maskine kan vise `btop` separat. Dets tal er maskinens faktiske
aktivitet; grafer og tal i disse shows er simulerede.

## Windows

Installér Python 3.8 eller nyere, kopiér/hent hele projektmappen, og åbn den i
Windows Terminal eller PowerShell:

```powershell
py -3 red_team.py --mode extract --station 2
```

På en anden maskine:

```powershell
py -3 blue_team.py --mode overview --station 6
```

Argumenterne og tasterne er de samme. Tilføj `--ascii`, hvis bloktegn eller
rammer vises forkert, eller `--no-color` for at slå farver fra. Windows er
understøttet i koden, men endnu ikke afprøvet på en Windows-PC.

## Demo-data

Alt er visuelle effekter: Der sendes ingen data, køres ingen eksterne kommandoer,
scannes ingen værter og oprettes ingen arkiver. Værtsnavne bruger `.invalid`,
og IP-adresser er fra dokumentationsområder. Hex-data er genererede visuelle
bytes, ikke indhold fra netværkstrafik eller rigtig kryptering.

Red team læser `navne.json` lokalt uden at ændre filen. Navnene er kombineret
fra indbyggede lister og kan tilfældigvis matche rigtige personer. CPR-felterne
vises som `******-****`; der genereres ingen CPR-numre. Alle visninger er
mærket med `SIMULATION / FIKTIVE DATA` nederst.

## Kontrol og test

```bash
python3 -m unittest -v
python3 red_team.py --mode extract --frames 1 --no-color
python3 blue_team.py --mode alerts --frames 1 --no-color
```

`--frames 1` skriver ét skærmbillede uden at kræve en interaktiv terminal.
Kør ét helt, forkortet forløb i en terminal med:

```bash
python3 red_team.py --duration 20 --once
```

Den samme kontrol kan udføres med `blue_team.py`.

## Generér nye navne

```bash
python3 generer.py
```

Kommandoen erstatter `navne.csv` og `navne.json` ved siden af scriptet.
Et fast seed giver samme 500 unikke navnekombinationer ved hver kørsel.
CSV-filen er semikolonsepareret UTF-8 med BOM, JSON-filen er UTF-8.
Hver post indeholder `demo_id`, `fornavn`, `mellemnavn`, `efternavn` og
`fuldt_navn`. Mellemnavnet kan være tomt.
