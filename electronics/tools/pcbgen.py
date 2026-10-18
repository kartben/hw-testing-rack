"""Build a `.kicad_pcb` from a board description (runs inside KiCad's Python).

Footprints come from the stock KiCad libraries (plus `electronics/lib/bench.pretty`),
nets and symbol paths come from the same `Board` object that produced the
schematic, so `kicad-cli pcb drc --schematic-parity` can prove both match.

Placement is given in each part's `pcb` hints (mm, board origin top-left).
Routing is delegated to Freerouting through Specctra DSN/SES; the result is
a reviewable starting point, not a signed-off layout (see docs/electronics.md).
"""

from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import pcbnew

from catalog import HAND_SOLDER_LCSC
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
# Thermal reliefs on every pour (pcbgen.py).  On fine-pitch pads (ESP32 module, MSOP/SOT pins)
# the neighbours leave room for one spoke only: one spoke is still a relief, and enough current
# for a GND pin.
(rule "one thermal spoke is enough"
	(constraint min_resolved_spokes 1))
"""

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
    # standard 2-layer 1.6 mm FR4, 1 oz copper
    "2L-1.6": [("F.Cu", 0.035), ("core", 1.51, "FR4", 4.5), ("B.Cu", 0.035)],
}


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
        if self.layers == 4:
            # b.pcb["inner"]: name and type of In1/In2.  "mixed" = a power layer the router may still
            # use for signals (its pours are added after routing, around the tracks)
            types = {"signal": pcbnew.LT_SIGNAL, "power": pcbnew.LT_POWER, "mixed": pcbnew.LT_MIXED}
            inner = self.b.pcb.get("inner", [("In1.GND", "power"), ("In2.SIG", "signal")])
            for layer, (name, kind) in zip((pcbnew.In1_Cu, pcbnew.In2_Cu), inner):
                bd.SetLayerName(layer, name)
                bd.SetLayerType(layer, types[kind])
        ds = bd.GetDesignSettings()
        # JLCPCB: 0.09 mm (4-layer) / 0.127 mm (2-layer); Freerouting necks down to 0.12 at fine-pitch pads
        ds.m_TrackMinWidth = MM(0.1 if self.layers >= 4 else 0.125)
        ds.m_MinClearance = MM(0.127)
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
                if hand:
                    # soldered by hand: thermal reliefs even on the solid power pours
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                if num in nets:
                    pad.SetNet(self.net(self.b.pcb_net_name(nets[num])))
                elif num in pins:
                    # KiCad names every unconnected symbol pin's net like this
                    pad.SetNet(self.net(f"unconnected-({p.ref}-{pins[num].name}-Pad{num})"))
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

        line(r, 0, w - r, 0); line(w, r, w, h - r); line(w - r, h, r, h); line(0, h - r, 0, r)
        arc(w - r, r, w - r, 0, w, r)
        arc(w - r, h - r, w, h - r, w - r, h)
        arc(r, h - r, r, h, 0, h - r)
        arc(r, r, 0, r, r, 0)

    # -------------------------------------------------------------- zones
    def zone(self, layer, net: str | None, poly, priority=0, keepout=False, name="", layers=None, tracks_only=False,
             connection="thermal"):
        z = pcbnew.ZONE(self.board)
        z.SetLayer(layer)
        if net:
            z.SetNet(self.net(self.b.pcb_net_name(net)))
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in poly:
            ol.Append(MM(x), MM(y))
        z.SetAssignedPriority(priority)
        if name:
            z.SetZoneName(name)
        if keepout:
            z.SetIsRuleArea(True)
            # tracks_only: keep the router's tracks out but let vias and the GND pour in
            # (exported to the DSN as a wire_keepout)
            z.SetDoNotAllowTracks(True)
            z.SetDoNotAllowVias(not tracks_only)
            z.SetDoNotAllowZoneFills(not tracks_only)
            z.SetDoNotAllowPads(False)
            z.SetDoNotAllowFootprints(False)
            ls = pcbnew.LSET()
            for l in layers or self.copper_layers():
                ls.AddLayer(l)
            z.SetLayerSet(ls)
        else:
            z.SetMinThickness(MM(0.2))
            z.SetLocalClearance(MM(0.25))
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

    def deferred_layers(self) -> set[str]:
        d = self.b.pcb.get("defer_pours", True)
        if d is True:
            return {"F.Cu", "B.Cu"}
        return set(d or [])

    def copper_layers(self):
        if self.layers == 4:
            return [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
        return [pcbnew.F_Cu, pcbnew.B_Cu]

    def zones(self, which: str = "all"):
        """which = "routing" (what the router sees: every zone except the deferred pours,
        plus keep-outs), "deferred" (the pours added once the SES is imported) or "all".

        b.pcb["defer_pours"]: True (both outer layers), False (none) or a list of layer names.
        A deferred outer pour forces Freerouting to give every SMD GND pad on that layer its
        own via to the plane, instead of trusting a pour that KiCad may later fill in pieces."""
        m = 0.4
        full = [(m, m), (self.w - m, m), (self.w - m, self.h - m), (m, self.h - m)]
        late = self.deferred_layers()
        have = {(pcbnew.LayerName(z.GetLayer()) if hasattr(pcbnew, "LayerName") else self.board.GetStandardLayerName(z.GetLayer()),
                 z.GetNetname()) for z in self.board.Zones() if not z.GetIsRuleArea()}
        for spec in self.b.pcb.get("zones", []):
            deferred = spec.get("defer", spec["layer"] in late)
            if (which == "routing" and deferred) or (which == "deferred" and not deferred):
                continue
            if which == "deferred" and (spec["layer"], self.b.pcb_net_name(spec["net"])) in have:
                continue          # re-importing a session onto a board that already has its pours
            layer = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu,
                     "In1.Cu": getattr(pcbnew, "In1_Cu", None), "In2.Cu": getattr(pcbnew, "In2_Cu", None)}[spec["layer"]]
            self.zone(layer, spec["net"], spec.get("poly", full), priority=spec.get("priority", 0),
                      name=spec.get("name", ""), connection=spec.get("connection", "thermal"))
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
                          layers=layers, tracks_only=ko.get("tracks_only", False))
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
        layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu, "In1.Cu": getattr(pcbnew, "In1_Cu", None),
                  "In2.Cu": getattr(pcbnew, "In2_Cu", None)}
        for net, layer, width, pts in self.b.pcb.get("tracks", []):
            for a, c in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(self.board)
                t.SetStart(V(*a))
                t.SetEnd(V(*c))
                t.SetWidth(MM(width))
                t.SetLayer(layers[layer])
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
        if self.b.pcb.get("fanout_nets"):
            specs = {self.b.pcb_net_name(k): v for k, v in self.b.pcb["fanout_nets"].items()}
            islands = [(self.b.pcb_net_name(z["net"]), z["poly"]) for z in self.b.pcb.get("zones", [])
                       if z["layer"] in ("F.Cu", "B.Cu") and "poly" in z]
            for net, n, todo in fanout_pads(self.board, specs, islands):
                print(f"fan-out {net}: {n} of {todo} pads")
        if route:
            self.autoroute(self.b.pcb.get("passes", 40))
        # zones are filled by `kicad-cli pcb drc --refill-zones --save-board` (KiCad's own filler)
        pcbnew.SaveBoard(str(self.path), self.board)
        write_stackup(self.path, self.b.pcb)
        write_via_rules(self.path.with_suffix(".kicad_pro"))
        return self.path


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


def export_dsn(b: Board, outdir: Path) -> Path:
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
    dsn.write_text(re.sub(r"\(clearance (\d+(?:\.\d+)?)\)", lambda m: f"(clearance {float(m.group(1)) + 2:g})", text),
                   encoding="utf-8")
    print("exported", dsn)
    return dsn


def import_session(b: Board, outdir: Path) -> Path:
    """Import Freerouting's session, then add the outer-layer copper pours (they were
    left out of the DSN so the router had to connect every pad with real copper)."""
    path = outdir / f"{b.name}.kicad_pcb"
    ses = outdir / "build" / f"{b.name}.ses"
    # the fan-out reservations have done their job: drop them from the file before loading it
    # (BOARD.Remove() on a zone leaves SWIG unable to type the board's footprints afterwards)
    path.write_text(_strip_zones(path.read_text(encoding="utf-8"), "fanout:"), encoding="utf-8")
    board = pcbnew.LoadBoard(str(path))
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise RuntimeError("SES import failed")
    pb = PcbBuilder.__new__(PcbBuilder)
    pb.b, pb.outdir, pb.path, pb.board = b, outdir, path, board
    pb.w, pb.h = b.pcb["size"]
    pb.layers = b.pcb.get("layers", 2)
    pb.nets = {}
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
    board.GetDesignSettings().m_TrackMinWidth = MM(0.1 if pb.layers >= 4 else 0.125)
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
    print("imported", ses)
    return path


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
    gone = []
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.m_Uuid.AsString() in uuids]:
        p = v.GetPosition()
        ends = [t.GetLayer() for t in board.GetTracks() if t.GetClass() != "PCB_VIA"
                and t.GetNetCode() == v.GetNetCode() and p in (t.GetStart(), t.GetEnd())]
        if not v.IsLocked() and len(ends) >= 2 and len(set(ends)) == 1:
            gone.append(v)
    for v in gone:
        board.Remove(v)
    if gone:
        pcbnew.SaveBoard(str(path), board)
        print(f"vias: dropped {len(gone)} pass-through via(s)")
    return len(gone)


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
    layers = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if board.GetEnabledLayers().Contains(l)]
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

    def via_fits(e):
        if not edge.Contains(e):
            return False
        for q, d in holes:
            if math.hypot(e.x - q.x, e.y - q.y) < d / 2 + MM(drill) / 2 + MM(0.35):
                return False
        if not on_plane(e, MM(via_d) / 2 + MM(0.1)):
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


def fanout_pads(board, specs: dict, islands: list) -> list[tuple[str, int, int]]:
    """b.pcb["fanout_nets"]: {net: (plane layer, via Ø, drill, track width)}.  Before routing, every
    SMD pad of these nets gets a short track out of its footprint to a via of its own landing on the
    net's plane (In1 for GND, the net's area of In2 for a supply), locked so Freerouting keeps it:
    no GND or supply pin then depends on an outer pour that signal tracks may cut in pieces.  Pads
    inside a top-side island of their own net (`islands`: [(net, poly mm)], which carry their own
    vias) and pads already reached by a fixed track are left alone.  Returns [(net, done, pads)]."""
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    err, clr = MM(0.005), MM(0.2)
    layers = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if board.GetEnabledLayers().Contains(l)]
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
            return not any(obst[l].Collide(e, r_via) for l in layers)

        pads = [p for fp in board.GetFootprints() for p in fp.Pads()
                if p.GetNetCode() == code and p.GetDrillSize().x == 0
                and (p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu))]
        done = todo = 0
        for pad in pads:
            a = pad.GetPosition()
            if any(s.Contains(a) for s in skip):
                continue
            bb = pad.GetBoundingBox()
            if any(bb.Contains(pcbnew.VECTOR2I(x, y)) for x, y in ends):
                continue
            todo += 1
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
                for step in range(30):
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
            if not best:
                print(f"fan-out {name}: no room by {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}")
                continue
            e = best[1]
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(a)
            t.SetEnd(e)
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
    copper = [l for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
              if board.GetEnabledLayers().Contains(l)]
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


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)
