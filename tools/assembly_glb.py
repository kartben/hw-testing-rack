#!/usr/bin/env python3
"""Bake the whole shelf into one GLB (render/assembly.glb) from site/assets/rack.json.

Same scene as the web viewer, flattened for offline tools: Blender renders
(render/render.py), any glTF viewer, CAD reference.  Objects are named
`<category>:<detail>` and carry one material per category so the Blender
script can restyle them.  Units: metres, Y-up (glTF convention).

    python tools/assembly_glb.py [--open 0.0] [--explode 0]
    python tools/assembly_glb.py --explode-bay C3 --out render/bay-exploded.glb   # one bay, laid flat, layers apart
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "site" / "assets"
OUT = REPO / "render" / "assembly.glb"

MATS = {
    "ladders": ([0.16, 0.18, 0.21, 1], 0.0, 0.62),
    "trays": ([0.23, 0.25, 0.29, 1], 0.0, 0.58),
    "braces": ([1.0, 0.45, 0.12, 1], 0.0, 0.42),
    "frameplates": ([0.19, 0.21, 0.25, 1], 0.0, 0.6),
    "drawers": ([0.90, 0.91, 0.92, 1], 0.0, 0.45),
    "plates": ([0.13, 0.36, 0.86, 1], 0.0, 0.42),
    "chain": ([0.05, 0.05, 0.06, 1], 0.1, 0.5),
    "chainparts": ([1.0, 0.45, 0.12, 1], 0.0, 0.45),
    "cameras": ([0.16, 0.18, 0.21, 1], 0.0, 0.55),
    "psu": ([0.72, 0.74, 0.77, 1], 0.9, 0.3),
    "powerbox": ([0.075, 0.08, 0.09, 1], 0.0, 0.55),
    "powerlabels": ([0.93, 0.92, 0.89, 1], 0.0, 0.6),
    "silver": ([0.78, 0.8, 0.82, 1], 0.95, 0.25),
    "plug": ([0.11, 0.115, 0.13, 1], 0.0, 0.45),
    "black": ([0.07, 0.07, 0.08, 1], 0.0, 0.6),
}
CABLE = {"c-to-c": [0.56, 0.36, 1.0, 1], "c-to-micro-b": [1.0, 0.69, 0.18, 1], "c-to-mini-b": [0.88, 0.54, 0.12, 1],
         "pc": [0.25, 0.71, 1.0, 1], "ext": [0.49, 0.52, 0.56, 1], "usb-pd": [0.06, 0.06, 0.07, 1]}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def mat(name_or_rgba, metallic=0.0, rough=0.55):
    """Colours are written as sRGB (like CSS); glTF baseColorFactor is linear."""
    if isinstance(name_or_rgba, str):
        rgba, metallic, rough = MATS[name_or_rgba]
    else:
        rgba = name_or_rgba
    lin = [srgb_to_linear(c) for c in rgba[:3]] + [rgba[3] if len(rgba) > 3 else 1.0]
    return PBRMaterial(baseColorFactor=lin, metallicFactor=metallic, roughnessFactor=rough)


# USB plugs (same outlines as site/app.js; plug frame: +z into the receptacle, x = width, y = up)
PLUG_SHAPE = {
    "usb-c": dict(shell="pill", sw=8.3, sh=2.5, sl=6.5, mw=12.0, mh=6.2, ml=15.0, relief=7.0),
    "micro-b": dict(shell="trap", sw=6.9, sh=1.85, sl=5.5, bw=5.4, mw=10.5, mh=5.4, ml=13.0, relief=6.0),
    "mini-b": dict(shell="trap", sw=7.7, sh=3.9, sl=6.0, bw=6.2, mw=11.0, mh=7.0, ml=14.0, relief=6.0),
    "usb-a": dict(shell="box", sw=12.0, sh=4.5, sl=12.0, mw=15.5, mh=7.5, ml=20.0, relief=8.0),
}
RIGHT_ANGLE = dict(depth=12.0, height=9.0, relief=6.0)      # as in tools/webscene.py


def plug_meshes(e: dict) -> list:
    """Meshes of one cable end (tools/webscene.py writes them into rack.json), in its space."""
    from shapely.geometry import LineString, Polygon
    d = PLUG_SHAPE.get(e["type"], PLUG_SHAPE["usb-c"])
    w, h = d["sw"] / 2, d["sh"] / 2
    if d["shell"] == "pill":
        outline = LineString([(-w + h, 0), (w - h, 0)]).buffer(h, quad_segs=8)
    elif d["shell"] == "trap":
        b = d["bw"] / 2
        outline = Polygon([(-b, -h), (b, -h), (w, h * 0.2), (w, h), (-w, h), (-w, h * 0.2)])
    else:
        outline = Polygon([(-w, -h), (w, -h), (w, h), (-w, h)])
    mold, shell = mat("plug"), mat("silver")
    out = [with_mat(trimesh.creation.extrude_polygon(outline, d["sl"]), shell)]
    if e.get("style") == "right":
        depth, height, relief = RIGHT_ANGLE["depth"], RIGHT_ANGLE["height"], RIGHT_ANGLE["relief"]
        lo = -d["mh"] / 2 - 0.4
        out.append(with_mat(trimesh.creation.box([d["mw"], height - lo, depth],
                                                 transform=translate([0, (height + lo) / 2, -depth / 2])), mold))
        out.append(with_mat(trimesh.creation.cylinder(radius=2.45, height=relief, sections=20,
                                                      transform=translate([0, height + relief / 2, -depth / 2])
                                                      @ rot_xyz([90, 0, 0])), mold))
    else:
        out.append(with_mat(trimesh.creation.box([d["mw"], d["mh"], d["ml"]],
                                                 transform=translate([0, 0, -d["ml"] / 2])), mold))
        out.append(with_mat(trimesh.creation.cylinder(radius=2.45, height=d["relief"], sections=20,
                                                      transform=translate([0, 0, -d["ml"] - d["relief"] / 2])), mold))
    if e.get("socket") == "panel":            # the drawer's panel-mount female: flange + two M3 screws
        out.append(with_mat(trimesh.creation.box([23, 8, 1.5], transform=translate([0, 0, 0.75])), mold))
        for sx in (-9, 9):
            out.append(with_mat(trimesh.creation.cylinder(radius=2.6, height=1.1, sections=16,
                                                          transform=translate([sx, 0, -0.5])), mat("silver")))
    z = np.array(e["dir"], float)
    z /= np.linalg.norm(z)
    up = np.array(e.get("up", (0, 0, 1)), float)
    x = np.cross(up, z)
    x = x / np.linalg.norm(x) if np.linalg.norm(x) > 1e-6 else np.array([1.0, 0, 0])
    y = np.cross(z, x)
    B = np.eye(4)
    B[:3, 0], B[:3, 1], B[:3, 2], B[:3, 3] = x, y, z, e["at"]
    return [m.apply_transform(B) for m in out]


def with_mat(m: trimesh.Trimesh, material) -> trimesh.Trimesh:
    m = m.copy()
    m.visual = trimesh.visual.TextureVisuals(material=material)
    return m


def hex_rgba(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]


def part_category(name):
    if name.endswith("_labels"):
        return "powerlabels"
    for prefix, cat in (("ladder_", "ladders"), ("brace_", "braces"), ("tray", "trays"), ("floor_plate", "frameplates"),
                        ("cap_plate", "frameplates"), ("drawer", "drawers"), ("chain_", "chainparts"),
                        ("plate_", "plates"), ("camera_", "cameras"), ("power_box_", "powerbox")):
        if name.startswith(prefix):
            return cat
    return "trays"


def rot_xyz(deg):
    rx, ry, rz = (math.radians(d) for d in deg)
    return (trimesh.transformations.rotation_matrix(rz, [0, 0, 1])
            @ trimesh.transformations.rotation_matrix(ry, [0, 1, 0])
            @ trimesh.transformations.rotation_matrix(rx, [1, 0, 0]))


def translate(v):
    return trimesh.transformations.translation_matrix(v)


def tube(points, radius, sides=10):
    """Simple swept circle along a polyline (Catmull-Rom smoothed)."""
    p = np.asarray(points, float)
    if len(p) > 2:  # smooth
        q = [p[0]]
        for i in range(len(p) - 1):
            p0, p1, p2, p3 = p[max(i - 1, 0)], p[i], p[i + 1], p[min(i + 2, len(p) - 1)]
            for t in np.linspace(0, 1, 5)[1:]:
                q.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                                + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
        p = np.asarray(q)
    n = len(p)
    tang = np.gradient(p, axis=0)
    tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-12
    ref = np.array([0, 0, 1.0])
    verts, faces = [], []
    normal = np.cross(tang[0], ref)
    if np.linalg.norm(normal) < 1e-6:
        normal = np.cross(tang[0], [1, 0, 0])
    normal /= np.linalg.norm(normal)
    for i in range(n):
        # parallel transport
        normal = normal - np.dot(normal, tang[i]) * tang[i]
        normal /= np.linalg.norm(normal) + 1e-12
        binorm = np.cross(tang[i], normal)
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append(p[i] + radius * (math.cos(a) * normal + math.sin(a) * binorm))
    for i in range(n - 1):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            c, d = a + sides, b + sides
            faces += [[a, b, d], [a, d, c]]
    return trimesh.Trimesh(np.asarray(verts), np.asarray(faces), process=False)


def chain_path(ch, frac):
    t = ch["travel"] * frac
    fx, fy = ch["fixed"]
    mx, my = ch["moving_x"], ch["foot_y"] - t
    b, r = ch["bend_y"] - t / 2, ch["radius"]
    cx = (fx + mx) / 2
    pts = [(fx, y) for y in np.arange(fy, b, 3)]
    pts += [(cx + r * math.cos(a), b + r * math.sin(a)) for a in np.linspace(math.pi, 0, 25)]
    pts += [(mx, y) for y in np.arange(b - 3, my, -3)] + [(mx, my)]
    o = ch["origin"]
    return np.array([(o[0] + x, o[1] + y, o[2] + ch["z"]) for x, y in pts])


BOARD_MODELS = REPO / "render" / "assets" / "boards"      # tools/board_models.py output (not committed)
_LIB = None


def real_board(b):
    """The vendor's 3D model of this board, if tools/board_models.py normalised one, turned like
    rackcfg.orient_board() turns the board (debug USB towards the drawer rear)."""
    global _LIB
    f = BOARD_MODELS / f"{b['id']}.norm.glb"
    if not f.exists():
        return None
    if _LIB is None:
        import yaml
        _LIB = yaml.safe_load((REPO / "mechanical" / "boards" / "boards.yaml").read_text(encoding="utf-8"))["boards"]
    spec = _LIB[b["id"]]
    w, l = spec["size"]
    edge = spec.get("usb", {}).get("edge", "top")
    M = np.eye(4)
    if edge == "bottom":
        M = translate([w, l, 0]) @ rot_xyz([0, 0, 180])
    elif edge == "left":
        M = translate([0, w, 0]) @ rot_xyz([0, 0, -90])
    elif edge == "right":
        M = translate([l, 0, 0]) @ rot_xyz([0, 0, 90])
    if spec.get("orient") == "side":                  # rear edge → right edge (rackcfg.orient_board)
        top_w = w if edge in ("top", "bottom") else l
        M = translate([0, top_w, 0]) @ rot_xyz([0, 0, -90]) @ M
    s = trimesh.load(f, force="scene")
    out = []
    for node in s.graph.nodes_geometry:
        tf, g = s.graph[node]
        out.append(s.geometry[g].copy().apply_transform(M @ tf))
    return out


def real_xiao(size):
    """The XIAO ESP32S3 Sense model for a camera pod: camera side down, seated at the top of the
    pod's box (size = the box the viewer draws)."""
    f = BOARD_MODELS / "xiao.norm.glb"
    if not f.exists():
        return None
    s = trimesh.load(f, force="scene")
    ms = [s.geometry[g].copy().apply_transform(rot_xyz([180, 0, 0]) @ tf)
          for tf, g in (s.graph[n] for n in s.graph.nodes_geometry)]
    lo = np.min([m.bounds[0] for m in ms], axis=0)
    hi = np.max([m.bounds[1] for m in ms], axis=0)
    shift = translate([size[0] / 2 - (lo[0] + hi[0]) / 2, size[1] / 2 - (lo[1] + hi[1]) / 2, size[2] - hi[2]])
    return [m.apply_transform(shift) for m in ms]


