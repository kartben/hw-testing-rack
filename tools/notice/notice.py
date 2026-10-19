"""Assembly-notice line art from FreeCAD: real solids, Fasteners screws, TechDraw hidden lines.

    NOTICE=a3,pin freecadcmd notice.py        -> <build>/out/<name>.svg  (<build> = $NOTICE_BUILD,
                                                 the whole set: python tools/notice/run.py)

Every drawing is ONE TechDraw.projectEx over the whole compound (old parts, new parts, screw
axis lines), so parts hide each other.  Visible hard edges + outlines only (no hidden lines,
no tangent edges).  Each visible edge is then given back to the part it lies on (its own
projection), to draw parts already in place in light grey and the new ones in black.
"""
import json, math, os, sys, time, traceback
import FreeCAD as App
import Part, TechDraw
from FreeCAD import Vector as V

BUILD = os.environ.get("NOTICE_BUILD") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mechanical", "build", "notice")
OUT = os.path.join(BUILD, "out")
PARTS = os.path.join(BUILD, "parts")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "notice_log.txt"), "a")


def log(*a):
    LOG.write(" ".join(str(x) for x in a) + "\n")
    LOG.flush()


# ------------------------------------------------------------------ constants (tools/panel_proto.py probe)
C = json.load(open(os.path.join(BUILD, "constants.json")))
P, T, CL, PR, BT = C["PANEL_PITCH"], C["PANEL_T"], C["PANEL_CLEAR"], C["PR"], C["BRACE_T"]
TILT = math.radians(C["TILT"])
U = (0.0, math.cos(TILT), math.sin(TILT))          # along the row slope (frame)


def M(rows):
    m = App.Matrix()
    (m.A11, m.A12, m.A13, m.A14), (m.A21, m.A22, m.A23, m.A24), (m.A31, m.A32, m.A33, m.A34) = rows
    return m


def m_tr(x, y, z):
    return M([[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z]])


def m_ladder(x0):           # profile x = frame Y, profile y = frame Z, extruded along frame X
    return M([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])


def m_row(k, x0):
    c, s = math.cos(TILT), math.sin(TILT)
    return M([[1, 0, 0, x0], [0, c, -s, C["ROW_Y0"]], [0, s, c, C["ROW_Z"][k]]])


def m_brace(xc):            # printed flat: x = frame X, y = frame Z, z = thickness (towards -Y)
    return M([[1, 0, 0, xc], [0, 0, -1, PR + BT], [0, 1, 0, 0]])


def brace_z(k):
    if k < 0:
        top = C["ROW_Z"][0] + (PR - C["ROW_Y0"]) * math.tan(TILT)
        return [30, 48, top - 44, top - 26]
    b0 = C["ROW_Z"][k] + (PR - C["ROW_Y0"]) * math.tan(TILT)
    h = C["ROW_Z"][k + 1] - C["ROW_Z"][k]
    return [b0 + 28, b0 + 46, b0 + h - 47, b0 + h - 29]


# ------------------------------------------------------------------ shapes
_cache = {}


def part(name):
    if name not in _cache:
        s = Part.Shape()
        s.importBrep(os.path.join(PARTS, name + ".brep"))
        _cache[name] = s
    return _cache[name]


_doc = None


def fastener(kind, dia, length=None):
    """Fasteners workbench solid, headless. Screws: head towards +Z, under-head plane z = 0."""
    global _doc
    key = (kind, dia, length)
    if key not in _cache:
        import FastenersCmd
        if _doc is None:
            _doc = App.newDocument("fasteners")
        o = _doc.addObject("Part::FeaturePython", kind)
        FastenersCmd.FSScrewObject(o, kind, None)
        o.Diameter = dia
        if length:
            o.Length = length
        if hasattr(o, "Thread"):
            o.Thread = True
        _doc.recompute()
        _cache[key] = o.Shape.copy()
    return _cache[key]


def fastener_z(kind, dia, length=None):
    """Fastener in its own frame: axis Z, head (or the insert's top face) towards +Z, seat plane z = 0."""
    key = ("z", kind, dia, length)
    if key not in _cache:
        s = fastener(kind, dia, length).copy()
        bb = s.BoundBox
        if kind == "IUTHeatInsert":          # top face at z = 0, body below
            s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMax))
        elif kind == "ISO7089":              # washer: bottom face at z = 0, towards the head
            s.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, -bb.ZMin))
        _cache[key] = s
        log("fastener", kind, dia, length, "bb", s.BoundBox)
    return _cache[key]


def node_shape():
    """Bay node: KiCad's STEP of the board plus stand-in bodies (node.py), node coordinates;
    without it, the bare board with its four holes."""
    if os.path.exists(os.path.join(PARTS, "bay_node.brep")):
        return part("bay_node")
    w, d = C["NODE_SIZE"]
    b = Part.makeBox(w, d, 1.6)
    for x, y in C["NODE_HOLES"]:
        b = b.cut(Part.makeCylinder(1.6, 2, V(x, d - y, -0.2)))
    return b


def row_cable():
    """The row cable's two connectors (notice.yaml row_cable: node 0's `from`, node 1's `to`) from
    node.py's parts/node.json: {"pins", "mouth" (node coordinates), "out" (unit, xy)} each; the
    v0.4 node's 2-pin J2 / J1 without it."""
    p = os.path.join(PARTS, "node.json")
    ph = {c["ref"]: c for c in json.load(open(p))["ph"]} if os.path.exists(p) else {}
    rc = C.get("ROW_CABLE", {"from": "J2", "to": "J1"})
    d = C["NODE_SIZE"][1]
    a = ph.get(rc["from"], {"pins": 2, "mouth": [64.1, d - 63.0, 3.975], "out": [1, 0]})
    b = ph.get(rc["to"], {"pins": 2, "mouth": [-0.1, d - 63.0, 3.975], "out": [-1, 0]})
    return a, b


def plug(m, out, n):
    """JST PH housing on a lead of n wires: 7 long (5.1 of it in the connector), 2(n-1)+2.2 wide."""
    w = 2.0 * (n - 1) + 2.2
    s = Part.makeBox(7.0, w, 2.65, V(-5.1, -w / 2, -1.325))
    s.rotate(V(0, 0, 0), V(0, 0, 1), math.degrees(math.atan2(out[1], out[0])))
    s.translate(m)
    return s


def lead(a, b, n, sag):
    """n wires (1.3 apart) from a to b, sagging by `sag` at the middle."""
    across = (b - a).cross(V(0, 0, 1))
    across.normalize()
    sols = []
    for i in range(n):
        o = across * (1.3 * (i - (n - 1) / 2))
        e = Part.Arc(a + o, (a + b) * 0.5 + o + V(0, 0, -sag), b + o).toShape()
        prof = Part.Wire(Part.makeCircle(0.6, e.valueAt(e.FirstParameter), e.tangentAt(e.FirstParameter)))
        sols.append(Part.Wire(e).makePipeShell([prof], True, True))
    return sols


def jumper_shape():
    """Row cable between node 0 and node 1, tray-0 carrier coordinates: two JST PH plugs and the lead."""
    ca, cb = row_cable()
    o0 = V(C["NODE_X0"], C["NODE_FRONT_Y"], C["NODE_Z"])
    ma, mb = o0 + V(*ca["mouth"]), o0 + V(P, 0, 0) + V(*cb["mouth"])
    oa, ob = V(ca["out"][0], ca["out"][1], 0), V(cb["out"][0], cb["out"][1], 0)
    sols = [plug(ma, ca["out"], ca["pins"]), plug(mb, cb["out"], cb["pins"])]
    return Part.makeCompound(sols + lead(ma + oa * 1.9, mb + ob * 1.9, ca["pins"], 3.0))


# ------------------------------------------------------------------ drag chain, DATA socket (run.py: rackcfg chain, drawer)
CH, DATA = C.get("CHAIN"), C.get("DATA")
if CH:                                         # chain_parts.scad / lib/carrier.scad names
    CHAIN_W, CHAIN_H = CH["outer"]             # across the side plates (vertical) x in the bend plane
    CHAIN_Z = CH["bottom"] + CHAIN_W / 2 + 0.6
    LINK_R, LINK_T = CHAIN_H / 2, (CHAIN_W - CH["inner"][1]) / 2
    LINK_B = (CHAIN_H - CH["inner"][0]) / 2
    LINK_MID0, POCKET = LINK_R + 0.3, 1.0


