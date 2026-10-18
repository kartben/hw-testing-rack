#!/usr/bin/env python3
"""Real 3D models of the dev boards, for the renders (and the viewer when the licence allows).

Drop a vendor model in render/assets/boards/<board-id>.{step,stp,glb,gltf,wrl}
(see docs/boards-3d.md for sources), then:

    python tools/board_models.py              # normalise every model found
    python tools/board_models.py nucleo-64    # just one

Writes render/assets/boards/<board-id>.norm.glb: millimetres, Z up, PCB bottom at z = 0, origin
at the bottom-left corner of the PCB as drawn in the vendor's mechanical drawing, i.e. the frame
mechanical/boards/boards.yaml uses.  tools/assembly_glb.py then places it exactly where the
stand-in box went.  Fix-ups per board in boards.yaml:

    model: { rot: 180, flip: false, offset: [0, 0] }   # extra turn about Z, upside-down export, nudge (mm)

A board made of several models (a shield on its host) lists them under model.stack instead (see stack()), and
model.web: true also writes the viewer's lighter copy to site/assets/boards/<id>.glb, for models whose licence
lets the repository publish them (see docs/boards-3d.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
import yaml

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "render" / "assets" / "boards"
EXTS = (".step", ".stp", ".glb", ".gltf", ".wrl")


def _rot(axis, deg):
    return trimesh.transformations.rotation_matrix(np.radians(deg), axis)


def load_mm(path: Path) -> trimesh.Scene:
    """Load any supported model as a scene in millimetres (STEP goes through cascadio/OpenCascade)."""
    scene = trimesh.load(str(path), force="scene")
    ext = scene.extents
    if ext is not None and max(ext) < 1.0:            # glTF / cascadio output is in metres
        scene.apply_scale(1000.0)
    return scene


def baked(scene: trimesh.Scene) -> list[trimesh.Trimesh]:
    out = []
    for node in scene.graph.nodes_geometry:
        tf, g = scene.graph[node]
        m = scene.geometry[g]
        if isinstance(m, trimesh.Trimesh) and len(m.faces):
            m = m.copy()
            m.apply_transform(tf)
            out.append(m)
    return out


def pcb_frame(meshes: list[trimesh.Trimesh]):
    """Find the PCB: the axis carrying the most flat area is its normal; its two biggest planes
    along that axis are the top and bottom faces.  Returns (axis, z_bottom, z_top, outline min, max)."""
    normals = np.vstack([m.face_normals for m in meshes])
    areas = np.concatenate([m.area_faces for m in meshes])
    centers = np.vstack([m.triangles_center for m in meshes])
    axis = int(np.argmax([areas[np.abs(normals[:, k]) > 0.98].sum() for k in range(3)]))
    flat = np.abs(normals[:, axis]) > 0.98
    levels = np.round(centers[flat, axis], 2)
    lv, inv = np.unique(levels, return_inverse=True)
    lv_area = np.bincount(inv, weights=areas[flat])
    top2 = lv[np.argsort(lv_area)[-2:]]
    z0, z1 = float(min(top2)), float(max(top2))
    others = [k for k in range(3) if k != axis]
    pts = np.vstack([m.vertices[m.faces[np.abs(m.face_normals[:, axis]) > 0.98].ravel()] for m in meshes])
    zc = pts[:, axis]
    pts = pts[(np.abs(zc - z0) < 0.03) | (np.abs(zc - z1) < 0.03)]
    lo, hi = pts[:, others].min(axis=0), pts[:, others].max(axis=0)
    return axis, z0, z1, lo, hi


def normalise(board_id: str, spec: dict, src: Path) -> dict:
    scene = load_mm(src)
    meshes = baked(scene)
    axis, z0, z1, lo, hi = pcb_frame(meshes)
    # 1. PCB normal → +Z
    T = np.eye(4)
    if axis == 0:
        T = _rot([0, 1, 0], -90) @ T
    elif axis == 1:
        T = _rot([1, 0, 0], 90) @ T
    for m in meshes:
        m.apply_transform(T)
    axis, z0, z1, lo, hi = pcb_frame(meshes)
    # 2. component side up: more geometry above the top plane than below the bottom one
    allv = np.vstack([m.vertices for m in meshes])
    above, below = allv[:, 2].max() - z1, z0 - allv[:, 2].min()
    flip = (below > above) != bool(spec.get("model", {}).get("flip", False))
    if flip:
        F = _rot([1, 0, 0], 180)
        for m in meshes:
            m.apply_transform(F)
        axis, z0, z1, lo, hi = pcb_frame(meshes)
    # 3. PCB outline to the drawing's frame; turn 90° if the aspect says so, plus any manual turn
    w, l = spec["size"]
    bw, bl = hi - lo
    turn = 90 if abs(bw - l) + abs(bl - w) < abs(bw - w) + abs(bl - l) else 0
    turn = (turn + spec.get("model", {}).get("rot", 0)) % 360
    c = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, 0])
    R = trimesh.transformations.translation_matrix([w / 2, l / 2, -z0]) @ _rot([0, 0, 1], turn) @ \
        trimesh.transformations.translation_matrix(-c)
    off = spec.get("model", {}).get("offset", [0, 0])
    R = trimesh.transformations.translation_matrix([off[0], off[1], 0]) @ R
    out = trimesh.Scene()
    for i, m in enumerate(meshes):
        m.apply_transform(R)
        out.add_geometry(m, node_name=f"{board_id}-{i}", geom_name=f"{board_id}-{i}")
    dst = SRC / f"{board_id}.norm.glb"
    out.export(dst)
    return {"src": src.name, "pcb_mm": [round(float(x), 1) for x in (bw, bl)], "thickness": round(z1 - z0, 2),
            "expected": spec["size"], "turn": turn, "flipped": bool(flip),
            "faces": int(sum(len(m.faces) for m in meshes)),
            "size_ok": bool(np.allclose(sorted([bw, bl]), sorted(spec["size"]), atol=3.0)), "out": dst.name}


def stack(board_id: str, spec: dict) -> dict:
    """A board made of several makers' models (boards.yaml › model.stack), e.g. a display shield plugged on its
    host: each part as its maker drew it (PCB top at z = 0), turned about X (`rot_x`, degrees) and moved (`at`)
    into the first part's frame, then the whole by `offset` into the drawing's frame (the outline's bottom-left
    corner at the origin, the lowest PCB's underside at z = 0)."""
    model = spec["model"]
    out = trimesh.Scene()
    k = 0
    for part in model["stack"]:
        src = next((p for p in sorted(SRC.glob(f"{part['src']}.*")) if p.suffix.lower() in EXTS and ".norm" not in p.name), None)
        if not src:
            raise FileNotFoundError(f"{part['src']}: run tools/fetch_render_assets.py")
        T = trimesh.transformations.translation_matrix(model.get("offset", [0, 0, 0])) @             trimesh.transformations.translation_matrix(part.get("at", [0, 0, 0])) @ _rot([1, 0, 0], part.get("rot_x", 0))
        for m in baked(load_mm(src)):
            m.apply_transform(T)
            m = _recolour(m, model.get("recolour", {}))
            out.add_geometry(m, node_name=f"{board_id}-{k}", geom_name=f"{board_id}-{k}")
            k += 1
    dst = SRC / f"{board_id}.norm.glb"
    out.export(dst)
    lo, hi = out.bounds
    return {"parts": [p["src"] for p in model["stack"]], "bounds": [[round(float(v), 2) for v in lo], [round(float(v), 2) for v in hi]],
            "faces": int(sum(len(g.faces) for g in out.geometry.values())), "out": dst.name}


WEB = REPO / "site" / "assets" / "boards"


def web_model(board_id: str, spec: dict, faces: int = 45000) -> dict:
    """The viewer's copy (boards.yaml › model.web: the licence lets us publish it), from the normalised model:
    the PCBs and other large parts as they are (decimation tears a drilled board), parts under 1.2 mm dropped,
    those under 4 mm as their box, the rest decimated to fit about `faces` triangles; one colour per part."""
    sc = trimesh.load(SRC / f"{board_id}.norm.glb", force="scene")
    keep, boxes, rest = [], [], []
    for m in baked(sc):
        size = max(m.extents)
        if size < 1.2:
            continue
        (keep if m.area > 3000 else boxes if size < 4.0 else rest).append(m)
    budget = max(1, faces - sum(len(m.faces) for m in keep) - 12 * len(boxes))
    ratio = min(1.0, budget / max(1, sum(len(m.faces) for m in rest)))
    out = trimesh.Scene()
    parts = [_solid(m, _mean_colour(m)) for m in keep] + [_solid(m.bounding_box_oriented.to_mesh(), _mean_colour(m)) for m in boxes]
    for m in rest:
        n = max(12, int(len(m.faces) * ratio))
        c = _mean_colour(m)
        if len(m.faces) > n:
            try:
                m = m.simplify_quadric_decimation(face_count=n)
            except Exception:
                pass
        parts.append(_solid(m, c))
    for i, m in enumerate(parts):
        out.add_geometry(m, node_name=f"{board_id}-{i}", geom_name=f"{board_id}-{i}")
    WEB.mkdir(parents=True, exist_ok=True)
    dst = WEB / f"{board_id}.glb"
    out.export(dst)
    return {"web": str(dst.relative_to(REPO)), "faces": int(sum(len(g.faces) for g in out.geometry.values())),
            "kB": round(dst.stat().st_size / 1024)}


def _solid(m: trimesh.Trimesh, colour) -> trimesh.Trimesh:
    """One colour for the whole part, as glTF vertex colours, which are linear: the makers' colours are sRGB."""
    c = np.asarray(colour, dtype=float) / 255
    lin = np.where(c[:3] <= 0.04045, c[:3] / 12.92, ((c[:3] + 0.055) / 1.055) ** 2.4)
    m.visual = trimesh.visual.ColorVisuals(m, face_colors=np.round(np.append(lin, c[3]) * 255).astype(np.uint8))
    return m


def _mean_colour(m: trimesh.Trimesh) -> np.ndarray:
    """One RGBA colour (uint8) for a part: its material's, else its faces' mean."""
    v = m.visual
    try:
        f = getattr(getattr(v, "material", None), "baseColorFactor", None)
        if f is not None:
            f = np.asarray(f, dtype=float)[:4]
            return np.round(f * 255 if f.max() <= 1 else f).astype(np.uint8)
        if hasattr(v, "main_color"):
            return np.asarray(v.main_color, dtype=np.uint8)
    except Exception:
        pass
    return np.array([128, 128, 128, 255], dtype=np.uint8)


def _recolour(m: trimesh.Trimesh, table: dict) -> trimesh.Trimesh:
    """Swap a model's generic colours for the real ones (boards.yaml › model.recolour: "#rrggbb": "#rrggbb")."""
    c = _mean_colour(m)
    key = "#%02x%02x%02x" % tuple(int(x) for x in c[:3])
    if key in table:
        h = table[key].lstrip("#")
        m.visual = trimesh.visual.ColorVisuals(m, face_colors=np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)] + [255], dtype=np.uint8))
    return m


def main(only=None):
    lib = yaml.safe_load((REPO / "mechanical" / "boards" / "boards.yaml").read_text(encoding="utf-8"))["boards"]
    SRC.mkdir(parents=True, exist_ok=True)
    found = 0
    for bid, spec in lib.items():
        if only and bid not in only:
            continue
        model = spec.get("model", {})
        src = next((p for p in sorted(SRC.glob(f"{bid}.*")) if p.suffix.lower() in EXTS and ".norm" not in p.name), None)
        if not src and "stack" not in model:
            continue
        found += 1
        try:
            print(bid, stack(bid, spec) if "stack" in model else normalise(bid, spec, src))
            if model.get("web"):
                print(bid, web_model(bid, spec))
        except Exception as ex:
            print(bid, "FAILED:", ex)
    if not found:
        print("no models in", SRC.relative_to(REPO), "- see docs/boards-3d.md")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
