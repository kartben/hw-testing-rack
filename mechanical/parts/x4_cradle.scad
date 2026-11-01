// DATA board cradle — holds a standing DATA board upright at the back of the drawer's rear bay (or a sled bay's
// port block), its vertical USB-C, standing with their slot upright, through the port wall's slots: the DATA ×6
// (config/rack.yaml › pcb.data_port_x6), every bay's, or the DATA ×4 v2 (› pcb.data_port_x4_v2;
// docs/data-x4-v2-layout-options.md, option B) where the DUT is wired.  Both are 100 × 70 with the same notches,
// their ports on one grid (the ×6 in all six slots, the v2 in slots 2–5): one cradle and one strip take either.
// Drawer coordinates (parts/drawer.scad): x from the drawer's left outer face, y from its front, z 0 on the
// tray's ledges.
//
//   -D 'PART="cradle"'   the printed cradle (PETG), standing as installed: no supports
//   -D 'PART="strip"'    the strip over the receptacles (PETG), its top face down: no supports
//   -D 'PART="strip_in_place"'   the same, where it goes, for the viewer and the checks
//   -D 'PART="board"'    the board's stand-in (outline, notches), for the viewer and the checks
//
// - The board stands on the drawer floor, its front face 7.4 mm behind the port wall's back face (the
//   receptacles' mouths 1 mm behind it), and slides down from above into two end slots (0.15 mm a side).
// - Plugging in pushes the board back onto the base's front edge, right behind the receptacles (relieved
//   round their shell legs).  Unplugging pulls it forwards onto the slots' front walls and two T-heads that
//   come through notches in its bottom edge, between slots 2–3 and 4–5.
// - A latch finger at each upright's top snaps over the board's top edge: press it back to lift the board.  It
//   bends across its layers, so it is long and its root is round: 0.21 % (docs/printed-parts-review.md).
// - The base sits on the DATA ×4's three shared bosses (H1–H3), 3 × M3 × 8 from above into heat-set inserts in
//   them (the user, 2026-10-21: a board is swapped often), and leaves the
//   cable window open: the board's PH 8 lead, on its rear face, drops behind it into the window.
// - The receptacles' guard (the user, 2026-10-26, after the design review): a comb on the floor in front of the
//   board, part of the cradle, holds each receptacle's standing body in a U (open on top: the board still drops
//   in) up to just over the bodies, and a strip on the comb, 5 × PT 2.3 × 8 into it between the ports, closes
//   the U's.  A cable pulled any way then bears on the cradle, not on the receptacles' joints.  Out: the strip
//   first, then the board.  A U at each of the six slots (on a v2 the end two stay empty), the strip screwed
//   between each two (no room outside the end ports).  The comb keeps 2.1 mm off the board's face (the parts
//   under each receptacle); the T-heads' bars reach into it, 4.7 mm wide, 1.1 mm off the USB-C left of each
//   notch.  No port numbers: on either board port 1 is the leftmost seen from the DUT's side (docs/mechanical.md).
// Print: as installed (bottom down), PETG, no supports; the base bridges ≤ 16 mm between its feet.
include <../lib/carrier.scad>

PART = "cradle";

// a warning until the v2 is re-placed on the ×6's grid (pcb.data_port_x4_v2), then an assert again
if (!(DATA_X6_SIZE == DATA_V2_SIZE && DATA_X6_X0 == DATA_V2_X0 && DATA_X6_T == DATA_V2_T
      && DATA_X6_FACE_Y == DATA_V2_FACE_Y && DATA_X6_NOTCH_X == DATA_V2_NOTCH_X && DATA_X6_NOTCH == DATA_V2_NOTCH))
    echo("WARNING: the DATA ×6 and the DATA ×4 v2 no longer share an outline: one cradle no longer takes both");
