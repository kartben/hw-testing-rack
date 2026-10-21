// Drawer covers (optional): the rear bay closed from above, printed once a bay is validated
// (docs/printed-parts-review.md, finding 17; the drawer-covers study).  One family, one fixing:
//
//   -D 'PART="lid1"'   a single DATA port board's bay: a flat lid on the four walls' tops
//   -D 'PART="box4"'   a DATA ×4 bay: the same outline and fixing raised into a box over the standing v2 in its
//                      cradle, its four headers' Dupont blocks under a notch in the front (it lifts off with the
//                      DUT leads plugged), a window in front of each port's LED and D1, vents over the board
//
// Both hook over the port wall's front face (lips between the U's, clear of the plugs' overmolds) and click
// into two pockets in the rear wall's inner face with two side-hinged tabs: each a strip of the rear skirt, free
// at one end, run up through a slot in the top to the bed, so it bends in the print plane (1.2 % for its 0.7 mm
// bump).  Lift the rear with a fingertip in the hole (or the box by its sides): the bumps let go both ways.
// Drawer coordinates (parts/drawer.scad).  Print: top face down, PETG, no supports.
include <../lib/carrier.scad>

PART = "lid1";
T = 1.6;                                   // walls
Z0 = DRAWER_WALL_H;                        // the drawer walls' top
PW = DRAWER_PORT_WALL_Y;                   // the port wall's back face; its front face PW − DRAWER_WALL
X0 = 0.3;  X1 = DRAWER_W - 0.3;            // inside the drawer's outline
YF = PW - DRAWER_WALL - 0.1 - T;           // the front lip / the box's front wall: just in front of the port wall
YB = DRAWER_D - 0.3;
PORT_XS = [for (u = DATA_X4_USB) DATA_X4_X0 + u];
UHW = USBC_PLUG_CUT[0] / 2 + 1.2;          // the lips stay this far from each U's axis (the plugs' overmolds)
LIP = 3;                                   // their drop
LIP_SEGS = [[DRAWER_WALL + 0.1, PORT_XS[0] - UHW], [PORT_XS[3] + UHW, DRAWER_W - DRAWER_WALL - 0.1]];
FOOT = [128, 172];                         // the chain foot's lock screw, reached from above

// the detent: COVER_TABS (lib/carrier.scad) — a tab 14 long, the hinge post 2, the skirt's inner face 0.1 off
// the rear wall, the bump 0.7 at the free end, 2.4 tall, low on the skirt
SKIRT = [DRAWER_D - DRAWER_WALL - 0.1 - 1.5, DRAWER_D - DRAWER_WALL - 0.1];   // its y
SKIRT_Z0 = 6;                              // its bottom
SLOT = 0.6;

// the box (box4): over the standing DATA ×4 v2 (config/rack.yaml › pcb.data_port_x4_v2)
TOP4 = 72.5 + 2.4 + 2 + T;                 // the board's top, its cradle's hooks (0.8), 2 mm clear, the top
V2H = 4;                                   // board x → drawer x
HDR_X = [for (x = [22, 40, 58, 76]) V2H + x - 7.62];   // the 2 × 6 headers' left ends, their z round 28.5
HDR_Z = [28.5 - 2.54, 28.5 + 2.54];
SLOT_M = 0.6;                              // round a Dupont block
LEDS = concat([for (x = [22, 40, 58, 76]) [V2H + x - 5.2, 35.5]], [[59.4, 70.1]]);   // VBUS per port, and D1

// one detent: the skirt's strip between the hinge post and the free end, the bump on its back near the free end
module bump(xc) translate([xc + 3, SKIRT[1], SKIRT_Z0 + 1]) rotate([90, 0, 90]) linear_extrude(5)
    polygon([[-EPS, 0], [COVER_BUMP, COVER_BUMP], [COVER_BUMP, COVER_BUMP + 1], [-EPS, 2 * COVER_BUMP + 1]]);
