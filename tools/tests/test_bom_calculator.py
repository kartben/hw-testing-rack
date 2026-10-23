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
        # the 1 × 2 base + logic panel: JLC's real quote of 2026-10-23 (green, Economic, $201.72) and the
        # RP2354B it left unplaced (JLC_SINCE_QUOTE), its parts scaled from the quote's at JLC's price breaks
        for n, usd in ((2, 207.86), (5, 325.10), (10, 517.51)):
            self.assertAlmostEqual(bom.panel_order(n, self.orders)["total"], usd, delta=0.02)

    def test_volume_is_order_cost(self):
        vol = bom.volume(self.orders)
        for name, unit in vol["unit"].items():
            for n, usd in unit.items():
                self.assertAlmostEqual(usd, round(bom.order_cost(name, n, self.orders)["total"] / n, 2), places=2)

    def test_quote_is_order_cost(self):
        # at the quoted quantity an order is its quote: as adjusted for the rack's order (the panel), else the
        # quote, what changed since on its PCBA lines (JLC_SINCE_QUOTE) and the rack's mask colour (the quotes
        # are green)
        for name in ("data-port-x4-v2", "data-port-x4-v2-base", "data-port-x4-v2-panel"):
            q = bom.JLC_QUOTE[name]
            since = sum(usd for _, line, usd in bom.JLC_SINCE_QUOTE.get(name, []) if line in q["pcba"])
            want = self.orders[name]["total"] if name in self.orders else                 q["total"] + since + sum(bom.mask_colour(name).values())
            self.assertAlmostEqual(bom.order_cost(name, q["assembled"], self.orders)["total"], want, places=2)

    def test_at_least_two(self):
        for name in self.orders:
            one, two = bom.order_cost(name, 1, self.orders), bom.order_cost(name, 2, self.orders)
            self.assertEqual(one["assembled"], 2)
            self.assertEqual(one["total"], two["total"])
        self.assertEqual(bom.panel_order(1, self.orders)["total"], bom.panel_order(2, self.orders)["total"])

    def test_minimum_purchase(self):
        # JLC's quotes of 2026-10-23 buy L1 by 5, and a real quote's components carry JLC's own purchase:
        # no minimum-buy line on the logic alone or the panel
        line = "L1 minimum purchase (5)"
        self.assertEqual(bom.JLC_MIN_BUY["data-port-x4-v2"][0][1], 5)
        self.assertNotIn(line, bom.order_cost("data-port-x4-v2", 2, self.orders)["once_lines"])
        self.assertNotIn(line, bom.panel_order(2, self.orders)["once_lines"])

    def test_panel_is_the_racks_order(self):
        # one order panel carries the rack's logic and base; their parts lines stay per board
        self.assertIn("data-port-x4-v2-panel", self.orders)
        self.assertNotIn("data-port-x4-v2", self.orders)
        self.assertNotIn("data-port-x4-v2-base", self.orders)
        o = self.orders["data-port-x4-v2-panel"]
        self.assertEqual((o["types"], o["extended"], o["preferred"]), (40, 17, 2))   # C25725, C20615800 preferred

    def test_economic_fees_follow_the_tiers(self):
        # Economic PCBA charges the extended types only: basic and preferred-extended ones load free (the
        # order's lines: a type the quote left unplaced comes back through JLC_SINCE_QUOTE)
        for name, o in self.orders.items():
            q = bom.JLC_QUOTE[name]
            if q["service"] == "Economic" and "extended parts" in o["pcba"]:
                self.assertAlmostEqual(o["pcba"]["extended parts"],
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
