// Rear brace — an X behind each bay, one per row (and one in the base), for the panel frame.
//
//   openscad -D ROW=0  -o brace_a.stl    parts/brace.scad    (row A; ROW=-1: the base)
//
// Without it the grid of ladders and trays sways sideways like a shelf without a back panel.
// tools/panel_frame_fea.py shows that what matters is slack, not stiffness: with taut braces
// the runner play in the trays no longer counts (0.16 mm of sway under 2 N on a 4 × 4).  So
// the brace has none: four M3 × 8 button-head screws go through snug 3.1 mm holes into heat-set
// inserts in the rear edges of its two ladders, and each diagonal is BRACE_PRELOAD shorter than
// its inserts' spacing, so the X is in tension once the fourth screw is in.  That tension
// (~2 MPa in the strap) relaxes to about half over the years and stays positive; the clamped
// screws keep the joints free of play for good.  The holes sit at different heights on the
// left and on the right, so the next bay's brace uses the other two inserts of the shared
// ladder.  Print: flat, PETG, 100 % (it is mostly perimeter).
include <../lib/panels.scad>

ROW = 0;

module brace(k) {
    z = brace_z(k);
    // corners: left ladder (x = 0) uses z[0], z[2]; right ladder (x = pitch) z[1], z[3]
    n = [[0, z[0]], [0, z[2]], [PANEL_PITCH, z[1]], [PANEL_PITCH, z[3]]];       // insert positions
    // each hole moves BRACE_PRELOAD / 2 towards its partner: screwed in, the diagonal is in tension
    pull = function (p, q) p + (q - p) / norm(q - p) * BRACE_PRELOAD / 2;
    c = [pull(n[0], n[3]), pull(n[1], n[2]), pull(n[2], n[1]), pull(n[3], n[0])];
    linear_extrude(BRACE_T) difference() {
        union() {
            for (s = [[c[0], c[3]], [c[1], c[2]]]) hull() for (p = s) translate(p) circle(d = XBRACE_W, $fn = 24);
            for (p = c) translate(p) circle(d = 11, $fn = 32);
        }
        for (p = c) translate(p) circle(d = BRACE_SCREW_HOLE, $fn = 24);
    }
}

brace(ROW);
