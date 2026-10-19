#!/usr/bin/env python3
"""Line art of the IKEA-style assembly notice, drawn by FreeCAD.

    python tools/notice/run.py                  # every drawing
    python tools/notice/run.py a3 pin hw:m3x8   # some of them (names: notice.py STEPS, thumb:<part>, hw:<fastener>)

1. the panel frame's constants (OpenSCAD probe, tools/panel_proto.py) -> <build>/constants.json;
2. the printed parts of one bay -> OpenSCAD CSG -> exact solids (csg2part.py, in freecadcmd);
3. the bay node: KiCad's STEP export and 3D coverage report, stand-ins for the parts without a
   body (node.py);
4. the drawings: notice.py in four freecadcmd processes -> <build>/out/*.svg, or on another
   machine (below);
5. pages.py plan: the drawings the canvas doesn't have yet.  Then upload, record, build and
   publish the pages: README.md, Publishing.  A full run takes about 40 minutes here.

<build> is mechanical/build/notice.  Needs FreeCAD 1.x with the Fasteners workbench
(FREECADCMD=path/to/freecadcmd if it is not found), OpenSCAD, and kicad-cli (or Docker) for
the bay node (without it, the node is drawn as a bare board).

Step 4 elsewhere: NOTICE_REMOTE is a command that runs its last argument in a shell on a
machine with FreeCAD + Fasteners + shapely at <NOTICE_REMOTE_DIR>/env/bin/freecadcmd
(NOTICE_REMOTE_DIR relative to its home, default claude-scratch/notice; README.md has the
setup), e.g. NOTICE_REMOTE="ssh -o BatchMode=yes box", or through a jump host whose ssh
config names the box, "ssh -o BatchMode=yes jump ssh -o BatchMode=yes box" (the command is
quoted once per ssh after the first).  jobs.py runs the drawings there within the box's
memory.  The solids and constants go there, the drawings come back; nothing else is left there
but jobs.py's record of each drawing's peak memory.
"""

from __future__ import annotations

