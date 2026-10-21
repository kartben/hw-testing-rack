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
// The rack's four screw types (docs/printed-parts-review.md, finding 13): M3 × 8 into inserts, nuts and
// spacers; PT 2.3 × 8 thread-forming into printed pilots; the M3 spacers; M2.5 washers
PT_PILOT = 1.9;            // a PT 2.3's pilot (≈ 0.8 × d)
PT_CLEAR = 2.6;            // and its clearance hole

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

module insert_hole(spec = INSERT_M3, runout = 0) {
    // Pocket for a heat-set insert, opening at z=0 and going -Z; `runout`: an M3 clearance hole that
    // carries on past it, so an M3 × 8 that goes deeper than the insert doesn't bottom on the plastic
    translate([0, 0, -spec[1]]) cylinder(d = spec[0], h = spec[1] + EPS);
    translate([0, 0, -0.6]) cylinder(d1 = spec[0], d2 = spec[0] + 0.8, h = 0.6 + EPS);
    if (runout > 0) translate([0, 0, -spec[1] - runout]) cylinder(d = M3_CLEAR, h = runout + EPS);
}

module screw_through(d = M3_CLEAR, h = 20, head = M3_HEAD, counterbore = true) {
    // Clearance hole along +Z from z=0, with an optional counterbore at z=h.
    translate([0, 0, -EPS]) cylinder(d = d, h = h + 2 * EPS);
    if (counterbore) translate([0, 0, h - head[1]]) cylinder(d = head[0] + 0.4, h = head[1] + EPS);
}

module magnet_pocket(d = DRAWER_MAGNET[0], t = DRAWER_MAGNET[1]) {
    // Slip-fit pocket for a glued disc magnet (docs/mechanical.md), opening at z=0 going -Z.
    translate([0, 0, -t - 0.2]) cylinder(d = d + 0.25, h = t + 0.2 + EPS);
}

module label_text(txt, size = 6, depth = 0.6, font = "Liberation Sans:style=Bold") {
    linear_extrude(depth) text(txt, size = size, font = font, halign = "center", valign = "center");
}


// ---------------------------------------------------------------- the visual language
// One set of rules for every part (docs/printed-parts-review.md › The visual language): R3 on the outer
// vertical edges of big parts, R1.5 on small ones; a 0.5 × 45° chamfer on the visible bed edges (it hides the
// elephant's foot); a 0.8 round on free top edges; text debossed 0.6 mm in Liberation Sans Bold, capitals at
// least 4.5 mm on a horizontal face, 5.5 on a vertical one.
VL_R = [3, 1.5];
VL_CHAMFER = 0.5;
VL_FILLET = 0.8;
VL_DEPTH = 0.6;
function vl_size(cap) = cap / 0.955;      // OpenSCAD's text size for a capital height (Liberation Sans Bold)

// cutters for a straight edge along +X from the origin, `len` long, between the faces y = 0 and z = 0 with
// the material at y >= 0, z >= 0: a 45° chamfer c, or a round of radius r.  Rotate / mirror them onto an edge
module edge_chamfer(len, c = VL_CHAMFER) translate([-EPS, 0, 0]) rotate([90, 0, 90]) linear_extrude(len + 2 * EPS)
    polygon([[-1, -1], [c, -1], [c, -EPS], [-EPS, c], [-1, c]]);
module edge_round(len, r = VL_FILLET) translate([-EPS, 0, 0]) rotate([90, 0, 90]) linear_extrude(len + 2 * EPS)
    difference() { translate([-1, -1]) square([r + 1, r + 1]); translate([r, r]) circle(r = r, $fn = 32); }

// text debossed into a face: lay it in the XY plane at the face (z = 0), reading from +Z; it goes `depth` down
module deboss(t, cap = 4.5, depth = VL_DEPTH, halign = "center", valign = "center")
    translate([0, 0, -depth]) linear_extrude(depth + EPS)
        text(t, size = vl_size(cap), font = "Liberation Sans:style=Bold", halign = halign, valign = valign);
