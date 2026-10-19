// Bay drawer (one per bay) — drawer coordinates: origin at the front-left
// corner of the drawer body, z = 0 on the tray's ledges.
//
//   -D 'PART="drawer"'  the drawer (default)
//   -D 'PART="sled"'    a sled bay's plate: the drawer cut 1 mm in front of its port wall, no chain foot,
//                       no magnet; two flange segments at its rear (lock screws in a fixed bay)
//   -D 'PART="block"'   a sled bay's port block: the drawer's rear bay on its own, locked into the tray by
//                       two PT 2.6 × 8 through the guide lips; -D PORTS=4: four USB-C (DATA ×4, placeholder)
//
// - Front panel with a finger pull and a recess for 12 mm label tape.
// - Board-plate pocket: plates drop in (two 180°-symmetric locating pins).
// - Rear bay behind the port wall: the DATA port board (USB-C source) on two
//   floor bosses, its USB-C behind a U in the wall facing the board, next to
//   the AUX pigtail slot; its 5-wire PH lead comes up through the cable window
//   behind it from the drag chain's moving end.  The chain foot slides into the rear-open groove under the
//   bottom and is locked by one PT 2.6 × 8 screw from inside the rear bay.
// - Rear flange segments run under the guide lips (anti-tip); a magnet under
//   the rear bay, over the tray's left ledge, gives a soft closed detent.
// - It rides on the tray's two side ledges (parts/tray.scad), so its floor only carries the
//   board plate: nine windows.
// - Pin holes over the node's RESET and BOOT (through every plate too): press them with the drawer in.
// Print: bottom down, PETG, 3 walls, no supports.
include <../lib/carrier.scad>

PART = "drawer";
PORTS = 1;                                     // the port block's DATA ports: 1, or 4 for a DATA ×4 board

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

function data_hole(h) = [DATA_PCB_X0 + h[0], DATA_PCB_Y0 + DATA_PCB_SIZE[1] - h[1]];   // KiCad → drawer xy
// the DATA ports along the port wall: today's board, or four at a 16 mm pitch (right-angle plugs are 12.4 wide)
function port_xs(n) = n == 1 ? [DATA_PORT_X[0]] : [for (k = [0 : n - 1]) DRAWER_W / 2 + (k - (n - 1) / 2) * 16];
X4_HOLES = [[DRAWER_W / 2 - 33, DATA_PCB_Y0 + 8.5], [DRAWER_W / 2 + 33, DATA_PCB_Y0 + 8.5]];   // DATA ×4: placeholder
function pin_spots() = [for (k = [NODE_RESET, NODE_BOOT]) node_xy(k) - [DRAWER_X0, 0]];   // the node's buttons, drawer xy

module port_wall(ports = 1) {
    y = DRAWER_PORT_WALL_Y;
    t = DRAWER_WALL;
    w = USBC_PLUG_CUT[0];
    r = 1.5;                                        // the U's bottom corners: a right-angle body's fit there
    difference() {
        translate([0, y - t, 0]) cube([DRAWER_W, t, DRAWER_WALL_H]);
        // the DATA port(s): the USB-C plug cut's width, from its bottom up through the wall's top
        for (x = port_xs(ports)) translate([x, y - t - EPS, PORT_Z - USBC_PLUG_CUT[1] / 2]) hull() {
            for (s = [-1, 1]) translate([s * (w / 2 - r), 0, r]) rotate([-90, 0, 0]) cylinder(r = r, h = t + 2 * EPS);
            translate([-w / 2, 0, r]) cube([w, t + 2 * EPS, DRAWER_WALL_H]);
        }
        translate([AUX_PORT_X, y - t - EPS, PORT_Z]) rotate([-90, 0, 0])
            hull() for (dx = [-3.0, 3.0]) translate([dx, 0, 0]) cylinder(d = 3.6, h = t + 2 * EPS);
    }
}

