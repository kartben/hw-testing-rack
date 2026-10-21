// DATA ×4 v2 cradle — holds the vertical DATA ×4 v2 (docs/data-x4-v2-layout-options.md, option B) upright at
// the back of the drawer's rear bay (or a sled bay's port block), its four vertical USB-C through the port
// wall's U's.  Drawer coordinates (parts/drawer.scad): x from the drawer's left outer face, y from its front,
// z 0 on the tray's ledges.
//
//   -D 'PART="cradle"'   the printed cradle (PETG), standing as installed: no supports
//   -D 'PART="board"'    the board's stand-in (outline, notches), for the viewer and the checks
//
// - The board stands on the drawer floor, its front face 7.4 mm behind the port wall's back face (the
//   receptacles' mouths 1 mm behind it), and slides down from above into two end slots (0.15 mm a side).
// - Plugging in pushes the board back onto the base's front edge, right behind the receptacles (relieved
//   round their shell legs).  Unplugging pulls it forwards onto the slots' front walls and two T-heads that
//   come through notches in its bottom edge, between ports 1–2 and 3–4.
// - A latch finger at each upright's top snaps over the board's top edge: press it back to lift the board.  It
//   bends across its layers, so it is long and its root is round: 0.21 % (docs/printed-parts-review.md).
// - The base sits on the DATA ×4's three shared bosses (H1–H3), 3 × PT 2.6 × 8 from above, and leaves the
//   cable window open: the board's PH 8 lead, on its rear face, drops behind it into the window.
// Print: as installed (bottom down), PETG, no supports; the base bridges ≤ 30 mm between its feet.
include <../lib/carrier.scad>

PART = "cradle";

V2 = [100, 70, 1.6];                      // the board: length (x), height (z), thickness (y): the v2 session, 2026-10-20
V2_X0 = 4;                                // its left edge
V2_Y = DATA_PCB_Y0 + 7.4;                 // its front face (the receptacles' mouths 1 mm behind the port wall)
V2_Z0 = DRAWER_BOTTOM;                    // its bottom edge, on the floor
PORT_XS = [for (u = DATA_X4_USB) DATA_X4_X0 + u];   // the four U's (drawer.scad)
GAP = 0.15;                               // per side in the slots and at the base's edge
END = 5.5;                                // the board's ends inside the slots (no parts there, either face)
UW = 2.4;                                 // the uprights' front and rear walls
OW = 1.2;                                 // their outer wall
NOTCH = [3.4, 6.5];                       // the board's bottom-edge notches: width, height
NOTCH_X = [35, 71];                       // their centres, drawer x: between ports 1–2 and 3–4
TEE = [7, 2.0];                           // a T-head's bar in front of the board: width (x), thickness (y)
BASE = [DATA_PCB_Z, 4.0];                 // the base: its underside (the bosses' top), thickness
LEG_RELIEF = [11, 1.2];                   // round each receptacle's shell legs on the rear face: width, depth
LATCH = [40, 0.8];                        // the latch finger: free length, hook over the board's top edge
SLIT = 1.0;                               // the slit that frees it from the outer wall
ROOT_R = 0.8;                             // the round at the slit's foot, into the finger's root

BOSSES = [for (i = [0 : 2]) let (h = DATA_X4_HOLES[i]) [DATA_X4_X0 + h[0], DATA_PCB_Y0 + DATA_X4_SIZE[1] - h[1]]];
WIN_X = BOSSES[2][0] + 4.5;               // the cable window's left edge (drawer.scad › wx)
WIN_Y = DATA_PCB_Y0 + DATA_PCB_SIZE[1] + 1;   // and its front edge (› wy)

Y_F = V2_Y - GAP;                         // the slot: front face
Y_R = V2_Y + V2[2] + GAP;                 // rear face
TOP = V2_Z0 + V2[1];                      // the board's top edge
X_L = V2_X0 - 0.5 - OW;                   // the left upright's outer face
X_MID = V2_X0 + V2[0] / 2;
BASE_Y1 = max([for (b = BOSSES) b[1]]) + 4.5;   // the base's rear edge
assert(X_L >= DRAWER_WALL + 0.3, "the left upright hits the drawer's wall");