def chain_path(open_frac=0.0):
    """Centre line of the chain, fixed mouth -> U bend -> moving mouth (rackcfg chain_state), as
    at(s) -> (x, y) and its length."""
    fx, fy = CH["fixed"]
    mx, r = CH["moving_x"], CH["radius"]
    t = C["DRAWER_TRAVEL"] * open_frac
    my, b = CH["moving_y"] + C["DRAWER_Y0"] - t, CH["bend_y"] - t / 2
    cx = (fx + mx) / 2
    l1, la, l2 = b - fy, math.pi * r, b - my

    def at(s):
        if s <= l1:
            return fx, fy + s
        if s <= l1 + la:
            a = math.pi - (s - l1) / r
            return cx + r * math.cos(a), b + r * math.sin(a)
        return mx, b - (s - l1 - la)
    return at, l1 + la + l2


def chain_links(open_frac=0.0):
    """The links' placements (tray coordinates): pins along the centre line between the two end
    pieces' pivots, each link from its pin towards the next one."""
    at, L = chain_path(open_frac)
    e = CH["end_length"]
    n = max(1, round((L - 2 * e) / CH["pitch"]))
    pins = [at(e + k * (L - 2 * e) / n) for k in range(n + 1)]
    out = []
    for (x0, y0), (x1, y1) in zip(pins, pins[1:]):
        m = App.Matrix()
        m.rotateZ(math.atan2(y1 - y0, x1 - x0))
        m.move(V(x0, y0, CHAIN_Z - CHAIN_W / 2))
        out.append(m)
    return out


def bar_placed(out=0.0):
    """A link's removable bar (chain_parts.scad bar(), as printed) in its pockets on the link's +y
    side (the U's outside), or `out` mm outside them."""
    s = part("chain_bar").copy()
    s.rotate(V(0, 0, 0), V(1, 0, 0), 90)
    s.translate(V(LINK_MID0 + 0.1, LINK_R + out, LINK_T - POCKET))
    return s


def chain_shape(state="closed", open_frac=0.0):
    """The bought chain's links (Olimex 7 x 7, links open on both sides; drawn as chain_parts.scad's
    link at its size): "closed" with their bars, "open" without, "bars" the bars alone, pulled out."""
    sols = []
    for m in chain_links(open_frac):
        if state in ("closed", "open"):
            s = part("chain_link").copy()
            s.transformShape(m)
            sols.append(s)
        if state in ("closed", "bars"):
            s = bar_placed(0.0 if state == "closed" else 9.0)
            s.transformShape(m)
            sols.append(s)
    return Part.makeCompound(sols)


def chain_ends_shape(open_frac=0.0):
    """The two end pieces: rigid U channels, mouth -> pivot along +y, their tab (the U's outer wall,
    2 holes) against the anchor's inner face (fixed run, -x) and the foot's fin (moving run, +x)."""
    fx, fy = CH["fixed"]
    my = CH["moving_y"] + C["DRAWER_Y0"] - C["DRAWER_TRAVEL"] * open_frac
    z0, e = CHAIN_Z - CHAIN_W / 2, CH["end_length"]
    sols = []
    for x, y in ((fx, fy), (CH["moving_x"], my)):
        u = Part.makeBox(CHAIN_H, e, CHAIN_W, V(x - LINK_R, y, z0))
        u = u.cut(Part.makeBox(CH["inner"][0], e + 2, CHAIN_W, V(x - CH["inner"][0] / 2, y - 1, z0 + LINK_T)))
        for hy in end_holes(y):
            u = u.cut(Part.makeCylinder(1.3, CHAIN_H + 2, V(x - LINK_R - 1, hy, CHAIN_Z), V(1, 0, 0)))
        sols.append(u)
    return Part.makeCompound(sols)


def end_holes(mouth_y):
    return [mouth_y + CH["end_holes"][1] + k * CH["end_holes"][0] for k in (0, 1)]


def slot_y(w, h, y0, y1):
    """A w x h stadium (in xz, centred on the y axis) from y0 to y1."""
    r = h / 2
    s = Part.makeBox(w - h, y1 - y0, h, V(-(w - h) / 2, y0, -r))
    for x in (-(w - h) / 2, (w - h) / 2):
        s = s.fuse(Part.makeCylinder(r, y1 - y0, V(x, y0, 0), V(0, 1, 0)))
    return s.removeSplitter()


def rbox_y(w, h, r, y0, y1):
    """A w x h box (x, z) from y0 to y1, centred on the y axis, its 4 edges along y rounded by r."""
    b = Part.makeBox(w, y1 - y0, h, V(-w / 2, y0, -h / 2))
    if r < 0.05:
        return b
    return b.makeFillet(r, [e for e in b.Edges if abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) > 1e-6])


def plug_up(m, n, rot=0.0):
    """JST PH housing pushed down into a vertical header whose mouth is m (its lead leaves upwards)."""
    w = 2.0 * (n - 1) + 2.2
    s = Part.makeBox(w, 4.2, 7.0, V(-w / 2, -2.1, -5.1))
    s.rotate(V(0, 0, 0), V(0, 0, 1), rot)
    s.translate(m)
    return s


def data_port_ph():
    """The DATA port board's side-entry PH (node.py's parts/data_port.json), tray coordinates of its
    mouth and its opening's direction (towards the rear), drawer closed."""
    j = json.load(open(os.path.join(PARTS, "data_port.json")))
    c = j["ph"][0]
    x0 = C["DRAWER_X0"] + DATA["x"] - DATA["pcb"]["usb"]
    o = V(x0, C["DRAWER_Y0"] + DATA["wall_y"], C["PLENUM"] + DATA["pcb_z"])
    return o + V(*c["mouth"]), c["out"], c["pins"]


_lead_cache = {}


def data_lead_shape(part="full"):
    if part not in _lead_cache:
        _lead_cache[part] = _data_lead_shape(part)
    return _lead_cache[part]


def _data_lead_shape(part="full"):
    """The 5-wire PH DATA lead (tray coordinates): its plug in the node's vertical J7, up and into
    the chain's fixed mouth, along the chain, out of the moving mouth; "full": forwards, curled back
    and up through the drawer's cable window into the DATA board's PH from the rear; "free": its far
    plug left hanging (the bench, the tray); "stub": only its last bit, up through the window."""
    node = json.load(open(os.path.join(PARTS, "node.json")))
    j7 = next(c for c in node["ph"] if c["ref"] == "J7")            # the DATA header (vertical PH 5)
    o0 = V(C["NODE_X0"], C["NODE_FRONT_Y"], C["NODE_Z"])
    m7 = o0 + V(*j7["mouth"])
    fx, fy = CH["fixed"]
    mx = CH["moving_x"]
    at, L = chain_path()
    my = at(L)[1]
    pm, pout, pn = data_port_ph()
    end = pm + V(pout[0], pout[1], 0) * 1.9
    tail = [(mx, my - 9, CHAIN_Z + 1.5), (mx - 3, my - 14, CHAIN_Z + 7), (mx - 12, my + 6, C["PLENUM"] - 3),
            (end.x + 1.5, end.y + 4, C["PLENUM"] - 1), (end.x, end.y + 5, C["PLENUM"] + 4), (end.x, end.y + 3, end.z - 3),
            tuple(end)]
    if part == "stub":
        return Part.makeCompound([plug(pm, pout, pn), pipe([(end.x + 1.5, end.y + 4, C["PLENUM"] - 9)] + tail[4:], 1.8)])
    pts = [tuple(m7 + V(0, 0, 1.9)), tuple(m7 + V(0, 0, 9)), (fx, fy - 22, CHAIN_Z + 4), (fx, fy - 8, CHAIN_Z)]
    pts += [(x, y, CHAIN_Z) for x, y in (at(s) for s in [k * L / 24 for k in range(25)])]
    sols = [plug_up(m7, j7["pins"], j7.get("rot", 0.0))]
    if part == "free":
        pts += [(mx, my - 7, CHAIN_Z), (mx, my - 13.1, CHAIN_Z)]           # straight on out of the mouth
        sols.append(plug(V(mx, my - 15, CHAIN_Z), (0, 1), pn))
    else:
        pts += tail
        sols.append(plug(pm, pout, pn))
    return Part.makeCompound(sols + [pipe(pts, 1.8)])


def lead_alone_shape():
    """The DATA lead on its own (the parts pages): two PH 5 plugs, a sagging flat lead."""
    return Part.makeCompound([plug(V(-1.9, 0, 0), (1, 0), 5), plug(V(91.9, 0, 0), (-1, 0), 5)]
                             + lead(V(0, 0, 0), V(90, 0, 0), 5, 22.0))


