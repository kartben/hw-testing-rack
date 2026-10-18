// Bay drawer (one per bay) — drawer coordinates: origin at the front-left
// corner of the drawer body, z = 0 on the tray's ledges.
//
// - Front panel with a finger pull and a recess for 12 mm label tape.
// - Board-plate pocket: plates drop in (two 180°-symmetric locating pins).
// - Rear bay behind the port wall: the DATA port board (USB-C source) under a
//   roof, its USB-C flush with the wall facing the board, next to the AUX
//   pigtail slot; its 5-wire PH lead comes up through the cable window from
//   the drag chain's moving end.  The chain foot slides into the rear-open groove under the
//   bottom and is locked by one PT 2.6 × 8 screw from inside the rear bay.
// - Rear flange segments run under the guide lips (anti-tip); a magnet under
//   the rear bay, over the tray's left ledge, gives a soft closed detent.
// - It rides on the tray's two side ledges (parts/tray.scad), so its floor only carries the
//   board plate: nine windows.
// Print: bottom down, PETG, 3 walls, no supports.
include <../lib/carrier.scad>

// the magnet sits right inside the left wall, its boss within the drawer's footprint (a boss
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

module port_wall() {
    y = DRAWER_PORT_WALL_Y;
    t = DRAWER_WALL + 1;
    W = DATA_PCB_SIZE[0];
    x0 = DATA_PCB_X0 - 1.5;                         // the roof: the board's width, 1.5 mm more on the left
    difference() {
        union() {
            translate([0, y - DRAWER_WALL, 0]) cube([DRAWER_W, t, PORT_WALL_H]);
            // the DATA board's roof, a bridge from the port wall to the rear wall, over the board and
            // its lead's plug; the rear wall raised under its far end
            translate([x0, y - DRAWER_WALL + t - EPS, DATA_ROOF_Z])
                cube([W + 2, DRAWER_D - DRAWER_WALL - (y - DRAWER_WALL + t) + 2 * EPS, PORT_WALL_H - DATA_ROOF_Z]);
            translate([x0, DRAWER_D - DRAWER_WALL, 0]) cube([W + 2, DRAWER_WALL, PORT_WALL_H]);
        }
        // the board's front edge through the wall, flush with its front face (2 mm under it for the
        // small parts), and the USB-C receptacle below it
        translate([DATA_PCB_X0 - 0.3, y - DRAWER_WALL - EPS, DATA_ROOF_Z - DATA_PCB_T - 2])
            cube([W + 0.6, t + 2 * EPS, DATA_PCB_T + 2 + EPS]);
        translate([DATA_PORT_X[0] - DATA_USB[0] / 2 - 0.3, y - DRAWER_WALL - EPS, DATA_ROOF_Z - DATA_PCB_T - DATA_USB[1] - 0.3])
            cube([DATA_USB[0] + 0.6, t + 2 * EPS, DATA_USB[1] + 0.3 + EPS]);
        // pilots for the board's two PT 2.6 × 8, up into the roof
        for (h = DATA_PCB_HOLES) translate([DATA_PCB_X0 + h[0], DATA_PCB_Y0 + DATA_PCB_SIZE[1] - h[1], DATA_ROOF_Z - EPS])
            cylinder(d = 2.1, h = 6.6);
        translate([AUX_PORT_X, y - DRAWER_WALL - EPS, PORT_Z]) rotate([-90, 0, 0])
            hull() for (dx = [-3.0, 3.0]) translate([dx, 0, 0]) cylinder(d = 3.6, h = t + 2 * EPS);
    }
}

module drawer() {
    difference() {
        union() {
            rbox([DRAWER_W, DRAWER_D, DRAWER_BOTTOM], r = 2);
            front_panel();
            // side and rear walls
            for (x = [0, DRAWER_W - DRAWER_WALL]) translate([x, DRAWER_FRONT_T, 0]) cube([DRAWER_WALL, DRAWER_D - DRAWER_FRONT_T, DRAWER_WALL_H]);
            translate([0, DRAWER_D - DRAWER_WALL, 0]) cube([DRAWER_W, DRAWER_WALL, DRAWER_WALL_H]);
            port_wall();
            // flange segments captured by the guides
            for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, FLANGE_Y[0], 0]) cube([DRAWER_FLANGE[0] + EPS, FLANGE_Y[1] - FLANGE_Y[0], DRAWER_FLANGE[1]]);
            // plate locating pins
            for (p = plate_pins()) translate([PLATE_X0 + p[0], PLATE_Y0 + p[1], DRAWER_BOTTOM]) cylinder(d = 3.8, h = 2.2);
            // boss for the foot lock screw, and for the detent magnet
            translate([FOOT_HOLE[0], FOOT_HOLE[1], 0]) cylinder(d = 9, h = DRAWER_BOTTOM + 4);
            translate([DETENT[0], DETENT[1], 0]) cylinder(d = DETENT_BOSS, h = DRAWER_MAGNET[1] + 1.2);
            // zip-tie anchor for the AUX pigtail in the rear bay (the DATA lead comes up under the roof)
            for (x = [AUX_PORT_X]) translate([x - 5, DRAWER_D - 12, DRAWER_BOTTOM]) difference() {
                cube([10, 4, 6]);
                translate([-EPS, 1, 2]) cube([10 + 2 * EPS, 2, 2.4]);
            }
        }
        // rear-open groove for the chain foot, and its lock screw
        translate([FOOT_HOLE[0] - FOOT_GROOVE[0] / 2, FOOT_HOLE[1] - 5, -EPS]) cube([FOOT_GROOVE[0], FOOT_GROOVE[1] + 5, FOOT_GROOVE[2]]);
        translate([FOOT_HOLE[0], FOOT_HOLE[1], -EPS]) {
            cylinder(d = 2.8, h = DRAWER_BOTTOM + 5);
            translate([0, 0, DRAWER_BOTTOM + 4 - 2]) cylinder(d = 5.4, h = 2 + EPS);
        }
        // cable window in the rear-bay floor, under the DATA board, up to 1 mm off the rear wall: the
        // lead comes up through it into the board's PH from the rear, and the board's screws go in
        // from below through it; 1 mm short of the foot's boss
        translate([FOOT_HOLE[0] - 48, DRAWER_PORT_WALL_Y + 2, -EPS])
            rbox([42.5, DRAWER_D - DRAWER_WALL - 1 - DRAWER_PORT_WALL_Y - 2, DRAWER_BOTTOM + 2 * EPS], r = 3);
        // detent magnet from below
        translate([DETENT[0], DETENT[1], 0]) mirror([0, 0, 1]) magnet_pocket(DRAWER_MAGNET[0], DRAWER_MAGNET[1]);
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

drawer();
