#!/usr/bin/env python3
"""Blue team: selvstændig, offline SOC-simulation med fiktive hændelser."""

import argparse
from dataclasses import dataclass
import sys
import time

from blue_display import MODES, render
from terminal import Terminal, duration_arg, terminal_size


@dataclass(frozen=True)
class Scene:
    elapsed: float
    duration: float

    @property
    def progress(self):
        return max(0, min(1, self.elapsed / self.duration))

    @property
    def alerts(self):
        return sum(self.progress >= at for at in (0.20, 0.34, 0.44, 0.56, 0.68))

    @property
    def blocked(self):
        return self.progress >= 0.82

    @property
    def resolved(self):
        return self.progress >= 0.94

    @property
    def severity(self):
        if self.resolved:
            return "CONTAINED", "green"
        if self.progress >= 0.44:
            return "CRITICAL", "red"
        if self.progress >= 0.20:
            return "ELEVATED", "yellow"
        return "NORMAL", "cyan"

    @property
    def phase(self):
        if self.resolved:
            return "INCIDENT CONTAINED", "green"
        if self.progress >= 0.87:
            return "HOST ISOLATED", "yellow"
        if self.blocked:
            return "EGRESS BLOCKED", "red"
        if self.progress >= 0.70:
            return "RESPONSE IN PROGRESS", "red"
        if self.progress >= 0.44:
            return "INCIDENT OPEN / TRIAGE", "red"
        if self.progress >= 0.20:
            return "ANOMALY DETECTED", "yellow"
        return "MONITORING / BASELINE NORMAL", "cyan"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="overview")
    parser.add_argument("--station", type=int, choices=range(1, 100), default=6, metavar="1-99")
    parser.add_argument("--duration", type=duration_arg, default=180)
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--frames", type=int, metavar="N", help="Skriv N skærmbilleder og afslut")
    parser.add_argument("--once", action="store_true", help="Kør ét forløb fra begyndelsen")
    args = parser.parse_args(argv)
    if args.frames is not None and not 1 <= args.frames <= 1000:
        parser.error("--frames skal være mellem 1 og 1000.")
    if not sys.stdout.isatty() and args.frames is None:
        parser.error("Start i en interaktiv terminal, eller brug --frames 1 til kontrol.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    mode, paused = args.mode, False
    elapsed = 0.0 if args.once else time.time() % args.duration
    previous = time.monotonic()

    def draw(terminal=None):
        size = terminal_size()
        lines = render(mode, Scene(elapsed, args.duration), size.columns, size.lines,
                       args.station, color=not args.no_color and terminal is not None,
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
