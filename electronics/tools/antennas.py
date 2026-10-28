"""Dangling copper ("antennas"), from the .kicad_pcb text alone (no pcbnew: it runs in CI).  The layout review,
2026-10-28: "les antennes PCB sont légion".  Four kinds, each a finding:

  * dead end: a track end that meets no other copper of its net on its layer: no other track (end or body), no
    via, no pad, no pour's fill;
  * lone via: a via that meets its net's copper on one layer or none (KiCad's "via dangling");
  * double: two collinear tracks of one net on one layer that overlap (one inside the other, or a shared run);
  * sliver: a track SLIVER mm long or shorter.

    python antennas.py BOARD.kicad_pcb [...]      → one line per finding, exit status 1 if any

pcbgen.clean_antennas removes them from a routed board; tools/tests/test_antennas.py holds the boards listed in
electronics/antennas.json to none.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from flowthru import _all, _get, _in_pad, _on_seg, parse, _rot

SLIVER = 0.1                                    # mm
EPS = 0.002                                     # mm: endpoints that coincide


def _inside(pts, x, y) -> bool:
    """Even-odd ray cast (KiCad stores a fill fractured: one outline per piece, holes slit open)."""
    hit = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _near_outline(pts, x, y, r) -> bool:
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        vx, vy = x2 - x1, y2 - y1
        L = vx * vx + vy * vy
        u = 0 if L == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / L))
        if math.hypot(x - x1 - u * vx, y - y1 - u * vy) <= r:
            return True
    return False


class Copper:
    """A board's copper by net: tracks, vias, pads (with their layers) and the pours' fills (per layer)."""

    def __init__(self, path):
        root = parse(Path(path).read_text(encoding="utf-8"))
        self.tracks, self.vias, self.pads, self.fills, self.values = [], [], [], {}, {}
        for fp in _all(root, "footprint"):
            at = _get(fp, "at")
            fx, fy, fr = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
            ref = next((p[2] for p in _all(fp, "property") if p[1] == "Reference"), "?")
            self.values[ref] = next((p[2] for p in _all(fp, "property") if p[1] == "Value"), "")
            for pad in _all(fp, "pad"):
                net = _get(pad, "net")
                pat, size = _get(pad, "at"), _get(pad, "size")
                px, py = _rot(float(pat[1]), float(pat[2]), fr)
                layers = set(_get(pad, "layers")[1:])
                if "*.Cu" in layers or pad[2] in ("thru_hole", "np_thru_hole"):
                    layers = {"*"}
                if net:
                    self.pads.append({"ref": f"{ref}.{pad[1]}", "net": net[-1], "x": fx + px, "y": fy + py,
                                      "rot": float(pat[3]) if len(pat) > 3 else 0.0, "w": float(size[1]),
                                      "h": float(size[2]), "shape": pad[3], "layers": layers})
        for s in _all(root, "segment"):
            st, en = _get(s, "start"), _get(s, "end")
            self.tracks.append({"net": _get(s, "net")[-1], "layer": _get(s, "layer")[1],
                                "g": (float(st[1]), float(st[2]), float(en[1]), float(en[2]),
                                      float(_get(s, "width")[1])),
                                "locked": _get(s, "locked") is not None and _get(s, "locked")[1:] != ["no"]})
        for v in _all(root, "via"):
            at = _get(v, "at")
            self.vias.append({"net": _get(v, "net")[-1], "x": float(at[1]), "y": float(at[2]),
                              "d": float(_get(v, "size")[1]), "layers": set(_get(v, "layers")[1:])})
        for z in _all(root, "zone"):
            net = _get(z, "net")
            if not net or net[-1] == "":
                continue
            for f in _all(z, "filled_polygon"):
                pts = [(float(p[1]), float(p[2])) for p in _get(f, "pts")[1:] if p[0] == "xy"]
                self.fills.setdefault((net[-1], _get(f, "layer")[1]), []).append(pts)

    def filled(self, net, layer, x, y, r=0.0) -> bool:
        """The point in the net's fill on that layer, or the fill within r of it (a via's thermal spokes)."""
        return any(_inside(p, x, y) or (r and _near_outline(p, x, y, r)) for p in self.fills.get((net, layer), ()))

    def pad_at(self, net, layer, x, y, r=0.0) -> bool:
        """A pad of the net on that layer at the point, or within r of it (a via overlapping its edge)."""
        return any(p["net"] == net and ("*" in p["layers"] or layer in p["layers"]) and _in_pad(p, x, y, r + EPS)
                   for p in self.pads)


def _via_layers(v):
    """A through via spans every copper layer; a blind one its two (KiCad lists the pair)."""
    return {"*"} if not v["layers"] or {"F.Cu", "B.Cu"} <= v["layers"] else v["layers"]


def _meets_track(t, x, y) -> bool:
    """A point on the track's body (its centre line, within half its width)."""
    x1, y1, x2, y2, w = t["g"]
    vx, vy = x2 - x1, y2 - y1
    L = vx * vx + vy * vy
    u = 0 if L == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / L))
    return math.hypot(x - x1 - u * vx, y - y1 - u * vy) <= w / 2 + EPS


