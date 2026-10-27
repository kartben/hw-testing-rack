"""Flow-through ESD check, from the .kicad_pcb text alone (no pcbnew: it runs in CI).

A flow-through protector (an H5VU25UC, a USBLC6, …) clamps a line only if the line runs *through* it: the
connector's pad, copper to the ESD part's first pad, its partner pad across the part, copper on to the next
part.  If the line reaches the next part another way and the ESD pads hang off it on a stub, a transient
bypasses them.  Each board lists its lines in `<board>/flow-through.json`:

    {"lines": [{"net": "PORT1_P1", "connector": "J102.2", "esd": ["U105.1", "U105.10"], "next": "RN101.1"}, …]}

`esd` is ordered: the connector side first.  For each line, with the two ESD pads taken out of the net's copper
(tracks, vias, pads; pours ignored), the connector and the next pad must fall apart.  The connector's piece must
touch the first ESD pad only and the next part's piece the second only, and any other piece must join the two
ESD pads (the board's link under the part, where the part has none inside).  Nothing else may hang on either
ESD pad.

    python flowthru.py BOARD.kicad_pcb [LINES.json]      → one line per failure, exit status 1 if any
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')
EPS = 0.002                                     # mm: endpoints that coincide


def parse(text: str):
    """S-expression → nested lists of str (quotes stripped)."""
    stack, cur = [], []
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t[1:-1] if t[0] == '"' else t)
    return cur[0]


def _get(node, key):
    return next((c for c in node[1:] if isinstance(c, list) and c and c[0] == key), None)


def _all(node, key):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == key]


def _rot(x, y, deg):
    """KiCad's rotation: degrees, counter-clockwise on screen (y down)."""
    a = math.radians(deg)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


class Board:
    def __init__(self, path):
        root = parse(Path(path).read_text(encoding="utf-8"))
        self.pads = {}                          # "REF.NUM" → [pad, …] (a number may repeat: shell, EP)
        self.items = []                         # (kind, net, layers, geometry)
        for fp in _all(root, "footprint"):
            at = _get(fp, "at")
            fx, fy, fr = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
            ref = next((p[2] for p in _all(fp, "property") if p[1] == "Reference"), "?")
            for pad in _all(fp, "pad"):
                net = _get(pad, "net")
                pat = _get(pad, "at")
                px, py = _rot(float(pat[1]), float(pat[2]), fr)
                size = _get(pad, "size")
                layers = set(_get(pad, "layers")[1:])
                if "*.Cu" in layers:
                    layers = {"*"}
                d = {"ref": ref, "num": pad[1], "x": fx + px, "y": fy + py,
                     "rot": float(pat[3]) if len(pat) > 3 else 0.0,
                     "w": float(size[1]), "h": float(size[2]), "shape": pad[3], "layers": layers,
                     "net": net[-1] if net else ""}
                self.pads.setdefault(f"{ref}.{pad[1]}", []).append(d)
                self.items.append(("pad", d["net"], layers, d))
        for s in _all(root, "segment"):
            st, en = _get(s, "start"), _get(s, "end")
            self.items.append(("seg", _get(s, "net")[-1], {_get(s, "layer")[1]},
                               (float(st[1]), float(st[2]), float(en[1]), float(en[2]), float(_get(s, "width")[1]))))
        for v in _all(root, "via"):
            at = _get(v, "at")
            self.items.append(("via", _get(v, "net")[-1], {"*"},
                               (float(at[1]), float(at[2]), float(_get(v, "size")[1]))))


def _net_of(name: str) -> str:
    return name.split("/")[-1]


def _in_pad(p, x, y, tol=EPS):
    """A point inside a pad (its rotated rectangle; ovals and circles as capsules)."""
    dx, dy = _rot(x - p["x"], y - p["y"], -p["rot"])
    hw, hh = p["w"] / 2 + tol, p["h"] / 2 + tol
    if p["shape"] in ("circle", "oval"):
        r = min(hw, hh)
        ex, ey = max(abs(dx) - (hw - r), 0), max(abs(dy) - (hh - r), 0)
        return ex * ex + ey * ey <= r * r
    return abs(dx) <= hw and abs(dy) <= hh


def _on_seg(s, x, y):
    x1, y1, x2, y2, w = s
    vx, vy = x2 - x1, y2 - y1
    L = vx * vx + vy * vy
    t = 0 if L == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / L))
    return math.hypot(x - x1 - t * vx, y - y1 - t * vy) <= EPS


def _share_layer(a, b):
    return "*" in a or "*" in b or bool(a & b)


