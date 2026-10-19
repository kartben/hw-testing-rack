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

import rackcfg
from build import BUILD, MECH, REPO, SITE_ASSETS, openscad_cmd

WEB_PARTS = {
    # name: (scad, defines)
    "tray": ("parts/tray.scad", {"PART": "tray"}),
    "drawer": ("parts/drawer.scad", {}),
    "drawer_sled": ("parts/drawer.scad", {"PART": "sled"}),
    "drawer_block": ("parts/drawer.scad", {"PART": "block"}),
    "drawer_x4": ("parts/drawer.scad", {"PORTS": 4}),                         # a converted bay's (`boards:`)
    "drawer_block_x4": ("parts/drawer.scad", {"PART": "block", "PORTS": 4}),
    "floor_plate": ("parts/tray.scad", {"PART": "floor_plate"}),
    "cap_plate": ("parts/tray.scad", {"PART": "cap_plate"}),
    "chain_foot": ("parts/chain_parts.scad", {"PART": "foot"}),
    "chain_anchor": ("parts/chain_parts.scad", {"PART": "anchor"}),
    "camera_pod": ("parts/camera_pod.scad", {"PART": "pod"}),
    "camera_diffuser": ("parts/camera_pod.scad", {"PART": "diffuser"}),
    "mega_camera": ("parts/camera_pod.scad", {"PART": "mega"}),
    "podpcb": ("parts/camera_pod.scad", {"PART": "podpcb"}),
    "podpcb_parts": ("parts/camera_pod.scad", {"PART": "podpcb_parts"}),
    "plate_universal": ("parts/board_plate.scad", {"BOARD": "universal"}),
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


# the row cable's tie anchors in the tray (tray.scad › JUMPER_TIES: carrier x, y of their centre)
JUMPER_TIES = [(118.0, 6.5), (150.0, 6.5)]


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
          "PHX": q["ph"], "PHY": q["notch"][1] + q["notch"][3], "NOTCH": q["notch"]}
    out.update({f"dataport_{k}_x4": ("parts/usb_plugs.scad", {**x4, "PIECE": k}, None) for k in ("pcb", "usb", "ph")})
    return out

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
    used = sorted({sl.board for b in rack.bays() if not rack.is_multi(b.id) for sl in rack.duts(b.id)})
    for bid in used:
        parts[f"plate_{bid}"] = ("parts/board_plate.scad", {"BOARD": bid}, None)
    for bay_id in rack.multi_bays():           # a converted bay: one plate for its boards
        parts[f"plate_bay_{bay_id.lower()}"] = ("parts/board_plate.scad", {"BAY": bay_id}, None)
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


def lead_to_board(e, mouth, z_low, x_run, depth=7.0):
    """The DATA lead from the drag chain's moving mouth (facing forwards) to the PH plug at the DATA
    board's rear edge, drawn from the plug: back out of it, down through the drawer's cable window,
    forwards under the drawer at z_low (over the camera-pod bosses) along x_run (clear of the chain's
    fixed run, which the drawer slides past), a flattened U-turn in front of the mouth (only `depth`
    deep: the tray's fascia is 17 mm ahead of it with the drawer out), in."""
    p0, d = plug_exit(e)
    p1 = p0 + d * 2.0
    p1b = np.array([x_run, p1[1], p1[2]])            # over to x_run still in the rear bay, then down
    p2 = np.array([x_run, p1[1], z_low])
    p3 = np.array([x_run, mouth[1] - 1.0, z_low])
    pts = rounded_path([p0, p1, p1b, p2, p3], 2.5)
    a, c = (mouth[0] - p3[0]) / 2, np.array([(mouth[0] + p3[0]) / 2, p3[1], 0.0])
    for t in np.linspace(0, math.pi, 16)[1:]:
        z = z_low + (mouth[2] - z_low) * t / math.pi
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


