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


# ------------------------------------------------------------------ USB plugs
# Plug dimensions (mm): metal shell (goes into the receptacle), overmold, strain relief.
# Right-angle plugs (the short DUT cables) let the cable leave upwards.
PLUG = {"usb-c": (6.5, 15.0, 7.0), "micro-b": (5.5, 13.0, 6.0), "mini-b": (6.0, 14.0, 6.0), "usb-a": (12.0, 20.0, 8.0)}
RIGHT_ANGLE = (12.0, 9.0, 6.0)        # overmold depth along the plug, height above its axis, relief


def plug_exit(end):
    """Where the cable leaves a plug and which way: straight plugs out of their back, right-angle
    plugs out of their top.  end = {at: receptacle face, dir: into the receptacle, up, type, style}."""
    at, d = np.array(end["at"], float), np.array(end["dir"], float)
    up = np.array(end.get("up", (0, 0, 1)), float)
    if end.get("style") == "right":
        depth, height, relief = RIGHT_ANGLE
        return at - d * depth / 2 + up * (height + relief), up
    _, mold, relief = PLUG[end["type"]]
    return at - d * (mold + relief), -d


def usb_cable(a, b, reach=22.0, n=28):
    """Cable between two plugs: leaves each along its exit direction, a cubic in between."""
    pa, ta = plug_exit(a)
    pb, tb = plug_exit(b)
    return bezier(pa, pa + ta * reach, pb + tb * reach, pb, n)


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
             "leds": []}
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
    data_ports = rack.data_port_x          # two DATA socket positions per drawer
    port_z = d["bottom"] + 8.5            # lib/carrier.scad › PORT_Z
    plate_x0 = d["wall"] + 0.3
    plate_y0 = d["front_thickness"] + 0.3
    plate_w = rack.drawer_w - 2 * d["wall"] - 0.6
    plate_d = port_wall_y - d["wall"] - d["front_thickness"] - 0.6
    fixed = raw["chain"]["fixed"]

    def unit_hardware(i, u, bid, dy, open_frac):
        """Tray, drawer, chain and node for one bay."""
        x0 = rack.unit_x(u)
        add("tray", (x0, 0, 0), row=i, layer="trays", bay=bid)
        add("drawer", (x0 + rack.drawer_x0, dy, plenum), row=i, layer="drawers", bay=bid, movable=True)
        chain_z = c["bottom"] + raw["chain"]["outer"][0] / 2 + 0.6
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
        # extension cable: straight USB-C plug in the node's DUT port, then into the drag chain,
        # whose moving end carries it to the panel-mount socket at the drawer's rear (DATA port)
        ext_a = {"at": [x0 + node["x0"] + node["size"][0] + 0.4,
                        rack.node_front_y + node["size"][1] - node["right"]["dut"], pcb_top + 1.6],
                 "dir": [-1, 0, 0], "type": "usb-c", "style": "straight"}
        pa, ta = plug_exit(ext_a)
        end = (x0 + fixed[0], fixed[1] - 4, chain_z)
        cable(bezier(pa, pa + ta * 16, (end[0], end[1] - 22, end[2]), end), row=i, kind="ext", bay=bid,
              radius=1.6, ends=[ext_a], label="Drawer extension (runs through the drag chain)")
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
                bx = dxw + plate_x0 + 6
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
                                    "verified": bd.get("verified", False), "movable": True})
            # DUT cable: drawer DATA port → board USB connector.  The DATA socket goes in the port
            # farther from the board's USB (the right one for a USB turned to the right wall), so
            # the two plugs never meet
            if o["usb_side"]:
                sx = dxw + max(data_ports)
            else:
                sx = max((dxw + px for px in data_ports), key=lambda x: abs(x - (bx + o["usb_x"])))
            meta["data_port"] = ["left" if sx - dxw < rack.drawer_w / 2 else "right"]
            # short right-angle cable: USB-C into the panel-mount socket on the drawer's rear wall,
            # the board's own connector (micro-B, USB-C…) at the other end, an arch in between
            ctype = info["cable"]
            btype = cables_cfg[ctype].get("b", "usb-c")
            end_a = {"at": [sx, dy + port_wall_y - d["wall"] - 2.5, dz + port_z], "dir": [0, 1, 0],   # mouth on the flange's face
                     "type": "usb-c", "style": "right", "socket": "panel"}
            zc = bz + 1.6 + (1.4 if btype != "usb-c" else 1.65)
            ux = o["usb_x"]
            if o["usb_side"]:
                end_b = {"at": [bx + o["w"] + 0.6, by + ux, zc], "dir": [-1, 0, 0], "type": btype, "style": "right"}
            else:
                end_b = {"at": [bx + ux, by + o["l"] + 0.6, zc], "dir": [0, -1, 0], "type": btype, "style": "right"}
            cable(usb_cable(end_a, end_b, 26), row=i, kind="dut", bay=b.id, type=ctype,
                  label=cables_cfg[ctype]["label"], a="usb-c", b=btype, ends=[end_a, end_b], radius=1.9,
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
        # camera pod: on the ceiling = the bottom of the tray above (or the cap plate)
        if b.id in cams:
            cm = raw["bay"]["camera_mount"]
            add("camera_mount", (x0 + cm[0], cm[1], 0), row=i + 1, layer="cameras", bay=b.id)
            add("camera_cradle", (x0 + cm[0], cm[1], -14 - 3), row=i + 1, layer="cameras", bay=b.id)
            items["boxes"].append({"kind": "xiao", "layer": "cameras", "bay": b.id, "row": i + 1, "space": "row",
                                   "pos": [x0 + cm[0] - 10.5, cm[1] - 8.9, -14 - 3 - 17], "size": [21, 17.8, 15],
                                   "color": "#202a44"})
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
