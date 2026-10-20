#!/usr/bin/env python3
"""Where the pegs go on a bay's honeycomb plate (config/rack.yaml › plate_grid, parts/pegs.scad).

    python tools/plate_layout.py            # every bay of config/rack.yaml › population
    python tools/plate_layout.py B3 A1      # some bays

A board is held at its edges, the way a fixture does it: eccentric stops (6 turns: 6 places in each hole)
place it, small cams on the opposite edges clamp it against them.  Each axis gets a datum edge (stops) and
a cam edge, whichever way round fits; a board whose long edges are lined with headers (boards.yaml ›
pegs › keepout) takes a pin through one of its mounting holes instead, and cams.  The board's place is
its hint (the classic placement, or a converted bay's `at`) moved by a few mm, so that the stops touch it
exactly and the cams reach it within their travel.  Nothing may touch another board, another peg's body,
a USB plug's way or a keep-out span of the board's edges.

Plate coords throughout: mm, origin at the plate's front-left corner, x to the right, y to the port wall
(rackcfg.Rack.plate_size, plate_holes).  A board's frame is rackcfg.orient_board's (w along x, l along y).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rackcfg  # noqa: E402

EDGES = ("L", "R", "F", "B")
NORMAL = {"L": (-1.0, 0.0), "R": (1.0, 0.0), "F": (0.0, -1.0), "B": (0.0, 1.0)}   # board → peg
AXIS = {"L": "x", "R": "x", "F": "y", "B": "y"}
OPPOSITE = {"L": "R", "R": "L", "F": "B", "B": "F"}

PCB_T = 1.6
FLANGE_R = 4.8
CAM_BODY_R = 8.0           # the cam swept round its pivot (spiral r1 + its flange's 1.2)
CAM_TOP = 4.8              # the cam's top above its own bottom (flange 1 + band 2 + grip 1.8)
PLUG_HALF = 6.5            # a USB plug's half width (12.4 overmold) and a margin
PLUG_LEN = 26.0            # its way out of the board: plug, its strain relief, the cable's first bend
WINDOW = 10.0              # how far a board may move from its hint
WINDOW_ALONE = 30.0        # ... along its USB edge, when it is its bay's only board
WALL_GAP = 0.2             # a board leaning on the drawer's wall: its edge this far inside the plate's edge
                           # (the wall's face is 0.3 mm outside it)
LIP_SPAN = 3.0             # a stop's lip (and a cam's band) over the PCB, ± along the edge
REAR_GAP_MAX = rackcfg.REAR_GAP_MAX


@dataclass
class Peg:
    kind: str                 # stop | cam | pin | bobbin
    row: int                  # the plate hole: row (1 at the front), its rank in the row from the left
    col: int
    x: float                  # the hole's centre
    y: float
    turn: int = 0             # stop / pin: the post at grid angle + 60°·turn
    angle: float = 0.0        # cam: its rotation, closed (degrees, as the viewer turns it)
    open_angle: float = 0.0   # cam: turned open (the board lifts out)
    h: float = 0.0            # the board's standoff
    hole_d: float = 0.0       # pin
    board: str = ""           # the slot it holds
    edge: str = ""            # the board's edge it touches (L R F B), "" for a pin or the bobbin
    post: tuple = (0.0, 0.0)  # stop / pin: the post's centre

    @property
    def parts(self) -> list[tuple[str, float]]:
        """(part name, rotation about z) of what is printed for it (parts/pegs.scad)."""
        if self.kind == "stop":
            return [(f"peg_stop_h{self.h:g}", 60.0 * self.turn)]
        if self.kind == "cam":
            return [(f"peg_base_h{self.h:g}", 0.0), ("peg_cam", self.angle)]
        if self.kind == "pin":
            return [(pin_name(self.hole_d, self.h), 60.0 * self.turn)]
        return [("peg_bobbin", 0.0)]


@dataclass
class Placed:
    slot: str
    board: str
    o: dict                   # rackcfg.orient_board
    at: tuple                 # its front-left corner
    h: float                  # standoff
    hint: tuple


@dataclass
class Layout:
    bay: str
    boards: list[Placed] = field(default_factory=list)
    pegs: list[Peg] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    alpha: float = 15.0       # the grid's stop angle (for the arrows' clock)


def pin_name(hole_d: float, h: float) -> str:
    return f"peg_pin_d{round(hole_d * 10)}_h{h:g}"


def peg_parts(boards: dict) -> dict[str, dict]:
    """Every peg part the board library needs: {name: -D defines for parts/pegs.scad}.  One stop and one
    cam base per standoff in boards.yaml, a pin per (hole Ø, standoff) of the boards with holes."""
    hs = sorted({float(b.get("standoff", 6)) for b in boards.values()})
    out = {"peg_cam": {"PART": "cam"}, "peg_bobbin": {"PART": "bobbin"}}
    for h in hs:
        out[f"peg_stop_h{h:g}"] = {"PART": "stop", "H": h}
        out[f"peg_base_h{h:g}"] = {"PART": "base", "H": h}
    for b in boards.values():
        if b.get("holes"):
            d, h = float(b.get("hole_d", 3.2)), float(b.get("standoff", 6))
            out[pin_name(d, h)] = {"PART": "pin", "H": h, "HOLE": d}
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ the grid and the pegs' geometry

class Grid:
    def __init__(self, rack: rackcfg.Rack):
        g = rack.plate_grid
        self.holes = rack.plate_holes()
        self.w, self.d = rack.plate_size
        dr = rack.drawer
        # the drawer's side walls reach above a board's PCB up to this standoff: such a board may lean on one
        # (WALL_GAP off it) instead of on stops; the front panel is always tall enough
        self.wall_h_max = dr["wall_height"] - dr["bottom"] - dr["plate"] - PCB_T - 0.5
        st, cm = g["stop"], g["cam"]
        self.e, self.alpha = st["offset"], st["angle"]
        self.neck, self.ledge, self.lip = st["neck"] / 2, st["ledge"] / 2, st["lip"] / 2
        self.under = 2.0 * math.tan(math.radians(cm["under"])) * (PCB_T / 2.0)   # the band's growth at the PCB's top
        self.cam = (cm["r0"], cm["r1"], cm["arc"])
        self._cam_table()
        self.stop_lines = {}
        for edge in EDGES:
            n = NORMAL[edge]
            rows = []
            for row, col, hx, hy in self.holes:
                for k, (ox, oy) in self.offsets():
                    cx, cy = hx + ox, hy + oy
                    line = (cx if AXIS[edge] == "x" else cy) - (n[0] + n[1]) * self.neck
                    rows.append((line, along((cx, cy), edge), row, col, hx, hy, k, cx, cy))
            self.stop_lines[edge] = rows

    def offsets(self):
        for k in range(6):
            a = math.radians(self.alpha + 60 * k)
            yield k, (self.e * math.cos(a), self.e * math.sin(a))

    def _cam_table(self):
        """The cam's support function: h(ψ) = how far its band reaches in direction ψ (cam frame), at the
        band's foot; and the monotonic stretch from its open minimum (the band, turning, pushes the edge
        out from DMIN to DMAX)."""
        r0, r1, arc = self.cam
        n = 400
        pts = [((r0 + (r1 - r0) * i / n) * math.cos(math.radians(arc * i / n)),
                (r0 + (r1 - r0) * i / n) * math.sin(math.radians(arc * i / n))) for i in range(n + 1)]
        self.psi = [math.radians(a / 4) for a in range(1440)]
        hs = [max(px * math.cos(s) + py * math.sin(s) for px, py in pts) for s in self.psi]
        i0 = min(range(len(hs)), key=hs.__getitem__)
        mono = [i0]
        for k in list(range(i0 + 1, len(hs))) + list(range(0, i0)):
            if hs[k] >= hs[mono[-1]]:
                mono.append(k)
            else:
                break
        self.h_cam = hs
        self.mono = mono
        self.open_psi = self.psi[i0]
        grow_top = 2.0 * math.tan(math.radians(20))                  # the band's growth over its 2 mm
        self.dmin = hs[i0] + grow_top + 0.3                          # open: the board drops in past the band's top
        self.dmax = hs[mono[-1]] + self.under - 0.3                  # closed, with 0.3 of travel left

    def cam_angles(self, dist: float, toward: float) -> tuple[float, float]:
        """The cam's rotation (deg) for its band to touch an edge `dist` away in direction `toward` (rad),
        and its open rotation."""
        k = min(self.mono, key=lambda k: abs(self.h_cam[k] - (dist - self.under)))
        return math.degrees(toward - self.psi[k]) % 360, math.degrees(toward - self.open_psi) % 360


def toward_board(edge: str) -> float:
    nx, ny = NORMAL[edge]
    return math.atan2(-ny, -nx)


def edge_coord(at, o, edge):
    x, y = at
    return {"L": x, "R": x + o["w"], "F": y, "B": y + o["l"]}[edge]


def edge_span(at, o, edge):
    x, y = at
    return (y, y + o["l"]) if AXIS[edge] == "x" else (x, x + o["w"])


def along(p, edge):
    return p[1] if AXIS[edge] == "x" else p[0]


# ------------------------------------------------------------------ a board's keep-outs

def orient_point(b: dict, x: float, y: float, side: bool) -> tuple[float, float]:
    """A point of the vendor drawing in rackcfg.orient_board's frame."""
    w, l = b["size"]
    edge = b.get("usb", {}).get("edge", "top")
    X, Y = {"top": (x, y), "bottom": (w - x, l - y), "left": (y, w - x), "right": (l - y, x)}[edge]
    if side:
        W = w if edge in ("top", "bottom") else l
        X, Y = Y, W - X
    return X, Y


