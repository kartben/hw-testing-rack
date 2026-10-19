"""OpenSCAD CSG tree -> exact FreeCAD Part solid (true circles and cylinders, no mesh).

OpenSCAD exports its evaluated tree (`openscad -o part.csg part.scad`): only primitives,
multmatrix and booleans are left.  This rebuilds it with OCC: circles with $fn >= 12 (or 0)
become real circles, hulls of circles / parallel cylinders become exact rounded outlines,
hulls of boxes exact polyhedra.  Smaller $fn (the hexagon reliefs) stay polygons, as printed.

    CSG2PART=tray,drawer_light freecadcmd csg2part.py   (<build>/csg/<name>.csg -> <build>/parts/<name>.brep;
                                                          <build> = $NOTICE_BUILD, see tools/notice/run.py)
"""
import math, os, re, sys, time
import FreeCAD as App
import Part
from FreeCAD import Vector as V

CIRCLE_MIN_FN = 12
TOL = 1e-6

# ------------------------------------------------------------------ parser
TOK = re.compile(r'\s*(?:(-?\d+\.?\d*(?:[eE][-+]?\d+)?|-?\.\d+(?:[eE][-+]?\d+)?)|("(?:[^"\\]|\\.)*")|([A-Za-z_$][A-Za-z0-9_$]*)|(.))')


def tokens(text):
    for m in TOK.finditer(text):
        num, s, ident, p = m.groups()
        if num is not None:
            yield ("num", float(num))
        elif s is not None:
            yield ("str", s[1:-1])
        elif ident is not None:
            yield ("id", ident)
        elif p is not None and not p.isspace():
            yield ("p", p)


class Parser:
    def __init__(self, text):
        self.t = list(tokens(text))
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def take(self, kind=None, val=None):
        tok = self.peek()
        if (kind and tok[0] != kind) or (val is not None and tok[1] != val):
            raise SyntaxError(f"expected {kind} {val}, got {tok} at {self.i}")
        self.i += 1
        return tok

    def value(self):
        k, v = self.peek()
        if k in ("num", "str"):
            self.i += 1
            return v
        if k == "id":
            self.i += 1
            return {"true": True, "false": False, "undef": None}.get(v, v)
        if (k, v) == ("p", "["):
            self.i += 1
            out = []
            while self.peek() != ("p", "]"):
                out.append(self.value())
                if self.peek() == ("p", ","):
                    self.i += 1
            self.i += 1
            return out
        raise SyntaxError(f"bad value {self.peek()}")

    def stmts(self):
        out = []
        while self.peek()[0] is not None and self.peek() != ("p", "}"):
            if self.peek() == ("p", ";"):
                self.i += 1
                continue
            out.append(self.stmt())
        return out

    def stmt(self):
        name = self.take("id")[1]
        self.take("p", "(")
        args, pos = {}, []
        while self.peek() != ("p", ")"):
            if self.peek()[0] == "id" and self.peek(1) == ("p", "="):
                key = self.take("id")[1]
                self.take("p", "=")
                args[key] = self.value()
            else:
                pos.append(self.value())
            if self.peek() == ("p", ","):
                self.i += 1
        self.take("p", ")")
        kids = []
        if self.peek() == ("p", "{"):
            self.i += 1
            kids = self.stmts()
            self.take("p", "}")
        elif self.peek() == ("p", ";"):
            self.i += 1
        return (name, args, pos, kids)


# ------------------------------------------------------------------ geometry helpers
class R:
    """Result of a node: dim 2 (faces in z = 0) or 3, a shape, and hull primitives."""
    def __init__(self, dim, shape, prims=None):
        self.dim, self.shape, self.prims = dim, shape, prims


warnings = []


def refine(s):
    try:
        r = s.removeSplitter()
        return r if not r.isNull() else s
    except Exception:
        return s


def fuse_all(shapes):
    shapes = [s for s in shapes if s is not None and not s.isNull()]
    if not shapes:
        return None
    if len(shapes) == 1:
        return shapes[0]
    return refine(shapes[0].multiFuse(shapes[1:]))


def polygon_face(pts):
    clean = []
    for p in pts:
        q = V(p[0], p[1], 0)
        if not clean or (q - clean[-1]).Length > 1e-7:
            clean.append(q)
    if (clean[0] - clean[-1]).Length < 1e-7:
        clean.pop()
    return Part.Face(Part.makePolygon(clean + [clean[0]]))


