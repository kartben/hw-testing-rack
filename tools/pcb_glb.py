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
    img[opening & cu] = FINISH
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


def convert(src: Path, dst: Path, art_path: Path | None = None, max_group_faces: int = 30000) -> dict:
    scene = trimesh.load(src)
    board = src.stem
    art = json.loads(art_path.read_text()) if art_path and art_path.exists() else None
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
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.export(dst)
    return {"textured": art is not None, "component_faces": faces, "dropped_layer_faces": dropped,
            "bytes": dst.stat().st_size}


def main(boards=("bay-node", "power-hub")):
    for b in boards:
        src = REPO / "electronics" / b / "fab" / f"{b}.glb"
        if not src.exists():
            print("skip", b, "(no fab GLB; run tools/kicad.sh", b, "--fab)")
            continue
        art = REPO / "electronics" / b / "build" / f"{b}-art.json"
        if not art.exists():
            print("warning:", art, "missing (tools/kicad.sh", b, "--fab writes it): untextured board")
        info = convert(src, REPO / "site" / "assets" / "pcb" / f"{b}.glb", art)
        print(b, info)


if __name__ == "__main__":
    main(sys.argv[1:] or ("bay-node", "power-hub"))
