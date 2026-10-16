"""Render one shot of the hw-testing-rack scene in a RUNNING Blender (see live_scene.py).

    python tools/blender_live.py exec render/live_render.py <shot> [out.jpg] [samples] [WxH]

Shots: hero, side, drawer:<bay>, exploded (frames the whole scene), front, rear, top.  Relative paths are
from the repository root; the default output is docs/img/<shot>.jpg (.png works too).
"""

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(HW_REPO)  # noqa: F821 — injected by tools/blender_live.py
SHOT = sys.argv[1] if len(sys.argv) > 1 else "hero"
OUT = str(REPO / (sys.argv[2] if len(sys.argv) > 2 else f"docs/img/{SHOT.replace(':', '-')}.jpg"))
SAMPLES = int(sys.argv[3]) if len(sys.argv) > 3 else 192
RES = sys.argv[4] if len(sys.argv) > 4 else "1920x1200"

sc = bpy.data.scenes["hw-testing-rack"]
bpy.context.window_manager.windows[0].scene = sc
for ob in sc.objects:
    ob.select_set(False)
cam = sc.camera
centre = Vector((0.35, 0.11, 0.44))


def aim(loc, target, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens


def bay_center(bay):
    data = json.loads((REPO / "site" / "assets" / "rack.json").read_text(encoding="utf-8"))
    b = next(x for x in data["bays"] if x["id"] == bay)
    return Vector(b["center"]) / 1000.0


name = SHOT.split(":")[0]
if name == "hero":
    aim((1.45, -1.55, 1.02), centre + Vector((0.0, 0.0, -0.03)), 40)
elif name == "side":
    aim((2.0, -0.95, 0.5), centre + Vector((0.0, 0.0, -0.02)), 42)
elif name == "front":
    aim((0.35, -2.35, 0.62), centre, 45)
elif name == "rear":
    aim((-0.85, 1.85, 1.15), centre, 40)
elif name == "top":
    aim((1.2, -1.0, 2.1), centre, 38)
elif name == "drawer":
    c = bay_center(SHOT.split(":")[1] if ":" in SHOT else "C2")
    aim(c + Vector((0.30, -0.55, 0.30)), c + Vector((0.0, -0.10, -0.03)), 50)
elif name == "exploded":
    # frame whatever the scene holds (e.g. one bay from assembly_glb.py --explode-bay)
    pts = [ob.matrix_world @ Vector(c) for ob in bpy.data.collections["rack"].all_objects
           if ob.type == "MESH" for c in ob.bound_box]
    lo = Vector([min(q[i] for q in pts) for i in range(3)])
    hi = Vector([max(q[i] for q in pts) for i in range(3)])
    c, size = (lo + hi) / 2, (hi - lo).length
    aim(c + Vector((0.85, -1.15, 0.55)) * size, c + Vector((0, 0, -0.02 * size)), 35)

w, h = (int(v) for v in RES.split("x"))
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.cycles.samples = SAMPLES
sc.render.filepath = OUT
jpeg = OUT.lower().endswith((".jpg", ".jpeg"))
sc.render.image_settings.file_format = "JPEG" if jpeg else "PNG"
if jpeg:
    sc.render.image_settings.quality = 90
Path(OUT).parent.mkdir(parents=True, exist_ok=True)
with bpy.context.temp_override(window=bpy.context.window_manager.windows[0], scene=sc):
    bpy.ops.render.render(write_still=True, scene=sc.name)
result = {"shot": SHOT, "out": OUT, "device": sc.cycles.device, "samples": SAMPLES}
