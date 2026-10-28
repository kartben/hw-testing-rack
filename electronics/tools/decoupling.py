"""Decoupling capacitors beside their pins (the layout review, 2026-10-28: "les capas de découplage sont parfois
loin de la pin"), from the .kicad_pcb text alone (no pcbnew: it runs in CI).  A board's design.py says which IC
power pin each decoupling capacitor serves, in b.pcb["decoupling"]: {"C14": "U3.3V3", ...} (the pin by name or
number; resolve() turns it into the pads).  A capacitor whose place is someone else's call (a datasheet's reference
layout) gets its own limit, with the reason beside it in design.py: {"C2": ("U1.VIN", 3.0)}.  For each:

  * pin: from the capacitor's pad on the pin's net to the pin's pad, edge to edge, REACH mm at most (or its own);
  * via: from its other pad (its return, GND) to the nearest via or through-hole pad of that net, edge to edge,
    VIA mm at most: the return goes straight down to the plane, not through a pour first;
  * order (a capacitor of SMALL or less, the pin → cap → via rule of the layout review): the pin reaches the
    capacitor's pad by copper on their one layer, no via on the way, and reaches no via of its rail but through that
    pad (a track straight across the pad counts as two, one each side).  Along tracks the order is strict.  Across a pour of the rail on that layer (an island the pin, the
    capacitor and the rail's vias share, as a buck's input), a via only comes "before" the capacitor if it is nearer
    the pin than the capacitor is.  A through-hole pad counts as a via, but for the pin itself (a connector's).
    Bulk capacitors, over SMALL, are held to the distances only.

    python decoupling.py BOARD [...]      → each board's table, exit status 1 if a capacitor is too far

The table also names the capacitors left undeclared (bulk, bootstrap, RC): what they serve is no pin's.

tools/tests/test_decoupling.py holds every board that declares its capacitors to both, but the ones
electronics/decoupling.json still lists.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from antennas import Copper, _meets_track
from flowthru import _in_pad, _rot

REACH = 2.0                                     # mm, capacitor pad to pin pad
VIA = 1.0                                       # mm, return pad to its via
SMALL = 100e-9                                  # F: a capacitor this small or smaller sits between its pin and via


def farads(value: str) -> float | None:
    """"100n", "4.7u", "22u/50V", "1µF" → farads (None: not a capacitance)."""
    import re
    m = re.match(r"\s*([0-9]*\.?[0-9]+)\s*([pnuµm]?)", value or "")
    if not m:
        return None
    return float(m.group(1)) * {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0}[m.group(2)]


def corners(p) -> list[tuple[float, float]]:
    """A pad's rectangle on the board (ovals and circles as their box: never nearer than they are)."""
    hw, hh = p["w"] / 2, p["h"] / 2
    return [(p["x"] + dx, p["y"] + dy) for dx, dy in
            (_rot(sx * hw, sy * hh, p["rot"]) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)))]


def _seg_point(a, b, x, y) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    L = vx * vx + vy * vy
    u = 0 if L == 0 else max(0.0, min(1.0, ((x - a[0]) * vx + (y - a[1]) * vy) / L))
    return math.hypot(x - a[0] - u * vx, y - a[1] - u * vy)


def _inside(poly, x, y) -> bool:
    """In a convex polygon (either winding)."""
    s = [(b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]) for a, b in zip(poly, poly[1:] + poly[:1])]
    return all(v >= 0 for v in s) or all(v <= 0 for v in s)


def pad_gap(p, q) -> float:
    """Edge to edge between two pads, 0 where they touch."""
    a, b = corners(p), corners(q)
    if any(_inside(b, *c) for c in a) or any(_inside(a, *c) for c in b):
        return 0.0
    return min(min(_seg_point(e0, e1, *c) for c in a for e0, e1 in zip(b, b[1:] + b[:1])),
               min(_seg_point(e0, e1, *c) for c in b for e0, e1 in zip(a, a[1:] + a[:1])))


