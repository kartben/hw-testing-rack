// Bay drawer (one per bay) — drawer coordinates: origin at the front-left
// corner of the drawer body, z = 0 on the tray's ledges.
//
//   -D 'PART="drawer"'  the drawer (default)
//   -D 'PART="sled"'    a sled bay's plate: the drawer cut 1 mm in front of its port wall, no chain foot,
//                       no magnet; two flange segments at its rear (lock screws in a fixed bay)
//   -D 'PART="block"'   a sled bay's port block: the drawer's rear bay on its own, locked into the tray by
//                       two PT 2.3 × 8 through the guide lips
//
// - Front panel with a finger pull and a recess for 12 mm label tape.
// - Board-plate pocket: plates drop in (two 180°-symmetric locating pins).
// - Rear bay behind the port wall, one for both DATA boards (a bay converts by changing the board, not the
//   drawer): four U's in the wall, the DATA ×4's ports.  A DATA ×4 v1 on three floor bosses; a DATA ×4 v2,
//   standing, in its cradle (parts/x4_cradle.scad) on the same three; or the single DATA port board on two
//   more, its USB-C behind the fourth U, the optional AUX pigtail through a free one.  Every board's PH 8 lead
//   comes up through the cable window at the rear right, from the drag chain's moving end: a rear strip (the
//   single board's lead, then along the rear wall to its PH; a v2's, over its cradle) and a side strip beside
//   a v1's right edge, under its J1.  The chain foot slides
//   into the rear-open groove under the bottom and is locked by one PT 2.3 × 8 screw from inside the rear bay.
// - Rear flange segments run under the guide lips (anti-tip); a notch under the left wall takes the bump of
//   the tray's printed detent tab (or, drawer.detent: magnet, a magnet under the rear bay over the left ledge).
// - It rides on the tray's two side ledges (parts/tray.scad), so its floor only carries the
//   board plate: nine windows.
// - Pin holes over the node's RESET and BOOT (through every plate too): press them with the drawer in.
// Print: bottom down, PETG, 3 walls, no supports.
include <../lib/carrier.scad>

PART = "drawer";

// drawer.detent: magnet: the magnet sits right inside the left wall, its boss within the drawer's footprint (a boss
// sticking out of the wall would hit the tray's guide lip on the last 10 mm before closing)
DETENT = [DRAWER_MAGNET[0] / 2 + 1, DRAWER_D - 14];
DETENT_BOSS = DRAWER_MAGNET[0] + 2;
RIB = 6;                                       // floor ribs

FRONT_OVERHANG = DRAWER_X0 - 1;            // front panel overhangs the guides
FOOT_GROOVE = [6.4, DRAWER_D - FOOT_HOLE[1] + 1, 2.3];

module front_panel() {
    difference() {
        translate([-FRONT_OVERHANG, 0, 0]) rbox([DRAWER_W + 2 * FRONT_OVERHANG, DRAWER_FRONT_T, DRAWER_FRONT_H], r = 1.2);
        // finger pull: scoop at the top centre
        translate([DRAWER_W / 2, -EPS, DRAWER_FRONT_H]) rotate([-90, 0, 0])
            scale([1, 0.32, 1]) cylinder(r = 28, h = DRAWER_FRONT_T + 2 * EPS, $fn = 96);
        // label recess (12 mm tape)
        translate([DRAWER_W / 2, -EPS, DRAWER_FRONT_H * 0.42]) rotate([90, 0, 0]) mirror([0, 0, 1])
            linear_extrude(0.9) offset(r = 0.6) square([DRAWER_W - 26, 12.4 - 1.2], center = true);
    }
}

function data_hole(h) = [DATA_PCB_X0 + h[0], DATA_PCB_Y0 + DATA_PCB_SIZE[1] - h[1]];   // KiCad → drawer xy
// the DATA ports along the port wall: the DATA ×4's four (config/rack.yaml › pcb.data_port_x4)
PORT_XS = [for (u = DATA_X4_USB) DATA_X4_X0 + u];
assert(abs(DATA_PORT_X[0] - PORT_XS[3]) < 0.01, "the single DATA board's USB-C sits on the fourth port");
// the DATA ×4's bosses: v1's first three holes, which the v2's cradle shares (v1 is not ordered: its front-edge
// ledges are gone, docs/printed-parts-review.md); a fourth hole, if v1 has one, stays unused
X4_HOLES = [for (i = [0 : 2]) let (h = DATA_X4_HOLES[i]) [DATA_X4_X0 + h[0], DATA_PCB_Y0 + DATA_X4_SIZE[1] - h[1]]];
// the single board's two holes: their bosses stand under the DATA ×4's bare underside, Ø5 to keep 0.8 mm
// from its second USB-C's shell leg
ONE_HOLES = [for (h = DATA_PCB_HOLES) data_hole(h)];
// the ledges under its front edge (drawer x from, to), either side of its USB4105's pegs (7 mm off its axis)
ONE_LEDGES = [[DATA_PCB_X0 + 1, DATA_PORT_X[0] - 7], [DATA_PORT_X[0] + 7, DATA_PCB_X0 + DATA_PCB_SIZE[0] - 1]];
function pin_spots() = [for (k = [NODE_RESET, NODE_BOOT]) node_xy(k) - [DRAWER_X0, 0]];   // the node's buttons, drawer xy

