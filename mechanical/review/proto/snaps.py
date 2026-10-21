"""docs/printed-parts-review.md: Hand calculation of every snap feature of the printed parts (constant-section cantilever, Bayer
snap-fit design guide): root strain e = 1.5 y h / L^2, deflection force P = b h^2 E e / (6 L),
mating force W = P (mu + tan a) / (1 - mu tan a).  PETG printed: E 1800 MPa (tools/panel_frame_fea.py).
Allowable strain (one-off / repeated), by the layer direction the beam bends across:
  in the print plane   3.0 % / 1.5 %   (PETG's own short-term allowable about 4 %, derated for FDM walls)
  across the layers    1.0 % / 0.5 %   (layer adhesion ~ 50-70 % of the in-plane strength)
"""
E, MU = 1800.0, 0.35

# name, y (mm), h (mm, in the flex direction), L (mm), b (mm), layers ("in" plane / "across"), ramp angle (deg), uses
SNAPS = [
    ("ladder hook (ladder.scad: HOOK_W 2.6, ROOT 7 + DROP 9, barb 1.0, slot clear 0.2)", 0.8, 2.6, 12.5, 7.4, "in", 22, "once"),
    ("ladder hook, ROOT 10 (proposed)", 0.8, 2.6, 15.5, 7.4, "in", 22, "once"),
    ("tray latch arm (tray.scad: wall 2 + runner 2.3, ARM 26, BARB 1.2)", 1.2, 4.3, 26.0, 5.0, "in", 30, "repeated"),
    ("cradle latch finger (x4_cradle.scad: UW 2.4, LATCH 24, hook 1.0 + gap 0.15)", 1.15, 2.4, 24.0, 5.4, "across", 45, "repeated"),
    ("cradle finger, L 34 + hook 0.8 (proposed)", 0.95, 2.4, 34.0, 5.4, "across", 45, "repeated"),
    ("cradle finger, L 34, hook 0.8, wall 1.6 (proposed b)", 0.95, 1.6, 34.0, 5.4, "across", 45, "repeated"),
    ("peg skin (hexgrid.scad: SKIN 0.7, free 3.0, nub 0.3 - clear 0.1)", 0.2, 0.7, 3.0, 2.6, "in", 30, "repeated"),
    ("peg skin, SKIN_H 3.4 and slot to the end (proposed)", 0.2, 0.7, 3.7, 3.4, "in", 30, "repeated"),
    ("cam pivot half-pin (pegs.scad: PIVOT 3.4 split 0.8, head 3.9, split 4.5)", 0.25, 1.3, 4.5, 3.0, "across", 40, "once"),
    ("cam pivot, split 6.5, head 3.7 (proposed)", 0.15, 1.3, 6.5, 3.0, "across", 40, "once"),
    ("camera sleeve wall (camera_pod.scad: SW 1.6, 12 tall, LIP 0.8)", 0.8, 1.6, 12.0, 16.0, "across", 45, "repeated"),
    ("camera sleeve, LIP 0.5 on 2 slit tabs 16 wide (proposed)", 0.5, 1.6, 12.0, 16.0, "across", 45, "repeated"),
    ("drawer detent spring tab (proposed: 2.5 thick, 20 long, bump 0.6)", 0.6, 2.5, 20.0, 6.0, "in", 45, "repeated"),
]
ALLOW = {"in": (3.0, 1.5), "across": (1.0, 0.5)}
import math
print(f"{'feature':74} {'strain':>7} {'allow':>6} {'P N':>6} {'W N':>6}  verdict")
for name, y, h, L, b, lay, a, use in SNAPS:
    e = 1.5 * y * h / L ** 2
    P = b * h * h * E * e / (6 * L)
    t = math.tan(math.radians(a))
    W = P * (MU + t) / (1 - MU * t)
    allow = ALLOW[lay][0 if use == "once" else 1]
    v = "ok" if e * 100 <= allow else ("marginal" if e * 100 <= 1.3 * allow else "TOO HIGH")
    print(f"{name:74} {e*100:6.2f}% {allow:5.1f}% {P:6.1f} {W:6.1f}  {v}")
