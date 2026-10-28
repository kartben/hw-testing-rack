"""Decoupling capacitors beside their pins (Eve's layout review, 2026-10-28: "les capas de découplage sont parfois
loin de la pin"), from the .kicad_pcb text alone (no pcbnew: it runs in CI).  A board's design.py says which IC
power pin each decoupling capacitor serves, in b.pcb["decoupling"]: {"C14": "U3.3V3", ...} (the pin by name or
number; resolve() turns it into the pads).  For each:

  * pin: from the capacitor's pad on the pin's net to the pin's pad, edge to edge, REACH mm at most;
  * via: from its other pad (its return, GND) to the nearest via or through-hole pad of that net, edge to edge,
    VIA mm at most: the return goes straight down to the plane, not through a pour first.

    python decoupling.py BOARD [...]      → each board's table, exit status 1 if a capacitor is too far

The table also names the capacitors left undeclared (bulk, bootstrap, RC): what they serve is no pin's.

tools/tests/test_decoupling.py holds every board that declares its capacitors to both, but the ones
electronics/decoupling.json still lists.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from antennas import Copper
from flowthru import _rot

REACH = 2.0                                     # mm, capacitor pad to pin pad
VIA = 1.0                                       # mm, return pad to its via


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


def resolve(b, decl: dict) -> dict[str, tuple[str, str | None]]:
    """{cap: "REF.PIN"} → {cap: ("REF.PIN", the pin's net in design.py)}: check() then takes a pin named, not
    numbered, as the part's pads on that net (the board file keeps pad numbers only; a tab and its pin both)."""
    out = {}
    for cap, pin in decl.items():
        ref, name = pin.split(".", 1)
        part = b.parts.get(ref)
        out[cap] = (pin, part.conns.get(name) if part is not None else None)
    return out


def check(path, decl: dict) -> list[dict]:
    """One row per declared capacitor: {cap, pin, net, ret, side, pin_mm, via_mm, problems}.  `decl`: {cap:
    "REF.NUM"}, or resolve()'s {cap: ("REF.PIN", net)}."""
    c = Copper(path)
    by_ref = {}
    for p in c.pads:
        by_ref.setdefault(p["ref"], []).append(p)
    rows = []
    for cap, pin in decl.items():
        pin, net = pin if isinstance(pin, tuple) else (pin, None)
        row = {"cap": cap, "pin": pin, "net": "?", "ret": "?", "side": "?", "pin_mm": math.inf, "via_mm": math.inf,
               "problems": []}
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
        if row["pin_mm"] > REACH:
            row["problems"].append(f"{row['pin_mm']:.2f} mm from {pin} (max {REACH})")
        if row["via_mm"] > VIA:
            row["problems"].append(f"its {rp['net']} {row['via_mm']:.2f} mm from a via (max {VIA})")
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
                   f"{r['pin_mm']:7.2f} {r['via_mm']:7.2f}  {'; '.join(r['problems']) or 'ok'}")
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
