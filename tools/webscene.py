"""Build the 3D viewer assets: site/assets/parts.glb + site/assets/rack.json.

parts.glb holds ONE mesh per printed part type (simplified for the web);
rack.json says where every instance goes, plus the procedural stand-ins
(dev boards, node PCBs, camera boards), the drag chains and every cable as a curve.
Units: millimetres, Z up (the viewer converts to three.js' Y-up).
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import trimesh

import plate_layout
import rackcfg
from build import BUILD, MECH, REPO, SITE_ASSETS, openscad_cmd

WEB_PARTS = {
    # name: (scad, defines)
    "tray": ("parts/tray.scad", {"PART": "tray"}),
    "drawer": ("parts/drawer.scad", {}),
    "drawer_sled": ("parts/drawer.scad", {"PART": "sled"}),
    "x4_cradle": ("parts/x4_cradle.scad", {"PART": "cradle"}),        # the standing DATA ×4 v2's (drawer coordinates)
    "drawer_block": ("parts/drawer.scad", {"PART": "block"}),
    "floor_plate": ("parts/tray.scad", {"PART": "floor_plate"}),
    "cap_plate": ("parts/tray.scad", {"PART": "cap_plate"}),
    "chain_foot": ("parts/chain_parts.scad", {"PART": "foot"}),
    "chain_anchor": ("parts/chain_parts.scad", {"PART": "anchor"}),
    "camera_pod": ("parts/camera_pod.scad", {"PART": "pod"}),
    "camera_diffuser": ("parts/camera_pod.scad", {"PART": "diffuser"}),
    "mega_camera": ("parts/camera_pod.scad", {"PART": "mega"}),
    "podpcb": ("parts/camera_pod.scad", {"PART": "podpcb"}),
    "podpcb_parts": ("parts/camera_pod.scad", {"PART": "podpcb_parts"}),
    "plate": ("parts/board_plate.scad", {}),                                 # the honeycomb plate
    "power_box_base": ("parts/power_box.scad", {"PART": "base"}),
    "power_box_lid": ("parts/power_box.scad", {"PART": "lid"}),
    "power_box_labels": ("parts/power_box.scad", {"PART": "labels"}),
    "power_box_lid_labels": ("parts/power_box.scad", {"PART": "lid_labels"}),
}

# USB cable plugs (mm), the single source for parts/usb_plugs.scad (which draws them) and for the
# cable routing (plug_exit): metal shell SW × SH × SL (SB: a trapezoid's narrow side), overmold
# W × H × L for a straight plug, D deep along the axis and TOP above it for a right-angle one,
# strain relief REL long, RD its diameters.  USB-C after the USB-IF reference overmold.  A micro-B /
# mini-B 90° adapter (male to female, its female facing up) is AW wide, AD deep, its mouth ATOP above
# the axis.
USB_PLUGS = {
    "usb-c":   dict(SHELL="pill", SW=8.3, SH=2.5, SL=6.65, SB=0,  W=12.4, H=7.0, L=20, D=7.0, TOP=15.5, REL=8, RD=[5.4, 4.2]),
    "micro-b": dict(SHELL="trap", SW=6.9, SH=1.85, SL=5.6, SB=5.4, W=11.0, H=7.0, L=18, D=7.0, TOP=14.0, REL=7, RD=[5.0, 4.0],
                    AW=11.5, AD=8.0, ATOP=11.5),
    "mini-b":  dict(SHELL="trap", SW=7.7, SH=3.9, SL=6.0, SB=6.2, W=11.5, H=8.5, L=18, D=8.0, TOP=15.0, REL=7, RD=[5.0, 4.0],
                    AW=12.5, AD=9.0, ATOP=13.0),
}
for _t, _d in USB_PLUGS.items():
    WEB_PARTS[f"usbplug_{_t}_shell"] = ("parts/usb_plugs.scad", {**_d, "PIECE": "shell"})
    for _style in ("straight", "right"):
        WEB_PARTS[f"usbplug_{_t}_{_style}"] = ("parts/usb_plugs.scad", {**_d, "STYLE": _style, "PIECE": "mold"})
    if "ATOP" in _d:
        for _piece in ("mold", "metal"):
            WEB_PARTS[f"usbplug_{_t}_adapter_{_piece}"] = ("parts/usb_plugs.scad", {**_d, "STYLE": "adapter", "PIECE": _piece})
WEB_PARTS["ph5_plug"] = ("parts/usb_plugs.scad", {"STYLE": "ph5"})
WEB_PARTS["ph8_plug"] = ("parts/usb_plugs.scad", {"STYLE": "ph8"})
# the node's J7 (DATA, JST PH 8 side entry on the right edge, at config/rack.yaml › pcb.bay_node.right.data): the
# plug goes in from +x, its mouth at the board's edge, 2.8 mm over the top (as on the port board)
NODE_J7_Z = 2.8
NODE_J6_H = 8.0     # J6 (camera, JST PH 8 vertical, at config/rack.yaml › pcb.bay_node.cam): mated height

# Dupont jumper wires, female–female, on 2.54 mm pin headers soldered pins up (boards.yaml › headers, the DATA
# ×4's): the housing (W square, L long, a slight shoulder at its back), the crimp's insulation barrel out of it
# (CRIMP), then a 26 AWG wire R in radius, its (EI / w)^⅓ SAG (stiff for its weight: jumpers stand in loops) and
# its tightest bend MIN_R; the wire runs straight on out of the crimp for LEAD before it bends (the barrel and
# the insulation it grips).  site/app.js draws the housing and crimp from these.  A header: a BASE high plastic
# strip, its pins PIN above it (a housing's mouth rests on the strip) and TAIL below the board.
DUPONT = dict(W=2.5, L=14.0, SHOULDER=1.6, CRIMP=1.8, R=0.65, SAG=80.0, MIN_R=4.0, STEP=5.0, LEAD=5.0)
HEADER = dict(BASE=2.5, PIN=6.0, TAIL=3.0, PITCH=2.54)
# the usual rainbow, used for meaning: GND black, VREF red, RESET brown, BOOT green, the signals by bus
DUPONT_COLOURS = {"black": "#1d1d1f", "brown": "#6e4127", "red": "#c62828", "orange": "#ef6c00",
                  "yellow": "#f2c40f", "green": "#2e8b3d", "blue": "#1f5fc8", "violet": "#7b3fb5",
                  "grey": "#8c8c8c", "white": "#ececec"}
STRIP_ORDER = ("brown", "red", "orange", "yellow", "green", "blue", "violet", "grey", "white", "black")   # the
# usual rainbow strip's wires side by side: wires torn off together keep that order in their ribbon
HEADER_PIN_COLOUR = {"GND": "black", "VREF": "red", "RESET": "brown", "BOOT": "green", "P1": "orange",
                     "P2": "yellow", "P3": "blue", "P4": "violet", "P5": "grey", "P6": "white", "P7": "green",
                     "P8": "brown"}
JUMPER_LENGTHS = (200, 300)   # mm, end to end: the 20 cm strips, 30 cm where 20 cm does not reach (the usual sizes)


# the row cable's tie anchors in the tray (tray.scad › JUMPER_TIES: carrier x, y of their centre)
JUMPER_TIES = [(118.0, 7.25), (150.0, 7.25)]


def x4_port_x(rack, n: int) -> float:
    """Drawer x of the DATA ×4 port n (1-4): config/rack.yaml › pcb.data_port_x4 (drawer.scad › port_xs(4))."""
    x4 = rack.raw["pcb"]["data_port_x4"]
    return x4["x0"] + x4["usb"][n - 1]


def dataport_parts(rack) -> dict:
    """The DATA port board's stand-in (parts/usb_plugs.scad), sized from config/rack.yaml › pcb.data_port, and
    the DATA ×4 one (pcb.data_port_x4; its USB-C at x 0, placed once per port)."""
    dp = rack.raw["pcb"]["data_port"]
    defs = {"STYLE": "dataport", "BW": dp["size"][0], "BD": dp["size"][1], "BT": dp["thickness"],
            "HOLES": dp["holes"], "USBX": dp["usb"], "PHX": dp["ph"]}
    out = {f"dataport_{k}": ("parts/usb_plugs.scad", {**defs, "PIECE": k}, None) for k in ("pcb", "usb", "ph")}
    q = rack.raw["pcb"]["data_port_x4"]
    x4 = {**defs, "BW": q["size"][0], "BD": q["size"][1], "BT": q["thickness"], "HOLES": q["holes"], "USBX": 0,
          "PHR": q["lead"]}                         # its PH 8 on the right edge, its mouth out of it
    out.update({f"dataport_{k}_x4": ("parts/usb_plugs.scad", {**x4, "PIECE": k}, None) for k in ("pcb", "usb", "ph")})
    return out


def header_pins(bd: dict) -> list[tuple[float, float, str]]:
    """A board's header pins (boards.yaml › headers): [(x, y, name)] in its drawing."""
    out = []
    for h in bd.get("headers", []):
        (x, y), (sx, sy) = h["at"], h.get("step", [0, -HEADER["PITCH"]])
        names = h.get("names", [])
        out += [(x + sx * k, y + sy * k, names[k] if k < len(names) else str(k + 1)) for k in range(h["n"])]
    return out


def x4_header_pins(raw: dict, port: int) -> list[tuple[float, float, str]]:
    """The DATA ×4's (v1) header at port 1–4, the 1 × 3 (GND, RESET, BOOT, pcb.data_port_x4.aux): [(x, y,
    name)], KiCad (y from the rear edge)."""
    a = raw["pcb"]["data_port_x4"]["aux"]
    return [(a["pin1"][port - 1] + a["step"][port - 1] * k, a["y"], name) for k, name in enumerate(a["names"])]


