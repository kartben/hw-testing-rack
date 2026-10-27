"""Tests for tools/webscene.py › front_status: what each bay's front display shows in the viewer.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))

import rackcfg  # noqa: E402

try:
    import webscene  # noqa: E402  (numpy, which the bayctl job doesn't install)
except ImportError:
    webscene = None


@unittest.skipIf(webscene is None, "numpy missing")
class FrontStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rack = rackcfg.load()
        pop = cls.rack.raw.get("population", {})
        cls.st = {b.id: webscene.front_status(cls.rack, b.id, pop.get(b.id, {})) for b in cls.rack.bays()}

    def test_as_display_c_reads_it(self):
        addrs = set()
        for bid, s in self.st.items():
            self.assertEqual(s["id"], bid)
            addrs.add(s["addr"])
            slots = self.rack.duts(bid)
            if self.rack.is_multi(bid):
                self.assertEqual(len(s["ports"]), 4)
                on = {sl.slot for sl in slots}
                self.assertEqual({k + 1 for k, p in enumerate(s["ports"]) if p["on"]}, on, bid)
                self.assertGreater(s["dut"]["ma"], sum(p["ma"] for p in s["ports"]))      # its hub on top
            else:
                self.assertIsNone(s["ports"], bid)                                          # "1  -" … "4  -"
            self.assertEqual(s["usbip"], 0 if s["path"] == "classic" else len(slots), bid)
        self.assertEqual(len(addrs), len(self.st))

    def test_docs_listing(self):
        # docs/ci.md's bayctl listing: the same addresses
        for bid, addr in (("A1", "192.168.1.61"), ("A2", "192.168.1.62"), ("B2", "192.168.1.78"), ("B3", "192.168.1.79")):
            if bid in self.st:
                self.assertEqual(self.st[bid]["addr"], addr)


if __name__ == "__main__":
    unittest.main()
