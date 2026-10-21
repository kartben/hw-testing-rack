// Review proto (not a part): a tray's side wall around its latch arm, seen from outside, with the ladder's
// groove core and its window in front of it (grey, translucent): the barb clicks into that window.  Today:
// arm 26 mm between 1 mm slots with square ends, 1.1 % for the 1.2 mm barb (fine for repeated use), but the
// FEM's 52 MPa sits in the slot's corner.  Proposed (accent): arm 32 mm, the slots' ends R0.5: 0.75 %.
// (OpenCSG preview: the accent piece is drawn as its own geometry, no intersection.)
// docs/printed-parts-review.md › Tray.
//
//   openscad -D 'VIEW="today"' -o latch_arm_today.png mechanical/review/proto/latch_arm.scad
include <_review.scad>
VIEW = "today";
WALL = 2; RUNNER_OUT = 2.3; RZ = [8, 13]; BARB = 1.2; SLOT = 1.0; LY = 30; L = 64; H = 20.1;
CORE = 2.6; CLEAR = 0.2; WIN = 6;
$fn = 24;
RH = RZ[1] - RZ[0];
module barb() translate([-RUNNER_OUT, LY, RZ[0]]) hull() { translate([-0.01, 0, 0]) cube([0.01, 4, RH]); translate([-BARB, 0, 0]) cube([BARB, 1.5, RH]); }
module wall_body() union() {
    cube([WALL, L, H]);
    translate([-RUNNER_OUT, 0, RZ[0]]) cube([RUNNER_OUT + 0.01, L, RH]);
    barb();
}
module slot_y() translate([-RUNNER_OUT - BARB - 1, LY - SLOT, RZ[0] - SLOT]) cube([WALL + RUNNER_OUT + BARB + 2, SLOT, RH + 2 * SLOT]);
module slot_z(arm, r, z) translate([-RUNNER_OUT - 1, LY - SLOT, z])
    if (r <= 0) cube([WALL + RUNNER_OUT + 2, arm + SLOT, SLOT]);
    else hull() for (y = [r, arm + SLOT - r]) translate([0, y, SLOT / 2]) rotate([0, 90, 0]) cylinder(r = r, h = WALL + RUNNER_OUT + 2);
module cuts(arm, r) { slot_y(); slot_z(arm, r, RZ[0] - SLOT); slot_z(arm, r, RZ[1]); }
// the arm itself: the wall strip and the runner strip between the slots, and the barb
module arm_box(arm) translate([-RUNNER_OUT - BARB - 0.5, LY, RZ[0]]) cube([WALL + RUNNER_OUT + BARB + 0.5, arm, RH]);
module arm_piece(arm) { translate([0, LY, RZ[0]]) cube([WALL, arm, RH]); translate([-RUNNER_OUT, LY, RZ[0]]) cube([RUNNER_OUT + 0.01, arm, RH]); barb(); }
// the ladder's groove core (between its two grooves), with the latch window the barb catches in
module groove_core() mate(0.4) translate([-RUNNER_OUT - CLEAR - 0.1 - CORE, 0, RZ[0] - 0.15]) difference() {
    cube([CORE, L, RH + 0.3]);
    translate([-1, LY - 0.2, -1]) cube([CORE + 2, WIN, RH + 2]);
}

if (VIEW == "today") { part() difference() { wall_body(); cuts(26, 0); } groove_core(); }
else {
    part() difference() { wall_body(); cuts(32, 0.5); arm_box(32); }
    changed() arm_piece(32);
    groove_core();
}