def keepouts(b: dict, o: dict) -> dict[str, list[tuple[float, float]]]:
    """Edge spans (board frame, along the edge) no peg may touch: boards.yaml › pegs › keepout (drawing frame:
    [edge, from, to] as usb.pos counts), and each debug USB connector's plug."""
    out = {e: [] for e in EDGES}
    w, l = b["size"]
    ends = {"top": lambda a: (a, l), "bottom": lambda a: (a, 0.0), "left": lambda a: (0.0, a), "right": lambda a: (w, a)}
    for edge, a0, a1 in (b.get("pegs") or {}).get("keepout", []):
        p0 = orient_point(b, *ends[edge](a0), o["usb_side"])
        p1 = orient_point(b, *ends[edge](a1), o["usb_side"])
        if abs(p0[0]) < 1e-6 and abs(p1[0]) < 1e-6:
            e = "L"
        elif abs(p0[0] - o["w"]) < 1e-6 and abs(p1[0] - o["w"]) < 1e-6:
            e = "R"
        elif abs(p0[1]) < 1e-6 and abs(p1[1]) < 1e-6:
            e = "F"
        else:
            e = "B"
        k = 1 if AXIS[e] == "x" else 0
        out[e].append(tuple(sorted((p0[k], p1[k]))))
    usb_edge = "R" if o["usb_side"] else "B"
    for ux in [o["usb_x"]] + ([o["usb2_x"]] if o.get("usb2_x") is not None else []):
        out[usb_edge].append((ux - PLUG_HALF, ux + PLUG_HALF))
    return out


