"""The layout review's rules generated from what a board declares (electronics/tools/netrules.py): netclass
patterns that must match a net.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "electronics" / "tools"))

import eda  # noqa: E402
import netrules  # noqa: E402

# a sub-sheet's nets carry its path; power symbols and nets shared by several sheets don't
NAMES = ["GND", "VIN", "+5V_A", "/Power/BUCK_EN", "/Power/BUCKA_SW", "/Power/BUCKB_SW", "PORT1_EN",
         "/Port 1/PORT1_VBUS", "/Hub/UP_DP"]


class Patterns(unittest.TestCase):
    def test_kicad_semantics(self):
        # as KiCad 10.0.7 assigns them (each pattern alone in a class, read back from the DSN export)
        for pat, name, hit in (("*VIN", "VIN", True), ("*vin", "VIN", False),
                               ("BUCK_EN", "/Power/BUCK_EN", False), ("/Power/BUCK_EN", "/Power/BUCK_EN", True),
                               ("?Power/BUCK_EN", "/Power/BUCK_EN", True), ("UCK_E", "/Power/BUCK_EN", False),
                               ("/power/buck_en", "/Power/BUCK_EN", False), ("PORT[12]_EN", "PORT1_EN", True),
                               (".*BUCKA_SW", "/Power/BUCKA_SW", True), ("*BUCK?_SW", "/Power/BUCKB_SW", True),
                               ("+5V_A", "+5V_A", True), ("+5V", "+5V_A", False)):
            with self.subTest(pattern=pat, net=name):
                self.assertEqual(netrules.kicad_pattern_match(pat, name), hit)

    def test_unmatched_named_with_the_wildcard_that_reaches_it(self):
        classes = [{"name": "Power", "_patterns": ["+5V_A", "BUCK_EN", "VBUS"]},
                   {"name": "USB", "_patterns": ["*_DP", "*_DM"]}]
        bad = netrules.unmatched_patterns(classes, NAMES)
        self.assertEqual(len(bad), 3, bad)
        self.assertIn("netclass Power: pattern 'BUCK_EN' matches no net", bad[0])
        self.assertIn("'*BUCK_EN' takes /Power/BUCK_EN", bad[0])
        self.assertIn("'*VBUS' takes /Port 1/PORT1_VBUS", bad[1])
        self.assertEqual(bad[2], "netclass USB: pattern '*_DM' matches no net")

    def test_every_pattern_matching_passes(self):
        self.assertEqual(netrules.unmatched_patterns([{"name": "Power", "_patterns": ["*VIN", "*BUCK?_SW"]}], NAMES),
                         [])
        self.assertEqual(netrules.unmatched_patterns(None, NAMES), [])

    def test_build_stops_on_a_pattern_that_matches_nothing(self):
        class Stub:                       # what write_project reads before anything else
            name = "stub"

            @staticmethod
            def nets():
                return {n.rsplit("/", 1)[-1]: [] for n in NAMES}

            @staticmethod
            def pcb_net_name(net):
                return next(n for n in NAMES if n.rsplit("/", 1)[-1] == net)

        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit) as stop:
            eda.write_project(Stub(), Path(d), [{"name": "Power", "_patterns": ["BUCK_EN"]}])
        self.assertIn("'*BUCK_EN' takes /Power/BUCK_EN", str(stop.exception))
        self.assertFalse((Path(d) / "stub.kicad_pro").exists())


@unittest.skipUnless(eda.KICAD_SYMBOL_DIR.exists(), "KiCad's symbol library (KICAD_SYMBOL_DIR) not here")
class Boards(unittest.TestCase):
    def test_every_pattern_matches_a_net(self):
        import build_board
        for design in sorted((ROOT / "electronics").glob("*/design.py")):
            mod = build_board.load_design(design.parent.name)
            b = mod.board()
            with self.subTest(board=design.parent.name):
                bad = netrules.unmatched_patterns(getattr(mod, "NETCLASSES", None), {b.pcb_net_name(n) for n in b.nets()})
                self.assertEqual(bad, [], "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
