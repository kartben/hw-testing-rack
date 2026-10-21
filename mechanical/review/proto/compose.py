"""Side-by-side AVANT | APRÈS sheets with callouts, from the renders pairs.sh makes.
    python mechanical/review/proto/compose.py      -> mechanical/review/pairs/<name>.png  (1600 px wide)
A callout is (column, text, xy): column 0 = avant, 1 = après; xy the arrow's target as a fraction of the
render (0,0 top-left).  The accent colour of the renders (the changed geometry) is echoed in the après label."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

HERE = Path(__file__).resolve().parent
PAIRS = HERE.parent / "pairs"
ACCENT, RED, GREY = "#ff7a1a", "#b03a2e", "#4b5a50"

SHEETS = {
    "tray_guide": ("Tray — guide lip and ledge start (section, front view)", [
        (0, "lip: 2 mm thick, 2.5 mm beyond the guide wall, flat\nunderneath over 189 mm: a shelf in the air (0° overhang)", (0.48, 0.19)),
        (0, "ledge: first gusset at y 53; the window skips y 5 and 29,\nso 48 mm start unsupported (and 0.5 mm off the fascia)", (0.60, 0.55)),
        (1, "lip underside at 45° from its tip; the tip\nstill 3.4 mm over the ledge (flange 3.0 + 0.4)", (0.48, 0.19)),
        (1, "gusset at y 10 (behind the tie strap, before the plug);\nfascia raised 0.5 mm under the ledge", (0.34, 0.55)),
    ]),
    "cradle_finger": ("DATA ×4 cradle — latch finger over the board's edge", [
        (0, "finger 24 mm free, hook 1.0, slit 0.6, square root:\nbends ACROSS the layers, 0.72 % (FEM 29 MPa);\nallowed 0.5 % for a finger used at every swap", (0.50, 0.30)),
        (1, "40 mm free, hook 0.8, slit 1.0, R0.8 root:\n0.25 %, insertion ≈ 2 N", (0.50, 0.30)),
    ]),
    "ladder_nut_trap": ("Ladder rear post — brace screw (cut along the screw, brace in grey)", [
        (0, "M3 heat-set insert, Ø4.0 × 6.2 hole along the 7.4 mm\nedge: 1.7 mm walls on the faces that keep 0.2 mm to\nthe trays; a horizontal hole prints oval", (0.52, 0.42)),
        (1, "DIN 562 M3 square nut 5.5 × 5.5 × 1.8 in a 5.9 × 5.9 × 2.2\npocket open to the top face, 2.2 mm from the edge;\nplain Ø3.4 hole; 0.2 mm all round (SolidCraft)", (0.52, 0.42)),
    ]),
    "cam_pin": ("Peg cam base — split pivot under the cam", [
        (0, "slit 0.8 × 4.5 deep, head Ø3.9 on a Ø3.4 pin:\n0.25 mm per half ACROSS the layers,\n2.4 % (FEM 64 MPa), allowed 1 %", (0.50, 0.28)),
        (1, "Ø4.4 × 2 relief in the column's top, slit 6.5,\nhead Ø3.7: 0.15 mm, 0.7 % (FEM 20 MPa)", (0.50, 0.28)),
    ]),
    "ladder_hook": ("Ladder — stacking hook in the slot below (flat, as printed)", [
        (0, "beam 2.6 wide, root 7 mm inside the band, square\nrelief ends: 2.0 % for the barb's 0.8 mm, FEM 56 MPa\nat the root (1.55 × the beam value)", (0.50, 0.40)),
        (1, "root 10 mm, R0.6 at the relief's ends: 1.3 %,\n≈ 40 MPa; two hooks seat with ≈ 25 N", (0.50, 0.40)),
    ]),
    "latch_arm": ("Tray — latch arm and the ladder's window (from outside)", [
        (0, "arm 26 mm between 1 mm slots with square ends:\n1.1 % for the 1.2 mm barb (allowed 1.5 %), but the\nFEM's 52 MPa sits in the slot's corner", (0.50, 0.50)),
        (1, "arm 32 mm, slot ends R0.5: 0.75 %,\n≈ 10 N per thumb to release", (0.50, 0.50)),
    ]),
    "sleeve_tab": ("Camera pod — sleeve snap, the case in grey", [
        (0, "rigid 1.6 mm wall, 12 mm tall, 0.8 mm lip: the wall\nbends ACROSS its layers, 1.3 % (FEM 42 MPa),\nallowed 0.5 % for repeated use", (0.50, 0.32)),
        (1, "tab 16 × 10 cut on three sides (0.6 slits), hinged\non a vertical edge, 0.5 mm lip: bends IN the print\nplane, 0.75 %", (0.50, 0.40)),
    ]),
    "anchor_boss": ("Tray — chain-anchor boss (cut in half, anchor in grey)", [
        (0, "boss 5.5 mm, insert pocket 5.7 mm deep: 0.2 mm\nthrough the 2.5 mm floor, a Ø4 hole in the first layer", (0.50, 0.70)),
        (1, "boss 7.5 mm: 1.8 mm of floor under the insert", (0.50, 0.55)),
    ]),
    "detent": ("Drawer detent — the tray's left ledge, drawer floor in grey", [
        (0, "Ø6 × 3 magnet CA-glued in a pocket of a widened pad,\nits twin in a boss under the drawer: 2 magnets, glue,\na polarity check per bay; ≈ 10 N hold", (0.58, 0.46)),
        (1, "spring tab 20 × 2.5 cut in the ledge (0.8 slits), a\n0.6 mm bump at 45° into a notch under the drawer:\n0.56 % in plane, ≈ 3 N; nothing to buy or glue", (0.50, 0.44)),
    ]),
    "peg_skin": ("Peg plug in its hole — spring skins (from below, plate in grey)", [
        (0, "skin 0.7 over 2.6 mm, slot 0.35 short of the flat's\nend: a 3.0 mm cantilever, 2.3 % for the nub's 0.2 mm;\nallowed 1.5 % for pegs moved at every re-layout", (0.50, 0.50)),
        (1, "SKIN_H 3.4, slot to the flat's end: 3.7 mm,\n1.5 %, ≈ 2.4 N to clip a peg", (0.50, 0.50)),
    ]),
    "power_box_labels": ("Power box — the markings three ways (front wall, lid on)", [
        (0, "5.25 mm bold capitals engraved 0.8 mm and inlaid: A B C D\nunder the LED pairs, PD, CTL; PD IN at the rear; A–D at the\nrow windows; the rack's name and RESET / BOOT on the lid", (0.42, 0.56)),
        (1, "walls bare; kept where a hand needs a mark: A–D at the\nleft-wall windows (plugging the rows), PD IN at the rear\nUSB-C (the front one is the console); the lid's name and\nRESET / BOOT dropped", (0.42, 0.56)),
        (2, "the same, plus 3 mm capitals debossed 0.4 mm, no inlay,\nunder the LED pairs (A B C D), PD, CTL, and RESET / BOOT\nby the lid's pin holes: 15 layers tall, read up close", (0.42, 0.56)),
    ], [("today", "AVANT"), ("plain", "APRÈS · bare"), ("small", "APRÈS · small letters")]),
    "visual_language": ("The visual language on a real part — the drawer's front corner", [
        (0, "r 1.2 vertical edges, the bottom edge straight onto\nthe bed (elephant's foot), a blank 100 × 12 label", (0.42, 0.45)),
        (1, "R3 vertical edges; 0.5 × 45° chamfer on the bed edge;\nthe bay ID debossed 0.8 mm in the label, filled by the\nsecond nozzle; `1 2 3 4` debossed 0.4 mm in the rear-bay\nfloor.  Same rules on every part: the ladders' outline\nand row letter, FRONT arrows on plates, PT2.6 marks", (0.42, 0.45)),
    ]),
}


def sheet(name, title, callouts, views=(("today", "AVANT"), ("proposed", "APRÈS"))):
    imgs = [mpimg.imread(PAIRS / f"{name}_{v}.png") for v, _ in views]
    n = len(views)
    fig, axes = plt.subplots(1, n, figsize=(16 if n == 2 else 21, 8.2), dpi=100)
    fig.suptitle(title, fontsize=17, fontweight="bold", y=0.985)
    for col, (ax, im, (_, lab)) in enumerate(zip(axes, imgs, views)):
        colr = RED if col == 0 else ACCENT
        ax.imshow(im)
        ax.set_title(lab, fontsize=16, color=colr, fontweight="bold", loc="left")
        ax.set_axis_off()
        h, w = im.shape[:2]
        notes = [c for c in callouts if c[0] == col]
        y = -0.03
        for _, text, xy in notes:
            n = text.count("\n") + 1
            ax.annotate(text, xy=(xy[0] * w, xy[1] * h), xycoords="data",
                        xytext=(0.02, y), textcoords="axes fraction", va="top", fontsize=11.5,
                        bbox=dict(boxstyle="round,pad=0.45", fc="#fff8e8", ec=colr, lw=1.4),
                        arrowprops=dict(arrowstyle="->", color=colr, lw=1.8, shrinkB=3))
            y -= 0.055 * n + 0.06
    if n == 2:
        axes[1].text(0.98, 1.035, "accent = the geometry the proposal changes · grey = the mating part", transform=axes[1].transAxes,
                     ha="right", va="bottom", fontsize=10, color=GREY)
    plt.subplots_adjust(left=0.015, right=0.985, top=0.9, bottom=0.3, wspace=0.04)
    out = PAIRS / f"{name}.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(out.name)


for name, spec in SHEETS.items():
    sheet(name, *spec)
