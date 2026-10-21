// Review proto (not a part): one of a ladder's stacking hooks seated in the slot of the ladder below (grey),
// seen flat as the ladders print.  Today: the beam's root 7 mm inside the band, square relief ends: 2.0 % at
// the root for the 0.8 mm the barb gives, 56 MPa in the FEM.  Proposed (accent): root 10 mm, R0.6 at the
// relief's ends: 1.3 %, the corner factor ≈ 1.2.  docs/printed-parts-review.md › Ladder.
//
//   openscad -D 'VIEW="today"' -o ladder_hook_today.png mechanical/review/proto/ladder_hook.scad
include <_review.scad>
VIEW = "today";
T = 7.4; HOOK_W = 2.6; HOOK_DROP = 9; HOOK_BARB = 1.0; HOOK_NECK = 4; BAND = 14;
$fn = 32;
module hook_2d() {
    translate([-HOOK_W / 2, -HOOK_DROP]) square([HOOK_W, HOOK_DROP + 0.01]);
    polygon([[HOOK_W / 2 - 0.01, -(HOOK_NECK + 0.3)], [HOOK_W / 2 + HOOK_BARB, -(HOOK_NECK + 0.3)],
             [HOOK_W / 2 + HOOK_BARB, -(HOOK_DROP - 2.5)], [HOOK_W / 2 - 0.01, -HOOK_DROP]]);
}
module relief_2d(root, r) for (s = [-1, 1]) translate([s > 0 ? HOOK_W / 2 : -HOOK_W / 2 - 1, -0.5])
    if (r > 0) hull() { square([1, 0.01]); translate([0.5, root + 0.5 - r]) circle(r = 0.5); }
    else square([1, root + 0.5]);
module upper_2d(root, r) difference() { union() { translate([-9, 0]) square([18, BAND]); hook_2d(); } relief_2d(root, r); }
module upper(root, r) linear_extrude(T) upper_2d(root, r);
module hook_region_2d(root) translate([-HOOK_W / 2 - 1.2, -HOOK_DROP - 0.5]) square([HOOK_W + 2.4 + HOOK_BARB, HOOK_DROP + root + 1.5]);
module lower() mate(0.7) translate([0, -0.3, 0]) linear_extrude(T) difference() {
    translate([-9, -BAND]) square([18, BAND]);
    translate([-HOOK_W / 2 - 1.2, -HOOK_NECK - 0.01]) square([HOOK_W + 1.4, HOOK_NECK + 1]);
    translate([-HOOK_W / 2 - 1.2, -(HOOK_DROP + 1)]) square([HOOK_W + 1.2 + HOOK_BARB + 1.0, HOOK_DROP + 1 - HOOK_NECK]);
}

if (VIEW == "today") { part() upper(7, 0); lower(); }
else {
    part() linear_extrude(T) difference() { upper_2d(10, 0.6); hook_region_2d(10); }
    changed() linear_extrude(T) intersection() { upper_2d(10, 0.6); hook_region_2d(10); }
    lower();
}