def span_free(keep: list, a: float, b: float) -> bool:
    return all(b <= k0 or a >= k1 for k0, k1 in keep)


# ------------------------------------------------------------------ collisions

def peg_shapes(p: Peg, g: Grid) -> list[tuple[float, float, float, float, float]]:
    """(x, y, r, z0, z1) circles a peg occupies above the plate's top."""
    h = p.h
    if p.kind == "stop":
        cx, cy = p.post
        return [(p.x, p.y, FLANGE_R, 0, 1.2), (cx, cy, 3.75, 0, 1.2), (cx, cy, g.ledge, 0, h),
                (cx, cy, g.lip, h + PCB_T, h + PCB_T + 2.3)]
    if p.kind == "cam":
        return [(p.x, p.y, FLANGE_R, 0, 1.2), (p.x, p.y, 4.25, 0, h - 1), (p.x, p.y, CAM_BODY_R, h - 1, h - 1 + CAM_TOP)]
    if p.kind == "pin":
        cx, cy = p.post
        return [(p.x, p.y, FLANGE_R, 0, 1.2), (cx, cy, (p.hole_d + 4.1) / 2, 0, h)]
    return [(p.x, p.y, 7.5, 0, 16.0)]


def shapes_clash(a, b) -> bool:
    for x1, y1, r1, z0, z1 in a:
        for x2, y2, r2, w0, w1 in b:
            if z0 < w1 and w0 < z1 and math.hypot(x1 - x2, y1 - y2) < r1 + r2 - 1e-6:
                return True
    return False


def circle_in_rect(x, y, r, rect) -> bool:
    x0, y0, x1, y1 = rect
    return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < r


