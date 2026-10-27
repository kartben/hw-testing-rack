"""Tests for tools/plate_layout.py: the honeycomb plate's grid and where its pegs go.

    python -m unittest discover -s tools/tests -v
"""

from __future__ import annotations

import math
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))

import plate_layout as PL  # noqa: E402
import rackcfg  # noqa: E402


class Grid(unittest.TestCase):
    def setUp(self):
        self.rack = rackcfg.load()
        self.holes = self.rack.plate_holes()

    def test_holes(self):
        w, d = self.rack.plate_size
        g = self.rack.plate_grid
        half_y = (g["hole"] + 2 * g["undercut"]) / math.sqrt(3)
        self.assertGreater(len(self.holes), 150)
        for _, _, x, y in self.holes:
            self.assertGreaterEqual(x - g["hole"] / 2 - g["undercut"], g["margin"] - 1e-6)
            self.assertLessEqual(x + g["hole"] / 2 + g["undercut"], w - g["margin"] + 1e-6)
            self.assertGreaterEqual(y - half_y, g["margin"] - 1e-6)
            for px, py in ((10, 10), (w - 10, d - 10)):                          # locating pins
                self.assertGreater(math.hypot(x - px, y - py), 2.1 + half_y)
            for bx, by in self.rack.plate_buttons():                             # RESET / BOOT pin holes
                self.assertGreater(math.hypot(x - bx, y - by), rackcfg.BUTTON_HOLE_R + half_y)
        pts = [(x, y) for _, _, x, y in self.holes]                              # a pitch apart, never closer
        closest = min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(pts) for b in pts[i + 1:])
        self.assertAlmostEqual(closest, g["pitch"], places=3)

    def test_generated(self):
        scad = (REPO / "mechanical" / "generated" / "config.scad").read_text(encoding="utf-8")
        found = re.search(r"HEX_HOLES = (\[.*?\]\]);", scad).group(1)
        self.assertEqual(found, rackcfg.scad_value([[x, y] for _, _, x, y in self.holes]),
                         "stale: run python tools/build.py config")

    def test_orient_point(self):
        for bid, b in rackcfg.load_boards().items():
            for side in (False, True):
                bb = {**b, "orient": "side" if side else "rear"}
                o = rackcfg.orient_board(bb)
                got = [PL.orient_point(bb, x, y, side) for x, y in b.get("holes", [])]
                for (gx, gy), (hx, hy) in zip(got, o["holes"]):
                    self.assertAlmostEqual(gx, hx, places=6, msg=bid)
                    self.assertAlmostEqual(gy, hy, places=6, msg=bid)

    def test_cam_travel(self):
        g = PL.Grid(self.rack)
        self.assertLess(g.dmin, 4.5)
        self.assertGreater(g.dmax - g.dmin, 2.8)          # more than the stops' coarsest step (1.84 mm)


