"""Board solids for the notice (the bay node), from the same sources as the viewer's (tools/pcb_glb.py):
KiCad's STEP export of the board (the KiCad library's models and electronics/lib/3dmodels, through
${KIPRJMOD}), plus a simple body for each part the export leaves without one.  Those are the
footprints KiCad's 3D coverage report (<board>/build/<board>-3d.json, see run.py) lists as
"missing"; without a report, every footprint the stand-in table knows.  The table and the
dimensions are pcb_glb.STANDINS', drawn here as exact solids.

Output, in board coordinates (front-left corner at the origin, y towards the rear, board bottom at
z = 0): parts/<out>.brep, and parts/<out>.json (board size, the side-entry JST PH connectors: the
row cable's plugs, and the stand-ins used); <out> is bay_node for the bay node, whose json the
notice reads as node.json.

    NODE_BUILD=1 NODE_PCB=<board>.kicad_pcb NODE_STEP=<board>.step NODE_OUT=<out> [NODE_COVERAGE=<board>-3d.json] freecadcmd node.py
"""
import json
import math
import os
import re
import sys

import FreeCAD as App
import Part
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.environ.get("NOTICE_BUILD") or os.path.join(HERE, "..", "..", "mechanical", "build", "notice")
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(REPO, "electronics", "tools"))
import sexp  # noqa: E402

TOP = 1.6


# ------------------------------------------------------------------ stand-ins
# Each builder works in the footprint's own frame turned right-handed (x right, y = -KiCad y, z up
# from the board top), as pcb_glb's, and returns one solid.
def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def stadium_y(w, h, y0, y1, z0):
    """Rounded USB-C outline (w x h in the xz plane), from y0 to y1, its bottom at z0."""
    r, L = h / 2, w - h
    cz = z0 + r
    f = Part.Face(Part.Wire(Part.__sortEdges__([
        Part.LineSegment(V(-L / 2, 0, cz - r), V(L / 2, 0, cz - r)).toShape(),
        Part.Arc(V(L / 2, 0, cz - r), V(w / 2, 0, cz), V(L / 2, 0, cz + r)).toShape(),
        Part.LineSegment(V(L / 2, 0, cz + r), V(-L / 2, 0, cz + r)).toShape(),
        Part.Arc(V(-L / 2, 0, cz + r), V(-w / 2, 0, cz), V(-L / 2, 0, cz - r)).toShape()])))
    f.translate(V(0, y0, 0))
    return f.extrude(V(0, y1 - y0, 0))


def usb_c(n):
    w, h, d = 8.94, 3.16, 7.3                     # HRO TYPE-C-31-M-12 / GCT USB4105, opening at local -y
    return stadium_y(w, h, -d / 2, d / 2, 0).cut(stadium_y(w - 0.6, h - 0.6, -d / 2 - 0.1, -d / 2 + 5.5, 0.3))


def ph_side(n):
    wid, d, h = 2.0 * (n - 1) + 4.0, 7.6, 4.75    # S#B-PH-SM4-TB, opening at local -y
    return box(-wid / 2, wid / 2, -5.0, d - 5.0, 0, h).cut(
        box(-wid / 2 + 0.8, wid / 2 - 0.8, -5.1, 0.5, 1.0, h - 0.9))


def esp32_mini(n):                                # 15.4 x 20.5 module, antenna end at local +y, shield can
    return box(-7.7, 7.7, -10.25, 10.25, 0, 0.8).fuse(box(-6.4, 6.4, -9.65, 3.65, 0.8, 2.45))


def button(n):                                    # TS-1187A, 5.1 x 5.1 x 1.5 + round button
    return box(-2.55, 2.55, -2.55, 2.55, 0, 1.5).fuse(Part.makeCylinder(1.5, 0.5, V(0, 0, 1.5)))


def slide(n):                                     # MSK12C02, lever towards local -y
    return box(-3.35, 3.35, -1.3, 1.3, 0, 1.4).fuse(box(-0.5, 0.5, -2.8, -1.3, 0.3, 1.2))


def ws2812_2020(n):
    return box(-1, 1, -1, 1, 0, 0.84)


def side_led(n):                                  # Kingbright KPA-3010, lens towards local -y
    return box(-1.5, 1.5, -0.5, 0.5, 0, 2.0)


STANDINS = [   # footprint name prefix -> builder(pin count), as tools/pcb_glb.py STANDINS
    ("RF_Module:ESP32-S2-MINI-1", esp32_mini), ("RF_Module:ESP32-S3-MINI-1", esp32_mini),
    ("Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", usb_c),
    ("Connector_USB:USB_C_Receptacle_GCT_USB4105", usb_c),
    ("Connector_JST:JST_PH_S", ph_side),
    ("Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", button),
    ("Button_Switch_SMD:SW_SPDT_Shouhan_MSK12C02", slide),
    ("LED_SMD:LED_WS2812B-2020", ws2812_2020),
    ("LED_SMD:LED_Kingbright_KPA-3010", side_led),
]


