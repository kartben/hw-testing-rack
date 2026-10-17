#!/usr/bin/env python3
"""Line art of the IKEA-style assembly notice, drawn by FreeCAD.

    python tools/notice/run.py                  # every drawing
    python tools/notice/run.py a3 pin hw:m3x8   # some of them (names: notice.py STEPS, thumb:<part>, hw:<fastener>)

1. the panel frame's constants (OpenSCAD probe, tools/panel_proto.py) -> <build>/constants.json;
2. the printed parts of one bay -> OpenSCAD CSG -> exact solids (csg2part.py, in freecadcmd);
3. the bay node: KiCad's STEP export, stand-ins for the parts without a 3D model (node.py);
4. the drawings: notice.py in four freecadcmd processes -> <build>/out/*.svg.

<build> is mechanical/build/notice.  Needs FreeCAD 1.x with the Fasteners workbench
(FREECADCMD=path/to/freecadcmd if it is not found), OpenSCAD, and kicad-cli (or Docker) for
the bay node (without it, the node is drawn as a bare board).
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from build import MECH, openscad_cmd  # noqa: E402
import panel_proto  # noqa: E402

BUILD = REPO / "mechanical" / "build" / "notice"
# the parts of one bay with one row, as the notice shows it (name: scad, defines)
PARTS = {
    "ladder_base": ("parts/ladder.scad", {"PART": "base"}),
    "ladder_a": ("parts/ladder.scad", {"PART": "row", "ROW": 0}),
    "ladder_cap1": ("parts/ladder.scad", {"PART": "cap", "ROW": 1}),
    "brace_base": ("parts/brace.scad", {"ROW": -1}),
    "brace_a": ("parts/brace.scad", {"ROW": 0}),
    "tray": ("parts/tray.scad", {"PART": "tray"}),
    "floor_plate": ("parts/tray.scad", {"PART": "floor_plate"}),
    "cap_plate": ("parts/tray.scad", {"PART": "cap_plate"}),
    "drawer_light": ("parts/drawer.scad", {}),
}
# heaviest first, dealt round-robin to the processes
JOBS = ["done", "b5", "b3", "b1", "a9", "b2", "a8", "b3n", "b4", "cover", "a7", "a6", "a5", "a4", "a3", "a2", "a1",
        "pin", "pin_b", "hook"] + [f"thumb:{p}" for p in ("lb", "la", "lc", "fp", "tr", "dr", "cp", "bb", "nd")] \
       + [f"hw:{h}" for h in ("m3x8", "m3x6", "m25x8", "insert", "jumper")]


def freecadcmd() -> str:
    exe = os.environ.get("FREECADCMD") or shutil.which("freecadcmd") or shutil.which("FreeCADCmd")
    if not exe:
        found = sorted(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Programs\FreeCAD*\bin\freecadcmd.exe"))
                       + glob.glob(r"C:\Program Files\FreeCAD*\bin\freecadcmd.exe"))
        exe = found[-1] if found else None
    if not exe:
        sys.exit("freecadcmd not found: set FREECADCMD")
    return exe


def fc(script: str, **env) -> None:
    subprocess.run([freecadcmd(), str(HERE / script)], env={**os.environ, "NOTICE_BUILD": str(BUILD), **env},
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def csg() -> None:
    (BUILD / "csg").mkdir(parents=True, exist_ok=True)
    for name, (scad, defines) in PARTS.items():
        cmd = openscad_cmd() + ["-o", str(BUILD / "csg" / f"{name}.csg")]
        for k, v in defines.items():
            cmd += ["-D", f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"]
        subprocess.run(cmd + [str(MECH / scad)], cwd=MECH, check=True, capture_output=True)


def node_step() -> None:
    out = BUILD / "parts" / "bay-node.step"
    pcb = REPO / "electronics" / "bay-node" / "bay-node.kicad_pcb"
    out.parent.mkdir(parents=True, exist_ok=True)
    cli = shutil.which("kicad-cli") or next(iter(sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"))), None)
    if shutil.which("docker"):            # the -full image has the 3D models
        cmd = ["docker", "run", "--rm", "-e", "KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels", "-v", f"{REPO}:/repo",
               "-w", "/repo", "kicad/kicad:10.0-full", "kicad-cli", "pcb", "export", "step", "--subst-models",
               "-o", "/repo/" + out.relative_to(REPO).as_posix(), pcb.relative_to(REPO).as_posix()]
    elif cli:
        cmd = [cli, "pcb", "export", "step", "--subst-models", "-o", str(out), str(pcb)]
    else:
        print("no kicad-cli: the bay node is drawn as a bare board")
        return
    subprocess.run(cmd, capture_output=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if out.exists():
        fc("node.py", NODE_BUILD="1")


def main() -> None:
    names = sys.argv[1:] or JOBS
    BUILD.mkdir(parents=True, exist_ok=True)
    c = panel_proto.constants(BUILD)
    (BUILD / "constants.json").write_text(__import__("json").dumps(c, indent=1), encoding="utf-8")
    print("constants, CSG ...")
    csg()
    fc("csg2part.py", CSG2PART=",".join(PARTS))
    print("bay node ...")
    node_step()
    print("drawings:", " ".join(names))
    groups = [names[k::4] for k in range(4)]
    procs = [subprocess.Popen([freecadcmd(), str(HERE / "notice.py")], env={**os.environ, "NOTICE_BUILD": str(BUILD),
                                                                           "NOTICE": ",".join(g), "REPROJECT": "1"},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for g in groups if g]
    for p in procs:
        p.wait()
    log = (BUILD / "out" / "notice_log.txt").read_text(encoding="utf-8", errors="replace")
    fails = [line for line in log.splitlines() if " FAIL" in line]
    print(f"{len(names) - len(fails)} written to {BUILD / 'out'}" + (f", failed: {fails}" if fails else ""))


if __name__ == "__main__":
    main()