class Layouts(unittest.TestCase):
    """Every populated bay of config/rack.yaml that is on the honeycomb plate."""

    @classmethod
    def setUpClass(cls):
        cls.rack = rackcfg.load()
        cls.boards = rackcfg.load_boards()
        cls.g = PL.Grid(cls.rack)
        cls.layouts = {b.id: PL.layout_bay(cls.rack, b.id, cls.boards) for b in cls.rack.bays()
                       if cls.rack.duts(b.id) and cls.rack.plate_kind(b.id) == "pegs"}

    def test_every_board_held(self):
        self.assertIn("B3", self.layouts)
        for bay, lay in self.layouts.items():
            for n in lay.notes:
                self.assertNotIn("no peg fits", n, msg=bay)
            for pb in lay.boards:
                own = [p for p in lay.pegs if p.board == pb.slot and p.kind != "bobbin"]
                self.assertGreaterEqual(len(own), 2, msg=pb.slot)
                self.assertTrue(any(p.kind in ("cam", "pin") for p in own), msg=f"{pb.slot}: nothing clamps it")

    def test_pegs_in_holes_and_apart(self):
        holes = {(r, c): (x, y) for r, c, x, y in self.rack.plate_holes()}
        for bay, lay in self.layouts.items():
            seen = set()
            for p in lay.pegs:
                self.assertEqual(holes[(p.row, p.col)], (p.x, p.y), msg=bay)
                self.assertNotIn((p.row, p.col), seen, msg=f"{bay}: two pegs in one hole")
                seen.add((p.row, p.col))
            for i, p in enumerate(lay.pegs):
                for q in lay.pegs[i + 1:]:
                    self.assertFalse(PL.shapes_clash(PL.peg_shapes(p, self.g), PL.peg_shapes(q, self.g)),
                                     msg=f"{bay}: {p.kind} r{p.row}h{p.col} and {q.kind} r{q.row}h{q.col}")

    def test_stops_touch_cams_reach(self):
        for bay, lay in self.layouts.items():
            at = {pb.slot: pb for pb in lay.boards}
            for p in lay.pegs:
                if p.kind not in ("stop", "cam"):
                    continue
                pb = at[p.board]
                ec = PL.edge_coord(pb.at, pb.o, p.edge)
                n = PL.NORMAL[p.edge]
                if p.kind == "stop":
                    c = p.post[0] if PL.AXIS[p.edge] == "x" else p.post[1]
                    gap = (c - ec) * (n[0] + n[1]) - self.g.neck
                    self.assertAlmostEqual(gap, 0.0, places=2, msg=f"{p.board} stop r{p.row}h{p.col}")
                    a = PL.along(p.post, p.edge)
                else:
                    c = p.x if PL.AXIS[p.edge] == "x" else p.y
                    dist = (c - ec) * (n[0] + n[1])
                    self.assertTrue(self.g.dmin - 1e-6 <= dist <= self.g.dmax + 1e-6, msg=f"{p.board} cam r{p.row}h{p.col}")
                    a = PL.along((p.x, p.y), p.edge)
                s0, s1 = PL.edge_span(pb.at, pb.o, p.edge)
                self.assertTrue(s0 <= a <= s1, msg=p.board)
                b = {**self.boards[pb.board], "orient": "side" if pb.o["usb_side"] else "rear"}
                for k0, k1 in PL.keepouts(b, pb.o)[p.edge]:                # its contact clear of keep-outs
                    self.assertFalse(k0 < a - s0 < k1, msg=f"{p.board}: {p.kind} in a keep-out of its {p.edge} edge")

    def test_boards_on_the_plate_apart(self):
        w, d = self.rack.plate_size
        wl, wr, wf = self.g.walls
        for bay, lay in self.layouts.items():
            rects = [PL.board_rect(pb.at, pb.o) for pb in lay.boards]
            for pb, (x0, y0, x1, y1) in zip(lay.boards, rects):
                # between the drawer's walls (over the plate's right gap at most: the display's lead is below)
                self.assertTrue(wl + PL.WALL_GAP - 1e-6 <= x0 and wf + PL.WALL_GAP - 1e-6 <= y0
                                and x1 <= wr - PL.WALL_GAP + 1e-6 and y1 <= d, msg=pb.slot)
                self.assertLessEqual(max(abs(pb.at[0] - pb.hint[0]), abs(pb.at[1] - pb.hint[1])), PL.WINDOW_ALONE + 1e-6)
                if self.rack.is_multi(bay):
                    self.assertLessEqual(math.hypot(pb.at[0] - pb.hint[0], pb.at[1] - pb.hint[1]), PL.WINDOW * 1.42)
            for i, a in enumerate(rects):
                for b in rects[i + 1:]:
                    self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3], msg=bay)

    def test_clear_of_the_front(self):
        """The display, its frame and the front's joints hang over the plate's front: a peg's flange only under them."""
        self.assertTrue(self.g.front)
        for bay, lay in self.layouts.items():
            for p in lay.pegs:
                for x, y, r, z0, z1 in PL.peg_shapes(p, self.g):
                    for rect in self.g.front:
                        self.assertFalse(z1 > PL.FLANGE_T and PL.circle_in_rect(x, y, r, rect),
                                         msg=f"{bay}: {p.kind} r{p.row}h{p.col} under the front's {rect}")
            for pb in lay.boards:
                x0, y0, x1, y1 = PL.board_rect(pb.at, pb.o)
                for a0, b0, a1, b1 in self.g.front:
                    self.assertFalse(x0 < a1 and a0 < x1 and y0 < b1 and b0 < y1, msg=f"{pb.slot} under the front")

    def test_parts_printed(self):
        parts = PL.peg_parts(self.boards)
        for lay in self.layouts.values():
            for p in lay.pegs:
                for name, _ in p.parts:
                    self.assertIn(name, parts)


if __name__ == "__main__":
    unittest.main()
