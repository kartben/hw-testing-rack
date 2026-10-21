"""Turn KiCad's GLB export into a light, good-looking model for the viewer and the renders.

KiCad writes metres, Y-up, one node per 3D-model body (thousands of nodes for a
populated board).  The viewer wants millimetres, Z-up, KiCad's origin at the
board's top-left corner with rack-style axes (x right, y = -KiCad y), and a
handful of meshes.

Copper, mask and silkscreen are *not* taken from KiCad's mesh layers: they are
huge, nearly coplanar (z-fighting) and turn into shards when decimated.
Instead the board body gets a texture on each face, painted from the layer
polygons that `electronics/tools/build_board.py` writes next to the fab outputs
(`build/<board>-art.json`): green mask, lighter mask over copper, ENIG pads,
white silkscreen, drill holes.  Component models are kept, merged by colour.
"""

from __future__ import annotations

import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[1]
# KiCad GLB (x, y-up, z = KiCad y) [m] → viewer (x, -KiCad y, up) [mm]
AXES = np.array([[1000, 0, 0, 0], [0, 0, -1000, 0], [0, 1000, 0, 0], [0, 0, 0, 1]], dtype=float)

PX_PER_MM = 16          # texture resolution
SUPERSAMPLE = 2         # painted at 2× then downsampled (anti-aliasing)
# sRGB
MASK = (30, 94, 54)             # green solder mask over bare laminate
MASK_CU = (56, 130, 74)         # mask over copper
FINISH = (212, 170, 86)         # ENIG pads (mask openings over copper)
FINISHES = {"ENIG": FINISH, "HASL": (198, 198, 192)}   # the board's copper_finish (design.py "finish")
LAMINATE = (176, 160, 112)      # mask opening without copper
SILK = (238, 238, 232)
# the rack's own boards' solder mask (config/rack.yaml › pcb.solder_mask): its colour, over copper, its roughness.
# JLC's black is a satin, nearly opaque black: the copper under it barely lighter, the traces showing mostly by
# their relief catching the light (relief())
SOLDER_MASKS = {"green": {"mask": MASK, "mask_cu": MASK_CU, "rough": 0.55},
                "black": {"mask": (17, 18, 20), "mask_cu": (25, 26, 29), "rough": 0.55},
                "white": {"mask": (232, 233, 229), "mask_cu": (222, 223, 218), "rough": 0.45, "silk": (24, 24, 26)}}
HOLE = (22, 22, 22)
EDGE = (150, 140, 102)          # board edge / hole walls


def _color(geom) -> tuple:
    v = geom.visual
    try:
        mat = v.material
        c = getattr(mat, "baseColorFactor", None)
        if c is None and hasattr(mat, "main_color"):
            c = mat.main_color
        if c is not None:
            c = np.asarray(c, dtype=float).ravel()
            if c.max() > 1.0:
                c = c / 255.0
            return tuple(np.round(c[:4] if len(c) >= 4 else list(c[:3]) + [1.0], 2))
    except Exception:
        pass
    try:
        vc = np.asarray(v.vertex_colors[:, :4], dtype=float) / 255.0
        return tuple(np.round(vc.mean(axis=0), 2))
    except Exception:
        return (0.5, 0.5, 0.5, 1.0)


