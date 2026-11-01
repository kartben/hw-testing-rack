"""The layout review's rules generated from what a board declares (electronics/tools/netrules.py): netclass
patterns that must match a net, the power classes' minimum width, the Sensitive class kept off the USB lines.

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
NAMES = ["GND", "VIN", "+3V3", "+5V_A", "/Power/BUCK_EN", "/Power/BUCKA_SW", "/Power/BUCKB_SW", "PORT1_EN",
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
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit) as stop:
            eda.write_project(Stub(), Path(d), [{"name": "Power", "_patterns": ["BUCK_EN"]}])
        self.assertIn("'*BUCK_EN' takes /Power/BUCK_EN", str(stop.exception))
        self.assertFalse((Path(d) / "stub.kicad_pro").exists())


class Stub:
    """What eda.write_project reads of a Board."""
    name, rev, root_uuid, sheets = "stub", "1", "00000000-0000-0000-0000-000000000000", []

    @staticmethod
    def nets():
        return {n.rsplit("/", 1)[-1]: [] for n in NAMES}

    @staticmethod
    def pcb_net_name(net):
        return next(n for n in NAMES if n.rsplit("/", 1)[-1] == net)


# the DATA x6's classes, cut down to what the rules read
X6 = [{"name": "Default", "clearance": 0.1, "track_width": 0.127},
      {"name": "Supply", "track_width": 0.25, "_patterns": ["+3V3"], "_min_width": 0.25},
      {"name": "Power", "track_width": 0.6, "_patterns": ["*VIN"], "_min_width": 0.25},
      {"name": "Port", "track_width": 0.3, "_patterns": ["*PORT?_VBUS"], "_min_width": 0.25},
      {"name": "Sensitive", "track_width": 0.127, "_patterns": ["*PORT?_EN"]},
      {"name": "USB", "track_width": 0.25, "diff_pair_width": 0.25, "_patterns": ["*_DP"]}]
X6_EXCEPT = {"courtyards": ["U1"], "nets": ["HUB_1V8PLL"], "why": "in the hub's fan-out"}


class Rules(unittest.TestCase):
    def test_power_classes_floor(self):
        text = netrules.min_width_rules(X6, {"min_width_except": X6_EXCEPT}, lambda n: f"/Hub/{n}")
        self.assertEqual(text, """
(rule "Supply, Power and Port: 0.25 mm at least, but in the hub's fan-out"
	(severity error)
	(condition "A.Type == 'Track' && (A.hasNetclass('Supply') || A.hasNetclass('Power') || A.hasNetclass('Port')) && !A.intersectsCourtyard('U1') && !(A.NetName == '/Hub/HUB_1V8PLL')")
	(constraint track_width (min 0.25mm)))
""")

    def test_one_rule_per_width_the_widest_last(self):
        classes = [{"name": "A", "_min_width": 0.4}, {"name": "B", "_min_width": 0.25}, {"name": "C"}]
        text = netrules.min_width_rules(classes, {})
        self.assertLess(text.index('"B: 0.25 mm at least"'), text.index('"A: 0.4 mm at least"'))
        self.assertEqual(text.count("(rule "), 2)
        self.assertNotIn("intersectsCourtyard", text)

    def test_sensitive_three_usb_widths_off(self):
        self.assertEqual(netrules.sensitive_rules(X6), """
(rule "Sensitive: 0.75 mm off USB, 3 times its track width"
	(severity error)
	(condition "A.hasNetclass('USB') && B.hasNetclass('Sensitive')")
	(constraint clearance (min 0.75mm)))
""")
        narrow = [nc if nc["name"] != "USB" else {**nc, "track_width": 0.15, "diff_pair_width": 0.15} for nc in X6]
        self.assertEqual(netrules.sensitive_spacing(narrow), [("Sensitive", "USB", 0.45)])

    def test_nothing_declared_nothing_generated(self):
        plain = [{"name": "Power", "track_width": 0.6, "_patterns": ["*VIN"]},
                 {"name": "USB", "track_width": 0.25, "_patterns": ["*_DP"]}]
        self.assertEqual(netrules.class_rules(plain, {}), "")
        self.assertEqual(netrules.class_rules(None, {}), "")
        self.assertEqual(netrules.sensitive_rules([{"name": "Sensitive", "_patterns": ["*EN"]}]), "")

    def test_no_track_angle_constraint(self):
        # KiCad drops the whole .kicad_dru on one, without a word
        self.assertNotIn("track_angle", netrules.class_rules(X6, {"min_width_except": X6_EXCEPT}))

    def test_generator_keys_stay_out_of_the_project(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            eda.write_project(Stub(), Path(d), X6)
            classes = json.loads((Path(d) / "stub.kicad_pro").read_text(encoding="utf-8"))["net_settings"]["classes"]
        self.assertEqual([c["name"] for c in classes], ["Default", "Supply", "Power", "Port", "Sensitive", "USB"])
        self.assertFalse([k for c in classes for k in c if k.startswith("_")])


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

    def test_committed_rules_carry_what_the_netclasses_ask(self):
        import build_board
        for design in sorted((ROOT / "electronics").glob("*/design.py")):
            name = design.parent.name
            dru = design.parent / f"{name}.kicad_dru"
            if not dru.exists():
                continue
            mod = build_board.load_design(name)
            b = mod.board()
            with self.subTest(board=name):
                rules = netrules.class_rules(getattr(mod, "NETCLASSES", None), b.pcb, b.pcb_net_name)
                self.assertIn(rules, dru.read_text(encoding="utf-8"), "run tools/kicad.sh <board> --rules")


if __name__ == "__main__":
    unittest.main()
