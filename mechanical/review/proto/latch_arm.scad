// Review proto (not a part): a tray's side wall around its latch arm, seen from outside (the runner and the
// barb), today (arm 26 mm between 1 mm square-ended slots: 1.1 %, the FEM's 52 MPa sits in the slot's corner)
// and proposed (arm 32 mm, the slots' ends rounded R0.5: 0.75 %).  docs/printed-parts-review.md › Tray.
//
//   openscad -D 'VIEW="today"' -o latch_arm_today.png mechanical/review/proto/latch_arm.scad
VIEW = "today";
WALL = 2; RUNNER_OUT = 2.3; RZ = [8, 13]; BARB = 1.2; SLOT = 1.0; LY = 30; L = 60; H = 20.1;
$fn = 24;
module wall_slice(arm, r) {
    rh = RZ[1] - RZ[0];
    difference() {
        union() {
            cube([WALL, L, H]);
            translate([-RUNNER_OUT, 0, RZ[0]]) cube([RUNNER_OUT + 0.01, L, rh]);
            translate([-RUNNER_OUT, LY, RZ[0]]) hull() {
                translate([-0.01, 0, 0]) cube([0.01, 4, rh]);
                translate([-BARB, 0, 0]) cube([BARB, 1.5, rh]);
            }
        }
        // the vertical slot in front of the barb, and the two horizontal slots over the arm
        slot([-RUNNER_OUT - BARB - 1, LY - SLOT, RZ[0] - SLOT], [WALL + RUNNER_OUT + BARB + 2, SLOT, rh + 2 * SLOT], r, "y");
        for (z = [RZ[0] - SLOT, RZ[1]])
            slot([-RUNNER_OUT - 1, LY - SLOT, z], [WALL + RUNNER_OUT + 2, arm + SLOT, SLOT], r, "z");
    }
}
// a slot cutter: a box, its far ends rounded (r) in the plane of the wall
module slot(p, s, r, axis) translate(p)
    if (r <= 0) cube(s);
    else if (axis == "z") hull() for (y = [r, s[1] - r]) translate([0, y, 0]) rotate([0, 90, 0]) translate([-s[2] / 2, 0, 0]) cylinder(r = r, h = s[0]);
    else cube(s);

if (VIEW == "today") color("#a9c4e4") wall_slice(26, 0);
else color("#a9c4e4") wall_slice(32, 0.5);