module tab(xc, top) {
    translate([xc - 8, SKIRT[0], SKIRT_Z0]) cube([16, SKIRT[1] - SKIRT[0], top - SKIRT_Z0]);
    bump(xc);
}
// what frees it: a slit at its free end through the skirt and the top over it, and the top round its other sides
module tab_cuts(xc, top, plate_z0) {
    translate([xc + 8, SKIRT[0] - 1, SKIRT_Z0 - 1]) cube([SLOT, SKIRT[1] - SKIRT[0] + 2, top + 2]);
    translate([xc - 6, SKIRT[0] - SLOT, plate_z0 - EPS]) difference() {
        cube([14 + SLOT, SKIRT[1] - SKIRT[0] + 2 * SLOT, top - plate_z0 + 1]);
        translate([0, SLOT, -1]) cube([14, SKIRT[1] - SKIRT[0], top + 2]);
    }
}

module lips() for (s = LIP_SEGS) translate([s[0], YF, Z0 - LIP]) cube([s[1] - s[0], T, LIP + EPS]);

module lid1() difference() {
    union() {
        translate([X0, YF, Z0]) cube([X1 - X0, YB - YF, T]);
        lips();
        for (x = COVER_TABS) tab(x, Z0 + T);
    }
    for (x = COVER_TABS) tab_cuts(x, Z0 + T, Z0);
    translate([FOOT[0], FOOT[1], Z0 - 1]) cylinder(d = 7, h = T + 2);                     // the foot's screw
    translate([64, YB - 12, Z0 - 1]) hull() for (x = [0, 10]) translate([x + 2, 4, 0]) cylinder(d = 4, h = T + 2);   // a finger hole
}

module box4() difference() {
    union() {
        // the shell: front wall in front of the port wall, sides on the drawer's side walls, the rear skirt inside
        // the rear wall, the top
        difference() {
            translate([X0, YF, Z0]) cube([X1 - X0, SKIRT[1] - YF, TOP4 - Z0]);
            translate([X0 + T, YF + T, Z0 - EPS]) cube([X1 - X0 - 2 * T, SKIRT[0] - YF - T, TOP4 - T - Z0 + EPS]);
        }
        translate([X0 + T, SKIRT[0], SKIRT_Z0]) cube([X1 - X0 - 2 * T, SKIRT[1] - SKIRT[0], Z0 - SKIRT_Z0 + EPS]);
        for (x = COVER_TABS) bump(x);
        // on the rear wall's top, a ledge (45° under it, as printed)
        translate([X0, SKIRT[1] - EPS, Z0]) rotate([90, 0, 90]) linear_extrude(X1 - X0)
            polygon([[0, 0], [YB - SKIRT[1] + EPS, 0], [YB - SKIRT[1] + EPS, T], [0, T + YB - SKIRT[1]]]);
        lips();
        // on the port wall's top between the U's, a ledge (45° under it)
        for (s = LIP_SEGS) translate([s[0], YF + T - EPS, Z0]) rotate([90, 0, 90]) linear_extrude(s[1] - s[0])
            polygon([[0, 0], [PW - (YF + T), 0], [PW - (YF + T), T], [0, T + PW - (YF + T)]]);
    }
    for (x = COVER_TABS) {
        tab_cuts(x, TOP4, TOP4 - T);
        translate([x - 6, SKIRT[1] - EPS, Z0 - 1]) cube([14 + SLOT, YB - SKIRT[1] + 1, 2 * T + 4]);   // the ledge off the tab
    }
    // the headers' Dupont blocks: one notch open at the bottom, so the box lifts off with the DUT leads plugged
    translate([HDR_X[0] - SLOT_M, YF - EPS, Z0 - LIP - 1]) cube([HDR_X[3] - HDR_X[0] + 15.24 + 2 * SLOT_M, T + 2 * EPS, HDR_Z[1] + SLOT_M - (Z0 - LIP - 1)]);
    for (l = LEDS) translate([l[0], YF - EPS, l[1]]) rotate([-90, 0, 0]) cylinder(d = 3.5, h = T + 2 * EPS);
    for (x = [20 : 10 : 100]) translate([x - 1.25, 175, TOP4 - T - 1]) cube([2.5, 25, T + 2]);   // vents over the board
    translate([FOOT[0], FOOT[1], TOP4 - T - 1]) cylinder(d = 7, h = T + 2);
}

if (PART == "lid1") rotate([180, 0, 0]) lid1();
else if (PART == "box4") rotate([180, 0, 0]) box4();
else if (PART == "lid1_in_place") lid1();
else if (PART == "box4_in_place") box4();