module port_wall() {
    y = DRAWER_PORT_WALL_Y;
    t = DRAWER_WALL;
    w = USBC_PLUG_CUT[0];
    r = 1.5;                                        // the U's bottom corners: a right-angle body's fit there
    difference() {
        translate([0, y - t, 0]) cube([DRAWER_W, t, DRAWER_WALL_H]);
        // the DATA ports: the USB-C plug cut's width, from its bottom up through the wall's top
        for (x = PORT_XS) translate([x, y - t - EPS, PORT_Z - USBC_PLUG_CUT[1] / 2]) hull() {
            for (s = [-1, 1]) translate([s * (w / 2 - r), 0, r]) rotate([-90, 0, 0]) cylinder(r = r, h = t + 2 * EPS);
            translate([-w / 2, 0, r]) cube([w, t + 2 * EPS, DRAWER_WALL_H]);
        }
    }
}

// rear = the rear bay (port wall, DATA board, window); foot = the chain foot's groove and boss, the magnet
module drawer(rear = true, foot = true) {
    difference() {
        union() {
            rbox([DRAWER_W, DRAWER_D, DRAWER_BOTTOM], r = 2);
            front_panel();
            // side and rear walls
            for (x = [0, DRAWER_W - DRAWER_WALL]) translate([x, DRAWER_FRONT_T, 0]) cube([DRAWER_WALL, DRAWER_D - DRAWER_FRONT_T, DRAWER_WALL_H]);
            translate([0, DRAWER_D - DRAWER_WALL, 0]) cube([DRAWER_W, DRAWER_WALL, DRAWER_WALL_H]);
            if (rear) port_wall();
            // flange segments captured by the guides
            for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, FLANGE_Y[0], 0]) cube([DRAWER_FLANGE[0] + EPS, FLANGE_Y[1] - FLANGE_Y[0], DRAWER_FLANGE[1]]);
            // plate locating pins
            for (p = plate_pins()) translate([PLATE_X0 + p[0], PLATE_Y0 + p[1], DRAWER_BOTTOM]) cylinder(d = 3.8, h = 2.2);
            // boss for the foot lock screw, and for the detent magnet (drawer.detent: magnet)
            if (foot) {
                translate([FOOT_HOLE[0], FOOT_HOLE[1], 0]) cylinder(d = 9, h = DRAWER_BOTTOM + 4);
                if (DRAWER_DETENT == "magnet") translate([DETENT[0], DETENT[1], 0]) cylinder(d = DETENT_BOSS, h = DRAWER_MAGNET[1] + 1.2);
            }
            if (rear) {
                // the boards' bosses, and two ledges under the single board's front edge (its underside is bare
                // but for its USB4105's pegs)
                for (h = X4_HOLES) translate([h[0], h[1], 0]) cylinder(d = 6, h = DATA_PCB_Z);
                for (h = ONE_HOLES) translate([h[0], h[1], 0]) cylinder(d = 5, h = DATA_PCB_Z);
                for (s = ONE_LEDGES) translate([s[0], DATA_PCB_Y0 - EPS, 0]) cube([s[1] - s[0], 2, DATA_PCB_Z]);
            }
        }
        // rear-open groove for the chain foot, and its lock screw
        if (foot) {
            translate([FOOT_HOLE[0] - FOOT_GROOVE[0] / 2, FOOT_HOLE[1] - 5, -EPS]) cube([FOOT_GROOVE[0], FOOT_GROOVE[1] + 5, FOOT_GROOVE[2]]);
            translate([FOOT_HOLE[0], FOOT_HOLE[1], -EPS]) {
                cylinder(d = 2.8, h = DRAWER_BOTTOM + 5);
                translate([0, 0, DRAWER_BOTTOM + 4 - 2]) cylinder(d = 5.4, h = 2 + EPS);
            }
            // detent magnet from below
            if (DRAWER_DETENT == "magnet") translate([DETENT[0], DETENT[1], 0]) mirror([0, 0, 1]) magnet_pocket(DRAWER_MAGNET[0], DRAWER_MAGNET[1]);
        }
        detent_notch();
        if (rear) {
            // pilots for the boards' (and the cradle's) PT 2.3 × 8, from above
            for (h = concat(X4_HOLES, ONE_HOLES))
                translate([h[0], h[1], DATA_PCB_Z - 7]) cylinder(d = PT_PILOT, h = 7 + EPS);
            // cable window in the rear-bay floor, up to 1 mm off the rear wall and 1 mm short of the foot's boss:
            // a rear strip from 1.5 mm right of the third boss (the single board's lead comes up there and runs
            // left along the rear wall to its PH; a v2's drops behind its cradle), and a side strip 1 mm right of
            // a v1's right edge, from 4 mm behind the port wall (v1's J1 plug is right above)
            wy = DATA_PCB_Y0 + DATA_PCB_SIZE[1] + 1;
            wx = X4_HOLES[2][0] + 4.5;
            sx = DATA_X4_X0 + DATA_X4_SIZE[0] + 1;
            sy = DATA_PCB_Y0 + 4;
            we = FOOT_HOLE[0] - 5.5;
            wr = DRAWER_D - DRAWER_WALL - 1;
            assert(sx < we - 4, "the DATA ×4 is too long for a side strip beside it");
            translate([0, 0, -EPS]) linear_extrude(DRAWER_BOTTOM + 2 * EPS) offset(r = 2) offset(delta = -2) union() {
                translate([wx, wy]) square([we - wx, wr - wy]);
                translate([sx, sy]) square([we - sx, wr - sy]);
            }
        }
        // pin holes over the node's RESET and BOOT
        for (p = pin_spots()) translate([p[0], p[1], -EPS]) cylinder(d = 3.2, h = DRAWER_BOTTOM + 2 * EPS);
        // open floor: 3 × 3 windows between 6 mm ribs, solid side strips (they ride on the
        // tray ledges) and solid rings around the plate pins
        x0 = 8;
        y0 = DRAWER_FRONT_T + 6;
        cw = (DRAWER_W - 2 * x0 - 2 * RIB) / 3;
        ch = (DRAWER_PORT_WALL_Y - 6 - y0 - 2 * RIB) / 3;
        translate([0, 0, -EPS]) linear_extrude(DRAWER_BOTTOM + 2 * EPS) offset(r = 4) offset(delta = -4) difference() {
            for (i = [0 : 2], j = [0 : 2]) translate([x0 + i * (cw + RIB), y0 + j * (ch + RIB)]) square([cw, ch]);
            for (p = plate_pins()) translate([PLATE_X0 + p[0], PLATE_Y0 + p[1]]) circle(r = 7);
        }
    }
}