def x_screw(x, y, z, head):
    """A fastener matrix with its head towards +x (head = 1) or -x (-1)."""
    return M([[0, 0, head, x], [0, 1, 0, y], [-head, 0, 0, z]])


def bay_chain_instances(inst, child, j, mt):
    """Bay j: the chain anchor (2 x M3 x 8 into the tray's inserts), the chain, its end pieces
    (2 x PT 2.6 x 8 and washers each, into the anchor and the foot's fin), the chain foot, the
    extension's cable, its panel socket (rides with the drawer, 2 x PT 2.6 x 8) and the foot's lock."""
    if not CH:
        return
    fx, fy = CH["fixed"]
    mx, my = CH["moving_x"], CH["moving_y"] + C["DRAWER_Y0"]
    z0 = CH["bottom"] + 3                                   # the anchor bosses' top
    x1 = fx - LINK_R                                        # the anchor's inner face = the fixed run's outer face
    inst[f"ca{j}"] = ("chain_anchor", mt.multiply(m_tr(fx, fy, z0)))
    child[f"ca{j}"] = []
    for n, y in enumerate((fy - 6 + 4, fy - 6 + 30 - 4)):    # lib/carrier.scad ANCHOR_BOSSES
        inst[f"i_ca{j}_{n}"] = ("insert", mt.multiply(m_tr(x1 - 4, y, z0)))
        child[f"tr{j}"].append((f"i_ca{j}_{n}", None, "follow"))
        inst[f"s_ca{j}_{n}"] = ("m3x8", mt.multiply(m_tr(x1 - 4, y, z0 + 3)))
        child[f"ca{j}"].append((f"s_ca{j}_{n}", NORMAL, "screw"))
    inst[f"ch{j}"] = ("chain", mt)
    inst[f"co{j}"] = ("chain_open", mt)
    inst[f"cb{j}"] = ("chain_bars", mt)
    inst[f"ce{j}"] = ("chain_ends", mt)
    inst[f"cx{j}"] = ("data_lead", mt)                     # the DATA lead, laid through the chain to the DATA board
    inst[f"cxf{j}"] = ("data_lead_free", mt)               # ... its far end still free (the bench, the tray)
    inst[f"dls{j}"] = ("data_lead_stub", mt)               # ... only its last bit, into the board (the drawer step)
    inst[f"cf{j}"] = ("chain_foot", mt.multiply(m_tr(mx, my, C["PLENUM"])))
    child[f"ce{j}"] = []
    for side, (x, mouth, head) in (("a", (x1 + LINK_B, fy, 1)), ("f", (mx + LINK_R - LINK_B, my, -1))):
        for n, y in enumerate(end_holes(mouth)):            # washer on the tab, the screw's head on it
            inst[f"w_ce{j}{side}{n}"] = ("w25", mt.multiply(x_screw(x, y, CHAIN_Z, head)))
            inst[f"s_ce{j}{side}{n}"] = ("pt26x8", mt.multiply(x_screw(x + head * 0.5, y, CHAIN_Z, head)))
            child[f"ce{j}"] += [(f"w_ce{j}{side}{n}", None, "follow"), (f"s_ce{j}{side}{n}", None, "follow")]
    dmt = mt.multiply(m_tr(C["DRAWER_X0"], C["DRAWER_Y0"], C["PLENUM"]))   # drawer coordinates
    # the DATA port board on its two bosses, components up, its front edge on the port wall's back face
    dp, x0 = DATA["pcb"], DATA["x"] - DATA["pcb"]["usb"]
    inst[f"dp{j}"] = ("data_port", dmt.multiply(m_tr(x0, DATA["wall_y"], DATA["pcb_z"])))
    child[f"dr{j}"].append((f"dp{j}", None, "follow"))
    for n, (hx, hy) in enumerate(dp["holes"]):              # 2 x PT 2.6 x 8 from above into the bosses
        inst[f"s_dp{j}_{n}"] = ("pt26x8", dmt.multiply(m_tr(x0 + hx, DATA["wall_y"] + dp["size"][1] - hy,
                                                           DATA["pcb_z"] + dp["thickness"])))
        child[f"dr{j}"].append((f"s_dp{j}_{n}", None, "follow"))
    # the foot lock: PT 2.6 x 8 from inside the rear bay (on its boss), down into the foot's tongue
    inst[f"s_cf{j}"] = ("pt26x8", dmt.multiply(m_tr(mx - C["DRAWER_X0"], CH["foot_y"], C["DRAWER_BOTTOM"] + 4)))
    child[f"dr{j}"].append((f"s_cf{j}", NORMAL, "own"))


# ------------------------------------------------------------------ the power box (run.py: rackcfg power_box())
PB = C.get("POWER_BOX")
CHARGER = (66.0, 66.0, 30.0)                  # a 140 W PD 3.1 charger, lying on the desk behind the rack


PIPE_PLAIN = False                             # check.py: True, cables as cylinders and balls (no sweeps, no fuse)


def pipe(points, r):
    """A round cable through `points` (frame), as a smooth spline: one sweep, or a few swept end to
    end and fused (tangent joints: the projection draws no line there).  A swept solid's BoundBox
    is loose (its poles): see tight_center."""
    c = Part.BSplineCurve()
    c.interpolate([V(*p) for p in points])
    e = c.toShape()
    if PIPE_PLAIN:                            # SolidCraft intersects swept splines too slowly: plain tubes
        return Part.makeCompound(tube(e, r))

    def sweep(cu):                            # a sweep can fail quietly: check its volume
        se = cu.toShape()
        prof = Part.Wire(Part.makeCircle(r, se.valueAt(se.FirstParameter), se.tangentAt(se.FirstParameter)))
        for frenet in (True, False):
            try:
                s = Part.Wire(se).makePipeShell([prof], True, frenet)
                if s.isValid() and abs(s.Volume / (math.pi * r * r * se.Length) - 1) < 0.03:
                    return s
            except Part.OCCError:
                pass
    a, b = c.FirstParameter, c.LastParameter
    for k in (1, 2, 3, 6):
        pieces = []
        for t0, t1 in ((a + (b - a) * i / k, a + (b - a) * (i + 1) / k) for i in range(k)):
            seg = c.copy()
            seg.segment(t0, t1)
            pieces.append(sweep(seg))
            if not pieces[-1]:
                break
        if all(pieces):
            return pieces[0].multiFuse(pieces[1:]) if k > 1 else pieces[0]
    # last resort: short cylinders fused with a ball at every joint (creases on the inner side of
    # each joint: a corrugated look)
    sols = tube(e, r)
    return sols[0].multiFuse(sols[1:])


def tube(e, r):
    """A cable along the edge e as short cylinders and a ball at every joint."""
    pts = e.discretize(Distance=4.0)
    sols = [Part.makeCylinder(r, (b - a).Length, a, b - a) for a, b in zip(pts, pts[1:]) if (b - a).Length > 1e-6]
    return sols + [Part.makeSphere(r, p) for p in pts[1:-1]]


UP = (C.get("USB_PLUGS") or {}).get("usb-c") or dict(SW=8.3, SH=2.5, SL=6.65, W=12.4, H=7.0, L=20, REL=8, RD=[5.4, 4.2])


def usbc_plug(m, out):
    """Straight USB-C plug (tools/webscene.py USB_PLUGS, as mechanical/parts/usb_plugs.scad draws it)
    in a receptacle whose mouth is m, the cable leaving along `out` (unit, frame): the metal shell
    inside, the rounded overmold and its strain relief outside.  Returns (solids, cable start)."""
    o = V(*out)
    up = V(0, 0, 1)
    side = o.cross(up)
    p = UP
    parts = [slot_y(p["SW"], p["SH"], -p["SL"], 0),                       # local y along `out`, x along `side`
             rbox_y(p["W"], p["H"], min(p["H"] / 2 - 0.1, 3), 0, p["L"]),
             Part.makeCone(p["RD"][0] / 2, p["RD"][1] / 2, p["REL"], V(0, p["L"], 0), V(0, 1, 0))]
    sols = []
    for s in parts:
        s = s.copy()
        s.transformShape(App.Matrix(side.x, o.x, up.x, m[0], side.y, o.y, up.y, m[1], side.z, o.z, up.z, m[2], 0, 0, 0, 1))
        sols.append(s)
    return sols, V(*m) + o * (p["L"] + p["REL"])