def reg_polygon(n, r):
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def mat_from(m):
    M = App.Matrix()
    M.A11, M.A12, M.A13, M.A14 = m[0]
    M.A21, M.A22, M.A23, M.A24 = m[1]
    M.A31, M.A32, M.A33, M.A34 = m[2]
    return M


def det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def transform(s, m):
    d = det3(m)
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    ortho = all(abs(sum(cols[a][k] * cols[b][k] for k in range(3)) - (1 if a == b else 0)) < 1e-6 for a in range(3) for b in range(3))
    s = s.copy()
    if ortho and d > 0:
        s.transformShape(mat_from(m))
        return s
    if ortho and d < 0:                       # mirror in x first, then the proper rotation
        s = s.mirror(V(0, 0, 0), V(1, 0, 0))
        m2 = [[-m[r][0], m[r][1], m[r][2], m[r][3]] for r in range(3)]
        s.transformShape(mat_from(m2))
        return s
    return s.transformGeometry(mat_from(m))


def apply_pt(m, p):
    x, y, z = (list(p) + [0, 0, 0])[:3]
    return tuple(m[r][0] * x + m[r][1] * y + m[r][2] * z + m[r][3] for r in range(3))


def hull2d_pts(pts):
    pts = sorted(set((round(p[0], 9), round(p[1], 9)) for p in pts))
    if len(pts) <= 2:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 1e-12:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 1e-12:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def mixed_hull(circles, pts, n=720):
    """2D hull of circles (any radii) and points: the hull of the points and of each circle sampled
    finely, then every run of samples from one circle replaced by its exact arc (a face in z = 0)."""
    tag = {}
    for p in pts:
        tag.setdefault((round(p[0], 9), round(p[1], 9)), (-1, None))
    for k, (c, r) in enumerate(circles):
        for i in range(n):
            a = 2 * math.pi * i / n
            tag.setdefault((round(c[0] + r * math.cos(a), 9), round(c[1] + r * math.sin(a), 9)), (k, None))
    h = hull2d_pts(list(tag))
    t = [tag[p][0] for p in h]
    s = next((i for i in range(len(h)) if t[i] != t[i - 1] or t[i] < 0), 0)   # start where a run starts
    h, t = h[s:] + h[:s], t[s:] + t[:s]
    runs = []
    for p, k in zip(h, t):
        if runs and k >= 0 and runs[-1][0] == k:
            runs[-1][1].append(p)
        else:
            runs.append((k, [p]))
    v = lambda p: V(p[0], p[1], 0)
    edges = []
    for i, (k, ps) in enumerate(runs):
        if k >= 0 and len(ps) >= 3:
            edges.append(Part.Arc(v(ps[0]), v(ps[len(ps) // 2]), v(ps[-1])).toShape())
        elif len(ps) == 2:
            edges.append(Part.LineSegment(v(ps[0]), v(ps[1])).toShape())
        nxt = runs[(i + 1) % len(runs)][1][0]
        if (v(ps[-1]) - v(nxt)).Length > 1e-9:
            edges.append(Part.LineSegment(v(ps[-1]), v(nxt)).toShape())
    return Part.Face(Part.Wire(Part.__sortEdges__(edges)))


def rounded_hull(centres, r):
    """Exact 2D hull of equal circles: tangent segments + arcs (a face in z = 0)."""
    h = hull2d_pts(centres)
    if len(h) == 1:
        return Part.Face(Part.Wire(Part.makeCircle(r, V(h[0][0], h[0][1], 0))))
    n = len(h)
    outs = []                                  # counter-clockwise: outward normal of a -> b is (dy, -dx)
    for i in range(n):
        a, b = h[i], h[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        nx, ny = dy / L, -dx / L
        outs.append((V(a[0] + nx * r, a[1] + ny * r, 0), V(b[0] + nx * r, b[1] + ny * r, 0), (nx, ny)))
    edges = []
    for i in range(n):
        p0, p1, n1 = outs[i]
        edges.append(Part.LineSegment(p0, p1).toShape())
        q0, _, n2 = outs[(i + 1) % n]
        c = h[(i + 1) % n]
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        ml = math.hypot(mx, my)
        if ml < 1e-9:                          # two circles: a half-circle cap, its middle straight ahead
            d = (c[0] - h[i][0], c[1] - h[i][1])
            dl = math.hypot(*d)
            mid = V(c[0] + d[0] / dl * r, c[1] + d[1] / dl * r, 0)
        else:
            mid = V(c[0] + mx / ml * r, c[1] + my / ml * r, 0)
        if (p1 - q0).Length > 1e-9:
            edges.append(Part.Arc(p1, mid, q0).toShape())
    return Part.Face(Part.Wire(Part.__sortEdges__(edges)))


def hull3d_pts(pts):
    from scipy.spatial import ConvexHull
    import numpy as np
    P = np.array(pts)
    ch = ConvexHull(P)
    faces = []
    for simp, eq in zip(ch.simplices, ch.equations):
        a, b, c = (V(*P[k]) for k in simp)
        if (b - a).cross(c - a).dot(V(*eq[:3])) < 0:
            b, c = c, b
        faces.append(Part.Face(Part.makePolygon([a, b, c, a])))
    return refine(Part.Solid(Part.Shell(faces)))


# ------------------------------------------------------------------ evaluator
def ev(node):
    name, a, pos, kids = node
    fn = int(a.get("$fn", 0) or 0)
    if name in ("group", "union", "render", "color"):
        rs = [r for r in (ev(k) for k in kids) if r is not None and r.shape is not None]
        if not rs:
            return None
        prims = []
        for r in rs:
            prims = None if (prims is None or r.prims is None) else prims + r.prims
        return R(rs[0].dim, fuse_all([r.shape for r in rs]), prims)
    if name == "difference":
        rs = [ev(k) for k in kids]
        if not rs or rs[0] is None or rs[0].shape is None:
            return None
        tools = [r.shape for r in rs[1:] if r is not None and r.shape is not None]
        s = rs[0].shape.cut(tools) if tools else rs[0].shape
        return R(rs[0].dim, refine(s))
    if name == "intersection":
        rs = [r for r in (ev(k) for k in kids) if r is not None and r.shape is not None]
        s = rs[0].shape
        for r in rs[1:]:
            s = s.common(r.shape)
        return R(rs[0].dim, refine(s))
    if name == "multmatrix":
        m = pos[0] if pos else a["m"]
        r = ev(("group", {}, [], kids))
        if r is None:
            return None
        prims = None
        if r.prims is not None:
            prims = []
            for p in r.prims:
                if p[0] == "circle":
                    sc = math.sqrt(abs(m[0][0] * m[1][1] - m[0][1] * m[1][0]))
                    prims.append(("circle", apply_pt(m, p[1])[:2], p[2] * sc))
                elif p[0] == "pts":
                    prims.append(("pts", [apply_pt(m, q) for q in p[1]]))
                elif p[0] == "cyl":
                    prims.append(("cyl", apply_pt(m, p[1]), apply_pt(m, p[2]), p[3], p[4]))
        return R(r.dim, transform(r.shape, m), prims)
    if name == "circle":
        r = a["r"]
        if fn == 0 or fn >= CIRCLE_MIN_FN:
            return R(2, Part.Face(Part.Wire(Part.makeCircle(r))), [("circle", (0, 0), r)])
        pts = reg_polygon(fn, r)
        return R(2, polygon_face(pts), [("pts", [(x, y, 0) for x, y in pts])])
    if name == "square":
        sx, sy = a["size"] if isinstance(a["size"], list) else (a["size"], a["size"])
        x0, y0 = (-sx / 2, -sy / 2) if a.get("center") else (0, 0)
        pts = [(x0, y0), (x0 + sx, y0), (x0 + sx, y0 + sy), (x0, y0 + sy)]
        return R(2, polygon_face(pts), [("pts", [(x, y, 0) for x, y in pts])])
    if name == "polygon":
        pts, paths = a["points"], a.get("paths")
        if not paths:
            f = polygon_face(pts)
        else:
            wires = []
            for path in paths:
                loop = [V(pts[int(k)][0], pts[int(k)][1], 0) for k in path]
                wires.append(Part.makePolygon(loop + [loop[0]]))
            f = Part.makeFace(wires, "Part::FaceMakerBullseye")
        return R(2, f, [("pts", [(p[0], p[1], 0) for p in pts])])
    if name == "cube":
        s = a["size"] if isinstance(a["size"], list) else [a["size"]] * 3
        o = [-x / 2 for x in s] if a.get("center") else [0, 0, 0]
        b = Part.makeBox(s[0], s[1], s[2], V(*o))
        corners = [(o[0] + i * s[0], o[1] + j * s[1], o[2] + k * s[2]) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
        return R(3, b, [("pts", corners)])
    if name == "cylinder":
        h, r1, r2 = a["h"], a["r1"], a["r2"]
        z0 = -h / 2 if a.get("center") else 0
        if fn == 0 or fn >= CIRCLE_MIN_FN:
            s = Part.makeCylinder(r1, h, V(0, 0, z0)) if abs(r1 - r2) < TOL else Part.makeCone(r1, r2, h, V(0, 0, z0))
            return R(3, s, [("cyl", (0, 0, z0), (0, 0, z0 + h), r1, r2)])
        w1 = Part.makePolygon([V(x, y, z0) for x, y in reg_polygon(fn, r1)] + [V(r1, 0, z0)])
        if abs(r1 - r2) < TOL:
            s = Part.Face(w1).extrude(V(0, 0, h))
        else:
            r2_ = max(r2, 1e-4)
            w2 = Part.makePolygon([V(x, y, z0 + h) for x, y in reg_polygon(fn, r2_)] + [V(r2_, 0, z0 + h)])
            s = Part.makeLoft([w1, w2], True, True)
        pts = [(x, y, z0) for x, y in reg_polygon(fn, r1)] + [(x, y, z0 + h) for x, y in reg_polygon(fn, r2)]
        return R(3, s, [("pts", pts)])
    if name == "text":                    # engraved labels: too fine for the notice's line art
        return None
    if name == "linear_extrude":
        r = ev(("group", {}, [], kids))
        if r is None:
            return None
        h = a["height"]
        sc = a.get("scale", [1, 1])
        if (isinstance(sc, list) and any(abs(x - 1) > 1e-9 for x in sc)) or abs(a.get("twist", 0) or 0) > 1e-9:
            raise NotImplementedError("linear_extrude scale/twist")
        s = r.shape.extrude(V(0, 0, h))
        if a.get("center"):
            s.translate(V(0, 0, -h / 2))
        return R(3, refine(s))
    if name == "offset":
        r = ev(("group", {}, [], kids))
        if r is None:
            return None
        if a.get("r") not in (None, 0):
            v, join = a["r"], 0
        else:
            v, join = a.get("delta", 0) or 0, 2
        if abs(v) < 1e-12:
            return r
        outs = []
        for f in r.shape.Faces:
            try:
                o = f.makeOffset2D(v, join, False, False, False)
                if not o.isNull() and o.Faces:
                    outs.append(o)
            except Exception:
                pass                      # vanished under a negative offset
        if not outs:
            return None
        return R(2, fuse_all(outs))
    if name == "hull":
        r = ev(("group", {}, [], kids))
        if r is None:
            return None
        prims = r.prims
        if prims is None:
            warnings.append("hull of a complex child: using its vertices")
            prims = [("pts", [(p.X, p.Y, p.Z) for p in r.shape.Vertexes])]
        if r.dim == 2:
            circ = [p for p in prims if p[0] == "circle"]
            pts = [q for p in prims if p[0] == "pts" for q in p[1]]
            if circ and not pts and max(c[2] for c in circ) - min(c[2] for c in circ) < 1e-6:
                return R(2, rounded_hull([c[1] for c in circ], circ[0][2]), prims)
            if pts and not circ:
                return R(2, polygon_face(hull2d_pts([q[:2] for q in pts])), prims)
            return R(2, mixed_hull([(c[1], c[2]) for c in circ], [q[:2] for q in pts]), prims)
        cyl = [p for p in prims if p[0] == "cyl"]
        pts = [q for p in prims if p[0] == "pts" for q in p[1]]
        if cyl and not pts:
            ax = V(*cyl[0][2]) - V(*cyl[0][1])
            hgt = ax.Length
            ax.normalize()
            ok = all(abs(c[3] - cyl[0][3]) < 1e-6 and abs(c[4] - c[3]) < 1e-6 for c in cyl)
            ok = ok and all(((V(*c[2]) - V(*c[1])) - ax * hgt).Length < 1e-6 and abs((V(*c[1]) - V(*cyl[0][1])).dot(ax)) < 1e-6 for c in cyl)
            if not ok:
                raise NotImplementedError("3D hull of non-parallel / unequal cylinders")
            ux = V(1, 0, 0) if abs(ax.x) < 0.9 else V(0, 1, 0)
            ux = (ux - ax * ux.dot(ax)).normalize()
            uy = ax.cross(ux)
            o = V(*cyl[0][1])
            loc = [((V(*c[1]) - o).dot(ux), (V(*c[1]) - o).dot(uy)) for c in cyl]
            s = rounded_hull(loc, cyl[0][3]).extrude(V(0, 0, hgt))
            s.transformShape(App.Matrix(ux.x, uy.x, ax.x, o.x, ux.y, uy.y, ax.y, o.y, ux.z, uy.z, ax.z, o.z, 0, 0, 0, 1))
            return R(3, s, prims)
        if pts and not cyl:
            return R(3, hull3d_pts(pts), prims)
        if cyl and pts:
            # parallel equal cylinders + boxes spanning the same length along their axis (a U / slot cut):
            # the 2D mixed hull across the axis, extruded (from the tray session's SolidCraft check)
            ax = V(*cyl[0][2]) - V(*cyl[0][1])
            hgt = ax.Length
            ax.normalize()
            o = V(*cyl[0][1])
            ok = all(abs(c[3] - cyl[0][3]) < 1e-6 and abs(c[4] - c[3]) < 1e-6 for c in cyl)
            ok = ok and all(((V(*c[2]) - V(*c[1])) - ax * hgt).Length < 1e-6 and abs((V(*c[1]) - o).dot(ax)) < 1e-6 for c in cyl)
            ok = ok and all(-1e-6 <= (V(*q) - o).dot(ax) <= hgt + 1e-6 for q in pts)
            if ok:
                ux = V(1, 0, 0) if abs(ax.x) < 0.9 else V(0, 1, 0)
                ux = (ux - ax * ux.dot(ax)).normalize()
                uy = ax.cross(ux)
                loc = [((V(*c[1]) - o).dot(ux), (V(*c[1]) - o).dot(uy)) for c in cyl]
                q2 = [((V(*q) - o).dot(ux), (V(*q) - o).dot(uy)) for q in pts]
                s = mixed_hull([(c, cyl[0][3]) for c in loc], q2).extrude(V(0, 0, hgt))
                s.transformShape(App.Matrix(ux.x, uy.x, ax.x, o.x, ux.y, uy.y, ax.y, o.y, ux.z, uy.z, ax.z, o.z, 0, 0, 0, 1))
                return R(3, s, prims)
        raise NotImplementedError("3D hull of mixed cylinders/boxes")
    raise NotImplementedError(name)


def convert(path):
    tree = Parser(open(path, encoding="utf-8").read()).stmts()
    s = ev(("group", {}, [], tree)).shape
    sols = s.Solids
    if len(sols) > 1:
        s = fuse_all(sols)
        sols = s.Solids
    return refine(sols[0] if len(sols) == 1 else Part.makeCompound(sols))


if __name__ in ("__main__", "csg2part") and os.environ.get("CSG2PART") is not None:
    HERE = os.environ.get("NOTICE_BUILD") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mechanical", "build", "notice")
    want = os.environ.get("CSG2PART", "")
    names = want.split(",") if want else sorted(f[:-4] for f in os.listdir(os.path.join(HERE, "csg")) if f.endswith(".csg"))
    os.makedirs(os.path.join(HERE, "parts"), exist_ok=True)
    log = open(os.path.join(HERE, "parts", "convert_log.txt"), "a")
    for n in names:
        t0 = time.time()
        warnings.clear()
        try:
            s = convert(os.path.join(HERE, "csg", n + ".csg"))
            s.exportBrep(os.path.join(HERE, "parts", n + ".brep"))
            bb = s.BoundBox
            log.write(f"{n}: ok {time.time() - t0:.1f}s valid={s.isValid()} solids={len(s.Solids)} faces={len(s.Faces)} vol={s.Volume:.0f} "
                      f"bb=({bb.XMin:.1f}..{bb.XMax:.1f}, {bb.YMin:.1f}..{bb.YMax:.1f}, {bb.ZMin:.1f}..{bb.ZMax:.1f}) warn={warnings}\n")
        except Exception:
            import traceback
            log.write(f"{n}: FAIL {time.time() - t0:.1f}s {traceback.format_exc()}\n")
        log.flush()
    log.close()
