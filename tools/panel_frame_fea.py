#!/usr/bin/env python3
"""Lateral stiffness of the panel frame: a 2D frame model of the rack seen from the front.

    python tools/panel_frame_fea.py            # runs the scenarios, writes a plot and a JSON

What is modelled (front view, X right, Z up; forces in N, lengths in mm):
  * each ladder column is a chain of beams whose bending stiffness comes from the real ladder
    meshes: I(Z) = A(Z)·t²/12, A(Z) the horizontal section of the stacked ladders at height Z
    (posts, bands, brace), t = the ladder thickness: the ladders bend on their thin side;
  * stacked ladders meet at a joint (ridge + two hooks): a rotational spring k_stack;
  * trays (and the floor / cap plates) are rigid struts between two ladders, joined to each
    one by a rotational spring with a dead band: free over ±play (runner in its groove, wall
    clearance), then k_tray;
  * the rear braces are tension-only bars with a slack (pin clearance in the holes);
  * the base ladders stand on the floor: pinned feet;
  * a horizontal force on the top of every column; the result is the top sway.
The joint stiffnesses are estimates (the detailed contact models come next); the script
sweeps them so the conclusions do not hang on one number.  PETG as printed: E = 1800 MPa.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

sys.path.insert(0, str(Path(__file__).parent))
from build import MECH  # noqa: E402

E = 1800.0
BUILD = MECH / "build" / "panel"


# ------------------------------------------------------------------ geometry from the build
def constants() -> dict:
    return json.loads((BUILD / "proto.json").read_text(encoding="utf-8"))["constants"]


def section_area(mesh: trimesh.Trimesh, z: float) -> float:
    """Area of the section of a ladder mesh (profile in local XY, Y = frame Z) at local y = z."""
    lines = trimesh.intersections.mesh_plane(mesh, plane_normal=[0, 1, 0], plane_origin=[0, z, 0])
    if len(lines) == 0:
        return 0.0
    r = lambda v: (round(float(v[0]), 3), round(float(v[2]), 3))    # snap: the slices meet exactly
    segs = [LineString([r(a), r(b)]) for a, b in lines if r(a) != r(b)]
    return sum(p.area for p in polygonize(unary_union(segs)))


def column_profile(c: dict, rows: int, dz: float = 4.0):
    """I(Z) of one ladder column (base, rows, cap strip) and the stacking-joint heights."""
    names = ["ladder_base"] + [f"ladder_{'abcd'[k]}" for k in range(rows)] + [f"ladder_cap{rows}"]
    meshes = [trimesh.load(BUILD / f"{n}.stl") for n in names]
    top = max(m.bounds[1][1] for m in meshes)
    zs = np.arange(0.0, top + dz, dz)
    t = c["PANEL_T"]
    areas = np.array([sum(section_area(m, z) for m in meshes if m.bounds[0][1] < z < m.bounds[1][1]) for z in zs])
    tilt = math.radians(c["TILT"])
    mid = (c["PR"] + c["PF"]) / 2 - c["ROW_Y0"]              # joints at mid-depth (they are tilted)
    joints = [c["ROW_Z"][k] + mid * math.tan(tilt) for k in range(rows + 1)]
    return zs, areas * t * t / 12.0, joints, top


# ------------------------------------------------------------------ a small nonlinear 2D frame solver
@dataclass
class Frame:
    xy: list = field(default_factory=list)          # node coordinates
    beams: list = field(default_factory=list)       # (a, b, EA, EI)
    ties: list = field(default_factory=list)        # (a, b): same x, z
    springs: list = field(default_factory=list)     # (a, b, k, play): rotational, dead band ±play
    bars: list = field(default_factory=list)        # (a, b, EA, slack): tension only
    fixed: list = field(default_factory=list)       # (node, dof)
    loads: dict = field(default_factory=dict)       # (node, dof) -> force

    def node(self, x, z):
        self.xy.append((x, z))
        return len(self.xy) - 1

    def solve(self, scale: float = 1.0, iters: int = 60):
        n = 3 * len(self.xy)
        K0 = np.zeros((n, n))
        for a, b, EA, EI in self.beams:
            (x1, z1), (x2, z2) = self.xy[a], self.xy[b]
            L = math.hypot(x2 - x1, z2 - z1)
            cs, sn = (x2 - x1) / L, (z2 - z1) / L
            k = np.array([[EA / L, 0, 0, -EA / L, 0, 0],
                          [0, 12 * EI / L**3, 6 * EI / L**2, 0, -12 * EI / L**3, 6 * EI / L**2],
                          [0, 6 * EI / L**2, 4 * EI / L, 0, -6 * EI / L**2, 2 * EI / L],
                          [-EA / L, 0, 0, EA / L, 0, 0],
                          [0, -12 * EI / L**3, -6 * EI / L**2, 0, 12 * EI / L**3, -6 * EI / L**2],
                          [0, 6 * EI / L**2, 2 * EI / L, 0, -6 * EI / L**2, 4 * EI / L]])
            T = np.zeros((6, 6))
            for i in (0, 3):
                T[i:i + 2, i:i + 2] = [[cs, sn], [-sn, cs]]
                T[i + 2, i + 2] = 1
            d = [3 * a, 3 * a + 1, 3 * a + 2, 3 * b, 3 * b + 1, 3 * b + 2]
            K0[np.ix_(d, d)] += T.T @ k @ T
        pen = 1e9
        for a, b in self.ties:
            for j in (0, 1):
                i1, i2 = 3 * a + j, 3 * b + j
                K0[i1, i1] += pen; K0[i2, i2] += pen; K0[i1, i2] -= pen; K0[i2, i1] -= pen
        F0 = np.zeros(n)
        for (nd, dof), f in self.loads.items():
            F0[3 * nd + dof] += f * scale
        free = np.ones(n, bool)
        for nd, dof in self.fixed:
            free[3 * nd + dof] = False
        sstate = [0] * len(self.springs)          # -1, 0 (in the dead band), +1
        bstate = [False] * len(self.bars)
        u = np.zeros(n)
        for _ in range(iters):
            K, F = K0.copy(), F0.copy()
            for (a, b, k, play), s in zip(self.springs, sstate):
                if s:
                    i1, i2 = 3 * a + 2, 3 * b + 2
                    K[i1, i1] += k; K[i2, i2] += k; K[i1, i2] -= k; K[i2, i1] -= k
                    F[i1] += k * play * s; F[i2] -= k * play * s     # M = k (Δθ - play·s)
                else:                                                  # tiny stiffness: no mechanism
                    i1, i2 = 3 * a + 2, 3 * b + 2
                    K[i1, i1] += 1.0; K[i2, i2] += 1.0; K[i1, i2] -= 1.0; K[i2, i1] -= 1.0
            for (a, b, EA, slack), on in zip(self.bars, bstate):
                (x1, z1), (x2, z2) = self.xy[a], self.xy[b]
                L = math.hypot(x2 - x1, z2 - z1)
                cs, sn = (x2 - x1) / L, (z2 - z1) / L
                g = np.array([-cs, -sn, cs, sn])
                d = [3 * a, 3 * a + 1, 3 * b, 3 * b + 1]
                k = (EA / L if on else 1e-6)
                K[np.ix_(d, d)] += k * np.outer(g, g)
                if on:
                    F[d] += k * slack * g                             # N = EA/L (δ - slack)
            uf = np.linalg.solve(K[np.ix_(free, free)], F[free])
            u = np.zeros(n); u[free] = uf
            ns = []
            for a, b, k, play in self.springs:
                dth = u[3 * a + 2] - u[3 * b + 2]
                ns.append(1 if dth > play else -1 if dth < -play else 0)
            nb = []
            for a, b, EA, slack in self.bars:
                (x1, z1), (x2, z2) = self.xy[a], self.xy[b]
                L = math.hypot(x2 - x1, z2 - z1)
                g = np.array([-(x2 - x1), -(z2 - z1), x2 - x1, z2 - z1]) / L
                nb.append(float(g @ u[[3 * a, 3 * a + 1, 3 * b, 3 * b + 1]]) > slack)
            if ns == sstate and nb == bstate:
                break
            sstate, bstate = ns, nb
        return u


# ------------------------------------------------------------------ the rack
def build_rack(c, prof, cols: int, rows: int, braces: bool, play_deg: float,
               k_tray: float, k_stack: float, pin_slack: float = 0.2) -> tuple[Frame, list]:
    zs, I, joints, top = prof
    P, t = c["PANEL_PITCH"], c["PANEL_T"]
    fr = Frame()
    play = math.radians(play_deg)
    A_col = 400.0                                    # axial stiffness hardly matters for sway
    tilt = math.radians(c["TILT"])
    mid = (c["PR"] + c["PF"]) / 2 - c["ROW_Y0"]
    tray_z = [10.5] + [c["ROW_Z"][k] + mid * math.tan(tilt) + 10.5 for k in range(rows + 1)]  # floor, rows, cap
    # brace pin heights (rear edge), per level: base = -1, rows 0..rows-1 (same rule as panels.scad)
    def brace_z(k):
        if k < 0:
            topb = c["ROW_Z"][0] + (c["PR"] - c["ROW_Y0"]) * math.tan(tilt)
            return [30, 48, topb - 44, topb - 26]
        b = c["ROW_Z"][k] + (c["PR"] - c["ROW_Y0"]) * math.tan(tilt)
        h = c["ROW_Z"][k + 1] - c["ROW_Z"][k]
        return [b + 28, b + 46, b + h - 47, b + h - 29]
    extra = sorted(set(round(z, 1) for z in tray_z + [z for k in range(-1, rows) for z in brace_z(k)]))
    key = sorted(set(extra + [round(float(z), 1) for z in zs if min(abs(z - e) for e in extra) > 1.5]))
    cols_nodes = []
    for i in range(cols + 1):
        x = i * P + t / 2
        nodes = {}
        prev = None
        for z in key:
            nd = fr.node(x, z)
            nodes[z] = nd
            if prev is not None:
                zp, ndp = prev
                zm = (zp + z) / 2
                Iz = max(float(np.interp(zm, zs, I)), 1.0)
                # a stacking joint inside this element: add its compliance in series
                L = z - zp
                if any(zp < j <= z for j in joints) and k_stack is not None:
                    Iz = 1.0 / (1.0 / Iz + E / (k_stack * L))
                fr.beams.append((ndp, nd, E * A_col, E * Iz))
            prev = (z, nd)
        fr.fixed += [(nodes[key[0]], 0), (nodes[key[0]], 1)]
        cols_nodes.append(nodes)
    def at(i, z):
        zz = min(cols_nodes[i], key=lambda k: abs(k - z))
        return cols_nodes[i][zz]
    for j in range(cols):
        for z in tray_z:
            a, b = at(j, z), at(j + 1, z)
            ea, eb = fr.node(*fr.xy[a]), fr.node(*fr.xy[b])
            fr.beams.append((ea, eb, 1e9, 1e12))
            for col_n, end_n in ((a, ea), (b, eb)):
                fr.ties.append((col_n, end_n))
                fr.springs.append((col_n, end_n, k_tray, play))
        if braces:
            for k in range(-1, rows):
                z = brace_z(k)
                EA = E * 8 * 3
                fr.bars.append((at(j, z[0]), at(j + 1, z[3]), EA, pin_slack))
                fr.bars.append((at(j, z[2]), at(j + 1, z[1]), EA, pin_slack))
    for i in range(cols + 1):
        fr.loads[(at(i, key[-1]), 0)] = 1.0 / (cols + 1)
    return fr, [at(i, key[-1]) for i in range(cols + 1)]


def sway_curve(c, prof, cols, rows, forces, **kw):
    out = []
    for F in forces:
        fr, tops = build_rack(c, prof, cols, rows, **kw)
        u = fr.solve(scale=F)
        out.append(float(np.mean([u[3 * n] for n in tops])))
    return out


def main() -> None:
    c = constants()
    forces = [0.5, 1, 2, 3, 5, 7.5, 10, 15, 20]
    results = {"forces": forces, "cases": []}
    profs = {r: column_profile(c, r) for r in (2, 4)}
    base = dict(k_tray=2e6, k_stack=3e4)
    cases = [
        ("2×2, no braces, no play", 2, 2, dict(braces=False, play_deg=0.0, **base)),
        ("2×2, no braces, play 0.5°", 2, 2, dict(braces=False, play_deg=0.5, **base)),
        ("2×2, braces, play 0.5°", 2, 2, dict(braces=True, play_deg=0.5, **base)),
        ("4×4, no braces, play 0.5°", 4, 4, dict(braces=False, play_deg=0.5, **base)),
        ("4×4, braces, play 0.5°", 4, 4, dict(braces=True, play_deg=0.5, **base)),
        ("4×4, braces, play 0.5°, rigid stack joints", 4, 4, dict(braces=True, play_deg=0.5, k_tray=2e6, k_stack=1e9)),
        ("4×4, braces, play 0.5°, soft trays (k/10)", 4, 4, dict(braces=True, play_deg=0.5, k_tray=2e5, k_stack=3e4)),
        ("4×4, braces, play 0.25°, pin slack 0.1", 4, 4, dict(braces=True, play_deg=0.25, pin_slack=0.1, **base)),
        ("4×4, taut braces (design), play 0.5°", 4, 4, dict(braces=True, play_deg=0.5, pin_slack=0.0, **base)),
        ("4×4, taut braces, trays as hinges", 4, 4, dict(braces=True, play_deg=0.0, pin_slack=0.0, k_tray=1.0, k_stack=3e4)),
    ]
    for name, cols, rows, kw in cases:
        d = sway_curve(c, profs[rows], cols, rows, forces, **kw)
        results["cases"].append({"name": name, "cols": cols, "rows": rows, **{k: v for k, v in kw.items()}, "sway": d})
        print(f"{name:<48} " + "  ".join(f"{F:>4}N:{x:6.2f}" for F, x in zip(forces, d) if F in (2, 5, 10, 20)))
    (BUILD / "fea.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5), dpi=130)
    for cse in results["cases"]:
        ax.plot(cse["sway"], forces, marker="o", ms=3, label=cse["name"])
    ax.set_xlabel("top sway (mm)"); ax.set_ylabel("lateral force at the top (N)")
    ax.set_xlim(0, 30); ax.grid(alpha=.3); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(BUILD / "fea.png")
    print("wrote", BUILD / "fea.json", "and fea.png")


if __name__ == "__main__":
    main()
