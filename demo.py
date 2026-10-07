#!/usr/bin/env python3
"""Offline terminalshow til open house. Ingen netværkstrafik eller CPR-numre."""

import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from dataclasses import dataclass

MODES = ("overview", "extract", "transfer", "soc", "matrix")
LABELS = {
    "overview": "OPERATIONSOVERBLIK", "extract": "DATAUDTRÆK",
    "transfer": "SIMULERET OVERFØRSEL", "soc": "SIKKERHEDSOVERVÅGNING",
    "matrix": "SIGNALVISUALISERING",
}
COLORS = {"green": "32", "cyan": "36", "yellow": "33", "red": "31", "dim": "90", "white": "97"}
FILES = (("personposter_demo.enc", 48.0), ("metadata_demo.json", 3.2), ("audit_demo.log", 12.8))
EVENTS = (
    (0.00, "INFO", "Ny øvelse startet / syntetisk miljø initialiseret"),
    (0.04, "INFO", "Inventar: demo-db.internal / demo-gateway.internal"),
    (0.09, "INFO", "Fiktivt personregister fundet / navnepulje indlæst"),
    (0.14, "INFO", "Udtræk startet / personposter behandles"),
    (0.26, "INFO", "Poster grupperes / CPR-felter er maskerede"),
    (0.38, "WARN", "SOC: usædvanligt antal databaseforespørgsler"),
    (0.48, "INFO", "Udtræk afsluttet / demoarkiv klargjort"),
    (0.53, "WARN", "Simuleret udgående overførsel startet"),
    (0.64, "WARN", "SOC: udgående trafik overstiger normalprofil"),
    (0.73, "ALERT", "SOC: mulig dataeksfiltration / undersøgelse startet"),
    (0.80, "BLOCK", "SOC: forbindelse blokeret / overførsel afbrudt"),
    (0.86, "INFO", "SOC: demo-vært isoleret / advarsler undersøgt"),
    (0.92, "OK", "Hændelse inddæmmet / demo-data forbliver lokale"),
    (0.97, "INFO", "Øvelse afsluttet / næste forløb starter automatisk"),
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
        return min(self.total, int(clamp((self.progress - 0.14) / 0.34) * self.total + 1e-9))

    @property
    def transfer(self):
        # Forsvaret blokerer ved 78 %; den simulerede overførsel fuldføres aldrig.
        return clamp((self.progress - 0.53) / 0.27) * 0.78

    @property
    def blocked(self):
        return self.progress >= 0.80

    @property
    def contained(self):
        return self.progress >= 0.92

    @property
    def phase(self):
        if self.contained:
            return "HÆNDELSE INDDÆMMET", "green"
        if self.blocked:
            return "FORBINDELSE BLOKERET", "red"
        if self.progress >= 0.73:
            return "ALARM / DATAEKSFILTRATION", "red"
        if self.progress >= 0.53:
            return "SIMULERET OVERFØRSEL", "yellow"
        if self.progress >= 0.48:
            return "ARKIV KLARGØRES", "cyan"
        if self.progress >= 0.14:
            return "PERSONPOSTER BEHANDLES", "cyan"
        return "MILJØ KORTLÆGGES", "green"

    @property
    def severity(self):
        if self.contained:
            return "INDDÆMMET", "green"
        if self.progress >= 0.73:
            return "KRITISK", "red"
        if self.progress >= 0.38:
            return "FORHØJET", "yellow"
        return "NORMAL", "green"

    @property
    def rate(self):
        if self.progress < 0.53 or self.blocked:
            return 0.0
        base_rate = sum(size for _, size in FILES) * 0.78 / (self.duration * 0.27)
        return base_rate * (1 + 0.15 * math.sin(self.elapsed * 1.3))

    def events(self):
        return [(at * self.duration, level, message) for at, level, message in EVENTS if at <= self.progress]


def sparkline(scene, width=48):
    glyphs = "▁▂▃▄▅▆▇█"
    values = []
    for i in range(width):
        at = scene.elapsed - (width - 1 - i) * scene.duration / 120
        sample = Scene(max(0, at), scene.duration, scene.total)
        peak_rate = sum(size for _, size in FILES) * 0.78 / (scene.duration * 0.27) * 1.15
        value = 0.1 if sample.rate == 0 else sample.rate / peak_rate
        values.append(glyphs[min(7, int(clamp(value) * 7))])
    return "".join(values)


class Screen:
    def __init__(self, width, color=True, unicode=True):
        self.width = max(1, width)
        self.color = color
        self.unicode = unicode
        self.lines = []

    def add(self, text="", color=None, bold=False):
        text = text[:self.width]
        if not self.unicode:
            text = text.translate(str.maketrans({"█": "#", "░": "-", "─": "-", "▁": ".", "▂": "_", "▃": "-", "▄": "=", "▅": "+", "▆": "*", "▇": "#"}))
        if self.color and (color or bold):
            code = ("1;" if bold else "") + COLORS.get(color, "37")
            text = f"\033[{code}m{text}\033[0m"
        self.lines.append(text)

    def rule(self, title=""):
        line = f"── {title} " if title else ""
        self.add(line + "─" * max(0, self.width - len(line)), "dim")

    def bar(self, label, progress, status="", color="cyan"):
        size = max(6, min(38, self.width - 37))
        count = int(clamp(progress) * size)
        self.add(f"{label:<15} [" + "█" * count + "░" * (size - count) + f"] {progress:>6.1%}  {status}", color)


def render(mode, scene, records, width=100, height=32, station=1, color=True, unicode=True, paused=False, repeat=True):
    screen = Screen(width - 4, color, unicode)
    if width < 62 or height < 22:
        screen.add("OPEN HOUSE / SIMULATION", "cyan", True)
        screen.add("Gør terminalen større: mindst 62 kolonner og 22 linjer.", "yellow")
        screen.add(f"Status: {scene.phase[0]}")
        screen.add("Q / Ctrl+C: afslut")
        return screen.lines[:max(1, height - 1)]

    screen.add("OPEN HOUSE // CYBER OPERATIONS", "cyan", True)
    screen.add(f"STATION {station:02d}  /  {LABELS[mode]}  /  {'PAUSE' if paused else 'LIVE SIMULATION'}", "white")
    screen.add("FIKTIVE DATA · LOKAL SIMULATION · INGEN RIGTIGE CPR-NUMRE", "dim")
    screen.rule()
    phase, phase_color = scene.phase
    screen.add(f"{phase}   |   FORLØB {int(scene.elapsed):03d}/{int(scene.duration):03d} s", phase_color, True)
    screen.bar("ØVELSE", scene.progress, "GENTAGER AUTOMATISK" if repeat else "ET ENKELT FORLØB", "green")
    screen.add()

    if mode == "overview":
        screen.rule("HÆNDELSESFORLØB")
        stages = ((0.00, 0.14, "01 KORTLÆGNING", "Demo-værter og database"),
                  (0.14, 0.48, "02 DATAUDTRÆK", f"{scene.extracted}/{scene.total} syntetiske poster"),
                  (0.48, 0.53, "03 ARKIVERING", "Demoarkiv klargøres"),
                  (0.53, 0.80, "04 OVERFØRSEL", f"{scene.transfer:.0%} / afbrydes af SOC"),
                  (0.80, 1.01, "05 INDDÆMNING", "Forbindelse blokeres og vært isoleres"))
        for start, end, name, description in stages:
            state = "OK" if scene.progress >= end else "AKTIV" if scene.progress >= start else "VENTER"
            screen.add(f"[{state:>6}] {name:<17} {description}", "green" if state == "OK" else "cyan" if state == "AKTIV" else "dim")
        screen.add()
        screen.add(f"UDTRUKKET {scene.extracted:>3}/{scene.total}   SENDT {scene.transfer:>5.0%}   ALARM {scene.severity[0]}", scene.severity[1])
        screen.rule("HÆNDELSESLOG")

    elif mode == "extract":
        screen.rule("PERSONREGISTER / SYNTETISKE POSTER")
        screen.bar("UDTRÆK", scene.extracted / scene.total, f"{scene.extracted}/{scene.total} POSTER")
        screen.add("DEMO-ID       NAVN                              CPR-FELT", "dim")
        slots = max(3, min(10, height - 19))
        end = scene.extracted
        shown = records[max(0, end - slots):end]
        for record in shown:
            screen.add(f"{record['demo_id']:<13} {record['fuldt_navn'][:33]:<33} ******-****", "green")
        for _ in range(slots - len(shown)):
            screen.add("... venter på næste post", "dim")
        screen.add()
        screen.add("SELECT demo_id, navn FROM personregister_demo;", "cyan")
        screen.rule("HÆNDELSESLOG")

    elif mode == "transfer":
        screen.rule("SIMULERET UDGÅENDE TRAFIK")
        screen.add("KILDE demo-db.internal  >  MÅL demo-destination.invalid", "dim")
        total_mb = sum(size for _, size in FILES)
        sent_mb = scene.transfer * total_mb
        consumed = 0.0
        for name, size in FILES:
            progress = clamp((sent_mb - consumed) / size)
            status = ("FÆRDIG" if progress == 1 else "ANNULLERET" if scene.blocked and progress == 0
                      else "AFBRUDT" if scene.blocked else "AKTIV" if progress > 0 else "VENTER")
            screen.add(f"{name:<27} {size:>5.1f} MB", "white")
            screen.bar("", progress, status, "red" if status in ("AFBRUDT", "ANNULLERET") else "cyan")
            consumed += size
        screen.add()
        screen.add(f"HASTIGHED {scene.rate:>4.1f} MB/s   SENDT {sent_mb:>4.1f}/{total_mb:.1f} MB", "yellow")
        screen.add(sparkline(scene, min(65, screen.width)), "cyan")
        screen.rule("HÆNDELSESLOG")

    elif mode == "soc":
        screen.rule("SECURITY OPERATIONS CENTER")
        severity, severity_color = scene.severity
        screen.add(f"TRUSSELSNIVEAU: {severity}", severity_color, True)
        rules = ((0.38, "DB-104", "Usædvanligt mange databaseforespørgsler"),
                 (0.64, "NET-208", "Udgående trafik over normalprofil"),
                 (0.73, "DLP-301", "Mulig overførsel af personposter"))
        for threshold, code, text in rules:
            triggered = scene.progress >= threshold
            screen.add(f"[{'ALARM' if triggered else 'KLAR ':5}] {code}  {text}", severity_color if triggered else "dim")
        screen.add()
        screen.add(f"FORBINDELSE: {'BLOKERET' if scene.blocked else 'OVERVÅGES'}", "red" if scene.blocked else "cyan")
        screen.add(f"DEMO-VÆRT:   {'ISOLERET' if scene.progress >= 0.86 else 'AKTIV'}", "green" if scene.contained else "yellow")
        screen.add(f"RESPONS:     {'HÆNDELSE INDDÆMMET' if scene.contained else 'AFVENTER' if scene.progress < 0.73 else 'UNDERSØGER / BLOKERER'}", severity_color)
        screen.rule("ALARM- OG RESPONSLOG")

    elif mode == "matrix":
        screen.rule("SIMULERET SIGNALSTRØM")
        chars = "01ABCDEF:./<>[]{}"
        tick = int(scene.elapsed * 7)
        for row in range(max(3, height - 13)):
            text = []
            for col in range(screen.width):
                head = (col * 11 + tick * (1 + col % 3)) % max(4, height - 13)
                distance = (head - row) % max(4, height - 13)
                text.append(chars[(row * 17 + col * 31 + tick) % len(chars)] if col % 3 != 2 and distance < 6 else " ")
            screen.add("".join(text), "green")
        screen.add("VISUEL EFFEKT / INGEN KOMMANDOER UDFØRES", "dim")

    # Reserver to linjer til tastaturhjælp og status, også på små skærme.
    if mode != "matrix":
        capacity = max(1, height - 1 - len(screen.lines) - 3)
        for at, level, message in scene.events()[-capacity:]:
            level_color = "red" if level in ("BLOCK", "ALERT") else "yellow" if level == "WARN" else "green" if level == "OK" else "dim"
            screen.add(f"[{int(at):03d}s] {level:<5} {message}", level_color)
    screen.lines = screen.lines[:height - 4]
    while len(screen.lines) < height - 4:
        screen.add()
    screen.rule()
    screen.add("1 OVERBLIK  2 UDTRÆK  3 TRANSFER  4 SOC  5 MATRIX", "dim")
    screen.add("P PAUSE  R GENSTART  Q AFSLUT  |  Ctrl+C afslutter også", "dim")
    return screen.lines


class Terminal:
    """Terminaltilstand gendannes ved normal afslutning og ved exceptions."""
    def __init__(self, stream=sys.stdout):
        self.stream = stream
        self.saved = None
        self.windows_mode = None

    def __enter__(self):
        try:
            if os.name == "nt":
                from ctypes import wintypes
                kernel = ctypes.windll.kernel32
                kernel.GetStdHandle.argtypes = [wintypes.DWORD]
                kernel.GetStdHandle.restype = wintypes.HANDLE
                kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
                kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                handle = kernel.GetStdHandle(-11)
                mode = wintypes.DWORD()
                if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                    raise OSError("Åbn programmet i Windows Terminal eller PowerShell.")
                if not kernel.SetConsoleMode(handle, mode.value | 0x0004):
                    raise OSError("Terminalen understøtter ikke ANSI-visning.")
                self.windows_mode = handle, mode.value
            elif sys.stdin.isatty():
                import termios
                import tty
                self.saved = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
            self.stream.write("\033[?1049h\033[?25l\033[2J\033[H")
            self.stream.flush()
            return self
        except BaseException:
            self.restore()
            raise

    def key(self):
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getwch().lower()
        elif sys.stdin.isatty():
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                return os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore").lower()
        return ""

    def draw(self, lines):
        self.stream.write("\033[H" + "\r\n".join("  " + line + "\033[K" for line in lines) + "\033[J")
        self.stream.flush()

    def restore(self):
        try:
            self.stream.write("\033[0m\033[?25h\033[?1049l")
            self.stream.flush()
        finally:
            if self.saved is not None:
                import termios
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.saved)
            if self.windows_mode is not None:
                ctypes.windll.kernel32.SetConsoleMode(*self.windows_mode)

    def __exit__(self, *_):
        self.restore()


def duration_arg(text):
    value = float(text)
    if not math.isfinite(value) or value < 20 or value > 3600:
        raise argparse.ArgumentTypeError("Forløbet skal vare mellem 20 og 3600 sekunder.")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="overview", help="Visning på denne PC")
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
        size = shutil.get_terminal_size((100, 32))
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
                time.sleep(0.15)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
