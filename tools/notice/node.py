"""Bay node solid for the notice: KiCad's STEP export (board + the parts it has models for), plus
simple bodies for the parts whose 3D model is missing from the KiCad library (module, USB-C,
JST PH side-entry, buttons, LED).  Output: parts/bay_node.brep in node coordinates (front-left
corner at the origin, y towards the rear, board bottom at z = 0).

    kicad-cli pcb export step --subst-models -o <build>/parts/bay-node.step electronics/bay-node/bay-node.kicad_pcb
    NODE_BUILD=1 freecadcmd node.py        (<build> = $NOTICE_BUILD, see tools/notice/run.py)
"""
import os
import FreeCAD as App
import Part
from FreeCAD import Vector as V

HERE = os.environ.get("NOTICE_BUILD") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mechanical", "build", "notice")
D = 80.0                      # board depth; KiCad y grows towards the front edge (y = 80)
TOP = 1.6


def kbox(x0, y0, x1, y1, z0, z1):
    """Box from KiCad coordinates (y down) to node coordinates (y up from the front... rear)."""
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, D - y1, z0))


def stadium(cx, cz, w, h, y0, y1, axis="y"):
    """Rounded USB-C shell: stadium w x h (in the xz or yz plane), extruded between y0 and y1."""
    r = h / 2
    L = w - h
    if axis == "y":
        f = Part.Face(Part.Wire(Part.__sortEdges__([
            Part.LineSegment(V(cx - L / 2, 0, cz - r), V(cx + L / 2, 0, cz - r)).toShape(),
            Part.Arc(V(cx + L / 2, 0, cz - r), V(cx + w / 2, 0, cz), V(cx + L / 2, 0, cz + r)).toShape(),
            Part.LineSegment(V(cx + L / 2, 0, cz + r), V(cx - L / 2, 0, cz + r)).toShape(),
            Part.Arc(V(cx - L / 2, 0, cz + r), V(cx - w / 2, 0, cz), V(cx - L / 2, 0, cz - r)).toShape()])))
        f.translate(V(0, y0, 0))
        return f.extrude(V(0, y1 - y0, 0))
    f = Part.Face(Part.Wire(Part.__sortEdges__([
        Part.LineSegment(V(0, cx - L / 2, cz - r), V(0, cx + L / 2, cz - r)).toShape(),
        Part.Arc(V(0, cx + L / 2, cz - r), V(0, cx + w / 2, cz), V(0, cx + L / 2, cz + r)).toShape(),
        Part.LineSegment(V(0, cx + L / 2, cz + r), V(0, cx - L / 2, cz + r)).toShape(),
        Part.Arc(V(0, cx - L / 2, cz + r), V(0, cx - w / 2, cz), V(0, cx - L / 2, cz - r)).toShape()])))
    f.translate(V(y0, 0, 0))
    return f.extrude(V(y1 - y0, 0, 0))


def usb_c(kx, ky, rot):
    """HRO TYPE-C-31-M-12: 8.94 x 7.3 x 3.16 shell, opening at the board edge."""
    w, h, d = 8.94, 3.16, 7.3
    cz = TOP + h / 2
    if rot == 0:                     # opening towards KiCad +y (front edge, node y = 0)
        y_front = D - (ky + 3.65)
        s = stadium(kx, cz, w, h, y_front, y_front + d)
        return s.cut(stadium(kx, cz, w - 0.6, h - 0.6, y_front - 0.1, y_front + 5.5))
    x_out = kx + 3.65                # rot 90: opening towards +x (right edge)
    s = stadium(D - ky, cz, w, h, x_out - d, x_out, axis="x")
    return s.cut(stadium(D - ky, cz, w - 0.6, h - 0.6, x_out - 5.5, x_out + 0.1, axis="x"))


def jst_ph_side(kx, ky, rot, n):
    """JST PH S#B-PH-SM4-TB, side entry: body 7.6 deep, 4.75 high, opening towards the edge."""
    wid = 2.0 * (n - 1) + 4.0
    d, h = 7.6, 4.75
    if rot == 90:                    # opening towards +x
        x1 = kx + 5.0
        b = kbox(x1 - d, ky - wid / 2, x1, ky + wid / 2, TOP, TOP + h)
        return b.cut(kbox(x1 - 5.5, ky - wid / 2 + 0.8, x1 + 0.1, ky + wid / 2 - 0.8, TOP + 1.0, TOP + h - 0.9))
    x0 = kx - 5.0                    # rot -90: opening towards -x
    b = kbox(x0, ky - wid / 2, x0 + d, ky + wid / 2, TOP, TOP + h)
    return b.cut(kbox(x0 - 0.1, ky - wid / 2 + 0.8, x0 + 5.5, ky + wid / 2 - 0.8, TOP + 1.0, TOP + h - 0.9))


def build():
    s = Part.read(os.path.join(HERE, "parts", "bay-node.step"))
    sols = []
    for so in s.Solids:
        so = so.copy()
        so.translate(V(0, D, 0))         # STEP y = -KiCad y; node y = 80 - KiCad y
        sols.append(so)
    # ESP32-S2-MINI-1 (U3 at 32, 10.5): 15.4 x 20.5 module, antenna end at the rear edge, shield can
    sols.append(kbox(32 - 7.7, 10.5 - 10.25, 32 + 7.7, 10.5 + 10.25, TOP, TOP + 0.8))
    sols.append(kbox(32 - 6.4, 10.5 - 10.25 + 6.6, 32 + 6.4, 10.5 + 10.25 - 0.6, TOP + 0.8, TOP + 2.45))
    sols.append(usb_c(32.0, 76.6, 0))            # J3: PC port, front edge
    sols.append(usb_c(60.4, 24.0, 90))           # J4: right edge
    sols.append(jst_ph_side(59.1, 63.0, 90, 6))   # J2: row cable out (6-pin: bus, CAN, POS), right
    sols.append(jst_ph_side(59.1, 40.0, 90, 6))   # J5
    sols.append(jst_ph_side(59.1, 11.65, 90, 2))  # J6
    sols.append(jst_ph_side(4.9, 63.0, -90, 6))   # J1: row cable in, left
    for x in (7.5, 15.5):                         # SW1, SW2: TS-1187A 5.1 x 5.1 x 1.5 + round button
        sols.append(kbox(x - 2.55, 11.5 - 2.55, x + 2.55, 11.5 + 2.55, TOP, TOP + 1.5))
        sols.append(Part.makeCylinder(1.5, 0.5, V(x, D - 11.5, TOP + 1.5)))
    sols.append(kbox(50 - 3.35, 77.3 - 1.3, 50 + 3.35, 77.3 + 1.3, TOP, TOP + 1.4))   # SW3 slide switch
    sols.append(kbox(50 - 0.5, 78.6, 50 + 0.5, 80.1, TOP + 0.3, TOP + 1.2))
    sols.append(kbox(12 - 1, 78.2 - 1, 12 + 1, 78.2 + 1, TOP, TOP + 0.84))          # D4 WS2812B-2020
    c = Part.makeCompound(sols)
    c.exportBrep(os.path.join(HERE, "parts", "bay_node.brep"))
    return c


if os.environ.get("NODE_BUILD"):
    c = build()
    open(os.path.join(HERE, "parts", "node_log.txt"), "w").write(f"solids {len(c.Solids)} faces {len(c.Faces)} bb {c.BoundBox}\n")
