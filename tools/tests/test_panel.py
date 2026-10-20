"""Tests for the order panel (electronics/tools/panelize.py): where each copy lands, and that the committed panel
BOM and CPL hold each copy's own variant, moved and turned with it.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "electronics" / "tools"))

import build_board  # noqa: E402
import panelize  # noqa: E402

SPEC = {"gap": 2.0, "boards": [{"tag": "L", "variant": None, "rot": 0}, {"tag": "B", "variant": "base", "rot": 180}]}


class Placement(unittest.TestCase):
    def test_first_copy_stays(self):
        _, _, rot, f = panelize.placement(SPEC, (100, 70))[0]
        self.assertEqual(rot, 0)
        for got, want in zip(f(9.7, 55.7), (9.7, 55.7)):
            self.assertAlmostEqual(got, want, places=9)

    def test_turned_copy_meets_top_to_top(self):
        _, _, rot, f = panelize.placement(SPEC, (100, 70))[1]
        self.assertEqual(rot, 180)
        for (x, y), (px, py) in (((0, 0), (100, -2)), ((100, 70), (0, -72)), ((9, 0), (91, -2))):
            gx, gy = f(x, y)
            self.assertAlmostEqual(gx, px, places=9)
            self.assertAlmostEqual(gy, py, places=9)


class CommittedPanel(unittest.TestCase):
    def test_halves_match_variants(self):
        name = "data-port-x4-v2"
        outdir = REPO / "electronics" / name
        if not (outdir / "fab" / f"{name}-panel-cpl-jlcpcb.csv").exists():
            self.skipTest("no panel outputs")
        b = build_board.load_design(name).board()
        self.assertEqual(panelize.check_halves(outdir, name, b.pcb["panel"], b.pcb["size"]), [])


if __name__ == "__main__":
    unittest.main()
