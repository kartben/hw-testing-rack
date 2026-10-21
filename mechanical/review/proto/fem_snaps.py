"""docs/printed-parts-review.md: FEM of the snap features as drawn (and as proposed): each beam rebuilt as a solid from the SCAD numbers,
root fixed, the barb's face pushed by the deflection the joint needs; CalculiX linear static, PETG E 1800
MPa, nu 0.38.  Reports max von Mises, max principal stress and the strain (sigma_1 / E) at the root.
Run: freecadcmd fem_snaps.py   -> fem_snaps.json"""
import os, json, math
import FreeCAD as App
import Part
import ObjectsFem
from femmesh.gmshtools import GmshTools
from femtools import ccxtools

HERE = os.path.dirname(os.path.abspath(__file__))
E = 1800.0


def ladder_hook(root=7.0, drop=9.0, w=2.6, barb=1.0, t=7.4, fillet=0.0):
    """The hook's 2D profile (ladder.scad hook_local + the beam root inside the band), extruded t.
    x = along the beam (0 at the band's root, +x down the hook), y = flex direction."""
    pts = [(0, -w / 2), (root + drop, -w / 2), (root + drop, w / 2),              # beam, far side then tip
           (root + drop - 2.5, w / 2 + barb), (root + 4.3, w / 2 + barb), (root + 4.3, w / 2), (0, w / 2)]
    wire = Part.makePolygon([App.Vector(x, y, 0) for x, y in pts] + [App.Vector(pts[0][0], pts[0][1], 0)])
    face = Part.Face(wire)
    solid = face.extrude(App.Vector(0, 0, t))
    # a block the beam grows from (the band): 6 mm behind the root, full width + 6
    block = Part.makeBox(6, w + 6, t, App.Vector(-6, -w / 2 - 3, 0))
    s = solid.fuse(block).removeSplitter()
    return s, {"fixed": lambda f: abs(f.CenterOfMass.x + 6) < 1e-3,                 # the block's back face
               "push": lambda f: abs(f.CenterOfMass.y - (w / 2 + barb)) < 1e-3 and f.CenterOfMass.x > root + 4}, "y"


def tray_arm(L=26.0, h=4.3, b=5.0, barb=1.2):
    s = Part.makeBox(L + 4, h, b)                      # 4 mm of wall behind the root
    bb = Part.makeBox(1.5, barb, b, App.Vector(L + 4 - 4, h, 0))   # the barb's catch block at the free end
    s = s.fuse(bb).removeSplitter()
    return s, {"fixed": lambda f: abs(f.CenterOfMass.x) < 1e-3,
               "push": lambda f: abs(f.CenterOfMass.y - (h + barb)) < 1e-3}, "y"


def cradle_finger(L=24.0, t=2.4, w=5.4, hook=1.0, gap=0.15):
    s = Part.makeBox(t, w, L + 5)                      # z up: the finger standing on 5 mm of wall
    hk = Part.makeBox(hook + gap, w, 1.6, App.Vector(-hook - gap, 0, L + 5 - 1.6))
    s = s.fuse(hk).removeSplitter()
    return s, {"fixed": lambda f: abs(f.CenterOfMass.z) < 1e-3,
               "push": lambda f: abs(f.CenterOfMass.x + hook + gap) < 1e-3}, "x"


def cam_pin(split=4.5, d=3.4, slot=0.8, head=3.9, headh=0.8, base=3.0):
    """One half of the split pivot: a half-cylinder (d, minus half the slot) standing on a base block."""
    cyl = Part.makeCylinder(d / 2, split + headh + base)
    cut = Part.makeBox(d, d, split + headh + base + 1, App.Vector(-d / 2, -d, -0.5))   # keep y > 0 half
    half = cyl.cut(cut)
    sl = Part.makeBox(d, slot / 2, split + headh + 1, App.Vector(-d / 2, 0, base))        # the slot's half
    half = half.cut(sl)
    hd = Part.makeCylinder(head / 2, headh, App.Vector(0, 0, base + split))
    hd = hd.cut(Part.makeBox(d, d, headh + 1, App.Vector(-d / 2, -d, base + split - 0.5))).cut(
        Part.makeBox(d, slot / 2, headh + 1, App.Vector(-d / 2, 0, base + split - 0.5)))
    s = half.fuse(hd).removeSplitter()
    y = (head - d) / 2
    return s, {"fixed": lambda f: abs(f.CenterOfMass.z) < 1e-3,
               "push": lambda f: f.CenterOfMass.z > base + split - 1e-3 and f.Surface.__class__.__name__ == "Cylinder"
               and abs(f.Surface.Radius - head / 2) < 1e-3}, ("y", -y)


def sleeve_wall(L=12.0, t=1.6, w=16.0, lip=0.8):
    s = Part.makeBox(t, w, L + 3)
    lp = Part.makeBox(lip, w, 1.2, App.Vector(-lip, 0, L + 3 - 1.2))
    s = s.fuse(lp).removeSplitter()
    return s, {"fixed": lambda f: abs(f.CenterOfMass.z) < 1e-3,
               "push": lambda f: abs(f.CenterOfMass.x + lip) < 1e-3}, "x"


