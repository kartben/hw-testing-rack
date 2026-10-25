"""Build a `.kicad_pcb` from a board description (runs inside KiCad's Python).

Footprints come from the stock KiCad libraries (plus `electronics/lib/bench.pretty`),
nets and symbol paths come from the same `Board` object that produced the
schematic, so `kicad-cli pcb drc --schematic-parity` can prove both match.

Placement is given in each part's `pcb` hints (mm, board origin top-left).
Routing is delegated to Freerouting through Specctra DSN/SES; the result is
a reviewable starting point, not a signed-off layout (see docs/electronics.md).
"""

from __future__ import annotations

import fnmatch
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pcbnew

import octilinear

from catalog import HAND_SOLDER_LCSC, MODELS
from eda import Board, Part, REPO

FP_DIR = Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
PROJECT_FP_DIR = REPO / "electronics" / "lib" / "bench.pretty"
FREEROUTING = os.environ.get("FREEROUTING", "/tmp/freerouting-cli")

MM = pcbnew.FromMM

# The smallest via used anywhere (GND ties squeezed between fine-pitch pads): 0.5 mm pad, 0.3 mm drill.
# 0.3 mm is JLCPCB's smallest drill at no extra cost; 0.25 mm is their "high precision" option, which
# also forces a 4-wire Kelvin test and FR4 Tg155 (≈ +$40 on a 20-board 4-layer order).  The 0.1 mm ring
# keeps the hole 0.25 mm from any track the router keeps 0.15 mm from the pad (Freerouting doesn't
# know KiCad's hole clearance rule).
SMALL_VIA = (0.5, 0.3)


DRU = """(version 1)
# Thermal reliefs on the pours (pcbgen.py), against tombstoning: small parts with one end on a pour.
# On fine-pitch pads (ESP32 module, MSOP/SOT pins) the neighbours leave room for one spoke only: one
# spoke is still a relief, enough for a signal or decoupling pad.  Pads that carry a board's power
# connect solid (b.pcb["power_nets"], power_pads()), and the power nets' rules below ask for more.
(rule "one thermal spoke is enough"
	(constraint min_resolved_spokes 1))
"""

# b.pcb["power_nets"]: the power nets' DRC rules.  Their power pins (ICs, connectors, inductors, any pad
# of 2.5 mm² or more) connect solid, also as a rule, so a later edit in KiCad keeps them so; a pad of
# theirs that keeps a relief (a small part's, against tombstoning) keeps at least that net's spokes.
DRU_POWER_SOLID = """
(rule "power pins connect solid"
	(condition "A.Type == 'Pad' && A.Pad_Type == 'SMD' && ({nets}) && ({parts})")
	(constraint zone_connection solid))
"""
DRU_POWER_SPOKES = """
(rule "power nets: {n} spokes where relieved"
	(condition "A.Type == 'Pad' && ({nets})")
	(constraint min_resolved_spokes {n}))
"""
# power pins of these parts connect solid; everything else on a power net is a small part (R, C, D, Q,
# LED...) unless one of its pads is this big
POWER_PARTS = ("U", "J", "L")
POWER_PAD_MM2 = 2.5

# b.pcb["edge_parts"]: footprints that sit on the outline on purpose (side-entry connector mouths,
# USB-C receptacles, the ESP32 antenna edge).  Their own silkscreen outline crosses the board edge;
# the fab clips it, so only that pairing is let through (every other silkscreen check still runs).
DRU_EDGE = """
(rule "parts overhanging the outline"
	(layer "F.SilkS")
	(condition "({cond}) && B.Layer == 'Edge.Cuts'")
	(constraint silk_clearance (min -10mm)))
"""

# b.pcb["stackup"]: what the fab builds, written into the board so KiCad's Board Setup, impedance
# calculator and 3D view use it (pcbnew's Python API has no stackup bindings: the block is added to
# the saved file, and KiCad keeps it on every later load/save).  (layer, thickness mm[, material, εr])
STACKUPS = {
    # JLCPCB JLC04161H-7628, their standard 4-layer 1.6 mm: 1 oz outer, 0.5 oz inner copper
    "JLC04161H-7628": [("F.Cu", 0.035), ("prepreg", 0.2104, "7628", 4.4), ("In1.Cu", 0.0152),
                       ("core", 1.065, "FR4", 4.6), ("In2.Cu", 0.0152), ("prepreg", 0.2104, "7628", 4.4),
                       ("B.Cu", 0.035)],
    # JLCPCB JLC06161H-3313, a 6-layer 1.6 mm: 3313 prepreg under each outer layer (0.0994 mm), 0.55 mm
    # cores, 2116 in the middle; 1 oz outer, 0.5 oz inner (jlcpcb.com/impedance, 2026-10-20)
    "JLC06161H-3313": [("F.Cu", 0.035), ("prepreg", 0.0994, "3313", 4.1), ("In1.Cu", 0.0152),
                       ("core", 0.55, "FR4", 4.6), ("In2.Cu", 0.0152), ("prepreg", 0.1088, "2116", 4.16),
                       ("In3.Cu", 0.0152), ("core", 0.55, "FR4", 4.6), ("In4.Cu", 0.0152),
                       ("prepreg", 0.0994, "3313", 4.1), ("B.Cu", 0.035)],
    # standard 2-layer 1.6 mm FR4, 1 oz copper
    "2L-1.6": [("F.Cu", 0.035), ("core", 1.51, "FR4", 4.5), ("B.Cu", 0.035)],
}
COPPER = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")


def cu(name: str) -> int:
    """KiCad copper layer id from its name ("In3.Cu" → pcbnew.In3_Cu)."""
    return getattr(pcbnew, name.replace(".", "_"))


def copper_of(board) -> list[int]:
    """The board's copper layers, outer first."""
    return [cu(n) for n in COPPER if board.GetEnabledLayers().Contains(cu(n))]


def stackup_sexpr(name: str, finish: str) -> str:
    rows = [("F.SilkS", "Top Silk Screen", None), ("F.Paste", "Top Solder Paste", None),
            ("F.Mask", "Top Solder Mask", 0.01)]
    out = ["\t\t(stackup"]

    def layer(lname, ltype, thick=None, extra=""):
        out.append(f'\t\t\t(layer "{lname}"\n\t\t\t\t(type "{ltype}")'
                   + (f"\n\t\t\t\t(thickness {thick})" if thick is not None else "") + extra + "\n\t\t\t)")

    for lname, ltype, thick in rows:
        layer(lname, ltype, thick)
    n = 0
    for item in STACKUPS[name]:
        if item[0].endswith(".Cu"):
            layer(item[0], "copper", item[1])
        else:
            n += 1
            kind, thick, material, er = item
            layer(f"dielectric {n}", kind, thick,
                  f'\n\t\t\t\t(material "{material}")\n\t\t\t\t(epsilon_r {er})\n\t\t\t\t(loss_tangent 0.02)')
    for lname, ltype, thick in (("B.Mask", "Bottom Solder Mask", 0.01), ("B.Paste", "Bottom Solder Paste", None),
                                ("B.SilkS", "Bottom Silk Screen", None)):
        layer(lname, ltype, thick)
    out.append(f'\t\t\t(copper_finish "{finish}")\n\t\t\t(dielectric_constraints no)\n\t\t)')
    return "\n".join(out) + "\n"


def write_stackup(path: Path, cfg: dict):
    if "stackup" not in cfg:
        return
    text = path.read_text(encoding="utf-8")
    if "(stackup" in text:
        return
    i = text.index("\t(setup\n") + len("\t(setup\n")
    path.write_text(text[:i] + stackup_sexpr(cfg["stackup"], cfg.get("finish", "None")) + text[i:], encoding="utf-8")