def x4v2_header_pins(raw: dict, port: int) -> list[tuple[float, float, str]]:
    """The standing v2's 2 × 6 header at port 1–4, on its front face, pins forward (pcb.data_port_x4_v2): [(board x,
    drawer z, name)], odd pins on the lower row."""
    h = raw["pcb"]["data_port_x4_v2"]["header"]
    x0 = h["x"][port - 1] - (h["cols"] - 1) * HEADER["PITCH"] / 2
    return [(x0 + HEADER["PITCH"] * (k // 2), h["even_z"] if k % 2 else h["odd_z"], name)
            for k, name in enumerate(h["names"])]


# The standing v2's main parts, until its KiCad model exists: the study's banded placement on 100 × 70
# (docs/data-x4-v2-layout-options.md), every face's parts in bands across the board.  (face: -1 the front, towards
# the DUTs, +1 the rear; board x of the body's left end, drawer z of its bottom, w along x, h along z, its height
# off the face, colour).  Per port at its USB-C's x (cx); then the shared parts.
IC, ARRAY, METAL = "#1b1b1d", "#2b2b2d", "#c9ccd1"


def x4v2_parts(usb_x) -> list[tuple]:
    out = []
    for cx in usb_x:
        out += [(-1, cx - 4.5, 18.0, 3.0, 3.0, 1.0, IC),                                         # INA226
                (-1, cx - 1.0, 18.7, 1.6, 3.2, 0.6, "#3c3c3e"),                                  # 100 mR shunt
                (-1, cx + 1.6, 18.1, 2.9, 2.8, 1.1, IC),                                         # TPS2553
                (-1, cx + 5.2, 8.6, 2.8, 2.9, 1.1, IC),                                          # USBLC6
                (+1, cx - 2.25, 30.75, 4.5, 2.5, 0.9, IC),                                       # LSF0108
                (+1, cx - 4.5, 26.0, 2.5, 1.0, 0.55, IC), (+1, cx + 2.0, 26.0, 2.5, 1.0, 0.55, IC),  # TPD4E05U06 ×2
                *[(+1, cx - 5.2 + 2.6 * k, 35.0, 2.0, 1.0, 0.45, ARRAY) for k in range(4)]]       # 0402 × 4 arrays
    return out + [(-1, 60.0, 52.0, 9.0, 9.0, 0.9, IC),                                           # USB2517 hub
                  (-1, 71.0, 56.0, 3.2, 2.5, 0.8, METAL),                                        # 24 MHz crystal
                  (-1, 76.0, 55.8, 2.9, 2.8, 1.1, IC),                                           # LDO
                  (-1, 81.0, 55.8, 3.0, 3.0, 0.9, IC), (-1, 85.5, 55.8, 3.0, 3.0, 0.9, IC),      # TCA6408A ×2
                  (+1, 10.0, 51.0, 10.0, 10.0, 0.9, IC),                                         # RP2354B
                  (+1, 26.0, 53.0, 6.0, 6.0, 0.9, IC), (+1, 36.0, 53.0, 6.0, 6.0, 0.9, IC),      # CH446Q ×2
                  (+1, 46.0, 54.5, 3.0, 3.0, 0.9, IC), (+1, 51.5, 54.6, 2.9, 2.8, 1.1, IC)]      # TCA9534A, charge pump


# Parts whose print orientation differs from their assembly orientation get an
# "assembly" variant rendered with the print rotation undone.
ASSEMBLY_WRAPPERS = {
    "camera_pod": "use <parts/camera_pod.scad>\ninclude <lib/carrier.scad>\npod();\n",
    "chain_foot": "use <parts/chain_parts.scad>\ninclude <lib/carrier.scad>\nfoot();\n",
    "power_box_lid": "use <parts/power_box.scad>\nlid();\n",
    "power_box_lid_labels": "use <parts/power_box.scad>\nlid_labels();\n",
}
# ladders (profile in the frame's side plane, printed flat) and braces (printed flat) stand up in
# frame coordinates; placed by a translation along X only
LADDER_UP = "multmatrix([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])"
BRACE_UP = "multmatrix([[1, 0, 0, 0], [0, 0, -1, PR + BRACE_T], [0, 1, 0, 0], [0, 0, 0, 1]])"

LAYER_H = 0.2       # mm, docs/mechanical.md › Printing


def print_up(name: str) -> list[int]:
    """The build plate's normal in the part's viewer frame (the layer lines run across it):
    LADDER_UP / BRACE_UP turn the print Z into +X / -Y, the camera pod prints upside down
    (rotate([180, 0, 0])), the chain foot on its side (rotate([0, 90, 0])), the rest as placed."""
    if name.startswith("ladder_"):
        return [1, 0, 0]
    if name.startswith("brace_"):
        return [0, -1, 0]
    if name == "camera_diffuser":
        return [0, 0, 1]
    if name.startswith("camera_"):
        return [0, 0, -1]
    if name == "chain_foot":
        return [-1, 0, 0]
    if name in ("power_box_lid", "power_box_lid_labels"):
        return [0, 0, -1]
    return [0, 0, 1]


def panel_parts(rack) -> dict:
    """Ladders and braces of this rack's rows: name -> (scad, defines, wrapper source)."""
    n = len(rack.rows)
    out = {
        "ladder_base": ("parts/ladder.scad", {}, f"use <parts/ladder.scad>\n{LADDER_UP} ladder_base();\n"),
        "ladder_cap": ("parts/ladder.scad", {}, f"use <parts/ladder.scad>\n{LADDER_UP} ladder_cap({n});\n"),
        "brace_base": ("parts/brace.scad", {}, f"include <lib/panels.scad>\nuse <parts/brace.scad>\n{BRACE_UP} brace(-1);\n"),
    }
    for k, row in enumerate(rack.rows):
        rid = row["id"].lower()
        out[f"ladder_{rid}"] = ("parts/ladder.scad", {}, f"use <parts/ladder.scad>\n{LADDER_UP} ladder_row({k});\n")
        out[f"brace_{rid}"] = ("parts/brace.scad", {}, f"include <lib/panels.scad>\nuse <parts/brace.scad>\n{BRACE_UP} brace({k});\n")
    return out


def render_web_stl(name: str, scad: str, defines: dict, fn: int = 28, sub: str = "web", wrapper_src: str | None = None) -> Path:
    out = BUILD / sub / f"{name}.stl"
    out.parent.mkdir(parents=True, exist_ok=True)
    src = scad
    wrapper_src = wrapper_src or ASSEMBLY_WRAPPERS.get(name)
    if wrapper_src:
        # wrapper lives in build/<sub>: make its relative includes resolve from mechanical/
        wrapper = MECH / "build" / sub / f"_{name}.scad"
        wrapper.write_text(wrapper_src.replace("<parts/", "<../../parts/").replace("<lib/", "<../../lib/"), encoding="utf-8")
        src = wrapper.relative_to(MECH).as_posix()
    base = openscad_cmd()
    docker = base[0] == "docker"
    cmd = base + ["--export-format", "binstl", "-D", f"$fn={fn}",
                  "-o", (f"build/{sub}/{name}.stl" if docker else str(out))]
    for k, v in defines.items():
        cmd += ["-D", f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"]
    cmd.append(src if docker else str(MECH / src))
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=MECH)
    if p.returncode != 0 or not out.exists():
        raise RuntimeError(f"OpenSCAD failed for {name}:\n{p.stderr[-1500:]}")
    return out


def build_parts_glb(rack, boards: dict, hq: bool = False) -> dict:
    """Render every web part (in parallel) and pack them into one GLB.

    hq=True is for the Blender renders: $fn=64, no decimation (it turns the plates' hexagon
    holes irregular), written to render/parts-hq.glb instead of the viewer's parts.glb."""
    import concurrent.futures as cf

    parts = {n: (s, d, None) for n, (s, d) in WEB_PARTS.items()}
    parts.update(panel_parts(rack))
    parts.update(dataport_parts(rack))
    for name, defines in plate_layout.peg_parts(boards).items():     # the honeycomb plate's pegs
        parts[name] = ("parts/pegs.scad", defines, None)
    for b in rack.bays():                      # a bay that keeps the former plates (`plate: boards`)
        if rack.duts(b.id) and rack.plate_kind(b.id) == "boards":
            if rack.is_multi(b.id):
                parts[f"plate_bay_{b.id.lower()}"] = ("parts/board_plate.scad", {"BAY": b.id}, None)
            else:
                parts[f"plate_{rack.duts(b.id)[0].board}"] = ("parts/board_plate.scad", {"BOARD": rack.duts(b.id)[0].board}, None)
    fn, sub = (64, "hq") if hq else (28, "web")
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(render_web_stl, n, s, d, fn, sub, w): n for n, (s, d, w) in parts.items()}
        stls = {futs[f]: f.result() for f in cf.as_completed(futs)}
    scene = trimesh.Scene()
    stats = {}
    for name in sorted(stls):
        m = trimesh.load(stls[name], force="mesh")
        m.merge_vertices()
        if len(m.faces) > 20000 and not hq:
            try:
                m = m.simplify_quadric_decimation(face_count=20000)
            except Exception:  # fast_simplification missing: keep full mesh
                pass
        stats[name] = len(m.faces)
        scene.add_geometry(m, node_name=name, geom_name=name)
    dst = REPO / "render" / "parts-hq.glb" if hq else SITE_ASSETS / "parts.glb"
    dst.parent.mkdir(parents=True, exist_ok=True)
    scene.export(dst)
    return stats


# ------------------------------------------------------------------ USB cables
CABLE_BEND_R = 12.0        # bend radius of a thin USB cable
CABLE_MIN_R = 10.0         # and the tightest it takes without kinking
# The highest a DUT cable's arch may rise above its row's origin: a camera pod hangs from the tray above
# down to 120 mm (that tray at 155), just in front of the arch with the drawer closed and over it while
# the drawer slides.  A longer cable's spare length is looped flat on the plate's hooks instead.
ARCH_TOP_MAX = 105.0

# ------------------------------------------------------------------ boards: real models and screens
def board_frame(bd: dict, pts):
    """Points of a board's drawing (boards.yaml frame) → the frame the viewer draws it in, turned like
    rackcfg.orient_board() turns the board (debug USB towards the drawer rear, or its right wall)."""
    return rackcfg.orient_board({**bd, "holes": [list(p) for p in pts]})["holes"]


def board_model(bid: str, bd: dict) -> dict | None:
    """site/assets/boards/<id>.glb (the maker's model, normalised by tools/board_models.py and slimmed for the
    web) and the matrix that turns it like the stand-in: three points of its frame mapped, z unchanged."""
    if not (SITE_ASSETS / "boards" / f"{bid}.glb").exists():
        return None
    o, x, y = board_frame(bd, [(0, 0), (1, 0), (0, 1)])
    ex, ey = np.subtract(x, o), np.subtract(y, o)
    m = [[ex[0], ey[0], 0, o[0]], [ex[1], ey[1], 0, o[1]], [0, 0, 1, 0], [0, 0, 0, 1]]
    return {"url": f"assets/boards/{bid}.glb", "matrix": [round(float(v), 6) for row in m for v in row],
            "credit": bd.get("model", {}).get("credit", "")}


def board_screen(bd: dict) -> dict | None:
    """A board's display (boards.yaml › screen: the active area's bottom-left corner and size in the drawing,
    `top`: where the image's top edge points in the drawing, +y (default) or -x, the glass's height above the
    PCB's underside): the image's bottom-left, bottom-right and top-left corners in the viewer's frame, for a
    live LVGL texture."""
    sc = bd.get("screen")
    if not sc:
        return None
    (x, y), (w, h) = sc["at"], sc["size"]
    corners = {"+y": [(x, y), (x + w, y), (x, y + h)],            # landscape: width along +x
               "-x": [(x + w, y), (x + w, y + h), (x, y)]}        # turned: width along +y, top towards -x
    bl, br, tl = board_frame(bd, corners[sc.get("top", "+y")])
    return {"bl": bl, "br": br, "tl": tl, "z": sc["z"], "px": sc["px"], "demo": sc.get("demo", "music")}


def plug_exit(end):
    """Where the cable leaves a plug's strain relief and which way: a straight plug out of its back,
    a right-angle one out of its top.  end = {at: receptacle face, dir: into it, up, type, style}."""
    at, d = np.array(end["at"], float), np.array(end["dir"], float)
    if end["type"] in ("ph5", "ph8"):                       # a JST PHR-n: its wires leave its back
        return at - d * 6.0, -d
    if end["type"] == "dupont":                             # out of the crimp at the housing's back
        return at - d * (DUPONT["L"] + DUPONT["CRIMP"]), -d
    up = np.array(end.get("up", (0, 0, 1)), float)
    p = USB_PLUGS.get(end["type"], USB_PLUGS["usb-c"])
    if end.get("style") == "right":
        return at - d * p["D"] / 2 + up * (p["TOP"] + p["REL"]), up
    return at - d * (p["L"] + p["REL"]), -d


def arch_cable(a, b, length, r=CABLE_BEND_R, step=2.5, top_max=ARCH_TOP_MAX):
    """arch_between() the two plugs' exits (both right-angle, their cables leaving upwards)."""
    pa, _ = plug_exit(a)
    pb, _ = plug_exit(b)
    return arch_between(pa, pb, length, r, step, top_max)


def side_arch_cable(a, b, length, r=CABLE_BEND_R, step=2.5, top_max=ARCH_TOP_MAX):
    """Plug a right-angle (its cable up), plug b straight and level (a board's USB facing the side
    wall with room for it, the F746G-DISCO): out of b's relief, a bend of radius r up, then the arch
    over to a."""
    pa, _ = plug_exit(a)
    p0, d = plug_exit(b)
    z = np.array([0.0, 0.0, 1.0])
    bend = [p0 + d * r * math.sin(t) + z * r * (1 - math.cos(t)) for t in np.linspace(0, math.pi / 2, 8)]
    pts, short = arch_between(pa, bend[-1], length - math.pi / 2 * r, r, step, top_max)
    return pts + [[round(float(c), 2) for c in p] for p in reversed(bend[:-1])], short


def arch_between(pa, pb, length, r=CABLE_BEND_R, step=2.5, top_max=ARCH_TOP_MAX):
    """A short cable between two upward exits pa, pb (right-angle plugs' reliefs): straight up out of
    each, a bend of radius r over towards the other, across, a bend down.  The
    arch stands in the vertical plane through both exits and is as tall as the cable is long
    (`length` = the free length between the two strain reliefs).  Returns (points, shortfall): the
    cable could not be shorter than the arch with no straight legs; shortfall > 0 means it is."""
    z = np.array([0.0, 0.0, 1.0])
    h = (pb - pa) - z * (pb - pa)[2]
    dist = float(np.linalg.norm(h))
    u = h / max(dist, 1e-9)
    r = min(r, dist / 2) if dist < 2 * r else r          # very close plugs: a tighter, still smooth arch
    lo = max(pa[2], pb[2]) + r + 2.0                      # the top of the arch, at least 2 mm of leg
    top = (length - math.pi * r - (dist - 2 * r) + 2 * r + pa[2] + pb[2]) / 2
    shortfall = max(0.0, lo - top) * 2
    top = min(max(top, lo), max(lo, top_max))              # spare length beyond top_max: looped on the plate
    pts = []

    def leg(p, z0, z1):
        n = max(1, int(abs(z1 - z0) / step))
        return [p + z * (z0 + (z1 - z0) * k / n - p[2]) for k in range(n + 1)]

    def arc(c, a0, a1):
        n = max(4, int(abs(a1 - a0) * r / step))
        return [c + (u * math.cos(a0 + (a1 - a0) * k / n) + z * math.sin(a0 + (a1 - a0) * k / n)) * r for k in range(n + 1)]

    ca = pa + u * r + z * (top - r - pa[2])
    cb = pb - u * r + z * (top - r - pb[2])
    pts += leg(pa, pa[2], top - r)
    pts += arc(ca, math.pi, math.pi / 2)[1:]
    n = max(1, int(np.linalg.norm(cb - ca) / step))
    pts += [ca + (cb - ca) * k / n + z * r for k in range(1, n)]
    pts += arc(cb, math.pi / 2, 0)
    pts += leg(pb, top - r, pb[2])[1:]
    return [[round(float(c), 2) for c in p] for p in pts], round(shortfall, 1)


def flat_cable(a, b, length, r=CABLE_BEND_R, step=2.5):
    """A short cable between two straight plugs at right angles in plan (the DATA socket's, pointing
    to the rear, and a board's turned to the side wall): straight out of each strain relief, one
    bend of radius r where the two lines meet, sloping from one plug's height to the other's.  The
    spare length lies on the plate (not drawn).  Returns (points, shortfall) like arch_cable."""
    pa, da = plug_exit(a)
    pb, db = plug_exit(b)
    # where the two cable lines meet in plan: pa + t·da = pb + s·db
    m = np.array([[da[0], -db[0]], [da[1], -db[1]]])
    t, s = np.linalg.solve(m, (pb - pa)[:2])
    c = pa + da * t
    c[2] = 0.0
    corner = min(t, s)
    r = min(r, max(corner, 0.0))
    q = c - da * r - db * r
    plan = [pa, c - da * r]
    plan += [q + (db * math.cos(th) + da * math.sin(th)) * r for th in np.linspace(0, math.pi / 2, 9)[1:]]
    plan += [pb]
    plan = [np.array([p[0], p[1], 0.0]) for p in plan]
    dense = [plan[0]]                    # the straight runs filled in, every `step` mm
    for p0, p1 in zip(plan, plan[1:]):
        n = max(1, int(np.linalg.norm(p1 - p0) / step))
        dense += [p0 + (p1 - p0) * k / n for k in range(1, n + 1)]
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
    total = float(run[-1])
    pts = [p + np.array([0.0, 0.0, pa[2] + (pb[2] - pa[2]) * d / total]) for p, d in zip(dense, run)]
    shortfall = max(0.0, total - length) + max(0.0, CABLE_MIN_R - corner) * 2   # a kink counts as too short
    return [[round(float(v), 2) for v in p] for p in pts], round(shortfall, 1)


def s_cable(a, b, length, step=2.5):
    """A short cable between two straight plugs facing each other (the DATA socket's, pointing to the rear,
    and a board's USB facing the port wall with room for a straight plug): out of each strain relief in its
    own direction, an S in plan between them (a cubic, its two control points half the gap out), sloping
    from one plug's height to the other's.  The spare length lies on the plate (not drawn).  Returns
    (points, shortfall) like arch_cable; a bend tighter than CABLE_MIN_R counts as too short."""
    pa, da = plug_exit(a)
    pb, db = plug_exit(b)
    gap = abs(float(np.dot(pb - pa, da)))
    c = [pa, pa + da * gap / 2, pb + db * gap / 2, pb]
    n = max(8, int(np.linalg.norm(pb - pa) / step))
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    plan = (1 - t) ** 3 * c[0] + 3 * (1 - t) ** 2 * t * c[1] + 3 * (1 - t) * t ** 2 * c[2] + t ** 3 * c[3]
    d1 = 3 * ((1 - t) ** 2 * (c[1] - c[0]) + 2 * (1 - t) * t * (c[2] - c[1]) + t ** 2 * (c[3] - c[2]))
    d2 = 6 * ((1 - t) * (c[2] - 2 * c[1] + c[0]) + t * (c[3] - 2 * c[2] + c[1]))
    bend = np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0])
    r_min = float(np.min(np.linalg.norm(d1[:, :2], axis=1) ** 3 / np.maximum(bend, 1e-9)))
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(plan[:, :2], axis=0), axis=1))])
    total = float(run[-1])
    pts = [np.array([p[0], p[1], pa[2] + (pb[2] - pa[2]) * s / total]) for p, s in zip(plan, run)]
    shortfall = max(0.0, total - length) + max(0.0, CABLE_MIN_R - r_min) * 2
    return [[round(float(v), 2) for v in p] for p in pts], round(shortfall, 1)