V2 = [DATA_X6_SIZE[0], DATA_X6_SIZE[1], DATA_X6_T];   // the board: length (x), height (z), thickness (y)
V2_X0 = DATA_X6_X0;                       // its left edge
V2_Y = DATA_PCB_Y0 + DATA_X6_FACE_Y;      // its front face (the receptacles' mouths 1 mm behind the port wall)
V2_Z0 = DRAWER_BOTTOM;                    // its bottom edge, on the floor
PORT_XS = DATA_PORTS;                     // the drawer's slots (lib/carrier.scad), the receptacles standing
GAP = 0.15;                               // per side in the slots and at the base's edge
END = 5.5;                                // the board's ends inside the slots (no parts there, either face)
UW = 2.4;                                 // the uprights' front and rear walls
OW = 1.2;                                 // their outer wall
NOTCH = DATA_X6_NOTCH;                    // the board's bottom-edge notches: width, height
NOTCH_X = DATA_X6_NOTCH_X;                // their centres, drawer x: between slots 2–3 and 4–5
// a T-head's bar in front of the board, from the comb to the slot's front face: its ends off the notch's centre.
// Its left end 1.1 off the USB-C on its left (ports 2 and 4: their shell legs at ±2.3), its right end 0.8 past
// the notch (nothing there below the 7 × 6 zone's top)
TEE = [-2.2, 2.5];
BASE = [DATA_PCB_Z, 4.0];                 // the base: its underside (the bosses' top), thickness
LEG_RELIEF = [7, 1.2];                    // round each receptacle's shell legs on the rear face (±2.15 across): width, depth
LATCH = [40, 0.8];                        // the latch finger: free length, hook over the board's top edge
SLIT = 1.0;                               // the slit that frees it from the outer wall
ROOT_R = 0.8;                             // the keyhole at the slit's foot: the finger's root round
// the guard.  HRO TYPE-C-31-D-06, from its drawing (the user, 2026-10-26): 8.94 × 3.16 × 6.40 nominal, the
// general tolerances' max taken here; its legs reach ±2.15 off the axis, ≈ 0.8 above the board (1.5 allowed).
// It stands (its slot upright, 2026-11-01): its length along z, its depth along x
USBC_BODY = [9.14, 3.31, 6.6];            // max: length (z), depth (x), height off the board (y)
GUARD_GAP = 0.1;                          // round the max body: 0.2 / 0.175 a side round a nominal one
COMB_Y = [V2_Y - 6.4 + 0.2, V2_Y - 2.1];  // 0.2 behind the mouths; 0.65 clear of the USBLC6s (1.45 tall) beside them
COMB_TOP = PORT_Z + USBC_BODY[0] / 2 + GUARD_GAP;   // GUARD_GAP over the bodies' top: the strip closes the U's there
STRIP_TOP = COMB_TOP + 5;                 // 5 mm: ≈ 0.02 mm under 20 N between two screws (2 mm: 0.45)
SEAT = [5.5, 2];                          // a slot across the strip for each screw's head (≤ Ø4.5): width, depth
GUARD_SY = (COMB_Y[0] + COMB_Y[1]) / 2;   // the screws' y

BOSSES = [for (i = [0 : 2]) let (h = DATA_X4_HOLES[i]) [DATA_X4_X0 + h[0], DATA_PCB_Y0 + DATA_X4_SIZE[1] - h[1]]];
BOSS_D = INSERT_M3[0] + 4;                // the bosses (drawer.scad › X4_BOSS_D)
WIN_X = BOSSES[2][0] + BOSS_D / 2 + 1.5;  // the cable window's left edge (drawer.scad › wx)
WIN_Y = DATA_WIN_Y;                       // and its front edge