def board_meshes(b):
    w, l = b["size"][:2]
    out = [with_mat(trimesh.creation.box([w, l, 1.6], transform=translate([w / 2, l / 2, 0.8])),
                    mat(hex_rgba(b["color"]), 0.05, 0.5))]
    rng = np.random.default_rng(abs(hash(b["id"] + b["bay"])) % 2 ** 32)
    for i in range(max(3, int(w * l / 1400))):
        cw, cl = 4 + rng.random() * min(14, w * .3), 4 + rng.random() * min(14, l * .25)
        cx, cy = 3 + rng.random() * max(1, w - cw - 6), 3 + rng.random() * max(1, l - cl - 14)
        h = 1 + rng.random() * 1.4
        out.append(with_mat(trimesh.creation.box([cw, cl, h], transform=translate([cx + cw / 2, cy + cl / 2, 1.6 + h / 2])),
                            mat("black" if i % 3 else "silver")))
    if w > 24 and l > 40:
        for x in (1.2, w - 3.7):
            out.append(with_mat(trimesh.creation.box([2.5, l * .62, 8.5], transform=translate([x + 1.25, l * .5, 1.6 + 4.25])),
                                mat("black")))
    for ux in (b.get("usb_x"), b.get("usb2_x")):
        if ux is not None and b.get("usb_side"):
            out.append(with_mat(trimesh.creation.box([7.4, 9, 3.2], transform=translate([w - 2.9, ux, 1.6 + 1.6])),
                                mat("silver")))
        elif ux is not None:
            out.append(with_mat(trimesh.creation.box([9, 7.4, 3.2], transform=translate([ux, l - 2.9, 1.6 + 1.6])),
                                mat("silver")))
    return out