def paint(art: dict, side: str) -> Image.Image:
    """Texture of one face of the board, in KiCad's top view (x right, y down)."""
    (ox, oy), (w, h) = art["origin"], art["size"]
    k = PX_PER_MM * SUPERSAMPLE
    size = (int(round(w * k)), int(round(h * k)))

    def layer(name):
        im = Image.new("L", size, 0)
        d = ImageDraw.Draw(im)
        for poly in art["layers"].get(name, []):
            if len(poly) >= 3:
                d.polygon([((x - ox) * k, (y - oy) * k) for x, y in poly], fill=255)
        return np.asarray(im) > 127

    p = "F" if side == "top" else "B"
    cu, opening, silk = layer(f"{p}.Cu"), layer(f"{p}.Mask"), layer(f"{p}.SilkS")
    img = np.empty((size[1], size[0], 3), np.uint8)
    img[:] = art.get("mask", MASK)              # a maker's board in its own colours (tools/vendor_pcb.py)
    img[cu] = art.get("mask_cu", MASK_CU)
    img[opening & cu] = FINISHES.get(art.get("finish"), FINISH)
    img[opening & ~cu] = LAMINATE
    img[silk & ~opening] = art.get("silk", SILK)
    out = Image.fromarray(img)
    d = ImageDraw.Draw(out)
    for x, y, dia in art["holes"]:
        r = dia / 2 * k
        cx, cy = (x - ox) * k, (y - oy) * k
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=HOLE)
    out = out.resize((size[0] // SUPERSAMPLE, size[1] // SUPERSAMPLE), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=88, optimize=True)
    return Image.open(io.BytesIO(buf.getvalue()))      # keeps format == "JPEG" for the GLB


def solder_mask(art: dict) -> dict:
    """art with the rack's own boards' solder mask (config/rack.yaml › pcb.solder_mask) where it names none."""
    import yaml
    raw = yaml.safe_load((REPO / "config" / "rack.yaml").read_text(encoding="utf-8"))
    sm = SOLDER_MASKS[raw.get("pcb", {}).get("solder_mask", "green")]
    return {"mask": sm["mask"], "mask_cu": sm["mask_cu"], "rough": sm["rough"], "silk": sm.get("silk", SILK), **art}


def relief(art: dict, side: str) -> Image.Image:
    """A normal map of one face (tangent space, as its texture): the mask lies over the copper (35 µm) and the
    silkscreen over the mask (≈ 15 µm), so the traces show by their edges catching the light, which on a dark
    mask is how one sees them."""
    (ox, oy), (w, h) = art["origin"], art["size"]
    k = PX_PER_MM / 2                             # half the colour's resolution: a subtle relief, a smaller file
    size = (int(round(w * k)), int(round(h * k)))

    def layer(name):
        im = Image.new("L", size, 0)
        d = ImageDraw.Draw(im)
        for poly in art["layers"].get(name, []):
            if len(poly) >= 3:
                d.polygon([((x - ox) * k, (y - oy) * k) for x, y in poly], fill=255)
        return im

    p = "F" if side == "top" else "B"
    hgt = (np.asarray(layer(f"{p}.Cu").filter(ImageFilter.GaussianBlur(0.8)), float) * 1.0
           + np.asarray(layer(f"{p}.SilkS").filter(ImageFilter.GaussianBlur(0.4)), float) * 0.4) / 255.0
    gy, gx = np.gradient(hgt)
    # 35 µm of copper under a mask that rounds its edges over ≈ 0.15 mm: a flank of ≈ 8–10° at its steepest
    s = 0.25
    n = np.dstack([-gx * s, gy * s, np.ones_like(hgt)])      # image y runs down the texture: v up
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    out = Image.fromarray(np.round((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=90, optimize=True)
    return Image.open(io.BytesIO(buf.getvalue()))


def board_body(parts: list, art: dict | None, name: str) -> list:
    body = trimesh.util.concatenate(parts)
    nz = body.face_normals[:, 2]
    top, bottom = np.where(nz > 0.5)[0], np.where(nz < -0.5)[0]
    edge = np.where(np.abs(nz) <= 0.5)[0]
    out = []
    pbr = trimesh.visual.material.PBRMaterial
    if art is None:
        body.visual = trimesh.visual.TextureVisuals(material=pbr(baseColorFactor=[c / 255 for c in MASK] + [1.0],
                                                                  metallicFactor=0.0, roughnessFactor=0.5))
        return [body]
    (ox, oy), (w, h) = art["origin"], art["size"]
    for faces, side in ((top, "top"), (bottom, "bottom")):
        if not len(faces):
            continue
        m = body.submesh([faces], append=True)
        kx, ky = m.vertices[:, 0], -m.vertices[:, 1]
        uv = np.column_stack([(kx - ox) / w, 1.0 - (ky - oy) / h])
        mat = pbr(baseColorTexture=paint(art, side), normalTexture=relief(art, side), metallicFactor=0.0,
                  roughnessFactor=art.get("rough", 0.55), name=f"{name}-{side}")
        m.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
        out.append(m)
    if len(edge):
        m = body.submesh([edge], append=True)
        m.visual = trimesh.visual.TextureVisuals(material=pbr(baseColorFactor=[c / 255 for c in EDGE] + [1.0],
                                                               metallicFactor=0.0, roughnessFactor=0.7))
        out.append(m)
    return out


# ------------------------------------------------------------------ stand-ins
# Parts the KiCad library has no 3D model for (the module, the USB-C receptacle, side-entry JST PH,
# the buttons, the slide switch, the 2020 LED, side-view LEDs) get simple bodies, placed from the
# .kicad_pcb.  Each builder works in the footprint's own frame turned right-handed (x right,
# y = -KiCad y, z up from the board top) and returns (mesh, sRGB colour, metallic) triples.
# Dimensions from the datasheets (as tools/notice/node.py).
SILVER, BEIGE, BLACK, WHITE = (200, 204, 209), (236, 226, 200), (24, 24, 26), (240, 240, 236)
MODULE_PCB = (26, 36, 58)


def _box(x0, x1, y0, y1, z0, z1):
    return trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0],
                                transform=trimesh.transformations.translation_matrix([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]))


def _stadium_y(w, h, y0, y1, z0):
    """Rounded USB-C outline (w × h in the xz plane), from y0 to y1, its bottom at z0."""
    from shapely.geometry import LineString
    r = h / 2
    outline = LineString([(-(w / 2 - r), 0), (w / 2 - r, 0)]).buffer(r, quad_segs=6)
    m = trimesh.creation.extrude_polygon(outline, y1 - y0)                  # along +z
    m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))   # extrusion along +y
    m.apply_translation([0, y0 - m.bounds[0][1], z0 + r])
    return m


