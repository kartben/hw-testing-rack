"""Antennas (electronics/tools/antennas.py): no dead end, lone via, doubled track or sliver on any board, but the
ones electronics/antennas.json still lists as pending (Eve's layout review, 2026-10-28).  Every board's count is
printed either way.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "electronics" / "tools"))

import antennas  # noqa: E402


class Boards(unittest.TestCase):
    def test_no_antennas(self):
        pending = set(json.loads((ROOT / "electronics" / "antennas.json").read_text(encoding="utf-8"))["pending"])
        boards = sorted(p for p in (ROOT / "electronics").glob("*/*.kicad_pcb") if p.stem == p.parent.name)
        self.assertTrue(boards)
        rows = []
        for board in boards:
            found = antennas.findings(board)
            kinds = {}
            for f in found:
                kinds[f.split(":")[0]] = kinds.get(f.split(":")[0], 0) + 1
            rows.append(f"  {board.stem:18} {len(found):4}  {kinds or ''}{'  (pending)' if board.stem in pending else ''}")
            if board.stem not in pending:
                with self.subTest(board=board.stem):
                    self.assertEqual(found, [], "\n".join(found))
        print("\nantennas per board:\n" + "\n".join(rows))


def pad(num, x, y, net, w=0.6, h=0.6):
    return f'(pad "{num}" smd rect (at {x} {y}) (size {w} {h}) (layers "F.Cu") (net "{net}"))'


def fp(ref, x, y, pads):
    return f'(footprint "x" (layer "F.Cu") (at {x} {y}) (property "Reference" "{ref}") {" ".join(pads)})'


def seg(a, b, net="N", layer="F.Cu", w=0.25):
    return f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width {w}) (layer "{layer}") (net "{net}"))'


def via(x, y, net="N"):
    return f'(via (at {x} {y}) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "{net}"))'


class Synthetic(unittest.TestCase):
    """Two pads of net N, P1 at (0, 0) and P2 at (10, 0)"""
    PARTS = [fp("P1", 0, 0, [pad(1, 0, 0, "N")]), fp("P2", 10, 0, [pad(1, 0, 0, "N")])]

    def run_check(self, copper):
        text = "(kicad_pcb " + " ".join(self.PARTS + copper) + ")"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text(text, encoding="utf-8")
            return antennas.findings(path)

    def test_clean(self):
        self.assertEqual(self.run_check([seg((0, 0), (5, 0)), seg((5, 0), (10, 0))]), [])

    def test_dead_end(self):
        found = self.run_check([seg((0, 0), (10, 0)), seg((5, 0), (5, 3))])
        self.assertTrue(any(f.startswith("dead end") for f in found), found)

    def test_double(self):
        found = self.run_check([seg((0, 0), (10, 0)), seg((2, 0), (6, 0))])
        self.assertTrue(any(f.startswith("double") for f in found), found)

    def test_sliver(self):
        found = self.run_check([seg((0, 0), (5, 0)), seg((5, 0), (5.05, 0)), seg((5.05, 0), (10, 0))])
        self.assertTrue(any(f.startswith("sliver") for f in found), found)

    def test_lone_via(self):
        found = self.run_check([seg((0, 0), (10, 0)), seg((5, 0), (5, 2)), via(5, 2)])
        self.assertTrue(any(f.startswith("lone via") for f in found), found)


if __name__ == "__main__":
    unittest.main()
