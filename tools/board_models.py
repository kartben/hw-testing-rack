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

    model: { rot: 180, flip: false, offset: [0, 0] }   # extra turn about Z, upside-down export, nudge (mm; a third
                                                       # value lowers a whole device under its "PCB" plane)
    model: { recolour: { "#003700": "#f4f4f2" },          # a STEP's design colours → the board's real ones; parts of
             recolour_in: [["#666666", [0, 70, 50, 82], "#e8e5d8"]] }   # one colour told apart by where they are
    model: { paint: <the maker's PCB design (PcbDoc)>, mask: "#161616" }   # its PCB's faces painted from the design

A board made of several models (a shield on its host) lists them under model.stack instead (see stack()), and
model.web: true also writes the viewer's copy to site/assets/boards/<id>.glb, for models whose licence lets the
repository publish them (see docs/boards-3d.md): compressed by gltfpack (meshoptimizer) when it is installed: on
the PATH, or the command in $GLTFPACK.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh
import yaml

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "render" / "assets" / "boards"
EXTS = (".step", ".stp", ".glb", ".gltf", ".wrl", ".pcbdoc")   # a PcbDoc: tools/vendor_pcb.py makes the model


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
    """The scene's meshes in its frame, one per material: a STEP solid painted face by face (a PCB's solder mask,
    pads and edges; a connector's shell and insulator) comes in with several, which a glTF export would melt into
    its first."""
    out = []
    for node in scene.graph.nodes_geometry:
        tf, g = scene.graph[node]
        m = scene.geometry[g]
        if isinstance(m, trimesh.Trimesh) and len(m.faces):
            m = m.copy()
            m.apply_transform(tf)
            out += _by_material(m)
    return out


def _by_material(m: trimesh.Trimesh) -> list[trimesh.Trimesh]:
    subs = getattr(getattr(m.visual, "material", None), "materials", None)
    fm = getattr(m.visual, "face_materials", None)
    if subs is None or fm is None:
        return [m]
    fm = np.asarray(fm)
    out = []
    for k, sub in enumerate(subs):
        faces = m.faces[fm == k]
        if not len(faces):
            continue
        part = trimesh.Trimesh(vertices=m.vertices, faces=faces, process=False)
        part.remove_unreferenced_vertices()
        part.visual = trimesh.visual.TextureVisuals(material=sub)
        out.append(part)
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
    if src.suffix.lower() == ".pcbdoc":         # a maker's PCB design: populated and painted through KiCad
        import vendor_pcb
        src = vendor_pcb.convert(src, board_id, spec.get("model", {}))
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
    off = list(spec.get("model", {}).get("offset", [0, 0])) + [0.0]
    R = trimesh.transformations.translation_matrix([off[0], off[1], off[2]]) @ R
    out = trimesh.Scene()
    t = z1 - z0
    kept = []
    for m in meshes:
        m.apply_transform(R)
        if 0.01 < m.bounds[0][2] and m.bounds[1][2] < t - 0.01:
            continue                            # inside the PCB (a board's inner copper planes): never seen
        for colour, (x0, y0, x1, y1), to in spec.get("model", {}).get("recolour_in", []):
            cx, cy = (m.bounds[0][:2] + m.bounds[1][:2]) / 2       # parts of one colour told apart by place
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                m = _recolour(m, {colour: to})
        kept.append(_recolour(m, spec.get("model", {}).get("recolour", {})))
    paint = spec.get("model", {}).get("paint")
    if paint:                                   # its PCB's faces painted from the maker's design (tools/vendor_pcb.py)
        import vendor_pcb
        pcb = vendor_pcb.design(SRC / paint, f"{board_id}-design", spec["model"])
        kept = vendor_pcb.paint_faces(kept, vendor_pcb.layer_art(pcb, spec["model"]), board_id, spec["size"], t)
    for i, m in enumerate(kept):
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


def web_model(board_id: str, spec: dict) -> dict:
    """The viewer's copy (boards.yaml › model.web: the licence lets us publish it), from the normalised model:
    by_material() (every part as drawn, one material per colour), then write_web() (meshopt when gltfpack is
    installed)."""
    out, n = by_material(baked(trimesh.load(SRC / f"{board_id}.norm.glb", force="scene")), board_id)
    dst = WEB / f"{board_id}.glb"
    packed = write_web(out, dst)
    return {"web": str(dst.relative_to(REPO)), "faces": int(sum(len(g.faces) for g in out.geometry.values())),
            "materials": n, "kB": round(dst.stat().st_size / 1024), "packed": packed}


def by_material(meshes: list[trimesh.Trimesh], name: str) -> tuple[trimesh.Scene, int]:
    """A model for the viewer from its meshes (Z up, the PCB in the XY plane): every part as the maker drew it
    (decimating CAD meshes tears them: a board, a chip's body), parts under 0.3 mm dropped; one material per
    part from its colour (gold and bright grey parts read as metal: pins, pads, shields, sockets; the PCB's
    layers as they are, the solder mask see-through over the copper), the parts of one material merged.
    Returns (scene, number of materials)."""
    lo = np.min([m.bounds[0] for m in meshes], axis=0)
    hi = np.max([m.bounds[1] for m in meshes], axis=0)
    span = hi - lo
    groups: dict[tuple, list] = {}
    out = trimesh.Scene()
    for i, m in enumerate(meshes):
        if getattr(getattr(m.visual, "material", None), "baseColorTexture", None) is not None:
            m.visual.material.baseColorTexture = _jpeg(m.visual.material.baseColorTexture)   # not re-encoded as PNG
            out.add_geometry(m, node_name=f"{name}-tex{i}", geom_name=f"{name}-tex{i}")   # a painted PCB face
            continue
        if max(m.extents) < 0.3:
            continue
        layer = m.extents[2] < 2.0 and m.extents[0] * m.extents[1] > 0.3 * span[0] * span[1]
        key = _finish(_mean_colour(m), layer)
        groups.setdefault(key, []).append(m)
    for i, (key, ms) in enumerate(sorted(groups.items())):
        rgba, metal, rough = key
        m = trimesh.util.concatenate(ms)
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (v / 255 for v in rgba[:3])]
        m.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=f"finish-{name}-{i}",          # its finish decided here (render/live_photo.py keeps it)
            baseColorFactor=[*lin, rgba[3] / 255], metallicFactor=metal, roughnessFactor=rough,
            alphaMode="BLEND" if rgba[3] < 250 else "OPAQUE", doubleSided=False))
        out.add_geometry(m, node_name=f"{name}-{i}", geom_name=f"{name}-{i}")
    return out, len(groups)


