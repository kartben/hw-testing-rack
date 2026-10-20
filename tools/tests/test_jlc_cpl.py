"""Tests for the JLC placement file rows (electronics/tools/build_board.py › jlc_cpl_row).

JLC places its own (EasyEDA) footprint at each CPL point.  On the bottom side it takes the position as seen
from the top and the rotation as seen from above the part: 180° − KiCad's, plus the part's correction.

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


class JlcCplRow(unittest.TestCase):
    def row(self, side, rot, lcsc="", package="SOT-23-5"):
        r = {"Ref": "U1", "PosX": "10.000000", "PosY": "-5.000000", "Rot": f"{rot:.6f}", "Side": side,
             "Package": package}
        return build_board.jlc_cpl_row(r, lcsc)

    def test_plain(self):
        self.assertEqual(self.row("top", 90), ["U1", "10.000000mm", "-5.000000mm", "Top", "90.000000"])
        self.assertEqual(self.row("bottom", 0), ["U1", "10.000000mm", "-5.000000mm", "Bottom", "180.000000"])
        self.assertEqual(self.row("bottom", 90)[4], "90.000000")
        self.assertEqual(self.row("bottom", 180)[4], "0.000000")

    def test_corrected(self):
        # AP2112K C51118: JLC draws it 270° from KiCad (top: 0 → 270; bottom: 180 − 0 + 270 → 90)
        self.assertEqual(self.row("top", 0, "C51118")[4], "-90.000000")
        self.assertEqual(self.row("bottom", 0, "C51118")[4], "90.000000")

    def test_offset_mirrored(self):
        # an origin offset along the footprint's y lands on the other side once mirrored
        fix = build_board.JLC_CPL_FIX
        fix["TEST"] = ("SOT-23-5", 0, 0.0, 1.0)
        try:
            self.assertEqual(self.row("top", 0, "TEST")[2], "-6.000000mm")
            self.assertEqual(self.row("bottom", 0, "TEST")[2], "-4.000000mm")
        finally:
            del fix["TEST"]

    def test_wrong_footprint(self):
        with self.assertRaises(SystemExit):
            self.row("top", 0, "C51118", package="SOT-23")


# Pin 1 of JLC's own footprint (its EasyEDA land, mm from its origin, Y down), for the parts whose rotation can't
# be told from the outline: JLC_CPL_FIX's turn must put it on pin 1 of our footprint.  (LCSC: (JLC's pin 1,
# our library footprint))
PIN1 = {
    # H5VU25UC: DFN2510-10L, 10 pads in two rows, symmetric but for the pin numbers (EasyEDA, 2026-10-20)
    "C20615800": ((-1.0, 0.433), REPO / "electronics" / "lib" / "bench.pretty" / "DFN2510-10L_2.5x1.0mm_P0.5mm.kicad_mod"),
}


class JlcPin1(unittest.TestCase):
    def test_pin1_lands_on_pin1(self):
        import math
        import re
        for lcsc, ((jx, jy), mod) in PIN1.items():
            _, drot, dx, dy = build_board.JLC_CPL_FIX[lcsc]
            m = re.search(r'\(pad "1" \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+)', mod.read_text(encoding="utf-8"))
            kx, ky = float(m.group(1)), float(m.group(2))
            a = math.radians(drot)              # JLC turns its footprint counter-clockwise as seen (Y down)
            x, y = jx * math.cos(a) + jy * math.sin(a) + dx, -jx * math.sin(a) + jy * math.cos(a) + dy
            self.assertLess(math.hypot(x - kx, y - ky), 0.05, f"{lcsc}: JLC's pin 1 at ({x:.3f}, {y:.3f}), "
                                                               f"ours at ({kx}, {ky})")


if __name__ == "__main__":
    unittest.main()