# ------------------------------------------------------------------ the board
def footprints(pcb):
    """(ref, footprint name, x, y, rotation, side) of every footprint, KiCad coordinates."""
    out = []
    for fp in sexp.find_all(pcb, "footprint"):
        at = sexp.find(fp, "at")
        ref = next((str(p[2]) for p in sexp.find_all(fp, "property") if str(p[1]) == "Reference"), "")
        side = "top" if str(sexp.find(fp, "layer")[1]) == "F.Cu" else "bottom"
        out.append((ref, str(fp[1]), float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, side))
    return out


def outline(pcb):
    """Board extent from Edge.Cuts: (width, depth); the board's top-left corner is KiCad (0, 0)."""
    xs, ys = [], []
    for kind in ("gr_line", "gr_arc", "gr_rect"):
        for g in sexp.find_all(pcb, kind):
            if str(sexp.find(g, "layer")[1]) != "Edge.Cuts":
                continue
            for key in ("start", "mid", "end"):
                p = sexp.find(g, key)
                if p:
                    xs.append(float(p[1]))
                    ys.append(float(p[2]))
    return max(xs) - min(xs), max(ys) - min(ys)


def placed(solid, x, y, rot, D):
    """Footprint frame -> node frame: node y = D - KiCad y, z from the board's bottom."""
    s = solid.copy()
    s.rotate(V(0, 0, 0), V(0, 0, 1), rot)
    s.translate(V(x, D - y, TOP))
    return s


def missing_refs(path):
    """The top-side references KiCad's export has no body for, or None without a report."""
    if not path or not os.path.exists(path):
        return None
    return {e["ref"] for e in json.load(open(path)) if e["status"] == "missing" and e["side"] == "top"}


def build(pcb_path, step, name, coverage=None):
    pcb = sexp.loads(open(pcb_path, encoding="utf-8").read())
    W, D = outline(pcb)
    only = missing_refs(coverage)
    log = [f"board {W:g} x {D:g}, coverage report: {coverage if only is not None else 'none (stand-ins by footprint name)'}"]
    s = Part.read(step)
    sols = []
    for so in s.Solids:
        so = so.copy()
        so.translate(V(0, D, 0))                  # STEP y = -KiCad y
        sols.append(so)
    used, bare, ph = [], [], []
    for ref, name, x, y, rot, side in footprints(pcb):
        builder = next((b for prefix, b in STANDINS if name.startswith(prefix)), None)
        m = re.search(r"_1x(\d+)", name)
        pins = int(m.group(1)) if m else 0
        if name.startswith("Connector_JST:JST_PH_S") and side == "top":
            a = math.radians(rot)                  # the opening: local -y, 5 mm from the origin
            ph.append({"ref": ref, "pins": pins, "mouth": [x + 5.0 * math.sin(a), D - y - 5.0 * math.cos(a), TOP + 4.75 / 2],
                       "out": [round(math.sin(a), 6), round(-math.cos(a), 6)]})
        if only is not None and ref not in only:
            continue
        if builder is None or side != "top":
            if only is not None:
                bare.append(f"{ref} {name}")
            continue
        sols.append(placed(builder(pins), x, y, rot, D))
        used.append(ref)
    log.append(f"{len(s.Solids)} STEP solids, stand-ins: {' '.join(sorted(used)) or 'none'}")
    if bare:
        log.append("NO BODY (add a stand-in to STANDINS here and in tools/pcb_glb.py): " + ", ".join(bare))
    c = Part.makeCompound(sols)
    c.exportBrep(os.path.join(BUILD, "parts", f"{name}.brep"))
    json.dump({"size": [W, D], "top": TOP, "ph": ph, "standins": sorted(used), "missing": bare},
              open(os.path.join(BUILD, "parts", "node.json" if name == "bay_node" else f"{name}.json"), "w"), indent=1)
    return c, log


if os.environ.get("NODE_BUILD"):
    name = os.environ.get("NODE_OUT", "bay_node")
    c, log = build(os.environ["NODE_PCB"], os.environ.get("NODE_STEP") or os.path.join(BUILD, "parts", "bay-node.step"),
                   name, os.environ.get("NODE_COVERAGE"))
    open(os.path.join(BUILD, "parts", f"{name}_log.txt"), "w").write(
        "\n".join(log) + f"\nsolids {len(c.Solids)} faces {len(c.Faces)} bb {c.BoundBox}\n")