CABLE_R = 1.9              # a thin USB cable's radius (as the viewer draws it)
CABLE_SAG = 60.0           # (EI / w)^⅓: the length over which its own weight bends a thin USB cable as much as
                           # its stiffness resists (EI ≈ 3·10⁻⁵ N·m², w ≈ 0.15 N/m)
ROD_STEP = 3.0             # the rod's segment length, mm


def _segment_gaps(a0, a1, b0, b1):
    """Distances between every segment a0[i]→a1[i] and every b0[j]→b1[j] (closest points, clamped)."""
    d1, d2 = (a1 - a0)[:, None, :], (b1 - b0)[None, :, :]
    r = a0[:, None, :] - b0[None, :, :]
    a, e = np.sum(d1 * d1, axis=2), np.sum(d2 * d2, axis=2)
    b, c, f = np.sum(d1 * d2, axis=2), np.sum(d1 * r, axis=2), np.sum(d2 * r, axis=2)
    den = a * e - b * b
    s = np.where(den > 1e-12, np.clip((b * f - c * e) / np.maximum(den, 1e-12), 0.0, 1.0), 0.0)
    t = (b * s + f) / np.maximum(e, 1e-12)
    s = np.where(t < 0, np.clip(-c / np.maximum(a, 1e-12), 0.0, 1.0), np.where(t > 1, np.clip((b - c) / np.maximum(a, 1e-12), 0.0, 1.0), s))
    t = np.clip(t, 0.0, 1.0)
    return np.linalg.norm(r + d1 * s[..., None] - d2 * t[..., None], axis=2)


def _resample(pts, n):
    """n + 1 points evenly spaced along a polyline."""
    pts = np.asarray(pts, float)
    run = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    s = np.linspace(0.0, run[-1], n + 1)
    return np.array([np.interp(s, run, pts[:, k]) for k in range(3)]).T


def rod_cable(a, b, length, floor_z=-1e9, ceil_z=1e9, boxes=(), guess=None, avoid=(), outward=None,
              r=CABLE_R, sag=CABLE_SAG, min_r=CABLE_MIN_R, step=None, push=200.0):
    """A cable as it really lies between two plugs: a rod exactly `length` long (the free length between the
    strain reliefs), leaving each relief along its plug's axis, in the shape of least energy (bending, with
    its own weight: an elastica), above floor_z, under ceil_z, out of `boxes` ((lo, hi) corners: boards,
    walls), off itself and the cables in `avoid` (their points, or (points, radius) for a cable thinner or thicker
    than this one), and nowhere tighter than min_r.  r, sag, min_r: the cable's radius, its (EI / w)^⅓ and its
    tightest bend (a thin USB cable's by default; a Dupont wire's: DUPONT); step, the segments' length
    (ROD_STEP by default; a jumper's 5 mm: the shape barely changes, the solve is 8 times faster); push, how hard
    it is kept off boxes and other cables (a penalty's weight: a ribbon's free wire ends need more).  Its spare
    length starts out bowed away from `outward` (an x, y: the bay's middle), so neighbours bulge apart.  SLSQP (scipy) on the segments' directions: the length
    is exact by construction.  `guess`: a path to start from (another route's points).  Returns (points,
    shortfall, note): shortfall > 0 when the plugs are too far apart for the cable, or no shape reaching both
    was found (the guess is returned then); note says what is wrong with a shape that was found (a cable too
    long for its gap bends tighter than min_r, or one that touches a board), "" when nothing is."""
    from scipy.optimize import minimize
    pa, da = a if isinstance(a, tuple) else plug_exit(a)     # or (point, direction out of the end) for either end
    pb, db = b if isinstance(b, tuple) else plug_exit(b)
    ta, tb = da / np.linalg.norm(da), -db / np.linalg.norm(db)
    n = int(np.clip(round(length / (step or ROD_STEP)), 12, 72))
    h = length / n
    reach = float(np.linalg.norm(pb - pa))
    start = np.array(guess if guess is not None else [pa, pb], float)
    if reach > length - h:
        return [[round(float(v), 2) for v in p] for p in start], round(reach - length + h, 1), ""
    # the start: the guess, bowed sideways and up until it is as long as the cable
    path = _resample(start, n)
    chord = pb - pa
    side = np.cross(chord, [0.0, 0.0, 1.0])
    side = side / (np.linalg.norm(side) or 1.0)
    if outward is not None and np.dot(side[:2], (pa + pb)[:2] / 2 - np.asarray(outward, float)[:2]) < 0:
        side = -side
    bow = (side + np.array([0.0, 0.0, 0.6])) / np.linalg.norm(side + np.array([0.0, 0.0, 0.6]))
    bump = np.sin(np.linspace(0.0, math.pi, n + 1))[:, None] * bow
    lo, hi = 0.0, length

    def plen(amp):
        q = path + bump * amp
        return float(np.sum(np.linalg.norm(np.diff(q, axis=0), axis=1)))
    if plen(0.0) < length:
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if plen(mid) < length else (lo, mid)
        path = path + bump * lo
    t0 = np.diff(path, axis=0)
    t0 /= np.linalg.norm(t0, axis=1)[:, None]
    x0 = np.concatenate([np.arctan2(t0[1:-1, 1], t0[1:-1, 0]), np.arcsin(np.clip(t0[1:-1, 2], -1, 1))])
    m = n - 2
    gap = r + 0.2                    # a resting cable touches what holds it: 0.2 mm so that the checks see contact
    boxes = [(np.asarray(lo_, float) - gap, np.asarray(hi_, float) + gap) for lo_, hi_ in boxes]

    def tangents(x):
        th, ph = x[:m], x[m:]
        mid = np.stack([np.cos(ph) * np.cos(th), np.cos(ph) * np.sin(th), np.sin(ph)], axis=1)
        return np.vstack([ta, mid, tb])

    def nodes(t):
        return pa + h * np.vstack([np.zeros(3), np.cumsum(t, axis=0)])

    box_lo = np.array([b_[0] for b_ in boxes], float).reshape(-1, 3)
    box_hi = np.array([b_[1] for b_ in boxes], float).reshape(-1, 3)

    def inside(p):
        if not len(box_lo):
            return np.zeros(len(p))
        d = np.minimum(p[:, None, :] - box_lo[None], box_hi[None] - p[:, None, :]).min(axis=2)
        return np.maximum(d.max(axis=1), 0.0)

    far = np.triu(np.ones((n, n), bool), k=max(3, int(math.ceil(2 * r / h)) + 2))
    others = [(np.asarray(q[0], float), float(q[1])) if isinstance(q, tuple) else (np.asarray(q, float), CABLE_R)
              for q in avoid]
    others = [(q, rq) for q, rq in others if len(q) > 1]

    def contact(p):
        """How far the cable runs into itself and into the other cables: segment to segment, 2 radii apart."""
        a0, a1 = p[:-1], p[1:]
        pen = float(np.sum(np.clip(2 * r - _segment_gaps(a0, a1, a0, a1)[far], 0.0, None) ** 2))
        for q, rq in others:
            gaps = _segment_gaps(a0[1:-1], a1[1:-1], q[:-1], q[1:])
            pen += float(np.sum(np.clip(r + rq - gaps, 0.0, None) ** 2))
        return pen

    def energy(x):
        t = tangents(x)
        p = nodes(t)
        bend = float(np.sum(np.diff(t, axis=0) ** 2)) / h
        weight = h * float(np.sum(p[1:-1, 2] - p[0, 2])) / sag ** 3
        return bend + weight + push * (float(np.sum(inside(p[1:-1]) ** 2)) + contact(p))

    cons = [{"type": "eq", "fun": lambda x: nodes(tangents(x))[-1] - pb},
            {"type": "ineq", "fun": lambda x: nodes(tangents(x))[1:-1, 2] - (floor_z + gap)},
            {"type": "ineq", "fun": lambda x: (ceil_z - r) - nodes(tangents(x))[1:-1, 2]},
            {"type": "ineq", "fun": lambda x: (h / min_r) ** 2 - np.sum(np.diff(tangents(x), axis=0) ** 2, axis=1)}]
    res = minimize(energy, x0, method="SLSQP", constraints=cons, options={"maxiter": 400, "ftol": 1e-7})
    t = tangents(res.x)
    p = nodes(t)
    miss = float(np.linalg.norm(p[-1] - pb))
    if miss > 0.5:                                         # no shape found that reaches: the start, flagged
        return [[round(float(v), 2) for v in q] for q in start], round(miss, 1), "no rest shape found"
    p[-1] = pb
    notes = []
    turn = np.linalg.norm(np.diff(t, axis=0), axis=1)
    if turn.size and h / max(float(turn.max()), 1e-9) < min_r - 0.5:
        notes.append(f"too long for the gap: it bends to R {h / float(turn.max()):.0f} mm")
    if float(inside(p[1:-1]).max(initial=0.0)) > 0.5:
        notes.append("it touches a board or a wall")
    if contact(p) > 0.01:
        notes.append("it runs into itself or another cable")
    return [[round(float(v), 2) for v in q] for q in p], 0.0, "; ".join(notes)


def rounded_path(pts, r, step=2.0):
    """A polyline with its corners rounded (a quadratic curve within r of each corner): a flexible lead."""
    pts = [np.array(p, float) for p in pts]
    pts = [p for k, p in enumerate(pts) if k == 0 or np.linalg.norm(p - pts[k - 1]) > 1e-6]   # no repeated corner
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, b, c = pts[k - 1], pts[k], pts[k + 1]
        rk = min(r, np.linalg.norm(b - a) / 2, np.linalg.norm(c - b) / 2)
        p0 = b + (a - b) / np.linalg.norm(a - b) * rk
        p1 = b + (c - b) / np.linalg.norm(c - b) * rk
        out += [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1 for t in np.linspace(0, 1, 7)]
    out.append(pts[-1])
    dense = [out[0]]
    for p0, p1 in zip(out, out[1:]):
        n = max(1, int(np.linalg.norm(p1 - p0) / step))
        dense += [p0 + (p1 - p0) * j / n for j in range(1, n + 1)]
    return [[round(float(v), 2) for v in p] for p in dense]


def lead_to_board(e, mouth, z_low, x_run, depth=7.0, lift=4.0, drop=None):
    """The DATA lead from the drag chain's moving mouth (facing forwards) to the PH plug on the DATA
    board, drawn from the plug: out of it and down through the drawer's cable window, forwards under the
    drawer at z_low (over the camera-pod bosses) along x_run (clear of the chain's fixed run, which the
    drawer slides past), a flattened U-turn in front of the mouth (only `depth` deep: the tray's fascia is
    17 mm ahead of it with the drawer out), raised `lift` at its front so that, the drawer out, it passes
    over the row cable lying on its tie anchors (y ≤ 9.4, z ≤ 10.8), in.  A plug facing the rear (the
    single board's): back out of it, over to x_run in the rear bay, down.  drop = (x, floor z): a plug on
    the board's right edge (the DATA ×4's): out of it, down just behind it into the window's side strip at
    x, then over to x_run under the drawer."""
    p0, d = plug_exit(e)
    if drop is None:
        p1 = p0 + d * 2.0
        head = [p0, p1, np.array([x_run, p1[1], p1[2]]), np.array([x_run, p1[1], z_low])]
    else:
        xd, floor = drop
        head = [p0, p0 + d * 1.0 + np.array([0.0, 0.0, -2.5]), np.array([xd, p0[1], floor + 2.0]),
                np.array([xd, p0[1], z_low]), np.array([x_run, p0[1] - 8.0, z_low])]
    p3 = np.array([x_run, mouth[1] - 1.0, z_low])
    pts = rounded_path(head + [p3], 2.5)
    a, c = (mouth[0] - p3[0]) / 2, np.array([(mouth[0] + p3[0]) / 2, p3[1], 0.0])
    for t in np.linspace(0, math.pi, 16)[1:]:
        z = z_low + (mouth[2] - z_low) * t / math.pi + lift * math.sin(t)
        pts.append([round(float(c[0] - a * math.cos(t)), 2), round(float(c[1] - depth * math.sin(t)), 2), round(z, 2)])
    pts.append([round(float(v), 2) for v in mouth])
    return pts


# the camera pod, in its frame (origin at the ceiling's insert square, carrier axes, z down from the ceiling):
# these mirror parts/camera_pod.scad (MEGA_CASE, the sleeve, POD_GAP...); the pod board's own geometry comes
# from config/rack.yaml › pcb.camera_pod
POD_CASE = (34.0, 34.0, 12.0)           # the Mega's case: x, y, height under the 3 mm plate
POD_XH = (15.0, 6.0, 7.0)               # its XH 6-pin on the case's right side
POD_SLEEVE_Y = 34.0 + 2 * 0.3 + 2 * 1.6 # the sleeve round the case, across y
POD_FACE_Z = -3.0 - 2.0 - 1.6           # the pod board's component face (down)


POD_LENS_DROP = 3.0 + POD_CASE[2] + 6.0 + 9.5  # plate, case, M12 holder, the 120° lens: its tip under the ceiling
POD_LED_Z = POD_FACE_Z - 0.8                    # the 2835 LEDs' face


def camera_view(x0, lens, cp):
    """What site/camera.js needs to light the pod and look through it (the pod's meshes are instances): the
    lens (row i+1 coordinates, its tip POD_LENS_DROP under the ceiling) and the light under the LED row, in
    the lens' frame: the pod board's LED edge behind the sleeve, its LEDs centred on the lens, the diffuser's
    floor 7 mm under them (drawn 0.1 mm lower than the printed one, which hides it)."""
    ly = POD_SLEEVE_Y / 2 + 0.5 + cp["led_y"]       # the LED row, behind the lens axis
    half = (cp["leds"][-1] - cp["leds"][0]) / 2
    leds = [[round(k - (cp["leds"][0] + cp["leds"][-1]) / 2, 2), 0] for k in cp["leds"]]
    return {"lens": [round(x0 + lens[0], 2), lens[1], -POD_LENS_DROP], "instances": True,
            "fov": 120, "aspect": 4 / 3,
            "lights": [{"at": [0, round(ly, 2)], "size": [round(2 * half + 8, 2), 10], "gap": 7, "diffuser": 1.0,
                        "leds": leds, "led_z": round(POD_LED_Z - 0.1, 2)}]}