def spacer_shape():
    """M3 male-female hex spacer, 12 mm (5.5 across flats) + a 6 mm stud: its seat (the hub's top) at z = 0."""
    r = 3.2
    hexw = Part.Face(Part.makePolygon([V(r * math.cos(math.radians(60 * k)), r * math.sin(math.radians(60 * k)), 0)
                                       for k in range(7)]))
    body = hexw.extrude(V(0, 0, 12)).cut(Part.makeCylinder(1.25, 5, V(0, 0, 7.01)))
    return body.fuse(Part.makeCylinder(1.5, 6, V(0, 0, -6))).removeSplitter()


def charger_shape():
    """The charger, its USB-C port on the face towards the rack (-y)."""
    w, d, h = CHARGER
    b = Part.makeBox(w, d, h)
    b = b.makeFillet(5.0, b.Edges)
    return b.cut(Part.makeBox(9.0, 6.0, 3.4, V(w / 2 - 4.5, -0.1, h / 2 - 1.7)))


def charger_at():
    """Front-left-bottom corner of the charger: on the desk, behind the rack, right of the box's port."""
    x, y, z = PB["pd"]
    return V(x - CHARGER[0] / 2 + 25.0, C["PR"] + 120.0, 0.0)


def pd_cable_shape():
    """The charger's USB-C cable: into the box's rear port, out of the back to the charger."""
    x, y, z = PB["pd"]
    a, ea = usbc_plug((x, y, z), (0, 1, 0))
    ch = charger_at()
    port = (ch.x + CHARGER[0] / 2, ch.y, CHARGER[2] / 2)
    b, eb = usbc_plug(port, (0, -1, 0))
    mid = [(x, C["PR"] + 30.0, z), (x + 8.0, C["PR"] + 70.0, 8.0)]
    return Part.makeCompound(a + b + [pipe([tuple(ea)] + mid + [tuple(eb)], 2.0)])


def feed_shape(row=0):
    """A row feed: from the hub's row connector out through the left base ladder's window,
    forward and up the rack's outer face, in through the row's jumper window to the first node's
    J1 (notice.yaml row_cable `to`).  JST PH plugs at both ends."""
    hub = json.load(open(os.path.join(PARTS, "hub.json")))
    hx, hy, hz = PB["hub"]
    hl = PB["hub_pcb"]["size"][1]
    k = PB["hub_pcb"]["rows"][row]                 # KiCad y of the row's connector
    c = min(hub["ph"], key=lambda e: abs((hl - e["mouth"][1]) - k))
    ma = V(hx + c["mouth"][0], hy - hl + c["mouth"][1], hz + c["mouth"][2])
    _, cb = row_cable()
    mt = m_row(row, T + CL)
    o0 = V(C["NODE_X0"], C["NODE_FRONT_Y"], C["NODE_Z"])
    plug_b = plug(o0 + V(*cb["mouth"]), cb["out"], cb["pins"])
    plug_b.transformShape(mt)
    mb = mt.multVec(o0 + V(*cb["mouth"]) + V(cb["out"][0], cb["out"][1], 0) * 1.9)
    lane = -4.0
    a = ma + V(-1.9, 0, 0)
    pts = [a, (a.x - 4, a.y, a.z), (lane, a.y, a.z), (lane, a.y - 10, a.z + 6), (lane, mb.y, mb.z - 25),
           (lane, mb.y, mb.z - 6), (lane + 4, mb.y, mb.z), mb]
    return Part.makeCompound([plug(ma, c["out"], c["pins"]), plug_b,
                              pipe([tuple(p) if not isinstance(p, tuple) else p for p in pts], 1.4)])


def power_box_instances(inst, child):
    if not PB:
        return
    hub = PB["hub_pcb"]
    ox, oy, oz = PB["origin"]
    W, D, H = PB["size"]
    t = PB["wall"]
    hx, hy, hz = PB["hub"]
    hl = hub["size"][1]
    inst["pb"] = ("power_box_base", m_tr(ox, oy, oz))
    inst["pl"] = ("power_box_lid", m_tr(ox, oy, oz))
    inst["hb"] = ("hub", m_tr(hx, hy - hl, hz))     # board frame: front-left corner at the origin
    child["pb"], child["hb"], child["pl"] = [], [], []
    for n, (kx, ky) in enumerate(hub["holes"]):    # inserts in the standoffs; hex spacers through the hub; the lid's M3 x 6 into them
        inst[f"i_pb_{n}"] = ("insert", m_tr(hx + kx, hy - ky, hz))
        child["pb"].append((f"i_pb_{n}", None, "follow"))
        inst[f"sp_hb_{n}"] = ("spacer", m_tr(hx + kx, hy - ky, hz + hub["thickness"]))
        child["hb"].append((f"sp_hb_{n}", (0, 0, 1), "screw"))
        inst[f"s_pl_{n}"] = ("m3x6", m_tr(hx + kx, hy - ky, oz + H))
        child["pl"].append((f"s_pl_{n}", (0, 0, 1), "screw"))
    inst["charger"] = ("charger", m_tr(*charger_at()))
    inst["xtl"] = ("lead_alone", m_tr(0, 0, 0))       # the DATA lead on its own, for the parts pages
    inst["dpx"] = ("data_port", m_tr(0, 0, 0))        # the DATA port board on its own
    inst["dcx"] = ("chain_full", m_tr(0, 0, 0))       # the chain with its end pieces, for the parts pages
    inst["pdc"] = ("pd_cable", m_tr(0, 0, 0))
    inst["feed"] = ("feed", m_tr(0, 0, 0))


def R_to(axis):
    """Rotation taking local +Z to a frame axis ('y' = +Y, 'z' = +Z)."""
    if axis == "y":
        return M([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0]])
    return M([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]])


NORMAL = (0.0, -math.sin(TILT), math.cos(TILT))     # tray normal (frame), the node's screws' axis
FAST = {  # kind: (Fasteners type, diameter, length or None, screw length for the dashed axis)
    "m3x8": ("ISO7045", "M3", "8", 8), "m3x6": ("ISO7045", "M3", "6", 6), "m25x8": ("ISO7045", "M2.5", "8", 8),
    "m25x6": ("ISO7045", "M2.5", "6", 6),
    "pt26x8": ("ISO7045", "M2.5", "8", 8),           # PT 2.6 x 8 thread-forming: drawn as an M2.5 x 8
    "w25": ("ISO7089", "M2.5", None, 0),              # DIN 125 / ISO 7089 washer
    "insert": ("IUTHeatInsert", "M3", None, 0),
}


def node_holes_carrier():
    """The node's M3 holes (config/rack.yaml pcb.bay_node.holes, KiCad y from the rear edge), carrier coordinates."""
    return [(C["NODE_X0"] + x, C["NODE_FRONT_Y"] + (C["NODE_SIZE"][1] - y)) for x, y in C["NODE_HOLES"]]


# ------------------------------------------------------------------ the scene (same ids as renderer/manual_build.py)
def instances():
    """INST[id] = (kind, matrix); CHILD[parent] = [(id, approach direction | None, mode)]:
    mode "follow": moves with its parent (inserts), "screw": parent offset + gap along the
    direction, "own": its own approach (gap along the direction) whenever the parent moves."""
    inst, child = {}, {}
    for i in range(3):
        inst[f"lb{i}"] = ("ladder_base", m_ladder(i * P))
        inst[f"la{i}"] = ("ladder_a", m_ladder(i * P))
        inst[f"lc{i}"] = ("ladder_cap1", m_ladder(i * P))
        for lid, k in ((f"lb{i}", -1), (f"la{i}", 0)):     # heat-set inserts in each rear edge
            child[lid] = []
            for n, zz in enumerate(brace_z(k)):
                iid = f"i_{lid}_{n}"
                inst[iid] = ("insert", m_tr(i * P + T / 2, PR, zz).multiply(R_to("y")))
                child[lid].append((iid, None, "follow"))
    for j in range(2):
        x0 = j * P + T + CL
        mt = m_row(0, x0)
        inst[f"fp{j}"] = ("floor_plate", m_tr(x0, C["FLOOR_Y0"], 0))
        inst[f"tr{j}"] = ("tray", mt)
        inst[f"dr{j}"] = ("drawer_light", mt.multiply(m_tr(C["DRAWER_X0"], C["DRAWER_Y0"], C["PLENUM"])))
        inst[f"cp{j}"] = ("cap_plate", m_row(1, x0))
        inst[f"bb{j}"] = ("brace_base", m_brace(j * P + T / 2))
        inst[f"ba{j}"] = ("brace_a", m_brace(j * P + T / 2))
        inst[f"nd{j}"] = ("node", mt.multiply(m_tr(C["NODE_X0"], C["NODE_FRONT_Y"], C["NODE_Z"])))
        child[f"tr{j}"], child[f"nd{j}"] = [], []
        for n, (x, y) in enumerate(node_holes_carrier()):
            iid = f"i_tr{j}_{n}"                             # inserts in the tray's node standoffs
            inst[iid] = ("insert", mt.multiply(m_tr(x, y, C["NODE_Z"])))
            child[f"tr{j}"].append((iid, None, "follow"))
            sid = f"s_nd{j}_{n}"                             # M3 x 6 through the node into them
            inst[sid] = ("m3x6", mt.multiply(m_tr(x, y, C["NODE_Z"] + 1.6)))
            child[f"nd{j}"].append((sid, NORMAL, "screw"))
        # drawer end stop: M2.5 x 8 through the left guide lip, put in once the drawer is in
        inst[f"s_dr{j}"] = ("m25x8", mt.multiply(m_tr(C["DRAWER_X0"] - 3 / 2 - 0.2, (196 - 26) - C["DRAWER_TRAVEL"] - 4.5, 28.5)))
        child[f"dr{j}"] = [(f"s_dr{j}", NORMAL, "own")]
        bay_chain_instances(inst, child, j, mt)
        for bid, k in ((f"bb{j}", -1), (f"ba{j}", 0)):      # brace screws, into the rear-edge inserts
            z = brace_z(k)
            xl, xr = j * P + T / 2, (j + 1) * P + T / 2
            child[bid] = []
            for n, (x, zz) in enumerate(((xl, z[0]), (xl, z[2]), (xr, z[1]), (xr, z[3]))):
                sid = f"s_{bid}_{n}"
                inst[sid] = ("m3x8", m_tr(x, PR + BT, zz).multiply(R_to("y")))
                child[bid].append((sid, (0, 1, 0), "screw"))
    inst["jumper"] = ("jumper", m_row(0, T + CL))
    power_box_instances(inst, child)
    return inst, child