// a sled: the drawer's front, flange segments under the guide lips at its rear.  Its floor ends open: the board
// plate runs to the port wall (y PLATE_D), over the sled's rear edge, so no rail can cross it there
// the printed detent's notch under the left wall (and a sled's flange): the tray's bump drops into it as the
// drawer closes; a sled gets the same detent
module detent_notch() if (DRAWER_DETENT == "printed")
    translate([DETENT_TAB_X - DRAWER_X0 - 0.2, DETENT_TAB_Y - DETENT_BUMP[1] / 2 - 0.2, -EPS])
        cube([DETENT_TAB[0] + 0.4, DETENT_BUMP[1] + 0.4, DETENT_BUMP[0] + 0.2]);

module sled() difference() {
    union() {
        intersection() {
            drawer(rear = false, foot = false);
            translate([-50, -50, -10]) cube([DRAWER_W + 100, SPLIT + 50, 100]);
        }
        for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, SLED_FLANGE_Y[0], 0])
            cube([DRAWER_FLANGE[0] + EPS, SLED_FLANGE_Y[1] - SLED_FLANGE_Y[0], DRAWER_FLANGE[1]]);
    }
    lock_holes(SLED_LOCK_Y);
    detent_notch();
}

// the port block: the drawer's rear bay on its own, its flanges drilled for the two lock screws
module block() difference() {
    intersection() {
        drawer(rear = true, foot = false);
        translate([-50, SPLIT, -10]) cube([DRAWER_W + 100, 100, 100]);
    }
    lock_holes(BLOCK_LOCK_Y);
}

// under the tray's lip screws (STOP_PIN_X, mirrored on the right): open at the flange's outer edge
module lock_holes(y) for (x = [STOP_PIN_X - DRAWER_X0, DRAWER_W - (STOP_PIN_X - DRAWER_X0)])
    translate([x, y, -EPS]) cylinder(d = LIP_SCREW[3], h = DRAWER_FLANGE[1] + 2 * EPS);

if (PART == "sled") sled();
else if (PART == "block") block();
else drawer();