def board_rect(at, o, pad=0.0):
    return (at[0] - pad, at[1] - pad, at[0] + o["w"] + pad, at[1] + o["l"] + pad)


def plug_rect(at, o, h=0.0):
    """The way out of the board's debug USB plug(s): (x0, y0, x1, y1, z0, z1), from the PCB's underside
    up to a 90° adapter's straight plug."""
    out = []
    z0, z1 = h, h + PCB_T + 25.0                 # an overmold hangs to about the PCB's underside behind its edge
    for ux in [o["usb_x"]] + ([o["usb2_x"]] if o.get("usb2_x") is not None else []):
        if o["usb_side"]:
            x = at[0] + o["w"]
            out.append((x, at[1] + ux - PLUG_HALF, x + PLUG_LEN, at[1] + ux + PLUG_HALF, z0, z1))
        else:
            y = at[1] + o["l"]
            out.append((at[0] + ux - PLUG_HALF, y, at[0] + ux + PLUG_HALF, y + PLUG_LEN, z0, z1))
    return out


def shape_in_plug(sh, plug) -> bool:
    x0, y0, x1, y1, z0, z1 = plug
    return any(c0 < z1 and z0 < c1 and circle_in_rect(x, y, r, (x0, y0, x1, y1)) for x, y, r, c0, c1 in sh)


class Scene:
    """What is already on the plate: boards, their plugs' ways, pegs."""

    def __init__(self, g: Grid):
        self.g = g
        self.boards: list[tuple[str, tuple, float]] = []    # (slot, rect, top z)
        self.plugs: list[tuple] = []
        self.pegs: list[Peg] = []
        self.future: list[tuple] = []       # the boards still to place: their hints, kept clear of pegs

    def peg_ok(self, p: Peg, own: str, own_plugs=(), extra: list[Peg] = ()) -> bool:
        sh = peg_shapes(p, self.g)
        for q in list(self.pegs) + list(extra):
            if (q.row, q.col) == (p.row, p.col) or shapes_clash(sh, peg_shapes(q, self.g)):
                return False
        for slot, rect, top in self.boards:
            if slot == own:
                continue
            if any(circle_in_rect(x, y, r, rect) for x, y, r, z0, z1 in sh):
                return False
        if any(shape_in_plug(sh, pl) for pl in self.plugs) or                 any(any(circle_in_rect(x, y, r, rect) for x, y, r, z0, z1 in sh) for rect in self.future):
            return False
        if any(shape_in_plug(sh, pl) for pl in own_plugs):
            return False                  # the board's own plug's way
        return True


# ------------------------------------------------------------------ one board

