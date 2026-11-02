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
from flowthru import _all, _get, parse  # noqa: E402

# The boards that carry the common title block, and their names (the user, 2026-11-02: one style on all four)
TITLED = {"power-hub": "POWER HUB v0.5", "bay-node": "BAY NODE v0.5", "data-port-x4-v2": "DATA ×4 v2.0",
          "data-port-x6": "DATA ×6 v1.0", "camera-pod": "CAM POD v1.0"}


class Marks(unittest.TestCase):
    def test_port_mark_within_limits(self):
        m = silk.port_mark(6, 10.0, 20.0)
        self.assertEqual((m["text"], m["style"], m["d"]), ("6", "disc", silk.MARK_D))
        self.assertGreaterEqual(m["thickness"], silk.MARK_GAP - 1e-9)
        self.assertGreaterEqual(m["size"], 1.5)

    def test_port_mark_refuses_a_thin_or_small_character(self):
        with self.assertRaises(AssertionError):
            silk.port_mark(1, 0, 0, stroke=0.28)
        with self.assertRaises(AssertionError):
            silk.port_mark(1, 0, 0, size=1.2)
        with self.assertRaises(AssertionError):
            silk.port_mark(1, 0, 0, d=2.0)

    def test_lead_pin_names(self):
        names = silk.lead_pin_names(91.75, 38.5, ["NC", "SCL", "SDA", "GND", "D-", "D+", "GND", "VIN"])
        self.assertEqual([n["y"] for n in names][:2], [38.5, 36.5])
        self.assertTrue(all(n["size"] >= 1.0 and n["thickness"] >= silk.SILK_TEXT for n in names))

    def test_title_block(self):
        mark, name, date = silk.title_block("DATA ×6 v1.0", 60.0, 2.0)
        self.assertEqual((mark["style"], mark["w"], name["size"], date["size"], date["text"]),
                         ("poly", silk.LOGO_W, 1.5, 1.0, silk.TITLE_DATE))
        self.assertTrue(all(e["layer"] == "B.SilkS" for e in (mark, name, date)))
        xs = [x for p in mark["polys"] for r in p for x, _ in r]
        self.assertAlmostEqual(max(xs), 60.0, places=3)         # read from below: it runs towards −x
        self.assertAlmostEqual(min(xs), 60.0 - silk.LOGO_W, places=3)
        self.assertGreaterEqual(name["y"] - 1.82, 2.0 + mark["h"] + silk.TITLE_GAP - 1e-3)     # capitals' ink
        self.assertEqual((name["y"], date["after"], name["vjust"]), (date["y"], 1.5, "bottom"))   # one baseline


class Boards(unittest.TestCase):
    """Every titled board carries the same block: the logo LOGO_W wide on B.SilkS, its name and then the date on
    one line under it, from the logo's left edge as read from below; and no board keeps the old "hw-testing-rack"
    line."""

    def test_title_blocks(self):
        self.assertEqual(len(TITLED), 5)            # the five boards ordered from NextPCB
        for board, title in TITLED.items():
            with self.subTest(board=board):
                root = parse((ROOT / "electronics" / board / f"{board}.kicad_pcb").read_text(encoding="utf-8"))
                polys = [p for p in _all(root, "gr_poly") if _get(p, "layer")[1] == "B.SilkS"]
                pts = [(float(q[1]), float(q[2])) for p in polys for q in _all(_get(p, "pts"), "xy")]
                x0, y0 = min(x for x, _ in pts), min(y for _, y in pts)
                x1, y1 = max(x for x, _ in pts), max(y for _, y in pts)
                mark = silk.logo(0, 0)
                self.assertEqual(len(polys), len(mark["polys"]))
                self.assertAlmostEqual(x1 - x0, silk.LOGO_W, places=2)
                self.assertAlmostEqual(y1 - y0, mark["h"], places=2)
                texts = {t[1]: t for t in _all(root, "gr_text")}
                name, date = texts.get(title), texts.get(silk.TITLE_DATE)
                self.assertIsNotNone(name, title)
                self.assertIsNotNone(date, silk.TITLE_DATE)
                (nx, ny), (dx, dy) = ((float(v) for v in _get(t, "at")[1:3]) for t in (name, date))
                self.assertEqual({_get(t, "layer")[1] for t in (name, date)}, {"B.SilkS"})
                self.assertAlmostEqual(nx, x1 + silk.TITLE_BEARING, places=2)   # read from below, it runs to −x
                self.assertAlmostEqual(dy, ny, places=3)
                self.assertGreater(ny - 1.82, y1)
                self.assertLess(dx, nx - 10)
                self.assertFalse([t for t in texts if "hw-testing-rack" in t])


    def test_title_blocks_air(self):
        """silkair.py: 1 mm from other silk, 0.3 mm from pads, holes and courtyards, 4 mm from the connectors,
        on the shapes KiCad plots (pcbnew; build_board.py --check runs it in the Hardware CI)."""
        try:
            import silkair
        except ImportError:
            self.skipTest("pcbnew")
        for board in TITLED:
            with self.subTest(board=board):
                found = silkair.findings(ROOT / "electronics" / board / f"{board}.kicad_pcb")
                self.assertEqual(found, [], "\n".join(found))


class Logo(unittest.TestCase):
    """The logo's silk variant at LOGO_W: its gaps LOGO_GAP, its lines LOGO_INK, read from the outlines the boards
    take (bitbunk-logo.silk.json), and those the same as the SVG gives."""

    @classmethod
    def setUpClass(cls):
        try:
            from shapely.geometry import Polygon
            from shapely.ops import unary_union
        except ImportError:
            raise unittest.SkipTest("shapely")
        m = silk.logo(0.0, 0.0, layer="F.SilkS")
        cls.silk = unary_union([Polygon(p[0], p[1:]) for p in m["polys"]])

    def test_same_as_the_svg(self):
        from shapely import affinity
        fresh = silk.derive_logo()
        x0, y0, x1, _ = fresh.bounds
        k = silk.LOGO_W / (x1 - x0)
        fresh = affinity.scale(affinity.translate(fresh, -x0, -y0), k, k, origin=(0, 0))
        self.assertLess(fresh.hausdorff_distance(self.silk), 1e-3)          # mm: the rounding alone

    def test_gaps(self):
        """Between its parts LOGO_GAP at least; and the ink may spread up to half of it a side before any gap or
        counter closes (the background, eroded by that much, keeps its pieces and its holes)."""
        parts = list(self.silk.geoms)
        least = min(a.distance(b) for i, a in enumerate(parts) for b in parts[i + 1:])
        self.assertGreaterEqual(least, silk.LOGO_GAP - 1e-4)       # 25.5 mm: 0.24999
        from shapely.geometry import box
        bg = box(*self.silk.buffer(1).bounds).difference(self.silk)
        er = bg.buffer(-(silk.LOGO_GAP / 2 - 1e-3))

        def shape(g):
            gs = list(getattr(g, "geoms", [g]))
            return len(gs), sum(len(p.interiors) for p in gs)
        self.assertEqual(shape(er), shape(bg))

    def test_ink(self):
        """No line under LOGO_INK: eroded by half of it, every part stays one piece."""
        er = self.silk.buffer(-(silk.LOGO_INK / 2))
        self.assertEqual(len(getattr(er, "geoms", [er])), len(self.silk.geoms))
