"""The title block's air (silk.title_block()), measured on the shapes KiCad plots (pcbnew: text ink, outlines).

The block (the logo's outlines, the board's name and the date) keeps SILK_AIR mm from any other silk text or mark
on its face (test pads' names and rings, parts' outlines), HARD_AIR mm from pads, holes and parts' courtyards, and
CONN_AIR mm from the connectors (J*: their pads, holes and courtyards; the user, 2026-11-02: away from the
connectors).  A test pad's courtyard does not count: silk beside a pad does not hinder a probe.

    python3 silkair.py BOARD.kicad_pcb [...]      → one line per item too close, exit status 1 if any

build_board.py --check runs it; tools/tests/test_silk.py too where pcbnew imports.
"""
from __future__ import annotations

import re
import sys

import pcbnew

SILK_AIR, HARD_AIR, CONN_AIR = 1.0, 0.3, 4.0      # mm
TITLE_TEXT = re.compile(r" v\d+\.\d+$|^\d{4}-\d{2}$")     # the block's two lines: "NAME vX.Y", "YYYY-MM"
ERR = pcbnew.FromMM(0.005)


def _shape(item, layer) -> pcbnew.SHAPE_POLY_SET:
    ps = pcbnew.SHAPE_POLY_SET()
    if isinstance(item, pcbnew.PCB_TEXT) or isinstance(item, pcbnew.PCB_FIELD):
        item.TransformTextToPolySet(ps, 0, ERR, pcbnew.ERROR_INSIDE)
    else:
        item.TransformShapeToPolygon(ps, layer, 0, ERR, pcbnew.ERROR_INSIDE)
    return ps


def parts(board) -> tuple[pcbnew.SHAPE_POLY_SET, list[tuple[str, float, pcbnew.SHAPE_POLY_SET]]]:
    """The title block's shapes, and every other item it keeps clear of: (label, air in mm, shapes)."""
    block, others = pcbnew.SHAPE_POLY_SET(), []
    side = pcbnew.B_SilkS
    for d in board.GetDrawings():
        if d.GetLayer() not in (pcbnew.B_SilkS, pcbnew.F_SilkS):
            continue
        is_text = hasattr(d, "GetText")
        mine = (d.GetShape() == pcbnew.SHAPE_T_POLY) if not is_text else bool(TITLE_TEXT.search(d.GetText()))
        if mine and d.GetLayer() == pcbnew.B_SilkS:
            block.Append(_shape(d, d.GetLayer()))
        elif d.GetLayer() == side:
            others.append((f"silk '{d.GetText()}'" if is_text else "silk shape", SILK_AIR, _shape(d, side)))
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        conn = ref.startswith("J")
        for it in [fp.Reference(), fp.Value()] + list(fp.GraphicalItems()):
            if it.GetLayer() == side and (not hasattr(it, "IsVisible") or it.IsVisible()):
                others.append((f"{ref} silk", SILK_AIR, _shape(it, side)))
        for p in fp.Pads():
            if p.IsOnLayer(pcbnew.B_Cu) or p.IsOnLayer(pcbnew.B_Mask):
                others.append((f"{ref} pad", CONN_AIR if conn else HARD_AIR, _shape(p, pcbnew.B_Cu)))
            if p.GetDrillSize().x > 0:
                ps = pcbnew.SHAPE_POLY_SET()
                p.TransformHoleToPolygon(ps, 0, ERR, pcbnew.ERROR_INSIDE)
                others.append((f"{ref} hole", CONN_AIR if conn else HARD_AIR, ps))
        if fp.GetLayer() == pcbnew.B_Cu and not ref.startswith("TP"):
            crt = fp.GetCourtyard(pcbnew.B_CrtYd)
            if not crt.IsEmpty():
                others.append((f"{ref} courtyard", CONN_AIR if conn else HARD_AIR, pcbnew.SHAPE_POLY_SET(crt)))
    return block, others


def _gap(a: pcbnew.SHAPE_POLY_SET, b: pcbnew.SHAPE_POLY_SET) -> float:
    """The least distance between two shape sets, mm (0 when they touch)."""
    best = None
    for s, t in ((a, b), (b, a)):
        for i in range(s.OutlineCount()):
            chains = [s.Outline(i)] + [s.Hole(i, j) for j in range(s.HoleCount(i))]
            for ch in chains:
                for k in range(ch.PointCount()):
                    d = t.SquaredDistance(ch.CPoint(k))
                    d = d.m_distance if hasattr(d, "m_distance") else d
                    best = d if best is None else min(best, d)
    return pcbnew.ToMM(int(best ** 0.5)) if best is not None else float("inf")


def findings(path) -> list[str]:
    board = pcbnew.LoadBoard(str(path))
    block, others = parts(board)
    if block.OutlineCount() == 0:
        return []
    bb = block.BBox()
    found = []
    for label, air, shapes in others:
        if shapes.OutlineCount() == 0:
            continue
        r = shapes.BBox()
        reach = pcbnew.FromMM(air)
        if (r.GetRight() < bb.GetLeft() - reach or r.GetLeft() > bb.GetRight() + reach
                or r.GetBottom() < bb.GetTop() - reach or r.GetTop() > bb.GetBottom() + reach):
            continue
        g = _gap(block, shapes)
        if g < air - 1e-3:
            found.append(f"title block {g:.2f} mm from {label} (keep {air})")
    return found


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        for f in findings(p):
            print(f"{p}: {f}")
            bad += 1
    sys.exit(1 if bad else 0)