def V(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def inset_poly(poly, d: float) -> list[list[tuple[float, float]]]:
    """Polygon (mm) shrunk by d mm; a narrow neck may split it, hence a list of outlines."""
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in poly:
        ps.Append(MM(x), MM(y))
    ps.Inflate(-MM(d), pcbnew.CORNER_STRATEGY_ALLOW_ACUTE_CORNERS, MM(0.01))
    mm = pcbnew.ToMM
    return [[(mm(ps.Outline(i).CPoint(k).x), mm(ps.Outline(i).CPoint(k).y)) for k in range(ps.Outline(i).PointCount())]
            for i in range(ps.OutlineCount())]


def load_fp(fpid: str) -> pcbnew.FOOTPRINT:
    lib, name = fpid.split(":", 1)
    path = PROJECT_FP_DIR if lib == "bench" else FP_DIR / f"{lib}.pretty"
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        raise FileNotFoundError(f"footprint {fpid} not found in {path}")
    fp.SetFPIDAsString(fpid) if hasattr(fp, "SetFPIDAsString") else None
    lib_id = pcbnew.LIB_ID(lib, name)
    fp.SetFPID(lib_id)
    return fp


class PcbBuilder:
    def __init__(self, b: Board, outdir: Path):
        self.b = b
        self.outdir = outdir
        self.path = outdir / f"{b.name}.kicad_pcb"
        self.board = pcbnew.NewBoard(str(self.path))
        self.nets: dict[str, pcbnew.NETINFO_ITEM] = {}
        cfg = b.pcb
        self.w, self.h = cfg["size"]
        self.layers = cfg.get("layers", 2)

    # -------------------------------------------------------------- setup
    def setup(self):
        bd = self.board
        bd.SetCopperLayerCount(self.layers)
        if self.layers >= 4:
            # b.pcb["inner"]: name and type of In1, In2 (In3, In4 on 6 layers).  "mixed" = a power layer
            # the router may still use for signals (its pours are added after routing, around the tracks)
            types = {"signal": pcbnew.LT_SIGNAL, "power": pcbnew.LT_POWER, "mixed": pcbnew.LT_MIXED}
            inner = self.b.pcb.get("inner", [("In1.GND", "power"), ("In2.SIG", "signal")])
            assert len(inner) == self.layers - 2, "b.pcb['inner'] names every inner layer"
            for layer, (name, kind) in zip([cu(f"In{i}.Cu") for i in range(1, self.layers - 1)], inner):
                bd.SetLayerName(layer, name)
                bd.SetLayerType(layer, types[kind])
        ds = bd.GetDesignSettings()
        # JLCPCB: 0.09 mm (4-layer) / 0.127 mm (2-layer); Freerouting necks down to 0.12 at fine-pitch pads
        # b.pcb["min_track"], ["min_clearance"], ["hole_clearance"]: a denser board's own floor (JLC multilayer:
        # 0.09 mm tracks and spaces, 0.2 mm from a via hole to a track)
        ds.m_TrackMinWidth = MM(self.b.pcb.get("min_track", 0.1 if self.layers >= 4 else 0.125))
        ds.m_MinClearance = MM(self.b.pcb.get("min_clearance", 0.127))
        ds.m_HoleClearance = MM(self.b.pcb.get("hole_clearance", 0.25))
        ds.m_ViasMinSize = MM(0.45)
        # JLC's no-extra-cost via is a 0.3 mm hole in a 0.4 mm (multilayer) / 0.45 mm pad: SMALL_VIA's ring
        ds.m_ViasMinAnnularWidth = MM((SMALL_VIA[0] - SMALL_VIA[1]) / 2)
        ds.m_MinThroughDrill = MM(SMALL_VIA[1])
        ds.m_CopperEdgeClearance = MM(0.3)
        ds.SetBoardThickness(MM(1.6))
        # custom DRC rules, next to the project (KiCad and kicad-cli read <board>.kicad_dru)
        dru = DRU
        if self.b.pcb.get("edge_parts"):
            dru += DRU_EDGE.format(cond=" || ".join(f"A.memberOfFootprint('{r}')" for r in self.b.pcb["edge_parts"]))
        dru += self.b.pcb.get("dru", "")           # the board's own rules (design.py)
        (self.outdir / f"{self.b.name}.kicad_dru").write_text(dru, encoding="utf-8")
        tb = bd.GetTitleBlock()
        tb.SetTitle(self.b.title)
        tb.SetRevision(self.b.rev)
        tb.SetCompany(self.b.company)
        for i, c in enumerate(self.b.comments[:9]):
            tb.SetComment(i, c)

    def net(self, name: str) -> pcbnew.NETINFO_ITEM:
        if name not in self.nets:
            ni = self.board.FindNet(name)
            if ni is None:
                ni = pcbnew.NETINFO_ITEM(self.board, name)
                self.board.Add(ni)
            self.nets[name] = ni
        return self.nets[name]

    # -------------------------------------------------------------- footprints
    def place_parts(self):
        for p in self.b.parts.values():
            if not p.on_board:
                continue
            fp = load_fp(p.footprint)
            fp.SetReference(p.ref)
            fp.SetValue(p.value)
            fp.SetPath(pcbnew.KIID_PATH(self.b.pcb_path(p)))
            fp.SetSheetname(p.sheet.name)
            fp.SetSheetfile(p.sheet.file)
            for k, v in {**p.fields, "Description": p.description, "Datasheet": p.datasheet}.items():
                fp.SetField(k, v)
                f = fp.GetField(k) if hasattr(fp, "GetField") else None
                if f is not None:
                    f.SetVisible(False)
                    f.SetLayer(pcbnew.F_Fab)
            fp.Value().SetVisible(False)
            set_model(fp, p.fields.get("MPN", ""))
            attrs = fp.GetAttributes()
            if not p.in_bom:
                attrs |= pcbnew.FP_EXCLUDE_FROM_BOM
            if p.dnp:
                attrs |= pcbnew.FP_DNP if hasattr(pcbnew, "FP_DNP") else 0
            fp.SetAttributes(attrs)
            self.board.Add(fp)
            hint = p.pcb
            x, y = hint.get("x", self.w / 2), hint.get("y", self.h / 2)
            fp.SetPosition(V(x, y))
            if hint.get("side", "top") == "bottom":
                fp.Flip(V(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetOrientationDegrees(hint.get("rot", 0))
            if "x" not in hint:
                print(f"note: {p.ref} has no placement hint, dropped at board centre")
            nets = p.pin_nets()
            pins = {pin.number: pin for pin in p.sym.pins}
            hand = p.fields.get("LCSC") in HAND_SOLDER_LCSC
            for pad in fp.Pads():
                num = pad.GetNumber()
                if hand or hint.get("relief"):
                    # soldered by hand, or forced (`relief` in its placement): thermal reliefs on every pad;
                    # power_pads() leaves these alone
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                    self.__dict__.setdefault("relief_refs", set()).add(p.ref)
                if num in nets:
                    pad.SetNet(self.net(self.b.pcb_net_name(nets[num])))
                elif num in pins:
                    # KiCad names every unconnected symbol pin's net like this ('/' in a pin name escaped)
                    name = pins[num].name.replace("/", "{slash}")
                    pad.SetNet(self.net(f"unconnected-({p.ref}-{name}-Pad{num})"))
            # references live on the fab layer: the silkscreen stays readable on a dense board
            ref = fp.Reference()
            ref.SetLayer(pcbnew.B_Fab if hint.get("side") == "bottom" else pcbnew.F_Fab)
            ref.SetTextSize(V(0.6, 0.6))
            ref.SetTextThickness(MM(0.09))

    # -------------------------------------------------------------- outline
    def outline(self):
        w, h = self.w, self.h
        r = self.b.pcb.get("corner_radius", 2.0)
        bd = self.board

        def line(x0, y0, x1, y1):
            s = pcbnew.PCB_SHAPE(bd)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1))
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
            bd.Add(s)

        def arc(cx, cy, sx, sy, ex, ey):
            s = pcbnew.PCB_SHAPE(bd)
            s.SetShape(pcbnew.SHAPE_T_ARC)
            mx = cx + (sx + ex - 2 * cx) / math.sqrt(2) / 2 * math.sqrt(2) / 1.0
            # midpoint on the 45° bisector
            ang_s = math.atan2(sy - cy, sx - cx); ang_e = math.atan2(ey - cy, ex - cx)
            da = (ang_e - ang_s)
            while da <= -math.pi: da += 2 * math.pi
            while da > math.pi: da -= 2 * math.pi
            am = ang_s + da / 2
            s.SetArcGeometry(V(sx, sy), V(cx + r * math.cos(am), cy + r * math.sin(am)), V(ex, ey))
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
            bd.Add(s)

        if self.b.pcb.get("outline"):
            self.outline_poly(self.b.pcb["outline"], line)
            return
        line(r, 0, w - r, 0); line(w, r, w, h - r); line(w - r, h, r, h); line(0, h - r, 0, r)
        arc(w - r, r, w - r, 0, w, r)
        arc(w - r, h - r, w, h - r, w - r, h)
        arc(r, h - r, r, h, 0, h - r)
        arc(r, r, 0, r, r, 0)

    def outline_poly(self, pts, line):
        """b.pcb["outline"]: [(x, y, r), ...] the board's corners in order, each rounded with radius r
        (0: sharp).  Edges may run at any angle; a concave corner (a notch's inner corner) takes the
        fillet the fab's router bit leaves anyway (≥ 0.5 mm)."""
        bd = self.board
        n = len(pts)

        def unit(dx, dy):
            d = math.hypot(dx, dy)
            return dx / d, dy / d

        ends = []          # per corner: where its fillet starts and ends
        for i, (x, y, r) in enumerate(pts):
            px, py, _ = pts[i - 1]
            nx, ny, _ = pts[(i + 1) % n]
            d1 = unit(x - px, y - py)
            d2 = unit(nx - x, ny - y)
            a = (x - r * d1[0], y - r * d1[1])
            b = (x + r * d2[0], y + r * d2[1])
            ends.append((a, b))
            if r > 0:
                c = (a[0] + r * d2[0], a[1] + r * d2[1])
                mx, my = unit(a[0] + b[0] - 2 * c[0], a[1] + b[1] - 2 * c[1])
                s = pcbnew.PCB_SHAPE(bd)
                s.SetShape(pcbnew.SHAPE_T_ARC)
                s.SetArcGeometry(V(*a), V(c[0] + r * mx, c[1] + r * my), V(*b))
                s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
                bd.Add(s)
        for i in range(n):
            (_, b), (a, _) = ends[i], ends[(i + 1) % n]
            line(b[0], b[1], a[0], a[1])

    # -------------------------------------------------------------- zones
    def zone(self, layer, net: str | None, poly, priority=0, keepout=False, name="", layers=None, tracks_only=False,
             connection="thermal", vias_only=False, fills_only=False, holes=None, clearance=None, min_width=None):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        if net:
            z.SetNet(self.net(self.b.pcb_net_name(net)))
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in poly:
            ol.Append(MM(x), MM(y))
        for hole in holes or []:              # areas the zone leaves out (e.g. a block with copper of its own)
            k = ol.NewHole()
            for (x, y) in hole:
                ol.Append(MM(x), MM(y), 0, k)
        z.SetAssignedPriority(priority)
        if name:
            z.SetZoneName(name)
        if keepout:
            z.SetIsRuleArea(True)
            # tracks_only: keep the router's tracks out but let vias and the GND pour in
            # (exported to the DSN as a wire_keepout); vias_only: keep vias out, tracks and pours in
            # (a via_keepout: e.g. a plane's narrow neck that a row of vias would cut); fills_only: keep the
            # pours out, tracks and vias in (not exported to the DSN: e.g. no copper under an inductor's body)
            z.SetDoNotAllowTracks(not (vias_only or fills_only))
            z.SetDoNotAllowVias(not (tracks_only or fills_only))
            z.SetDoNotAllowZoneFills(not (tracks_only or vias_only))
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowFootprints(False)
            ls = pcbnew.LSET()
            for l in layers or self.copper_layers():
                ls.AddLayer(l)
            z.SetLayerSet(ls)
        else:
            z.SetMinThickness(MM(0.2 if min_width is None else min_width))
            z.SetLocalClearance(MM(0.25 if clearance is None else clearance))
            # thermal reliefs: a pad on a pour heats up like the pad at its other end, so small
            # parts don't tombstone in reflow and hand-soldered pins can be soldered.  "solid" is
            # for the buck's hot-loop islands, where both ends of every part sit on copper anyway.
            if connection == "solid":
                z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            else:
                z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                z.SetThermalReliefGap(MM(0.3))
                z.SetThermalReliefSpokeWidth(MM(0.4))
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        self.board.Add(z)
        return z

    # -------------------------------------------------------------- power pads
    def power_net_names(self) -> dict[str, int]:
        """b.pcb["power_nets"] {net pattern: minimum spokes} → {board net name: minimum spokes}."""
        out = {}
        for name in (str(n) for n in self.board.GetNetsByName().keys()):
            for pat, n in self.b.pcb["power_nets"].items():
                if fnmatch.fnmatchcase(name.split("/")[-1], pat):
                    out[name] = n
                    break
        return out

    def power_rules(self) -> str:
        """The power nets' DRC rules (DRU_POWER_*) with the board's own net names: power pins solid, and
        each net's minimum spokes on a pad that keeps a relief."""
        power = self.power_net_names()
        cond = lambda names: " || ".join(f"A.NetName == '{x}'" for x in sorted(names))
        out = DRU_POWER_SOLID.format(nets=cond(power),
                                     parts=" || ".join(f"A.memberOfFootprint('{p}*')" for p in POWER_PARTS))
        for n in sorted({n for n in power.values() if n > 1}):
            out += DRU_POWER_SPOKES.format(n=n, nets=cond(x for x, m in power.items() if m == n))
        return out

    def power_pads(self) -> list[str]:
        """Pads that carry a board's power (b.pcb["power_nets"]: GND, the bus, the supplies, ≳ 0.5 A) must
        not hang on a thermal relief: one 0.4 mm spoke is a bottleneck (resistance, heat, voltage drop).
          * power pins of ICs, connectors and inductors (POWER_PARTS), and any pad of POWER_PAD_MM2 or more
            (bulk capacitors, TVSs, power FETs), connect solid;
          * a small part (R, C, D, Q, LED) gets the same connection on all its ends, against tombstoning:
            where one end sits on a solid pour, solid if every end sits on a pour (a decoupling capacitor
            between a power island and the GND pour: the lowest inductance too), reliefs if an end is a
            track; otherwise the pours' reliefs (`relief` in a placement forces reliefs);
          * through-hole pins keep their reliefs, so they can be soldered; a hand-soldered one gets 0.8 mm
            spokes.
        Run once the zones exist (it looks up the pour each pad sits in).  Returns a summary per net."""
        power = self.power_net_names()
        zones = [z for z in self.board.Zones() if not z.GetIsRuleArea()]

        def pour_mode(pad):
            hit = None
            for z in zones:
                if z.GetNetCode() != pad.GetNetCode():
                    continue
                for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if pad.IsOnLayer(layer) and z.IsOnLayer(layer) and z.Outline().Contains(pad.GetPosition()):
                        if hit is None or z.GetAssignedPriority() > hit.GetAssignedPriority():
                            hit = z
            return None if hit is None else hit.GetPadConnection()

        def mm2(pad):
            s = pad.GetSize(pcbnew.F_Cu)
            return pcbnew.ToMM(s.x) * pcbnew.ToMM(s.y)

        done = {}
        for fp in self.board.GetFootprints():
            ref = fp.GetReference()
            pads = [p for p in fp.Pads() if p.GetNetname() in power]
            if not pads:
                continue
            hand = _field(fp, "LCSC") in HAND_SOLDER_LCSC
            big = re.match(r"[A-Z]*", ref).group(0) in POWER_PARTS or any(mm2(p) >= POWER_PAD_MM2 for p in fp.Pads())
            for pad in pads:
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    if hand and hasattr(pad, "SetLocalThermalSpokeWidthOverride"):
                        pad.SetLocalThermalSpokeWidthOverride(MM(0.8))
                elif big and pour_mode(pad) is not None and \
                        pad.GetLocalZoneConnection() != pcbnew.ZONE_CONNECTION_FULL:
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
                    done.setdefault(pad.GetNetname().split("/")[-1], []).append(f"{ref}.{pad.GetNumber()}")
            if big or ref in getattr(self, "relief_refs", ()):
                continue
            # a small part: the same connection on every end
            modes = []                      # (pad, its connection: local, else its pour's; None off a pour)
            for pad in fp.Pads():
                if pad.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_PTH):
                    continue
                local = pad.GetLocalZoneConnection()
                modes.append((pad, pour_mode(pad) if local == pcbnew.ZONE_CONNECTION_INHERITED else local))
            kinds = {m for _, m in modes}
            if pcbnew.ZONE_CONNECTION_FULL in kinds and len(kinds) > 1:
                both = None not in kinds
                to = pcbnew.ZONE_CONNECTION_FULL if both else pcbnew.ZONE_CONNECTION_THERMAL
                for pad, mode in modes:
                    if mode is not None:
                        pad.SetLocalZoneConnection(to)
                done.setdefault("(both ends solid)" if both else "(both ends relieved)", []).append(ref)
        return [f"power pads: {n} {' '.join(sorted(set(v)))}" for n, v in sorted(done.items())]

    def deferred_layers(self) -> set[str]:
        d = self.b.pcb.get("defer_pours", True)
        if d is True:
            return {"F.Cu", "B.Cu"}
        return set(d or [])

    def copper_layers(self):
        return [pcbnew.F_Cu] + [cu(f"In{i}.Cu") for i in range(1, self.layers - 1)] + [pcbnew.B_Cu]

    def zones(self, which: str = "all"):
        """which = "routing" (what the router sees: every zone except the deferred pours,
        plus keep-outs), "deferred" (the pours added once the SES is imported) or "all".

        b.pcb["defer_pours"]: True (both outer layers), False (none) or a list of layer names.
        A deferred outer pour forces Freerouting to give every SMD GND pad on that layer its
        own via to the plane, instead of trusting a pour that KiCad may later fill in pieces."""
        m = 0.4
        full = [(m, m), (self.w - m, m), (self.w - m, self.h - m), (m, self.h - m)]
        if self.b.pcb.get("outline"):
            full = inset_poly([(x, y) for x, y, _ in self.b.pcb["outline"]], m)[0]
        late = self.deferred_layers()
        have = {(pcbnew.LayerName(z.GetLayer()) if hasattr(pcbnew, "LayerName") else self.board.GetStandardLayerName(z.GetLayer()),
                 z.GetNetname()) for z in self.board.Zones() if not z.GetIsRuleArea()}
        for spec in self.b.pcb.get("zones", []):
            deferred = spec.get("defer", spec["layer"] in late)
            if (which == "routing" and deferred) or (which == "deferred" and not deferred):
                continue
            if which == "deferred" and (spec["layer"], self.b.pcb_net_name(spec["net"])) in have:
                continue          # re-importing a session onto a board that already has its pours
            layer = cu(spec["layer"])
            self.zone(layer, spec["net"], spec.get("poly", full), priority=spec.get("priority", 0),
                      name=spec.get("name", ""), connection=spec.get("connection", "thermal"),
                      holes=spec.get("holes"), clearance=spec.get("clearance"), min_width=spec.get("min_width"))
            if spec.get("exclusive") and which != "deferred":
                # Freerouting doesn't treat a copper area on a signal layer as an obstacle: other nets'
                # tracks would cross the pour and cut it in pieces.  Keep tracks out of its core; the
                # margin (spec["exclusive"], mm) still lets the router reach the pour with its own net.
                for i, core in enumerate(inset_poly(spec["poly"], spec["exclusive"])):
                    self.zone(pcbnew.F_Cu, None, core, keepout=True, name=f"core:{spec.get('name', spec['net'])}:{i}",
                              layers=[layer], tracks_only=True)
        if which != "deferred":
            for ko in self.b.pcb.get("keepouts", []):
                layers = [getattr(pcbnew, n.replace(".", "_")) for n in ko["layers"]] if "layers" in ko else None
                self.zone(pcbnew.F_Cu, None, ko["poly"], keepout=True, name=ko.get("name", "keepout"),
                          layers=layers, tracks_only=ko.get("tracks_only", False),
                          vias_only=ko.get("vias_only", False), fills_only=ko.get("fills_only", False))
            for ref, num in self.b.pcb.get("fanout", []):
                _, _, poly = fanout_geometry(self.board, ref, num)
                self.zone(pcbnew.F_Cu, None, poly, keepout=True, name=f"fanout:{ref}.{num}")

    # -------------------------------------------------------------- fixed vias
    def vias(self):
        """b.pcb["vias"]: [(net, x, y)] placed by hand before routing (e.g. the GND vias tying the
        buck's top-side GND island to the inner plane, right next to the capacitors' GND pads)."""
        for net, x, y, *size in self.b.pcb.get("vias", []):
            d, drill = size or (0.6, 0.3)
            v = pcbnew.PCB_VIA(self.board)
            v.SetPosition(V(x, y))
            v.SetWidth(MM(d))
            v.SetDrill(MM(drill))
            v.SetNet(self.net(self.b.pcb_net_name(net)))
            if hasattr(v, "SetIsFree"):
                v.SetIsFree(True)       # tied to the copper through zones only: keep its net
            v.SetLocked(True)           # protected wiring for Freerouting
            self.board.Add(v)

    # -------------------------------------------------------------- fixed tracks
    def tracks(self):
        """b.pcb["tracks"]: [(net, layer, width mm, [(x, y), ...])] drawn before routing and locked,
        so the DSN hands them to Freerouting as protected wiring it routes around (e.g. the USB
        High-Speed pairs, which need coupling and length matching the router can't do)."""
        for net, layer, width, pts in self.b.pcb.get("tracks", []):
            for a, c in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(self.board)
                t.SetStart(V(*a))
                t.SetEnd(V(*c))
                t.SetWidth(MM(width))
                t.SetLayer(cu(layer))
                t.SetNet(self.net(self.b.pcb_net_name(net)))
                t.SetLocked(True)
                self.board.Add(t)

    # -------------------------------------------------------------- texts
    def texts(self):
        for t in self.b.pcb.get("texts", []):
            tx = pcbnew.PCB_TEXT(self.board)
            tx.SetText(t["text"])
            tx.SetPosition(V(t["x"], t["y"]))
            tx.SetLayer(pcbnew.F_SilkS if t.get("layer", "F.SilkS") == "F.SilkS" else pcbnew.B_SilkS)
            sz = t.get("size", 1.0)
            tx.SetTextSize(V(sz, sz))
            tx.SetTextThickness(MM(sz * 0.15))
            if t.get("layer") == "B.SilkS":
                tx.SetMirrored(True)
            tx.SetTextAngleDegrees(t.get("rot", 0))
            self.board.Add(tx)

    # -------------------------------------------------------------- routing
    def autoroute(self, passes: int = 40):
        dsn = self.outdir / "build" / f"{self.b.name}.dsn"
        ses = self.outdir / "build" / f"{self.b.name}.ses"
        dsn.parent.mkdir(parents=True, exist_ok=True)
        if not pcbnew.ExportSpecctraDSN(self.board, str(dsn)):
            raise RuntimeError("DSN export failed")
        cmd = [FREEROUTING, "-de", str(dsn), "-do", str(ses), "-mp", str(passes)]
        print("running:", " ".join(cmd))
        log = self.outdir / "build" / "freerouting.log"
        with open(log, "w") as fh:
            subprocess.run(cmd, check=True, stdout=fh, stderr=subprocess.STDOUT, timeout=3600)
        if not pcbnew.ImportSpecctraSES(self.board, str(ses)):
            raise RuntimeError("SES import failed")

    def fill(self):
        filler = pcbnew.ZONE_FILLER(self.board)
        filler.Fill(self.board.Zones())

    def save(self):
        self.board.Save(str(self.path)) if hasattr(self.board, "Save") else pcbnew.SaveBoard(str(self.path), self.board)

    def build(self, route: bool = True, defer_pours: bool = False):
        self.setup()
        self.place_parts()
        self.outline()
        self.texts()
        self.vias()
        self.tracks()
        self.zones("routing" if defer_pours else "all")
        if self.b.pcb.get("power_nets"):
            for line in self.power_pads():
                print(line)
            # the power nets' DRC rules need the board's net names: added once the parts are placed
            dru = self.outdir / f"{self.b.name}.kicad_dru"
            dru.write_text(dru.read_text(encoding="utf-8") + self.power_rules(), encoding="utf-8")
        if self.b.pcb.get("fanout_nets"):
            specs = {self.b.pcb_net_name(k): v for k, v in self.b.pcb["fanout_nets"].items()}
            islands = [(self.b.pcb_net_name(z["net"]), z["poly"]) for z in self.b.pcb.get("zones", [])
                       if z["layer"] in ("F.Cu", "B.Cu") and "poly" in z]
            for net, n, todo in fanout_pads(self.board, specs, islands):
                print(f"fan-out {net}: {n} of {todo} pads")
        if self.b.pcb.get("edge_fence"):
            f = self.b.pcb["edge_fence"]
            outline = ([(x, y) for x, y, _ in self.b.pcb["outline"]] if self.b.pcb.get("outline")
                       else [(0, 0), (self.w, 0), (self.w, self.h), (0, self.h)])
            n, want = edge_fence(self.board, outline, self.net(self.b.pcb_net_name("GND")), f["pitch"], f["inset"])
            print(f"edge fence: {n} of {want} GND vias")
        if route:
            self.autoroute(self.b.pcb.get("passes", 40))
        # zones are filled by `kicad-cli pcb drc --refill-zones --save-board` (KiCad's own filler)
        pcbnew.SaveBoard(str(self.path), self.board)
        write_stackup(self.path, self.b.pcb)
        write_via_rules(self.path.with_suffix(".kicad_pro"))
        return self.path