// rear = the rear bay (port wall, DATA board, window); foot = the chain foot's groove and boss, the magnet
module drawer(rear = true, foot = true, ports = 1) {
    difference() {
        union() {
            rbox([DRAWER_W, DRAWER_D, DRAWER_BOTTOM], r = 2);
            front_panel();
            // side and rear walls
            for (x = [0, DRAWER_W - DRAWER_WALL]) translate([x, DRAWER_FRONT_T, 0]) cube([DRAWER_WALL, DRAWER_D - DRAWER_FRONT_T, DRAWER_WALL_H]);
            translate([0, DRAWER_D - DRAWER_WALL, 0]) cube([DRAWER_W, DRAWER_WALL, DRAWER_WALL_H]);
            if (rear) port_wall(ports);
            // flange segments captured by the guides
            for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, FLANGE_Y[0], 0]) cube([DRAWER_FLANGE[0] + EPS, FLANGE_Y[1] - FLANGE_Y[0], DRAWER_FLANGE[1]]);
            // plate locating pins
            for (p = plate_pins()) translate([PLATE_X0 + p[0], PLATE_Y0 + p[1], DRAWER_BOTTOM]) cylinder(d = 3.8, h = 2.2);
            // boss for the foot lock screw, and for the detent magnet
            if (foot) {
                translate([FOOT_HOLE[0], FOOT_HOLE[1], 0]) cylinder(d = 9, h = DRAWER_BOTTOM + 4);
                translate([DETENT[0], DETENT[1], 0]) cylinder(d = DETENT_BOSS, h = DRAWER_MAGNET[1] + 1.2);
            }
            if (rear) {
                // the DATA board's two bosses, and a ledge under its front edge either side of the USB4105's
                // pegs (the board's underside is bare but for them); DATA ×4: two bosses, placeholders
                if (ports == 1) {
                    for (h = DATA_PCB_HOLES) translate([each data_hole(h), 0]) cylinder(d = 6, h = DATA_PCB_Z);
                    for (s = [[1, 23], [37, 39]]) translate([DATA_PCB_X0 + s[0], DATA_PCB_Y0 - EPS, 0]) cube([s[1] - s[0], 2, DATA_PCB_Z]);
                } else for (h = X4_HOLES) translate([h[0], h[1], 0]) cylinder(d = 6, h = DATA_PCB_Z);
                // zip-tie anchor for the AUX pigtail in the rear bay
                for (x = [AUX_PORT_X]) translate([x - 5, DRAWER_D - 12, DRAWER_BOTTOM]) difference() {
                    cube([10, 4, 6]);
                    translate([-EPS, 1, 2]) cube([10 + 2 * EPS, 2, 2.4]);
                }
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
            translate([DETENT[0], DETENT[1], 0]) mirror([0, 0, 1]) magnet_pocket(DRAWER_MAGNET[0], DRAWER_MAGNET[1]);
        }
        if (rear) {
            // pilots for the board's two PT 2.6 × 8, from above
            for (h = ports == 1 ? [for (h = DATA_PCB_HOLES) data_hole(h)] : X4_HOLES)
                translate([h[0], h[1], DATA_PCB_Z - 7]) cylinder(d = 2.1, h = 7 + EPS);
            // cable window in the rear-bay floor behind the DATA board, up to 1 mm off the rear wall: the
            // lead comes up through it into the board's PH from the rear; 1 mm short of the foot's boss
            wy = DATA_PCB_Y0 + DATA_PCB_SIZE[1] + 1;
            wx = ports == 1 ? FOOT_HOLE[0] - 48 : DRAWER_W / 2 - 30;
            translate([wx, wy, -EPS]) rbox([ports == 1 ? 42.5 : 60, DRAWER_D - DRAWER_WALL - 1 - wy, DRAWER_BOTTOM + 2 * EPS], r = 3);
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

// a sled: the drawer's front, a low rear rail, flange segments under the guide lips at its rear
module sled() difference() {
    union() {
        intersection() {
            drawer(rear = false, foot = false);
            translate([-50, -50, -10]) cube([DRAWER_W + 100, SPLIT + 50, 100]);
        }
        translate([0, SPLIT - DRAWER_WALL, 0]) cube([DRAWER_W, DRAWER_WALL, 6]);
        for (x = [-DRAWER_FLANGE[0], DRAWER_W]) translate([x, SLED_FLANGE_Y[0], 0])
            cube([DRAWER_FLANGE[0] + EPS, SLED_FLANGE_Y[1] - SLED_FLANGE_Y[0], DRAWER_FLANGE[1]]);
    }
    lock_holes(SLED_LOCK_Y);
}

// the port block: the drawer's rear bay on its own, its flanges drilled for the two lock screws
module block(ports = 1) difference() {
    intersection() {
        drawer(rear = true, foot = false, ports = ports);
        translate([-50, SPLIT, -10]) cube([DRAWER_W + 100, 100, 100]);
    }
    lock_holes(BLOCK_LOCK_Y);
}

module lock_holes(y) for (x = [-DRAWER_FLANGE[0] / 2, DRAWER_W + DRAWER_FLANGE[0] / 2])
    translate([x, y, -EPS]) cylinder(d = 2.8, h = DRAWER_FLANGE[1] + 2 * EPS);

if (PART == "sled") sled();
else if (PART == "block") block(PORTS);
else drawer();
