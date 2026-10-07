# Open House Demo

Datasæt og navnegenerator til en simuleret cybersikkerhedsopstilling.
Projektet indeholder aktuelt 500 unikke navnekombinationer med typiske danske
fornavne, mellemnavne og efternavne. Skærmdemoen er endnu ikke implementeret.

Navnene er tilfældigt kombinerede fra indbyggede navnelister, ikke hentet fra
personregistre eller officielle lister over godkendte navne. De kan tilfældigvis
matche rigtige personer. Datasættet indeholder demo-id'er og ingen CPR-numre.

## Generér data

Python 3 er den eneste afhængighed. Kør fra repositoriets mappe:

```bash
python3 generer.py
```

Kommandoen skriver `navne.csv` og `navne.json` ved siden af scriptet og erstatter
eventuelle eksisterende filer med de samme navne. Et fast seed giver samme
datasæt ved hver kørsel.

- `navne.csv`: semikolonsepareret CSV i UTF-8 med BOM til brug i eksempelvis Excel.
- `navne.json`: UTF-8 JSON til brug i en kommende browserdemo.

Hver post indeholder `demo_id`, `fornavn`, `mellemnavn`, `efternavn` og
`fuldt_navn`. Mellemnavnet kan være tomt.