# the project's own 3D models (electronics/lib/3dmodels), relative to each board's project folder
MODEL_PATH = "${KIPRJMOD}/../lib/3dmodels/"


def set_model(fp, mpn: str) -> bool:
    """Give a footprint the 3D model catalog.MODELS lists for its part (vendor models KiCad's
    library lacks, kept in the repo), in place of the footprint's own.  The path is relative to the
    board's project, so it resolves on any machine and in CI."""
    if mpn not in MODELS:
        return False
    file, offset, rot = MODELS[mpn]
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = file if file.startswith("${") else MODEL_PATH + file      # or one of KiCad's own
    m.m_Offset = pcbnew.VECTOR3D(*offset)
    m.m_Rotation = pcbnew.VECTOR3D(*rot)
    m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
    models = fp.Models()
    models.clear()
    models.push_back(m)
    return True


def _field(fp, name: str) -> str:
    for f in fp.GetFields():
        if f.GetName() == name:
            return f.GetText()
    return ""


def apply_models(path: Path) -> int:
    """set_model() on every footprint of a saved board (for boards placed before a model was added)."""
    board = pcbnew.LoadBoard(str(path))
    n = sum(set_model(fp, _field(fp, "MPN")) for fp in board.GetFootprints())
    if n:
        pcbnew.SaveBoard(str(path), board)
    return n


