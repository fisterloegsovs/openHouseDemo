"""Kontrollér hændelsesforløbet og den terminalvisning, publikum ser."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from display import MODES, TOTAL_RECORDS, demo_cpr
from red_team import Scene, load_records, render

ROOT = Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_records(ROOT / "navne.json")

    def test_extraction_and_archiving_finish_before_transfer_completes(self):
        before = Scene(180 * 0.13, 180)
        extracted = Scene(180 * 0.52, 180)
        archived = Scene(180 * 0.58, 180)
        transferring = Scene(180 * 0.65, 180)
        completed = Scene(180 * 0.95, 180)
        self.assertEqual(before.extracted, 0)
        self.assertEqual(extracted.extracted, 8_800_000)
        self.assertIn("8.800.000", extracted.events()[-1][2])
        self.assertEqual(extracted.transfer, 0)
        self.assertAlmostEqual(archived.archive, 1)
        self.assertGreater(transferring.transfer, 0)
        self.assertGreater(transferring.rate, 0)
        self.assertEqual(completed.rate, 0)
        self.assertEqual(completed.transfer, 1)
        self.assertEqual(completed.phase[0], "TRANSFER COMPLETE / CPR-DATA")

    def test_extraction_count_advances_and_stops_at_8_8_million(self):
        counts = [Scene(180 * fraction, 180).extracted
                  for fraction in (0, 0.14, 0.2, 0.33, 0.51, 0.52, 0.95, 1)]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(counts[:2], [0, 0])
        self.assertEqual(counts[3], 4_400_000)
        self.assertEqual(counts[-3:], [8_800_000] * 3)

    def test_every_view_fits_laptop_terminal_at_all_phases(self):
        for width, height in ((62, 22), (80, 24), (120, 40), (180, 55), (260, 75)):
            for mode in MODES:
                for fraction in (0, 0.2, 0.5, 0.7, 0.81, 0.95, 1):
                    with self.subTest(width=width, height=height, mode=mode, fraction=fraction):
                        lines = render(mode, Scene(180 * fraction, 180),
                                       self.records, width, height)
                        self.assertEqual(len(lines), height)
                        self.assertTrue(all(len(ANSI.sub("", line)) == width - 1 for line in lines))
                        self.assertTrue(all(ANSI.sub("", line).strip() for line in lines))
                        self.assertIn("FIKTIVE DATA", ANSI.sub("", "\n".join(lines)))
                        self.assertIn("Q AFSLUT", ANSI.sub("", lines[-1]))

    def test_extraction_uses_names_and_prominent_fictional_cpr_fields(self):
        output = "\n".join(render("extract", Scene(180 * 0.52, 180),
                                   self.records, 100, 32, color=False))
        self.assertIn(self.records[-1]["fuldt_navn"], output)
        self.assertIn("CPR-NUMMER", output)
        self.assertIn(demo_cpr(TOTAL_RECORDS - 1), output)
        self.assertIn("8.800.000/8.800.000 CPR-POSTER", output)
        self.assertTrue(all(number.startswith("00") for number in re.findall(r"\b\d{6}-\d{4}\b", output)))

    def test_demo_cpr_values_are_unique_and_have_an_impossible_birth_day(self):
        # Kontrollér både gamle gentagelsesgrænser og værdier sidst i millionudtrækket.
        indices = set(range(0, TOTAL_RECORDS, 500))
        for start in (0, 9999, 999_999, TOTAL_RECORDS - 500):
            indices.update(range(start, start + 500))
        numbers = [demo_cpr(i) for i in indices]
        self.assertEqual(len(set(numbers)), len(indices))
        for number in numbers:
            self.assertRegex(number, r"^00\d{4}-\d{4}$")
            self.assertTrue(1 <= int(number[2:4]) <= 12)

    def test_cpr_target_visible_in_every_mode_even_on_a_small_laptop(self):
        for mode in MODES:
            output = "\n".join(render(mode, Scene(140, 180), self.records,
                                       62, 22, color=False))
            self.assertIn("CPR-REGISTER", output.splitlines()[0])
            self.assertIn("8.800.000", output.splitlines()[0])
            self.assertIn("CPR", output.splitlines()[2])

    def test_cpr_column_comes_first_and_has_a_distinct_color(self):
        lines = render("extract", Scene(100, 180), self.records, 100, 32)
        cpr = demo_cpr(TOTAL_RECORDS - 1)
        row = next(line for line in lines if cpr in line)
        self.assertIn("\033[40;1;93m" + cpr, row)
        plain = ANSI.sub("", row)
        self.assertLess(plain.index(cpr), plain.index(self.records[-1]["fuldt_navn"]))

    def test_red_team_finishes_transfer_without_defensive_content(self):
        scene = Scene(175, 180)
        transfer = "\n".join(render("transfer", scene, self.records, 120, 32, color=False))
        self.assertIn("TRANSFER COMPLETE", transfer)
        self.assertIn("2200.0/2200.0 MB", transfer)
        for mode in MODES:
            output = "\n".join(render(mode, scene, self.records, 180, 40, color=False))
            for defensive_term in ("SOC", "ALARM", "BLOKERET", "CONTAINED", "TRUSSELSNIVEAU"):
                self.assertNotIn(defensive_term, output)

    def test_small_terminal_and_ascii_fallback(self):
        scene = Scene(90, 180)
        small = "\n".join(render("overview", scene, self.records, 40, 12, color=False))
        self.assertIn("Gør terminalen større", small)
        ascii_output = "\n".join(render("transfer", scene, self.records, color=False, unicode=False))
        self.assertNotRegex(ascii_output, "[█░─▁▂▃▄▅▆▇]")
        once = "\n".join(render("overview", scene, self.records, color=False, repeat=False))
        self.assertIn("ET ENKELT FORLØB", once)
        self.assertNotIn("AUTO LOOP", once)

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
            default = subprocess.run([sys.executable, str(ROOT / "red_team.py"), "--frames", "1"],
                                     cwd=directory, capture_output=True, text=True)
            self.assertEqual(default.returncode, 0, default.stderr)
            self.assertIn("CPR-NUMMER", default.stdout)
            self.assertIn("8.800.000", default.stdout)
            for mode in MODES:
                result = subprocess.run([sys.executable, str(ROOT / "red_team.py"), "--mode", mode,
                                         "--frames", "1", "--no-color"], cwd=directory,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("SIMULATION", result.stdout)
                self.assertNotIn("\x1b", result.stdout)
            missing = subprocess.run([sys.executable, str(ROOT / "red_team.py"), "--frames", "1",
                                      "--names", str(Path(directory) / "missing.json")],
                                     capture_output=True, text=True)
            self.assertEqual(missing.returncode, 1)
            self.assertIn("Kan ikke indlæse navne", missing.stderr)


if __name__ == "__main__":
    unittest.main()
