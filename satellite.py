#!/usr/bin/env python3
"""Offline satellitstation med verdenskort, baner og simuleret radiosignal."""

import argparse
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
import sys
import time

from terminal import Terminal, duration_arg, terminal_size

EARTH_RADIUS = 6371.0
DOT_BITS = ((1, 2, 4, 64), (8, 16, 32, 128))
PALETTE = {"coast": "2;90", "cyan": "96", "yellow": "93", "green": "92",
           "pink": "95", "white": "97", "dim": "90", "signal": "36"}


@dataclass(frozen=True)
class Satellite:
    name: str
    inclination: float
    period: float
    altitude: float
    frequency: float
    offset: float

    def position(self, seconds):
        angle = 2 * math.pi * (seconds / (self.period * 60) + self.offset)
        inclination = math.radians(self.inclination)
        latitude = math.degrees(math.asin(math.sin(angle) * math.sin(inclination)))
        longitude = math.degrees(math.atan2(math.sin(angle) * math.cos(inclination), math.cos(angle)))
        longitude = (longitude - seconds / 86164 * 360 + 180) % 360 - 180
        return latitude, longitude


SATELLITES = (Satellite("AURORA-1", 67, 95, 550, 437.325, 0.15),
              Satellite("POLARIS-2", 82, 101, 710, 436.750, 0.43),
              Satellite("VEGA-3", 54, 93, 420, 435.950, 0.76))


def observer(satellite, seconds, latitude, longitude):
    """Azimut, elevation og afstand for en cirkulær, fiktiv bane."""
    sat_lat, sat_lon = map(math.radians, satellite.position(seconds))
    lat, lon = math.radians(latitude), math.radians(longitude)
    radius = EARTH_RADIUS + satellite.altitude
    dx = radius * math.cos(sat_lat) * math.cos(sat_lon) - EARTH_RADIUS * math.cos(lat) * math.cos(lon)
    dy = radius * math.cos(sat_lat) * math.sin(sat_lon) - EARTH_RADIUS * math.cos(lat) * math.sin(lon)
    dz = radius * math.sin(sat_lat) - EARTH_RADIUS * math.sin(lat)
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz
    up = math.cos(lat) * math.cos(lon) * dx + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz
    azimuth = math.degrees(math.atan2(east, north)) % 360
    elevation = math.degrees(math.atan2(up, math.hypot(east, north)))
    return azimuth, elevation, math.sqrt(dx * dx + dy * dy + dz * dz)


def load_coastlines(path):
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    rings = data.get("rings") if isinstance(data, dict) else None
    if not isinstance(rings, list) or not rings:
        raise ValueError("Kortfilen skal indeholde kystlinjer i feltet rings.")
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 3:
            raise ValueError("En kystlinje skal have mindst tre punkter.")
        for point in ring:
            if not isinstance(point, list) or len(point) != 2 or any(
                not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
                for value in point
            ) or not -180 <= point[0] <= 180 or not -90 <= point[1] <= 90:
                raise ValueError("Ugyldig geografisk koordinat i kortfilen.")
    return tuple(tuple(tuple(point) for point in ring) for ring in rings)


