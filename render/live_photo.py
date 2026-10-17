"""Photoreal "on a desk" shots of the rack, in a RUNNING Blender (see tools/blender_live.py).

    python tools/blender_live.py exec render/live_photo.py build [glb]
    python tools/blender_live.py exec render/live_photo.py shot <desk|drawer|boards|detail> [out.jpg] [samples] [WxH]

(Renders at full size take ~1 min: use blender_live.py rather than an MCP call with a short timeout.)

Builds its own scene ("hw-testing-rack-photo"), so the neutral technical scene
from live_scene.py stays as it is.  Materials are replaced by object category:
PETG with 0.2 mm layer lines (along each part's print Z) and shading-rounded
edges for every printed part (the whole frame is printed); lacquered solder
mask on the PCBs.  The set is a small office: oak desk
against a plaster wall, a laptop wired to bay C4's front port by a hanging
USB-C cable, lit only through a window (sun + sky, with a light portal).
The GLB comes from `tools/assembly_glb.py --hq --with-pc-cable --open-bays B3 --out render/assembly-photo.glb`; the scanned
textures from `tools/fetch_render_assets.py` and the laptop screen from `render/screen_terminal.py`
(both into render/assets/, optional: procedural fallbacks).
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

# printed parts; their layers stack along the part's thinnest local axis (ladders, braces and
# plates print flat, drawers and trays floor-down)
PRINTED = {"ladders", "braces", "frameplates", "trays", "drawers", "chainparts", "plates", "cameras", "labels"}


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


def rounded_edges(nt, radius=0.0006):
    """Cycles Bevel node: shading-only rounded edges, so CAD-sharp edges catch light like real parts."""
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = radius
    return bev


def petg(color, axis):
    """PETG: satin, faint variation, layer lines along `axis` of the object (mm), rounded edges."""
    key = f"photo-petg-{axis}-" + "".join(f"{int(c * 255):02x}" for c in color[:3])
    if key in bpy.data.materials:
        return bpy.data.materials[key]
    # real pigmented PETG is less saturated than the viewer's flat colours
    grey = sum(color[:3]) / 3
    color = [grey + 0.82 * (c - grey) for c in color[:3]]
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
    nt.links.new(rounded_edges(nt).outputs["Normal"], bump.inputs["Normal"])
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
    b.inputs["Roughness"].default_value = 0.34
    b.inputs["Specular IOR Level"].default_value = 0.5
    b.inputs["Coat Weight"].default_value = 0.06
    b.inputs["Coat Roughness"].default_value = 0.3
    if grey > 0.45:                       # light PETG lets a little light through
        b.inputs["Subsurface Weight"].default_value = 0.12
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.9, 0.8)
        b.inputs["Subsurface Scale"].default_value = 0.0015
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
            if cat in PRINTED:
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
                    r, g, b_, _ = bsdf.inputs["Base Color"].default_value
                    hi, lo = max(r, g, b_), min(r, g, b_)
                    sat = (hi - lo) / hi if hi else 0
                    if cat != "pcb" and hi > 0.45 and (sat < 0.12 or (r > g > b_ and sat > 0.35 and hi > 0.5)):
                        bsdf.inputs["Metallic"].default_value = 1.0       # nickel shells, gold pins / pads
                        bsdf.inputs["Roughness"].default_value = 0.25
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
    uv = bm.loops.layers.uv.new("UVMap")          # box projection in metres, for the scanned textures
    for f in bm.faces:
        n = f.normal
        a, b_ = (0, 1) if abs(n.z) >= max(abs(n.x), abs(n.y)) else ((0, 2) if abs(n.y) >= abs(n.x) else (1, 2))
        for loop in f.loops:
            co = loop.vert.co + Vector(loc)
            loop[uv].uv = (co[a], co[b_])
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


TEX = REPO / "render" / "assets" / "polyhaven"


def scanned(name, asset, tile_m, tint=None, normal=1.0, coat=0.0):
    """PBR material from a Poly Haven texture set (tools/fetch_render_assets.py), on the box UVs."""
    d = TEX / asset
    maps = {k: next(iter(sorted(d.glob(f"*_{k}_*.jpg"))), None) for k in ("diff", "nor_gl", "rough")} if d.exists() else {}
    if not maps or not all(maps.values()):
        return None
    m, nt, b = _principled(name)
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile_m, 1 / tile_m, 1)
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])

    def img(path, color):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(path), check_existing=True)
        t.image.colorspace_settings.name = "sRGB" if color else "Non-Color"
        nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        return t

    diff = img(maps["diff"], True)
    if tint:
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs["B"].default_value = (*tint, 1)
        nt.links.new(diff.outputs["Color"], mix.inputs["A"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    else:
        nt.links.new(diff.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(img(maps["rough"], False).outputs["Color"], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nm.inputs["Strength"].default_value = normal
    nt.links.new(img(maps["nor_gl"], False).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.25
    return m


def oak():
    name = "photo-oak"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = scanned(name, "wood_table_001", 1.6, coat=0.25)
    if m:
        return m
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
    m = scanned(name, "painted_plaster_wall", 1.8, tint=(1.3, 1.25, 1.17), normal=0.35)
    if m:
        return m
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


def screen_material():
    """Laptop screen showing the bay node in KiCad's 3D viewer (its top render), on a dark UI."""
    name = "photo-screen"
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m, nt, b = _principled(name)
    b.inputs["Base Color"].default_value = (0.01, 0.01, 0.012, 1)
    b.inputs["Roughness"].default_value = 0.05
    term = REPO / "render" / "assets" / "laptop-screen.png"          # render/screen_terminal.py
    img_path = term if term.exists() else REPO / "electronics" / "bay-node" / "docs" / "bay-node-top.png"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    # generated coords on the screen's X/Z face; the KiCad render keeps the board's aspect
    if not term.exists():
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
    b.inputs["Emission Strength"].default_value = 1.2
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
    # USB-C port on the left side, 3 cm behind the middle; returns (port centre, outward direction)
    port = at((-0.156, 0.03, 0.0075))
    out = R.to_3x3() @ Vector((-1, 0, 0))
    box("laptop-port", (0.0012, 0.0089, 0.0033), port + out * 0.0004, simple("photo-port", (0.01, 0.01, 0.01), rough=0.6),
        coll, rot=(0, 0, rz))
    return port, out