INST, CHILD = instances()


def shape_of(iid):
    name, m = INST[iid]
    if name in FAST:
        f = FAST[name]
        s = fastener_z(f[0], f[1], f[2])
    elif name == "node":
        s = node_shape()
    elif name == "jumper":
        s = jumper_shape()
    elif name in ("chain", "chain_open", "chain_bars"):
        s = chain_shape({"chain": "closed", "chain_open": "open", "chain_bars": "bars"}[name])
    elif name == "chain_full":
        s = Part.makeCompound([chain_shape("closed"), chain_ends_shape()])
    elif name == "chain_ends":
        s = chain_ends_shape()
    elif name in ("data_lead", "data_lead_free", "data_lead_stub"):
        s = data_lead_shape({"data_lead": "full", "data_lead_free": "free", "data_lead_stub": "stub"}[name])
    elif name == "lead_alone":
        s = lead_alone_shape()
    elif name == "data_port":
        s = part("data_port")
    elif name == "spacer":
        s = spacer_shape()
    elif name == "charger":
        s = charger_shape()
    elif name == "pd_cable":
        s = pd_cable_shape()
    elif name == "feed":
        s = feed_shape()
    else:
        s = part(name)
    s = s.copy()
    s.transformShape(m)
    return s


def seat_point(iid):
    m = INST[iid][1]
    return V(m.A14, m.A24, m.A34)


def seat_axis(iid):
    """The fastener's head direction (its local +Z) in the frame."""
    m = INST[iid][1]
    return V(m.A13, m.A23, m.A33)


def expand(step):
    """Bring each part's inserts and screws along: old -> old in place; new -> kind and offset per CHILD."""
    old = list(step["old"])
    add = dict(step["add"])
    gap = step.get("screw_gap", 45)
    for pid in list(step["old"]):
        for cid, _, _ in CHILD.get(pid, []):
            if cid not in add:
                old.append(cid)
    for pid, o in list(step["add"].items()):
        moving = math.sqrt(sum(x * x for x in o)) > 1
        for cid, d, mode in CHILD.get(pid, []):
            if cid in add or cid in old:
                continue
            if mode == "follow" or not moving:
                add[cid] = o
            elif mode == "screw":
                add[cid] = tuple(o[i] + d[i] * gap for i in range(3))
            else:
                add[cid] = tuple(d[i] * step.get("own_gap", 22) for i in range(3))
    hide = step.get("hide", ())                 # parts not there yet in this step (screws put in later)
    return [i for i in old if i not in hide], {i: o for i, o in add.items() if i not in hide}


def u_(k):
    return tuple(k * c for c in U)


def n_(k):
    return tuple(k * c for c in NORMAL)


def plus(*vs):
    return tuple(sum(v[i] for v in vs) for i in range(3))


