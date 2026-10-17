#!/usr/bin/env python3
"""Panel-frame prototype: render its parts, estimate their filament, export a 3D scene.

    python tools/panel_proto.py [--cols 2] [--rows 2] [--out mechanical/build/panel]

Writes, in --out:
  * <part>.stl          every part type (OpenSCAD, $fn=24)
  * proto.glb           one mesh per part type (mm, Z up)
  * proto.json          instances (4×4 matrices, frame coordinates), boards, masses, and the
                        comparison with today's aluminium-frame rack
Filament is estimated from the mesh, as a slicer would lay it: a 1.1 mm shell over the whole
surface (3 perimeters, 4–5 top/bottom layers), 15 % infill inside, PETG at 1.27 g/cm³.  The
same rule is applied to today's STLs (mechanical/stl/), so the comparison is like for like.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).parent))
import rackcfg  # noqa: E402
from build import MECH, openscad_cmd  # noqa: E402

PETG = 1.27          # g/cm³
SHELL = 1.1          # mm
INFILL = 0.15

PARTS = {
    # name: (scad, defines)
    "ladder_base": ("parts/ladder.scad", {"PART": "base"}),
    "ladder_a": ("parts/ladder.scad", {"PART": "row", "ROW": 0}),
    "ladder_b": ("parts/ladder.scad", {"PART": "row", "ROW": 1}),
    "ladder_c": ("parts/ladder.scad", {"PART": "row", "ROW": 2}),
    "ladder_d": ("parts/ladder.scad", {"PART": "row", "ROW": 3}),
    "ladder_cap": ("parts/ladder.scad", {"PART": "cap", "ROW": 2}),
    "tray": ("parts/tray.scad", {"PART": "tray"}),
    "cap_plate": ("parts/tray.scad", {"PART": "cap_plate"}),
    "floor_plate": ("parts/tray.scad", {"PART": "floor_plate"}),
    "drawer_light": ("parts/drawer.scad", {"LIGHT": True}),
}
LABELS = {
    "ladder_base": "Base ladder", "ladder_a": "Ladder, row A", "ladder_b": "Ladder, row B",
    "ladder_cap": "Cap strip", "tray": "Tray", "cap_plate": "Cap plate", "floor_plate": "Floor plate",
    "drawer_light": "Drawer (light)",
}
TODAY_PER_BAY = {"carrier_base": 1, "carrier_deck": 1, "drawer": 1, "drawer_guide_left": 1, "drawer_guide_right": 1}
PROBE = """include <lib/panels.scad>
echo(PANEL_T=PANEL_T, PANEL_CLEAR=PANEL_CLEAR, PANEL_PITCH=PANEL_PITCH, PF=PF, PR=PR, ROW_Y0=FRAME_ROW_Y0,
     TILT=TILT, ROW_Z=[for (k = [0 : 4]) row_z(k)], CARRIER_W=CARRIER_W, CARRIER_D=CARRIER_D,
     PLENUM=CARRIER_PLENUM, DRAWER_X0=DRAWER_X0, DRAWER_Y0=DRAWER_Y0, DRAWER_TRAVEL=DRAWER_TRAVEL,
     DRAWER_BOTTOM=DRAWER_BOTTOM, PLATE_X0=PLATE_X0, PLATE_Y0=PLATE_Y0, PLATE_W=PLATE_W, PLATE_D=PLATE_D,
     PLATE_T=PLATE_T, NODE_X0=NODE_X0, NODE_FRONT_Y=NODE_FRONT_Y, NODE_Z=CARRIER_BOTTOM + CARRIER_STANDOFF,
     NODE_SIZE=NODE_SIZE, FLOOR_Y0=PF + 1);
