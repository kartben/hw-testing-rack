"""Side-by-side before/after sheets with callouts, from the pairs pairs.sh renders.
    python mechanical/review/proto/compose.py      -> mechanical/review/pairs/<name>.png
Each callout is (column, text, xy): column 0 = today, 1 = proposed; xy the arrow's target as a fraction
of the render (0,0 top-left), None for a plain note under the image."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

HERE = Path(__file__).resolve().parent
PAIRS = HERE.parent / "pairs"

SHEETS = {
    "tray_guide": ("Tray: guide lip and ledge start", [
        (0, "lip: 2 mm thick, 2.5 mm beyond the guide wall,\nflat underneath, 189 mm long: a shelf in the air", (0.42, 0.30)),
        (0, "ledge: first gusset at y 53, nothing at the\nfront (window skips y 5 and 29): 48 mm unsupported", (0.55, 0.62)),
        (1, "lip underside at 45° from its tip,\nthe tip still 3.4 mm over the ledge", (0.42, 0.30)),
        (1, "gusset at y 10 (behind the tie strap);\nfascia raised 0.5 mm under the ledge", (0.30, 0.66)),
    ]),
    "cradle_finger": ("DATA ×4 cradle: latch finger", [
        (0, "finger 24 mm free, hook 1.0, square root:\nbends ACROSS the layers, 0.72 % (FEM 29 MPa)\nallowed 0.5 % for repeated use", (0.50, 0.25)),
        (1, "40 mm free, hook 0.8, slit 1.0, R0.8 root:\n0.25 %, insertion ≈ 2 N", (0.50, 0.25)),
    ]),
    "ladder_nut_trap": ("Ladder rear post: brace screw", [
        (0, "M3 heat-set insert, Ø4.0 × 6.2 hole along the\n7.4 mm edge: 1.7 mm walls on the faces that keep\n0.2 mm to the trays; the horizontal hole prints oval", (0.47, 0.45)),
        (1, "DIN 562 M3 square nut (5.5 × 5.5 × 1.8) in a\n5.9 × 5.9 × 2.2 pocket open to the top face, 2.2 mm\nfrom the edge; plain Ø3.4 hole; 0.2 mm all round (SolidCraft)", (0.47, 0.45)),
    ]),
    "cam_pin": ("Peg cam base: split pivot", [
        (0, "slit 0.8 × 4.5 deep, head Ø3.9 on a Ø3.4 pin:\n0.25 mm per half-pin ACROSS the layers,\n2.4 % (FEM 64 MPa), allowed 1 %", (0.50, 0.30)),
        (1, "Ø4.4 × 2 relief in the column's top, slit 6.5,\nhead Ø3.7: 0.15 mm, 0.7 % (FEM 20 MPa)", (0.50, 0.30)),
    ]),
    "drawer_front": ("Drawer front: edges and bay label", [
        (0, "square-ish r 1.2 edges straight onto the bed;\nblank 100 × 12 label (tape or a printed blank)", (0.50, 0.52)),
        (1, "0.5 × 45° chamfer at the bed (elephant's foot),\nR2 on the top edge; the bay ID debossed 0.8 mm\nin the label, filled by the second nozzle", (0.50, 0.52)),
    ]),
    "ladder_hook": ("Ladder: stacking hook", [
        (0, "beam 2.6 wide, root 7 mm inside the band,\nsquare relief ends: 2.0 % for the 0.8 mm the barb\nmust give; FEM 56 MPa at the root (1.55 × the beam)", (0.50, 0.42)),
        (1, "root 10 mm, R0.6 at the relief's ends:\n1.3 %, ≈ 40 MPa; two hooks ≈ 25 N to seat", (0.50, 0.42)),
    ]),
    "latch_arm": ("Tray: latch arm (from outside)", [
        (0, "arm 26 mm between 1 mm slots with square\nends: 1.1 % for the 1.2 mm barb (fine), but the\nFEM's 52 MPa sits in the slot's corner", (0.50, 0.50)),
        (1, "arm 32 mm, slot ends R0.5:\n0.75 %, ≈ 10 N per thumb", (0.50, 0.50)),
    ]),
    "sleeve_tab": ("Camera pod: sleeve snap", [
        (0, "rigid 1.6 mm wall, 12 mm tall, 0.8 mm lip:\nthe wall bends ACROSS its layers, 1.3 %\n(FEM 42 MPa), allowed 0.5 % repeated", (0.50, 0.32)),
        (1, "tab 16 × 10 cut on three sides (0.6 slits),\nhinged on a vertical edge, 0.5 mm lip:\n0.75 % IN the print plane", (0.50, 0.40)),
    ]),
    "anchor_boss": ("Tray: chain-anchor boss (half)", [
        (0, "boss 5.5 mm, insert pocket 5.7 mm deep:\n0.2 mm through the floor, a Ø4 hole in\nthe first layer", (0.50, 0.70)),
        (1, "boss 7.5 mm: 1.8 mm of floor under the insert", (0.50, 0.55)),
    ]),
    "detent": ("Drawer detent (tray's left ledge)", [
        (0, "Ø6 × 3 magnet CA-glued in a pocket of a widened\npad, its twin under the drawer: 2 magnets, glue,\na polarity check per bay; ≈ 10 N hold", (0.60, 0.42)),
        (1, "spring tab 20 × 2.5 cut in the ledge (0.8 slits),\n0.6 mm bump 45° both ways into a notch under the\ndrawer: 0.56 % in plane, ≈ 3 N; no parts", (0.50, 0.42)),
    ]),
    "peg_skin": ("Peg plug: spring skins (from below)", [
        (0, "skin 0.7 over 2.6 mm, slot 0.35 short of the\nflat's end: a 3.0 mm cantilever, 2.3 % for the\nnub's 0.2 mm; allowed 1.5 % repeated", (0.50, 0.50)),
        (1, "SKIN_H 3.4, slot to the flat's end:\n3.7 mm, 1.5 %, ≈ 2.4 N per peg", (0.50, 0.50)),
    ]),
}


def sheet(name, title, callouts):
    imgs = [mpimg.imread(PAIRS / f"{name}_{v}.png") for v in ("today", "proposed")]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4), dpi=110)
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)
    for col, (ax, im, lab) in enumerate(zip(axes, imgs, ("TODAY", "PROPOSED"))):
        ax.imshow(im)
        ax.set_title(lab, fontsize=13, color="#b03a2e" if col == 0 else "#1e7a45", fontweight="bold", loc="left")
        ax.set_axis_off()
        h, w = im.shape[:2]
        notes = [c for c in callouts if c[0] == col]
        for k, (_, text, xy) in enumerate(notes):
            ty = 1.02 + 0.17 * k      # below the image, in axes fraction (inverted: y grows downwards here)
            if xy is None:
                ax.annotate(text, xy=(0.02, -0.02 - 0.17 * k), xycoords="axes fraction", va="top", fontsize=10.5)
            else:
                ax.annotate(text, xy=(xy[0] * w, xy[1] * h), xycoords="data",
                            xytext=(0.03, -0.03 - 0.17 * k), textcoords="axes fraction", va="top", fontsize=10.5,
                            bbox=dict(boxstyle="round,pad=0.4", fc="#fff8e8", ec="#c0392b", lw=1.2),
                            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.6, shrinkB=2))
    plt.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.26, wspace=0.05)
    out = PAIRS / f"{name}.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(out.name)


for name, (title, callouts) in SHEETS.items():
    sheet(name, title, callouts)
