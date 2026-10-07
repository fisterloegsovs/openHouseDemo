from pathlib import Path
import re
import subprocess
import sys
import unittest

from blue_display import MODES, render
from blue_team import Scene

ROOT = Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class BlueTeamTests(unittest.TestCase):
    def test_anomaly_triage_block_and_containment(self):
        baseline = Scene(0, 180)
        anomaly = Scene(180 * 0.25, 180)
        critical = Scene(180 * 0.60, 180)
        blocked = Scene(180 * 0.85, 180)
        resolved = Scene(180 * 0.96, 180)
        self.assertEqual(baseline.alerts, 0)
        self.assertEqual(baseline.severity[0], "NORMAL")
        self.assertGreater(anomaly.alerts, 0)
        self.assertEqual(critical.severity[0], "CRITICAL")
        self.assertFalse(critical.blocked)
        self.assertTrue(blocked.blocked)
        self.assertTrue(resolved.resolved)
        self.assertEqual(resolved.severity[0], "CONTAINED")

    def test_all_views_fill_terminal_and_preserve_notice(self):
        for width, height in ((62, 22), (80, 24), (120, 40), (180, 55), (260, 75)):
            for mode in MODES:
                for fraction in (0, 0.25, 0.60, 0.85, 0.96):
                    with self.subTest(width=width, height=height, mode=mode, fraction=fraction):
                        lines = render(mode, Scene(180 * fraction, 180), width, height)
                        plain = [ANSI.sub("", line) for line in lines]
                        self.assertEqual(len(plain), height)
                        self.assertTrue(all(len(line) == width - 1 for line in plain))
                        self.assertTrue(all(line.strip() for line in plain))
                        self.assertIn("FIKTIVE DATA", "\n".join(plain))
                        self.assertIn("Q AFSLUT", plain[-1])

    def test_defensive_views_show_drops_and_completed_response(self):
        scene = Scene(175, 180)
        traffic = "\n".join(render("traffic", scene, 120, 40, color=False))
        response = "\n".join(render("response", scene, 120, 40, color=False))
        self.assertIn("EGRESS POLICY: DENY", traffic)
        self.assertIn("DROP", traffic)
        self.assertIn("[DONE] BLOCK", response)
        self.assertIn("INCIDENT CONTAINED", response)
        self.assertNotIn("root@ghost", response)

    def test_live_content_changes_without_waiting_for_new_phase(self):
        for mode in MODES:
            first = render(mode, Scene(50, 180), 180, 50, color=False)
            second = render(mode, Scene(50.4, 180), 180, 50, color=False)
            self.assertNotEqual(first, second)

    def test_cli_apps_have_separate_modes_and_blue_needs_no_names(self):
        for mode in MODES:
            result = subprocess.run([sys.executable, str(ROOT / "blue_team.py"), "--mode", mode,
                                     "--frames", "1", "--no-color"], cwd='/tmp',
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("S E N T I N E L", result.stdout)
            self.assertNotIn("\x1b", result.stdout)
        for script, unavailable_mode in (("red_team.py", "alerts"), ("blue_team.py", "extract")):
            result = subprocess.run([sys.executable, str(ROOT / script), "--mode", unavailable_mode,
                                     "--frames", "1"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