def camera_lead(j6, x0, row_h, tilt, lens, mount, depth, cp):
    """The camera's PH-8 lead (double-ended), in the bay's row coordinates: up out of the node's J6
    (vertical, at its rear right, between the antenna keep-out and the DATA / AUX plugs), straight back
    along the plenum and out of the tray's rear slot (x 20-80), straight up behind the tray's rear wall (square to
    the row, in the gap behind the drawer: the brace's plane leans back, following it would cost ≈ 6 cm),
    forwards under the ceiling (row i+1's origin is row_h higher, so at y + row_h·sin(tilt),
    z = row_h·cos(tilt) here) between the node and the chain above,
    down behind the pod's plate and into the pod board's J1 from its right.  Returns the lead, its pod
    end, and the Mega's XH → Dupont cable from its case's side round to the board's J2.  cp = config
    pcb.camera_pod."""
    t = math.radians(tilt)
    up_y, up_z = row_h * math.sin(t), row_h * math.cos(t)
    pod = lambda q: (x0 + mount[0] + q[0], up_y + mount[1] + q[1], up_z + q[2])     # pod frame → row
    lx, ly = lens[0] - mount[0], lens[1] - mount[1]
    b0 = (lx - (cp["leds"][0] + cp["leds"][-1]) / 2, ly + POD_SLEEVE_Y / 2 + 0.5)    # the board's KiCad origin
    board = lambda kx, ky, z: pod((b0[0] + kx, b0[1] + ky, z))
    p0, d = plug_exit(j6)
    xs, top = min(p0[0], x0 + 78.0), up_z - 2.0
    zr = 12.0                                         # along the plenum floor, through the rear slot
    yc = depth + 2.5                                  # the climb, just behind the tray's rear wall
    j1 = board(cp["size"][0], cp["lead"], POD_FACE_Z - 2.8)
    end = {"at": [round(v, 2) for v in j1], "dir": [-1, 0, 0], "up": [0, 0, -1], "type": "ph8"}
    q, _ = plug_exit(end)
    xu = x0 + mount[0] - 24.0                         # under the ceiling: right of the node above, left of its chain
    behind = board(cp["size"][0] + 8, cp["size"][1] + 6, POD_FACE_Z - 2.8)
    pts = [p0, p0 + d * 1.5, (xs, p0[1] + 12, p0[2] + 1.5), (xs, p0[1] + 30, zr), (xs, depth - 5, zr), (xs, yc, zr),
           (xs, yc, top), (xu, yc - 10, top), (xu, behind[1] + 12, top), (behind[0], behind[1], behind[2]),
           (q[0] + 3, q[1] + 3, q[2]), q]
    xh = pod((lx + POD_CASE[0] / 2 + POD_XH[1] + 8, ly, -3.0 - POD_CASE[2] / 2))
    hdr = board(cp["header"][0], cp["header"][1], POD_FACE_Z - 16.5)
    mega = [xh, (xh[0] + 6, xh[1] + 8, xh[2] - 3), board(cp["size"][0] - 6, 4, POD_FACE_Z - 13),
            (hdr[0] + 6, hdr[1] + 6, hdr[2] - 2.5), (hdr[0], hdr[1], hdr[2] - 2.5), hdr]   # above the lens tip
    rnd = lambda q: [[round(float(v), 2) for v in p] for p in q]
    return rnd(rounded_path(pts, 6.0)), end, rnd(rounded_path(mega, 5.0))


def data_lead_short(j7, ph, x_run, top, x_up, drop=None):
    """A sled bay's DATA lead (no drag chain): out of the node's J7 (side entry, right edge), rising to the
    plenum's top (under the sled) at x_run, right of the node, back along it, over to the port block's
    window and up through it at x_up, then along the rear wall into the single board's PH from the rear.
    drop = (x, floor z): a DATA ×4's PH on its right edge: up the window's side strip at x, just behind the
    plug, and into it."""
    p0, d = plug_exit(j7)
    q, dq = plug_exit(ph)
    if drop is not None:
        xd, floor = drop
        pts = [p0, p0 + d * 5.0, (x_run, p0[1] + 12, top), (x_run, q[1] - 12, top), (xd, q[1], top),
               (xd, q[1], floor + 2.0), q + dq * 1.0 + np.array([0.0, 0.0, -2.5]), q]
        return rounded_path(pts, 3.0)
    yb = q[1] + 2.0
    pts = [p0, p0 + d * 5.0, (x_run, p0[1] + 12, top), (x_run, yb - 12, top), (x_up, yb, top),
           (x_up, yb, q[2]), (q[0], yb, q[2]), q]
    return rounded_path(pts, 5.0)


def cable_free_length(cab, a, b):
    """A cable's length between its two strain reliefs: its length end to end less both plugs (a
    straight plug: shell, overmold and relief; a right-angle one: about its body's depth)."""
    def plug(e):
        if e["type"] == "dupont":
            return DUPONT["L"] + DUPONT["CRIMP"]
        p = USB_PLUGS.get(e["type"], USB_PLUGS["usb-c"])
        return 12 if e.get("style") == "right" else p["SL"] + p["L"] + p["REL"]
    return cab.get("length", 120) - plug(a) - plug(b)


def catenary_cable(a, touchdown, b, r=2.0):
    """A cable hanging from plug a under its own weight (a catenary) to `touchdown` on the floor,
    then lying there up to plug b.  Frame coordinates."""
    s, ta = plug_exit(a)
    pts = [s + ta * k for k in (0.0, 8.0, 16.0)]
    s = pts[-1]
    t = np.array([touchdown[0], touchdown[1], r])
    horiz = np.array([t[0] - s[0], t[1] - s[1], 0.0])
    h, height = np.linalg.norm(horiz), s[2] - r
    lo, hi = 1e-3, 1e5
    for _ in range(100):                                  # a·(cosh(h/a) − 1) = height
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if mid * (math.cosh(h / mid) - 1) > height else (lo, mid)
    ca, u = (lo + hi) / 2, horiz / max(h, 1e-9)
    for k in range(1, 33):
        left = h * (1 - k / 32)
        p = t - u * left
        p[2] = r + ca * (math.cosh(left / ca) - 1)
        pts.append(p)
    e, tb = plug_exit(b)
    floor = bezier(t, t + u * 60, e + tb * 60, e, 20)
    pts += [np.array(p) for p in floor[1:]]
    return [[round(float(c), 2) for c in p] for p in pts]


# ------------------------------------------------------------------ geometry helpers

def bezier(p0, p1, p2, p3, n=24):
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    t = np.linspace(0, 1, n)[:, None]
    pts = (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3
    return [[round(float(c), 2) for c in p] for p in pts]


RIBBON_BOND = 0.5      # how much of its outer wires' stretching a strip's web carries (0: loose wires, 1: one solid)
RIBBON_TWIST = 0.8     # its twisting stiffness over its bending out of its plane's (round wires: GJ ≈ 0.8 EI)


def ribbon_ends(exits, order):
    """A ribbon's two ends: per end the direction across its wires (square to the plugs' axis), the one along which
    the housings stand most clearly in the strip's order (the least gap between neighbours in the strip the
    most), as the strip is laid onto its pins, and the wires' ranks across the strip (`order`: per wire its
    place in the strip it was torn from).  exits: per end, per wire (point, direction out of the crimp)."""
    n = len(order)
    rank = np.argsort(np.argsort(np.asarray(order, float)))
    seq = np.argsort(rank)                          # the wires in the strip's order
    ws = []
    for e in (0, 1):
        q = np.array([p for p, _ in exits[e]], float)
        d = np.asarray(exits[e][0][1], float)
        d = d / np.linalg.norm(d)
        e1 = np.cross(d, [1.0, 0.0, 0.0] if abs(d[0]) < 0.9 else [0.0, 1.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(d, e1)
        best = None
        for th in np.radians(np.arange(0.0, 360.0, 2.0)):
            w = math.cos(th) * e1 + math.sin(th) * e2
            score = float(np.min(np.diff((q @ w)[seq]))) if n > 1 else 0.0
            if best is None or score > best[0] + 1e-9:
                best = (score, w)
        ws.append(best[1])
    return ws[0], ws[1], rank


def ribbon_rod(a, b, length, wa, wb, n, floor_z=-1e9, ceil_z=1e9, boxes=(), guess=None, avoid=(), step=None):
    """A strip of n Dupont wires bonded side by side as it lies between its two ends (a, b: the plugs' middles):
    a Kirchhoff rod exactly `length` long carrying its material frame, its width (the direction across the
    wires) leaving a along wa and arriving at b along wb (unit, square to the plugs' axis), its centreline
    straight out of each end along the plugs' axis for its first and last segment (the wires' lead out of their
    housings).  Soft to bend out of its plane (the n wires' own stiffness), 1 + ⅔·(n² − 1) times stiffer within
    it at RIBBON_BOND ½ (its outer wires would have to stretch, its inner ones to shorten: Σ A·y² against
    n·I), RIBBON_TWIST to twist; its own weight (as one wire's per wire: DUPONT's sag); above floor_z, under
    ceil_z, out of `boxes`, off itself and the cables in `avoid`, nowhere tighter than DUPONT's MIN_R.  SLSQP on
    its segments' directions and frame angles.  Returns (nodes, the segments' tangents, the segments' widths,
    shortfall, note) as rod_cable; the guess, its frame turned evenly from wa to wb, when no shape reaches."""
    from scipy.optimize import minimize
    pa, da = plug_exit(a)
    pb, db = plug_exit(b)
    ta, tb = da / np.linalg.norm(da), -db / np.linalg.norm(db)
    r = DUPONT["R"] * n
    stiff = 1.0 + RIBBON_BOND * 4.0 / 3.0 * (n * n - 1)
    N = int(np.clip(round(length / (step or DUPONT["STEP"])), 12, 72))
    h = length / N
    m = N - 2
    ref_v = np.cross(pb - pa, [0.0, 0.0, 1.0])
    ref_v = ref_v / np.linalg.norm(ref_v) if np.linalg.norm(ref_v) > 1e-6 else np.array([1.0, 0.0, 0.0])

    def frames(t, psi):
        u = ref_v - (t @ ref_v)[:, None] * t
        u /= np.linalg.norm(u, axis=1)[:, None]
        return u, np.cos(psi)[:, None] * u + np.sin(psi)[:, None] * np.cross(t, u)

    def ref_twist(t, u):
        """The reference frame's own turn about the rod at each joint (against parallel transport)."""
        t0_, t1_ = t[:-1], t[1:]
        c = 1.0 + np.sum(t0_ * t1_, axis=1)
        q = u[:-1] - (np.sum(u[:-1] * t1_, axis=1) / c)[:, None] * (t0_ + t1_)
        return np.arctan2(np.sum(np.cross(q, u[1:]) * t1_, axis=1), np.sum(q * u[1:], axis=1))

    def angle(w, t):
        u, _ = frames(t[None], np.zeros(1))
        w = np.asarray(w, float) - np.dot(w, t) * t
        return math.atan2(float(np.dot(w, np.cross(t, u[0]))), float(np.dot(w, u[0])))

    def plain(path):
        """A path's segments' directions and its frame turned evenly from wa to wb: the start, and the fallback."""
        t = np.diff(path, axis=0)
        t /= np.linalg.norm(t, axis=1)[:, None]
        t[0], t[-1] = ta, tb
        u, _ = frames(t, np.zeros(len(t)))
        ref = np.concatenate([[0.0], np.cumsum(ref_twist(t, u))])
        p0, p1 = angle(wa, ta), angle(wb, tb)
        p1 -= 2 * math.pi * round((p1 - p0 + ref[-1]) / (2 * math.pi))     # the least twist end to end
        psi = p0 + np.linspace(0.0, 1.0, len(t)) * (p1 - p0 + ref[-1]) - ref
        return t, psi, p0, p1

    reach = float(np.linalg.norm(pb - pa))
    start = _resample(np.array(guess if guess is not None else [pa, pb], float), N)
    if reach > length - h:
        t, psi, _, _ = plain(start)
        return start, t, frames(t, psi)[1], round(reach - length + h, 1), ""
    path = start                       # the start: the guess, bowed sideways and up until it is as long as the rod
    side = np.cross(pb - pa, [0.0, 0.0, 1.0])
    side = side / (np.linalg.norm(side) or 1.0)
    bow = (side + np.array([0.0, 0.0, 0.6])) / np.linalg.norm(side + np.array([0.0, 0.0, 0.6]))
    bump = np.sin(np.linspace(0.0, math.pi, N + 1))[:, None] * bow
    lo, hi = 0.0, length

    def plen(amp):
        return float(np.sum(np.linalg.norm(np.diff(path + bump * amp, axis=0), axis=1)))
    if plen(0.0) < length:
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if plen(mid) < length else (lo, mid)
        path = path + bump * lo
    t0, psi_0, psi_a, psi_b = plain(path)
    x0 = np.concatenate([np.arctan2(t0[1:-1, 1], t0[1:-1, 0]), np.arcsin(np.clip(t0[1:-1, 2], -1, 1)), psi_0[1:-1]])
    gap = r + 0.2
    boxes = [(np.asarray(lo_, float) - gap, np.asarray(hi_, float) + gap) for lo_, hi_ in boxes]
    box_lo = np.array([b_[0] for b_ in boxes], float).reshape(-1, 3)
    box_hi = np.array([b_[1] for b_ in boxes], float).reshape(-1, 3)

    def tangents(x):
        th, ph = x[:m], x[m:2 * m]
        mid = np.stack([np.cos(ph) * np.cos(th), np.cos(ph) * np.sin(th), np.sin(ph)], axis=1)
        return np.vstack([ta, mid, tb])

    def nodes(t):
        return pa + h * np.vstack([np.zeros(3), np.cumsum(t, axis=0)])

    def inside(p):
        if not len(box_lo):
            return np.zeros(len(p))
        d = np.minimum(p[:, None, :] - box_lo[None], box_hi[None] - p[:, None, :]).min(axis=2)
        return np.maximum(d.max(axis=1), 0.0)

    far = np.triu(np.ones((N, N), bool), k=max(3, int(math.ceil(2 * r / h)) + 2))
    others = [(np.asarray(q[0], float), float(q[1])) if isinstance(q, tuple) else (np.asarray(q, float), CABLE_R)
              for q in avoid]
    others = [(q, rq) for q, rq in others if len(q) > 1]

    def contact(p):
        a0, a1 = p[:-1], p[1:]
        pen = float(np.sum(np.clip(2 * r - _segment_gaps(a0, a1, a0, a1)[far], 0.0, None) ** 2))
        for q, rq in others:
            pen += float(np.sum(np.clip(r + rq - _segment_gaps(a0[1:-1], a1[1:-1], q[:-1], q[1:]), 0.0, None) ** 2))
        return pen

    def energy(x):
        t = tangents(x)
        p = nodes(t)
        psi = np.concatenate([[psi_a], x[2 * m:], [psi_b]])
        u, m1 = frames(t, psi)
        m2 = np.cross(t, m1)
        t0_, t1_ = t[:-1], t[1:]
        kb = 2.0 * np.cross(t0_, t1_) / (1.0 + np.sum(t0_ * t1_, axis=1))[:, None]   # curvature binormal
        w1, w2 = m1[:-1] + m1[1:], m2[:-1] + m2[1:]
        k1 = np.sum(kb * w1, axis=1) / np.linalg.norm(w1, axis=1)                     # out of its plane
        k2 = np.sum(kb * w2, axis=1) / np.linalg.norm(w2, axis=1)                     # within it
        tw = np.diff(psi) + ref_twist(t, u)
        bend = (float(np.sum(k1 ** 2)) + stiff * float(np.sum(k2 ** 2)) + RIBBON_TWIST * float(np.sum(tw ** 2))) / h
        weight = h * float(np.sum(p[1:-1, 2] - p[0, 2])) / DUPONT["SAG"] ** 3
        return bend + weight + 200.0 * (float(np.sum(inside(p[1:-1]) ** 2)) + contact(p))

    min_r = DUPONT["MIN_R"]
    cons = [{"type": "eq", "fun": lambda x: nodes(tangents(x))[-1] - pb},
            {"type": "ineq", "fun": lambda x: nodes(tangents(x))[1:-1, 2] - (floor_z + gap)},
            {"type": "ineq", "fun": lambda x: (ceil_z - r) - nodes(tangents(x))[1:-1, 2]},
            {"type": "ineq", "fun": lambda x: (h / min_r) ** 2 - np.sum(np.diff(tangents(x), axis=0) ** 2, axis=1)}]
    res = minimize(energy, x0, method="SLSQP", constraints=cons, options={"maxiter": 500, "ftol": 1e-7})
    t = tangents(res.x)
    p = nodes(t)
    miss = float(np.linalg.norm(p[-1] - pb))
    if miss > 0.5:
        t, psi, _, _ = plain(start)
        return start, t, frames(t, psi)[1], round(miss, 1), "no rest shape found"
    p[-1] = pb
    w = frames(t, np.concatenate([[psi_a], res.x[2 * m:], [psi_b]]))[1]
    notes = []
    if float(inside(p[1:-1]).max(initial=0.0)) > 0.5:
        notes.append("it touches a board or a wall")
    if contact(p) > 0.01:
        notes.append("it runs into itself or another cable")
    return p, t, w, 0.0, "; ".join(notes)


def ribbon_curve(p, t, w, sub=5):
    """A ribbon rod's centreline (ribbon_rod's nodes, segment tangents and widths) sampled `sub` times a segment:
    a cubic Hermite between the nodes (through each node along its two segments' mean, straight along the
    first and the last: the leads), its width carried along (square to it) and its normal.  Returns (points,
    tangents, widths, normals, arc length)."""
    p, t, w = (np.asarray(v, float) for v in (p, t, w))
    T = np.vstack([t[0], t[0], t[1:-2] + t[2:-1], t[-1], t[-1]])
    W = np.vstack([w[0], w[0], w[1:-2] + w[2:-1], w[-1], w[-1]])
    T /= np.linalg.norm(T, axis=1)[:, None]
    s = np.linspace(0.0, 1.0, sub + 1)[:-1][None, :, None]
    L = np.linalg.norm(np.diff(p, axis=0), axis=1)[:, None, None]
    p0, p1, T0, T1 = p[:-1, None], p[1:, None], T[:-1, None] * L, T[1:, None] * L
    q = (2 * s ** 3 - 3 * s ** 2 + 1) * p0 + (s ** 3 - 2 * s ** 2 + s) * T0 + (3 * s ** 2 - 2 * s ** 3) * p1 + (s ** 3 - s ** 2) * T1
    dq = (6 * s ** 2 - 6 * s) * p0 + (3 * s ** 2 - 4 * s + 1) * T0 + (6 * s - 6 * s ** 2) * p1 + (3 * s ** 2 - 2 * s) * T1
    wq = (1 - s) * W[:-1, None] + s * W[1:, None]
    q, dq, wq = (np.vstack([v.reshape(-1, 3), last]) for v, last in ((q, p[-1]), (dq, t[-1]), (wq, W[-1])))
    dq /= np.linalg.norm(dq, axis=1)[:, None]
    wq -= np.sum(wq * dq, axis=1)[:, None] * dq
    wq /= np.linalg.norm(wq, axis=1)[:, None]
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))])
    return q, dq, wq, np.cross(dq, wq), arc