import glob
import io
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
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
    "power_box_base": ("parts/power_box.scad", {"PART": "base"}),
    "power_box_lid": ("parts/power_box.scad", {}, "lid();"),     # as assembled (it prints top face down)
    "chain_anchor": ("parts/chain_parts.scad", {"PART": "anchor"}),
    "chain_foot": ("parts/chain_parts.scad", {}, "include <{MECH}/lib/carrier.scad>\nfoot();"),   # as assembled
    "chain_link": ("parts/chain_parts.scad", {}, "include <{MECH}/lib/carrier.scad>\nlink();"),   # lying as in the rack
    "chain_bar": ("parts/chain_parts.scad", {"PART": "bar"}),
}
# heaviest first, dealt round-robin to the processes
JOBS = ["done", "b5", "b5a", "c_done", "b3", "b1", "a9", "c5", "b2", "a8", "a11t", "c3", "c4", "b3n", "b4", "cover",
        "a7", "a6", "a5", "a4", "a12s", "a9b", "a10o", "a3", "a2", "a1", "c0", "c1", "c2", "pin", "pin_b", "hook"] \
       + [f"thumb:{p}" for p in ("lb", "la", "lc", "fp", "tr", "dr", "cp", "bb", "nd", "pb", "pl", "hb", "ch",
                                  "an", "ft", "dc", "xt", "dp")] \
       + [f"hw:{h}" for h in ("m3x8", "m3x6", "pt26x8", "w25", "sp12", "mag", "insert", "jumper", "usbc")]


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
    for name, (scad, defines, *call) in PARTS.items():
        cmd = openscad_cmd() + ["-o", str(BUILD / "csg" / f"{name}.csg")]
        for k, v in defines.items():
            cmd += ["-D", f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"]
        src = MECH / scad
        if call:                           # a module of the file, called by a wrapper next to the CSG
            src = BUILD / "csg" / f"_{name}.scad"
            src.write_text(f"use <{(MECH / scad).as_posix()}>\n{call[0].replace('{MECH}', MECH.as_posix())}\n", encoding="utf-8")
        subprocess.run(cmd + [str(src)], cwd=MECH, check=True, capture_output=True)


BOARDS = {"bay-node": "bay_node", "power-hub": "hub", "data-port": "data_port"}   # KiCad board -> its solid in <build>/parts


def node_step(NODE: str = "bay-node") -> None:
    """A board as the viewer has it (tools/pcb_glb.py): KiCad's STEP export, its models resolved
    from KiCad's library and electronics/lib/3dmodels (${KIPRJMOD}); and KiCad's 3D coverage report
    (electronics/tools/build_board.py export_3d_coverage, where it exists), so node.py adds
    stand-ins only for the parts the export has no body for."""
    out = BUILD / "parts" / f"{NODE}.step"
    pcb = REPO / "electronics" / NODE / f"{NODE}.kicad_pcb"
    report = REPO / "electronics" / NODE / "build" / f"{NODE}-3d.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    cli = shutil.which("kicad-cli") or next(iter(sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"))), None)
    export = ["kicad-cli", "pcb", "export", "step", "--subst-models", "-o", "/repo/" + out.relative_to(REPO).as_posix(),
              pcb.relative_to(REPO).as_posix()]
    if shutil.which("docker"):            # the -full image has the KiCad library's 3D models
        coverage = ("export_3d_coverage" in (REPO / "electronics" / "tools" / "build_board.py").read_text(encoding="utf-8"))
        script = " ".join(export)
        if coverage:
            script += (" && python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, \"electronics/tools\"); "
                       f"import build_board; build_board.export_3d_coverage(Path(\"/repo/electronics/{NODE}\"), \"{NODE}\")'")
        cmd = ["docker", "run", "--rm", "-e", "HOME=/tmp", "-e", "KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels",
               "-v", f"{REPO}:/repo", "-w", "/repo", "kicad/kicad:10.0-full", "sh", "-c", script]
    elif cli:
        cmd = [cli] + export[1:-2] + [str(out), str(pcb)]
    else:
        print("no kicad-cli: the bay node is drawn as a bare board")
        return
    p = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if not out.exists():
        print("STEP export failed: the bay node is drawn as a bare board\n" + p.stderr[-800:])
        return
    fc("node.py", NODE_BUILD="1", NODE_PCB=str(pcb), NODE_COVERAGE=str(report) if report.exists() else "",
       NODE_STEP=str(out), NODE_OUT=BOARDS[NODE])
    print((BUILD / "parts" / f"{BOARDS[NODE]}_log.txt").read_text(encoding="utf-8").strip())


def on_remote(cmd: str) -> list[str]:
    """NOTICE_REMOTE running the shell command `cmd` there: quoted again for each ssh hop after the first."""
    rem = shlex.split(os.environ["NOTICE_REMOTE"])
    for _ in range(sum(w == "ssh" for w in rem) - 1):
        cmd = shlex.quote(cmd)
    return rem + [cmd]


def remote_drawings(names: list[str]) -> None:
    """Step 4 on NOTICE_REMOTE: notice.py, jobs.py, constants.json and the solids there (a fresh
    run/), the drawings run by jobs.py, out/ back here, run/ removed."""
    d = os.environ.get("NOTICE_REMOTE_DIR", "claude-scratch/notice")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(HERE / "notice.py", "notice.py")
        t.add(HERE / "jobs.py", "jobs.py")
        t.add(BUILD / "constants.json", "build/constants.json")
        for f in sorted((BUILD / "parts").glob("*")):
            if f.suffix in (".brep", ".json"):
                t.add(f, f"build/parts/{f.name}")
    subprocess.run(on_remote(f"rm -rf {d}/run && mkdir -p {d}/run/build/out && tar -xzf - -C {d}/run"),
                   input=buf.getvalue(), check=True)
    subprocess.run(on_remote(f"cd {d}/run && NOTICE_BUILD=$PWD/build REPROJECT=1 ../env/bin/python jobs.py ../env/bin/freecadcmd "
                             + ",".join(names)), check=True)
    back = subprocess.run(on_remote(f"COPYFILE_DISABLE=1 tar -czf - -C {d}/run/build out && rm -rf {d}/run"), capture_output=True, check=True)
    with tarfile.open(fileobj=io.BytesIO(back.stdout), mode="r:gz") as t:
        t.extractall(BUILD, filter="data")


