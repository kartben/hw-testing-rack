"""Decoupling (electronics/tools/decoupling.py): every capacitor a board's design.py declares in
b.pcb["decoupling"] sits within REACH of the power pin it serves, its return within VIA of a via, but on the boards
electronics/decoupling.json still lists as pending (Eve's layout review, 2026-10-28).  Every board's table is
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
        pending = set(json.loads((ROOT / "electronics" / "decoupling.json").read_text(encoding="utf-8"))["pending"])
        tables = []
        for design in sorted((ROOT / "electronics").glob("*/design.py")):
            name = design.parent.name
            board = design.parent / f"{name}.kicad_pcb"
            if not board.exists() or not DECLARES.search(design.read_text(encoding="utf-8")):
                continue
            b = build_board.load_design(name).board()
            decl = b.pcb["decoupling"]
            rows = decoupling.check(board, decoupling.resolve(b, decl))
            tables.append(decoupling.table(name + ("  (pending)" if name in pending else ""), rows,
                                           decoupling.undeclared(board, decl)))
            with self.subTest(board=name):
                wrong = [f"{r['cap']}: {p}" for r in rows for p in r["problems"]
                         if r["net"] == "?" or r["ret"] == "?" or "more than one net" in p]
                self.assertEqual(wrong, [], "\n".join(wrong))
                if name not in pending:
                    far = [f"{r['cap']} ({r['pin']}): {p}" for r in rows for p in r["problems"]]
                    self.assertEqual(far, [], "\n".join(far))
        self.assertTrue(tables, "no board declares its decoupling")
        print("\n" + "\n".join(tables))


def pad(num, x, y, net, w=0.6, h=0.6, kind="smd", layers='"F.Cu"'):
    return f'(pad "{num}" {kind} rect (at {x} {y}) (size {w} {h}) (layers {layers}) (net "{net}"))'


def fp(ref, x, y, pads, rot=0):
    return f'(footprint "x" (layer "F.Cu") (at {x} {y} {rot}) (property "Reference" "{ref}") {" ".join(pads)})'


def via(x, y, net="GND"):
    return f'(via (at {x} {y}) (size 0.5) (drill 0.3) (layers "F.Cu" "B.Cu") (net "{net}"))'


class Synthetic(unittest.TestCase):
    """U1 pin 1 (+3V3) at (0, 0), 0.6 mm square; C1 a 0402-ish pair, pad 1 on +3V3, pad 2 on GND, 1 mm apart"""

    def run_check(self, cx, cy, extra=(), rot=0):
        parts = [fp("U1", 0, 0, [pad(1, 0, 0, "+3V3")]),
                 fp("C1", cx, cy, [pad(1, -0.5, 0, "+3V3", 0.5, 0.5), pad(2, 0.5, 0, "GND", 0.5, 0.5)], rot)]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text("(kicad_pcb " + " ".join(parts + list(extra)) + ")", encoding="utf-8")
            return decoupling.check(path, {"C1": "U1.1"})[0]

    def test_beside(self):
        r = self.run_check(1.55, 0, [via(2.8, 0)])           # C1.1's edge 0.5 from U1.1's, the via's 0.25 from C1.2's
        self.assertAlmostEqual(r["pin_mm"], 0.5, places=3)
        self.assertAlmostEqual(r["via_mm"], 0.25, places=3)
        self.assertEqual(r["problems"], [])

    def test_far(self):
        r = self.run_check(4.0, 0, [via(5.0, 0)])
        self.assertAlmostEqual(r["pin_mm"], 2.95, places=3)
        self.assertTrue(any("from U1.1" in p for p in r["problems"]), r)

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
