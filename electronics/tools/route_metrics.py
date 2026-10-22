"""What a routed board looks like, in numbers (runs inside KiCad's Python).

tools/route_farm.py ranks candidate routings of the same placement with these, next to KiCad's DRC: vias,
copper length (per layer), the pairs' skew and coupling, copper on the plane layers, and whether the tracks
design.py drew and locked are still there.
"""

from __future__ import annotations

import math

import pcbnew

import octilinear

MM = pcbnew.ToMM


def diff_pairs(b, names: set[str]) -> list[tuple[str, str]]:
    """The board's differential pairs: b.pcb["match"]'s, else every net ending in _DP / _P with its _DN / _N."""
    if b.pcb.get("match"):
        return [(b.pcb_net_name(p), b.pcb_net_name(n)) for p, n in b.pcb["match"]["pairs"]]
    out = []
    for n in sorted(names):
        for sp, sn in (("_DP", "_DN"), ("_D+", "_D-"), ("_P", "_N")):
            if n.endswith(sp) and n[: -len(sp)] + sn in names:
                out.append((n, n[: -len(sp)] + sn))
    return out


def _segments(tracks, code):
    return [(t.GetLayer(), MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth()))
            for t in tracks if t.GetNetCode() == code and t.GetClass() != "PCB_VIA"]


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)


def pair_quality(tracks, pos_code, neg_code, step: float = 0.1) -> dict:
    """Skew and coupling of one pair: its lines' copper lengths, and how much of the positive line runs beside
    the negative one on the same layer (centre to centre within twice its width plus 0.25 mm), with the mean
    centre distance over the coupled stretches."""
    p, n = _segments(tracks, pos_code), _segments(tracks, neg_code)
    lp = sum(math.hypot(x1 - x0, y1 - y0) for _, x0, y0, x1, y1, _ in p)
    ln = sum(math.hypot(x1 - x0, y1 - y0) for _, x0, y0, x1, y1, _ in n)
    coupled = total = dsum = 0.0
    for layer, x0, y0, x1, y1, w in p:
        L = math.hypot(x1 - x0, y1 - y0)
        k = max(1, int(L / step))
        near = [s for s in n if s[0] == layer]
        for i in range(k):
            u = (i + 0.5) / k
            px, py = x0 + u * (x1 - x0), y0 + u * (y1 - y0)
            d = min((_seg_dist(px, py, *s[1:5]) for s in near), default=math.inf)
            total += L / k
            if d <= 2 * w + 0.25:
                coupled += L / k
                dsum += d * L / k
    return {"len_p": round(lp, 2), "len_n": round(ln, 2), "skew": round(abs(lp - ln), 2),
            "coupled": round(coupled / total, 3) if total else 0.0,
            "pitch": round(dsum / coupled, 3) if coupled else None}


def routing_metrics(board, b) -> dict:
    """Vias, track length per layer, bends, pairs, plane-layer copper and locked tracks of a loaded board."""
    tracks = list(board.GetTracks())
    vias = [t for t in tracks if t.GetClass() == "PCB_VIA"]
    segs = [t for t in tracks if t.GetClass() != "PCB_VIA"]
    per_layer: dict[str, float] = {}
    for t in segs:
        name = board.GetLayerName(t.GetLayer())
        per_layer[name] = per_layer.get(name, 0.0) + MM(t.GetLength())
    # the plane layers (b.pcb["inner"] entries typed "power"): copper of a net that has no pour there
    planes = {f"In{i + 1}.Cu" for i, (_, kind) in enumerate(b.pcb.get("inner", [])) if kind == "power"}
    poured = {(z["layer"], b.pcb_net_name(z["net"])) for z in b.pcb.get("zones", [])}
    on_planes = sum(MM(t.GetLength()) for t in segs
                    if board.GetLayerName(t.GetLayer()) in planes
                    and (board.GetLayerName(t.GetLayer()), t.GetNetname()) not in poured)
    nets = {str(n): v.GetNetCode() for n, v in board.GetNetsByName().items()}
    pairs = {}
    for pn, nn in diff_pairs(b, set(nets)):
        if pn in nets and nn in nets:
            pairs[f"{pn.split('/')[-1]}/{nn.split('/')[-1]}"] = pair_quality(tracks, nets[pn], nets[nn])
    # bends: where exactly two segments of a net meet on a layer and the track turns
    ends: dict = {}
    for t in segs:
        a, e = t.GetStart(), t.GetEnd()
        for p, q in ((a, e), (e, a)):
            ends.setdefault((t.GetNetCode(), t.GetLayer(), p.x, p.y), []).append((q.x - p.x, q.y - p.y))
    bends = sum(1 for v in ends.values() if len(v) == 2 and octilinear.bent(*v))
    return {
        "vias": len(vias), "tracks": len(segs), "bends": bends,
        "length_mm": round(sum(per_layer.values()), 1),
        "length_per_layer": {k: round(v, 1) for k, v in sorted(per_layer.items())},
        "locked_tracks": sum(1 for t in segs if t.IsLocked()), "locked_vias": sum(1 for t in vias if t.IsLocked()),
        "plane_layer_signal_mm": round(on_planes, 1),
        "pairs": pairs,
    }