def write_via_rules(pro: Path):
    """KiCad's DRC reads the board's minimum drill and annular ring from <board>.kicad_pro, which
    pcbnew.SaveBoard leaves alone: write SMALL_VIA's limits there, so a via under JLC's no-extra-cost
    size is a DRC error."""
    import json
    data = json.loads(pro.read_text(encoding="utf-8"))
    rules = data.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules["min_through_hole_diameter"] = SMALL_VIA[1]
    rules["min_via_annular_width"] = round((SMALL_VIA[0] - SMALL_VIA[1]) / 2, 4)
    pro.write_text(json.dumps(data, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")


def _zone_clearance(z) -> int:
    c = z.GetLocalClearance()
    return c if isinstance(c, int) else MM(0.25)


def plane_areas(board, log=print) -> dict[int, list[list[tuple[float, float]]]]:
    """What the DSN export should say of each copper zone it writes as a plane (board.Zones(): copper, not
    rule areas, in its order), where KiCad's outline would mislead Freerouting:
      * a zone another net's zone cuts: its outline less every zone of another net that wins over it on its
        layer (KiCad's fill order: the higher priority, then KiCad's own tie-break), grown by the clearance
        between them, fractured (no holes).  Overlapping outlines put a via of either net "in" both;
      * an area of a net that nothing fixed (a via, a through-hole pad, a drawn track) ties to the net's main
        area (its largest, on a plane layer if it has one): left out.  Freerouting takes an item that touches
        any area of its net as connected to the plane and never tries to route it: an island fed by nothing hid
        its pads' open links (KiCad's DRC found them, Freerouting's report didn't).
    {index: outlines in mm, [] to leave the zone out}; zones not listed stay as KiCad wrote them."""
    zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.IsOnCopperLayer()]
    polys, cut = [], set()
    for i, z in enumerate(zones):
        ps = z.Outline().CloneDropTriangulation()
        for j, o in enumerate(zones):
            if i == j or o.GetNetCode() == z.GetNetCode() or o.GetLayer() != z.GetLayer() or not o.HigherPriority(z):
                continue
            hole = o.Outline().CloneDropTriangulation()
            hole.Inflate(max(_zone_clearance(z), _zone_clearance(o)), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS,
                         MM(0.01))
            before = ps.Area()
            ps.BooleanSubtract(hole)
            if ps.Area() < before:
                cut.add(i)
        ps.Fracture()
        polys.append(ps)
    # each net's areas (zone, outline) and fixed copper, joined where they touch: union-find
    areas = [(i, k) for i, ps in enumerate(polys) for k in range(ps.OutlineCount())]
    parent = list(range(len(areas)))

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(x, y):
        parent[root(x)] = root(y)

    def under(net, pt, layer=None):
        """The areas of `net` at `pt` (on `layer`, or on any layer for a drill)."""
        return [ai for ai, (i, k) in enumerate(areas) if zones[i].GetNetCode() == net
                and (layer is None or zones[i].GetLayer() == layer) and polys[i].Outline(k).PointInside(pt)]

    def node(hits=()):
        n = len(parent)
        parent.append(n)
        for h in hits:
            join(n, h)
        return n
    # a drill (via, through-hole pad) joins every area of its net it sits in; an SMD pad, those on its layer
    drills, pads = {}, []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            q = t.GetPosition()
            drills[(t.GetNetCode(), q.x, q.y)] = node(under(t.GetNetCode(), q))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            q, n = pad.GetPosition(), pad.GetNetCode()
            if pad.GetDrillSize().x > 0:
                drills[(n, q.x, q.y)] = node(under(n, q))
            else:
                layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
                pads.append((n, layer, pad, node(under(n, q, layer))))
    # a drawn track joins what its ends touch: a drill, a pad, an area on its layer, another track's end
    ends = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        n, layer, me = t.GetNetCode(), t.GetLayer(), node()
        for e in (t.GetStart(), t.GetEnd()):
            for h in under(n, e, layer):
                join(me, h)
            if (n, e.x, e.y) in drills:
                join(me, drills[(n, e.x, e.y)])
            for pn, pl, pad, v in pads:
                if pn == n and pl == layer and pad.HitTest(e):
                    join(me, v)
            key = (n, layer, e.x, e.y)
            if key in ends:
                join(me, ends[key])
            ends[key] = me
    plane_layers = {zones[i].GetLayer() for i, _ in areas if board.GetLayerType(zones[i].GetLayer()) == pcbnew.LT_POWER}
    out = {}
    for n in sorted({zones[i].GetNetCode() for i, _ in areas}):
        mine = [ai for ai, (i, k) in enumerate(areas) if zones[i].GetNetCode() == n]
        main = root(max(mine, key=lambda ai: (zones[areas[ai][0]].GetLayer() in plane_layers,
                                              abs(polys[areas[ai][0]].Outline(areas[ai][1]).Area()))))
        for ai in mine:
            if root(ai) != main:
                i, k = areas[ai]
                log(f"plane {zones[i].GetNetname()} on {board.GetLayerName(zones[i].GetLayer())}: an area of "
                    f"{abs(polys[i].Outline(k).Area()) / 1e12:.0f} mm² that nothing fixed ties to the rest, left out "
                    "(its pads are routed like any other)")
                out.setdefault(i, list(range(polys[i].OutlineCount()))).remove(k)
    for i in sorted(cut | set(out)):
        keep = out.get(i, range(polys[i].OutlineCount()))
        out[i] = [[(pcbnew.ToMM(polys[i].Outline(k).CPoint(m).x), pcbnew.ToMM(polys[i].Outline(k).CPoint(m).y))
                   for m in range(polys[i].Outline(k).PointCount())] for k in keep]
        if i in cut:
            log(f"plane {zones[i].GetNetname()} on {board.GetLayerName(zones[i].GetLayer())}: cut by the zones over it")
    return out


def export_dsn(b: Board, outdir: Path) -> Path:
    import dsn as dsnlib
    path = outdir / f"{b.name}.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    dsn = outdir / "build" / f"{b.name}.dsn"
    dsn.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise RuntimeError("DSN export failed")
    # Freerouting rounds its geometry and sometimes lands a hair under the clearance (0.1487 for
    # 0.15 mm): give it 2 µm of margin over what KiCad's DRC checks
    import re
    text = dsn.read_text(encoding="utf-8")
    text = re.sub(r"\(clearance (\d+(?:\.\d+)?)\)", lambda m: f"(clearance {float(m.group(1)) + 2:g})", text)
    # the planes as KiCad's fill can reach them, not as their outlines overlap (plane_areas)
    # (PCBGEN_DSN_PLANES=kicad keeps KiCad's outlines, to compare)
    entries = dsnlib.planes(text)
    zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.IsOnCopperLayer()]
    if os.environ.get("PCBGEN_DSN_PLANES") == "kicad":
        print("planes: KiCad's outlines (PCBGEN_DSN_PLANES=kicad)")
    elif len(entries) == len(zones) and all(z.GetNetname() == net.strip('"') for z, (_, _, net, _) in zip(zones, entries)):
        text = dsnlib.replace_planes(text, plane_areas(board))
    else:
        print(f"planes: {len(entries)} in the DSN for {len(zones)} zones: left as exported")
    # no via of Freerouting's on an SMD pad (b.pcb["via_at_smd"]: True allows it): an open via there drains a
    # small part's joint; the exposed pads' vias are drawn
    if not b.pcb.get("via_at_smd"):
        text = dsnlib.no_via_at_smd(text)
    # in one order whatever order KiCad wrote it in: the same design routes the same way every time
    dsn.write_text(dsnlib.canonical(text), encoding="utf-8")
    print("exported", dsn)
    return dsn


def import_session(b: Board, outdir: Path, routed: Path | None = None) -> Path:
    """Import Freerouting's session, then add the outer-layer copper pours (they were
    left out of the DSN so the router had to connect every pad with real copper).
    `routed`: a board another router routed from this one (tools/route_farm.py), taken instead of the
    session, with the same steps after it."""
    path = outdir / f"{b.name}.kicad_pcb"
    ses = outdir / "build" / f"{b.name}.ses"
    # the fan-out reservations and the exclusive pours' cores have done their job (they kept the router's
    # tracks off): drop them from the file before loading it, so a drawn track of the pour's own net may
    # cross its core (BOARD.Remove() on a zone leaves SWIG unable to type the board's footprints afterwards)
    path.write_text(_strip_zones(_strip_zones((routed or path).read_text(encoding="utf-8"), "fanout:"), "core:"),
                    encoding="utf-8")
    board = pcbnew.LoadBoard(str(path))
    if routed is None and not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise RuntimeError("SES import failed")
    pb = PcbBuilder.__new__(PcbBuilder)
    pb.b, pb.outdir, pb.path, pb.board = b, outdir, path, board
    pb.w, pb.h = b.pcb["size"]
    pb.layers = b.pcb.get("layers", 2)
    pb.nets = {}
    if b.pcb.get("tidy", {}) is not None:
        board.Save(str(path))
        tidy_board(b, path)
        board = pcbnew.LoadBoard(str(path))
        pb.board = board
    if b.pcb.get("match"):
        m = b.pcb["match"]
        for line in tune_pairs(board, [(b.pcb_net_name(p), b.pcb_net_name(n)) for p, n in m["pairs"]],
                               m.get("tol", 1.0)):
            print(line)
    pb.zones("deferred")
    for ref, num in b.pcb.get("fanout", []):
        pad, via_at, _ = fanout_geometry(board, ref, num)
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pad.GetPosition())
        t.SetEnd(via_at)
        t.SetWidth(MM(0.3))
        t.SetLayer(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
        t.SetNet(pad.GetNet())
        board.Add(t)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(via_at)
        v.SetWidth(MM(0.6))
        v.SetDrill(MM(0.3))
        v.SetNet(pad.GetNet())
        board.Add(v)
    board.GetDesignSettings().m_TrackMinWidth = MM(b.pcb.get("min_track", 0.1 if pb.layers >= 4 else 0.125))
    gnd = pb.net(b.pcb_net_name("GND"))
    if b.pcb.get("stitch"):
        n = stitch_gnd(board, gnd, b.pcb["stitch"])
        print(f"stitching: {n} GND vias")
    pcbnew.SaveBoard(str(path), board)
    # without outer GND pours every SMD GND pad needs its own way down to the plane: Freerouting
    # fans most of them out, the ones it leaves get a short track to a GND via (KiCad's DRC says which)
    for _ in range(2):
        spots = unconnected_pads(path)
        board = pcbnew.LoadBoard(str(path))
        gnd = board.FindNet(b.pcb_net_name("GND"))
        # a pad whose pour fragment has no via is reported against the zone, not the pad
        spots = sorted(set(spots) | set(loose_gnd_pads(board, gnd)))
        if not spots:
            break
        n = connect_gnd_pads(board, gnd, spots)
        print(f"gnd: {n} of {len(spots)} isolated GND pads tied to the plane")
        pcbnew.SaveBoard(str(path), board)
    # pads of the power-plane nets (b.pcb["plane_nets"]: net → layer) the router left without a way
    # down to their plane get a short track to a via landing inside that net's fill
    for name, layer in b.pcb.get("plane_nets", {}).items():
        netname = b.pcb_net_name(name)
        for _ in range(2):
            spots = unconnected_pads(path, netname)
            if not spots:
                break
            board = pcbnew.LoadBoard(str(path))
            n = connect_gnd_pads(board, board.FindNet(netname), spots, via_d=0.6, drill=0.3, width_mm=0.4,
                                 plane=getattr(pcbnew, layer.replace(".", "_")))
            print(f"plane {name}: {n} of {len(spots)} pads tied to {layer}")
            pcbnew.SaveBoard(str(path), board)
    drop_passthrough_vias(path)
    drop_pad_dots(path)
    print("imported", routed or ses)
    return path


def drop_pad_dots(path: Path):
    """Freerouting leaves a dot on some pads it reached: a track a few µm long, at its net's width, inside
    a pad of its own net.  Remove them (a board of its own: SWIG loses its types after a Remove)."""
    board = pcbnew.LoadBoard(str(path))
    pads = [(p.GetNetCode(), p) for fp in board.GetFootprints() for p in fp.Pads()]
    dots = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLength() < MM(0.01)
            and any(n == t.GetNetCode() and p.IsOnLayer(t.GetLayer()) and p.HitTest(t.GetStart())
                    and p.HitTest(t.GetEnd()) for n, p in pads)]
    for t in dots:
        board.Remove(t)
    if dots:
        pcbnew.SaveBoard(str(path), board)
        print(f"dropped {len(dots)} dots Freerouting left on pads")


def drop_passthrough_vias(path: Path) -> int:
    """Freerouting sometimes leaves a via where its route stays on one layer (KiCad's DRC: "via
    connected on only one layer").  Remove those whose tracks all sit on a single layer and meet at
    the via: the route stays connected through the tracks."""
    import json
    import tempfile
    rpt = Path(tempfile.mkstemp(suffix=".json")[1])
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--refill-zones", "-o", str(rpt), str(path)],
                   check=False, capture_output=True)
    data = json.loads(rpt.read_text(encoding="utf-8"))
    uuids = {it["uuid"] for v in data.get("violations", []) if v["type"] == "via_dangling" for it in v["items"]}
    if not uuids:
        return 0
    board = pcbnew.LoadBoard(str(path))
    # one snapshot of the board, everything worked out on it, the removals all at the end: after a few
    # Remove() calls SWIG can no longer list the board's tracks
    items = list(board.GetTracks())
    gone, stubs = [], []
    for v in [t for t in items if t.GetClass() == "PCB_VIA" and t.m_Uuid.AsString() in uuids]:
        p = v.GetPosition()
        ends = [t.GetLayer() for t in items if t.GetClass() != "PCB_VIA"
                and t.GetNetCode() == v.GetNetCode() and p in (t.GetStart(), t.GetEnd())]
        if not v.IsLocked() and len(ends) >= 2 and len(set(ends)) == 1:
            gone.append(v)
        elif not v.IsLocked() and len(ends) <= 1:
            stubs.append(v)          # the end of a dead branch: the via and the branch go
    zoned = {z.GetNetCode() for z in board.Zones()}
    nets = {v.GetNetCode() for v in stubs} - zoned       # a free track end in a pour of its net is connected
    removed = {id(v) for v in gone + stubs}
    pads = {}
    for pad in board.GetPads():
        pads.setdefault(pad.GetNetCode(), []).append(pad)
    hits: dict = {}

    def on_pad(net, pt):
        if (net, pt) not in hits:
            hits[(net, pt)] = any(q.HitTest(pcbnew.VECTOR2I(*pt)) for q in pads.get(net, ()))
        return hits[(net, pt)]
    live = [t for t in items if t.GetClass() == "PCB_TRACK" and t.GetNetCode() in nets]
    ends = {id(t): ((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)) for t in live}
    vias = {(v.GetNetCode(), v.GetPosition().x, v.GetPosition().y) for v in items
            if v.GetClass() == "PCB_VIA" and id(v) not in removed}
    pruned = []
    while True:
        free = []
        for t in live:
            net = t.GetNetCode()

            def joined(pt, me=t, net=net):
                return (any(o is not me and o.GetNetCode() == net and pt in ends[id(o)] for o in live)
                        or (net, *pt) in vias or on_pad(net, pt))
            if not t.IsLocked() and not all(joined(pt) for pt in ends[id(t)]):
                free.append(t)
        if not free:
            break
        dead = {id(t) for t in free}
        live = [t for t in live if id(t) not in dead]
        pruned += free
    for o in gone + stubs + pruned:
        board.Remove(o)
    if gone or stubs:
        pcbnew.SaveBoard(str(path), board)
    pruned = len(pruned)
    if gone or stubs:
        print(f"vias: dropped {len(gone)} pass-through via(s), {len(stubs)} dead-end via(s) and {pruned} stub track(s)")
    return len(gone) + len(stubs)


