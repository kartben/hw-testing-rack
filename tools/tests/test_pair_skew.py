"""Link skew (electronics/tools/skew.py): the two sides of every High-Speed link a board's design.py lists in
b.pcb["skew"] (a chip's pin to the far pin: the hub's pair, its USBLC6, the crossover to the receptacle) run the
same length within its "tol" (mm), or within the figure "loose" gives that link with its reason (the review of
2026-11-02: the upstream pair had lost its compensation, 4.2 mm, unnoticed).  Every board's table is printed.

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

DECLARES = re.compile(r"""["']skew["']\s*:""")


class Boards(unittest.TestCase):
    def test_links_matched(self):
        rows = []
        for design in sorted((ROOT / "electronics").glob("*/design.py")):
            name = design.parent.name
            board = design.parent / f"{name}.kicad_pcb"
            if not board.exists() or not DECLARES.search(design.read_text(encoding="utf-8")):
                continue
            spec = build_board.load_design(name).board().pcb["skew"]
            loose = spec.get("loose", {})
            bad = []
            for link, lp, ln, missing in skew.skews(board, spec["links"]):
                lim = loose[link][0] if link in loose else spec["tol"]
                rows.append(f"{name:18s} {link:8s} {lp:8.3f} {ln:8.3f}  {lp - ln:+.3f}  (<= {lim})")
                if missing or abs(lp - ln) > lim:
                    bad.append(f"{link}: {lp:.3f} / {ln:.3f} mm, skew {lp - ln:+.3f} (<= {lim})"
                               + (f", no track on {' '.join(missing)}" if missing else ""))
            with self.subTest(board=name):
                self.assertEqual([k for k in loose if k not in spec["links"]], [], "loose names no link")
                self.assertEqual(bad, [], "\n".join(bad))
        self.assertTrue(rows, "no board lists its High-Speed links")
        print("\n" + "\n".join(rows))


def seg(a, b, net):
    return f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width 0.25) (layer "F.Cu") (net "{net}"))'


class Synthetic(unittest.TestCase):
    def test_lengths(self):
        text = "(kicad_pcb " + " ".join([seg((0, 0), (3, 4), "/Hub/A_DP"), seg((3, 4), (3, 6), "/Sheet/B_DP"),
                                         seg((0, 1), (6, 1), "A_DN")]) + ")"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.kicad_pcb"
            path.write_text(text, encoding="utf-8")
            (name, lp, ln, missing), = skew.skews(path, {"A": (("A_DP", "B_DP"), ("/Hub/A_DN", "B_DN"))})
        self.assertEqual((name, missing), ("A", ["B_DN"]))
        self.assertAlmostEqual(lp, 7.0)
        self.assertAlmostEqual(ln, 6.0)