def findings(path) -> list[str]:
    c = Copper(path)
    out = []
    by = {}
    for i, t in enumerate(c.tracks):
        by.setdefault((t["net"], t["layer"]), []).append(i)
    vias_by = {}
    for v in c.vias:
        vias_by.setdefault(v["net"], []).append(v)
    for i, t in enumerate(c.tracks):
        x1, y1, x2, y2, w = t["g"]
        net, layer = t["net"], t["layer"]
        L = math.hypot(x2 - x1, y2 - y1)
        where = f"{net} on {layer} ({x1:.3f}, {y1:.3f})–({x2:.3f}, {y2:.3f})"
        if L <= SLIVER + EPS:
            out.append(f"sliver: {L * 1000:.0f} µm track, {where}")
        for x, y in ((x1, y1), (x2, y2)):
            if any(j != i and _meets_track(c.tracks[j], x, y) for j in by[(net, layer)]):
                continue
            if any(math.hypot(x - v["x"], y - v["y"]) <= v["d"] / 2 + EPS
                   for v in vias_by.get(net, ()) if "*" in _via_layers(v) or layer in v["layers"]):
                continue
            if c.pad_at(net, layer, x, y) or c.filled(net, layer, x, y):
                continue
            out.append(f"dead end: {net} on {layer} at ({x:.3f}, {y:.3f})")
    # doubles: collinear, one net, one layer, their runs overlapping by more than EPS
    for (net, layer), idx in by.items():
        for a in range(len(idx)):
            ta = c.tracks[idx[a]]["g"]
            for b in range(a + 1, len(idx)):
                tb = c.tracks[idx[b]]["g"]
                if not (_on_line(ta, tb[0], tb[1]) and _on_line(ta, tb[2], tb[3])):
                    continue
                if _overlap(ta, tb) > EPS:
                    out.append(f"double: {net} on {layer} ({ta[0]:.3f}, {ta[1]:.3f})–({ta[2]:.3f}, {ta[3]:.3f}) "
                               f"and ({tb[0]:.3f}, {tb[1]:.3f})–({tb[2]:.3f}, {tb[3]:.3f})")
    # lone vias: copper of the net met on fewer than two layers
    layers_of = sorted({t["layer"] for t in c.tracks} | {l for (_, l) in c.fills} | {"F.Cu", "B.Cu"})
    for v in c.vias:
        met = set()
        for layer in layers_of:
            if layer not in _via_layers(v) and "*" not in _via_layers(v):
                continue
            r = v["d"] / 2 + EPS
            if (any(c.tracks[j]["layer"] == layer and _near_track(c.tracks[j], v["x"], v["y"], r)
                    for j in by.get((v["net"], layer), ()))
                    or c.pad_at(v["net"], layer, v["x"], v["y"], r) or c.filled(v["net"], layer, v["x"], v["y"], r)):
                met.add(layer)
        if len(met) < 2:
            out.append(f"lone via: {v['net']} at ({v['x']:.3f}, {v['y']:.3f}), meets {sorted(met) or 'nothing'}")
    return out


def _on_line(t, x, y) -> bool:
    x1, y1, x2, y2, _ = t
    vx, vy = x2 - x1, y2 - y1
    L = math.hypot(vx, vy)
    if L < EPS:
        return math.hypot(x - x1, y - y1) <= EPS
    return abs((x - x1) * vy - (y - y1) * vx) / L <= EPS


def _overlap(a, b) -> float:
    """The length two collinear tracks share."""
    x1, y1, x2, y2, _ = a
    vx, vy = x2 - x1, y2 - y1
    L = math.hypot(vx, vy)
    if L < EPS:
        return 0.0
    ux, uy = vx / L, vy / L
    p = sorted(((b[0] - x1) * ux + (b[1] - y1) * uy, (b[2] - x1) * ux + (b[3] - y1) * uy))
    return min(L, p[1]) - max(0.0, p[0])


def _near_track(t, x, y, r) -> bool:
    """A track whose body reaches within r of the point (an end on a via, or a track across it)."""
    x1, y1, x2, y2, w = t["g"]
    vx, vy = x2 - x1, y2 - y1
    L = vx * vx + vy * vy
    u = 0 if L == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / L))
    return math.hypot(x - x1 - u * vx, y - y1 - u * vy) <= r + w / 2


if __name__ == "__main__":
    found = []
    for p in sys.argv[1:]:
        for f in findings(p):
            print(f"{Path(p).stem}: {f}")
            found.append(f)
    sys.exit(1 if found else 0)
