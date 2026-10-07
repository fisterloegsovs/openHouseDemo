"""Kontrollér hændelsesforløbet og den terminalvisning, publikum ser."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from demo import MODES, Scene, load_records, render

ROOT = Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records(ROOT / "navne.json")

    def test_extraction_finishes_before_transfer_and_defense_stops_transfer(self):
        before = Scene(180 * 0.13, 180, 500)
        extracted = Scene(180 * 0.48, 180, 500)
        transferring = Scene(180 * 0.65, 180, 500)
        blocked = Scene(180 * 0.81, 180, 500)
        contained = Scene(180 * 0.95, 180, 500)
        self.assertEqual(before.extracted, 0)
        self.assertEqual(extracted.extracted, 500)
        self.assertEqual(extracted.transfer, 0)
        self.assertGreater(transferring.transfer, 0)
        self.assertGreater(transferring.rate, 0)
        self.assertFalse(transferring.blocked)
        self.assertTrue(blocked.blocked)
        self.assertEqual(blocked.rate, 0)
        self.assertAlmostEqual(blocked.transfer, 0.78)
        self.assertEqual(blocked.transfer, contained.transfer)
        self.assertTrue(contained.contained)
        self.assertEqual(contained.severity[0], "INDDÆMMET")

    def test_every_view_fits_laptop_terminal_at_all_phases(self):
        for width, height in ((62, 22), (80, 24), (120, 40)):
            for mode in MODES:
                for fraction in (0, 0.2, 0.5, 0.7, 0.81, 0.95, 1):
                    with self.subTest(width=width, height=height, mode=mode, fraction=fraction):
                        lines = render(mode, Scene(180 * fraction, 180, len(self.records)),
                                       self.records, width, height)
                        self.assertLess(len(lines), height)
                        self.assertTrue(all(len(ANSI.sub("", line)) + 2 <= width for line in lines))
                        self.assertIn("FIKTIVE DATA", ANSI.sub("", "\n".join(lines)))
                        self.assertIn("Q AFSLUT", ANSI.sub("", lines[-1]))

    def test_extraction_uses_names_and_masked_cpr_fields(self):
        output = "\n".join(render("extract", Scene(180 * 0.48, 180, len(self.records)),
                                   self.records, 100, 32, color=False))
        self.assertIn(self.records[-1]["fuldt_navn"], output)
        self.assertIn("******-****", output)
        self.assertNotRegex(output, r"\b\d{6}-\d{4}\b")
        self.assertIn("500/500 POSTER", output)

    def test_transfer_screen_reports_interruption_and_soc_reports_containment(self):
        scene = Scene(175, 180, len(self.records))
        transfer = "\n".join(render("transfer", scene, self.records, 120, 32, color=False))
        soc = "\n".join(render("soc", scene, self.records, 120, 32, color=False))
        self.assertIn("AFBRUDT", transfer)
        self.assertIn("ANNULLERET", transfer)
        self.assertIn("0.0 MB/s", transfer)
        self.assertIn("FORBINDELSE: BLOKERET", soc)
        self.assertIn("HÆNDELSE INDDÆMMET", soc)

    def test_small_terminal_and_ascii_fallback(self):
        scene = Scene(90, 180, len(self.records))
        small = "\n".join(render("soc", scene, self.records, 40, 12, color=False))
        self.assertIn("Gør terminalen større", small)
        ascii_output = "\n".join(render("transfer", scene, self.records, color=False, unicode=False))
        self.assertNotRegex(ascii_output, "[█░─▁▂▃▄▅▆▇]")
        once = "\n".join(render("soc", scene, self.records, color=False, repeat=False))
        self.assertIn("ET ENKELT FORLØB", once)
        self.assertNotIn("GENTAGER AUTOMATISK", once)

    def test_name_file_validation_and_control_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.json"
            for invalid in ([], {}, [{"demo_id": "DEMO-1"}]):
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_records(path)
            path.write_text(json.dumps([{"demo_id": "DEMO-1", "fuldt_navn": "Anna\nJensen\x1b[2J"}]), encoding="utf-8")
            name = load_records(path)[0]["fuldt_navn"]
            self.assertNotIn("\x1b", name)
            self.assertNotIn("\n", name)

    def test_cli_works_from_another_directory_and_reports_missing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in MODES:
                result = subprocess.run([sys.executable, str(ROOT / "demo.py"), "--mode", mode,
                                         "--frames", "1", "--no-color"], cwd=directory,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("SIMULATION", result.stdout)
                self.assertNotIn("\x1b", result.stdout)
            missing = subprocess.run([sys.executable, str(ROOT / "demo.py"), "--frames", "1",
                                      "--names", str(Path(directory) / "missing.json")],
                                     capture_output=True, text=True)
            self.assertEqual(missing.returncode, 1)
            self.assertIn("Kan ikke indlæse navne", missing.stderr)


if __name__ == "__main__":
    unittest.main()