# ------------------------------------------------------------------ steps
ISO, REAR, ISO_R = (-0.95, -1.45, 0.95), (-0.9, 1.5, 0.85), (0.95, -1.45, 0.95)
CHAIN0, CHAIN1 = ["ca0", "ch0", "ce0", "cf0", "cx0"], ["ca1", "ch1", "ce1", "cf1", "cx1"]   # anchor, chain, end pieces, foot, extension
BAY0 = ["lb0", "lb1", "fp0", "bb0", "la0", "la1", "tr0", "nd0", "ba0", "lc0", "lc1", "cp0"] + CHAIN0 + ["dr0"]
BAY1 = ["lb2", "fp1", "bb1", "la2", "tr1", "nd1", "jumper", "ba1", "lc2", "cp1"] + CHAIN1 + ["dr1"]
A = lambda *ids: list(ids)
STEPS = {
    "cover": {"view": ISO, "old": [], "add": {i: (0, 0, 0) for i in BAY0}, "slot": "cover"},
    "a1": {"view": ISO, "old": [], "add": {"lb0": (0, 0, 0), "lb1": (0, 0, 0)}},
    "a2": {"view": ISO, "old": A("lb0", "lb1"), "add": {"fp0": (0, -120, 0)}, "clic": True},
    "a3": {"view": REAR, "old": A("lb0", "lb1", "fp0"), "add": {"bb0": (0, 80, 0)}, "screw_gap": 45, "detail": True},
    "pin": {"view": (0.8, 1.2, 0.55), "old": A("lb1"), "add": {"bb0": (0, 12, 0)}, "screw_gap": 16,
            "focus": {"at": (P + T / 2, PR + 16, 47), "size": 34}, "arrows": False},
    "a4": {"view": ISO, "old": A("lb0", "lb1", "fp0", "bb0"), "add": {"la0": (0, 0, 70), "la1": (0, 0, 70)}, "clic": True, "detail": True},
    "hook": {"view": (-1, -0.35, 0.3), "old": A("lb0"), "add": {"la0": (0, 0, 13)},
             "focus": {"at": (0, 25 + 45 * math.cos(TILT), 80 + 45 * math.sin(TILT) + 5), "size": 40}, "arrows": False},
    "a5": {"view": ISO, "old": A("lb0", "lb1", "fp0", "bb0", "la0", "la1"), "add": {"tr0": u_(-150)}, "clic": True},
    "a6": {"view": REAR, "old": A("lb0", "lb1", "fp0", "bb0", "la0", "la1", "tr0"), "add": {"ba0": (0, 80, 0)}, "screw_gap": 45},
    "a7": {"view": ISO, "old": A("lb0", "lb1", "fp0", "bb0", "la0", "la1", "tr0", "ba0"),
           "add": {"lc0": (0, 0, 55), "lc1": (0, 0, 55), "cp0": plus(u_(-150), (0, 0, 55))}, "clic": True},
    "a8": {"view": (0.5, -1.2, 1.6), "old": A("lb0", "lb1", "fp0", "bb0", "la0", "la1", "tr0", "ba0", "lc0", "lc1", "cp0"),
           "add": {"nd0": n_(32)}, "screw_gap": 16, "frame": {"at": (98, 100, 125), "size": 320}},
    # at the bench: the end pieces onto the anchor and the foot's fin (PT 2.6 x 8 + washer, from inside the U)
    "a9b": {"view": (-0.35, -0.9, 1.5), "old": [], "add": {"ca0": (0, 0, 0), "cf0": (0, 0, 0), "ch0": (0, 0, 0), "ce0": (0, 0, 0),
            **{f"{k}_ce0{sd}{n}": ((g if sd == "a" else -g), 0, 0) for k, g in (("s", 12), ("w", 7)) for sd in "af" for n in (0, 1)}},
            "hide": ["s_ca0_0", "s_ca0_1"], "arrows": False,
            "frame": {"at": tuple(m_row(0, T + CL).multVec(V(115, 132, 8))), "size": 250}},
    # open the links, lay the extension's cable in, close them
    "a10o": {"view": (-1.1, -0.7, 0.75), "old": A("ca0", "cf0", "ce0", "co0"), "add": {"cb0": (0, 0, 0), "cxf0": (0, 0, 0)},
             "hide": ["s_ca0_0", "s_ca0_1"], "frame": {"at": tuple(m_row(0, T + CL).multVec(V(112, 135, 10))), "size": 270}},
    # into the tray: the anchor's 2 x M3 x 8, the plug in the node
    "a11t": {"view": (0.5, -1.2, 1.6), "old": A("lb0", "lb1", "fp0", "bb0", "la0", "la1", "tr0", "ba0", "nd0"),   # no cap: into the tray
             "add": {i: n_(22) for i in ("ca0", "ch0", "ce0", "cf0", "cxf0")}, "screw_gap": 16, "arrow_ids": ["ch0"],
             "frame": {"at": tuple(m_row(0, T + CL).multVec(V(105, 140, 10))), "size": 340}},
    # the drawer's DATA socket: through the port wall from the front, 2 x PT 2.6 x 8
    # the drawer's DATA board: on its bosses, 2 x PT 2.6 x 8 from above; the lead up through the window into its PH
    "a12s": {"view": (0.35, 1.1, 1.5), "old": A("dr0"), "add": {"dp0": n_(25), "s_dp0_0": n_(42), "s_dp0_1": n_(42), "dls0": (0, 0, 0)},
             "hide": ["s_dr0", "s_cf0"], "screw_gap": 0,
             "frame": {"at": tuple(m_row(0, T + CL).multVec(V(C["DRAWER_X0"] + DATA["x"] - 12, C["DRAWER_Y0"] + DATA["wall_y"] + 10,
                                                                  C["PLENUM"] + DATA["pcb_z"] + 12))), "size": 200}},
    "a9": {"view": ISO_R, "old": [i for i in BAY0 if i != "dr0"], "add": {"dr0": u_(-170)}, "slot": "single", "own_gap": 26},
    "b1": {"view": ISO_R, "old": BAY0, "add": {"lb2": (90, 0, 0), "fp1": (0, -120, 0)}, "clic": True},
    "b2": {"view": (0.9, 1.5, 0.85), "old": BAY0 + A("lb2", "fp1"), "add": {"bb1": (0, 80, 0)}, "screw_gap": 45, "detail": True},
    "pin_b": {"view": (0.45, 1.2, 0.5), "old": A("lb1", "bb0"), "add": {"bb1": (0, 12, 0)}, "screw_gap": 16,
              "focus": {"at": (P + T / 2, PR + 14, 39), "size": 44}, "arrows": False},
    "b3": {"view": ISO_R, "old": BAY0 + A("lb2", "fp1", "bb1"), "add": {"la2": (0, 0, 70), "tr1": u_(-150)}, "clic": True},
    "b3n": {"view": (0.5, -1.2, 1.6), "old": BAY0 + A("lb2", "fp1", "bb1", "la2", "tr1"), "add": {"nd1": n_(40)}, "screw_gap": 16, "frame": {"at": (205, 95, 125), "size": 300}},
    "b4": {"view": (0.15, -0.55, 1.9), "old": [i for i in BAY0 if i not in ("cp0", "lc0", "lc1", "dr0")] + A("lb2", "fp1", "bb1", "la2", "tr1", "nd1"),
           "add": {"jumper": (0, 0, 0)}, "frame": {"at": (126, 62, 100), "size": 300}},
    "b5a": {"view": ISO_R, "old": BAY0 + A("lb2", "fp1", "bb1", "la2", "tr1", "nd1", "jumper"),
            "add": {"ba1": (0, 80, 0), "lc2": (0, 0, 55), "cp1": plus(u_(-150), (0, 0, 55))}, "screw_gap": 45, "clic": True},
    "b5": {"view": ISO_R, "old": BAY0 + A("lb2", "fp1", "bb1", "la2", "tr1", "nd1", "jumper", "ba1", "lc2", "cp1"),
           "add": {"dr1": u_(-170), **{i: (0, 0, 0) for i in CHAIN1}}, "slot": "single", "own_gap": 26},
    "done": {"view": ISO_R, "old": [], "add": {i: (0, 0, 0) for i in BAY0 + BAY1}, "slot": "done"},
}
if PB:                                  # the power box, under A1
    BOX = ["pb", "hb", "pl"]
    _o, _s, _pd = PB["origin"], PB["size"], PB["pd"]
    _bc = (_o[0] + _s[0] / 2, _o[1] + _s[1] / 2, _o[2] + _s[2] / 2)
    _top = (0.55, -1.0, 1.5)
    STEPS.update({
        "c0": {"view": _top, "old": A("pb"), "add": {f"i_pb_{n}": (0, 0, 25) for n in range(4)}, "arrows": False},
        "c1": {"view": _top, "old": A("pb"), "add": {"hb": (0, 0, 45)}, "screw_gap": 18},
        "c2": {"view": _top, "old": A("pb", "hb"), "add": {"pl": (0, 0, 45)}, "screw_gap": 18},
        "c3": {"view": (-0.95, -1.45, 0.5), "old": BAY0, "add": {i: (0, -150, 30) for i in BOX}, "screw_gap": 0,
               "arrow_ids": ["pb"], "frame": {"at": (_bc[0] + 40, _bc[1] - 50, 70), "size": 380}},
        "c4": {"view": REAR, "old": BAY0 + BOX, "add": {"pdc": (0, 40, 0), "charger": (0, 40, 0)},
               "arrow_ids": ["pdc"], "frame": {"at": (_pd[0] + 10, PR + 85, 35), "size": 370}},
        "c5": {"view": (-1.4, -0.8, 0.6), "old": BAY0 + BOX, "add": {"feed": (0, 0, 0)},
               "frame": {"at": (20, 110, 75), "size": 330}},
        "c_done": {"view": ISO, "old": [], "add": {i: (0, 0, 0) for i in BAY0 + BOX + ["feed"]},
                   "slot": "done"},
    })



# ------------------------------------------------------------------ projection
class View:
    """TechDraw's 2D frame for a view direction, and the turn that puts frame Z up."""
    def __init__(self, d):
        self.d = V(*d)
        imgs = []
        for ax in (V(100, 0, 0), V(0, 100, 0), V(0, 0, 100)):
            e = TechDraw.projectEx(Part.makeLine(V(0, 0, 0), ax), self.d)[0].Edges[0]
            a, b = e.Vertexes[0].Point, e.Vertexes[1].Point
            if a.Length > b.Length:
                a, b = b, a
            imgs.append(((b.x - a.x) / 100, (b.y - a.y) / 100))
        self.ex = V(imgs[0][0], imgs[1][0], imgs[2][0])     # 2D x = p . ex
        self.ey = V(imgs[0][1], imgs[1][1], imgs[2][1])     # 2D y = p . ey
        # mirrored?  (a proper view has ex x ey along the direction towards the viewer)
        self.mx = -1 if self.ex.cross(self.ey).dot(self.d) < 0 else 1
        zx, zy = self.mx * self.ex.z, self.ey.z
        self.rot = math.atan2(zx, zy)                     # turn so that Z points up

    def screen(self, x, y):
        """TechDraw 2D -> screen (x right, y up), unscaled."""
        x *= self.mx
        c, s = math.cos(self.rot), math.sin(self.rot)
        return (c * x - s * y, s * x + c * y)

    def point(self, p):
        return self.screen(p.dot(self.ex), p.dot(self.ey))


def polylines(shape, defl):
    out = []
    for e in shape.Edges:
        try:
            pts = e.discretize(Deflection=defl)
        except Exception:
            continue
        if len(pts) >= 2:
            out.append([(p.x, p.y) for p in pts])
    return out


def visible(r):
    return [c for c in (r[0], r[3]) if c is not None and not c.isNull()]



