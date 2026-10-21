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


def convert(src: Path, bid: str, model: dict) -> Path:
    """render/assets/vendor/<bid>/<bid>.glb: the populated board, millimetres, z up from its underside's plane
    (x right, y = -KiCad y, as tools/pcb_glb.py writes the rack's own boards)."""
    cli, py = kicad()
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
    parts = work / f"{bid}-parts.glb"
    parts.unlink(missing_ok=True)
    r = subprocess.run([cli, "pcb", "export", "glb", "--subst-models", "-f", "-o", str(parts), str(pcb)],
                       capture_output=True, text=True)      # exit 2 for a model it can't read: it still writes the rest
    if not parts.exists():
        raise RuntimeError(f"kicad-cli pcb export glb: {r.stdout[-800:]}{r.stderr[-800:]}")
    # KiCad's own python: none of this interpreter's environment (a venv's launcher variable points it at the
    # wrong standard library)
    env = {k: v for k, v in os.environ.items() if k not in ("__PYVENV_LAUNCHER__", "PYTHONHOME", "PYTHONPATH",
                                                             "VIRTUAL_ENV")}
    r = subprocess.run([py, "-c", "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                                  "import build_board; build_board.export_art(Path(sys.argv[2]), sys.argv[3])",
                        str(REPO / "electronics" / "tools"), str(work), bid], capture_output=True, text=True, env=env)
    if r.returncode:
        raise RuntimeError(f"export_art (KiCad's python): {r.stderr[-1500:]}")
    art = json.loads((work / "build" / f"{bid}-art.json").read_text())
    mask = _rgb(model.get("mask", "#1e5e36"))
    art.update(mask=mask, mask_cu=_lighter(mask, 0.16), silk=_rgb(model.get("silk", "#eeeee8")),
               finish=model.get("finish", "ENIG"))
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


if __name__ == "__main__":
    import yaml
    lib = yaml.safe_load((REPO / "mechanical" / "boards" / "boards.yaml").read_text(encoding="utf-8"))["boards"]
    for bid in sys.argv[1:]:
        print(bid, convert(REPO / "render" / "assets" / "boards" / f"{bid}.PcbDoc", bid, lib[bid].get("model", {})))