def _usb_c(n):
    w, h, d = 8.94, 3.16, 7.3                       # HRO TYPE-C-31-M-12 / GCT USB4105, opening at KiCad +y (local -y)
    return [(_stadium_y(w, h, -d / 2, d / 2, 0), SILVER, 0.9),
            (_stadium_y(w - 0.9, h - 0.9, -d / 2 - 0.05, -d / 2 + 0.2, 0.45), BLACK, 0.0)]


def _ph_side(n):
    wid, d, h = 2.0 * (n - 1) + 4.0, 7.6, 4.75      # S#B-PH-SM4-TB, opening at KiCad +y (local -y)
    return [(_box(-wid / 2, wid / 2, -5.0, d - 5.0, 0, h), BEIGE, 0.0),
            (_box(-wid / 2 + 0.8, wid / 2 - 0.8, -5.05, -4.8, 1.0, h - 0.9), BLACK, 0.0)]


def _esp32_mini(n):
    # 15.4 × 20.5 module, antenna end towards KiCad -y (the board's rear edge), shield can
    return [(_box(-7.7, 7.7, -10.25, 10.25, 0, 0.8), MODULE_PCB, 0.0),
            (_box(-6.4, 6.4, -9.65, 3.65, 0.8, 2.45), SILVER, 0.9)]


def _button(n):                                       # TS-1187A, 5.1 × 5.1 × 1.5 + round button
    cap = trimesh.creation.cylinder(radius=1.5, height=0.5, sections=20)
    cap.apply_translation([0, 0, 1.75])
    return [(_box(-2.55, 2.55, -2.55, 2.55, 0, 1.5), SILVER, 0.8), (cap, BLACK, 0.0)]


def _slide(n):                                        # MSK12C02, lever towards KiCad +y
    return [(_box(-3.35, 3.35, -1.3, 1.3, 0, 1.4), SILVER, 0.8), (_box(-0.5, 0.5, -2.8, -1.3, 0.3, 1.2), BLACK, 0.0)]


def _ws2812_2020(n):
    return [(_box(-1, 1, -1, 1, 0, 0.84), WHITE, 0.0), (_box(-0.6, 0.6, -0.6, 0.6, 0.84, 0.86), (250, 236, 180), 0.0)]


