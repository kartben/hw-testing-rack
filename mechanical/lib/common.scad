// Shared helpers for every printed part of hw-testing-rack.
include <../generated/config.scad>

$fn = $preview ? 32 : 64;
EPS = 0.01;

// Heat-set inserts (Ruthex-style).  Hole Ø is the recommended pre-hole.
INSERT_M3 = [4.0, 5.7];    // [hole Ø, depth]
INSERT_M2 = [3.2, 4.0];
INSERT_M25 = [3.6, 4.5];
M3_CLEAR = 3.4;
M5_CLEAR = 5.5;
M3_HEAD = [6.0, 3.0];      // DIN 912 / ISO 7380 head Ø × height (button head ~5.7)

module rbox(size, r = 2, center = false) {
    // Box with rounded vertical edges.
    translate(center ? [-size[0] / 2, -size[1] / 2, 0] : [0, 0, 0])
        hull() for (x = [r, size[0] - r], y = [r, size[1] - r])
            translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

module rslot(len, w, h) {
    // Stadium-shaped slot along X, centred on the origin.
    hull() for (x = [-(len - w) / 2, (len - w) / 2]) translate([x, 0, 0]) cylinder(d = w, h = h);
}

module insert_hole(spec = INSERT_M3) {
    // Pocket for a heat-set insert, opening at z=0 and going -Z.
    translate([0, 0, -spec[1]]) cylinder(d = spec[0], h = spec[1] + EPS);
    translate([0, 0, -0.6]) cylinder(d1 = spec[0], d2 = spec[0] + 0.8, h = 0.6 + EPS);
}

module screw_through(d = M3_CLEAR, h = 20, head = M3_HEAD, counterbore = true) {
    // Clearance hole along +Z from z=0, with an optional counterbore at z=h.
    translate([0, 0, -EPS]) cylinder(d = d, h = h + 2 * EPS);
    if (counterbore) translate([0, 0, h - head[1]]) cylinder(d = head[0] + 0.4, h = head[1] + EPS);
}

module magnet_pocket(d = DRAWER_MAGNET[0], t = DRAWER_MAGNET[1]) {
    // Press-fit/glue pocket for a disc magnet, opening at z=0 going -Z.
    translate([0, 0, -t - 0.2]) cylinder(d = d + 0.25, h = t + 0.2 + EPS);
}

module label_text(txt, size = 6, depth = 0.6, font = "Liberation Sans:style=Bold") {
    linear_extrude(depth) text(txt, size = size, font = font, halign = "center", valign = "center");
}

// 2020 B-type profile, simplified (good enough for previews and clearance checks).
module extrusion2020(len) {
    s = FRAME_PROFILE;
    difference() {
        translate([-s / 2, -s / 2, 0]) cube([s, s, len]);
        for (a = [0, 90, 180, 270]) rotate([0, 0, a])
            translate([s / 2 - 1.8, -3, -EPS]) {
                cube([1.8 + EPS, 6, len + 2 * EPS]);
                translate([-4.2, -2.6, 0]) cube([4.3, 11.2, len + 2 * EPS]);
            }
        translate([0, 0, -EPS]) cylinder(d = 4.2, h = len + 2 * EPS);
    }
}