Y_F = V2_Y - GAP;                         // the slot: front face
Y_R = V2_Y + V2[2] + GAP;                 // rear face
TOP = V2_Z0 + V2[1];                      // the board's top edge
X_L = V2_X0 - 0.5 - OW;                   // the left upright's outer face
X_MID = V2_X0 + V2[0] / 2;
BASE_Y1 = max([for (b = BOSSES) b[1]]) + 6;     // the base's rear edge
// the comb and the strip run from upright to upright; the strip's screws go between each two ports, and 9 mm
// outside an end port where the strip reaches past it (the 15.5 mm grid leaves no room there)
COMB_X1 = 2 * X_MID - X_L;
STRIP_X = [V2_X0 + END + 0.1, V2_X0 + V2[0] - END - 0.1];
function on_strip(x) = x - SEAT[0] / 2 - 1 >= STRIP_X[0] && x + SEAT[0] / 2 + 1 <= STRIP_X[1];
GUARD_SCREWS = concat([for (x = [PORT_XS[0] - 9]) if (on_strip(x)) x],
                      [for (i = [0 : len(PORT_XS) - 2]) (PORT_XS[i] + PORT_XS[i + 1]) / 2],
                      [for (x = [PORT_XS[len(PORT_XS) - 1] + 9]) if (on_strip(x)) x]);
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
        // the slit's foot: a keyhole, so the finger's root corner is round (and the mesh has no knife edge)
        translate([xs - SLIT / 2, Y_R - EPS, TOP - LATCH[0]]) rotate([-90, 0, 0]) cylinder(r = ROOT_R, h = UW + 2 * EPS, $fn = 32);
        // the visual language: R1.5 on its four vertical edges, a 0.8 round on its outer top edges
        for (c = [[X_L, Y_F - UW, 0, 0], [X_L, Y_R + UW, 0, 1], [x1, Y_F - UW, 1, 0], [x1, Y_R + UW, 1, 1]])
            translate([c[0], c[1], V2_Z0 - EPS]) mirror([c[2], 0, 0]) mirror([0, c[3], 0])
                multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) edge_round(TOP - V2_Z0 + 2 * EPS, r = VL_R[1]);
        translate([X_L, Y_F - UW, TOP]) mirror([0, 0, 1]) edge_round(x1 - X_L);
        translate([X_L, Y_R + UW, TOP]) rotate([0, 0, -90]) mirror([0, 0, 1]) edge_round(Y_R + UW - (Y_F - UW));
    }
    translate([xs, 0, TOP]) rotate([90, 0, 90]) linear_extrude(x1 - xs)
        polygon([[Y_R + UW, 0], [Y_R, 0], [Y_R, 0.2], [Y_R - GAP - LATCH[1], 0.2], [Y_R - GAP - LATCH[1], 0.6],
                 [Y_R, 1.6 + LATCH[1]], [Y_R + UW, 1.6 + LATCH[1]]]);
}

// a U round a standing receptacle's body, along y through the comb: GUARD_GAP off the max body, its bottom flat
// with r 1 corners (the shell's own are ≈ 1.25: a full round would leave its corners 0.06), its sides straight
// up through `top`, a 1 mm lead-in there
module guard_pocket(x, top) {
    w = USBC_BODY[1] + 2 * GUARD_GAP;
    h = USBC_BODY[0] + 2 * GUARD_GAP;
    l = COMB_Y[1] - COMB_Y[0] + 2;
    r = 1;
    z = PORT_Z - h / 2;                   // the bottom
    translate([x, COMB_Y[0] - 1, 0]) {
        hull() {
            for (s = [-1, 1]) translate([s * (w / 2 - r), 0, z + r]) rotate([-90, 0, 0]) cylinder(r = r, h = l, $fn = 32);
            translate([-w / 2, 0, z + r]) cube([w, l, top + 1 - z - r]);
        }
        translate([0, 0, top]) rotate([-90, 0, 0]) linear_extrude(l)
            polygon([[-w / 2 - 1, -EPS], [w / 2 + 1, -EPS], [w / 2, 1], [-w / 2, 1]]);
    }
}

// the comb: on the floor from the uprights' outer faces, fused with their front walls and the T-heads.  Nothing
// of it behind COMB_Y: the board's face carries parts under each receptacle from z 4.27 (up to 1.25 tall)
module comb() difference() {
    translate([X_L, COMB_Y[0], V2_Z0]) cube([COMB_X1 - X_L, COMB_Y[1] - COMB_Y[0], COMB_TOP - V2_Z0]);
    for (x = PORT_XS) guard_pocket(x, COMB_TOP);
    for (x = GUARD_SCREWS) translate([x, GUARD_SY, COMB_TOP - 5.5]) cylinder(d = PT_PILOT, h = 5.5 + EPS, $fn = 24);
}