def _side_led(n):                                     # Kingbright KPA-3010 (3 × 1 × 2), lens towards KiCad +y
    return [(_box(-1.5, 1.5, -0.5, 0.5, 0, 2.0), WHITE, 0.0), (_box(-1.0, 1.0, -0.55, -0.45, 0.4, 1.6), (230, 232, 225), 0.0)]


STANDINS = [   # footprint name prefix → builder(pin count)
    ("RF_Module:ESP32-S2-MINI-1", _esp32_mini), ("RF_Module:ESP32-S3-MINI-1", _esp32_mini),
    ("Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", _usb_c),
    ("Connector_USB:USB_C_Receptacle_GCT_USB4105", _usb_c),     # same 8.94 × 3.16 shell
    ("Connector_JST:JST_PH_S", _ph_side),
    ("Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", _button),
    ("Button_Switch_SMD:SW_SPDT_Shouhan_MSK12C02", _slide),
    ("LED_SMD:LED_WS2812B-2020", _ws2812_2020),
    ("LED_SMD:LED_Kingbright_KPA-3010", _side_led),
]


def coverage(board: str) -> list[dict] | None:
    """electronics/<board>/build/<board>-3d.json (written by `tools/kicad.sh <board> --fab`): per
    footprint, "model" / "no-body" / "missing" in KiCad's 3D export."""
    path = REPO / "electronics" / board / "build" / f"{board}-3d.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _ref(fp, sexp) -> str:
    for p in sexp.find_all(fp, "property"):
        if str(p[1]) == "Reference":
            return str(p[2])
    return ""


def standins(pcb: Path, top: float = 1.6, only: set | None = None) -> list:
    """(mesh, colour, metallic) for the top-side footprints in STANDINS, in viewer coordinates:
    the ones in `only` (references whose KiCad model is missing), or every match without it."""
    import re
    sys.path.insert(0, str(REPO / "electronics" / "tools"))
    import sexp
    tree = sexp.loads(pcb.read_text(encoding="utf-8"))
    out = []
    for fp in sexp.find_all(tree, "footprint"):
        name = str(fp[1])
        build = next((b for prefix, b in STANDINS if name.startswith(prefix)), None)
        layer = sexp.find(fp, "layer")
        if build is None or layer is None or layer[1] != "F.Cu":
            continue
        if only is not None and _ref(fp, sexp) not in only:
            continue
        at = sexp.find(fp, "at")
        x, y, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        pins = re.search(r"_1x(\d+)", name)
        T = trimesh.transformations.translation_matrix([x, -y, top]) @ \
            trimesh.transformations.rotation_matrix(np.radians(rot), [0, 0, 1])
        for m, col, metal in build(int(pins.group(1)) if pins else 0):
            out.append((m.copy().apply_transform(T), col, metal))
    return out


def check_coverage(board: str, strict: bool = False) -> set | None:
    """The references KiCad's export left without a body and STANDINS covers; prints, loudly, any
    it doesn't cover (and raises with `strict`).  None when the board has no coverage report yet."""
    cov = coverage(board)
    if cov is None:
        print(f"warning: no 3D coverage report for {board} (tools/kicad.sh {board} --fab writes it): "
              "stand-ins by footprint name only, unchecked")
        return None
    miss = [e for e in cov if e["status"] == "missing"]
    covered = {e["ref"] for e in miss if e["side"] == "top" and any(e["footprint"].startswith(p) for p, _ in STANDINS)}
    bare = [e for e in miss if e["ref"] not in covered]
    print(f"{board} 3D: {sum(e['status'] == 'model' for e in cov)} KiCad models, {len(covered)} stand-ins, "
          f"{sum(e['status'] == 'no-body' for e in cov)} without a body by nature, {len(bare)} MISSING")
    if bare:
        lines = "\n".join(f"    {e['ref']:6s} {e['footprint']}  ({e['model'] or 'no model'})" for e in bare)
        msg = (f"\n!!! {board}: {len(bare)} placed part(s) have no 3D body in the viewer:\n{lines}\n"
               "!!! add a stand-in to STANDINS in tools/pcb_glb.py (or a model to the footprint)\n")
        if strict:
            raise SystemExit(msg)
        print(msg)
    return covered


