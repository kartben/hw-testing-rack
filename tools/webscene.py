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
    "floor_plate": ("parts/tray.scad", {"PART": "floor_plate"}),
    "cap_plate": ("parts/tray.scad", {"PART": "cap_plate"}),
    "chain_foot": ("parts/chain_parts.scad", {"PART": "foot"}),
    "chain_anchor": ("parts/chain_parts.scad", {"PART": "anchor"}),
    "camera_mount": ("parts/camera_pod.scad", {"PART": "mount"}),
    "camera_cradle": ("parts/camera_pod.scad", {"PART": "cradle"}),
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
# the node's J7 (DATA, JST PH 5 vertical): KiCad (40, 37.4) in electronics/bay-node/design.py; mated 8 mm tall
NODE_J7 = (40.0, 37.4, 8.0)


def dataport_parts(rack) -> dict:
    """The DATA port board's stand-in (parts/usb_plugs.scad), sized from config/rack.yaml › pcb.data_port."""
    dp = rack.raw["pcb"]["data_port"]
    defs = {"STYLE": "dataport", "BW": dp["size"][0], "BD": dp["size"][1], "BT": dp["thickness"],
            "HOLES": dp["holes"], "USBX": dp["usb"], "PHX": dp["ph"]}
    return {f"dataport_{k}": ("parts/usb_plugs.scad", {**defs, "PIECE": k}, None) for k in ("pcb", "usb", "ph")}

