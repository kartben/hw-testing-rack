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
from PIL import Image, ImageDraw

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
    img[:] = MASK
    img[cu] = MASK_CU
    img[opening & cu] = FINISHES.get(art.get("finish"), FINISH)
    img[opening & ~cu] = LAMINATE
    img[silk & ~opening] = SILK
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
        mat = pbr(baseColorTexture=paint(art, side), metallicFactor=0.0, roughnessFactor=0.55, name=f"{name}-{side}")
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
    art = json.loads(art_path.read_text()) if art_path and art_path.exists() else None
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


def convert_bodies(src: Path, board: str) -> dict:
    """A board's GLB converted from its STEP rather than KiCad's own GLB export: every body, the PCB one of them,
    no copper or silkscreen meshes (the standing DATA ×4 v2's, from its session).  To the viewer's axes, then
    board_models' treatment: one material per colour, nothing decimated (decimation tears CAD meshes).  Written
    plain to render/assets/pcb (the renders read it) and meshopt-compressed to site/assets/pcb (the viewer)."""
    import board_models
    scene = trimesh.load(src, force="scene")
    meshes = []
    for node in scene.graph.nodes_geometry:
        tf, gname = scene.graph[node]
        g = scene.geometry[gname]
        if isinstance(g, trimesh.Trimesh) and len(g.faces):
            m = g.copy()
            m.apply_transform(AXES @ tf)
            meshes += board_models._by_material(m)
    out, n = board_models.by_material(meshes, board)
    plain = REPO / "render" / "assets" / "pcb" / f"{board}.glb"
    plain.parent.mkdir(parents=True, exist_ok=True)
    out.export(plain)
    dst = REPO / "site" / "assets" / "pcb" / f"{board}.glb"
    packed = board_models.write_web(out, dst)
    return {"faces": int(sum(len(g.faces) for g in out.geometry.values())), "materials": n, "packed": packed,
            "bytes": dst.stat().st_size}


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


def main(boards=("bay-node", "power-hub", "data-port-x4-v2")):
    """  pcb_glb.py [--strict] [board ...]     KiCad fab GLBs → site/assets/pcb (+ stand-ins, 3D coverage); a
                                                FROM_STEP board's (its STEP's GLB) → convert_bodies
         pcb_glb.py --standins [board ...]      redo only the stand-ins of the viewer GLBs
         pcb_glb.py --check [board ...]         the 3D coverage report alone; exit 1 if a part has no body"""
    boards = list(boards)
    strict = "--strict" in boards
    boards = [b for b in boards if b != "--strict"] or ["bay-node", "power-hub", "data-port-x4-v2"]
    if boards[0] == "--check":
        bad = 0
        for b in boards[1:] or ("bay-node", "power-hub"):
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
        if b in FROM_STEP:
            print(b, convert_bodies(src, b))
            continue
        art = REPO / "electronics" / b / "build" / f"{b}-art.json"
        if not art.exists():
            print("warning:", art, "missing (tools/kicad.sh", b, "--fab writes it): untextured board")
        info = convert(src, REPO / "site" / "assets" / "pcb" / f"{b}.glb", art, strict=strict)
        print(b, info)


if __name__ == "__main__":
    main(sys.argv[1:])
