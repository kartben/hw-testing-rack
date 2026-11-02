"""Pair skew (electronics/tools/skew.py): the two lines of every High-Speed pair a board's design.py lists in
b.pcb["match"] run the same length within its "tol" (mm; the review of 2026-11-02: the upstream pair had lost its
compensation, 4.2 mm, unnoticed).  Every board's table is printed either way.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "electronics" / "tools"))

import build_board  # noqa: E402
import skew  # noqa: E402

DECLARES = re.compile(r"""["']match["']\s*:""")


class Boards(unittest.TestCase):
    def test_pairs_matched(self):
        rows = []
        for design in sorted((ROOT / "electronics").glob("*/design.py")):
            name = design.parent.name
            board = design.parent / f"{name}.kicad_pcb"
            if not board.exists() or not DECLARES.search(design.read_text(encoding="utf-8")):
                continue
            m = build_board.load_design(name).board().pcb["match"]
            tol = m.get("tol", 1.0)
            got = skew.skews(board, m["pairs"])
            rows += [f"{name:18s} {p:16s} {lp:8.3f} {n:16s} {ln:8.3f}  {lp - ln:+.3f}" for p, n, lp, ln in got]
            with self.subTest(board=name):
                bad = [f"{p} / {n}: {lp:.3f} / {ln:.3f} mm, skew {lp - ln:+.3f} (tol {tol})"
                       for p, n, lp, ln in got if not lp or not ln or abs(lp - ln) > tol]
                self.assertEqual(bad, [], "\n".join(bad))
        self.assertTrue(rows, "no board lists its High-Speed pairs")
        print("\n" + "\n".join(rows))


def seg(a, b, net):
    return f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width 0.25) (layer "F.Cu") (net "{net}"))'


class Synthetic(unittest.TestCase):
    def test_lengths(self):
        text = "(kicad_pcb " + " ".join([seg((0, 0), (3, 4), "/Hub/A_DP"), seg((3, 4), (3, 6), "/Hub/A_DP"),
                                         seg((0, 1), (6, 1), "A_DN")]) + ")"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text(text, encoding="utf-8")
            (p, n, lp, ln), = skew.skews(path, [("A_DP", "/Hub/A_DN")])
        self.assertAlmostEqual(lp, 7.0)
        self.assertAlmostEqual(ln, 6.0)
