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


if __name__ == "__main__":
    unittest.main()
