"""Straight and 45° track geometry, free of KiCad: the shortest such paths between two points with the fewest
bends (pcbgen.tidy_tracks), and whether a polyline bends where two segments meet (route_metrics)."""

from __future__ import annotations

import math

# where a three-segment path puts its middle segment along the way, when none of the run's own lines will do
SPLITS = tuple(k / 16 for k in (8, 6, 10, 4, 12, 2, 14, 7, 9, 5, 11, 3, 13, 1, 15))


def paths(a: tuple[int, int], b: tuple[int, int], tol: int = 1, through=()) -> list[list[tuple[int, int]]]:
    """Every path of straight and 45° segments from a to b, as short as such a path can be, by fewest bends:
    one segment when b is straight or 45° from a (within tol); else the two with one bend (45° then
    straight, straight then 45°), then the doglegs (straight, 45°, straight and 45°, straight, 45°): first
    those whose middle segment runs through one of the points `through` (on the route being replaced: its
    own lines are clear), then with it at each of SPLITS of the way."""
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    if abs(dx) <= tol or abs(dy) <= tol or abs(abs(dx) - abs(dy)) <= tol:
        return [[a, b]]
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    d = min(abs(dx), abs(dy))                   # the 45° part, along each axis
    s = max(abs(dx), abs(dy)) - d               # the straight part, along the major axis
    major_x = abs(dx) > abs(dy)
    ux, uy = (sx, 0) if major_x else (0, sy)
    out = [[a, (ax + sx * d, ay + sy * d), b], [a, (bx - sx * d, by - sy * d), b]]
    s_at, d_at = [], []
    for x, y in through:
        # the 45° line through (x, y), met after s1 of straight; the straight one, after d1 of 45°
        s_at.append((x - ax) * sx + (ay - y) * sy if major_x else (y - ay) * sy + (ax - x) * sx)
        d_at.append((y - ay) * sy if major_x else (x - ax) * sx)
    s_at += [round(s * f) for f in SPLITS]
    d_at += [round(d * f) for f in SPLITS]
    seen = set()
    for s1, d1 in zip(s_at, d_at):
        for kind, v, top in (("s", s1, s), ("d", d1, d)):
            if not tol < v < top - tol or (kind, v) in seen:
                continue
            seen.add((kind, v))
            if kind == "s":
                p = (ax + ux * v, ay + uy * v)
                out.append([a, p, (p[0] + sx * d, p[1] + sy * d), b])
            else:
                p = (ax + sx * v, ay + sy * v)
                out.append([a, p, (p[0] + ux * s, p[1] + uy * s), b])
    return out


def length(pts) -> float:
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))


def bent(u: tuple[int, int], v: tuple[int, int], deg: float = 1.0) -> bool:
    """Two segments leave a point along u and v: does the track turn there (by more than `deg`)?"""
    nu, nv = math.hypot(*u), math.hypot(*v)
    if not nu or not nv:
        return False
    cos = (u[0] * v[0] + u[1] * v[1]) / (nu * nv)
    return cos > -math.cos(math.radians(deg))      # straight through: u and v opposite, cos = -1