def unconnected_pads(path: Path, net: str = "GND") -> list[tuple[float, float]]:
    """Positions (mm) of the pads of `net` KiCad's DRC reports as unconnected (zones refilled)."""
    import json
    import tempfile
    rpt = Path(tempfile.mkstemp(suffix=".json")[1])
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--refill-zones", "-o", str(rpt), str(path)],
                   check=False, capture_output=True)
    data = json.loads(rpt.read_text(encoding="utf-8"))
    out = []
    for v in data.get("unconnected_items", []):
        for it in v.get("items", []):
            d = it.get("description", "")
            if d.startswith("Pad") and f"[{net}]" in d:
                out.append((it["pos"]["x"], it["pos"]["y"]))
    return sorted(set(out))


def loose_gnd_pads(board, gnd) -> list[tuple[float, float]]:
    """Positions (mm) of the SMD GND pads sitting in an outer-layer GND fill fragment that holds no
    GND via or through-hole pad (zones refilled): KiCad's DRC reports those as an unconnected
    zone, without saying which pad."""
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    code = gnd.GetNetCode()
    anchors = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == code]
    anchors += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads()
                if p.GetNetCode() == code and p.GetDrillSize().x > 0]
    # a GND track leaving the fragment ties it to the rest (e.g. the one connect_gnd_pads just drew)
    anchors += [e for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetCode() == code
                for e in (t.GetStart(), t.GetEnd())]
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetCode() != code:
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(layer):
                continue
            polys = z.GetFilledPolysList(layer)
            for i in range(polys.OutlineCount()):
                if any(polys.Contains(a, i) for a in anchors):
                    continue
                out += [(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))
                        for fp in board.GetFootprints() for p in fp.Pads()
                        if p.GetNetCode() == code and p.GetDrillSize().x == 0 and p.IsOnLayer(layer)
                        and polys.Contains(p.GetPosition(), i)]
    return out