def outputs(name: str) -> list[str]:
    """The drawings a job writes (out/<name>.svg)."""
    kind, _, k = name.rpartition(":")
    return {"thumb": [f"card_{k}", f"chip_{k}"], "hw": [f"hw_{k}"]}.get(kind, [name])


def mtime(name: str) -> int | None:
    f = BUILD / "out" / f"{name}.svg"
    return f.stat().st_mtime_ns if f.exists() else None


def main() -> None:
    import json
    import time
    import yaml
    t0 = time.time()
    names = sys.argv[1:] or JOBS
    BUILD.mkdir(parents=True, exist_ok=True)
    c = panel_proto.constants(BUILD)
    c["ROW_CABLE"] = yaml.safe_load((HERE / "notice.yaml").read_text(encoding="utf-8"))["row_cable"]
    import rackcfg
    rack = rackcfg.load()                  # the power box's placement (frame) and the hub's
    c["POWER_BOX"] = {**rack.power_box(), "hub_pcb": rack.raw["pcb"]["power_hub"]}
    d, node = rack.drawer, rack.node                 # the drag chain, the DATA socket, the node's DUT port
    c["CHAIN"] = {**rack.chain, "bottom": rack.carrier["bottom"]}
    dp = rack.raw["pcb"]["data_port"]               # the DATA port board on the rear-bay floor (lib/carrier.scad DATA_PCB_*)
    c["DATA"] = {"x": rack.data_port_x[0], "wall_y": d["depth"] - d["rear_bay"], "z": d["bottom"] + 8.5,   # PORT_Z
                 "wall": d["wall"], "pcb": dp, "pcb_z": d["bottom"] + 8.5 - 1.63 - dp["thickness"]}
    c["NODE_DUT"] = [node["size"][0] + 0.4, node["size"][1] - node["right"]["dut"], node["thickness"] + 1.6]
    c["NODE_HOLES"] = node["holes"]                 # M3, KiCad coordinates (y from the rear edge)
    import webscene                                  # the USB plugs' sizes, as the viewer draws them
    c["USB_PLUGS"] = getattr(webscene, "USB_PLUGS", None)
    (BUILD / "constants.json").write_text(json.dumps(c, indent=1), encoding="utf-8")
    print("constants, CSG ...")
    csg()
    fc("csg2part.py", CSG2PART=",".join(PARTS))
    for b in BOARDS:
        print(b, "...")
        node_step(b)
    print("drawings:", " ".join(names))
    (BUILD / "out" / "notice_log.txt").unlink(missing_ok=True)     # this run's failures only
    before = {o: mtime(o) for n in names for o in outputs(n)}
    if os.environ.get("NOTICE_REMOTE"):
        remote_drawings(names)
    else:
        groups = [names[k::4] for k in range(4)]
        procs = [subprocess.Popen([freecadcmd(), str(HERE / "notice.py")], env={**os.environ, "NOTICE_BUILD": str(BUILD),
                                                                               "NOTICE": ",".join(g), "REPROJECT": "1"},
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for g in groups if g]
        for p in procs:
            p.wait()
    fails = [n for n in names if any(mtime(o) in (None, before[o]) for o in outputs(n))]   # failed, or killed
    print(f"{len(names) - len(fails)} written to {BUILD / 'out'}"
          + (f", NOT written: {' '.join(fails)} (out/notice_log.txt)" if fails else ""))
    import pages
    pages.plan()
    print(f"{time.time() - t0:.0f} s.  Next: upload the drawings above to the canvas, pages.py record, "
          "pages.py build, publish the pages (tools/notice/README.md, Publishing)")


if __name__ == "__main__":
    main()
