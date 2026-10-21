"""Printability of every part (docs/printed-parts-review.md).  Inputs: <scratch>/parts/<part>.brep from
tools/notice/csg2part.py (CSG2PART=... NOTICE_BUILD=<scratch> freecadcmd csg2part.py, after `openscad -o <scratch>/csg/<part>.csg`).
Printability of every part from its exact solid, in its print orientation (the CSG is exported as
printed): downward-facing faces steeper than 45 deg from the bed (normal.z < -cos 45), not on the bed
(z > 0.25), are overhangs that need support; horizontal ones among them are bridges (if spanning) or
shelves.  Writes the STEPs for SolidCraft too.  Run: freecadcmd overhang.py"""
import os, json, math
import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.join(HERE, "..", "..", "build", "review", "step")     # git-ignored; SolidCraft opens these
os.makedirs(STEP, exist_ok=True)
names = sorted(f[:-5] for f in os.listdir(os.path.join(HERE, "parts")) if f.endswith(".brep"))
report = {}
COS45 = math.cos(math.radians(45))
for n in names:
    s = Part.Shape()
    s.read(os.path.join(HERE, "parts", n + ".brep"))
    s.exportStep(os.path.join(STEP, n + ".step"))
    bb = s.BoundBox
    zmin = bb.ZMin
    over, flat, total = [], 0.0, 0.0
    for i, f in enumerate(s.Faces):
        a = f.Area
        if a < 0.05:
            continue
        total += a
        # average normal: sample the face's parameter centre
        try:
            u0, u1, v0, v1 = f.ParameterRange
            nrm = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        except Exception:
            continue
        if False:
            nrm = -nrm
        c = f.CenterOfMass
        if c.z - zmin < 0.25:
            continue                      # on the bed
        if nrm.z < -COS45 - 1e-3:
            ang = math.degrees(math.acos(-nrm.z))   # 0 = facing straight down
            over.append({"face": i, "area": round(a, 1), "down_deg": round(ang, 0), "center": [round(c.x, 1), round(c.y, 1), round(c.z, 1)],
                         "flat": abs(nrm.z + 1) < 1e-3})
    over.sort(key=lambda d: -d["area"])
    report[n] = {"faces": len(s.Faces), "volume_cm3": round(s.Volume / 1000, 1), "bbox": [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)],
                 "overhang_area_mm2": round(sum(d["area"] for d in over), 1), "overhang_faces": len(over), "worst": over[:8]}
    print(n, "vol", round(s.Volume / 1000, 1), "cm3", "overhang", round(sum(d["area"] for d in over), 1), "mm2 in", len(over), "faces")
json.dump(report, open(os.path.join(HERE, "overhang.json"), "w"), indent=1)