def camera_lead(j6, x0, node_right, row_h, tilt, lens, mount, depth, cp):
    """The camera's PH-8 lead (double-ended), in the bay's row coordinates: up out of the node's J6
    (vertical), over to the right of the node (under the DATA lead, which runs higher), back along the
    plenum and out of the tray's rear slot (x 20-80), straight up behind the tray's rear wall (square to
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
    xs, top = min(node_right + 8.0, x0 + 78.0), up_z - 2.0
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


def data_lead_short(j7, ph, x_run, top):
    """A sled bay's DATA lead (no drag chain): up out of the node's J7 to the plenum's top (under the sled),
    over to x_run right of the node (clear of the module's antenna at its rear edge), back along it, over to
    the port block's window and up through it into the DATA board's PH from the rear."""
    p0, _ = plug_exit(j7)
    q, _ = plug_exit(ph)
    yb = q[1] + 2.0
    pts = [p0, (p0[0], p0[1], top), (x_run, p0[1] + 12, top), (x_run, yb - 12, top), (q[0], yb, top),
           (q[0], yb, q[2]), q]
    return rounded_path(pts, 5.0)


def cable_free_length(cab, a, b):
    """A cable's length between its two strain reliefs: its length end to end less both plugs (a
    straight plug: shell, overmold and relief; a right-angle one: about its body's depth)."""
    def plug(e):
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
             "leds": [], "cameras": []}
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

    def unit_hardware(i, u, bid, dy, open_frac, drawer=True, x4=False):
        """Tray, node and either the drawer and its chain, or a sled bay's sled and port block (no chain; the
        viewer doesn't slide them: the DUT cable is unplugged first).  x4: a converted bay's (`boards:`) drawer
        or port block, with a DATA ×4 board."""
        x0 = rack.unit_x(u)
        add("tray", (x0, 0, 0), row=i, layer="trays", bay=bid)
        if drawer:
            add("drawer_x4" if x4 else "drawer", (x0 + rack.drawer_x0, dy, plenum), row=i, layer="drawers", bay=bid,
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
            for part in ("drawer_sled", "drawer_block_x4" if x4 else "drawer_block"):
                add(part, (x0 + rack.drawer_x0, 0, plenum), row=i, layer="drawers", bay=bid)
        info_ = pop.get(bid, {})
        led = "#2f7bff" if info_.get("pc_cable") else ("#ffb300" if info_.get("open") else "#19e07a")
        items["leds"].append({"bay": bid, "row": i, "space": "row", "color": led,
                              "pos": [x0 + node["x0"] + node["front"]["led"], 0.4, pcb_top + 0.7]})
        items["pcbs"].append({"board": "bay-node", "bay": bid, "row": i, "space": "row",
                              "pos": [x0 + node["x0"], rack.node_front_y + node["size"][1], c["bottom"] + c["standoff"]],
                              "size": [node["size"][0], node["size"][1], node["thickness"]]})
        # the DATA port board on its floor bosses in the drawer (components up) and its 5-wire PH lead: up
        # out of the node's J7, across the node under the drawer into the drag chain's fixed end; out of
        # its moving end, a U-turn, up through the drawer's cable window into the board's PH from the rear
        dxw_ = x0 + rack.drawer_x0
        if x4:                       # the DATA ×4 stand-in: its board and PH, a USB-C at each of the four ports
            q = raw["pcb"]["data_port_x4"]
            bx4 = dxw_ + q["x0"]
            for k in ("pcb", "ph"):
                add(f"dataport_{k}_x4", (bx4, dy + dp_y0, plenum + dp_z), row=i, layer="drawers", bay=bid,
                    movable=drawer)
            for n in range(1, 5):
                add("dataport_usb_x4", (dxw_ + x4_port_x(rack, n), dy + dp_y0, plenum + dp_z), row=i,
                    layer="drawers", bay=bid, movable=drawer)
            ph_xy = (bx4 + q["ph"], dy + dp_y0 + q["size"][1] - q["notch"][1] - q["notch"][3])
        else:
            for k in ("pcb", "usb", "ph"):
                add(f"dataport_{k}", (dxw_ + dp_x0, dy + dp_y0, plenum + dp_z), row=i, layer="drawers", bay=bid,
                    movable=drawer)
            ph_xy = (dxw_ + dp_x0 + dp["ph"], dy + dp_y0 + dp["size"][1])
        j7 = {"at": [x0 + node["x0"] + node["size"][0], rack.node_front_y + node["size"][1] - node["right"]["data"],
                     pcb_top + NODE_J7_Z], "dir": [-1, 0, 0], "up": [0, 0, 1], "type": "ph8"}
        ph = {"at": [ph_xy[0], ph_xy[1], plenum + dp_z + dp["thickness"] + 2.8],
              "dir": [0, -1, 0], "up": [0, 0, 1], "type": "ph8"}
        if not drawer:
            cable(data_lead_short(j7, ph, x0 + node["x0"] + node["size"][0] + 4.0, plenum - 3.0), row=i, kind="ext",
                  bay=bid, radius=1.2, ends=[j7, ph], label="DATA lead (JST PH 8, node J7 → the port block)")
            return x0, plenum
        p0, _ = plug_exit(j7)
        top = plenum - 2.0                                 # under the drawer
        cable(rounded_path([p0, (p0[0], p0[1], top), (x0 + fixed[0], fixed[1] - 21, top),
                            (x0 + fixed[0], fixed[1] - 11, chain_z), (x0 + fixed[0], fixed[1], chain_z)], 6.0),
              row=i, kind="ext", bay=bid, radius=1.2, ends=[j7], label="DATA lead (JST PH 8, through the drag chain)")
        mouth = (x0 + raw["chain"]["moving_x"], raw["chain"]["moving_y"] + dy, chain_z)
        x_run = max(ph["at"][0], x0 + fixed[0] + raw["chain"]["outer"][1] / 2 + 6.0)   # 6 mm off the fixed run
        cable(lead_to_board(ph, mouth, z_low=9.0, x_run=x_run), row=i, kind="ext", bay=bid, radius=1.2, ends=[ph],
              label="DATA lead (JST PH 8, through the drag chain)", movable=True)
        return x0, plenum

    def dut_board(i, bay, slot, board_id, bd, o, bx, by, dz, dy, drawer, ctype, sx):
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
        pts, short = route(end_a, end_b, free)
        if short:
            print(f"warning: {slot or bay}: the {ctype} cable is {short:.0f} mm too short "
                  f"from the DATA socket to the board")
        cable(pts, row=i, kind="dut", bay=bay, type=ctype, label=cables_cfg[ctype]["label"], a="usb-c", b=btype,
              ends=ends, radius=1.9, movable=drawer)

    for b in rack.bays():
        i = b.row
        info = pop.get(b.id, {})
        drawer = rack.mount(b.id) == "drawer"
        open_frac = 1.0 if info.get("open") and drawer else 0.0
        dy = -d["travel"] * open_frac
        x0, dz = unit_hardware(i, b.unit, b.id, dy, open_frac, drawer, rack.is_multi(b.id))
        dxw = x0 + rack.drawer_x0
        meta = {"id": b.id, "row": rack.rows[i]["id"], "row_index": i, "col": b.index + 1, "span": 1,
                "camera": b.id in cams, "unit_x": x0,
                "label_pos": [x0 + rack.carrier_w / 2, -3, plenum + d["front_height"] + 6]}
        if info and rack.is_multi(b.id):
            # a converted bay: one plate (board_plate.scad › BAY), its boards where rackcfg.bay_layout puts them,
            # each on its own DATA ×4 port
            add(f"plate_bay_{b.id.lower()}", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i,
                layer="plates", bay=b.id, movable=drawer)
            slots = []
            for e in rack.bay_layout(b.id, boards):
                # the board as turned on this plate: to the port wall unless its entry says `orient: side`
                sl, o = e["slot"], e["o"]
                bd = {**boards[e["board"]], "orient": sl.orient or "rear"}
                dut_board(i, b.id, sl.id, e["board"], bd, o, dxw + plate_x0 + e["at"][0], dy + plate_y0 + e["at"][1],
                          dz, dy, drawer, sl.cable, dxw + x4_port_x(rack, sl.slot))
                slots.append({"id": sl.id, "port": sl.slot, "board": bd["name"], "board_id": e["board"],
                              "cable": cables_cfg[sl.cable]["label"], "usb": bd["usb"]["type"],
                              "verified": bd.get("verified", False)})
            meta.update({"board": f"{len(slots)} boards on a DATA ×4", "slots": slots, "data_port": ["×4"],
                         "open": bool(info.get("open")) and drawer, "mount": rack.mount(b.id),
                         "verified": all(sl_["verified"] for sl_ in slots)})
        elif info:
            bd = boards[info["board"]]
            o = rackcfg.orient_board(bd)
            cab = cables_cfg[info["cable"]]
            add(f"plate_{info['board']}", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i,
                layer="plates", bay=b.id, movable=drawer)
            if o["usb_side"]:            # same placement as board_plate.scad
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
            dut_board(i, b.id, None, info["board"], bd, o, bx, by, dz, dy, drawer, info["cable"], sx)
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
            lead, pod_end, mega = camera_lead(j6, x0, x0 + node["x0"] + node["size"][0], rack.rows[i]["height"],
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
        **items, "bays": bays,
    }
    out = SITE_ASSETS / "rack.json"
    out.write_text(json.dumps(scene, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", out, f"({out.stat().st_size / 1024:.0f} kB)", "and parts.glb",
          f"({(SITE_ASSETS / 'parts.glb').stat().st_size / 1e6:.1f} MB)")
    return out
