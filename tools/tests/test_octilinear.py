"""Tests for the straight and 45° track geometry (electronics/tools/octilinear.py) that pcbgen.tidy_tracks
straightens Freerouting's staircases with, and route_metrics counts bends with.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "electronics" / "tools"))

import octilinear  # noqa: E402


def octilinear_segments(path) -> bool:
    return all(dx == 0 or dy == 0 or abs(dx) == abs(dy)
               for dx, dy in ((q[0] - p[0], q[1] - p[1]) for p, q in zip(path, path[1:])))


class Paths(unittest.TestCase):
    def test_aligned(self):
        for b in ((5000, 0), (0, -5000), (3000, 3000), (-3000, 3000)):
            self.assertEqual(octilinear.paths((0, 0), b), [[(0, 0), b]])

    def test_shortest_fewest_bends_first(self):
        for a, b in (((0, 0), (10000, 3000)), ((0, 0), (-2000, 7000)), ((500, -400), (-9100, -3300))):
            ps = octilinear.paths(a, b)
            dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
            shortest = max(dx, dy) - min(dx, dy) + min(dx, dy) * math.sqrt(2)
            self.assertEqual([len(p) - 1 for p in ps[:2]], [2, 2])                   # one bend first
            self.assertTrue(all(len(p) - 1 == 3 for p in ps[2:]))                 # then the doglegs
            for p in ps:
                self.assertEqual((p[0], p[-1]), (a, b))
                self.assertTrue(octilinear_segments(p), p)
                self.assertAlmostEqual(octilinear.length(p), shortest, delta=2)

    def test_staircase_is_no_shorter(self):
        # a Freerouting staircase: 45°, straight, 45°, straight, 45°: as long as the one-bend path
        stair = [(0, 0), (1000, 1000), (3000, 1000), (4000, 2000), (6000, 2000), (7000, 3000)]
        self.assertTrue(octilinear_segments(stair))
        self.assertAlmostEqual(octilinear.length(stair), octilinear.length(octilinear.paths((0, 0), (7000, 3000))[0]))


class Bent(unittest.TestCase):
    def test_bent(self):
        self.assertFalse(octilinear.bent((-1000, 0), (2000, 0)))              # straight through
        self.assertTrue(octilinear.bent((-1000, 0), (1000, 1000)))            # 45°
        self.assertTrue(octilinear.bent((-1000, 0), (0, 1000)))               # 90°
        self.assertFalse(octilinear.bent((0, 0), (1000, 0)))                  # a zero-length segment


if __name__ == "__main__":
    unittest.main()
