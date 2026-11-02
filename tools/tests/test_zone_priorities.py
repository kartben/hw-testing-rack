"""Zone priorities (electronics/tools/zoneprio.py): no board has two pours of different nets on a layer, with one
priority, closer than their clearance, which KiCad would rank by their UUIDs (the DATA ×4 v2's panel halves, the
DATA ×6's power plane, 2026-11-02).

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "electronics" / "tools"))

import zoneprio  # noqa: E402


class Boards(unittest.TestCase):
    def test_no_pours_ranked_by_chance(self):
        boards = sorted(p for p in (ROOT / "electronics").glob("*/*.kicad_pcb") if p.stem == p.parent.name)
        self.assertTrue(boards)
        for board in boards:
            with self.subTest(board=board.stem):
                found = zoneprio.findings(board)
                self.assertEqual(found, [], "\n".join(found))


def zone(net, layer, pts, priority=None, clearance=0.25, name=""):
    xy = " ".join(f"(xy {x} {y})" for x, y in pts)
    prio = f"(priority {priority})" if priority is not None else ""
    return (f'(zone (net "{net}") (layer "{layer}") (name "{name}") {prio} (connect_pads (clearance {clearance})) '
            f'(polygon (pts {xy})))')


def square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class Synthetic(unittest.TestCase):
    """Two plane areas 0.2 mm apart along x = 10, clearance 0.25"""

    def found(self, *zones):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.kicad_pcb"
            p.write_text(f'(kicad_pcb {" ".join(zones)})', encoding="utf-8")
            return zoneprio.findings(p)

    def test_equal_priorities_too_close(self):
        f = self.found(zone("+3V3", "In2.Cu", square(0, 0, 10, 10), name="a"),
                       zone("+5V", "In2.Cu", square(10.2, 0, 20, 10), name="b"))
        self.assertEqual(len(f), 1)
        self.assertIn("0.200 mm apart", f[0])

    def test_distinct_priorities(self):
        self.assertEqual(self.found(zone("+3V3", "In2.Cu", square(0, 0, 10, 10), priority=1),
                                    zone("+5V", "In2.Cu", square(10.2, 0, 20, 10))), [])

    def test_far_enough_other_layer_same_net(self):
        self.assertEqual(self.found(zone("+3V3", "In2.Cu", square(0, 0, 10, 10)),
                                    zone("+5V", "In2.Cu", square(10.3, 0, 20, 10))), [])
        self.assertEqual(self.found(zone("+3V3", "In2.Cu", square(0, 0, 10, 10)),
                                    zone("+5V", "In1.Cu", square(5, 0, 20, 10))), [])
        self.assertEqual(self.found(zone("GND", "F.Cu", square(0, 0, 10, 10)),
                                    zone("GND", "F.Cu", square(5, 0, 20, 10))), [])

    def test_overlap_and_inside(self):
        self.assertIn("0.000 mm apart", self.found(zone("GND", "F.Cu", square(0, 0, 20, 20)),
                                                   zone("+5V", "F.Cu", square(5, 5, 8, 8)))[0])


if __name__ == "__main__":
    unittest.main()