class BoardSolver:
    def __init__(self, g: Grid, scene: Scene, slot: str, b: dict, o: dict, hint: tuple, alone: bool = False):
        self.g, self.scene, self.slot, self.b, self.o, self.hint = g, scene, slot, b, o, hint
        self.h = float(b.get("standoff", 6))
        self.keep = keepouts(b, o)
        # how far it may move from its hint, per axis: a bay's only board may slide further along its USB edge
        # (its cable doesn't care), a converted bay's boards stay near their `at`
        along_usb = WINDOW_ALONE if alone else WINDOW
        self.window = (WINDOW, along_usb) if o["usb_side"] else (along_usb, WINDOW)

    def in_window(self, at) -> bool:
        return abs(at[0] - self.hint[0]) <= self.window[0] + 1e-9 and abs(at[1] - self.hint[1]) <= self.window[1] + 1e-9

    # -- candidates
    def stop_options(self, edge: str, at: tuple) -> list[tuple[float, Peg]]:
        """Stops that can touch `edge` with the board near `at`: (the board's coordinate on that axis, peg)."""
        out = []
        s0, s1 = edge_span(at, self.o, edge)
        size = self.o["w"] if edge == "R" else self.o["l"] if edge == "B" else 0.0
        hint = self.hint[0] if AXIS[edge] == "x" else self.hint[1]
        win = self.window[0] if AXIS[edge] == "x" else self.window[1]
        for line, a, row, col, hx, hy, k, cx, cy in self.g.stop_lines[edge]:
            coord = line - size
            if abs(coord - hint) > win or not (s0 + LIP_SPAN <= a <= s1 - LIP_SPAN):
                continue
            rel = a - s0
            if not span_free(self.keep[edge], rel - LIP_SPAN, rel + LIP_SPAN):
                continue
            out.append((coord, Peg("stop", row, col, hx, hy, turn=k, h=self.h, board=self.slot, edge=edge,
                                   post=(cx, cy))))
        return out

    def cam_options(self, edge: str, at: tuple) -> list[Peg]:
        out = []
        n = NORMAL[edge]
        ec = edge_coord(at, self.o, edge)
        s0, s1 = edge_span(at, self.o, edge)
        for row, col, hx, hy in self.g.holes:
            dist = (hx - ec) * n[0] if AXIS[edge] == "x" else (hy - ec) * n[1]
            if not (self.g.dmin <= dist <= self.g.dmax):
                continue
            a = along((hx, hy), edge)
            if not (s0 + LIP_SPAN <= a <= s1 - LIP_SPAN):
                continue
            rel = a - s0
            if not span_free(self.keep[edge], rel - LIP_SPAN - 1, rel + LIP_SPAN + 1):
                continue
            ang, op = self.g.cam_angles(dist, toward_board(edge))
            out.append(Peg("cam", row, col, hx, hy, angle=round(ang, 1), open_angle=round(op, 1), h=self.h,
                           board=self.slot, edge=edge))
        return out

    def pick_stops(self, edge, at, n_want) -> list[Peg] | None:
        """n_want stops on `edge` (all touching, the same contact line), spread along it, none clashing."""
        coord = edge_coord(at, self.o, edge)
        found = [p for c, p in self.stop_options(edge, at) if abs((c + (self.o["w"] if edge == "R" else self.o["l"] if edge == "B" else 0)) - coord) < 1e-3]
        found = [p for p in found if self.scene.peg_ok(p, self.slot, plug_rect(at, self.o, self.h))]
        if not found:
            return None
        found.sort(key=lambda p: along(p.post, edge))
        if n_want == 1 or len(found) == 1:
            s0, s1 = edge_span(at, self.o, edge)
            mid = (s0 + s1) / 2
            return [min(found, key=lambda p: abs(along(p.post, edge) - mid))]
        a, b = found[0], found[-1]
        if along(b.post, edge) - along(a.post, edge) < 12 or not self.scene.peg_ok(b, self.slot, plug_rect(at, self.o, self.h), [a]):
            return [a]
        return [a, b]

    def pick_cams(self, edge, at, n_want, extra) -> list[Peg]:
        cams = [p for p in self.cam_options(edge, at) if self.scene.peg_ok(p, self.slot, plug_rect(at, self.o, self.h), extra)]
        if not cams:
            return []
        mid_d = (self.g.dmin + self.g.dmax) / 2
        s0, s1 = edge_span(at, self.o, edge)
        if n_want == 1 or len(cams) == 1:
            return [min(cams, key=lambda p: abs(along((p.x, p.y), edge) - (s0 + s1) / 2) * 0.05
                        + abs(abs((p.x if AXIS[edge] == 'x' else p.y) - edge_coord(at, self.o, edge)) - mid_d))]
        cams.sort(key=lambda p: along((p.x, p.y), edge))
        a = cams[0]
        b = next((c for c in reversed(cams) if along((c.x, c.y), edge) - along((a.x, a.y), edge) >= 20
                  and self.scene.peg_ok(c, self.slot, plug_rect(at, self.o, self.h), extra + [a])), None)
        return [a, b] if b else [a]

    def away(self, axis: str, coord: float) -> float:
        """How much a move costs the board's DUT cable: a board facing the port wall moved away from it (its
        cable gets longer); one turned to the right wall moved towards it (its straight plug and the cable's
        bend need the room between it and the DATA socket's line)."""
        usb_axis = "x" if self.o["usb_side"] else "y"
        if axis != usb_axis:
            return 0.0
        hint = self.hint[0] if axis == "x" else self.hint[1]
        return max(0.0, coord - hint) if self.o["usb_side"] else max(0.0, hint - coord)

    # -- one axis
    def axis_options(self, axis: str, at: tuple) -> list[tuple[float, float, str, str]]:
        """(cost, coordinate, datum edge, cam edge or "") for the board's position on one axis."""
        edges = ("L", "R") if axis == "x" else ("F", "B")
        hint = self.hint[0] if axis == "x" else self.hint[1]
        out = []
        for datum in edges:
            cam_edge = OPPOSITE[datum]
            for coord, p in self.stop_options(datum, at):
                a2 = (coord, at[1]) if axis == "x" else (at[0], coord)
                has_cam = bool(self.cam_options(cam_edge, a2))
                out.append((abs(coord - hint) + self.away(axis, coord) + (0 if has_cam else 15), coord, datum,
                            cam_edge if has_cam else ""))
        for wall, coord in self.wall_options(axis):
            if abs(coord - hint) > (self.window[0] if axis == "x" else self.window[1]):
                continue
            a2 = (coord, at[1]) if axis == "x" else (at[0], coord)
            cam_edge = OPPOSITE[wall]
            has_cam = bool(self.cam_options(cam_edge, a2))
            out.append((abs(coord - hint) + self.away(axis, coord) + (0 if has_cam else 15), coord, "wall" + wall,
                        cam_edge if has_cam else ""))
        out.sort()
        seen, uniq = set(), []
        for c in out:
            key = (round(c[1], 3), c[2], c[3])
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        return uniq

    def wall_options(self, axis: str) -> list[tuple[str, float]]:
        """The drawer's walls a board may lean on: (edge, the board's coordinate)."""
        if axis == "y":
            return [("F", WALL_GAP)]
        if self.h > self.g.wall_h_max:
            return []
        return [("L", WALL_GAP), ("R", self.g.w - self.o["w"] - WALL_GAP)]

    def edges_layout(self) -> tuple[float, tuple, list[Peg], list[str]] | None:
        """Stops and cams on the edges.  Returns (cost, at, pegs, notes)."""
        best = None
        ys = self.axis_options("y", self.hint)[:12] or [(30.0, self.hint[1], "", "")]
        for cy, y, dy, ky in ys:
            xs = self.axis_options("x", (self.hint[0], y))[:12] or [(30.0, self.hint[0], "", "")]
            for cx, x, dx, kx in xs:
                at = (x, y)
                r = self.realise(at, [(dy, ky), (dx, kx)])
                if r is None:
                    continue
                pegs, notes = r
                cost = cx + cy + 2 * len([n for n in notes if "against" not in n]) + 0.3 * len(pegs)
                if best is None or cost < best[0]:
                    best = (cost, at, pegs, notes)
            if best and best[0] < 3:
                break
        return best

    def realise(self, at, plan) -> tuple[list[Peg], list[str]] | None:
        """The pegs of a plan [(datum edge, cam edge)] at `at`, or None if they don't fit."""
        if not self.fits(at):
            return None
        pegs, notes = [], []
        for datum, cam_edge in plan:
            if not datum:
                notes.append("held along one axis by friction only")
                continue
            if datum.startswith("wall"):
                notes.append({"L": "against the drawer's left wall", "R": "against the drawer's right wall",
                              "F": "against the drawer's front panel"}[datum[4:]])
                if cam_edge:
                    length = (self.o["l"] if AXIS[cam_edge] == "x" else self.o["w"])
                    cams = self.pick_cams(cam_edge, at, 2 if length >= 60 else 1, pegs)
                    if not cams:
                        return None
                    pegs += cams
                continue
            length = (self.o["l"] if AXIS[datum] == "x" else self.o["w"])
            stops = self.pick_stops(datum, at, 2 if length >= 30 else 1)
            if stops is None:
                return None
            pegs += stops
            if cam_edge:
                cams = self.pick_cams(cam_edge, at, 2 if length >= 60 else 1, pegs)
                if not cams:
                    return None
                pegs += cams
            else:
                notes.append(f"no cam on its {OPPOSITE[datum]} edge")
        # the pegs of one board must not clash with each other either
        for i, p in enumerate(pegs):
            for q in pegs[i + 1:]:
                if (p.row, p.col) == (q.row, q.col) or shapes_clash(peg_shapes(p, self.g), peg_shapes(q, self.g)):
                    return None
        return pegs, notes

    def pin_layout(self) -> tuple[float, tuple, list[Peg], list[str]] | None:
        """A pin through one mounting hole, cams on the edges that push the board onto it."""
        holes = self.o.get("holes") or []
        if not holes:
            return None
        d = float(self.b.get("hole_d", 3.2))
        best = None
        for hx_b, hy_b in holes:
            for row, col, hx, hy in self.g.holes:
                for k, (ox, oy) in self.g.offsets():
                    px, py = hx + ox, hy + oy
                    at = (round(px - hx_b, 3), round(py - hy_b, 3))
                    off = math.hypot(at[0] - self.hint[0], at[1] - self.hint[1])
                    if not self.in_window(at) or not self.fits(at):
                        continue
                    pin = Peg("pin", row, col, hx, hy, turn=k, h=self.h, hole_d=d, board=self.slot, post=(px, py))
                    if not self.scene.peg_ok(pin, self.slot, plug_rect(at, self.o, self.h)):
                        continue
                    # cams, the edges farther from the pin first (they push the board onto it), two at most
                    far = [("F" if hy_b > self.o["l"] / 2 else "B"), ("L" if hx_b > self.o["w"] / 2 else "R")]
                    pegs = [pin]
                    for e in far + [OPPOSITE[f] for f in far]:
                        if len(pegs) >= 3:
                            break
                        want = min(3 - len(pegs), 2 if (self.o["w"] if AXIS[e] == "y" else self.o["l"]) >= 30 else 1)
                        pegs += self.pick_cams(e, at, want, pegs)
                    n_cams = len(pegs) - 1
                    if n_cams == 0:
                        continue
                    # a cam close to the pin barely stops the board turning about it: the pin goes to the far end
                    lever = max(math.hypot(p.x - px, p.y - py) for p in pegs[1:])
                    short = 10.0 if lever < max(self.o["w"], self.o["l"]) / 2 else 0.0
                    cost = off + self.away("x", at[0]) + self.away("y", at[1]) + 6.0 + (20 if n_cams < 2 else 0) + short
                    if best is None or cost < best[0]:
                        best = (cost, at, pegs, [] if n_cams >= 2 else ["one cam only"])
        return best

    def fits(self, at) -> bool:
        x0, y0, x1, y1 = board_rect(at, self.o)
        if x0 < WALL_GAP - 1e-6 or y0 < WALL_GAP - 1e-6 or x1 > self.g.w - WALL_GAP + 1e-6 or y1 > self.g.d - 0.5:
            return False
        for slot, rect, top in self.scene.boards:
            a0, b0, a1, b1 = rect
            if x0 < a1 + 1 and a0 < x1 + 1 and y0 < b1 + 1 and b0 < y1 + 1:
                return False
        for p in self.scene.pegs:
            if any(circle_in_rect(x, y, r, (x0, y0, x1, y1)) for x, y, r, z0, z1 in peg_shapes(p, self.g)):
                return False
        for rect in plug_rect(at, self.o, self.h):
            r0, s0, r1, s1 = rect[:4]
            if r1 > self.g.w + 30 or s1 > self.g.d + 40:
                return False
        return True

    def solve(self) -> tuple[tuple, list[Peg], list[str]]:
        cands = [c for c in (self.edges_layout(), self.pin_layout()) if c]
        if not cands:
            return self.hint, [], ["no peg fits: placed at its hint, unheld"]
        cost, at, pegs, notes = min(cands, key=lambda c: c[0])
        return at, pegs, notes