def ribbon_plan(curve, exits, rank, pitch):
    """Where a ribbon's wires part (ribbon_curve: its centreline; exits: per end, per wire (point, direction out
    of the crimp); rank: the wires' places across the strip, `pitch` apart).  The strip stays whole up to a
    cross-section 15 mm past the housings' leads, or twice the housings' spread there when they spread wider;
    past it each wire's free end is the same length for every wire (torn together, they were cut together): what
    the one with the farthest to go needs, with 8 % to spare for a gentle curve.  Returns the plan ribbon_wires
    draws from, with "total": a wire's length as planned, crimp to crimp (the caller lengthens or shortens the
    ribbon until it is the jumper's)."""
    q, T, W, Nn, u = curve
    n = len(rank)
    U = float(u[-1])
    lead = DUPONT["LEAD"]
    b = (np.asarray(rank, float) - (n - 1) / 2) * pitch
    cut = []
    for e in (0, 1):
        pts = np.array([p for p, _ in exits[e]], float)
        spread = float(np.max(np.linalg.norm(pts - pts.mean(axis=0), axis=1)))
        whole = lead + max(15.0, 2.0 * spread)
        cut.append(int(np.searchsorted(u, whole)) if e == 0 else int(np.searchsorted(u, U - whole)))
    i0, i1 = cut
    if i1 - i0 < 4:
        i0 = i1 = len(u) // 2
    bonded = [q[i0:i1 + 1] + W[i0:i1 + 1] * b[k] for k in range(n)]
    ends = []
    for e, i in ((0, i0), (1, i1)):
        starts = [np.asarray(p, float) + np.asarray(d, float) / np.linalg.norm(d) * lead for p, d in exits[e]]
        joins = [bonded[k][0 if e == 0 else -1] for k in range(n)]
        free = 1.08 * max(float(np.linalg.norm(joins[k] - starts[k])) for k in range(n)) + 0.5
        # the free end reaches its place in the ribbon running along it (into it from the A end, out of it to B)
        ends.append({"starts": starts, "joins": joins, "into": -T[i] if e == 0 else T[i], "free": free,
                     "normal": Nn[i]})
    run = [float(np.sum(np.linalg.norm(np.diff(bk, axis=0), axis=1))) for bk in bonded]
    total = 2 * lead + ends[0]["free"] + ends[1]["free"] + float(np.mean(run))
    return {"exits": exits, "bonded": bonded, "run": run, "ends": ends, "total": total}


def ribbon_wires(plan, length, floor_z, ceil_z, boxes=(), avoid=()):
    """A ribbon's wires from its plan (ribbon_plan), each `length` long crimp to crimp: straight out of its housing
    for DUPONT's LEAD, then free (an elastica: rod_cable, as thin as a wire, off the boards, the housings, the
    cables in `avoid` and the wires already drawn) to its place in the ribbon, bonded to its neighbours from there
    on.  The free ends' lengths: the plan's at either end, shared out so that each wire is `length` exactly.  The
    farthest-going free ends first, so that the others find their way round them.  Returns ([points] per wire,
    their lengths)."""
    exits, bonded, run, ends = plan["exits"], plan["bonded"], plan["run"], plan["ends"]
    n = len(bonded)
    lead = DUPONT["LEAD"]
    r = DUPONT["R"]
    keep = r + 0.35                    # the wires already drawn, a little fatter: the penalty acts before they touch
    drawn = list(avoid) + [(bk[:12], keep) for bk in bonded] + [(bk[-12:], keep) for bk in bonded]
    peels = [[None, None] for _ in range(n)]
    share = ends[0]["free"] / (ends[0]["free"] + ends[1]["free"])
    for e in (0, 1):
        end = ends[e]
        order = sorted(range(n), key=lambda k: -float(np.linalg.norm(end["joins"][k] - end["starts"][k])))
        for k in order:
            free = (length - 2 * lead - run[k]) * (share if e == 0 else 1 - share)
            a = (end["starts"][k], np.asarray(exits[e][k][1], float))
            b = (end["joins"][k], end["into"])
            best = None
            # a free end that runs into one already drawn tries again, started bowed out of the ribbon's plane one
            # way, then the other (the elastica keeps the side it starts on)
            for lift in (0.0, 3.0, -3.0):
                mid = (a[0] + b[0]) / 2 + end["normal"] * lift
                pts, short, _ = rod_cable(a, b, free, floor_z, ceil_z, boxes, avoid=drawn, r=r, sag=DUPONT["SAG"],
                                          min_r=DUPONT["MIN_R"], step=2.0, guess=[a[0], mid, b[0]] if lift else None,
                                          push=5000.0)
                pts = np.asarray(pts, float)
                g = -1e9                       # no shape found (the guess comes back): the last resort
                if len(pts) > 3 and not short:
                    g = min([float(_segment_gaps(pts[1:-2], pts[2:-1], o[:-1], o[1:]).min()) - 2 * r
                             for o in (np.asarray(o_, float) for o_, _ in drawn[len(avoid):])] or [0.0])
                if best is None or g > best[0]:
                    best = (g, pts, short)
                if g > -0.05:
                    break
            _, pts, short = best
            if short:
                print(f"warning: a ribbon wire's free end is {short:.1f} mm too short")
            peels[k][e] = pts
            drawn.append((pts, keep))
    wires = []
    for k in range(n):
        a_exit, b_exit = (np.asarray(exits[e][k][0], float) for e in (0, 1))
        w = np.vstack([a_exit, peels[k][0], bonded[k][1:-1], peels[k][1][::-1], b_exit])
        wires.append(w)
    return ([w.round(2).tolist() for w in wires],
            [float(np.sum(np.linalg.norm(np.diff(w, axis=0), axis=1))) for w in wires])


def poly(*pts):
    return [[round(float(c), 2) for c in p] for p in pts]


def chain_path(rack, open_frac, origin):
    """Centre-line of the drag chain (fixed end → U bend → moving end), carrier XY + origin."""
    st = rack.chain_state(open_frac)
    fx, fy = st["fixed"]
    mx, my = st["moving"]
    b, r = st["bend_y"], st["radius"]
    z = rack.carrier["bottom"] + rack.chain["outer"][0] / 2 + 0.6
    cx = (fx + mx) / 2
    pts = []
    for y in np.linspace(fy, b, max(2, int((b - fy) / 6))):
        pts.append([fx, y, z])
    for a in np.linspace(math.pi, 0, 14):
        pts.append([cx + r * math.cos(a), b + r * math.sin(a), z])
    for y in np.linspace(b, my, max(2, int((b - my) / 6))):
        pts.append([mx, y, z])
    ox, oy, oz = origin
    return [[round(p[0] + ox, 2), round(p[1] + oy, 2), round(p[2] + oz, 2)] for p in pts]


# ------------------------------------------------------------------ scene

