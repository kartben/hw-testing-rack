// Board plate — the swappable "form-factor" plate a dev board is screwed to.
//
//   openscad -D 'BOARD="nucleo-144"' -o plate_nucleo-144.stl parts/board_plate.scad
//   openscad -D 'BOARD="universal"'  -o plate_universal.stl  parts/board_plate.scad
//   openscad -D 'BOARD="nucleo-64"' -D 'MODE="snap"' ...   (tool-less snap pins)
//   openscad -D 'BAY="B3"' -o plate_bay_b3.stl parts/board_plate.scad   (a converted bay: its boards, one plate)
//
// Plates drop into any drawer (two 180°-symmetric locating pins), so a board
// can move between bays without touching a screw.  The board is placed with
// its debug USB facing the drawer's rear port wall; boards too long for a plug
// behind them (usb_side) turn it to the right wall instead and sit to the left.
// The short cable loops under the two cable hooks.
//   MODE = "insert": heat-set inserts (M3, or M2/M2.5 for small boards)
//   MODE = "snap"  : split snap pins, push the board on, pinch to release
// Hole-less or not-yet-measured boards (fence = true) get corner fences.
// Print: flat, PETG/PLA, 2–3 walls; ~15 min per plate.
include <../lib/carrier.scad>
include <../generated/boards.scad>

BOARD = "universal";
BAY = "";                             // a converted bay's shared plate (generated/boards.scad › BAY_PLATES)
MODE = "insert";
REAR_GAP_MAX = 26;                    // room for the USB plug + cable bend behind the board
SIDE_X = 2.5;                         // a usb_side board's gap to the plate's left edge (tools/webscene.py)

function board_rec(id) = BOARD_DB[search([id], BOARD_DB, 1, 0)[0]];
function rear_gap(l) = max(3, min(REAR_GAP_MAX, PLATE_D - l - 4));
function usb_side(rec) = len(rec) > 12 && rec[12];
function board_origin(rec) = usb_side(rec)
    ? [SIDE_X, (PLATE_D - rec[2][1]) / 2]
    : [(PLATE_W - rec[2][0]) / 2, PLATE_D - rear_gap(rec[2][1]) - rec[2][1]];

module plate_body() {
    difference() {
        rbox([PLATE_W, PLATE_D, PLATE_T], r = 3);
        for (p = plate_pins()) translate([p[0], p[1], -EPS]) cylinder(d = 4.2, h = PLATE_T + 1);
        // finger holes to lift the plate out
        for (x = [12, PLATE_W - 12]) translate([x, PLATE_D / 2, -EPS]) rslot(14, 9, PLATE_T + 1);
        // pin holes over the node's RESET and BOOT, as in the drawer's floor
        for (q = button_holes()) translate(concat(q, [-EPS]))
            cylinder(d = 3.2, h = PLATE_T + 1);
    }
}

module insert_standoff(hole_d, h) {
    ins = hole_d < 2.4 ? INSERT_M2 : hole_d < 3.0 ? INSERT_M25 : INSERT_M3;
    difference() {
        cylinder(d1 = ins[0] + 5, d2 = ins[0] + 3, h = h);
        translate([0, 0, h]) insert_hole(ins);
    }
}

module snap_standoff(hole_d, h) {
    pcb_t = 1.75;
    cylinder(d1 = hole_d + 6, d2 = hole_d + 4, h = h);
    difference() {
        union() {
            translate([0, 0, h]) cylinder(d = hole_d - 0.25, h = pcb_t + 0.3);
            translate([0, 0, h + pcb_t]) cylinder(d1 = hole_d + 0.5, d2 = hole_d - 0.7, h = 2.0);
        }
        translate([-0.55, -hole_d, h + 0.6]) cube([1.1, 2 * hole_d, pcb_t + 3]);
    }
}

module fences(rec, o) {
    size = rec[2]; h = rec[7]; c = 0.3;
    for (sx = [0, 1], sy = [0, 1]) {
        px = o[0] + sx * size[0] + (sx ? c : -c);
        py = o[1] + sy * size[1] + (sy ? c : -c);
        translate([px, py, PLATE_T]) mirror([sx, 0, 0]) mirror([0, sy, 0]) translate([-2, -2, 0])
            difference() {
                cube([9, 9, h + 2.4]);
                translate([2, 2, h]) cube([9, 9, 10]);
            }
    }
    // support pads
    for (fx = [0.2, 0.8], fy = [0.2, 0.8])
        translate([o[0] + fx * size[0], o[1] + fy * size[1], PLATE_T]) cylinder(d = 6, h = h);
}

module cable_hooks(rec, o) {
    // two open hooks either side of the USB plug path
    if (usb_side(rec)) {
        uy = o[1] + rec[5];
        for (dy = [-22, 22]) translate([PLATE_W - 8, uy + dy, PLATE_T]) rotate([0, 0, 90]) hook();
    } else {
        ux = o[0] + rec[5];
        for (dx = [-22, 22]) translate([ux + dx, PLATE_D - 8, PLATE_T]) hook();
    }
}

