"""Photoreal "on a desk" shots of the rack, in a RUNNING Blender (see tools/blender_live.py).

    python tools/blender_live.py exec render/live_photo.py build [glb]
    python tools/blender_live.py exec render/live_photo.py shot <desk|drawer|detail> [out.jpg] [samples] [WxH]

(Renders at full size take ~1 min: use blender_live.py rather than an MCP call with a short timeout.)

Builds its own scene ("hw-testing-rack-photo"), so the neutral technical scene
from live_scene.py stays as it is.  Materials are replaced by object category:
black anodised, brushed aluminium for the 2020 frame; PETG with 0.2 mm layer
lines (along each part's print Z) for the printed parts; lacquered solder mask
on the PCBs.  The set is an oak desk against a plaster wall, a laptop wired to
bay C4's front port and a mug, lit by low window sun and a soft window fill.
The GLB comes from `tools/assembly_glb.py --with-pc-cable --out render/assembly-photo.glb`.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

REPO = Path(HW_REPO)  # noqa: F821 — injected by tools/blender_live.py
MODE = sys.argv[1] if len(sys.argv) > 1 else "build"
SCENE = "hw-testing-rack-photo"
LAYER_MM = 0.2

# printed parts; their layers stack along the part's thinnest local axis (plates, decks,
# panels and brackets print flat, drawers and carriers floor-down)
PRINTED = {"carrier", "deck", "guides", "drawers", "chainparts", "plates", "cameras", "base", "basepanels",
           "roof", "feet", "labels"}


def layer_axis(ob):
    ext = [max(c[i] for c in ob.bound_box) - min(c[i] for c in ob.bound_box) for i in range(3)]
    return "XYZ"[ext.index(min(ext))]


# ---------------------------------------------------------------------------- materials
def _principled(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, b


def petg(color, axis):
    """PETG: satin, faint variation, layer lines along `axis` of the object (mm)."""
    key = f"photo-petg-{axis}-" + "".join(f"{int(c * 255):02x}" for c in color[:3])
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    m, nt, b = _principled(key)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 2 * math.pi / LAYER_MM
    nt.links.new(sep.outputs[axis], mul.inputs[0])
    sine = nt.nodes.new("ShaderNodeMath"); sine.operation = "SINE"
    nt.links.new(mul.outputs[0], sine.inputs[0])
    # rounded ridges, not a pure sine: |sin|
    ab = nt.nodes.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
    nt.links.new(sine.outputs[0], ab.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.00004
    nt.links.new(ab.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    # slight colour / gloss variation, like a real spool
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.02
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.08
    mix.inputs["A"].default_value = (*color[:3], 1)
    nt.links.new(noise.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.38
    b.inputs["Specular IOR Level"].default_value = 0.5
    b.inputs["Coat Weight"].default_value = 0.06
    b.inputs["Coat Roughness"].default_value = 0.3
    return m


def alu_black():
    name = "photo-alu-black-anodised"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, nt, b = _principled(name)
    b.inputs["Base Color"].default_value = (0.03, 0.03, 0.034, 1)
    b.inputs["Metallic"].default_value = 1.0
    # brushed: noise stretched along the extrusion axis (object -Y, mm) drives roughness + micro bump
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (6.0, 0.03, 6.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 4.0
    noise.inputs["Detail"].default_value = 8.0
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.26
    rr.inputs["To Max"].default_value = 0.40
    nt.links.new(noise.outputs["Fac"], rr.inputs["Value"])
    nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Anisotropic"].default_value = 0.5
    return m


def simple(name, color, rough=0.5, metal=0.0, coat=0.0, emission=0.0):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, nt, b = _principled(name)
    b.inputs["Base Color"].default_value = (*color[:3], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emission:
        b.inputs["Emission Color"].default_value = (*color[:3], 1)
        b.inputs["Emission Strength"].default_value = emission
    return m


def base_color(mat):
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if mat and mat.use_nodes else None
    return tuple(bsdf.inputs["Base Color"].default_value) if bsdf else (0.5, 0.5, 0.5, 1)


def dress(rack):
    for ob in rack.all_objects:
        if ob.type != "MESH":
            continue
        cat, part = (ob.name.split(":") + [""])[:2]
        part = part.split("#")[0]
        for slot in ob.material_slots:
            src = slot.material
            col = base_color(src)
            if cat == "frame" and part == "extrusion":
                slot.material = alu_black()
            elif cat in PRINTED or (cat == "frame" and "bracket" in part):
                slot.material = petg(col, layer_axis(ob))
            elif cat == "psu":
                slot.material = simple("photo-alu-natural", (0.62, 0.63, 0.65), rough=0.35, metal=1.0)
            elif cat == "chain":
                slot.material = simple("photo-pa-black", (0.012, 0.012, 0.013), rough=0.55)
            elif cat == "cable":
                slot.material = simple(f"photo-cable-{src.name}", col, rough=0.5, coat=0.15)
            elif cat == "led":
                slot.material = simple(f"photo-led-{src.name}", col, rough=0.3, emission=12.0)
            elif cat in ("pcb", "boards", "xiao") and src and src.use_nodes:
                bsdf = next((n for n in src.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf and not src.get("photo"):
                    if bsdf.inputs["Metallic"].default_value < 0.5:
                        bsdf.inputs["Roughness"].default_value = 0.32
                        bsdf.inputs["Coat Weight"].default_value = 0.35      # solder-mask lacquer
                        bsdf.inputs["Coat Roughness"].default_value = 0.15
                    else:
                        bsdf.inputs["Roughness"].default_value = 0.25
                    src["photo"] = True


# ---------------------------------------------------------------------------- the set
def box(name, size, loc, mat, coll, bevel=0.0, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location, ob.rotation_euler = loc, rot
    me.materials.append(mat)
    coll.objects.link(ob)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = bevel, 3
    for p in me.polygons:
        p.use_smooth = False
    return ob


def oak():
    name = "photo-oak"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, nt, b = _principled(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.5, 5.0, 1.0)            # grain runs along X
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"; wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 5.0
    wave.inputs["Distortion"].default_value = 14.0
    wave.inputs["Detail"].default_value = 6.0
    wave.inputs["Detail Scale"].default_value = 2.0
    wave.inputs["Detail Roughness"].default_value = 0.6
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.34, 0.20, 0.10, 1)
    ramp.color_ramp.elements[1].color = (0.47, 0.30, 0.16, 1)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[1].position = 0.85
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.42
    b.inputs["Coat Weight"].default_value = 0.4                   # oiled / lacquered top
    b.inputs["Coat Roughness"].default_value = 0.22
    return m


def plaster():
    name = "photo-plaster"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, nt, b = _principled(name)
    b.inputs["Base Color"].default_value = (0.74, 0.72, 0.68, 1)
    b.inputs["Roughness"].default_value = 0.92
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 60.0
    noise.inputs["Detail"].default_value = 10.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.06
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def disc(name, radius, loc, mat, coll):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=48)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    me.materials.append(mat)
    coll.objects.link(ob)
    return ob


def mug(coll, at=(-0.36, -0.30)):
    ceramic = simple("photo-ceramic", (0.86, 0.85, 0.82), rough=0.18, coat=0.6)
    me = bpy.data.meshes.new("mug")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=0.041, radius2=0.043, depth=0.095)
    top = max(bm.faces, key=lambda f: f.calc_center_median().z)
    bmesh.ops.delete(bm, geom=[top], context="FACES_ONLY")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("mug", me)
    ob.location = (at[0], at[1], 0.0475)
    me.materials.append(ceramic)
    coll.objects.link(ob)
    ob.modifiers.new("wall", "SOLIDIFY").thickness = 0.004
    ob.modifiers.new("smooth", "SUBSURF").levels = 1
    me = bpy.data.meshes.new("mug-handle")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, radius=0.026, segments=32)
    bm.to_mesh(me)
    bm.free()
    h = bpy.data.objects.new("mug-handle", me)       # a ring, thickened by a skin modifier
    h.location = (at[0] + 0.05, at[1], 0.05)
    h.rotation_euler = (math.radians(90), 0, 0)
    coll.objects.link(h)
    h.modifiers.new("skin", "SKIN")
    for v in h.data.skin_vertices[0].data:
        v.radius = (0.006, 0.006)
    h.modifiers.new("smooth", "SUBSURF").levels = 2
    h.data.materials.append(ceramic)
    disc("coffee", 0.038, (at[0], at[1], 0.083), simple("photo-coffee", (0.05, 0.025, 0.012), rough=0.05), coll)


def screen_material():
    """Laptop screen showing the bay node in KiCad's 3D viewer (its top render), on a dark UI."""
    name = "photo-screen"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, nt, b = _principled(name)
    b.inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1)
    b.inputs["Roughness"].default_value = 0.05
    img_path = REPO / "electronics" / "bay-node" / "docs" / "bay-node-top.png"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    # box UVs are per-face; use generated coords on the X/Z face plane, keep the board's aspect
    mp.inputs["Scale"].default_value = (1.0, 1.0, 1.32)
    mp.inputs["Location"].default_value = (0.0, 0.0, -0.16)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    sw = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(mp.outputs["Vector"], sw.inputs["Vector"])
    uv = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sw.outputs["X"], uv.inputs["X"])
    nt.links.new(sw.outputs["Z"], uv.inputs["Y"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.extension = "CLIP"
    if img_path.exists():
        tex.image = bpy.data.images.load(str(img_path), check_existing=True)
    nt.links.new(uv.outputs["Vector"], tex.inputs["Vector"])
    ui = nt.nodes.new("ShaderNodeMix"); ui.data_type = "RGBA"
    ui.inputs["A"].default_value = (0.035, 0.04, 0.05, 1)          # dark KiCad 3D-viewer background
    nt.links.new(tex.outputs["Alpha"], ui.inputs["Factor"])
    nt.links.new(tex.outputs["Color"], ui.inputs["B"])
    nt.links.new(ui.outputs["Result"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 1.6
    return m


def laptop(coll, c=(1.14, -0.17), deg=-14.0):
    """Space-grey laptop facing the viewer, lid open ~110°; its left port takes the C4 cable."""
    from mathutils import Matrix
    gray = simple("photo-laptop-alu", (0.36, 0.37, 0.39), rough=0.32, metal=1.0)
    rz = math.radians(deg)
    R = Matrix.Rotation(rz, 4, "Z")
    o = Vector((c[0], c[1], 0.0))

    def at(local):
        return o + R.to_3x3() @ Vector(local)

    box("laptop-base", (0.312, 0.218, 0.014), at((0, 0, 0.007)), gray, coll, bevel=0.003, rot=(0, 0, rz))
    box("laptop-keys", (0.27, 0.10, 0.0006), at((0, 0.03, 0.0143)), simple("photo-keys", (0.02, 0.02, 0.022), rough=0.6),
        coll, rot=(0, 0, rz))
    box("laptop-pad", (0.11, 0.065, 0.0004), at((0, -0.065, 0.0142)), simple("photo-pad", (0.30, 0.31, 0.33), rough=0.25),
        coll, rot=(0, 0, rz))
    hinge = at((0, 0.106, 0.014))
    tilt = (math.radians(-20), 0, rz)                 # lid leans back 20° from vertical
    lid = box("laptop-lid", (0.312, 0.005, 0.21), (0, 0, 0), gray, coll, bevel=0.002)
    lid.data.transform(Matrix.Translation((0, 0, 0.105)))
    lid.location, lid.rotation_euler = hinge, tilt
    screen = box("laptop-screen", (0.29, 0.0004, 0.18), (0, 0, 0), screen_material(), coll)
    screen.data.transform(Matrix.Translation((0, -0.0028, 0.108)))
    screen.location, screen.rotation_euler = hinge, tilt


def build(glb):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    win = bpy.context.window_manager.windows[0]
    win.scene = sc
    for ob in list(sc.collection.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(sc.collection.children):
        bpy.data.collections.remove(coll)
    rack = bpy.data.collections.new("photo-rack")
    sc.collection.children.link(rack)
    setc = bpy.data.collections.new("photo-set")
    sc.collection.children.link(setc)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[rack.name]
    with bpy.context.temp_override(window=win, scene=sc):
        bpy.ops.import_scene.gltf(filepath=str(glb))
    dress(rack)

    # desk top (z = 0 is the rack's feet), legs, wall, floor
    box("desk-top", (2.0, 0.86, 0.03), (0.25, -0.13, -0.015), oak(), setc, bevel=0.003)
    steel = simple("photo-steel-black", (0.02, 0.02, 0.02), rough=0.45, metal=0.8)
    for x in (-0.68, 1.18):
        for y in (-0.50, 0.24):
            box("desk-leg", (0.04, 0.04, 0.72), (x, y, -0.39), steel, setc)
    wall = box("wall", (7.0, 0.05, 3.2), (0.25, 0.33, 0.85), plaster(), setc)
    box("floor", (7.0, 7.0, 0.02), (0.25, -2.0, -0.76), simple("photo-floor", (0.16, 0.12, 0.09), rough=0.6), setc)
    box("skirting", (7.0, 0.012, 0.08), (0.25, 0.302, -0.71), simple("photo-skirt", (0.85, 0.85, 0.83), rough=0.5), setc)
    laptop(setc)
    mug(setc)

    # world: dim sky for reflections; key: low window sun from the left; soft window fill; warm bounce
    world = bpy.data.worlds.get("photo-world") or bpy.data.worlds.new("photo-world")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    try:
        sky.sky_type = "NISHITA"
        sky.sun_elevation = math.radians(22)
        sky.sun_rotation = math.radians(-60)
    except Exception:
        pass
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.05
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    def lamp(name, kind, loc, rot, energy, color, **kw):
        ld = bpy.data.lights.new(name, kind)
        ld.energy, ld.color = energy, color
        for k, v in kw.items():
            setattr(ld, k, v)
        ob = bpy.data.objects.new(name, ld)
        ob.location, ob.rotation_euler = loc, [math.radians(a) for a in rot]
        setc.objects.link(ob)
        return ob

    lamp("sun", "SUN", (-2, -2, 3), (64, 0, -58), 5.0, (1.0, 0.86, 0.70), angle=math.radians(0.8))
    win_light = lamp("window", "AREA", (-2.2, -0.9, 1.3), (80, 0, -70), 160, (0.88, 0.93, 1.0), shape="RECTANGLE")
    win_light.data.size, win_light.data.size_y = 1.4, 1.2
    lamp("fill", "AREA", (1.4, -2.6, 1.2), (65, 0, 28), 35, (1.0, 0.95, 0.88), size=2.5)
    lamp("bounce", "AREA", (0.3, -0.9, -0.2), (-80, 0, 0), 12, (1.0, 0.82, 0.65), size=1.5)

    cam = bpy.data.objects.new("photo-cam", bpy.data.cameras.new("photo-cam"))
    setc.objects.link(cam)
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    sc.cycles.samples = 256
    sc.cycles.use_denoising = True
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.2
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1200
    return {"scene": sc.name, "objects": len(rack.all_objects), "set": len(setc.objects)}


# ---------------------------------------------------------------------------- shots
def aim(cam, loc, target, lens, fstop, focus=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = fstop
    cam.data.dof.focus_distance = (Vector(focus or target) - Vector(loc)).length


def bay_center(bay):
    import json
    data = json.loads((REPO / "site" / "assets" / "rack.json").read_text(encoding="utf-8"))
    return Vector(next(x for x in data["bays"] if x["id"] == bay)["center"]) / 1000.0


def shot(name, out, samples, res):
    sc = bpy.data.scenes[SCENE]
    bpy.context.window_manager.windows[0].scene = sc
    cam = sc.camera
    if name == "desk":
        aim(cam, (-0.62, -1.72, 0.78), (0.42, 0.06, 0.36), 35, 5.6, focus=(0.30, 0.02, 0.45))
    elif name == "drawer":
        c = bay_center("C2")
        aim(cam, c + Vector((0.30, -0.62, 0.28)), c + Vector((-0.02, -0.12, -0.03)), 50, 4.0,
            focus=c + Vector((0.0, -0.16, -0.02)))
    elif name == "detail":
        # raking view along row B's drawer fronts: status LEDs, printed fronts, bracket and post
        c = bay_center("B1")
        aim(cam, c + Vector((-0.24, -0.36, 0.05)), c + Vector((0.20, -0.08, -0.03)), 50, 4.0,
            focus=c + Vector((0.02, -0.12, -0.02)))
    w, h = (int(v) for v in res.split("x"))
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.cycles.samples = samples
    sc.render.filepath = out
    jpeg = out.lower().endswith((".jpg", ".jpeg"))
    sc.render.image_settings.file_format = "JPEG" if jpeg else "PNG"
    if jpeg:
        sc.render.image_settings.quality = 90
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0], scene=sc):
        bpy.ops.render.render(write_still=True, scene=sc.name)
    return {"shot": name, "out": out, "samples": samples}


if MODE == "build":
    glb = REPO / (sys.argv[2] if len(sys.argv) > 2 else "render/assembly-photo.glb")
    result = build(glb)
else:
    name = sys.argv[2] if len(sys.argv) > 2 else "desk"
    out = str(REPO / (sys.argv[3] if len(sys.argv) > 3 else f"docs/img/photo-{name}.jpg"))
    result = shot(name, out, int(sys.argv[4]) if len(sys.argv) > 4 else 256,
                  sys.argv[5] if len(sys.argv) > 5 else "1920x1200")
