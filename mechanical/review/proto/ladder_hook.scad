// Review proto (not a part): one of a ladder's stacking hooks in its receiving slot, today (the beam's root
// 7 mm inside the band, square relief ends: 2.0 % at the root, 56 MPa in the FEM) and proposed (root 10 mm,
// R0.6 at the relief's ends: 1.3 %, the corner factor ≈ 1.2).  The profile is the ladder's (printed flat):
// the hook bends in the print plane.  docs/printed-parts-review.md › Ladder.
//
//   openscad -D 'VIEW="today"' -o ladder_hook_today.png mechanical/review/proto/ladder_hook.scad
VIEW = "today";
T = 7.4; HOOK_W = 2.6; HOOK_DROP = 9; HOOK_BARB = 1.0; HOOK_NECK = 4; BAND = 14;
$fn = 32;

module hook_2d() {
    translate([-HOOK_W / 2, -HOOK_DROP]) square([HOOK_W, HOOK_DROP + 0.01]);
    polygon([[HOOK_W / 2 - 0.01, -(HOOK_NECK + 0.3)], [HOOK_W / 2 + HOOK_BARB, -(HOOK_NECK + 0.3)],
             [HOOK_W / 2 + HOOK_BARB, -(HOOK_DROP - 2.5)], [HOOK_W / 2 - 0.01, -HOOK_DROP]]);
}
module relief_2d(root, r) for (s = [-1, 1]) translate([s > 0 ? HOOK_W / 2 : -HOOK_W / 2 - 1, -0.5])
    if (r > 0) hull() { translate([0.5, 0]) square([0.01, 0.01]); translate([0.5, root + 0.5 - r]) circle(r = 0.5); translate([0, 0]) square([1, 0.01]); }
    else square([1, root + 0.5]);
// a slice of the upper ladder's bottom band with one hook (y > 0 the band, the hook hangs below)
module upper(root, r) linear_extrude(T) difference() {
    union() { translate([-8, 0]) square([16, BAND]); hook_2d(); }
    relief_2d(root, r);
}
// the lower ladder's top band with the slot (drawn 0.3 mm lower for the joint's ridge)
module lower() color("#8fa8c8") translate([0, -0.3, 0]) linear_extrude(T) difference() {
    translate([-8, -BAND]) square([16, BAND]);
    translate([-HOOK_W / 2 - 1.2, -HOOK_NECK - 0.01]) square([HOOK_W + 1.4, HOOK_NECK + 1]);
    translate([-HOOK_W / 2 - 1.2, -(HOOK_DROP + 1)]) square([HOOK_W + 1.2 + HOOK_BARB + 1.0, HOOK_DROP + 1 - HOOK_NECK]);
}

if (VIEW == "today") { color("#a9c4e4") upper(7, 0); lower(); }
else { color("#a9c4e4") upper(10, 0.6); lower(); }