def via_gap(p, x, y, r) -> float:
    """Edge to edge between a pad and a via (centre x, y, radius r), 0 where the via is on the pad."""
    dx, dy = _rot(x - p["x"], y - p["y"], -p["rot"])
    return max(math.hypot(max(abs(dx) - p["w"] / 2, 0), max(abs(dy) - p["h"] / 2, 0)) - r, 0.0)


def _limit(v) -> tuple[str, float]:
    """A declaration's pin and its limit: "REF.PIN", or ("REF.PIN", mm)."""
    return (v, REACH) if isinstance(v, str) else (v[0], float(v[1]))


def resolve(b, decl: dict) -> dict[str, tuple[str, str | None, float]]:
    """{cap: "REF.PIN" or ("REF.PIN", mm)} → {cap: ("REF.PIN", the pin's net in design.py, limit)}: check() then
    takes a pin named, not numbered, as the part's pads on that net (the board file keeps pad numbers only; a tab and
    its pin both)."""
    out = {}
    for cap, v in decl.items():
        pin, reach = _limit(v)
        ref, name = pin.split(".", 1)
        part = b.parts.get(ref)
        out[cap] = (pin, part.conns.get(name) if part is not None else None, reach)
    return out


def _pad_points(p):
    """A pad's corners and edge midpoints: where a pour's spokes or a track's end meet it."""
    cs = corners(p)
    return cs + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(cs, cs[1:] + cs[:1])]


def _split_at(t: dict, pad: dict) -> list[dict]:
    """A track that runs across a pad, as its pieces outside it, each ending just inside its edge: a walk along the
    track then meets the pad between them, as the current does (a pin's track straight through its capacitor)."""
    x0, y0, x1, y1, w = t["g"][:5]
    n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 0.01))
    at = lambda k: (x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n)
    inside = [_in_pad(pad, *at(k)) for k in range(n + 1)]
    if not any(inside):
        return [t]
    pieces, k = [], 0
    while k <= n:
        if inside[k]:
            k += 1
            continue
        j = k
        while j < n and not inside[j + 1]:
            j += 1
        a, b = at(max(k - 1, 0)), at(min(j + 1, n))
        pieces.append({**t, "g": (*a, *b, w)})
        k = j + 1
    return pieces