def _contacts(a, b) -> list[tuple[float, float]]:
    """Where two copper items of a net meet (empty: they don't).  Pads meet only through copper."""
    ka, _, la, ga = a
    kb, _, lb, gb = b
    if not _share_layer(la, lb) or (ka == "pad" and kb == "pad"):
        return []
    if kb == "pad" or (kb == "via" and ka == "seg"):
        a, b = b, a
        ka, ga, kb, gb = kb, gb, ka, ga
    if ka == "pad":
        ends = [(gb[0], gb[1]), (gb[2], gb[3])] if kb == "seg" else [(gb[0], gb[1])]
        return [e for e in ends if _in_pad(ga, *e)]
    if ka == "via":
        if kb == "via":
            return [(ga[0], ga[1])] if math.hypot(ga[0] - gb[0], ga[1] - gb[1]) <= EPS else []
        return [e for e in ((gb[0], gb[1]), (gb[2], gb[3])) if math.hypot(ga[0] - e[0], ga[1] - e[1]) <= ga[2] / 2]
    # two tracks: an end on the other (a joint or a T)
    return ([e for e in ((ga[0], ga[1]), (ga[2], ga[3])) if _on_seg(gb, *e)] +
            [e for e in ((gb[0], gb[1]), (gb[2], gb[3])) if _on_seg(ga, *e)])


def _touch(a, b, inside=()) -> bool:
    """They meet somewhere outside the pads in `inside` (copper meeting inside an ESD pad meets through it)."""
    return any(not any(_in_pad(p, *c) for p in inside) for c in _contacts(a, b))


def check_line(board: Board, line: dict) -> list[str]:
    """The line's failures (empty: it runs through its ESD part)."""
    net = line["net"]
    items = [it for it in board.items if _net_of(it[1]) == net]
    if not items:
        return [f"{net}: no such net"]

    def pad(name):
        for p in board.pads.get(name, ()):
            if _net_of(p["net"]) == net:
                return p
        return None
    con, e1, e2, nxt = pad(line["connector"]), pad(line["esd"][0]), pad(line["esd"][1]), pad(line["next"])
    missing = [n for n, p in zip((line["connector"], *line["esd"], line["next"]), (con, e1, e2, nxt)) if p is None]
    if missing:
        return [f"{net}: pad {', '.join(missing)} not on the net"]
    # the net's copper without the two ESD pads, in pieces
    rest = [it for it in items if not (it[0] == "pad" and it[3] in (e1, e2))]
    n = len(rest)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if _touch(rest[i], rest[j], (e1, e2)):
                parent[find(i)] = find(j)
    piece = {}
    for i in range(n):
        piece.setdefault(find(i), []).append(rest[i])
    e1_item, e2_item = ("pad", net, e1["layers"], e1), ("pad", net, e2["layers"], e2)

    def touches(members, e):
        return any(_touch(m, e) for m in members)
    where = {id(it[3]): k for k, members in piece.items() for it in members if it[0] == "pad"}
    kc, kn = where[id(con)], where[id(nxt)]
    out = []
    if kc == kn:
        out.append(f"{net}: {line['connector']} reaches {line['next']} "
                   f"without passing {line['esd'][0]}/{line['esd'][1]}")
    else:
        if not touches(piece[kc], e1_item) or touches(piece[kc], e2_item):
            out.append(f"{net}: the connector's copper must reach {line['esd'][0]} only")
        if not touches(piece[kn], e2_item) or touches(piece[kn], e1_item):
            out.append(f"{net}: {line['next']}'s copper must start at {line['esd'][1]} only")
    def within(members, e):                     # copper lying inside the pad: the pad's own, not a stub
        return all(m[0] == "seg" and _in_pad(e, m[3][0], m[3][1]) and _in_pad(e, m[3][2], m[3][3]) for m in members)
    for k, members in piece.items():
        if k in (kc, kn) or within(members, e1) or within(members, e2):
            continue
        a, b = touches(members, e1_item), touches(members, e2_item)
        if (a or b) and not (a and b):
            out.append(f"{net}: a stub hangs on {line['esd'][0] if a else line['esd'][1]}")
    return out


def check(board_path, lines_path=None) -> list[str]:
    board_path = Path(board_path)
    lines_path = Path(lines_path) if lines_path else board_path.parent / "flow-through.json"
    lines = json.loads(lines_path.read_text(encoding="utf-8"))["lines"]
    board = Board(board_path)
    return [f for line in lines for f in check_line(board, line)]


if __name__ == "__main__":
    fails = check(*sys.argv[1:3])
    for f in fails:
        print(f)
    sys.exit(1 if fails else 0)