def tight_center(s):
    """The centre of a shape's box; the exact box where BoundBox is much looser (swept cables)."""
    bb = s.BoundBox
    ob = s.optimalBoundingBox(False)
    if bb.DiagonalLength > ob.DiagonalLength + 1.0:
        bb = ob
    return V((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, (bb.ZMin + bb.ZMax) / 2)


def step_scene(step):
    """Items (id, old|add, shape, is_fastener), dashed screw axes and motion arrows of a step."""
    old, add = expand(step)
    fast = lambda iid: INST[iid][0] in FAST
    items = [(iid, "old", shape_of(iid), fast(iid)) for iid in old]
    for iid, o in add.items():
        s = shape_of(iid)
        s.translate(V(*o))
        items.append((iid, "add", s, fast(iid)))
    axes = []                               # from the screw tip (approach position) into its hole
    for iid, o in add.items():
        L = FAST.get(INST[iid][0], (0, 0, 0, 0))[3]
        if L and math.sqrt(sum(x * x for x in o)) > 1:
            seat, ax = seat_point(iid), seat_axis(iid)
            axes.append(Part.makeLine(seat + V(*o) - ax * (L + 0.2), seat - ax * (L - 2.5)))
    arrows = []                             # from the approach position towards the seat
    if step.get("arrows", True):
        shp = {i: s for i, _, s, _ in items}
        for iid, o in step["add"].items():
            if "arrow_ids" in step and iid not in step["arrow_ids"]:
                continue
            L = math.sqrt(sum(x * x for x in o))
            if L < 1:
                continue
            c = tight_center(shp[iid])
            dv = V(*o).normalize() * -1
            Ls = min(L * 0.9, 130)
            s0 = c - dv * (Ls * 0.5)
            arrows.append((s0, s0 + dv * Ls))
    return items, axes, arrows


def fit(scr, arr2, W, H, pad, keepout):
    """Largest scale (and an offset as central as possible) that fits the slot and keeps the
    drawing out of the page's overlays: keepout = [("circle", cx, cy, r) | ("rect", x0, y0, x1, y1)] in px."""
    import numpy as np
    pl = [p for v in scr.values() for p in v] + [list(a) for a in arr2]
    xs = [x for p in pl for x, _ in p]
    ys = [y for p in pl for _, y in p]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k0 = min((W - 2 * pad) / max(x1 - x0, 1e-6), (H - 2 * pad) / max(y1 - y0, 1e-6))
    centred = lambda k: (W / 2 - (x1 + x0) / 2 * k, H / 2 + (y1 + y0) / 2 * k)
    if not keepout:
        return (k0,) + centred(k0)
    # densify every line to ~2 px at the full scale
    pts = []
    for p in pl:
        a = np.array(p, float)
        if len(a) < 2:
            continue
        seg = np.diff(a, axis=0)
        n = np.maximum(1, np.ceil(np.hypot(seg[:, 0], seg[:, 1]) * k0 / 2).astype(int))
        for (sx, sy), (dx, dy), m in zip(a[:-1], seg, n):
            t = np.arange(m) / m
            pts.append(np.stack([sx + dx * t, sy + dy * t], 1))
        pts.append(a[-1:])
    D = np.concatenate(pts)
    for k in k0 * 0.97 ** np.arange(0, 40):
        PX, PY = D[:, 0] * k, -D[:, 1] * k                        # px, before the offset
        ox_r = (pad - PX.min(), W - pad - PX.max())
        oy_r = (pad - PY.min(), H - pad - PY.max())
        cx0, cy0 = centred(k)
        best = None
        for ox in np.linspace(*ox_r, 41):
            for oy in np.linspace(*oy_r, 31):
                ok = True
                for ko in keepout:
                    if ko[0] == "circle":
                        _, cx, cy, r = ko
                        if (((PX + ox - cx) ** 2 + (PY + oy - cy) ** 2) < r * r).any():
                            ok = False
                            break
                    else:
                        _, rx0, ry0, rx1, ry1 = ko
                        if ((PX + ox > rx0) & (PX + ox < rx1) & (PY + oy > ry0) & (PY + oy < ry1)).any():
                            ok = False
                            break
                if ok:
                    d = (ox - cx0) ** 2 + (oy - cy0) ** 2
                    if best is None or d < best[0]:
                        best = (d, ox, oy)
        if best:
            log("fit", f"scale {k / k0:.2f} of the full fit")
            return k, best[1], best[2]
    return (k0,) + centred(k0)


KEYS = {("old", False): "old", ("old", True): "old_f", ("add", False): "add", ("add", True): "add_f"}
CACHE = os.path.join(OUT, "cache")


def project(name, items, view_dir, axes=(), arrows=(), focus=None):
    """One hidden-line projection of everything; each visible edge given to its part.
    Returns (and caches) screen polylines (mm, x right, y up) per layer, arrows and focus."""
    from shapely.geometry import MultiLineString, Point
    t0 = time.time()
    view = View(view_dir)
    comp = Part.makeCompound([s for _, _, s, _ in items] + list(axes))
    r = TechDraw.projectEx(comp, view.d)
    vis = [e for c in visible(r) for e in c.Edges]
    log(name, "projected", len(vis), "edges", f"{time.time() - t0:.1f}s")
    # whose edge is it?  every part's own projection, its polylines in one spatial index
    import numpy as np
    import shapely
    from shapely import STRtree, LineString
    geoms, gkey, gadd = [], [], []
    for iid, kind, s, fast in items:
        ri = TechDraw.projectEx(s, view.d)
        for p in (p for c in visible(ri) for p in polylines(c, 0.01)):
            geoms.append(LineString(p))
            gkey.append(KEYS[(kind, fast)])
            gadd.append(kind == "add")
    geoms, gadd = np.array(geoms, dtype=object), np.array(gadd)
    tree = STRtree(geoms)
    axl = None
    if axes:
        axl = MultiLineString([[(p.x, p.y) for p in TechDraw.projectEx(a, view.d)[0].Edges[0].discretize(2)] for a in axes])
    layers = {}
    edges, mids = [], []
    for e in vis:
        pts = polylines(e, 0.01)
        if not pts:
            continue
        mid = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
        if axl is not None and all(axl.distance(Point(p[0], p[1])) < 0.02 for p in (pts[0][0], (mid.x, mid.y), pts[-1][-1])):
            layers.setdefault("dash", []).extend(pts)          # a piece of a screw axis (all of it on the axis)
            continue
        edges.append(pts)
        mids.append((mid.x, mid.y))
    P = shapely.points(np.array(mids)) if mids else np.array([])
    best = np.full(len(mids), 1e9)
    owner = np.full(len(mids), -1)
    if len(mids):
        ii, jj = tree.query(P, predicate="dwithin", distance=0.08)
        if len(ii):
            d = shapely.distance(P[ii], geoms[jj]) - np.where(gadd[jj], 0.002, 0.0)   # ties go to the new part
            order = np.lexsort((d, ii))
            ii, jj, d = ii[order], jj[order], d[order]
            first = np.r_[True, ii[1:] != ii[:-1]]
            best[ii[first]], owner[ii[first]] = d[first], jj[first]
        miss = np.where(owner < 0)[0]
        if len(miss):
            near = tree.query_nearest(P[miss])
            owner[near[0] if near.ndim == 1 else miss[near[0]]] = near[1] if near.ndim > 1 else near
    unk = int((best > 0.08).sum())
    for pts, j in zip(edges, owner):
        layers.setdefault(gkey[j] if j >= 0 else "old", []).extend(pts)
    log(name, "classified", {k: len(v) for k, v in layers.items()}, "unmatched", unk, f"{time.time() - t0:.1f}s")
    data = {"layers": {k: [[[round(c, 4) for c in view.screen(x, y)] for x, y in p] for p in v] for k, v in layers.items()},
            "arrows": [[view.point(a), view.point(b)] for a, b in arrows]}
    if focus:
        data["focus"] = {"xy": view.point(V(*focus["at"])), "size": focus["size"]}
    os.makedirs(CACHE, exist_ok=True)
    json.dump(data, open(os.path.join(CACHE, name + ".json"), "w"))
    return data


def render(name, data, slot, widths, fast_k=0.5, pad=8, keepout=(), display=None, fixed_k=None, fade=False):
    """Screen polylines -> <name>.svg, `slot` px (viewBox), strokes in px; framed on the focus, or fitted.
    `display`: the width/height the page shows it at, when drawn at 2x for a small slot."""
    t0 = time.time()
    scr, arr2 = data["layers"], data["arrows"]
    W, H = slot
    focus = data.get("focus")
    if focus:
        (fx, fy), k = focus["xy"], W / focus["size"]
        ox, oy = W / 2 - fx * k, H / 2 + fy * k
    elif fixed_k:                                          # a common scale (the hardware icons), centred
        xs = [x for v in scr.values() for p in v for x, _ in p]
        ys = [y for v in scr.values() for p in v for _, y in p]
        k = fixed_k
        ox, oy = W / 2 - (max(xs) + min(xs)) / 2 * k, H / 2 + (max(ys) + min(ys)) / 2 * k
    else:
        k, ox, oy = fit(scr, arr2, W, H, pad, keepout)
    tf = lambda x, y: (ox + x * k, oy - y * k)

    def path(pls):
        out = []
        for p in pls:
            q = [tf(x, y) for x, y in p]
            if focus:                       # drop what lies wholly outside the frame (by extent, not by vertices)
                xs_, ys_ = [x for x, _ in q], [y for _, y in q]
                if max(xs_) < -20 or min(xs_) > W + 20 or max(ys_) < -20 or min(ys_) > H + 20:
                    continue
            out.append("M" + " ".join(f"{x:.2f},{y:.2f}" for x, y in q))
        return "".join(out)

    wo, wn = widths
    style = {"old": ("#a3a3a0", wo), "old_f": ("#a3a3a0", wo * fast_k), "add": ("#111", wn), "add_f": ("#111", wn * fast_k)}
    DW, DH = display or slot
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{DW}" height="{DH}">']
    if fade:                                               # a cropped view: its lines fade out towards the edges
        svg.append(f'<defs><filter id="b" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="14"/></filter>'
                   f'<mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect x="34" y="34" width="{W - 68}" height="{H - 68}" fill="#fff" filter="url(#b)"/></mask></defs><g mask="url(#m)">')
    for key in ("old", "old_f", "add", "add_f"):
        if scr.get(key):
            col, w = style[key]
            svg.append(f'<path d="{path(scr[key])}" fill="none" stroke="{col}" stroke-width="{w:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    if scr.get("dash"):
        svg.append(f'<path d="{path(scr["dash"])}" fill="none" stroke="#111" stroke-width="{wn * 0.7:.2f}" stroke-dasharray="{wn * 3:.1f} {wn * 2:.1f}"/>')
    if fade:
        svg.append("</g>")
    for a, b in arr2:
        (x0, y0), (x1, y1) = tf(*a), tf(*b)
        ang = math.atan2(y1 - y0, x1 - x0)
        hl, hw = 19, 10
        bx, by = x1 - math.cos(ang) * hl, y1 - math.sin(ang) * hl
        head = f"M{x1:.1f},{y1:.1f}L{bx - math.sin(ang) * hw:.1f},{by + math.cos(ang) * hw:.1f}L{bx + math.sin(ang) * hw:.1f},{by - math.cos(ang) * hw:.1f}Z"
        svg.append(f'<path d="M{x0:.1f},{y0:.1f}L{bx:.1f},{by:.1f}" stroke="#fff" stroke-width="9" stroke-linecap="round"/>')
        svg.append(f'<path d="{head}" fill="#fff" stroke="#fff" stroke-width="4" stroke-linejoin="round"/>')
        svg.append(f'<path d="M{x0:.1f},{y0:.1f}L{bx:.1f},{by:.1f}" stroke="#111" stroke-width="4.2" stroke-linecap="round"/>')
        svg.append(f'<path d="{head}" fill="#111"/>')
    svg.append("</svg>")
    open(os.path.join(OUT, name + ".svg"), "w").write("\n".join(svg))
    log(name, "written", f"{time.time() - t0:.1f}s")


def cached(name):
    p = os.path.join(CACHE, name + ".json")
    return json.load(open(p)) if os.path.exists(p) and os.environ.get("REPROJECT") != "1" else None


# ------------------------------------------------------------------ jobs
# page slots (px): two steps a page; A-05's single step; the cover and its small copy; B-04
SLOTS = {"step": (682, 412), "single": (682, 583), "cover": (666, 762), "cover_small": (562, 300), "done": (682, 867)}


def job_step(n):
    st = STEPS[n]
    data = cached(n)
    if data is None:
        items, axes, arrows = step_scene(st)
        data = project(n, items, st["view"], axes, arrows, st.get("focus") or st.get("frame"))
    fr = st.get("focus") or st.get("frame")
    if fr:                                                 # (re)frame from the cache without projecting again
        data["focus"] = {"xy": View(st["view"]).point(V(*fr["at"])), "size": fr["size"]}
    if "focus" in st:                                      # detail circle
        render(n, data, (230, 230), (1.1, 2.0))
        return
    slot = st.get("slot", "step")
    allblack = not st["old"]
    w = (1.0, 1.5) if allblack and slot in ("cover", "done") else (1.0, 1.7)
    if slot == "cover":
        render(n, data, SLOTS["cover"], w)
        render(n + "_small", data, SLOTS["cover_small"], (1.0, 1.1))
        return
    W, H = SLOTS[slot]
    ko = ([("circle", W - 115, H - 115, 125)] if st.get("detail") else []) + ([("rect", -10, H - 70, 150, H + 10)] if st.get("clic") else [])
    render(n, data, (W, H), w, keepout=ko, fade="frame" in st)


def job_thumb(n):
    """Part chips (72 x 54) and parts-page cards (190 x 156), both drawn at 2x: one part, black."""
    iid, view = THUMBS[n]
    data = cached("thumb_" + n)
    if data is None:
        s = shape_of(iid)
        data = project("thumb_" + n, [(iid, "add", s, False)], view)
    render(f"chip_{n}", data, (144, 108), (1, 2.2), pad=4, display=(72, 54))
    render(f"card_{n}", data, (380, 312), (1, 2.6), pad=6, display=(190, 156))


def hw_shape(n):
    if n == "jumper":                          # a short row cable for the chip: two plugs, a sagging lead
        pins = row_cable()[0]["pins"]
        sols = [plug(V(-1.9, 0, 0), (1, 0), pins), plug(V(35.9, 0, 0), (-1, 0), pins)]   # leads leave at x = 0 and 34
        return Part.makeCompound(sols + lead(V(0, 0, 0), V(34, 0, 0), pins, 7.0))
    if n == "mag":                             # 6 x 3 disc magnet, on edge
        return Part.makeCylinder(3, 3, V(0, 0, 0), V(1, 0, 0))
    if n == "sp12":                            # hex spacer, axis along X, stud towards +X
        s = spacer_shape()
        s.rotate(V(0, 0, 0), V(0, 1, 0), -90)
        return s
    if n == "usbc":                            # the charger's cable: two USB-C plugs, a thick sagging lead
        a, ea = usbc_plug((0, 0, 0), (1, 0, 0))
        b, eb = usbc_plug((76, 0, 0), (-1, 0, 0))
        return Part.makeCompound(a + b + [pipe([tuple(ea), (38, 0, -9), tuple(eb)], 2.0)])
    kind, dia, length, _ = FAST[n]
    s = fastener_z(kind, dia, length).copy()
    s.rotate(V(0, 0, 0), V(0, 1, 0), -90)      # axis along X, head towards -X
    return s


def job_hw(n):
    """Hardware icons (64 x 30 on the page, drawn at 2x): one fastener nearly side on, a little from its head side."""
    data = cached("hw_" + n) or project("hw_" + n, [(n, "add", hw_shape(n), False)], HW_VIEW.get(n, HW_VIEW["*"]))
    cable = n in ("jumper", "usbc", "sp12", "mag")
    render(f"hw_{n}", data, (128, 60), (1, 1.8 if cable else 1.15), pad=3, display=(64, 30),
           fixed_k=None if cable else 9.4)        # every fastener at the same scale (the M3 x 8 fills it)


THUMBS = {
    "lb": ("lb0", (-1.4, -0.6, 0.5)), "la": ("la0", (-1.4, -0.6, 0.5)), "lc": ("lc0", (-1.4, -0.6, 0.5)),
    "fp": ("fp0", ISO), "tr": ("tr0", ISO), "dr": ("dr0", ISO), "cp": ("cp0", ISO),
    "bb": ("bb0", (0, 1, 0.15)), "nd": ("nd0", ISO),
    "pb": ("pb", ISO), "pl": ("pl", ISO), "hb": ("hb", ISO), "ch": ("charger", ISO),
    "an": ("ca0", ISO), "ft": ("cf0", ISO_R), "dc": ("dcx", (-0.2, -0.5, 1.5)), "xt": ("xtl", (0.1, -1.0, 0.6)), "dp": ("dpx", ISO),
}
HW_VIEW = {"*": (-0.5, -1.0, 0.35), "jumper": (0.1, -1.0, 0.35), "usbc": (0.1, -1.0, 0.35)}

if __name__ in ("__main__", "notice") and os.environ.get("NOTICE"):
    for n in os.environ["NOTICE"].split(","):
        try:
            if n.startswith("thumb:"):
                job_thumb(n[6:])
            elif n.startswith("hw:"):
                job_hw(n[3:])
            else:
                job_step(n)
        except Exception:
            log(n, "FAIL", traceback.format_exc())
    LOG.close()