def add_standins(scene: trimesh.Scene, pcb: Path, top: float = 1.6, only: set | None = None) -> int:
    """Add the stand-ins to a viewer scene, one mesh per colour (nodes "standin*")."""
    groups = defaultdict(list)
    for m, col, metal in standins(pcb, top, only):
        groups[(col, metal)].append(m)
    for i, ((col, metal), ms) in enumerate(sorted(groups.items())):
        m = trimesh.util.concatenate(ms)
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=[c / 255 for c in col] + [1.0], metallicFactor=metal, roughnessFactor=0.35 if metal else 0.55))
        scene.add_geometry(m, node_name=f"standin{i}", geom_name=f"standin{i}")
    return sum(len(ms) for ms in groups.values())


def convert(src: Path, dst: Path, art_path: Path | None = None, max_group_faces: int = 30000,
            strict: bool = False) -> dict:
    scene = trimesh.load(src)
    board = src.stem
    art = solder_mask(json.loads(art_path.read_text())) if art_path and art_path.exists() else None
    pcb = REPO / "electronics" / board / f"{board}.kicad_pcb"
    if art is not None and pcb.exists():
        m = re.search(r'\(copper_finish "([^"]+)"\)', pcb.read_text(encoding="utf-8"))
        art["finish"] = m.group(1) if m else None
    body, groups, dropped = [], defaultdict(list), 0
    for node in scene.graph.nodes_geometry:
        tf, gname = scene.graph[node]
        g = scene.geometry[gname]
        if not isinstance(g, trimesh.Trimesh) or len(g.faces) == 0:
            continue
        if gname.startswith(f"{board}_"):
            if gname.startswith(f"{board}_PCB"):
                m = g.copy()
                m.apply_transform(AXES @ tf)
                body.append(m)
            else:
                dropped += len(g.faces)          # copper / pads / vias / mask / silk meshes → texture
            continue
        m = g.copy()
        m.apply_transform(AXES @ tf)
        groups[_color(g)].append(m)
    out = trimesh.Scene()
    for i, m in enumerate(board_body(body, art, board)):
        out.add_geometry(m, node_name=f"board{i}", geom_name=f"board{i}")
    faces = 0
    for i, (col, ms) in enumerate(sorted(groups.items(), key=lambda kv: -sum(len(x.faces) for x in kv[1]))):
        m = trimesh.util.concatenate(ms)
        if len(m.faces) > max_group_faces:
            m = m.simplify_quadric_decimation(face_count=max_group_faces)
        rgba = [float(c) for c in col]
        metallic = 0.9 if (rgba[0] > 0.6 and abs(rgba[0] - rgba[1]) < 0.08 and abs(rgba[1] - rgba[2]) < 0.08) else 0.05
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=rgba, metallicFactor=metallic, roughnessFactor=0.45))
        out.add_geometry(m, node_name=f"part{i}", geom_name=f"part{i}")
        faces += len(m.faces)
    pcb = src.parents[1] / f"{board}.kicad_pcb"
    only = check_coverage(board, strict)
    n_standins = add_standins(out, pcb, top=max(b.bounds[1][2] for b in body), only=only) if pcb.exists() and body else 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.export(dst)
    return {"textured": art is not None, "component_faces": faces, "dropped_layer_faces": dropped,
            "standins": n_standins, "bytes": dst.stat().st_size}


