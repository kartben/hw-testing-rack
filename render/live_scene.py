"""Build (or rebuild) the hw-testing-rack scene inside a RUNNING Blender.

Sent through the Blender MCP add-on socket by tools/blender_live.py:

    python tools/blender_live.py exec render/live_scene.py [glb] [scene-name]

Creates its own scene (default "hw-testing-rack") with its own world, so the
user's other scenes are never touched; re-running replaces only that scene's
content.  Then: tools/blender_live.py exec render/live_render.py <shot> [out.png].
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(HW_REPO)  # noqa: F821 — injected by tools/blender_live.py
GLB = REPO / (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else "render/assembly.glb")
SCENE = sys.argv[2] if len(sys.argv) > 2 else "hw-testing-rack"

# --- a dedicated scene ---------------------------------------------------------
sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
win = bpy.context.window_manager.windows[0]
win.scene = sc
for ob in list(sc.collection.all_objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in list(sc.collection.children):
    bpy.data.collections.remove(coll)

rack = bpy.data.collections.new("rack")
sc.collection.children.link(rack)
studio = bpy.data.collections.new("studio")
sc.collection.children.link(studio)

# --- import the assembly into the rack collection -------------------------------
layer_coll = bpy.context.view_layer.layer_collection.children[rack.name]
bpy.context.view_layer.active_layer_collection = layer_coll
with bpy.context.temp_override(window=win, scene=sc):
    bpy.ops.import_scene.gltf(filepath=str(GLB))

# --- materials: make the glTF PBR read like printed PETG / anodised aluminium ---
for ob in rack.all_objects:
    for slot in getattr(ob, "material_slots", []):
        m = slot.material
        if not m or not m.use_nodes or m.get("hw_tweaked"):
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        if bsdf.inputs["Metallic"].default_value < 0.5:
            bsdf.inputs["Roughness"].default_value = max(0.38, bsdf.inputs["Roughness"].default_value)
            if "Coat Weight" in bsdf.inputs:
                bsdf.inputs["Coat Weight"].default_value = 0.08
        else:
            bsdf.inputs["Roughness"].default_value = 0.32
            if "Anisotropic" in bsdf.inputs:
                bsdf.inputs["Anisotropic"].default_value = 0.4
        if ob.name.startswith("led"):
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 6.0
        if ob.name.startswith("screen"):          # a lit display behind glass (tools/assembly_glb.py › screen_quad)
            bsdf.inputs["Roughness"].default_value = 0.1
            bsdf.inputs["Emission Strength"].default_value = 0.9
        m["hw_tweaked"] = True

# --- studio: world gradient, area lights, floor -----------------------------------
world = bpy.data.worlds.get("hw-studio") or bpy.data.worlds.new("hw-studio")
sc.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
bg = nt.nodes.new("ShaderNodeBackground")
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
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
bg.inputs["Strength"].default_value = 0.35


def area(name, loc, rot, size, power, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, "AREA")
    light.size, light.energy, light.color = size, power, color
    ob = bpy.data.objects.new(name, light)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    studio.objects.link(ob)


area("key", (1.9, -1.6, 2.2), (52, 0, 48), 1.6, 220, (1.0, 0.95, 0.9))
area("fill", (-1.6, -1.4, 1.1), (70, 0, -52), 2.2, 70, (0.85, 0.92, 1.0))
area("rim", (0.3, 1.8, 1.9), (-55, 0, 180), 1.2, 160)
area("top", (0.35, 0.1, 2.4), (0, 0, 0), 1.4, 60)

mesh = bpy.data.meshes.new("floor")
mesh.from_pydata([(-6, -6, 0), (6, -6, 0), (6, 6, 0), (-6, 6, 0)], [], [(0, 1, 2, 3)])
floor = bpy.data.objects.new("floor", mesh)
fm = bpy.data.materials.get("hw-floor") or bpy.data.materials.new("hw-floor")
fm.use_nodes = True
b = fm.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.045, 0.05, 0.06, 1)
b.inputs["Roughness"].default_value = 0.45
mesh.materials.append(fm)
floor.location = (0.35, 0.1, 0)
studio.objects.link(floor)

cam_data = bpy.data.cameras.new("hw-cam")
cam = bpy.data.objects.new("hw-cam", cam_data)
studio.objects.link(cam)
sc.camera = cam
cam.location = (1.62, -1.62, 1.18)
cam.rotation_euler = (Vector((0.35, 0.11, 0.42)) - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_data.lens = 42

# --- render settings: Cycles on the GPU when there is one --------------------------
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
device = "CPU"
for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
    try:
        prefs.compute_device_type = backend
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type != "CPU"]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend       # the GPU alone: a CPU taking tiles slows an OptiX render
            device = backend
            break
    except Exception:
        continue
sc.cycles.device = "GPU" if device != "CPU" else "CPU"
sc.cycles.samples = 128
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = -0.3
sc.render.resolution_x, sc.render.resolution_y = 1920, 1200

# --- show it: camera view, material preview in every 3D viewport -----------------
for area_ in win.screen.areas:
    if area_.type == "VIEW_3D":
        space = area_.spaces.active
        space.shading.type = "MATERIAL"
        space.region_3d.view_perspective = "CAMERA"

result = {"scene": sc.name, "objects": len(rack.all_objects), "device": device,
          "glb": str(GLB)}
