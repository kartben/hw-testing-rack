"""Photoreal renders of the shelf with Blender + Cycles (run headless).

    blender -b --factory-startup -P render/render.py -- --glb render/assembly.glb --shot hero --out docs/img/hero.jpg

The GLB comes from tools/assembly_glb.py (same scene as the web viewer).
Shots: hero, side, drawer (close-up of one bay), exploded (frames the imported GLB, e.g.
render/bay-exploded.glb), rear.
Coordinates are the rack's (metres, X right, Y back, Z up): the glTF importer
converts the GLB's Y-up back to Blender's Z-up.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=str(REPO / "render" / "assembly.glb"))
    ap.add_argument("--shot", default="hero")
    ap.add_argument("--out", default=None)
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--res", default="1920x1200")
    ap.add_argument("--bay", default="C2")
    return ap.parse_args(argv)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material_tweaks():
    """Make the glTF PBR materials read like the real thing."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        col = bsdf.inputs["Base Color"].default_value
        metallic = bsdf.inputs["Metallic"].default_value
        if metallic < 0.5:
            # printed PETG / plastics: a faint sheen and a touch of subsurface-ish softness
            bsdf.inputs["Roughness"].default_value = max(0.38, bsdf.inputs["Roughness"].default_value)
            if "Coat Weight" in bsdf.inputs:
                bsdf.inputs["Coat Weight"].default_value = 0.08
        else:
            # anodised aluminium / steel: brushed-ish
            bsdf.inputs["Roughness"].default_value = 0.32
            if "Anisotropic" in bsdf.inputs:
                bsdf.inputs["Anisotropic"].default_value = 0.4


def studio(floor_z=0.0):
    world = bpy.data.worlds.new("studio")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    grad = nt.nodes.new("ShaderNodeTexGradient")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.035, 0.04, 0.05, 1)
    ramp.color_ramp.elements[1].color = (0.20, 0.22, 0.26, 1)
    mapping.inputs["Rotation"].default_value = (0, math.radians(-90), 0)
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.35

    def area(name, loc, rot, size, power, color=(1, 1, 1)):
        light = bpy.data.lights.new(name, "AREA")
        light.size = size
        light.energy = power
        light.color = color
        ob = bpy.data.objects.new(name, light)
        ob.location = loc
        ob.rotation_euler = [math.radians(a) for a in rot]
        bpy.context.collection.objects.link(ob)

    area("key", (1.9, -1.6, 2.2), (52, 0, 48), 1.6, 220, (1.0, 0.95, 0.9))
    area("fill", (-1.6, -1.4, 1.1), (70, 0, -52), 2.2, 70, (0.85, 0.92, 1.0))
    area("rim", (0.3, 1.8, 1.9), (-55, 0, 180), 1.2, 160)
    area("top", (0.35, 0.1, 2.4), (0, 0, 0), 1.4, 60)

    bpy.ops.mesh.primitive_plane_add(size=12, location=(0.35, 0.1, floor_z))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    b = fm.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.045, 0.05, 0.06, 1)
    b.inputs["Roughness"].default_value = 0.45
    floor.data.materials.append(fm)


def camera(loc, target, lens=50):
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.dof.use_dof = False
    ob = bpy.data.objects.new("cam", cam)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def bay_center(bay):
    data = json.loads((REPO / "site" / "assets" / "rack.json").read_text(encoding="utf-8"))
    b = next(x for x in data["bays"] if x["id"] == bay)
    return Vector(b["center"]) / 1000.0, data


def main():
    a = args()
    reset()
    bpy.ops.import_scene.gltf(filepath=a.glb)
    material_tweaks()
    studio()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = a.samples
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.3
    w, h = (int(v) for v in a.res.split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = False
    centre = Vector((0.35, 0.11, 0.44))
    if a.shot == "hero":
        camera((1.62, -1.62, 1.18), centre + Vector((0, 0, -0.02)), lens=42)
    elif a.shot == "side":
        camera((2.15, 0.06, 0.62), centre, lens=50)
    elif a.shot == "rear":
        camera((-0.9, 1.9, 1.2), centre, lens=42)
    elif a.shot == "exploded":
        # frame whatever was imported (e.g. one bay from assembly_glb.py --explode-bay)
        pts = [ob.matrix_world @ Vector(c) for ob in sc.objects if ob.type == "MESH" and ob.name != "Plane"
               for c in ob.bound_box]
        lo = Vector([min(q[i] for q in pts) for i in range(3)])
        hi = Vector([max(q[i] for q in pts) for i in range(3)])
        c, size = (lo + hi) / 2, (hi - lo).length
        camera(c + Vector((0.85, -1.15, 0.55)) * size, c + Vector((0, 0, -0.02 * size)), lens=35)
    elif a.shot == "drawer":
        c, _ = bay_center(a.bay)
        camera(c + Vector((0.32, -0.62, 0.36)), c + Vector((0, -0.08, -0.02)), lens=55)
    out = a.out or str(REPO / "docs" / "img" / f"{a.shot}.jpg")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = out
    jpeg = out.lower().endswith((".jpg", ".jpeg"))
    sc.render.image_settings.file_format = "JPEG" if jpeg else "PNG"
    if jpeg:
        sc.render.image_settings.quality = 90
    bpy.ops.render.render(write_still=True)
    print("rendered", out)


main()