def usb_c_plug(name, tip, direction, coll):
    """USB-C plug seated in a port at `tip`, pointing out along `direction`: nickel shell (mostly
    in the port), soft-touch overmold, strain relief.  Returns where the cable leaves it."""
    d = Vector(direction).normalized()
    rot = d.to_track_quat("Z", "Y").to_euler()
    q = d.to_track_quat("Z", "Y").to_matrix()
    nickel = simple("photo-nickel", (0.75, 0.74, 0.72), rough=0.22, metal=1.0)
    mold = simple("photo-overmold", (0.035, 0.035, 0.038), rough=0.45, coat=0.1)
    box(f"{name}-shell", (0.0083, 0.0025, 0.0045), tip + d * 0.0012, nickel, coll, bevel=0.0009, rot=rot)
    box(f"{name}-mold", (0.0125, 0.0068, 0.019), tip + d * 0.0130, mold, coll, bevel=0.0022, rot=rot)
    relief = bpy.data.meshes.new(f"{name}-relief")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.0028, radius2=0.0023, depth=0.012)
    bm.to_mesh(relief)
    bm.free()
    for poly in relief.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(f"{name}-relief", relief)
    ob.matrix_world = (__import__("mathutils").Matrix.Translation(tip + d * 0.0285) @ q.to_4x4())
    relief.materials.append(mold)
    coll.objects.link(ob)
    return tip + d * 0.0345


