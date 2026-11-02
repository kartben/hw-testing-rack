"""Copper pours that KiCad would rank by chance, from the .kicad_pcb text alone (no pcbnew: it runs in CI).

Two pours of different nets on a common copper layer, with the same priority, whose outlines come closer than
their clearance (the larger of the zones' own and their nets' netclasses', from the .kicad_pro beside the board):
one of them must pull back, and with equal priorities KiCad picks it by the zones' UUIDs.  Those are new at each
rebuild from design.py and in each of KiKit's panel copies, so the fill can flip between builds while DRC stays
clean (the DATA ×4 v2's panel halves, 2026-11-02; the DATA ×6's power plane, four fills in four fresh-UUID
refills).  Give one of each pair a priority.

    python zoneprio.py BOARD.kicad_pcb [...]      → one line per pair, exit status 1 if any

build_board.py --check prints them; tools/tests/test_zone_priorities.py holds every board to none.
"""
from __future__ import annotations

import json
import math
import sys
from fnmatch import fnmatchcase
from pathlib import Path

from flowthru import _all, _get, parse


def class_clearances(path):
    """net name → its netclass's clearance (mm), from the project beside the board (Default when none matches)."""
    pro = Path(path).with_suffix(".kicad_pro")
    if not pro.exists():
        return lambda net: 0.0
    ns = json.loads(pro.read_text(encoding="utf-8"))["net_settings"]
    clear = {c["name"]: c.get("clearance", 0.0) for c in ns["classes"]}
    assigned = ns.get("netclass_assignments") or {}
    patterns = ns.get("netclass_patterns") or []

    def of(net):
        names = assigned.get(net) or [p["netclass"] for p in patterns if fnmatchcase(net, p["pattern"])]
        names = [names] if isinstance(names, str) else names
        return max((clear.get(n, 0.0) for n in names), default=clear.get("Default", 0.0))
    return of


def pours(path) -> list[dict]:
    """The board's copper pours (rule areas left out): name, net, layers, priority, clearance, outline."""
    root = parse(Path(path).read_text(encoding="utf-8"))
    out = []
    for z in _all(root, "zone"):
        net = _get(z, "net")
        if _get(z, "keepout") or not net or not net[1]:
            continue
        layers = (_get(z, "layers") or _get(z, "layer"))[1:]
        prio = _get(z, "priority")
        pads = _get(z, "connect_pads")
        clear = _get(pads, "clearance") if pads else None
        name = _get(z, "name")
        for poly in _all(z, "polygon"):
            pts = [(float(p[1]), float(p[2])) for p in _all(_get(poly, "pts"), "xy")]
            if len(pts) >= 3:
                out.append({"name": name[1] if name else "", "net": net[1], "layers": set(layers),
                            "priority": int(prio[1]) if prio else 0, "clearance": float(clear[1]) if clear else 0.0,
                            "outline": pts})
    return out


def _inside(pts, x, y) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _pt_seg(p, a, b) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    L = vx * vx + vy * vy
    u = 0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L))
    return math.hypot(p[0] - a[0] - u * vx, p[1] - a[1] - u * vy)


def _cross(a, b, c, d) -> bool:
    def s(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return s(a, b, c) * s(a, b, d) < 0 and s(c, d, a) * s(c, d, b) < 0


def gap(p, q, within: float) -> float:
    """The distance between two polygons' areas (0 when they touch or overlap); `within` only prunes: an
    answer at or past it may be any value ≥ it."""
    bp = (min(x for x, _ in p), min(y for _, y in p), max(x for x, _ in p), max(y for _, y in p))
    bq = (min(x for x, _ in q), min(y for _, y in q), max(x for x, _ in q), max(y for _, y in q))
    if bp[0] > bq[2] + within or bq[0] > bp[2] + within or bp[1] > bq[3] + within or bq[1] > bp[3] + within:
        return within
    if _inside(q, *p[0]) or _inside(p, *q[0]):
        return 0.0
    sp, sq = list(zip(p, p[1:] + p[:1])), list(zip(q, q[1:] + q[:1]))
    near = [s for s in sq if min(s[0][0], s[1][0]) <= bp[2] + within and max(s[0][0], s[1][0]) >= bp[0] - within
            and min(s[0][1], s[1][1]) <= bp[3] + within and max(s[0][1], s[1][1]) >= bp[1] - within]
    best = within
    for a, b in sp:
        lo = (min(a[0], b[0]) - within, min(a[1], b[1]) - within, max(a[0], b[0]) + within, max(a[1], b[1]) + within)
        for c, d in near:
            if max(c[0], d[0]) < lo[0] or min(c[0], d[0]) > lo[2] or max(c[1], d[1]) < lo[1] or min(c[1], d[1]) > lo[3]:
                continue
            if _cross(a, b, c, d):
                return 0.0
            best = min(best, _pt_seg(a, c, d), _pt_seg(b, c, d), _pt_seg(c, a, b), _pt_seg(d, a, b))
    return best


def findings(path) -> list[str]:
    zs = pours(path)
    of = class_clearances(path)
    found = []
    for i, a in enumerate(zs):
        for b in zs[i + 1:]:
            common = a["layers"] & b["layers"]
            if a["net"] == b["net"] or a["priority"] != b["priority"] or not common:
                continue
            need = max(a["clearance"], b["clearance"], of(a["net"]), of(b["net"]))
            d = gap(a["outline"], b["outline"], need)
            if d < need - 1e-6:
                found.append(f"equal priority {a['priority']}: {a['name'] or '-'} ({a['net']}) and "
                             f"{b['name'] or '-'} ({b['net']}) on {', '.join(sorted(common))}, {d:.3f} mm apart "
                             f"(clearance {need})")
    return found


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        for f in findings(p):
            print(f"{p}: {f}")
            bad += 1
    sys.exit(1 if bad else 0)