def order(c: Copper, pins: list, cp: dict) -> str | None:
    """The pin → cap → via rule on the capacitor's layer: None if kept, else what breaks it."""
    net = cp["net"]
    layer = "F.Cu" if "F.Cu" in cp["layers"] else "B.Cu" if "B.Cu" in cp["layers"] else None
    on = lambda p: "*" in p["layers"] or layer in p["layers"]
    if layer is None or not all(on(q) for q in pins):
        return f"not on {pins[0]['ref']}'s layer"
    # the rail's copper on that layer, as nodes: pads, tracks, vias, pour pieces
    nodes = [("pad", q) for q in c.pads if q["net"] == net and on(q)]
    nodes += [("trk", t) for t0 in c.tracks if t0["net"] == net and t0["layer"] == layer for t in _split_at(t0, cp)]
    nodes += [("via", v) for v in c.vias if v["net"] == net]
    nodes += [("fill", f) for f in c.fills.get((net, layer), ())]
    idx = {id(n[1]): i for i, n in enumerate(nodes)}
    from antennas import _inside as in_fill, _near_outline

    def touch(a, b, block=None) -> bool:
        """Two copper items of the rail meet; never at a point inside `block` (the capacitor's pad, which the walk
        must pass: two tracks joined on it meet through it)."""
        (ka, x), (kb, y) = a, b
        if ka > kb:
            (ka, x), (kb, y) = (kb, y), (ka, x)
        free = lambda q: block is None or not _in_pad(block, *q)
        ends = lambda t: (t["g"][:2], t["g"][2:4])
        if ka == "fill" and kb == "fill":
            return False
        if ka == "fill":                                    # fill with pad, trk, via
            pts = _pad_points(y) if kb == "pad" else ends(y) if kb == "trk" else [(y["x"], y["y"])]
            r = 0.1 if kb == "pad" else y["g"][4] / 2 if kb == "trk" else y["d"] / 2
            return any(in_fill(x, *q) or _near_outline(x, *q, r) for q in pts)
        if ka == "pad" and kb == "pad":
            return any(_in_pad(y, *q) for q in _pad_points(x)) or any(_in_pad(x, *q) for q in _pad_points(y))
        if ka == "pad" and kb == "trk":
            return any(_in_pad(x, *e, y["g"][4] / 2) for e in ends(y))
        if ka == "pad" and kb == "via":
            return via_gap(x, y["x"], y["y"], y["d"] / 2) == 0.0
        if ka == "trk" and kb == "trk":
            return (any(_meets_track(y, *e) and free(e) for e in ends(x))
                    or any(_meets_track(x, *e) and free(e) for e in ends(y)))
        if ka == "trk" and kb == "via":                     # a track's end in the via, or the via on the track
            v = (y["x"], y["y"])
            return (any(math.hypot(e[0] - v[0], e[1] - v[1]) <= y["d"] / 2 + 0.002 and free(e) for e in ends(x))
                    or (_meets_track(x, *v) and free(v)))
        return False                                        # via with via: not on one layer's copper

    def spread(start, stop, through_vias, fills=True):
        """The nodes reached from `start`, never past `stop` (nor through it); vias (and through-hole pads) only if
        allowed, pours only if `fills`."""
        block = nodes[next(iter(stop))][1] if stop else None
        seen, todo = set(start), list(start)
        while todo:
            i = todo.pop()
            for j, n in enumerate(nodes):
                if j in seen or j in stop:
                    continue
                if not through_vias and (n[0] == "via" or (n[0] == "pad" and "*" in n[1]["layers"] and j not in start)):
                    continue
                if not fills and n[0] == "fill":
                    continue
                if touch(nodes[i], n, block):
                    seen.add(j)
                    todo.append(j)
        return seen

    start = {idx[id(q)] for q in pins if id(q) in idx}
    cap = idx[id(cp)]
    if cap not in spread(start, set(), False):
        return f"no copper from {pins[0]['ref']} to it on {layer} but through a via"
    is_via = lambda n: n[0] == "via" or (n[0] == "pad" and "*" in n[1]["layers"])
    tracked = spread(start, {cap}, True, fills=False) - start
    for j in sorted(tracked):
        if is_via(nodes[j]):
            n = nodes[j][1]
            return f"{pins[0]['ref']} reaches a via at ({n['x']:.2f}, {n['y']:.2f}) before it"
    gap = min(pad_gap(cp, q) for q in pins)
    for j in sorted(spread(start, {cap}, True) - start - tracked):
        if is_via(nodes[j]):
            n = nodes[j][1]
            d = min(via_gap(q, n["x"], n["y"], n["d"] / 2) if nodes[j][0] == "via" else pad_gap(q, n) for q in pins)
            if d < gap:
                return (f"{pins[0]['ref']} reaches a via at ({n['x']:.2f}, {n['y']:.2f}) across the pour, {d:.2f} mm "
                        f"off: nearer than it")
    return None