def footprint_boxes(pcb: Path) -> list[tuple[str, bool, float, float, float, float]]:
    """Every footprint's pads' extent on the board: (reference, on the front (F.Cu), x0, y0, x1, y1), KiCad mm."""
    sys.path.insert(0, str(REPO / "electronics" / "tools"))
    import sexp
    out = []
    for fp in sexp.find_all(sexp.loads(pcb.read_text(encoding="utf-8")), "footprint"):
        at, layer = sexp.find(fp, "at"), sexp.find(fp, "layer")
        x, y, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0
        c, s_ = np.cos(np.radians(rot)), np.sin(np.radians(rot))
        pts = []
        for pad in sexp.find_all(fp, "pad"):
            pa, size = sexp.find(pad, "at"), sexp.find(pad, "size")
            px, py, w, h = float(pa[1]), float(pa[2]), float(size[1]), float(size[2])
            r = max(w, h) / 2                       # each pad as a square round its centre: rotation-proof
            # KiCad turns a footprint counter-clockwise on screen, y down: (px, py) → (px c + py s, −px s + py c)
            qx, qy = x + px * c + py * s_, y - px * s_ + py * c
            pts += [(qx - r, qy - r), (qx + r, qy + r)]
        if pts:
            a = np.array(pts)
            out.append((_ref(fp, sexp), str(layer[1]) == "F.Cu", *a.min(axis=0), *a.max(axis=0)))
    return out


def convert_bodies(src: Path, board: str, hide: set | None = None, name: str | None = None) -> dict:
    """A board's GLB converted from its STEP rather than KiCad's own GLB export: every body, the PCB one of them,
    no copper or silkscreen meshes (the standing DATA ×4 v2's, from its session).  To the viewer's axes, then
    board_models' treatment: one material per colour, nothing decimated (decimation tears CAD meshes).  Written
    plain to render/assets/pcb (the renders read it) and meshopt-compressed to site/assets/pcb (the viewer), as
    `name` (default the board's).  hide: the references an assembly variant leaves off: a body goes with the
    smallest footprint whose pads (0.6 mm round) hold its middle, on its side of the board; the board's own
    faces (anything over 30 mm) stay.  With the board's layer art (build/<board>-art.json, as KiCad's GLBs
    get it) the PCB's two faces are painted from its copper, mask, silkscreen and holes (board_body): an
    assembly variant's empty footprints show."""
    import board_models
    scene = trimesh.load(src, force="scene")
    pcb = REPO / "electronics" / board / f"{board}.kicad_pcb"
    boxes = footprint_boxes(pcb) if hide else []
    art_path = REPO / "electronics" / board / "build" / f"{board}-art.json"
    art = solder_mask(json.loads(art_path.read_text())) if art_path.exists() else None
    if art is not None:
        m_ = re.search(r'\(copper_finish "([^"]+)"\)', pcb.read_text(encoding="utf-8"))
        art["finish"] = m_.group(1) if m_ else None
    meshes, hidden, faces = [], set(), []
    for node in scene.graph.nodes_geometry:
        tf, gname = scene.graph[node]
        g = scene.geometry[gname]
        if isinstance(g, trimesh.Trimesh) and len(g.faces):
            m = g.copy()
            m.apply_transform(AXES @ tf)
            if art is not None and m.extents[2] < 2.5 and m.extents[0] > 0.9 * art["size"][0] \
                    and m.extents[1] > 0.9 * art["size"][1]:
                faces.append(m)             # one of the PCB's faces: painted instead
                continue
            if boxes and max(m.extents) < 30.0:
                cx, cy, cz = (m.bounds[0] + m.bounds[1]) / 2            # viewer axes: y = -KiCad y, z off the face
                hold = [b for b in boxes if b[1] == (cz > 0.8) and b[2] - 0.6 <= cx <= b[4] + 0.6
                        and b[3] - 0.6 <= -cy <= b[5] + 0.6]
                ref = min(hold, key=lambda b: (b[4] - b[2]) * (b[5] - b[3]))[0] if hold else None
                if ref in hide:
                    hidden.add(ref)
                    continue
            meshes += board_models._by_material(m)
    name = name or board
    out, n = board_models.by_material(meshes, name)
    for i, m in enumerate(board_body(faces, art, name) if faces else []):
        out.add_geometry(m, node_name=f"board{i}", geom_name=f"board{i}")
    plain = REPO / "render" / "assets" / "pcb" / f"{name}.glb"
    plain.parent.mkdir(parents=True, exist_ok=True)
    out.export(plain)
    dst = REPO / "site" / "assets" / "pcb" / f"{name}.glb"
    packed = board_models.write_web(out, dst)
    info = {"faces": int(sum(len(g.faces) for g in out.geometry.values())), "materials": n, "packed": packed,
            "bytes": dst.stat().st_size, "painted": bool(faces)}
    if hide:
        info.update(hidden=len(hidden), unseen=sorted(hide - hidden))       # left-off parts with no body found
    return info