# Parts whose print orientation differs from their assembly orientation get an
# "assembly" variant rendered with the print rotation undone.
ASSEMBLY_WRAPPERS = {
    "camera_mount": "use <parts/camera_pod.scad>\ninclude <lib/carrier.scad>\nmount();\n",
    "camera_cradle": "use <parts/camera_pod.scad>\ninclude <lib/carrier.scad>\ncradle();\n",
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
    used = sorted({p["board"] for p in rack.raw.get("population", {}).values()})
    for bid in used:
        parts[f"plate_{bid}"] = ("parts/board_plate.scad", {"BOARD": bid}, None)
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

# The bay camera (2026-10-18 hand-over): an Arducam Mega 3MP (B0434, 33 × 33 mm PCB; Arducam gives 35 mm overall
# with its stock M12 lens, publishes no 3D model) fitted with a ~120° M12 lens, which is shorter: Ø14 front, 9.5 mm
# out of the holder.  Wired to the bay's own node, its lens over bay X 64, Y 84 (the one spot that frames every board
# in the population), looking straight down; on each side a light box, 3 white LEDs behind a 1 mm white PETG
# diffuser.  The real pod is the mechanics' (mechanical/parts/camera_pod.scad): move these numbers to
# config/rack.yaml with it.
VIEWER_CAMERAS = ("B2",)                # the user, 2026-10-18: one camera in the viewer, in B2
CAMERA_RIG = {
    "plate": [66, 34, 3],                # the pod's plate under the ceiling, centred on the lens
    "standoff": 3,                       # plate → the Mega's PCB
    "board": [33, 33, 1.6],              # the Mega's PCB, lens down
    "holder": [14, 10.5, 22],            # M12 holder: square base, height, span of its two screw ears
    "optic": [14, 12, 9.5],              # 120° M12 lens: front ring Ø, barrel Ø, length out of the holder
    "fov": 120, "aspect": 4 / 3,         # diagonal field of view (fisheye), sensor aspect
    "lights": [{"at": [s * 25.5, 0], "size": [12, 26], "gap": 8, "leds": 3, "diffuser": 1.0} for s in (-1, 1)],
}
CAMERA_LENS = (64.0, 84.0, round(CAMERA_RIG["plate"][2] + CAMERA_RIG["standoff"] + CAMERA_RIG["board"][2]
                                 + CAMERA_RIG["holder"][1] + CAMERA_RIG["optic"][2], 2))   # bay X, Y; drop below the ceiling


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
    if end["type"] == "ph5":                                # a JST PHR-5: its wires leave its back
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


def rounded_path(pts, r, step=2.0):
    """A polyline with its corners rounded (a quadratic curve within r of each corner): a flexible lead."""
    pts = [np.array(p, float) for p in pts]
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
    cams = set(raw.get("cameras", [])) & set(VIEWER_CAMERAS)   # config: the rack's cameras (BOM); the viewer shows one
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

    def unit_hardware(i, u, bid, dy, open_frac):
        """Tray, drawer, chain and node for one bay."""
        x0 = rack.unit_x(u)
        add("tray", (x0, 0, 0), row=i, layer="trays", bay=bid)
        add("drawer", (x0 + rack.drawer_x0, dy, plenum), row=i, layer="drawers", bay=bid, movable=True)
        add("chain_anchor", (x0 + fixed[0], fixed[1], c["bottom"] + 3), row=i, layer="chain", bay=bid)
        add("chain_foot", (x0 + raw["chain"]["moving_x"], raw["chain"]["moving_y"] + dy, plenum), row=i,
            layer="chain", bay=bid, movable=True)
        items["chains"].append({"bay": bid, "row": i, "origin": [x0, 0, 0], "open": open_frac,
                                "fixed": fixed, "moving_x": raw["chain"]["moving_x"],
                                "moving_y": raw["chain"]["moving_y"], "bend_y": raw["chain"]["bend_y"],
                                "radius": raw["chain"]["radius"], "travel": d["travel"], "z": chain_z,
                                "width": raw["chain"]["outer"][0], "height": raw["chain"]["outer"][1],
                                "pitch": raw["chain"]["pitch"]})
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
        for k in ("pcb", "usb", "ph"):
            add(f"dataport_{k}", (dxw_ + dp_x0, dy + dp_y0, plenum + dp_z), row=i, layer="drawers", bay=bid,
                movable=True)
        j7 = {"at": [x0 + node["x0"] + NODE_J7[0], rack.node_front_y + node["size"][1] - NODE_J7[1],
                     pcb_top + NODE_J7[2] - 6.0], "dir": [0, 0, -1], "up": [0, 1, 0], "type": "ph5"}
        p0, _ = plug_exit(j7)
        top = plenum - 2.0                                 # under the drawer
        cable(rounded_path([p0, (p0[0], p0[1], top), (x0 + fixed[0], fixed[1] - 21, top),
                            (x0 + fixed[0], fixed[1] - 11, chain_z), (x0 + fixed[0], fixed[1], chain_z)], 6.0),
              row=i, kind="ext", bay=bid, radius=1.2, ends=[j7], label="DATA lead (JST PH 5, through the drag chain)")
        ph = {"at": [dxw_ + dp_x0 + dp["ph"], dy + dp_y0 + dp["size"][1], plenum + dp_z + dp["thickness"] + 2.8],
              "dir": [0, -1, 0], "up": [0, 0, 1], "type": "ph5"}
        mouth = (x0 + raw["chain"]["moving_x"], raw["chain"]["moving_y"] + dy, chain_z)
        x_run = max(ph["at"][0], x0 + fixed[0] + raw["chain"]["outer"][1] / 2 + 6.0)   # 6 mm off the fixed run
        cable(lead_to_board(ph, mouth, z_low=9.0, x_run=x_run), row=i, kind="ext", bay=bid, radius=1.2, ends=[ph],
              label="DATA lead (JST PH 5, through the drag chain)", movable=True)
        return x0, plenum

    for b in rack.bays():
        i = b.row
        info = pop.get(b.id, {})
        open_frac = 1.0 if info.get("open") else 0.0
        dy = -d["travel"] * open_frac
        x0, dz = unit_hardware(i, b.unit, b.id, dy, open_frac)
        dxw = x0 + rack.drawer_x0
        meta = {"id": b.id, "row": rack.rows[i]["id"], "row_index": i, "col": b.index + 1, "span": 1,
                "camera": b.id in cams, "unit_x": x0,
                "label_pos": [x0 + rack.carrier_w / 2, -3, plenum + d["front_height"] + 6]}
        if info:
            bd = boards[info["board"]]
            o = rackcfg.orient_board(bd)
            cab = cables_cfg[info["cable"]]
            add(f"plate_{info['board']}", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i,
                layer="plates", bay=b.id, movable=True)
            if o["usb_side"]:            # same placement as board_plate.scad
                bx = dxw + plate_x0 + 2.5    # board_plate.scad › SIDE_X
                by = dy + plate_y0 + (plate_d - o["l"]) / 2
            else:
                rear_gap = max(3, min(26, plate_d - o["l"] - 4))
                bx = dxw + plate_x0 + (plate_w - o["w"]) / 2
                by = dy + plate_y0 + plate_d - rear_gap - o["l"]
            bz = dz + d["bottom"] + d["plate"] + bd.get("standoff", 6)
            items["boards"].append({"bay": b.id, "row": i, "id": info["board"], "name": bd["name"],
                                    "label": bd.get("short", ""), "pos": [round(bx, 2), round(by, 2), round(bz, 2)],
                                    "size": [o["w"], o["l"], 1.6], "height": bd.get("height", 10),
                                    "color": bd.get("color", "#1b5e20"), "usb_x": o["usb_x"],
                                    "usb_type": bd["usb"]["type"], "usb2_x": o.get("usb2_x"),
                                    "usb_side": o["usb_side"],
                                    "verified": bd.get("verified", False), "movable": True,
                                    **({"model": mdl} if (mdl := board_model(info["board"], bd)) else {}),
                                    **({"screen": scr} if (scr := board_screen(bd)) else {})})
            # DUT cable: drawer DATA port → board USB connector.  The DATA socket goes in the port
            # farther from the board's USB (the right one for a USB turned to the right wall), so
            # the two plugs never meet
            if o["usb_side"]:
                sx = dxw + max(data_ports)
            else:
                sx = max((dxw + px for px in data_ports), key=lambda x: abs(x - (bx + o["usb_x"])))
            meta["data_port"] = ["left" if sx - dxw < rack.drawer_w / 2 else "right"]
            # short cable: USB-C into the panel-mount socket on the drawer's rear wall, the board's own
            # connector (micro-B, USB-C…) at the other end.  A board's USB facing the port wall:
            # right-angle plugs (`right`), or for a micro-B / mini-B board a 90° adapter with a
            # straight plug standing on it (`adapter`), and an arch in between; a small board turned
            # to the side wall (orient: side): straight plugs (`straight`) and one flat bend
            ctype = info["cable"]
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
            pts, short = route(end_a, end_b, free)
            if short:
                print(f"warning: bay {b.id}: the {ctype} cable is {short:.0f} mm too short "
                      f"from the DATA socket to the board")
            cable(pts, row=i, kind="dut", bay=b.id, type=ctype,
                  label=cables_cfg[ctype]["label"], a="usb-c", b=btype, ends=ends, radius=1.9,
                  movable=True)
            meta.update({"board": bd["name"], "board_id": info["board"], "cable": cab["label"],
                         "usb": bd["usb"]["type"], "classic": bool(info.get("pc_cable")), "open": bool(info.get("open")),
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
        # camera: an Arducam Mega under the ceiling (the bottom of the tray above, or the cap plate), wired to
        # this bay's own node; the viewer draws it, its light boxes and its preview (site/camera.js)
        if b.id in cams:
            lx, ly, drop = CAMERA_LENS
            up = rack.rows[i]["height"] * math.sin(math.radians(rack.tilt))    # the tray above sits further back
            cm = raw["bay"]["camera_mount"]          # the ceiling's insert square: the pod's arm reaches it
            items["cameras"].append({"bay": b.id, "row": i + 1, "space": "row", "layer": "cameras",
                                     "lens": [round(x0 + lx, 2), round(ly - up, 2), -drop],
                                     "mount": [round(cm[0] - lx, 2), round(cm[1] - (ly - up), 2), cm[2]], **CAMERA_RIG})
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
    # them mirrored, so each wire keeps its side: a flat lead, no twist
    for i, r in enumerate(rack.rows):
        zc = pcb_top + 5
        vy = rack.node_front_y + node["size"][1] - node["pwr_y"]
        for u in range(rack.units - 1):
            xa = rack.unit_x(u) + node["x0"] + node["size"][0]
            xb = rack.unit_x(u + 1) + node["x0"]
            for k, col in enumerate(("#c62828", "#222222", "#f9a825", "#2e7d32", "#222222", "#eeeeee")):
                y = vy + 5 - 2 * k                                # JST PH, 2 mm pitch, 24 AWG
                cable(bezier((xa, y, zc), (xa + 40, y - 4, zc + 2), (xb - 40, y - 4, zc + 2), (xb, y, zc)),
                      row=i, kind="power-jumper", color=col, radius=0.7)

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