# stack-up order of one bay, for --explode-bay (multiples of the layer gap, along the shelf normal)
BAY_LAYERS = [("tray", 0), ("chain", 1), ("pcb", 1), ("led", 1), ("drawer", 3), ("plate", 4), ("boards", 5),
              ("camera", 4), ("xiao", 4)]   # the pod already hangs a row pitch higher


def bay_layer(name):
    return next((k for key, k in BAY_LAYERS if key in name), None)


def build(open_frac=None, explode=0.0, out_path=OUT, with_pc=False, explode_bay=None, gap=45.0, open_bays=(),
          hq=False):
    scene_json = json.loads((ASSETS / "rack.json").read_text(encoding="utf-8"))
    parts_glb = ASSETS / "parts.glb"
    if hq:
        # full-resolution printed parts for the renders ($fn=64, not decimated like the viewer's)
        parts_glb = REPO / "render" / "parts-hq.glb"
        stls = list((REPO / "mechanical" / "stl").glob("*.stl"))
        if not parts_glb.exists() or any(s.stat().st_mtime > parts_glb.stat().st_mtime for s in stls):
            # rebuilt when any STL is newer: a stale cache silently drops parts renamed since
            import sys
            sys.path.insert(0, str(REPO / "tools"))
            import rackcfg
            import webscene
            webscene.build_parts_glb(rackcfg.load(), rackcfg.load_boards(), hq=True)
    parts = trimesh.load(parts_glb)
    geoms = {}
    for node in parts.graph.nodes_geometry:
        tf, g = parts.graph[node]
        geoms[node] = parts.geometry[g].copy().apply_transform(tf)
    pcb = {}
    for name in ("bay-node", "power-hub"):
        f = ASSETS / "pcb" / f"{name}.glb"
        if f.exists():
            s = trimesh.load(f)
            pcb[name] = [(s.geometry[g].copy().apply_transform(tf)) for tf, g in
                         (s.graph[n] for n in s.graph.nodes_geometry)]
    rows = scene_json["rack"]["rows"]
    travel = scene_json["rack"]["drawer_travel"]
    row_tf = []
    for i, r in enumerate(rows):
        T = translate(np.add(r["origin"], [0, 0, explode * i * 150])) @ rot_xyz([r["tilt"], 0, 0])
        row_tf.append(T)
    initial = {c["bay"]: c["open"] for c in scene_json["chains"]}
    flat = np.eye(4)
    if explode_bay:
        base = next(i for i in scene_json["instances"] if i.get("bay") == explode_bay and i["part"] == "tray")
        flat = np.linalg.inv(row_tf[base["row"]])

    def place(space, row, local):
        return (row_tf[row] if space == "row" and row is not None else
                translate([0, 0, explode * (row or 0) * 150]) if row is not None else np.eye(4)) @ local

    def drawer_dy(item):
        if not item.get("movable") or not item.get("bay"):
            return 0.0
        if item["bay"] in open_bays:
            return -travel * (1.0 - initial.get(item["bay"], 0))
        if open_frac is None:
            return 0.0
        return -travel * (open_frac - initial.get(item["bay"], 0))

    out = trimesh.Scene()
    k = 0

    def add(mesh, name, T, bay=None):
        nonlocal k
        if explode_bay:
            layer = bay_layer(name)
            if bay != explode_bay or layer is None:
                return
            T = translate([0, 0, layer * gap]) @ flat @ T
        k += 1
        out.add_geometry(mesh, node_name=f"{name}#{k}", geom_name=f"{name}#{k}", transform=T)

    for it in scene_json["instances"]:
        g = geoms.get(it["part"])
        if g is None:
            continue
        local = translate(np.add(it["pos"], [0, drawer_dy(it), 0])) @ rot_xyz(it["rot"])
        add(with_mat(g, mat(part_category(it["part"]))), f"{part_category(it['part'])}:{it['part']}",
            place(it.get("space"), it.get("row"), local), it.get("bay"))
    for b in scene_json["boards"]:
        for m in real_board(b) or board_meshes(b):
            add(m, f"boards:{b['id']}", place("row", b["row"], translate(np.add(b["pos"], [0, drawer_dy(b), 0]))),
                b.get("bay"))
    for p in scene_json["pcbs"]:
        for m in pcb.get(p["board"], []):
            add(m, f"pcb:{p['board']}", place(p.get("space"), p.get("row"), translate(p["pos"])), p.get("bay"))
    for bx in scene_json["boxes"]:
        real = real_xiao(bx["size"]) if bx["kind"] == "xiao" else None
        if real:
            for m in real:
                add(m, f"xiao:{bx.get('bay', '')}", place(bx.get("space"), bx.get("row"), translate(bx["pos"])),
                    bx.get("bay"))
            continue
        m = trimesh.creation.box(bx["size"], transform=translate(np.array(bx["size"]) / 2))
        add(with_mat(m, mat("psu") if bx["kind"] == "psu" else mat(hex_rgba(bx["color"]))), f"{bx['kind']}:{bx.get('bay', '')}",
            place(bx.get("space"), bx.get("row"), translate(bx["pos"])), bx.get("bay"))
    for led in scene_json.get("leds", []):
        rgb = hex_rgba(led["color"])[:3]
        em = PBRMaterial(baseColorFactor=[*(srgb_to_linear(c) for c in rgb), 1.0], emissiveFactor=rgb,
                         metallicFactor=0.0, roughnessFactor=0.3)
        m = trimesh.creation.cylinder(radius=1.5, height=1.2, sections=16,
                                      transform=translate([0, 0.6, 0]) @ rot_xyz([90, 0, 0]))
        add(with_mat(m, em), f"led:{led.get('bay', 'power')}",
            place(led.get("space", "row"), led.get("row"), translate(led["pos"])), led.get("bay"))
    link = trimesh.creation.box([8.4, 10, 11])
    for ch in scene_json["chains"]:
        frac = 1.0 if ch["bay"] in open_bays else (ch["open"] if open_frac is None else open_frac)
        pts = chain_path(ch, frac)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cum = np.concatenate([[0], np.cumsum(seg)])
        links = []
        for d in np.arange(4.5, cum[-1], 9):
            i = min(np.searchsorted(cum, d) - 1, len(seg) - 1)
            t = (d - cum[i]) / max(seg[i], 1e-9)
            pos = pts[i] + t * (pts[i + 1] - pts[i])
            R = trimesh.geometry.align_vectors([1, 0, 0], (pts[i + 1] - pts[i]) / max(seg[i], 1e-9))
            links.append(link.copy().apply_transform(translate(pos) @ R))
        add(with_mat(trimesh.util.concatenate(links), mat("chain")), f"chain:{ch['bay']}",
            place("row", ch["row"], np.eye(4)), ch["bay"])
    for c in scene_json["cables"]:
        if c["kind"] == "pc" and not with_pc:
            continue
        col = c.get("color")
        rgba = hex_rgba(col) if col else CABLE.get(c.get("type") or c["kind"], [0.5, 0.5, 0.5, 1])
        pts = np.array(c["points"], float)
        if c.get("space", "row") == "row" and c.get("movable"):
            pts = pts + [0, drawer_dy(c), 0]
        add(with_mat(tube(pts, c.get("radius", 1.5)), mat(rgba, 0, 0.5)), f"cable:{c['kind']}",
            place(c.get("space"), c.get("row"), np.eye(4)))
        dy = drawer_dy(c) if c.get("space", "row") == "row" and c.get("movable") else 0.0
        for e in c.get("ends", []):
            for m in plug_meshes(e):
                add(m, f"plug:{c['kind']}", place(c.get("space"), c.get("row"), translate([0, dy, 0])), c.get("bay"))
    # mm, Z-up → m, Y-up
    out.apply_transform(rot_xyz([-90, 0, 0]))
    out.apply_scale(0.001)
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.export(dst)
    print("wrote", dst, f"{dst.stat().st_size / 1e6:.1f} MB, {len(out.geometry)} objects")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", type=float, default=None, help="open every drawer by this fraction")
    ap.add_argument("--explode", type=float, default=0.0)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--with-pc-cable", action="store_true", help="include the demo laptop cable")
    ap.add_argument("--explode-bay", metavar="BAY", help="only this bay, laid flat, its layers pulled apart")
    ap.add_argument("--gap", type=float, default=45.0, help="layer gap for --explode-bay (mm)")
    ap.add_argument("--open-bays", metavar="B3,B4", help="also pull these drawers fully out")
    ap.add_argument("--hq", action="store_true", help="full-resolution part meshes (render/parts-hq.glb)")
    a = ap.parse_args()
    build(a.open, a.explode, a.out, a.with_pc_cable, a.explode_bay, a.gap,
          tuple(b for b in (a.open_bays or "").split(",") if b), a.hq)