def connect_gnd_pads(board, gnd, spots_mm, via_d=SMALL_VIA[0], drill=SMALL_VIA[1], width_mm=0.25, plane=None) -> int:
    """Tie each listed (isolated) SMD pad of net `gnd` to its plane: the shortest straight track that
    reaches a via / through-hole pad of the net, or a spot where a small via fits (on every layer).
    With `plane` (the layer of a power net's plane), vias only count where they land inside that
    net's fill on it."""
    code = gnd.GetNetCode()
    fill = None
    if plane is not None:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        fill = pcbnew.SHAPE_POLY_SET()
        for z in board.Zones():
            if not z.GetIsRuleArea() and z.GetNetCode() == code and z.IsOnLayer(plane):
                fill.Append(z.GetFilledPolysList(plane))

    def on_plane(e, r=0):
        if fill is None:
            return True
        return all(fill.Contains(pcbnew.VECTOR2I(int(e.x + r * math.cos(a)), int(e.y + r * math.sin(a))))
                   for a in [k * math.pi / 4 for k in range(8)] + [0]) if r else fill.Contains(e)
    err = MM(0.005)
    layers = copper_of(board)
    clr = MM(0.2)

    def obstacles_on(layer):
        sh = pcbnew.SHAPE_POLY_SET()
        for t in board.GetTracks():
            if t.GetNetCode() != code and t.IsOnLayer(layer):
                t.TransformShapeToPolygon(sh, layer, clr, err, pcbnew.ERROR_OUTSIDE)
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetNetCode() != code and p.IsOnLayer(layer):
                    p.TransformShapeToPolygon(sh, layer, clr, err, pcbnew.ERROR_OUTSIDE)
        for z in board.Zones():
            if z.GetIsRuleArea() and z.IsOnLayer(layer) and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                sh.Append(z.Outline())
        return sh

    obst = {l: obstacles_on(l) for l in layers}
    # foreign-net zone fills on the inner layers: a via may cross them (KiCad refills around it), so
    # only tracks, pads and keep-outs count there; holes must keep their distance everywhere
    holes = []
    anchors = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            holes.append((t.GetPosition(), t.GetDrillValue()))
            if t.GetNetCode() == code and on_plane(t.GetPosition()):
                anchors.append((t.GetPosition(), MM(0.2)))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0:
                holes.append((p.GetPosition(), max(p.GetDrillSize().x, p.GetDrillSize().y)))
                if p.GetNetCode() == code:
                    anchors.append((p.GetPosition(), min(p.GetSize().x, p.GetSize().y) // 2))
    edge = board.GetBoardEdgesBoundingBox()
    edge.Inflate(-MM(0.6))
    smd = pcbnew.SHAPE_POLY_SET()             # no via on an SMD pad, its own net's included (fanout_pads)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetDrillSize().x == 0:
                for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if p.IsOnLayer(l):
                        p.TransformShapeToPolygon(smd, l, MM(0.05), err, pcbnew.ERROR_OUTSIDE)

    def via_fits(e):
        if not edge.Contains(e):
            return False
        for q, d in holes:
            if math.hypot(e.x - q.x, e.y - q.y) < d / 2 + MM(drill) / 2 + MM(0.35):
                return False
        if not on_plane(e, MM(via_d) / 2 + MM(0.1)):
            return False
        if smd.Collide(e, MM(via_d) // 2):
            return False
        return not any(obst[l].Collide(e, MM(via_d) // 2) for l in layers)

    pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code and p.GetDrillSize().x == 0]
    n = 0
    for x, y in spots_mm:
        pad = min(pads, key=lambda p: (p.GetPosition().x - MM(x)) ** 2 + (p.GetPosition().y - MM(y)) ** 2)
        layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        a = pad.GetPosition()
        half = MM(width_mm) // 2
        best = None
        for k in range(48):
            ang = k * math.pi / 24
            dx, dy = math.cos(ang), math.sin(ang)
            for step in range(2, 41):
                L = MM(step * 0.1)
                if best and L >= best[0]:
                    break
                e = pcbnew.VECTOR2I(int(a.x + dx * L), int(a.y + dy * L))
                if obst[layer].Collide(pcbnew.SEG(a, e), half):
                    break
                hit = next((q for q, r in anchors if math.hypot(e.x - q.x, e.y - q.y) < r), None)
                if hit is not None:
                    best = (L, e, False)
                    break
                if via_fits(e):
                    best = (L, e, True)
                    break
        if not best:
            print(f"{gnd.GetNetname()}: pad {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()} "
                  f"at ({x:.2f}, {y:.2f}) still isolated")
            continue
        _, e, via = best
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a)
        t.SetEnd(e)
        t.SetWidth(MM(width_mm))
        t.SetLayer(layer)
        t.SetNet(gnd)
        board.Add(t)
        if via:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(e)
            v.SetWidth(MM(via_d))
            v.SetDrill(MM(drill))
            v.SetNet(gnd)
            board.Add(v)
            holes.append((e, MM(drill)))
            anchors.append((e, MM(via_d) // 2))
        n += 1
    return n


# a supply pad over another net's area of a split plane: how far its fan-out may go to reach its own (mm)
REMOTE_FEED_MM = 8.0


def _feed_path(a, layer, obst, via_fits, half, inside, max_mm=REMOTE_FEED_MM, step_mm=0.1):
    """The shortest track (45° steps on a 0.1 mm grid, a little extra for each bend) from pad centre `a`, on
    `layer`, clear of `obst[layer]` (other nets' copper, grown by the clearance), to a spot where
    `via_fits`, tried only where `inside` (the net's own area); at most `max_mm` long.  Its corners, or None."""
    import heapq
    st = MM(step_mm)
    moves = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    free, goal = {}, {}

    def pt(n):
        return pcbnew.VECTOR2I(a.x + n[0] * st, a.y + n[1] * st)

    def ok(n):
        if n not in free:
            free[n] = n == (0, 0) or not obst[layer].Collide(pt(n), half)
        return free[n]
    limit = max_mm / step_mm
    seen = {}
    heap = [(0.0, (0, 0), -1, None)]
    while heap:
        cost, n, d, prev = heapq.heappop(heap)
        if (n, d) in seen:
            continue
        seen[(n, d)] = prev
        if n != (0, 0) and inside(pt(n)):
            if n not in goal:
                goal[n] = via_fits(pt(n))
            if goal[n]:
                path, key = [n], (n, d)
                while seen[key] is not None:
                    key = seen[key]
                    path.append(key[0])
                corners = [path[0]] + [q for i, q in enumerate(path[1:-1], 1)
                                       if (path[i - 1][0] - q[0], path[i - 1][1] - q[1]) != (q[0] - path[i + 1][0],
                                                                                         q[1] - path[i + 1][1])] + [path[-1]]
                pts = [pt(q) for q in reversed(corners)]
                pts[0] = a
                if any(obst[layer].Collide(pcbnew.SEG(u, v), half) for u, v in zip(pts[1:], pts[2:])):
                    return None
                return pts
        for k, (dx, dy) in enumerate(moves):
            m = (n[0] + dx, n[1] + dy)
            c = cost + (1.4142 if dx and dy else 1.0) + (3.0 if d not in (-1, k) else 0.0)
            if c > limit * 1.5 or (m, k) in seen or not ok(m):
                continue
            heapq.heappush(heap, (c, m, k, (n, d)))
    return None


def fanout_pads(board, specs: dict, islands: list, only=None) -> list[tuple[str, int, int]]:
    """b.pcb["fanout_nets"]: {net: (plane layer, via Ø, drill, track width)}.  Before routing, every
    SMD pad of these nets gets a short track out of its footprint to a via of its own landing on the
    net's plane (In1 for GND, the net's area of In2 for a supply), locked so Freerouting keeps it:
    no GND or supply pin then depends on an outer pour that signal tracks may cut in pieces.  Pads
    inside a top-side island of their own net (`islands`: [(net, poly mm)], which carry their own
    vias) and pads already reached by a fixed track are left alone.  A pad over another net's area of
    a split plane gets its track to the nearest spot of its own area, up to REMOTE_FEED_MM away:
    Freerouting doesn't route those (its fan-out drops their via in the wrong area, then it leaves
    them open).  `only`: the pads ("REF.PAD") to fan out, the others left alone (a routed board's patch).
    Returns [(net, done, pads)]."""
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    err, clr = MM(0.005), MM(0.2)
    layers = copper_of(board)
    edge = board.GetBoardEdgesBoundingBox()
    edge.Inflate(-MM(0.6))
    out = []
    for name, (plane_name, via_d, drill, width) in specs.items():
        net = board.FindNet(name)
        if net is None:
            continue
        code = net.GetNetCode()
        plane = getattr(pcbnew, plane_name.replace(".", "_"))
        fill = pcbnew.SHAPE_POLY_SET()
        for z in board.Zones():
            if not z.GetIsRuleArea() and z.GetNetCode() == code and z.IsOnLayer(plane):
                fill.Append(z.GetFilledPolysList(plane))
        obst = {}
        for layer in layers:
            sh = pcbnew.SHAPE_POLY_SET()
            for t in board.GetTracks():
                if t.GetNetCode() != code and t.IsOnLayer(layer):
                    t.TransformShapeToPolygon(sh, layer, clr, err, pcbnew.ERROR_OUTSIDE)
            for fp in board.GetFootprints():
                for p in fp.Pads():
                    if p.GetNetCode() != code and p.IsOnLayer(layer):
                        p.TransformShapeToPolygon(sh, layer, clr, err, pcbnew.ERROR_OUTSIDE)
            for z in board.Zones():
                if z.GetIsRuleArea() and z.IsOnLayer(layer) and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
                    sh.Append(z.Outline())
            obst[layer] = sh
        # a fan-out via lands on no SMD pad, its own net's included (an open via in a small part's pad drains
        # its joint)
        smd = pcbnew.SHAPE_POLY_SET()
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetDrillSize().x == 0 and p.GetNetCode() == code:
                    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                        if p.IsOnLayer(layer):
                            p.TransformShapeToPolygon(smd, layer, MM(0.05), err, pcbnew.ERROR_OUTSIDE)
        holes = [(t.GetPosition(), t.GetDrillValue()) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
        holes += [(p.GetPosition(), max(p.GetDrillSize().x, p.GetDrillSize().y))
                  for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
        ends = {(e.x, e.y) for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetCode() == code
                for e in (t.GetStart(), t.GetEnd())}
        skip = []
        for n_, poly in islands:
            if n_ == name:
                s = pcbnew.SHAPE_POLY_SET()
                s.NewOutline()
                for x, y in poly:
                    s.Append(MM(x), MM(y))
                skip.append(s)
        r_via = MM(via_d) // 2

        def via_fits(e):
            if not edge.Contains(e):
                return False
            if any(math.hypot(e.x - q.x, e.y - q.y) < d / 2 + MM(drill) / 2 + MM(0.35) for q, d in holes):
                return False
            if not all(fill.Contains(pcbnew.VECTOR2I(int(e.x + (r_via + MM(0.15)) * math.cos(a)),
                                                     int(e.y + (r_via + MM(0.15)) * math.sin(a))))
                       for a in [k * math.pi / 4 for k in range(8)]):
                return False
            return not smd.Collide(e, r_via) and not any(obst[l].Collide(e, r_via) for l in layers)

        pads = [p for fp in board.GetFootprints() for p in fp.Pads()
                if p.GetNetCode() == code and p.GetDrillSize().x == 0
                and (p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu))]
        done = todo = 0
        for pad in pads:
            a = pad.GetPosition()
            if any(s.Contains(a) for s in skip):
                continue
            if only is not None and f"{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}" not in only:
                continue
            bb = pad.GetBoundingBox()
            if any(bb.Contains(pcbnew.VECTOR2I(x, y)) for x, y in ends):
                continue
            todo += 1
            remote = not fill.Contains(a)
            layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            c = pad.GetParentFootprint().GetPosition()
            ux, uy = a.x - c.x, a.y - c.y
            norm = math.hypot(ux, uy)
            ux, uy = (ux / norm, uy / norm) if norm > MM(0.05) else (0.0, -1.0)
            best = None
            for k in range(16):
                ang = k * math.pi / 8
                dx, dy = math.cos(ang), math.sin(ang)
                bend = 1 - (dx * ux + dy * uy)           # 0 straight out of the footprint, 2 back into it
                reach = abs(dx) * bb.GetWidth() / 2 + abs(dy) * bb.GetHeight() / 2 + r_via + MM(0.1)
                for step in range(int(REMOTE_FEED_MM * 10) if remote else 30):
                    L = reach + MM(0.1 * step)
                    score = pcbnew.ToMM(L) + 1.5 * bend
                    if best and score >= best[0]:
                        break
                    e = pcbnew.VECTOR2I(int(a.x + dx * L), int(a.y + dy * L))
                    if obst[layer].Collide(pcbnew.SEG(a, e), MM(width) // 2):
                        break
                    if via_fits(e):
                        best = (score, e)
                        break
            path = [a, best[1]] if best else None
            if not best and remote:
                # no straight way out to its own area: one with bends
                path = _feed_path(a, layer, obst, via_fits, MM(width) // 2, lambda q: fill.Contains(q))
            if not path:
                print(f"fan-out {name}: no room by {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}")
                continue
            e = path[-1]
            for u, w in zip(path, path[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(u)
                t.SetEnd(w)
                t.SetWidth(MM(width))
                t.SetLayer(layer)
                t.SetNet(net)
                t.SetLocked(True)
                board.Add(t)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(e)
            v.SetWidth(MM(via_d))
            v.SetDrill(MM(drill))
            v.SetNet(net)
            v.SetLocked(True)
            board.Add(v)
            holes.append((e, MM(drill)))
            done += 1
            if remote:
                L = sum(pcbnew.ToMM((w - u).EuclideanNorm()) for u, w in zip(path, path[1:]))
                print(f"fan-out {name}: {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()} over another "
                      f"net's area, fed by {L:.1f} mm of track ({len(path) - 2} bends)")
        out.append((name, done, todo))
    return out


def _strip_zones(text: str, name_prefix: str) -> str:
    """Remove every top-level (zone ...) whose name starts with name_prefix from a .kicad_pcb text."""
    out, i = [], 0
    key = '(name "' + name_prefix
    while True:
        j = text.find("(zone", i)
        if j < 0:
            out.append(text[i:])
            return "".join(out)
        depth, k, quoted = 0, j, False
        while True:
            ch = text[k]
            if quoted:
                if ch == "\\":
                    k += 1
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        block = text[j:k + 1]
        if key in block[:400]:
            out.append(text[i:j].rstrip(" 	"))
        else:
            out.append(text[i:k + 1])
        i = k + 1


def fanout_geometry(board, ref: str, num: str, via_d: float = 0.6, margin: float = 0.2):
    """Dog-bone for a pad the pour can't be trusted to reach (e.g. the middle GND pin of a
    SOT-23-6): the via goes straight out of the package, away from its centre.
    Returns (pad, via position, keep-out polygon in mm reserving the path while routing)."""
    fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
    pad = next(p for p in fp.Pads() if p.GetNumber() == str(num))
    c, q = fp.GetPosition(), pad.GetPosition()
    dx, dy = q.x - c.x, q.y - c.y
    ux, uy = (1 if dx > 0 else -1, 0) if abs(dx) >= abs(dy) else (0, 1 if dy > 0 else -1)
    bb = pad.GetBoundingBox()
    half = (bb.GetWidth() if ux else bb.GetHeight()) / 2
    reach = half + MM(0.25 + via_d / 2)
    via_at = pcbnew.VECTOR2I(int(q.x + ux * reach), int(q.y + uy * reach))
    w = MM(via_d / 2 + margin)                     # half-width of the reserved strip
    a = (q.x + ux * half, q.y + uy * half)         # pad edge
    e = (via_at.x + ux * w, via_at.y + uy * w)     # beyond the via
    xs = sorted([a[0], e[0]]) if ux else [q.x - w, q.x + w]
    ys = sorted([a[1], e[1]]) if uy else [q.y - w, q.y + w]
    mm = pcbnew.ToMM
    poly = [(mm(xs[0]), mm(ys[0])), (mm(xs[1]), mm(ys[0])), (mm(xs[1]), mm(ys[1])), (mm(xs[0]), mm(ys[1]))]
    return pad, via_at, poly


def stitch_gnd(board, gnd, pitch_mm: float, via_d: float = 0.6, drill: float = 0.3, clear: float = 0.25,
               hole_gap: float = 0.35) -> int:
    """Drop GND vias wherever every copper layer is GND fill (or plane) around the via.

    Freerouting assumes the outer GND pours connect the pads it left on them; once KiCad
    fills the pours with real clearances they break into fragments.  A grid of vias ties
    the big areas to the inner GND plane, then every fragment still without a via (or a
    GND through-hole pad) gets one at the first spot where it fits.
    """
    filler = pcbnew.ZONE_FILLER(board)
    gnd_code = gnd.GetNetCode()
    copper = copper_of(board)
    keepouts = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    def ring_of(rad):
        return [(0, 0)] + [(rad * math.cos(a), rad * math.sin(a)) for a in [k * math.pi / 8 for k in range(16)]]

    # grid vias keep a generous margin; in a fragment the fill already keeps its clearance
    # from foreign copper, so a via whose land lies inside the fill is fine
    r = via_d / 2 + clear + 0.05
    tracks_in = [t for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetLayer() in copper
                 and t.GetNetCode() != gnd_code]

    # every drilled hole on the board: vias, PTH/NPTH pads (x, y, drill diameter)
    holes = []
    anchors = []          # things that tie all layers to GND: GND vias and GND through-hole pads
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            holes.append((p.x, p.y, t.GetDrillValue()))
            if t.GetNetCode() == gnd_code:
                anchors.append(p)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d = pad.GetDrillSize()
            if d.x > 0:
                p = pad.GetPosition()
                holes.append((p.x, p.y, max(d.x, d.y)))
                if pad.GetNetCode() == gnd_code:
                    anchors.append(p)

    # no stitching via on an SMD pad, a GND one included: a solid pad lies inside its pour's fill, and an open via
    # there drains the joint (a small part's, a crystal's)
    smd = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetDrillSize().x == 0:
                for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if pad.IsOnLayer(l):
                        pad.TransformShapeToPolygon(smd, l, MM(0.05), MM(0.005), pcbnew.ERROR_OUTSIDE)

    def fills():
        filler.Fill(board.Zones())
        out = {l: [] for l in copper}
        for z in board.Zones():
            # "fill" zones (GND behind a power layer's pours) don't make it a GND layer
            if z.GetIsRuleArea() or z.GetNetCode() != gnd_code or z.GetZoneName().startswith("fill"):
                continue
            for l in copper:
                if z.IsOnLayer(l):
                    out[l].append(z.GetFilledPolysList(l))
        return out

    def hole_ok(x, y, d=drill):
        for hx, hy, hd in holes:
            if math.hypot(x - hx, y - hy) < hd / 2 + MM(d) / 2 + MM(hole_gap):
                return False
        return True

    def covered(f, x, y, rad=None, d=drill, skip=None):
        rad = r if rad is None else rad
        ring = ring_of(rad)
        for l in copper:
            if l == skip:
                continue
            polys = f[l]
            if not polys:
                # layer without a GND pour (e.g. an inner signal layer): only require no foreign track nearby
                for t in tracks_in:
                    if t.GetLayer() != l:
                        continue
                    a, b = t.GetStart(), t.GetEnd()
                    if _seg_dist(x, y, a.x, a.y, b.x, b.y) < MM(rad + clear) + t.GetWidth() / 2:
                        return False
                continue
            for dx, dy in ring:
                pt = pcbnew.VECTOR2I(int(x + MM(dx)), int(y + MM(dy)))
                if not any(pp.Contains(pt) for pp in polys):
                    return False
        for z in keepouts:
            if z.Outline().Contains(pcbnew.VECTOR2I(int(x), int(y))):
                return False
        if smd.Collide(pcbnew.VECTOR2I(int(x), int(y)), MM(via_d) // 2):
            return False
        return hole_ok(x, y, d)

    def add(x, y, vd=via_d, d=drill):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
        v.SetWidth(MM(vd))
        v.SetDrill(MM(d))
        v.SetNet(gnd)
        board.Add(v)
        holes.append((int(x), int(y), MM(d)))
        anchors.append(pcbnew.VECTOR2I(int(x), int(y)))

    # 1. coarse grid
    f = fills()
    bb = board.GetBoardEdgesBoundingBox()
    step = MM(pitch_mm)
    n = 0
    y = bb.GetTop() + step
    while y < bb.GetBottom() - step / 2:
        x = bb.GetLeft() + step
        while x < bb.GetRight() - step / 2:
            if covered(f, x, y):
                add(x, y)
                n += 1
            x += step
        y += step

    def stuck_fragments(f):
        return [(l, polys, i) for l in copper for polys in f[l] for i in range(polys.OutlineCount())
                if not any(polys.Contains(a, i) for a in anchors)]

    # 2. every fragment of every GND fill without an anchor gets a via (fine search,
    #    standard via first, then the small one)
    sizes = [(via_d, drill), SMALL_VIA]
    for _ in range(3):
        f = fills()
        added = 0
        for l, polys, i in stuck_fragments(f):
            spot = _find_spot(polys, i, lambda x, y, vd, d: covered(f, x, y, vd / 2 + 0.03, d), sizes)
            if spot:
                add(*spot)
                added += 1
        n += added
        if not added:
            break

    # 3. a GND pad no connected fill reaches (walled in by tracks, or in a fragment too small for a
    #    via): a thin track can often squeeze out (the pour needs 2 × 0.25 mm clearance + 0.2 mm,
    #    a 0.2 mm track far less) to a connected part of the pour, or to a spot where a small via fits
    def lonely_pads(f):
        out = []
        for l in copper:
            conn = [(pp, j) for pp in f[l] for j in range(pp.OutlineCount())
                    if any(pp.Contains(a, j) for a in anchors)]
            if not f[l]:
                continue
            for fp in board.GetFootprints():
                for pad in fp.Pads():
                    if (pad.GetNetCode() == gnd_code and pad.GetDrillSize().x == 0 and pad.IsOnLayer(l)
                            and not any(pp.Contains(pad.GetPosition(), j) for pp, j in conn)):
                        out.append((l, pad))
        return out

    f = fills()
    lonely = lonely_pads(f)
    if lonely:
        for l, pad in lonely:
            fix = _squeeze_to_gnd(board, gnd, l, pad, f[l], anchors,
                                  lambda x, y, l=l: covered(f, x, y, 0.45 / 2 + 0.03, 0.25, skip=l))
            if fix:
                (ax, ay), (ex, ey), via = fix
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(int(ax), int(ay)))
                t.SetEnd(pcbnew.VECTOR2I(int(ex), int(ey)))
                t.SetWidth(MM(0.2))
                t.SetLayer(l)
                t.SetNet(gnd)
                board.Add(t)
                if via:
                    add(ex, ey, *SMALL_VIA)
                    n += 1
        f = fills()
        for l, pad in lonely_pads(f):
            q = pad.GetPosition()
            print(f"stitching: GND pad {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()} still isolated "
                  f"on {board.GetLayerName(l)} at ({pcbnew.ToMM(q.x):.2f}, {pcbnew.ToMM(q.y):.2f})")
    filler.Fill(board.Zones())
    return n


def _squeeze_to_gnd(board, gnd, layer, pad, layer_fills, anchors, via_fits, width_mm=0.2):
    """Shortest straight track from a GND pad to connected GND fill (or to a via spot)."""
    code = gnd.GetNetCode()
    try:
        own = gnd.GetNetClass().GetClearance()
    except Exception:
        own = MM(0.2)
    err = MM(0.005)
    obstacles = pcbnew.SHAPE_POLY_SET()
    for t in board.GetTracks():
        if t.GetNetCode() == code or not t.IsOnLayer(layer):
            continue
        t.TransformShapeToPolygon(obstacles, layer, max(own, t.GetOwnClearance(layer)) + MM(0.01), err,
                                  pcbnew.ERROR_OUTSIDE)
    for fp in board.GetFootprints():
        for other in fp.Pads():
            if other.IsOnLayer(layer) and other.GetNetCode() != code:
                other.TransformShapeToPolygon(obstacles, layer, max(own, other.GetOwnClearance(layer)) + MM(0.01),
                                              err, pcbnew.ERROR_OUTSIDE)
    for z in board.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(layer):
            obstacles.Append(z.Outline())
    edge = board.GetBoardEdgesBoundingBox()
    edge.Inflate(-MM(0.5))
    connected = [(pp, j) for pp in layer_fills for j in range(pp.OutlineCount())
                 if any(pp.Contains(k, j) for k in anchors)]
    half = MM(width_mm) // 2
    best = None
    a = pad.GetPosition()
    for k in range(36):
        ang = k * math.pi / 18
        dx, dy = math.cos(ang), math.sin(ang)
        for step in range(3, 31):
            L = MM(step * 0.1)
            e = pcbnew.VECTOR2I(int(a.x + dx * L), int(a.y + dy * L))
            if not edge.Contains(e) or obstacles.Collide(pcbnew.SEG(a, e), half):
                break          # longer tracks in this direction collide too
            if best and L >= best[0]:
                break
            if any(pp.Contains(e, j) for pp, j in connected):
                best = (L, (a.x, a.y), (e.x, e.y), False)
                break
            if not obstacles.Collide(e, MM(0.45) // 2) and via_fits(e.x, e.y):
                best = (L, (a.x, a.y), (e.x, e.y), True)
                break
    return best[1:] if best else None


def _find_spot(polys, i, ok, sizes, step_mm=0.1):
    """First point of fragment i (of a SHAPE_POLY_SET) where ok(x, y, via_d, drill) holds."""
    box = polys.Outline(i).BBox()
    step = MM(step_mm)
    for vd, d in sizes:
        yy = box.GetTop()
        while yy <= box.GetBottom():
            xx = box.GetLeft()
            while xx <= box.GetRight():
                if polys.Contains(pcbnew.VECTOR2I(int(xx), int(yy)), i) and ok(xx, yy, vd, d):
                    return xx, yy, vd, d
                xx += step
            yy += step
    return None


def _copper_obstacles(board, layers, clear: float, skip=lambda item: False) -> dict:
    """Per copper layer, every track, via and pad (but those `skip` names) grown by `clear` mm."""
    err = MM(0.005)
    out = {}
    for l in layers:
        sh = pcbnew.SHAPE_POLY_SET()
        for t in board.GetTracks():
            if t.IsOnLayer(l) and not skip(t):
                t.TransformShapeToPolygon(sh, l, MM(clear), err, pcbnew.ERROR_OUTSIDE)
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(l) and not skip(p):
                    p.TransformShapeToPolygon(sh, l, MM(clear), err, pcbnew.ERROR_OUTSIDE)
        out[l] = sh
    return out


def edge_fence(board, outline, gnd, pitch: float, inset: float, via_d: float = 0.5, drill: float = 0.3,
               clear: float = 0.2) -> tuple[int, int]:
    """b.pcb["edge_fence"]: {"pitch": mm, "inset": mm}.  GND vias along the board's edge, drawn before
    routing and locked, so Freerouting routes inside them: with the outer GND pours and the GND plane they
    close the edge, and the power plane's cavity (its planes held back from the edge) doesn't radiate from
    it.  One every `pitch` mm along the outline inset by `inset` mm, each slid along it by up to half a
    pitch to clear other copper, holes and keep-outs.  Returns (placed, wanted)."""
    layers = copper_of(board)
    obst = _copper_obstacles(board, layers, clear)
    holes = [(t.GetPosition().x, t.GetPosition().y, t.GetDrillValue()) for t in board.GetTracks()
             if t.GetClass() == "PCB_VIA"]
    holes += [(p.GetPosition().x, p.GetPosition().y, max(p.GetDrillSize().x, p.GetDrillSize().y))
              for fp in board.GetFootprints() for p in fp.Pads() if p.GetDrillSize().x > 0]
    keep = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    ring = [(MM(x), MM(y)) for x, y in inset_poly(outline, inset)[0]]
    segs = list(zip(ring, ring[1:] + ring[:1]))
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs]
    total = sum(lens)
    n = max(1, round(total / MM(pitch)))
    step = total / n
    r = MM(via_d) // 2

    def at(s):
        s %= total
        for (a, b), L in zip(segs, lens):
            if s <= L:
                f = s / L if L else 0.0
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            s -= L
        return ring[0]

    def fits(x, y):
        if any(math.hypot(x - hx, y - hy) < hd / 2 + MM(drill) / 2 + MM(0.35) for hx, hy, hd in holes):
            return False
        e = pcbnew.VECTOR2I(int(x), int(y))
        if any(z.Outline().Collide(e, r) for z in keep):
            return False
        return not any(obst[l].Collide(e, r) for l in layers)

    placed = 0
    slide = MM(0.25)
    for i in range(n):
        tries = [0] + [sgn * k * slide for k in range(1, int(step / 2 / slide) + 1) for sgn in (1, -1)]
        for ds in tries:
            x, y = at(i * step + ds)
            if fits(x, y):
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                v.SetWidth(MM(via_d))
                v.SetDrill(MM(drill))
                v.SetNet(gnd)
                if hasattr(v, "SetIsFree"):
                    v.SetIsFree(True)       # tied to the copper through zones only
                v.SetLocked(True)
                board.Add(v)
                holes.append((x, y, MM(drill)))
                placed += 1
                break
    return placed, n


def _net_length(board, code: int) -> float:
    return sum(t.GetLength() for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetCode() == code)


def tidy_board(b: Board, path: Path):
    """tidy_tracks() on the board saved at `path`, as b.pcb["tidy"] says (every board, unless it says None),
    in a process of its own: removing tracks leaves this one's SWIG proxies untyped.  The differential pairs'
    lines stay as the router laid them, side by side; the exclusive pours' cores and the fan-out
    reservations bar tracks as they did while routing."""
    kw = b.pcb.get("tidy", {})
    if kw is None:
        return
    from route_metrics import diff_pairs
    names = {str(n) for n in pcbnew.LoadBoard(str(path)).GetNetsByName().keys()}
    cores = [(spec["layer"], b.pcb_net_name(spec["net"]), inset_poly(spec["poly"], spec["exclusive"]))
             for spec in b.pcb.get("zones", []) if spec.get("exclusive")]
    kw = {**kw, "skip": [n for pair in diff_pairs(b, names) for n in pair], "cores": cores,
          "fanout": [list(f) for f in b.pcb.get("fanout", [])]}
    subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); import pcbgen; "
                    "pcbgen.tidy_file(sys.argv[2], **json.loads(sys.argv[3]))",
                    str(Path(__file__).parent), str(path), json.dumps(kw)], check=True)


def tidy_file(path: str, cores=(), fanout=(), **kw):
    """tidy_tracks() on a saved board (see tidy_board).  cores: [layer, net, [poly mm, ...]] that other nets'
    tracks stay out of; fanout: [ref, pad] whose dog-bone's room no track may take."""
    t0 = time.time()
    board = pcbnew.LoadBoard(path)

    def poly_set(poly):
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        for x, y in poly:
            ps.Append(MM(x), MM(y))
        return ps

    bars = [(board.GetLayerID(layer), net, poly_set(p)) for layer, net, polys in cores for p in polys]
    bars += [(None, None, poly_set(fanout_geometry(board, ref, num)[2])) for ref, num in fanout]
    n, widened, before, after = tidy_tracks(board, bars=bars, **kw)
    board.Save(path)
    print(f"tidy: {n} runs straightened or merged, {widened} necks widened, router segments {before} -> {after} "
          f"({time.time() - t0:.0f} s)")


def tidy_tracks(board, short: float = 0.6, reach: int = 12, margin: float = 0.002, skip=(),
                bars=()) -> tuple[int, int, int, int]:
    """b.pcb["tidy"]: {"short": mm, "reach": segments}.  Freerouting lays a route as it found it, around each
    obstacle's clearance octagon: staircases of 45° and straight segments where one bend would do, pads left
    by a short straight and a micro-jog; its optimizer pulls them tight one corner at a time and keeps them.
    After the session's import, along each chain of the router's own segments (one net, one layer, one
    width, through bends that no via, pad, drawn track or branch touches), a run of up to `reach` segments
    becomes the fewest straight and 45° segments that join its ends (octilinear.paths: one, one bend or a
    dogleg), or, for a run holding one shorter than `short` mm, as many without it.  Only when that is no
    longer than the run and keeps its clearance (+ `margin` mm) to every other net's copper, the board's
    edge, the keep-outs that bar tracks (the footprints' too) and `bars`: (layer or None for all, net or
    None for all, SHAPE_POLY_SET) that other nets' tracks stay out of.  Then collinear neighbours merge.
    Drawn (locked) tracks and the nets in `skip` are never touched.  Where neighbours or vias hem a
    staircase in (a bus weaving through a via field), it stays: only a re-route moves it.  First, a router
    track that Freerouting's neck-down left under the board's minimum width (0.063 mm against the DATA ×4
    v2's 0.09) is widened to it, where its clearances allow.  Returns (runs replaced, tracks widened, router
    segments before, after)."""
    T = MM(0.001)                                       # 1 µm: the geometry's tolerance
    layers = copper_of(board)
    skip = set(skip)
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    edge_segs = [outline.Outline(i).CSegment(k) for i in range(outline.OutlineCount())
                 for k in range(outline.Outline(i).SegmentCount())]
    edge_clear = board.GetDesignSettings().m_CopperEdgeClearance
    areas = list(board.Zones()) + [z for fp in board.GetFootprints() for z in fp.Zones()]
    keep = {l: [(None, pcbnew.SHAPE_POLY_SET(z.Outline())) for z in areas
                if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(l)]
            + [(net, ps) for bl, net, ps in bars if bl is None or bl == l] for l in layers}
    cell = MM(2.0)
    grid = {l: {} for l in layers}                      # per layer, a 2 mm grid of (uuid, net, clearance, shape)
    dead = set()

    def cells(x0, y0, x1, y1):
        return [(i, j) for i in range(int(x0 // cell), int(x1 // cell) + 1)
                for j in range(int(y0 // cell), int(y1 // cell) + 1)]

    def index(item, l):
        bb = item.GetBoundingBox()
        entry = (item.m_Uuid.AsString(), item.GetNetCode(), item.GetOwnClearance(l), item.GetEffectiveShape(l))
        for c in cells(bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()):
            grid[l].setdefault(c, []).append(entry)

    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]

    def index_all():
        for l in layers:
            grid[l].clear()
        for item in list(board.GetTracks()) + pads:
            for l in layers:
                if item.IsOnLayer(l):
                    index(item, l)

    index_all()

    def clear_of(a, b, w, l, net, name, own):
        """Segment a-b, w wide, of `net` on layer l: clear of every other net, the edge and the keep-outs."""
        seg = pcbnew.SEG(a, b)
        half = w // 2
        r = half + MM(1.0)
        seen = set()
        for c in cells(min(a.x, b.x) - r, min(a.y, b.y) - r, max(a.x, b.x) + r, max(a.y, b.y) + r):
            for uid, o_net, o_clear, shape in grid[l].get(c, ()):
                if uid in seen or uid in dead or (o_net == net and net > 0):
                    continue
                seen.add(uid)
                if shape.Collide(seg, half + max(own, o_clear) + MM(margin)):
                    return False
        if any(e.Distance(seg) < half + edge_clear + MM(margin) for e in edge_segs):
            return False
        return not any(k.Collide(seg, half) for k_net, k in keep[l] if k_net != name)

    def dist(p, q):
        return math.hypot(q.x - p.x, q.y - p.y)

    def key(p):
        return (p.x, p.y)

    def router_tracks():
        return [t for t in board.GetTracks()
                if t.GetClass() == "PCB_TRACK" and not t.IsLocked() and t.GetLayer() in layers]

    floor, widened = board.GetDesignSettings().m_TrackMinWidth, 0
    for t in router_tracks():
        l = t.GetLayer()
        if t.GetWidth() < floor and clear_of(t.GetStart(), t.GetEnd(), floor, l, t.GetNetCode(), t.GetNetname(),
                                              t.GetOwnClearance(l)):
            t.SetWidth(floor)
            widened += 1
    if widened:
        index_all()                                     # the widened tracks' shapes
    before, replaced = len(router_tracks()), 0
    for _ in range(4):
        changed = False
        vias, other_ends, groups = {}, {}, {}
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                vias.setdefault(t.GetNetCode(), set()).add(key(t.GetPosition()))
            elif t.GetClass() == "PCB_TRACK":
                if not t.IsLocked() and t.GetLayer() in layers and t.GetNetname() not in skip:
                    groups.setdefault((t.GetNetCode(), t.GetLayer(), t.GetWidth()), []).append(t)
                for p in (t.GetStart(), t.GetEnd()):
                    other_ends.setdefault((t.GetNetCode(), t.GetLayer()), []).append(
                        (key(p), t.IsLocked() or t.GetNetname() in skip, t.GetWidth()))
        for (net, l, w), segs in groups.items():
            name = segs[0].GetNetname()
            ends = {}
            for t in segs:
                for p in (t.GetStart(), t.GetEnd()):
                    ends.setdefault(key(p), []).append(t)
            fixed = set(vias.get(net, ())) | {k for k, locked, wd in other_ends.get((net, l), ()) if locked or wd != w}
            for p in pads:
                if p.GetNetCode() == net and p.IsOnLayer(l):
                    # a pad's centre stays; the bends inside it move only when the chain ends on that centre
                    c = key(p.GetPosition())
                    fixed.add(c)
                    if c not in ends:
                        fixed.update(k for k in ends if p.HitTest(pcbnew.VECTOR2I(*k)))
            anchor = {k for k, ts in ends.items() if len(ts) != 2 or k in fixed}
            done = set()
            for start in [k for k in ends if k in anchor]:
                for first in ends[start]:
                    if first.m_Uuid.AsString() in done:
                        continue
                    chain, pts, k, t = [], [pcbnew.VECTOR2I(*start)], start, first
                    while t is not None and t.m_Uuid.AsString() not in done:
                        done.add(t.m_Uuid.AsString())
                        chain.append(t)
                        k = key(t.GetEnd()) if key(t.GetStart()) == k else key(t.GetStart())
                        pts.append(pcbnew.VECTOR2I(*k))
                        if k in anchor:
                            break
                        t = next((o for o in ends[k] if o.m_Uuid.AsString() != t.m_Uuid.AsString()), None)
                    own = chain[0].GetOwnClearance(l)
                    new, i, edits = [pts[0]], 0, 0
                    while i < len(pts) - 1:
                        best = None
                        for j in range(min(len(pts) - 1, i + reach), i + 1, -1):
                            run = pts[i:j + 1]
                            least = min(dist(p, q) for p, q in zip(run, run[1:]))
                            old = sum(dist(p, q) for p, q in zip(run, run[1:]))
                            for cand in octilinear.paths(key(pts[i]), key(pts[j]), T, [key(p) for p in run[1:-1]]):
                                n = len(cand) - 1
                                # fewer segments, or as many with the run's shortest one gone
                                if n > j - i or (n == j - i and least >= MM(short)):
                                    continue
                                if octilinear.length(cand) > old + T:
                                    continue
                                shortest = min(math.dist(p, q) for p, q in zip(cand, cand[1:]))
                                if shortest < MM(0.05) or (n == j - i and shortest < max(2 * least, MM(0.25))):
                                    continue
                                cand = [pcbnew.VECTOR2I(*p) for p in cand]
                                if all(clear_of(p, q, w, l, net, name, own) for p, q in zip(cand, cand[1:])):
                                    best = (j, cand)
                                    break
                            if best:
                                break
                        if best:
                            new += best[1][1:]
                            i = best[0]
                            edits += 1
                        else:
                            new.append(pts[i + 1])
                            i += 1
                    merged = [new[0]]
                    for p in new[1:]:                   # collinear neighbours, same direction: one segment
                        if len(merged) >= 2:
                            a, b = merged[-2], merged[-1]
                            cross = (b.x - a.x) * (p.y - b.y) - (b.y - a.y) * (p.x - b.x)
                            if abs(cross) <= T * max(dist(a, b), dist(b, p), 1) and \
                                    (b.x - a.x) * (p.x - b.x) + (b.y - a.y) * (p.y - b.y) > 0:
                                merged[-1] = p
                                edits += 1
                                continue
                        merged.append(p)
                    if not edits:
                        continue
                    changed, replaced = True, replaced + edits
                    for c in chain:
                        dead.add(c.m_Uuid.AsString())
                        board.Remove(c)
                    for p, q in zip(merged, merged[1:]):
                        nt = pcbnew.PCB_TRACK(board)
                        nt.SetStart(p)
                        nt.SetEnd(q)
                        nt.SetWidth(w)
                        nt.SetLayer(l)
                        nt.SetNetCode(net)
                        board.Add(nt)
                        index(nt, l)
        if not changed:
            break
    return replaced, widened, before, len(router_tracks())


def tune_pairs(board, pairs, tol: float, clear: float = 0.15, pitch: float = 0.5, margin: float = 0.6,
               heights=(1.0, 0.75, 0.5, 0.35)) -> list[str]:
    """b.pcb["match"]: {"pairs": [(net, net), ...], "tol": mm}.  Freerouting routes the two lines of a
    differential pair on their own: after the session's import, lengthen the shorter line until the two
    match within `tol` mm, with meanders (bumps `pitch` mm wide, as high and as many as the room beside it
    allows) on its own straight, unlocked segments, clear of all other copper and keep-outs.  Returns one
    report line per pair."""
    layers = [pcbnew.F_Cu, pcbnew.B_Cu]
    keep = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
    islands = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() != "GND"]
    err = MM(0.005)
    out = []

    def place(t, short, code, deficit, base):
        """One meander on track t (as much of `deficit` as fits); returns the length added, or 0."""
        layer, w = t.GetLayer(), t.GetWidth()
        obst = pcbnew.SHAPE_POLY_SET(base[layer])
        tid = t.m_Uuid.AsString()
        for o in board.GetTracks():
            if o.GetClass() != "PCB_VIA" and o.GetNetCode() == code and o.IsOnLayer(layer) and o.m_Uuid.AsString() != tid:
                o.TransformShapeToPolygon(obst, layer, MM(clear), err, pcbnew.ERROR_OUTSIDE)
        a = pcbnew.VECTOR2I(t.GetStart().x, t.GetStart().y)
        b = pcbnew.VECTOR2I(t.GetEnd().x, t.GetEnd().y)
        L = t.GetLength()
        if L <= 0:
            return 0
        ux, uy = (b.x - a.x) / L, (b.y - a.y) / L
        wp, mg = MM(pitch), MM(margin)
        mmax = int((L - 2 * mg + wp) // (2 * wp))
        for h in heights:
            hh = MM(h)
            m = min(mmax, math.ceil(deficit / (2 * hh)))
            while m >= 1:
                last = min(hh, (deficit - 2 * hh * (m - 1)) / 2)   # the last bump's height: no more than the deficit
                if last < MM(0.15):
                    m -= 1
                    continue
                span = wp * (2 * m - 1)
                for side in (1, -1):
                    nx, ny = -uy * side, ux * side
                    s0 = mg
                    while s0 + span <= L - mg:
                        pts = []
                        for j in range(m):
                            hj = hh if j < m - 1 else last
                            x0 = s0 + 2 * wp * j
                            for dx, dh in ((x0, 0), (x0, hj), (x0 + wp, hj), (x0 + wp, 0)):
                                pts.append((a.x + ux * dx + nx * dh, a.y + uy * dx + ny * dh))
                        vs = [pcbnew.VECTOR2I(int(x), int(y)) for x, y in pts]
                        if not any(obst.Collide(pcbnew.SEG(p, q), w // 2) for p, q in zip(vs, vs[1:])):
                            t.SetEnd(vs[0])
                            for p, q in zip(vs, vs[1:] + [b]):
                                nt = pcbnew.PCB_TRACK(board)
                                nt.SetStart(p)
                                nt.SetEnd(q)
                                nt.SetWidth(w)
                                nt.SetLayer(layer)
                                nt.SetNet(short)
                                board.Add(nt)
                            return 2 * hh * (m - 1) + 2 * last
                        s0 += MM(0.25)
                m = m - 1 if m <= 4 else m // 2              # less of it where the whole doesn't fit
        return 0

    for p_name, n_name in pairs:
        nets = [board.FindNet(p_name), board.FindNet(n_name)]
        if None in nets:
            out.append(f"match {p_name}/{n_name}: net missing")
            continue
        lp, ln = (_net_length(board, n.GetNetCode()) for n in nets)
        before = abs(lp - ln)
        for _ in range(40):
            lp, ln = (_net_length(board, n.GetNetCode()) for n in nets)
            short = nets[0] if lp < ln else nets[1]
            deficit = abs(lp - ln)
            if deficit <= MM(0.25):
                break
            code = short.GetNetCode()
            # everything but the short line's own tracks, grown by the clearance, once per meander
            base = _copper_obstacles(board, layers, clear,
                                     skip=lambda it: it.GetClass() != "PCB_VIA" and it.GetNetCode() == code)
            for layer in layers:
                for z in keep + islands:
                    if z.IsOnLayer(layer):
                        base[layer].Append(z.Outline())
            segs = sorted((t for t in board.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetCode() == code
                           and not t.IsLocked() and t.GetLayer() in layers), key=lambda t: -t.GetLength())
            if not any(place(t, short, code, deficit, base) for t in segs):
                break
        lp, ln = (_net_length(board, n.GetNetCode()) for n in nets)
        out.append(f"match {p_name.split('/')[-1]}/{n_name.split('/')[-1]}: {pcbnew.ToMM(lp):.2f} / "
                   f"{pcbnew.ToMM(ln):.2f} mm, {pcbnew.ToMM(before):.2f} → {pcbnew.ToMM(abs(lp - ln)):.2f} mm"
                   + ("" if abs(lp - ln) <= MM(tol) else f"  NOT within {tol} mm"))
    return out


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)
