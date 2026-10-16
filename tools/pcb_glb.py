"""Turn KiCad's GLB export into a light model for the web viewer.

KiCad writes metres, Y-up, one node per 3D-model body (10 000+ nodes for a
populated board).  The viewer wants millimetres, Z-up, KiCad's origin at the
board's top-left corner with rack-style axes (x right, y = -KiCad y), and a
handful of meshes.  We bake every node's transform, merge by material colour,
decimate, and export one small GLB per board.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[1]
# KiCad GLB (x, y-up, z = KiCad y) [m] → viewer (x, -KiCad y, up) [mm]
AXES = np.array([[1000, 0, 0, 0], [0, 0, -1000, 0], [0, 1000, 0, 0], [0, 0, 0, 1]], dtype=float)


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


def convert(src: Path, dst: Path, max_faces: int = 60000) -> dict:
    scene = trimesh.load(src)
    groups: dict[tuple, list] = defaultdict(list)
    for node in scene.graph.nodes_geometry:
        tf, gname = scene.graph[node]
        g = scene.geometry[gname]
        if not isinstance(g, trimesh.Trimesh) or len(g.faces) == 0:
            continue
        m = g.copy()
        m.apply_transform(AXES @ tf)
        groups[_color(g)].append(m)
    merged = {k: trimesh.util.concatenate(v) for k, v in groups.items()}
    total = sum(len(m.faces) for m in merged.values())
    out = trimesh.Scene()
    stats = {}
    for i, (col, m) in enumerate(sorted(merged.items(), key=lambda kv: -len(kv[1].faces))):
        target = max(200, int(max_faces * len(m.faces) / max(total, 1)))
        if len(m.faces) > target:
            try:
                m = m.simplify_quadric_decimation(face_count=target)
            except Exception:
                pass
        rgba = [float(c) for c in col]
        metallic = 0.9 if (rgba[0] > 0.6 and abs(rgba[0] - rgba[1]) < 0.08 and abs(rgba[1] - rgba[2]) < 0.08) else 0.05
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            baseColorFactor=rgba, metallicFactor=metallic, roughnessFactor=0.45))
        out.add_geometry(m, node_name=f"part{i}", geom_name=f"part{i}")
        stats[str(col)] = len(m.faces)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.export(dst)
    return {"in_faces": total, "out_faces": sum(stats.values()), "groups": len(stats), "bytes": dst.stat().st_size}


def main(boards=("bay-node", "power-hub")):
    for b in boards:
        src = REPO / "electronics" / b / "fab" / f"{b}.glb"
        if not src.exists():
            print("skip", b, "(no fab GLB; run tools/kicad.sh", b, "--fab)")
            continue
        info = convert(src, REPO / "site" / "assets" / "pcb" / f"{b}.glb")
        print(b, info)


if __name__ == "__main__":
    main(sys.argv[1:] or ("bay-node", "power-hub"))