def build(rack) -> Path:
    """Assemble the viewer scene.

    Items carry `space`: "row" (coordinates in that row's tilted frame, see
    config/rack.yaml) or "frame".  The viewer puts row items in a group per
    row (origin + tilt), so drawers slide along the slope and rows explode as units.
    The structure is the panel frame: per column boundary a base ladder, one ladder per row
    and a cap strip; per column a floor plate, a cap plate and an X brace per level; per bay a
    tray (its bottom on the row's origin plane) and a drawer on its ledges.
    """
    boards = rackcfg.load_boards()
    print("rendering web meshes ...")
    stats = build_parts_glb(rack, boards)
    for k, v in stats.items():
        print(f"  {k:28s} {v:7d} tris")

    raw = rack.raw
    W, D = rack.width, rack.depth
    BD = rack.bay_depth
    c = rack.carrier
    d = rack.drawer
    node = rack.node
    pcb_top = rack.pcb_top
    plenum = rack.plenum
    pop = raw.get("population", {})
    cams = set(raw.get("cameras", []))
    cables_cfg = raw["cables"]
    n_rows = len(rack.rows)
    pitch, T = rack.pitch, rack.panel_t

    items = {"instances": [], "frame": [], "cables": [], "chains": [], "boards": [], "pcbs": [], "boxes": [], "props": [],
             "leds": [], "cameras": [], "headers": []}
    bays = []

    def add(part, pos, rot=(0, 0, 0), space="row", row=None, **meta):
        items["instances"].append({"part": part, "pos": [round(v, 3) for v in pos], "rot": list(rot),
                                   "space": space, "row": row, **meta})

    def cable(points, space="row", row=None, **meta):
        items["cables"].append({"points": points, "space": space, "row": row, **meta})

    # --- the panel frame (frame space; ladders and braces carry their row for the explode view) ---
    for i in range(rack.units + 1):
        x = i * pitch
        add("ladder_base", (x, 0, 0), space="frame", layer="ladders")
        for k, r in enumerate(rack.rows):
            add(f"ladder_{r['id'].lower()}", (x, 0, 0), space="frame", row=k, layer="ladders")
        add("ladder_cap", (x, 0, 0), space="frame", row=n_rows, layer="ladders")
    floor_y0 = rack.row_origin_y - 5            # ladder.scad: FLOOR_Y0 = PF + 1, PF = ROW_Y0 - 6
    for u in range(rack.units):
        xc = u * pitch + T / 2
        add("floor_plate", (rack.unit_x(u), floor_y0, 0), space="frame", layer="frameplates")
        add("brace_base", (xc, 0, 0), space="frame", layer="braces")
        for k, r in enumerate(rack.rows):
            add(f"brace_{r['id'].lower()}", (xc, 0, 0), space="frame", row=k, layer="braces")
        add("cap_plate", (rack.unit_x(u), 0, 0), row=n_rows, layer="frameplates")

    port_wall_y = d["depth"] - d["rear_bay"]
    data_ports = rack.data_port_x          # the DATA coupler's position(s) per drawer
    port_z = d["bottom"] + 8.5            # lib/carrier.scad › PORT_Z: the DATA board's USB-C mouth
    dp = raw["pcb"]["data_port"]
    dp_x0 = data_ports[0] - dp["usb"]      # the DATA board in the drawer (lib/carrier.scad › DATA_PCB_X0, ..)
    dp_y0 = port_wall_y                   # its front edge: the port wall's back face
    dp_z = port_z - 1.63 - dp["thickness"]  # its underside, on the floor bosses (components up)
    plate_x0 = d["wall"] + 0.3
    plate_y0 = d["front_thickness"] + 0.3
    plate_w = rack.drawer_w - 2 * d["wall"] - 0.6
    plate_d = port_wall_y - d["wall"] - d["front_thickness"] - 0.6
    fixed = raw["chain"]["fixed"]
    chain_z = c["bottom"] + raw["chain"]["outer"][0] / 2 + 0.6     # the chain's mid-height

    def x4_frame(dy, dz):
        """The DATA ×4 (v1) in a drawer: (x of its left edge less the drawer's, y of its rear edge, z of its top) in
        drawer terms, to turn KiCad (x, y from the rear) into the row's frame: (x0 + x, y_rear - y, top)."""
        q = raw["pcb"]["data_port_x4"]
        return q["x0"], dy + dp_y0 + q["size"][1], dz + dp_z + q["thickness"]

    def x4v2_frame(dy, dz):
        """The standing v2 in a drawer: (x of its left edge less the drawer's, y of its front face, z of its bottom
        edge on the floor), to turn board x and drawer z into the row's frame: (x0 + x, y, dz + z)."""
        v = raw["pcb"]["data_port_x4_v2"]
        return v["x0"], dy + dp_y0 + v["face_y"], dz + d["bottom"]

    def x4v2_header_points(dxw, dy, dz, port):
        """The standing v2's header at a port, in the row's frame: [(the housing's mouth on the pins' strip, name)],
        a housing pushed on along +y."""
        vx0, y_face, _ = x4v2_frame(dy, dz)
        return [((dxw + vx0 + x, y_face - HEADER["BASE"], dz + z), n) for x, z, n in x4v2_header_pins(raw, port)]

    def unit_hardware(i, u, bid, dy, open_frac, drawer=True, x4=False, v2=False):
        """Tray, node and either the drawer and its chain, or a sled bay's sled and port block (no chain; the
        viewer doesn't slide them: the DUT cable is unplugged first).  x4: a converted bay's (`boards:`) DATA ×4
        board, in the same drawer or port block as the single DATA board; v2: the planned v2 (`x4: v2`) instead
        of v1, its parts' stand-ins and its 2 × 6 headers (v1: its 1 × 3 RESET/BOOT headers)."""
        x0 = rack.unit_x(u)
        add("tray", (x0, 0, 0), row=i, layer="trays", bay=bid)
        if drawer:
            add("drawer", (x0 + rack.drawer_x0, dy, plenum), row=i, layer="drawers", bay=bid,
                movable=True)
            add("chain_anchor", (x0 + fixed[0], fixed[1], c["bottom"] + 3), row=i, layer="chain", bay=bid)
            add("chain_foot", (x0 + raw["chain"]["moving_x"], raw["chain"]["moving_y"] + dy, plenum), row=i,
                layer="chain", bay=bid, movable=True)
            items["chains"].append({"bay": bid, "row": i, "origin": [x0, 0, 0], "open": open_frac,
                                    "fixed": fixed, "moving_x": raw["chain"]["moving_x"],
                                    "moving_y": raw["chain"]["moving_y"], "bend_y": raw["chain"]["bend_y"],
                                    "radius": raw["chain"]["radius"], "travel": d["travel"], "z": chain_z,
                                    "width": raw["chain"]["outer"][0], "height": raw["chain"]["outer"][1],
                                    "pitch": raw["chain"]["pitch"]})
        else:
            for part in ("drawer_sled", "drawer_block"):
                add(part, (x0 + rack.drawer_x0, 0, plenum), row=i, layer="drawers", bay=bid)
        info_ = pop.get(bid, {})
        led = "#2f7bff" if info_.get("pc_cable") else ("#ffb300" if info_.get("open") else "#19e07a")
        items["leds"].append({"bay": bid, "row": i, "space": "row", "color": led,
                              "pos": [x0 + node["x0"] + node["front"]["led"], 0.4, pcb_top + 0.7]})
        items["pcbs"].append({"board": "bay-node", "bay": bid, "row": i, "space": "row",
                              "pos": [x0 + node["x0"], rack.node_front_y + node["size"][1], c["bottom"] + c["standoff"]],
                              "size": [node["size"][0], node["size"][1], node["thickness"]]})
        # the DATA port board (or the DATA ×4) on its floor bosses in the drawer (components up) and its PH 8
        # lead: out of the node's J7 into the drag chain's fixed end; out of its moving end, a U-turn, up
        # through the drawer's cable window at the rear right and into the board's PH: the single board's from
        # the rear, along the rear wall; the DATA ×4's from its right, the window beside it
        dxw_ = x0 + rack.drawer_x0
        q4 = raw["pcb"]["data_port_x4"]
        # the cable window (drawer.scad): a rear strip from 1.5 mm right of the third boss to 1 mm short of the
        # chain foot's boss, and a side strip from 1 mm right of the DATA ×4's edge.  The single board's lead
        # comes up the rear strip's middle; the DATA ×4's (its PH on its right edge) drops into the side
        # strip's middle, right behind its plug.  Under the drawer both run forwards at x_win: further left, a
        # U-turn in front of the open drawer's chain mouth would pass over the row cable on its tie anchor
        w_end = raw["chain"]["moving_x"] - rack.drawer_x0 - 5.5
        x_win = dxw_ + (q4["x0"] + q4["holes"][2][0] + 4.5 + w_end) / 2
        x4_drop = (dxw_ + (q4["x0"] + q4["size"][0] + 1.0 + w_end) / 2, plenum + d["bottom"])
        ph_z = plenum + dp_z + dp["thickness"] + 2.8
        if x4 and v2:                # the planned v2 standing in its cradle: board, receptacles, headers, parts, PH 8
            v = raw["pcb"]["data_port_x4_v2"]
            vx0, y_face, z0 = x4v2_frame(dy, plenum)
            bx, t, (bw, bh) = dxw_ + vx0, v["thickness"], v["size"]
            mv = {"layer": "drawers", "bay": bid, "row": i, "space": "row", "movable": drawer}
            add("x4_cradle", (dxw_, dy, plenum), row=i, layer="drawers", bay=bid, movable=drawer)

            def slab(x_a, x_b, z_a, z_b):
                items["boxes"].append({"kind": "pcb", "pos": [round(x_a, 3), round(y_face, 3), round(z_a, 3)],
                                       "size": [round(x_b - x_a, 3), t, round(z_b - z_a, 3)], "color": "#1e6b3c", **mv})
            nw, nh = v["notches"]["size"]
            cuts = sorted(dxw_ + x for x in v["notches"]["x"])
            slab(bx, bx + bw, z0 + nh, z0 + bh)                       # the board, its bottom strip between the notches
            for x_a, x_b in zip([bx] + [c + nw / 2 for c in cuts], [c - nw / 2 for c in cuts] + [bx + bw]):
                slab(x_a, x_b, z0, z0 + nh)
            for n in range(1, 5):          # the vertical USB-C, their mouths 1 mm behind the port wall at v1's height
                add("dataport_usb_x4", (dxw_ + x4_port_x(rack, n), y_face - v["face_y"] + 1.0, plenum + dp_z), row=i,
                    layer="drawers", bay=bid, movable=drawer)
            pins = [[round(c, 3) for c in pt] for n in range(1, 5) for pt, _ in x4v2_header_points(dxw_, dy, plenum, n)]
            items["headers"].append({"bay": bid, "row": i, "space": "row", "movable": drawer, "board": "DATA ×4 v2",
                                     "pins": [[x, round(y + HEADER["BASE"], 3), z] for x, y, z in pins],
                                     "dir": [0, -1, 0], "tail": 0})     # SMD, on the front face, pins forward
            for face, x, z, w, h, hh, col in x4v2_parts(v["usb"]):
                y = y_face - hh if face < 0 else y_face + t
                items["boxes"].append({"kind": "chip", "pos": [round(bx + x, 3), round(y, 3), round(plenum + z, 3)],
                                       "size": [w, hh, h], "color": col, **mv})
            for ux in v["usb"]:            # the port LEDs on the front face's top edge
                items["leds"].append({"bay": bid, "row": i, "space": "row", "color": "#19e07a", "movable": drawer,
                                      "pos": [round(bx + ux, 3), round(y_face - 0.4, 3), round(z0 + bh - 1.5, 3)]})
            lx, lz = v["lead"]             # the PH 8 on the rear face, its mouth towards the rear
            ph_h = 6.0
            items["boxes"].append({"kind": "chip", "pos": [round(bx + lx - 9.75, 3), round(y_face + t, 3),
                                                           round(plenum + lz - 2.25, 3)],
                                   "size": [19.5, ph_h, 4.5], "color": "#f2f0e8", **mv})
            ph_xy = (bx + lx, y_face + t + ph_h)
            ph_dir = [0, -1, 0]
            ph_z = plenum + lz
        elif x4:                     # the DATA ×4 stand-in: its board and PH, a USB-C at each of the four ports
            q = raw["pcb"]["data_port_x4"]
            bx4 = dxw_ + q["x0"]
            add("dataport_pcb_x4", (bx4, dy + dp_y0, plenum + dp_z), row=i, layer="drawers", bay=bid, movable=drawer)
            add("dataport_ph_x4", (bx4, dy + dp_y0, plenum + dp_z), row=i, layer="drawers", bay=bid, movable=drawer)
            for n in range(1, 5):
                add("dataport_usb_x4", (dxw_ + x4_port_x(rack, n), dy + dp_y0, plenum + dp_z), row=i,
                    layer="drawers", bay=bid, movable=drawer)
            # its headers, soldered for the Dupont jumpers, and the v2's parts (stand-ins of the concept placement)
            kx0, y_rear, top = x4_frame(dy, plenum)
            pins = [[round(dxw_ + kx0 + x, 3), round(y_rear - y, 3)]
                    for n in range(1, 5) for x, y, _ in x4_header_pins(raw, n)]
            items["headers"].append({"bay": bid, "row": i, "space": "row", "movable": drawer, "z": round(top, 3),
                                     "pins": pins, "board": "DATA ×4"})
            ph_xy = (bx4 + q["size"][0], dy + dp_y0 + q["size"][1] - q["lead"][1])     # J1's mouth, right edge
            ph_dir = [-1, 0, 0]
        else:
            for k in ("pcb", "usb", "ph"):
                add(f"dataport_{k}", (dxw_ + dp_x0, dy + dp_y0, plenum + dp_z), row=i, layer="drawers", bay=bid,
                    movable=drawer)
            ph_xy = (dxw_ + dp_x0 + dp["ph"], dy + dp_y0 + dp["size"][1])
            ph_dir = [0, -1, 0]
        j7 = {"at": [x0 + node["x0"] + node["size"][0], rack.node_front_y + node["size"][1] - node["right"]["data"],
                     pcb_top + NODE_J7_Z], "dir": [-1, 0, 0], "up": [0, 0, 1], "type": "ph8"}
        ph = {"at": [ph_xy[0], ph_xy[1], ph_z], "dir": ph_dir, "up": [0, 0, 1], "type": "ph8"}
        drop = x4_drop if x4 and not v2 else None     # v1's J1 drops into the side strip; the v2's lead the rear one
        if not drawer:
            cable(data_lead_short(j7, ph, x0 + node["x0"] + node["size"][0] + 12.0, plenum - 3.0, x_win,
                                  drop=drop), row=i, kind="ext",
                  bay=bid, radius=1.2, ends=[j7, ph], label="DATA lead (JST PH 8, node J7 → the port block)")
            return x0, plenum
        p0, d7 = plug_exit(j7)                             # out of the side-entry J7, straight to the chain's fixed end
        cable(rounded_path([p0, p0 + d7 * 6.0, (x0 + fixed[0], fixed[1] - 13, chain_z),
                            (x0 + fixed[0], fixed[1], chain_z)], 6.0),
              row=i, kind="ext", bay=bid, radius=1.2, ends=[j7], label="DATA lead (JST PH 8, through the drag chain)")
        mouth = (x0 + raw["chain"]["moving_x"], raw["chain"]["moving_y"] + dy, chain_z)
        x_run = max(x0 + fixed[0] + raw["chain"]["outer"][1] / 2 + 6.0, x_win)   # 6 mm off the fixed run
        cable(lead_to_board(ph, mouth, z_low=9.0, x_run=x_run, drop=drop), row=i, kind="ext",
              bay=bid, radius=1.2, ends=[ph],
              label="DATA lead (JST PH 8, through the drag chain)", movable=True)
        return x0, plenum

    def board_box(bd, o, bx, by, dz):
        """What a board fills, for its cables to keep out of: from the plate up to its tallest part."""
        top = dz + d["bottom"] + d["plate"] + bd.get("standoff", 6) + 1.6 + bd.get("height", 10)
        return (bx, by, dz + d["bottom"] + d["plate"]), (bx + o["w"], by + o["l"], top)

    def dut_board(i, bay, slot, board_id, bd, o, bx, by, dz, dy, drawer, ctype, sx, others=(), drawn=None, mid=None,
                  dxw=None):
        """A board on its plate (front-left corner bx, by; o: rackcfg.orient_board) and its short DUT cable from
        the DATA socket at drawer x sx: USB-C into the panel-mount socket on the drawer's port wall, the board's
        own connector (micro-B, USB-C…) at the other end.  A board's USB facing the port wall: right-angle plugs
        (`right`), or for a micro-B / mini-B board a 90° adapter with a straight plug standing on it (`adapter`),
        and an arch in between; a small board turned to the side wall (orient: side): straight plugs
        (`straight`) and one flat bend; a board facing the port wall from far enough (a converted bay's):
        straight plugs too, facing each other, and an S on the plate."""
        bz = dz + d["bottom"] + d["plate"] + bd.get("standoff", 6)
        items["boards"].append({"bay": bay, **({"slot": slot} if slot else {}), "row": i, "id": board_id,
                                "name": bd["name"], "label": bd.get("short", ""),
                                "pos": [round(bx, 2), round(by, 2), round(bz, 2)],
                                "size": [o["w"], o["l"], 1.6], "height": bd.get("height", 10),
                                "color": bd.get("color", "#1b5e20"), "usb_x": o["usb_x"],
                                "usb_type": bd["usb"]["type"], "usb2_x": o.get("usb2_x"),
                                "usb_side": o["usb_side"],
                                "verified": bd.get("verified", False), "movable": drawer,
                                **({"model": mdl} if (mdl := board_model(board_id, bd)) else {}),
                                **({"screen": scr} if (scr := board_screen(bd)) else {})})
        btype = cables_cfg[ctype].get("b", "usb-c")
        style = cables_cfg[ctype].get("style", "right")
        end_a = {"at": [sx, dy + dp_y0 - 0.28, dz + port_z], "dir": [0, 1, 0],   # the DATA board's USB-C, 0.28 proud of its edge
                 "type": "usb-c", "style": "straight" if style == "straight" else "right"}
        b_style = "straight" if style == "side" else style
        zc = bz + 1.6 + (1.4 if btype != "usb-c" else 1.65)
        ux = o["usb_x"]
        if o["usb_side"]:
            end_b = {"at": [bx + o["w"] + 0.6, by + ux, zc], "dir": [-1, 0, 0], "type": btype, "style": b_style}
        else:
            end_b = {"at": [bx + ux, by + o["l"] + 0.6, zc], "dir": [0, -1, 0], "type": btype, "style": b_style}
        ends = [end_a, end_b]
        if style == "adapter":       # the cable's own plug: straight, down into the adapter's female
            p = USB_PLUGS[btype]
            bd_ = np.array(end_b["dir"], float)
            mouth = np.array(end_b["at"]) - bd_ * p["AD"] / 2 + np.array([0, 0, p["ATOP"]])
            end_b = {"at": [round(float(c), 2) for c in mouth], "dir": [0, 0, -1], "up": end_b["dir"],
                     "type": btype, "style": "straight"}
            ends.append(end_b)
        free = cable_free_length(cables_cfg[ctype], end_a, end_b)
        route = {"straight": flat_cable, "side": side_arch_cable}.get(style, arch_cable)
        if style == "straight" and np.dot(end_a["dir"], end_b["dir"]) < -0.9:
            route = s_cable              # the board's USB faces the port wall: the plugs face each other
        guess, short0 = route(end_a, end_b, free)
        # the cable as it lies, its whole length: on the plate, under the camera pod, out of the boards and the
        # port wall (rod_cable); the routes above only give it a start
        floor_z = dz + d["bottom"] + d["plate"]
        wall = ((sx - 200, dy + port_wall_y - d["wall"], dz), (sx + 200, dy + port_wall_y + 1, dz + d["wall_height"]))
        boxes = [board_box(bd, o, bx, by, dz), *others, wall]
        if dxw is not None:          # the drawer's side walls and front panel, as high as the cable may rise: it stays in
            top = ARCH_TOP_MAX + 10  # the drawer, which slides in its tray
            boxes += [((dxw - 30, dy, dz), (dxw + d["wall"], dy + port_wall_y, top)),
                      ((dxw + rack.drawer_w - d["wall"], dy, dz), (dxw + rack.drawer_w + 30, dy + port_wall_y, top)),
                      ((dxw - 30, dy - 30, dz), (dxw + rack.drawer_w + 30, dy + d["front_thickness"], top))]
        pts, short, note = rod_cable(end_a, end_b, free, floor_z, ARCH_TOP_MAX, boxes, guess=guess,
                                     avoid=drawn or (), outward=mid)
        if short and not short0:
            print(f"warning: {slot or bay}: no rest shape found for the {ctype} cable: drawn along its route")
            pts, short = guess, short0
        if note:
            print(f"warning: {slot or bay}: the {ctype} cable: {note}")
        if short:
            print(f"warning: {slot or bay}: the {ctype} cable is {short:.0f} mm too short "
                  f"from the DATA socket to the board")
        if drawn is not None:            # the bay's next cables keep off this one
            drawn.append(pts)
        cable(pts, row=i, kind="dut", bay=bay, type=ctype, label=cables_cfg[ctype]["label"], a="usb-c", b=btype,
              ends=ends, radius=1.9, movable=drawer)

    def route_jumpers(i, bid, spec, boards_at, dut_pins, dy, dz, dxw, drawer, drawn, v2):
        """A converted bay's Dupont jumpers (population › jumpers: per board, {DATA ×4 header pin: board pin}),
        female–female, 20 cm (30 where that does not reach: JUMPER_LENGTHS), from the board's port's header to
        its pin header (dut_pins: slot → (the pins' plastic top, [(x, y, name)])), each housing pushed down on its
        pin; on the standing v2 (v2), pushed on its front face's pins from the front.  A board's wires as one ribbon
        (ribbon_rod, ribbon_wires): out of the crimps (up off v1, forwards off v2), over the port wall and down
        onto the board, clear of the boards, the walls, the USB plugs, the v2 and its cradle, every housing and the
        cables already drawn."""
        kx0, y_rear, top = x4_frame(dy, dz)
        slots = {e["slot"].id: e["slot"] for e, _, _ in boards_at}
        runs = []
        for sid, pinmap in (spec or {}).items():
            sl = slots.get(sid)
            if sl is None:
                raise ValueError(f"{bid} jumpers: no board {sid} in the bay")
            if v2:                       # (the housing's mouth on the strip, the way it goes on) per header pin
                hdr = {n: (pt, [0, 1, 0], [0, 0, 1]) for pt, n in x4v2_header_points(dxw, dy, dz, sl.slot)}
            else:
                hdr = {n: ((dxw + kx0 + x, y_rear - y, top + HEADER["BASE"]), [0, 0, -1], [0, 1, 0])
                       for x, y, n in x4_header_pins(raw, sl.slot)}
            bz, pins = dut_pins.get(sid, (None, []))
            for hp, dpin in pinmap.items():
                if hp not in hdr:
                    raise ValueError(f"{sid} jumpers: the DATA ×4 header has no pin {hp} ({', '.join(hdr)})")
                (ax, ay, az), adir, aup = hdr[hp]
                cands = [(x, y) for x, y, n in pins if n == str(dpin)]
                if not cands:
                    raise ValueError(f"{sid} jumpers: its board has no header pin {dpin} (boards.yaml › headers)")
                px, py = min(cands, key=lambda c: math.hypot(c[0] - ax, c[1] - ay))
                ends = [{"at": [round(ax, 3), round(ay, 3), round(az, 3)], "dir": adir, "up": aup, "type": "dupont"},
                        {"at": [round(px, 3), round(py, 3), round(bz + HEADER["BASE"], 3)], "dir": [0, 0, -1],
                         "up": [0, 1, 0], "type": "dupont"}]
                runs.append((sid, sl.slot, hp, str(dpin), ends, HEADER_PIN_COLOUR.get(hp, "white")))
        if not runs:
            return []
        w2, ln = DUPONT["W"] / 2, DUPONT["L"]

        def housing(e):
            """A housing's box: from its mouth back along the way it goes on, W square across."""
            at, dv = np.array(e["at"], float), np.array(e["dir"], float)
            back, side = at - dv * ln, (1.0 - np.abs(dv)) * w2
            return tuple(np.minimum(at, back) - side), tuple(np.maximum(at, back) + side)
        housings = [housing(e) for *_, ends, _ in runs for e in ends]
        top_ = ARCH_TOP_MAX + 10
        walls = [((dxw - 30, dy + port_wall_y - d["wall"], dz), (dxw + rack.drawer_w + 30, dy + port_wall_y, dz + d["wall_height"])),
                 ((dxw - 30, dy + d["depth"] - d["wall"], dz), (dxw + rack.drawer_w + 30, dy + d["depth"] + 30, top_)),
                 ((dxw - 30, dy, dz), (dxw + d["wall"], dy + d["depth"], top_)),
                 ((dxw + rack.drawer_w - d["wall"], dy, dz), (dxw + rack.drawer_w + 30, dy + d["depth"], top_)),
                 ((dxw - 30, dy - 30, dz), (dxw + rack.drawer_w + 30, dy + d["front_thickness"], top_))]
        p = USB_PLUGS["usb-c"]                      # the straight USB-C plugs in the port wall's sockets
        plugs = [((dxw + x4_port_x(rack, n) - p["W"] / 2, dy + port_wall_y - p["L"] - p["REL"], dz + port_z - p["H"] / 2),
                  (dxw + x4_port_x(rack, n) + p["W"] / 2, dy + port_wall_y, dz + port_z + p["H"] / 2)) for n in range(1, 5)]
        if v2:                       # the standing v2 and its cradle's uprights (their walls round its ends)
            vx0, y_face, z0 = x4v2_frame(dy, dz)
            (bw, bh), t = raw["pcb"]["data_port_x4_v2"]["size"], raw["pcb"]["data_port_x4_v2"]["thickness"]
            walls += [((dxw + vx0, y_face, z0), (dxw + vx0 + bw, y_face + t, z0 + bh)),
                      ((dxw + vx0 - 2.0, y_face - 2.6, z0), (dxw + vx0 + 5.5, y_face + t + 2.6, z0 + bh)),
                      ((dxw + vx0 + bw - 5.5, y_face - 2.6, z0), (dxw + vx0 + bw + 2.0, y_face + t + 2.6, z0 + bh))]
        boxes = [board_box(boards[e["board"]], e["o"], ex, ey, dz) for e, ex, ey in boards_at] + walls + plugs + housings
        avoid = [(q, CABLE_R) for q in drawn]
        out = []
        # a board's jumpers are torn off the strip together: one ribbon (ribbon_rod: an elastic strip, stiff within
        # its plane), its wires about it (ribbon_wires), all as long as the strip's
        for sid in dict.fromkeys(run[0] for run in runs):
            grp = [run for run in runs if run[0] == sid]
            n = len(grp)
            ea, eb = ({"at": np.mean([run[4][k]["at"] for run in grp], axis=0).round(3).tolist(),
                       "dir": grp[0][4][k]["dir"], "up": grp[0][4][k]["up"], "type": "dupont"} for k in (0, 1))
            pa, da = plug_exit(ea)
            pb, _ = plug_exit(eb)
            zt = max(pa[2], pb[2]) + 15.0
            pa1 = pa + da * 15.0               # out along the housings first: up off v1, forwards off the standing v2
            guess = [pa, [pa1[0], pa1[1], max(pa1[2], zt)], [pb[0], pb[1], zt], pb]
            r_band = DUPONT["R"] * n
            exits = [[plug_exit(run[4][k]) for run in grp] for k in (0, 1)]
            floor = dz + d["bottom"] + d["plate"]
            for length in JUMPER_LENGTHS:
                free = span = cable_free_length({"length": length}, ea, eb)
                if n == 1:
                    pts, short, note = rod_cable(ea, eb, free, floor, ARCH_TOP_MAX, boxes, guess=guess, avoid=avoid,
                                                 r=r_band, sag=DUPONT["SAG"], min_r=DUPONT["MIN_R"], step=DUPONT["STEP"])
                    wires, lens = [pts], [free]
                else:
                    # the wires peel off their ribbon and bow: the centreline is a little shorter than they are
                    wa, wb, rank = ribbon_ends(exits, [STRIP_ORDER.index(run[5]) for run in grp])
                    g = guess
                    for _ in range(5):
                        pts, tt, ww, short, note = ribbon_rod(ea, eb, span, wa, wb, n, floor, ARCH_TOP_MAX, boxes,
                                                              guess=g, avoid=avoid)
                        plan = ribbon_plan(ribbon_curve(pts, tt, ww), exits, rank, 2 * DUPONT["R"])
                        err = free - plan["total"]
                        if short or abs(err) < 0.5:
                            break
                        span, g = span + err, pts
                    wires, lens = ribbon_wires(plan, free, floor, ARCH_TOP_MAX, boxes, avoid)
                    pts = [[round(float(v), 2) for v in q] for q in pts]
                if not short:
                    break
            what = f"{sid}: its {n}-wire ribbon"
            print(f"  {what}: {length // 10} cm, centreline {span:.0f} mm, wires {min(lens):.1f}–{max(lens):.1f} of "
                  f"{free:.1f} mm, top {max(q[2] for q in pts):.1f}", flush=True)
            if short:
                print(f"warning: {what} is {short:.0f} mm too short")
            if note:
                print(f"warning: {what}: {note}")
            avoid.append((pts, r_band))
            for (_, port, hp, dpin, ends, col), wpts in zip(grp, wires):
                cable(wpts, row=i, kind="jumper", bay=bid, color=DUPONT_COLOURS[col], radius=DUPONT["R"], ends=ends,
                      label=f"Dupont F–F {length // 10} cm: DATA ×4 port {port} {hp} → {sid} {dpin}", length=length,
                      movable=drawer)
                out.append({"slot": sid, "from": hp, "to": dpin, "colour": col, "length": length, "points": wpts,
                            "ends": ends})
        return out

    jumpers_drawn = {}          # bay → its routed jumpers (the SolidCraft check reads them back from rack.json)
    for b in rack.bays():
        i = b.row
        info = pop.get(b.id, {})
        drawer = rack.mount(b.id) == "drawer"
        open_frac = 1.0 if info.get("open") and drawer else 0.0
        dy = -d["travel"] * open_frac
        x0, dz = unit_hardware(i, b.unit, b.id, dy, open_frac, drawer, rack.is_multi(b.id), info.get("x4") == "v2")
        dxw = x0 + rack.drawer_x0
        meta = {"id": b.id, "row": rack.rows[i]["id"], "row_index": i, "col": b.index + 1, "span": 1,
                "camera": b.id in cams, "unit_x": x0,
                "label_pos": [x0 + rack.carrier_w / 2, -3, plenum + d["front_height"] + 6]}
        pegs_plate = bool(info) and rack.plate_kind(b.id) == "pegs"
        placed = {}
        if pegs_plate:
            # the honeycomb plate, its pegs (tools/plate_layout.py: stops, cams, pins, the cable's bobbin) and its
            # boards where that layout puts them
            lay = plate_layout.layout_bay(rack, b.id, boards)
            top = dz + d["bottom"] + d["plate"]
            add("plate", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i, layer="plates", bay=b.id,
                movable=drawer)
            for peg in lay.pegs:
                for name, rot in peg.parts:
                    z = top + (peg.h - 1.0 if name == "peg_cam" else 0.0)
                    add(name, (dxw + plate_x0 + peg.x, dy + plate_y0 + peg.y, z), rot=(0, 0, round(rot, 1)), row=i,
                        layer="plates", bay=b.id, movable=drawer)
            placed = {pb.slot: pb.at for pb in lay.boards}
            meta["pegs"] = {"count": len(lay.pegs), "notes": lay.notes}
        if info and rack.is_multi(b.id):
            # a converted bay: one plate (the honeycomb one, or board_plate.scad › BAY), its boards where the peg
            # layout (or rackcfg.bay_layout) puts them, each on its own DATA ×4 port
            if not pegs_plate:
                add(f"plate_bay_{b.id.lower()}", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i,
                    layer="plates", bay=b.id, movable=drawer)
            slots = []
            # each board where the peg layout (or rackcfg.bay_layout) puts it, in drawer-frame coordinates
            boards_at = []
            for e in rack.bay_layout(b.id, boards):
                at = placed.get(e["slot"].id, e["at"])
                boards_at.append(({**e, "at": at}, dxw + plate_x0 + at[0], dy + plate_y0 + at[1]))
            drawn = []
            # the middle of the bay's cables (between its ports and its boards' USB): each spare length bows away from it
            mid_x = sum(dxw + x4_port_x(rack, e["slot"].slot) + ex + e["o"]["usb_x"]
                        for e, ex, _ in boards_at) / (2 * len(boards_at))
            for e, ex, ey in boards_at:
                # the board as turned on this plate: to the port wall unless its entry says `orient: side`
                sl, o = e["slot"], e["o"]
                bd = {**boards[e["board"]], "orient": sl.orient or "rear"}
                others = [board_box(boards[f["board"]], f["o"], fx, fy, dz) for f, fx, fy in boards_at if f is not e]
                dut_board(i, b.id, sl.id, e["board"], bd, o, ex, ey, dz, dy, drawer, sl.cable,
                          dxw + x4_port_x(rack, sl.slot), others, drawn, (mid_x, dy), dxw)
                slots.append({"id": sl.id, "port": sl.slot, "board": bd["name"], "board_id": e["board"],
                              "cable": cables_cfg[sl.cable]["label"], "usb": bd["usb"]["type"],
                              "verified": bd.get("verified", False)})
            # the boards' pin headers (soldered pins up), then the Dupont jumpers from the DATA ×4's headers
            v2 = info.get("x4") == "v2"
            dut_pins = {}
            for e, ex, ey in boards_at:
                sl = e["slot"]
                bd = {**boards[e["board"]], "orient": sl.orient or "rear"}
                hp = header_pins(bd)
                if not hp:
                    continue
                bz = dz + d["bottom"] + d["plate"] + bd.get("standoff", 6) + bd.get("pcb_t", 1.6)
                pts = [(ex + px, ey + py) for px, py in board_frame(bd, [(x, y) for x, y, _ in hp])]
                dut_pins[sl.id] = (bz, [(x, y, n) for (x, y), (_, _, n) in zip(pts, hp)])
                items["headers"].append({"bay": b.id, "row": i, "space": "row", "movable": drawer, "z": round(bz, 3),
                                         "pins": [[round(x, 3), round(y, 3)] for x, y in pts], "board": sl.id})
            jumpers_drawn[b.id] = route_jumpers(i, b.id, info.get("jumpers"), boards_at, dut_pins, dy, dz, dxw,
                                                drawer, drawn, v2)
            meta["jumpers"] = len(jumpers_drawn[b.id])
            meta.update({"board": f"{len(slots)} boards on a DATA ×4", "slots": slots, "data_port": ["×4"],
                         "open": bool(info.get("open")) and drawer, "mount": rack.mount(b.id),
                         "verified": all(sl_["verified"] for sl_ in slots)})
        elif info:
            bd = boards[info["board"]]
            o = rackcfg.orient_board(bd)
            cab = cables_cfg[info["cable"]]
            if pegs_plate:               # where the peg layout puts it
                bx, by = dxw + plate_x0 + placed[b.id][0], dy + plate_y0 + placed[b.id][1]
            else:                        # its own plate (`plate: boards`), placed as board_plate.scad places it
                add(f"plate_{info['board']}", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i,
                    layer="plates", bay=b.id, movable=drawer)
                if o["usb_side"]:
                    bx = dxw + plate_x0 + 2.5    # board_plate.scad › SIDE_X
                    by = dy + plate_y0 + (plate_d - o["l"]) / 2
                else:
                    rear_gap = max(3, min(26, plate_d - o["l"] - 4))
                    bx = dxw + plate_x0 + (plate_w - o["w"]) / 2
                    by = dy + plate_y0 + plate_d - rear_gap - o["l"]
            # the DATA socket goes in the port farther from the board's USB (the right one for a USB turned to
            # the right wall), so the two plugs never meet
            if o["usb_side"]:
                sx = dxw + max(data_ports)
            else:
                sx = max((dxw + px for px in data_ports), key=lambda x: abs(x - (bx + o["usb_x"])))
            meta["data_port"] = ["left" if sx - dxw < rack.drawer_w / 2 else "right"]
            dut_board(i, b.id, None, info["board"], bd, o, bx, by, dz, dy, drawer, info["cable"], sx,
                      mid=(dxw + rack.drawer_w / 2, dy), dxw=dxw)
            meta.update({"board": bd["name"], "board_id": info["board"], "cable": cab["label"],
                         "usb": bd["usb"]["type"], "classic": bool(info.get("pc_cable")), "open": bool(info.get("open")) and drawer, "mount": rack.mount(b.id),
                         "verified": bd.get("verified", False)})
            if info.get("pc_cable"):
                fx = x0 + node["x0"] + node["front"]["pc_port"]
                fz = pcb_top + 1.6
                o0 = np.array(rack.to_frame(i, (0, 0, 0)))
                frame_dir = lambda v: [round(float(c), 4) for c in np.array(rack.to_frame(i, v)) - o0]  # noqa: E731
                pc_a = {"at": rack.to_frame(i, (fx, rack.node_front_y - 0.3, fz)), "dir": frame_dir((0, 1, 0)),
                        "up": frame_dir((0, 0, 1)), "type": "usb-c", "style": "straight"}
                # a laptop on the floor/desk to the right of the rack, its left-side USB-C port wired in
                lap = [W + 270, -200, 0]
                pc_b = {"at": [lap[0] - 156, lap[1] + 40, 7.5], "dir": [1, 0, 0], "type": "usb-c", "style": "straight"}
                items["props"].append({"kind": "laptop", "space": "frame", "pos": lap, "size": [312, 218, 14],
                                       "lid_deg": 110, "bay": b.id})
                cable(catenary_cable(pc_a, (W + 30, -150), pc_b), space="frame", kind="pc", bay=b.id,
                      label="Laptop → front PC port (classic mode)", a="usb-c", b="usb-c", ends=[pc_a, pc_b],
                      radius=2.0)
        # camera: an Arducam Mega in the printed pod under the ceiling (the bottom of the tray above, or the cap
        # plate), lens down at bay.camera_lens, wired to this bay's own node (J6).  The pod's parts are instances
        # (parts/camera_pod.scad); site/camera.js adds the light and the preview through its lens
        if b.id in cams:
            cm = raw["bay"]["camera_mount"]
            for part in ("camera_pod", "camera_diffuser", "mega_camera", "podpcb", "podpcb_parts"):
                add(part, (x0 + cm[0], cm[1], 0), row=i + 1, layer="cameras", bay=b.id)
            items["cameras"].append({"bay": b.id, "row": i + 1, "space": "row", "layer": "cameras",
                                     **camera_view(x0, raw["bay"]["camera_lens"], raw["pcb"]["camera_pod"])})
            j6 = {"at": [x0 + node["x0"] + node["cam"][0], rack.node_front_y + node["size"][1] - node["cam"][1],
                         pcb_top + NODE_J6_H - 6.0], "dir": [0, 0, -1], "up": [1, 0, 0], "type": "ph8"}
            lead, pod_end, mega = camera_lead(j6, x0, rack.rows[i]["height"],
                                              rack.tilt, raw["bay"]["camera_lens"], cm, BD, raw["pcb"]["camera_pod"])
            cable(lead, row=i, kind="ext", bay=b.id, radius=1.5, ends=[j6, pod_end],
                  label="Camera lead (JST PH 8, node J6 → the pod board's J1)")
            cable(mega, row=i, kind="ext", bay=b.id, radius=1.0, label="XH → Dupont cable (the Mega → the pod board's J2)")
        meta["center"] = rack.to_frame(i, [x0 + rack.carrier_w / 2, BD / 2, plenum + 40])
        bays.append(meta)

    # --- the power box under row A: hub, status LEDs, the charger's USB-C cable, row feeds -----
    pb = rack.power_box()
    add("power_box_base", pb["origin"], space="frame", layer="powerbox")
    add("power_box_lid", pb["origin"], space="frame", layer="powerlid")
    add("power_box_labels", pb["origin"], space="frame", layer="powerbox")      # the optional inlays
    add("power_box_lid_labels", pb["origin"], space="frame", layer="powerlid")
    items["pcbs"].append({"board": "power-hub", "space": "frame", "pos": pb["hub"]})
    lit = {"on": "#3ddc84", "pd": "#3ddc84", "ctl": "#4aa3ff"}
    for led in pb["leds"]:
        if led["kind"] in lit and (led["row"] is None or led["row"] < n_rows):
            items["leds"].append({"space": "frame", "layer": "powerbox", "pos": led["pos"], "color": lit[led["kind"]]})
    # the USB-C PD cable: out of the box's rear wall, down and back to the charger behind the rack
    pd = pb["pd"]
    cable(poly(pd, (pd[0], pd[1] + 30, pd[2]), (pd[0] + 5, pd[1] + 60, 3), (pd[0] + 30, pd[1] + 240, 3)),
          space="frame", kind="usb-pd", radius=2.0)
    # row feeds: out of the box's left wall through the base ladder's window, forward along its
    # outer face, up the rack's left side, and in through each row's jumper window to the first node
    vy = rack.node_front_y + node["size"][1] - node["pwr_y"]
    for i in range(n_rows):
        x, y, z = pb["rows"][i]
        j1 = rack.to_frame(i, [rack.unit_x(0) + node["x0"] - 1, vy, pcb_top + 5])
        lane = -3.0 - 2.6 * i
        pts = poly((x - 2, y, z), (lane + 2, y, z), (lane, y - 6, z), (lane, j1[1] + 8, z), (lane, j1[1], z + 10),
                   (lane, j1[1], j1[2] - 10), (lane + 3, j1[1], j1[2]), j1)
        cable(pts, space="frame", kind="power-feed", color="#c62828", radius=1.4)

    # --- row cable: 6-pin jumpers between neighbouring nodes, through the shared ladder (docs/can.md) ----
    # VRACK, GND, CAN_H, CAN_L, GND, POS (J1's pins 1-6, pin 1 towards the rear); J2 (right edge) carries
    # them mirrored, so each wire keeps its side: a flat lead, no twist.  From J2 it heads for the tray's
    # front right, crosses that side in front of the chain foot's reach (the drawer out brings the foot to
    # y 12) through the two tie anchors (tray.scad › JUMPER_TIES), at y ≤ 9, and turns back up to the next
    # node's J1 inside the ladder (panels.scad › JUMPER_Y)
    ties_x = [t[0] for t in JUMPER_TIES]
    for i, r in enumerate(rack.rows):
        zc = pcb_top + 5
        zf = c["bottom"] + 5 + 1.2                          # on the anchors
        vy = rack.node_front_y + node["size"][1] - node["pwr_y"]
        for u in range(rack.units - 1):
            x0u, x0n = rack.unit_x(u), rack.unit_x(u + 1)
            xa = x0u + node["x0"] + node["size"][0]
            xb = x0n + node["x0"]
            for k, col in enumerate(("#c62828", "#222222", "#f9a825", "#2e7d32", "#222222", "#eeeeee")):
                y = vy + 5 - 2 * k                                # JST PH, 2 mm pitch, 24 AWG
                yf = 4.4 + 0.85 * (5 - k)                         # bunched at the front: 4.4–8.65
                zk = zf + (0.7 if k % 2 else 0.0)
                pts = [(xa, y, zc), (xa + 12, y, zc), (x0u + ties_x[0] - 14, yf, zk), (x0u + ties_x[1], yf, zk),
                       (x0n - 4, yf, zk), (x0n - 4, y, zc), (xb, y, zc)]
                cable(rounded_path(pts, 5.0), row=i, kind="power-jumper", color=col, radius=0.7)

    # --- row transforms for the viewer -------------------------------------------------
    rows_out = []
    for i in range(n_rows + 1):
        origin, tilt = rack.row_matrix(i)
        rows_out.append({"id": rack.rows[i]["id"] if i < n_rows else "cap", "origin": origin, "tilt": tilt,
                         "height": rack.rows[i]["height"] if i < n_rows else 0,
                         "layout": rack.layout(i) if i < n_rows else [1] * rack.units})
    scene = {
        "units": "mm", "up": "z",
        "rack": {"width": W, "depth": D, "height": rack.height, "base_height": rack.base_height, "rows": rows_out,
                 "drawer_travel": d["travel"], "plenum": plenum, "pitch": pitch, "panel": T,
                 "bay_depth": BD, "inner_x0": rack.inner_x0},
        "print": {"layer": LAYER_H, "up": {name: print_up(name) for name in sorted(stats)}},
        "dupont": DUPONT, "header": HEADER,
        **items, "bays": bays,
    }
    out = SITE_ASSETS / "rack.json"
    out.write_text(json.dumps(scene, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", out, f"({out.stat().st_size / 1024:.0f} kB)", "and parts.glb",
          f"({(SITE_ASSETS / 'parts.glb').stat().st_size / 1e6:.1f} MB)")
    return out