class Pixels:
    """To gange fire prikker pr. terminalcelle giver et detaljeret braille-kort."""
    def __init__(self, width, height, base=None):
        self.width, self.height = width, height
        self.cells = dict(base) if base else {}

    def dot(self, x, y, color="coast", priority=0):
        if 0 <= x < self.width * 2 and 0 <= y < self.height * 4:
            cell = (int(x) // 2, int(y) // 4)
            mask, old_color, old_priority = self.cells.get(cell, (0, color, priority))
            mask |= DOT_BITS[int(x) % 2][int(y) % 4]
            self.cells[cell] = (mask, color if priority >= old_priority else old_color, max(priority, old_priority))

    def line(self, start, end, color="coast", priority=0):
        x0, y0 = map(int, start)
        x1, y1 = map(int, end)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.dot(x0, y0, color, priority)
            if x0 == x1 and y0 == y1:
                return
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def coordinate(self, latitude, longitude):
        # Equirektangulær projektion med fuld geografisk bredde.
        return round((longitude + 180) / 360 * (self.width * 2 - 1)), round((90 - latitude) / 180 * (self.height * 4 - 1))

    def path(self, points, color="coast", priority=0):
        previous = None
        for latitude, longitude in points:
            current = self.coordinate(latitude, longitude)
            if previous is not None and abs(current[0] - previous[0]) <= self.width:
                self.line(previous, current, color, priority)
            else:
                self.dot(*current, color, priority)
            previous = current


@lru_cache(maxsize=8)
def coast_mask(rings, width, height):
    pixels = Pixels(width, height)
    for ring in rings:
        pixels.path(((lat, lon) for lon, lat in ring))
    return tuple(pixels.cells.items())


def footprint(latitude, longitude, altitude):
    radius = math.acos(EARTH_RADIUS / (EARTH_RADIUS + altitude))
    lat, lon = math.radians(latitude), math.radians(longitude)
    points = []
    for i in range(97):
        bearing = i / 96 * 2 * math.pi
        y = math.asin(math.sin(lat) * math.cos(radius) + math.cos(lat) * math.sin(radius) * math.cos(bearing))
        x = lon + math.atan2(math.sin(bearing) * math.sin(radius) * math.cos(lat), math.cos(radius) - math.sin(lat) * math.sin(y))
        points.append((math.degrees(y), (math.degrees(x) + 180) % 360 - 180))
    return points


def raster_rows(pixels, ascii=False):
    rows = []
    for y in range(pixels.height):
        cells = []
        for x in range(pixels.width):
            mask, color, _ = pixels.cells.get((x, y), (0, "dim", 0))
            glyph = ("." if color == "coast" else "+") if ascii and mask else chr(0x2800 + mask) if mask else " "
            cells.append((glyph, color))
        rows.append(cells)
    return rows


def map_rows(rings, satellite, seconds, width, height, station_lat, station_lon, ascii=False):
    pixels = Pixels(width, height, coast_mask(rings, width, height))
    period = satellite.period * 60
    for offset, color, priority in ((-period, "cyan", 1), (period, "cyan", 1), (0, "yellow", 2)):
        points = [satellite.position(seconds + offset - period / 2 + period * i / 480) for i in range(481)]
        pixels.path(points, color, priority)
    lat, lon = satellite.position(seconds)
    pixels.path(footprint(lat, lon, satellite.altitude), "green", 3)
    sx, sy = pixels.coordinate(station_lat, station_lon)
    for offset in range(-2, 3):
        pixels.dot(sx + offset, sy, "white", 4)
        pixels.dot(sx, sy + offset, "white", 4)
    rows = raster_rows(pixels, ascii)
    x, y = pixels.coordinate(lat, lon)
    x, y = x // 2, y // 4
    label = "+ " + satellite.name
    start = min(x, max(0, width - len(label)))
    for i, char in enumerate(label[:width]):
        rows[y][start + i] = (char, "pink")
    return rows


def polar_rows(satellite, seconds, width, height, latitude, longitude, ascii=False):
    pixels = Pixels(width, height)
    # Terminalceller er ca. dobbelt så høje som brede.
    cx, cy = width - 1, height * 2 - 1
    radius = min(width - 3, height * 2 - 3)
    for fraction in (1 / 3, 2 / 3, 1):
        points = [(cx + radius * fraction * math.sin(i * math.pi / 90), cy - radius * fraction * math.cos(i * math.pi / 90)) for i in range(181)]
        for first, second in zip(points, points[1:]):
            pixels.line(first, second, "coast")
    pixels.line((cx - radius, cy), (cx + radius, cy))
    pixels.line((cx, cy - radius), (cx, cy + radius))
    previous = None
    for i in range(181):
        at = seconds - 600 + i * 10
        azimuth, elevation, _ = observer(satellite, at, latitude, longitude)
        if elevation <= 0:
            previous = None
            continue
        distance = radius * (90 - elevation) / 90
        point = (cx + distance * math.sin(math.radians(azimuth)), cy - distance * math.cos(math.radians(azimuth)))
        if previous:
            pixels.line(previous, point, "cyan", 2)
        previous = point
    rows = raster_rows(pixels, ascii)
    azimuth, elevation, _ = observer(satellite, seconds, latitude, longitude)
    if elevation > 0:
        distance = radius * (90 - elevation) / 90
        px = round((cx + distance * math.sin(math.radians(azimuth))) / 2)
        py = round((cy - distance * math.cos(math.radians(azimuth))) / 4)
        if 0 <= px < width and 0 <= py < height:
            rows[py][px] = ("*", "yellow")
    for x, y, letter in ((width // 2, 0, "N"), (width // 2, height - 1, "S"), (0, height // 2, "W"), (width - 1, height // 2, "E")):
        rows[y][x] = (letter, "yellow")
    return rows


def radio_rows(satellite, seconds, width, height, ascii=False):
    rows = []
    spectrum_height = max(3, height // 3)
    rows.append([(c, "yellow") for c in "SPECTRUM / dB".ljust(width)[:width]])
    bins = []
    for x in range(width):
        noise = 0.09 + 0.06 * abs(math.sin(x * 1.7 + seconds * 0.23))
        peak = 0.8 * math.exp(-((x / max(1, width - 1) - 0.5 - 0.025 * math.sin(seconds * 0.001)) / 0.03) ** 2)
        bins.append(min(1, noise + peak))
    for y in range(spectrum_height):
        threshold = 1 - y / spectrum_height
        rows.append([("#" if ascii else "█", "cyan") if value >= threshold else (" ", "dim") for value in bins])
    if len(rows) < height:
        rows.append([(c, "yellow") for c in f"WATERFALL / {satellite.frequency:.3f} MHz".ljust(width)[:width]])
    while len(rows) < height:
        row = []
        for x in range(width):
            power = bins[x] + 0.14 * abs(math.sin(x * 1.3 + seconds * 0.16 - len(rows) * 0.7))
            glyph = "#" if power > 0.65 else "+" if power > 0.28 else "."
            row.append((glyph if ascii else "█" if power > 0.65 else "▒" if power > 0.28 else "░", "green" if power > 0.65 else "cyan" if power > 0.28 else "coast"))
        rows.append(row)
    return rows[:height]


def render(rings, elapsed, width=140, height=42, satellite_index=0, station=1,
           speed=60, latitude=55.68, longitude=12.57, waterfall=False,
           color=True, ascii=False, paused=False):
    canvas, height = max(1, width - 1), max(1, height)
    satellite = SATELLITES[satellite_index]
    seconds = elapsed * speed

    def styled(cells):
        groups = []
        previous, chars = None, []
        for char, shade in cells:
            if shade != previous and chars:
                text = "".join(chars)
                groups.append(f"\033[40;{PALETTE[previous]}m{text}" if color else text)
                chars = []
            previous = shade
            chars.append(char)
        if chars:
            text = "".join(chars)
            groups.append(f"\033[40;{PALETTE[previous]}m{text}" if color else text)
        return "".join(groups) + ("\033[0m" if color else "")

    def text_row(text, size, shade="white"):
        return [(c, shade) for c in text[:size].ljust(size)]

    if width < 70 or height < 24:
        messages = ["SATELLITE GROUND STATION / SIMULATION", "Gør terminalen større: mindst 70 x 24.", "Q / Ctrl+C: afslut"]
        return [styled(text_row(messages[i] if i < len(messages) else "", canvas)) for i in range(height)]

    sidebar = max(24, min(34, width // 5))
    map_width = canvas - sidebar - 1
    body_height = height - 3
    polar_height = min(18, max(6, body_height - 19))
    info_height = body_height - polar_height
    azimuth, elevation, distance = observer(satellite, seconds, latitude, longitude)
    lat, lon = satellite.position(seconds)
    status = "SIGNAL LOCK" if elevation > 0 else "STANDBY"
    def field(label, value):
        return label.ljust(max(len(label) + 1, sidebar - 1 - len(value))) + value

    info = [("Station Status", "yellow"), (field("Observation", status), "green" if elevation > 0 else "yellow"),
            (field("Satellite", satellite.name), "cyan"), (field("Mode", "GFSK"), "cyan"),
            (field("Frequency", f"{satellite.frequency:.3f} MHz"), "white"),
            (field("Latitude", f"{lat:+.3f} deg"), "white"), (field("Longitude", f"{lon:+.3f} deg"), "white"),
            (field("Altitude", f"{satellite.altitude:.1f} km"), "white"),
            (field("Velocity", f"{math.sqrt(398600 / (EARTH_RADIUS + satellite.altitude)):.3f} km/s"), "white"),
            (field("Range", f"{distance:.1f} km"), "white"),
            (field("Azimuth", f"{azimuth:.2f} deg"), "white"), (field("Elevation", f"{elevation:.2f} deg"), "white"),
            (field("Period", f"{satellite.period:.1f} min"), "white"),
            ("Ground Station", "yellow"), (field(f"GS-{station:02d}", f"{latitude:+.2f}/{longitude:+.2f}"), "cyan"),
            (field("Mission", f"T+{int(seconds) // 3600:02d}:{int(seconds) // 60 % 60:02d}:{int(seconds) % 60:02d}"), "white"),
            (field("Time scale", f"x{speed:g}"), "dim"), ("Orbit / Antenna", "yellow")]
    if info_height < len(info):
        # På små laptops prioriteres satellitdata og antennevinkler.
        info = info[:12]
    while len(info) < info_height:
        seq = int(seconds * 3) + len(info)
        info.append((f"RX {seq % 65536:04X} / CRC OK / ACK", "coast"))
    left = [text_row(text, sidebar, shade) for text, shade in info[:info_height]]
    left += polar_rows(satellite, seconds, sidebar, polar_height, latitude, longitude, ascii)
    if waterfall:
        radio_height = min(body_height - 10, max(8, body_height // 3))
        right = map_rows(rings, satellite, seconds, map_width, body_height - radio_height, latitude, longitude, ascii)
        right += radio_rows(satellite, seconds, map_width, radio_height, ascii)
    else:
        right = map_rows(rings, satellite, seconds, map_width, body_height, latitude, longitude, ascii)
    title = f"GS-{station:02d} // {satellite.name}"
    counter = f"T+{int(seconds) // 3600:02d}:{int(seconds) // 60 % 60:02d}:{int(seconds) % 60:02d} {'PAUSE' if paused else 'TRACKING'}"
    header = title + " " * max(1, canvas - len(title) - len(counter)) + counter
    lines = [styled(text_row(header, canvas, "white"))]
    divider = "|" if ascii else "│"
    for lrow, rrow in zip(left, right):
        lines.append(styled(lrow + [(divider, "coast")] + rrow))
    lines.append(styled(text_row("SIMULATION / FIKTIVE DATA | CYAN: ADJACENT ORBITS  YELLOW: CURRENT  GREEN: FOOTPRINT", canvas, "dim")))
    lines.append(styled(text_row("1-3 SATELLITE  W SPECTRUM  P PAUSE  R RESTART  Q AFSLUT", canvas, "dim")))
    return lines


def bounded_float(low, high, label):
    def parse(text):
        value = float(text)
        if not math.isfinite(value) or not low <= value <= high:
            raise argparse.ArgumentTypeError(f"{label} skal være mellem {low} og {high}.")
        return value
    return parse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--satellite", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--station", type=int, choices=range(1, 100), default=1, metavar="1-99")
    parser.add_argument("--latitude", type=bounded_float(-90, 90, "Breddegrad"), default=55.68)
    parser.add_argument("--longitude", type=bounded_float(-180, 180, "Længdegrad"), default=12.57)
    parser.add_argument("--speed", type=bounded_float(1, 3600, "Tidsfaktor"), default=60)
    parser.add_argument("--waterfall", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--frames", type=int)
    parser.add_argument("--once", action="store_true", help="Afslut efter --duration sekunder")
    parser.add_argument("--duration", type=duration_arg, default=180)
    parser.add_argument("--map", type=Path, default=Path(__file__).resolve().parent / "assets" / "coastlines.json")
    args = parser.parse_args(argv)
    if args.frames is not None and not 1 <= args.frames <= 1000:
        parser.error("--frames skal være mellem 1 og 1000.")
    if not sys.stdout.isatty() and args.frames is None:
        parser.error("Start i en interaktiv terminal, eller brug --frames 1 til kontrol.")
    try:
        rings = load_coastlines(args.map)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Kan ikke indlæse kort: {error}\n")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    elapsed, paused = 0.0, False
    satellite_index, waterfall = args.satellite - 1, args.waterfall
    previous = time.monotonic()

    def draw(terminal=None):
        size = terminal_size()
        lines = render(rings, elapsed, size.columns, size.lines, satellite_index,
                       args.station, args.speed, args.latitude, args.longitude, waterfall,
                       color=not args.no_color and terminal is not None, ascii=args.ascii, paused=paused)
        if terminal:
            terminal.draw(lines)
        else:
            print("\n".join(lines))

    try:
        if args.frames is not None:
            for _ in range(args.frames):
                draw()
                elapsed += 0.2
            return 0
        with Terminal() as terminal:
            while True:
                key = terminal.key()
                if key in ("q", "\x03"):
                    break
                if key and key in "123":
                    satellite_index = int(key) - 1
                elif key == "w":
                    waterfall = not waterfall
                elif key in ("p", " "):
                    paused = not paused
                elif key == "r":
                    elapsed = 0
                now = time.monotonic()
                if not paused:
                    elapsed += now - previous
                previous = now
                draw(terminal)
                if args.once and elapsed >= args.duration:
                    break
                time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
