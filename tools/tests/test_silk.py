"""Shared silkscreen marks (electronics/tools/silk.py): their sizes stay inside the fab's limits, and the boards
that number their ports do it with the same mark.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "electronics" / "tools"))

import silk  # noqa: E402


class Marks(unittest.TestCase):
    def test_port_mark_within_limits(self):
        m = silk.port_mark(6, 10.0, 20.0)
        self.assertEqual((m["text"], m["style"], m["d"]), ("6", "disc", silk.MARK_D))
        self.assertGreaterEqual(m["thickness"], 0.2)
        self.assertGreaterEqual(m["size"], 1.5)

    def test_port_mark_refuses_a_thin_or_small_character(self):
        with self.assertRaises(AssertionError):
            silk.port_mark(1, 0, 0, stroke=0.15)
        with self.assertRaises(AssertionError):
            silk.port_mark(1, 0, 0, size=1.2)
        with self.assertRaises(AssertionError):
            silk.port_mark(1, 0, 0, d=2.0)

    def test_lead_pin_names(self):
        names = silk.lead_pin_names(91.75, 38.5, ["NC", "SCL", "SDA", "GND", "D-", "D+", "GND", "VIN"])
        self.assertEqual([n["y"] for n in names][:2], [38.5, 36.5])
        self.assertTrue(all(n["size"] >= 1.0 and n["thickness"] >= silk.SILK_TEXT for n in names))

    def test_title_block(self):
        name, date = silk.title_block("DATA x6 v1.0", 17.0, 22.75, "2026-11")
        self.assertEqual((name["size"], date["size"], date["y"]), (1.5, 1.0, 24.75))
