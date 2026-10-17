// Rear brace — an X behind each bay, one per row (and one in the base), for the panel frame.
//
//   openscad -D ROW=0  -o brace_a.stl    parts/brace.scad    (row A; ROW=-1: the base)
//
// Without it the grid of ladders and trays sways sideways like a shelf without a back panel:
// the posts bend on their 7.4 mm side.  Two 8 × 3 mm diagonals turn each bay into a braced
// frame (about ten times stiffer) and still leave the rear open for cables and air.  Four
// split snap pins push into the holes in the rear edges of the two ladders; the pins sit at
// different heights on the left and on the right, so the next bay's brace uses the other two
// holes of the shared ladder.  Print: flat, pins up, PETG, 100 % (it is mostly perimeter).
include <../lib/panels.scad>

ROW = 0;

module snap_pin() {
    d = BRACE_PIN[0];
    l = BRACE_PIN[1];
    difference() {
        union() {
            cylinder(d = d, h = l - 1.2, $fn = 24);
            translate([0, 0, l - 2.6]) cylinder(d1 = d + 0.7, d2 = d - 0.6, h = 2.6, $fn = 24);   // barb
        }
        translate([-0.5, -d, 2.5]) cube([1.0, 2 * d, l]);                                    // split
    }
}

module brace(k) {
    z = brace_z(k);
    // corners: left ladder (x = 0) uses z[0], z[2]; right ladder (x = pitch) z[1], z[3]
    c = [[0, z[0]], [0, z[2]], [PANEL_PITCH, z[1]], [PANEL_PITCH, z[3]]];
    linear_extrude(BRACE_T) {
        for (s = [[c[0], c[3]], [c[1], c[2]]]) hull() for (p = s) translate(p) circle(d = XBRACE_W, $fn = 24);
        for (p = c) translate(p) circle(d = 11, $fn = 32);
    }
    for (p = c) translate([p[0], p[1], BRACE_T]) snap_pin();
}

brace(ROW);