CASES = {
    "ladder_hook_as_drawn": (ladder_hook, {}, 0.8),
    "ladder_hook_root10": (ladder_hook, {"root": 10.0}, 0.8),
    "tray_arm_as_drawn": (tray_arm, {}, 1.2),
    "cradle_finger_as_drawn": (cradle_finger, {}, 1.15),
    "cradle_finger_L34_hook08": (cradle_finger, {"L": 34.0, "hook": 0.8}, 0.95),
    "cam_pin_as_drawn": (cam_pin, {}, 0.25),
    "cam_pin_split65_head37": (cam_pin, {"split": 6.5, "head": 3.7}, 0.15),
    "sleeve_wall_as_drawn": (sleeve_wall, {}, 0.8),
    "sleeve_wall_lip05": (sleeve_wall, {"lip": 0.5}, 0.5),
    # as built (2026-10-21)
    "built_ladder_hook_root10": (ladder_hook, {"root": 10.0}, 0.8),
    "built_tray_arm_32": (tray_arm, {"L": 32.0}, 1.2),
    "built_cradle_finger_L40_hook08": (cradle_finger, {"L": 40.0, "w": 5.0, "hook": 0.8}, 0.95),
    "built_cam_pin_split65_head39": (cam_pin, {"split": 6.5, "head": 3.9}, 0.15),
    "sleeve_tab_through_plate_16": (tray_arm, {"L": 16.0, "h": 1.6, "b": 15.0, "barb": 0.8}, 0.8),   # proposed, not built
}
ONLY = [c for c in os.environ.get("CASES", "").split(",") if c]     # run these only, merged into fem_snaps.json


def run(name, builder, kw, y):
    doc = App.newDocument(name)
    shape, picks, axis = builder(**kw)
    sign = 1.0
    if isinstance(axis, tuple):
        axis, sign = axis[0], -1.0 if axis[1] < 0 else 1.0
    part = doc.addObject("Part::Feature", "Part")
    part.Shape = shape
    fixed = [f"Face{i}" for i, f in enumerate(shape.Faces, 1) if picks["fixed"](f)]
    push = [f"Face{i}" for i, f in enumerate(shape.Faces, 1) if picks["push"](f)]
    assert fixed and push, (name, fixed, push)
    analysis = ObjectsFem.makeAnalysis(doc, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiX")
    solver.AnalysisType = "static"
    analysis.addObject(solver)
    mat = ObjectsFem.makeMaterialSolid(doc, "PETG")
    m = mat.Material
    m.update({"Name": "PETG printed", "YoungsModulus": f"{E} MPa", "PoissonRatio": "0.38", "Density": "1270 kg/m^3"})
    mat.Material = m
    analysis.addObject(mat)
    fx = ObjectsFem.makeConstraintFixed(doc, "Fixed")
    fx.References = [(part, f) for f in fixed]
    analysis.addObject(fx)
    dp = ObjectsFem.makeConstraintDisplacement(doc, "Push")
    dp.References = [(part, f) for f in push]
    # push the barb inwards: against the direction it protrudes
    setattr(dp, axis + "Free", False)
    setattr(dp, axis + "Displacement", -y * sign)
    analysis.addObject(dp)
    mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
    mesh.Shape = part
    bb = shape.BoundBox
    mesh.CharacteristicLengthMax = max(0.25, min(bb.XLength, bb.YLength, bb.ZLength) / 6)
    mesh.ElementOrder = "2nd"
    analysis.addObject(mesh)
    doc.recompute()
    GmshTools(mesh).create_mesh()
    fea = ccxtools.FemToolsCcx(analysis, solver)
    fea.purge_results()
    fea.update_objects()
    fea.setup_working_dir(os.path.join(HERE, "ccx", name))
    fea.write_inp_file()
    fea.ccx_run()
    fea.load_results()
    res = [o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject")][0]
    vm, p1 = max(res.vonMises), max(res.PrincipalMax)
    # reaction: sum of nodal forces not exported; estimate the force from the hand formula instead
    out = {"nodes": mesh.FemMesh.NodeCount, "deflection_mm": y, "vm_max_MPa": round(vm, 1), "p1_max_MPa": round(p1, 1),
           "strain_pct": round(p1 / E * 100, 2), "disp_max_mm": round(max(res.DisplacementLengths), 3)}
    print(name, json.dumps(out))
    doc.saveAs(os.path.join(HERE, "ccx", name + ".FCStd"))
    return out


OUT = os.path.join(HERE, "..", "fem_snaps.json")
results = json.load(open(OUT)) if ONLY and os.path.exists(OUT) else {}
for name, (b, kw, y) in CASES.items():
    if ONLY and name not in ONLY:
        continue
    try:
        results[name] = run(name, b, kw, y)
    except Exception as ex:
        import traceback
        results[name] = {"error": traceback.format_exc()[-600:]}
        print(name, "FAILED", ex)
json.dump(results, open(OUT, "w"), indent=1)