def variant_dnp(board: str, variant: str) -> set:
    """The references an assembly variant leaves off: in the board's fab CPL, not in the variant's."""
    import csv
    fab = REPO / "electronics" / board / "fab"
    refs = [{r["Designator"] for r in csv.DictReader(open(f, encoding="utf-8"))}
            for f in (fab / f"{board}-cpl-jlcpcb.csv", fab / f"{board}-{variant}-cpl-jlcpcb.csv")]
    return refs[0] - refs[1]


def restand(board: str) -> int:
    """Redo the stand-ins of an existing viewer GLB (site/assets/pcb/<board>.glb) from the current
    .kicad_pcb, without KiCad: drops its "standin*" nodes and adds them again."""
    path = REPO / "site" / "assets" / "pcb" / f"{board}.glb"
    scene = trimesh.load(path)
    for node in [n for n in scene.graph.nodes_geometry if n.startswith("standin")]:
        scene.delete_geometry(scene.graph[node][1])
    boards = [scene.geometry[scene.graph[n][1]] for n in scene.graph.nodes_geometry if n.startswith("board")]
    n = add_standins(scene, REPO / "electronics" / board / f"{board}.kicad_pcb",
                     top=max(b.bounds[1][2] for b in boards) if boards else 1.6, only=check_coverage(board))
    scene.export(path)
    return n


FROM_STEP = ("data-port-x4-v2",)     # boards whose fab GLB is their STEP's (every body: convert_bodies)
VARIANTS = {"data-port-x4-v2": ("base",)}   # and their assembly variants, each its own model: <board>-<variant>.glb


VIEWER_BOARDS = ("bay-node", "power-hub", "data-port", "camera-pod", "data-port-x4-v2")   # the boards the viewer draws


def main(boards=VIEWER_BOARDS):
    """  pcb_glb.py [--strict] [board ...]     KiCad fab GLBs → site/assets/pcb (+ stand-ins, 3D coverage); a
                                                FROM_STEP board's (its STEP's GLB) → convert_bodies
         pcb_glb.py --standins [board ...]      redo only the stand-ins of the viewer GLBs
         pcb_glb.py --check [board ...]         the 3D coverage report alone; exit 1 if a part has no body"""
    boards = list(boards)
    strict = "--strict" in boards
    boards = [b for b in boards if b != "--strict"] or list(VIEWER_BOARDS)
    if boards[0] == "--check":
        bad = 0
        for b in boards[1:] or ("bay-node", "power-hub", "data-port", "camera-pod"):
            try:
                check_coverage(b, strict=True)
            except SystemExit as e:
                print(e)
                bad += 1
        raise SystemExit(1 if bad else 0)
    if boards[0] == "--standins":          # only refresh the stand-ins of the viewer GLBs
        for b in boards[1:] or ("bay-node",):
            print(b, "stand-ins:", restand(b))
        return
    for b in boards:
        src = REPO / "electronics" / b / "fab" / f"{b}.glb"
        if not src.exists():
            print("skip", b, "(no fab GLB; run tools/kicad.sh", b, "--fab)")
            continue
        art = REPO / "electronics" / b / "build" / f"{b}-art.json"
        if not art.exists():
            print("warning:", art, "missing (tools/kicad.sh", b, "--fab writes it): untextured board")
        if b in FROM_STEP:
            print(b, convert_bodies(src, b))
            for v in VARIANTS.get(b, ()):
                print(f"{b}-{v}", convert_bodies(src, b, hide=variant_dnp(b, v), name=f"{b}-{v}"))
            continue
        info = convert(src, REPO / "site" / "assets" / "pcb" / f"{b}.glb", art, strict=strict)
        print(b, info)


if __name__ == "__main__":
    main(sys.argv[1:])