def _jpeg(img):
    """A texture as a JPEG-format image: glTF export keeps a JPEG as JPEG, anything else becomes a (big) PNG."""
    import io
    from PIL import Image
    if getattr(img, "format", None) == "JPEG":
        return img
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
    return Image.open(io.BytesIO(buf.getvalue()))


def write_web(scene: trimesh.Scene, dst: Path) -> bool:
    """Write a viewer model: through gltfpack (meshoptimizer: on the PATH, or its command in $GLTFPACK), which
    quantises and meshopt-compresses it (about a tenth of the size; the viewer decodes it, GLTFLoader +
    MeshoptDecoder), else plain.  True when packed."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    pack = shlex.split(os.environ["GLTFPACK"], posix=False) if os.environ.get("GLTFPACK") else (
        [shutil.which("gltfpack")] if shutil.which("gltfpack") else None)
    if pack:
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.glb"
            scene.export(raw)
            subprocess.run([*pack, "-i", str(raw), "-o", str(dst), "-cc", "-km"], check=True, capture_output=True)
        return True
    scene.export(dst)
    print(f"{dst.name}: no gltfpack, not compressed")
    return False


def _finish(rgba, layer: bool) -> tuple:
    """A part's material from its colour (sRGB, 0-255): (colour, metalness, roughness).  Gold (ENIG pads, pins)
    and bright neutral greys (tin, nickel: shields, sockets, crystals) as metal, unless the part is one of the PCB's
    layers; the rest as plastic, solder mask, silkscreen."""
    r, g, b, a = (int(v) for v in rgba)
    hi, lo = max(r, g, b), min(r, g, b)
    sat = (hi - lo) / hi if hi else 0.0
    if hi > 120 and sat > 0.35 and r >= g > b:                    # gold
        return (r, g, b, a), 1.0, 0.3
    if not layer and sat < 0.12 and 85 <= hi <= 235:                # tin, nickel
        return (r, g, b, a), 0.9, 0.35
    return (r, g, b, a), 0.0, 0.45 if layer else 0.55


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
