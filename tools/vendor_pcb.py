#!/usr/bin/env python3
"""Populated 3D models of the dev boards whose makers publish their PCB design but no STEP (the Nordic DKs: an
Altium PcbDoc, its parts' models embedded).

    python tools/vendor_pcb.py nrf52840-dk      # render/assets/boards/<id>.PcbDoc → render/assets/vendor/<id>/<id>.glb

tools/board_models.py calls it for a board whose model is a PcbDoc (tools/fetch_render_assets.py extracts it) and
normalises the result like any maker's model.  KiCad imports the design (kicad-cli pcb import), exports its
parts with the models it carries (kicad-cli pcb export glb) and its copper, mask openings, silkscreen and holes
(build_board.export_art, in KiCad's python); tools/pcb_glb.py paints the board's two faces with them, in the
board's own colours (boards.yaml › model: `mask`, `silk`).  A part whose model KiCad can't read (a SolidWorks
part) gets a black block over its pads.  The design's text variables (its product name on the silkscreen) come
from model.vars.  Needs KiCad 10: kicad-cli and a python with pcbnew, from $KICAD_CLI and $KICAD_PYTHON, else
the PATH's kicad-cli and python3, else the Windows installation's.
"""

from __future__ import annotations

import json
import os

import numpy as np
import shutil
import subprocess
import sys
from pathlib import Path

import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "electronics" / "tools"))
import pcb_glb  # noqa: E402

WORK = REPO / "render" / "assets" / "vendor"
WIN_KICAD = Path(r"C:\Program Files\KiCad\10.0\bin")
MODEL_EXTS = (".step", ".stp", ".wrl", ".igs", ".iges")
STANDIN = (24, 24, 26)          # a part without a readable model: a black block over its pads
STANDIN_H = 0.9


def kicad() -> tuple[str, str]:
    cli = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or str(WIN_KICAD / "kicad-cli.exe")
    py = os.environ.get("KICAD_PYTHON") or (str(WIN_KICAD / "python.exe") if os.name == "nt" else "python3")
    return cli, py


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lighter(c, k: float) -> tuple[int, int, int]:
    return tuple(int(round(v + (255 - v) * k)) for v in c)


def unreadable(pcb: Path) -> list[tuple[str, bool, float, float, float, float]]:
    """The footprints whose 3D model KiCad can't load (not STEP/VRML/IGES), as pcb_glb.footprint_boxes gives them."""
    import sexp
    tree = sexp.loads(pcb.read_text(encoding="utf-8"))
    bad = set()
    for fp in sexp.find_all(tree, "footprint"):
        models = [str(m[1]) for m in sexp.find_all(fp, "model")]
        if models and not any(m.lower().endswith(MODEL_EXTS) for m in models):
            bad.add(pcb_glb._ref(fp, sexp))
    return [b for b in pcb_glb.footprint_boxes(pcb) if b[0] in bad]


def design(src: Path, bid: str, model: dict) -> Path:
    """render/assets/vendor/<bid>/<bid>.kicad_pcb: the maker's design (an Altium PcbDoc through KiCad's import,
    or a KiCad board), its text variables from model.vars."""
    cli, _ = kicad()
    work = WORK / bid
    work.mkdir(parents=True, exist_ok=True)
    pcb = work / f"{bid}.kicad_pcb"
    if src.suffix.lower() == ".pcbdoc":
        subprocess.run([cli, "pcb", "import", "--format", "altium", "-o", str(pcb), str(src)], check=True,
                       capture_output=True)
    else:
        shutil.copyfile(src, pcb)
    (work / f"{bid}.kicad_pro").write_text(json.dumps({"meta": {"filename": f"{bid}.kicad_pro", "version": 3},
                                                       "text_variables": model.get("vars", {})}, indent=2))
    return pcb


def layer_art(pcb: Path, model: dict) -> dict:
    """The design's copper, mask openings, silkscreen and holes (build_board.export_art, in KiCad's python), in
    the board's colours (model: mask, silk, finish), for tools/pcb_glb.py to paint its faces."""
    _, py = kicad()
    # KiCad's own python: none of this interpreter's environment (a venv's launcher variable points it at the
    # wrong standard library)
    env = {k: v for k, v in os.environ.items() if k not in ("__PYVENV_LAUNCHER__", "PYTHONHOME", "PYTHONPATH",
                                                             "VIRTUAL_ENV")}
    r = subprocess.run([py, "-c", "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                                  "import build_board; build_board.export_art(Path(sys.argv[2]), sys.argv[3])",
                        str(REPO / "electronics" / "tools"), str(pcb.parent), pcb.stem], capture_output=True,
                       text=True, env=env)
    if r.returncode:
        raise RuntimeError(f"export_art (KiCad's python): {r.stderr[-1500:]}")
    art = json.loads((pcb.parent / "build" / f"{pcb.stem}-art.json").read_text())
    if model.get("tent_vias"):
        # a design whose import lost its vias' tenting (the BeaglePlay's, from Allegro through Altium): the vias
        # (drill ≤ 0.3 mm) under the mask, as the board is built, not 2000 gold rings
        vias = np.array([h[:2] for h in art["holes"] if h[2] <= 0.3])
        art["holes"] = [h for h in art["holes"] if h[2] > 0.3]
        for side in ("F.Mask", "B.Mask"):
            keep = []
            for poly in art["layers"].get(side, []):
                p = np.array(poly)
                lo, hi = p.min(axis=0), p.max(axis=0)
                c = (lo + hi) / 2
                if max(hi - lo) <= 0.6 and len(vias) and np.min(np.hypot(*(vias - c).T)) < 0.15:
                    continue                    # a via's opening
                keep.append(poly)
            art["layers"][side] = keep
    mask = _rgb(model.get("mask", "#1e5e36"))
    art.update(mask=mask, mask_cu=_lighter(mask, 0.16), silk=_rgb(model.get("silk", "#eeeee8")),
               finish=model.get("finish", "ENIG"))
    return art


