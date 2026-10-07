import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from satellite import SATELLITES, Pixels, coast_mask, load_coastlines, map_rows, observer, render

ROOT = Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class SatelliteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rings = load_coastlines(ROOT / "assets" / "coastlines.json")

    def test_orbits_stay_on_earth_and_move(self):
        for satellite in SATELLITES:
            positions = [satellite.position(t) for t in range(0, 20000, 137)]
            self.assertGreater(len(set(positions)), 100)
            self.assertTrue(all(-satellite.inclination <= lat <= satellite.inclination and -180 <= lon < 180
                                for lat, lon in positions))
            for seconds in (0, 1000, 6000):
                azimuth, elevation, distance = observer(satellite, seconds, 55.68, 12.57)
                self.assertTrue(all(math.isfinite(v) for v in (azimuth, elevation, distance)))
                self.assertTrue(0 <= azimuth < 360)
                self.assertTrue(-90 <= elevation <= 90)
                self.assertGreater(distance, 0)

    def test_braille_dots_and_dateline_do_not_draw_across_world(self):
        pixels = Pixels(2, 2)
        for x in range(2):
            for y in range(4):
                pixels.dot(x, y)
        self.assertEqual(pixels.cells[(0, 0)][0], 255)
        world = Pixels(100, 40)
        world.path(((0, 179), (0, -179)), "yellow", 2)
        self.assertTrue(all(x < 3 or x > 96 for x, _ in world.cells))

    def test_map_contains_coasts_tracks_footprint_and_label(self):
        rows = map_rows(self.rings, SATELLITES[0], 2000, 100, 30, 55.68, 12.57)
        shades = {shade for row in rows for _, shade in row}
        for shade in ("coast", "cyan", "yellow", "green", "pink"):
            self.assertIn(shade, shades)
        self.assertIn("AURORA-1", "\n".join("".join(char for char, _ in row) for row in rows))
        self.assertNotEqual(rows, map_rows(self.rings, SATELLITES[0], 2040, 100, 30, 55.68, 12.57))

    def test_screen_fills_terminal_for_all_satellites_and_radio_views(self):
        for width, height in ((70, 24), (80, 24), (140, 42), (200, 65)):
            for index in range(3):
                for waterfall in (False, True):
                    with self.subTest(width=width, height=height, satellite=index, waterfall=waterfall):
                        lines = render(self.rings, 32, width, height, index, waterfall=waterfall)
                        plain = [ANSI.sub("", line) for line in lines]
                        self.assertEqual(len(plain), height)
                        self.assertTrue(all(len(line) == width - 1 for line in plain))
                        self.assertIn("FIKTIVE DATA", plain[-2])
                        self.assertIn("Q AFSLUT", plain[-1])
                        self.assertIn("Station Status", "\n".join(plain))
                        if waterfall:
                            self.assertIn("SPECTRUM", "\n".join(plain))
                            self.assertIn("WATERFALL", "\n".join(plain))

    def test_ascii_small_screen_and_static_coast_cache(self):
        for waterfall in (False, True):
            output = "\n".join(render(self.rings, 20, 140, 42, waterfall=waterfall, ascii=True, color=False))
            self.assertTrue(output.isascii())
        small = "\n".join(render(self.rings, 0, 40, 12, color=False))
        self.assertIn("Gør terminalen større", small)
        before = coast_mask(self.rings, 100, 30)
        map_rows(self.rings, SATELLITES[0], 100, 100, 30, 55.68, 12.57)
        self.assertEqual(before, coast_mask(self.rings, 100, 30))

    def test_bad_map_and_cli_from_other_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.json"
            for invalid in ({}, {"rings": []}, {"rings": [[[200, 0], [0, 0], [1, 1]]]}):
                path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    load_coastlines(path)
            result = subprocess.run([sys.executable, str(ROOT / "satellite.py"), "--frames", "1", "--no-color"],
                                    cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("AURORA-1", result.stdout)
            self.assertNotIn("\x1b", result.stdout)
            missing = subprocess.run([sys.executable, str(ROOT / "satellite.py"), "--frames", "1",
                                      "--map", str(Path(directory) / "missing.json")],
                                     capture_output=True, text=True)
            self.assertEqual(missing.returncode, 1)
            self.assertIn("Kan ikke indlæse kort", missing.stderr)


if __name__ == "__main__":
    unittest.main()
