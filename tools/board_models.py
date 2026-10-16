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


def main(only=None):
    lib = yaml.safe_load((REPO / "mechanical" / "boards" / "boards.yaml").read_text(encoding="utf-8"))["boards"]
    SRC.mkdir(parents=True, exist_ok=True)
    found = 0
    for bid, spec in lib.items():
        if only and bid not in only:
            continue
        src = next((p for p in sorted(SRC.glob(f"{bid}.*")) if p.suffix.lower() in EXTS and ".norm" not in p.name), None)
        if not src:
            continue
        found += 1
        try:
            print(bid, normalise(bid, spec, src))
        except Exception as ex:
            print(bid, "FAILED:", ex)
    if not found:
        print("no models in", SRC.relative_to(REPO), "- see docs/boards-3d.md")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
