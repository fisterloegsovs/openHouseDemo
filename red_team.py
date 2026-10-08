#!/usr/bin/env python3
"""Red team: offline hacker-terminalshow med fiktive data."""

import argparse
import json
import math
from pathlib import Path
import sys
import time
from dataclasses import dataclass

from display import FILES, MODES, render
from terminal import Terminal, duration_arg, terminal_size

EVENTS = (
    (0.00, "INFO", "TARGET CPR-REGISTER / workers online"),
    (0.04, "INFO", "cpr-register.demo.invalid / database found"),
    (0.10, "OK", "CPR-REGISTER / session established"),
    (0.14, "OK", "CPR-REGISTER: ADGANG OPNÅET"),
    (0.26, "INFO", "CPR-NUMRE + NAVNE / udtræk startet"),
    (0.40, "INFO", "CPR-POSTER / batches serialized"),
    (0.52, "OK", "CPR DUMP COMPLETE / demo-poster cached"),
    (0.55, "INFO", "CPR-ARKIV / cipher buffer ready"),
    (0.58, "INFO", "CPR-NUMRE OVERFØRES / uplink open"),
    (0.70, "INFO", "CPR-DATA / ACK received"),
    (0.84, "OK", "CPR checksum OK / final segments queued"),
    (0.94, "OK", "CPR TRANSFER COMPLETE"),
    (0.98, "OK", "CPR session archived / next cycle queued"),
)


def clamp(value):
    return max(0.0, min(1.0, value))


def clean(value):
    """Forhindr kontroltegn i lokale navnefiler i at påvirke terminalen."""
    return "".join(c for c in value if c.isprintable())[:100]


def load_records(path):
    with Path(path).open(encoding="utf-8") as stream:
        records = json.load(stream)
    if not isinstance(records, list) or not records:
        raise ValueError("Navnefilen skal indeholde en ikke-tom JSON-liste.")
    result = []
    for item in records:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) and clean(item[key]).strip()
            for key in ("demo_id", "fuldt_navn")
        ):
            raise ValueError("Hver navnepost skal have demo_id og fuldt_navn som tekst.")
        result.append({key: clean(item[key]) for key in ("demo_id", "fuldt_navn")})
    return result


@dataclass(frozen=True)
class Scene:
    elapsed: float
    duration: float
    total: int

    @property
    def progress(self):
        return clamp(self.elapsed / self.duration)

    @property
    def extracted(self):
        return min(self.total, int(clamp((self.progress - 0.14) / 0.38) * self.total + 1e-9))

    @property
    def archive(self):
        return clamp((self.progress - 0.52) / 0.06)

    @property
    def transfer(self):
        return clamp((self.progress - 0.58) / 0.36)

    @property
    def phase(self):
        if self.progress >= 0.94:
            return "TRANSFER COMPLETE / CPR-DATA", "green"
        if self.progress >= 0.58:
            return "CPR-NUMRE OVERFØRES", "green"
        if self.progress >= 0.52:
            return "CPR-ARKIV PAKKES", "green"
        if self.progress >= 0.14:
            return "CPR-NUMRE UDTRÆKKES", "green"
        if self.progress >= 0.10:
            return "CPR-REGISTER: SESSION OPEN", "green"
        return "TARGET: CPR-REGISTER", "green"

    @property
    def rate(self):
        if self.progress < 0.58 or self.progress >= 0.94:
            return 0.0
        base_rate = sum(size for _, size in FILES) / (self.duration * 0.36)
        return base_rate * (1 + 0.15 * math.sin(self.elapsed * 1.3))

    def events(self):
        return [(at * self.duration, level, message) for at, level, message in EVENTS if at <= self.progress]

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="extract", help="Visning på denne PC (standard: extract)")
    parser.add_argument("--station", type=int, choices=range(1, 100), default=1, metavar="1-99")
    parser.add_argument("--duration", type=duration_arg, default=180, help="Sekunder pr. forløb (standard: 180)")
    parser.add_argument("--names", type=Path, default=Path(__file__).resolve().with_name("navne.json"))
    parser.add_argument("--no-color", action="store_true", help="Slå farver fra")
    parser.add_argument("--ascii", action="store_true", help="Brug simple tegn i grafer")
    parser.add_argument("--frames", type=int, metavar="N", help="Skriv N skærmbilleder og afslut (til kontrol uden TTY)")
    parser.add_argument("--once", action="store_true", help="Kør ét forløb fra begyndelsen og afslut")
    args = parser.parse_args(argv)
    if args.frames is not None and not 1 <= args.frames <= 1000:
        parser.error("--frames skal være mellem 1 og 1000.")
    if not sys.stdout.isatty() and args.frames is None:
        parser.error("Start i en interaktiv terminal, eller brug --frames 1 til kontrol.")
    try:
        records = load_records(args.names)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Kan ikke indlæse navne: {error}\n")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mode, paused = args.mode, False
    # Fælles vægursbaseret forløb lader flere PC'er følge samme hændelse.
    elapsed = 0.0 if args.once else time.time() % args.duration
    previous = time.monotonic()

    def draw(terminal=None):
        size = terminal_size()
        lines = render(mode, Scene(elapsed, args.duration, len(records)), records,
                       size.columns, size.lines, args.station,
                       color=not args.no_color and (terminal is not None),
                       unicode=not args.ascii, paused=paused, repeat=not args.once)
        if terminal:
            terminal.draw(lines)
        else:
            print("\n".join(lines))

    try:
        if args.frames is not None:
            for _ in range(args.frames):
                draw()
                elapsed = (elapsed + 0.2) % args.duration
            return 0
        with Terminal() as terminal:
            while True:
                key = terminal.key()
                if key in ("q", "\x03"):
                    break
                if key in "12345" and key:
                    mode = MODES[int(key) - 1]
                elif key in ("p", " "):
                    paused = not paused
                elif key == "r":
                    elapsed = 0
                now = time.monotonic()
                if not paused:
                    elapsed += now - previous
                previous = now
                if elapsed >= args.duration:
                    if args.once:
                        draw(terminal)
                        break
                    elapsed %= args.duration
                draw(terminal)
                time.sleep(0.10)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