// the left upright, a U-channel round the board's left end: front wall, outer wall, rear wall.  The rear
// wall's top is a latch finger (slit from the outer wall, its foot rounded into the finger's root), its hook
// over the board's top edge with a 45° lead-in on top, so the board's edge pushes it back going in
module upright() {
    x1 = V2_X0 + END;
    xs = X_L + OW + SLIT;                 // the finger's slit-side face
    difference() {
        translate([X_L, Y_F - UW, V2_Z0]) cube([x1 - X_L, Y_R + UW - (Y_F - UW), TOP - V2_Z0]);
        translate([V2_X0 - 0.5, Y_F, V2_Z0 - EPS]) cube([x1 - V2_X0 + 0.5 + EPS, Y_R - Y_F, TOP - V2_Z0 + 2 * EPS]);
        translate([X_L + OW, Y_R - EPS, TOP - LATCH[0]]) cube([SLIT, UW + 2 * EPS, LATCH[0] + EPS]);
        translate([xs, Y_R - EPS, TOP - LATCH[0]]) rotate([-90, 0, 0]) difference() {
            cube([ROOT_R, ROOT_R, UW + 2 * EPS]);
            translate([ROOT_R, ROOT_R, -1]) cylinder(r = ROOT_R, h = UW + 2, $fn = 32);
        }
    }
    translate([xs, 0, TOP]) rotate([90, 0, 90]) linear_extrude(x1 - xs)
        polygon([[Y_R + UW, 0], [Y_R, 0], [Y_R, 0.2], [Y_R - GAP - LATCH[1], 0.2], [Y_R - GAP - LATCH[1], 0.6],
                 [Y_R, 1.6 + LATCH[1]], [Y_R + UW, 1.6 + LATCH[1]]]);
}

module cradle() {
    difference() {
        union() {
            upright();
            translate([2 * X_MID, 0, 0]) mirror([1, 0, 0]) upright();
            // the base: from right behind the board to behind the bosses, short of the cable window
            translate([X_L, Y_R, BASE[0]]) difference() {
                cube([2 * X_MID - 2 * X_L, BASE_Y1 - Y_R, BASE[1]]);
                translate([WIN_X - 1 - X_L, WIN_Y - 1 - Y_R, -EPS]) cube([100, 100, BASE[1] + 2 * EPS]);
            }
            // feet round the bosses (the base's supports while printing; clear of the bosses in the drawer)
            for (b = [BOSSES[0], BOSSES[1]]) translate([b[0], b[1], V2_Z0]) difference() {
                cylinder(d = 10, h = BASE[0] - V2_Z0 + EPS);
                translate([0, 0, -EPS]) cylinder(d = 6.8, h = BASE[0]);
            }
            translate([78, BOSSES[1][1], V2_Z0]) cylinder(d = 6, h = BASE[0] - V2_Z0 + EPS);
            // the T-heads: a bar in front of the board's bottom, a fin through its notch, a riser behind it
            // up to the base
            for (x = NOTCH_X) {
                h = NOTCH[1] - 0.5;
                translate([x - TEE[0] / 2, Y_F - TEE[1], V2_Z0]) cube([TEE[0], TEE[1] + EPS, h]);
                translate([x - NOTCH[0] / 2 + 0.3, Y_F - EPS, V2_Z0]) cube([NOTCH[0] - 0.6, Y_R - Y_F + 2 * EPS, h]);
                translate([x - NOTCH[0] / 2 + 0.3, Y_R, V2_Z0]) cube([NOTCH[0] - 0.6, 3, BASE[0] + BASE[1] - V2_Z0]);
            }
        }
        // screw holes, heads countersunk into the base
        for (b = BOSSES) translate([b[0], b[1], BASE[0] - EPS]) {
            cylinder(d = 2.9, h = BASE[1] + 2 * EPS);
            translate([0, 0, BASE[1] - 2]) cylinder(d = 5.6, h = 2 + 2 * EPS);
        }
        // reliefs round each receptacle's shell legs, through the rear face
        for (x = PORT_XS) translate([x - LEG_RELIEF[0] / 2, Y_R - EPS, BASE[0] - EPS]) cube([LEG_RELIEF[0], LEG_RELIEF[1], BASE[1] + 2 * EPS]);
    }
}

// the board's stand-in: its outline and the two bottom-edge notches
module board() translate([V2_X0, V2_Y, V2_Z0]) difference() {
    cube([V2[0], V2[2], V2[1]]);
    for (x = NOTCH_X) translate([x - V2_X0 - NOTCH[0] / 2, -EPS, -EPS]) cube([NOTCH[0], V2[2] + 2 * EPS, NOTCH[1] + EPS]);
}

if (PART == "board") board();
else cradle();
