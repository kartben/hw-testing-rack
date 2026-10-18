// Bay drawer (one per bay) — drawer coordinates: origin at the front-left
// corner of the drawer body, z = 0 on the tray's ledges.
//
// - Front panel with a finger pull and a recess for 12 mm label tape.
// - Board-plate pocket: plates drop in (two 180°-symmetric locating pins).
// - Rear bay behind the port wall: the panel-mount USB-C DATA socket faces the
//   board from one of two positions (left or right: whichever is farther from
//   the board's USB, so the two plugs never meet), next to the AUX pigtail
//   slot; the cables come up from the drag chain through the cable window.  The chain foot slides into the rear-open groove under the
//   bottom and is locked by one M2.5 screw from inside the rear bay.
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
    difference() {
        translate([0, y - DRAWER_WALL, 0]) cube([DRAWER_W, DRAWER_WALL + 1, DRAWER_WALL_H]);
        // DATA sockets: open to the plug's overmold, so the plug seats whether the panel-mount
        // socket sits behind the 3 mm wall (ears on the rear face) or passes through it
        for (x = PORT_X) translate([x, y - DRAWER_WALL - EPS, PORT_Z]) rotate([-90, 0, 0]) {
            if (x == AUX_PORT_X) hull() for (dx = [-3.0, 3.0]) translate([dx, 0, 0]) cylinder(d = 3.6, h = DRAWER_WALL + 2);
            else usbc_plug_cut(DRAWER_WALL + 2);
            for (dx = [-PORT_EARS / 2, PORT_EARS / 2]) translate([dx, 0, 0]) cylinder(d = 3.2, h = DRAWER_WALL + 2);
        }
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
            // zip-tie anchors for the port cables in the rear bay
            for (x = PORT_X) translate([x - 5, DRAWER_D - 12, DRAWER_BOTTOM]) difference() {
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
        // cable window in the rear-bay floor (big enough to pass a panel-mount connector)
        translate([FOOT_HOLE[0] - 48, DRAWER_PORT_WALL_Y + 2, -EPS]) rbox([40, 18, DRAWER_BOTTOM + 2 * EPS], r = 3);
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