def convert(src: Path, bid: str, model: dict) -> Path:
    """render/assets/vendor/<bid>/<bid>.glb: the populated board, millimetres, z up from its underside's plane
    (x right, y = -KiCad y, as tools/pcb_glb.py writes the rack's own boards)."""
    cli, _ = kicad()
    work = WORK / bid
    pcb = design(src, bid, model)
    parts = work / f"{bid}-parts.glb"
    parts.unlink(missing_ok=True)
    r = subprocess.run([cli, "pcb", "export", "glb", "--subst-models", "-f", "-o", str(parts), str(pcb)],
                       capture_output=True, text=True)      # exit 2 for a model it can't read: it still writes the rest
    if not parts.exists():
        raise RuntimeError(f"kicad-cli pcb export glb: {r.stdout[-800:]}{r.stderr[-800:]}")
    art = layer_art(pcb, model)
    scene = trimesh.load(parts)
    body, out = [], trimesh.Scene()
    for node in scene.graph.nodes_geometry:
        tf, gname = scene.graph[node]
        g = scene.geometry[gname]
        if not isinstance(g, trimesh.Trimesh) or not len(g.faces):
            continue
        m = g.copy()
        m.apply_transform(pcb_glb.AXES @ tf)
        if gname.startswith(f"{bid}_PCB"):
            body.append(m)
        elif not gname.startswith(f"{bid}_"):
            out.add_geometry(m)
    for i, m in enumerate(pcb_glb.board_body(body, art, bid)):
        out.add_geometry(m, node_name=f"board{i}", geom_name=f"board{i}")
    top = max(b.bounds[1][2] for b in body)
    t = top - min(b.bounds[0][2] for b in body)
    for ref, front, x0, y0, x1, y1 in unreadable(pcb):
        z0, z1 = (top, top + STANDIN_H) if front else (top - t - STANDIN_H, top - t)
        blk = pcb_glb._box(x0 + 0.3, x1 - 0.3, -y1 + 0.3, -y0 - 0.3, z0, z1)
        blk.visual = trimesh.visual.ColorVisuals(blk, face_colors=[*STANDIN, 255])
        out.add_geometry(blk, node_name=f"standin-{ref}", geom_name=f"standin-{ref}")
    dst = work / f"{bid}.glb"
    out.export(dst)
    return dst


def paint_faces(meshes: list, art: dict, name: str, size, t: float) -> list:
    """A maker's STEP in the drawing's frame (PCB outline from (0, 0), underside at z = 0, t thick) with its PCB's
    faces painted from its design's layers: the PCB's body (the biggest flat part) swapped for painted faces
    (pcb_glb.board_body, its outline laid on the design's), the STEP's own flat layers on its faces (copper,
    mask: zero-thick sheets) dropped.  Its other parts as they are."""
    body = max(meshes, key=lambda m: m.extents[0] * m.extents[1] if m.extents[2] > 0.5 * t else 0.0)
    keep = [m for m in meshes if m is not body and not (
        m.extents[2] < 0.02 and (abs(m.bounds[0][2]) < 0.06 or abs(m.bounds[1][2] - t) < 0.06))]
    (bx0, by0, _), (bx1, by1, _) = body.bounds
    (ox, oy), (aw, ah) = art["origin"], art["size"]
    if abs(aw - (bx1 - bx0)) > 0.05 * (bx1 - bx0) or abs(ah - (by1 - by0)) > 0.05 * (by1 - by0):
        # an import that left more than the outline on Edge.Cuts (a drawing frame): the board where its copper
        # and mask are, at the STEP's size
        pts = np.array([q for k in ("F.Cu", "B.Cu", "F.Mask", "B.Mask") for poly in art["layers"].get(k, [])
                        for q in poly])
        c = (pts.min(axis=0) + pts.max(axis=0)) / 2
        aw, ah = bx1 - bx0, by1 - by0
        ox, oy = c[0] - aw / 2, c[1] - ah / 2
        art = {**art, "origin": [float(ox), float(oy)], "size": [float(aw), float(ah)]}
    sx, sy = aw / (bx1 - bx0), ah / (by1 - by0)
    # drawing (x, y) → board_body's frame (KiCad x, −KiCad y): the outlines' boxes laid on each other
    to_kicad = np.array([[sx, 0, 0, ox - bx0 * sx], [0, sy, 0, -oy - by1 * sy], [0, 0, 1, 0], [0, 0, 0, 1]])
    painted = pcb_glb.board_body([body.copy().apply_transform(to_kicad)], art, name)
    back = np.linalg.inv(to_kicad)
    return keep + [m.apply_transform(back) for m in painted]


if __name__ == "__main__":
    import yaml
    lib = yaml.safe_load((REPO / "mechanical" / "boards" / "boards.yaml").read_text(encoding="utf-8"))["boards"]
    for bid in sys.argv[1:]:
        print(bid, convert(REPO / "render" / "assets" / "boards" / f"{bid}.PcbDoc", bid, lib[bid].get("model", {})))