def hanging_cable(coll, a_port, a_dir, b_port, b_dir, touchdown, r=0.0021):
    """Cable from plug A, hanging under its own weight (a catenary: the shape gravity gives a flexible
    cable, so no simulation needed) to `touchdown` on the desk, lying there, into plug B."""
    a = usb_c_plug("plug-rack", a_port, a_dir, coll)
    b = usb_c_plug("plug-laptop", b_port, b_dir, coll)
    pts = [a + Vector(a_dir).normalized() * t for t in (0.0, 0.01, 0.02)]          # stiff bit after the relief
    start = pts[-1]
    t = Vector((touchdown[0], touchdown[1], r))
    horiz = Vector((t.x - start.x, t.y - start.y, 0))
    h, height = horiz.length, start.z - r
    lo, hi = 1e-4, 10.0                                   # a·(cosh(h/a) − 1) = height
    for _ in range(80):
        mid = (lo + hi) / 2
        if mid * (math.cosh(h / mid) - 1) > height:
            lo = mid
        else:
            hi = mid
    ca, u = (lo + hi) / 2, horiz.normalized()
    for i in range(1, 41):
        s_ = h * (1 - i / 40)                            # horizontal distance left to the touchdown
        p = t - u * s_
        p.z = r + ca * (math.cosh(s_ / ca) - 1)
        pts.append(p)
    # lying on the desk: a lazy curve that leaves the touchdown along the fall direction and
    # arrives in line with the laptop port
    end = b + Vector(b_dir).normalized() * 0.012
    end.z = r
    c1, c2 = t + u * 0.10, end + Vector(b_dir).normalized() * 0.10
    c2.z = r
    for i in range(1, 31):
        k = i / 30
        p = (1 - k) ** 3 * t + 3 * (1 - k) ** 2 * k * c1 + 3 * (1 - k) * k ** 2 * c2 + k ** 3 * end
        p.z = r
        pts.append(p)
    pts += [b + Vector(b_dir).normalized() * 0.006, b]
    cu = bpy.data.curves.new("pc-cable", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = r, 6, True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for pt, co in zip(sp.points, pts):
        pt.co = (co.x, co.y, co.z, 1)
    sp.order_u, sp.use_endpoint_u, sp.resolution_u = 4, True, 6
    ob = bpy.data.objects.new("pc-cable", cu)
    cu.materials.append(simple("photo-cable-rubber", (0.022, 0.022, 0.024), rough=0.55, coat=0.08))
    coll.objects.link(ob)
    return ob


def build(glb):
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    win = bpy.context.window_manager.windows[0]
    win.scene = sc
    for ob in list(sc.collection.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(sc.collection.children):
        bpy.data.collections.remove(coll)
    for m in [m for m in bpy.data.materials if m.name.startswith("photo-")]:
        bpy.data.materials.remove(m)          # rebuilt from this file every time
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
    box("wall", (4.4, 0.05, 2.75), (0.825, 0.33, 0.595), plaster(), setc)
    box("floor", (7.0, 7.0, 0.02), (0.25, -2.0, -0.76), simple("photo-floor", (0.16, 0.12, 0.09), rough=0.6), setc)
    box("skirting", (4.3, 0.012, 0.08), (0.825, 0.302, -0.71), simple("photo-skirt", (0.85, 0.85, 0.83), rough=0.5), setc)
    port, out = laptop(setc)
    # the demo cable from the GLB is a viewer bezier: replace it with a hanging one with real plugs
    for ob in [o for o in rack.all_objects if o.name.startswith("cable:pc")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    import json
    pc = next(c for c in json.loads((REPO / "site" / "assets" / "rack.json").read_text(encoding="utf-8"))["cables"]
              if c["kind"] == "pc")
    tilt = math.radians(20)
    rack_port = Vector(pc["points"][0]) / 1000.0
    hanging_cable(setc, rack_port, (0, -math.cos(tilt), -math.sin(tilt)), port, out, touchdown=(0.70, -0.21))

    # a closed room, lit only through a window in the left wall (sun + sky), like a real office
    white = simple("photo-paint", (0.80, 0.79, 0.76), rough=0.85)
    wx, t = -1.35, 0.12                          # left wall plane, thickness
    y0, y1, z0, z1 = -1.55, -0.25, 0.10, 1.40     # window opening
    zf, zc, yb, yf = -0.76, 1.95, 0.33, -3.3     # floor, ceiling, back wall, front wall
    box("wall-left-low", (t, yb - yf, z0 - zf), (wx, (yb + yf) / 2, (z0 + zf) / 2), plaster(), setc)
    box("wall-left-high", (t, yb - yf, zc - z1), (wx, (yb + yf) / 2, (zc + z1) / 2), plaster(), setc)
    box("wall-left-back", (t, yb - y1, z1 - z0), (wx, (yb + y1) / 2, (z0 + z1) / 2), plaster(), setc)
    box("wall-left-front", (t, y0 - yf, z1 - z0), (wx, (y0 + yf) / 2, (z0 + z1) / 2), plaster(), setc)
    frame = simple("photo-window-frame", (0.88, 0.88, 0.86), rough=0.4)
    box("mullion-v", (0.06, 0.05, z1 - z0), (wx, (y0 + y1) / 2, (z0 + z1) / 2), frame, setc)
    box("mullion-h", (0.06, y1 - y0, 0.05), (wx, (y0 + y1) / 2, z0 + 0.62 * (z1 - z0)), frame, setc)
    box("sill", (0.30, y1 - y0 + 0.1, 0.03), (wx + 0.05, (y0 + y1) / 2, z0 - 0.015), frame, setc)
    box("wall-right", (t, yb - yf, zc - zf), (3.0, (yb + yf) / 2, (zc + zf) / 2), white, setc)
    box("wall-front", (4.6, t, zc - zf), (0.8, yf, (zc + zf) / 2), white, setc)
    box("ceiling", (4.6, yb - yf, 0.05), (0.8, (yb + yf) / 2, zc), white, setc)

    world = bpy.data.worlds.get("photo-world") or bpy.data.worlds.new("photo-world")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sun_dir = Vector((0.80, 0.40, -0.45)).normalized()          # coming in through the window
    try:
        sky.sky_type = "NISHITA"
        sky.sun_disc = False
        sky.sun_elevation = math.asin(-sun_dir.z)
        sky.sun_rotation = math.atan2(-sun_dir.x, sun_dir.y) + math.pi
    except Exception:
        pass
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.35
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    def lamp(name, kind, loc, rot, energy, color, **kw):
        ld = bpy.data.lights.new(name, kind)
        ld.energy, ld.color = energy, color
        for k, v in kw.items():
            setattr(ld, k, v)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = rot if not isinstance(rot, tuple) else [math.radians(a) for a in rot]
        setc.objects.link(ob)
        return ob

    lamp("sun", "SUN", (-3, -2, 3), sun_dir.to_track_quat("-Z", "Y").to_euler(), 6.0, (1.0, 0.88, 0.74),
         angle=math.radians(0.6))
    # light portal in the window: tells Cycles where the sky comes in (much less noise indoors)
    portal = lamp("window-portal", "AREA", (wx - t / 2, (y0 + y1) / 2, (z0 + z1) / 2), (0, 90, 0), 0, (1, 1, 1),
                  shape="RECTANGLE")
    portal.data.size, portal.data.size_y = z1 - z0, y1 - y0
    portal.data.cycles.is_portal = True
    # a photographer's bounce card from the camera side, so shadows don't go black
    lamp("bounce-card", "AREA", (0.9, -1.9, 0.35), (75, 0, 25), 30, (1.0, 0.95, 0.9), size=1.2)

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
    sc.view_settings.exposure = 0.3
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1200
    sc.cycles.max_bounces = 16
    sc.cycles.diffuse_bounces = 6
    sc.cycles.glossy_bounces = 6
    sc.cycles.sample_clamp_indirect = 8.0
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.01
    sc.cycles.glossy_bounces = 8
    sc.cycles.transmission_bounces = 8
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    sc.cycles.denoising_prefilter = "ACCURATE"
    try:
        sc.cycles.denoising_quality = "HIGH"
    except Exception:
        pass
    lens_fx(sc)
    return {"scene": sc.name, "objects": len(rack.all_objects), "set": len(setc.objects)}


def lens_fx(sc):
    """Compositor: LED bloom, a hint of chromatic aberration, soft vignette (Blender 5 node-group API)."""
    try:
        ng = bpy.data.node_groups.get("photo-lens") or bpy.data.node_groups.new("photo-lens", "CompositorNodeTree")
        ng.nodes.clear()
        if not any(getattr(i, "in_out", "") == "OUTPUT" for i in ng.interface.items_tree):
            ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        rl.scene = sc
        glare = ng.nodes.new("CompositorNodeGlare")
        glare.inputs["Type"].default_value = "Bloom"
        glare.inputs["Threshold"].default_value = 1.2
        glare.inputs["Strength"].default_value = 0.35
        glare.inputs["Size"].default_value = 0.6
        lens = ng.nodes.new("CompositorNodeLensdist")
        lens.inputs["Dispersion"].default_value = 0.012
        mask = ng.nodes.new("CompositorNodeEllipseMask")
        mask.inputs["Size"].default_value = (0.95, 0.85)
        blur = ng.nodes.new("CompositorNodeBlur")
        blur.inputs["Size"].default_value = (300, 300)
        ramp = ng.nodes.new("ShaderNodeMapRange")
        ramp.inputs["To Min"].default_value = 0.72
        mix = ng.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        out = ng.nodes.new("NodeGroupOutput")
        link = ng.links.new
        link(rl.outputs["Image"], glare.inputs["Image"])
        link(glare.outputs["Image"], lens.inputs["Image"])
        link(mask.outputs["Mask"], blur.inputs["Image"])
        link(blur.outputs["Image"], ramp.inputs["Value"])
        link(lens.outputs["Image"], mix.inputs["A"])
        link(ramp.outputs["Result"], mix.inputs["B"])
        link(mix.outputs["Result"], out.inputs[0])
        sc.compositing_node_group = ng
        sc.render.use_compositing = True
        return True
    except Exception as ex:                       # older Blender: no compositor effects, still renders
        print("lens_fx skipped:", ex)
        return False


# ---------------------------------------------------------------------------- shots
def aim(cam, loc, target, lens, fstop, focus=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = fstop
    cam.data.dof.focus_distance = (Vector(focus or target) - Vector(loc)).length


def led_world(bay):
    """Frame-space position (m) of a bay's front status LED, from site/assets/rack.json."""
    import json
    data = json.loads((REPO / "site" / "assets" / "rack.json").read_text(encoding="utf-8"))
    led = next(x for x in data["leds"] if x["bay"] == bay)
    row = data["rack"]["rows"][led["row"]]
    t = math.radians(row["tilt"])
    x, y, z = led["pos"]
    return (Vector(row["origin"]) + Vector((x, y * math.cos(t) - z * math.sin(t), y * math.sin(t) + z * math.cos(t)))) / 1000.0


def bay_center(bay):
    import json
    data = json.loads((REPO / "site" / "assets" / "rack.json").read_text(encoding="utf-8"))
    return Vector(next(x for x in data["bays"] if x["id"] == bay)["center"]) / 1000.0


def shot(name, out, samples, res):
    sc = bpy.data.scenes[SCENE]
    bpy.context.window_manager.windows[0].scene = sc
    cam = sc.camera
    if name == "desk":
        aim(cam, (-0.40, -2.15, 0.50), (0.50, 0.05, 0.30), 58, 2.8, focus=(0.30, 0.0, 0.33))
    elif name == "drawer":
        c = bay_center("C2")
        aim(cam, c + Vector((0.30, -0.62, 0.28)), c + Vector((-0.02, -0.12, -0.03)), 50, 4.0,
            focus=c + Vector((0.0, -0.16, -0.02)))
    elif name == "boards":
        # the vendor models up close: Raspberry Pi Pico 2 on B3's pulled-out drawer, the
        # Arduino UNO R4 WiFi next door in B4 (the photo GLB is baked with --open-bays B3)
        c = bay_center("B3") + Vector((0.0, -0.13, -0.05))
        aim(cam, c + Vector((-0.20, -0.42, 0.30)), c + Vector((0.03, 0.0, 0.0)), 70, 4.0, focus=c)
    elif name == "detail":
        # raking view along row B's drawer fronts: status LEDs, printed fronts, tray fascias and ladder;
        # sharp on B2's LED
        c = bay_center("B1")
        aim(cam, c + Vector((-0.24, -0.36, 0.05)), c + Vector((0.20, -0.08, -0.03)), 50, 5.6,
            focus=led_world("B2"))
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
    result = shot(name, out, int(sys.argv[4]) if len(sys.argv) > 4 else 384,
                  sys.argv[5] if len(sys.argv) > 5 else "1600x1000")
