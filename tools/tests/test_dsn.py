"""Tests for the DSN edits made before Freerouting reads a board (electronics/tools/dsn.py) and the route farm's
run bookkeeping (tools/route_farm.py).

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "electronics" / "tools"))
sys.path.insert(0, str(REPO / "tools"))

import dsn  # noqa: E402
import route_farm  # noqa: E402

# the shape of KiCad 10's export, cut down: a split power layer (In2) with two nets' planes
BOARD = """(pcb "/work/x.dsn"
  (parser
    (string_quote ")
    (space_in_quoted_tokens on)
    (host_cad "KiCad's Pcbnew")
  )
  (resolution um 10)
  (unit um)
  (structure
    (layer F.Cu
      (type signal)
      (property
        (index 0)
      )
    )
    (layer In1.GND
      (type power)
      (property
        (index 1)
      )
    )
    (layer In2.PWR
      (type power)
      (property
        (index 2)
      )
    )
    (layer B.Cu
      (type signal)
      (property
        (index 3)
      )
    )
    (boundary
      (path pcb 0  0 0  50000 0  50000 -30000  0 -30000  0 0)
    )
    (plane GND (polygon In1.GND 0  400 -400  49600 -400  49600 -29600  400 -29600  400 -400))
    (plane +3V3 (polygon In2.PWR 0  400 -400  30000 -400  30000 -29600  400 -29600  400 -400))
    (plane "+5 V" (polygon In2.PWR 0  20000 -400  49600 -400  49600 -29600  20000 -29600  20000 -400))
  )
  (placement
    (component R1 (place R1 1000 -1000 front 0 (PN "10k")))
    (component R2 (place R2 2000 -1000 front 0 (PN "10k")))
    (component R3 (place R3 3000 -1000 front 0 (PN "10k")))
  )
  (network
    (net A (pins R1-1 R2-1))
    (net B (pins R2-2 R3-1))
    (net "C D" (pins R1-2 R3-2))
    (class kicad_default "" A B "C D" (circuit (use_via Via)))
  )
  (wiring
    (via "Via[0-3]_600:300_um"  10750 -6800 (net +3V3)(type fix))
  )
)
"""


class Spans(unittest.TestCase):
    def test_string_quote_is_one_character(self):
        # the parser block's lone '"' must not open a string that swallows the rest of the file
        top = dsn.find(BOARD)
        self.assertEqual(top, (0, len(BOARD.rstrip())))
        self.assertEqual([k for _, _, k in dsn.children(BOARD, *top)],
                         ["parser", "resolution", "unit", "structure", "placement", "network", "wiring"])

    def test_planes(self):
        got = [(net, layer) for _, _, net, layer in dsn.planes(BOARD)]
        self.assertEqual(got, [("GND", "In1.GND"), ("+3V3", "In2.PWR"), ('"+5 V"', "In2.PWR")])


class Shuffle(unittest.TestCase):
    def test_same_lists_other_order(self):
        out = dsn.shuffle(BOARD, 3)
        nets = lambda t: [t[a:b] for a, b, k in dsn.children(t, *dsn.find(t, "network")) if k == "net"]
        comps = lambda t: [t[a:b] for a, b, k in dsn.children(t, *dsn.find(t, "placement")) if k == "component"]
        self.assertEqual(sorted(nets(out)), sorted(nets(BOARD)))
        self.assertEqual(sorted(comps(out)), sorted(comps(BOARD)))
        self.assertEqual(len(out), len(BOARD))
        # the class list stays after the nets, everything outside network/placement as it was
        self.assertIn('(class kicad_default "" A B "C D"', out)
        self.assertEqual(out[:out.index("(placement")], BOARD[:BOARD.index("(placement")])

    def test_deterministic(self):
        self.assertEqual(dsn.shuffle(BOARD, 7), dsn.shuffle(BOARD, 7))
        self.assertNotEqual([dsn.shuffle(BOARD, s) for s in range(1, 6)], [BOARD] * 5)


class ReplacePlanes(unittest.TestCase):
    def test_cut_plane_written_like_kicad(self):
        # +3V3 cut back to x 19.75 mm (the +5 V area and its clearance): KiCad axes in, µm with Y up out
        area = [(0.4, 0.4), (19.75, 0.4), (19.75, 29.6), (0.4, 29.6)]
        out = dsn.replace_planes(BOARD, {1: [area]})
        self.assertIn("(plane +3V3 (polygon In2.PWR 0  400 -400  19750 -400  19750 -29600  400 -29600  400 -400))", out)
        self.assertIn('(plane "+5 V" (polygon In2.PWR 0  20000 -400', out)       # untouched
        self.assertEqual(len(dsn.planes(out)), 3)

    def test_several_outlines_and_none(self):
        a = [(0.4, 0.4), (5, 0.4), (5, 5), (0.4, 5)]
        b = [(10, 10), (15, 10), (15, 15), (10, 15)]
        out = dsn.replace_planes(BOARD, {1: [a, b], 2: []})
        self.assertEqual([(net, layer) for _, _, net, layer in dsn.planes(out)],
                         [("GND", "In1.GND"), ("+3V3", "In2.PWR"), ("+3V3", "In2.PWR")])
        self.assertEqual(dsn.find(out)[1], len(out.rstrip()))           # still one balanced file


class SplitAsSignals(unittest.TestCase):
    def test_split_layer_becomes_a_wireless_signal_layer(self):
        out, layers = dsn.split_planes_as_signals(BOARD)
        self.assertEqual(layers, ["In2.PWR"])
        types = {dsn.atoms(out[a:b])[1]: "(type power)" in out[a:b]
                 for a, b, k in dsn.children(out, *dsn.find(out, "structure")) if k == "layer"}
        self.assertEqual(types, {"F.Cu": False, "In1.GND": True, "In2.PWR": False, "B.Cu": False})
        keep = [out[a:b] for a, b, k in dsn.children(out, *dsn.find(out, "structure")) if k == "wire_keepout"]
        self.assertEqual(keep, ['(wire_keepout "split-plane" (polygon In2.PWR 0  -1000 -31000  51000 -31000  '
                                '51000 1000  -1000 1000  -1000 -31000))'])
        self.assertEqual(len(dsn.planes(out)), 3)

    def test_single_net_plane_kept(self):
        one = BOARD.replace('(plane "+5 V" (polygon In2.PWR', '(plane GND (polygon B.Cu')
        self.assertEqual(dsn.split_planes_as_signals(one), (one, []))


class NoViaAtSmd(unittest.TestCase):
    def test_control_in_structure(self):
        out = dsn.no_via_at_smd(BOARD)
        s, e = dsn.find(out, "structure")
        ctl = [out[a:b] for a, b, k in dsn.children(out, s, e) if k == "control"]
        self.assertEqual(ctl, ["(control (via_at_smd off))"])
        self.assertEqual(out.replace("(control (via_at_smd off))", "").replace("\n    \n", "\n"), BOARD)

    def test_replaces_an_existing_control(self):
        out = dsn.no_via_at_smd(dsn.no_via_at_smd(BOARD).replace("via_at_smd off", "via_at_smd on"))
        self.assertEqual(out.count("(control"), 1)
        self.assertIn("(control (via_at_smd off))", out)


class DropKeepouts(unittest.TestCase):
    # as KiCad writes rule areas: a footprint keep-out on both faces, a real one, a wire_keepout; one wrapped line
    AREAS = BOARD.replace(
        '    (plane "+5 V"',
        '    (keepout "" (polygon F.Cu 0  0 0  5500 0  5500 -30000  0 -30000  0 0))\n'
        '    (keepout "" (polygon B.Cu 0  0 0  5500 0  5500 -30000  0 -30000  0 0))\n'
        '    (keepout "" (polygon F.Cu 0  31000 -24000  38000 -24000  38000 -30000  31000 -30000\n'
        '            31000 -24000))\n'
        '    (wire_keepout "" (polygon F.Cu 0  0 0  5500 0  5500 -30000  0 -30000  0 0))\n'
        '    (plane "+5 V"')

    def test_only_the_areas_named_go(self):
        band = [(0, 0), (5500, 0), (5500, -30000), (0, -30000)]           # any order, no closing repeat
        out = dsn.drop_keepouts(self.AREAS, [("F.Cu", band[::-1]), ("B.Cu", band),
                                             ("F.Cu", [(31000.2, -24000), (38000, -24000), (38000, -30000),
                                                       (31000, -30000)])])
        kids = [(k, out[a:b]) for a, b, k in dsn.children(out, *dsn.find(out, "structure"))]
        self.assertEqual([k for k, _ in kids if "keepout" in k], ["wire_keepout"])
        self.assertEqual(out, BOARD.replace('    (plane "+5 V"', '    (wire_keepout "" (polygon F.Cu 0  0 0  5500 0  '
                                            '5500 -30000  0 -30000  0 0))\n    (plane "+5 V"'))

    def test_other_shape_or_layer_kept(self):
        band = [(0, 0), (5500, 0), (5500, -30000), (0, -30000)]
        self.assertEqual(dsn.drop_keepouts(self.AREAS, [("In1.GND", band), ("F.Cu", band[:3])]), self.AREAS)
        self.assertEqual(dsn.drop_keepouts(self.AREAS, []), self.AREAS)


class ClassClearance(unittest.TestCase):
    # KiCad 10 names each net's classes together: a Sensitive net's class is "Sensitive,Default"
    CLASSES = BOARD.replace('    (class kicad_default "" A B "C D" (circuit (use_via Via)))\n',
                            '    (class kicad_default "" (circuit (use_via Via)))\n'
                            "    (class Sensitive,Default A (circuit (use_via Via)) (rule (width 127) (clearance 100)))\n"
                            "    (class USB,Default B (circuit (use_via Via)) (rule (width 250) (clearance 127)))\n"
                            '    (class "USB,Pins,Default" "C D" (rule (width 250) (clearance 127)))\n')

    def test_one_entry_per_pair_of_classes_at_the_end_of_the_network(self):
        out = dsn.class_clearance(self.CLASSES, "Sensitive", "USB", 750)
        kids = [(k, out[a:b]) for a, b, k in dsn.children(out, *dsn.find(out, "network"))]
        self.assertEqual([k for k, _ in kids], ["net", "net", "net", "class", "class", "class", "class",
                                                "class_class", "class_class"])
        self.assertEqual(kids[-2][1], "(class_class (classes Sensitive,Default USB,Default)\n"
                                      "      (rule (clearance 750))\n    )")
        self.assertIn("(classes Sensitive,Default USB,Pins,Default)", kids[-1][1])
        self.assertEqual(dsn.find(out)[1], len(out.rstrip()))           # still one balanced file
        # what follows the network as KiCad wrote it
        self.assertEqual(out[out.index("  (wiring"):], self.CLASSES[self.CLASSES.index("  (wiring"):])

    def test_canonical_keeps_it(self):
        out = dsn.canonical(dsn.class_clearance(self.CLASSES, "Sensitive", "USB", 752))
        self.assertIn("(rule (clearance 752))", out)

    def test_nothing_without_both_classes(self):
        self.assertEqual(dsn.class_clearance(BOARD, "Sensitive", "USB", 750), BOARD)
        self.assertEqual(dsn.class_clearance(self.CLASSES, "Sensitive", "HDMI", 750), self.CLASSES)


class Canonical(unittest.TestCase):
    # what changes between two KiCad exports of one board: list order, a fixed track's grouping into paths,
    # the numbering of same-name footprint images, their coordinates' last digit
    LIB = """  (library
    (image R_0805
      (pin Rect[T]Pad 1 -900 0)
    )
    (image MH
      (pin Round[A]Pad 1 0 0)
      (keepout "" (circle F.Cu 5000 0 0))
    )
    (image MH::1
      (pin Round[A]Pad 1 0 0)
      (keepout "" (polygon F.Cu 0  -2706.44 1167.44  2706.44 1167.44))
    )
  )
"""
    WIRING = """  (wiring
    (wire (path F.Cu 250  0 0  1000 0  1000 1000)(net A)(type fix))
    (via "Via[0-3]_600:300_um"  10750 -6800 (net +3V3)(type fix))
  )
"""

    def build(self, order: int, images: str, wiring: str) -> str:
        t = BOARD.replace("  (network", images + "  (network")
        t = dsn.shuffle(t, order) if order else t
        return t.replace("""  (wiring
    (via "Via[0-3]_600:300_um"  10750 -6800 (net +3V3)(type fix))
  )
""", wiring)

    def test_two_exports_one_text(self):
        a = self.build(0, self.LIB, self.WIRING)
        # the other export: components and nets in another order, the two MH images swapped and their
        # keep-out a hundredth of a µm off, the track in two pieces and after the via
        lib_b = self.LIB.replace("(image MH\n", "(image MH::X\n").replace("(image MH::1\n", "(image MH\n") \
            .replace("(image MH::X\n", "(image MH::1\n").replace("-2706.44 1167.44  2706.44", "-2706.43 1167.44  2706.43")
        wiring_b = """  (wiring
    (via "Via[0-3]_600:300_um"  10750 -6800 (net +3V3)(type fix))
    (wire (path F.Cu 250  1000 0  1000 1000)(net A)(type fix))
    (wire (path F.Cu 250  0 0  1000 0)(net A)(type fix))
  )
"""
        b = self.build(5, lib_b, wiring_b)
        self.assertNotEqual(a, b)
        self.assertEqual(dsn.canonical(a), dsn.canonical(b))

    def test_idempotent_and_whole(self):
        c = dsn.canonical(self.build(2, self.LIB, self.WIRING))
        self.assertEqual(dsn.canonical(c), c)
        self.assertEqual(dsn.find(c)[1], len(c.rstrip()))
        self.assertEqual(sorted(dsn.atoms(c[a:b])[1].split("::")[0] for a, b, k in
                                dsn.children(c, *dsn.find(c, "library")) if k == "image"), ["MH", "MH", "R_0805"])


class FarmRuns(unittest.TestCase):
    def test_run_dsn(self):
        self.assertEqual(route_farm.run_dsn(BOARD, {}), BOARD)
        self.assertEqual(route_farm.run_dsn(BOARD, {"order": 2}), dsn.shuffle(BOARD, 2))
        self.assertIn("split-plane", route_farm.run_dsn(BOARD, {"planes": "signals"}))

    def test_rank(self):
        s = lambda unc, cu, vias, mm: {"drc": {"unconnected": unc, "parity": 0, "copper": {"clearance": cu} if cu else {}},
                                       "routing": {"vias": vias, "length_mm": mm}}
        runs = {"a": s(0, 0, 40, 200.0), "b": s(0, 0, 20, 230.0), "c": s(1, 0, 0, 10.0), "d": s(0, 2, 0, 10.0), "e": {}}
        order = sorted(runs, key=lambda r: route_farm.rank_key(runs[r]))
        # complete first, then clean, then copper + 2 mm a via: b (230 + 40) before a (200 + 80)
        self.assertEqual(order, ["b", "a", "d", "c", "e"])

    def test_rank_bends(self):
        # as long, as many vias: the straighter first, a bend counting 0.5 mm
        s = lambda bends: {"drc": {"unconnected": 0, "parity": 0, "copper": {}},
                           "routing": {"vias": 10, "length_mm": 100.0, "bends": bends}}
        self.assertLess(route_farm.rank_key(s(40)), route_farm.rank_key(s(60)))
        self.assertEqual(route_farm.cost(s(40)), 100.0 + 2 * 10 + 0.5 * 40)