def check(path, decl: dict) -> list[dict]:
    """One row per declared capacitor: {cap, pin, net, ret, side, pin_mm, via_mm, reach, problems}.  `decl`: {cap:
    "REF.NUM" or ("REF.NUM", mm)}, or resolve()'s {cap: ("REF.PIN", net, mm)}."""
    c = Copper(path)
    by_ref = {}
    for p in c.pads:
        by_ref.setdefault(p["ref"], []).append(p)
    rows = []
    for cap, v in decl.items():
        (pin, net, reach) = v if isinstance(v, tuple) and len(v) == 3 else (_limit(v)[0], None, _limit(v)[1])
        row = {"cap": cap, "pin": pin, "net": "?", "ret": "?", "side": "?", "pin_mm": math.inf, "via_mm": math.inf,
               "reach": reach, "small": False, "order": None, "problems": []}
        rows.append(row)
        ref = pin.split(".", 1)[0]
        pins = by_ref.get(pin) or [q for n, qs in by_ref.items() if n.split(".", 1)[0] == ref for q in qs
                                   if net and (q["net"] == net or q["net"].endswith("/" + net))]
        mine = by_ref.get(f"{cap}.1", []) + by_ref.get(f"{cap}.2", [])
        if not pins or len(mine) != 2:
            row["problems"].append(f"no pad {pin}" if not pins else f"{cap} not a two-pad part")
            continue
        net = row["net"] = pins[0]["net"]
        on = [p for p in mine if p["net"] == net]
        if len(on) != 1:
            row["problems"].append(f"{cap} not on {pin}'s net {net}")
            continue
        cp, rp = on[0], next(p for p in mine if p is not on[0])
        row["ret"] = rp["net"]
        side = lambda p: "*" if "*" in p["layers"] else "B" if "B.Cu" in p["layers"] else "F"
        row["side"] = side(cp) + ("" if side(cp) == side(pins[0]) else f" ({pin} {side(pins[0])})")
        row["pin_mm"] = min(pad_gap(cp, q) for q in pins)
        holes = [(v["x"], v["y"], v["d"] / 2) for v in c.vias if v["net"] == rp["net"]]
        holes += [(p["x"], p["y"], min(p["w"], p["h"]) / 2) for p in c.pads if p["net"] == rp["net"] and "*" in p["layers"]]
        row["via_mm"] = min((via_gap(rp, *h) for h in holes), default=math.inf)
        if len({q["net"] for q in pins}) > 1:
            row["problems"].append(f"{pin}'s pads on more than one net")
        if row["pin_mm"] > reach:
            row["problems"].append(f"{row['pin_mm']:.2f} mm from {pin} (max {reach})")
        if row["via_mm"] > VIA:
            row["problems"].append(f"its {rp['net']} {row['via_mm']:.2f} mm from a via (max {VIA})")
        f = farads(c.values.get(cap, ""))
        row["small"] = f is not None and f <= SMALL * 1.001
        if row["small"]:
            row["order"] = order(c, pins, cp)
            if row["order"]:
                row["problems"].append(f"order: {row['order']}")
    return rows


def undeclared(path, decl: dict) -> list[str]:
    """The board's two-pad capacitors (C…) that `decl` leaves out, with their nets."""
    nets = {}
    for p in Copper(path).pads:
        ref, _, num = p["ref"].partition(".")
        if ref[:1] == "C" and ref[1:].isdigit() and num in ("1", "2"):
            nets.setdefault(ref, {})[num] = p["net"].split("/")[-1]
    return [f"{r} {n.get('1', '?')}/{n.get('2', '?')}" for r, n in sorted(nets.items(), key=lambda kv: int(kv[0][1:]))
            if r not in decl]


def table(name, rows, left=()) -> str:
    out = [f"{name}: {len(rows)} capacitors, {sum(bool(r['problems']) for r in rows)} too far",
           f"  {'cap':6} {'pin':10} {'net':14} {'side':10} {'to pin':>7} {'to via':>7}"]
    for r in rows:
        out.append(f"  {r['cap']:6} {r['pin']:10} {r['net'].split('/')[-1][-14:]:14} {r['side']:10} "
                   f"{r['pin_mm']:7.2f} {r['via_mm']:7.2f}  {'; '.join(r['problems']) or 'ok'}"
                   + (f" (its own limit: {r['reach']} mm)" if r["reach"] != REACH else ""))
    if left:
        out.append("  not declared: " + ", ".join(left))
    return "\n".join(out)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_board
    bad = False
    for name in sys.argv[1:]:
        b = build_board.load_design(name).board()
        decl = b.pcb.get("decoupling", {})
        path = build_board.REPO / "electronics" / name / f"{name}.kicad_pcb"
        rows = check(path, resolve(b, decl))
        print(table(name, rows, undeclared(path, decl)))
        bad |= any(r["problems"] for r in rows)
    sys.exit(1 if bad else 0)
