"""Each notice step's assembled state as a STEP, for SolidCraft's interference check (sc_check.py).

    NOTICE_BUILD=<build> CHECK=a3,a8 freecadcmd tools/notice/check.py     (CHECK=all: every step)
    -> <build>/check/<step>.step, <step>.json

A step's state: its old parts and its new ones seated (no approach offsets, hidden ones left out),
fasteners included (without their threads: plain()), each body labelled with its scene id.
Every screw put in during the step (the first step that shows it, the cover and the finished
views aside) also gets a screwdriver: a Ø TOOL_D cylinder TOOL_L long on the screw's axis, from
just above its head outwards, labelled tool_<screw id>; anything it hits is in the screwdriver's
way.  The json lists the bodies, their kinds, and each fastener's axis (for telling a screw in
its hole from a real overlap).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import FreeCAD as App  # noqa: E402
import Import  # noqa: E402
import Part  # noqa: E402
import notice as N  # noqa: E402
N.PIPE_PLAIN = True                    # cables as cylinders and balls: SolidCraft intersects swept splines too slowly
from FreeCAD import Vector as V  # noqa: E402

TOOL_D, TOOL_L = 5.0, 100.0           # a PH1 screwdriver's shaft, bit included
OUT = os.path.join(N.BUILD, "check")


def plain(iid):
    """A fastener without its threads (intersecting helical faces would take minutes per pair):
    a screw's head and its core (0.8 d, a pilot hole's size: a screw in its hole touches nothing),
    an insert's or a washer's outer cylinder."""
    kind, m = N.INST[iid]
    f = N.fastener_z(*N.FAST[kind][:3]).BoundBox
    if N.FAST[kind][3]:                                   # a screw: head above z = 0, shank below
        d = float(N.FAST[kind][1][1:])
        s = Part.makeCylinder(f.XMax, f.ZMax).fuse(Part.makeCylinder(0.4 * d, N.FAST[kind][3], V(0, 0, -N.FAST[kind][3])))
    else:
        s = Part.makeCylinder(f.XMax, f.ZLength, V(0, 0, f.ZMin))
    s.transformShape(m)
    return s


def export(name, driven):
    """driven: the screws earlier steps put in (this one adds its own)."""
    step = N.STEPS[name]
    old, add = N.expand(step)
    ids = list(old) + [i for i in add if i not in old]
    doc = App.newDocument("check_" + name)
    objs, info = [], {"step": name, "bodies": {}, "fasteners": {}, "tools": {}}

    def put(label, shape):
        o = doc.addObject("Part::Feature", label)
        o.Label = label
        o.Shape = shape
        objs.append(o)

    for iid in ids:
        kind = N.INST[iid][0]
        if kind == "screwdriver":                            # the drawings' prop, not a part
            continue
        put(iid, plain(iid) if kind in N.FAST else N.shape_of(iid))
        info["bodies"][iid] = kind
        if kind in N.FAST:
            seat, ax = N.seat_point(iid), N.seat_axis(iid)
            bb = N.fastener_z(*N.FAST[kind][:3]).BoundBox
            head = bb.ZMax
            info["fasteners"][iid] = {"kind": kind, "seat": list(seat), "axis": list(ax),
                                      "depth": max(N.FAST[kind][3], -bb.ZMin), "head": head}
            if (N.FAST[kind][3] and iid in add and iid not in driven and step.get("slot") not in ("cover", "done")
                    and not step.get("fitted")):             # a tray fitted at the bench: driven there
                t = Part.makeCylinder(TOOL_D / 2, TOOL_L, seat + ax * (head + 0.3), ax)
                put("tool_" + iid, t)                        # a screw driven in this step
                info["tools"]["tool_" + iid] = iid
                driven.add(iid)
    doc.recompute()
    os.makedirs(OUT, exist_ok=True)
    Import.export(objs, os.path.join(OUT, name + ".step"))
    json.dump(info, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    App.closeDocument(doc.Name)
    N.log("check", name, len(ids), "bodies", len(info["tools"]), "tools")


names = os.environ.get("CHECK", "all")
want = list(N.STEPS) if names == "all" else names.split(",")
driven = set()
for n in N.STEPS:                       # in notice order, for the screws' first steps
    if n not in want:
        old, add = N.expand(N.STEPS[n])
        if N.STEPS[n].get("slot") not in ("cover", "done"):
            driven |= {i for i in add if N.INST[i][0] in N.FAST and N.FAST[N.INST[i][0]][3]}
        continue
    try:
        export(n, driven)
    except Exception:
        import traceback
        N.log("check", n, "FAIL", traceback.format_exc())
