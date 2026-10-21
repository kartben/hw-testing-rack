// Review proto (not a part): the DATA ×4 v2 cradle's left upright with its latch finger, today (24 mm
// free, 1.0 mm hook, a square root) and proposed (40 mm free, 0.8 mm hook, an R0.8 root, a 1.0 mm slit).
// The finger stands along the layers and bends across them, so it needs the lowest strain of all the
// rack's snaps: 0.72 % today at its root, 0.25 % proposed (docs/printed-parts-review.md › Cradle).
//
//   openscad -D 'VIEW="both"' -o cradle_finger.png mechanical/review/proto/cradle_finger.scad
VIEW = "both";
GAP = 0.15; UW = 2.4; OW = 1.2; END = 5.5; H = 72.6; T = 1.6;   // the board 1.6 thick
SLIT = 0.6;
module upright(latch = 24, hook = 1.0, slit = 0.6, fillet = 0) {
    x1 = 0.5 + OW + END;            // the upright's inner end
    difference() {
        cube([x1, UW + 2 * GAP + T + UW, H]);
        translate([OW + 0.5, UW, -1]) cube([END + 1, 2 * GAP + T, H + 2]);          // the slot the board's end sits in
        translate([OW, UW + 2 * GAP + T - 0.01, H - latch]) cube([slit, UW + 1, latch + 1]);   // the slit freeing the finger
        if (fillet) translate([OW + slit + fillet, UW + 2 * GAP + T - 0.01, H - latch]) rotate([-90, 0, 0])
            difference() { translate([-fillet, 0, 0]) cube([fillet, fillet, UW + 1]); translate([0, fillet, 0]) cylinder(r = fillet, h = UW + 1, $fn = 32); }
    }
    // the hook over the board's top edge, 45° lead-in on top
    yb = UW + 2 * GAP + T;
    translate([OW + slit, 0, H]) rotate([90, 0, 90]) linear_extrude(x1 - OW - slit)
        polygon([[yb + UW, 0], [yb, 0], [yb, 0.2], [yb - GAP - hook, 0.2], [yb - GAP - hook, 0.6], [yb, 1.6 + hook], [yb + UW, 1.6 + hook]]);
}
module board() color("#2f6f4f") translate([OW + 0.5 + 0.3, UW + GAP, 0]) cube([END + 6, T, H]);
// the top 36 mm only: the finger is what matters
module top(h = 36) intersection() { children(); translate([-1, -1, H - h]) cube([40, 20, h + 5]); }

if (VIEW == "today" || VIEW == "both") top() { color("#a9c4e4") upright(); board(); }
if (VIEW == "proposed" || VIEW == "both") translate([VIEW == "both" ? 22 : 0, 0, 0]) top() { color("#a9c4e4") upright(40, 0.8, 1.0, 0.8); board(); }
