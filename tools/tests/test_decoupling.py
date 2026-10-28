"""Decoupling (electronics/tools/decoupling.py): every capacitor a board's design.py declares in
b.pcb["decoupling"] sits within REACH of the power pin it serves, its return within VIA of a via, but on the boards
electronics/decoupling.json still lists as pending (the layout review, 2026-10-28).  A capacitor of 100 nF or less
also keeps the pin → cap → via order, but on the boards its "order_pending" list names.  Every board's table is
printed either way; a declaration that names no such pin or capacitor fails on every board.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "electronics" / "tools"))

import build_board  # noqa: E402
import decoupling  # noqa: E402

DECLARES = re.compile(r"""["']decoupling["']\s*:""")


class Boards(unittest.TestCase):
    def test_capacitors_beside_their_pins(self):
        lists = json.loads((ROOT / "electronics" / "decoupling.json").read_text(encoding="utf-8"))
        pending, order_pending = set(lists["pending"]), set(lists["order_pending"])
        tables = []
        for design in sorted((ROOT / "electronics").glob("*/design.py")):
            name = design.parent.name
            board = design.parent / f"{name}.kicad_pcb"
            if not board.exists() or not DECLARES.search(design.read_text(encoding="utf-8")):
                continue
            b = build_board.load_design(name).board()
            decl = b.pcb["decoupling"]
            rows = decoupling.check(board, decoupling.resolve(b, decl))
            tables.append(decoupling.table(name + ("  (pending)" if name in pending else "")
                                           + ("  (order pending)" if name in order_pending else ""), rows,
                                           decoupling.undeclared(board, decl)))
            with self.subTest(board=name):
                wrong = [f"{r['cap']}: {p}" for r in rows for p in r["problems"]
                         if r["net"] == "?" or r["ret"] == "?" or "more than one net" in p]
                self.assertEqual(wrong, [], "\n".join(wrong))
                if name not in pending:
                    far = [f"{r['cap']} ({r['pin']}): {p}" for r in rows for p in r["problems"]
                           if name not in order_pending or not p.startswith("order:")]
                    self.assertEqual(far, [], "\n".join(far))
        self.assertTrue(tables, "no board declares its decoupling")
        print("\n" + "\n".join(tables))


def pad(num, x, y, net, w=0.6, h=0.6, kind="smd", layers='"F.Cu"'):
    return f'(pad "{num}" {kind} rect (at {x} {y}) (size {w} {h}) (layers {layers}) (net "{net}"))'


def fp(ref, x, y, pads, rot=0, value=""):
    return (f'(footprint "x" (layer "F.Cu") (at {x} {y} {rot}) (property "Reference" "{ref}") '
            f'(property "Value" "{value}") {" ".join(pads)})')


def seg(a, b, net="+3V3", w=0.25):
    return f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width {w}) (layer "F.Cu") (net "{net}"))'


def pour(pts, net="+3V3"):
    xy = " ".join(f"(xy {x} {y})" for x, y in pts)
    return f'(zone (net "{net}") (layer "F.Cu") (filled_polygon (layer "F.Cu") (pts {xy})))'


def via(x, y, net="GND"):
    return f'(via (at {x} {y}) (size 0.5) (drill 0.3) (layers "F.Cu" "B.Cu") (net "{net}"))'


