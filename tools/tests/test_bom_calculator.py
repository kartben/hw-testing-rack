"""Tests for tools/bom.py's JLC order model: order_cost(), panel_order() and the BOM page's calculator.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))

import bom  # noqa: E402
import rackcfg  # noqa: E402


class Orders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.orders = bom.electronics(rackcfg.load())

    def test_panel_reproduces_the_quote(self):
        # the 1 × 2 base + logic panel as priced in docs/jlc-parts-audit.md (rounding: the quoted SMT lines), its
        # bare PCBs at 6 layers since the HS review (2026-10-22: $8.40 more for 5 panels, $8.80 for 10)
        for n, usd in ((2, 235.28), (5, 366.13), (10, 564.57)):
            self.assertAlmostEqual(bom.panel_order(n, self.orders)["total"], usd, delta=0.02)

    def test_volume_is_order_cost(self):
        vol = bom.volume(self.orders)
        for name, unit in vol["unit"].items():
            for n, usd in unit.items():
                self.assertAlmostEqual(usd, round(bom.order_cost(name, n, self.orders)["total"] / n, 2), places=2)

    def test_quote_is_order_cost(self):
        # at the quoted quantity an estimate built from the fab files is the quote itself
        for name in ("data-port-x4-v2", "data-port-x4-v2-base", "data-port-x4-v2-panel"):
            q = bom.JLC_QUOTE[name]
            self.assertAlmostEqual(bom.order_cost(name, q["assembled"], self.orders)["total"], q["total"], places=2)

    def test_at_least_two(self):
        for name in self.orders:
            one, two = bom.order_cost(name, 1, self.orders), bom.order_cost(name, 2, self.orders)
            self.assertEqual(one["assembled"], 2)
            self.assertEqual(one["total"], two["total"])
        self.assertEqual(bom.panel_order(1, self.orders)["total"], bom.panel_order(2, self.orders)["total"])

    def test_minimum_purchase(self):
        line = "L1 minimum purchase (32)"
        self.assertAlmostEqual(bom.order_cost("data-port-x4-v2", 2, self.orders)["once_lines"][line], 9.54, places=2)
        self.assertEqual(bom.order_cost("data-port-x4-v2", 32, self.orders)["once_lines"][line], 0)
        self.assertEqual(bom.panel_order(40, self.orders)["once_lines"][line], 0)

    def test_panel_is_the_racks_order(self):
        # one order panel carries the rack's logic and base; their parts lines stay per board
        self.assertIn("data-port-x4-v2-panel", self.orders)
        self.assertNotIn("data-port-x4-v2", self.orders)
        self.assertNotIn("data-port-x4-v2-base", self.orders)
        o = self.orders["data-port-x4-v2-panel"]
        self.assertEqual((o["types"], o["extended"], o["preferred"]), (40, 17, 2))   # C25725, C20615800 preferred

    def test_economic_fees_follow_the_tiers(self):
        # Economic PCBA charges the extended types only: basic and preferred-extended ones load free
        for name, o in self.orders.items():
            q = bom.JLC_QUOTE[name]
            if q["service"] == "Economic" and "extended parts" in q["pcba"]:
                self.assertAlmostEqual(q["pcba"]["extended parts"],
                                       o["extended"] * bom.JLC_FEES["Economic"]["per type"], places=2, msg=name)

    def test_calculator(self):
        c = bom.calculator(self.orders)
        self.assertEqual(c["n"][:3], [1, 2, 3])
        self.assertEqual(c["n"][-2:], [150, 200])
        for name, o in c["orders"].items():
            self.assertEqual(len(o["total"]), len(c["n"]), name)
            # a price break can make n + 1 boards cheaper than n (JLC buys every part at the break reached)
            self.assertTrue(all(usd > 0 for usd in o["total"]), name)
            self.assertLess(o["total"][0], o["total"][-1], name)
        self.assertIn("data-port-x4-v2-panel", c["orders"])
        self.assertEqual(sorted(c["design"]["data-port-x4-v2"]),
                         ["data-port-x4-v2", "data-port-x4-v2-base", "data-port-x4-v2-panel"])


if __name__ == "__main__":
    unittest.main()