# ------------------------------------------------------------------ a bay

SIDE_X_MAX = 66.0          # a board turned to the right wall: its right edge at most here (plate x), so that its
                           # straight plug and the cable's bend fit before the DATA socket's line (webscene's
                           # flat_cable: the socket at 0.8 × the drawer's width, a 28 mm plug, a 10 mm bend)


def classic_hint(o: dict, w: float, d: float) -> tuple[float, float]:
    """A one-board bay's place before pegs: centred, its USB REAR_GAP_MAX from the port wall at most; a board
    turned to the right wall as far right as its cable allows, up to 16 mm off the left edge (room for a cam
    there), centred front to back (`away` keeps it from going further right)."""
    if o["usb_side"]:
        return max(7.0, min(16.0, SIDE_X_MAX - o["w"])), (d - o["l"]) / 2
    rear_gap = max(3.0, min(REAR_GAP_MAX, d - o["l"] - 4))
    return (w - o["w"]) / 2, d - rear_gap - o["l"]


def layout_bay(rack: rackcfg.Rack, bay_id: str, boards: dict | None = None, bobbin: bool | None = None) -> Layout:
    lib = boards if boards is not None else rackcfg.load_boards()
    g = Grid(rack)
    scene = Scene(g)
    out = Layout(bay_id, alpha=g.alpha)
    entries = []
    if rack.is_multi(bay_id):
        for e in rack.bay_layout(bay_id, lib):
            sl = e["slot"]
            entries.append((sl.id, e["board"], {**lib[e["board"]], "orient": sl.orient or "rear"}, e["o"], e["at"]))
    else:
        for sl in rack.duts(bay_id):
            o = rackcfg.orient_board(lib[sl.board])
            entries.append((sl.id, sl.board, lib[sl.board], o, classic_hint(o, g.w, g.d)))
    for n, (slot, bid, b, o, hint) in enumerate(entries):
        scene.future = [board_rect(h, oo, 1.0) for _, _, _, oo, h in entries[n + 1:]]
        s = BoardSolver(g, scene, slot, b, o, tuple(hint), alone=not rack.is_multi(bay_id))
        at, pegs, notes = s.solve()
        at = (round(at[0], 3), round(at[1], 3))
        out.boards.append(Placed(slot, bid, o, at, s.h, tuple(hint)))
        out.pegs += pegs
        out.notes += [f"{slot}: {n}" for n in notes]
        scene.boards.append((slot, board_rect(at, o), s.h + PCB_T + float(b.get("height", 10))))
        scene.plugs += plug_rect(at, o, s.h)
        scene.pegs += pegs
    if bobbin if bobbin is not None else not rack.is_multi(bay_id):
        p = place_bobbin(g, scene, out)
        if p:
            out.pegs.append(p)
            scene.pegs.append(p)
    return out


