"""Generér opdigtede navnekombinationer til skærmdemoen; ingen persondata."""

import csv
import json
import random
from pathlib import Path

FORNAVNE = [
    "Anders", "Christian", "Daniel", "Emil", "Frederik", "Henrik", "Jakob",
    "Jens", "Jesper", "Jonas", "Kasper", "Lars", "Mads", "Magnus", "Martin",
    "Mathias", "Mikkel", "Niels", "Oliver", "Peter", "Rasmus", "Simon",
    "Søren", "Thomas", "William", "Anna", "Anne", "Camilla", "Caroline",
    "Charlotte", "Clara", "Emma", "Freja", "Ida", "Julie", "Karen",
    "Katrine", "Laura", "Lene", "Line", "Louise", "Maja", "Maria", "Mette",
    "Nanna", "Nina", "Pernille", "Sofie", "Trine", "Victoria",
]
MELLEMNAVNE = [
    "Bjerre", "Dahl", "Holm", "Lind", "Lund", "Møller", "Nørgaard",
    "Skov", "Søndergaard", "Vestergaard", "Østergaard",
]
EFTERNAVNE = [
    "Andersen", "Christensen", "Hansen", "Jensen", "Johansen", "Jørgensen",
    "Knudsen", "Kristensen", "Larsen", "Madsen", "Mortensen", "Nielsen",
    "Olsen", "Pedersen", "Petersen", "Poulsen", "Rasmussen", "Sørensen",
    "Thomsen", "Møller", "Lund", "Holm", "Dahl", "Skov", "Vestergaard",
    "Nørgaard", "Søndergaard", "Østergaard",
]


def generate(count=500, seed=2026):
    rng = random.Random(seed)
    records, seen = [], set()
    while len(records) < count:
        first = rng.choice(FORNAVNE)
        last = rng.choice(EFTERNAVNE)
        middle = rng.choice([n for n in MELLEMNAVNE if n != last]) if rng.random() < 0.6 else ""
        full = " ".join(n for n in (first, middle, last) if n)
        if full in seen:
            continue
        seen.add(full)
        records.append({"demo_id": f"DEMO-{len(records) + 1:05d}",
                        "fornavn": first, "mellemnavn": middle,
                        "efternavn": last, "fuldt_navn": full})
    return records


if __name__ == "__main__":
    records = generate()
    destination = Path(__file__).resolve().parent
    with (destination / "navne.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    (destination / "navne.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Genereret {len(records)} unikke navnekombinationer i {destination}")
