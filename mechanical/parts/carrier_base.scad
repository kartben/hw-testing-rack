// Bay carrier — base (one per bay).
//
// Sits on the front and rear 2020 beams of a row and forms the "plenum"
// that hides the bay-node PCB and the drawer's drag chain.  Its bottom plate
// is the ceiling of the bay below (camera pods screw into it from under);
// its front wall is the bay's fascia: PC/classic USB-C port, status LED
// window and the SERVICE slide switch.
// Print: bottom plate down, PETG/ASA, 0.2 mm, 3 walls, 15–20 % infill, no supports.
include <../lib/carrier.scad>

module fascia_cutouts() {
    // [kicad_x, width, height, z above PCB top]
    cuts = [
        [NODE_FRONT[0], 9.6, 3.8, 1.6, "usbc"],    // PC / classic USB-C
        [NODE_FRONT[1], 3.2, 3.2, 0.7, "round"],   // status LED window
        [NODE_FRONT[2], 7.4, 3.0, 1.4, "rect"],    // SERVICE switch
    ];
    for (c = cuts) {
        x = NODE_X0 + c[0];
        z = NODE_PCB_TOP + c[3];
        translate([x, -EPS, z]) rotate([-90, 0, 0]) {
            if (c[4] == "usbc") hull() for (dx = [-(c[1] - c[2]) / 2, (c[1] - c[2]) / 2])
                translate([dx, 0, 0]) cylinder(d = c[2], h = CARRIER_FASCIA + 2);
            else if (c[4] == "round") cylinder(d = c[1], h = CARRIER_FASCIA + 2);
            else translate([-c[1] / 2, -c[2] / 2, 0]) cube([c[1], c[2], CARRIER_FASCIA + 2]);
        }
    }
    // embossed icons above the cut-outs would be lovely but kill bridging; labels go on the drawer
}

module carrier_base() {
    difference() {
        intersection() {
        rbox([CARRIER_W, CARRIER_D, CARRIER_WALL_H + 1], r = 3);
        union() {
            rbox([CARRIER_W, CARRIER_D, CARRIER_BOTTOM], r = 3);
            // perimeter walls
            difference() {
                rbox([CARRIER_W, CARRIER_D, CARRIER_WALL_H], r = 3);
                translate([WALL, CARRIER_FASCIA, -EPS])
                    rbox([CARRIER_W - 2 * WALL, CARRIER_D - CARRIER_FASCIA - WALL, CARRIER_WALL_H + 1], r = 1.5);
            }
            // node PCB standoffs
            for (h = NODE_HOLES) translate(concat(node_xy(h), [0]))
                cylinder(d = BOSS_D, h = CARRIER_BOTTOM + CARRIER_STANDOFF);
            // side screw bosses (merge with the walls) and deck pillars
            for (b = side_screws()) translate([b[0], b[1], 0]) cylinder(d = BOSS_D, h = CARRIER_WALL_H);
            for (b = deck_pillars()) translate([b[0], b[1], 0]) cylinder(d = 9, h = CARRIER_WALL_H);
            // camera-pod insert bosses (inserts go in from below)
            for (c = cam_inserts()) translate([c[0], c[1], 0]) cylinder(d = 7.5, h = CARRIER_BOTTOM + 4);
            // drag-chain fixed-end anchor (2 × M3 inserts)
            translate([CHAIN_FIXED_RUN_X, CHAIN_FIXED[1] - 8, 0])
                for (dx = [-8, 8]) translate([dx, 0, 0]) cylinder(d = 7.5, h = CARRIER_BOTTOM + 3);
            // low guide rails keeping the chain runs straight
            for (x = [CHAIN_FIXED_RUN_X - CHAIN_H / 2 - 1.6, CHAIN_MOVING_X + CHAIN_H / 2 + 0.4])
                translate([x, CHAIN_FIXED[1], 0]) cube([1.2, CARRIER_D - CHAIN_FIXED[1] - 30, CARRIER_BOTTOM + 3]);
        }
        }
        // inserts
        for (h = NODE_HOLES) translate(concat(node_xy(h), [CARRIER_BOTTOM + CARRIER_STANDOFF])) insert_hole(INSERT_M3);
        for (b = concat(side_screws(), deck_pillars())) translate([b[0], b[1], CARRIER_WALL_H]) insert_hole(INSERT_M3);
        for (c = cam_inserts()) translate([c[0], c[1], 0]) mirror([0, 0, 1]) insert_hole(INSERT_M3);
        translate([CHAIN_FIXED_RUN_X, CHAIN_FIXED[1] - 8, CARRIER_BOTTOM + 3])
            for (dx = [-8, 8]) translate([dx, 0, 0]) insert_hole(INSERT_M3);
        // beam fixing: M5 slots over the beams' top T-slots (slot centre 10 mm in from the edge)
        for (y = [FRAME_PROFILE / 2, CARRIER_D - FRAME_PROFILE / 2], x = [26, CARRIER_W - 26])
            translate([x, y, -EPS]) rslot(12, M5_CLEAR, CARRIER_BOTTOM + 2);
        fascia_cutouts();
        // bay label recess on the fascia, right of the controls
        translate([CARRIER_W - 34, 0.6 - EPS, CARRIER_WALL_H / 2]) rotate([90, 0, 0])
            linear_extrude(0.7) square([52, 11], center = true);
        // 24 V jumper notches through both side walls, at the node's JST PH height (a PHR-2 plug,
        // 6 × 4.5 mm, threads through)
        for (x = [-EPS, CARRIER_W - WALL - EPS])
            translate([x, PWR_NOTCH_Y - 4.5, CARRIER_BOTTOM + CARRIER_STANDOFF])
                cube([WALL + 2 * EPS, 9, CARRIER_WALL_H]);
        // camera 5 V cable to the pod below
        translate([CAM_CABLE_HOLE[0], CAM_CABLE_HOLE[1], -EPS]) rslot(10, 5, CARRIER_BOTTOM + 2);
        // rear service slot (row feed for the left bay, top-row camera cables, airflow)
        translate([20, CARRIER_D - WALL - EPS, CARRIER_BOTTOM + 2]) cube([60, WALL + 2 * EPS, CARRIER_WALL_H - 5]);
        // material relief in the bottom plate (keeps clear of beams, bosses and the chain)
        for (y = [NODE_REAR_Y + 18 : 18 : CARRIER_D - 34], x = [12 : 18 : 70])
            if (norm([x + 6, y + 6] - CAM_CENTER) > 26 && norm([x + 6, y + 6] - CAM_CABLE_HOLE) > 12
                && norm([x + 6, y + 6] - [40, 165]) > 12 && norm([x + 6, y + 6] - [82, 165]) > 12)
                translate([x, y, -EPS]) rbox([12, 12, CARRIER_BOTTOM + 2 * EPS], r = 3);
    }
}

carrier_base();