def place_bobbin(g: Grid, scene: Scene, lay: Layout) -> Peg | None:
    """The cable's bobbin: a free hole near the port wall, away from the USB plug's way."""
    if not lay.boards:
        return None
    pb = lay.boards[0]
    ux = pb.at[0] + (pb.o["w"] if pb.o["usb_side"] else pb.o["usb_x"])
    best = None
    for row, col, x, y in g.holes:
        p = Peg("bobbin", row, col, x, y, board=pb.slot)
        if y < g.d - 40 or not scene.peg_ok(p, ""):
            continue
        if any(circle_in_rect(x, y, 8.5, rect) for _, rect, _ in scene.boards):
            continue
        cost = -abs(x - ux) * 0.3 + (g.d - y) * 0.2
        if best is None or cost < best[0]:
            best = (cost, p)
    return best[1] if best else None


# ------------------------------------------------------------------ CLI

def clock(turn: int, alpha: float) -> str:
    """A stop's or pin's turn as the clock hour its flange's arrow points to, 12 o'clock towards the port
    wall (the rear), seen from above."""
    h = ((90 - (alpha + 60 * turn)) / 30) % 12
    hh, mm = int(h), round((h - int(h)) * 60)
    return f"{hh or 12}:{mm:02d}"


def describe(lay: Layout) -> str:
    lines = [f"{lay.bay}:"]
    for pb in lay.boards:
        dx, dy = pb.at[0] - pb.hint[0], pb.at[1] - pb.hint[1]
        lines.append(f"  {pb.slot} {pb.board}: front-left corner at ({pb.at[0]:.1f}, {pb.at[1]:.1f})"
                     + (f", {math.hypot(dx, dy):.1f} mm from its hint" if math.hypot(dx, dy) > 0.05 else ""))
        for p in sorted([q for q in lay.pegs if q.board == pb.slot and q.kind != "bobbin"], key=lambda q: (q.row, q.col)):
            arrow = clock(p.turn, lay.alpha)
            what = {"stop": f"stop H{p.h:g}, arrow at {arrow}, {p.edge} edge",
                    "cam": f"cam on base H{p.h:g}, {p.edge} edge",
                    "pin": f"pin d{p.hole_d - 0.3:.1f} H{p.h:g}, arrow at {arrow}"}[p.kind]
            lines.append(f"    row {p.row:2d}, hole {p.col:2d}: {what}")
    for p in lay.pegs:
        if p.kind == "bobbin":
            lines.append(f"  bobbin: row {p.row}, hole {p.col}")
    for n in lay.notes:
        lines.append(f"  note: {n}")
    return "\n".join(lines)


def main():
    rack = rackcfg.load()
    want = [a.upper() for a in sys.argv[1:]] or [b.id for b in rack.bays()]
    for bay in rack.bays():
        if bay.id in want and rack.duts(bay.id) and rack.plate_kind(bay.id) == "pegs":
            print(describe(layout_bay(rack, bay.id)))


if __name__ == "__main__":
    main()