module hook() {
    difference() {
        translate([-5, -3, 0]) cube([10, 6, 9]);
        translate([-5 - EPS, 0, 5]) rotate([0, 90, 0]) cylinder(d = 4.6, h = 10 + 2 * EPS);
        translate([-5 - EPS, -0.8, 5]) cube([10 + 2 * EPS, 1.6, 5]);
    }
}

module lightening(rec, o) {
    size = rec[2];
    for (x = [14 : 13 : PLATE_W - 14], y = [12 : 11.3 : PLATE_D - 14]) {
        xx = x + ((round(y / 11.3) % 2) ? 6.5 : 0);
        inside = xx > o[0] - 8 && xx < o[0] + size[0] + 8 && y > o[1] - 8 && y < o[1] + size[1] + 8;
        near_pin = norm([xx, y] - plate_pins()[0]) < 10 || norm([xx, y] - plate_pins()[1]) < 10;
        if (!inside && !near_pin && xx < PLATE_W - 10)
            translate([xx, y, -EPS]) cylinder(d = 10, h = PLATE_T + 2 * EPS, $fn = 6);
    }
}

module universal_plate() {
    difference() {
        plate_body();
        // M3 slots on a 12 mm pitch: bolt standard nylon/brass standoffs anywhere
        for (y = [18 : 12 : PLATE_D - 18]) for (xc = [PLATE_W * 0.27, PLATE_W * 0.73])
            translate([xc, y, -EPS]) rslot(PLATE_W * 0.42, M3_CLEAR, PLATE_T + 2 * EPS);
        translate([PLATE_W / 2, 7, PLATE_T - 0.5]) label_text("UNIVERSAL - M3", size = 4, depth = 0.5 + EPS);
    }
}

module board_plate(id) {
    rec = board_rec(id);
    o = board_origin(rec);
    difference() {
        union() {
            plate_body();
            if (rec[8] || len(rec[4]) == 0) fences(rec, o);
            else for (h = rec[4]) translate([o[0] + h[0], o[1] + h[1], PLATE_T])
                if (MODE == "snap") snap_standoff(rec[3], rec[7]); else insert_standoff(rec[3], rec[7]);
            cable_hooks(rec, o);
        }
        lightening(rec, o);
        translate([PLATE_W / 2, 7, PLATE_T - 0.5]) label_text(rec[1], size = 4.5, depth = 0.5 + EPS);
    }
}

// A converted bay (config/rack.yaml › population › boards, a DATA ×4 board behind the port wall): its
// boards on one plate, each at its `at` on its own standoffs or fences, its port number engraved in
// front of it.  No cable hooks: each cable runs back to its own socket.  tools/rackcfg.py checks the
// layout (check_bay_plate): on the plate, apart, clear of the pins, finger slots and RESET/BOOT holes.
function bay_rec(id) = BAY_PLATES[search([id], BAY_PLATES, 1, 0)[0]];
function button_holes() = [for (k = [NODE_RESET, NODE_BOOT]) node_xy(k) - [DRAWER_X0 + PLATE_X0, PLATE_Y0]];

module bay_lightening(places) {
    keep = concat(plate_pins(), button_holes(), [[12, PLATE_D / 2], [PLATE_W - 12, PLATE_D / 2]]);
    for (x = [14 : 13 : PLATE_W - 14], y = [12 : 11.3 : PLATE_D - 14]) {
        xx = x + ((round(y / 11.3) % 2) ? 6.5 : 0);
        over = [for (b = places) let(o = b[1], size = b[2][2])
            if (xx > o[0] - 8 && xx < o[0] + size[0] + 8 && y > o[1] - 11 && y < o[1] + size[1] + 8) 1];
        near = [for (q = keep) if (norm([xx, y] - q) < 12) 1];
        label = abs(xx - PLATE_W / 2) < 30 && y < 20;
        if (len(over) == 0 && len(near) == 0 && !label && xx < PLATE_W - 10)
            translate([xx, y, -EPS]) cylinder(d = 10, h = PLATE_T + 2 * EPS, $fn = 6);
    }
}

module bay_plate(id) {
    bay = bay_rec(id);
    assert(bay != undef, str("no converted bay ", id, " in BAY_PLATES: tools/build.py config"));
    assert(bay[1] == "boards", str("plate kind ", bay[1], ": not made yet"));
    places = bay[2];                  // [slot, [x, y], board record]
    difference() {
        union() {
            plate_body();
            for (b = places) let(rec = b[2], o = b[1])
                if (rec[8] || len(rec[4]) == 0) fences(rec, o);
                else for (h = rec[4]) translate([o[0] + h[0], o[1] + h[1], PLATE_T])
                    if (MODE == "snap") snap_standoff(rec[3], rec[7]); else insert_standoff(rec[3], rec[7]);
        }
        bay_lightening(places);
        translate([PLATE_W / 2, 7, PLATE_T - 0.5]) label_text(id, size = 4.5, depth = 0.5 + EPS);
        for (b = places) translate([b[1][0] + b[2][2][0] / 2, b[1][1] - 6, PLATE_T - 0.5])
            label_text(str(b[0]), size = 4, depth = 0.5 + EPS);
    }
}

if (BAY != "") bay_plate(BAY);
else if (BOARD == "universal") universal_plate(); else board_plate(BOARD);