class Synthetic(unittest.TestCase):
    """U1 pin 1 (+3V3) at (0, 0), 0.6 mm square; C1 a 0402-ish pair, pad 1 on +3V3, pad 2 on GND, 1 mm apart (no value:
    the distances only; the order tests give it 100 nF)"""

    def run_check(self, cx, cy, extra=(), rot=0, decl="U1.1", value=""):
        parts = [fp("U1", 0, 0, [pad(1, 0, 0, "+3V3")]),
                 fp("C1", cx, cy, [pad(1, -0.5, 0, "+3V3", 0.5, 0.5), pad(2, 0.5, 0, "GND", 0.5, 0.5)], rot, value)]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text("(kicad_pcb " + " ".join(parts + list(extra)) + ")", encoding="utf-8")
            return decoupling.check(path, {"C1": decl})[0]

    def test_beside(self):
        r = self.run_check(1.55, 0, [via(2.8, 0)])           # C1.1's edge 0.5 from U1.1's, the via's 0.25 from C1.2's
        self.assertAlmostEqual(r["pin_mm"], 0.5, places=3)
        self.assertAlmostEqual(r["via_mm"], 0.25, places=3)
        self.assertEqual(r["problems"], [])

    def test_far(self):
        r = self.run_check(4.0, 0, [via(5.0, 0)])
        self.assertAlmostEqual(r["pin_mm"], 2.95, places=3)
        self.assertTrue(any("from U1.1" in p for p in r["problems"]), r)

    def test_own_limit(self):
        """A capacitor declared with its own limit (a datasheet's layout) is held to it, not to REACH"""
        r = self.run_check(4.0, 0, [via(5.0, 0)], decl=("U1.1", 3.0))        # 2.95 mm: within its 3 mm
        self.assertEqual(r["problems"], [])
        r = self.run_check(4.2, 0, [via(5.2, 0)], decl=("U1.1", 3.0))        # 3.15 mm: beyond it
        self.assertTrue(any("max 3.0" in p for p in r["problems"]), r)

    def test_own_limit_resolved(self):
        """resolve() carries the limit through to check()"""
        class Part:
            conns = {"VDD": "+3V3"}
        class B:
            parts = {"U1": Part()}
        decl = decoupling.resolve(B(), {"C1": ("U1.VDD", 3.0), "C2": "U1.VDD"})
        self.assertEqual(decl["C1"], ("U1.VDD", "+3V3", 3.0))
        self.assertEqual(decl["C2"], ("U1.VDD", "+3V3", decoupling.REACH))
        r = self.run_check(4.0, 0, [via(5.0, 0)], decl=decl["C1"])
        self.assertEqual(r["problems"], [])
        r = self.run_check(4.0, 0, [via(5.0, 0)], decl=decl["C2"])
        self.assertTrue(any("max 2.0" in p for p in r["problems"]), r)

    def test_order_kept(self):
        """pin → track → cap pad → track → its via: the pin → cap → via order"""
        r = self.run_check(1.55, 0, [via(2.8, 0), seg((0, 0), (1.05, 0)), seg((1.05, 0), (1.05, -1.0)),
                                     via(1.05, -1.0, "+3V3")], value="100n")
        self.assertIsNone(r["order"], r)
        self.assertEqual(r["problems"], [])

    def test_order_through_the_plane(self):
        """the pin and the cap each on its own via: they only meet through the plane"""
        r = self.run_check(1.55, 0, [via(2.8, 0), via(0, -1.0, "+3V3"), seg((0, 0), (0, -1.0)),
                                     via(1.05, -1.0, "+3V3"), seg((1.05, 0), (1.05, -1.0))], value="100n")
        self.assertTrue(r["order"] and r["order"].startswith("no copper"), r)

    def test_order_via_before_the_cap(self):
        """the pin reaches the cap by a track, but its own via too, not through the cap"""
        r = self.run_check(1.55, 0, [via(2.8, 0), seg((0, 0), (1.05, 0)), via(0, -1.0, "+3V3"),
                                     seg((0, 0), (0, -1.0))], value="100n")
        self.assertTrue(r["order"] and "before it" in r["order"], r)

    def test_order_track_through_the_cap(self):
        """the pin's one track straight across the cap pad, on to its via: the via is past the cap"""
        r = self.run_check(1.55, 1.0, [via(2.8, 1.0), seg((0, 0), (1.05, 0)), seg((1.05, 0), (1.05, 2.0)),
                                       via(1.05, 2.0, "+3V3")], value="100n")
        self.assertIsNone(r["order"], r)
        r = self.run_check(1.55, 1.0, [via(2.8, 1.0), seg((0, 0), (1.05, 0)), seg((1.05, 0), (1.05, 2.0)),
                                       via(0.55, 0, "+3V3")], value="100n")       # the via on the pin's side
        self.assertTrue(r["order"] and "before it" in r["order"], r)

    def test_order_bulk_exempt(self):
        """a 10 µF is held to the distances only"""
        parts = [fp("U1", 0, 0, [pad(1, 0, 0, "+3V3")]),
                 fp("C1", 1.55, 0, [pad(1, -0.5, 0, "+3V3", 0.5, 0.5), pad(2, 0.5, 0, "GND", 0.5, 0.5)], value="10u"),
                 via(2.8, 0), via(0, -1.0, "+3V3"), seg((0, 0), (0, -1.0))]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text("(kicad_pcb " + " ".join(parts) + ")", encoding="utf-8")
            r = decoupling.check(path, {"C1": "U1.1"})[0]
        self.assertFalse(r["small"])
        self.assertEqual(r["problems"], [])

    def test_order_across_a_pour(self):
        """pin and cap on one island of the rail: a via farther from the pin than the cap is fine, a nearer one isn't"""
        island = pour([(-0.5, -0.5), (6.0, -0.5), (6.0, 0.5), (-0.5, 0.5)])
        r = self.run_check(1.55, 0, [via(2.8, 0), island, via(5.0, 0, "+3V3")], value="100n")
        self.assertIsNone(r["order"], r)
        r = self.run_check(2.55, 0, [via(3.8, 0), island, via(0.7, 0, "+3V3")], value="100n")
        self.assertTrue(r["order"] and "across the pour" in r["order"], r)

    def test_turned(self):
        r = self.run_check(0, 1.55, [via(0, 2.55)], rot=-90)   # pad 1 towards the pin: KiCad turns y down
        self.assertAlmostEqual(r["pin_mm"], 0.5, places=3)

    def test_no_via(self):
        r = self.run_check(1.55, 0, [via(5.0, 0)])
        self.assertTrue(any("from a via" in p for p in r["problems"]), r)

    def test_wrong_net(self):
        parts = [fp("U1", 0, 0, [pad(1, 0, 0, "+5V")]),
                 fp("C1", 1.55, 0, [pad(1, -0.5, 0, "+3V3", 0.5, 0.5), pad(2, 0.5, 0, "GND", 0.5, 0.5)])]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text("(kicad_pcb " + " ".join(parts) + ")", encoding="utf-8")
            row = decoupling.check(path, {"C1": "U1.1"})[0]
        self.assertTrue(any("not on" in p for p in row["problems"]), row)


if __name__ == "__main__":
    unittest.main()
