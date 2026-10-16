// Small frame accessories.
//
//   -D 'PART="foot"'       TPU foot under each corner post (M5 into the post's core)
//   -D 'PART="slot_clip"'  snap clip holding up to four 0.75 mm² wires in a 2020 slot
//   -D 'PART="label"'      12 × 100 mm label blank for the drawer front recess
include <../lib/carrier.scad>

PART = "foot";

module foot() {
    difference() {
        hull() {
            translate([-12, -12, 0]) rbox([24, 24, 1], r = 4);
            translate([-10, -10, FRAME_FOOT_H - 1]) rbox([20, 20, 1], r = 3);
        }
        translate([0, 0, -EPS]) cylinder(d = M5_CLEAR, h = FRAME_FOOT_H + 1);
        translate([0, 0, -EPS]) cylinder(d = 9.5, h = FRAME_FOOT_H - 3);
    }
}

module slot_clip() {
    // T-profile that snaps into the 6 mm slot; wires sit in the channel behind the cover
    difference() {
        union() {
            translate([-12, -5.8 / 2, 0]) cube([24, 5.8, 6]);          // body in the slot
            translate([-12, -10 / 2, 6]) cube([24, 10, 1.2]);           // cover flush with the profile face
            for (s = [-1, 1]) translate([-12, s * 2.9 - (s > 0 ? 0 : 1.2), 1]) cube([24, 1.2, 2]);   // barbs
        }
        translate([-12 - EPS, -3.8 / 2, -EPS]) cube([24 + 2 * EPS, 3.8, 5]);
    }
}

module label() {
    difference() {
        rbox([100, 12, 1.0], r = 1);
    }
}

if (PART == "foot") foot();
else if (PART == "slot_clip") slot_clip();
else label();
