"""Build the 3D viewer assets: site/assets/parts.glb + site/assets/rack.json.

parts.glb holds ONE mesh per printed part type (simplified for the web);
rack.json says where every instance goes, plus the procedural stand-ins
(extrusions, dev boards, PSU), the drag chains and every cable as a curve.
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
    "carrier_base": ("parts/carrier_base.scad", {}),
    "carrier_deck": ("parts/carrier_deck.scad", {}),
    "drawer": ("parts/drawer.scad", {}),
    "drawer_guide_left": ("parts/drawer_guide.scad", {"SIDE": "left"}),
    "drawer_guide_right": ("parts/drawer_guide.scad", {"SIDE": "right"}),
    "chain_foot": ("parts/chain_parts.scad", {"PART": "foot"}),
    "chain_anchor": ("parts/chain_parts.scad", {"PART": "anchor"}),
    "camera_mount": ("parts/camera_pod.scad", {"PART": "mount"}),
    "camera_cradle": ("parts/camera_pod.scad", {"PART": "cradle"}),
    "roof_deck": ("parts/roof_deck.scad", {}),
    "base_plate": ("parts/base.scad", {"PART": "plate"}),
    "base_psu_saddle": ("parts/base.scad", {"PART": "psu_saddle"}),
    "base_inlet_panel": ("parts/base.scad", {"PART": "inlet_panel"}),
    "base_side_panel": ("parts/base.scad", {"PART": "side_panel"}),
    "base_front_panel": ("parts/base.scad", {"PART": "front_panel"}),
    "base_hub_mount": ("parts/base.scad", {"PART": "hub_mount"}),
    "foot": ("parts/frame_parts.scad", {"PART": "foot"}),
    "plate_universal": ("parts/board_plate.scad", {"BOARD": "universal"}),
    "tier_bracket_left": ("parts/tier_bracket.scad", {"SIDE": "left"}),
    "tier_bracket_right": ("parts/tier_bracket.scad", {"SIDE": "right"}),
    "bridge_bar": ("parts/bridge_bar.scad", {}),
}

# Parts whose print orientation differs from their assembly orientation get an
# "assembly" variant rendered with the print rotation undone.
ASSEMBLY_WRAPPERS = {
    "camera_mount": "use <parts/camera_pod.scad>\ninclude <lib/carrier.scad>\nmount();\n",
    "camera_cradle": "use <parts/camera_pod.scad>\ninclude <lib/carrier.scad>\ncradle();\n",
    "chain_foot": "use <parts/chain_parts.scad>\ninclude <lib/carrier.scad>\nfoot();\n",
    "base_inlet_panel": "use <parts/base.scad>\ninclude <lib/carrier.scad>\ninlet_panel();\n",
    "base_side_panel": "use <parts/base.scad>\ninclude <lib/carrier.scad>\nside_panel();\n",
    "base_front_panel": "use <parts/base.scad>\ninclude <lib/carrier.scad>\nfront_panel();\n",
}


def render_web_stl(name: str, scad: str, defines: dict, fn: int = 28, sub: str = "web") -> Path:
    out = BUILD / sub / f"{name}.stl"
    out.parent.mkdir(parents=True, exist_ok=True)
    src = scad
    if name in ASSEMBLY_WRAPPERS:
        wrapper = MECH / "build" / "web" / f"_{name}.scad"
        wrapper.write_text(ASSEMBLY_WRAPPERS[name], encoding="utf-8")
        src = wrapper.relative_to(MECH).as_posix()
        # wrapper lives in build/web: make its relative includes resolve from mechanical/
        wrapper.write_text(ASSEMBLY_WRAPPERS[name].replace("<parts/", "<../../parts/").replace("<lib/", "<../../lib/"),
                           encoding="utf-8")
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

    parts = dict(WEB_PARTS)
    used = sorted({p["board"] for p in rack.raw.get("population", {}).values()
                   if boards.get(p["board"], {}).get("span", 1) == 1})
    for bid in used:
        parts[f"plate_{bid}"] = ("parts/board_plate.scad", {"BOARD": bid})
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(render_web_stl, n, s, d, *((64, "hq") if hq else ())): n for n, (s, d) in parts.items()}
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
    """
    boards = rackcfg.load_boards()
    print("rendering web meshes ...")
    stats = build_parts_glb(rack, boards)
    for k, v in stats.items():
        print(f"  {k:28s} {v:7d} tris")

    raw = rack.raw
    P = rack.profile
    W, D = rack.width, rack.depth
    BD = rack.bay_depth
    c = rack.carrier
    d = rack.drawer
    node = rack.node
    pcb_top = rack.pcb_top
    plenum = rack.plenum
    wall_h = rack.wall_h
    pop = raw.get("population", {})
    cams = set(raw.get("cameras", []))
    cables_cfg = raw["cables"]
    n_rows = len(rack.rows)
    x_in = rack.inner_x0

    items = {"instances": [], "frame": [], "cables": [], "chains": [], "boards": [], "pcbs": [], "boxes": [],
             "leds": []}
    bays = []

    def add(part, pos, rot=(0, 0, 0), space="row", row=None, **meta):
        items["instances"].append({"part": part, "pos": [round(v, 3) for v in pos], "rot": list(rot),
                                   "space": space, "row": row, **meta})

    def cable(points, space="row", row=None, **meta):
        items["cables"].append({"points": points, "space": space, "row": row, **meta})

    # --- frame posts and base box (frame space) ---------------------------------------
    front_post_h = rack.to_frame(n_rows, [0, P / 2, P / 2])[2] + 26
    rear_post_h = rack.to_frame(n_rows, [0, BD - P / 2, P / 2])[2] + 26
    for x in (P / 2, W - P / 2):
        items["frame"].append({"from": [x, P / 2, 0], "to": [x, P / 2, front_post_h], "role": "post", "space": "frame"})
        items["frame"].append({"from": [x, D - P / 2, 0], "to": [x, D - P / 2, rear_post_h], "role": "post",
                               "space": "frame"})
        for y in (P / 2, D - P / 2):
            add("foot", (x, y, 0), (180, 0, 0), space="frame", layer="frame")
    bh = rack.base_height
    for zc in (P / 2, bh - P / 2):
        for y in (P / 2, D - P / 2):
            items["frame"].append({"from": [P, y, zc], "to": [W - P, y, zc], "role": "beam", "space": "frame"})
        for x in (P / 2, W - P / 2):
            items["frame"].append({"from": [x, P, zc], "to": [x, D - P, zc], "role": "beam", "space": "frame"})

    # --- rows (and the roof "row") ------------------------------------------------------
    for i in range(n_rows + (1 if raw["frame"].get("top_cap", True) else 0)):
        # beams in row space, brackets in frame space (they are vertical plates)
        for y in (P / 2, BD - P / 2):
            items["frame"].append({"from": [x_in, y, P / 2], "to": [W - x_in, y, P / 2], "role": "beam",
                                   "space": "row", "row": i})
        add("tier_bracket_left", (P, 0, rack.row_z(i)), space="frame", row=i, layer="frame")
        add("tier_bracket_right", (W - P, 0, rack.row_z(i)), space="frame", row=i, layer="frame")
        if i == n_rows:
            for u in range(rack.units):
                add("roof_deck", (rack.unit_x(u), 0, P), row=i, layer="roof")

    port_wall_y = d["depth"] - d["rear_bay"]
    port_x = rack.drawer_w * 0.38
    port_z = d["bottom"] + 7
    plate_x0 = d["wall"] + 0.3
    plate_y0 = d["front_thickness"] + 0.3
    plate_w = rack.drawer_w - 2 * d["wall"] - 0.6
    plate_d = port_wall_y - d["front_thickness"] - 0.6
    drawer_inner_w = rack.drawer_w - 2 * d["wall"]
    fixed = raw["chain"]["fixed"]

    def unit_hardware(i, u, bid, dy, open_frac, with_node=True):
        """Carrier, deck, guides, drawer, chain and node for one unit."""
        x0 = rack.unit_x(u)
        z0 = P
        add("carrier_base", (x0, 0, z0), row=i, layer="carrier", bay=bid)
        add("carrier_deck", (x0, 0, z0 + wall_h), row=i, layer="deck", bay=bid)
        add("drawer_guide_left", (x0, 0, z0 + plenum), row=i, layer="guides", bay=bid)
        add("drawer_guide_right", (x0, 0, z0 + plenum), row=i, layer="guides", bay=bid)
        add("drawer", (x0 + rack.drawer_x0, dy, z0 + plenum), row=i, layer="drawers", bay=bid, movable=True)
        add("chain_anchor", (x0 + fixed[0], fixed[1] - 8, z0 + c["bottom"] + 3), row=i, layer="chain", bay=bid)
        add("chain_foot", (x0 + raw["chain"]["moving_x"], raw["chain"]["foot_y"] + dy, z0 + plenum), row=i,
            layer="chain", bay=bid, movable=True)
        items["chains"].append({"bay": bid, "row": i, "origin": [x0, 0, z0], "open": open_frac,
                                "fixed": fixed, "moving_x": raw["chain"]["moving_x"],
                                "foot_y": raw["chain"]["foot_y"], "bend_y": raw["chain"]["bend_y"],
                                "radius": raw["chain"]["radius"], "travel": d["travel"],
                                "z": c["bottom"] + raw["chain"]["outer"][0] / 2 + 0.6,
                                "width": raw["chain"]["outer"][0], "height": raw["chain"]["outer"][1]})
        if with_node:
            info_ = pop.get(bid, {})
            led = "#2f7bff" if info_.get("pc_cable") else ("#ffb300" if info_.get("open") else "#19e07a")
            items["leds"].append({"bay": bid, "row": i, "space": "row", "color": led,
                                  "pos": [x0 + node["x0"] + node["front"]["led"], 0.4,
                                          z0 + pcb_top + 0.7]})
            items["pcbs"].append({"board": "bay-node", "bay": bid, "row": i, "space": "row",
                                  "pos": [x0 + node["x0"], rack.node_front_y + node["size"][1],
                                          z0 + c["bottom"] + c["standoff"]],
                                  "size": [node["size"][0], node["size"][1], node["thickness"]]})
            ex0 = (x0 + node["x0"] + node["size"][0] + 6, rack.node_front_y + node["size"][1] - node["right"]["dut"],
                   z0 + pcb_top + 1.6)
            cable(bezier(ex0, (ex0[0] + 18, ex0[1], ex0[2]), (x0 + fixed[0], fixed[1] - 22, z0 + 8.6),
                         (x0 + fixed[0], fixed[1] - 4, z0 + 8.6)), row=i, kind="ext", bay=bid, radius=1.6,
                  label="Drawer extension (runs through the drag chain)")
        return x0, z0 + plenum

    for b in rack.bays():
        i = b.row
        info = pop.get(b.id, {})
        open_frac = 1.0 if info.get("open") else 0.0
        dy = -d["travel"] * open_frac
        units = list(range(b.unit, b.unit + b.span))
        drawers = [unit_hardware(i, u, b.id, dy, open_frac, with_node=True) for u in units]
        x0, dz = drawers[0]
        dxw = x0 + rack.drawer_x0
        meta = {"id": b.id, "row": rack.rows[i]["id"], "row_index": i, "col": b.index + 1, "span": b.span,
                "camera": b.id in cams, "unit_x": rack.unit_x(b.unit),
                "label_pos": [rack.unit_x(b.unit) + (b.span * rack.pitch - rack.raw["bay"]["gap"]) / 2, -3,
                              P + plenum + d["front_height"] + 6]}
        if info:
            bd = boards[info["board"]]
            o = rackcfg.orient_board(bd)
            cab = cables_cfg[info["cable"]]
            if b.span == 1:
                add(f"plate_{info['board']}", (dxw + plate_x0, dy + plate_y0, dz + d["bottom"]), row=i,
                    layer="plates", bay=b.id, movable=True)
                rear_gap = max(3, min(26, plate_d - o["l"] - 4))
                bx = dxw + plate_x0 + (plate_w - o["w"]) / 2
                by = dy + plate_y0 + plate_d - rear_gap - o["l"]
                bz = dz + d["bottom"] + d["plate"] + bd.get("standoff", 6)
            else:
                # double bay: two bridge bars across both drawers, EVK on 12 mm standoffs
                bar_z = dz + d["bottom"]
                inner_x = dxw + d["wall"]
                add("bridge_bar", (inner_x, dy + plate_y0 + 4, bar_z), row=i, layer="plates", bay=b.id, movable=True)
                add("bridge_bar", (inner_x + rack.pitch + drawer_inner_w, dy + plate_y0 + plate_d - 4, bar_z),
                    (0, 0, 180), row=i, layer="plates", bay=b.id, movable=True)
                span_w = rack.pitch + drawer_inner_w
                bx = inner_x + (span_w - o["w"]) / 2
                by = dy + plate_y0 + (plate_d - o["l"]) / 2 - 6
                bz = bar_z + (d["wall_height"] - d["bottom"] + 0.5) + 6 + 12
            items["boards"].append({"bay": b.id, "row": i, "id": info["board"], "name": bd["name"],
                                    "label": bd.get("short", ""), "pos": [round(bx, 2), round(by, 2), round(bz, 2)],
                                    "size": [o["w"], o["l"], 1.6], "height": bd.get("height", 10),
                                    "color": bd.get("color", "#1b5e20"), "usb_x": o["usb_x"],
                                    "usb_type": bd["usb"]["type"], "usb2_x": o.get("usb2_x"),
                                    "verified": bd.get("verified", False), "movable": True})
            # DUT cable(s): drawer DATA port(s) → board USB connector(s)
            targets = [(dxw + port_x, o["usb_x"], info["cable"])]
            if b.span == 2 and o.get("usb2_x") is not None:
                targets.append((dxw + rack.pitch + port_x, o["usb2_x"], "c-to-c"))
            for sx, ux, ctype in targets:
                ps = (sx, dy + port_wall_y - d["wall"] - 6, dz + port_z)
                pe = (bx + ux, by + o["l"] + 3, bz + 2.0)
                mid_y = (ps[1] + pe[1]) / 2
                cable(bezier(ps, (ps[0], mid_y + 4, max(ps[2], pe[2]) + 4), (pe[0] + 10, mid_y, pe[2] + 6), pe),
                      row=i, kind="dut", bay=b.id, type=ctype, label=cables_cfg[ctype]["label"], a="usb-c",
                      b=cables_cfg[ctype].get("b", "usb-c"), radius=1.9, movable=True)
            meta.update({"board": bd["name"], "board_id": info["board"], "cable": cab["label"],
                         "usb": bd["usb"]["type"], "classic": bool(info.get("pc_cable")), "open": bool(info.get("open")),
                         "verified": bd.get("verified", False)})
            if info.get("pc_cable"):
                fx = x0 + node["x0"] + node["front"]["pc_port"]
                fz = P + pcb_top + 1.6
                pts = [rack.to_frame(i, p) for p in ((fx, -8, fz), (fx, -120, fz + 10))]
                end = [W + 280, -60, 0]
                cable(bezier(pts[0], pts[1], [W + 200, -160, pts[1][2] - 80], end), space="frame", kind="pc",
                      bay=b.id, label="Laptop → front PC port (classic mode)", a="usb-c", b="usb-a", radius=2.0)
        # camera pod: on the ceiling = carrier bottom of the row above (or the roof)
        if b.id in cams:
            cm = raw["bay"]["camera_mount"]
            ux = rack.unit_x(b.unit)
            add("camera_mount", (ux + cm[0], cm[1], P), row=i + 1, layer="cameras", bay=b.id)
            add("camera_cradle", (ux + cm[0], cm[1], P - 14 - 3), row=i + 1, layer="cameras", bay=b.id)
            items["boxes"].append({"kind": "xiao", "layer": "cameras", "bay": b.id, "row": i + 1, "space": "row",
                                   "pos": [ux + cm[0] - 10.5, cm[1] - 8.9, P - 14 - 3 - 17], "size": [21, 17.8, 15],
                                   "color": "#202a44"})
        meta["center"] = rack.to_frame(i, [rack.unit_x(b.unit) + b.span * rack.pitch / 2, BD / 2, plenum + 40])
        bays.append(meta)

    # --- row power: jumpers between adjacent nodes, feeds from the hub ------------------
    for i, r in enumerate(rack.rows):
        zc = P + pcb_top + 5
        vy = rack.node_front_y + node["size"][1] - node["vh_y"]
        for u in range(rack.units - 1):
            xa = rack.unit_x(u) + node["x0"] + node["size"][0]
            xb = rack.unit_x(u + 1) + node["x0"]
            for k, col in ((0, "#c62828"), (1, "#222222")):
                off = (k - 0.5) * 3
                cable(bezier((xa, vy + off, zc), (xa + 40, vy + off - 4, zc + 2), (xb - 40, vy + off - 4, zc + 2),
                             (xb, vy + off, zc)), row=i, kind="power-jumper", color=col, radius=1.1)
        # feed: hub (base, right side) → up the rear-left post → the row's first node
        hub_end = [rack.unit_x(3) + 40, D / 2 + 20, P + 3 + 9 + 12]
        entry = rack.to_frame(i, [rack.unit_x(0) + node["x0"], vy, zc])
        rear = rack.to_frame(i, [x_in - 3, BD - 30, zc])
        for k, col in ((0, "#c62828"), (1, "#222222")):
            off = (k - 0.5) * 3 + i * 1.6
            pts = [[hub_end[0], hub_end[1] + off, hub_end[2]], [P + 6 + off, D - 30, P + 10],
                   [P + 6 + off, D - 26, rear[2] - 20], [x_in - 3 + off, rear[1], rear[2]],
                   [x_in - 3 + off, entry[1] + 20, entry[2]], [entry[0], entry[1] + off, entry[2]]]
            cable(poly(*pts), space="frame", kind="power-feed", color=col, radius=1.1, smooth=True)

    # --- base: plates, PSU, hub, panels (frame space) ---------------------------------
    for u in range(rack.units):
        add("base_plate", (rack.unit_x(u), 7.5, P), space="frame", layer="base")
    psu = [194, 55, 26]
    psu_pos = [rack.unit_x(1) + rack.pitch - psu[0] / 2, D / 2 - psu[1] / 2 - 10, P + 3 + 3]
    items["boxes"].append({"kind": "psu", "layer": "base", "space": "frame", "pos": psu_pos, "size": psu,
                           "color": "#b8bcc2", "label": "Mean Well UHP-200-24"})
    for sx in (psu_pos[0] + 30, psu_pos[0] + psu[0] - 48):
        add("base_psu_saddle", (sx + 9, psu_pos[1] + psu[1] / 2, P + 3), (0, 0, 90), space="frame", layer="base")
    hub = raw["pcb"]["power_hub"]["size"]
    hub_pos = [rack.unit_x(3) + rack.carrier_w / 2 - hub[0] / 2, D / 2 - hub[1] / 2, P + 3 + 9]
    add("base_hub_mount", (hub_pos[0] - 4, hub_pos[1] - 4, P + 3), space="frame", layer="base")
    items["pcbs"].append({"board": "power-hub", "space": "frame", "pos": [hub_pos[0], hub_pos[1] + hub[1], hub_pos[2]],
                          "size": [hub[0], hub[1], 1.6]})
    for u in range(rack.units):
        add("base_front_panel", (rack.unit_x(u), -3, P), space="frame", layer="base-panels")
        add("base_inlet_panel" if u == 0 else "base_front_panel", (rack.unit_x(u) + rack.carrier_w, D + 3, P),
            (0, 0, 180), space="frame", layer="base-panels")
    add("base_side_panel", (0, P, P), (0, 0, 90), space="frame", layer="base-panels")
    add("base_side_panel", (W, D - P, P), (0, 0, 270), space="frame", layer="base-panels")
    inlet = [rack.unit_x(0) + rack.carrier_w * 0.65, D + 6, P + (bh - 2 * P) / 2]
    cable(bezier(inlet, [inlet[0] - 20, D + 90, inlet[2] - 10], [inlet[0] - 70, D + 150, 0], [inlet[0] - 120, D + 260, 0]),
          space="frame", kind="mains", label="IEC C13 mains cord", radius=3.2, color="#111111")

    # --- row transforms for the viewer -------------------------------------------------
    rows_out = []
    for i in range(n_rows + 1):
        origin, tilt = rack.row_matrix(i)
        rows_out.append({"id": rack.rows[i]["id"] if i < n_rows else "roof", "origin": origin, "tilt": tilt,
                         "height": rack.rows[i]["height"] if i < n_rows else 0,
                         "layout": rack.layout(i) if i < n_rows else [1] * rack.units})
    scene = {
        "units": "mm", "up": "z",
        "rack": {"width": W, "depth": D, "height": rack.height, "base_height": bh, "rows": rows_out,
                 "drawer_travel": d["travel"], "plenum": plenum, "pitch": rack.pitch, "profile": P,
                 "bay_depth": BD, "inner_x0": x_in},
        **items, "bays": bays,
    }
    out = SITE_ASSETS / "rack.json"
    out.write_text(json.dumps(scene, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("wrote", out, f"({out.stat().st_size / 1024:.0f} kB)", "and parts.glb",
          f"({(SITE_ASSETS / 'parts.glb').stat().st_size / 1e6:.1f} MB)")
    return out
