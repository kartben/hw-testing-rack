"""Flow-through ESD (electronics/tools/flowthru.py): every line a board lists in its flow-through.json runs connector
→ ESD pad → partner pad → next part, with no bypass and no stub (the kicad-happy review's X2-1, 2026-10-27).

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

import flowthru  # noqa: E402


class Boards(unittest.TestCase):
    def test_every_listed_line_runs_through_its_esd(self):
        lists = sorted((ROOT / "electronics").glob("*/flow-through.json"))
        self.assertTrue(lists, "no board lists its flow-through lines")
        for lines in lists:
            board = next(lines.parent.glob(f"{lines.parent.name}.kicad_pcb"), None)
            with self.subTest(board=lines.parent.name):
                self.assertIsNotNone(board, f"{lines.parent.name}: no .kicad_pcb")
                fails = flowthru.check(board, lines)
                self.assertEqual(fails, [], "\n".join(fails))


def pad(num, x, y, net, w=0.3, h=0.6, layers='"F.Cu"'):
    return f'(pad "{num}" smd rect (at {x} {y}) (size {w} {h}) (layers {layers}) (net "{net}"))'


def fp(ref, x, y, pads):
    return f'(footprint "x" (layer "F.Cu") (at {x} {y}) (property "Reference" "{ref}") {" ".join(pads)})'


def seg(a, b, net, layer="F.Cu"):
    return f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width 0.127) (layer "{layer}") (net "{net}"))'


class Synthetic(unittest.TestCase):
    """A connector J1.1 at y 10, the ESD's pads U1.1 (y 6) and U1.2 (y 5), the next part R1.1 at y 1, one net"""
    PARTS = [fp("J1", 0, 10, [pad(1, 0, 0, "L", 1.0, 1.0, '"*.Cu"')]),
             fp("U1", 0, 0, [pad(1, 0, 6, "L"), pad(2, 0, 5, "L")]),
             fp("R1", 0, 1, [pad(1, 0, 0, "L")])]
    LINE = {"net": "L", "connector": "J1.1", "esd": ["U1.1", "U1.2"], "next": "R1.1"}

    def run_check(self, copper):
        text = "(kicad_pcb " + " ".join(self.PARTS + copper) + ")"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text(text, encoding="utf-8")
            return flowthru.check_line(flowthru.Board(path), self.LINE)

    def test_through(self):
        self.assertEqual(self.run_check([seg((0, 10), (0, 6), "L"), seg((0, 6), (0, 5), "L"),
                                         seg((0, 5), (0, 1), "L")]), [])

    def test_bypass(self):
        # the connector runs straight to the next part; the ESD hangs on a stub off that track
        fails = self.run_check([seg((0, 10), (1, 9), "L"), seg((1, 9), (1, 2), "L"), seg((1, 2), (0, 1), "L"),
                                seg((1, 6), (0, 6), "L"), seg((0, 6), (0, 5), "L")])
        self.assertTrue(any("without passing" in f for f in fails), fails)

    def test_stub(self):
        # through, but a dead branch hangs off the partner pad
        fails = self.run_check([seg((0, 10), (0, 6), "L"), seg((0, 6), (0, 5), "L"), seg((0, 5), (0, 1), "L"),
                                seg((0, 5), (2, 5), "L")])
        self.assertFalse(fails == [], fails)

    def test_wrong_order(self):
        # the connector reaches the partner pad, the next part the first pad
        fails = self.run_check([seg((0, 10), (1, 9), "L"), seg((1, 9), (1, 5), "L"), seg((1, 5), (0, 5), "L"),
                                seg((0, 5), (0, 6), "L"), seg((0, 6), (-1, 6), "L"), seg((-1, 6), (-1, 1), "L"),
                                seg((-1, 1), (0, 1), "L")])
        self.assertTrue(fails, fails)


if __name__ == "__main__":
    unittest.main()