"""


def run_scad(src: str, out: Path, defines: dict) -> str:
    cmd = openscad_cmd() + ["--export-format", "binstl", "-D", "$fn=24", "-o", str(out)]
    for k, v in defines.items():
        cmd += ["-D", f'{k}="{v}"' if isinstance(v, str) else f"{k}={str(v).lower() if isinstance(v, bool) else v}"]
    cmd.append(src)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=MECH)
    if p.returncode != 0 or not out.exists():
        raise RuntimeError(f"OpenSCAD failed for {out.name}:\n{p.stderr[-1500:]}")
    return p.stderr


def constants(out: Path) -> dict:
    probe = MECH / "_panel_probe.scad"
    probe.write_text(PROBE, encoding="utf-8")
    try:
        cmd = openscad_cmd() + ["-o", str(out / "_probe.echo"), str(probe)]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=MECH)
    finally:
        probe.unlink()
    echo = out / "_probe.echo"
    text = p.stderr + p.stdout + (echo.read_text(encoding="utf-8") if echo.exists() else "")
    line = next(l for l in text.splitlines() if l.startswith("ECHO:"))
    c = {}
    for k, v in re.findall(r"(\w+) = (\[[^\]]*\]|[-\d.e]+)", line):
        c[k] = json.loads(v) if v.startswith("[") else float(v)
    return c


def grams(mesh: trimesh.Trimesh) -> float:
    v = abs(mesh.volume)
    shell = min(v, mesh.area * SHELL)
    return (shell + INFILL * (v - shell)) / 1000.0 * PETG


def bbox(mesh: trimesh.Trimesh) -> list[float]:
    """Smallest footprint on the bed, print orientation as exported (XY), rounded."""
    ext = mesh.bounds[1] - mesh.bounds[0]
    return [round(float(x), 1) for x in ext]


# ------------------------------------------------------------------ transforms (frame mm, Z up)

def m_ladder(x0: float) -> np.ndarray:
    # ladder profile: 2D x = frame Y, 2D y = frame Z, extruded along +z = frame X
    return np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)


def m_row(c: dict, k: int, x0: float) -> np.ndarray:
    t = math.radians(c["TILT"])
    return np.array([[1, 0, 0, x0],
                     [0, math.cos(t), -math.sin(t), c["ROW_Y0"]],
                     [0, math.sin(t), math.cos(t), c["ROW_Z"][k]],
                     [0, 0, 0, 1]], float)


def m_tr(x, y, z) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = [x, y, z]
    return m


def scene(c: dict, cols: int, rows: int, boards: dict) -> dict:
    inst, extra = [], []
    pitch, t, clear = c["PANEL_PITCH"], c["PANEL_T"], c["PANEL_CLEAR"]
    row_names = "abcd"

    def add(part, m, group, level=0, col=0, row=None, slide=None):
        inst.append({"part": part, "m": [round(float(v), 4) for v in m.T.flatten()], "group": group,
                     "level": level, "col": col, "row": row, "slide": slide})

    for i in range(cols + 1):
        x = i * pitch
        add("ladder_base", m_ladder(x), "ladder", level=0, col=i)
        for k in range(rows):
            add(f"ladder_{row_names[k]}", m_ladder(x), "ladder", level=k + 1, col=i)
        add("ladder_cap", m_ladder(x), "ladder", level=rows + 1, col=i)
    t_rad = math.radians(c["TILT"])
    u = [0.0, math.cos(t_rad), math.sin(t_rad)]
    demo = ["nucleo-64", "nrf52840-dk", "rpi-pico2", "esp32-s3-devkitc", "frdm-mcxn947", "arduino-uno-r4"]
    n = 0
    for j in range(cols):
        x0 = j * pitch + t + clear
        add("floor_plate", m_tr(x0, c["FLOOR_Y0"], 0), "plate", level=0, col=j, slide=[0, -1, 0])
        add("cap_plate", m_row(c, rows, x0), "plate", level=rows + 1, col=j, row=rows, slide=[-v for v in u])
        for k in range(rows):
            mt = m_row(c, k, x0)
            add("tray", mt, "tray", level=k + 1, col=j, row=k, slide=[-v for v in u])
            md = mt @ m_tr(c["DRAWER_X0"], c["DRAWER_Y0"], c["PLENUM"])
            add("drawer_light", md, "drawer", level=k + 1, col=j, row=k, slide=[-v for v in u])
            # stand-ins: bay node PCB in the tray, a dev board on its plate in the drawer
            extra.append({"kind": "pcb", "color": "#1f7a4d", "size": [c["NODE_SIZE"][0], c["NODE_SIZE"][1], 1.6],
                          "m": [round(float(v), 4) for v in (mt @ m_tr(c["NODE_X0"], c["NODE_FRONT_Y"], c["NODE_Z"])).T.flatten()],
                          "follows": "tray", "level": k + 1, "col": j, "row": k})
            bid = demo[n % len(demo)]
            n += 1
            b = boards[bid]
            o = rackcfg.orient_board(b)
            if o["usb_side"]:
                bx, by = 6, (c["PLATE_D"] - o["l"]) / 2
            else:
                gap = max(3, min(26, c["PLATE_D"] - o["l"] - 4))
                bx, by = (c["PLATE_W"] - o["w"]) / 2, c["PLATE_D"] - gap - o["l"]
            mp = md @ m_tr(c["PLATE_X0"], c["PLATE_Y0"], c["DRAWER_BOTTOM"])
            extra.append({"kind": "plate", "color": "#e7e2d6", "size": [c["PLATE_W"], c["PLATE_D"], c["PLATE_T"]],
                          "m": [round(float(v), 4) for v in mp.T.flatten()], "follows": "drawer", "level": k + 1, "col": j, "row": k})
            mb = mp @ m_tr(bx, by, c["PLATE_T"] + b.get("standoff", 6))
            extra.append({"kind": "board", "id": bid, "name": b.get("short", b["name"]), "color": b.get("color", "#1b5e20"),
                          "size": [o["w"], o["l"], 1.6], "height": b.get("height", 10),
                          "m": [round(float(v), 4) for v in mb.T.flatten()], "follows": "drawer", "level": k + 1, "col": j, "row": k})
    return {"instances": inst, "extras": extra, "slide_dir_row": u, "drawer_travel": c["DRAWER_TRAVEL"]}


def rack_counts(cols: int, rows: int) -> dict:
    """Part counts of a cols × rows panel-frame rack of single bays."""
    lad = cols + 1
    counts = {"ladder_base": lad, "ladder_cap": lad, "tray": cols * rows, "drawer_light": cols * rows,
              "cap_plate": cols, "floor_plate": cols}
    for k in range(rows):
        counts[f"ladder_{'abcd'[k]}"] = lad
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--rows", type=int, default=2)
    ap.add_argument("--out", type=Path, default=MECH / "build" / "panel")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    c = constants(a.out)
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {name: ex.submit(run_scad, scad, a.out / f"{name}.stl", d) for name, (scad, d) in PARTS.items()}
        for name, f in futs.items():
            f.result()
            print("rendered", name)
    meshes = {name: trimesh.load(a.out / f"{name}.stl") for name in PARTS}

    masses = {name: round(grams(m), 1) for name, m in meshes.items()}
    beds = {name: bbox(m) for name, m in meshes.items()}
    today = {}
    for name in TODAY_PER_BAY:
        today[name] = round(grams(trimesh.load(MECH / "stl" / f"{name}.stl")), 1)
    # today's printed parts tied to the aluminium frame (tier brackets, roof decks, base plates)
    frame_today = {n: round(grams(trimesh.load(MECH / "stl" / f"{n}.stl")), 1)
                   for n in ("tier_bracket_left", "tier_bracket_right", "roof_deck", "base_plate")}

    boards = rackcfg.load_boards()
    sc = scene(c, a.cols, a.rows, boards)
    proto = {}
    for i in sc["instances"]:
        proto[i["part"]] = proto.get(i["part"], 0) + 1
    rack = rack_counts(4, 4)
    per_bay_today = sum(today[n] * q for n, q in TODAY_PER_BAY.items())
    per_bay_new = masses["tray"] + masses["drawer_light"]
    rack_new = sum(masses[n] * q for n, q in rack.items())
    rack_today = 16 * per_bay_today + 5 * (frame_today["tier_bracket_left"] + frame_today["tier_bracket_right"]) \
        + 4 * frame_today["roof_deck"] + 4 * frame_today["base_plate"]
    data = {
        "constants": c, "scene": sc, "labels": LABELS,
        "parts": {n: {"grams": masses[n], "bbox": beds[n], "proto_qty": proto.get(n, 0)} for n in PARTS if proto.get(n) or n in rack},
        "proto_total": round(sum(masses[n] * q for n, q in proto.items()), 0),
        "per_bay": {"today": round(per_bay_today, 1), "today_parts": today, "new": round(per_bay_new, 1)},
        "rack_4x4": {"today": round(rack_today, 0), "new": round(rack_new, 0), "counts": rack,
                     "today_frame_parts": frame_today},
        "estimator": {"shell_mm": SHELL, "infill": INFILL, "density": PETG},
    }
    (a.out / "proto.json").write_text(json.dumps(data, indent=1), encoding="utf-8")

    sc3 = trimesh.Scene()
    for name in proto:
        sc3.add_geometry(meshes[name], node_name=name, geom_name=name)
    (a.out / "proto.glb").write_bytes(sc3.export(file_type="glb"))

    print(f"\n{'part':<16}{'g each':>8}{'proto qty':>11}  bed footprint (mm)")
    for n, p in data["parts"].items():
        print(f"{n:<16}{p['grams']:>8}{p['proto_qty']:>11}  {p['bbox']}")
    print(f"\nprototype {a.cols}×{a.rows}: {data['proto_total']:.0f} g")
    print(f"per bay: today {per_bay_today:.0f} g (carrier + deck + drawer + guides) → {per_bay_new:.0f} g (tray + drawer)")
    print(f"4×4 rack, structure + bays (plates, cameras, base enclosure not counted): "
          f"today {rack_today:.0f} g + aluminium → {rack_new:.0f} g")
    print("wrote", a.out / "proto.json", "and", a.out / "proto.glb")


if __name__ == "__main__":
    main()
