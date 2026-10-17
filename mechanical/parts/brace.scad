// Rear brace — an X behind each bay, one per row (and one in the base), for the panel frame.
//
//   openscad -D ROW=0  -o brace_a.stl    parts/brace.scad    (row A; ROW=-1: the base)
//
// Without it the grid of ladders and trays sways sideways like a shelf without a back panel.
// tools/panel_frame_fea.py shows that what matters is slack, not stiffness: with taut braces
// the runner play in the trays no longer counts (0.16 mm of sway under 2 N on a 4 × 4).  So
// the brace has none: its split pins are 0.2 mm over the hole (squeezed shut when pushed in)
// and each diagonal is BRACE_PRELOAD shorter than its holes' spacing, so the X is in tension
// once fitted.  That tension (~2 MPa in the strap) relaxes to about half over the years and
// stays positive.  The pins sit at different heights on the left and on the right, so the next
// bay's brace uses the other two holes of the shared ladder.  Print: flat, pins up, PETG, 100 % (it is mostly perimeter).
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
    n = [[0, z[0]], [0, z[2]], [PANEL_PITCH, z[1]], [PANEL_PITCH, z[3]]];       // nominal (hole) positions
    // each pin moves BRACE_PRELOAD / 2 towards its partner: fitted, the diagonal is in tension
    pull = function (p, q) p + (q - p) / norm(q - p) * BRACE_PRELOAD / 2;
    c = [pull(n[0], n[3]), pull(n[1], n[2]), pull(n[2], n[1]), pull(n[3], n[0])];
    linear_extrude(BRACE_T) {
        for (s = [[c[0], c[3]], [c[1], c[2]]]) hull() for (p = s) translate(p) circle(d = XBRACE_W, $fn = 24);
        for (p = c) translate(p) circle(d = 11, $fn = 32);
    }
    for (p = c) translate([p[0], p[1], BRACE_T]) snap_pin();
}

brace(ROW);