// the strip: on the comb between the uprights, its underside GUARD_GAP over the max bodies, a PT 2.3 × 8
// through it at each screw, its head in a slot across the strip
module strip() difference() {
    translate([STRIP_X[0], COMB_Y[0], COMB_TOP]) cube([STRIP_X[1] - STRIP_X[0], COMB_Y[1] - COMB_Y[0], STRIP_TOP - COMB_TOP]);
    for (x = GUARD_SCREWS) {
        translate([x, GUARD_SY, COMB_TOP - EPS]) cylinder(d = PT_CLEAR, h = STRIP_TOP - COMB_TOP + 2 * EPS, $fn = 24);
        translate([x - SEAT[0] / 2, COMB_Y[0] - 1, STRIP_TOP - SEAT[1]]) cube([SEAT[0], COMB_Y[1] - COMB_Y[0] + 2, SEAT[1] + 1]);
    }
    // the visual language: a 0.8 round on its top's long edges
    translate([STRIP_X[0] - 0.1, COMB_Y[0], STRIP_TOP]) mirror([0, 0, 1]) edge_round(STRIP_X[1] - STRIP_X[0] + 0.2);
    translate([STRIP_X[0] - 0.1, COMB_Y[1], STRIP_TOP]) mirror([0, 1, 0]) mirror([0, 0, 1]) edge_round(STRIP_X[1] - STRIP_X[0] + 0.2);
}

module cradle() {
    difference() {
        union() {
            comb();
            upright();
            translate([2 * X_MID, 0, 0]) mirror([1, 0, 0]) upright();
            // the base: from right behind the board to behind the bosses, short of the cable window
            translate([X_L, Y_R, BASE[0]]) difference() {
                cube([2 * X_MID - 2 * X_L, BASE_Y1 - Y_R, BASE[1]]);
                translate([WIN_X - 1 - X_L, WIN_Y - 1 - Y_R, -EPS]) cube([100, 100, BASE[1] + 2 * EPS]);
            }
            // feet round the bosses (the base's supports while printing; clear of the bosses in the drawer)
            for (b = [BOSSES[0], BOSSES[1]]) translate([b[0], b[1], V2_Z0]) difference() {
                cylinder(d = BOSS_D + 4, h = BASE[0] - V2_Z0 + EPS);
                translate([0, 0, -EPS]) cylinder(d = BOSS_D + 0.8, h = BASE[0]);
            }
            // and Ø6 posts where the drawer's floor is bare, so the base bridges ≤ 16 mm as printed (the one at
            // x 95 forward of the third boss; docs/printed-parts-fdm-review.md, item 3)
            for (p = [[36, BOSSES[1][1]], [78, BOSSES[1][1]], [95, 179]])
                translate([p[0], p[1], V2_Z0]) cylinder(d = 6, h = BASE[0] - V2_Z0 + EPS);
            // the T-heads: a bar from the comb to the board's bottom, a fin through its notch, a riser behind it
            // up to the base
            for (x = NOTCH_X) {
                h = NOTCH[1] - 0.5;
                translate([x + TEE[0], COMB_Y[1] - 1, V2_Z0]) cube([TEE[1] - TEE[0], Y_F - COMB_Y[1] + 1 + EPS, h]);
                translate([x - NOTCH[0] / 2 + 0.3, Y_F - EPS, V2_Z0]) cube([NOTCH[0] - 0.6, Y_R - Y_F + 2 * EPS, h]);
                translate([x - NOTCH[0] / 2 + 0.3, Y_R, V2_Z0]) cube([NOTCH[0] - 0.6, 3, BASE[0] + BASE[1] - V2_Z0]);
            }
        }
        // screw holes, heads countersunk into the base
        for (b = BOSSES) translate([b[0], b[1], BASE[0] - EPS]) {
            cylinder(d = M3_CLEAR, h = BASE[1] + 2 * EPS);
            translate([0, 0, BASE[1] - 2.4]) cylinder(d = 6.2, h = 2.4 + 2 * EPS);     // an M3 pan head, flush
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
else if (PART == "strip") rotate([180, 0, 0]) strip();
else if (PART == "strip_in_place") strip();
else cradle();
