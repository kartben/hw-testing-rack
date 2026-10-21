// Review proto (not a part): the DATA ×4 v2 cradle's left upright, its top 34 mm, with the board's end in
// its slot, seen from behind the cradle (the latch finger is the rear wall's top).  Today: 24 mm free, 1.0
// hook, a 0.6 slit, a square root: it bends across the layers at 0.72 % on every board swap (FEM 29 MPa),
// allowed 0.5 %.  Proposed (accent): 40 mm free, 0.8 hook, 1.0 slit, R0.8 at the root: 0.25 %.
// docs/printed-parts-review.md › Cradle.
//
//   openscad -D 'VIEW="today"' -o cradle_finger_today.png mechanical/review/proto/cradle_finger.scad
include <_review.scad>
VIEW = "today";
GAP = 0.15; UW = 2.4; OW = 1.2; END = 5.5; H = 72.6; T = 1.6;
X1 = 0.5 + OW + END;                 // the upright's inner end
YB = UW + 2 * GAP + T;               // the rear wall's inner face
TOP_H = 34;                          // the slice shown
module slot() translate([OW + 0.5, UW, -1]) cube([END + 1, 2 * GAP + T, H + 2]);
module slit(latch, slit) translate([OW, YB - 0.01, H - latch]) cube([slit, UW + 1, latch + 1]);
module root_fillet(latch, slit, fillet) translate([OW + slit + fillet, YB - 0.01, H - latch]) rotate([-90, 0, 0])
    difference() { translate([-fillet, 0, 0]) cube([fillet, fillet, UW + 1]); translate([0, fillet, 0]) cylinder(r = fillet, h = UW + 1, $fn = 32); }
module hook(hook, slit) translate([OW + slit, 0, H]) rotate([90, 0, 90]) linear_extrude(X1 - OW - slit)
    polygon([[YB + UW, 0], [YB, 0], [YB, 0.2], [YB - GAP - hook, 0.2], [YB - GAP - hook, 0.6], [YB, 1.6 + hook], [YB + UW, 1.6 + hook]]);
module finger_box(latch, slit) translate([OW + slit - 0.01, YB - 0.01, H - latch]) cube([X1, UW + 1, latch + 1]);
module finger_piece(latch, hook_h, slit) { translate([OW + slit, YB, H - latch]) cube([X1 - OW - slit, UW, latch]); hook(hook_h, slit); }
module below() translate([-5, -5, -1]) cube([50, 30, H - TOP_H + 1]);     // removed: the slice shows the top only
module board() color(PCB, 0.75) translate([OW + 0.5 + 0.3, UW + GAP, H - TOP_H]) cube([END + 9, T, TOP_H]);

if (VIEW == "today") { part() difference() { union() { cube([X1, YB + UW, H]); hook(1.0, 0.6); } slot(); slit(24, 0.6); below(); } board(); }
else {
    part() difference() { cube([X1, YB + UW, H]); slot(); slit(40, 1.0); root_fillet(40, 1.0, 0.8); finger_box(40, 1.0); below(); }
    changed() difference() { finger_piece(40, 0.8, 1.0); below(); }
    board();
}
